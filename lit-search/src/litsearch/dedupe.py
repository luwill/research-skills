"""跨源去重：标识符传递合并 + 保守的标题模糊配对。

两趟：
1. **标识符趟**：任意两条记录共享 doi/pmid/arxiv/openalex/s2 中任一项即合并（并查集，可传递）。
2. **标题趟**：处理"预印本 ↔ 正式版"这类标识符不相交的情况。必须保守——
   "2D U-Net" 与 "3D U-Net" 的标题相似度高达 97%，靠阈值分不开，
   因此额外要求**含数字的词元集合完全一致**且年份相差不超过 1 年。
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Iterable

from pydantic import BaseModel, Field, model_validator
from rapidfuzz import fuzz

from litsearch.normalize import (
    DateEvidence,
    PartialDate,
    Record,
    WindowStatus,
    classify_window,
    detect_source_date_conflict,
    governing_field,
    resolve_canonical_date,
)
from litsearch.protocol import Window

#: 参与传递合并的标识符，按可信度排序
IDENTIFIER_PRIORITY = ("doi", "pmid", "arxiv", "arxiv_doi", "pmcid", "openalex", "s2")

TITLE_SIMILARITY_THRESHOLD = 95.0
TITLE_BLOCK_PREFIX = 16
MAX_YEAR_GAP = 1

_DATE_FIELDS = ("published_online", "published_print", "preprint_submitted", "source_reported")


def title_key(title: str) -> str:
    """大小写、标点、空白无关的标题键。"""
    normalized = unicodedata.normalize("NFKC", title).casefold()
    return "".join(char for char in normalized if char.isalnum()) or normalized.strip()


def numeric_tokens(title: str) -> frozenset[str]:
    """含数字的词元（2D/3D、v2、2022、ISLES24）——这些通常是语义分水岭，不能被模糊掉。"""
    normalized = unicodedata.normalize("NFKC", title).casefold()
    tokens = re.split(r"[^0-9a-z]+", normalized)
    return frozenset(token for token in tokens if token and any(ch.isdigit() for ch in token))


def dedup_key(record: Record) -> str:
    """一条记录的主键，用于展示与排序；实际合并用的是全部标识符。"""
    for kind in IDENTIFIER_PRIORITY:
        if value := record.identifiers.get(kind):
            return f"{kind}:{value.casefold()}"
    digest = hashlib.sha256(title_key(record.title).encode()).hexdigest()
    return f"title:{digest[:32]}"


def _identifier_keys(record: Record) -> list[str]:
    return [
        f"{kind}:{record.identifiers[kind].casefold()}"
        for kind in IDENTIFIER_PRIORITY
        if record.identifiers.get(kind)
    ]


class _UnionFind:
    def __init__(self, size: int) -> None:
        self._parent = list(range(size))

    def find(self, item: int) -> int:
        while self._parent[item] != item:
            self._parent[item] = self._parent[self._parent[item]]
            item = self._parent[item]
        return item

    def union(self, left: int, right: int) -> None:
        left_root, right_root = self.find(left), self.find(right)
        if left_root != right_root:
            # 始终并到较小下标，使分组代表 = 首次出现的记录
            low, high = sorted((left_root, right_root))
            self._parent[high] = low


class CanonicalRecord(BaseModel):
    """合并后的规范记录。保留全部成员与全部标识符，合并过程可审计、可回溯。"""

    key: str
    title: str
    abstract: str | None = None
    authors: list[str] = Field(default_factory=list)
    venue: str | None = None
    publication_type: str | None = None
    identifiers: dict[str, str] = Field(default_factory=dict)
    urls: dict[str, str] = Field(default_factory=dict)
    citation_count: int | None = None
    referenced_works: list[str] = Field(default_factory=list)
    is_retracted: bool = False
    dates: DateEvidence = Field(default_factory=DateEvidence)
    canonical_date: PartialDate | None = None
    window_status: WindowStatus | None = None
    date_conflict: bool = False
    near_edge: bool = False
    sources: tuple[str, ...] = ()
    found_by: list[str] = Field(default_factory=list)
    #: 每种标识符的完整集合，避免精简落盘后丢失预印本 DOI 等合并成员身份。
    identifier_sets: dict[str, list[str]] = Field(default_factory=dict)
    #: 轻量成员索引用于回溯到 records*.jsonl，不复制成员摘要和引文边。
    member_refs: list[dict[str, object]] = Field(default_factory=list)
    #: 仅在去重计算期间/旧 corpus 读取时保留；新 corpus 落盘排除这一重副本。
    members: list[Record] = Field(default_factory=list, exclude=True)
    #: 人工日期裁定的审计信息；原始日期证据仍保留在 dates/members 中。
    date_adjudication: dict[str, str] | None = None
    #: 合并依据，例如 ["identifier:doi:10.1/a", "title"]
    merge_evidence: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _backfill_compact_identity(self) -> CanonicalRecord:
        if not self.identifier_sets:
            values: dict[str, list[str]] = {}
            for kind, value in self.identifiers.items():
                values.setdefault(kind, []).append(value)
            for member in self.members:
                for kind, value in member.identifiers.items():
                    if value not in values.setdefault(kind, []):
                        values[kind].append(value)
            self.identifier_sets = values
        if not self.member_refs and self.members:
            self.member_refs = [
                {
                    "source": member.source,
                    "source_id": member.source_id,
                    "raw_sha256": member.raw_sha256,
                    "identifiers": member.identifiers,
                }
                for member in self.members
            ]
        return self

    @property
    def all_dois(self) -> set[str]:
        return set(self.identifier_sets.get("doi", []))

    @property
    def needs_human_review(self) -> bool:
        return self.window_status in {WindowStatus.BOUNDARY, WindowStatus.UNDATED}

    @property
    def year(self) -> int | None:
        return self.canonical_date.earliest.year if self.canonical_date else None

    def has_identifier(self, kind: str, value: str) -> bool:
        target = value.casefold()
        return any(item.casefold() == target for item in self.identifier_sets.get(kind, []))


def _merge_dates(members: list[Record]) -> DateEvidence:
    """逐字段取第一个非空值；不同源对同一字段的分歧保留在各自 member 中可查。"""
    merged: dict[str, str | None] = {}
    for field_name in _DATE_FIELDS:
        for member in members:
            if value := member.dates.get(field_name):
                merged[field_name] = value
                break
    return DateEvidence(**merged)


def _pick_publication_type(members: list[Record]) -> str | None:
    """正式发表类型优先于 preprint——否则预印本会把正式版的类型盖掉。"""
    types = [member.publication_type for member in members if member.publication_type]
    for value in types:
        if value.casefold() != "preprint":
            return value
    return types[0] if types else None


def _build_canonical(members: list[Record], evidence: list[str]) -> CanonicalRecord:
    identifiers: dict[str, str] = {}
    identifier_sets: dict[str, list[str]] = {}
    urls: dict[str, str] = {}
    for member in members:
        for kind, value in member.identifiers.items():
            identifiers.setdefault(kind, value)
            if value not in identifier_sets.setdefault(kind, []):
                identifier_sets[kind].append(value)
        for kind, value in member.urls.items():
            urls.setdefault(kind, value)

    abstracts = [member.abstract for member in members if member.abstract]
    citations = [member.citation_count for member in members if member.citation_count is not None]
    authors = max((member.authors for member in members), key=len, default=[])
    references: list[str] = []
    for member in members:
        for work in member.referenced_works:
            if work not in references:
                references.append(work)

    sources: list[str] = []
    for member in members:
        if member.source not in sources:
            sources.append(member.source)

    found_by: list[str] = []
    for member in members:
        for item in member.found_by:
            if item not in found_by:
                found_by.append(item)

    return CanonicalRecord(
        key=dedup_key(members[0]),
        title=members[0].title,
        abstract=max(abstracts, key=len) if abstracts else None,
        authors=list(authors),
        venue=next((member.venue for member in members if member.venue), None),
        publication_type=_pick_publication_type(members),
        identifiers=identifiers,
        urls=urls,
        citation_count=max(citations) if citations else None,
        referenced_works=references,
        is_retracted=any(member.is_retracted for member in members),
        dates=_merge_dates(members),
        sources=tuple(sources),
        found_by=found_by,
        identifier_sets=identifier_sets,
        member_refs=[
            {
                "source": member.source,
                "source_id": member.source_id,
                "raw_sha256": member.raw_sha256,
                "identifiers": member.identifiers,
            }
            for member in members
        ],
        members=list(members),
        merge_evidence=evidence,
    )


def _titles_match(left: Record, right: Record) -> bool:
    """保守的标题配对判定。"""
    if numeric_tokens(left.title) != numeric_tokens(right.title):
        return False

    left_year, right_year = left.year, right.year
    if left_year is not None and right_year is not None:
        if abs(left_year - right_year) > MAX_YEAR_GAP:
            return False

    return fuzz.ratio(title_key(left.title), title_key(right.title)) >= TITLE_SIMILARITY_THRESHOLD


def deduplicate(
    records: Iterable[Record], window: Window, date_priority: list[str]
) -> list[CanonicalRecord]:
    """把多源记录合并为规范记录集合，并重新解析合并后的 canonical_date。"""
    items = list(records)
    if not items:
        return []

    union = _UnionFind(len(items))
    evidence: dict[int, set[str]] = {index: set() for index in range(len(items))}

    # 第一趟：标识符传递合并
    by_identifier: dict[str, int] = {}
    for index, record in enumerate(items):
        for key in _identifier_keys(record):
            if (seen := by_identifier.get(key)) is not None:
                union.union(seen, index)
                evidence[union.find(index)].add(f"identifier:{key}")
            else:
                by_identifier[key] = index

    # 第二趟：标题模糊配对（按标题前缀分块，避免 O(n^2)）
    blocks: dict[str, list[int]] = {}
    for index, record in enumerate(items):
        blocks.setdefault(title_key(record.title)[:TITLE_BLOCK_PREFIX], []).append(index)

    for bucket in blocks.values():
        for position, left_index in enumerate(bucket):
            for right_index in bucket[position + 1 :]:
                if union.find(left_index) == union.find(right_index):
                    continue
                if _titles_match(items[left_index], items[right_index]):
                    union.union(left_index, right_index)
                    evidence[union.find(left_index)].add("title")

    grouped: dict[int, list[int]] = {}
    for index in range(len(items)):
        grouped.setdefault(union.find(index), []).append(index)

    canonical: list[CanonicalRecord] = []
    for root in sorted(grouped):
        members = [items[index] for index in sorted(grouped[root])]
        record = _build_canonical(members, sorted(evidence.get(root, set())))
        record.canonical_date = resolve_canonical_date(record.dates, date_priority)
        record.window_status = classify_window(record.canonical_date, window)
        # 只比较**同一个字段**在各源之间的取值——跨字段分歧由 date_priority 规则解决
        field_name = governing_field(record.dates, date_priority)
        record.date_conflict = bool(field_name) and detect_source_date_conflict(
            (member.dates.get(field_name) for member in members), window
        )
        if record.date_conflict and record.window_status is not WindowStatus.UNDATED:
            record.window_status = WindowStatus.BOUNDARY
        record.near_edge = bool(
            record.canonical_date and window.is_near_edge(record.canonical_date.earliest)
        )
        canonical.append(record)

    return canonical
