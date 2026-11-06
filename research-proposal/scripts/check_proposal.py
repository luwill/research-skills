#!/usr/bin/env python3
"""research-proposal Phase 5 citation gate.

    python3 scripts/check_proposal.py proposal_<slug>_<date>.md [--style auto|apa|numeric]

Checks, each a FAIL line naming the offending item:

1. citation-without-entry / entry-never-cited — in-text citations ↔ the References list,
   both directions. `apa`: (Smith, 2024) / (Smith et al., 2024a) / Smith and Lee (2024)
   keyed by first-author surname + year. `numeric` (GB/T 7714 顺序编码制): [1], [2-4] ↔ `[N]`
   entries. `auto` picks numeric when the References entries start with `[N]`.
2. placeholder / ai-tell — the SKILL.md Phase 5 grep patterns, same regex (AI-tell: body only).
3. scaffold-bracket — a leftover `[instruction]` from the scaffold. Figure-suggestion labels
   are allowed. An applicant-specific personalization field SKILL.md lists (`[年月]` …) is a
   WARN, not a FAIL: fill it from what the user said, or delete the line.

Exit 0: no mechanical findings (not proof the proposal is right). 1: findings. 2: bad input.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from integrity_gate import (  # noqa: E402
    Finding,
    InputError,
    apa_citations,
    apa_entries,
    finish,
    numeric_citations,
    numeric_entries,
    normalize_brackets,
    pattern_hits,
    read_text,
    reconcile,
    split_body,
    usage_error,
)

#: 与 SKILL.md Phase 5 的 canonical 占位符 grep 逐字相同（tests/test_check_proposal.py 锁定）
PLACEHOLDER_PATTERN = (
    r"xxx|XXXX|\[TBD\]|\[UNVERIFIED[^]]*\]|10\.xxxx|doi:10\.[a-z]+/x|forthcoming DOI|\[.*占位.*\]"
)
#: 与 SKILL.md Phase 5 的 AI-tell grep -nEi 逐字相同
AI_TELL_PATTERN = (
    r"over the past ((few|several|two|three) )?(decades?|years)|in recent years,|it is worth noting"
    r"|plays a (crucial|pivotal|vital) role|sheds light on|paves the way|ever-evolving"
    r"|has garnered significant attention|delves into|a testament to|众所周知|近年来，?随着|日益受到(广泛)?关注"
)
DISCLOSED_FLAG_RE = re.compile(r"^\[UNVERIFIED")
#: SKILL.md Phase 5 列出的申请人个性化字段——不判失败，但给 WARN：能填就填，不知道就删掉整行
EXEMPT_BRACKETS = {
    "University/Institution Name", "Your Field", "Month Year",
    "所属学科", "大学/研究机构名称", "年月",
}
EXEMPT_BRACKET_RE = re.compile(r"^(Figure \d+ Suggestion|图\s*\d+\s*建议)$")
BRACKET_RE = re.compile(r"(?<!!)\[([^\]\n]+)\](?![(\[:])")
REF_INSTRUCTION_RE = re.compile(r"^[*_>\s]*(?:[^\[\]]{0,12}[:：]\s*)?\[([^\]\n]+)\]")
#: 不是 scaffold 残留的方括号：顺序编码引文、复选框、脚注、citekey、旗标（另有占位符门禁），
#: 以及 GB/T 7714 文献类型标识 [J] [M] [C] [EB/OL] 与引用日期 [2024-01-01]
NOT_SCAFFOLD_RE = re.compile(
    r"^(\d+(\s*[-–—,，]\s*\d+)*|[ xX]|\^.*|@.*|UNVERIFIED.*|TBD|[A-Z]{1,2}(/OL)?|\d{4}-\d{2}-\d{2})$"
)


def check_citations(path: Path, body, refs, style: str) -> list[Finding]:
    numeric_cited, apa_cited = numeric_citations(body), apa_citations(body)
    if not refs:
        # 没有文献表时无从判断制式——两种都数，任何一处引用都说明文献表丢了
        count = len(numeric_cited) + len(apa_cited)
        return [Finding("no-references-section", path.name,
                        f"{count} in-text citation(s) but no '## References' / '## 参考文献' section")
                ] if count else []
    findings: list[Finding] = []
    if numeric_cited and apa_cited:
        # 只按一种制式对账会把另一种引用整体漏掉——宁可失败也不静默放过
        findings.append(Finding("mixed-citation-style", path.name,
                                f"{len(numeric_cited)} numeric [N] and {len(apa_cited)} author-year "
                                "citations in one text — use one style throughout"))
    if style == "auto":
        if numeric_cited or apa_cited:
            style = "numeric" if len(numeric_cited) >= len(apa_cited) else "apa"
        else:
            style = "numeric" if any(line.lstrip().startswith("[") for _, line in refs) else "apa"
    elif (style == "numeric" and apa_cited and not numeric_cited) or (
        style == "apa" and numeric_cited and not apa_cited
    ):
        findings.append(Finding("style-mismatch", path.name,
                                f"--style {style} but the in-text citations are the other style"))
    if style == "numeric":
        cited = {f"[{key}]": line for key, line in numeric_cited.items()}
        listed = {f"[{key}]": f"{path.name} References {where}"
                  for key, where in numeric_entries(refs).items()}
    else:
        cited = apa_cited
        listed = {key: f"{path.name} References {where}" for key, where in apa_entries(refs).items()}
    return findings + reconcile(cited, listed, path.name, "the References list")


def check_patterns(path: Path, text: str, body, allow_flags: bool):
    findings: list[Finding] = []
    warnings: list[Finding] = []
    for line, hit, context in pattern_hits(text, PLACEHOLDER_PATTERN):
        item = Finding("placeholder", f"{path.name}:{line}", f"'{hit}' in: {context[:80]}")
        (warnings if allow_flags and DISCLOSED_FLAG_RE.match(hit) else findings).append(item)
    body_text = "\n".join(line for _, line in body)
    body_numbers = [number for number, _ in body]
    for index, hit, context in pattern_hits(body_text, AI_TELL_PATTERN, ignore_case=True):
        findings.append(Finding("ai-tell", f"{path.name}:{body_numbers[index - 1]}",
                                f"'{hit}' in: {context[:80]}"))
    return findings, warnings


def _scaffold_hit(path: Path, number: int, content: str) -> Finding | None:
    content = content.strip()
    if content in EXEMPT_BRACKETS or EXEMPT_BRACKET_RE.match(content) or NOT_SCAFFOLD_RE.match(content):
        return None
    return Finding("scaffold-bracket", f"{path.name}:{number}", f"leftover scaffold field '[{content[:60]}]'")


def personalization_warnings(path: Path, body) -> list[Finding]:
    return [
        Finding("personalization-field", f"{path.name}:{number}",
                f"'[{match.group(1).strip()}]' left for the user: fill it from what they said, or delete the line")
        for number, line in body
        for match in BRACKET_RE.finditer(line)
        if match.group(1).strip() in EXEMPT_BRACKETS
    ]


def check_scaffold_brackets(path: Path, body, refs) -> list[Finding]:
    findings = [
        hit
        for number, line in body
        for match in BRACKET_RE.finditer(line)
        if (hit := _scaffold_hit(path, number, match.group(1)))
    ]
    # 参考文献节里 APA 条目合法地带 [Doctoral dissertation] [Data set]——只查整行就是说明的残留，
    # 例如 `[Follow appropriate citation style …]`、`*总字数：[约5,000字…]*`
    for number, line in refs:
        if match := REF_INSTRUCTION_RE.match(line):
            if hit := _scaffold_hit(path, number, match.group(1)):
                findings.append(hit)
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("proposal", type=Path)
    parser.add_argument("--style", choices=("auto", "apa", "numeric"), default="auto")
    parser.add_argument("--allow-disclosed-flags", action="store_true",
                        help="[UNVERIFIED…] already disclosed to the user: warn, don't fail")
    args = parser.parse_args(argv)
    if not args.proposal.is_file():
        return usage_error(f"proposal not found: {args.proposal}")

    try:
        text = read_text(args.proposal)
    except InputError as error:
        return usage_error(str(error))
    body, refs = (normalize_brackets(part) for part in split_body(text))
    findings = check_citations(args.proposal, body, refs, args.style)
    pattern_findings, warnings = check_patterns(args.proposal, text, body, args.allow_disclosed_flags)
    findings += pattern_findings
    findings += check_scaffold_brackets(args.proposal, body, refs)
    warnings += personalization_warnings(args.proposal, body)
    return finish(findings, warnings, "check_proposal")


if __name__ == "__main__":
    sys.exit(main())
