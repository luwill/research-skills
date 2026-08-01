"""OpenReview —— ICLR/NeurIPS/MIDL 等的投稿，含**被拒稿**这类真正的灰色文献。

两个实测事实决定了用法：

1. ``/notes?content.venueid=ICLR.cc/2024/Conference`` 返回 **403 Challenge**，
   按会场枚举这条路走不通，只能用 ``/notes/search``；
2. ``/notes/search`` 对多词查询是 **OR** 语义。实测
   ``ischemic stroke lesion segmentation`` 返回 ``count=10000``（就是返回上限），
   而加引号的 ``"ischemic stroke"`` 只返回 210 条，``"stroke lesion segmentation"`` 69 条。

所以必须**逐个加引号的锚点短语**去打，每条检索式的结果集才有界、才翻得完。
把布尔串直接塞进来会静默退化成"一万条噪声里取前几页"——那正是本项目最要避免的
"看起来有结果、其实召回边界失控"。

search 的返回里混着评审意见、公开评论这类 note，它们**没有标题**，必须剔除。
另外索引里还包含 DBLP 镜像记录（``venueid: dblp.org/journals/...``），
那是真论文，保留——DBLP 自己的 API 实测返回 503，这里反而捡回来了。
"""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from litsearch.localfilter import build_matcher
from litsearch.normalize import DateEvidence, Record
from litsearch.query import SourceQuery
from litsearch.sources.base import SourceContext, record_hash

ENDPOINT = "https://api2.openreview.net/notes/search"
PAGE_SIZE = 1000
FORUM_URL = "https://openreview.net/forum?id="
_DOI_RE = re.compile(r"(?i)\bdoi\s*=\s*[{\"']?\s*(10\.\d{4,9}/[^\s,}\"']+)")


def _value(content: dict[str, Any], key: str) -> Any:
    """OpenReview API v2 把每个字段包成 ``{"value": ...}``，v1 是裸值。两种都要吃。"""
    raw = content.get(key)
    if isinstance(raw, dict) and "value" in raw:
        return raw["value"]
    return raw


def _epoch_ms(value: Any) -> str | None:
    """OpenReview 的时间戳是**毫秒**。当秒用会把 2025 年算成 1970 年。"""
    if not isinstance(value, int | float) or value <= 0:
        return None
    return datetime.fromtimestamp(value / 1000, tz=UTC).date().isoformat()


class OpenReviewSource:
    name = "openreview"

    def __init__(self) -> None:
        self.last_total: int | None = None
        self.page_size = PAGE_SIZE

    def _params(self, query: SourceQuery, limit: int, offset: int) -> dict[str, Any]:
        # 引号不能省——见模块头注释
        return {"term": f'"{query.query}"', "limit": limit, "offset": offset}

    async def estimate(self, query: SourceQuery, context: SourceContext) -> int | None:
        payload = await context.client.get_json(
            ENDPOINT, self._params(query, 1, 0), source=self.name
        )
        return payload.get("count")

    async def fetch(self, query: SourceQuery, context: SourceContext) -> AsyncIterator[Record]:
        matcher = build_matcher(context.topic)
        offset = 0
        page = 0

        while True:
            body = await context.client.get_text(
                ENDPOINT,
                self._params(query, self.page_size, offset),
                source=self.name,
                pages_fetched=page,
            )
            page += 1
            context.store.write(self.name, query.query_hash, page, body, "json")

            payload = json.loads(body)
            if page == 1:
                self.last_total = payload.get("count")
            notes = payload.get("notes") or []
            for note in notes:
                if record := self._to_record(note, matcher):
                    yield record

            offset += self.page_size
            total = self.last_total or 0
            # 短页即结束：服务端报的 count 与实际可翻条数并不总是一致
            if len(notes) < self.page_size or offset >= total:
                break

    def _to_record(self, note: dict[str, Any], matcher) -> Record | None:
        content = note.get("content") or {}
        title = _value(content, "title")
        if not title:
            return None  # 评审意见/评论，不是论文

        abstract = _value(content, "abstract") or ""
        if not matcher.matches_all_required(f"{title} {abstract}"):
            return None

        note_id = str(note.get("id") or "")
        identifiers = {"openreview": note_id}
        if match := _DOI_RE.search(str(_value(content, "_bibtex") or "")):
            identifiers["doi"] = match.group(1).rstrip(".,;")

        authors = _value(content, "authors") or []
        return Record(
            source=self.name,
            source_id=note_id,
            title=title,
            abstract=abstract or None,
            authors=[str(item) for item in authors if item],
            venue=_value(content, "venue") or _value(content, "venueid"),
            publication_type="conference-paper",
            identifiers=identifiers,
            urls={"landing": f"{FORUM_URL}{note.get('forum') or note_id}"},
            dates=DateEvidence(
                published_online=_epoch_ms(note.get("pdate")),
                # cdate 是 note 建成时间，语义上等同"投稿"，不能当作发表日期
                preprint_submitted=_epoch_ms(note.get("cdate")),
                source_reported=str(_value(content, "venue") or "") or None,
            ),
            raw_sha256=record_hash({"id": note_id, "title": title}),
        )
