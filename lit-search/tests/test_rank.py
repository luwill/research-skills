"""分层标注的测试。

核心不变量：**标注不删记录**。这一层一旦开始丢东西，PRISMA 就数不出来了。
"""

from __future__ import annotations

import pytest

from litsearch.dedupe import CanonicalRecord
from litsearch.rank import (
    DEFAULT_BANDS,
    UNRANKED,
    Band,
    JournalMetrics,
    VenueKind,
    WorkMetrics,
    assign_band,
    classify_kind,
    match_summary,
    normalize_issn,
    rank_records,
    tier_report_markdown,
)


def _record(key: str, **kwargs) -> CanonicalRecord:
    payload = {
        "key": key,
        "title": kwargs.pop("title", f"标题 {key}"),
        "identifiers": kwargs.pop("identifiers", {}),
        "venue": kwargs.pop("venue", None),
        "publication_type": kwargs.pop("publication_type", None),
        "sources": kwargs.pop("sources", ["pubmed"]),
        **kwargs,
    }
    return CanonicalRecord.model_validate(payload)


class TestNormalizeIssn:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("1361-8415", "1361-8415"),
            ("13618415", "1361-8415"),
            (" 1361-8415 ", "1361-8415"),
            ("1361-841x", "1361-841X"),
            ("1361841X", "1361-841X"),
        ],
    )
    def test_normalizes(self, raw: str, expected: str) -> None:
        assert normalize_issn(raw) == expected

    @pytest.mark.parametrize("raw", ["", None, "abcd-efgh", "1361-84", "X361-8415", "136-18415x"])
    def test_rejects_garbage(self, raw) -> None:
        assert normalize_issn(raw) is None

    def test_rejects_rather_than_guesses(self) -> None:
        """长度不对就返回 None，不截断也不补齐——猜出来的 ISSN 会静默匹配到别的刊。"""
        assert normalize_issn("1361-84155") is None


class TestClassifyKind:
    def test_arxiv_doi_prefix_is_preprint(self) -> None:
        record = _record("a", identifiers={"doi": "10.48550/arXiv.2401.01234"})
        assert classify_kind(record, None) is VenueKind.PREPRINT

    def test_arxiv_venue_is_preprint(self) -> None:
        assert classify_kind(_record("a", venue="arXiv"), None) is VenueKind.PREPRINT

    @pytest.mark.parametrize("venue", ["medRxiv", "bioRxiv", "Research Square"])
    def test_preprint_servers(self, venue: str) -> None:
        assert classify_kind(_record("a", venue=venue), None) is VenueKind.PREPRINT

    def test_zenodo_is_repository(self) -> None:
        assert classify_kind(_record("a", venue="Zenodo"), None) is VenueKind.REPOSITORY

    def test_lncs_is_conference(self) -> None:
        """MICCAI 的 container 是 LNCS——按刊处理会给它一个毫无意义的影响因子。"""
        record = _record("a", venue="Lecture Notes in Computer Science")
        assert classify_kind(record, None) is VenueKind.CONFERENCE

    def test_openalex_source_type_wins_over_guessing(self) -> None:
        work = WorkMetrics(doi="10.1/x", work_type="article", source_type="conference")
        assert classify_kind(_record("a", venue="某会议论文集"), work) is VenueKind.CONFERENCE

    def test_journal(self) -> None:
        work = WorkMetrics(doi="10.1/x", work_type="article", source_type="journal")
        assert classify_kind(_record("a", venue="Stroke"), work) is VenueKind.JOURNAL

    def test_unknown_when_nothing_known(self) -> None:
        assert classify_kind(_record("a"), None) is VenueKind.UNKNOWN


class TestAssignBand:
    def test_picks_highest_matching_band(self) -> None:
        assert assign_band(10.1, DEFAULT_BANDS) == DEFAULT_BANDS[0].label

    def test_boundary_is_inclusive_at_lower_bound(self) -> None:
        bands = (Band("高", 4.0), Band("低", 0.0))
        assert assign_band(4.0, bands) == "高"
        assert assign_band(3.999, bands) == "低"

    def test_none_is_unranked(self) -> None:
        assert assign_band(None, DEFAULT_BANDS) == UNRANKED


class TestRankRecords:
    def test_never_drops_a_record(self) -> None:
        """标注层的核心契约：进多少条，出多少条。"""
        records = [_record(f"k{i}") for i in range(7)]
        ranked = rank_records(records, works={}, journals={})
        assert len(ranked) == 7
        assert [item.key for item in ranked] == [item.key for item in records]

    def test_journal_gets_band_from_issn(self) -> None:
        record = _record("k1", identifiers={"doi": "10.1016/j.media.2023.1"}, venue="MedIA")
        works = {
            "10.1016/j.media.2023.1": WorkMetrics(
                doi="10.1016/j.media.2023.1",
                work_type="article",
                source_type="journal",
                issn_l="1361-8415",
                source_name="Medical Image Analysis",
            )
        }
        journals = {
            "1361-8415": JournalMetrics(
                issn_l="1361-8415", display_name="Medical Image Analysis", mean_citedness_2yr=10.1
            )
        }
        ranked = rank_records([record], works=works, journals=journals)
        assert ranked[0].kind is VenueKind.JOURNAL
        assert ranked[0].metric == pytest.approx(10.1)
        assert ranked[0].band == DEFAULT_BANDS[0].label

    def test_conference_never_gets_a_journal_band(self) -> None:
        """会议拿到 LNCS 的影响因子是错的——那个数描述的是整套丛书，不是这个会。"""
        record = _record("k1", identifiers={"doi": "10.1007/978-3-031-16443-9_1"})
        works = {
            "10.1007/978-3-031-16443-9_1": WorkMetrics(
                doi="10.1007/978-3-031-16443-9_1",
                work_type="book-chapter",
                source_type="book series",
                issn_l="0302-9743",
                source_name="Lecture Notes in Computer Science",
            )
        }
        journals = {
            "0302-9743": JournalMetrics(
                issn_l="0302-9743", display_name="LNCS", mean_citedness_2yr=1.42
            )
        }
        ranked = rank_records([record], works=works, journals=journals)
        assert ranked[0].kind is VenueKind.CONFERENCE
        assert ranked[0].metric is None
        assert ranked[0].band == UNRANKED

    def test_preprint_is_unranked_not_excluded(self) -> None:
        record = _record("k1", venue="arXiv")
        ranked = rank_records([record], works={}, journals={})
        assert ranked[0].kind is VenueKind.PREPRINT
        assert ranked[0].band == UNRANKED

    def test_records_reason_when_unmatched(self) -> None:
        ranked = rank_records([_record("k1", venue="某刊")], works={}, journals={})
        assert ranked[0].unmatched_reason is not None

    def test_top_percentile_flag_is_carried(self) -> None:
        """论文级救济：低分刊上的高被引论文要能被单独识别出来。"""
        record = _record("k1", identifiers={"doi": "10.1/x"})
        works = {
            "10.1/x": WorkMetrics(
                doi="10.1/x",
                work_type="article",
                source_type="journal",
                issn_l="1234-5678",
                cited_by_count=200,
                in_top_10_percent=True,
            )
        }
        journals = {"1234-5678": JournalMetrics(issn_l="1234-5678", mean_citedness_2yr=1.2)}
        ranked = rank_records([record], works=works, journals=journals)
        assert ranked[0].in_top_10_percent is True
        assert ranked[0].band == DEFAULT_BANDS[-1].label


class TestMatchSummary:
    def test_counts_each_stage(self) -> None:
        records = [
            _record("k1", identifiers={"doi": "10.1/a"}),
            _record("k2", identifiers={"doi": "10.1/b"}),
            _record("k3"),
        ]
        works = {"10.1/a": WorkMetrics(doi="10.1/a", source_type="journal", issn_l="1234-5678")}
        journals = {"1234-5678": JournalMetrics(issn_l="1234-5678", mean_citedness_2yr=5.0)}
        summary = match_summary(rank_records(records, works=works, journals=journals))
        assert summary.total == 3
        assert summary.with_doi == 2
        assert summary.with_openalex == 1
        assert summary.with_issn == 1
        assert summary.with_metric == 1

    def test_openalex_hit_is_not_inferred_from_the_reason_text(self) -> None:
        """预印本有 DOI 但 OpenAlex 没收录时，不能因为它的 unmatched_reason
        写着"预印本"就被算成命中。状态要显式记录，不能靠文案反推。"""
        records = [_record("k1", venue="arXiv", identifiers={"doi": "10.48550/arXiv.2401.1"})]
        summary = match_summary(rank_records(records, works={}, journals={}))
        assert summary.with_doi == 1
        assert summary.with_openalex == 0


class TestTierReport:
    def test_reports_match_rate(self) -> None:
        ranked = rank_records([_record("k1")], works={}, journals={})
        text = tier_report_markdown(ranked, bands=DEFAULT_BANDS)
        assert "匹配率" in text

    def test_states_that_nothing_was_filtered(self) -> None:
        """报告必须自己声明它没有过滤——否则读的人会当成筛选结果。"""
        ranked = rank_records([_record("k1")], works={}, journals={})
        assert "未过滤" in tier_report_markdown(ranked, bands=DEFAULT_BANDS)

    def test_warns_that_metric_is_not_jif(self) -> None:
        """OpenAlex 的 2yr 不是 JIF，报告里不写清楚就会被当成 JIF 用。"""
        ranked = rank_records([_record("k1")], works={}, journals={})
        assert "不是 JIF" in tier_report_markdown(ranked, bands=DEFAULT_BANDS)


class TestFetchLayer:
    """取数层：分批、解析、以及"失败必须抛出"。"""

    @pytest.fixture
    def client(self):
        import httpx

        from litsearch.sources.base import HttpClient, RateLimiter

        return HttpClient(
            httpx.AsyncClient(timeout=5.0),
            rate_limiter=RateLimiter(min_interval=0.0),
            max_attempts=2,
            backoff_base=0.0,
        )

    @pytest.mark.asyncio
    async def test_batches_dois_by_fifty(self, respx_mock, client) -> None:
        import httpx

        from litsearch.rank import OPENALEX_WORKS, fetch_works

        route = respx_mock.get(OPENALEX_WORKS).mock(
            return_value=httpx.Response(200, json={"results": []})
        )
        await fetch_works(client, [f"10.1/{i}" for i in range(120)])
        assert route.call_count == 3

    @pytest.mark.asyncio
    async def test_strips_the_doi_url_prefix(self, respx_mock, client) -> None:
        import httpx

        from litsearch.rank import OPENALEX_WORKS, fetch_works

        respx_mock.get(OPENALEX_WORKS).mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "doi": "https://doi.org/10.1016/J.MEDIA.2023.1",
                            "type": "article",
                            "cited_by_count": 12,
                            "citation_normalized_percentile": {"is_in_top_10_percent": True},
                            "primary_location": {
                                "source": {
                                    "display_name": "Medical Image Analysis",
                                    "issn_l": "1361-8415",
                                    "type": "journal",
                                }
                            },
                        }
                    ]
                },
            )
        )
        works = await fetch_works(client, ["10.1016/j.media.2023.1"])
        assert "10.1016/j.media.2023.1" in works
        assert works["10.1016/j.media.2023.1"].in_top_10_percent is True

    @pytest.mark.asyncio
    async def test_journal_is_indexed_under_every_issn(self, respx_mock, client) -> None:
        """按电子版 ISSN 查、回来的是 issn_l 时，仍然要能查到。"""
        import httpx

        from litsearch.rank import OPENALEX_SOURCES, fetch_journals

        respx_mock.get(OPENALEX_SOURCES).mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "display_name": "Stroke",
                            "issn_l": "0039-2499",
                            "issn": ["0039-2499", "1524-4628"],
                            "type": "journal",
                            "summary_stats": {"2yr_mean_citedness": 1.81, "h_index": 457},
                        }
                    ]
                },
            )
        )
        journals = await fetch_journals(client, ["1524-4628"])
        assert journals["1524-4628"].display_name == "Stroke"
        assert journals["0039-2499"].display_name == "Stroke"

    @pytest.mark.asyncio
    async def test_http_failure_propagates(self, respx_mock, client) -> None:
        """取不到指标 ≠ 指标很低。静默降级会把前者伪装成后者。"""
        import httpx

        from litsearch.rank import OPENALEX_WORKS, fetch_works
        from litsearch.sources.base import SourceError

        respx_mock.get(OPENALEX_WORKS).mock(return_value=httpx.Response(500))
        with pytest.raises(SourceError):
            await fetch_works(client, ["10.1/a"])


class TestPersistence:
    def test_round_trip_preserves_every_field(self) -> None:
        """元数据取自有日配额的 OpenAlex；重跑渲染必须能不联网复用。"""
        from litsearch.rank import load_ranked, ranked_rows

        original = rank_records(
            [_record("k1", identifiers={"doi": "10.1/x"}, venue="某刊")],
            works={
                "10.1/x": WorkMetrics(
                    doi="10.1/x",
                    source_type="journal",
                    issn_l="1234-5678",
                    cited_by_count=42,
                    in_top_1_percent=True,
                    in_top_10_percent=True,
                )
            },
            journals={
                "1234-5678": JournalMetrics(
                    issn_l="1234-5678", display_name="某刊", mean_citedness_2yr=9.5, h_index=88
                )
            },
        )
        assert load_ranked(ranked_rows(original)) == original

    def test_unknown_fields_are_ignored(self) -> None:
        """加字段后的文件要能被旧代码读，反过来也一样。"""
        from litsearch.rank import load_ranked, ranked_rows

        rows = ranked_rows(rank_records([_record("k1")], works={}, journals={}))
        rows[0]["未来才有的字段"] = 1
        assert load_ranked(rows)[0].key == "k1"
