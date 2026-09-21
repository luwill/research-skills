"""``lit facets``：给已纳入的记录打类型化标注。

产物只有两份独立文件，**不进证据表、不进 included.csv**——``report.py`` 明令
禁止猜测只有全文才知道的字段，而摘要标注恰恰只是「摘要说了什么」，不是
「研究做了什么」。把它灌进证据表，就是把一层推测混进一层事实里。
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import typer

from litsearch.cli_support import (
    DEFAULT_RUNS_ROOT,
    load_topic_or_exit,
    open_compatible_run_or_exit,
)
from litsearch.dedupe import CanonicalRecord
from litsearch.facets import (
    DEFAULT_FACETS,
    STATED,
    FacetRow,
    active_facets,
    compile_facet_questions,
    facet_questions_sha256,
    facets_csv,
    facets_for,
    pending_facets,
    score_facets,
)
from litsearch.jev_client import JevFatalError, build_jev_client
from litsearch.providers import describe as describe_provider
from litsearch.providers import resolve_provider
from litsearch.screen_jev import CHARS_PER_TOKEN, build_state
from litsearch.sources.registry import Credentials

FACET_ROWS = "facets.jsonl"
FACET_TABLE = "facets.csv"
CHECKPOINT_EVERY = 200


def _load_rows(run_dir) -> dict[str, FacetRow]:
    return {row["record_key"]: FacetRow.from_json(row) for row in run_dir.read_jsonl(FACET_ROWS)}


def _estimate_tokens(records, questions, profile) -> int:
    question_chars = len(json.dumps(questions, ensure_ascii=False))
    total = 0
    for item in records:
        state_chars = len(json.dumps(build_state(item, profile), ensure_ascii=False))
        total += int((state_chars + question_chars) / CHARS_PER_TOKEN)
    return total


def facets_command(
    run: str = typer.Argument(..., help="run 目录、<topic>/<run_id>，或 <topic> 取最新"),
    topic: Path = typer.Option(..., "--topic", help="课题协议 YAML"),
    jev_profile: Path = typer.Option(..., "--jev-profile", help="判定 API 的阈值与标注配置"),
    runs_root: Path = typer.Option(DEFAULT_RUNS_ROOT, "--runs-root"),
    dry_run: bool = typer.Option(False, "--dry-run", help="只估成本，不打网络"),
    concurrency: int = typer.Option(16, "--concurrency", min=1),
) -> None:
    """给已纳入的记录打标注：外部验证、多中心、公开数据集、代码公开、前瞻性设计。

    每个问题都问「摘要**明确陈述**了 X 吗」，答案只有 stated / not_stated，
    **永远没有 no**——摘要没提外部验证，不等于这项研究没做外部验证。
    产物是独立的 facets.jsonl / facets.csv，不参与任何自动判定。
    """
    from litsearch.cli_judge import _require_profile

    loaded = load_topic_or_exit(topic)
    run_dir = open_compatible_run_or_exit(runs_root, run, loaded, topic)
    profile = _require_profile(jev_profile, loaded)
    provider = resolve_provider(profile.model)

    records = [CanonicalRecord.model_validate(row) for row in run_dir.read_jsonl("included.jsonl")]
    if not records:
        typer.secho(
            "included.jsonl 是空的——先跑 lit screen 把纳入集定下来。",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=2)

    facets = active_facets(profile)
    if not profile.facets:
        typer.secho(
            f"配置里没写 facets，用随附的 {len(DEFAULT_FACETS)} 个通用维度："
            f"{'、'.join(item.id for item in DEFAULT_FACETS)}。"
            f"课题特有的维度请在判定配置里覆盖。",
            fg=typer.colors.YELLOW,
        )

    questions = compile_facet_questions(profile)
    digest = facet_questions_sha256(questions)
    known = _load_rows(run_dir)
    pending = pending_facets(records, known, digest)
    typer.echo(f"\n已纳入 {len(records):,} 条，待标注 {len(pending):,} 条，{len(facets)} 个维度")

    if dry_run:
        tokens = _estimate_tokens(pending, questions, profile)
        typer.echo(f"后端            {describe_provider(provider)}")
        typer.echo(f"请求数          {len(pending):,}")
        typer.echo(f"输入 token（估） {tokens:,}")
        if provider.pricing:
            typer.secho(
                f"预计成本        ${tokens / 1_000_000 * provider.pricing.input_miss:,.4f}"
                f"（输出免费）",
                fg=typer.colors.YELLOW,
            )
        return

    if pending:
        known = _run_scoring(run_dir, profile, pending, known, concurrency)

    run_dir.write_jsonl(FACET_ROWS, [known[key].to_json() for key in sorted(known)])
    run_dir.write_artifact(
        FACET_TABLE, facets_csv(known, records, profile), inputs=["included.jsonl"]
    )
    _echo_summary(known, records, profile)
    typer.secho(
        f"标注 → {run_dir.root / FACET_TABLE}（概率也留在 {FACET_ROWS} 里，阈值随时可改）",
        fg=typer.colors.GREEN,
    )


def _run_scoring(run_dir, profile, pending, known, concurrency) -> dict[str, FacetRow]:
    api_key = (Credentials.from_env().api_keys or {}).get("typesafe")
    if not api_key:
        typer.secho(
            "找不到判定 API 密钥。设 TYPESAFE_API_KEY 后重试；仅估算可加 --dry-run。",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=2)

    failures: list[str] = []
    buffer: list[FacetRow] = []

    def checkpoint(row: FacetRow) -> None:
        buffer.append(row)
        if len(buffer) % CHECKPOINT_EVERY == 0:
            snapshot = {**known, **{item.record_key: item for item in buffer}}
            run_dir.write_jsonl(FACET_ROWS, [snapshot[key].to_json() for key in sorted(snapshot)])

    async def go():
        client, raw = build_jev_client(api_key, model=profile.model)
        try:
            return await score_facets(
                client,
                pending,
                profile,
                state_of=lambda item: build_state(item, profile),
                concurrency=concurrency,
                on_error=lambda key, err: failures.append(f"{key}: {err}"),
                checkpoint=checkpoint,
                progress=lambda done, total: (
                    typer.echo(f"  {done:,}/{total:,}") if done % 200 == 0 else None
                ),
            )
        finally:
            await raw.aclose()

    try:
        rows, tokens = asyncio.run(go())
    except JevFatalError as error:
        typer.secho(f"\n请求本身不合法，整轮中止：{error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2) from error

    if failures:
        typer.secho(
            f"{len(failures):,} 条标注失败，它们在表里记为「未标注」而不是「没有」。",
            fg=typer.colors.YELLOW,
        )
    typer.echo(f"输入 token {tokens:,}")
    return {**known, **{item.record_key: item for item in rows}}


def _echo_summary(rows, records, profile) -> None:
    typer.echo(f"\n{'维度':<22}{'摘要明确陈述':>14}")
    typer.echo("-" * 36)
    for facet in active_facets(profile):
        stated = sum(
            1
            for item in records
            if (row := rows.get(item.key)) and facets_for(row, profile).get(facet.id) == STATED
        )
        typer.echo(f"{facet.id:<22}{stated:>8,} / {len(records):,}")
    typer.secho(
        "注：这些数字是「摘要里说了」的条数，**不是**「做到了」的条数——"
        "没说不等于没做，别把它当成质量评分。",
        fg=typer.colors.YELLOW,
    )
