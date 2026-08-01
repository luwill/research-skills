"""Crossref 会议录整卷补全：MICCAI/LNCS。

MICCAI 收录在 Springer LNCS 下，且在 Crossref 里的 type 是 **book-chapter**
而不是 proceedings-article——按 ``type:proceedings-article`` 过滤会一篇都拿不到。

关键发现：LNCS 的 DOI 后缀里就嵌着这一卷的 ISBN——
``10.1007/978-3-031-16443-9_1`` → ISBN ``9783031164439``。
所以语料里**任何一篇** MICCAI 论文都能解锁它所在的整卷，把同卷的兄弟篇一次补齐。
这是引文滚雪球之外的另一条闭包路径，且完全不消耗 OpenAlex 配额。

另一个实测陷阱：``filter=isbn:`` 必须传**去掉连字符**的 ISBN。
``isbn:978-3-031-16443-9`` 静默返回 0 条，``isbn:9783031164439`` 返回 70 条。
"""

from __future__ import annotations

import json

import httpx
import pytest

from litsearch.normalize import parse_partial_date
from litsearch.query import SourceQuery
from litsearch.sources.crossref import (
    ENDPOINT,
    CrossrefVolumeSource,
    discover_volumes,
    isbn_from_doi,
)

from .conftest import fixture_text


class TestIsbnFromDoi:
    def test_extracts_isbn_from_a_real_lncs_doi(self):
        assert isbn_from_doi("10.1007/978-3-031-16443-9_1") == "9783031164439"

    def test_strips_hyphens_because_the_filter_silently_returns_zero_with_them(self):
        assert "-" not in isbn_from_doi("10.1007/978-3-031-72111-3_20")

    def test_handles_uppercase_and_url_forms(self):
        assert isbn_from_doi("https://doi.org/10.1007/978-3-031-43990-2_5") == "9783031439902"

    @pytest.mark.parametrize(
        "doi",
        [
            "10.1038/s41597-022-01875-5",  # 期刊论文
            "10.1109/tmi.2024.3362879",
            "10.48550/arxiv.2206.06694",
            None,
            "",
        ],
    )
    def test_non_lncs_dois_yield_nothing(self, doi):
        assert isbn_from_doi(doi) is None


class TestDiscoverVolumes:
    def test_collects_distinct_isbns_from_a_corpus(self):
        dois = [
            "10.1007/978-3-031-16443-9_1",
            "10.1007/978-3-031-16443-9_57",  # 同卷
            "10.1007/978-3-031-72111-3_20",
            "10.1038/s41597-022-01875-5",  # 非 LNCS
        ]

        assert discover_volumes(dois) == ["9783031164439", "9783031721113"]

    def test_empty_corpus_yields_nothing(self):
        assert discover_volumes([]) == []


def query(isbn: str = "9783031164439") -> SourceQuery:
    return SourceQuery(source="crossref", query=isbn, kind="volume", label=f"ISBN {isbn}")


class TestFetch:
    def _mock(self, respx_mock, body: str | None = None):
        """真实的一卷会翻到空页为止。用**可终止的序列**建模而不是 return_value：
        翻页跑飞时会直接报"没有更多响应"，而不是安静地转下去。"""
        empty = json.dumps({"message": {"total-results": 70, "items": [], "next-cursor": "z"}})
        return respx_mock.get(ENDPOINT).mock(
            side_effect=[
                httpx.Response(200, text=body or fixture_text("crossref_isbn.json")),
                httpx.Response(200, text=empty),
            ]
        )

    async def test_isbn_filter_has_no_hyphens(self, respx_mock, stage3_context):
        route = self._mock(respx_mock)

        [item async for item in CrossrefVolumeSource().fetch(query(), stage3_context)]

        assert route.calls[0].request.url.params["filter"] == "isbn:9783031164439"

    async def test_parses_the_real_volume(self, respx_mock, stage3_context):
        self._mock(respx_mock)

        records = [item async for item in CrossrefVolumeSource().fetch(query(), stage3_context)]

        assert len(records) == 20
        first = records[0]
        assert first.identifiers["doi"] == "10.1007/978-3-031-16443-9_4"
        assert first.title.startswith("Exploring Smoothness and Class-Separation")
        assert "Yicheng Wu" in first.authors

    async def test_venue_is_the_proceedings_not_the_series(self, respx_mock, stage3_context):
        """container-title 是 ['Lecture Notes in Computer Science', 'MICCAI 2022']——
        取第一个会得到毫无信息量的丛书名。"""
        self._mock(respx_mock)

        records = [item async for item in CrossrefVolumeSource().fetch(query(), stage3_context)]

        assert "MICCAI" in records[0].venue

    async def test_year_only_dates_keep_their_precision(self, respx_mock, stage3_context):
        """Crossref 的 ``published`` 是"已知最早发表日期"，不区分在线/印刷，
        因此进优先级最低的 source_reported，不冒充确切语义；年份精度原样保留。"""
        self._mock(respx_mock)

        records = [item async for item in CrossrefVolumeSource().fetch(query(), stage3_context)]

        assert records[0].dates.source_reported == "2022"
        assert records[0].dates.published_online is None
        assert parse_partial_date("2022").precision == "year"

    async def test_cursor_pagination_walks_the_whole_volume(self, respx_mock, stage3_context):
        body = json.loads(fixture_text("crossref_isbn.json"))
        tail = {
            "message": {
                "total-results": 70,
                "items": body["message"]["items"][:5],
                "next-cursor": "cur2",
            }
        }
        empty = {"message": {"total-results": 70, "items": [], "next-cursor": "cur3"}}
        route = respx_mock.get(ENDPOINT).mock(
            side_effect=[
                httpx.Response(200, text=fixture_text("crossref_isbn.json")),
                httpx.Response(200, text=json.dumps(tail)),
                httpx.Response(200, text=json.dumps(empty)),
            ]
        )

        records = [item async for item in CrossrefVolumeSource().fetch(query(), stage3_context)]

        assert len(records) == 25
        assert route.calls[1].request.url.params["cursor"] == body["message"]["next-cursor"]

    async def test_whole_volume_is_kept_without_local_filtering(self, respx_mock, stage3_context):
        """整卷补全的目的就是拿到同卷兄弟篇，不能在这里按概念块过滤——
        筛选是筛选阶段的事，这里过滤等于把召回边界又收窄一次。"""
        self._mock(respx_mock)

        records = [item async for item in CrossrefVolumeSource().fetch(query(), stage3_context)]

        assert any("stroke" not in item.title.lower() for item in records)

    async def test_reported_total_is_the_volume_size(self, respx_mock, stage3_context):
        self._mock(respx_mock)
        source = CrossrefVolumeSource()

        [item async for item in source.fetch(query(), stage3_context)]

        assert source.last_total == 70

    async def test_polite_pool_email_is_sent(self, respx_mock, stage3_context):
        route = self._mock(respx_mock)

        [item async for item in CrossrefVolumeSource().fetch(query(), stage3_context)]

        assert route.calls[0].request.url.params["mailto"] == "probe@example.com"
