"""Europe PMC —— 补预印本与 PMC 全文覆盖。

翻页用 cursorMark。``firstPublicationDate`` 是"首次以任何形式发表"的日期，
语义上最接近 online-first，因此落入 ``published_online``。
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from litsearch.normalize import DateEvidence, Record
from litsearch.query import SourceQuery
from litsearch.sources.base import SourceContext, SourceError, record_hash

ENDPOINT = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
PAGE_SIZE = 500


class EuropePMCSource:
    name = "europepmc"

    def __init__(self) -> None:
        self.last_total: int | None = None

    def _query(self, query: SourceQuery, context: SourceContext) -> str:
        window = context.window
        span = f"[{window.harvest_start.isoformat()} TO {window.harvest_end.isoformat()}]"
        return f"({query.query}) AND (FIRST_PDATE:{span})"

    async def estimate(self, query: SourceQuery, context: SourceContext) -> int | None:
        params = {
            "query": self._query(query, context),
            "format": "json",
            "pageSize": 1,
            "resultType": "idlist",
        }
        payload = await context.client.get_json(ENDPOINT, params, source=self.name)
        return payload.get("hitCount")

    async def fetch(self, query: SourceQuery, context: SourceContext) -> AsyncIterator[Record]:
        cursor = "*"
        page = 0
        seen_cursors: set[str] = set()

        while cursor and cursor not in seen_cursors:
            seen_cursors.add(cursor)
            params = {
                "query": self._query(query, context),
                "format": "json",
                "pageSize": PAGE_SIZE,
                "resultType": "core",
                "cursorMark": cursor,
            }
            body = await context.client.get_text(
                ENDPOINT, params, source=self.name, pages_fetched=page
            )
            page += 1
            context.store.write(self.name, query.query_hash, page, body, "json")

            try:
                payload = json.loads(body)
            except json.JSONDecodeError as error:
                raise SourceError(
                    self.name, f"响应不是合法 JSON：{error}", pages_fetched=page
                ) from error

            if page == 1:
                self.last_total = payload.get("hitCount")
            results = (payload.get("resultList") or {}).get("result") or []
            for item in results:
                if record := self._to_record(item):
                    yield record

            if not results:
                break
            cursor = payload.get("nextCursorMark")

    def _to_record(self, item: dict[str, Any]) -> Record | None:
        source_id = str(item.get("id") or "").strip()
        title = item.get("title")
        if not source_id or not title:
            return None

        identifiers = {
            key: value
            for key, value in {
                "doi": item.get("doi"),
                "pmid": item.get("pmid"),
                "pmcid": item.get("pmcid"),
            }.items()
            if value
        }

        authors = [
            author.get("fullName", "")
            for author in ((item.get("authorList") or {}).get("author") or [])
            if author.get("fullName")
        ]
        types = (item.get("pubTypeList") or {}).get("pubType") or []
        journal = ((item.get("journalInfo") or {}).get("journal") or {}).get("title")

        urls = {}
        for link in (item.get("fullTextUrlList") or {}).get("fullTextUrl") or []:
            if url := link.get("url"):
                urls.setdefault("pdf" if link.get("documentStyle") == "pdf" else "landing", url)

        return Record(
            source=self.name,
            source_id=source_id,
            title=title,
            abstract=item.get("abstractText"),
            authors=authors,
            venue=journal or item.get("bookOrReportDetails", {}).get("publisher"),
            publication_type=types[0] if types else None,
            language=item.get("language"),
            identifiers=identifiers,
            urls=urls,
            citation_count=item.get("citedByCount"),
            dates=DateEvidence(
                published_online=item.get("firstPublicationDate"),
                source_reported=str(item["pubYear"]) if item.get("pubYear") else None,
            ),
            raw_sha256=record_hash(item),
        )
