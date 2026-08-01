"""课题协议：加载、校验、冻结。

协议先于检索冻结，避免事后调参制造选择偏倚。每次 run 记录协议文件的 SHA-256，
使任何一份检索结果都能追溯到确切的协议版本。
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

DEFAULT_HARVEST_MARGIN_DAYS = 365
DEFAULT_NEAR_EDGE_DAYS = 180
DEFAULT_MAX_TERMS_PER_BLOCK = 16

DATE_PRIORITY_VALUES = (
    "published_online",
    "published_print",
    "preprint_submitted",
    "source_reported",
)


class ProtocolError(ValueError):
    """课题协议无效。"""


def _dedupe_preserving_order(values: list[str]) -> list[str]:
    """大小写不敏感去重，保留首次出现的原始大小写。"""
    seen: set[str] = set()
    result: list[str] = []
    for raw in values:
        value = unicodedata.normalize("NFKC", str(raw)).strip()
        if not value:
            continue
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


#: arXiv 为每篇论文分配的 DataCite DOI，形如 10.48550/arXiv.2206.06694
ARXIV_DOI_RE = re.compile(r"(?i)^10\.48550/arxiv\.(?P<id>.+)$")


def arxiv_id_from_doi(doi: str | None) -> str | None:
    """从 arXiv 的 DataCite DOI 反解 arXiv ID；不是这种 DOI 则返回 None。"""
    if not doi:
        return None
    match = ARXIV_DOI_RE.match(doi.strip())
    return re.sub(r"v\d+$", "", match.group("id")) if match else None


def arxiv_doi_from_id(arxiv_id: str | None) -> str | None:
    return f"10.48550/arxiv.{arxiv_id.lower()}" if arxiv_id else None


def normalize_doi(value: str | None) -> str | None:
    """把各种 DOI 写法归一到裸 DOI 小写形式。"""
    if not value:
        return None
    text = str(value).strip()
    text = re.sub(r"(?i)^https?://(?:dx\.)?doi\.org/", "", text)
    text = re.sub(r"(?i)^doi:\s*", "", text)
    return text.strip().lower() or None


class ProtocolModel(BaseModel):
    """协议模型基类。

    ``extra="forbid"``：topic.yaml 里的未知键必须报错。配置驱动的工具里，
    一个拼错的键名被静默忽略，等于让整套设置无声失效。
    """

    model_config = ConfigDict(extra="forbid")


class Window(ProtocolModel):
    """检索时间窗。

    ``start``/``end`` 是严格窗口，决定最终纳入；``harvest_start``/``harvest_end``
    是放宽后的采集窗口，用于抵消各源日期语义差异（online-first、预印本、印刷版）。
    """

    start: date
    end: date
    harvest_margin_days: int = Field(default=DEFAULT_HARVEST_MARGIN_DAYS, ge=0)
    #: 仅用于报告中的"贴近边界"一栏，**不**决定是否进人工队列。
    #: 实测：按 ±180 天盲标会把 45% 的记录送进人工队列，其中 96% 是精确到日、
    #: 根本不存在歧义的记录——那样的队列没人会看，等于没有把关。
    near_edge_days: int = Field(default=DEFAULT_NEAR_EDGE_DAYS, ge=0)
    date_priority: list[str] = Field(default_factory=lambda: list(DATE_PRIORITY_VALUES))

    @model_validator(mode="after")
    def _check(self) -> Window:
        if self.end < self.start:
            raise ValueError("window.end 必须不早于 window.start")
        unknown = [item for item in self.date_priority if item not in DATE_PRIORITY_VALUES]
        if unknown:
            raise ValueError(
                f"window.date_priority 含未知取值 {unknown}；可选：{list(DATE_PRIORITY_VALUES)}"
            )
        if not self.date_priority:
            raise ValueError("window.date_priority 不能为空")
        return self

    @property
    def harvest_start(self) -> date:
        return self.start - timedelta(days=self.harvest_margin_days)

    @property
    def harvest_end(self) -> date:
        return self.end + timedelta(days=self.harvest_margin_days)

    def contains(self, value: date) -> bool:
        """严格窗口的闭区间判定。"""
        return self.start <= value <= self.end

    def is_near_edge(self, value: date) -> bool:
        """是否贴近窗口任一边界（仅供报告标注，不影响纳排与人工队列）。"""
        if self.near_edge_days <= 0:
            return False
        return (
            abs((value - self.start).days) <= self.near_edge_days
            or abs((value - self.end).days) <= self.near_edge_days
        )


class ConceptBlock(ProtocolModel):
    """一个概念块，渲染为查询中的一个 OR 组。"""

    required: bool = False
    terms: list[str] = Field(default_factory=list)
    mesh: list[str] = Field(default_factory=list)
    wildcards: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _dedupe(self) -> ConceptBlock:
        self.terms = _dedupe_preserving_order(self.terms)
        self.mesh = _dedupe_preserving_order(self.mesh)
        self.wildcards = _dedupe_preserving_order(self.wildcards)
        return self

    @property
    def is_empty(self) -> bool:
        return not (self.terms or self.mesh or self.wildcards)


class QueryPlan(ProtocolModel):
    combinations: list[list[str]]
    max_terms_per_block: int = Field(default=DEFAULT_MAX_TERMS_PER_BLOCK, ge=1)

    @model_validator(mode="after")
    def _check(self) -> QueryPlan:
        if not self.combinations:
            raise ValueError("query_plan.combinations 不能为空")
        return self


class Criterion(ProtocolModel):
    id: str
    text: str


class Criteria(ProtocolModel):
    include: list[Criterion] = Field(default_factory=list)
    exclude: list[Criterion] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check(self) -> Criteria:
        if not self.include:
            raise ValueError("criteria.include 至少需要一条纳入标准")
        ids = [item.id for item in (*self.include, *self.exclude)]
        duplicates = {value for value in ids if ids.count(value) > 1}
        if duplicates:
            raise ValueError(f"criteria 存在重复 id：{sorted(duplicates)}")
        return self


class SeedItem(ProtocolModel):
    """金标准种子或窗口外对照，至少携带一个标识符。"""

    doi: str | None = None
    arxiv: str | None = None
    pmid: str | None = None
    openalex: str | None = None
    note: str | None = None

    @model_validator(mode="after")
    def _check(self) -> SeedItem:
        self.doi = normalize_doi(self.doi)
        if self.arxiv:
            self.arxiv = re.sub(r"v\d+$", "", re.sub(r"(?i)^arxiv:", "", self.arxiv.strip()))
        if not self.arxiv and (derived := arxiv_id_from_doi(self.doi)):
            self.arxiv = derived
        if not any((self.doi, self.arxiv, self.pmid, self.openalex)):
            raise ValueError("每个种子至少需要一个 identifier（doi / arxiv / pmid / openalex）")
        return self

    @property
    def identifiers(self) -> dict[str, str]:
        pairs = {
            "doi": self.doi,
            "arxiv": self.arxiv,
            "pmid": self.pmid,
            "openalex": self.openalex,
        }
        return {key: value for key, value in pairs.items() if value}


class PublicationTypes(ProtocolModel):
    include: list[str] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=list)


class SourceConfig(ProtocolModel):
    enabled: bool = False
    #: ``recall`` 计入召回边界；``enrich`` 只做元数据补全，不生成检索查询。
    role: str = "recall"
    categories: list[str] = Field(default_factory=list)
    venues: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check(self) -> SourceConfig:
        if self.role not in {"recall", "enrich"}:
            raise ValueError(f"sources.role 只能是 recall 或 enrich，收到 {self.role!r}")
        return self


class SnowballConfig(ProtocolModel):
    enabled: bool = True
    directions: list[str] = Field(default_factory=lambda: ["backward", "forward"])
    max_rounds: int = Field(default=6, ge=1)
    saturation_consecutive_rounds: int = Field(default=2, ge=1)
    saturation_new_inclusion_rate: float = Field(default=0.05, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _check(self) -> SnowballConfig:
        unknown = [item for item in self.directions if item not in {"backward", "forward"}]
        if unknown:
            raise ValueError(f"snowball.directions 含未知取值 {unknown}")
        if not self.directions:
            raise ValueError("snowball.directions 不能为空")
        return self


class ScreeningConfig(ProtocolModel):
    channels: int = Field(default=2, ge=1, le=4)
    confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    batch_size: int = Field(default=25, ge=1)


class Topic(ProtocolModel):
    id: str
    title: str
    description: str | None = None
    window: Window
    languages: list[str] = Field(default_factory=lambda: ["en"])
    publication_types: PublicationTypes = Field(default_factory=PublicationTypes)
    concepts: dict[str, ConceptBlock]
    known_items: list[str] = Field(default_factory=list)
    query_plan: QueryPlan
    criteria: Criteria
    gold_set: list[SeedItem] = Field(default_factory=list)
    out_of_window_controls: list[SeedItem] = Field(default_factory=list)
    sources: dict[str, SourceConfig] = Field(default_factory=dict)
    snowball: SnowballConfig = Field(default_factory=SnowballConfig)
    screening: ScreeningConfig = Field(default_factory=ScreeningConfig)

    @model_validator(mode="after")
    def _check(self) -> Topic:
        if not self.concepts:
            raise ValueError("concepts 不能为空")

        for name, block in self.concepts.items():
            if block.is_empty:
                raise ValueError(f"概念块 {name} 为空：至少需要一个 term / mesh / wildcard")

        required = {name for name, block in self.concepts.items() if block.required}
        for index, combination in enumerate(self.query_plan.combinations):
            unknown = [name for name in combination if name not in self.concepts]
            if unknown:
                raise ValueError(f"query_plan.combinations[{index}] 引用了未定义的概念块 {unknown}")
            if len(set(combination)) != len(combination):
                raise ValueError(f"query_plan.combinations[{index}] 存在重复概念块")
            missing = sorted(required - set(combination))
            if missing:
                raise ValueError(
                    f"query_plan.combinations[{index}] 缺少必需概念块 {missing}；"
                    "required 块必须出现在每个组合中，否则召回边界不受控"
                )

        self.known_items = _dedupe_preserving_order(self.known_items)
        return self

    def effective_terms(self, block_name: str) -> list[str]:
        """按 max_terms_per_block 截断后的术语表。"""
        return self.concepts[block_name].terms[: self.query_plan.max_terms_per_block]

    def enabled_sources(self) -> set[str]:
        return {name for name, config in self.sources.items() if config.enabled}

    def recall_sources(self) -> list[str]:
        """参与召回的源（按声明顺序），排除 role=enrich。"""
        return [
            name
            for name, config in self.sources.items()
            if config.enabled and config.role == "recall"
        ]


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as error:
        raise ProtocolError(f"无法读取课题协议 {path}: {error}") from error

    try:
        payload = yaml.safe_load(raw)
    except yaml.YAMLError as error:
        raise ProtocolError(f"课题协议 {path} 不是合法 YAML: {error}") from error

    if not isinstance(payload, dict):
        raise ProtocolError(f"课题协议 {path} 顶层必须是映射，实际为 {type(payload).__name__}")
    return payload


def load_topic(path: str | Path) -> Topic:
    """加载并校验课题协议。任何问题都以 ProtocolError 抛出。"""
    topic_path = Path(path)
    payload = _read_yaml(topic_path)
    try:
        return Topic.model_validate(payload)
    except ValidationError as error:
        details = "; ".join(
            f"{'.'.join(str(part) for part in item['loc'])}: {item['msg']}"
            for item in error.errors()
        )
        raise ProtocolError(f"课题协议 {topic_path} 校验失败 -> {details}") from error


def freeze_topic(path: str | Path) -> str:
    """返回协议**文件字节**的 SHA-256，用于把一次 run 钉死到确切的文件版本。"""
    topic_path = Path(path)
    try:
        return hashlib.sha256(topic_path.read_bytes()).hexdigest()
    except OSError as error:
        raise ProtocolError(f"无法冻结课题协议 {topic_path}: {error}") from error


def protocol_fingerprint(topic: Topic) -> str:
    """返回协议**语义内容**的 SHA-256。

    判断"两批采集是否属于同一次系统检索"必须按语义，不能按字节：给 topic.yaml
    加一行注释不改变任何检索行为，却会让字节哈希变掉，从而把整次 run 的续接能力
    废掉——那是在惩罚写注释的人。反过来改一个术语必须被拦下。

    映射的键排序后再哈希（概念块在 YAML 里换个书写顺序不改变检索空间），
    列表顺序原样保留（术语顺序是语义的：``max_terms_per_block`` 按顺序截断）。
    """
    payload = json.dumps(
        topic.model_dump(mode="json"), sort_keys=True, ensure_ascii=False, default=str
    )
    return hashlib.sha256(payload.encode()).hexdigest()
