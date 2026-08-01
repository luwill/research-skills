"""跨源去重与预印本-正式版配对合并。"""

from __future__ import annotations

from datetime import date

from litsearch.dedupe import CanonicalRecord, dedup_key, deduplicate
from litsearch.normalize import DateEvidence, Record
from litsearch.protocol import Window

WINDOW = Window(start=date(2021, 7, 1), end=date(2026, 7, 27), near_edge_days=180)
PRIORITY = ["published_online", "published_print", "preprint_submitted", "source_reported"]


def make(
    source: str,
    source_id: str,
    title: str,
    *,
    doi: str | None = None,
    pmid: str | None = None,
    arxiv: str | None = None,
    online: str | None = None,
    preprint: str | None = None,
    abstract: str | None = None,
    ptype: str | None = None,
    citations: int | None = None,
) -> Record:
    identifiers = {
        key: value for key, value in {"doi": doi, "pmid": pmid, "arxiv": arxiv}.items() if value
    }
    record = Record(
        source=source,
        source_id=source_id,
        title=title,
        abstract=abstract,
        identifiers=identifiers,
        publication_type=ptype,
        citation_count=citations,
        dates=DateEvidence(published_online=online, preprint_submitted=preprint),
    )
    record.resolve(WINDOW, PRIORITY)
    return record


class TestDedupKey:
    def test_doi_wins_over_other_identifiers(self):
        record = make("openalex", "W1", "T", doi="10.1/a", pmid="123", arxiv="2206.06694")

        assert dedup_key(record) == "doi:10.1/a"

    def test_falls_back_through_pmid_then_arxiv(self):
        assert dedup_key(make("pubmed", "1", "T", pmid="123")) == "pmid:123"
        assert dedup_key(make("arxiv", "1", "T", arxiv="2206.06694")) == "arxiv:2206.06694"

    def test_title_hash_when_no_identifier(self):
        key = dedup_key(make("cvf", "1", "Stroke Lesion Segmentation!"))

        assert key.startswith("title:")
        # 标点与大小写差异不应产生不同的 key
        assert key == dedup_key(make("openreview", "2", "stroke lesion segmentation"))


class TestDeduplicate:
    def test_same_doi_across_sources_merges(self):
        records = [
            make("openalex", "W1", "ISLES 2022 dataset", doi="10.1038/x", online="2022-12-10"),
            make("pubmed", "36494370", "ISLES 2022 dataset", doi="10.1038/X", pmid="36494370"),
        ]

        merged = deduplicate(records, WINDOW, PRIORITY)

        assert len(merged) == 1
        assert merged[0].sources == ("openalex", "pubmed")
        assert merged[0].identifiers["doi"] == "10.1038/x"
        assert merged[0].identifiers["pmid"] == "36494370"

    def test_transitive_merge_via_shared_identifier(self):
        # A 有 doi+pmid，B 只有 pmid，C 只有 doi —— 三者应合并为一条
        records = [
            make("openalex", "W1", "Paper A", doi="10.1/a", pmid="999"),
            make("pubmed", "999", "Paper A", pmid="999"),
            make("crossref", "x", "Paper A", doi="10.1/a"),
        ]

        merged = deduplicate(records, WINDOW, PRIORITY)

        assert len(merged) == 1
        assert set(merged[0].sources) == {"openalex", "pubmed", "crossref"}

    def test_distinct_papers_are_not_merged(self):
        records = [
            make("openalex", "W1", "Stroke lesion segmentation with nnU-Net", doi="10.1/a"),
            make("openalex", "W2", "Cardiac chamber segmentation with transformers", doi="10.1/b"),
        ]

        assert len(deduplicate(records, WINDOW, PRIORITY)) == 2

    def test_preprint_and_published_version_merge_by_title(self):
        records = [
            make(
                "arxiv",
                "2206.06694",
                "ISLES 2022: A multi-center magnetic resonance imaging stroke lesion "
                "segmentation dataset",
                arxiv="2206.06694",
                doi="10.48550/arxiv.2206.06694",
                preprint="2022-06-14",
                ptype="preprint",
            ),
            make(
                "openalex",
                "W2",
                "ISLES 2022: A multi-center magnetic resonance imaging stroke lesion "
                "segmentation dataset",
                doi="10.1038/s41597-022-01875-5",
                online="2022-12-10",
                ptype="data-paper",
            ),
        ]

        merged = deduplicate(records, WINDOW, PRIORITY)

        assert len(merged) == 1
        canonical = merged[0]
        # 两个 DOI 都必须保留，否则金标准按预印本 DOI 查会漏
        assert canonical.all_dois == {"10.48550/arxiv.2206.06694", "10.1038/s41597-022-01875-5"}
        # 正式版日期优先于预印本提交日
        assert canonical.canonical_date.earliest == date(2022, 12, 10)
        assert canonical.publication_type == "data-paper"

    def test_similar_but_different_titles_do_not_merge(self):
        records = [
            make("openalex", "W1", "Stroke lesion segmentation using 2D U-Net"),
            make("openalex", "W2", "Stroke lesion segmentation using 3D U-Net"),
        ]

        assert len(deduplicate(records, WINDOW, PRIORITY)) == 2

    def test_title_merge_requires_close_years(self):
        records = [
            make("openalex", "W1", "A robust ensemble for stroke seg", online="2015-01-01"),
            make("openalex", "W2", "A robust ensemble for stroke seg", online="2024-01-01"),
        ]

        assert len(deduplicate(records, WINDOW, PRIORITY)) == 2

    def test_richest_abstract_and_max_citations_win(self):
        records = [
            make("pubmed", "1", "Paper", doi="10.1/a", abstract="short", citations=3),
            make(
                "openalex",
                "W1",
                "Paper",
                doi="10.1/a",
                abstract="a considerably longer and more complete abstract",
                citations=41,
            ),
        ]

        canonical = deduplicate(records, WINDOW, PRIORITY)[0]

        assert canonical.abstract == "a considerably longer and more complete abstract"
        assert canonical.citation_count == 41

    def test_merged_record_keeps_every_member_for_audit(self):
        records = [
            make("openalex", "W1", "Paper", doi="10.1/a"),
            make("pubmed", "999", "Paper", doi="10.1/a", pmid="999"),
        ]

        canonical = deduplicate(records, WINDOW, PRIORITY)[0]

        assert isinstance(canonical, CanonicalRecord)
        assert len(canonical.members) == 2
        assert {member.source_id for member in canonical.members} == {"W1", "999"}

    def test_corpus_serialization_uses_lightweight_member_refs(self):
        canonical = deduplicate(
            [
                make("arxiv", "a", "Paper", doi="10.48550/arxiv.1"),
                make("openalex", "b", "Paper", doi="10.1/published"),
            ],
            WINDOW,
            PRIORITY,
        )[0]

        payload = canonical.model_dump(mode="json")
        restored = CanonicalRecord.model_validate(payload)

        assert "members" not in payload
        assert len(payload["member_refs"]) == 2
        assert restored.members == []
        assert restored.all_dois == {"10.48550/arxiv.1", "10.1/published"}
        assert restored.has_identifier("doi", "10.48550/arxiv.1")

    def test_source_contribution_counts_unique_finds(self):
        records = [
            make("openalex", "W1", "Shared", doi="10.1/a"),
            make("pubmed", "1", "Shared", doi="10.1/a"),
            make("europepmc", "2", "Only europepmc has this", doi="10.1/b"),
        ]

        merged = deduplicate(records, WINDOW, PRIORITY)
        unique = [item for item in merged if len(item.sources) == 1]

        assert len(unique) == 1
        assert unique[0].sources == ("europepmc",)

    def test_sources_disagreeing_on_the_same_field_across_the_edge_need_human_review(self):
        """两个源都报 published_online，一个在窗外一个在窗内——必须人工裁定。"""
        records = [
            make("openalex", "W1", "Edge case paper", doi="10.1/edge", online="2021-06-20"),
            make("pubmed", "1", "Edge case paper", doi="10.1/edge", online="2021-08-01"),
        ]

        canonical = deduplicate(records, WINDOW, PRIORITY)[0]

        assert canonical.date_conflict is True
        assert canonical.needs_human_review is True

    def test_sources_agreeing_on_the_same_side_are_not_a_conflict(self):
        records = [
            make("openalex", "W1", "Agreed paper", doi="10.1/ok", online="2023-01-10"),
            make("pubmed", "1", "Agreed paper", doi="10.1/ok", online="2023-02-14"),
        ]

        canonical = deduplicate(records, WINDOW, PRIORITY)[0]

        assert canonical.date_conflict is False
        assert canonical.needs_human_review is False

    def test_empty_input(self):
        assert deduplicate([], WINDOW, PRIORITY) == []
