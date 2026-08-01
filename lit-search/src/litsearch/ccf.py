"""CCF 推荐国际学术会议和期刊目录：解析与匹配。

**目录由用户提供，不随仓库分发。** 和 JCR / 中科院分区是同一个槽位——
工具提供解析器与匹配器，数据是你的。

匹配设计：

- **全称匹配走归一化**（去掉所有非字母数字后小写）。PDF 抽取会吃掉词间空格，
  ``IEEETransactionsonMedicalImaging`` 与语料里的
  ``IEEE transactions on medical imaging`` 归一化后完全相同。
- **简称匹配要求词边界且长度 ≥ 3**。``SC`` / ``CC`` / ``DC`` 这类两字母简称
  会在任意刊名里命中，宁可漏也不能错——错配不报错，它给你一个看起来合理的等级。
- **不猜没收录的。** 目录里没有的会议就是"未评级"，不是"低等级"。
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

#: 简称匹配的最短长度。短于此的简称只在**整串完全相等**时才算命中。
MIN_ABBREV_TOKENS = 3

_SECTION_RE = re.compile(r"^中国计算机学会推荐国际学术(期刊|会议)")
_CLASS_RE = re.compile(r"^[一二三]、([ABC])\s*类")
_HEADER_RE = re.compile(r"^序号\s")
_DOMAIN_RE = re.compile(r"^（(.+)）$")
_ROW_RE = re.compile(r"^(\d+)\s")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")

_KIND = {"期刊": "journal", "会议": "conference"}
#: 等级的先后。A 最好。
RANK_ORDER = ("A", "B", "C")


class CcfError(RuntimeError):
    """目录解析失败。**不静默降级**——匹配不上和没有目录是两回事。"""


@dataclass(frozen=True, slots=True)
class CcfEntry:
    """目录里的一条。"""

    kind: str  # "journal" | "conference"
    rank: str  # "A" | "B" | "C"
    full_name: str
    abbrev: str | None = None
    publisher: str | None = None
    url: str | None = None
    domain: str | None = None


def normalize_name(value: str | None) -> str:
    """归一化到只剩小写字母数字。空白、标点、大小写差异全部抹平。"""
    return _NON_ALNUM.sub("", (value or "").lower())


def _merge_wrapped(tokens: Sequence[str]) -> list[str]:
    """把被换行切断的词接回去：以 ``-`` 或 ``/`` 结尾的片段与下一个合并。"""
    merged: list[str] = []
    for token in tokens:
        if merged and (merged[-1].endswith("-") or merged[-1].endswith("/")):
            merged[-1] += token
        else:
            merged.append(token)
    return merged


def _parse_row(
    buffer: Sequence[str], *, kind: str, rank: str, domain: str | None
) -> CcfEntry | None:
    text = re.sub(r"\s+", " ", " ".join(buffer)).strip()
    tokens = _merge_wrapped(text.split(" "))
    if len(tokens) < 3 or not tokens[-1].startswith("http"):
        return None
    url, publisher, rest = tokens[-1], tokens[-2], tokens[1:-2]
    if not rest:
        return None
    # 有简称时它独占第一段且很短；没有简称的条目整段都是全称。
    if len(rest) >= 2 and len(rest[0]) <= 15:
        abbrev, full_name = rest[0], "".join(rest[1:])
    else:
        abbrev, full_name = None, "".join(rest)
    return CcfEntry(
        kind=kind,
        rank=rank,
        full_name=full_name,
        abbrev=abbrev,
        publisher=publisher,
        url=url,
        domain=domain,
    )


def parse_pdf(path: Path) -> list[CcfEntry]:
    """解析 CCF 目录 PDF。"""
    try:
        import pypdf
    except ImportError as error:  # pragma: no cover - 环境问题，不是逻辑分支
        raise CcfError("解析 CCF PDF 需要 pypdf：uv add pypdf") from error

    try:
        reader = pypdf.PdfReader(str(path))
    except Exception as error:
        raise CcfError(f"无法打开 {path}：{error}") from error

    entries: list[CcfEntry] = []
    kind: str | None = None
    rank: str | None = None
    domain: str | None = None
    buffer: list[str] = []

    def flush(
        pending: list[str], current_kind: str | None, current_rank: str | None, area: str | None
    ) -> list[str]:
        """把攒着的行拼成一条，返回清空后的缓冲区。

        显式传参而不是闭包捕获——条目跨页续行时，闭包会悄悄读到已经翻过页的状态。
        """
        if pending and current_kind and current_rank:
            entry = _parse_row(pending, kind=current_kind, rank=current_rank, domain=area)
            if entry:
                entries.append(entry)
        return []

    for page in reader.pages:
        for raw in (page.extract_text() or "").splitlines():
            line = raw.strip()
            if not line:
                continue
            if match := _SECTION_RE.match(line):
                buffer = flush(buffer, kind, rank, domain)
                kind = _KIND[match.group(1)]
                continue
            if match := _CLASS_RE.match(line):
                buffer = flush(buffer, kind, rank, domain)
                rank = match.group(1)
                continue
            if _HEADER_RE.match(line):
                buffer = flush(buffer, kind, rank, domain)
                continue
            if match := _DOMAIN_RE.match(line):
                label = match.group(1)
                if "/" in label and len(label) < 40:
                    domain = label
                    continue
            if _ROW_RE.match(line):
                buffer = flush(buffer, kind, rank, domain)
                buffer.append(line)
            elif buffer:
                buffer.append(line)
        buffer = flush(buffer, kind, rank, domain)

    if not entries:
        raise CcfError(f"{path} 里没解析出任何条目——格式可能不是 CCF 目录")
    return entries


def load_catalog(path: Path) -> list[CcfEntry]:
    """从 ``.pdf`` 或 ``.json`` 载入目录。"""
    if path.suffix.lower() == ".json":
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise CcfError(f"无法读取 {path}：{error}") from error
        return [CcfEntry(**row) for row in payload]
    return parse_pdf(path)


def dump_catalog(entries: Iterable[CcfEntry]) -> str:
    """序列化为 JSON，避免每次重解析 PDF。"""
    return json.dumps(
        [
            {
                "kind": item.kind,
                "rank": item.rank,
                "full_name": item.full_name,
                "abbrev": item.abbrev,
                "publisher": item.publisher,
                "url": item.url,
                "domain": item.domain,
            }
            for item in entries
        ],
        ensure_ascii=False,
        indent=1,
    )


def _better(left: CcfEntry | None, right: CcfEntry) -> CcfEntry:
    """同名多条时取等级更高的那条（跨领域重复收录很常见）。"""
    if left is None:
        return right
    return left if RANK_ORDER.index(left.rank) <= RANK_ORDER.index(right.rank) else right


class CcfMatcher:
    """把语料里的载体名匹配到目录条目。"""

    def __init__(self, entries: Sequence[CcfEntry]) -> None:
        self._entries = list(entries)
        self._by_name: dict[str, CcfEntry] = {}
        self._by_abbrev: dict[str, CcfEntry] = {}
        for entry in entries:
            name = normalize_name(entry.full_name)
            if name:
                self._by_name[name] = _better(self._by_name.get(name), entry)
            abbrev = normalize_name(entry.abbrev)
            if abbrev:
                self._by_abbrev[abbrev] = _better(self._by_abbrev.get(abbrev), entry)

    def __len__(self) -> int:
        return len(self._entries)

    def match(self, *names: str | None) -> CcfEntry | None:
        """依次尝试给定的候选名，返回第一个命中。

        候选名按可信度传入（如：OpenAlex 载体名、语料 venue、论文标题）。
        """
        for name in names:
            if hit := self._match_one(name):
                return hit
        return None

    def _match_one(self, name: str | None) -> CcfEntry | None:
        if not name:
            return None
        normalized = normalize_name(name)
        if not normalized:
            return None
        if hit := self._by_name.get(normalized):
            return hit
        if hit := self._by_abbrev.get(normalized):
            return hit
        return self._match_token(name)

    def _match_token(self, name: str) -> CcfEntry | None:
        """在载体名里找简称。要求词边界 + 长度 ≥ 3。

        ``IEEE ICASSP 2023`` 这类"会议缩写 + 年份"的写法只能靠这条命中；
        而长度门槛挡住 ``SC``/``CC`` 这类会在任意刊名里误中的两字母简称。
        """
        best: CcfEntry | None = None
        for token in re.split(r"[^A-Za-z0-9]+", name):
            if len(token) < MIN_ABBREV_TOKENS:
                continue
            if hit := self._by_abbrev.get(normalize_name(token)):
                best = _better(best, hit)
        return best
