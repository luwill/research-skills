"""PRISMA 计数、纳入集与证据表。

这一层唯一的职责是**让数字自洽**，并在不自洽时**拒绝出报告**。
一份各环节对不上的 PRISMA 流程图比没有更糟——它看起来像证据，实际是错的，
而读者没有办法从报告本身发现这一点。

两条硬规矩：

1. **对不上就抛异常，不出图。** 识别 − 去重 = 规范记录；窗口判定之和 = 规范记录；
   筛选各类之和 = 筛选输入。任何一条不成立都说明上游丢了记录，必须先查清。
2. **没做的事不写进图里。** 筛选还没跑，流程图就只画到"筛选输入"为止，
   并显式写明"尚未筛选"——绝不把窗口内记录数当作纳入数。

证据表同理：方法、数据集、评价指标要读全文才知道，标题摘要阶段拿不到，
就留空并标注"需全文提取"，而不是从标题里猜一个填上去。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from litsearch.dedupe import CanonicalRecord
from litsearch.screen import Decision, MergedDecision

#: 引文闭包与灰色文献属于 PRISMA 2020 的"其他途径"，必须与数据库检索分开计数
OTHER_METHODS = frozenset({"snowball", "grey", "crossref", "cvf", "openreview"})


class ReportInconsistency(RuntimeError):
    """PRISMA 各环节计数对不上。必须先查清，不能出报告。"""


@dataclass
class PrismaCounts:
    #: 各源识别到的**去重前**记录数
    identified: dict[str, int]
    #: 去重后的规范记录数
    canonical: int
    #: 规范记录的窗口判定分布
    by_status: dict[str, int]
    #: 筛选结果分布；为空表示尚未筛选
    screened: dict[str, int] = field(default_factory=dict)

    @property
    def identified_total(self) -> int:
        return sum(self.identified.values())

    @property
    def from_databases(self) -> dict[str, int]:
        return {name: value for name, value in self.identified.items() if name not in OTHER_METHODS}

    @property
    def from_other_methods(self) -> dict[str, int]:
        return {name: value for name, value in self.identified.items() if name in OTHER_METHODS}

    @property
    def duplicates_removed(self) -> int:
        return self.identified_total - self.canonical

    @property
    def screening_input(self) -> int:
        return self.by_status.get("in_window", 0)

    @property
    def excluded_before_screening(self) -> int:
        """按日期排除的记录：窗口外，加上待人工裁定日期的。"""
        return self.canonical - self.screening_input

    @property
    def has_screening(self) -> bool:
        return bool(self.screened)

    def check(self) -> None:
        if self.canonical > self.identified_total:
            raise ReportInconsistency(
                f"去重后（{self.canonical:,}）多于识别数（{self.identified_total:,}）——"
                "去重只会减少记录，这说明上游计数有误"
            )
        status_total = sum(self.by_status.values())
        if status_total != self.canonical:
            raise ReportInconsistency(
                f"窗口判定之和（{status_total:,}）≠ 规范记录数（{self.canonical:,}），"
                f"差 {self.canonical - status_total:,} 条——有记录既没判定也没被计入"
            )
        if self.has_screening:
            screened_total = sum(self.screened.values())
            if screened_total != self.screening_input:
                raise ReportInconsistency(
                    f"筛选各类之和（{screened_total:,}）≠ 筛选输入（{self.screening_input:,}），"
                    f"差 {self.screening_input - screened_total:,} 条——有记录没被判定"
                )


def _rows(counts: dict[str, int]) -> list[str]:
    return [f"  - {name}：{value:,}" for name, value in sorted(counts.items())]


def prisma_markdown(
    counts: PrismaCounts,
    *,
    title: str = "",
    degraded: list[str] | None = None,
    notes: list[str] | None = None,
) -> str:
    """渲染 PRISMA 2020 流程计数。计数对不上会直接抛异常，不出报告。"""
    counts.check()

    lines = [f"# PRISMA 流程计数{' — ' + title if title else ''}", ""]

    lines += ["## 识别（Identification）", ""]
    lines += [f"数据库检索：**{sum(counts.from_databases.values()):,}** 条"]
    lines += _rows(counts.from_databases)
    if other := counts.from_other_methods:
        lines += ["", f"其他途径（引文闭包 / 会议录 / 灰色文献）：**{sum(other.values()):,}** 条"]
        lines += _rows(other)
    lines += ["", f"合计识别：**{counts.identified_total:,}** 条", ""]

    lines += [
        "## 去重（Screening — duplicates）",
        "",
        f"去除重复：**{counts.duplicates_removed:,}** 条",
        f"去重后规范记录：**{counts.canonical:,}** 条",
        "",
    ]

    lines += ["## 按发表日期排除（筛选之前）", ""]
    for key, label in (
        ("out_of_window", "窗口外"),
        ("boundary", "日期精度不足，待人工裁定"),
        ("undated", "无日期证据，待人工裁定"),
    ):
        if value := counts.by_status.get(key):
            lines.append(f"  - {label}：{value:,}")
    lines += [
        "",
        f"排除小计：**{counts.excluded_before_screening:,}** 条",
        f"进入标题摘要筛选：**{counts.screening_input:,}** 条",
        "",
    ]

    if not counts.has_screening:
        lines += [
            "## 筛选（Screening）",
            "",
            "> **尚未筛选。** 本流程图到「进入标题摘要筛选」为止。",
            "> 窗口内记录数**不是**纳入研究数——把它当作纳入数会严重高估证据量。",
            "> 运行 `lit screen` 后重新生成本报告。",
            "",
        ]
    else:
        lines += [
            "## 筛选（Screening）",
            "",
            f"  - 标题摘要初筛通过：**{counts.screened.get('include', 0):,}**",
            f"  - 排除：{counts.screened.get('exclude', 0):,}",
            f"  - 待人工裁定（通道分歧 / 低置信度）：{counts.screened.get('human_queue', 0):,}",
            "",
            "## 进入全文资格审查（Eligibility input）",
            "",
            f"**{counts.screened.get('include', 0):,}** 条候选报告进入全文资格审查。",
            "尚未记录全文获取、全文排除理由或最终纳入研究数；本流程因此止于此处。",
            "",
        ]

    if degraded:
        lines += [
            "## ⚠️ 采集完整性告警",
            "",
            f"以下源存在 partial/failed 的检索式：**{', '.join(sorted(degraded))}**。",
            "其召回数字**不可当作完整值**，上表中相应的识别数是下界而非实际值。",
            "补跑这些检索式后应重新生成本报告。",
            "",
        ]

    if notes:
        lines += ["## 备注", "", *[f"- {item}" for item in notes], ""]

    return "\n".join(lines)


def _included(
    records: dict[str, CanonicalRecord], decisions: dict[str, MergedDecision]
) -> list[tuple[CanonicalRecord, MergedDecision]]:
    pairs = [
        (records[key], verdict)
        for key, verdict in decisions.items()
        if key in records and verdict.decision is Decision.INCLUDE and not verdict.needs_human
    ]
    return sorted(pairs, key=lambda pair: (pair[0].year or 0, pair[0].title))


def included_csv(records: dict[str, CanonicalRecord], decisions: dict[str, MergedDecision]) -> str:
    lines = ["key,year,doi,venue,sources,matched_criteria,title"]
    for record, verdict in _included(records, decisions):
        title = record.title.replace('"', "'")
        venue = (record.venue or "").replace('"', "'")
        lines.append(
            f"{record.key},{record.year or ''},{record.identifiers.get('doi', '')},"
            f'"{venue}",{"+".join(record.sources)},'
            f'{"|".join(verdict.matched_criteria)},"{title}"'
        )
    return "\n".join(lines) + "\n"


def evidence_table_markdown(
    records: dict[str, CanonicalRecord], decisions: dict[str, MergedDecision]
) -> str:
    """标题摘要初筛通过、等待全文资格审查的候选表。

    只写**这一步能核实**的字段。方法、数据集、模态、评价指标要读全文才知道，
    标题摘要筛选阶段拿不到，因此统一标为"需全文提取"——留空比猜一个填上去诚实。
    """
    pairs = _included(records, decisions)
    lines = [
        "# 全文资格审查候选表（尚非最终纳入研究）",
        "",
        f"共 **{len(pairs)}** 条候选报告。方法/数据集/模态/指标及最终资格"
        "需全文核验，本表不做推测。",
        "",
        "| 年份 | 标题 | 来源刊物 | DOI | 命中标准 | 方法·数据集·指标 |",
        "|---|---|---|---|---|---|",
    ]
    for record, verdict in pairs:
        title = record.title.replace("|", "\\|")
        venue = (record.venue or "—").replace("|", "\\|")
        doi = record.identifiers.get("doi", "—")
        lines.append(
            f"| {record.year or '—'} | {title} | {venue} | {doi} | "
            f"{'、'.join(verdict.matched_criteria) or '—'} | _需全文提取_ |"
        )
    return "\n".join(lines) + "\n"


def zotero_dois(
    records: dict[str, CanonicalRecord], decisions: dict[str, MergedDecision]
) -> list[str]:
    """纳入研究里可直接推送 Zotero 的 DOI，按首次出现顺序去重。

    没有 DOI 的记录不在此列——凭空造一个标识符去推送，比漏推一条糟得多。
    它们会出现在 included.csv 里，需人工处理。
    """
    found: list[str] = []
    for record, _ in _included(records, decisions):
        doi = record.identifiers.get("doi")
        if doi and doi not in found:
            found.append(doi)
    return found
