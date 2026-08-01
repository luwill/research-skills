"""概念块 → 各源查询串。

各源的字段语法差异全部收敛在这一层：PubMed 用 ``[tiab]``/``[Mesh]`` 且支持通配符，
OpenAlex 用裸短语，Europe PMC 用 ``TITLE_ABS:``，arXiv 用 ``abs:`` 且不支持通配符。
生成的每一条查询串都原样落盘到 ``search_strategies.md``，供他人复现。

阶段 3 的三个源根本不在这个"布尔方言"的谱系里，各自另立一种检索式形态：

- **短语式**（OpenReview / 灰色文献）：这些源的多词查询是 **OR** 语义，
  把布尔串塞进去会静默返回上万条噪声。因此改为**逐个加引号的锚点短语**，
  每条检索式各自有界、各自可翻完，任务块留给本地 AND（见 ``localfilter``）。
- **枚举式**（CVF）：根本没有检索接口，只能按会议年份把整届论文列表拉下来。

三种形态都走同一个 ``SourceQuery``，因此 manifest、原始响应落盘、续跑
这些机制对它们一视同仁。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from litsearch.localfilter import build_matcher
from litsearch.protocol import ConceptBlock, Topic, Window

QUERY_HASH_LENGTH = 16

#: 只有单框检索、且多词为 OR 语义的源——必须逐个短语打
PHRASE_SOURCES = frozenset({"openreview", "grey"})
#: 没有检索接口、只能整体枚举的源
ENUMERATION_SOURCES = frozenset({"cvf"})


@dataclass(frozen=True)
class SourceQuery:
    """一条可直接发给某个源的检索式。"""

    source: str
    query: str
    kind: str  # "crossproduct" | "known_item"
    blocks: tuple[str, ...] = ()
    label: str = ""
    query_hash: str = field(default="", compare=False)

    def __post_init__(self) -> None:
        if not self.query_hash:
            digest = hashlib.sha256(
                "\x1f".join([self.source, self.kind, ",".join(self.blocks), self.query]).encode()
            ).hexdigest()
            object.__setattr__(self, "query_hash", digest[:QUERY_HASH_LENGTH])


def _quote(term: str) -> str:
    """含空格的短语必须加引号，否则会被拆成隐式 AND/OR。"""
    return f'"{term}"' if " " in term or "-" in term else term


def _phrase(term: str) -> str:
    """始终加引号的形式，用于字段限定语法。"""
    return f'"{term}"'


def _render_pubmed(block: ConceptBlock, limit: int) -> list[str]:
    parts = [f"{_phrase(term)}[tiab]" for term in block.terms[:limit]]
    parts += [f"{_phrase(term)}[Mesh]" for term in block.mesh]
    # 通配符不能加引号，PubMed 会把带引号的当作精确短语从而失效
    parts += [f"{term}[tiab]" for term in block.wildcards]
    return parts


def _render_openalex(block: ConceptBlock, limit: int) -> list[str]:
    # OpenAlex 的 search 不支持受控词与通配符，只保留自由词
    return [_quote(term) for term in block.terms[:limit]]


def _render_europepmc(block: ConceptBlock, limit: int) -> list[str]:
    parts = [f"TITLE_ABS:{_phrase(term)}" for term in block.terms[:limit]]
    parts += [f"MESH:{_phrase(term)}" for term in block.mesh]
    return parts


def _render_arxiv(block: ConceptBlock, limit: int) -> list[str]:
    # arXiv 无受控词，且 Atom API 不支持通配符——原样传入会静默返回空结果
    return [f"abs:{_phrase(term)}" for term in block.terms[:limit]]


def _render_plain(block: ConceptBlock, limit: int) -> list[str]:
    """无布尔检索能力的源（CVF/OpenReview/灰色文献）：给出裸短语，由本地过滤兜底。"""
    return [_quote(term) for term in block.terms[:limit]]


_RENDERERS = {
    "pubmed": _render_pubmed,
    "openalex": _render_openalex,
    "europepmc": _render_europepmc,
    "arxiv": _render_arxiv,
    "semantic_scholar": _render_plain,
    "openreview": _render_plain,
    "cvf": _render_plain,
    "grey": _render_plain,
}


def render_block(block: ConceptBlock, source: str, limit: int) -> str:
    """把一个概念块渲染为目标源方言下的 OR 组。"""
    renderer = _RENDERERS.get(source, _render_plain)
    parts = renderer(block, limit)
    if not parts:
        raise ValueError(f"概念块在 {source} 方言下渲染为空；检查 terms/mesh/wildcards")
    return "(" + " OR ".join(parts) + ")"


def render_known_item(phrase: str, source: str) -> str:
    """已知项检索：直接按短语打，不参与概念块交叉。"""
    if source == "pubmed":
        return f"{_phrase(phrase)}[tiab]"
    if source == "europepmc":
        return f"TITLE_ABS:{_phrase(phrase)}"
    if source == "arxiv":
        return f"all:{_phrase(phrase)}"
    return _phrase(phrase)


def conference_years(window: Window, venues: list[str]) -> list[str]:
    """采集窗口触及的每个会议年份，形如 ``CVPR2024``。

    用**宽进**窗口而不是严格窗口：CVPR 在 6 月开、NeurIPS 在 12 月开，
    按严格窗口取整年会把边界那届整个漏掉。不存在的会议年份（ICCV 只在奇数年办）
    由源自己按 404 忽略。
    """
    years = range(window.harvest_start.year, window.harvest_end.year + 1)
    return [f"{venue}{year}" for venue in venues for year in years]


def _phrase_queries(topic: Topic, source: str) -> list[SourceQuery]:
    matcher = build_matcher(topic)
    phrases = [(phrase, "phrase") for phrase in matcher.anchor_phrases()]
    phrases += [(phrase, "known_item") for phrase in topic.known_items]
    return [
        SourceQuery(source=source, query=phrase, kind=kind, label=phrase)
        for phrase, kind in phrases
    ]


def _enumeration_queries(topic: Topic, source: str) -> list[SourceQuery]:
    venues = topic.sources[source].venues
    if not venues:
        raise ValueError(
            f"源 {source} 已启用但未配置 venues；枚举式源不知道该枚举什么，"
            f"请在 topic.yaml 的 sources.{source}.venues 中列出会议"
        )
    return [
        SourceQuery(source=source, query=item, kind="enumeration", label=item)
        for item in conference_years(topic.window, venues)
    ]


def effective_combinations(topic: Topic, *, include_subsumed: bool = False) -> list[list[str]]:
    """去掉被更宽组合完全包含的组合。

    ``[condition, task, modality]`` 的结果是 ``[condition, task]`` 的**真子集**——
    在完整翻页的前提下，跑它对召回没有任何增量，只是把配额和时间乘以 N。
    （实测 OpenAlex 匿名配额仅 1000 信用点/天、每次请求 10 点，这个浪费是致命的。）

    只有当某个源会截断结果时，窄组合才有"挖得更深"的价值——
    那种情况请显式传 ``include_subsumed=True``。
    """
    combinations = [list(item) for item in topic.query_plan.combinations]
    if include_subsumed:
        return combinations

    kept: list[list[str]] = []
    for combination in combinations:
        blocks = set(combination)
        if any(set(other) < blocks for other in combinations):
            continue  # 存在更宽的组合，本组合是其真子集
        kept.append(combination)
    return kept


def build_queries(topic: Topic, *, include_subsumed: bool = False) -> list[SourceQuery]:
    """为课题的每个召回源生成完整的检索式集合。"""
    limit = topic.query_plan.max_terms_per_block
    queries: list[SourceQuery] = []
    combinations = effective_combinations(topic, include_subsumed=include_subsumed)

    for source in topic.recall_sources():
        if source in ENUMERATION_SOURCES:
            queries.extend(_enumeration_queries(topic, source))
            continue
        if source in PHRASE_SOURCES:
            queries.extend(_phrase_queries(topic, source))
            continue

        for combination in combinations:
            rendered = [render_block(topic.concepts[name], source, limit) for name in combination]
            queries.append(
                SourceQuery(
                    source=source,
                    query=" AND ".join(rendered),
                    kind="crossproduct",
                    blocks=tuple(combination),
                    label="+".join(combination),
                )
            )

        for phrase in topic.known_items:
            queries.append(
                SourceQuery(
                    source=source,
                    query=render_known_item(phrase, source),
                    kind="known_item",
                    label=phrase,
                )
            )

    return queries


def strategies_markdown(topic: Topic, queries: list[SourceQuery]) -> str:
    """把检索策略导出为可复现的 Markdown（对齐系统评价的 strategies/ 契约）。"""
    lines = [
        f"# 检索策略 — {topic.title} (`{topic.id}`)",
        "",
        f"- 严格窗口：{topic.window.start} ~ {topic.window.end}",
        f"- 采集窗口（宽进）：{topic.window.harvest_start} ~ {topic.window.harvest_end}",
        f"- 每块最多术语数：{topic.query_plan.max_terms_per_block}",
        f"- 召回源：{', '.join(topic.recall_sources()) or '（无）'}",
        "",
    ]
    for source in topic.recall_sources():
        lines.append(f"## {source}")
        lines.append("")
        for query in (item for item in queries if item.source == source):
            lines.append(f"### `{query.query_hash}` — {query.kind} / {query.label}")
            lines.append("")
            lines.append("```")
            lines.append(query.query)
            lines.append("```")
            lines.append("")
    return "\n".join(lines)
