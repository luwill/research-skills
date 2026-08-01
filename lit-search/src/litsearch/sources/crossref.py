"""Crossref 会议录整卷补全 —— MICCAI / LNCS。

Crossref **不**作召回边界：实测 ``query.bibliographic`` 对本课题返回 23 万条模糊
排序结果，``query.container-title="Medical Image Computing..."`` 返回 39 万条且
排在最前的是 SPIE 的钢管缺陷检测。它擅长的是精确定向。

MICCAI 的两个实测陷阱：

- 它在 Crossref 里的 type 是 **book-chapter**（收录在 LNCS 丛书下），
  按 ``type:proceedings-article`` 过滤一篇都拿不到；
- ``filter=isbn:`` 必须传**去掉连字符**的 ISBN。``isbn:978-3-031-16443-9``
  静默返回 0 条，``isbn:9783031164439`` 返回 70 条——这种"静默返回 0"最危险。

关键杠杆：LNCS 的 DOI 后缀里就嵌着卷 ISBN——``10.1007/978-3-031-16443-9_1``
→ ``9783031164439``。于是语料里**任何一篇** MICCAI 论文都能解锁它所在的整卷，
把同卷兄弟篇一次补齐。这是引文滚雪球之外的另一条闭包路径，
而且完全不消耗 OpenAlex 配额。
"""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator, Iterable
from typing import Any

from litsearch.normalize import DateEvidence, Record
from litsearch.protocol import normalize_doi
from litsearch.query import SourceQuery
from litsearch.sources.base import SourceContext, record_hash

ENDPOINT = "https://api.crossref.org/works"
ROWS = 100
SELECT = (
    "DOI,title,author,container-title,ISBN,published,published-online,"
    "published-print,type,abstract,page,link"
)

#: LNCS 的 DOI：10.<前缀>/<带连字符的 ISBN-13>_<章号>
_LNCS_DOI_RE = re.compile(r"^10\.\d{4,9}/(?P<isbn>97[89](?:-\d+)+)_\d+$")


def isbn_from_doi(doi: str | None) -> str | None:
    """从 LNCS 的 DOI 反解本卷 ISBN-13（去连字符）。不是 LNCS DOI 则返回 None。"""
    normalized = normalize_doi(doi)
    if not normalized:
        return None
    match = _LNCS_DOI_RE.match(normalized)
    if not match:
        return None
    # 连字符必须去掉，否则 Crossref 静默返回 0 条
    return match.group("isbn").replace("-", "")


def discover_volumes(dois: Iterable[str | None]) -> list[str]:
    """从语料的 DOI 里找出所有值得整卷补全的 LNCS 卷，按首次出现顺序去重。"""
    found: list[str] = []
    for doi in dois:
        isbn = isbn_from_doi(doi)
        if isbn and isbn not in found:
            found.append(isbn)
    return found


def _date_parts(value: Any) -> str | None:
    parts = (value or {}).get("date-parts") or []
    if not parts or not parts[0]:
        return None
    # 只给到年就只写年——补成 1 月 1 日会凭空造出并不存在的精度
    return "-".join(
        f"{int(item):02d}" if index else str(int(item))
        for index, item in enumerate(parts[0])
        if item is not None
    )


class CrossrefVolumeSource:
    name = "crossref"

    def __init__(self) -> None:
        self.last_total: int | None = None

    def _params(self, isbn: str, context: SourceContext, cursor: str) -> dict[str, Any]:
        params: dict[str, Any] = {
            "filter": f"isbn:{isbn}",
            "rows": ROWS,
            "cursor": cursor,
            "select": SELECT,
        }
        if context.contact_email:
            params["mailto"] = context.contact_email
        return params

    async def estimate(self, query: SourceQuery, context: SourceContext) -> int | None:
        payload = await context.client.get_json(
            ENDPOINT, self._params(query.query, context, "*") | {"rows": 0}, source=self.name
        )
        return (payload.get("message") or {}).get("total-results")

    async def fetch(self, query: SourceQuery, context: SourceContext) -> AsyncIterator[Record]:
        cursor = "*"
        page = 0

        while cursor:
            body = await context.client.get_text(
                ENDPOINT,
                self._params(query.query, context, cursor),
                source=self.name,
                pages_fetched=page,
            )
            page += 1
            context.store.write(self.name, query.query_hash, page, body, "json")

            message = json.loads(body).get("message") or {}
            if page == 1:
                self.last_total = message.get("total-results")

            items = message.get("items") or []
            for item in items:
                if record := self._to_record(item):
                    yield record

            # 整卷全取，**不**在这里按概念块过滤：拿同卷兄弟篇正是这一步的目的，
            # 该不该纳入是筛选阶段的判断。
            if not items:
                break
            cursor = message.get("next-cursor")

    def _to_record(self, item: dict[str, Any]) -> Record | None:
        titles = item.get("title") or []
        doi = item.get("DOI")
        if not titles or not doi:
            return None

        containers = item.get("container-title") or []
        # container-title 是 ['Lecture Notes in Computer Science', 'MICCAI 2022']——
        # 取第一个只会得到毫无信息量的丛书名
        venue = containers[-1] if containers else None

        links = {entry.get("URL"): entry for entry in item.get("link") or [] if entry.get("URL")}

        return Record(
            source=self.name,
            source_id=str(doi),
            title=titles[0],
            abstract=item.get("abstract"),
            authors=[
                " ".join(part for part in (person.get("given"), person.get("family")) if part)
                for person in item.get("author") or []
                if person.get("family")
            ],
            venue=venue,
            publication_type=item.get("type"),
            identifiers={"doi": doi},
            urls={"tdm": next(iter(links), "")} if links else {},
            dates=DateEvidence(
                published_online=_date_parts(item.get("published-online")),
                published_print=_date_parts(item.get("published-print")),
                # Crossref 的 `published` 是"已知最早发表日期"，并不区分在线/印刷，
                # 因此放在优先级最低的一栏，不冒充任何一种确切语义
                source_reported=_date_parts(item.get("published")),
            ),
            raw_sha256=record_hash({"doi": doi, "title": titles[0]}),
        )
