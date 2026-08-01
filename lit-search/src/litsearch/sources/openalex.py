"""OpenAlex Works API —— 召回主干与引文图。

翻页用 cursor（每页 200 条），因此不存在"只取前 N 条"的采样问题。
日期语义：OpenAlex 的 ``publication_date`` 对正式发表物通常是 online-first 日期，
对 preprint 则是投递日期，因此按 ``type`` 分别落入不同的日期证据字段。
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from litsearch.normalize import DateEvidence, Record
from litsearch.query import SourceQuery
from litsearch.sources.base import SourceContext, SourceError, record_hash

ENDPOINT = "https://api.openalex.org/works"
PER_PAGE = 200
SELECT = (
    "id,doi,display_name,publication_date,publication_year,type,cited_by_count,"
    "is_retracted,primary_location,authorships,ids,abstract_inverted_index,language"
)


def restore_abstract(index: Any) -> str | None:
    """OpenAlex 只给倒排索引，需要还原成正文。"""
    if not isinstance(index, dict):
        return None
    positions: list[tuple[int, str]] = []
    for word, offsets in index.items():
        for offset in offsets or []:
            positions.append((int(offset), str(word)))
    positions.sort()
    return " ".join(word for _, word in positions) or None


class OpenAlexSource:
    name = "openalex"

    def __init__(self) -> None:
        self.last_total: int | None = None

    def _filter(self, query: SourceQuery, context: SourceContext) -> str:
        if "," in query.query:
            # OpenAlex 的 filter 用逗号分隔多个条件，检索式里出现逗号会被截断成两个过滤器
            raise SourceError(self.name, "OpenAlex 检索式不能包含逗号")
        window = context.window
        return ",".join(
            [
                f"from_publication_date:{window.harvest_start.isoformat()}",
                f"to_publication_date:{window.harvest_end.isoformat()}",
                f"title_and_abstract.search:{query.query}",
            ]
        )

    def _params(self, query: SourceQuery, context: SourceContext) -> dict[str, Any]:
        params: dict[str, Any] = {"filter": self._filter(query, context)}
        if context.contact_email:
            params["mailto"] = context.contact_email
        if key := context.api_keys.get("openalex"):
            params["api_key"] = key
        return params

    async def estimate(self, query: SourceQuery, context: SourceContext) -> int | None:
        params = self._params(query, context) | {"per-page": 1, "select": "id"}
        payload = await context.client.get_json(ENDPOINT, params, source=self.name)
        return (payload.get("meta") or {}).get("count")

    async def fetch(self, query: SourceQuery, context: SourceContext) -> AsyncIterator[Record]:
        cursor: str | None = "*"
        page = 0
        while cursor:
            params = self._params(query, context) | {
                "per-page": PER_PAGE,
                "select": SELECT,
                "cursor": cursor,
            }
            body = await context.client.get_text(
                ENDPOINT, params, source=self.name, pages_fetched=page
            )
            page += 1
            context.store.write(self.name, query.query_hash, page, body, "json")

            payload = json.loads(body)
            if page == 1:
                self.last_total = (payload.get("meta") or {}).get("count")
            results = payload.get("results") or []
            for item in results:
                if record := self._to_record(item):
                    yield record

            cursor = (payload.get("meta") or {}).get("next_cursor")
            if not results:
                break

    def _to_record(self, item: dict[str, Any]) -> Record | None:
        source_id = str(item.get("id") or "").rsplit("/", 1)[-1]
        title = item.get("display_name")
        if not source_id or not title:
            return None

        location = item.get("primary_location") or {}
        venue = (location.get("source") or {}).get("display_name")
        identifiers = dict(item.get("ids") or {})
        identifiers["openalex"] = source_id
        if item.get("doi"):
            identifiers["doi"] = item["doi"]

        urls = {}
        if location.get("landing_page_url"):
            urls["landing"] = location["landing_page_url"]
        if location.get("pdf_url"):
            urls["pdf"] = location["pdf_url"]

        work_type = str(item.get("type") or "").casefold()
        published = item.get("publication_date") or (
            str(item["publication_year"]) if item.get("publication_year") else None
        )
        dates = (
            DateEvidence(preprint_submitted=published)
            if work_type == "preprint"
            else DateEvidence(published_online=published)
        )

        return Record(
            source=self.name,
            source_id=source_id,
            title=title,
            abstract=restore_abstract(item.get("abstract_inverted_index")),
            authors=[
                (authorship.get("author") or {}).get("display_name", "")
                for authorship in item.get("authorships") or []
                if (authorship.get("author") or {}).get("display_name")
            ],
            venue=venue,
            publication_type=item.get("type"),
            language=item.get("language"),
            identifiers=identifiers,
            urls=urls,
            citation_count=item.get("cited_by_count"),
            is_retracted=bool(item.get("is_retracted")),
            dates=dates,
            raw_sha256=record_hash(item),
        )
