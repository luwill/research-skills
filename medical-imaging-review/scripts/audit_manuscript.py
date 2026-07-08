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
    r"doi:\s*10\.[A-Za-z0-9_.-]+/x{2,}",  # require >=2 trailing 'x' so real DOIs like /xyz123 are not flagged
    r"to be added",
    r"to be declared",
    r"figure placeholder",
    r"\[Figure placeholder\]",
]

# Headings (case-insensitive) that mark the start of a reference/bibliography section.
# Internationalised so Chinese ("参考文献") and other variants are recognised; without
# this a Chinese manuscript parses refs={} and every [N] is mis-flagged as missing.
REFERENCE_HEADING_TITLES = (
    "references",
    "reference list",
    "reference",
    "bibliography",
    "works cited",
    "literature cited",
    "参考文献",
    "引用文献",
    "参考资料",
    "参考书目",
)

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


def heading_text(line: str) -> str | None:
    """Return the normalised text of a Markdown ATX heading, or None if not a heading."""
    match = re.match(r"^\s*#{1,6}\s+(.+?)\s*$", line)
    if not match:
        return None
    text = match.group(1).strip()
    # Drop trailing numbering, colons and full-width colons so "References:" / "参考文献：" match.
    text = text.strip("：: .")
    return text.strip()


def is_reference_heading(line: str) -> bool:
    text = heading_text(line)
    if text is None:
        return False
    normalized = text.lower()
    for title in REFERENCE_HEADING_TITLES:
        if title.isascii():
            # Allow trailing words for Latin headings ("References and Notes").
            if normalized == title or normalized.startswith(title + " "):
                return True
        else:
            # CJK titles must match exactly to avoid catching "文献综述" (literature review).
            if text == title:
                return True
    return False


def split_body_and_refs(lines: list[str]) -> tuple[list[str], list[str]]:
    ref_start = None
    for idx, line in enumerate(lines):
        if is_reference_heading(line):
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


# A name token: capitalised initial + Latin letters (incl. accents), hyphen or apostrophe.
_NAME = r"[A-Z][A-Za-zÀ-ɏ'`-]+"

# Author mention anchored directly on the citation marker. Requires an explicit
# connector ("et al." or "and <Name>/colleagues") so method/dataset names such as
# "U-Net [12]" are NOT misread as an author. Works under the skill's own house
# style "Author et al. [N]" (with the space before the bracket) as well as
# "Author et al.[N]" and "Author and Li [N]".
AUTHOR_CITATION_RE = re.compile(
    rf"({_NAME})"
    rf"\s+(?:et\s+al\.?|and\s+(?:colleagues|co-?workers|{_NAME}))"
    rf"\s*\[(\d+)\]"
)


def author_citations_in_line(line: str) -> list[tuple[str, int]]:
    """Yield (first-author-surname-lowercased, citation-number) anchored on each [N]."""
    return [
        (match.group(1).lower(), int(match.group(2)))
        for match in AUTHOR_CITATION_RE.finditer(line)
    ]


def reference_author_tokens(entry: str) -> set[str]:
    """Capitalised tokens from the leading author zone of a reference entry.

    A leading window is used because the author list precedes the title. Membership
    (rather than strict first-token equality) tolerates both "Xu C, ..." (surname
    first) and "Chenchu Xu, ..." (given-name first) journal styles.
    """
    head = entry[:80]
    return {token.lower() for token in re.findall(_NAME, head)}


def reference_mentions_author(entry: str, surname: str) -> bool:
    tokens = reference_author_tokens(entry)
    if not tokens:
        return True  # cannot tell — do not flag
    return surname in tokens


def first_author_from_ref(entry: str) -> str | None:
    if not entry:
        return None
    match = re.match(rf"\s*({_NAME})", entry)
    return match.group(1) if match else None


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
    # Box context is determined solely by the CURRENT heading. A passing body
    # mention of "Box 1" must not silence detection for the rest of the section.
    box_context = False
    for idx, line in enumerate(lines, start=1):
        if re.match(r"^#{1,4}\s+", line):
            box_context = "box" in line.lower()
        if "$$" in line and not box_context:
            yield Finding("medium", "display_equation_outside_box", idx, "Display equation outside an obvious Box context.", line_excerpt(line))


def scan_citations(body_lines: list[str], refs: dict[int, str]) -> Iterable[Finding]:
    body_nums: list[tuple[int, int]] = []
    for idx, line in enumerate(body_lines):
        for num in citation_numbers(line):
            body_nums.append((idx, num))

    # No reference section recognised: emit ONE triage note instead of flagging every
    # [N] as a missing reference (which would bury real signal on e.g. Chinese drafts).
    if not refs:
        if body_nums:
            yield Finding(
                "low",
                "references_not_detected",
                0,
                f"No reference/bibliography section detected, but the body contains "
                f"{len(body_nums)} [N] citation marker(s). Add or rename a section such "
                f"as '## References' / '## 参考文献' so body citations can be reconciled "
                f"against the bibliography.",
                "",
            )
        return

    for idx, num in body_nums:
        if num not in refs:
            yield Finding("high", "missing_reference", idx + 1, f"Body citation [{num}] has no bibliography entry.", line_excerpt(body_lines[idx]))

    # Author↔citation mismatch, anchored on each marker (works under "Author et al. [N]").
    for idx, line in enumerate(body_lines):
        for surname, num in author_citations_in_line(line):
            entry = refs.get(num)
            if not entry:
                continue  # missing_reference already reported above
            if reference_mentions_author(entry, surname):
                continue
            bib_author = first_author_from_ref(entry)
            starts = f" (reference begins '{bib_author} ...')" if bib_author else ""
            yield Finding(
                "high",
                "author_citation_mismatch",
                idx + 1,
                f"Body cites {surname.title()} et al. [{num}], but reference [{num}] "
                f"does not list a '{surname.title()}' author{starts}. Verify the "
                f"author↔citation match.",
                line_excerpt(line),
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


SELF_SYSTEMATIC_CLAIM_RES = [
    # "We conducted/performed/present ... a systematic review / meta-analysis"
    re.compile(
        r"\b(?:we|the\s+authors?)\b[^.\n]{0,80}?"
        r"\b(?:conduct(?:ed)?|perform(?:ed)?|present(?:ed)?|report(?:ed)?|undert(?:ook|ake)|"
        r"carr(?:y|ied)\s+out)\b[^.\n]{0,40}?\b(systematic\s+review|meta-?analysis)\b",
        flags=re.I,
    ),
    # "This / the present / our systematic review ..." (tight — self-descriptive)
    re.compile(r"\b(?:this|the\s+present|our)\s+(?:\w+\s+){0,2}?(systematic\s+review|meta-?analysis)\b", flags=re.I),
    # "A systematic review was/were conducted/registered ..."
    re.compile(
        r"\b(systematic\s+review|meta-?analysis)\b[^.\n]{0,30}?\b(?:was|were)\s+"
        r"(?:conducted|performed|undertaken|carried\s+out|registered)\b",
        flags=re.I,
    ),
]


def scan_systematic_support(lines: list[str]) -> Iterable[Finding]:
    """Flag a systematic/meta-analysis *self-claim* that lacks methods support.

    Only fires when the manuscript describes *itself* as systematic (title or an
    explicit "we conducted a systematic review" statement). Merely referencing prior
    systematic reviews ("earlier systematic reviews [3] focused on ...") is exempt.
    """
    text = "\n".join(lines)
    lower_full = text.lower()

    # Strip negations first so "this is not a systematic review" is not a self-claim.
    front = "\n".join(lines[:150])
    for neg in (
        r"not\s+(?:intended\s+as\s+)?(?:a\s+)?systematic\s+review",
        r"not\s+(?:intended\s+as\s+)?(?:a\s+)?meta-?analysis",
        r"rather\s+than\s+a\s+systematic\s+review",
        r"narrative\s+rather\s+than",
    ):
        front = re.sub(neg, " ", front, flags=re.I)

    title = lines[0].strip() if lines else ""
    title_self_claim = bool(re.match(r"^#\s", title)) and bool(
        re.search(r"\b(systematic\s+review|meta-?analysis)\b", title, flags=re.I)
    )
    body_self_claim = any(rgx.search(front) for rgx in SELF_SYSTEMATIC_CLAIM_RES)

    if not (title_self_claim or body_self_claim):
        return

    missing = [term for term in SYSTEMATIC_SUPPORT_TERMS if term.lower() not in lower_full]
    if missing:
        yield Finding(
            "critical",
            "unsupported_systematic_claim",
            0,
            "Manuscript claims to be a systematic review / meta-analysis but methods "
            "support terms are missing: " + ", ".join(missing),
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

    try:
        text = args.manuscript.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"error: manuscript not found: {args.manuscript}", file=sys.stderr)
        return 2
    except IsADirectoryError:
        print(f"error: expected a file but got a directory: {args.manuscript}", file=sys.stderr)
        return 2
    except UnicodeDecodeError:
        print(f"error: manuscript is not valid UTF-8: {args.manuscript}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"error: could not read {args.manuscript}: {exc}", file=sys.stderr)
        return 2

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
