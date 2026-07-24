"""review_config.yaml validation and screening-flow count arithmetic.

Part of the mir_audit package (split from the original audit_manuscript.py).
"""

from __future__ import annotations

import json
import re

from pathlib import Path

from .projectio import *  # noqa: F401,F403


def validate_project_config(route: str, project_dir: Path, *, formal: bool) -> list[str]:
    config, error = read_project_config(project_dir)
    if error:
        return [error]
    problems: list[str] = []
    if config.get("schema_version") != "2.0":
        problems.append("review_config.yaml schema_version must be exactly 2.0")
    if not re.fullmatch(
        r"[a-z0-9]+(?:-[a-z0-9]+)*-\d{8}-\d{6}-[a-f0-9]{8}",
        project_dir.name,
    ):
        problems.append("project directory name is not a collision-safe initializer ID")
    if config.get("project_id") != project_dir.name:
        problems.append("review_config.yaml project_id must match the collision-safe directory name")
    if config.get("project_dir") != ".":
        problems.append("review_config.yaml project_dir must be exactly .")
    if config.get("project_dir_base") != "review_config_directory":
        problems.append(
            "review_config.yaml project_dir_base must be exactly review_config_directory"
        )
    if config.get("route") != route:
        problems.append("review_config.yaml route must match the requested audit route")
    if yaml_scalar(str(config.get("schemas", "")), "claim_ledger") != "2.0":
        problems.append("review_config.yaml schemas.claim_ledger must be exactly 2.0")
    if route == "systematic" and yaml_scalar(
        str(config.get("schemas", "")), "human_review_gate"
    ) != "2.0":
        problems.append("review_config.yaml schemas.human_review_gate must be exactly 2.0")
    if yaml_scalar(str(config.get("citations", "")), "bibliography") != "references.bib":
        problems.append("review_config.yaml citations.bibliography must be references.bib")
    if yaml_scalar(str(config.get("citations", "")), "working_syntax") != "pandoc-citekey":
        problems.append("review_config.yaml citations.working_syntax must be pandoc-citekey")
    if route == "systematic" and yaml_scalar(
        str(config.get("human_review", "")), "gate_path"
    ) != "human_review_gate.json":
        problems.append("review_config.yaml human_review.gate_path must be human_review_gate.json")
    if formal:
        for key in (
            "question_framework",
            "question",
            "population",
            "concept_or_index_test",
            "outcomes_or_target_condition",
            "context",
            "modality",
            "anatomy",
            "task",
            "setting",
            "audience",
            "target_journal",
            "language",
        ):
            if not yaml_field_is_resolved(str(config.get("review", "")), key):
                problems.append(f"review_config.yaml review.{key} must be resolved")
        for key in (
            "start",
            "end",
            "evidence_cutoff",
            "databases_available",
            "eligibility_languages",
            "grey_literature_policy",
        ):
            if not yaml_field_is_resolved(str(config.get("coverage", "")), key):
                problems.append(f"review_config.yaml coverage.{key} must be resolved")
        if not yaml_field_is_resolved(str(config.get("delivery", "")), "format"):
            problems.append("review_config.yaml delivery.format must be resolved")
        methods_section = str(config.get("methods", ""))
        for key in ("conduct_guidance", "review_reporting_guidance"):
            records, record_error = yaml_record_list(methods_section, key)
            if record_error:
                problems.append(f"review_config.yaml {record_error}")
            elif not records:
                problems.append(f"review_config.yaml methods.{key} must contain a versioned record")
        if route == "systematic":
            records, record_error = yaml_record_list(methods_section, "risk_of_bias_tools")
            if record_error:
                problems.append(f"review_config.yaml {record_error}")
            elif not records:
                problems.append(
                    "review_config.yaml methods.risk_of_bias_tools must contain a versioned record"
                )
        if config.get("ai_used") not in {"true", "false"}:
            problems.append("review_config.yaml ai_assistance.used must be boolean true or false")
        if config.get("human_decision_authority_confirmed") != "true":
            problems.append(
                "review_config.yaml ai_assistance.human_decision_authority_confirmed must be true"
            )
        if not disclosure_has_substance(project_dir, config.get("ai_used")):
            problems.append("AI_USE_DISCLOSURE.md does not substantiate the resolved AI-use state")
    return problems


def validate_flow_counts(project_dir: Path) -> tuple[dict[str, int], str | None]:
    path = project_dir / "reporting/flow_counts.json"
    required = (
        "identified",
        "deduplicated",
        "screened",
        "full_text_assessed",
        "included",
    )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {}, f"cannot read {path}: {exc}"
    if not isinstance(payload, dict):
        return {}, "reporting/flow_counts.json must contain a JSON object"
    counts: dict[str, int] = {}
    for key in required:
        value = payload.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            return {}, f"reporting/flow_counts.json {key} must be a non-negative integer"
        counts[key] = value
    if not (
        counts["identified"]
        >= counts["deduplicated"]
        >= counts["screened"]
        >= counts["full_text_assessed"]
        >= counts["included"]
    ):
        return {}, "reporting/flow_counts.json contains inconsistent decreasing-stage counts"
    return counts, None
