"""判定器相关的命令：评估（``screen-eval``）与分诊（``triage``）。

单独成文件，因为这些命令和 ``cli.py`` 里的检索流水线关注点不同：
流水线命令回答"找到了什么"，这些命令回答"判得准不准、该先看哪几条"。
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from pathlib import Path
from urllib.parse import urlsplit

import typer

from litsearch.adjudicate import AdjudicationError, apply_machine
from litsearch.cli_support import (
    DEFAULT_RUNS_ROOT,
    finish_screening_round,
    load_latest_decisions,
    load_round,
    load_topic_or_exit,
    open_compatible_run_or_exit,
)
from litsearch.dedupe import CanonicalRecord
from litsearch.jev_client import JevFatalError, build_jev_client
from litsearch.jev_profile import JevProfile, load_profile
from litsearch.protocol import ProtocolError, Topic, freeze_topic, protocol_fingerprint
from litsearch.providers import describe as describe_provider
from litsearch.providers import resolve_provider
from litsearch.run import Run
from litsearch.screen import (
    MergedDecision,
    ScreeningRound,
    render_human_queue,
    summarize,
)
from litsearch.screen_commit import BackendResult, included_rows
from litsearch.screen_eval import (
    disagreements_csv,
    predictions_from_round,
    predictions_from_scores,
    reference_from_round,
    render_markdown,
    sweep,
)
from litsearch.screen_jev import (
    ScoreRow,
    compile_questions,
    estimate_jev,
    gold_set_violations,
    pending_records,
    questions_sha256,
    render_triage_queue,
    route_all,
    score_records,
    tiebreak_candidates,
)
from litsearch.sources.registry import Credentials

#: 扫排除带时默认试的阈值。覆盖"几乎不自动排除"到"排除带很宽"两端。
DEFAULT_SWEEP_GRID = (0.02, 0.05, 0.10, 0.20, 0.30)


def gold_keys_in(records: Sequence[CanonicalRecord], topic: Topic) -> frozenset[str]:
    """金标种子在本 run 语料里对应的 record_key。

    金标是按标识符声明的，语料里是按合并后的 key 存的——不映射就永远对不上，
    "金标有没有被误排"这个问题也就检查不了。
    """
    wanted = {
        (kind, value) for seed in topic.gold_set for kind, value in seed.identifiers.items()
    }
    return frozenset(
        item.key
        for item in records
        if any((kind, value) in wanted for kind, value in item.identifiers.items())
    )


def _read_scores(run_dir: Run, name: str, score_keys: str | None) -> dict[str, float]:
    """读打分文件。判定器无关：认 ``score`` 字段，也认 ``answers`` 字典。

    ``answers`` + ``--score-keys I1,I2`` 取这几项的**最小值**——多条纳入标准要同时
    满足，合取的自然读法是取最小，而不是求平均（平均会让一条严重不满足的标准
    被另一条高分掩盖）。
    """
    path = run_dir.root / name
    if not path.exists():
        typer.secho(f"打分文件不存在：{path}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)
    wanted = [item.strip() for item in score_keys.split(",")] if score_keys else None
    scores: dict[str, float] = {}
    for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        key = row["record_key"]
        if "score" in row:
            scores[key] = float(row["score"])
            continue
        answers = row.get("answers") or {}
        picked = wanted or sorted(answers)
        missing = [item for item in picked if item not in answers]
        if missing:
            typer.secho(
                f"{path.name} 第 {index} 行缺少打分项 {missing}", fg=typer.colors.RED, err=True
            )
            raise typer.Exit(code=2)
        if not picked:
            typer.secho(f"{path.name} 第 {index} 行没有任何打分项", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=2)
        scores[key] = min(float(answers[item]) for item in picked)
    return scores


def _sweep_markdown(scores: Mapping[str, float], ref, include_at: float) -> str:
    rows = sweep(scores, ref, grid=DEFAULT_SWEEP_GRID, include_at=include_at)
    lines = [
        "### 排除带阈值扫描",
        "",
        f"纳入带固定在 {include_at}。每行的代价是「不可逆漏排」，收益是「队列更短」。",
        "",
        "| exclude_below | 不可逆漏排 | 人工队列 | 自动纳入精度 | 自动排除 NPV |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        hit = row.auto_include_precision
        npv_value = row.auto_exclude_npv
        precision = "—" if hit is None else f"{hit:.1%}"
        npv = "—" if npv_value is None else f"{npv_value:.1%}"
        lines.append(
            f"| {row.exclude_below:.2f} | **{row.missed}** | {row.queued} | {precision} | {npv} |"
        )
    return "\n".join(lines) + "\n"


def screen_eval_command(
    run: str = typer.Argument(..., help="run 目录、<topic>/<run_id>，或 <topic> 取最新"),
    topic: Path = typer.Option(..., "--topic", help="课题协议 YAML"),
    reference_round: int = typer.Option(
        ..., "--reference-round", help="当作参考标签的轮次（通常是经过人工裁决的最后一轮）"
    ),
    candidate_round: int | None = typer.Option(
        None, "--candidate-round", help="被评估的轮次"
    ),
    candidate_scores: str | None = typer.Option(
        None, "--candidate-scores", help="被评估的打分文件名（run 目录内），如 jev_scores.jsonl"
    ),
    score_keys: str | None = typer.Option(
        None, "--score-keys", help="打分文件用 answers 字典时，取哪几项的最小值，逗号分隔"
    ),
    include_at: float = typer.Option(0.7, "--include-at", help="打分 ≥ 此值自动纳入"),
    exclude_below: float = typer.Option(0.1, "--exclude-below", help="打分 < 此值自动排除"),
    runs_root: Path = typer.Option(DEFAULT_RUNS_ROOT, "--runs-root"),
) -> None:
    """评估一个判定器：对照参考轮次报精度、校准与分歧清单。

    不打任何网络请求——评的是已经落盘的判定或打分。
    """
    if (candidate_round is None) == (candidate_scores is None):
        typer.secho(
            "必须且只能给一个被评估对象：--candidate-round 或 --candidate-scores",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=2)

    loaded = load_topic_or_exit(topic)
    run_dir = open_compatible_run_or_exit(runs_root, run, loaded, topic)
    records = [CanonicalRecord.model_validate(row) for row in run_dir.read_jsonl("corpus.jsonl")]
    if not records:
        typer.secho("corpus.jsonl 为空，先跑 lit harvest", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)

    reference = reference_from_round(
        load_round(run_dir, reference_round), gold_keys=gold_keys_in(records, loaded)
    )
    if not reference.labels:
        typer.secho(
            f"第 {reference_round} 轮没有任何已定结论（全部仍在人工队列），无法当参考标签",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=2)

    inputs = [f"screening_round_{reference_round}.json"]
    scores: dict[str, float] = {}
    if candidate_round is not None:
        label = f"round{candidate_round}"
        preds = predictions_from_round(load_round(run_dir, candidate_round))
        inputs.append(f"screening_round_{candidate_round}.json")
    else:
        label = Path(candidate_scores).stem
        scores = _read_scores(run_dir, candidate_scores, score_keys)
        preds = predictions_from_scores(
            scores, include_at=include_at, exclude_below=exclude_below
        )
        inputs.append(candidate_scores)

    stem = f"screen_eval_{label}_vs_round{reference_round}"
    report = render_markdown(
        title=f"{label} 对照第 {reference_round} 轮", preds=preds, ref=reference, scores=scores
    )
    if scores:
        report += "\n" + _sweep_markdown(scores, reference, include_at)
    report_path = run_dir.write_artifact(f"{stem}.md", report, inputs=inputs)

    by_key = {item.key: item for item in records}
    csv_path = run_dir.write_artifact(
        f"{stem}_disagreements.csv", disagreements_csv(preds, reference, by_key), inputs=inputs
    )

    _echo_summary(preds, reference, report_path, csv_path)


def _echo_summary(preds, reference, report_path: Path, csv_path: Path) -> None:
    from litsearch.screen_eval import confusion

    overall = confusion(preds, reference)
    gold = confusion(preds, reference, tier="gold")
    typer.echo(
        f"\n参考标签 {overall.total:,} 条（金标 {gold.total:,}）"
        f"｜不可逆漏排 {overall.missed}"
        f"｜人工队列 {overall.queued:,}"
        f"（{overall.queue_rate:.1%}）"
    )
    if overall.must_keep_violations:
        typer.secho(
            f"金标种子被自动排除：{'、'.join(overall.must_keep_violations)}",
            fg=typer.colors.RED,
            err=True,
        )
    disagreements = max(0, len(csv_path.read_text(encoding="utf-8").splitlines()) - 1)
    typer.echo(f"报告 {report_path}")
    typer.echo(f"分歧清单 {csv_path}（{disagreements:,} 条，填好可直接 lit adjudicate）")


JEV_SCORES = "jev_scores.jsonl"
JEV_SCORES_TRIAL = "jev_scores_trial.jsonl"
#: 每打这么多条就落一次盘。上万条要跑二十多分钟，中途断掉不该全部重来。
CHECKPOINT_EVERY = 200
#: 失败率超过这个比例就不写轮次——打分留着供续跑，但这一轮不能当结果用。
MAX_FAILURE_RATE = 0.05


def _load_scores(run_dir: Run, name: str) -> dict[str, ScoreRow]:
    return {
        row["record_key"]: ScoreRow.from_json(row) for row in run_dir.read_jsonl(name)
    }


def _require_profile(profile_path: Path | None, topic: Topic) -> JevProfile:
    if profile_path is None:
        typer.secho(
            "--model jev 必须同时给 --jev-profile。阈值是逐课题调出来的，"
            f"没有通用默认值——实测同一套阈值在一个课题上把人工队列从 18.3% 压到 8.1%，"
            f"在另一个课题上反而比现有 LLM 更差。约定路径：topics/{topic.id}.jev.yaml",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=2)
    try:
        return load_profile(profile_path, topic)
    except ProtocolError as error:
        typer.secho(str(error), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2) from error


def _echo_dry_run(topic: Topic, profile: JevProfile, provider, pending, questions: dict) -> None:
    estimate = estimate_jev(topic, profile, pending)
    cost = estimate.usage.cost(provider.pricing)
    typer.echo(f"\n待打分记录       {estimate.records:,}")
    typer.echo(f"后端             {describe_provider(provider)}")
    typer.echo(f"问题数           {len(questions)}（每条生效标准一个 Noul）")
    typer.echo(f"纳入带 / 排除带   ≥{profile.include_at} / <{profile.exclude_below}")
    typer.echo(f"请求数           {estimate.requests:,}（一条记录一个请求）")
    typer.echo(f"输入 token（估）  {estimate.usage.cache_miss:,}（无前缀缓存，全按未命中计）")
    if cost is None:
        typer.secho("预计成本         **无法估算**", fg=typer.colors.YELLOW)
    else:
        typer.secho(f"预计成本         ${cost:,.4f}（输出免费）", fg=typer.colors.YELLOW)
    typer.secho(
        "注：粗估，按字符数近似；实测每条约 1,200 token。放量前先 --limit 4 验"
        "服务端约束，再 --limit 100 验任务设计——假客户端测得了代码，测不了服务端。",
        fg=typer.colors.YELLOW,
    )


def _report_model_drift(rows: Sequence[ScoreRow]) -> str | None:
    """打分用的模型版本。出现多个说明中途换过版本，阈值就不再是同一套标准。"""
    seen = sorted({row.model for row in rows if row.model})
    if not seen:
        return None
    if len(seen) > 1:
        typer.secho(
            f"这一轮的打分来自多个模型版本：{seen}。阈值是在某一个版本上调出来的，"
            f"混用会让同一个分数含义不同——建议删掉 {JEV_SCORES} 重打。",
            fg=typer.colors.YELLOW,
            err=True,
        )
    return seen[0] if len(seen) == 1 else "+".join(seen)


def run_jev_screening(
    *,
    run_dir: Run,
    topic_path: Path,
    topic: Topic,
    records: Sequence[CanonicalRecord],
    provider,
    profile_path: Path | None,
    previous: Mapping[str, MergedDecision] | None,
    resume: bool,
    limit: int | None,
    dry_run: bool,
    concurrency: int,
    allow_regression: bool,
    api_key: str | None,
) -> None:
    """用判定 API 跑一轮筛选。

    与另外两个后端的关键差别：它先把打分落成 ``jev_scores.jsonl``，再由纯函数
    路由成判定。改阈值、扫阈值、分诊、评估全部是对同一批打分重新路由，零成本。
    """
    profile = _require_profile(profile_path, topic)
    if profile.model != provider.model:
        typer.secho(
            f"判定配置写的是 {profile.model}，实际要跑的是 {provider.model}。"
            f"阈值不跨版本转移——改配置或改 --model，别让它们不一致。",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=2)

    questions = compile_questions(topic, profile)
    digest = questions_sha256(questions)
    scores_name = JEV_SCORES_TRIAL if limit else JEV_SCORES
    known = _load_scores(run_dir, scores_name) if resume else {}
    pending = pending_records(records, known, digest) if resume else list(records)

    if resume and not pending:
        typer.secho("所有记录都按当前问题集打过分了，无需续跑。", fg=typer.colors.GREEN)
        return
    if resume:
        typer.echo(f"\n待补打分 {len(pending):,} / {len(records):,} 条")

    if dry_run:
        _echo_dry_run(topic, profile, provider, pending, questions)
        return

    if not api_key:
        typer.secho(
            "找不到判定 API 密钥。设 TYPESAFE_API_KEY（.env 或环境变量）后重试；"
            "仅估算成本可加 --dry-run。",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=2)

    rows, usage, failures = _score(
        topic, profile, pending, run_dir, scores_name, known, api_key, concurrency
    )
    merged = {**known, **{row.record_key: row for row in rows}}
    run_dir.write_jsonl(scores_name, [merged[key].to_json() for key in sorted(merged)])
    typer.echo(f"打分 → {run_dir.root / scores_name}（{len(merged):,} 条）")

    rate = len(failures) / max(1, len(pending))
    if rate > MAX_FAILURE_RATE:
        typer.secho(
            f"\n{len(failures):,} / {len(pending):,} 条打分失败（{rate:.1%}），"
            f"超过 {MAX_FAILURE_RATE:.0%} 的上限——**不写入轮次**。"
            f"打分已保存，修好后用 --resume 补齐即可，不必重跑已成功的部分。\n"
            f"失败样例：{failures[0]}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)

    decisions = route_all(records, merged, topic, profile)
    if violations := gold_set_violations(decisions, records, topic):
        typer.secho(
            f"\n{len(violations)} 条金标种子被**自动排除**：{'、'.join(violations[:5])}。\n"
            f"金标是「必须被检出并保留」的定义，被排掉说明阈值或判定器有缺陷，"
            f"不是可以接受的误差。**不写入轮次**——请先跑 lit screen-eval 调准入。",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)

    by_key = {item.key: item for item in records}
    finish_screening_round(
        run_dir=run_dir,
        topic_path=topic_path,
        topic=topic,
        result=BackendResult(
            decisions=decisions,
            usage=asdict(usage),
            failures=failures,
            provider=urlsplit(provider.base_url).hostname,
            model=_report_model_drift(list(merged.values())) or provider.model,
            endpoint_host=urlsplit(provider.base_url).hostname,
            parameters={
                "judge": "jev",
                "channels": 1,
                "concurrency": concurrency,
                "scores": scores_name,
                "questions_sha256": digest,
                "profile_sha256": profile.sha256(),
                "profile": profile.model_dump(mode="json"),
                **({"allow_regression": True} if allow_regression else {}),
            },
            prompt_sha256=digest,
        ),
        records=by_key,
        previous=previous,
        trial=bool(limit),
        allow_regression=allow_regression,
    )


def _score(topic, profile, pending, run_dir, scores_name, known, api_key, concurrency):
    """打分，每 CHECKPOINT_EVERY 条落一次盘。"""
    failures: list[str] = []
    buffer: list[ScoreRow] = []

    def checkpoint(row: ScoreRow) -> None:
        buffer.append(row)
        if len(buffer) % CHECKPOINT_EVERY == 0:
            snapshot = {**known, **{item.record_key: item for item in buffer}}
            run_dir.write_jsonl(scores_name, [snapshot[key].to_json() for key in sorted(snapshot)])

    async def go():
        # 建客户端、打分、关闭必须在**同一个**事件循环里。httpx 的连接池绑在创建它
        # 的循环上，分两次 asyncio.run 会在关闭时抛 "Event loop is closed"——
        # 而 respx 在传输层拦截、不建真实连接，所以单测测不出来，只有真跑才会炸。
        client, raw = build_jev_client(api_key, model=profile.model)
        try:
            return await score_records(
                client,
                topic,
                profile,
                pending,
                concurrency=concurrency,
                checkpoint=checkpoint,
                on_error=lambda key, err: failures.append(f"{key}: {err}"),
                progress=lambda done, total: (
                    typer.echo(f"  {done:,}/{total:,}") if done % 500 == 0 else None
                ),
            )
        finally:
            await raw.aclose()

    try:
        rows, usage = asyncio.run(go())
    except JevFatalError as error:
        typer.secho(
            f"\n请求本身不合法，每条记录都会一样地错，整轮中止：{error}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=2) from error
    return rows, usage, failures


def _echo_spread(decisions, rows, topic, profile) -> None:
    inclusions = [item.id for item in profile.active_inclusions(topic)]
    scores = [
        min(row.answers[cid] for cid in inclusions)
        for key, item in decisions.items()
        if item.needs_human and (row := rows.get(key)) and all(c in row.answers for c in inclusions)
    ]
    if not scores:
        return
    high = sum(1 for value in scores if value >= profile.include_at)
    low = sum(1 for value in scores if value < profile.exclude_below)
    typer.echo(
        f"队列分布：{high:,} 条 ≥{profile.include_at}（很可能该纳入），"
        f"{low:,} 条 <{profile.exclude_below}（很可能该排除），"
        f"{len(scores) - high - low:,} 条在中间"
    )


def triage_command(
    run: str = typer.Argument(..., help="run 目录、<topic>/<run_id>，或 <topic> 取最新"),
    topic: Path = typer.Option(..., "--topic", help="课题协议 YAML"),
    jev_profile: Path = typer.Option(..., "--jev-profile", help="判定 API 的阈值配置"),
    runs_root: Path = typer.Option(DEFAULT_RUNS_ROOT, "--runs-root"),
    auto_resolve: bool = typer.Option(
        False,
        "--auto-resolve",
        help="两个 LLM 通道矛盾、判定器明确站纳入一侧时自动裁定（只往 include 方向）",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="只估成本，不打网络"),
    concurrency: int = typer.Option(16, "--concurrency", min=1),
) -> None:
    """给人工队列排优先级：判定器打分、标注争议标准、按最可能纳入排序。

    队列常常没人看得完——实测两个历史 run 合计 2,541 行至今空着。这个命令
    **不替人裁定**（除非显式 --auto-resolve），只把「随机顺序的一千多行」
    变成「有优先级、带线索的工作队列」。
    """
    loaded = load_topic_or_exit(topic)
    run_dir = open_compatible_run_or_exit(runs_root, run, loaded, topic)
    profile = _require_profile(jev_profile, loaded)
    provider = resolve_provider(profile.model)

    records = [CanonicalRecord.model_validate(row) for row in run_dir.read_jsonl("corpus.jsonl")]
    by_key = {item.key: item for item in records}
    decisions = load_latest_decisions(run_dir)
    if not decisions:
        typer.secho("该 run 还没有筛选轮次，先跑 lit screen。", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)

    queued = [by_key[key] for key, item in decisions.items() if item.needs_human and key in by_key]
    if not queued:
        typer.secho("人工队列是空的，没什么可分诊的。", fg=typer.colors.GREEN)
        return
    typer.echo(f"\n人工队列 {len(queued):,} 条")

    questions = compile_questions(loaded, profile)
    digest = questions_sha256(questions)
    known = _load_scores(run_dir, JEV_SCORES)
    pending = pending_records(queued, known, digest)

    if dry_run:
        _echo_dry_run(loaded, profile, provider, pending, questions)
        return

    if pending:
        api_key = (Credentials.from_env().api_keys or {}).get("typesafe")
        if not api_key:
            typer.secho(
                "找不到判定 API 密钥。设 TYPESAFE_API_KEY 后重试；仅估算可加 --dry-run。",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(code=2)
        rows, _, failures = _score(
            loaded, profile, pending, run_dir, JEV_SCORES, known, api_key, concurrency
        )
        known = {**known, **{item.record_key: item for item in rows}}
        run_dir.write_jsonl(JEV_SCORES, [known[key].to_json() for key in sorted(known)])
        if failures:
            typer.secho(
                f"{len(failures):,} 条打分失败，它们会排在队列末尾并标为未打分。",
                fg=typer.colors.YELLOW,
            )
    else:
        typer.echo("队列里的记录都已按当前问题集打过分，直接重排。")

    run_dir.write_text(
        "human_queue.csv", render_triage_queue(decisions, records, known, loaded, profile)
    )
    _echo_spread(decisions, known, loaded, profile)
    typer.secho(
        f"队列已重排（最可能纳入的在最前）→ {run_dir.root / 'human_queue.csv'}",
        fg=typer.colors.GREEN,
    )

    candidates = tiebreak_candidates(decisions, known, loaded, profile)
    if not auto_resolve:
        if candidates:
            typer.echo(
                f"\n其中 {len(candidates):,} 条是「两个通道矛盾、判定器明确站纳入一侧」，"
                f"加 --auto-resolve 可自动裁定（只往 include 方向，仍记入审计）。"
            )
        return
    if not candidates:
        typer.echo("\n没有可自动裁定的僵局，队列全部留给人。")
        return
    _write_triage_round(run_dir, topic, loaded, decisions, candidates, by_key, profile)


def _write_triage_round(run_dir, topic_path, loaded, decisions, candidates, by_key, profile):
    """把机器裁决写成新一轮。与人工裁定同构，但 adjudicated_by 记的是判定器。"""
    judge = f"jev:{profile.model}"
    try:
        updated, audit = apply_machine(decisions, candidates, judge=judge)
    except AdjudicationError as error:
        typer.secho(str(error), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from error

    rounds = sorted(
        run_dir.root.glob("screening_round_*.json"),
        key=lambda item: int(item.stem.rsplit("_", 1)[-1]),
    )
    base = ScreeningRound.model_validate_json(rounds[-1].read_text(encoding="utf-8"))
    written = ScreeningRound(
        number=base.number + 1,
        topic_sha256=freeze_topic(topic_path),
        topic_fingerprint=protocol_fingerprint(loaded),
        provider=judge,
        model=profile.model,
        parameters={
            "kind": "triage",
            "judge": judge,
            "base_round": base.number,
            "resolved": len(candidates),
            "include_at": profile.include_at,
            "profile_sha256": profile.sha256(),
        },
        expected_records=len(updated),
        decisions=updated,
    )
    run_dir.write_text(
        f"screening_round_{written.number}.json", written.model_dump_json(indent=2)
    )
    run_dir.write_jsonl(
        "adjudications.jsonl", [*run_dir.read_jsonl("adjudications.jsonl"), *audit]
    )
    run_dir.write_text("human_queue.csv", render_human_queue(updated, by_key))
    run_dir.write_jsonl("included.jsonl", included_rows(updated, by_key))
    typer.secho(
        f"\n机器裁定 {len(candidates):,} 条 → 轮次 {written.number}"
        f"（adjudicated_by={judge}，PRISMA 里可单列）。"
        f"仍待人工 {summarize(updated)['human_queue']:,} 条。",
        fg=typer.colors.GREEN,
    )
