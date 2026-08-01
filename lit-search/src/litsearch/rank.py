"""期刊/会议分层标注。**只标注，不过滤。**

三条设计原则，每一条都来自实测：

1. **分层是记录上的一个字段，过滤是下游一个显式的、有计数的决定。**
   把"没有分层属性"和"分层太低"合成同一个动作，PRISMA 就数不出来了——
   而这两者的性质完全不同：前者是数据缺失，后者是质量判断。

2. **匹配走 ISSN，不走刊名。** 实测在 26 本刊上，刊名匹配错 2 本（Neuroradiology
   被匹配成 AJNR、Brain Sciences 被匹配成 Behavioral and Brain Sciences）、漏 6 本。
   错配**不会报错**，它给你一个看起来合理的数——这比匹配不上危险得多。

3. **OpenAlex 的 ``2yr_mean_citedness`` 不是 JIF。** JIF 的分母只算 citable items
   （article + review），OpenAlex 的分母算全部条目。发大量学会年会摘要的刊会被
   系统性低估三到五倍：实测 Stroke 得 1.81、Neurology 得 1.11。
   **阈值必须在实际使用的标度上校准，不能跨标度搬运。**
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from litsearch.dedupe import CanonicalRecord

#: 没有可用分层属性时的标签。它**不是**一个低档位——是"这个维度上无法评价"。
UNRANKED = "未分层"

_ISSN_RE = re.compile(r"^(\d{4})-?(\d{3}[\dX])$")

#: DOI 前缀直接决定载体的少数几种情况
_ARXIV_DOI_PREFIX = "10.48550/"

_PREPRINT_VENUES = frozenset(
    {"arxiv", "medrxiv", "biorxiv", "chemrxiv", "techrxiv", "research square", "ssrn", "preprints"}
)
_REPOSITORY_VENUES = frozenset({"zenodo", "figshare", "dryad", "osf", "hal"})

#: 会议论文集常见的载体名。LNCS 是重点：MICCAI/ECCV 都挂在它下面，
#: 按刊处理会给它们一个描述整套丛书的影响因子，对具体会议毫无意义。
_CONFERENCE_HINTS = (
    "lecture notes in computer science",
    "lecture notes in artificial intelligence",
    "proceedings",
    "conference on",
    "workshop",
    "symposium",
)

_CONFERENCE_SOURCE_TYPES = frozenset({"conference", "book series", "proceedings"})
_JOURNAL_SOURCE_TYPES = frozenset({"journal"})
_REPOSITORY_SOURCE_TYPES = frozenset({"repository"})


class VenueKind(StrEnum):
    """载体类型。决定这条记录**该用哪把尺子**，而不是它好不好。"""

    JOURNAL = "journal"
    CONFERENCE = "conference"
    PREPRINT = "preprint"
    REPOSITORY = "repository"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class Band:
    """一个分层档位。``minimum`` 是闭区间下界。"""

    label: str
    minimum: float


#: 默认档位，切在 OpenAlex ``2yr_mean_citedness`` 的标度上。
#: **这些数字不等于 JIF 的同名数字**——见模块文档第 3 条。
DEFAULT_BANDS: tuple[Band, ...] = (
    Band("≥8.0", 8.0),
    Band("4.0–8.0", 4.0),
    Band("2.0–4.0", 2.0),
    Band("<2.0", 0.0),
)


@dataclass(frozen=True, slots=True)
class WorkMetrics:
    """一篇论文在 OpenAlex 上的元数据与论文级指标。"""

    doi: str
    work_type: str | None = None
    source_name: str | None = None
    source_type: str | None = None
    issn_l: str | None = None
    cited_by_count: int | None = None
    in_top_10_percent: bool | None = None
    in_top_1_percent: bool | None = None
    fwci: float | None = None


@dataclass(frozen=True, slots=True)
class JournalMetrics:
    """一本刊的期刊级指标。"""

    issn_l: str
    display_name: str | None = None
    mean_citedness_2yr: float | None = None
    h_index: int | None = None
    works_count: int | None = None
    is_in_doaj: bool | None = None


@dataclass(frozen=True, slots=True)
class RankedRecord:
    """一条记录 + 它的分层标注。原记录不被修改。"""

    key: str
    title: str
    doi: str | None
    venue: str | None
    kind: VenueKind
    band: str
    metric: float | None = None
    h_index: int | None = None
    journal_name: str | None = None
    issn_l: str | None = None
    cited_by_count: int | None = None
    in_top_10_percent: bool | None = None
    in_top_1_percent: bool | None = None
    #: canonical_date 的 ISO 文本。排序要用，但**日期缺失不等于"新"**。
    date_text: str | None = None
    #: CCF 等级 A/B/C；``None`` = 目录里没有 = **未评级，不是低等级**
    ccf_rank: str | None = None
    ccf_name: str | None = None
    #: OpenAlex 是否收录了这个 DOI。显式记录，不从 unmatched_reason 反推——
    #: 靠匹配理由字符串来判断状态，改一句文案就会悄悄改变统计口径。
    openalex_hit: bool = False
    unmatched_reason: str | None = None


@dataclass(frozen=True, slots=True)
class MatchSummary:
    """逐级匹配率。**这是这份报告里最重要的数字。**

    如果只有 60% 的记录能匹配到指标，那么"卡 4 分"实际执行的是
    "卡 4 分**加上删掉所有匹配不上的**"——这两件事完全不同。
    """

    total: int
    with_doi: int
    with_openalex: int
    with_issn: int
    with_metric: int


def normalize_issn(raw: str | None) -> str | None:
    """归一化 ISSN 为 ``NNNN-NNNC`` 形式；不合法返回 ``None``。

    长度不对**不猜**——截断或补齐出来的 ISSN 会静默匹配到另一本刊。
    """
    if not raw:
        return None
    match = _ISSN_RE.match(str(raw).strip().upper())
    return f"{match.group(1)}-{match.group(2)}" if match else None


def _venue_key(record: CanonicalRecord) -> str:
    return (record.venue or "").strip().lower()


def classify_kind(record: CanonicalRecord, work: WorkMetrics | None) -> VenueKind:
    """判定载体类型。OpenAlex 的 ``source_type`` 优先于刊名猜测。"""
    doi = (record.identifiers or {}).get("doi", "")
    if doi.startswith(_ARXIV_DOI_PREFIX):
        return VenueKind.PREPRINT

    venue = _venue_key(record)
    if venue in _PREPRINT_VENUES:
        return VenueKind.PREPRINT
    if venue in _REPOSITORY_VENUES:
        return VenueKind.REPOSITORY

    source_type = (work.source_type or "").lower() if work else ""
    source_name = (work.source_name or "").lower() if work else ""
    haystack = f"{venue} {source_name}"
    if source_type in _CONFERENCE_SOURCE_TYPES:
        return VenueKind.CONFERENCE
    if any(hint in haystack for hint in _CONFERENCE_HINTS):
        return VenueKind.CONFERENCE
    if source_type in _REPOSITORY_SOURCE_TYPES:
        return VenueKind.REPOSITORY
    if source_type in _JOURNAL_SOURCE_TYPES:
        return VenueKind.JOURNAL
    if venue:
        return VenueKind.JOURNAL
    return VenueKind.UNKNOWN


def assign_band(value: float | None, bands: Sequence[Band]) -> str:
    """把一个指标值落进档位。无值即 ``UNRANKED``，不当作最低档。"""
    if value is None:
        return UNRANKED
    for band in bands:
        if value >= band.minimum:
            return band.label
    return UNRANKED


def _doi_of(record: CanonicalRecord) -> str | None:
    return ((record.identifiers or {}).get("doi") or "").strip().lower() or None


def _date_text(record: CanonicalRecord) -> str | None:
    published = getattr(record, "canonical_date", None)
    if not published:
        return None
    earliest = getattr(published, "earliest", None)
    return earliest.isoformat() if earliest else (getattr(published, "text", None) or None)


def rank_records(
    records: Iterable[CanonicalRecord],
    *,
    works: Mapping[str, WorkMetrics],
    journals: Mapping[str, JournalMetrics],
    bands: Sequence[Band] = DEFAULT_BANDS,
    ccf=None,
) -> list[RankedRecord]:
    """给每条记录附上分层标注。**输入多少条，输出多少条。**

    ``ccf`` 是可选的 :class:`~litsearch.ccf.CcfMatcher`。没有目录时会议就是
    "未评级"——**不猜等级**，编出来的 CCF-A 和真的长得一模一样。
    """
    ranked: list[RankedRecord] = []
    for record in records:
        doi = _doi_of(record)
        work = works.get(doi) if doi else None
        kind = classify_kind(record, work)

        issn = normalize_issn(work.issn_l) if work else None
        journal = journals.get(issn) if issn else None

        # 只有期刊才吃期刊级指标。会议拿 LNCS 的影响因子是错的。
        metric = journal.mean_citedness_2yr if (journal and kind is VenueKind.JOURNAL) else None
        h_index = journal.h_index if (journal and kind is VenueKind.JOURNAL) else None

        # 候选名按可信度排：期刊/会议正式名 > 语料 venue > OpenAlex 载体名
        entry = (
            ccf.match(
                journal.display_name if journal else None,
                record.venue,
                work.source_name if work else None,
            )
            if ccf is not None
            else None
        )

        ranked.append(
            RankedRecord(
                key=record.key,
                title=record.title,
                doi=doi,
                venue=record.venue,
                kind=kind,
                band=assign_band(metric, bands),
                metric=metric,
                h_index=h_index,
                journal_name=(journal.display_name if journal else None)
                or (work.source_name if work else None),
                issn_l=issn,
                cited_by_count=work.cited_by_count if work else None,
                in_top_10_percent=work.in_top_10_percent if work else None,
                in_top_1_percent=work.in_top_1_percent if work else None,
                date_text=_date_text(record),
                ccf_rank=entry.rank if entry else None,
                ccf_name=(entry.abbrev or entry.full_name) if entry else None,
                openalex_hit=work is not None,
                unmatched_reason=_unmatched_reason(kind, doi, work, issn, metric),
            )
        )
    return ranked


def _unmatched_reason(
    kind: VenueKind,
    doi: str | None,
    work: WorkMetrics | None,
    issn: str | None,
    metric: float | None,
) -> str | None:
    """说清楚**为什么**没有指标——"缺 DOI"和"这本刊 OpenAlex 没收录"要分开。"""
    if metric is not None:
        return None
    if kind in (VenueKind.PREPRINT, VenueKind.REPOSITORY):
        return "预印本/仓库，无期刊级指标（按设计全部保留）"
    if kind is VenueKind.CONFERENCE:
        return "会议论文，需 CCF 目录评级"
    if doi is None:
        return "无 DOI，无法定位 OpenAlex 记录"
    if work is None:
        return "OpenAlex 未收录该 DOI"
    if issn is None:
        return "OpenAlex 记录无 ISSN"
    return "该 ISSN 无期刊级指标"


def match_summary(ranked: Sequence[RankedRecord]) -> MatchSummary:
    """逐级匹配率。"""
    return MatchSummary(
        total=len(ranked),
        with_doi=sum(1 for item in ranked if item.doi),
        with_openalex=sum(1 for item in ranked if item.openalex_hit),
        with_issn=sum(1 for item in ranked if item.issn_l),
        with_metric=sum(1 for item in ranked if item.metric is not None),
    )


def _pct(part: int, whole: int) -> str:
    return f"{part / whole:.1%}" if whole else "—"


def tier_report_markdown(
    ranked: Sequence[RankedRecord],
    *,
    bands: Sequence[Band] = DEFAULT_BANDS,
    threshold: float | None = None,
    top_journals: int = 40,
) -> str:
    """渲染分层报告。

    报告必须自己声明**它没有过滤任何东西**，否则读的人会当成筛选结果。
    """
    summary = match_summary(ranked)
    lines: list[str] = [
        "# 分层标注报告",
        "",
        f"> 记录 **{summary.total:,}** 条，**未过滤**——本报告只标注，一条也没有删除。",
        "> 指标为 OpenAlex `2yr_mean_citedness`，**不是 JIF**："
        "JIF 分母只算 citable items，OpenAlex 分母算全部条目，",
        "> 发大量会议摘要的期刊会被系统性低估三到五倍（实测 Stroke 1.81、Neurology 1.11）。",
        "> **阈值必须在这个标度上重新校准，不能直接套用 JCR 的数字。**",
        "",
        "## 逐级匹配率",
        "",
        "| 环节 | 数量 | 占比 |",
        "|---|---:|---:|",
        f"| 记录总数 | {summary.total:,} | 100% |",
        f"| 有 DOI | {summary.with_doi:,} | {_pct(summary.with_doi, summary.total)} |",
        f"| OpenAlex 命中 | {summary.with_openalex:,} | "
        f"{_pct(summary.with_openalex, summary.total)} |",
        f"| 拿到 ISSN | {summary.with_issn:,} | {_pct(summary.with_issn, summary.total)} |",
        f"| **拿到期刊指标** | **{summary.with_metric:,}** | "
        f"**{_pct(summary.with_metric, summary.total)}** |",
        "",
    ]

    if summary.with_metric < summary.total:
        gap = summary.total - summary.with_metric
        lines += [
            f"⚠️ **{gap:,} 条（{_pct(gap, summary.total)}）没有期刊级指标。** "
            "对它们设阈值等于直接排除，",
            "而它们大多不是质量问题——是**没有这个属性**。构成见下方「未分层构成」。",
            "",
        ]

    lines += ["## 载体构成", "", "| 载体 | 数量 | 占比 |", "|---|---:|---:|"]
    kind_labels = {
        VenueKind.JOURNAL: "期刊",
        VenueKind.CONFERENCE: "会议",
        VenueKind.PREPRINT: "预印本",
        VenueKind.REPOSITORY: "仓库/数据集",
        VenueKind.UNKNOWN: "未知",
    }
    for kind, label in kind_labels.items():
        count = sum(1 for item in ranked if item.kind is kind)
        if count:
            lines.append(f"| {label} | {count:,} | {_pct(count, summary.total)} |")
    lines.append("")

    journals = [item for item in ranked if item.kind is VenueKind.JOURNAL]
    lines += ["## 期刊分层", "", "| 档位 | 论文数 | 占期刊 |", "|---|---:|---:|"]
    for band in bands:
        count = sum(1 for item in journals if item.band == band.label)
        lines.append(f"| {band.label} | {count:,} | {_pct(count, len(journals))} |")
    unranked_journals = sum(1 for item in journals if item.band == UNRANKED)
    lines.append(
        f"| {UNRANKED}（匹配不到指标） | {unranked_journals:,} | "
        f"{_pct(unranked_journals, len(journals))} |"
    )
    lines.append("")

    if threshold is not None:
        above = sum(1 for item in journals if (item.metric or -1) >= threshold)
        below = sum(1 for item in journals if item.metric is not None and item.metric < threshold)
        rescued = sum(
            1
            for item in journals
            if item.metric is not None and item.metric < threshold and item.in_top_10_percent
        )
        collateral = summary.total - len(journals) + unranked_journals
        lines += [
            f"## 若以 {threshold} 为界（仅推演，未执行）",
            "",
            f"- 期刊论文达标：**{above:,}**",
            f"- 期刊论文不达标：**{below:,}**，其中 **{rescued:,}** 篇本身进入同领域引用前 10%",
            f"- 无期刊级指标而会被一并排除：**{collateral:,}**",
            "",
            "最后一行是这个阈值的**真实代价**——它们不是低质量，是没有被评价过。",
            "",
        ]

    ranked_journals = sorted(
        {
            (item.journal_name or item.venue or "?", item.metric, item.h_index, item.issn_l)
            for item in journals
            if item.metric is not None
        },
        key=lambda row: -(row[1] or 0),
    )
    if ranked_journals:
        counts: dict[str | None, int] = {}
        for item in journals:
            counts[item.issn_l] = counts.get(item.issn_l, 0) + 1
        lines += [
            f"## 期刊清单（按指标降序，前 {top_journals}）",
            "",
            "| 指标 | h | 论文数 | 期刊 | ISSN |",
            "|---:|---:|---:|---|---|",
        ]
        for name, metric, h_index, issn in ranked_journals[:top_journals]:
            lines.append(
                f"| {metric:.2f} | {h_index or '—'} | {counts.get(issn, 0)} | {name} | {issn} |"
            )
        lines.append("")

    reasons: dict[str, int] = {}
    for item in ranked:
        if item.unmatched_reason:
            reasons[item.unmatched_reason] = reasons.get(item.unmatched_reason, 0) + 1
    if reasons:
        lines += ["## 未分层构成", "", "| 原因 | 数量 |", "|---|---:|"]
        for reason, count in sorted(reasons.items(), key=lambda kv: -kv[1]):
            lines.append(f"| {reason} | {count:,} |")
        lines.append("")

    conferences = sorted(
        {
            (item.journal_name or item.venue or "?")
            for item in ranked
            if item.kind is VenueKind.CONFERENCE
        }
    )
    if conferences:
        lines += [
            "## 待 CCF 目录评级的会议载体",
            "",
            "会议没有影响因子，必须用 CCF 目录。**本工具不内置猜测的 CCF 等级**——",
            "编造出来的等级看起来和真的一样，这是最危险的地方。请提供官方目录后重跑。",
            "",
        ]
        lines += [f"- {name}" for name in conferences[:60]]
        if len(conferences) > 60:
            lines.append(f"- …另有 {len(conferences) - 60} 个")
        lines.append("")

    return "\n".join(lines)


OPENALEX_WORKS = "https://api.openalex.org/works"
OPENALEX_SOURCES = "https://api.openalex.org/sources"
#: OpenAlex 的 filter 支持 ``a|b|c`` 取或。50 是官方建议的单次上限——
#: 调大会让 URL 超长，而超长 URL 的失败是 414，不在重试白名单里。
BATCH_SIZE = 50

_WORK_SELECT = "doi,type,cited_by_count,fwci,citation_normalized_percentile,primary_location"
_SOURCE_SELECT = "id,display_name,issn_l,issn,type,is_in_doaj,works_count,summary_stats"


def _batched(items: Sequence[str], size: int = BATCH_SIZE) -> list[list[str]]:
    return [list(items[i : i + size]) for i in range(0, len(items), size)]


def _parse_work(payload: Mapping) -> WorkMetrics | None:
    raw_doi = (payload.get("doi") or "").strip().lower()
    doi = raw_doi.removeprefix("https://doi.org/") or None
    if not doi:
        return None
    source = ((payload.get("primary_location") or {}).get("source")) or {}
    percentile = payload.get("citation_normalized_percentile") or {}
    return WorkMetrics(
        doi=doi,
        work_type=payload.get("type"),
        source_name=source.get("display_name"),
        source_type=source.get("type"),
        issn_l=source.get("issn_l"),
        cited_by_count=payload.get("cited_by_count"),
        in_top_10_percent=percentile.get("is_in_top_10_percent"),
        in_top_1_percent=percentile.get("is_in_top_1_percent"),
        fwci=payload.get("fwci"),
    )


def _parse_source(payload: Mapping) -> JournalMetrics | None:
    issn = normalize_issn(payload.get("issn_l"))
    if not issn:
        return None
    stats = payload.get("summary_stats") or {}
    return JournalMetrics(
        issn_l=issn,
        display_name=payload.get("display_name"),
        mean_citedness_2yr=stats.get("2yr_mean_citedness"),
        h_index=stats.get("h_index"),
        works_count=payload.get("works_count"),
        is_in_doaj=payload.get("is_in_doaj"),
    )


async def fetch_works(
    client, dois: Sequence[str], *, mailto: str | None = None
) -> dict[str, WorkMetrics]:
    """按 DOI 批量取 OpenAlex 记录。返回 ``doi -> WorkMetrics``。

    请求失败会向上抛 ``SourceError``——**不吞**。取不到指标和"这本刊指标很低"
    是完全不同的两件事，静默降级会把前者伪装成后者。
    """
    found: dict[str, WorkMetrics] = {}
    for batch in _batched(list(dois)):
        payload = await client.get_json(
            OPENALEX_WORKS,
            {
                "filter": "doi:" + "|".join(batch),
                "select": _WORK_SELECT,
                "per-page": len(batch),
                "mailto": mailto,
            },
            source="openalex",
        )
        for row in payload.get("results") or []:
            work = _parse_work(row)
            if work:
                found[work.doi] = work
    return found


async def fetch_journals(
    client, issns: Sequence[str], *, mailto: str | None = None
) -> dict[str, JournalMetrics]:
    """按 ISSN 批量取期刊级指标。返回 ``issn_l -> JournalMetrics``。

    一本刊可能有多个 ISSN（印刷版/电子版），查询用请求里的每一个，
    但索引统一落在 ``issn_l`` 上——否则同一本刊会被算成两本。
    """
    found: dict[str, JournalMetrics] = {}
    for batch in _batched(list(issns)):
        payload = await client.get_json(
            OPENALEX_SOURCES,
            {
                "filter": "issn:" + "|".join(batch),
                "select": _SOURCE_SELECT,
                "per-page": len(batch),
                "mailto": mailto,
            },
            source="openalex",
        )
        for row in payload.get("results") or []:
            journal = _parse_source(row)
            if not journal:
                continue
            found[journal.issn_l] = journal
            # 请求里给的 ISSN 可能是电子版，回来的是 issn_l——两边都建索引，
            # 否则按请求的那个 ISSN 去查会查不到。
            for alias in row.get("issn") or []:
                normalized = normalize_issn(alias)
                if normalized:
                    found.setdefault(normalized, journal)
    return found


#: 持久化用的字段清单。显式列出，避免加字段时悄悄改变文件格式。
_RANKED_FIELDS = (
    "key",
    "title",
    "doi",
    "venue",
    "band",
    "metric",
    "h_index",
    "journal_name",
    "issn_l",
    "cited_by_count",
    "in_top_10_percent",
    "in_top_1_percent",
    "date_text",
    "ccf_rank",
    "ccf_name",
    "openalex_hit",
    "unmatched_reason",
)


def ranked_rows(ranked: Sequence[RankedRecord]) -> list[dict]:
    """序列化为可写 JSONL 的字典。

    元数据取自 OpenAlex，有日配额；重跑渲染不该重取一次网络。
    """
    return [
        {"kind": item.kind.value, **{name: getattr(item, name) for name in _RANKED_FIELDS}}
        for item in ranked
    ]


def load_ranked(rows: Iterable[Mapping]) -> list[RankedRecord]:
    """从 :func:`ranked_rows` 的输出还原。未知字段直接忽略，便于向前兼容。"""
    return [
        RankedRecord(
            kind=VenueKind(row["kind"]),
            **{name: row.get(name) for name in _RANKED_FIELDS},
        )
        for row in rows
    ]


def ranked_csv(ranked: Sequence[RankedRecord]) -> str:
    """逐条标注的 CSV，供人工核对与下游过滤。"""
    import csv
    import io

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "key",
            "kind",
            "ccf",
            "band",
            "metric",
            "h_index",
            "cited_by",
            "top1%",
            "top10%",
            "date",
            "journal",
            "issn",
            "doi",
            "title",
            "unmatched_reason",
        ]
    )
    for item in ranked:
        writer.writerow(
            [
                item.key,
                item.kind.value,
                item.ccf_rank or "",
                item.band,
                f"{item.metric:.3f}" if item.metric is not None else "",
                item.h_index or "",
                item.cited_by_count if item.cited_by_count is not None else "",
                "Y" if item.in_top_1_percent else "",
                "Y" if item.in_top_10_percent else "",
                item.date_text or "",
                item.journal_name or item.venue or "",
                item.issn_l or "",
                item.doi or "",
                item.title,
                item.unmatched_reason or "",
            ]
        )
    return buffer.getvalue()
