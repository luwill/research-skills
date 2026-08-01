"""交付层：DOI 清单 + 参考文献列表。

**全量交付。** 分层只决定顺序与分节，不决定去留——
被排在后面的记录仍然在文档里，读的人自己判断。

参考文献走 **doi.org 内容协商**：免费、无需任何 API key、支持 CSL 全部样式。
没有 DOI 的记录用本地字段渲染，并**明确标注未经校验**——
一条无法核对的引文混在校验过的引文里，比缺一条更糟。
"""

from __future__ import annotations

import asyncio
import html
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from litsearch.order import group_by_tier
from litsearch.rank import RankedRecord, VenueKind

DOI_RESOLVER = "https://doi.org/"

#: CSL 样式名。**必须先校验**：写错样式名时 doi.org 会对每一条都返回
#: ``{"code":"style-not-found"}`` 的 JSON，而你要到全部跑完才发现。
#: 实测：``vancouver`` 与 ``gb-t-7714-2015-numeric`` 都不存在。
STYLES: dict[str, str] = {
    "apa": "apa",
    "ieee": "ieee",
    "gbt7714": "china-national-standard-gb-t-7714-2015-numeric",
    "nature": "nature",
    "ama": "american-medical-association",
}
BIBTEX = "bibtex"

_ACCEPT_BIBTEX = "application/x-bibtex"


class DeliverError(RuntimeError):
    """交付前置条件不满足。"""


@dataclass(frozen=True, slots=True)
class Citation:
    """一条引文。``verified`` 区分"出版商登记的"与"本地拼的"。"""

    key: str
    text: str
    verified: bool
    error: str | None = None


def resolve_style(name: str) -> str:
    """把用户给的样式名解析成 CSL 样式名；不认识就**立刻报错**。"""
    if name == BIBTEX:
        return BIBTEX
    try:
        return STYLES[name]
    except KeyError:
        raise DeliverError(f"不认识的样式 {name!r}。可选：{', '.join([*STYLES, BIBTEX])}") from None


def accept_header(style: str) -> str:
    if style == BIBTEX:
        return _ACCEPT_BIBTEX
    return f"text/x-bibliography; style={style}"


_LEADING_NUMBER_RE = re.compile(r"^\[\d+\]\s*")
#: 引文再长也不会到这个量级；超过就说明拿回来的是网页
_MAX_CITATION_CHARS = 4000


class NotACitation(ValueError):
    """响应是 200，但内容不是引文。"""


def validate_citation(text: str, *, style: str) -> str:
    """确认返回的**确实是**所要的格式。

    实测：部分 DOI 会被解析到出版商落地页，**HTTP 200 返回整页 HTML**——
    内容协商没被遵守。只挡 JSON 错误是不够的，HTML 会一路写进参考文献。
    这和"枚举源 200 但解析出 0 条"是同一类错误：状态码说成功，内容说别的。
    """
    stripped = text.strip()
    if not stripped:
        raise NotACitation("空响应")
    if stripped.startswith("{"):
        # doi.org 用 200 + JSON 报错（如 style-not-found）
        raise NotACitation(stripped[:120])
    lowered = stripped[:400].lower()
    if stripped.startswith("<") or "<!doctype" in lowered or "<html" in lowered:
        raise NotACitation("返回的是 HTML 页面，不是引文")
    if len(stripped) > _MAX_CITATION_CHARS:
        raise NotACitation(f"响应长度 {len(stripped):,} 字符，不像引文")
    if style == BIBTEX and not stripped.startswith("@"):
        raise NotACitation("不是 BibTeX 条目")
    return stripped


def clean_citation(text: str) -> str:
    """清理 doi.org 返回的引文。

    两件事：**编号样式自带 ``[n]``**（gbt7714 / ieee 都是），而文档自己也要编号，
    不去掉就会出现 ``[1] [1]Billot…``；以及还原 HTML 实体——出版商登记的标题里
    带 ``&amp;`` 是常态，偶尔还有 ``&amp;amp;`` 这类双重转义，所以要反复解到稳定。
    """
    unescaped = html.unescape(text)
    for _ in range(3):
        once = html.unescape(unescaped)
        if once == unescaped:
            break
        unescaped = once
    return _LEADING_NUMBER_RE.sub("", unescaped.strip())


def local_citation(record: RankedRecord) -> str:
    """没有 DOI 时的本地渲染。字段不全就照实留空，不编。"""
    parts = [record.title.strip().rstrip(".")]
    if record.venue:
        parts.append(record.venue.strip())
    if record.date_text:
        parts.append(record.date_text[:4])
    return ". ".join(part for part in parts if part) + "."


def _tier_line(record: RankedRecord) -> str:
    """一条记录的证据标记——说清它为什么排在这里。"""
    marks: list[str] = []
    if record.ccf_rank:
        marks.append(f"CCF-{record.ccf_rank}")
    if record.in_top_1_percent:
        marks.append("引用前 1%")
    elif record.in_top_10_percent:
        marks.append("引用前 10%")
    if record.metric is not None:
        marks.append(f"刊指标 {record.metric:.2f}")
    if record.cited_by_count:
        marks.append(f"被引 {record.cited_by_count:,}")
    return " · ".join(marks)


def dois_markdown(
    ranked: Sequence[RankedRecord],
    *,
    today: date,
    title: str,
    window: str | None = None,
    run_id: str | None = None,
) -> str:
    """按质量层分节的 DOI 清单。**全量，一条不删。**"""
    grouped = group_by_tier(ranked, today=today)
    total = len(ranked)
    with_doi = sum(1 for item in ranked if item.doi)

    lines = [
        f"# {title} · 文献清单",
        "",
        f"> 共 **{total:,}** 条，**全量交付**——分层只决定顺序，不决定去留。",
    ]
    if window:
        lines.append(f"> 时间窗 {window}")
    if run_id:
        lines.append(f"> run `{run_id}` ｜ 生成于 {today.isoformat()}")
    lines += [
        "> 期刊指标为 OpenAlex `2yr_mean_citedness`，**不是 JIF**（标度不同，"
        "发大量会议摘要的刊会被系统性低估）。",
        "> CCF 等级来自你提供的目录；目录里没有的会议标为**未评级**，不是低等级。",
        "",
        "## 分层概览",
        "",
        "| 层 | 判据 | 数量 | 占比 |",
        "|---|---|---:|---:|",
    ]
    for tier, items in grouped:
        share = f"{len(items) / total:.1%}" if total else "—"
        lines.append(f"| **{tier.heading}** | {tier.rationale} | {len(items):,} | {share} |")
    lines += [
        "",
        f"有 DOI **{with_doi:,}** 条（{with_doi / total:.1%}）；"
        f"其余 {total - with_doi:,} 条见文末，需人工处理。",
        "",
    ]

    for tier, items in grouped:
        lines += [f"## {tier.heading}（{len(items):,}）", "", f"> {tier.rationale}", ""]
        if not items:
            lines += ["_本层没有记录。_", ""]
            continue
        lines += ["| # | DOI | 标题 | 载体 | 证据 |", "|---:|---|---|---|---|"]
        for index, item in enumerate(items, start=1):
            doi = f"`{item.doi}`" if item.doi else "—"
            venue = (item.journal_name or item.venue or "—")[:46]
            title_cell = item.title.replace("|", r"\|")[:110]
            lines.append(
                f"| {index} | {doi} | {title_cell} | {venue} | {_tier_line(item) or '—'} |"
            )
        lines.append("")

    missing = [item for item in ranked if not item.doi]
    if missing:
        lines += [
            f"## 无 DOI（{len(missing)}）",
            "",
            "**不为它们编造标识符。** 需人工补齐或按标题检索。",
            "",
            "| 标题 | 载体 | 日期 |",
            "|---|---|---|",
        ]
        for item in missing:
            lines.append(
                f"| {item.title.replace('|', chr(92) + '|')[:110]} | "
                f"{(item.venue or '—')[:40]} | {item.date_text or '—'} |"
            )
        lines.append("")

    return "\n".join(lines)


def references_markdown(
    ranked: Sequence[RankedRecord],
    citations: dict[str, Citation],
    *,
    today: date,
    title: str,
    style: str,
) -> str:
    """参考文献列表，顺序与 DOI 清单一致。"""
    grouped = group_by_tier(ranked, today=today)
    verified = sum(1 for item in citations.values() if item.verified)
    total = len(ranked)

    lines = [
        f"# {title} · 参考文献",
        "",
        f"> 样式 `{style}` ｜ 共 **{total:,}** 条 ｜ 生成于 {today.isoformat()}",
        f"> 其中 **{verified:,}** 条由出版商登记数据渲染（doi.org 内容协商），"
        f"**{total - verified:,}** 条为本地渲染，标 ⚠️。",
        "",
    ]
    counter = 0
    for tier, items in grouped:
        if not items:
            continue
        lines += [f"## {tier.heading}", ""]
        for item in items:
            counter += 1
            citation = citations.get(item.key)
            if citation and citation.verified:
                lines.append(f"[{counter}] {citation.text}")
            else:
                text = citation.text if citation else local_citation(item)
                lines.append(f"[{counter}] ⚠️ {text}")
            lines.append("")
    return "\n".join(lines)


def bibtex_document(
    ranked: Sequence[RankedRecord], citations: dict[str, Citation], *, today: date
) -> str:
    """BibTeX 文件。只写拿到出版商登记数据的条目——
    本地拼出来的 BibTeX 字段不全，混进去会污染整个 .bib。"""
    chunks = [f"% 生成于 {today.isoformat()}；仅含 doi.org 登记数据的条目"]
    skipped = 0
    for item in ranked:
        citation = citations.get(item.key)
        if citation and citation.verified:
            chunks.append(citation.text.strip())
        else:
            skipped += 1
    if skipped:
        chunks.insert(1, f"% 另有 {skipped} 条无法从 doi.org 取得，见 references.md 中标 ⚠️ 的条目")
    return "\n\n".join(chunks) + "\n"


async def fetch_citations(
    client,
    ranked: Sequence[RankedRecord],
    *,
    style: str,
    concurrency: int = 8,
    progress=None,
) -> dict[str, Citation]:
    """按 DOI 逐条取格式化引文。

    单条失败不影响其它条——它降级为本地渲染并**标记为未校验**，
    不会伪装成出版商数据。
    """
    header = accept_header(style)
    semaphore = asyncio.Semaphore(concurrency)
    results: dict[str, Citation] = {}
    done = 0

    async def one(record: RankedRecord) -> None:
        nonlocal done
        async with semaphore:
            try:
                text = await client.get_text(
                    f"{DOI_RESOLVER}{record.doi}", {}, source="doi.org", headers={"Accept": header}
                )
                stripped = validate_citation(text, style=style)
                body = stripped if style == BIBTEX else clean_citation(stripped)
                results[record.key] = Citation(record.key, body, verified=True)
            except Exception as error:  # noqa: BLE001 - 单条失败降级，不中断整批
                results[record.key] = Citation(
                    record.key, local_citation(record), verified=False, error=str(error)[:120]
                )
            done += 1
            if progress and done % 50 == 0:
                progress(done)

    targets = [item for item in ranked if item.doi]
    await asyncio.gather(*(one(item) for item in targets))
    for item in ranked:
        results.setdefault(item.key, Citation(item.key, local_citation(item), verified=False))
    return results


def summarize_kinds(ranked: Sequence[RankedRecord]) -> dict[VenueKind, int]:
    counts = {kind: 0 for kind in VenueKind}
    for item in ranked:
        counts[item.kind] += 1
    return counts
