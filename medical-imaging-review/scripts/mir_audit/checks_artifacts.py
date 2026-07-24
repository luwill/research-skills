"""Formal-artifact-content validation and overall project-readiness aggregation.

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
from .checks_human import *  # noqa: F401,F403


def validate_formal_artifact_content(
    route: str, project_dir: Path
) -> list[Finding]:
    problems: list[str] = validate_project_config(route, project_dir, formal=True)
    for relative, words in (
        ("protocol/PROTOCOL.md", 50),
        ("search/search_plan.md", 35),
        ("screening/calibration_log.md", 15),
    ):
        if not markdown_is_substantive(project_dir / relative, minimum_words=words):
            problems.append(f"{relative} is empty, templated, or not substantive")

    checklist = (
        "reporting/PRISMA_ScR_checklist.md"
        if route == "scoping"
        else "reporting/PRISMA_2020_checklist.md"
    )
    if not checklist_is_completed(project_dir / checklist):
        problems.append(f"{checklist} has no completed checklist item")
    if route == "systematic" and not markdown_is_substantive(
        project_dir / "risk_of_bias/decision_rules.md", minimum_words=20
    ):
        problems.append(
            "risk_of_bias/decision_rules.md is empty, templated, or not substantive"
        )

    search_rows, search_error = read_csv_rows_exact(
        project_dir / "search/search_log.csv", SEARCH_LOG_COLUMNS
    )
    if search_error:
        problems.append(search_error)
    else:
        valid_searches = 0
        total_search_results = 0
        for index, row in enumerate(search_rows, start=2):
            if row_is_blank(row):
                continue
            required = (
                "source",
                "platform",
                "coverage",
                "search_date",
                "strategy_file",
                "result_count",
                "export_file",
                "searcher_id",
            )
            if not all(str(row.get(field, "")).strip() for field in required):
                problems.append(f"search/search_log.csv row {index} is incomplete")
                continue
            try:
                result_count = int(str(row.get("result_count", "")).strip())
            except ValueError:
                problems.append(f"search/search_log.csv row {index} result_count is not an integer")
                continue
            strategy = project_dir / str(row["strategy_file"]).strip()
            export = project_dir / str(row["export_file"]).strip()
            if result_count < 0 or not path_is_project_owned_file(project_dir, strategy):
                problems.append(f"search/search_log.csv row {index} has no preserved strategy file")
                continue
            if not path_is_project_owned_file(project_dir, export):
                problems.append(f"search/search_log.csv row {index} has no immutable source export")
                continue
            valid_searches += 1
            total_search_results += result_count
        if valid_searches == 0:
            problems.append(
                "search/search_log.csv must contain at least one reproducible executed-search row"
            )

    flow_counts, flow_error = validate_flow_counts(project_dir)
    if flow_error:
        problems.append(flow_error)
    elif search_error is None and valid_searches and total_search_results != flow_counts["identified"]:
        problems.append(
            "sum of search_log result_count values does not match flow_counts identified"
        )

    exclusion_rows, exclusion_error = read_csv_rows_exact(
        project_dir / "screening/full_text_exclusions.csv",
        FULL_TEXT_EXCLUSION_COLUMNS,
    )
    if exclusion_error:
        problems.append(exclusion_error)
    elif flow_counts:
        valid_exclusions = [
            row
            for row in exclusion_rows
            if not row_is_blank(row)
            and all(
                str(row.get(field, "")).strip()
                for field in FULL_TEXT_EXCLUSION_COLUMNS
            )
            and not ai_like_reviewer_id(str(row.get("reviewer_id", "")).strip())
        ]
        expected_exclusions = flow_counts["full_text_assessed"] - flow_counts["included"]
        if len({str(row["record_id"]).strip() for row in valid_exclusions}) != expected_exclusions:
            problems.append(
                "screening/full_text_exclusions.csv does not reconcile with flow_counts"
            )

    dedup_rows, dedup_error = read_csv_rows_exact(
        project_dir / "search/deduplication_log.csv", DEDUPLICATION_COLUMNS
    )
    if dedup_error:
        problems.append(dedup_error)
    elif flow_counts:
        expected_deduplications = flow_counts["identified"] - flow_counts["deduplicated"]
        valid_dedup = [
            row
            for row in dedup_rows
            if not row_is_blank(row)
            and all(
                str(row.get(field, "")).strip()
                for field in DEDUPLICATION_COLUMNS
            )
            and str(row.get("decision", "")).strip().casefold() == "remove"
            and not ai_like_reviewer_id(str(row.get("reviewer_id", "")).strip())
        ]
        removed_record_ids = [
            str(row.get("record_id", "")).strip() for row in valid_dedup
        ]
        if len(removed_record_ids) != len(set(removed_record_ids)):
            problems.append(
                "search/deduplication_log.csv repeats a removed record_id; duplicate rows cannot reconcile flow counts"
            )
        if len(set(removed_record_ids)) != expected_deduplications:
            problems.append(
                "search/deduplication_log.csv unique removal decisions do not exactly match the flow-count reduction"
            )

    screening_groups, screening_error = screening_decision_groups(
        project_dir / "screening/screening_decisions.csv"
    )
    included_records: set[str] = set()
    if screening_error:
        problems.append(screening_error)
    else:
        expected_stage_counts = {
            "title_abstract": flow_counts.get("screened", 0),
            "full_text": flow_counts.get("full_text_assessed", 0),
        }
        for stage, expected in expected_stage_counts.items():
            records = {record_id for record_id, observed in screening_groups if observed == stage}
            if len(records) != expected:
                problems.append(
                    f"screening {stage} unique-record count ({len(records)}) does not match flow_counts ({expected})"
                )
        for (record_id, stage), identifiers in screening_groups.items():
            if len(identifiers) < 2:
                problems.append(
                    "screening/screening_decisions.csv "
                    f"record_id={record_id} stage={stage} must contain at least "
                    "two distinct human reviewer IDs"
                )
        screening_rows, rows_error = read_csv_rows_exact(
            project_dir / "screening/screening_decisions.csv", SCREENING_COLUMNS
        )
        conflict_rows, conflict_error = read_csv_rows_exact(
            project_dir / "adjudication/conflict_log.csv", CONFLICT_COLUMNS
        )
        if rows_error:
            problems.append(rows_error)
            screening_rows = []
        if conflict_error:
            problems.append(conflict_error)
            conflict_rows = []
        valid_conflicts: list[dict[str, str]] = []
        for index, row in enumerate(conflict_rows, start=2):
            if row_is_blank(row):
                continue
            adjudicator = str(row.get("adjudicator_id", "")).strip()
            if not all(
                str(row.get(field, "")).strip()
                for field in (
                    "conflict_id",
                    "artifact",
                    "resolution",
                    "adjudicator_id",
                    "resolved_at",
                    "rationale",
                )
            ) or not (
                str(row.get("record_id", "")).strip()
                or str(row.get("decision_group_id", "")).strip()
            ) or ai_like_reviewer_id(adjudicator) or not is_resolved_value(
                row.get("resolution", "")
            ):
                problems.append(f"adjudication/conflict_log.csv row {index} is unresolved or non-human")
            else:
                valid_conflicts.append(row)

        rows_by_group: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
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
            rows_by_group[(str(row.get("record_id", "")).strip(), stage)].append(row)
        resolved_title_includes: set[str] = set()
        for (record_id, stage), rows in rows_by_group.items():
            decisions = {str(row.get("decision", "")).strip().casefold() for row in rows}
            declared = any(
                str(row.get("conflict", "")).strip().casefold() in {"true", "yes", "1"}
                for row in rows
            )
            matching = [
                row
                for row in valid_conflicts
                if "screen" in str(row.get("artifact", "")).casefold()
                and str(row.get("record_id", "")).strip() == record_id
                and stage in str(row.get("rationale", "")).casefold()
            ]
            resolution = (
                str(matching[-1].get("resolution", "")).strip().casefold()
                if matching
                else ""
            )
            needs_adjudication = (
                len(decisions) > 1
                or declared
                or not decisions.issubset({"include", "exclude"})
            )
            if needs_adjudication:
                if (
                    not matching
                    or resolution not in {"include", "exclude"}
                    or not all(
                    str(row.get("adjudication_status", "")).strip().casefold()
                    in {"complete", "resolved", "adjudicated"}
                    for row in rows
                    )
                ):
                    problems.append(
                        f"screening conflict lacks resolved adjudication: record_id={record_id} stage={stage}"
                    )
            elif len(decisions) == 1:
                resolution = next(iter(decisions))
            if stage == "title_abstract" and resolution == "include":
                resolved_title_includes.add(record_id)
            if stage == "full_text" and resolution == "include":
                included_records.add(record_id)
        if len(included_records) != flow_counts.get("included", 0):
            problems.append(
                "resolved full-text include records do not match flow_counts included"
            )

        valid_exclusion_ids = {
            str(row.get("record_id", "")).strip()
            for row in exclusion_rows
            if not row_is_blank(row)
            and all(
                str(row.get(field, "")).strip()
                for field in FULL_TEXT_EXCLUSION_COLUMNS
            )
        }
        full_text_records = {
            record_id for record_id, stage in screening_groups if stage == "full_text"
        }
        if resolved_title_includes != full_text_records:
            problems.append(
                "resolved title/abstract include record IDs must exactly match full-text screening record IDs"
            )
        if valid_exclusion_ids != full_text_records - included_records:
            problems.append(
                "full_text_exclusions record IDs do not match resolved full-text exclusions"
            )

    if route == "scoping":
        chart_rows, chart_error = read_csv_rows_exact(
            project_dir / "extraction/charting_table.csv", CHARTING_COLUMNS
        )
        if chart_error:
            problems.append(chart_error)
        else:
            verified_records: set[str] = set()
            for index, row in enumerate(chart_rows, start=2):
                if row_is_blank(row):
                    continue
                record_id = str(row.get("record_id", "")).strip()
                charter = str(row.get("charter_id", "")).strip()
                verifier = str(row.get("independent_verifier_id", "")).strip()
                status = str(row.get("verification_status", "")).strip().casefold()
                required = (
                    "record_id",
                    "citekey",
                    "population",
                    "concept",
                    "context",
                    "study_design",
                    "modality",
                    "task",
                    "data_items",
                    "charter_id",
                    "independent_verifier_id",
                    "verification_status",
                )
                if (
                    all(str(row.get(field, "")).strip() for field in required)
                    and charter != verifier
                    and not ai_like_reviewer_id(charter)
                    and not ai_like_reviewer_id(verifier)
                    and status == "verified"
                ):
                    verified_records.add(record_id)
                else:
                    problems.append(f"extraction/charting_table.csv row {index} is not independently verified")
            included = flow_counts.get("included")
            if isinstance(included, int) and len(verified_records) < included:
                problems.append(
                    "extraction/charting_table.csv has fewer independently verified "
                    "records than reporting/flow_counts.json included"
                )
            if verified_records != included_records:
                problems.append(
                    "scoping charting record IDs do not match resolved included records"
                )
    else:
        verified_studies: set[str] = set()
        study_rows, study_error = read_csv_rows_exact(
            project_dir / "extraction/study_characteristics.csv",
            STUDY_CHARACTERISTICS_COLUMNS,
        )
        if study_error:
            problems.append(study_error)
        else:
            verified_studies = {
                str(row.get("study_id", "")).strip()
                for row in study_rows
                if not row_is_blank(row)
                and all(
                    str(row.get(field, "")).strip()
                    for field in STUDY_CHARACTERISTICS_COLUMNS
                    if field != "notes"
                )
                and str(row.get("verification_status", "")).strip().casefold()
                == "verified"
            }
            if len(verified_studies) < flow_counts.get("included", 0):
                problems.append(
                    "extraction/study_characteristics.csv has fewer verified studies than flow_counts included"
                )
            verified_report_ids = {
                str(row.get("report_id", "")).strip()
                for row in study_rows
                if str(row.get("study_id", "")).strip() in verified_studies
            }
            if verified_report_ids != included_records:
                problems.append(
                    "systematic study_characteristics report IDs do not match resolved included records"
                )
        cohort_rows, cohort_error = read_csv_rows_exact(
            project_dir / "extraction/cohort_linkage.csv", COHORT_LINKAGE_COLUMNS
        )
        if cohort_error:
            problems.append(cohort_error)
        else:
            linked_studies = {
                str(row.get("study_id", "")).strip()
                for row in cohort_rows
                if not row_is_blank(row)
                and all(
                    str(row.get(field, "")).strip()
                    for field in COHORT_LINKAGE_COLUMNS
                    if field != "notes"
                )
                and not ai_like_reviewer_id(str(row.get("reviewer_id", "")).strip())
            }
            if not verified_studies.issubset(linked_studies):
                problems.append(
                    "extraction/cohort_linkage.csv does not cover every verified included study"
                )
        critical_rows, critical_error = read_csv_rows_exact(
            project_dir / "extraction/critical_data.csv", CRITICAL_DATA_COLUMNS
        )
        rob_rows, rob_error = read_csv_rows_exact(
            project_dir / "risk_of_bias/assessments.csv", RISK_OF_BIAS_COLUMNS
        )
        if critical_error:
            problems.append(critical_error)
        if rob_error:
            problems.append(rob_error)
        if not critical_error and not rob_error:
            critical_studies = {
                str(row.get("study_id", "")).strip()
                for row in critical_rows
                if not row_is_blank(row)
            }
            rob_studies = {
                str(row.get("study_id", "")).strip()
                for row in rob_rows
                if not row_is_blank(row)
            }
            if not verified_studies.issubset(critical_studies):
                problems.append("critical_data.csv does not cover every verified included study")
            if not verified_studies.issubset(rob_studies):
                problems.append("risk_of_bias/assessments.csv does not cover every verified included study")

    if not problems:
        return []
    return [
        Finding(
            "critical",
            "not_ready",
            0,
            f"{route.capitalize()} project artifacts are incomplete: "
            + "; ".join(problems),
        )
    ]


def scan_project_readiness(route: str, project_dir: Path | None) -> list[Finding]:
    if project_dir is None:
        if route in {"scoping", "systematic"}:
            return [
                Finding(
                    "critical",
                    "not_ready",
                    0,
                    f"The {route} route requires --project-dir for artifact readiness checks.",
                )
            ]
        return []
    if project_dir.is_symlink() or not project_dir.exists() or not project_dir.is_dir():
        return [Finding("critical", "not_ready", 0, f"Project directory does not exist: {project_dir}")]
    groups = list(COMMON_PROJECT_FILES)
    if route in {"narrative", "method-survey"}:
        groups.extend(NARRATIVE_PROJECT_FILES)
    elif route == "scoping":
        groups.extend(SCOPING_PROJECT_FILES)
    elif route == "systematic":
        groups.extend(SYSTEMATIC_PROJECT_FILES)
    findings: list[Finding] = []
    for alternatives in groups:
        if find_existing(project_dir, alternatives) is None:
            findings.append(
                Finding(
                    "critical",
                    "not_ready",
                    0,
                    f"Required project artifact is missing: {' or '.join(alternatives)}.",
                )
            )
    if not findings:
        config_problems = validate_project_config(
            route, project_dir, formal=route in {"scoping", "systematic"}
        )
        if config_problems:
            findings.append(
                Finding(
                    "critical",
                    "not_ready",
                    0,
                    "Project identity/configuration is incomplete: "
                    + "; ".join(config_problems),
                )
            )
    if route in {"narrative", "method-survey"} and not findings:
        exploration_rows, exploration_error = read_csv_rows_exact(
            project_dir / "search/narrative_exploration_log.csv",
            NARRATIVE_EXPLORATION_COLUMNS,
        )
        narrative_problems: list[str] = []
        if exploration_error:
            narrative_problems.append(exploration_error)
        elif not any(
            not row_is_blank(row)
            and all(str(row.get(field, "")).strip() for field in NARRATIVE_EXPLORATION_COLUMNS)
            for row in exploration_rows
        ):
            narrative_problems.append(
                "search/narrative_exploration_log.csv has no complete source-selection row"
            )
        if not markdown_is_substantive(
            project_dir / "search/selection_rationale.md", minimum_words=35
        ):
            narrative_problems.append(
                "search/selection_rationale.md is empty, templated, or not substantive"
            )
        if narrative_problems:
            findings.append(
                Finding(
                    "critical",
                    "not_ready",
                    0,
                    "Narrative/method-survey project artifacts are incomplete: "
                    + "; ".join(narrative_problems),
                )
            )
    if route in {"scoping", "systematic"} and not findings:
        findings.extend(validate_formal_artifact_content(route, project_dir))
    if route == "systematic":
        findings.extend(validate_human_gate(project_dir))
    return findings
