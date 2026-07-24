"""Markdown/citation/reference parsing helpers — pure, side-effect-free readers.

Part of the mir_audit package (split from the original audit_manuscript.py).
"""

from __future__ import annotations

import re

from pathlib import Path
from typing import Iterable

from .constants import *  # noqa: F401,F403
from .model import *  # noqa: F401,F403


def line_excerpt(line: str, limit: int = 180) -> str:
    compact = " ".join(line.strip().split())
    return compact if len(compact) <= limit else compact[: limit - 3] + "..."


def strip_heading_number(title: str) -> str:
    return re.sub(
        r"^\s*(?:(?:\d+(?:\.\d+)*[.)]?)|(?:[一二三四五六七八九十]+[、.]))\s*",
        "",
        title,
    ).strip()


def parse_heading(line: str) -> tuple[int, str] | None:
    match = HEADING_RE.match(line)
    if not match:
        return None
    return len(match.group(1)), match.group(2).strip()


def visible_lines(text: str) -> list[SourceLine]:
    """Replace fenced-code content with blank lines while preserving line numbers."""

    result: list[SourceLine] = []
    fence_char: str | None = None
    fence_length = 0
    for number, raw in enumerate(text.splitlines(), start=1):
        match = FENCE_RE.match(raw)
        if fence_char is None and match:
            marker = match.group(1)
            fence_char = marker[0]
            fence_length = len(marker)
            result.append(SourceLine(number, ""))
            continue
        if fence_char is not None:
            closing = re.match(
                rf"^\s{{0,3}}{re.escape(fence_char)}{{{fence_length},}}\s*$", raw
            )
            if closing:
                fence_char = None
                fence_length = 0
            result.append(SourceLine(number, ""))
            continue
        result.append(SourceLine(number, raw))
    return result


def heading_key(line: SourceLine) -> str | None:
    heading = parse_heading(line.text)
    title = heading[1] if heading else line.text.strip().rstrip(":：")
    normalized = strip_heading_number(title).strip().casefold()
    return normalized or None


def is_reference_heading(line: SourceLine) -> bool:
    return heading_key(line) in REFERENCE_TITLES


def split_body_and_refs(
    lines: list[SourceLine],
) -> tuple[list[SourceLine], list[SourceLine], bool]:
    for index, line in enumerate(lines):
        if is_reference_heading(line):
            return lines[:index], lines[index + 1 :], True
    return lines, [], False


def parse_references(ref_lines: list[SourceLine]) -> ReferenceSet:
    entries: dict[str, str] = {}
    entry_lines: dict[str, int] = {}
    findings: list[Finding] = []
    current_id: str | None = None
    current_line = 0
    current_parts: list[str] = []

    def flush() -> None:
        nonlocal current_id, current_line, current_parts
        if current_id is None:
            return
        entry = " ".join(part.strip() for part in current_parts if part.strip()).strip()
        if not entry:
            findings.append(
                Finding(
                    "high",
                    "malformed_reference",
                    current_line,
                    f"Reference {current_id} has no bibliographic content.",
                )
            )
        if current_id in entries:
            findings.append(
                Finding(
                    "high",
                    "duplicate_reference_identifier",
                    current_line,
                    f"Reference identifier {current_id} is repeated; the first entry is retained.",
                    line_excerpt(entry),
                )
            )
        else:
            entries[current_id] = entry
            entry_lines[current_id] = current_line
        current_id = None
        current_line = 0
        current_parts = []

    for source in ref_lines:
        if not source.text.strip():
            continue
        match = REF_ENTRY_RE.match(source.text)
        if match:
            flush()
            identifier = match.group("bracket_num") or match.group("plain_num") or match.group("citekey")
            if identifier and identifier.isdigit():
                identifier = str(int(identifier))
            current_id = identifier
            current_line = source.number
            current_parts = [match.group("entry")]
            continue
        if re.match(r"^\s*(?:[\[［【]\s*(?:\d+|@)|\d+\s*[.)])", source.text):
            flush()
            findings.append(
                Finding(
                    "medium",
                    "malformed_reference",
                    source.number,
                    "Reference-like line uses an unsupported or incomplete identifier format.",
                    line_excerpt(source.text),
                )
            )
            continue
        if current_id is not None and parse_heading(source.text) is None:
            current_parts.append(source.text)
    flush()
    return ReferenceSet(entries, entry_lines, findings)


def parse_project_bibliography(project_dir: Path | None) -> ReferenceSet:
    """Parse complete, balanced BibTeX entries from the canonical bibliography."""

    if project_dir is None:
        return ReferenceSet({}, {}, [])
    path = project_dir / "references.bib"
    if path.is_symlink():
        return ReferenceSet(
            {},
            {},
            [Finding("critical", "not_ready", 0, "references.bib must not be a symlink")],
        )
    if not path.is_file():
        return ReferenceSet({}, {}, [])
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return ReferenceSet(
            {},
            {},
            [Finding("critical", "not_ready", 0, f"references.bib is unreadable: {exc}")],
        )
    # A full-line percent comment cannot introduce an entry. Preserve newlines so
    # line numbers in diagnostics remain meaningful.
    cleaned = "\n".join(
        "" if line.lstrip().startswith("%") else line for line in text.splitlines()
    )
    entries: dict[str, str] = {}
    entry_lines: dict[str, int] = {}
    findings: list[Finding] = []
    cursor = 0
    start_re = re.compile(
        r"@(?P<kind>[A-Za-z]+)\s*(?P<open>[{(])\s*(?P<key>[^,\s{}()]+)\s*,",
        flags=re.I,
    )

    def balanced_end(start: int, opener: str) -> int | None:
        closer = "}" if opener == "{" else ")"
        depth = 0
        brace_depth = 0
        in_quote = False
        escaped = False
        for index in range(start, len(cleaned)):
            char = cleaned[index]
            if escaped:
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char == '"':
                in_quote = not in_quote
                continue
            if in_quote:
                continue
            if opener == "(":
                if char == "{":
                    brace_depth += 1
                    continue
                if char == "}" and brace_depth:
                    brace_depth -= 1
                    continue
                if brace_depth:
                    continue
            if char == opener:
                depth += 1
            elif char == closer:
                depth -= 1
                if depth == 0:
                    return index + 1
        return None

    while True:
        at = cleaned.find("@", cursor)
        if at < 0:
            break
        directive = re.match(
            r"@(?P<kind>comment|preamble|string)\s*(?P<open>[{(])",
            cleaned[at:],
            flags=re.I,
        )
        if directive:
            opener_index = at + directive.start("open")
            end = balanced_end(opener_index, directive.group("open"))
            line = cleaned.count("\n", 0, at) + 1
            if end is None:
                findings.append(
                    Finding(
                        "critical",
                        "malformed_bibliography_entry",
                        line,
                        f"BibTeX @{directive.group('kind')} directive is truncated or unbalanced.",
                    )
                )
                break
            cursor = end
            continue
        match = start_re.match(cleaned, at)
        line = cleaned.count("\n", 0, at) + 1
        if not match:
            findings.append(
                Finding(
                    "critical",
                    "malformed_bibliography_entry",
                    line,
                    "BibTeX entry start is malformed or lacks a citekey and comma.",
                    line_excerpt(cleaned[at : cleaned.find("\n", at) if "\n" in cleaned[at:] else len(cleaned)]),
                )
            )
            cursor = at + 1
            continue
        opener_index = match.start("open")
        end = balanced_end(opener_index, match.group("open"))
        if end is None:
            findings.append(
                Finding(
                    "critical",
                    "malformed_bibliography_entry",
                    line,
                    f"BibTeX entry @{match.group('kind')}{{{match.group('key')}}} is truncated or unbalanced.",
                )
            )
            break
        entry = cleaned[at:end]
        cursor = end
        identifier = f"@{match.group('key')}"
        if identifier in entries:
            findings.append(
                Finding(
                    "critical",
                    "duplicate_reference_identifier",
                    line,
                    f"BibTeX citekey {identifier} is repeated; the first entry is retained.",
                )
            )
        else:
            entries[identifier] = entry
            entry_lines[identifier] = line
    return ReferenceSet(entries, entry_lines, findings)


def merge_references(inline: ReferenceSet, external: ReferenceSet) -> ReferenceSet:
    entries = dict(inline.entries)
    entry_lines = dict(inline.entry_lines)
    findings = [*inline.findings, *external.findings]
    for identifier, entry in external.entries.items():
        if identifier in entries:
            findings.append(
                Finding(
                    "low",
                    "duplicate_reference_identifier",
                    entry_lines.get(identifier, 0),
                    f"Reference {identifier} appears in both the manuscript and references.bib.",
                )
            )
            continue
        entries[identifier] = entry
        entry_lines[identifier] = 0
    return ReferenceSet(entries, entry_lines, findings)


def parse_numeric_group(content: str) -> tuple[list[str], str | None]:
    normalized = content.replace("–", "-").replace("—", "-").replace("，", ",").replace("；", ";")
    parts = re.split(r"\s*[,;]\s*", normalized)
    if not parts or any(not part for part in parts):
        return [], "empty item in numeric citation group"
    identifiers: list[str] = []
    for part in parts:
        if part.isdigit():
            value = int(part)
            if value <= 0:
                return [], "citation numbers must be positive"
            identifiers.append(str(value))
            continue
        range_match = re.fullmatch(r"(\d+)\s*-\s*(\d+)", part)
        if not range_match:
            return [], f"unsupported numeric citation token: {part}"
        start, end = map(int, range_match.groups())
        if start <= 0 or end < start:
            return [], f"invalid citation range: {part}"
        if end - start > 1000:
            return [], f"citation range is unreasonably large: {part}"
        identifiers.extend(str(value) for value in range(start, end + 1))
    return identifiers, None


def parse_citations(body_lines: list[SourceLine]) -> tuple[list[Citation], list[Finding]]:
    citations: list[Citation] = []
    findings: list[Finding] = []
    for source in body_lines:
        text = INLINE_CODE_RE.sub("", source.text)
        bracket_spans: list[tuple[int, int]] = []
        for match in BRACKET_RE.finditer(text):
            bracket_spans.append(match.span())
            if match.start() > 0 and text[match.start() - 1] == "!":
                continue
            if match.end() < len(text) and text[match.end()] == "(":
                continue
            content = match.group(1).strip()
            # Pandoc permits arbitrary bracket prefixes/suffixes and locators:
            # [e.g., @smith2024, p. 4; see also @jones2025].  Extract every
            # citekey instead of requiring the content to start with ``@``.
            pandoc_tokens = re.findall(
                r"(?<![\w@])(@[^\s,;:.!?。！？；，()\[\]［］【】]+)", content
            )
            if pandoc_tokens:
                citations.extend(
                    Citation(token, source.number, match.group(0))
                    for token in dict.fromkeys(pandoc_tokens)
                )
                continue
            if content and content[0].isdigit():
                if re.match(
                    r"^\d+(?:\.\d+)?\s*(?:%|％|percent\b|%?\s*CI\b|confidence\s+interval\b)",
                    content,
                    flags=re.I,
                ):
                    continue
                identifiers, error = parse_numeric_group(content)
                if error:
                    findings.append(
                        Finding(
                            "medium",
                            "malformed_citation",
                            source.number,
                            f"Malformed numeric citation [{content}]: {error}.",
                            line_excerpt(source.text),
                        )
                    )
                    continue
                citations.extend(Citation(identifier, source.number, match.group(0)) for identifier in identifiers)
        # Common numbered styles also use parentheses. Restrict this to pure
        # positive integer lists/ranges below 1000 so years and section numbers
        # are not treated as citations.
        for match in PAREN_NUMERIC_CITATION_RE.finditer(text):
            content = match.group(1)
            identifiers, error = parse_numeric_group(content)
            if error or any(int(identifier) >= 1000 for identifier in identifiers):
                continue
            citations.extend(
                Citation(identifier, source.number, match.group(0))
                for identifier in identifiers
            )
        # Pandoc also permits textual citations such as @smith2024 outside a
        # bracketed group. Avoid double-counting keys inside brackets.
        for match in re.finditer(r"(?<![\w@])(@[^\s,;:.!?。！？；，()\[\]［］【】]+)", text):
            if any(start <= match.start() < end for start, end in bracket_spans):
                continue
            citations.append(Citation(match.group(1), source.number, match.group(0)))
    return citations, findings


def is_markdown_table_line(line: str) -> bool:
    stripped = line.strip()
    return "|" in stripped and not stripped.startswith(">")


def extract_title_and_abstract(body_lines: list[SourceLine]) -> tuple[str, str]:
    title = ""
    for source in body_lines:
        heading = parse_heading(source.text)
        if heading and heading[0] == 1:
            title = heading[1]
            break
        if source.text.strip() and not title:
            title = source.text.strip()
            break

    abstract_parts: list[str] = []
    collecting = False
    abstract_level = 0
    for source in body_lines:
        heading = parse_heading(source.text)
        if heading:
            level, heading_title = heading
            key = strip_heading_number(heading_title).casefold()
            if key in {"abstract", "摘要"}:
                collecting = True
                abstract_level = level
                continue
            if collecting and level <= abstract_level:
                break
        elif collecting and source.text.strip():
            abstract_parts.append(source.text.strip())
    return title, " ".join(abstract_parts)


def phrase_is_negated(text: str, start: int, end: int) -> bool:
    prefix = text[max(0, start - 60) : start].casefold()
    suffix = text[end : min(len(text), end + 60)].casefold()
    return bool(
        re.search(
            r"(?:\bno\b|\bwithout\b|\bnot\b|\bneither\b|rather\s+than|"
            r"did\s+not|was\s+not|is\s+not)\b[^.!?。！？]*$",
            prefix,
        )
        or re.search(r"^(?:\s+\w+){0,5}\s+(?:was\s+not|were\s+not|is\s+not|not\s+performed|not\s+conducted)\b", suffix)
        or re.search(r"(?:并非|不是|未进行|不进行|未作|不作|无)\s*$", prefix)
        or re.search(r"^.{0,20}(?:未进行|不进行|未实施|不实施)", suffix)
    )


def contains_positive_phrase(text: str, patterns: Iterable[str]) -> bool:
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.I):
            if not phrase_is_negated(text, match.start(), match.end()):
                return True
    return False


def infer_route(body_lines: list[SourceLine]) -> tuple[str, str]:
    title, abstract = extract_title_and_abstract(body_lines)
    title_abstract = f"{title}\n{abstract}"
    route_patterns = (
        ("scoping", (r"\bscoping\s+review\b", r"范围性?综述")),
        ("systematic", (r"\bsystematic(?:\s+literature)?\s+review\b", r"系统性?综述")),
        ("method-survey", (r"\bmethod(?:ological|s)?\s+(?:survey|review)\b", r"(?:方法|技术)综述")),
        ("narrative", (r"\bnarrative\s+review\b", r"(?:叙述性|叙事)综述")),
    )
    for route, patterns in route_patterns:
        if contains_positive_phrase(title_abstract, patterns):
            return route, "title_or_abstract"
    return "narrative", "auto_default"


def find_section(
    lines: list[SourceLine], aliases: set[str]
) -> tuple[int, int, int] | None:
    for index, source in enumerate(lines):
        heading = parse_heading(source.text)
        if not heading:
            continue
        level, title = heading
        key = strip_heading_number(title).casefold()
        if key in aliases:
            end = len(lines)
            for next_index in range(index + 1, len(lines)):
                next_heading = parse_heading(lines[next_index].text)
                if next_heading and next_heading[0] <= level:
                    end = next_index
                    break
            return index, end, level
    return None


def heading_has_content(lines: list[SourceLine], heading_index: int, level: int) -> bool:
    for index in range(heading_index + 1, len(lines)):
        heading = parse_heading(lines[index].text)
        if heading and heading[0] <= level:
            break
        text = lines[index].text.strip()
        if text and not parse_heading(text) and len(PLACEHOLDER_RE.sub("", text).strip()) >= 8:
            return True
    return False
