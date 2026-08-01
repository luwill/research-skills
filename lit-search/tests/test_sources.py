"""源解析与翻页测试，回放**录制的真实响应**，不打网络。

fixture 取自各源的线上真实响应（见 tests/fixtures/）。用真实结构而非手搓样例，
才能抓到 PubMed 的 ReferenceList 污染 DOI 这类只有真数据才暴露的问题。
"""

from __future__ import annotations

import gzip
import json
from datetime import date
from pathlib import Path

import httpx
import pytest
import respx

from litsearch.normalize import Record, WindowStatus
from litsearch.protocol import Topic
from litsearch.query import SourceQuery
from litsearch.sources.arxiv import ArxivSource
from litsearch.sources.base import HttpClient, PageStore, RateLimiter, SourceContext, collect
from litsearch.sources.europepmc import EuropePMCSource
from litsearch.sources.openalex import OpenAlexSource, restore_abstract
from litsearch.sources.pubmed import PubMedSource

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.fixture
def topic() -> Topic:
    return Topic.model_validate(
        {
            "id": "t",
            "title": "T",
            "window": {
                "start": "2021-07-01",
                "end": "2026-07-27",
                "harvest_margin_days": 365,
            },
            "concepts": {"a": {"required": True, "terms": ["stroke"]}},
            "query_plan": {"combinations": [["a"]]},
            "criteria": {"include": [{"id": "I1", "text": "x"}]},
        }
    )


@pytest.fixture
def context(topic, tmp_path) -> SourceContext:
    client = HttpClient(
        httpx.AsyncClient(timeout=5.0),
        rate_limiter=RateLimiter(min_interval=0.0),
        backoff_base=0.0,  # 测试回放验证重试次数，不消耗真实退避时间
    )
    return SourceContext(
        client=client,
        store=PageStore(tmp_path / "raw"),
        topic=topic,
        contact_email="test@example.com",
    )


def topic_with_single_day_window() -> Topic:
    """采集窗口只有一天，用于构造"再也切不动"的极端情况。"""
    return Topic.model_validate(
        {
            "id": "t",
            "title": "T",
            "window": {
                "start": "2023-01-01",
                "end": "2023-01-01",
                "harvest_margin_days": 0,
            },
            "concepts": {"a": {"required": True, "terms": ["stroke"]}},
            "query_plan": {"combinations": [["a"]]},
            "criteria": {"include": [{"id": "I1", "text": "x"}]},
        }
    )


def query(source: str) -> SourceQuery:
    return SourceQuery(source=source, query='"stroke lesion segmentation"', kind="crossproduct")


async def drain(source, source_query, context) -> list[Record]:
    return [record async for record in source.fetch(source_query, context)]


class TestOpenAlex:
    def test_restore_abstract_from_inverted_index(self):
        assert restore_abstract({"Stroke": [0], "lesion": [1], "segmentation": [2]}) == (
            "Stroke lesion segmentation"
        )
        assert restore_abstract(None) is None

    @respx.mock
    async def test_parses_real_page(self, context):
        respx.get("https://api.openalex.org/works").mock(
            side_effect=[
                httpx.Response(200, text=fixture("openalex_page1.json")),
                httpx.Response(200, json={"results": [], "meta": {"next_cursor": None}}),
            ]
        )

        records = await drain(OpenAlexSource(), query("openalex"), context)

        assert len(records) == 2
        first = records[0]
        assert first.source == "openalex"
        assert first.title
        assert first.identifiers.get("openalex", "").startswith("W")
        assert first.canonical_date is None  # resolve() 由上层调用，源层不做窗口判定

    @respx.mock
    async def test_follows_cursor_until_exhausted(self, context):
        page = json.loads(fixture("openalex_page1.json"))
        route = respx.get("https://api.openalex.org/works").mock(
            side_effect=[
                httpx.Response(200, json=page),
                httpx.Response(200, json={"results": [], "meta": {"next_cursor": "c2"}}),
            ]
        )

        await drain(OpenAlexSource(), query("openalex"), context)

        assert route.call_count == 2
        assert "cursor=%2A" in str(route.calls[0].request.url)

    @respx.mock
    async def test_estimate_reads_meta_count(self, context):
        respx.get("https://api.openalex.org/works").mock(
            return_value=httpx.Response(200, json={"meta": {"count": 369}, "results": []})
        )

        assert await OpenAlexSource().estimate(query("openalex"), context) == 369

    @respx.mock
    async def test_raw_pages_are_persisted(self, context, tmp_path):
        respx.get("https://api.openalex.org/works").mock(
            side_effect=[
                httpx.Response(200, text=fixture("openalex_page1.json")),
                httpx.Response(200, json={"results": [], "meta": {}}),
            ]
        )

        source_query = query("openalex")
        await drain(OpenAlexSource(), source_query, context)

        saved = tmp_path / "raw" / "openalex" / source_query.query_hash / "page_0001.json.gz"
        assert saved.exists()
        assert "results" in gzip.decompress(saved.read_bytes()).decode()

    async def test_comma_in_query_is_rejected(self, context):
        # OpenAlex 的 filter 用逗号分隔条件，检索式含逗号会被静默截断成两个过滤器
        with pytest.raises(Exception, match="逗号"):
            await drain(
                OpenAlexSource(),
                SourceQuery(source="openalex", query="stroke, segmentation", kind="crossproduct"),
                context,
            )

    @respx.mock
    async def test_harvest_window_is_used_not_strict_window(self, context):
        route = respx.get("https://api.openalex.org/works").mock(
            return_value=httpx.Response(200, json={"meta": {"count": 0}, "results": []})
        )

        await OpenAlexSource().estimate(query("openalex"), context)

        url = str(route.calls[0].request.url)
        assert "2020-07-01" in url and "2027-07-27" in url


class TestPubMed:
    @respx.mock
    async def test_article_doi_is_not_polluted_by_reference_list(self, context):
        """回归测试：曾用 ".//ArticleIdList" 取到最后一条参考文献的 DOI。"""
        respx.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi").mock(
            return_value=httpx.Response(
                200,
                json={
                    "esearchresult": {
                        "count": "2",
                        "webenv": "MCID_x",
                        "querykey": "1",
                    }
                },
            )
        )
        respx.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi").mock(
            return_value=httpx.Response(200, text=fixture("pubmed_efetch.xml"))
        )

        records = await drain(PubMedSource(), query("pubmed"), context)

        assert len(records) == 2
        first = next(item for item in records if item.identifiers["pmid"] == "42469491")
        assert first.identifiers["doi"] == "10.1007/s10278-026-02121-9"
        # 参考文献里的 DOI 一条都不能出现在标识符里
        assert first.identifiers["doi"] != "10.1007/s11263-019-01228-7"

    @respx.mock
    async def test_reference_list_feeds_backward_snowball(self, context):
        respx.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi").mock(
            return_value=httpx.Response(
                200, json={"esearchresult": {"count": "2", "webenv": "M", "querykey": "1"}}
            )
        )
        respx.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi").mock(
            return_value=httpx.Response(200, text=fixture("pubmed_efetch.xml"))
        )

        records = await drain(PubMedSource(), query("pubmed"), context)
        first = next(item for item in records if item.identifiers["pmid"] == "42469491")

        assert len(first.referenced_works) > 50
        assert all(item.startswith("doi:") for item in first.referenced_works)

    @respx.mock
    async def test_extracts_title_abstract_dates(self, context):
        respx.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi").mock(
            return_value=httpx.Response(
                200, json={"esearchresult": {"count": "2", "webenv": "M", "querykey": "1"}}
            )
        )
        respx.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi").mock(
            return_value=httpx.Response(200, text=fixture("pubmed_efetch.xml"))
        )

        records = await drain(PubMedSource(), query("pubmed"), context)
        first = records[0]

        assert first.title
        assert first.abstract
        assert first.authors
        assert first.dates.published_online == "2026-07-17"

    @respx.mock
    async def test_uses_history_server(self, context):
        search = respx.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi").mock(
            return_value=httpx.Response(
                200, json={"esearchresult": {"count": "2", "webenv": "M", "querykey": "1"}}
            )
        )
        fetch = respx.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi").mock(
            return_value=httpx.Response(200, text=fixture("pubmed_efetch.xml"))
        )

        await drain(PubMedSource(), query("pubmed"), context)

        assert "usehistory=y" in str(search.calls[0].request.url)
        assert "WebEnv=M" in str(fetch.calls[0].request.url)

    @respx.mock
    async def test_query_over_9999_hits_is_split_by_date(self, context):
        """PubMed 硬上限 9,999：不切分就会静默少召回 40%（本课题实测 16,725 命中）。"""
        counts = iter(["16725", "9000", "7725"])
        respx.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi").mock(
            side_effect=lambda request: httpx.Response(
                200,
                json={
                    "esearchresult": {
                        "count": next(counts),
                        "webenv": "W",
                        "querykey": "1",
                    }
                },
            )
        )
        fetch = respx.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi").mock(
            return_value=httpx.Response(200, text=fixture("pubmed_efetch.xml"))
        )

        source = PubMedSource()
        await drain(source, query("pubmed"), context)

        # 整段超限 -> 二分成两段，两段都在限内
        assert source.last_total == 9000 + 7725
        starts = sorted(
            {str(call.request.url).split("retstart=")[1].split("&")[0] for call in fetch.calls},
            key=int,
        )
        assert starts[0] == "0"
        # 两段共 16,725 条，按 200 一批 -> 84 次 efetch，且 retstart 从未越过 9998
        assert max(int(value) for value in starts) <= 9998

    @respx.mock
    async def test_unsplittable_slice_is_reported_not_silently_truncated(self, context):
        """单日仍超上限时必须报错，绝不能假装取全了。"""
        respx.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi").mock(
            return_value=httpx.Response(
                200, json={"esearchresult": {"count": "50000", "webenv": "W", "querykey": "1"}}
            )
        )
        respx.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi").mock(
            return_value=httpx.Response(200, text=fixture("pubmed_efetch.xml"))
        )
        one_day = topic_with_single_day_window()
        context.topic = one_day

        with pytest.raises(Exception, match="截断"):
            await drain(PubMedSource(), query("pubmed"), context)

    @respx.mock
    async def test_missing_history_fails_loudly(self, context):
        # 拿不到 WebEnv 就无法取全 10,000 条以上的结果，必须报错而不是只取一页
        respx.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi").mock(
            return_value=httpx.Response(200, json={"esearchresult": {"count": "20000"}})
        )

        with pytest.raises(Exception, match="WebEnv"):
            await drain(PubMedSource(), query("pubmed"), context)

    @respx.mock
    async def test_zero_hits_yields_nothing(self, context):
        respx.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi").mock(
            return_value=httpx.Response(200, json={"esearchresult": {"count": "0"}})
        )

        assert await drain(PubMedSource(), query("pubmed"), context) == []


class TestEuropePMC:
    @respx.mock
    async def test_parses_real_page(self, context):
        payload = json.loads(fixture("europepmc_page1.json"))
        respx.get("https://www.ebi.ac.uk/europepmc/webservices/rest/search").mock(
            side_effect=[
                httpx.Response(200, json=payload),
                httpx.Response(200, json={"resultList": {"result": []}, "nextCursorMark": None}),
            ]
        )

        records = await drain(EuropePMCSource(), query("europepmc"), context)

        assert len(records) == 2
        assert records[0].title
        assert records[0].dates.published_online

    @respx.mock
    async def test_stops_on_repeated_cursor(self, context):
        """服务端返回同一个 cursorMark 时必须停止，否则会无限翻页。"""
        payload = json.loads(fixture("europepmc_page1.json"))
        payload["nextCursorMark"] = "*"
        route = respx.get("https://www.ebi.ac.uk/europepmc/webservices/rest/search").mock(
            return_value=httpx.Response(200, json=payload)
        )

        await drain(EuropePMCSource(), query("europepmc"), context)

        assert route.call_count == 1

    @respx.mock
    async def test_estimate_reads_hit_count(self, context):
        respx.get("https://www.ebi.ac.uk/europepmc/webservices/rest/search").mock(
            return_value=httpx.Response(200, json={"hitCount": 101})
        )

        assert await EuropePMCSource().estimate(query("europepmc"), context) == 101


class TestArxiv:
    @respx.mock
    async def test_parses_real_atom_feed(self, context):
        respx.get("https://export.arxiv.org/api/query").mock(
            return_value=httpx.Response(200, text=fixture("arxiv_page1.xml"))
        )

        records = await drain(ArxivSource(), query("arxiv"), context)

        assert len(records) == 2
        first = records[0]
        assert first.identifiers["arxiv"]
        assert "v" not in first.identifiers["arxiv"].split(".")[-1]  # 版本号已剥离
        assert first.publication_type == "preprint"
        # v1 提交日落在 preprint_submitted，而不是 published_online
        assert first.dates.preprint_submitted
        assert first.dates.published_online is None

    @respx.mock
    async def test_pagination_stops_at_total(self, context):
        route = respx.get("https://export.arxiv.org/api/query").mock(
            return_value=httpx.Response(200, text=fixture("arxiv_page1.xml"))
        )

        await drain(ArxivSource(), query("arxiv"), context)

        # fixture 的 totalResults=2 < PAGE_SIZE，一页即止
        assert route.call_count == 1


class TestCollect:
    @respx.mock
    async def test_failure_becomes_partial_not_silent_zero(self, context):
        respx.get("https://api.openalex.org/works").mock(
            side_effect=[
                httpx.Response(200, text=fixture("openalex_page1.json")),
                httpx.Response(500, text="boom"),
                httpx.Response(500, text="boom"),
                httpx.Response(500, text="boom"),
                httpx.Response(500, text="boom"),
            ]
        )

        result = await collect(OpenAlexSource(), query("openalex"), context)

        assert result.status == "partial"
        assert result.error is not None
        assert len(result.records) == 2
        # 总数来自第一页的 meta，无需额外请求
        assert result.reported_total == 369

    @respx.mock
    async def test_success_is_marked_complete_and_tags_provenance(self, context):
        respx.get("https://api.openalex.org/works").mock(
            side_effect=[
                httpx.Response(200, text=fixture("openalex_page1.json")),
                httpx.Response(200, json={"results": [], "meta": {}}),
            ]
        )
        source_query = query("openalex")

        result = await collect(OpenAlexSource(), source_query, context)

        assert result.status == "complete"
        assert all(record.found_by == [source_query.query_hash] for record in result.records)

    @respx.mock
    async def test_no_separate_estimate_request_by_default(self, context):
        """采集时不额外打 estimate——OpenAlex 匿名配额每天只有约 100 次请求。"""
        route = respx.get("https://api.openalex.org/works").mock(
            side_effect=[
                httpx.Response(200, text=fixture("openalex_page1.json")),
                httpx.Response(200, json={"results": [], "meta": {}}),
            ]
        )

        await collect(OpenAlexSource(), query("openalex"), context)

        assert route.call_count == 2  # 两页翻页，没有第三次 estimate 请求

    @respx.mock
    async def test_quota_exhaustion_fails_fast_instead_of_sleeping(self, context):
        """Retry-After 长达数小时时必须立刻失败，不能把流水线挂死。"""
        respx.get("https://api.openalex.org/works").mock(
            return_value=httpx.Response(
                429,
                headers={"retry-after": "53780", "x-ratelimit-remaining": "0"},
                text="quota",
            )
        )

        result = await collect(OpenAlexSource(), query("openalex"), context)

        assert result.status == "failed"
        assert "配额" in result.error
        assert "53,780" in result.error


class TestWindowIntegration:
    async def test_records_are_resolved_against_the_strict_window(self, context, topic):
        """采集窗口放宽到 2020-07-01，纳排仍以严格窗口 2021-07-01 起算。"""
        inside = Record(
            source="openalex",
            source_id="W1",
            title="Just inside the strict window",
            dates={"published_online": "2021-08-01"},
        ).resolve(topic.window, topic.window.date_priority)

        outside = Record(
            source="openalex",
            source_id="W2",
            title="Harvested by the widened window but outside the strict one",
            dates={"published_online": "2020-11-01"},
        ).resolve(topic.window, topic.window.date_priority)

        assert inside.canonical_date.earliest == date(2021, 8, 1)
        assert inside.window_status is WindowStatus.IN_WINDOW
        assert inside.needs_human_review is False

        assert outside.window_status is WindowStatus.OUT_OF_WINDOW
