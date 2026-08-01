"""质量分层排序的测试。

契约：**排序不删记录。** 全量交付，只是把高质量的排前面。
"""

from __future__ import annotations

from datetime import date

import pytest

from litsearch.order import (
    PREPRINT_FRESH_DAYS,
    Tier,
    assign_tier,
    order_ranked,
    tier_counts,
)
from litsearch.rank import RankedRecord, VenueKind

TODAY = date(2026, 7, 30)


def _ranked(key: str = "k", **kwargs) -> RankedRecord:
    payload = {
        "key": key,
        "title": kwargs.pop("title", "标题"),
        "doi": kwargs.pop("doi", None),
        "venue": kwargs.pop("venue", None),
        "kind": kwargs.pop("kind", VenueKind.JOURNAL),
        "band": kwargs.pop("band", "—"),
        **kwargs,
    }
    return RankedRecord(**payload)


class TestAssignTier:
    def test_top_one_percent_is_the_benchmark_tier(self) -> None:
        record = _ranked(in_top_1_percent=True, metric=0.5)
        assert assign_tier(record, today=TODAY) is Tier.BENCHMARK

    def test_a_conference_can_reach_the_top_via_paper_level_impact(self) -> None:
        """没有 CCF 目录时，会议靠论文级影响力进前排——不靠我猜它的等级。"""
        record = _ranked(kind=VenueKind.CONFERENCE, in_top_1_percent=True)
        assert assign_tier(record, today=TODAY) is Tier.BENCHMARK

    def test_high_metric_journal(self) -> None:
        assert assign_tier(_ranked(metric=9.0), today=TODAY) is Tier.TOP

    def test_ccf_a_is_the_benchmark_tier(self) -> None:
        record = _ranked(kind=VenueKind.CONFERENCE, ccf_rank="A")
        assert assign_tier(record, today=TODAY) is Tier.BENCHMARK

    def test_ccf_b_conference_reaches_the_top_tier(self) -> None:
        """MICCAI 是 CCF-B——没有目录时它只能靠被引进前排，有目录就该直接进。"""
        record = _ranked(kind=VenueKind.CONFERENCE, ccf_rank="B")
        assert assign_tier(record, today=TODAY) is Tier.TOP

    def test_takes_the_better_of_ccf_and_metric(self) -> None:
        """MedIA 是 CCF-C，但指标 10.14 全语料最高。两把尺子取较优。"""
        record = _ranked(ccf_rank="C", metric=10.14)
        assert assign_tier(record, today=TODAY) is Tier.TOP

    def test_ccf_lifts_a_journal_its_metric_would_bury(self) -> None:
        record = _ranked(ccf_rank="B", metric=1.2)
        assert assign_tier(record, today=TODAY) is Tier.TOP

    def test_top_ten_percent_reaches_top_even_on_a_low_metric_journal(self) -> None:
        record = _ranked(metric=1.11, in_top_10_percent=True)
        assert assign_tier(record, today=TODAY) is Tier.TOP

    def test_mid_metric_journal(self) -> None:
        assert assign_tier(_ranked(metric=5.0), today=TODAY) is Tier.STRONG

    def test_low_metric_journal(self) -> None:
        assert assign_tier(_ranked(metric=1.2), today=TODAY) is Tier.OTHER_JOURNAL

    def test_fresh_preprint(self) -> None:
        record = _ranked(kind=VenueKind.PREPRINT, date_text="2026-05-01")
        assert assign_tier(record, today=TODAY) is Tier.FRESH_PREPRINT

    def test_stale_preprint_falls_to_the_tail(self) -> None:
        record = _ranked(kind=VenueKind.PREPRINT, date_text="2022-01-01")
        assert assign_tier(record, today=TODAY) is Tier.REMAINDER

    def test_preprint_freshness_boundary(self) -> None:
        edge = TODAY.toordinal() - PREPRINT_FRESH_DAYS
        record = _ranked(kind=VenueKind.PREPRINT, date_text=date.fromordinal(edge).isoformat())
        assert assign_tier(record, today=TODAY) is Tier.FRESH_PREPRINT

    def test_preprint_without_a_date_is_not_called_fresh(self) -> None:
        """日期缺失不等于新。猜"新"会把 2021 年的预印本推到列表最前面。"""
        record = _ranked(kind=VenueKind.PREPRINT, date_text=None)
        assert assign_tier(record, today=TODAY) is Tier.REMAINDER

    def test_conference_absent_from_the_catalog_is_unrated_not_low(self) -> None:
        record = _ranked(kind=VenueKind.CONFERENCE)
        assert assign_tier(record, today=TODAY) is Tier.CONFERENCE

    def test_unranked_journal_is_not_demoted_below_low_metric_ones(self) -> None:
        """没有指标 ≠ 指标低。它去"其余"，不去"其它期刊"档。"""
        record = _ranked(kind=VenueKind.JOURNAL, metric=None)
        assert assign_tier(record, today=TODAY) is Tier.REMAINDER


class TestOrderRanked:
    def test_never_drops_a_record(self) -> None:
        records = [_ranked(f"k{i}", metric=float(i)) for i in range(9)]
        assert len(order_ranked(records, today=TODAY)) == 9

    def test_tiers_come_in_order(self) -> None:
        records = [
            _ranked("low", metric=1.0),
            _ranked("bench", in_top_1_percent=True),
            _ranked("strong", metric=5.0),
            _ranked("top", metric=9.0),
        ]
        ordered = order_ranked(records, today=TODAY)
        assert [item.key for item in ordered] == ["bench", "top", "strong", "low"]

    def test_a_fresh_preprint_outranks_a_low_metric_journal(self) -> None:
        records = [
            _ranked("journal", metric=1.0),
            _ranked("preprint", kind=VenueKind.PREPRINT, date_text="2026-06-01"),
        ]
        ordered = order_ranked(records, today=TODAY)
        assert [item.key for item in ordered] == ["preprint", "journal"]

    def test_within_tier_sorts_by_citations_then_metric(self) -> None:
        """被引是横跨期刊/会议/预印本的同一种货币；期刊指标只做决胜。"""
        records = [
            _ranked("a", metric=9.0, cited_by_count=5),
            _ranked("b", metric=9.0, cited_by_count=50),
            _ranked("c", metric=12.0, cited_by_count=1),
        ]
        assert [item.key for item in order_ranked(records, today=TODAY)] == ["b", "a", "c"]

    def test_fresh_preprints_sort_newest_first(self) -> None:
        records = [
            _ranked("old", kind=VenueKind.PREPRINT, date_text="2025-06-01"),
            _ranked("new", kind=VenueKind.PREPRINT, date_text="2026-07-01"),
        ]
        assert [item.key for item in order_ranked(records, today=TODAY)] == ["new", "old"]

    def test_order_is_stable_for_identical_keys(self) -> None:
        """同分时保持输入顺序，让同一份语料每次都产出同一份文档。"""
        records = [_ranked(f"k{i}", metric=5.0) for i in range(6)]
        twice = [order_ranked(records, today=TODAY) for _ in range(2)]
        assert [item.key for item in twice[0]] == [item.key for item in twice[1]]
        assert [item.key for item in twice[0]] == [f"k{i}" for i in range(6)]


class TestTierCounts:
    def test_counts_every_tier_and_totals_to_the_input(self) -> None:
        records = [
            _ranked("a", in_top_1_percent=True),
            _ranked("b", metric=9.0),
            _ranked("c", metric=1.0),
            _ranked("d", kind=VenueKind.CONFERENCE),
        ]
        counts = tier_counts(order_ranked(records, today=TODAY), today=TODAY)
        assert sum(counts.values()) == 4
        assert counts[Tier.BENCHMARK] == 1
        assert counts[Tier.CONFERENCE] == 1


@pytest.mark.parametrize("tier", list(Tier))
def test_every_tier_has_a_label_and_a_rationale(tier: Tier) -> None:
    """每一层都要说得出"为什么在这里"，否则读的人只能猜。"""
    assert tier.label
    assert tier.rationale
