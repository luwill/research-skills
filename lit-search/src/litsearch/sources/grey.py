"""灰色文献（Zenodo）—— 挑战赛材料、数据集、基线权重、技术报告。

挑战赛的产出大多不进期刊：赛题说明、评测协议、基线模型权重都发在 Zenodo，
带正式 DOI 和日期，但 PubMed/OpenAlex 一条都查不到。实测
``"ischemic stroke lesion segmentation"`` 返回 9 条，其中包括 ISLES
2022/2024/2026 三届的官方记录——2026 那条（2026-04-29）正是本课题的赛题本身。

与 OpenReview 同样的约束：只有一个单框检索、多词是 OR 语义，所以同样走
"加引号的锚点短语 + 本地 AND"。

Zenodo 对宽泛查询会 **504**（实测裸 ``ISLES`` 一词就会超时），基础层的重试会覆盖；
重试仍失败必须报 failed，绝不能当成"这个源没有结果"。
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from litsearch.localfilter import build_matcher
from litsearch.normalize import DateEvidence, Record, clean_text
from litsearch.query import SourceQuery
from litsearch.sources.base import SourceContext, record_hash

ENDPOINT = "https://zenodo.org/api/records"
#: 未认证请求的每页上限就是 25。实测传 100 会返回
#: ``HTTP 400 A validation error occurred / Page size cannot be greater than 25``，
#: 而 400 不在可重试状态里，整批检索式会一起失败。
PAGE_SIZE = 25


class GreySource:
    name = "grey"

    def __init__(self) -> None:
        self.last_total: int | None = None
        self.page_size = PAGE_SIZE

    def _params(self, query: SourceQuery, size: int, page: int) -> dict[str, Any]:
        return {"q": f'"{query.query}"', "size": size, "page": page}

    async def estimate(self, query: SourceQuery, context: SourceContext) -> int | None:
        payload = await context.client.get_json(
            ENDPOINT, self._params(query, 1, 1), source=self.name
        )
        return _total(payload)

    async def fetch(self, query: SourceQuery, context: SourceContext) -> AsyncIterator[Record]:
        matcher = build_matcher(context.topic)
        page = 0
        seen = 0

        while True:
            page += 1
            body = await context.client.get_text(
                ENDPOINT,
                self._params(query, self.page_size, page),
                source=self.name,
                pages_fetched=page - 1,
            )
            context.store.write(self.name, query.query_hash, page, body, "json")

            payload = json.loads(body)
            if page == 1:
                self.last_total = _total(payload)
            hits = ((payload.get("hits") or {}).get("hits")) or []
            for hit in hits:
                if record := self._to_record(hit, matcher):
                    yield record

            seen += len(hits)
            if len(hits) < self.page_size or seen >= (self.last_total or 0):
                break

    def _to_record(self, hit: dict[str, Any], matcher) -> Record | None:
        metadata = hit.get("metadata") or {}
        title = clean_text(metadata.get("title"))
        if not title:
            return None

        # description 是 HTML，clean_text 会把标签剥掉
        abstract = clean_text(metadata.get("description"))
        if not matcher.matches_all_required(f"{title} {abstract}"):
            return None

        record_id = str(hit.get("id") or metadata.get("doi") or "")
        links = hit.get("links") or {}
        urls = {
            key: value
            for key, value in {
                "landing": links.get("self_html") or hit.get("doi_url"),
                "files": links.get("files"),
            }.items()
            if value
        }

        return Record(
            source=self.name,
            source_id=record_id,
            title=title,
            abstract=abstract or None,
            authors=[
                str(item.get("name")) for item in metadata.get("creators") or [] if item.get("name")
            ],
            venue="Zenodo",
            # dataset / software / publication 的区分留给筛选阶段，这里不丢
            publication_type=(metadata.get("resource_type") or {}).get("type"),
            identifiers={"doi": hit.get("doi") or metadata.get("doi")},
            urls=urls,
            dates=DateEvidence(published_online=metadata.get("publication_date")),
            raw_sha256=record_hash({"id": record_id, "title": title}),
        )


def _total(payload: dict[str, Any]) -> int | None:
    total = (payload.get("hits") or {}).get("total")
    # 新版 Zenodo 返回 {"total": {"value": N}}，旧版直接是整数
    if isinstance(total, dict):
        return total.get("value")
    return total
