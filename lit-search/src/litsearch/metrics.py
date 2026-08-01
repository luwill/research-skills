"""召回率证据。

"尽可能全面"必须可验证，否则只是一句自我评价。这里给三类证据：

1. **金标准召回**——手工列出的必检文献是否全部命中。低于 100% 说明检索策略有洞。
2. **来源独有贡献**——每个源贡献了多少别的源没有的记录。为 0 说明该源冗余。
3. **捕获-再捕获**——用两个独立源的重叠度估计"总体有多大"，从而估计漏了多少。

外加**窗口外对照**：确认严格窗口过滤真的生效，而不是只靠源端的日期参数。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from litsearch.dedupe import CanonicalRecord
from litsearch.normalize import WindowStatus
from litsearch.protocol import SeedItem


def _matches(record: CanonicalRecord, seed: SeedItem) -> bool:
    return any(record.has_identifier(kind, value) for kind, value in seed.identifiers.items())


def _find(records: list[CanonicalRecord], seed: SeedItem) -> CanonicalRecord | None:
    return next((record for record in records if _matches(record, seed)), None)


@dataclass
class GoldSetReport:
    total: int
    found_count: int
    missing: list[SeedItem] = field(default_factory=list)
    found_out_of_window: list[SeedItem] = field(default_factory=list)
    found_pending_date: list[SeedItem] = field(default_factory=list)

    @property
    def recall(self) -> float | None:
        """金标准为空时返回 None——不能把"没有标准"粉饰成"满分"。"""
        return self.found_count / self.total if self.total else None


def gold_set_recall(gold_set: list[SeedItem], records: list[CanonicalRecord]) -> GoldSetReport:
    """金标准命中率。任何漏检都必须点名，以便回溯到具体的检索式缺陷。"""
    missing: list[SeedItem] = []
    out_of_window: list[SeedItem] = []
    pending_date: list[SeedItem] = []
    found = 0

    for seed in gold_set:
        record = _find(records, seed)
        if record is None:
            missing.append(seed)
            continue
        if record.window_status is WindowStatus.IN_WINDOW:
            found += 1
        elif record.window_status is WindowStatus.OUT_OF_WINDOW:
            out_of_window.append(seed)
        else:
            pending_date.append(seed)

    return GoldSetReport(
        total=len(gold_set),
        found_count=found,
        missing=missing,
        found_out_of_window=out_of_window,
        found_pending_date=pending_date,
    )


@dataclass
class LeakageReport:
    checked: int
    leaked: list[SeedItem] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return not self.leaked


def out_of_window_leakage(
    controls: list[SeedItem], records: list[CanonicalRecord]
) -> LeakageReport:
    """窗口外对照若出现在窗口内结果中，说明 canonical_date 过滤没生效。"""
    leaked = [
        seed
        for seed in controls
        if (record := _find(records, seed)) and record.window_status is WindowStatus.IN_WINDOW
    ]
    return LeakageReport(checked=len(controls), leaked=leaked)


@dataclass
class SourceRow:
    source: str
    total: int
    unique: int

    @property
    def redundant(self) -> bool:
        """该源没有贡献任何别处没有的记录——删掉它不影响召回。"""
        return self.unique == 0

    @property
    def unique_share(self) -> float:
        return self.unique / self.total if self.total else 0.0


def source_contribution(records: list[CanonicalRecord]) -> list[SourceRow]:
    """每个源的总贡献与独有贡献。独有贡献高 = 少了它就会漏。"""
    totals: dict[str, int] = {}
    uniques: dict[str, int] = {}

    for record in records:
        for source in record.sources:
            totals[source] = totals.get(source, 0) + 1
        if len(record.sources) == 1:
            only = record.sources[0]
            uniques[only] = uniques.get(only, 0) + 1

    return sorted(
        (
            SourceRow(source=name, total=count, unique=uniques.get(name, 0))
            for name, count in totals.items()
        ),
        key=lambda row: row.total,
        reverse=True,
    )


@dataclass
class CaptureRecapture:
    observed: int
    total: float | None
    note: str = ""

    @property
    def recall(self) -> float | None:
        """两源并集相对 Chapman 总体估计的覆盖度，不是整条流水线召回率。"""
        if self.total is None or self.total <= 0:
            return None
        return min(1.0, self.observed / self.total)


def capture_recapture(*, captured_a: int, captured_b: int, overlap: int) -> CaptureRecapture:
    """Chapman 估计量：N ≈ (n_a+1)(n_b+1)/(m+1) − 1。

    两个源必须近似独立才有意义（如 PubMed 与 OpenAlex 的索引策略不同）。
    零重叠时估计量发散，此时明确返回"无法估计"而不是编一个数字。
    """
    observed = captured_a + captured_b - overlap

    if captured_a <= 0 or captured_b <= 0:
        return CaptureRecapture(observed=observed, total=None, note="某一样本为空，无法估计")
    if overlap <= 0:
        return CaptureRecapture(
            observed=observed,
            total=None,
            note="两个样本零重叠，Chapman 估计不成立；请改用重叠度更高的一对源",
        )

    estimate = (captured_a + 1) * (captured_b + 1) / (overlap + 1) - 1
    variance = (
        (captured_a + 1) * (captured_b + 1) * (captured_a - overlap) * (captured_b - overlap)
    ) / ((overlap + 1) ** 2 * (overlap + 2))
    stderr = math.sqrt(variance) if variance > 0 else 0.0

    return CaptureRecapture(
        observed=observed,
        total=estimate,
        note=f"Chapman 估计 {estimate:,.0f} ± {1.96 * stderr:,.0f} (95% CI)",
    )


def overlap_between(
    records: list[CanonicalRecord], source_a: str, source_b: str
) -> tuple[int, int, int]:
    """返回 (仅/含 A 的条数, 含 B 的条数, 两者都含的条数)，供捕获-再捕获使用。"""
    in_a = sum(1 for record in records if source_a in record.sources)
    in_b = sum(1 for record in records if source_b in record.sources)
    both = sum(1 for record in records if source_a in record.sources and source_b in record.sources)
    return in_a, in_b, both
