"""引文滚雪球：从已纳入研究出发，做双向引文闭包。

纯关键词检索必然漏掉用词不同的论文——"core infarct estimation"、
"tissue-at-risk mapping"、"follow-up lesion prediction" 都不会命中
"segmentation"，但它们就是同一件事。滚雪球是补上这一块的唯一办法。

**种子集是这一步的全部。** 实测本课题：从 13,920 条**未筛选**的窗口内记录出发，
后向候选是 **134,317** 条；而这 13,920 条里最终会被纳入的大约只有几百条。
换句话说绝大多数候选来自"本来就该被排除"的论文的参考文献列表——
滚雪球从"补齐遗漏"变成了"把噪声放大一个数量级"，还要为此付十倍的筛选费用。

所以默认种子是 ``included``（筛选纳入），这也是系统综述的规范做法。
没跑筛选就想滚雪球，本模块会直接报错，而不是替你选一个看起来能跑的默认值。

## 为什么全部走 Europe PMC

OpenAlex 匿名配额约每天 100 次请求，而种子有上万条，``cites:`` 逐条打不可行
（它支持 ``|`` 批量，每批 50，配了 API key 才划算）。Europe PMC 免费、无需 key，
且两个方向都能**批量**：

- 后向：燃料在阶段 2 就已经免费拿到了——PubMed 的 ReferenceList 存进了
  ``referenced_works``（全语料 6,840 条记录、207,914 条引文边），一次请求都不用发；
  只有取新候选的元数据才需要请求（``DOI:"a" OR DOI:"b" …``，每批 100）。
- 前向：``CITES:<pmid>_MED`` 也能 OR 批量（实测每批 200 个种子仍可用）。

批量的上限是 **URL 长度**，不是条数：实测 200 个 DOI（6,907 字符）返回
``HTTP 414 Request-URI Too Large``，100 个（3,475 字符）正常。因此按字符预算切批。
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum

from litsearch.dedupe import CanonicalRecord
from litsearch.localfilter import build_matcher
from litsearch.normalize import WindowStatus
from litsearch.protocol import SnowballConfig, Topic, normalize_doi
from litsearch.query import SourceQuery
from litsearch.screen import Decision, MergedDecision

#: Europe PMC 的检索式走 GET，上限是 URL 长度而非条数。实测 6,907 字符 → HTTP 414。
MAX_QUERY_CHARS = 3800
MAX_TERMS_PER_BATCH = 100
FORWARD_TEMPLATE = "CITES:{}_MED"
BACKWARD_TEMPLATE = 'DOI:"{}"'
JOINER = " OR "


class SeedMode(str, Enum):
    #: 筛选纳入的研究——系统综述的规范做法，默认值
    INCLUDED = "included"
    #: 金标准种子。用于验证滚雪球链路本身是否通
    GOLD = "gold"
    #: 标题+摘要在本地满足全部必需块。没有筛选结果时的确定性替代
    MATCHED = "matched"
    #: 全部窗口内记录。召回上限，但候选量与筛选成本会爆炸
    IN_WINDOW = "in_window"


def select_seeds(
    records: list[CanonicalRecord],
    topic: Topic,
    mode: SeedMode,
    *,
    decisions: dict[str, MergedDecision] | None = None,
) -> list[CanonicalRecord]:
    """挑出滚雪球的起点。任何模式下都只用窗口内的记录。"""
    in_window = [item for item in records if item.window_status is WindowStatus.IN_WINDOW]

    if mode is SeedMode.IN_WINDOW:
        return in_window

    if mode is SeedMode.INCLUDED:
        if not decisions:
            raise ValueError(
                "种子模式 included 需要先跑筛选（lit screen）。"
                "没有筛选结果就从全部候选滚雪球，会把噪声放大一个数量级——"
                "实测本课题后向候选会从数百条膨胀到 13 万条。"
                "若确实要那样做，请显式指定 --seeds in-window。"
            )
        return [
            item
            for item in in_window
            if (verdict := decisions.get(item.key))
            and verdict.decision is Decision.INCLUDE
            and not verdict.needs_human
        ]

    if mode is SeedMode.GOLD:
        wanted = {
            (kind, value) for seed in topic.gold_set for kind, value in seed.identifiers.items()
        }
        return [
            item
            for item in in_window
            if any((kind, value) in wanted for kind, value in item.identifiers.items())
        ]

    matcher = build_matcher(topic)
    return [
        item
        for item in in_window
        if matcher.matches_all_required(f"{item.title} {item.abstract or ''}")
    ]


def backward_candidates(records: Iterable[CanonicalRecord], known: set[str]) -> list[str]:
    """种子引用过、但还不在语料里的 DOI，按首次出现顺序去重。

    PubMed 把参考文献存成 ``doi:10.1007/...``——前缀不剥掉就永远匹配不上语料，
    于是每一条参考文献都会被当成"新候选"，静默把候选量翻好几倍。
    """
    found: list[str] = []
    seen: set[str] = set()
    for record in records:
        for raw in record.referenced_works:
            text = str(raw)
            if text.lower().startswith("doi:"):
                text = text[4:]
            doi = normalize_doi(text)
            if not doi or not doi.startswith("10."):
                continue
            if doi in known or doi in seen:
                continue
            seen.add(doi)
            found.append(doi)
    return found


def forward_seed_ids(records: Iterable[CanonicalRecord]) -> list[str]:
    """能做前向引文的种子。Europe PMC 的 ``CITES:`` 语法要求 ``<pmid>_MED``。"""
    found: list[str] = []
    seen: set[str] = set()
    for record in records:
        pmid = record.identifiers.get("pmid")
        if pmid and pmid not in seen:
            seen.add(pmid)
            found.append(pmid)
    return found


def batch_terms(
    terms: list[str],
    template: str,
    *,
    max_chars: int = MAX_QUERY_CHARS,
    max_items: int = MAX_TERMS_PER_BATCH,
) -> list[list[str]]:
    """按**字符预算**切批，因为上限是 URL 长度而不是条数。"""
    batches: list[list[str]] = []
    current: list[str] = []
    length = 0
    for term in terms:
        rendered = len(template.format(term))
        addition = rendered + (len(JOINER) if current else 0)
        if current and (length + addition > max_chars or len(current) >= max_items):
            batches.append(current)
            current, length = [], 0
            addition = rendered
        current.append(term)
        length += addition
    if current:
        batches.append(current)
    return batches


def _queries(
    terms: list[str], template: str, direction: str, round_number: int
) -> list[SourceQuery]:
    return [
        SourceQuery(
            source="snowball",
            query=JOINER.join(template.format(term) for term in batch),
            kind="snowball",
            label=f"r{round_number}-{direction}-{index:03d}",
        )
        for index, batch in enumerate(batch_terms(terms, template))
    ]


def build_snowball_queries(
    seeds: list[CanonicalRecord], known: set[str], round_number: int
) -> list[SourceQuery]:
    """把一轮滚雪球展开成 Europe PMC 检索式。

    两个方向都是普通检索式，因此可以直接交给既有的采集机制——
    翻页、原始响应落盘、manifest 结局记录、分阶段并入全部复用，不必另建一套。
    """
    return [
        *_queries(forward_seed_ids(seeds), FORWARD_TEMPLATE, "forward", round_number),
        *_queries(backward_candidates(seeds, known), BACKWARD_TEMPLATE, "backward", round_number),
    ]


@dataclass(frozen=True)
class RoundStat:
    number: int
    seeds: int
    candidates: int
    new_records: int
    new_in_window: int
    corpus_before: int

    @property
    def new_rate(self) -> float:
        """本轮新增占轮前语料的比例。分母为 0 时视为 0，不制造无穷大。"""
        return self.new_in_window / self.corpus_before if self.corpus_before else 0.0


def is_saturated(history: list[RoundStat], config: SnowballConfig) -> bool:
    """饱和判据：连续 N 轮新增占比低于阈值。

    用"连续 N 轮"而不是"某一轮"，是因为单轮产出会抖动——一轮偶然很少
    并不说明挖到底了。一轮丰收会把连续计数清零。
    """
    needed = config.saturation_consecutive_rounds
    if len(history) < needed:
        return False
    tail = history[-needed:]
    return all(item.new_rate < config.saturation_new_inclusion_rate for item in tail)
