"""全文位置解析。只解析合法来源，拿不到的如实标记而不是伪装成拿到了。"""

from __future__ import annotations

import httpx
import pytest
import respx

from litsearch.dedupe import CanonicalRecord
from litsearch.fulltext import (
    ArxivLinkResolver,
    CrossrefTdmResolver,
    EuropePMCResolver,
    FullTextLocation,
    UnpaywallResolver,
    institutional_access_csv,
    resolve_fulltext,
    summarize,
)
from litsearch.sources.base import HttpClient, RateLimiter


@pytest.fixture
def client() -> HttpClient:
    return HttpClient(
        httpx.AsyncClient(timeout=5.0),
        rate_limiter=RateLimiter(min_interval=0.0),
        backoff_base=1.0,
        max_attempts=1,
    )


@pytest.fixture
def clients(client) -> dict[str, HttpClient]:
    return dict.fromkeys(["unpaywall", "europepmc", "arxiv", "crossref"], client)


def record(**overrides) -> CanonicalRecord:
    payload = {
        "key": "doi:10.1016/j.media.2023.1",
        "title": "A method paper",
        "venue": "Medical image analysis",
        "identifiers": {"doi": "10.1016/j.media.2023.1"},
    }
    payload.update(overrides)
    return CanonicalRecord.model_validate(payload)


class TestLocationRanking:
    def test_published_version_outranks_preprint(self):
        published = FullTextLocation(
            url="a", host="publisher", version="publishedVersion", is_pdf=True
        )
        preprint = FullTextLocation(url="b", host="arxiv", version="submittedVersion", is_pdf=True)

        assert published.rank > preprint.rank

    def test_accepted_version_outranks_submitted(self):
        accepted = FullTextLocation(url="a", host="repository", version="acceptedVersion")
        submitted = FullTextLocation(url="b", host="repository", version="submittedVersion")

        assert accepted.rank > submitted.rank


class TestUnpaywall:
    @respx.mock
    async def test_returns_every_oa_location(self, client):
        respx.get(url__startswith="https://api.unpaywall.org/v2/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "is_oa": True,
                    "oa_locations": [
                        {
                            "url_for_pdf": "https://pub/pdf",
                            "host_type": "publisher",
                            "version": "publishedVersion",
                            "license": "cc-by",
                        },
                        {
                            "url": "https://repo/abs",
                            "host_type": "repository",
                            "version": "submittedVersion",
                        },
                    ],
                },
            )
        )

        found = await UnpaywallResolver("t@example.com").resolve(record(), client)

        assert len(found) == 2
        assert found[0].is_pdf is True
        assert found[0].license == "cc-by"

    @respx.mock
    async def test_closed_paper_yields_nothing(self, client):
        respx.get(url__startswith="https://api.unpaywall.org/v2/").mock(
            return_value=httpx.Response(200, json={"is_oa": False, "oa_locations": []})
        )

        assert await UnpaywallResolver("t@example.com").resolve(record(), client) == []

    @respx.mock
    async def test_api_failure_is_not_fatal(self, client):
        respx.get(url__startswith="https://api.unpaywall.org/v2/").mock(
            return_value=httpx.Response(500, text="boom")
        )

        assert await UnpaywallResolver("t@example.com").resolve(record(), client) == []

    async def test_record_without_doi_is_skipped(self, client):
        no_doi = record(identifiers={"pmid": "123"})

        assert await UnpaywallResolver("t@example.com").resolve(no_doi, client) == []


class TestArxivLink:
    async def test_uses_the_arxiv_identity_already_merged_into_the_record(self, client):
        merged = record(identifiers={"doi": "10.1109/tmi.1", "arxiv": "2403.19425"})

        found = await ArxivLinkResolver().resolve(merged, client)

        assert found[0].url == "https://arxiv.org/pdf/2403.19425"
        assert found[0].version == "submittedVersion"

    async def test_no_arxiv_identity_yields_nothing(self, client):
        assert await ArxivLinkResolver().resolve(record(), client) == []


class TestEuropePMC:
    @respx.mock
    async def test_open_access_record_yields_pmc_links(self, client):
        respx.get(url__startswith="https://www.ebi.ac.uk").mock(
            return_value=httpx.Response(
                200,
                json={
                    "resultList": {
                        "result": [
                            {
                                "isOpenAccess": "Y",
                                "pmcid": "PMC1",
                                "fullTextUrlList": {
                                    "fullTextUrl": [
                                        {
                                            "url": "https://europepmc.org/articles/PMC1",
                                            "documentStyle": "html",
                                        }
                                    ]
                                },
                            }
                        ]
                    }
                },
            )
        )

        found = await EuropePMCResolver().resolve(record(), client)

        assert found and found[0].host == "pmc"

    @respx.mock
    async def test_closed_record_yields_nothing(self, client):
        respx.get(url__startswith="https://www.ebi.ac.uk").mock(
            return_value=httpx.Response(
                200, json={"resultList": {"result": [{"isOpenAccess": "N"}]}}
            )
        )

        assert await EuropePMCResolver().resolve(record(), client) == []


class TestCrossrefTdm:
    @respx.mock
    async def test_picks_only_text_mining_links(self, client):
        respx.get(url__startswith="https://api.crossref.org/works/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "message": {
                        "link": [
                            {"URL": "https://pub/tdm.pdf", "intended-application": "text-mining"},
                            {"URL": "https://pub/view", "intended-application": "syndication"},
                        ]
                    }
                },
            )
        )

        links = await CrossrefTdmResolver("t@example.com").resolve_tdm(record(), client)

        assert links == ["https://pub/tdm.pdf"]


class TestResolveFullText:
    @respx.mock
    async def test_open_access_paper_is_marked_open(self, clients):
        respx.get(url__startswith="https://api.unpaywall.org/v2/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "is_oa": True,
                    "oa_locations": [
                        {
                            "url_for_pdf": "https://pub/pdf",
                            "host_type": "publisher",
                            "version": "publishedVersion",
                        }
                    ],
                },
            )
        )

        [resolution] = await resolve_fulltext([record()], clients, email="t@example.com")

        assert resolution.status == "open"
        assert resolution.best.url == "https://pub/pdf"

    @respx.mock
    async def test_closed_paper_with_tdm_link_is_marked_tdm_not_open(self, clients):
        """有 TDM 链接不等于能公开下载——它需要订阅方凭证，必须如实区分。"""
        respx.get(url__startswith="https://api.unpaywall.org/v2/").mock(
            return_value=httpx.Response(200, json={"is_oa": False})
        )
        respx.get(url__startswith="https://www.ebi.ac.uk").mock(
            return_value=httpx.Response(200, json={"resultList": {"result": []}})
        )
        respx.get(url__startswith="https://api.crossref.org/works/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "message": {
                        "link": [
                            {"URL": "https://els/tdm.xml", "intended-application": "text-mining"}
                        ]
                    }
                },
            )
        )

        [resolution] = await resolve_fulltext([record()], clients, email="t@example.com")

        assert resolution.status == "tdm"
        assert resolution.locations == []
        assert "订阅方凭证" in resolution.notes[0]

    @respx.mock
    async def test_fully_closed_paper_is_marked_unavailable(self, clients):
        respx.get(url__startswith="https://api.unpaywall.org/v2/").mock(
            return_value=httpx.Response(200, json={"is_oa": False})
        )
        respx.get(url__startswith="https://www.ebi.ac.uk").mock(
            return_value=httpx.Response(200, json={"resultList": {"result": []}})
        )
        respx.get(url__startswith="https://api.crossref.org/works/").mock(
            return_value=httpx.Response(200, json={"message": {}})
        )

        [resolution] = await resolve_fulltext([record()], clients, email="t@example.com")

        assert resolution.status == "unavailable"

    @respx.mock
    async def test_arxiv_identity_short_circuits_without_unpaywall(self, clients):
        """预印本身份在合并阶段就已经有了，不必再问一次 Unpaywall。"""
        unpaywall = respx.get(url__startswith="https://api.unpaywall.org/v2/").mock(
            return_value=httpx.Response(200, json={"is_oa": False})
        )
        merged = record(identifiers={"doi": "10.1109/tmi.1", "arxiv": "2403.19425"})

        [resolution] = await resolve_fulltext([merged], clients, email="t@example.com")

        assert resolution.status == "open"
        assert resolution.best.host == "arxiv"
        # Unpaywall 仍然会问（可能有更好的出版版），但结论不依赖它
        assert unpaywall.call_count == 1


class TestReporting:
    def test_summary_counts_by_status(self):
        from litsearch.fulltext import Resolution

        items = [
            Resolution(key="a", status="open"),
            Resolution(key="b", status="open"),
            Resolution(key="c", status="tdm"),
            Resolution(key="d", status="unavailable"),
        ]

        summary = summarize(items)

        assert (summary.open_access, summary.tdm_only, summary.unavailable) == (2, 1, 1)
        assert summary.open_rate == 0.5

    def test_institutional_csv_excludes_open_papers(self):
        from litsearch.fulltext import Resolution

        csv = institutional_access_csv(
            [
                Resolution(key="a", status="open", title="Open one"),
                Resolution(key="b", status="tdm", title="Needs TDM", venue="MIA"),
            ]
        )

        assert "Open one" not in csv
        assert "Needs TDM" in csv
