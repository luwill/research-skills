"""The human-governance gate validator (independent-reviewer / adjudication evidence).

Part of the mir_audit package (split from the original audit_manuscript.py).
"""

from __future__ import annotations

import csv
import json
import re

from collections import defaultdict
from pathlib import Path

from .constants import *  # noqa: F401,F403
from .model import *  # noqa: F401,F403
from .projectio import *  # noqa: F401,F403
from .checks_config import *  # noqa: F401,F403


def validate_human_gate(project_dir: Path) -> list[Finding]:
    path = project_dir / "human_review_gate.json"
    if not path_is_project_owned_file(project_dir, path):
        return [
            Finding(
                "critical",
                "not_ready",
                0,
                "Systematic review human_review_gate.json is missing, symlinked, or outside the owned project tree.",
            )
        ]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [Finding("critical", "not_ready", 0, f"human_review_gate.json is unreadable or invalid: {exc}")]
    problems: list[str] = []
    config, config_error = read_project_config(project_dir)
    if config_error:
        problems.append(config_error)
        config = {}
    if not isinstance(payload, dict):
        problems.append("top level must be an object")
        payload = {}
    if payload.get("schema_version") != "2.0":
        problems.append("schema_version must be exactly 2.0")
    if payload.get("route") != "systematic":
        problems.append("route must be exactly systematic")
    project_id = str(payload.get("project_id", "")).strip()
    if not project_id:
        problems.append("project_id must be non-empty")
    elif config.get("project_id") and project_id != config.get("project_id"):
        problems.append("project_id must match review_config.yaml")
    if payload.get("status") != "complete":
        problems.append("status must be exactly complete")
    reviewers = payload.get("reviewer_ids")
    clean_reviewers = {
        item.strip() for item in reviewers if isinstance(item, str) and item.strip()
    } if isinstance(reviewers, list) else set()
    if len(clean_reviewers) < 2:
        problems.append("reviewer_ids must contain at least two distinct non-empty human identifiers")
    ai_ids = sorted(identifier for identifier in clean_reviewers if ai_like_reviewer_id(identifier))
    if ai_ids:
        problems.append(f"reviewer_ids contains AI/automation-like identifiers: {ai_ids}")
    checks = payload.get("checks")
    if not isinstance(checks, dict):
        problems.append("checks must be an object")
        checks = {}
    for check in HUMAN_GATE_CHECKS[:4]:
        if checks.get(check) != "complete":
            problems.append(f"checks.{check} must be exactly complete")
    for check in HUMAN_GATE_CHECKS[-2:]:
        if checks.get(check) is not True:
            problems.append(f"checks.{check} must be boolean true")
    certainty_rows, certainty_error = read_csv_rows_exact(
        project_dir / "certainty/assessments.csv", CERTAINTY_COLUMNS
    )
    if certainty_error:
        problems.append(certainty_error)
    certainty_used = bool(certainty_rows) if certainty_error is None else False
    configured_certainty = str(config.get("certainty_framework") or "").casefold() not in {
        "",
        "null",
        "none",
        "{}",
    }
    certainty_value = checks.get("certainty_approval")
    if configured_certainty or certainty_used:
        if certainty_value != "complete":
            problems.append(
                "checks.certainty_approval must be complete when certainty is configured or assessed"
            )
        for row in certainty_rows:
            if row_is_blank(row):
                continue
            reviewer = str(row.get("reviewer_id", "")).strip()
            human = str(row.get("human_reviewer", "")).strip().casefold()
            approval = str(row.get("approval_status", "")).strip().casefold()
            if (
                not reviewer
                or human not in {"true", "yes", "1"}
                or ai_like_reviewer_id(reviewer)
                or approval not in {"complete", "approved"}
                or not all(
                    str(row.get(field, "")).strip()
                    for field in ("outcome_id", "framework", "certainty", "rationale")
                )
            ):
                problems.append(
                    "certainty/assessments.csv contains a row without valid human approval"
                )
                break
    elif certainty_value not in {"complete", "not_applicable"}:
        problems.append("checks.certainty_approval must be complete or not_applicable")

    evidence = payload.get("evidence")
    if evidence != EXPECTED_GATE_EVIDENCE:
        problems.append("evidence paths must exactly match the schema 2.0 contract")
    completed_at = str(payload.get("completed_at", "")).strip()
    if not completed_at or not re.match(r"^\d{4}-\d{2}-\d{2}(?:T|$)", completed_at):
        problems.append("completed_at must be non-empty")
    completed_by = str(payload.get("completed_by", "")).strip()
    if not completed_by:
        problems.append("completed_by must be non-empty")
    elif ai_like_reviewer_id(completed_by) or completed_by not in clean_reviewers:
        problems.append("completed_by must be a tracked human reviewer ID")
    if config.get("ai_used") not in {"true", "false"}:
        problems.append("review_config.yaml ai_assistance.used must be boolean true or false")
    if config.get("human_decision_authority_confirmed") != "true":
        problems.append(
            "review_config.yaml ai_assistance.human_decision_authority_confirmed must be true"
        )
    if not disclosure_has_substance(project_dir, config.get("ai_used")):
        problems.append("AI_USE_DISCLOSURE.md does not substantiate the resolved AI-use state")

    screening_path = project_dir / "screening/screening_decisions.csv"
    screening_groups, screening_error = screening_decision_groups(screening_path)
    flow_counts, flow_error = validate_flow_counts(project_dir)
    if flow_error:
        problems.append(flow_error)
    if screening_error:
        problems.append(screening_error)
    else:
        present_stages = {stage for _, stage in screening_groups}
        expected_stage_counts = {
            "title_abstract": flow_counts.get("screened", 0),
            "full_text": flow_counts.get("full_text_assessed", 0),
        }
        for required_stage, expected_count in expected_stage_counts.items():
            if expected_count and required_stage not in present_stages:
                problems.append(
                    "screening/screening_decisions.csv must contain at least one "
                    f"record at stage={required_stage}"
                )
            observed = len(
                {record_id for record_id, stage in screening_groups if stage == required_stage}
            )
            if observed != expected_count:
                problems.append(
                    "screening/screening_decisions.csv unique "
                    f"{required_stage} records ({observed}) do not match flow count ({expected_count})"
                )
        for (record_id, stage), identifiers in screening_groups.items():
            if len(identifiers) < 2:
                problems.append(
                    "screening/screening_decisions.csv "
                    f"record_id={record_id} stage={stage} must contain at least two "
                    "distinct human reviewer IDs"
                )
            untracked = sorted(identifiers - clean_reviewers)
            if untracked:
                problems.append(
                    "screening/screening_decisions.csv "
                    f"record_id={record_id} stage={stage} contains reviewer IDs "
                    f"absent from the gate: {untracked}"
                )

    evidence_specs = (
        (
            project_dir / "extraction/critical_data.csv",
            CRITICAL_DATA_COLUMNS,
            "extractor_id",
            ("study_id", "outcome_id", "decision_group_id"),
            (
                "study_id",
                "outcome_id",
                "decision_group_id",
                "citekey",
                "dataset_or_cohort",
                "dataset_split",
                "split_unit",
                "subgroup",
                "threshold",
                "comparator",
                "metric",
                "time_point",
                "estimate",
                "unit",
                "uncertainty_interval",
                "source_locator",
                "extractor_id",
                "human_reviewer",
                "decision_status",
            ),
        ),
        (
            project_dir / "risk_of_bias/assessments.csv",
            RISK_OF_BIAS_COLUMNS,
            "reviewer_id",
            ("study_id", "domain", "decision_group_id"),
            (
                "study_id",
                "decision_group_id",
                "tool",
                "tool_version",
                "domain",
                "reviewer_id",
                "human_reviewer",
                "judgment",
                "source_locator",
                "rationale",
            ),
        ),
    )
    for evidence_path, columns, id_column, group_columns, required_columns in evidence_specs:
        groups, error = grouped_human_reviewer_ids(
            evidence_path, columns, id_column, group_columns, required_columns
        )
        if error:
            problems.append(error)
            continue
        if not groups and flow_counts.get("included", 0) > 0:
            problems.append(
                f"{evidence_path.relative_to(project_dir)} must contain at least one "
                "complete decision group"
            )
        for group, identifiers in groups.items():
            group_label = ", ".join(
                f"{column}={value}" for column, value in zip(group_columns, group)
            )
            if len(identifiers) < 2:
                problems.append(
                    f"{evidence_path.relative_to(project_dir)} {group_label} must "
                    "contain at least two distinct human reviewer IDs"
                )
            untracked = sorted(identifiers - clean_reviewers)
            if untracked:
                problems.append(
                    f"{evidence_path.relative_to(project_dir)} {group_label} contains "
                    f"reviewer IDs absent from the gate: {untracked}"
                )
    conflict_rows, conflict_error = read_csv_rows_exact(
        project_dir / "adjudication/conflict_log.csv", CONFLICT_COLUMNS
    )
    if conflict_error:
        problems.append(conflict_error)
    else:
        resolved_conflicts: list[dict[str, str]] = []
        for row in conflict_rows:
            if not str(row.get("conflict_id", "")).strip():
                if not row_is_blank(row):
                    problems.append(
                        "adjudication/conflict_log.csv contains a populated row without conflict_id"
                    )
                    break
                continue
            has_target = bool(
                str(row.get("record_id", "")).strip()
                or str(row.get("decision_group_id", "")).strip()
            )
            adjudicator = str(row.get("adjudicator_id", "")).strip()
            resolution = str(row.get("resolution", "")).strip()
            if (
                not str(row.get("artifact", "")).strip()
                or not has_target
                or not is_resolved_value(resolution)
                or not adjudicator
                or ai_like_reviewer_id(adjudicator)
                or adjudicator not in clean_reviewers
                or not str(row.get("resolved_at", "")).strip()
                or not str(row.get("rationale", "")).strip()
            ):
                problems.append(
                    "adjudication/conflict_log.csv contains an unresolved or non-human-adjudicated conflict"
                )
                continue
            resolved_conflicts.append(row)

        def matching_conflict_row(
            artifact_token: str, *, record_id: str = "", decision_group_id: str = "", stage: str = ""
        ) -> dict[str, str] | None:
            for row in resolved_conflicts:
                if artifact_token not in str(row.get("artifact", "")).casefold():
                    continue
                if record_id and str(row.get("record_id", "")).strip() != record_id:
                    continue
                if decision_group_id and str(row.get("decision_group_id", "")).strip() != decision_group_id:
                    continue
                if stage and stage not in str(row.get("rationale", "")).casefold():
                    continue
                return row
            return None

        screening_rows, screening_rows_error = read_csv_rows_exact(
            project_dir / "screening/screening_decisions.csv", SCREENING_COLUMNS
        )
        if screening_rows_error:
            problems.append(screening_rows_error)
        else:
            decisions: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
            for row in screening_rows:
                if row_is_blank(row):
                    continue
                stage = re.sub(
                    r"[^a-z]+", "_", str(row.get("stage", "")).strip().casefold()
                ).strip("_")
                if stage in {"title_and_abstract", "titleabstract"}:
                    stage = "title_abstract"
                elif stage == "fulltext":
                    stage = "full_text"
                decisions[(str(row.get("record_id", "")).strip(), stage)].append(row)
            resolved_title_includes: set[str] = set()
            observed_full_text: set[str] = {
                record_id for record_id, stage in decisions if stage == "full_text"
            }
            for (record_id, stage), rows in decisions.items():
                values = {str(row.get("decision", "")).strip().casefold() for row in rows}
                declared = any(
                    str(row.get("conflict", "")).strip().casefold() in {"true", "yes", "1"}
                    for row in rows
                )
                needs_adjudication = (
                    len(values) > 1
                    or declared
                    or not values.issubset({"include", "exclude"})
                )
                resolution = next(iter(values), "") if not needs_adjudication else ""
                if needs_adjudication:
                    resolved = all(
                        str(row.get("adjudication_status", "")).strip().casefold()
                        in {"complete", "resolved", "adjudicated"}
                        for row in rows
                    )
                    conflict_row = matching_conflict_row(
                        "screen", record_id=record_id, stage=stage
                    )
                    resolution = (
                        str(conflict_row.get("resolution", "")).strip().casefold()
                        if conflict_row
                        else ""
                    )
                    if not resolved or resolution not in {"include", "exclude"}:
                        problems.append(
                            "screening disagreement lacks a matching resolved human conflict record: "
                            f"record_id={record_id} stage={stage}"
                        )
                if stage == "title_abstract" and resolution == "include":
                    resolved_title_includes.add(record_id)
            if resolved_title_includes != observed_full_text:
                problems.append(
                    "resolved title/abstract include record IDs must exactly match full-text screening record IDs"
                )

        critical_rows, critical_error = read_csv_rows_exact(
            project_dir / "extraction/critical_data.csv", CRITICAL_DATA_COLUMNS
        )
        if critical_error:
            problems.append(critical_error)
        else:
            critical_groups: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
            critical_entities: dict[str, set[tuple[str, str]]] = defaultdict(set)
            for row in critical_rows:
                if not row_is_blank(row):
                    group_key = (
                        str(row.get("study_id", "")).strip(),
                        str(row.get("outcome_id", "")).strip(),
                        str(row.get("decision_group_id", "")).strip(),
                    )
                    critical_groups[group_key].append(row)
                    critical_entities[group_key[2]].add(group_key[:2])
            for group_id, entities in critical_entities.items():
                if len(entities) != 1:
                    problems.append(
                        "critical-data decision_group_id maps to multiple study/outcome "
                        f"entities: decision_group_id={group_id}"
                    )
            disagreement_fields = (
                "dataset_or_cohort",
                "dataset_split",
                "split_unit",
                "subgroup",
                "threshold",
                "comparator",
                "metric",
                "time_point",
                "estimate",
                "unit",
                "uncertainty_interval",
                "numerator",
                "denominator",
            )
            for (study_id, outcome_id, group_id), rows in critical_groups.items():
                if any(
                    str(row.get("decision_status", "")).strip().casefold()
                    not in {"complete", "verified", "adjudicated"}
                    for row in rows
                ):
                    problems.append(
                        f"critical-data group {group_id} contains a non-terminal decision_status"
                    )
                values = {
                    tuple(
                        str(row.get(field, "")).strip()
                        for field in disagreement_fields
                    )
                    for row in rows
                }
                if len(values) > 1:
                    resolutions = {
                        str(row.get("adjudicated_value", "")).strip() for row in rows
                    }
                    adjudicators = {
                        str(row.get("adjudicator_id", "")).strip() for row in rows
                    }
                    adjudicated_value = next(iter(resolutions), "")
                    conflict_row = matching_conflict_row(
                        "extract", decision_group_id=group_id
                    )
                    conflict_value = (
                        structured_resolution_value(
                            conflict_row.get("resolution", ""), "adjudicated_value"
                        )
                        if conflict_row
                        else None
                    )
                    if (
                        len(resolutions) != 1
                        or not is_resolved_value(adjudicated_value)
                        or len(adjudicators) != 1
                        or not is_resolved_value(next(iter(adjudicators), ""))
                        or ai_like_reviewer_id(next(iter(adjudicators), ""))
                        or next(iter(adjudicators), "") not in clean_reviewers
                        or conflict_value is None
                        or conflict_value.casefold() != adjudicated_value.casefold()
                    ):
                        problems.append(
                            "critical-data disagreement lacks one substantive adjudicated "
                            "value that agrees with the matching conflict resolution: "
                            f"study_id={study_id} outcome_id={outcome_id} decision_group_id={group_id}"
                        )

        rob_rows, rob_error = read_csv_rows_exact(
            project_dir / "risk_of_bias/assessments.csv", RISK_OF_BIAS_COLUMNS
        )
        if rob_error:
            problems.append(rob_error)
        else:
            rob_groups: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
            rob_entities: dict[str, set[tuple[str, str]]] = defaultdict(set)
            for row in rob_rows:
                if not row_is_blank(row):
                    group_key = (
                        str(row.get("study_id", "")).strip(),
                        str(row.get("domain", "")).strip(),
                        str(row.get("decision_group_id", "")).strip(),
                    )
                    rob_groups[group_key].append(row)
                    rob_entities[group_key[2]].add(group_key[:2])
            for group_id, entities in rob_entities.items():
                if len(entities) != 1:
                    problems.append(
                        "risk-of-bias decision_group_id maps to multiple study/domain "
                        f"entities: decision_group_id={group_id}"
                    )
            for (study_id, domain, group_id), rows in rob_groups.items():
                judgments = {str(row.get("judgment", "")).strip().casefold() for row in rows}
                declared = any(
                    str(row.get("conflict", "")).strip().casefold() in {"true", "yes", "1"}
                    for row in rows
                )
                if len(judgments) > 1 or declared:
                    resolved = all(
                        str(row.get("adjudication_status", "")).strip().casefold()
                        in {"complete", "resolved", "adjudicated"}
                        for row in rows
                    )
                    conflict_row = matching_conflict_row(
                        "risk", decision_group_id=group_id
                    )
                    final_judgment = (
                        structured_resolution_value(
                            conflict_row.get("resolution", ""), "final_judgment"
                        )
                        if conflict_row
                        else None
                    )
                    if (
                        not resolved
                        or final_judgment is None
                        or final_judgment.casefold() not in judgments
                    ):
                        problems.append(
                            "risk-of-bias disagreement lacks a matching structured "
                            "final_judgment resolution: "
                            f"study_id={study_id} domain={domain} decision_group_id={group_id}"
                        )
    if problems:
        return [
            Finding(
                "critical",
                "not_ready",
                0,
                "Systematic human review gate is incomplete: " + "; ".join(problems),
            )
        ]
    return []
