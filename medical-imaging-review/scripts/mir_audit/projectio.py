"""Project-directory I/O: CSV/YAML readers and small resolution predicates.

Part of the mir_audit package (split from the original audit_manuscript.py).
"""

from __future__ import annotations

import csv
import json
import os
import re

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .constants import *  # noqa: F401,F403
from .parsing import *  # noqa: F401,F403


def path_is_project_owned_file(project_dir: Path, candidate: Path) -> bool:
    try:
        if project_dir.is_symlink() or not candidate.is_file():
            return False
        project_resolved = project_dir.resolve(strict=True)
        candidate.resolve(strict=True).relative_to(project_resolved)
    except (OSError, ValueError):
        return False
    project_absolute = Path(os.path.abspath(project_dir))
    current = Path(os.path.abspath(candidate))
    while True:
        if current.is_symlink():
            return False
        if current == project_absolute:
            break
        if current == current.parent:
            return False
        current = current.parent
    return True


def find_existing(project_dir: Path, alternatives: tuple[str, ...]) -> Path | None:
    for relative in alternatives:
        candidate = project_dir / relative
        if path_is_project_owned_file(project_dir, candidate):
            return candidate
    return None


def read_csv_rows_exact(
    path: Path, expected_columns: tuple[str, ...]
) -> tuple[list[dict[str, str]], str | None]:
    try:
        if path.is_symlink():
            return [], f"{path} must not be a symlink"
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            actual = tuple(reader.fieldnames or ())
            if actual != expected_columns:
                return [], (
                    f"{path.name} header must exactly match schema 2.0; "
                    f"expected {list(expected_columns)}, found {list(actual)}"
                )
            return list(reader), None
    except (OSError, UnicodeError, csv.Error) as exc:
        return [], f"cannot read {path}: {exc}"


def row_is_blank(row: dict[str, str]) -> bool:
    return not any(str(value or "").strip() for value in row.values())


def is_resolved_value(value: object) -> bool:
    """Return whether an adjudication value is substantive and terminal."""

    text = str(value or "").strip()
    return bool(text) and text.casefold() not in NON_VALUE_TOKENS and not bool(
        PLACEHOLDER_RE.search(text)
    )


def structured_resolution_value(resolution: object, key: str) -> str | None:
    """Read a named adjudication result from JSON or ``key=value`` text.

    Critical extraction conflicts may also use a plain scalar for backwards
    compatibility.  RoB intentionally requires the explicit
    ``final_judgment`` key so the final domain judgment is machine-auditable.
    """

    text = str(resolution or "").strip()
    if not is_resolved_value(text):
        return None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        payload = None
    if isinstance(payload, dict):
        value = payload.get(key)
        return str(value).strip() if is_resolved_value(value) else None
    match = re.fullmatch(
        rf"\s*{re.escape(key)}\s*[:=]\s*(.+?)\s*", text, flags=re.I
    )
    if match and is_resolved_value(match.group(1)):
        return match.group(1).strip()
    if key == "adjudicated_value":
        return text
    return None


def grouped_human_reviewer_ids(
    path: Path,
    expected_columns: tuple[str, ...],
    id_column: str,
    group_columns: tuple[str, ...],
    required_row_columns: tuple[str, ...],
) -> tuple[dict[tuple[str, ...], set[str]], str | None]:
    groups: dict[tuple[str, ...], set[str]] = defaultdict(set)
    rows, error = read_csv_rows_exact(path, expected_columns)
    if error:
        return groups, error
    for index, row in enumerate(rows, start=2):
        if row_is_blank(row):
            continue
        reviewer = str(row.get(id_column, "")).strip()
        human = str(row.get("human_reviewer", "")).strip().casefold()
        group = tuple(str(row.get(column, "")).strip() for column in group_columns)
        missing = [
            column
            for column in required_row_columns
            if not str(row.get(column, "")).strip()
        ]
        if (
            human not in {"true", "yes", "1"}
            or not reviewer
            or ai_like_reviewer_id(reviewer)
            or not all(group)
            or missing
        ):
            return groups, (
                f"{path.name} row {index} is not a complete human decision"
                + (f"; missing {missing}" if missing else "")
            )
        groups[group].add(reviewer)
    return groups, None


def screening_decision_groups(
    path: Path,
) -> tuple[dict[tuple[str, str], set[str]], str | None]:
    groups: dict[tuple[str, str], set[str]] = defaultdict(set)
    rows, error = read_csv_rows_exact(path, SCREENING_COLUMNS)
    if error:
        return groups, error
    for index, row in enumerate(rows, start=2):
        if row_is_blank(row):
            continue
        reviewer = str(row.get("reviewer_id", "")).strip()
        record_id = str(row.get("record_id", "")).strip()
        human = str(row.get("human_reviewer", "")).strip().casefold()
        stage = re.sub(
            r"[^a-z]+", "_", str(row.get("stage", "")).strip().casefold()
        ).strip("_")
        if stage in {"title_abstract", "title_and_abstract", "titleabstract"}:
            stage = "title_abstract"
        elif stage in {"full_text", "fulltext"}:
            stage = "full_text"
        else:
            return groups, f"{path.name} row {index} has an invalid screening stage"
        required_values = (record_id, reviewer, str(row.get("decision", "")).strip(), str(row.get("decided_at", "")).strip())
        decision = str(row.get("decision", "")).strip().casefold()
        conflict = str(row.get("conflict", "")).strip().casefold()
        if (
            human not in {"true", "yes", "1"}
            or not all(required_values)
            or ai_like_reviewer_id(reviewer)
            or decision not in {"include", "exclude", "unclear", "maybe"}
            or (stage == "full_text" and decision not in {"include", "exclude"})
            or conflict not in {"true", "false", "yes", "no", "1", "0"}
        ):
            return groups, f"{path.name} row {index} is not a complete human screening decision"
        groups[(record_id, stage)].add(reviewer)
    return groups, None


def yaml_section(text: str, section_name: str) -> str:
    lines = text.splitlines()
    start: int | None = None
    collected: list[str] = []
    for index, line in enumerate(lines):
        if re.fullmatch(rf"{re.escape(section_name)}:\s*", line):
            start = index + 1
            continue
        if start is not None:
            if line and not line[0].isspace() and re.match(r"^[A-Za-z_][\w-]*:\s*", line):
                break
            collected.append(line)
    return "\n".join(collected)


def yaml_scalar(text: str, key: str) -> str | None:
    match = re.search(
        rf"(?m)^\s*{re.escape(key)}:\s*(.*?)\s*(?:#.*)?$", text
    )
    if not match:
        return None
    value = match.group(1).strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1]
    return value


def yaml_top_scalar(text: str, key: str) -> str | None:
    matches = re.findall(
        rf"(?m)^{re.escape(key)}:\s*(.*?)\s*(?:#.*)?$", text
    )
    if len(matches) != 1:
        return None
    value = matches[0].strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1]
    return value


def yaml_boolean_scalar(text: str, key: str) -> str | None:
    match = re.search(rf"(?m)^\s*{re.escape(key)}:\s*(true|false)\s*(?:#.*)?$", text)
    return match.group(1) if match else None


def yaml_record_list(
    section: str, key: str
) -> tuple[list[dict[str, str]], str | None]:
    lines = section.splitlines()
    key_index: int | None = None
    key_indent = 0
    inline_value = ""
    for index, line in enumerate(lines):
        match = re.match(rf"^(\s*){re.escape(key)}:\s*(.*?)\s*$", line)
        if match:
            key_index = index
            key_indent = len(match.group(1))
            inline_value = match.group(2)
            break
    if key_index is None:
        return [], f"methods.{key} is missing"
    if inline_value:
        if inline_value == "[]":
            return [], None
        return [], f"methods.{key} must use block records, not an inline value"
    records: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in lines[key_index + 1 :]:
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        if indent <= key_indent:
            break
        item = re.match(r"^\s*-\s+([A-Za-z_][\w-]*):\s*(.*?)\s*$", line)
        field = re.match(r"^\s+([A-Za-z_][\w-]*):\s*(.*?)\s*$", line)
        if item:
            if current is not None:
                records.append(current)
            current = {item.group(1): item.group(2).strip("\"'")}
        elif field and current is not None:
            current[field.group(1)] = field.group(2).strip("\"'")
        else:
            return [], f"methods.{key} contains an unsupported YAML record shape"
    if current is not None:
        records.append(current)
    required = {"title", "version", "url", "accessed_at", "applicability", "replaces"}
    for index, record in enumerate(records, start=1):
        if set(record) != required or any(
            not str(record.get(field, "")).strip() for field in required
        ):
            return [], (
                f"methods.{key} record {index} must contain exactly the standard record fields"
            )
    return records, None


def yaml_contract_duplicate_error(text: str) -> str | None:
    """Reject semantic shadowing in the small documented YAML contract."""

    top_counts: Counter[str] = Counter()
    section_key_counts: dict[str, Counter[str]] = defaultdict(Counter)
    current_section: str | None = None
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        top = re.match(r"^([A-Za-z_][\w-]*):(?:\s|$)", raw)
        if top:
            key = top.group(1)
            top_counts[key] += 1
            current_section = key if key in CONTRACT_CONFIG_SECTIONS else None
            continue
        direct = re.match(r"^  ([A-Za-z_][\w-]*):(?:\s|$)", raw)
        if current_section and direct:
            section_key_counts[current_section][direct.group(1)] += 1
    duplicate_top = sorted(key for key, count in top_counts.items() if count > 1)
    duplicate_nested = sorted(
        f"{section}.{key}"
        for section, counts in section_key_counts.items()
        for key, count in counts.items()
        if count > 1
    )
    duplicates = [*duplicate_top, *duplicate_nested]
    if duplicates:
        return (
            "review_config.yaml contains duplicate contract section/key entries: "
            + ", ".join(duplicates)
        )
    return None


def read_project_config(project_dir: Path) -> tuple[dict[str, Any], str | None]:
    path = project_dir / "review_config.yaml"
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return {}, f"cannot read {path}: {exc}"
    duplicate_error = yaml_contract_duplicate_error(text)
    if duplicate_error:
        return {}, duplicate_error
    ai = yaml_section(text, "ai_assistance")
    methods = yaml_section(text, "methods")
    review = yaml_section(text, "review")
    coverage = yaml_section(text, "coverage")
    delivery = yaml_section(text, "delivery")
    schemas = yaml_section(text, "schemas")
    citations = yaml_section(text, "citations")
    human_review = yaml_section(text, "human_review")
    used_raw = yaml_boolean_scalar(ai, "used")
    confirmed_raw = yaml_boolean_scalar(ai, "human_decision_authority_confirmed")
    certainty_raw = yaml_scalar(methods, "certainty_framework")
    return {
        "schema_version": yaml_top_scalar(text, "schema_version"),
        "project_id": yaml_top_scalar(text, "project_id"),
        "project_dir": yaml_top_scalar(text, "project_dir"),
        "project_dir_base": yaml_top_scalar(text, "project_dir_base"),
        "route": yaml_top_scalar(text, "route"),
        "ai_used": used_raw,
        "human_decision_authority_confirmed": confirmed_raw,
        "certainty_framework": certainty_raw,
        "review": review,
        "coverage": coverage,
        "delivery": delivery,
        "schemas": schemas,
        "citations": citations,
        "human_review": human_review,
        "methods": methods,
    }, None


def yaml_field_is_resolved(section: str, key: str) -> bool:
    value = yaml_scalar(section, key)
    if value is None:
        return False
    normalized = value.strip().casefold()
    if normalized not in {"", "[]", "{}", "null", "unknown", "tbd"}:
        return True
    # Accept populated block lists below ``key:``.
    lines = section.splitlines()
    for index, line in enumerate(lines):
        if re.match(rf"^\s*{re.escape(key)}:\s*$", line):
            base_indent = len(line) - len(line.lstrip())
            for following in lines[index + 1 :]:
                if not following.strip():
                    continue
                indent = len(following) - len(following.lstrip())
                if indent <= base_indent:
                    break
                if re.match(r"^\s*-\s+\S", following):
                    return True
            break
    return False


def ai_like_reviewer_id(identifier: str) -> bool:
    return bool(
        re.search(
            r"(?i)(?:^|[-_:])(gpt|claude|llm|bot|ai-agent|automation|gemini|copilot)(?:[-_:]|$)|@openai\b|@anthropic\b",
            identifier,
        )
    )


def disclosure_has_substance(project_dir: Path, ai_used: str | None) -> bool:
    path = project_dir / "AI_USE_DISCLOSURE.md"
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return False
    if ai_used == "false":
        return bool(re.search(r"(?i)\bno\s+AI\s+assistance\s+was\s+used\b|未使用.*(?:AI|人工智能)", text))
    tool_section = text.partition("## Tools")[2].partition("## Assisted tasks")[0]
    task_section = text.partition("## Assisted tasks")[2].partition("## Prohibited substitutions")[0]

    def substantive_rows(section: str) -> list[list[str]]:
        rows: list[list[str]] = []
        for line in section.splitlines():
            if not line.strip().startswith("|") or re.fullmatch(r"[|:\-\s]+", line.strip()):
                continue
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if cells and all(cells) and not any(
                marker in {cell.casefold() for cell in cells}
                for marker in {"tool/model", "task", "<tool>", "<task>"}
            ):
                rows.append(cells)
        return rows

    return bool(substantive_rows(tool_section) and substantive_rows(task_section))


def markdown_is_substantive(path: Path, *, minimum_words: int = 30) -> bool:
    try:
        if path.is_symlink():
            return False
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return False
    if PLACEHOLDER_RE.search(text) or re.search(r"<[^>\n]+>", text):
        return False
    prose = "\n".join(
        line
        for line in text.splitlines()
        if not parse_heading(line)
        and not re.fullmatch(r"\s*[|:\-\s]+\s*", line)
        and not re.match(r"^\s*[-*]\s*\[\s*[ xX]?\s*\]\s*$", line)
    )
    return len(re.findall(r"\w+|[\u3400-\u9fff]", prose, flags=re.UNICODE)) >= minimum_words


def checklist_is_completed(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return False
    return bool(re.search(r"(?im)^\s*[-*]\s*\[[xX]\]\s+\S", text)) and not bool(
        PLACEHOLDER_RE.search(text)
    )


def normalize_claim(text: str) -> str:
    text = PAREN_NUMERIC_CITATION_RE.sub("", BRACKET_RE.sub("", text)).casefold()
    text = re.sub(r"(?<!\w)@[^\s,;:.!?()]+", "", text)
    return " ".join(re.findall(r"\w+", text, flags=re.UNICODE))
