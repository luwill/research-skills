"""召回率证据：金标准命中、来源独有贡献、捕获-再捕获估计。

这一层决定了能否**声称**"检索是全面的"，而不是只能说"我尽力了"。
"""

from __future__ import annotations

from datetime import date

import pytest

from litsearch.dedupe import deduplicate
from litsearch.metrics import (
    capture_recapture,
    gold_set_recall,
    out_of_window_leakage,
    source_contribution,
)
from litsearch.normalize import DateEvidence, Record
from litsearch.protocol import SeedItem, Window

WINDOW = Window(start=date(2021, 7, 1), end=date(2026, 7, 27))
PRIORITY = ["published_online", "published_print", "preprint_submitted", "source_reported"]


def make(source: str, title: str, *, doi=None, arxiv=None, pmid=None, online="2023-01-01"):
    identifiers = {
        key: value for key, value in {"doi": doi, "arxiv": arxiv, "pmid": pmid}.items() if value
    }
    return Record(
        source=source,
        source_id=f"{source}-{title}",
        title=title,
        identifiers=identifiers,
        dates=DateEvidence(published_online=online),
    ).resolve(WINDOW, PRIORITY)


def corpus(records):
    return deduplicate(records, WINDOW, PRIORITY)


class TestGoldSetRecall:
    def test_full_recall(self):
        gold = [SeedItem(doi="10.1/a"), SeedItem(doi="10.1/b")]
        found = corpus([make("openalex", "A", doi="10.1/a"), make("pubmed", "B", doi="10.1/b")])

        report = gold_set_recall(gold, found)

        assert report.recall == 1.0
        assert report.missing == []
        assert report.found_count == 2

    def test_missing_items_are_named_not_just_counted(self):
        gold = [SeedItem(doi="10.1/a"), SeedItem(doi="10.1/missing", note="ISLES 2024")]
        found = corpus([make("openalex", "A", doi="10.1/a")])

        report = gold_set_recall(gold, found)

        assert report.recall == 0.5
        assert [item.doi for item in report.missing] == ["10.1/missing"]
        assert report.missing[0].note == "ISLES 2024"

    def test_matches_on_any_identifier_not_only_doi(self):
        gold = [SeedItem(arxiv="2206.06694")]
        found = corpus([make("arxiv", "ISLES 2022", arxiv="2206.06694", doi="10.48550/x")])

        assert gold_set_recall(gold, found).recall == 1.0

    def test_preprint_doi_found_via_merged_record(self):
        """预印本与正式版合并后，按预印本 DOI 查也必须命中。"""
        merged = corpus(
            [
                make("arxiv", "ISLES 2022 dataset", doi="10.48550/arxiv.2206.06694"),
                make("openalex", "ISLES 2022 dataset", doi="10.1038/s41597-022-01875-5"),
            ]
        )
        assert len(merged) == 1

        report = gold_set_recall([SeedItem(doi="10.48550/arxiv.2206.06694")], merged)

        assert report.recall == 1.0

    def test_gold_item_given_as_arxiv_doi_matches_a_record_carrying_only_the_arxiv_id(self):
        """实测踩过的坑：论文在库里，却因 DOI/ID 两种写法不通而被判为漏检。"""
        found = corpus([make("arxiv", "ISLES 2022", arxiv="2206.06694")])

        report = gold_set_recall([SeedItem(doi="10.48550/arXiv.2206.06694")], found)

        assert report.recall == 1.0

    def test_empty_gold_set_reports_none_not_a_fake_perfect_score(self):
        assert gold_set_recall([], corpus([])).recall is None

    def test_a_gold_item_found_only_outside_the_strict_window_is_not_recalled(self):
        seed = SeedItem(doi="10.1/old")
        found = corpus([make("openalex", "Old paper", doi="10.1/old", online="2016-07-22")])

        report = gold_set_recall([seed], found)

        assert report.found_count == 0
        assert report.recall == 0.0
        assert report.found_out_of_window == [seed]


class TestOutOfWindowLeakage:
    def test_controls_outside_the_window_must_not_be_included(self):
        controls = [SeedItem(doi="10.1/old")]
        found = corpus([make("openalex", "Old paper", doi="10.1/old", online="2016-07-22")])

        report = out_of_window_leakage(controls, found)

        assert report.leaked == []
        assert report.checked == 1

    def test_leak_is_reported_when_a_control_lands_in_window(self):
        controls = [SeedItem(doi="10.1/old")]
        found = corpus([make("openalex", "Old paper", doi="10.1/old", online="2023-01-01")])

        report = out_of_window_leakage(controls, found)

        assert [item.doi for item in report.leaked] == ["10.1/old"]


class TestSourceContribution:
    def test_counts_total_and_unique_per_source(self):
        found = corpus(
            [
                make("openalex", "Shared", doi="10.1/a"),
                make("pubmed", "Shared", doi="10.1/a"),
                make("europepmc", "Only here", doi="10.1/b"),
                make("openalex", "Also only here", doi="10.1/c"),
            ]
        )

        rows = {row.source: row for row in source_contribution(found)}

        assert rows["openalex"].total == 2
        assert rows["openalex"].unique == 1
        assert rows["pubmed"].total == 1
        assert rows["pubmed"].unique == 0
        assert rows["europepmc"].unique == 1

    def test_source_with_zero_unique_contribution_is_flagged_redundant(self):
        found = corpus([make("openalex", "S", doi="10.1/a"), make("pubmed", "S", doi="10.1/a")])

        rows = {row.source: row for row in source_contribution(found)}

        assert rows["pubmed"].redundant is True
        assert rows["openalex"].redundant is True


class TestCaptureRecapture:
    def test_chapman_estimate_on_overlapping_samples(self):
        # A 抓到 100，B 抓到 100，重叠 50 -> Chapman ≈ 199
        estimate = capture_recapture(captured_a=100, captured_b=100, overlap=50)

        assert estimate.total is not None
        assert 195 <= estimate.total <= 205
        assert estimate.observed == 150
        assert 0.7 <= estimate.recall <= 0.8

    def test_complete_overlap_implies_full_recall(self):
        estimate = capture_recapture(captured_a=100, captured_b=100, overlap=100)

        assert estimate.total == pytest.approx(100, abs=2)
        assert estimate.recall >= 0.97

    def test_no_overlap_cannot_be_estimated(self):
        # 零重叠时 Chapman 估计无意义，必须明说而不是给一个假数字
        estimate = capture_recapture(captured_a=100, captured_b=100, overlap=0)

        assert estimate.total is None
        assert estimate.recall is None
        assert "重叠" in estimate.note

    def test_empty_sample_cannot_be_estimated(self):
        assert capture_recapture(captured_a=0, captured_b=10, overlap=0).total is None
