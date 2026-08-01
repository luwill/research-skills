"""质量分层排序。**全量交付，只改顺序。**

为什么是排序而不是过滤：阈值会把"没被评价过"和"质量低"变成同一个动作，
而前者在这份语料里占 22.9%——它们不是低质量，是**没有这个属性**。
排序保住全量，同时让读的人一眼看出哪些是高质量的。

三条判据上的诚实边界：

1. **没有 CCF 目录，就不判定"顶会"。** 会议靠**论文级**影响力进前排
   （同领域引用前 1% / 前 10%）——那是可证的事实，而会议等级是我猜的。
   编出来的等级和真的长得一模一样，这是最危险的地方。
2. **期刊指标是 OpenAlex ``2yr_mean_citedness``，不是 JIF**，标度不同。
   所以任何期刊指标的档位都配了一条**论文级旁路**：低分刊上的高被引论文
   照样进前排（实测 Neurology 被引 175、Stroke 被引 142 都在这条路上）。
3. **日期缺失不等于"新"。** 没有日期的预印本不进"最新"档——
   猜"新"会把三年前的预印本推到列表最前面。
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from enum import Enum

from litsearch.rank import RankedRecord, VenueKind

#: 预印本"最新"的时间跨度。18 个月：够长到覆盖一轮投稿-返修周期，
#: 短到还没被期刊版本取代。
PREPRINT_FRESH_DAYS = 548

#: 进入"顶刊/高影响"档的期刊指标下界（OpenAlex 标度，不是 JIF 标度）
TOP_METRIC = 8.0
#: 进入"优质期刊"档的期刊指标下界
STRONG_METRIC = 4.0


class Tier(Enum):
    """质量层。每一层都要说得出"为什么在这里"。"""

    BENCHMARK = ("S", "顶会顶刊 / 标杆", "CCF-A，或论文引用进入同领域前 1%")
    TOP = (
        "A",
        "高水平",
        f"CCF-B，或期刊指标 ≥ {TOP_METRIC}，或论文进入同领域引用前 10%",
    )
    STRONG = ("B", "优质", f"CCF-C，或期刊指标 {STRONG_METRIC}–{TOP_METRIC}")
    FRESH_PREPRINT = (
        "C",
        "最新预印本",
        f"预印本 / 仓库，且发布于最近 {PREPRINT_FRESH_DAYS // 30} 个月内",
    )
    CONFERENCE = ("D", "会议（未评级）", "会议载体，但 CCF 目录里没有——**未评级，不是低等级**")
    OTHER_JOURNAL = ("E", "其它期刊", f"期刊指标 < {STRONG_METRIC}，且不在 CCF 目录")
    REMAINDER = ("F", "其余", "早期预印本 / 仓库 / 无任何评价依据——**未被评价，不是低质量**")

    def __init__(self, code: str, label: str, rationale: str) -> None:
        self.code = code
        self.label = label
        self.rationale = rationale

    @property
    def heading(self) -> str:
        return f"{self.code}｜{self.label}"


#: 层的先后。显式写出来，不依赖枚举定义顺序——
#: 顺序是产品决定，改枚举定义不该悄悄改变文档结构。
TIER_ORDER: tuple[Tier, ...] = (
    Tier.BENCHMARK,
    Tier.TOP,
    Tier.STRONG,
    Tier.FRESH_PREPRINT,
    Tier.CONFERENCE,
    Tier.OTHER_JOURNAL,
    Tier.REMAINDER,
)


def _parse_date(text: str | None) -> date | None:
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _is_fresh(record: RankedRecord, today: date) -> bool:
    published = _parse_date(record.date_text)
    if published is None:
        return False
    return (today.toordinal() - published.toordinal()) <= PREPRINT_FRESH_DAYS


#: CCF 等级到层的映射
_CCF_TIER = {"A": Tier.BENCHMARK, "B": Tier.TOP, "C": Tier.STRONG}


def assign_tier(record: RankedRecord, *, today: date) -> Tier:
    """给一条记录定层：**取所有可用信号里最好的那个**。

    CCF 与影响力指标测的是不同的东西——实测 Medical Image Analysis 是 CCF-C，
    但它的 OpenAlex 指标 10.14 是全语料最高。压成一个轴会两边都失真，
    所以取较优：**任何一把公认的尺子说它好，它就该排在前面。**
    """
    candidates: list[Tier] = []

    if tier := _CCF_TIER.get(record.ccf_rank or ""):
        candidates.append(tier)

    # 论文级证据对会议同样适用——没有 CCF 目录时，这是会议进前排的唯一诚实通道。
    if record.in_top_1_percent:
        candidates.append(Tier.BENCHMARK)
    elif record.in_top_10_percent:
        candidates.append(Tier.TOP)

    metric = record.metric
    if metric is not None:
        if metric >= TOP_METRIC:
            candidates.append(Tier.TOP)
        elif metric >= STRONG_METRIC:
            candidates.append(Tier.STRONG)
        else:
            candidates.append(Tier.OTHER_JOURNAL)

    if record.kind in (VenueKind.PREPRINT, VenueKind.REPOSITORY) and _is_fresh(record, today):
        candidates.append(Tier.FRESH_PREPRINT)

    if candidates:
        return min(candidates, key=TIER_ORDER.index)

    # 没有任何评价依据。会议单列，其余归入"其余"——
    # 把未评价的混进低分档，就等于替它下了一个没有依据的结论。
    if record.kind is VenueKind.CONFERENCE:
        return Tier.CONFERENCE
    return Tier.REMAINDER


def _within_tier_key(record: RankedRecord, tier: Tier) -> tuple:
    """层内排序键。

    已评级的层按**被引降序**——引用量是横跨期刊、会议、预印本的同一种货币，
    换成期刊指标就没法给会议排序了。指标与日期依次做决胜。
    时效性本身由"最新预印本"这一层承载，不必再混进排序键。
    """
    cited = record.cited_by_count or 0
    metric = record.metric or 0.0
    published = _parse_date(record.date_text)
    recency = published.toordinal() if published else 0

    if tier in (Tier.FRESH_PREPRINT, Tier.REMAINDER):
        return (-recency, -cited)
    return (-cited, -metric, -recency)


def order_ranked(records: Sequence[RankedRecord], *, today: date) -> list[RankedRecord]:
    """按质量层排序。**输入多少条，输出多少条。**

    排序是稳定的：同分时保持输入顺序，让同一份语料每次都产出同一份文档。
    """
    tier_index = {tier: position for position, tier in enumerate(TIER_ORDER)}
    decorated = [
        (
            tier_index[assign_tier(item, today=today)],
            _within_tier_key(item, assign_tier(item, today=today)),
            position,
            item,
        )
        for position, item in enumerate(records)
    ]
    decorated.sort(key=lambda row: (row[0], row[1], row[2]))
    return [row[3] for row in decorated]


def tier_of(record: RankedRecord, *, today: date) -> Tier:
    """公开的单条定层入口，供渲染层复用。"""
    return assign_tier(record, today=today)


def tier_counts(records: Sequence[RankedRecord], *, today: date) -> dict[Tier, int]:
    """每层的记录数。总和必然等于输入条数——这是排序层不丢数据的凭据。"""
    counts = {tier: 0 for tier in TIER_ORDER}
    for item in records:
        counts[assign_tier(item, today=today)] += 1
    return counts


def group_by_tier(
    records: Sequence[RankedRecord], *, today: date
) -> list[tuple[Tier, list[RankedRecord]]]:
    """按层分组，层内已排序。空层也保留——"这一层一条都没有"是有信息量的。"""
    ordered = order_ranked(records, today=today)
    grouped: dict[Tier, list[RankedRecord]] = {tier: [] for tier in TIER_ORDER}
    for item in ordered:
        grouped[assign_tier(item, today=today)].append(item)
    return [(tier, grouped[tier]) for tier in TIER_ORDER]
