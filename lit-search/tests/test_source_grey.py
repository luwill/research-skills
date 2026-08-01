"""灰色文献源（Zenodo）：挑战赛材料、数据集、模型权重、技术报告。

挑战赛的产出大多不进期刊：ISLES 各届的赛题说明、基线权重、评测脚本都发在 Zenodo，
带正式 DOI 和日期。实测 ``"ischemic stroke lesion segmentation"`` 返回 9 条，
其中包括 ISLES 2022/2024/2026 三届的官方记录——这些在 PubMed/OpenAlex 里都查不到。

与 OpenReview 相同的约束：Zenodo 只有一个单框检索，多词是 OR 语义，
因此同样走"锚点短语 + 本地 AND"。
"""

from __future__ import annotations

import json

import httpx

from litsearch.query import SourceQuery
from litsearch.sources.base import collect
from litsearch.sources.grey import ENDPOINT, GreySource

from .conftest import fixture_text

PHRASE = "ischemic stroke lesion segmentation"


def query(phrase: str = PHRASE) -> SourceQuery:
    return SourceQuery(source="grey", query=phrase, kind="phrase", label=phrase)


class TestFetch:
    def _mock(self, respx_mock, body: str | None = None):
        return respx_mock.get(ENDPOINT).mock(
            return_value=httpx.Response(200, text=body or fixture_text("zenodo_records.json"))
        )

    async def test_phrase_is_quoted(self, respx_mock, stage3_context):
        route = self._mock(respx_mock)

        [item async for item in GreySource().fetch(query(), stage3_context)]

        assert route.calls[0].request.url.params["q"] == f'"{PHRASE}"'

    async def test_parses_the_real_response(self, respx_mock, stage3_context):
        self._mock(respx_mock)

        records = [item async for item in GreySource().fetch(query(), stage3_context)]

        assert len(records) == 9
        challenge = next(item for item in records if item.title.endswith("Challenge 2024"))
        assert challenge.identifiers["doi"] == "10.5281/zenodo.10991145"
        assert challenge.dates.published_online == "2024-04-18"

    async def test_html_in_the_description_is_stripped(self, respx_mock, stage3_context):
        self._mock(respx_mock)

        records = [item async for item in GreySource().fetch(query(), stage3_context)]

        assert all("<p>" not in (item.abstract or "") for item in records)

    async def test_month_precision_dates_are_preserved(self, respx_mock, stage3_context):
        """Zenodo 允许 ``2026-03`` 这种只到月的日期，不能补成某一天。"""
        self._mock(respx_mock)

        records = [item async for item in GreySource().fetch(query(), stage3_context)]
        record = next(item for item in records if item.dates.published_online == "2026-03")

        assert record.canonical_date is None or record.canonical_date.precision != "day"

    async def test_resource_type_is_carried_through(self, respx_mock, stage3_context):
        """dataset / software / publication 的区分要留给筛选阶段，不在这里丢掉。"""
        self._mock(respx_mock)

        records = [item async for item in GreySource().fetch(query(), stage3_context)]

        assert {"dataset", "software", "other"} <= {item.publication_type for item in records}

    async def test_arxiv_doi_on_a_zenodo_record_is_linked(self, respx_mock, stage3_context):
        """ISLES'22 集成算法的权重记录挂的是 arXiv DOI——必须能与语料里的预印本合并。"""
        self._mock(respx_mock)

        records = [item async for item in GreySource().fetch(query(), stage3_context)]
        record = next(item for item in records if "Ensemble Algorithm" in item.title)

        assert record.identifiers["arxiv"] == "2403.19425"

    async def test_local_and_filter_applies(self, respx_mock, stage3_context):
        body = {
            "hits": {
                "total": 1,
                "hits": [
                    {
                        "id": 1,
                        "doi": "10.5281/zenodo.1",
                        "metadata": {
                            "title": "A cardiology dataset",
                            "description": "No imaging task here",
                            "publication_date": "2024-01-01",
                            "resource_type": {"type": "dataset"},
                        },
                    }
                ],
            }
        }
        self._mock(respx_mock, json.dumps(body))

        records = [item async for item in GreySource().fetch(query(), stage3_context)]

        assert records == []

    async def test_pagination_walks_pages(self, respx_mock, stage3_context):
        def page(ids: list[int]) -> str:
            return json.dumps(
                {
                    "hits": {
                        "total": 4,
                        "hits": [
                            {
                                "id": i,
                                "doi": f"10.5281/zenodo.{i}",
                                "metadata": {
                                    "title": "Ischemic stroke lesion segmentation report",
                                    "description": "d",
                                    "publication_date": "2024-01-01",
                                    "resource_type": {"type": "other"},
                                },
                            }
                            for i in ids
                        ],
                    }
                }
            )

        route = respx_mock.get(ENDPOINT).mock(
            side_effect=[
                httpx.Response(200, text=page([1, 2])),
                httpx.Response(200, text=page([3, 4])),
            ]
        )
        source = GreySource()
        source.page_size = 2

        records = [item async for item in source.fetch(query(), stage3_context)]

        assert len(records) == 4
        assert route.calls[1].request.url.params["page"] == "2"

    async def test_page_size_stays_within_the_unauthenticated_cap(self, respx_mock, stage3_context):
        """实测：未认证请求 size 超过 25 会返回 HTTP 400（validation error），
        而且它不在可重试状态里——26 条检索式会**整批**失败。"""
        route = self._mock(respx_mock)

        [item async for item in GreySource().fetch(query(), stage3_context)]

        assert int(route.calls[0].request.url.params["size"]) <= 25

    async def test_reported_total_is_recorded(self, respx_mock, stage3_context):
        self._mock(respx_mock)

        outcome = await collect(GreySource(), query(), stage3_context)

        assert outcome.reported_total == 9
        assert outcome.status == "complete"

    async def test_gateway_timeout_is_retried_not_swallowed(self, respx_mock, stage3_context):
        """实测宽泛查询会 504。重试仍失败就必须报错，绝不能当成"这个源没有结果"。"""
        respx_mock.get(ENDPOINT).mock(return_value=httpx.Response(504, text="Gateway Time-out"))

        outcome = await collect(GreySource(), query(), stage3_context)

        assert outcome.status == "failed"
        assert "504" in (outcome.error or "")

    async def test_raw_pages_are_persisted(self, respx_mock, stage3_context):
        self._mock(respx_mock)

        [item async for item in GreySource().fetch(query(), stage3_context)]

        assert list((stage3_context.store.root / "grey").rglob("*.json.gz"))
