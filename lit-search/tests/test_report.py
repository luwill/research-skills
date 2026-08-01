"""PRISMA 计数与报告。

这一层的唯一职责是**让数字自洽**，并在不自洽时拒绝出报告。
一份各环节对不上的 PRISMA 流程图比没有更糟——它看起来像证据，实际是错的。

同样重要的是**不许凑数**：筛选还没跑，PRISMA 就只能画到"筛选输入"为止，
不能把窗口内记录数当成纳入数写上去。
"""

from __future__ import annotations

import pytest

from litsearch.dedupe import CanonicalRecord
from litsearch.normalize import WindowStatus
from litsearch.report import (
    PrismaCounts,
    ReportInconsistency,
    evidence_table_markdown,
    included_csv,
    prisma_markdown,
    zotero_dois,
)
from litsearch.screen import Decision, MergedDecision


def record(
    key,
    *,
    status=WindowStatus.IN_WINDOW,
    doi=None,
    title="A paper",
    venue="A journal",
    sources=("pubmed",),
    year="2024-01-01",
):
    from datetime import date

    from litsearch.normalize import DateEvidence, PartialDate

    return CanonicalRecord(
        key=key,
        title=title,
        venue=venue,
        sources=tuple(sources),
        identifiers={"doi": doi} if doi else {},
        window_status=status,
        dates=DateEvidence(published_online=year),
        canonical_date=PartialDate.exact(date.fromisoformat(year)),
    )


def verdict(key, decision, *, needs_human=False, criteria=()):
    return (
        MergedDecision(
            record_key=key,
            decision=Decision(decision),
            needs_human=needs_human,
            reason="r",
            channel_verdicts=[],
        )
        if not criteria
        else MergedDecision(
            record_key=key,
            decision=Decision(decision),
            needs_human=needs_human,
            reason="r",
            channel_verdicts=[
                {
                    "record_key": key,
                    "decision": decision,
                    "confidence": 0.9,
                    "reason": "r",
                    "matched_criteria": list(criteria),
                }
            ],
        )
    )


class TestPrismaCounts:
    def test_identification_minus_duplicates_equals_screening_input(self):
        counts = PrismaCounts(
            identified={"pubmed": 100, "arxiv": 20},
            canonical=90,
            by_status={"in_window": 70, "out_of_window": 18, "boundary": 2},
        )

        assert counts.identified_total == 120
        assert counts.duplicates_removed == 30
        assert counts.screening_input == 70

    def test_inconsistent_status_counts_are_refused(self):
        """窗口判定之和必须等于规范记录数，对不上说明上游丢了记录。"""
        counts = PrismaCounts(
            identified={"pubmed": 100},
            canonical=90,
            by_status={"in_window": 70, "out_of_window": 5},  # 只有 75
        )

        with pytest.raises(ReportInconsistency, match="窗口判定"):
            counts.check()

    def test_more_canonical_than_identified_is_refused(self):
        counts = PrismaCounts(identified={"pubmed": 10}, canonical=20, by_status={"in_window": 20})

        with pytest.raises(ReportInconsistency, match="去重"):
            counts.check()

    def test_screening_totals_must_match_the_input(self):
        counts = PrismaCounts(
            identified={"pubmed": 100},
            canonical=90,
            by_status={"in_window": 70, "out_of_window": 20},
            screened={"include": 10, "exclude": 30, "human_queue": 5},  # 只有 45
        )

        with pytest.raises(ReportInconsistency, match="筛选"):
            counts.check()

    def test_a_consistent_set_passes(self):
        counts = PrismaCounts(
            identified={"pubmed": 100},
            canonical=90,
            by_status={"in_window": 70, "out_of_window": 20},
            screened={"include": 10, "exclude": 55, "human_queue": 5},
        )

        counts.check()


class TestPrismaMarkdown:
    def _counts(self, **kw):
        base = dict(
            identified={"pubmed": 100, "snowball": 20},
            canonical=90,
            by_status={"in_window": 70, "out_of_window": 20},
        )
        base.update(kw)
        return PrismaCounts(**base)

    def test_every_stage_count_appears(self):
        text = prisma_markdown(
            self._counts(screened={"include": 10, "exclude": 55, "human_queue": 5})
        )

        for value in ("120", "90", "30", "70", "10", "55", "5"):
            assert value in text

    def test_database_and_other_methods_are_separated(self):
        """PRISMA 2020 要求"数据库检索"与"其他途径"分开计数。"""
        text = prisma_markdown(
            self._counts(screened={"include": 10, "exclude": 55, "human_queue": 5})
        )

        assert "其他途径" in text and "snowball" in text

    def test_without_screening_the_flow_stops_and_says_so(self):
        """筛选没跑就不能画到"纳入"——那会把窗口内记录数伪装成纳入数。"""
        text = prisma_markdown(self._counts())

        assert "尚未筛选" in text
        assert "## 纳入研究" not in text  # 没有"纳入"那一节，只有说明为什么没有

    def test_degraded_sources_are_stated_in_the_report(self):
        text = prisma_markdown(
            self._counts(screened={"include": 10, "exclude": 55, "human_queue": 5}),
            degraded=["grey"],
        )

        assert "grey" in text
        assert "不可当作完整值" in text

    def test_title_abstract_passes_are_not_called_final_included_studies(self):
        text = prisma_markdown(
            self._counts(screened={"include": 10, "exclude": 55, "human_queue": 5})
        )

        assert "进入全文资格审查" in text
        assert "尚未记录全文" in text
        assert "## 纳入研究" not in text

    def test_an_inconsistent_count_never_renders(self):
        with pytest.raises(ReportInconsistency):
            prisma_markdown(self._counts(by_status={"in_window": 70}))


class TestIncludedOutputs:
    def _data(self):
        records = {
            "a": record("a", doi="10.1/a", title="Included one"),
            "b": record("b", doi="10.1/b", title="Excluded one"),
            "c": record("c", title="Queued one"),
        }
        decisions = {
            "a": verdict("a", "include", criteria=["I1", "I2"]),
            "b": verdict("b", "exclude"),
            "c": verdict("c", "unclear", needs_human=True),
        }
        return records, decisions

    def test_included_csv_holds_only_included_studies(self):
        records, decisions = self._data()

        csv = included_csv(records, decisions)

        assert "Included one" in csv
        assert "Excluded one" not in csv
        assert "Queued one" not in csv

    def test_matched_criteria_are_carried_into_the_table(self):
        records, decisions = self._data()

        table = evidence_table_markdown(records, decisions)

        assert "I1" in table and "I2" in table

    def test_evidence_table_does_not_invent_fields_it_cannot_verify(self):
        """方法/数据集/指标要读全文才知道，这一步没有——留空并标注，不猜。"""
        records, decisions = self._data()

        table = evidence_table_markdown(records, decisions)

        assert "需全文提取" in table

    def test_zotero_list_is_deduplicated_and_doi_only(self):
        records, decisions = self._data()
        records["d"] = record("d", doi="10.1/a", title="Same DOI")
        decisions["d"] = verdict("d", "include")

        dois = zotero_dois(records, decisions)

        assert dois == ["10.1/a"]

    def test_records_without_a_doi_are_reported_separately(self):
        records, decisions = self._data()
        decisions["c"] = verdict("c", "include")

        dois = zotero_dois(records, decisions)

        assert "10.1/a" in dois
        assert len(dois) == 1  # c 没有 DOI，不能凭空造一个
