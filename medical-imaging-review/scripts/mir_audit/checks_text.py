"""Manuscript-level static checks (headings, citations, equations, route claims).

Part of the mir_audit package (split from the original audit_manuscript.py).
"""

from __future__ import annotations

import re

from collections import defaultdict
from typing import Any, Iterable

from .constants import *  # noqa: F401,F403
from .model import *  # noqa: F401,F403
from .parsing import *  # noqa: F401,F403


def scan_citation_reconciliation(
    body_lines: list[SourceLine], references: ReferenceSet
) -> tuple[list[Citation], list[Finding]]:
    citations, findings = parse_citations(body_lines)
    for citation in citations:
        if citation.identifier not in references.entries:
            findings.append(
                Finding(
                    "critical",
                    "missing_reference",
                    citation.line,
                    f"Body citation {citation.raw} resolves to {citation.identifier}, which has no bibliography entry.",
                )
            )
    cited = {citation.identifier for citation in citations}
    unused = sorted(set(references.entries) - cited)
    if unused:
        suffix = " ..." if len(unused) > 20 else ""
        findings.append(
            Finding(
                "low",
                "uncited_reference",
                0,
                f"{len(unused)} bibliography entries are not cited in the body: {unused[:20]}{suffix}",
            )
        )
    return citations, findings


def scan_placeholders(lines: Iterable[SourceLine]) -> list[Finding]:
    findings: list[Finding] = []
    for source in lines:
        if not source.text:
            continue
        generic = PLACEHOLDER_RE.search(source.text)
        doi_placeholder = False
        for doi_match in DOI_CANDIDATE_RE.finditer(source.text):
            token = doi_match.group(0)
            if (
                "?" in token
                or re.search(r"(?:tbd|xxx|to[-\s]+be[-\s]+filled)", token, flags=re.I)
                or re.search(r"/x(?:[.,;:)]|$)", token, flags=re.I)
            ):
                doi_placeholder = True
                break
        if generic or doi_placeholder:
            findings.append(
                Finding(
                    "critical",
                    "placeholder",
                    source.number,
                    "Placeholder or unfinished string found.",
                    line_excerpt(source.text),
                )
            )
    return findings


def scan_headings(body_lines: list[SourceLine], profile: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    numbered = re.compile(
        r"^\s*(?:(?:\d+(?:\.\d+)*[.)]?)|(?:[一二三四五六七八九十]+[、.]))\s+"
    )
    for source in body_lines:
        heading = parse_heading(source.text)
        if not heading:
            continue
        level, title = heading
        violates_numbering = (
            level >= 2
            and (
                (profile["heading_numbering_expected"] == "unnumbered" and numbered.match(title))
                or (profile["heading_numbering_expected"] == "numbered" and not numbered.match(title))
                or (
                    profile["heading_numbering_expected"] is None
                    and profile["allow_numbered_headings"] is False
                    and numbered.match(title)
                )
            )
        )
        if violates_numbering:
            findings.append(
                Finding(
                    "medium",
                    "numbered_heading",
                    source.number,
                    "Numbered heading conflicts with the active route/profile.",
                    line_excerpt(source.text),
                    False,
                )
            )
        if profile["max_heading_level"] is not None and level > profile["max_heading_level"]:
            findings.append(
                Finding(
                    "medium",
                    "heading_depth",
                    source.number,
                    f"H{level} exceeds the explicit profile maximum H{profile['max_heading_level']}.",
                    line_excerpt(source.text),
                    False,
                )
            )
    return findings


def scan_vendor_mentions(
    body_lines: list[SourceLine], profile: dict[str, Any]
) -> list[Finding]:
    if profile["allow_vendor_body_mentions"]:
        return []
    findings: list[Finding] = []
    for source in body_lines:
        if is_markdown_table_line(source.text):
            continue
        for vendor in profile["vendors"]:
            if re.search(rf"(?<!\w){re.escape(vendor)}(?!\w)", source.text, flags=re.I):
                findings.append(
                    Finding(
                        "medium",
                        "vendor_body_mention",
                        source.number,
                        f"Vendor/product name in prose: {vendor}. Confirm that precision requires it.",
                        line_excerpt(source.text),
                        False,
                    )
                )
    return findings


def scan_profile_layout(
    body_lines: list[SourceLine], profile: dict[str, Any]
) -> list[Finding]:
    findings: list[Finding] = []
    if profile["table_limit"] is not None:
        table_count = sum(
            bool(re.match(r"^\s*\|?\s*:?-{3,}.*\|.*-{3,}", source.text))
            for source in body_lines
        )
        if table_count > profile["table_limit"]:
            findings.append(
                Finding(
                    "medium",
                    "table_limit",
                    0,
                    f"Detected {table_count} Markdown tables; profile limit is {profile['table_limit']}.",
                    gate_relevant=False,
                )
            )
    if profile["figure_limit"] is not None:
        figure_lines = {
            source.number
            for source in body_lines
            if re.search(r"!\[[^\]]*\]\([^)]*\)|\bFigure\s+\d+\b|图\s*\d+", source.text, flags=re.I)
        }
        if len(figure_lines) > profile["figure_limit"]:
            findings.append(
                Finding(
                    "medium",
                    "figure_limit",
                    0,
                    f"Detected {len(figure_lines)} figure references; profile limit is {profile['figure_limit']}.",
                    gate_relevant=False,
                )
            )
    if profile["section_order"]:
        actual = [
            strip_heading_number(heading[1]).casefold()
            for source in body_lines
            if (heading := parse_heading(source.text)) and heading[0] == 2
        ]
        expected = [str(item).strip().casefold() for item in profile["section_order"]]
        positions: list[int] = []
        cursor = 0
        for name in expected:
            try:
                position = actual.index(name, cursor)
            except ValueError:
                positions = []
                break
            positions.append(position)
            cursor = position + 1
        if len(positions) != len(expected):
            findings.append(
                Finding(
                    "medium",
                    "section_order",
                    0,
                    "H2 section order does not match the explicit style profile.",
                    gate_relevant=False,
                )
            )
    return findings


def scan_equations(
    body_lines: list[SourceLine], profile: dict[str, Any]
) -> list[Finding]:
    if not profile["require_box_for_display_equations"]:
        return []
    findings: list[Finding] = []
    box_heading_level: int | None = None
    bold_box_active = False
    in_dollar_display = False
    for source in body_lines:
        heading = parse_heading(source.text)
        if heading:
            level, title = heading
            if box_heading_level is not None and level <= box_heading_level:
                box_heading_level = None
            bold_box_active = False
            if BOX_TITLE_RE.match(strip_heading_number(title)):
                box_heading_level = level
        elif BOLD_BOX_RE.match(source.text):
            bold_box_active = True
        in_box = box_heading_level is not None or bold_box_active
        line = INLINE_CODE_RE.sub("", source.text)
        dollar_count = line.count("$$")
        if dollar_count:
            if not in_dollar_display and not in_box:
                findings.append(
                    Finding(
                        "medium",
                        "display_equation_outside_box",
                        source.number,
                        "Display equation appears outside an explicit Box section.",
                        line_excerpt(source.text),
                        False,
                    )
                )
            if dollar_count % 2:
                in_dollar_display = not in_dollar_display
        if re.search(r"\\\[|\\begin\{(?:equation|align|gather)\*?\}", line) and not in_box:
            findings.append(
                Finding(
                    "medium",
                    "display_equation_outside_box",
                    source.number,
                    "Display equation appears outside an explicit Box section.",
                    line_excerpt(source.text),
                    False,
                )
            )
    return findings


def scan_unsupported_route_claims(body_lines: list[SourceLine]) -> list[Finding]:
    title, abstract = extract_title_and_abstract(body_lines)
    front = f"{title}\n{abstract}"
    full_body = "\n".join(source.text for source in body_lines)
    findings: list[Finding] = []
    methodological_lines: list[str] = []
    active_method_level: int | None = None
    for source in body_lines:
        heading = parse_heading(source.text)
        if heading:
            level, heading_title = heading
            normalized_title = strip_heading_number(heading_title).casefold()
            if re.search(
                r"\b(?:methods?|synthesis|statistical\s+analysis|data\s+analysis)\b|方法|综合|统计分析|数据分析",
                normalized_title,
            ):
                active_method_level = (
                    level
                    if active_method_level is None
                    else min(active_method_level, level)
                )
            elif active_method_level is not None and level <= active_method_level:
                active_method_level = None
            continue
        if active_method_level is not None:
            methodological_lines.append(source.text)
    methodological_text = "\n".join(methodological_lines)

    explicit_meta_operational = (
        r"\bwe\s+(?:used|conducted|performed|undertook|fit)\s+(?:a\s+)?meta[-\s]?analysis\b",
        r"\bthis\s+(?:study|review)\s+(?:is|was|uses?)\s+(?:a\s+)?meta[-\s]?analysis\b",
        r"\b(?:we|our\s+(?:review|analysis)|this\s+(?:review|analysis))\s+meta[-\s]?analy(?:s|z)ed\b",
        r"\b(?:we|our\s+(?:review|analysis)|this\s+(?:review|analysis))\s+(?:performed|used|conducted)?\s*quantitative\s+pooling\b",
        r"\b(?:we|our\s+(?:review|analysis)|this\s+(?:review|analysis))\s+(?:used|applied|fit)\s+(?:an?\s+)?inverse[-\s]variance(?:\s+(?:method|weighting))?\b",
        r"\b(?:we|our\s+(?:review|analysis)|this\s+(?:review|analysis))\s+(?:report(?:ed)?|calculated|estimated)\s+pooled\s+(?:effect|estimate|sensitivity|specificity|accuracy|result)s?\b",
        r"\b(?:we|our\s+(?:review|analysis)|this\s+(?:review|analysis))\s+(?:used|fit|applied)\s+(?:a\s+)?random[-\s]effects?\s+model\b",
        r"\b(?:we|our\s+(?:review|analysis)|this\s+(?:review|analysis))\s+(?:generated|produced|used)\s+(?:a\s+)?(?:forest|funnel)\s+plot\b",
        r"(?:我们|本(?:研究|综述)).{0,16}(?:开展|进行|实施).{0,12}荟萃分析",
        r"(?:我们|本(?:研究|综述)).{0,20}(?:采用|使用).{0,8}随机效应(?:模型)?.{0,16}(?:合并|汇总)效应量",
        r"(?:我们|本(?:研究|综述)).{0,20}(?:合并效应量|定量合并|逆方差加权)",
    )
    passive_method_meta = (
        r"\ba\s+meta[-\s]?analysis\s+(?:synthesi[sz]ed|combined|pooled|estimated|was\s+used)\b",
        r"\b(?:eligible\s+studies|study\s+results|effect\s+(?:estimates|sizes)|the\s+data)\s+(?:were\s+)?meta[-\s]?analy(?:s|z)ed\b",
        r"\bquantitative\s+pooling\s+(?:was\s+)?(?:performed|conducted|used|undertaken)(?:\s+using\s+inverse[-\s]variance(?:\s+weighting)?)?\b",
        r"\beffect\s+sizes\s+were\s+meta[-\s]?analy(?:s|z)ed\s+using\s+inverse[-\s]variance\b",
        r"\b(?:our|the)\s+(?:meta[-\s]?analysis|pooled\s+analysis).{0,40}(?:I\s*[²2]|heterogeneity)\s*(?:=|was|were|of)\b",
        r"采用.{0,8}随机效应(?:模型)?.{0,16}(?:合并|汇总)效应量",
    )
    if (
        contains_positive_phrase(front, (r"\bmeta[-\s]?analysis\b", r"荟萃分析"))
        or contains_positive_phrase(full_body, explicit_meta_operational)
        or contains_positive_phrase(methodological_text, passive_method_meta)
    ):
        findings.append(
            Finding(
                "critical",
                "unsupported_route_claim",
                0,
                "Meta-analysis is outside this auditor's supported review routes.",
            )
        )
    umbrella_operational = (
        r"\bthis\s+(?:study\s+is\s+an?\s+)?umbrella\s+review\b",
        r"\bwe\s+(?:conducted|performed|undertook)\s+(?:an?\s+)?umbrella\s+review\b",
        r"\boverview\s+of\s+(?:systematic\s+)?reviews\b",
        r"\breview\s+overlap\b",
        r"\bcorrected\s+covered\s+area\b",
        r"\bCCA\b.{0,30}\boverlap\b",
        r"综述重叠|校正覆盖面积",
    )
    if contains_positive_phrase(front, (r"\bumbrella\s+review\b", r"伞形综述")) or contains_positive_phrase(full_body, umbrella_operational):
        findings.append(
            Finding(
                "critical",
                "unsupported_route_claim",
                0,
                "Umbrella review is outside this auditor's supported review routes.",
            )
        )
    return findings


def scan_evidence_route_methods(route: str, body_lines: list[SourceLine]) -> list[Finding]:
    methods = find_section(body_lines, {"methods", "methodology", "materials and methods", "方法", "方法学"})
    if methods is None:
        return [
            Finding(
                "critical",
                "missing_methods_section",
                0,
                f"The {route} route requires a structured Methods section.",
            )
        ]
    start, end, _ = methods
    method_lines = body_lines[start + 1 : end]
    required = SCOPING_METHOD_ELEMENTS if route == "scoping" else SYSTEMATIC_METHOD_ELEMENTS
    findings: list[Finding] = []
    headings: list[tuple[int, int, str]] = []
    for index, source in enumerate(method_lines):
        heading = parse_heading(source.text)
        if heading:
            headings.append((index, heading[0], strip_heading_number(heading[1]).casefold()))
    for element, patterns in required.items():
        matches = [item for item in headings if any(re.search(pattern, item[2], flags=re.I) for pattern in patterns)]
        if not matches:
            findings.append(
                Finding(
                    "critical",
                    "missing_methods_element",
                    body_lines[start].number,
                    f"Structured Methods is missing the required {route} element: {element}.",
                )
            )
            continue
        if not any(heading_has_content(method_lines, index, level) for index, level, _ in matches):
            findings.append(
                Finding(
                    "critical",
                    "empty_methods_element",
                    method_lines[matches[0][0]].number,
                    f"Methods heading for {element} has no substantive content.",
                    line_excerpt(method_lines[matches[0][0]].text),
                )
            )
    methods_text = "\n".join(source.text for source in method_lines)
    framework_pattern = r"\bPCC\b|Population.{0,80}Concept.{0,80}Context|人群.{0,80}概念.{0,80}情境"
    if route == "systematic":
        framework_pattern = r"\b(?:PICOS?|PIRD)\b|Participants?.{0,100}(?:Index test|Intervention)|研究对象.{0,100}(?:指标测试|干预)"
    if not re.search(framework_pattern, methods_text, flags=re.I | re.S):
        findings.append(
            Finding(
                "critical",
                "missing_question_framework",
                body_lines[start].number,
                f"Methods does not state the route-appropriate question framework for {route}.",
            )
        )
    return findings


def scan_structure(
    route: str,
    body_lines: list[SourceLine],
    ref_heading_found: bool,
    references: ReferenceSet,
    citations: list[Citation],
    profile: dict[str, Any],
) -> list[Finding]:
    visible_text = "".join(source.text.strip() for source in body_lines)
    if not visible_text:
        return [Finding("critical", "empty_manuscript", 0, "The manuscript has no auditable prose.")]

    findings: list[Finding] = []
    title, abstract = extract_title_and_abstract(body_lines)
    if not title:
        findings.append(Finding("high", "missing_title", 0, "No manuscript title was found."))
    if profile["require_abstract"] and not abstract:
        findings.append(Finding("high", "missing_abstract", 0, "No populated Abstract section was found."))
    if profile["require_references"]:
        if not ref_heading_found and not references.entries:
            findings.append(
                Finding("critical", "missing_references_section", 0, "No supported References/Bibliography heading or canonical project bibliography was found.")
            )
        elif not references.entries:
            findings.append(Finding("critical", "empty_references", 0, "The references section has no parsed entries."))
    if not citations:
        findings.append(Finding("critical", "no_body_citations", 0, "No supported body citations were found."))

    key_section = find_section(body_lines, {"key points", "key messages", "要点", "关键点"})
    if profile["require_key_points"]:
        if key_section is None:
            findings.append(
                Finding(
                    "medium",
                    "missing_key_points",
                    0,
                    "The explicit profile requires a Key Points section.",
                    gate_relevant=False,
                )
            )
    if profile["key_points_expected"] == "absent" and key_section is not None:
        findings.append(
            Finding(
                "medium",
                "unexpected_key_points",
                body_lines[key_section[0]].number,
                "The explicit profile expects no Key Points section.",
                gate_relevant=False,
            )
        )

    if route in {"scoping", "systematic"}:
        findings.extend(scan_evidence_route_methods(route, body_lines))
    elif find_section(body_lines, {"methods", "methodology", "方法", "方法学"}) is None:
        findings.append(Finding("high", "missing_methods_section", 0, "No Methods section was found."))
    return findings


def scan_duplicate_dois(references: ReferenceSet) -> list[Finding]:
    doi_to_ids: dict[str, list[str]] = defaultdict(list)
    for identifier, entry in references.entries.items():
        for raw in DOI_RE.findall(entry):
            doi = raw.casefold().rstrip(".,;:})")
            doi_to_ids[doi].append(identifier)
    return [
        Finding(
            "high",
            "duplicate_doi",
            references.entry_lines.get(identifiers[-1], 0),
            f"Duplicate DOI {doi} appears in references {identifiers}.",
        )
        for doi, identifiers in doi_to_ids.items()
        if len(identifiers) > 1
    ]
