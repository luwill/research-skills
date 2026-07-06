#!/usr/bin/env python3
"""Audit a medical-imaging review manuscript for common AI-review failure modes.

This script is intentionally conservative. It flags likely issues for review; it
does not prove that a citation or claim is correct. Source-level verification is
still required for quantitative and directional claims.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable


PLACEHOLDER_PATTERNS = [
    r"\bxxx\b",
    r"\[TBD\]",
    r"x\):xxx",
    r"doi:10\.[A-Za-z0-9_.-]+/x",
    r"to be added",
    r"to be declared",
    r"figure placeholder",
    r"\[Figure placeholder\]",
]

LLM_TELLS = [
    "has shown promising",
    "may suggest",
    "interestingly,",
    "in recent years,",
    "it is worth noting",
    "demonstrates the effectiveness of",
    "may offer significant advantages",
]

DEFAULT_VENDORS = [
    "HeartFlow",
    "Cleerly",
    "Caristo",
    "Keya",
    "Shukun",
    "DeepVessel",
    "CaRi-Heart",
    "CaRi-Plaque",
]

SYSTEMATIC_TERMS = [
    "systematic review",
    "meta-analysis",
    "metaanalysis",
]

SYSTEMATIC_SUPPORT_TERMS = [
    "PRISMA",
    "eligibility criteria",
    "search strategy",
    "screening",
    "risk of bias",
    "data extraction",
]


@dataclass
class Finding:
    severity: str
    category: str
    line: int
    message: str
    excerpt: str = ""


def line_excerpt(line: str, limit: int = 180) -> str:
    line = line.strip()
    return line if len(line) <= limit else line[: limit - 3] + "..."


def is_table_line(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("|") and stripped.endswith("|")


def split_body_and_refs(lines: list[str]) -> tuple[list[str], list[str]]:
    ref_start = None
    for idx, line in enumerate(lines):
        if re.match(r"^#{1,4}\s+References\b", line.strip(), flags=re.I):
            ref_start = idx
            break
    if ref_start is None:
        return lines, []
    return lines[:ref_start], lines[ref_start + 1 :]


def parse_references(ref_lines: list[str]) -> dict[int, str]:
    refs: dict[int, str] = {}
    current_num = None
    current_parts: list[str] = []

    def flush() -> None:
        nonlocal current_num, current_parts
        if current_num is not None:
            refs[current_num] = " ".join(part.strip() for part in current_parts).strip()
        current_num = None
        current_parts = []

    for line in ref_lines:
        match = re.match(r"^\s*(?:\[(\d+)\]|(\d+)\.)\s*(.+)", line)
        if match:
            flush()
            current_num = int(match.group(1) or match.group(2))
            current_parts = [match.group(3)]
        elif current_num is not None and line.strip():
            current_parts.append(line.strip())
    flush()
    return refs


def citation_numbers(text: str) -> list[int]:
    nums: list[int] = []
    for bracket in re.findall(r"\[([0-9][0-9,\-\s]*)\]", text):
        parsed: list[int] = []
        invalid = False
        for part in re.split(r",", bracket):
            part = part.strip()
            if not part:
                continue
            if "-" in part:
                bounds = [p.strip() for p in part.split("-", 1)]
                if all(p.isdigit() for p in bounds):
                    start, end = map(int, bounds)
                    if 0 < start <= end <= start + 50:
                        parsed.extend(range(start, end + 1))
                    else:
                        invalid = True
            elif part.isdigit():
                value = int(part)
                if value <= 0:
                    invalid = True
                else:
                    parsed.append(value)
        if not invalid:
            nums.extend(parsed)
    return nums


def sentence_containing(lines: list[str], line_index: int, citation: int) -> str:
    line = lines[line_index].strip()
    marker = f"[{citation}]"
    if marker not in line:
        return line
    fragments = re.split(r"(?<=[.!?])\s+", line)
    for fragment in fragments:
        if marker in fragment:
            return fragment
    return line


def first_author_from_ref(entry: str) -> str | None:
    if not entry:
        return None
    first_chunk = entry.split(".", 1)[0]
    match = re.match(r"\s*([A-Z][A-Za-z'`-]+)", first_chunk)
    return match.group(1).lower() if match else None


def mentioned_author(sentence: str) -> str | None:
    match = re.search(r"\b([A-Z][A-Za-z'`-]+)\s+et\s+al\.", sentence)
    if match:
        return match.group(1).lower()
    return None


def scan_placeholders(lines: list[str]) -> Iterable[Finding]:
    pattern = re.compile("|".join(f"(?:{p})" for p in PLACEHOLDER_PATTERNS), flags=re.I)
    for idx, line in enumerate(lines, start=1):
        if pattern.search(line):
            yield Finding("critical", "placeholder", idx, "Placeholder or unfinished string found.", line_excerpt(line))


def scan_headings(lines: list[str]) -> Iterable[Finding]:
    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        if re.match(r"^#{2,4}\s+\d+(?:\.\d+)*\.?\s+", stripped):
            yield Finding("medium", "numbered_heading", idx, "Numbered heading found.", line_excerpt(line))
        if stripped.startswith("#### "):
            yield Finding("medium", "h4_heading", idx, "H4 heading found; use bold lead-ins in narrative body sections.", line_excerpt(line))


def scan_llm_tells(lines: list[str]) -> Iterable[Finding]:
    for idx, line in enumerate(lines, start=1):
        lower = line.lower()
        for tell in LLM_TELLS:
            if tell in lower:
                yield Finding("low", "llm_tell", idx, f"LLM-tell phrase found: {tell}", line_excerpt(line))


def scan_vendor_mentions(body_lines: list[str], vendors: list[str]) -> Iterable[Finding]:
    for idx, line in enumerate(body_lines, start=1):
        if is_table_line(line):
            continue
        for vendor in vendors:
            if re.search(rf"\b{re.escape(vendor)}\b", line):
                yield Finding("high", "vendor_body_mention", idx, f"Vendor/product name in body: {vendor}. Justify or rewrite.", line_excerpt(line))


def scan_equations(lines: list[str]) -> Iterable[Finding]:
    box_context = False
    for idx, line in enumerate(lines, start=1):
        if re.match(r"^#{1,4}\s+", line):
            box_context = "box" in line.lower()
        if re.search(r"\bbox\s+\d+", line, flags=re.I):
            box_context = True
        if "$$" in line and not box_context:
            yield Finding("medium", "display_equation_outside_box", idx, "Display equation outside an obvious Box context.", line_excerpt(line))


def scan_citations(body_lines: list[str], refs: dict[int, str]) -> Iterable[Finding]:
    body_nums: list[tuple[int, int]] = []
    for idx, line in enumerate(body_lines):
        for num in citation_numbers(line):
            body_nums.append((idx, num))

    for idx, num in body_nums:
        if num not in refs:
            yield Finding("high", "missing_reference", idx + 1, f"Body citation [{num}] has no bibliography entry.", line_excerpt(body_lines[idx]))
            continue
        sentence = sentence_containing(body_lines, idx, num)
        author = mentioned_author(sentence)
        bib_author = first_author_from_ref(refs.get(num, ""))
        if author and bib_author and author != bib_author:
            yield Finding(
                "high",
                "author_citation_mismatch",
                idx + 1,
                f"Sentence mentions {author.title()} et al. but reference [{num}] appears to start with {bib_author.title()}.",
                line_excerpt(sentence),
            )

    ref_nums = set(refs)
    cited_nums = {num for _, num in body_nums}
    unused = sorted(ref_nums - cited_nums)
    if unused:
        yield Finding("low", "uncited_reference", 0, f"{len(unused)} bibliography entries are not cited in body: {unused[:20]}", "")


def scan_duplicate_dois(refs: dict[int, str]) -> Iterable[Finding]:
    doi_to_nums: dict[str, list[int]] = defaultdict(list)
    doi_re = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", flags=re.I)
    for num, entry in refs.items():
        for doi in doi_re.findall(entry):
            doi_to_nums[doi.lower().rstrip(".")].append(num)
    for doi, nums in doi_to_nums.items():
        if len(nums) > 1:
            yield Finding("high", "duplicate_doi", 0, f"Duplicate DOI {doi} appears in references {nums}.", "")


def scan_systematic_support(lines: list[str]) -> Iterable[Finding]:
    text = "\n".join(lines)
    front_text = "\n".join(lines[:150])
    lower = text.lower()
    lower_for_claims = front_text.lower()
    lower_for_claims = re.sub(r"\bnarrative\s+rather\s+than\s+a\s+systematic\s+review\b", "", lower_for_claims)
    lower_for_claims = re.sub(r"\bnot\s+(?:intended\s+as\s+)?a\s+systematic\s+review\b", "", lower_for_claims)
    lower_for_claims = re.sub(r"\bnot\s+(?:intended\s+as\s+)?a\s+meta-analysis\b", "", lower_for_claims)
    lower_for_claims = re.sub(r"\bnot\s+(?:intended\s+as\s+)?a\s+scoping\s+review\b", "", lower_for_claims)
    if not any(term in lower_for_claims for term in SYSTEMATIC_TERMS):
        return
    missing = [term for term in SYSTEMATIC_SUPPORT_TERMS if term.lower() not in lower]
    if missing:
        yield Finding(
            "critical",
            "unsupported_systematic_claim",
            0,
            "Systematic/meta-analysis language appears but methods support terms are missing: " + ", ".join(missing),
            "",
        )


def severity_rank(severity: str) -> int:
    return {"critical": 4, "high": 3, "medium": 2, "low": 1}.get(severity, 0)


def render_markdown(path: Path, findings: list[Finding], refs: dict[int, str]) -> str:
    counts = Counter(f.severity for f in findings)
    lines = [
        f"# Manuscript Audit Report",
        "",
        f"File: `{path}`",
        f"References parsed: {len(refs)}",
        "",
        "## Summary",
        "",
        f"- Critical: {counts['critical']}",
        f"- High: {counts['high']}",
        f"- Medium: {counts['medium']}",
        f"- Low: {counts['low']}",
        "",
    ]
    if not findings:
        lines.append("No automated findings. Continue with source-level citation verification.")
        return "\n".join(lines) + "\n"

    lines.extend(["## Findings", ""])
    for finding in sorted(findings, key=lambda f: (-severity_rank(f.severity), f.category, f.line)):
        loc = f"line {finding.line}" if finding.line else "global"
        lines.append(f"- **{finding.severity.upper()}** `{finding.category}` ({loc}): {finding.message}")
        if finding.excerpt:
            lines.append(f"  - `{finding.excerpt}`")
    lines.append("")
    lines.append("Automated findings are triage signals. Verify quantitative and directional claims against first sources.")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit a medical-imaging review manuscript.")
    parser.add_argument("manuscript", type=Path)
    parser.add_argument("--output", type=Path, help="Write a Markdown audit report to this path.")
    parser.add_argument("--json", action="store_true", help="Emit JSON to stdout instead of Markdown.")
    parser.add_argument("--vendors", nargs="*", default=DEFAULT_VENDORS, help="Vendor/product names to flag outside tables.")
    parser.add_argument("--fail-on", choices=["none", "critical", "high", "medium", "low"], default="none")
    args = parser.parse_args()

    text = args.manuscript.read_text(encoding="utf-8")
    lines = text.splitlines()
    body_lines, ref_lines = split_body_and_refs(lines)
    refs = parse_references(ref_lines)

    findings: list[Finding] = []
    for scanner in [
        scan_placeholders,
        scan_headings,
        scan_llm_tells,
        scan_equations,
        scan_systematic_support,
    ]:
        findings.extend(scanner(lines))
    findings.extend(scan_vendor_mentions(body_lines, args.vendors))
    findings.extend(scan_citations(body_lines, refs))
    findings.extend(scan_duplicate_dois(refs))

    if args.json:
        payload = {
            "file": str(args.manuscript),
            "reference_count": len(refs),
            "findings": [asdict(f) for f in findings],
            "summary": dict(Counter(f.severity for f in findings)),
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        report = render_markdown(args.manuscript, findings, refs)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(report, encoding="utf-8")
        else:
            print(report)

    if args.fail_on != "none":
        threshold = severity_rank(args.fail_on)
        if any(severity_rank(f.severity) >= threshold for f in findings):
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
