"""litsearch 命令行入口。"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from dataclasses import asdict
from pathlib import Path
from urllib.parse import urlsplit

import typer

from litsearch.adjudicate import (
    AdjudicationError,
    apply_dates,
    apply_screening,
    load_rows,
)
from litsearch.ccf import CcfError, CcfMatcher, load_catalog
from litsearch.coverage import coverage_markdown, find_gaps
from litsearch.dedupe import CanonicalRecord, deduplicate
from litsearch.deliver import (
    BIBTEX,
    bibtex_document,
    dois_markdown,
    fetch_citations,
    references_markdown,
    resolve_style,
)
from litsearch.deliver import DeliverError as _DeliverError
from litsearch.fulltext import (
    institutional_access_csv,
    resolve_fulltext,
)
from litsearch.fulltext import summarize as summarize_fulltext
from litsearch.harvest import PlanReport, harvest, harvest_into, plan, read_all_records
from litsearch.harvest import _boundary_csv as boundary_csv
from litsearch.metrics import (
    capture_recapture,
    gold_set_recall,
    out_of_window_leakage,
    overlap_between,
    source_contribution,
)
from litsearch.normalize import Record, WindowStatus
from litsearch.order import group_by_tier
from litsearch.profiles import DEFAULT_DEPTH, profile_for, sources_for, summary_table
from litsearch.protocol import ProtocolError, freeze_topic, load_topic, protocol_fingerprint
from litsearch.providers import (
    ENV_API_KEY,
    HOST_MODEL,
    ProviderError,
    api_key_from,
    resolve_provider,
)
from litsearch.providers import describe as describe_provider
from litsearch.query import SourceQuery, build_queries
from litsearch.rank import (
    VenueKind,
    fetch_journals,
    fetch_works,
    load_ranked,
    match_summary,
    normalize_issn,
    rank_records,
    ranked_csv,
    ranked_rows,
    tier_report_markdown,
)
from litsearch.report import (
    PrismaCounts,
    ReportInconsistency,
    evidence_table_markdown,
    included_csv,
    prisma_markdown,
    zotero_dois,
)
from litsearch.run import (
    Run,
    assert_topic_compatible,
    jsonl_text,
    latest_degraded,
    resolve_run,
    unrun_sources,
)
from litsearch.screen import (
    Decision,
    MergedDecision,
    ScreeningRound,
    build_channel_prompt,
    merge_verdicts,
    render_human_queue,
    summarize,
)
from litsearch.screen_host import (
    HOST_BATCH_SIZE,
    HOST_DEFAULT_MODEL,
    OVERHEAD_TOKENS_PER_CALL,
    HostBackendError,
    run_host_screening,
)
from litsearch.screen_runner import (
    build_client as build_screen_client,
)
from litsearch.screen_runner import (
    build_requests,
    estimate,
    pending_by_channel,
    regroup_by_channel,
    run_screening,
)
from litsearch.snowball import (
    RoundStat,
    SeedMode,
    build_snowball_queries,
    is_saturated,
    select_seeds,
)
from litsearch.sources.crossref import discover_volumes
from litsearch.sources.registry import Credentials, available_sources, build_client
from litsearch.verify import verify_run

app = typer.Typer(add_completion=False, help="时间窗受限的高召回文献检索")

DEFAULT_RUNS_ROOT = Path("runs")


def _load(topic_path: Path):
    try:
        return load_topic(topic_path)
    except ProtocolError as error:
        typer.secho(str(error), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2) from error


def _today():
    """今天。抽成函数是为了让"最新预印本"的判定在测试里可控。"""
    from datetime import date

    return date.today()


def _split(value: str | None) -> list[str] | None:
    return [item.strip() for item in value.split(",") if item.strip()] if value else None


#: 逐源记录按采集阶段分文件存放：``records.jsonl`` 是主采集，
#: ``records_<阶段>.jsonl`` 是后续补全（整卷、滚雪球）。每个文件只写一次，
#: 语料由它们合并去重而来——这样"哪一条是哪一阶段拿到的"永远可回答。
RECORD_FILES = "records*.jsonl"


def _open_run(runs_root: Path, reference: str) -> Run:
    try:
        return Run.open(resolve_run(runs_root, reference))
    except FileNotFoundError as error:
        typer.secho(str(error), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2) from error


def _open_compatible_run(runs_root: Path, reference: str, topic, topic_path: Path) -> Run:
    """Open a run and reject commands that supply an unrelated protocol."""
    run = _open_run(runs_root, reference)
    try:
        assert_topic_compatible(run, topic, topic_path)
    except ValueError as error:
        typer.secho(str(error), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2) from error
    return run


def _read_all_records(run_dir: Run) -> list[Record]:
    records = read_all_records(run_dir)
    if not records and not list(run_dir.root.glob(RECORD_FILES)):
        raise FileNotFoundError(
            "该 run 没有 records.jsonl（早于该文件的加入），无法重判——需重新采集。"
        )
    return records


@app.command("strategies")
def strategies(
    topic: Path = typer.Option(..., "--topic", help="课题协议 YAML"),
) -> None:
    """打印将要执行的全部检索式，不发任何网络请求。"""
    loaded = _load(topic)
    queries = build_queries(loaded)
    typer.echo(f"课题 {loaded.id}：{len(queries)} 条检索式")
    typer.echo(
        f"严格窗口 {loaded.window.start} ~ {loaded.window.end}；"
        f"采集窗口 {loaded.window.harvest_start} ~ {loaded.window.harvest_end}"
    )
    for query in queries:
        typer.echo(f"\n[{query.source}] {query.query_hash}  {query.kind}/{query.label}")
        typer.echo(f"  {query.query}")


@app.command("plan")
def plan_command(
    topic: Path = typer.Option(..., "--topic", help="课题协议 YAML"),
    sources: str = typer.Option(None, "--sources", help="逗号分隔，只跑这些源"),
) -> None:
    """干跑：在真正采集前，按源、按检索式给出预计命中数与筛选成本。"""
    loaded = _load(topic)
    report: PlanReport = asyncio.run(plan(loaded, Credentials.from_env(), only=_split(sources)))

    typer.echo(
        f"\n课题 {report.topic_id}  采集窗口 "
        f"{loaded.window.harvest_start} ~ {loaded.window.harvest_end}\n"
    )
    typer.echo(f"{'源':<16}{'检索式':<8}{'命中合计(含重复)':>18}")
    typer.echo("-" * 44)
    for source, total in sorted(report.by_source().items()):
        count = sum(1 for row in report.rows if row.source == source)
        shown = "未知" if total is None else f"{total:,}"
        typer.echo(f"{source:<16}{count:<8}{shown:>18}")

    typer.echo("\n命中最多的 10 条检索式：")
    ranked = sorted(
        (row for row in report.rows if row.estimate is not None),
        key=lambda row: row.estimate,
        reverse=True,
    )
    for row in ranked[:10]:
        typer.echo(f"  {row.estimate:>8,}  [{row.source}] {row.kind}/{row.label}")

    if unresolved := report.unresolved():
        typer.secho(f"\n{len(unresolved)} 条检索式未能取得计数：", fg=typer.colors.YELLOW)
        for row in unresolved[:10]:
            typer.echo(f"  [{row.source}] {row.label}: {row.error or '无返回'}")

    if skipped := sorted(set(loaded.recall_sources()) - available_sources()):
        typer.secho(f"\n协议启用但尚未实现的源：{skipped}", fg=typer.colors.YELLOW)

    typer.echo(
        "\n注：以上为各检索式命中之和，含跨检索式与跨源重复，是**上界**；"
        "去重后的实际规模以 harvest 结果为准。"
    )


@app.command("harvest")
def harvest_command(
    topic: Path = typer.Option(..., "--topic", help="课题协议 YAML"),
    runs_root: Path = typer.Option(DEFAULT_RUNS_ROOT, "--runs-root"),
    sources: str = typer.Option(None, "--sources", help="逗号分隔，只跑这些源"),
    depth: str = typer.Option(
        DEFAULT_DEPTH.value, "--depth", help="quick / standard / systematic（见 lit depths）"
    ),
    max_per_query: int = typer.Option(
        None,
        "--max-per-query",
        min=1,
        help="每条检索式最多取多少条（仅用于冒烟测试，正式跑不要设）",
    ),
    resume: str = typer.Option(
        None, "--resume", help="续跑某次 run 中 partial/failed 的检索式，其余结果直接沿用"
    ),
    into: str = typer.Option(
        None, "--into", help="把本次采集并入已有 run（需同时给 --phase），语料按全部阶段重建"
    ),
    phase: str = typer.Option(
        None, "--phase", help="阶段名，决定写入 records_<阶段>.jsonl，如 stage3 / snowball1"
    ),
    labels: str = typer.Option(
        None, "--labels", help="逗号分隔，只跑这些 label 的检索式（配合 --into 用于定点补跑）"
    ),
) -> None:
    """多源完整翻页采集 → 规范化 → 去重 → 落盘到 runs/。

    ``--into <run> --phase <名字>`` 把这一批并入已有 run：原始记录按阶段各占一个文件，
    只追加不改写，语料由全部阶段合并去重重建。协议必须与该 run 一致。
    """
    loaded = _load(topic)
    if bool(into) != bool(phase):
        typer.secho("--into 与 --phase 必须成对使用", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)

    only = _split(sources) or _depth_sources(depth, loaded)

    if into:
        target = _open_compatible_run(runs_root, into, loaded, topic)
        try:
            report = asyncio.run(
                harvest_into(
                    loaded,
                    topic,
                    target,
                    Credentials.from_env(),
                    phase=phase,
                    only=only,
                    labels=_split(labels),
                    max_records_per_query=max_per_query,
                    progress=lambda line: typer.echo(line),
                )
            )
        except (ValueError, FileExistsError) as error:
            typer.secho(str(error), fg=typer.colors.RED, err=True)
            raise typer.Exit(code=2) from error
        _print_harvest_report(report, target)
        return

    resume_run = None
    if resume:
        try:
            resume_run = Run.open(resolve_run(runs_root, resume))
        except (FileNotFoundError, OSError) as error:
            typer.secho(str(error), fg=typer.colors.RED, err=True)
            raise typer.Exit(code=2) from error

    run = Run.create(runs_root, loaded.id)
    report = asyncio.run(
        harvest(
            loaded,
            topic,
            run,
            Credentials.from_env(),
            resume_from=resume_run,
            only=only,
            depth=depth,
            max_records_per_query=max_per_query,
            progress=lambda line: typer.echo(line),
        )
    )
    _print_harvest_report(report, run)


def _print_harvest_report(report, run: Run) -> None:

    typer.echo(f"\nrun 目录：{run.root}")
    typer.echo(f"原始记录 {report.raw_count:,} 条 → 去重后 {len(report.canonical):,} 条\n")
    typer.echo(f"{'窗口判定':<16}{'数量':>10}")
    typer.echo("-" * 26)
    labels = {
        "in_window": "窗口内",
        "boundary": "边界待裁定",
        "undated": "无日期待裁定",
        "out_of_window": "窗口外",
    }
    for key, count in report.manifest.counts.items():
        if key in labels:
            typer.echo(f"{labels[key]:<16}{count:>10,}")

    typer.echo("\n各源采集状态：")
    for source in report.manifest.sources:
        outcomes = [item for item in report.manifest.outcomes if item.source == source]
        fetched = sum(item.fetched for item in outcomes)
        bad = [item for item in outcomes if item.status != "complete"]
        flag = f"  ⚠️ {len(bad)} 条检索式未完成" if bad else ""
        typer.echo(f"  {source:<14}{fetched:>8,} 条{flag}")

    for note in report.manifest.notes:
        typer.secho(f"\n注意：{note}", fg=typer.colors.YELLOW)

    boundary = report.manifest.counts.get("boundary", 0) + report.manifest.counts.get("undated", 0)
    if boundary:
        typer.secho(
            f"\n{boundary:,} 条记录需要人工裁定日期，见 {run.root / 'boundary_cases.csv'}",
            fg=typer.colors.YELLOW,
        )


@app.command("reclassify")
def reclassify_command(
    run: str = typer.Argument(..., help="run 目录、<topic>/<run_id>，或 <topic> 取最新"),
    topic: Path = typer.Option(..., "--topic", help="课题协议 YAML"),
    runs_root: Path = typer.Option(DEFAULT_RUNS_ROOT, "--runs-root"),
) -> None:
    """用当前规则从 records.jsonl 重新去重与判定窗口，不重新采集。

    去重和日期判定的规则会演进；采集是昂贵的一次性动作，判定不是。
    records.jsonl 保留了去重前的逐源记录，因此规则一改就能便宜地重判。
    """
    loaded = _load(topic)
    run_dir = _open_compatible_run(runs_root, run, loaded, topic)
    path = run_dir.root
    try:
        records = _read_all_records(run_dir)
    except FileNotFoundError as error:
        typer.secho(str(error), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2) from error

    canonical = deduplicate(records, loaded.window, loaded.window.date_priority)

    counts: dict[str, int] = {}
    for item in canonical:
        key = item.window_status.value if item.window_status else "unknown"
        counts[key] = counts.get(key, 0) + 1

    manifest = run_dir.load_manifest()
    previous = manifest.get("counts", {})
    typer.echo(f"\n记录 {len(records):,} → 去重 {len(canonical):,}\n")
    typer.echo(f"{'窗口判定':<16}{'原':>10}{'现':>10}{'变化':>10}")
    typer.echo("-" * 46)
    labels = {
        "in_window": "窗口内",
        "boundary": "待人工裁定",
        "undated": "无日期",
        "out_of_window": "窗口外",
    }
    for key, label in labels.items():
        was, now = previous.get(key, 0), counts.get(key, 0)
        typer.echo(f"{label:<16}{was:>10,}{now:>10,}{now - was:>+10,}")

    run_dir.write_jsonl("corpus.jsonl", [item.model_dump(mode="json") for item in canonical])
    run_dir.write_text("boundary_cases.csv", boundary_csv(canonical))
    manifest["counts"] = manifest.get("counts", {}) | counts
    manifest.setdefault("notes", []).append(
        f"已用当前规则重判（协议 {freeze_topic(topic)[:16]}…），未重新采集"
    )
    run_dir.write_text("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    typer.secho(f"\n已更新 {path / 'corpus.jsonl'}", fg=typer.colors.GREEN)


@app.command("proceedings")
def proceedings_command(
    run: str = typer.Argument(..., help="run 目录、<topic>/<run_id>，或 <topic> 取最新"),
    topic: Path = typer.Option(..., "--topic", help="课题协议 YAML"),
    runs_root: Path = typer.Option(DEFAULT_RUNS_ROOT, "--runs-root"),
    limit: int | None = typer.Option(None, "--limit", min=1, help="最多补全多少卷"),
    phase: str = typer.Option("proceedings", "--phase", help="阶段名，决定写入哪个记录文件"),
    dry_run: bool = typer.Option(False, "--dry-run", help="只列出将要补全的卷，不请求"),
) -> None:
    """按 LNCS 卷 ISBN 把 MICCAI 等会议录整卷补齐。

    LNCS 的 DOI 后缀里嵌着卷 ISBN（``10.1007/978-3-031-16443-9_1`` → ``9783031164439``），
    所以语料里任何一篇 MICCAI 论文都能解锁它所在的整卷，一次拿到全部同卷兄弟篇。
    这是引文滚雪球之外的另一条闭包路径，且不消耗 OpenAlex 配额。
    """
    loaded = _load(topic)
    run_dir = _open_compatible_run(runs_root, run, loaded, topic)
    records = _read_all_records(run_dir)

    volumes = discover_volumes(item.identifiers.get("doi") for item in records)
    if limit:
        volumes = volumes[:limit]
    if not volumes:
        typer.secho("语料中没有 LNCS 会议录论文，无卷可补。", fg=typer.colors.YELLOW)
        return

    typer.echo(f"\n发现 {len(volumes)} 个 LNCS 卷（由语料中已有论文的 DOI 反解）")
    if dry_run:
        for isbn in volumes:
            typer.echo(f"  {isbn}")
        return

    queries = [
        SourceQuery(source="crossref", query=isbn, kind="volume", label=f"ISBN {isbn}")
        for isbn in volumes
    ]
    # 走与滚雪球相同的并入机制：检索式由语料生成，其余（原始响应落盘、
    # manifest 结局、语料重建）全部复用——自己另写一套就会漏记结局，
    # 那 670 条记录会静默不出现在 PRISMA 的识别数里。
    try:
        report = asyncio.run(
            harvest_into(
                loaded,
                topic,
                run_dir,
                Credentials.from_env(),
                phase=phase,
                queries=queries,
                progress=lambda line: typer.echo(line),
            )
        )
    except (ValueError, FileExistsError) as error:
        typer.secho(str(error), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2) from error

    typer.echo(
        f"\n记录 {report.raw_count:,} → 去重 {len(report.canonical):,}；"
        f"窗口内 {report.manifest.counts.get('in_window', 0):,}"
    )
    typer.secho(f"已更新 {run_dir.root / 'corpus.jsonl'}", fg=typer.colors.GREEN)


@app.command("snowball")
def snowball_command(
    run: str = typer.Argument(..., help="run 目录、<topic>/<run_id>，或 <topic> 取最新"),
    topic: Path = typer.Option(..., "--topic", help="课题协议 YAML"),
    runs_root: Path = typer.Option(DEFAULT_RUNS_ROOT, "--runs-root"),
    seeds: SeedMode = typer.Option(
        SeedMode.INCLUDED, "--seeds", help="滚雪球起点：included / gold / matched / in_window"
    ),
    max_rounds: int = typer.Option(None, "--max-rounds", min=1, help="覆盖协议里的最大轮数"),
    depth: str = typer.Option(
        DEFAULT_DEPTH.value, "--depth", help="quick 不滚、standard 滚 1 轮、systematic 滚到饱和"
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="只报种子数与请求数，不发请求"),
) -> None:
    """双向引文滚雪球至饱和。

    默认从**筛选纳入**的研究出发——这是系统综述的规范做法。从全部未筛选候选出发
    会把候选量放大一个数量级（实测本课题：数百 → 13 万），筛选成本随之爆炸。
    """
    loaded = _load(topic)
    run_dir = _open_compatible_run(runs_root, run, loaded, topic)
    config = loaded.snowball
    profile = profile_for(depth)
    if max_rounds is None and not profile.runs_snowball:
        typer.secho(
            f"深度 {profile.depth.value} 不跑滚雪球。实测滚雪球独有贡献占 92%——"
            "要说得清召回边界请用 --depth standard 或 systematic，"
            "或显式给 --max-rounds。",
            fg=typer.colors.YELLOW,
        )
        raise typer.Exit(code=0)
    # 档位只收紧，不放宽：协议里写 3 轮就不该因为选了 systematic 变成 6 轮
    ceiling = profile.snowball_rounds
    limit = max_rounds or (
        config.max_rounds if ceiling is None else min(ceiling, config.max_rounds)
    )

    corpus = [CanonicalRecord.model_validate(row) for row in run_dir.read_jsonl("corpus.jsonl")]
    if not corpus:
        typer.secho("该 run 还没有语料，请先 lit harvest。", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)

    decisions = _load_decisions(run_dir)
    try:
        seed_records = select_seeds(corpus, loaded, seeds, decisions=decisions)
    except ValueError as error:
        typer.secho(str(error), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2) from error

    # 轮次号从已有的阶段文件接着数：一次命令跑一轮、跑完等筛选，
    # 下次再调用时不能又从 1 开始，否则会撞上"阶段已存在"的护栏。
    done_rounds = [
        int(item.stem.rsplit("-", 1)[-1])
        for item in run_dir.root.glob(f"records_snowball-{seeds.value}-*.jsonl")
        if item.stem.rsplit("-", 1)[-1].isdigit()
    ]
    first = max(done_rounds, default=0) + 1

    # 饱和判据要看**跨调用**的完整轮次史。只看本次调用的话，
    # "一次命令跑一轮"的模式下永远判不出饱和——用户也就永远得不到停止信号。
    history: list[RoundStat] = [
        RoundStat(**row) for row in run_dir.read_jsonl("snowball_rounds.jsonl")
    ]
    if history and is_saturated(history, config):
        typer.secho(
            f"已达饱和：连续 {config.saturation_consecutive_rounds} 轮窗口内新增占比 "
            f"< {config.saturation_new_inclusion_rate:.0%}（轮次 "
            f"{'、'.join(f'{item.number}:{item.new_rate:.1%}' for item in history[-3:])}）。"
            f"引文闭包已完成。",
            fg=typer.colors.GREEN,
        )
        return

    for number in range(first, first + limit):
        known = _known_dois(corpus)
        queries = build_snowball_queries(seed_records, known, number)
        typer.echo(
            f"\n第 {number} 轮：种子 {len(seed_records):,} 条 → "
            f"前向 {sum(1 for q in queries if 'forward' in q.label)} 批 / "
            f"后向 {sum(1 for q in queries if 'backward' in q.label)} 批"
        )
        if dry_run or not queries:
            if dry_run:
                typer.secho("--dry-run：未发任何请求", fg=typer.colors.YELLOW)
            break

        before = len(corpus)
        in_window_before = sum(1 for item in corpus if item.window_status is WindowStatus.IN_WINDOW)
        rolled = {item.key for item in seed_records}

        # 阶段名带上种子模式：不同种子集是不同来源，混进同一个文件就
        # 再也分不清"这批是从金标准滚出来的还是从纳入集滚出来的"
        phase = f"snowball-{seeds.value}-{number}"
        try:
            report = asyncio.run(
                harvest_into(
                    loaded,
                    topic,
                    run_dir,
                    Credentials.from_env(),
                    phase=phase,
                    queries=queries,
                    progress=lambda line: typer.echo(line),
                )
            )
        except (ValueError, FileExistsError) as error:
            typer.secho(str(error), fg=typer.colors.RED, err=True)
            raise typer.Exit(code=2) from error
        corpus = report.canonical
        stat = RoundStat(
            number=number,
            seeds=len(seed_records),
            candidates=len(queries),
            new_records=len(corpus) - before,
            new_in_window=report.manifest.counts.get("in_window", 0) - in_window_before,
            corpus_before=in_window_before,
        )
        history.append(stat)
        typer.echo(
            f"  语料 {before:,} → {len(corpus):,}；"
            f"窗口内新增 {stat.new_in_window:,}（占轮前 {stat.new_rate:.1%}）"
        )

        if is_saturated(history, config):
            typer.secho(
                f"\n已达饱和：连续 {config.saturation_consecutive_rounds} 轮"
                f"窗口内新增占比 < {config.saturation_new_inclusion_rate:.0%}",
                fg=typer.colors.GREEN,
            )
            break

        # 下一轮只从**本轮新出现**的合格记录继续；已经滚过的种子再滚一遍
        # 只会重复发同样的请求，还会让"新增率"这个饱和信号失真。
        seed_records = [
            item
            for item in select_seeds(corpus, loaded, seeds, decisions=decisions)
            if item.key not in rolled
        ]
        if not seed_records:
            if seeds is SeedMode.INCLUDED and stat.new_in_window:
                # 本轮新拿到的记录还没筛过，自然当不了"已纳入"种子。
                # 这**不是**饱和——把它说成饱和，会让人以为引文闭包做完了。
                typer.secho(
                    f"\n本轮新增 {stat.new_in_window:,} 条窗口内记录，但它们**尚未筛选**，"
                    f"因此产生不了新的合格种子。\n"
                    f"这**不是**饱和——引文闭包需要「筛选 → 滚雪球」交替进行：\n"
                    f"  lit screen   {run} --topic {topic} --resume\n"
                    f"  lit snowball {run} --topic {topic} --seeds included",
                    fg=typer.colors.YELLOW,
                )
            else:
                typer.secho("\n本轮没有产生新的合格种子，滚雪球自然终止。", fg=typer.colors.GREEN)
            break
    else:
        typer.secho(
            f"\n已达最大轮数 {limit} 但**尚未饱和**——这批结果不能声称做到了引文闭包。",
            fg=typer.colors.YELLOW,
        )

    if history:
        typer.echo(f"\n{'轮次':<8}{'种子':>10}{'新增':>10}{'占轮前':>10}")
        typer.echo("-" * 38)
        for stat in history:
            typer.echo(
                f"{stat.number:<8}{stat.seeds:>10,}{stat.new_records:>10,}{stat.new_rate:>9.1%}"
            )
        # history 已含读回的历史轮次，整体写回即为累计——
        # 只写本次调用的轮次会把之前的抹掉，饱和曲线也就再也画不出来
        merged = {stat.number: stat for stat in history}
        run_dir.write_jsonl(
            "snowball_rounds.jsonl",
            [asdict(merged[number]) for number in sorted(merged)],
        )


def _known_dois(records: list[CanonicalRecord]) -> set[str]:
    return {doi for item in records if (doi := item.identifiers.get("doi"))}


def _load_decisions(run_dir: Run) -> dict[str, MergedDecision] | None:
    """读回**最近一轮**筛选判定；没有就返回 None。

    判定按轮次不可变追加（`screening_round_N.json`），改判开新一轮。
    这里取轮次号最大的那一轮——它才是当前结论。
    """
    rounds = sorted(
        run_dir.root.glob("screening_round_*.json"),
        key=lambda item: int(item.stem.rsplit("_", 1)[-1]),
    )
    if not rounds:
        return None
    payload = json.loads(rounds[-1].read_text(encoding="utf-8"))
    return {
        key: MergedDecision.model_validate(value)
        for key, value in (payload.get("decisions") or {}).items()
    }


@app.command("validate")
def validate_command(
    run: str = typer.Argument(..., help="run 目录、<topic>/<run_id>，或 <topic> 取最新"),
    topic: Path = typer.Option(..., "--topic", help="课题协议 YAML"),
    runs_root: Path = typer.Option(DEFAULT_RUNS_ROOT, "--runs-root"),
) -> None:
    """给出召回率证据：金标准命中、窗口外泄漏、来源独有贡献、捕获-再捕获。"""
    loaded = _load(topic)
    run_dir = _open_compatible_run(runs_root, run, loaded, topic)
    path = run_dir.root
    records = [CanonicalRecord.model_validate(row) for row in run_dir.read_jsonl("corpus.jsonl")]
    if not records:
        typer.secho("corpus.jsonl 为空，先跑 lit harvest", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)

    failed = False
    strict = [item for item in records if item.window_status is WindowStatus.IN_WINDOW]
    typer.echo(f"\nrun {path.name}：宽采集 {len(records):,} 条，严格窗口 {len(strict):,} 条\n")

    gold = gold_set_recall(loaded.gold_set, records)
    if gold.recall is None:
        typer.secho("金标准集为空，无法评估召回率", fg=typer.colors.YELLOW)
    else:
        colour = typer.colors.GREEN if gold.recall == 1.0 else typer.colors.RED
        typer.secho(f"金标准召回  {gold.found_count}/{gold.total} = {gold.recall:.0%}", fg=colour)
        for seed in gold.missing:
            failed = True
            typer.secho(
                f"  漏检 {seed.doi or seed.arxiv or seed.pmid}  {seed.note or ''}",
                fg=typer.colors.RED,
            )
        for seed in gold.found_out_of_window:
            failed = True
            typer.secho(
                f"  命中但被判为窗口外 {seed.doi or seed.arxiv or seed.pmid}  {seed.note or ''}",
                fg=typer.colors.YELLOW,
            )
        for seed in gold.found_pending_date:
            failed = True
            typer.secho(
                f"  命中但日期待裁定 {seed.doi or seed.arxiv or seed.pmid}  {seed.note or ''}",
                fg=typer.colors.YELLOW,
            )

    leak = out_of_window_leakage(loaded.out_of_window_controls, records)
    if leak.checked:
        colour = typer.colors.GREEN if leak.clean else typer.colors.RED
        typer.secho(f"\n窗口外对照  {leak.checked} 条，泄漏 {len(leak.leaked)} 条", fg=colour)
        for seed in leak.leaked:
            failed = True
            typer.secho(f"  泄漏 {seed.doi}  {seed.note or ''}", fg=typer.colors.RED)

    typer.echo(f"\n{'源':<14}{'总贡献':>10}{'独有':>10}{'独有占比':>12}")
    typer.echo("-" * 46)
    for row in source_contribution(strict):
        mark = "  ← 冗余" if row.redundant else ""
        typer.echo(
            f"{row.source:<14}{row.total:>10,}{row.unique:>10,}{row.unique_share:>11.0%}{mark}"
        )

    present = {source for record in strict for source in record.sources}
    if {"pubmed", "openalex"} <= present:
        in_a, in_b, both = overlap_between(strict, "pubmed", "openalex")
        estimate = capture_recapture(captured_a=in_a, captured_b=in_b, overlap=both)
        typer.echo(f"\n两源重叠诊断（pubmed × openalex）：{in_a:,} / {in_b:,}，重叠 {both:,}")
        if estimate.recall is None:
            typer.secho(f"  {estimate.note}", fg=typer.colors.YELLOW)
        else:
            colour = typer.colors.GREEN if estimate.recall >= 0.9 else typer.colors.YELLOW
            typer.secho(
                f"  Chapman 估计总体 {estimate.total:,.0f}，两源并集 {estimate.observed:,}，"
                f"并集覆盖度 {estimate.recall:.0%}",
                fg=colour,
            )
            typer.echo(f"  {estimate.note}")
            typer.secho(
                "  该值仅是 PubMed∪OpenAlex 的索引重叠诊断，不是多源流水线召回率。",
                fg=typer.colors.YELLOW,
            )
    else:
        typer.secho("\n两源重叠诊断需要 pubmed 与 openalex 同时在场", fg=typer.colors.YELLOW)

    if failed:
        typer.secho("\n验证未通过：修复检索策略后重跑。", fg=typer.colors.RED)
        raise typer.Exit(code=1)


@app.command("fulltext")
def fulltext_command(
    run: str = typer.Argument(..., help="run 目录、<topic>/<run_id>，或 <topic> 取最新"),
    runs_root: Path = typer.Option(DEFAULT_RUNS_ROOT, "--runs-root"),
    venue: str = typer.Option(None, "--venue", help="只解析刊名匹配该正则的记录"),
    limit: int = typer.Option(None, "--limit", min=1, help="只解析前 N 条（抽样用）"),
    included: bool = typer.Option(
        False, "--included", help="只解析筛选纳入的研究（需先跑 lit screen）"
    ),
) -> None:
    """解析每条记录的**合法**全文位置；拿不到的写入 institutional_access.csv。

    只查开放来源（预印本 / 仓库 / PMC / 出版商 OA）。闭源正文需要你自己的机构订阅
    或出版商 TDM 接口——本命令不绕过付费墙。

    ``--included`` 是筛选之后的正确用法：给会被排除的论文找 PDF 纯属浪费，
    而全语料一万多条意味着一万多次请求。
    """
    import re as _re

    email = Credentials.from_env().contact_email or os.environ.get("LITSEARCH_CONTACT_EMAIL")
    if not email:
        typer.secho(
            "需要设置 CONTACT_EMAIL（.env 或环境变量）——Unpaywall 与 Crossref 都要求声明身份",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=2)

    run_dir = _open_run(runs_root, run)
    records = [CanonicalRecord.model_validate(row) for row in run_dir.read_jsonl("corpus.jsonl")]
    records = [item for item in records if item.window_status == WindowStatus.IN_WINDOW]
    if included:
        decisions = _load_decisions(run_dir)
        if not decisions:
            typer.secho(
                "该 run 还没有筛选结果，--included 无从判断。先跑 lit screen。",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(code=2)
        keep = {
            key
            for key, item in decisions.items()
            if item.decision is Decision.INCLUDE and not item.needs_human
        }
        records = [item for item in records if item.key in keep]
    if venue:
        pattern = _re.compile(venue, _re.IGNORECASE)
        records = [item for item in records if pattern.search(item.venue or "")]
    if limit:
        records = records[:limit]

    if not records:
        typer.secho("没有匹配的记录", fg=typer.colors.YELLOW)
        raise typer.Exit(code=0)

    credentials = Credentials.from_env()
    clients: dict[str, object] = {}
    raw_clients = []
    for name in ("unpaywall", "europepmc", "arxiv", "crossref"):
        client, raw = build_client("crossref" if name == "unpaywall" else name, credentials)
        clients[name], _ = client, raw_clients.append(raw)

    async def go():
        try:
            return await resolve_fulltext(records, clients, email=email)
        finally:
            for raw in raw_clients:
                await raw.aclose()

    typer.echo(f"解析 {len(records):,} 条记录的全文位置…")
    resolutions = asyncio.run(go())
    summary = summarize_fulltext(resolutions)

    typer.echo(f"\n{'状态':<22}{'数量':>8}{'占比':>10}")
    typer.echo("-" * 40)
    for label, count in (
        ("合法开放全文", summary.open_access),
        ("需机构订阅/TDM", summary.tdm_only),
        ("暂无可用途径", summary.unavailable),
    ):
        share = count / summary.total if summary.total else 0
        typer.echo(f"{label:<22}{count:>8,}{share:>9.0%}")

    hosts: dict[str, int] = {}
    for item in resolutions:
        if item.best:
            hosts[item.best.host] = hosts.get(item.best.host, 0) + 1
    if hosts:
        typer.echo("\n开放全文的来源：")
        for host, count in sorted(hosts.items(), key=lambda kv: -kv[1]):
            typer.echo(f"  {host:<14}{count:>6,}")

    run_dir.write_jsonl("fulltext.jsonl", [item.model_dump(mode="json") for item in resolutions])
    run_dir.write_text("institutional_access.csv", institutional_access_csv(resolutions))
    typer.echo(f"\n位置清单 → {run_dir.root / 'fulltext.jsonl'}")
    typer.secho(
        f"需机构访问的 {summary.tdm_only + summary.unavailable:,} 条 → "
        f"{run_dir.root / 'institutional_access.csv'}",
        fg=typer.colors.YELLOW,
    )


@app.command("screen")
def screen_command(
    run: str = typer.Argument(..., help="run 目录、<topic>/<run_id>，或 <topic> 取最新"),
    topic: Path = typer.Option(..., "--topic", help="课题协议 YAML"),
    runs_root: Path = typer.Option(DEFAULT_RUNS_ROOT, "--runs-root"),
    model: str = typer.Option(
        None,
        "--model",
        help=f"模型名；'{HOST_MODEL}' 用宿主 Claude Code 判定（零配置，不需要 key）",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="只估算成本，不发起筛选"),
    limit: int = typer.Option(None, "--limit", min=1, help="只筛前 N 条（试跑用）"),
    concurrency: int = typer.Option(None, "--concurrency", min=1, help="并发请求数"),
    host_model: str = typer.Option(
        HOST_DEFAULT_MODEL,
        "--host-model",
        help="宿主后端用哪个模型（haiku / sonnet / opus）；只在 --model host 时生效",
    ),
    resume: bool = typer.Option(
        False, "--resume", help="只补上一轮中各通道缺判定的记录，结果并成新一轮"
    ),
) -> None:
    """双通道标题摘要初筛。分歧与低置信度进人工队列，不让模型单方面拍板。

    两种后端：

    - **API**（默认）：任何 OpenAI 兼容端点。设 ``LITSEARCH_LLM_MODEL`` /
      ``LITSEARCH_LLM_BASE_URL`` / ``LITSEARCH_LLM_API_KEY``。
    - **宿主**（``--model host``）：调本机的 ``claude -p``，**不需要任何 key**。
      每次调用有约 20,000 token 的框架开销，所以批次会自动放大到
      ``HOST_BATCH_SIZE``；适合 quick/standard 规模，上万条请用 API。
    """
    try:
        provider = resolve_provider(model)
    except ProviderError as error:
        typer.secho(str(error), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2) from error
    host = provider.model == HOST_MODEL
    if concurrency is None:
        concurrency = 3 if host else 6
    loaded = _load(topic)
    run_dir = _open_compatible_run(runs_root, run, loaded, topic)
    records = [CanonicalRecord.model_validate(row) for row in run_dir.read_jsonl("corpus.jsonl")]
    records = [item for item in records if item.window_status == WindowStatus.IN_WINDOW]
    if limit:
        records = records[:limit]
    if not records:
        typer.secho("窗口内没有记录，先跑 lit harvest", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)

    by_key = {item.key: item for item in records}
    previous = _load_decisions(run_dir) if resume else None
    if resume and not previous:
        typer.secho("该 run 还没有筛选轮次，无从续跑。", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)

    plan = pending_by_channel(loaded, records, previous) if resume else None
    if resume:
        outstanding = sum(len(item) for item in plan.values())
        typer.echo(
            "\n各通道待补：" + "，".join(f"通道 {c} {len(v):,}" for c, v in sorted(plan.items()))
        )
        if not outstanding:
            typer.secho("上一轮已经判全，无需续跑。", fg=typer.colors.GREEN)
            return

    batch_size = HOST_BATCH_SIZE if host else loaded.screening.batch_size
    report = estimate(loaded, records, per_channel=plan, batch_size=batch_size)

    if dry_run:
        typer.echo(f"\n窗口内记录        {report.records:,}")
        typer.echo(f"后端              {describe_provider(provider)}")
        typer.echo(f"通道数            {loaded.screening.channels}")
        typer.echo(f"每批记录数        {batch_size}")
        typer.echo(f"请求数            {report.requests:,}")
        if host:
            overhead = report.requests * OVERHEAD_TOKENS_PER_CALL
            typer.echo(f"宿主模型          {host_model}")
            typer.echo(f"框架开销（估）     {overhead:,} token（{OVERHEAD_TOKENS_PER_CALL:,}/次）")
            typer.secho(
                "宿主后端不按 token 计费——订阅用户走自己的额度。"
                "开销是**按次**算的，所以批次已放大到 "
                f"{HOST_BATCH_SIZE} 条。上万条规模请改用 API 后端。",
                fg=typer.colors.YELLOW,
            )
            return
        typer.echo(f"输入·缓存命中（估）{report.usage.cache_hit:,}")
        typer.echo(f"输入·未命中（估）  {report.usage.cache_miss:,}")
        typer.echo(f"输出 token（估）   {report.usage.output:,}")
        cost = report.usage.cost(provider.pricing)
        if cost is None:
            typer.secho(
                "预计成本          **无法估算**——该模型没有内置价目。"
                "设 LITSEARCH_PRICING 指向价目表可算出金额。",
                fg=typer.colors.YELLOW,
            )
        else:
            typer.secho(f"预计成本          ${cost:,.2f}", fg=typer.colors.YELLOW)
        if provider.prefix_cache:
            typer.echo(
                "注：纳排标准是逐字不变的 system 前缀，端点会自动缓存；"
                f"仅每通道首次请求（共 {report.cold_requests} 次）按未命中计价。"
            )
        typer.secho(
            "⚠️ 没有 count_tokens 端点，以上均为字符数粗估，仅供判断数量级。"
            "真实用量在跑完后由 API 回报。",
            fg=typer.colors.YELLOW,
        )
        return

    failures: list[str] = []

    if host:
        requests = build_requests(loaded, records, per_channel=plan, batch_size=batch_size)
        typer.echo(
            f"\n{len(requests):,} 次 claude -p 调用（宿主后端 · {host_model}，不需要 API key）"
        )
        try:
            channels, host_usage = asyncio.run(
                run_host_screening(
                    requests,
                    model=host_model,
                    concurrency=concurrency,
                    progress=lambda done, total: (
                        typer.echo(f"  {done:,}/{total:,}") if done % 5 == 0 else None
                    ),
                    on_error=lambda req, err: failures.append(f"{req.custom_id}: {err}"),
                )
            )
        except HostBackendError as error:
            typer.secho(str(error), fg=typer.colors.RED, err=True)
            raise typer.Exit(code=2) from error
        typer.echo(
            f"\n实际用量：{host_usage.calls:,} 次调用 / 输出 {host_usage.output_tokens:,} token"
        )
        typer.secho(
            f"API 等价成本：${host_usage.cost_usd:,.4f}（订阅用户走自己的额度，不会这样计费）",
            fg=typer.colors.GREEN,
        )
    else:
        api_key = api_key_from(os.environ) or (Credentials.from_env().api_keys or {}).get(
            "deepseek"
        )
        if not api_key:
            typer.secho(
                f"找不到凭据。请设 {ENV_API_KEY}=...（.env 或环境变量），"
                f"或用 --model {HOST_MODEL} 走宿主模型（零配置）。"
                "仅估算成本可加 --dry-run。",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(code=2)

        cost = report.usage.cost(provider.pricing)
        shown = f"${cost:,.2f}（粗估）" if cost is not None else "未知（该模型无内置价目）"
        typer.echo(f"\n{report.requests:,} 个请求，预计成本 {shown}")

        async def go():
            client = build_screen_client(api_key, base_url=provider.base_url)
            try:
                return await run_screening(
                    loaded,
                    records,
                    client,
                    model=provider.model,
                    concurrency=concurrency,
                    per_channel=plan,
                    batch_size=batch_size,
                    thinking=not provider.disable_thinking,
                    progress=lambda line: typer.echo(line),
                    on_error=failures.append,
                )
            finally:
                await client.close()

        channels, usage = asyncio.run(go())

        typer.echo(
            f"\n实际用量：缓存命中 {usage.cache_hit:,} / 未命中 {usage.cache_miss:,} / "
            f"输出 {usage.output:,}"
        )
        actual = usage.cost(provider.pricing)
        typer.secho(
            f"实际成本：${actual:,.4f}" if actual is not None else "实际成本：未知（无价目）",
            fg=typer.colors.GREEN,
        )
    if failures:
        typer.secho(
            f"\n{len(failures)} 个批次失败——这些记录会因「通道缺少判定」进人工队列，"
            f"不会被当作「没有相关文献」：",
            fg=typer.colors.YELLOW,
        )
        for item in failures[:5]:
            typer.echo(f"  {item}")

    # 宿主续跑可能只请求了编号较小的通道；补齐空槽，才能把旧轮次的其它通道并回。
    while len(channels) < loaded.screening.channels:
        channels.append([])

    if previous:
        # 把上一轮已有的判定按通道并回来，再统一合并——
        # 续跑补的是"缺的那个通道"，不是重判整条记录
        for channel, verdicts in enumerate(regroup_by_channel(previous, loaded.screening.channels)):
            channels[channel].extend(verdicts)

    decisions = merge_verdicts(channels, loaded.screening, expected_keys=by_key)
    counts = summarize(decisions)

    system_prompts = "\n--- channel ---\n".join(
        build_channel_prompt(loaded.criteria, channel)
        for channel in range(loaded.screening.channels)
    )
    endpoint_host = urlsplit(provider.base_url).hostname if provider.base_url else None
    round_metadata = {
        "topic_fingerprint": protocol_fingerprint(loaded),
        "provider": "host" if host else endpoint_host,
        "model": host_model if host else provider.model,
        "endpoint_host": endpoint_host,
        "parameters": {
            "channels": loaded.screening.channels,
            "batch_size": batch_size,
            "concurrency": concurrency,
            "thinking": False if host else not provider.disable_thinking,
        },
        "system_prompt_sha256": hashlib.sha256(system_prompts.encode()).hexdigest(),
        "expected_records": len(by_key),
        "failures": failures,
        "usage": asdict(host_usage if host else usage),
    }

    # 一轮判定比上一轮还少，说明这次跑砸了（配额耗尽、网络中断……）。
    # 写下去会遮蔽上一轮——下游只认轮次号最大的那一轮，等于把好结果弄丢。
    if previous and len(decisions) < len(previous):
        typer.secho(
            f"\n本次只得到 {len(decisions):,} 条判定，少于上一轮的 {len(previous):,} 条——"
            f"判定退步说明这次跑砸了，**不写入新轮次**，上一轮结果保持不变。",
            fg=typer.colors.RED,
            err=True,
        )
        if failures:
            typer.secho(f"失败样例：{failures[0]}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    typer.echo(f"\n{'判定':<16}{'数量':>10}")
    typer.echo("-" * 26)
    for label, key in (("纳入", "include"), ("排除", "exclude"), ("待人工裁定", "human_queue")):
        typer.echo(f"{label:<16}{counts[key]:>10,}")

    missing = sum(1 for item in decisions.values() if item.needs_human and "缺少" in item.reason)
    if missing:
        typer.secho(
            f"其中 {missing:,} 条是**某个通道漏判**（模型没把这条写进返回），"
            f"占 {missing / len(decisions):.1%}",
            fg=typer.colors.YELLOW,
        )

    if limit:
        # 试跑不占轮次：否则一次 --limit 100 的试跑会盖住正式全量结果，
        # 而下游只认轮次号最大的那一轮。
        run_dir.write_text(
            "screening_trial.json",
            ScreeningRound(
                number=1,
                topic_sha256=freeze_topic(topic),
                decisions=decisions,
                **round_metadata,
            ).model_dump_json(indent=2),
        )
        run_dir.write_text("human_queue_trial.csv", render_human_queue(decisions, by_key))
        typer.secho(
            f"\n试跑结果 → {run_dir.root / 'screening_trial.json'}（不计入轮次，下游读不到它）",
            fg=typer.colors.YELLOW,
        )
        return

    existing = [
        int(item.stem.rsplit("_", 1)[-1]) for item in run_dir.root.glob("screening_round_*.json")
    ]
    screened = ScreeningRound(
        number=max(existing, default=0) + 1,
        topic_sha256=freeze_topic(topic),
        decisions=decisions,
        **round_metadata,
    )
    run_dir.write_text(
        f"screening_round_{screened.number}.json", screened.model_dump_json(indent=2)
    )
    run_dir.write_text("human_queue.csv", render_human_queue(decisions, by_key))
    run_dir.write_jsonl(
        "included.jsonl",
        [
            by_key[key].model_dump(mode="json")
            for key, item in decisions.items()
            if not item.needs_human and item.decision.value == "include"
        ],
    )
    typer.echo(f"\n判定 → {run_dir.root / f'screening_round_{screened.number}.json'}")
    typer.secho(
        f"待人工裁定 {counts['human_queue']:,} 条 → {run_dir.root / 'human_queue.csv'}",
        fg=typer.colors.YELLOW,
    )


@app.command("adjudicate")
def adjudicate_command(
    run: str = typer.Argument(..., help="run 目录、<topic>/<run_id>，或 <topic> 取最新"),
    input_file: Path = typer.Option(
        ...,
        "--input",
        exists=True,
        dir_okay=False,
        help="人工裁定 CSV：record_key,decision,reviewer,reason",
    ),
    kind: str = typer.Option("screening", "--kind", help="screening（纳排）或 date（严格窗口）"),
    topic: Path = typer.Option(..., "--topic", help="课题协议 YAML"),
    runs_root: Path = typer.Option(DEFAULT_RUNS_ROOT, "--runs-root"),
) -> None:
    """导入人工裁定并保留原判定、裁定人、时间与理由的审计轨迹。"""
    loaded = _load(topic)
    run_dir = _open_compatible_run(runs_root, run, loaded, topic)
    if kind not in {"screening", "date"}:
        typer.secho("--kind 必须是 screening 或 date", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)
    try:
        rows = load_rows(input_file)
        corpus = [CanonicalRecord.model_validate(row) for row in run_dir.read_jsonl("corpus.jsonl")]
        by_key = {item.key: item for item in corpus}
        input_sha256 = hashlib.sha256(input_file.read_bytes()).hexdigest()

        if kind == "screening":
            round_paths = sorted(
                run_dir.root.glob("screening_round_*.json"),
                key=lambda item: int(item.stem.rsplit("_", 1)[-1]),
            )
            if not round_paths:
                raise AdjudicationError("该 run 没有筛选轮次，无法导入筛选裁定")
            previous_round = ScreeningRound.model_validate_json(
                round_paths[-1].read_text(encoding="utf-8")
            )
            decisions, audit = apply_screening(previous_round.decisions, rows)
            screened = ScreeningRound(
                number=previous_round.number + 1,
                topic_sha256=freeze_topic(topic),
                topic_fingerprint=protocol_fingerprint(loaded),
                provider="human",
                parameters={
                    "kind": "screening",
                    "input_file": input_file.name,
                    "input_sha256": input_sha256,
                    "base_round": previous_round.number,
                },
                expected_records=len(decisions),
                decisions=decisions,
            )
            run_dir.write_text(
                f"screening_round_{screened.number}.json",
                screened.model_dump_json(indent=2),
            )
            existing_audit = run_dir.read_jsonl("adjudications.jsonl")
            run_dir.write_jsonl("adjudications.jsonl", [*existing_audit, *audit])
            run_dir.write_text("human_queue.csv", render_human_queue(decisions, by_key))
            run_dir.write_jsonl(
                "included.jsonl",
                [
                    by_key[key].model_dump(mode="json")
                    for key, item in decisions.items()
                    if key in by_key and not item.needs_human and item.decision is Decision.INCLUDE
                ],
            )
            remaining = summarize(decisions)["human_queue"]
            typer.secho(
                f"已写入人工筛选轮次 {screened.number}：裁定 {len(rows)} 条，"
                f"仍待人工 {remaining} 条。",
                fg=typer.colors.GREEN,
            )
            return

        revised, audit = apply_dates(corpus, rows)
        existing_audit = run_dir.read_jsonl("adjudications.jsonl")
        run_dir.write_jsonl("adjudications.jsonl", [*existing_audit, *audit])
        run_dir.write_jsonl("corpus.jsonl", [item.model_dump(mode="json") for item in revised])
        run_dir.write_text("boundary_cases.csv", boundary_csv(revised))
        manifest = run_dir.load_manifest()
        status_counts = {status.value: 0 for status in WindowStatus}
        for item in revised:
            if item.window_status:
                status_counts[item.window_status.value] += 1
        manifest["counts"] = manifest.get("counts", {}) | status_counts
        manifest.setdefault("notes", []).append(
            f"导入人工日期裁定 {len(rows)} 条（文件 SHA-256 {input_sha256[:16]}…）"
        )
        # manifest 仍是提交标记，最后落盘。
        run_dir.write_text("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        typer.secho(
            f"已导入日期裁定 {len(rows)} 条；剩余边界记录见 "
            f"{run_dir.root / 'boundary_cases.csv'}。",
            fg=typer.colors.GREEN,
        )
    except AdjudicationError as error:
        typer.secho(str(error), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2) from error


def _derived_inputs(run_dir: Run, *, extra: list[str] | None = None) -> list[str]:
    """派生产物依赖的 run 内文件，用于 ``write_artifact`` 记录新鲜度。

    只登记 **run 目录内**的文件——``write_artifact`` 靠哈希比对判断过期，
    而它只能哈希自己管得到的东西。像 ``--ccf`` 目录这种外部输入不在此列：
    换一份目录重跑，哈希检查发现不了。宁可不声称，也不假装覆盖到了。
    """
    inputs = ["manifest.json", "corpus.jsonl"]
    inputs += [path.name for path in sorted(run_dir.root.glob("records*.jsonl"))]
    inputs += [
        name for name in ("topic.yaml", "snowball_rounds.jsonl") if (run_dir.root / name).exists()
    ]
    if rounds := sorted(
        run_dir.root.glob("screening_round_*.json"),
        key=lambda item: int(item.stem.rsplit("_", 1)[-1]),
    ):
        inputs.append(rounds[-1].name)
    inputs += [name for name in (extra or []) if (run_dir.root / name).exists()]
    return inputs


def _depth_sources(depth: str, loaded) -> list[str] | None:
    """把档位翻译成源清单，并把**代价预期**打印出来。

    档位只做减法：协议里没启用的源，任何档位都不会打开——
    否则用户会拿到一份自己没声明过的检索策略。
    """
    try:
        profile = profile_for(depth)
    except ValueError as error:
        typer.secho(str(error), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2) from error

    ready = available_sources()
    enabled = sorted(set(loaded.recall_sources()) & ready)
    chosen = sources_for(profile.depth, enabled=enabled)
    dropped = [name for name in enabled if name not in chosen]
    # 协议里 enabled、注册表里没有的源，在这个交集处被丢掉。丢掉可以，不吭声不行：
    # 用户会以为自己补上了覆盖面，而实际上什么都没发生。
    missing = sorted(set(loaded.recall_sources()) - ready)

    typer.echo(
        f"深度 {profile.depth.value}｜{profile.label}："
        f"预计 {profile.scale}，{profile.wall_clock}，筛选成本 {profile.api_cost}"
    )
    typer.echo(f"  本档跑：{', '.join(chosen) or '（无）'}")
    if missing:
        typer.secho(
            f"  ⚠️ 协议启用但本版本尚未实现：{', '.join(missing)}——"
            f"这些源不会被采集，请勿据此认为覆盖面已补上",
            fg=typer.colors.RED,
        )
    if dropped:
        typer.secho(
            f"  本档跳过：{', '.join(dropped)}（协议里是启用的；换 --depth systematic 可全跑）",
            fg=typer.colors.YELLOW,
        )
    if not profile.runs_snowball:
        typer.secho(
            "  本档不跑滚雪球。实测滚雪球独有贡献占 92%——只想摸底可以，要说得清召回边界必须跑。",
            fg=typer.colors.YELLOW,
        )
    return chosen or None


@app.command("depths")
def depths_command() -> None:
    """三档检索深度的规模、耗时与成本对照。"""
    typer.echo(summary_table())
    typer.echo(
        "\n三档的差别只在**跑多少源、滚几轮雪球**。"
        "判定规则、去重、时间窗、召回率证据在三档里完全一致——"
        "降档降的是覆盖面，不是严谨度。"
    )


def _load_ccf(path: Path | None) -> CcfMatcher | None:
    """载入 CCF 目录。目录由用户提供，不随仓库分发。"""
    if path is None:
        return None
    try:
        entries = load_catalog(path)
    except CcfError as error:
        typer.secho(str(error), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2) from error
    conferences = sum(1 for item in entries if item.kind == "conference")
    typer.echo(
        f"CCF 目录 {path}：{len(entries):,} 条"
        f"（会议 {conferences:,} / 期刊 {len(entries) - conferences:,}）"
    )
    return CcfMatcher(entries)


@app.command("rank")
def rank_command(
    run: str = typer.Argument(..., help="run 目录、<topic>/<run_id>，或 <topic> 取最新"),
    runs_root: Path = typer.Option(DEFAULT_RUNS_ROOT, "--runs-root"),
    included: bool = typer.Option(
        False, "--included", help="只标注筛选纳入的研究（需先跑 lit screen）"
    ),
    ccf: Path = typer.Option(None, "--ccf", help="CCF 推荐目录（.pdf 或 .json）"),
    threshold: float = typer.Option(
        None, "--threshold", help="推演一个阈值的后果——**只报告，不过滤**"
    ),
) -> None:
    """给每条记录标注载体类型与期刊级指标。**只标注，一条也不删。**

    过滤是下游一个显式的、有计数的决定。把"没有指标"和"指标太低"合成同一个
    动作，PRISMA 就数不出来了——而这两者性质完全不同：前者是数据缺失，
    后者才是质量判断。

    指标取 OpenAlex ``2yr_mean_citedness``，**不是 JIF**（JIF 是 Clarivate 授权
    数据，不能随开源仓库分发）。两者标度不同，阈值必须重新校准。
    """
    run_dir = _open_run(runs_root, run)
    records = [CanonicalRecord.model_validate(row) for row in run_dir.read_jsonl("corpus.jsonl")]
    records = [item for item in records if item.window_status == WindowStatus.IN_WINDOW]
    if included:
        decisions = _load_decisions(run_dir)
        if not decisions:
            typer.secho(
                "该 run 还没有筛选结果，--included 无从判断。先跑 lit screen。",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(code=2)
        keep = {
            key
            for key, item in decisions.items()
            if item.decision is Decision.INCLUDE and not item.needs_human
        }
        records = [item for item in records if item.key in keep]

    if not records:
        typer.secho("没有可标注的记录", fg=typer.colors.YELLOW)
        raise typer.Exit(code=0)

    matcher = _load_ccf(ccf)
    credentials = Credentials.from_env()
    client, raw_client = build_client("openalex", credentials)
    dois = sorted(
        {(item.identifiers or {}).get("doi", "").strip().lower() for item in records} - {""}
    )

    async def go():
        try:
            typer.echo(f"取 {len(dois):,} 条 DOI 的 OpenAlex 记录…")
            works = await fetch_works(client, dois, mailto=credentials.contact_email)
            issns = sorted({normalize_issn(item.issn_l) for item in works.values()} - {None})
            typer.echo(f"取 {len(issns):,} 本刊的期刊级指标…")
            journals = await fetch_journals(client, issns, mailto=credentials.contact_email)
            return works, journals
        finally:
            await raw_client.aclose()

    works, journals = asyncio.run(go())
    ranked = rank_records(records, works=works, journals=journals, ccf=matcher)
    summary = match_summary(ranked)

    typer.echo(f"\n{'环节':<20}{'数量':>9}{'占比':>9}")
    typer.echo("-" * 38)
    for label, count in (
        ("记录总数", summary.total),
        ("有 DOI", summary.with_doi),
        ("OpenAlex 命中", summary.with_openalex),
        ("拿到 ISSN", summary.with_issn),
        ("拿到期刊指标", summary.with_metric),
    ):
        typer.echo(f"{label:<20}{count:>9,}{count / summary.total:>8.1%}")

    typer.echo("\n载体构成：")
    for kind, label in (
        (VenueKind.JOURNAL, "期刊"),
        (VenueKind.CONFERENCE, "会议"),
        (VenueKind.PREPRINT, "预印本"),
        (VenueKind.REPOSITORY, "仓库/数据集"),
        (VenueKind.UNKNOWN, "未知"),
    ):
        count = sum(1 for item in ranked if item.kind is kind)
        if count:
            typer.echo(f"  {label:<14}{count:>7,}{count / summary.total:>8.1%}")

    if matcher is not None:
        hits = sum(1 for item in ranked if item.ccf_rank)
        typer.echo(f"\nCCF 命中 {hits:,}（{hits / summary.total:.1%}）：")
        for grade in ("A", "B", "C"):
            count = sum(1 for item in ranked if item.ccf_rank == grade)
            if count:
                typer.echo(f"  CCF-{grade}{count:>10,}")

    typer.echo("\n质量分层：")
    for tier, items in group_by_tier(ranked, today=_today()):
        typer.echo(f"  {tier.heading:<18}{len(items):>7,}{len(items) / summary.total:>8.1%}")

    rank_inputs = _derived_inputs(run_dir)
    run_dir.write_artifact(
        "tier_report.md", tier_report_markdown(ranked, threshold=threshold), inputs=rank_inputs
    )
    run_dir.write_artifact("ranked.csv", ranked_csv(ranked), inputs=rank_inputs)
    run_dir.write_artifact("ranked.jsonl", jsonl_text(ranked_rows(ranked)), inputs=rank_inputs)
    typer.echo(f"\n分层报告 → {run_dir.root / 'tier_report.md'}")
    typer.echo(f"逐条标注 → {run_dir.root / 'ranked.csv'}")
    typer.secho("本命令未过滤任何记录。分层只决定顺序，不决定去留。", fg=typer.colors.YELLOW)


@app.command("deliver")
def deliver_command(
    run: str = typer.Argument(..., help="run 目录、<topic>/<run_id>，或 <topic> 取最新"),
    runs_root: Path = typer.Option(DEFAULT_RUNS_ROOT, "--runs-root"),
    topic: Path = typer.Option(None, "--topic", help="课题协议，用于文档标题与时间窗"),
    included: bool = typer.Option(True, "--included/--all", help="默认只交付筛选纳入的研究"),
    ccf: Path = typer.Option(None, "--ccf", help="CCF 推荐目录（.pdf 或 .json）"),
    style: str = typer.Option("gbt7714", "--style", help="apa / ieee / gbt7714 / nature / ama"),
    bibtex: bool = typer.Option(
        False, "--bibtex", help="另出 references.bib（需再跑一遍 doi.org，耗时翻倍）"
    ),
    refresh: bool = typer.Option(
        False, "--refresh", help="重取 OpenAlex 元数据（默认复用 ranked.jsonl，省日配额）"
    ),
    skip_citations: bool = typer.Option(
        False, "--no-citations", help="只出 DOI 清单，跳过引文格式化"
    ),
) -> None:
    """出两份交付文档：DOI 清单 + 参考文献列表。**全量，分层只决定顺序。**

    高质量的排前面（CCF-A/B、高影响期刊、引用前 1%/10%、最新预印本），
    但一条都不删——被排在后面的仍在文档里，读的人自己判断。

    参考文献走 doi.org 内容协商：免费、无需任何 API key。
    """
    try:
        csl_style = resolve_style(style)
    except _DeliverError as error:
        typer.secho(str(error), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2) from error

    run_dir = _open_run(runs_root, run)
    loaded = _load(topic) if topic else None
    if loaded is not None:
        try:
            assert_topic_compatible(run_dir, loaded, topic)
        except ValueError as error:
            typer.secho(str(error), fg=typer.colors.RED, err=True)
            raise typer.Exit(code=2) from error
    records = [CanonicalRecord.model_validate(row) for row in run_dir.read_jsonl("corpus.jsonl")]
    records = [item for item in records if item.window_status == WindowStatus.IN_WINDOW]
    if included:
        decisions = _load_decisions(run_dir)
        if not decisions:
            typer.secho(
                "该 run 还没有筛选结果。先跑 lit screen，或用 --all 交付全部窗口内记录。",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(code=2)
        keep = {
            key
            for key, item in decisions.items()
            if item.decision is Decision.INCLUDE and not item.needs_human
        }
        records = [item for item in records if item.key in keep]

    if not records:
        typer.secho("没有可交付的记录", fg=typer.colors.YELLOW)
        raise typer.Exit(code=0)

    credentials = Credentials.from_env()
    dois = sorted(
        {(item.identifiers or {}).get("doi", "").strip().lower() for item in records} - {""}
    )
    cached = list(run_dir.read_jsonl("ranked.jsonl")) if not refresh else []

    if cached and len(cached) == len(records):
        # OpenAlex 有日配额，重跑渲染不该再烧一次。
        typer.echo(f"复用 ranked.jsonl（{len(cached):,} 条）；要重取元数据加 --refresh")
        ranked = load_ranked(cached)
    else:
        if cached:
            typer.secho(
                f"ranked.jsonl 有 {len(cached):,} 条，与本次的 {len(records):,} 条不符，重取。",
                fg=typer.colors.YELLOW,
            )
        matcher = _load_ccf(ccf)
        meta_client, meta_raw = build_client("openalex", credentials)

        async def collect_metadata():
            try:
                typer.echo(f"取 {len(dois):,} 条 DOI 的 OpenAlex 记录…")
                works = await fetch_works(meta_client, dois, mailto=credentials.contact_email)
                issns = sorted({normalize_issn(item.issn_l) for item in works.values()} - {None})
                typer.echo(f"取 {len(issns):,} 本刊的期刊级指标…")
                return works, await fetch_journals(
                    meta_client, issns, mailto=credentials.contact_email
                )
            finally:
                await meta_raw.aclose()

        works, journals = asyncio.run(collect_metadata())
        ranked = rank_records(records, works=works, journals=journals, ccf=matcher)

    today = _today()

    typer.echo("\n质量分层：")
    for tier, items in group_by_tier(ranked, today=today):
        share = len(items) / len(ranked)
        typer.echo(f"  {tier.heading:<18}{len(items):>7,}{share:>8.1%}   {tier.rationale}")

    title = loaded.title if loaded else run_dir.root.parent.name
    window = f"{loaded.window.start} ~ {loaded.window.end}" if loaded else None
    # 顺序要紧：dois.md 把 ranked.jsonl 登记为输入，所以缓存必须先落盘。
    # 反过来写的话，记下的是**上一次**的 ranked.jsonl 哈希，产物刚生成就被判过期。
    base_inputs = _derived_inputs(run_dir)
    run_dir.write_artifact("ranked.jsonl", jsonl_text(ranked_rows(ranked)), inputs=base_inputs)
    run_dir.write_artifact("ranked.csv", ranked_csv(ranked), inputs=base_inputs)

    deliver_inputs = [*base_inputs, "ranked.jsonl"]
    run_dir.write_artifact(
        "dois.md",
        dois_markdown(ranked, today=today, title=title, window=window, run_id=run_dir.root.name),
        inputs=deliver_inputs,
    )
    typer.echo(f"\nDOI 清单 → {run_dir.root / 'dois.md'}")
    typer.echo(f"逐条标注 → {run_dir.root / 'ranked.csv'}")

    if skip_citations:
        return

    def collect_citations(fmt: str):
        cite_client, cite_raw = build_client("doi.org", credentials)

        async def go():
            try:
                return await fetch_citations(
                    cite_client,
                    ranked,
                    style=fmt,
                    progress=lambda done: typer.echo(f"  引文 {done:,}/{len(dois):,}"),
                )
            finally:
                await cite_raw.aclose()

        return asyncio.run(go())

    typer.echo(f"\n按 {style} 样式格式化 {len(dois):,} 条引文（doi.org，免 key）…")
    citations = collect_citations(csl_style)
    verified = sum(1 for item in citations.values() if item.verified)

    run_dir.write_artifact(
        "references.md",
        references_markdown(ranked, citations, today=today, title=title, style=style),
        inputs=deliver_inputs,
    )
    typer.echo(f"\n参考文献 → {run_dir.root / 'references.md'}")
    typer.echo(
        f"其中 {verified:,} 条来自出版商登记数据，"
        f"{len(ranked) - verified:,} 条为本地渲染（文档里标 ⚠️）"
    )

    if bibtex:
        # BibTeX 必须单独取一遍：一次请求只能拿一种格式，
        # 拿参考文献样式的结果去写 .bib，产出的文件根本不是 BibTeX。
        typer.echo(f"\n取 {len(dois):,} 条 BibTeX…")
        entries = collect_citations(BIBTEX)
        run_dir.write_artifact(
            "references.bib",
            bibtex_document(ranked, entries, today=today),
            inputs=deliver_inputs,
        )
        typer.echo(f"BibTeX → {run_dir.root / 'references.bib'}")


@app.command("report")
def report_command(
    run: str = typer.Argument(..., help="run 目录、<topic>/<run_id>，或 <topic> 取最新"),
    topic: Path = typer.Option(..., "--topic", help="课题协议 YAML"),
    runs_root: Path = typer.Option(DEFAULT_RUNS_ROOT, "--runs-root"),
) -> None:
    """产出 PRISMA 计数、证据表、覆盖率证据与 Zotero 推送清单。

    各环节计数必须自洽，对不上会直接报错而不是出一份看起来像证据的错报告。
    """
    loaded = _load(topic)
    run_dir = _open_compatible_run(runs_root, run, loaded, topic)
    manifest = run_dir.load_manifest()
    corpus = [CanonicalRecord.model_validate(row) for row in run_dir.read_jsonl("corpus.jsonl")]
    if not corpus:
        typer.secho("该 run 还没有语料，请先 lit harvest。", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)

    # 识别数以**实际落盘的逐源记录**为准，而不是 manifest 的检索式结局：
    # 后者只覆盖走了检索式流程的采集，一旦有阶段忘了写结局，PRISMA 的识别数
    # 就会静默少算（实测 crossref 整卷补全的 670 条就这样漏掉过）。
    identified: dict[str, int] = {}
    for item in _read_all_records(run_dir):
        identified[item.source] = identified.get(item.source, 0) + 1

    by_status: dict[str, int] = {}
    for item in corpus:
        key = item.window_status.value if item.window_status else "unknown"
        by_status[key] = by_status.get(key, 0) + 1

    decisions = _load_decisions(run_dir) or {}
    counts = PrismaCounts(
        identified=identified,
        canonical=len(corpus),
        by_status=by_status,
        screened=summarize(decisions) if decisions else {},
    )

    # 按检索式取**最新**结局：先失败、后补跑成功的源不该一直挂着告警
    degraded = sorted(latest_degraded(manifest.get("outcomes", [])))
    try:
        prisma = prisma_markdown(
            counts,
            title=loaded.title,
            degraded=degraded,
            notes=[f"协议语义指纹 `{manifest.get('topic_fingerprint', '')[:16]}…`"],
        )
    except ReportInconsistency as error:
        typer.secho(f"PRISMA 计数不自洽，拒绝出报告：\n{error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from error

    rounds = run_dir.read_jsonl("snowball_rounds.jsonl")
    # 声明了什么 vs 实际访问了什么。这两者对不上过——续跑把两个从没访问过的源
    # 写进了 manifest，而当时没有任何一份产物提到这件事。
    gaps = find_gaps(
        declared=manifest.get("sources", []),
        executed=sorted({item["source"] for item in manifest.get("outcomes", [])}),
        enabled=loaded.recall_sources(),
        available=available_sources(),
        depth=manifest.get("depth"),
        ran_snowball=bool(rounds),
    )

    by_key = {item.key: item for item in corpus}
    report_inputs = _derived_inputs(run_dir)

    run_dir.write_artifact("PRISMA.md", prisma, inputs=report_inputs)
    run_dir.write_artifact(
        "evidence_table.md",
        evidence_table_markdown(by_key, decisions),
        inputs=report_inputs,
    )
    run_dir.write_artifact("included.csv", included_csv(by_key, decisions), inputs=report_inputs)
    run_dir.write_artifact(
        "coverage_report.md",
        coverage_markdown(
            title=loaded.title,
            corpus=corpus,
            gold_set=loaded.gold_set,
            controls=loaded.out_of_window_controls,
            gaps=gaps,
            snowball_rounds=rounds,
        ),
        inputs=report_inputs,
    )
    dois = zotero_dois(by_key, decisions)
    run_dir.write_artifact(
        "zotero_dois.txt",
        "\n".join(dois) + ("\n" if dois else ""),
        inputs=report_inputs,
    )

    typer.echo(
        f"\n识别 {counts.identified_total:,} → 去重 {counts.canonical:,} "
        f"→ 窗口内 {counts.screening_input:,}"
    )
    if counts.has_screening:
        typer.echo(
            f"纳入 {counts.screened.get('include', 0):,}；"
            f"待人工裁定 {counts.screened.get('human_queue', 0):,}"
        )
    else:
        typer.secho(
            "尚未筛选：PRISMA 只画到「进入标题摘要筛选」。"
            "窗口内记录数不是纳入数，先跑 lit screen。",
            fg=typer.colors.YELLOW,
        )
    if degraded:
        typer.secho(
            f"⚠️ 采集不完整的源：{', '.join(degraded)}——识别数是下界", fg=typer.colors.YELLOW
        )
    for gap in gaps:
        typer.secho(f"⚠️ 未执行：{gap.what}——{gap.why}", fg=typer.colors.YELLOW)

    for name in (
        "PRISMA.md",
        "evidence_table.md",
        "included.csv",
        "coverage_report.md",
        "zotero_dois.txt",
    ):
        typer.echo(f"  {run_dir.root / name}")


@app.command("verify")
def verify_command(
    run: str = typer.Argument(..., help="run 目录、<topic>/<run_id>，或 <topic> 取最新"),
    runs_root: Path = typer.Option(DEFAULT_RUNS_ROOT, "--runs-root"),
    strict: bool = typer.Option(
        False, "--strict", help="把旧格式、无法证明新鲜度的 warning 也视为失败"
    ),
) -> None:
    """检查计数、阶段提交、筛选完整性、协议快照和派生产物是否过期。"""
    run_dir = _open_run(runs_root, run)
    issues = verify_run(run_dir)
    if not issues:
        typer.secho("验证通过：未发现完整性或产物新鲜度问题。", fg=typer.colors.GREEN)
        return

    for item in issues:
        colour = typer.colors.RED if item.severity == "error" else typer.colors.YELLOW
        typer.secho(f"{item.severity.upper():<7} [{item.code}] {item.message}", fg=colour)
    errors = sum(item.severity == "error" for item in issues)
    warnings = len(issues) - errors
    typer.echo(f"\n{errors} 个错误，{warnings} 个警告。")
    if errors or (strict and warnings):
        raise typer.Exit(code=1)


@app.command("show")
def show_command(
    run: str = typer.Argument(..., help="run 目录、<topic>/<run_id>，或 <topic> 取最新"),
    runs_root: Path = typer.Option(DEFAULT_RUNS_ROOT, "--runs-root"),
) -> None:
    """查看一次 run 的清单摘要。"""
    try:
        path = resolve_run(runs_root, run)
    except FileNotFoundError as error:
        typer.secho(str(error), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2) from error

    manifest = Run.open(path).load_manifest()
    typer.echo(f"run       : {manifest['run_id']}")
    typer.echo(f"课题      : {manifest['topic_id']}")
    typer.echo(f"协议哈希  : {manifest['topic_sha256'][:16]}…")
    typer.echo(f"严格窗口  : {manifest['window_start']} ~ {manifest['window_end']}")
    typer.echo(f"采集窗口  : {manifest['harvest_start']} ~ {manifest['harvest_end']}")
    typer.echo(f"深度档位  : {manifest.get('depth') or '未记录（早于该字段的 run）'}")
    typer.echo(f"声明的源  : {', '.join(manifest['sources'])}")
    # 声明 ≠ 执行。这两者对不上过，而当时没有任何产物提到。
    if never_ran := unrun_sources(manifest["sources"], manifest.get("outcomes", [])):
        typer.secho(
            f"未执行的源: {', '.join(never_ran)}——声明了但一条检索式都没跑过",
            fg=typer.colors.RED,
        )
    typer.echo(f"计数      : {manifest['counts']}")
    for note in manifest.get("notes", []):
        typer.secho(f"注意      : {note}", fg=typer.colors.YELLOW)


if __name__ == "__main__":
    app()
