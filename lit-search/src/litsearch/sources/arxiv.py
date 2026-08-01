"""arXiv Atom API —— 预印本与顶会技术报告的第一落点。

日期语义：``<published>`` 是 **v1 提交日**，不是正式发表日。一篇 2021 年的预印本
可能 2023 年才发在 TMI 上——因此它落入 ``preprint_submitted``，在合并后会被
正式版的 ``published_online`` 依优先级覆盖。

arXiv 官方要求请求之间间隔 3 秒，限速在 registry 中配置。
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import AsyncIterator

from litsearch.normalize import DateEvidence, Record
from litsearch.query import SourceQuery
from litsearch.sources.base import SourceContext, SourceError, record_hash

ENDPOINT = "https://export.arxiv.org/api/query"
PAGE_SIZE = 100
ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV_NS = "{http://arxiv.org/schemas/atom}"
OPENSEARCH = "{http://a9.com/-/spec/opensearch/1.1/}"


def _text(element: ET.Element | None) -> str:
    return " ".join("".join(element.itertext()).split()) if element is not None else ""


class ArxivSource:
    name = "arxiv"

    def __init__(self) -> None:
        self.last_total: int | None = None

    def _search_query(self, query: SourceQuery, context: SourceContext) -> str:
        window = context.window
        start = window.harvest_start.strftime("%Y%m%d") + "0000"
        end = window.harvest_end.strftime("%Y%m%d") + "2359"
        return f"({query.query}) AND submittedDate:[{start} TO {end}]"

    async def _page(self, query: SourceQuery, context: SourceContext, start: int) -> ET.Element:
        params = {
            "search_query": self._search_query(query, context),
            "start": start,
            "max_results": PAGE_SIZE,
            "sortBy": "submittedDate",
            "sortOrder": "ascending",
        }
        body = await context.client.get_text(
            ENDPOINT, params, source=self.name, pages_fetched=start // PAGE_SIZE
        )
        context.store.write(self.name, query.query_hash, start // PAGE_SIZE + 1, body, "xml")
        try:
            return ET.fromstring(body)
        except ET.ParseError as error:
            raise SourceError(self.name, f"Atom 响应无法解析：{error}") from error

    async def estimate(self, query: SourceQuery, context: SourceContext) -> int | None:
        root = await self._page(query, context, 0)
        total = _text(root.find(f"{OPENSEARCH}totalResults"))
        return int(total) if total.isdigit() else None

    async def fetch(self, query: SourceQuery, context: SourceContext) -> AsyncIterator[Record]:
        start = 0
        total: int | None = None

        while True:
            root = await self._page(query, context, start)
            if total is None:
                raw_total = _text(root.find(f"{OPENSEARCH}totalResults"))
                total = int(raw_total) if raw_total.isdigit() else None
                self.last_total = total

            entries = root.findall(f"{ATOM}entry")
            for entry in entries:
                if record := self._to_record(entry):
                    yield record

            start += PAGE_SIZE
            if not entries or (total is not None and start >= total):
                break

    def _to_record(self, entry: ET.Element) -> Record | None:
        raw_id = _text(entry.find(f"{ATOM}id"))
        title = _text(entry.find(f"{ATOM}title"))
        if not raw_id or not title:
            return None

        arxiv_id = raw_id.rsplit("/abs/", 1)[-1]
        identifiers = {"arxiv": arxiv_id}
        if doi := _text(entry.find(f"{ARXIV_NS}doi")):
            identifiers["doi"] = doi

        urls = {"landing": raw_id.replace("http://", "https://")}
        for link in entry.findall(f"{ATOM}link"):
            if link.get("title") == "pdf" and (href := link.get("href")):
                urls["pdf"] = href.replace("http://", "https://")

        categories = [
            node.get("term", "") for node in entry.findall(f"{ATOM}category") if node.get("term")
        ]

        return Record(
            source=self.name,
            source_id=arxiv_id,
            title=title,
            abstract=_text(entry.find(f"{ATOM}summary")) or None,
            authors=[
                _text(node.find(f"{ATOM}name"))
                for node in entry.findall(f"{ATOM}author")
                if _text(node.find(f"{ATOM}name"))
            ],
            venue=_text(entry.find(f"{ARXIV_NS}journal_ref")) or "arXiv",
            publication_type="preprint",
            identifiers=identifiers,
            urls=urls,
            dates=DateEvidence(preprint_submitted=_text(entry.find(f"{ATOM}published"))),
            raw_sha256=record_hash({"id": arxiv_id, "title": title, "categories": categories}),
        )
