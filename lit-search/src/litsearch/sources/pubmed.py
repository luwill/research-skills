"""PubMed E-utilities —— 召回主干，并提供 MeSH 受控词。

**9,999 条硬上限**：PubMed 对同一个检索式最多只能取回 9,999 条，``usehistory=y`` 也绕不过。
实测 retstart≥9999 会返回

    'retstart' cannot be larger than 9998. For PubMed, ESearch can only retrieve
    the first 9,999 records matching the query.

本课题的 ``condition AND task`` 检索式命中 16,725 条——若不处理就会静默少召回 40%，
而这正是本项目要消灭的失败模式。因此按**发表日期递归二分**，把检索式切成若干个
命中数低于上限的子区间分别取全。若某个单日仍超过上限（极端情况），显式报 partial。

日期语义：``ArticleDate[@DateType="Electronic"]`` 是 online-first 日期，
``Journal/JournalIssue/PubDate`` 是印刷版日期，两者分别落入不同的日期证据字段。
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from litsearch.normalize import DateEvidence, Record
from litsearch.query import SourceQuery
from litsearch.sources.base import SourceContext, SourceError, record_hash

ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
BATCH_SIZE = 200
#: NCBI 硬上限：retstart 不得大于 9998
MAX_RETRIEVABLE = 9998


@dataclass
class _Slice:
    """一个命中数低于硬上限的日期子区间。"""

    start: date
    end: date
    count: int
    web_env: str
    query_key: str
    truncated: bool = False


def _text(element: ET.Element | None) -> str:
    """取节点下的全部文本，含 <i>/<sup> 等内联标签。"""
    return "".join(element.itertext()).strip() if element is not None else ""


def _pubdate(node: ET.Element | None) -> str | None:
    """PubDate 可能是 <Year>+<Month>+<Day>，也可能是自由文本 <MedlineDate>。"""
    if node is None:
        return None
    if medline := _text(node.find("MedlineDate")):
        return medline
    parts = [_text(node.find(tag)) for tag in ("Year", "Month", "Day")]
    return " ".join(part for part in parts if part) or None


def _article_date(article: ET.Element) -> str | None:
    for node in article.findall(".//ArticleDate"):
        if node.get("DateType", "Electronic") == "Electronic":
            parts = [_text(node.find(tag)) for tag in ("Year", "Month", "Day")]
            if joined := "-".join(part for part in parts if part):
                return joined
    return None


class PubMedSource:
    name = "pubmed"

    def __init__(self) -> None:
        self.last_total: int | None = None

    def _common(self, context: SourceContext) -> dict[str, Any]:
        params: dict[str, Any] = {"db": "pubmed", "tool": "litsearch"}
        if context.contact_email:
            params["email"] = context.contact_email
        if key := context.api_keys.get("pubmed"):
            params["api_key"] = key
        return params

    def _search_params(
        self, query: SourceQuery, start: date, end: date, context: SourceContext
    ) -> dict[str, Any]:
        return self._common(context) | {
            "term": query.query,
            "retmode": "json",
            "datetype": "pdat",
            "mindate": start.strftime("%Y/%m/%d"),
            "maxdate": end.strftime("%Y/%m/%d"),
        }

    async def _esearch(
        self, query: SourceQuery, start: date, end: date, context: SourceContext
    ) -> _Slice | None:
        params = self._search_params(query, start, end, context) | {
            "retmax": 0,
            "usehistory": "y",
        }
        payload = await context.client.get_json(ESEARCH, params, source=self.name)
        result = payload.get("esearchresult") or {}
        if errors := result.get("errorlist"):
            raise SourceError(self.name, f"esearch 报错：{errors}")

        count = int(result.get("count") or 0)
        if count == 0:
            return None

        web_env, query_key = result.get("webenv"), result.get("querykey")
        if not web_env or not query_key:
            raise SourceError(self.name, "esearch 未返回 WebEnv/QueryKey，无法分批取全")
        return _Slice(start=start, end=end, count=count, web_env=web_env, query_key=query_key)

    async def estimate(self, query: SourceQuery, context: SourceContext) -> int | None:
        window = context.window
        params = self._search_params(query, window.harvest_start, window.harvest_end, context) | {
            "retmax": 0
        }
        payload = await context.client.get_json(ESEARCH, params, source=self.name)
        count = (payload.get("esearchresult") or {}).get("count")
        return int(count) if count is not None else None

    async def plan_slices(
        self, query: SourceQuery, start: date, end: date, context: SourceContext
    ) -> list[_Slice]:
        """递归二分日期区间，直到每段命中数都低于 9,999 的硬上限。"""
        current = await self._esearch(query, start, end, context)
        if current is None:
            return []
        if current.count <= MAX_RETRIEVABLE:
            return [current]
        if start >= end:
            # 单日仍超上限，无法再切——如实标记截断，不假装取全了
            current.truncated = True
            return [current]

        middle = start + (end - start) // 2
        left = await self.plan_slices(query, start, middle, context)
        right = await self.plan_slices(query, middle + timedelta(days=1), end, context)
        return left + right

    async def fetch(self, query: SourceQuery, context: SourceContext) -> AsyncIterator[Record]:
        window = context.window
        slices = await self.plan_slices(query, window.harvest_start, window.harvest_end, context)
        self.last_total = sum(item.count for item in slices)
        if not slices:
            return

        page = 0
        for item in slices:
            reachable = min(item.count, MAX_RETRIEVABLE + 1)
            for offset in range(0, reachable, BATCH_SIZE):
                fetch_params = self._common(context) | {
                    "retmode": "xml",
                    "rettype": "abstract",
                    "WebEnv": item.web_env,
                    "query_key": item.query_key,
                    "retstart": offset,
                    "retmax": min(BATCH_SIZE, reachable - offset),
                }
                body = await context.client.get_text(
                    EFETCH, fetch_params, source=self.name, pages_fetched=page
                )
                page += 1
                context.store.write(self.name, query.query_hash, page, body, "xml")

                try:
                    root = ET.fromstring(body)
                except ET.ParseError as error:
                    raise SourceError(
                        self.name, f"efetch 返回的 XML 无法解析：{error}", pages_fetched=page
                    ) from error

                for article in root.findall(".//PubmedArticle"):
                    if record := self._to_record(article):
                        yield record

        if truncated := [item for item in slices if item.truncated]:
            # 记录已全部产出，但必须让调用方把这次采集标为 partial
            spans = ", ".join(f"{item.start}~{item.end}({item.count:,})" for item in truncated)
            raise SourceError(
                self.name,
                f"以下日期区间命中数超过 9,999 硬上限且已无法再切分，结果被截断：{spans}",
                pages_fetched=page,
            )

    def _to_record(self, article: ET.Element) -> Record | None:
        pmid = _text(article.find(".//MedlineCitation/PMID"))
        title = _text(article.find(".//Article/ArticleTitle"))
        if not pmid or not title:
            return None

        abstract_parts = []
        for node in article.findall(".//Article/Abstract/AbstractText"):
            label = node.get("Label")
            text = _text(node)
            abstract_parts.append(f"{label}: {text}" if label and text else text)

        authors = []
        for node in article.findall(".//Article/AuthorList/Author"):
            last, fore = _text(node.find("LastName")), _text(node.find("ForeName"))
            collective = _text(node.find("CollectiveName"))
            if name := " ".join(part for part in (fore, last) if part) or collective:
                authors.append(name)

        identifiers: dict[str, str] = {"pmid": pmid}
        # 必须走直接路径。用 ".//ArticleIdList/ArticleId" 会钻进 PubmedData/ReferenceList，
        # 把最后一条**参考文献**的 DOI 当成本文 DOI（实测一篇综述有 156 条参考文献 ID）。
        for node in article.findall("PubmedData/ArticleIdList/ArticleId"):
            kind = (node.get("IdType") or "").lower()
            if kind in {"doi", "pmc", "pmcid"} and (value := _text(node)):
                identifiers["doi" if kind == "doi" else "pmcid"] = value
        if "doi" not in identifiers:
            for node in article.findall("MedlineCitation/Article/ELocationID"):
                if (node.get("EIdType") or "").lower() == "doi" and (value := _text(node)):
                    identifiers["doi"] = value

        # PubMed 的结构化参考文献是免费的后向滚雪球燃料
        references = [
            f"doi:{value.lower()}"
            for node in article.findall('PubmedData/ReferenceList//ArticleId[@IdType="doi"]')
            if (value := _text(node))
        ]

        types = [_text(node) for node in article.findall(".//PublicationTypeList/PublicationType")]
        mesh = [
            _text(node) for node in article.findall(".//MeshHeadingList/MeshHeading/DescriptorName")
        ]

        payload = {
            "pmid": pmid,
            "title": title,
            "identifiers": identifiers,
            "types": types,
            "mesh": mesh,
        }

        return Record(
            source=self.name,
            source_id=pmid,
            title=title,
            abstract=" ".join(part for part in abstract_parts if part) or None,
            authors=authors,
            venue=_text(article.find(".//Article/Journal/Title")) or None,
            publication_type=types[0] if types else None,
            language=_text(article.find(".//Article/Language")) or None,
            identifiers=identifiers,
            urls={"landing": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"},
            referenced_works=references,
            dates=DateEvidence(
                published_online=_article_date(article),
                published_print=_pubdate(article.find(".//Article/Journal/JournalIssue/PubDate")),
            ),
            raw_sha256=record_hash(payload),
        )
