"""本地概念过滤器——给没有布尔检索能力的源兜底。

主干四源（PubMed/OpenAlex/Europe PMC/arXiv）都能把概念块的 AND/OR 交给服务端。
阶段 3 的三个源都不能：

- **CVF** 根本没有检索接口，只有按会议年份的完整标题列表；
- **OpenReview** 的 ``/notes/search`` 对多词查询是 **OR** 语义——实测
  ``ischemic stroke lesion segmentation`` 返回 ``count=10000``（上限），
  而单个加引号短语 ``"ischemic stroke"`` 只返回 210 条；
- **Zenodo** 只有一个单框检索。

因此这些源必须：用**锚点块的短语**逐条去检索（保证每个结果集有界、可翻完），
再在本地对**全部必需块**做 AND。两步都由本模块提供。

刻意**不**把 MeSH 词纳入本地匹配：MeSH 是给已建立索引的库用的受控词，
把它当自由文本正则会悄悄放宽概念边界（本课题的 ``Stroke`` 一词就会命中
CVPR 的"笔触"论文）。受控词只在支持它的源上使用。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from litsearch.protocol import Topic

#: 术语内部的空格与连字符视为等价——各源对 "non-contrast CT" 的写法并不一致
_SEPARATOR = r"[\s\-‐-―]+"


def _term_pattern(term: str) -> str:
    """精确术语：词边界包裹，内部分隔符宽松。"""
    parts = [re.escape(part) for part in re.split(_SEPARATOR, term.strip()) if part]
    return r"(?<!\w)" + _SEPARATOR.join(parts) + r"(?!\w)"


def _wildcard_pattern(wildcard: str) -> str:
    """通配符 ``infarct*``：只在词内展开，不跨词。"""
    stem = wildcard.rstrip("*").strip()
    parts = [re.escape(part) for part in re.split(_SEPARATOR, stem) if part]
    return r"(?<!\w)" + _SEPARATOR.join(parts) + r"\w*"


@dataclass(frozen=True)
class BlockMatcher:
    name: str
    required: bool
    #: (原始写法, 编译后的模式)，保留原始写法以便报告"命中了哪个词"
    patterns: tuple[tuple[str, re.Pattern[str]], ...]
    phrases: tuple[str, ...]

    def hits(self, text: str) -> list[str]:
        return [term for term, pattern in self.patterns if pattern.search(text)]

    def matches(self, text: str) -> bool:
        return any(pattern.search(text) for _, pattern in self.patterns)


@dataclass(frozen=True)
class ConceptMatcher:
    """把课题的概念块编译成可对任意文本求值的匹配器。"""

    blocks: tuple[BlockMatcher, ...]
    anchor: str

    @property
    def required_blocks(self) -> tuple[BlockMatcher, ...]:
        return tuple(block for block in self.blocks if block.required)

    def hits(self, text: str) -> dict[str, list[str]]:
        """每个块命中了哪些词。空块也保留键，便于直接落盘成证据。"""
        return {block.name: block.hits(text) for block in self.blocks}

    def matches_all_required(self, text: str) -> bool:
        return all(block.matches(text) for block in self.required_blocks)

    def missing_required(self, text: str) -> list[str]:
        return [block.name for block in self.required_blocks if not block.matches(text)]

    def matches_any_required(self, text: str) -> bool:
        """较松的门槛：只有标题可用时（CVF），命中任一必需块就值得去取摘要。

        取回摘要后再用 ``matches_all_required`` 严格判定。宁可多取几百个页面，
        也不能因为标题里没写全概念而漏掉一篇。
        """
        return any(block.matches(text) for block in self.required_blocks)

    def reason(self, text: str) -> str:
        missing = self.missing_required(text)
        return f"缺少必需概念块：{', '.join(missing)}" if missing else ""

    def anchor_phrases(self) -> list[str]:
        """锚点块的短语，逐条作为独立检索式发给源。

        只用锚点块，是因为任务块的词太泛：实测 OpenReview 上 ``"segmentation"``
        单独一个词就撞上 10,000 条的返回上限，翻不完也就谈不上召回边界。
        """
        return list(next(block.phrases for block in self.blocks if block.name == self.anchor))


def build_matcher(topic: Topic, *, anchor: str | None = None) -> ConceptMatcher:
    """把课题协议编译成本地匹配器。"""
    blocks: list[BlockMatcher] = []
    for name, block in topic.concepts.items():
        patterns = [(term, re.compile(_term_pattern(term), re.I)) for term in block.terms]
        patterns += [(card, re.compile(_wildcard_pattern(card), re.I)) for card in block.wildcards]
        blocks.append(
            BlockMatcher(
                name=name,
                required=block.required,
                patterns=tuple(patterns),
                phrases=tuple(block.terms),
            )
        )

    required = [block.name for block in blocks if block.required]
    if not required:
        raise ValueError(
            "课题没有任何 required 概念块，无法为无布尔检索能力的源确定召回边界；"
            "请在 topic.yaml 中至少把一个概念块标为 required: true"
        )

    resolved = anchor or required[0]
    if resolved not in {block.name for block in blocks}:
        raise ValueError(f"锚点块 {resolved!r} 不存在于 concepts 中")
    if not next(block.phrases for block in blocks if block.name == resolved):
        raise ValueError(f"锚点块 {resolved!r} 没有 terms，无法生成锚点检索式")

    return ConceptMatcher(blocks=tuple(blocks), anchor=resolved)
