"""日期证据 -> canonical_date -> 时间窗判定。

这是"指定时间范围"最容易翻车的一层：各源日期语义不一致，且大量记录只有年份或年月。
原则：宁可标为待裁定，也绝不静默丢弃。
"""

from __future__ import annotations

from datetime import date

import pytest

from litsearch.normalize import (
    DateEvidence,
    PartialDate,
    Record,
    WindowStatus,
    classify_window,
    parse_partial_date,
    resolve_canonical_date,
)
from litsearch.protocol import Window

WINDOW = Window(start=date(2021, 7, 1), end=date(2026, 7, 27), near_edge_days=180)


class TestParsePartialDate:
    @pytest.mark.parametrize(
        ("raw", "earliest", "latest", "precision"),
        [
            ("2022-06-16", date(2022, 6, 16), date(2022, 6, 16), "day"),
            ("2022/06/16", date(2022, 6, 16), date(2022, 6, 16), "day"),
            ("2022-06", date(2022, 6, 1), date(2022, 6, 30), "month"),
            ("2022", date(2022, 1, 1), date(2022, 12, 31), "year"),
            ("2024 Feb 6", date(2024, 2, 6), date(2024, 2, 6), "day"),
            ("2024 Feb", date(2024, 2, 1), date(2024, 2, 29), "month"),
        ],
    )
    def test_parses_common_shapes(self, raw, earliest, latest, precision):
        parsed = parse_partial_date(raw)

        assert parsed is not None
        assert parsed.earliest == earliest
        assert parsed.latest == latest
        assert parsed.precision == precision

    @pytest.mark.parametrize("raw", [None, "", "n/a", "no date here", "12-31"])
    def test_returns_none_for_unparseable(self, raw):
        assert parse_partial_date(raw) is None

    def test_leap_year_february_is_handled(self):
        assert parse_partial_date("2024-02").latest == date(2024, 2, 29)
        assert parse_partial_date("2023-02").latest == date(2023, 2, 28)


class TestResolveCanonicalDate:
    def test_follows_priority_order(self):
        evidence = DateEvidence(
            published_print="2023-01-01",
            published_online="2022-12-10",
            preprint_submitted="2022-06-14",
        )

        resolved = resolve_canonical_date(
            evidence, ["published_online", "published_print", "preprint_submitted"]
        )

        assert resolved.earliest == date(2022, 12, 10)

    def test_falls_through_missing_fields(self):
        evidence = DateEvidence(preprint_submitted="2022-06-14")

        resolved = resolve_canonical_date(
            evidence, ["published_online", "published_print", "preprint_submitted"]
        )

        assert resolved.earliest == date(2022, 6, 14)

    def test_returns_none_when_no_evidence(self):
        assert resolve_canonical_date(DateEvidence(), ["published_online"]) is None

    def test_unparseable_field_is_skipped_not_fatal(self):
        evidence = DateEvidence(published_online="in press", published_print="2023-05-02")

        resolved = resolve_canonical_date(evidence, ["published_online", "published_print"])

        assert resolved.earliest == date(2023, 5, 2)


class TestClassifyWindow:
    def test_clearly_inside(self):
        assert (
            classify_window(PartialDate.exact(date(2023, 5, 1)), WINDOW) is WindowStatus.IN_WINDOW
        )

    def test_clearly_outside(self):
        assert (
            classify_window(PartialDate.exact(date(2019, 1, 1)), WINDOW)
            is WindowStatus.OUT_OF_WINDOW
        )
        assert (
            classify_window(PartialDate.exact(date(2027, 1, 1)), WINDOW)
            is WindowStatus.OUT_OF_WINDOW
        )

    def test_exact_date_near_the_edge_is_not_ambiguous(self):
        """精确到日的记录哪怕紧贴边界也不该进人工队列。

        实测：按 ±180 天盲标，1,914 条记录里有 864 条被标为待裁定，
        其中 833 条精确到日——那种队列没人会看，等于没有把关。
        """
        assert (
            classify_window(PartialDate.exact(date(2021, 7, 2)), WINDOW) is WindowStatus.IN_WINDOW
        )
        assert (
            classify_window(PartialDate.exact(date(2026, 7, 26)), WINDOW) is WindowStatus.IN_WINDOW
        )
        assert (
            classify_window(PartialDate.exact(date(2021, 6, 30)), WINDOW)
            is WindowStatus.OUT_OF_WINDOW
        )

    def test_year_only_date_spanning_the_boundary_is_boundary(self):
        # 只知道是 2021 年——窗口从 2021-07-01 开始，无法判定，必须人工裁定
        assert classify_window(parse_partial_date("2021"), WINDOW) is WindowStatus.BOUNDARY

    def test_year_only_date_fully_inside_is_in_window(self):
        assert classify_window(parse_partial_date("2023"), WINDOW) is WindowStatus.IN_WINDOW

    def test_year_only_date_fully_outside_is_out(self):
        assert classify_window(parse_partial_date("2018"), WINDOW) is WindowStatus.OUT_OF_WINDOW

    def test_missing_date_is_undated_never_dropped(self):
        assert classify_window(None, WINDOW) is WindowStatus.UNDATED


class TestRecord:
    def _record(self, **overrides) -> Record:
        payload = {
            "source": "openalex",
            "source_id": "W123",
            "title": "  ISLES 2022:  A   multi-center   dataset ",
            "identifiers": {"doi": "https://doi.org/10.1038/S41597-022-01875-5"},
            "dates": DateEvidence(published_online="2022-12-10"),
        }
        payload.update(overrides)
        return Record.model_validate(payload)

    def test_title_whitespace_is_collapsed(self):
        assert self._record().title == "ISLES 2022: A multi-center dataset"

    def test_identifiers_are_normalized(self):
        record = self._record(
            identifiers={
                "doi": "https://doi.org/10.1038/S41597-022-01875-5",
                "pmid": "https://pubmed.ncbi.nlm.nih.gov/36494370/",
                "arxiv": "arXiv:2206.06694v3",
            }
        )

        assert record.identifiers["doi"] == "10.1038/s41597-022-01875-5"
        assert record.identifiers["pmid"] == "36494370"
        assert record.identifiers["arxiv"] == "2206.06694"

    def test_arxiv_doi_and_arxiv_id_are_linked(self):
        """arXiv 给每篇论文都分配了 DataCite DOI ``10.48550/arXiv.<id>``。

        但 Atom feed 的 ``arxiv:doi`` 字段存的是**期刊 DOI**，不是这个。
        若不把两种写法打通，按 arXiv DOI 查金标准会漏检——即使论文就在库里。
        """
        from_doi = self._record(identifiers={"doi": "10.48550/arXiv.2206.06694"})
        assert from_doi.identifiers["arxiv"] == "2206.06694"
        assert from_doi.identifiers["arxiv_doi"] == "10.48550/arxiv.2206.06694"

        # 已有期刊 DOI 时，arXiv DOI 单独存放，不覆盖期刊 DOI
        from_id = self._record(
            identifiers={"arxiv": "2206.06694", "doi": "10.1038/s41597-022-01875-5"}
        )
        assert from_id.identifiers["doi"] == "10.1038/s41597-022-01875-5"
        assert from_id.identifiers["arxiv_doi"] == "10.48550/arxiv.2206.06694"

    def test_non_arxiv_doi_does_not_produce_an_arxiv_id(self):
        record = self._record(identifiers={"doi": "10.1038/s41597-022-01875-5"})

        assert "arxiv" not in record.identifiers
        assert "arxiv_doi" not in record.identifiers

    def test_empty_title_is_rejected(self):
        with pytest.raises(ValueError):
            self._record(title="   ")

    def test_resolve_sets_canonical_date_and_status(self):
        record = self._record()
        record.resolve(WINDOW, ["published_online", "published_print"])

        assert record.canonical_date.earliest == date(2022, 12, 10)
        assert record.window_status is WindowStatus.IN_WINDOW

    def test_resolve_marks_undated_record_for_review(self):
        record = self._record(dates=DateEvidence())
        record.resolve(WINDOW, ["published_online"])

        assert record.canonical_date is None
        assert record.window_status is WindowStatus.UNDATED
        assert record.needs_human_review is True

    def test_year_only_record_at_the_edge_needs_human_review(self):
        record = self._record(dates=DateEvidence(published_online="2021"))
        record.resolve(WINDOW, ["published_online"])

        assert record.window_status is WindowStatus.BOUNDARY
        assert record.needs_human_review is True

    def test_priority_resolves_cross_field_disagreement_without_human_review(self):
        """预印本在窗外、正式版在窗内——这不是歧义，date_priority 已经规定了听谁的。

        实测：把跨字段分歧当歧义，会把 1,778 条记录送进人工队列，
        其中 94% 的主日期精确到日。真歧义只有"多个源对同一字段各执一词"。
        """
        record = self._record(
            dates=DateEvidence(published_online="2021-09-01", preprint_submitted="2021-03-01")
        )
        record.resolve(WINDOW, ["published_online", "preprint_submitted"])

        assert record.date_conflict is False
        assert record.window_status is WindowStatus.IN_WINDOW
        assert record.needs_human_review is False

    def test_consistent_dates_on_the_same_side_are_not_a_conflict(self):
        record = self._record(
            dates=DateEvidence(published_online="2022-12-10", preprint_submitted="2022-06-14")
        )
        record.resolve(WINDOW, ["published_online", "preprint_submitted"])

        assert record.date_conflict is False
        assert record.window_status is WindowStatus.IN_WINDOW

    def test_near_edge_is_reported_but_does_not_gate(self):
        record = self._record(dates=DateEvidence(published_online="2021-08-01"))
        record.resolve(WINDOW, ["published_online"])

        assert record.near_edge is True
        assert record.window_status is WindowStatus.IN_WINDOW
        assert record.needs_human_review is False
