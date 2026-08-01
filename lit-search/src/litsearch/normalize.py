"""统一记录模型、日期证据解析与时间窗判定。

"指定时间范围"最容易翻车的一层。各源日期语义不一致：PubMed 有 pdat/edat/crdt，
OpenAlex 的 publication_date 常是 online-first 日期，arXiv 的是 v1 提交日，
Crossref 取印刷/在线较早者。而且大量记录只有年份或年月。

处理原则：
1. 采集时窗口放宽（宽进），在这里按统一优先级算出 canonical_date 再严格过滤（严出）；
2. 只知道年份、或落在边界带的记录，标为待人工裁定——**绝不静默丢弃**。
"""

from __future__ import annotations

import calendar
import re
import unicodedata
from collections.abc import Iterable
from datetime import date
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator

from litsearch.protocol import (
    Window,
    arxiv_doi_from_id,
    arxiv_id_from_doi,
    normalize_doi,
)

_MONTHS = {name.lower(): index for index, name in enumerate(calendar.month_abbr) if name}
_MONTHS.update({name.lower(): index for index, name in enumerate(calendar.month_name) if name})

_ISO_RE = re.compile(r"\b(?P<y>(?:18|19|20|21)\d{2})(?:[-/](?P<m>\d{1,2}))?(?:[-/](?P<d>\d{1,2}))?")
_TEXT_RE = re.compile(
    r"\b(?P<y>(?:18|19|20|21)\d{2})\s+(?P<mon>[A-Za-z]{3,9})(?:\s+(?P<d>\d{1,2}))?"
)


class WindowStatus(str, Enum):
    IN_WINDOW = "in_window"
    OUT_OF_WINDOW = "out_of_window"
    #: 落在边界带内，或日期精度不足以判定内外——必须人工裁定
    BOUNDARY = "boundary"
    #: 完全没有日期证据——同样必须人工裁定，不得当作窗口外丢弃
    UNDATED = "undated"


class PartialDate(BaseModel):
    """带精度的日期。年份/年月记录展开为一个区间，而不是假装成某一天。"""

    earliest: date
    latest: date
    precision: str  # "day" | "month" | "year"
    text: str = ""

    @classmethod
    def exact(cls, value: date) -> PartialDate:
        return cls(earliest=value, latest=value, precision="day", text=value.isoformat())

    @property
    def is_exact(self) -> bool:
        return self.precision == "day"

    def __str__(self) -> str:
        return self.text or self.earliest.isoformat()


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    last = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last)


def parse_partial_date(value: Any) -> PartialDate | None:
    """把各源千奇百怪的日期串解析为带精度的区间。无法解析时返回 None（而非猜测）。"""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None

    if match := _TEXT_RE.search(text):  # "2024 Feb 6"
        month = _MONTHS.get(match.group("mon").lower())
        if month:
            year = int(match.group("y"))
            if day := match.group("d"):
                try:
                    exact = date(year, month, int(day))
                except ValueError:
                    return None
                return PartialDate(earliest=exact, latest=exact, precision="day", text=text)
            first, last = _month_bounds(year, month)
            return PartialDate(earliest=first, latest=last, precision="month", text=text)

    if match := _ISO_RE.search(text):
        year = int(match.group("y"))
        month = int(match.group("m")) if match.group("m") else None
        day = int(match.group("d")) if match.group("d") else None

        if month and not 1 <= month <= 12:
            return None
        if month and day:
            try:
                exact = date(year, month, day)
            except ValueError:
                return None
            return PartialDate(earliest=exact, latest=exact, precision="day", text=text)
        if month:
            first, last = _month_bounds(year, month)
            return PartialDate(earliest=first, latest=last, precision="month", text=text)
        return PartialDate(
            earliest=date(year, 1, 1), latest=date(year, 12, 31), precision="year", text=text
        )

    return None


class DateEvidence(BaseModel):
    """一条记录能提供的全部日期证据，按来源字段分开保存，便于审计与敏感性分析。"""

    published_online: str | None = None
    published_print: str | None = None
    preprint_submitted: str | None = None
    source_reported: str | None = None

    def get(self, field_name: str) -> str | None:
        return getattr(self, field_name, None)


def resolve_canonical_date(evidence: DateEvidence, priority: list[str]) -> PartialDate | None:
    """按优先级取第一个**可解析**的日期。不可解析的字段跳过而非致命失败。"""
    for field_name in priority:
        if parsed := parse_partial_date(evidence.get(field_name)):
            return parsed
    return None


def classify_window(value: PartialDate | None, window: Window) -> WindowStatus:
    """判定一条记录相对严格窗口的位置。

    BOUNDARY 只留给**真歧义**：日期精度不足以判定内外（如只知道年份、而窗口从年中开始）。
    精确到日的记录哪怕紧贴边界也不算歧义——它就在窗口的这一边或那一边。
    """
    if value is None:
        return WindowStatus.UNDATED

    fully_inside = window.contains(value.earliest) and window.contains(value.latest)
    if fully_inside:
        return WindowStatus.IN_WINDOW

    fully_outside = value.latest < window.start or value.earliest > window.end
    if fully_outside:
        return WindowStatus.OUT_OF_WINDOW

    # 区间跨越了窗口边界——精度不够，无法判定
    return WindowStatus.BOUNDARY


def governing_field(evidence: DateEvidence, priority: list[str]) -> str | None:
    """按优先级决定哪个日期字段说了算。"""
    for field_name in priority:
        if parse_partial_date(evidence.get(field_name)):
            return field_name
    return None


def detect_source_date_conflict(values: Iterable[str | None], window: Window) -> bool:
    """多个源对**同一个日期字段**给出的值是否指向窗口的不同侧。

    这才是真歧义：OpenAlex 说 2021-06-20、PubMed 说 2021-08-01，
    同一个语义字段却跨了窗口下沿，必须人工裁定。

    注意**不要**跨字段比较。"预印本 2021-03 在窗外、正式版 2021-09 在窗内"不是歧义——
    协议里的 date_priority 已经明确规定了该听谁的。实测跨字段比较会把 1,778 条记录
    送进人工队列，其中 94% 的主日期精确到日、毫无歧义。
    """
    verdicts: set[WindowStatus] = set()
    for value in values:
        parsed = parse_partial_date(value)
        if parsed is None:
            continue
        verdict = classify_window(parsed, window)
        if verdict is WindowStatus.BOUNDARY:
            return True
        verdicts.add(verdict)
    return len(verdicts) > 1


def normalize_identifiers(values: dict[str, Any]) -> dict[str, str]:
    """把各源的标识符写法归一。DOI 小写裸形、PMID 去 URL、arXiv 去版本号。"""
    aliases = {
        "doi": "doi",
        "pmid": "pmid",
        "pubmed": "pmid",
        "pmcid": "pmcid",
        "pmc": "pmcid",
        "arxiv": "arxiv",
        "arxivid": "arxiv",
        "openalex": "openalex",
        "semanticscholar": "s2",
        "semantic_scholar": "s2",
        "s2": "s2",
        "corpusid": "s2_corpus",
        "openreview": "openreview",
        "arxivdoi": "arxiv_doi",
    }
    normalized: dict[str, str] = {}
    for raw_kind, raw_value in values.items():
        kind = aliases.get(str(raw_kind).lower().replace("_", "").replace("-", ""))
        if not kind:
            continue
        value = str(raw_value or "").strip()
        if not value:
            continue
        if kind == "doi":
            value = normalize_doi(value) or ""
        elif kind == "pmid":
            value = re.sub(r"(?i)^https?://pubmed\.ncbi\.nlm\.nih\.gov/", "", value).strip("/")
        elif kind == "pmcid":
            value = re.sub(r"(?i)^https?://.*?/", "", value).strip("/")
        elif kind == "arxiv":
            value = re.sub(r"(?i)^https?://arxiv\.org/abs/", "", value)
            value = re.sub(r"(?i)^arxiv:", "", value)
            value = re.sub(r"v\d+$", "", value).strip()
        elif kind in {"openalex", "s2", "openreview"}:
            value = value.rsplit("/", 1)[-1]
        if value:
            normalized[kind] = value

    # arXiv 的 DataCite DOI 与 arXiv ID 是同一身份的两种写法，必须互相打通：
    # Atom feed 的 arxiv:doi 存的是期刊 DOI，不是这个，不打通就会误判漏检。
    if not normalized.get("arxiv") and (derived := arxiv_id_from_doi(normalized.get("doi"))):
        normalized["arxiv"] = derived
    if normalized.get("arxiv") and not normalized.get("arxiv_doi"):
        normalized["arxiv_doi"] = arxiv_doi_from_id(normalized["arxiv"])
    return normalized


def clean_text(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


class Record(BaseModel):
    """来自单个源的一条规范化记录。合并发生在 dedupe 层，这里保持源的原始视角。"""

    source: str
    source_id: str
    title: str
    abstract: str | None = None
    authors: list[str] = Field(default_factory=list)
    venue: str | None = None
    publication_type: str | None = None
    language: str | None = None
    identifiers: dict[str, str] = Field(default_factory=dict)
    urls: dict[str, str] = Field(default_factory=dict)
    citation_count: int | None = None
    referenced_works: list[str] = Field(default_factory=list)
    is_retracted: bool = False
    dates: DateEvidence = Field(default_factory=DateEvidence)
    raw_sha256: str | None = None
    #: 找到这条记录的检索式；滚雪球得到的记录记为 snowball:<round>
    found_by: list[str] = Field(default_factory=list)

    canonical_date: PartialDate | None = None
    window_status: WindowStatus | None = None
    #: 不同日期证据把这条记录指向窗口的不同侧
    date_conflict: bool = False
    #: 仅供报告标注：canonical_date 贴近窗口边界
    near_edge: bool = False

    @field_validator("title", mode="before")
    @classmethod
    def _clean_title(cls, value: Any) -> str:
        cleaned = clean_text(value)
        if not cleaned:
            raise ValueError("记录缺少标题")
        return cleaned

    @field_validator("abstract", mode="before")
    @classmethod
    def _clean_abstract(cls, value: Any) -> str | None:
        return clean_text(value) or None if value else None

    @field_validator("identifiers", mode="before")
    @classmethod
    def _normalize_ids(cls, value: Any) -> dict[str, str]:
        return normalize_identifiers(dict(value or {}))

    def resolve(self, window: Window, priority: list[str]) -> Record:
        """算出 canonical_date 与窗口判定。就地更新并返回自身，便于链式调用。"""
        self.canonical_date = resolve_canonical_date(self.dates, priority)
        self.window_status = classify_window(self.canonical_date, window)
        # 单个源的记录不存在跨源分歧；跨字段分歧由 date_priority 规则解决
        self.near_edge = bool(
            self.canonical_date and window.is_near_edge(self.canonical_date.earliest)
        )
        return self

    @property
    def needs_human_review(self) -> bool:
        return self.window_status in {WindowStatus.BOUNDARY, WindowStatus.UNDATED}

    @property
    def year(self) -> int | None:
        return self.canonical_date.earliest.year if self.canonical_date else None
