"""OpenReview 源：锚点短语检索 + 本地 AND。

两个实测事实决定了这个源的用法：

1. ``/notes?content.venueid=...`` 返回 **403 Challenge**，按会场枚举这条路走不通，
   只能用 ``/notes/search``；
2. ``/notes/search`` 对多词查询是 **OR** 语义——``ischemic stroke lesion segmentation``
   返回 ``count=10000``（返回上限），而加引号的 ``"ischemic stroke"`` 只返回 210 条。

所以：只用**锚点块**的短语逐条检索（每条结果集有界、可翻完），任务块在本地 AND。
另外 search 会返回评审意见这类**没有标题**的 note，必须剔除。

fixture 是 ``"ischemic stroke"`` 的真实响应：25 条 note，其中 1 条是无标题的评审意见。
"""

from __future__ import annotations

import json

import httpx

from litsearch.query import SourceQuery
from litsearch.sources.base import collect
from litsearch.sources.openreview import ENDPOINT, OpenReviewSource

from .conftest import fixture_text

PHRASE = "ischemic stroke"


def query(phrase: str = PHRASE) -> SourceQuery:
    return SourceQuery(source="openreview", query=phrase, kind="phrase", label=phrase)


def payload(notes: list, count: int) -> str:
    return json.dumps({"notes": notes, "count": count})


class TestFetch:
    def _mock(self, respx_mock, body: str | None = None):
        return respx_mock.get(ENDPOINT).mock(
            return_value=httpx.Response(200, text=body or fixture_text("openreview_search.json"))
        )

    async def test_phrase_is_quoted_in_the_request(self, respx_mock, stage3_context):
        """不加引号就变成 OR 语义，直接撞上 10,000 条上限——这是这个源的头号陷阱。"""
        route = self._mock(respx_mock)

        [item async for item in OpenReviewSource().fetch(query(), stage3_context)]

        assert route.calls[0].request.url.params["term"] == '"ischemic stroke"'

    async def test_untitled_notes_are_dropped(self, respx_mock, stage3_context):
        """search 会返回评审意见/评论，它们没有标题，不是论文。"""
        self._mock(respx_mock)

        records = [item async for item in OpenReviewSource().fetch(query(), stage3_context)]

        assert all(item.title for item in records)
        assert len(records) == 13  # 25 条 note → 24 条有标题 → 13 条通过本地 AND

    async def test_local_and_filter_is_applied(self, respx_mock, stage3_context):
        """服务端只保证命中锚点短语，任务块必须在本地过滤。"""
        self._mock(respx_mock)

        records = [item async for item in OpenReviewSource().fetch(query(), stage3_context)]

        assert all(
            "segmentation" in f"{item.title} {item.abstract or ''}".lower() for item in records
        )

    async def test_metadata_is_mapped(self, respx_mock, stage3_context):
        self._mock(respx_mock)

        records = [item async for item in OpenReviewSource().fetch(query(), stage3_context)]
        record = next(item for item in records if item.title.startswith("Uncertainty Estimation"))

        assert record.venue == "MIDL 2025 - Short Papers"
        assert "Ewout Heylen" in record.authors
        assert record.identifiers["openreview"] == "BXCmwipKRb"
        assert record.urls["landing"].endswith("BXCmwipKRb")

    async def test_publication_date_uses_millisecond_epoch(self, respx_mock, stage3_context):
        """OpenReview 的日期是**毫秒**时间戳，当秒用会把 2025 年算成 1970 年。"""
        self._mock(respx_mock)

        records = [item async for item in OpenReviewSource().fetch(query(), stage3_context)]
        record = next(item for item in records if item.title.startswith("Uncertainty Estimation"))

        assert record.dates.published_online.startswith("2025-")

    async def test_creation_date_is_submission_not_publication(self, respx_mock, stage3_context):
        self._mock(respx_mock)

        records = [item async for item in OpenReviewSource().fetch(query(), stage3_context)]
        record = records[0]

        assert record.dates.preprint_submitted is not None

    async def test_pagination_walks_offset_until_count_is_reached(self, respx_mock, stage3_context):
        note = {
            "id": "n1",
            "cdate": 1700000000000,
            "content": {
                "title": {"value": "Ischemic stroke segmentation"},
                "abstract": {"value": "lesion segmentation"},
            },
        }
        route = respx_mock.get(ENDPOINT).mock(
            side_effect=[
                httpx.Response(200, text=payload([dict(note, id=f"a{i}") for i in range(3)], 5)),
                httpx.Response(200, text=payload([dict(note, id=f"b{i}") for i in range(2)], 5)),
            ]
        )
        source = OpenReviewSource()
        source.page_size = 3

        records = [item async for item in source.fetch(query(), stage3_context)]

        assert len(records) == 5
        assert route.calls[1].request.url.params["offset"] == "3"

    async def test_a_short_page_ends_pagination(self, respx_mock, stage3_context):
        """服务端报的 count 与实际可翻条数不一定一致，短页必须能收住。"""
        respx_mock.get(ENDPOINT).mock(return_value=httpx.Response(200, text=payload([], 500)))

        records = [item async for item in OpenReviewSource().fetch(query(), stage3_context)]

        assert records == []

    async def test_reported_total_is_recorded(self, respx_mock, stage3_context):
        self._mock(respx_mock)

        outcome = await collect(OpenReviewSource(), query(), stage3_context)

        assert outcome.reported_total == 210
        assert outcome.status == "complete"

    async def test_raw_pages_are_persisted(self, respx_mock, stage3_context):
        self._mock(respx_mock)

        [item async for item in OpenReviewSource().fetch(query(), stage3_context)]

        assert list((stage3_context.store.root / "openreview").rglob("*.json.gz"))


class TestEstimate:
    async def test_estimate_uses_count_without_paging(self, respx_mock, stage3_context):
        route = respx_mock.get(ENDPOINT).mock(
            return_value=httpx.Response(200, text=fixture_text("openreview_search.json"))
        )

        total = await OpenReviewSource().estimate(query(), stage3_context)

        assert total == 210
        assert route.calls[0].request.url.params["limit"] == "1"


class TestQueryDialect:
    def test_multiword_unquoted_is_never_emitted(self, stage3_topic):
        """回归护栏：一旦有人把布尔串塞进来，这个源就会静默返回 10,000 条噪声。"""
        from litsearch.query import build_queries

        queries = [item for item in build_queries(stage3_topic) if item.source == "openreview"]

        assert queries, "openreview 应当生成锚点短语检索式"
        assert all(" AND " not in item.query and " OR " not in item.query for item in queries)

    def test_anchor_phrases_and_known_items_are_covered(self, stage3_topic):
        from litsearch.query import build_queries

        queries = [item for item in build_queries(stage3_topic) if item.source == "openreview"]
        labels = {item.label for item in queries}

        assert {"ischemic stroke", "stroke lesion", "ISLES challenge"} <= labels
        assert "segmentation" not in labels  # 任务块不当锚点
