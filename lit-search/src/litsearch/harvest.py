"""采集编排：干跑计数（plan）与完整翻页采集（harvest）。

`plan` 存在的理由：召回优先的检索式很容易膨胀到上万条，筛选成本必须在真正采集之前
就摆在桌面上，让 topic.yaml 的调整基于实测数字而非猜测。
"""

from __future__ import annotations

import asyncio
import json
import re
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

from litsearch.dedupe import CanonicalRecord, deduplicate
from litsearch.normalize import Record, WindowStatus
from litsearch.protocol import Topic, freeze_topic, protocol_fingerprint
from litsearch.query import SourceQuery, build_queries, strategies_markdown
from litsearch.run import QueryOutcome, Run, RunManifest, new_manifest
from litsearch.sources.base import (
    HarvestResult,
    QuotaExhausted,
    SourceContext,
    SourceError,
    collect,
)
from litsearch.sources.registry import (
    Credentials,
    available_sources,
    build_client,
    build_source,
)


@dataclass
class PlanRow:
    source: str
    query_hash: str
    kind: str
    label: str
    estimate: int | None
    error: str | None = None


@dataclass
class PlanReport:
    topic_id: str
    rows: list[PlanRow]

    def by_source(self) -> dict[str, int | None]:
        """每个源的检索式命中数之和（**含跨检索式重复**，是上界不是去重后的量）。"""
        totals: dict[str, int | None] = {}
        for row in self.rows:
            if row.estimate is None:
                totals.setdefault(row.source, None)
                continue
            current = totals.get(row.source)
            totals[row.source] = row.estimate if current is None else current + row.estimate
        return totals

    def unresolved(self) -> list[PlanRow]:
        return [row for row in self.rows if row.estimate is None]


def _skipped(topic: Topic) -> list[str]:
    return sorted(set(topic.recall_sources()) - available_sources())


async def _run_source_queries(
    source_name: str,
    queries: list[SourceQuery],
    topic: Topic,
    credentials: Credentials,
    raw_root: Path | None,
    max_records_per_query: int | None,
    estimate_only: bool,
    progress: Callable[[str], None] | None = None,
):
    from litsearch.sources.base import PageStore

    client, raw_client = build_client(source_name, credentials)
    context = SourceContext(
        client=client,
        store=PageStore(raw_root),
        topic=topic,
        contact_email=credentials.contact_email,
        api_keys=dict(credentials.api_keys or {}),
        max_records_per_query=max_records_per_query,
    )
    source = build_source(source_name)
    results = []
    quota_error: str | None = None
    try:
        for query in queries:
            if quota_error:
                # 配额已耗尽，后续检索式一律记为 failed 而不是继续白打请求
                results.append(
                    PlanRow(
                        source=source_name,
                        query_hash=query.query_hash,
                        kind=query.kind,
                        label=query.label,
                        estimate=None,
                        error=quota_error,
                    )
                    if estimate_only
                    else HarvestResult(
                        source=source_name,
                        query_hash=query.query_hash,
                        reported_total=None,
                        records=[],
                        pages_fetched=0,
                        status="failed",
                        error=quota_error,
                    )
                )
                continue
            if estimate_only:
                try:
                    results.append(
                        PlanRow(
                            source=source_name,
                            query_hash=query.query_hash,
                            kind=query.kind,
                            label=query.label,
                            estimate=await source.estimate(query, context),
                        )
                    )
                except QuotaExhausted as error:
                    quota_error = str(error)
                    results.append(
                        PlanRow(
                            source=source_name,
                            query_hash=query.query_hash,
                            kind=query.kind,
                            label=query.label,
                            estimate=None,
                            error=quota_error,
                        )
                    )
                except SourceError as error:
                    results.append(
                        PlanRow(
                            source=source_name,
                            query_hash=query.query_hash,
                            kind=query.kind,
                            label=query.label,
                            estimate=None,
                            error=str(error),
                        )
                    )
            else:
                outcome = await collect(source, query, context)
                results.append(outcome)
                if outcome.status == "failed" and outcome.error and "配额" in outcome.error:
                    quota_error = outcome.error
                if progress:
                    flag = "" if outcome.status == "complete" else f" [{outcome.status}]"
                    progress(
                        f"  {source_name:<12} {len(results):>2}/{len(queries)}  "
                        f"{query.kind}/{query.label[:34]:<34} {len(outcome.records):>6,} 条{flag}"
                    )
    finally:
        await raw_client.aclose()
    return results


async def plan(
    topic: Topic, credentials: Credentials, *, only: list[str] | None = None
) -> PlanReport:
    """不落盘、不翻页，只问每条检索式预计命中多少。"""
    queries = build_queries(topic)
    sources = [
        name
        for name in topic.recall_sources()
        if name in available_sources() and (not only or name in only)
    ]

    tasks = [
        _run_source_queries(
            name,
            [query for query in queries if query.source == name],
            topic,
            credentials,
            raw_root=None,
            max_records_per_query=None,
            estimate_only=True,
        )
        for name in sources
    ]
    results = await asyncio.gather(*tasks)
    return PlanReport(topic_id=topic.id, rows=[row for batch in results for row in batch])


@dataclass
class HarvestReport:
    manifest: RunManifest
    canonical: list[CanonicalRecord]
    raw_count: int

    def status_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for record in self.canonical:
            key = record.window_status.value if record.window_status else "unknown"
            counts[key] = counts.get(key, 0) + 1
        return counts


async def harvest(
    topic: Topic,
    topic_path: Path,
    run: Run,
    credentials: Credentials,
    *,
    only: list[str] | None = None,
    depth: str | None = None,
    max_records_per_query: int | None = None,
    progress: Callable[[str], None] | None = None,
    resume_from: Run | None = None,
) -> HarvestReport:
    """多源完整翻页采集 → 规范化 → 去重 → 落盘。

    ``resume_from`` 用于续跑：只重跑上一次 partial/failed 的检索式，
    成功的部分直接从上次的 ``records.jsonl`` 读回。一个源被限流不该让整批结果作废。
    """
    queries = build_queries(topic)
    sources = [
        name
        for name in topic.recall_sources()
        if name in available_sources() and (not only or name in only)
    ]

    previous = resume_from.load_manifest() if resume_from is not None else None
    widened: list[str] = []
    if previous is not None:
        # 续跑**按定义**只重跑上一轮未完成的检索式，它没有能力覆盖一个从没跑过的源。
        # 此时若把当前算出的清单写进 manifest，就等于声称采集了从未访问过的地方——
        # 而这份 manifest 正是"这批文献是怎么来的"的唯一答案。
        inherited = set(previous["sources"])
        widened = [name for name in sources if name not in inherited]
        sources = [name for name in sources if name in inherited]

    manifest = new_manifest(topic, topic_path, run.run_id, sources, depth=depth)
    run.save_topic_snapshot(topic_path)
    attempt_id = uuid.uuid4().hex[:12]
    if skipped := _skipped(topic):
        manifest.notes.append(f"以下源已在协议中启用但尚未实现，本次未采集：{skipped}")
    if widened:
        manifest.notes.append(
            f"续跑不能扩源，以下源本次未采集：{widened}。"
            f"要补这些源请另跑 lit harvest --into <run> --phase <阶段名> "
            f"--sources {','.join(widened)}"
        )

    carried: list[Record] = []
    if previous is not None:
        if previous["topic_sha256"] != manifest.topic_sha256:
            raise ValueError(
                "协议已变更，不能续跑上一次采集——请重新开始，否则结果无法追溯到单一协议版本"
            )
        retry_hashes = {
            item["query_hash"] for item in previous["outcomes"] if item["status"] != "complete"
        }
        done = [item for item in previous["outcomes"] if item["status"] == "complete"]
        for item in done:
            manifest.outcomes.append(QueryOutcome(**item))
        carried = [
            Record.model_validate(row)
            for row in resume_from.read_jsonl("records.jsonl")
            if not set(row.get("found_by") or []) & retry_hashes
        ]
        queries = [query for query in queries if query.query_hash in retry_hashes]
        manifest.notes.append(
            f"续跑自 {previous['run_id']}：沿用 {len(done)} 条已完成检索式的 "
            f"{len(carried):,} 条记录，重跑 {len(queries)} 条未完成检索式"
        )
        if not queries:
            manifest.notes.append("上一次采集没有未完成的检索式，无需续跑")

    tasks = [
        _run_source_queries(
            name,
            [query for query in queries if query.source == name],
            topic,
            credentials,
            raw_root=run.raw / "initial" / attempt_id,
            max_records_per_query=max_records_per_query,
            estimate_only=False,
            progress=progress,
        )
        for name in sources
    ]
    batches = await asyncio.gather(*tasks) if tasks else []

    by_hash = {query.query_hash: query for query in queries}
    records: list[Record] = list(carried)
    for batch in batches:
        for result in batch:
            query = by_hash[result.query_hash]
            manifest.outcomes.append(
                QueryOutcome(
                    source=result.source,
                    query_hash=result.query_hash,
                    kind=query.kind,
                    label=query.label,
                    query=query.query,
                    reported_total=result.reported_total,
                    fetched=len(result.records),
                    status=result.status,
                    error=result.error,
                    truncated=result.truncated,
                )
            )
            records.extend(result.records)

    canonical = deduplicate(records, topic.window, topic.window.date_priority)

    manifest.counts = {
        "records_fetched": len(records),
        "canonical_records": len(canonical),
        "in_window": sum(1 for item in canonical if item.window_status is WindowStatus.IN_WINDOW),
        "boundary": sum(1 for item in canonical if item.window_status is WindowStatus.BOUNDARY),
        "undated": sum(1 for item in canonical if item.window_status is WindowStatus.UNDATED),
        "out_of_window": sum(
            1 for item in canonical if item.window_status is WindowStatus.OUT_OF_WINDOW
        ),
    }
    if degraded := manifest.degraded_sources:
        manifest.notes.append(
            f"以下源采集不完整（partial/failed），其召回数字不可当作完整值：{degraded}"
        )
    manifest.phases["initial"] = {
        "status": "complete",
        "attempt_id": attempt_id,
        "record_file": "records.jsonl",
        "records": len(records),
        "sources": sources,
    }

    run.write_text("search_strategies.md", strategies_markdown(topic, queries))
    # 去重前的逐源记录：resume 时无需重跑已成功的检索式
    run.write_jsonl("records.jsonl", [record.model_dump(mode="json") for record in records])
    run.write_jsonl("corpus.jsonl", [record.model_dump(mode="json") for record in canonical])
    run.write_text("boundary_cases.csv", _boundary_csv(canonical))
    # manifest 是阶段提交标记，必须最后写；否则中断会留下一个看似完整的 run。
    run.save_manifest(manifest)

    return HarvestReport(manifest=manifest, canonical=canonical, raw_count=len(records))


#: 阶段名只允许字母数字与连字符/下划线——它会直接进文件名
_PHASE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


def read_all_records(run: Run) -> list[Record]:
    """读回一次 run 的全部逐源记录。

    ``records.jsonl`` 是主采集，``records_<阶段>.jsonl`` 是后续补全（顶会、整卷、
    滚雪球）。按文件名排序读取，主采集恒排在前。
    """
    return [
        Record.model_validate(row)
        for path in sorted(run.root.glob("records*.jsonl"))
        for row in run.read_jsonl(path.name)
    ]


async def harvest_into(
    topic: Topic,
    topic_path: Path,
    run: Run,
    credentials: Credentials,
    *,
    phase: str,
    only: list[str] | None = None,
    labels: list[str] | None = None,
    queries: list[SourceQuery] | None = None,
    max_records_per_query: int | None = None,
    progress: Callable[[str], None] | None = None,
) -> HarvestReport:
    """把新一批采集并入已有 run，语料按全部阶段重建。

    采集是分阶段的：主干四源 → 顶会/灰色文献 → 会议录整卷 → 引文滚雪球。
    每阶段各写一个 ``records_<阶段>.jsonl``，原始记录只追加不改写，
    "哪一条是哪一阶段拿到的"因此永远可回答；派生的语料随时可重算。

    协议必须与该 run 一致：协议一改，两批结果就不属于同一次系统检索，
    拼起来的语料无法追溯到单一协议版本。
    """
    if not _PHASE_RE.match(phase or ""):
        raise ValueError(f"阶段名 {phase!r} 非法：只允许字母数字与 - _，且不能以符号开头")

    target = run.root / f"records_{phase}.jsonl"
    manifest_data = run.load_manifest()
    phase_committed = manifest_data.get("phases", {}).get(phase, {}).get("status") == "complete"
    legacy_manifest = int(manifest_data.get("schema_version", 1)) < 2
    if target.exists() and (phase_committed or legacy_manifest):
        raise FileExistsError(
            f"阶段 {phase} 的记录已存在（{target.name}）。重跑会覆盖上一次的原始记录——"
            f"请换一个阶段名，或新开一次 run。"
        )

    fingerprint = protocol_fingerprint(topic)
    recorded = manifest_data.get("topic_fingerprint")
    if recorded:
        matches = recorded == fingerprint
    else:
        # 早于该字段的 run：退回字节哈希比对，一致就补记语义指纹，
        # 此后加注释、调整概念块书写顺序都不再误判为"协议已变更"
        matches = manifest_data["topic_sha256"] == freeze_topic(topic_path)
    if not matches:
        raise ValueError(
            "协议已变更，不能并入这次 run——两批结果将无法追溯到单一协议版本。请新开一次 run。"
        )
    manifest_data["topic_fingerprint"] = fingerprint
    attempt_id = uuid.uuid4().hex[:12]

    # 滚雪球的检索式由语料生成而非协议，因此允许直接传入
    from_protocol = queries is None
    queries = build_queries(topic) if from_protocol else list(queries)
    if labels:
        # 只重跑指定的几条检索式——修好某个源的解析缺陷后，不必把整个源重跑一遍
        wanted = set(labels)
        unknown = wanted - {query.label for query in queries}
        if unknown:
            raise ValueError(f"以下 label 不存在于本协议的检索式中：{sorted(unknown)}")
        queries = [query for query in queries if query.label in wanted]

    candidates = (
        topic.recall_sources() if from_protocol else sorted({query.source for query in queries})
    )
    sources = [
        name for name in candidates if name in available_sources() and (not only or name in only)
    ]
    batches = (
        await asyncio.gather(
            *(
                _run_source_queries(
                    name,
                    [query for query in queries if query.source == name],
                    topic,
                    credentials,
                    raw_root=run.raw / phase / attempt_id,
                    max_records_per_query=max_records_per_query,
                    estimate_only=False,
                    progress=progress,
                )
                for name in sources
            )
        )
        if sources
        else []
    )

    by_hash = {query.query_hash: query for query in queries}
    fetched: list[Record] = []
    degraded: set[str] = set()
    for batch in batches:
        for result in batch:
            query = by_hash[result.query_hash]
            manifest_data["outcomes"].append(
                asdict(
                    QueryOutcome(
                        source=result.source,
                        query_hash=result.query_hash,
                        kind=query.kind,
                        label=query.label,
                        query=query.query,
                        reported_total=result.reported_total,
                        fetched=len(result.records),
                        status=result.status,
                        error=result.error,
                        truncated=result.truncated,
                    )
                )
            )
            if result.status != "complete":
                degraded.add(result.source)
            fetched.extend(result.records)

    run.write_jsonl(target.name, [record.model_dump(mode="json") for record in fetched])

    records = read_all_records(run)
    canonical = deduplicate(records, topic.window, topic.window.date_priority)

    manifest_data["sources"] = sorted({*manifest_data.get("sources", []), *sources})
    manifest_data["counts"] = (
        manifest_data.get("counts", {})
        | _window_counts(canonical)
        | {
            "records_fetched": len(records),
            "canonical_records": len(canonical),
        }
    )
    manifest_data.setdefault("notes", []).append(
        f"阶段 {phase} 并入：源 {sources}，新增 {len(fetched):,} 条逐源记录"
    )
    if degraded:
        manifest_data["notes"].append(
            f"阶段 {phase} 中以下源采集不完整（partial/failed），"
            f"其召回数字不可当作完整值：{sorted(degraded)}"
        )

    run.write_jsonl("corpus.jsonl", [item.model_dump(mode="json") for item in canonical])
    run.write_text("boundary_cases.csv", _boundary_csv(canonical))
    manifest_data.setdefault("phases", {})[phase] = {
        "status": "complete",
        "attempt_id": attempt_id,
        "record_file": target.name,
        "records": len(fetched),
        "sources": sources,
    }
    manifest_data.setdefault("schema_version", 2)
    # manifest 最后提交。若此前中断，schema v2 允许同名阶段重新生成并原子替换。
    run.write_text("manifest.json", json.dumps(manifest_data, ensure_ascii=False, indent=2))

    manifest = RunManifest(
        **{key: value for key, value in manifest_data.items() if key != "outcomes"},
        outcomes=[QueryOutcome(**item) for item in manifest_data["outcomes"]],
    )
    return HarvestReport(manifest=manifest, canonical=canonical, raw_count=len(records))


def _window_counts(canonical: list[CanonicalRecord]) -> dict[str, int]:
    counts = {status.value: 0 for status in WindowStatus}
    for record in canonical:
        if record.window_status:
            counts[record.window_status.value] += 1
    return counts


def _boundary_csv(canonical: list[CanonicalRecord]) -> str:
    """边界与无日期记录清单——这些绝不能被静默处理，必须人工裁定。"""
    header = (
        "record_key,current_status,decision,reviewer,reason,"
        "canonical_date,precision,doi,title,sources,evidence"
    )
    lines = [header]
    for record in canonical:
        if not record.needs_human_review:
            continue
        date_text = str(record.canonical_date) if record.canonical_date else ""
        precision = record.canonical_date.precision if record.canonical_date else ""
        evidence = " | ".join(
            f"{field}={value}" for field, value in record.dates.model_dump().items() if value
        )
        title = record.title.replace('"', "'")
        lines.append(
            f"{record.key},{record.window_status.value},,,,{date_text},{precision},"
            f'{record.identifiers.get("doi", "")},"{title}",'
            f'{"+".join(record.sources)},"{evidence}"'
        )
    return "\n".join(lines) + "\n"
