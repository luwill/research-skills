#!/usr/bin/env python3
"""Create a collision-safe medical-imaging review project.

The initializer creates a new child below ``review_project/`` and never writes
into an existing project directory.  It uses only the Python standard library.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import sys
import uuid
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path


SUPPORTED_ROUTES = ("narrative", "method-survey", "scoping", "systematic")
SAFE_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
class ProjectInitError(RuntimeError):
    """Raised when a project cannot be initialized safely."""


def csv_text(headers: list[str]) -> str:
    stream = StringIO()
    csv.writer(stream, lineterminator="\n").writerow(headers)
    return stream.getvalue()


def make_project_id(slug: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{slug}-{timestamp}-{uuid.uuid4().hex[:8]}"


def review_config(project_id: str, route: str) -> str:
    return f'''# Complete consequential fields before evidence collection.
schema_version: "2.0"
project_id: "{project_id}"
project_dir: "."
project_dir_base: "review_config_directory"
route: "{route}"

schemas:
  claim_ledger: "2.0"
  human_review_gate: "2.0"

review:
  title_working: ""
  question_framework: ""
  question: ""
  population: ""
  concept_or_index_test: ""
  comparator_or_reference_standard: ""
  outcomes_or_target_condition: ""
  context: ""
  modality: ""
  anatomy: ""
  task: ""
  setting: ""
  audience: ""
  target_journal: ""
  language: ""

coverage:
  start: ""
  end: ""
  evidence_cutoff: ""
  databases_available: []
  eligibility_languages: []
  grey_literature_policy: ""

methods:
  standard_record_fields: [title, version, url, accessed_at, applicability, replaces]
  conduct_guidance: []
  review_reporting_guidance: []
  primary_study_reporting_frameworks: []
  risk_of_bias_tools: []
  certainty_framework: null

citations:
  bibliography: "references.bib"
  working_syntax: "pandoc-citekey"
  target_csl: null

human_review:
  screeners: []
  extractors_or_charters: []
  adjudicator: ""
  risk_of_bias_reviewers: []
  certainty_reviewers: []
  gate_path: {('"human_review_gate.json"' if route == 'systematic' else 'null')}

ai_assistance:
  used: "unknown"
  uses: []
  disclosure_path: "AI_USE_DISCLOSURE.md"
  human_decision_authority_confirmed: false

delivery:
  format: "markdown"
  project_status: "planning"
  audit_profile: null
'''


def context_template(project_id: str, route: str) -> str:
    return f"""# Review Context

## Identity

- Project ID: `{project_id}`
- Route: `{route}`
- Working title:
- Target audience:
- Target journal and article type:

## Locked question and scope

- Review question:
- Population:
- Concept, intervention, model, or index test:
- Comparator or reference standard:
- Outcomes or target condition:
- Modality, anatomy, task, and setting:
- Explicit exclusions:

## Claim boundary

State what this route can and cannot conclude. Statistical pooling and
review-of-reviews methods are outside this skill.

## Instruction precedence

1. Target-journal requirements
2. Review-type conduct and reporting requirements
3. Explicit user requirements
4. Verified exemplar conventions
5. Skill defaults

## Terminology

| Preferred term | Definition | Avoid or distinguish from |
|---|---|---|
|  |  |  |

## Dataset, cohort, and report dependencies

Record reused datasets, shared test sets, companion reports, model variants,
thresholds, and other dependencies that could cause duplicate counting.

## Decisions and unresolved issues

| Date | Decision or issue | Rationale/impact | Human owner |
|---|---|---|---|
|  |  |  |  |
"""


def implementation_plan(route: str) -> str:
    return f"""# Review Implementation Plan

## Stage 1: Route and context

**Status:** in_progress

- [ ] `{route}` route and claim boundary approved
- [ ] `review_config.yaml` completed
- [ ] Human roles assigned where required
- [ ] AI assistance disclosure initialized

## Stage 2: Protocol and search

**Status:** not_started

- [ ] Route-specific protocol/search artifacts completed
- [ ] Every limit justified; no inherited count or recency quota
- [ ] Exact strategies, dates, platforms, and exports preserved
- [ ] Protocol deviations recorded

## Stage 3: Selection, extraction, and appraisal

**Status:** not_started

- [ ] Human decisions and conflicts preserved
- [ ] Extraction or charting records verified
- [ ] Cohort and dataset overlap tracked
- [ ] Risk-of-bias and certainty work completed where applicable
- [ ] `human_review_gate.json` complete for systematic route

## Stage 4: Verified synthesis and delivery

**Status:** not_started

- [ ] Stable citekeys and bibliography reconciled
- [ ] Every material claim represented in `claim_ledger.csv`
- [ ] Automated findings and `not_assessed` items reviewed
- [ ] Reporting checklist and rendered output checked
- [ ] Expert sign-off requirements listed
"""


def protocol_template(project_id: str, route: str) -> str:
    question = "PCC" if route == "scoping" else "PICOS or PIRD"
    return f"""# Protocol

## Administrative information

- Project ID: `{project_id}`
- Route: `{route}`
- Version/date:
- Registration, identifier, or rationale for no registration:
- Human authors/reviewers and roles:

## Rationale and objectives

- Rationale:
- Objective:

## Question framework

- Suggested framework: {question}
- Review question:

## Eligibility criteria

Define population/context, concept/index test/intervention,
comparator/reference standard, outcomes/target condition, study designs,
report types, setting, and every justified date or language limit.

## Information sources and search

List databases, platforms, registers, websites, grey-literature sources,
citation chasing, strategy locations, search peer review, and update plans.

## Selection process

Define human reviewer count, independence, calibration, automation, duplicate
reports, conflict resolution, and full-text exclusion reasons.

## Data collection and data items

Define charting/extraction forms, human reviewer independence, source-locator
capture, missing information, author contact, cohort linkage, and critical data.

## Appraisal

For systematic reviews, specify a design-matched risk-of-bias tool, decision
rules, independent human assessment, adjudication, and certainty approach. For
scoping reviews, state whether appraisal is needed and how it will be used.

## Synthesis

Define route-appropriate mapping or qualitative synthesis. Quantitative pooling
is outside this skill.

## Reporting bias and certainty

State the systematic-route methods, or `not_applicable` with rationale.

## Amendments and deviations

Append every change to `protocol_deviations.md` with timing, rationale, impact,
and human approval.

## Data, code, funding, conflicts, and AI assistance

Record availability, support, competing interests, and AI disclosure plans.
"""


def human_gate(project_id: str) -> str:
    payload = {
        "schema_version": "2.0",
        "project_id": project_id,
        "route": "systematic",
        "status": "not_ready",
        "reviewer_ids": [],
        "checks": {
            "title_abstract_screening": "not_ready",
            "full_text_screening": "not_ready",
            "critical_data_extraction": "not_ready",
            "risk_of_bias": "not_ready",
            "certainty_approval": "not_applicable",
            "conflicts_adjudicated": False,
            "ai_assistance_disclosed": False,
        },
        "evidence": {
            "title_abstract_screening": "screening/screening_decisions.csv",
            "full_text_screening": "screening/screening_decisions.csv",
            "critical_data_extraction": "extraction/critical_data.csv",
            "risk_of_bias": "risk_of_bias/assessments.csv",
            "certainty_approval": "certainty/assessments.csv",
            "conflicts": "adjudication/conflict_log.csv",
            "ai_disclosure": "AI_USE_DISCLOSURE.md",
        },
        "completed_at": None,
        "completed_by": None,
        "note": (
            "reviewer_ids is the aggregate union across roles; each required stage "
            "still needs two distinct humans. LLM agents do not count as human reviewers."
        ),
    }
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def common_files(project_id: str, route: str) -> dict[str, str]:
    return {
        "review_config.yaml": review_config(project_id, route),
        "REVIEW_CONTEXT.md": context_template(project_id, route),
        "IMPLEMENTATION_PLAN.md": implementation_plan(route),
        "PARADIGM.md": (
            "# Paradigm Profile\n\n"
            "## Binding journal requirements\n\n"
            "Record the current source, access date, and exact requirement.\n\n"
            "## Verified exemplars\n\n"
            "Record why each exemplar is comparable and which conventions were observed.\n\n"
            "## Profile decisions\n\n"
            "Record adopted and rejected conventions with rationale. Exemplar-derived "
            "preferences are non-binding warnings.\n"
        ),
        "manuscript.md": "",
        "references.bib": (
            "% Use stable citekeys while drafting; render journal numbering only "
            "with CSL/Pandoc.\n"
        ),
        "claim_ledger.csv": csv_text(
            [
                "claim_id",
                "section",
                "claim_text",
                "claim_type",
                "citekey",
                "source_id",
                "source_locator",
                "evidence_excerpt",
                "population_or_dataset",
                "data_split",
                "split_unit",
                "comparator",
                "metric",
                "estimate",
                "unit",
                "uncertainty_interval",
                "direction",
                "access_level",
                "source_role",
                "access_uri",
                "accessed_at",
                "verification_status",
                "verified_by",
                "verified_at",
                "notes",
            ]
        ),
        "AI_USE_DISCLOSURE.md": (
            "# AI Assistance Disclosure\n\n"
            "## Tools\n\n"
            "| Tool/model | Version or access date | Provider | Data sent | Retention/privacy notes |\n"
            "|---|---|---|---|---|\n"
            "|  |  |  |  |  |\n\n"
            "## Assisted tasks\n\n"
            "| Task | Assistance provided | Human decision-maker | Verification performed | Known limitations |\n"
            "|---|---|---|---|---|\n"
            "|  |  |  |  |  |\n\n"
            "## Prohibited substitutions\n\n"
            "Required boundary to confirm before sign-off: AI assistance must not replace "
            "required independent human screening, "
            "critical-data extraction, risk-of-bias assessment, conflict adjudication, "
            "or expert sign-off.\n\n"
            "## Errors and corrections\n\n"
            "| Date | Error or disagreement | Detection | Correction | Human approver |\n"
            "|---|---|---|---|---|\n"
            "|  |  |  |  |  |\n"
        ),
        "protocol_deviations.md": (
            "# Protocol Deviations\n\n"
            "This file is append-only. Use one entry per deviation.\n\n"
            "## DEV-<number>\n\n"
            "- Date:\n"
            "- Route/protocol version:\n"
            "- Original plan:\n"
            "- Change:\n"
            "- Reason:\n"
            "- Timing: <before seeing results|after seeing results>\n"
            "- Potential impact on eligibility, selection, extraction, synthesis, or conclusions:\n"
            "- Corrective/sensitivity action:\n"
            "- Human approver:\n"
            "- Reflected in manuscript: <yes/no and location>\n"
        ),
        "EXPERT_SIGNOFF.md": (
            "# Expert Sign-off\n\n"
            "This record does not promise acceptance or replace journal review.\n\n"
            "| Area | Required human/role | Status | Evidence or unresolved issue |\n"
            "|---|---|---|---|\n"
            "| Clinical/domain interpretation |  | pending |  |\n"
            "| Information retrieval/search |  | pending |  |\n"
            "| Evidence-synthesis methods |  | pending |  |\n"
            "| Risk of bias and certainty |  | pending |  |\n"
            "| Statistics, if applicable |  | pending |  |\n"
            "| Regulatory/reimbursement, if applicable |  | pending |  |\n"
            "| Authorship, conflicts, funding, and journal requirements |  | pending |  |\n"
        ),
    }


def selection_files() -> dict[str, str]:
    return {
        "protocol/PROTOCOL.md": "",
        "search/search_plan.md": (
            "# Search Plan\n\n"
            "## Question concepts and controlled vocabulary\n\n"
            "## Databases, platforms, registers, and supplementary sources\n\n"
            "## Database-specific strategy files\n\n"
            "## Limits and rationale\n\n"
            "## Deduplication, peer review, and update trigger\n"
        ),
        "search/search_log.csv": csv_text(
            ["source", "platform", "coverage", "search_date", "strategy_file", "filters", "result_count", "export_file", "searcher_id", "notes"]
        ),
        "search/deduplication_log.csv": csv_text(
            ["record_id", "duplicate_group", "decision", "rule", "reviewer_id", "decided_at"]
        ),
        "screening/screening_decisions.csv": csv_text(
            ["record_id", "stage", "reviewer_id", "human_reviewer", "decision", "exclusion_reason", "conflict", "adjudication_status", "decided_at"]
        ),
        "screening/full_text_exclusions.csv": csv_text(
            ["record_id", "citekey", "exclusion_reason", "reviewer_id", "adjudication_status"]
        ),
        "screening/calibration_log.md": (
            "# Screening Calibration Log\n\n"
            "Record the sample, human reviewers, agreement/disagreements, rule "
            "changes, adjudicator, and approval before formal screening.\n"
        ),
        "adjudication/conflict_log.csv": csv_text(
            ["conflict_id", "artifact", "record_id", "decision_group_id", "reviewer_1_decision", "reviewer_2_decision", "resolution", "adjudicator_id", "resolved_at", "rationale"]
        ),
        "reporting/flow_counts.json": json.dumps(
            {
                "identified": None,
                "deduplicated": None,
                "screened": None,
                "full_text_assessed": None,
                "included": None,
            },
            indent=2,
        )
        + "\n",
    }


def project_files(project_id: str, route: str) -> dict[str, str]:
    files = common_files(project_id, route)

    if route in {"narrative", "method-survey"}:
        files.update(
            {
                "search/narrative_exploration_log.csv": csv_text(
                    ["source", "query_or_navigation", "searched_at", "result_reference", "decision", "rationale"]
                ),
                "search/selection_rationale.md": (
                    "# Narrative Selection Rationale\n\n"
                    "## Purpose and boundaries\n\n"
                    "State why this is a narrative or method-survey exploration and "
                    "what it does not claim.\n\n"
                    "## Discovery routes\n\n"
                    "Record databases, websites, local collections, citation chaining, "
                    "and known-item searching.\n\n"
                    "## Selection logic\n\n"
                    "Record relevance, evidential role, historical importance, "
                    "counterevidence, and any justified recency choice.\n\n"
                    "## Deliberate limits\n\n"
                    "Record each language, date, and source restriction with its likely "
                    "consequence; do not inherit defaults.\n\n"
                    "## Likely blind spots\n\n"
                    "Record indexing, access, geographic, negative-evidence, and "
                    "unpublished-work limitations.\n"
                ),
            }
        )

    if route in {"scoping", "systematic"}:
        files.update(selection_files())
        files["protocol/PROTOCOL.md"] = protocol_template(project_id, route)

    if route == "scoping":
        files.update(
            {
                "extraction/charting_table.csv": csv_text(
                    ["record_id", "citekey", "population", "concept", "context", "study_design", "modality", "task", "data_items", "charter_id", "independent_verifier_id", "verification_status", "notes"]
                ),
                "reporting/PRISMA_ScR_checklist.md": "# PRISMA-ScR Checklist\n",
            }
        )

    if route == "systematic":
        files.update(
            {
                "extraction/study_characteristics.csv": csv_text(
                    ["study_id", "report_id", "citekey", "study_design", "population", "modality", "task", "dataset_or_cohort", "split_method", "split_unit", "reference_standard", "external_validation", "extractor_id", "verification_status", "notes"]
                ),
                "extraction/critical_data.csv": csv_text(
                    ["study_id", "outcome_id", "decision_group_id", "citekey", "dataset_or_cohort", "dataset_split", "split_unit", "subgroup", "threshold", "comparator", "metric", "time_point", "estimate", "unit", "uncertainty_interval", "numerator", "denominator", "source_locator", "extractor_id", "human_reviewer", "decision_status", "adjudicated_value", "adjudicator_id", "notes"]
                ),
                "extraction/cohort_linkage.csv": csv_text(
                    ["cohort_id", "dataset_name", "study_id", "report_id", "site", "date_range", "participant_overlap_status", "shared_test_set_status", "linkage_evidence", "decision_for_synthesis", "reviewer_id", "notes"]
                ),
                "risk_of_bias/assessments.csv": csv_text(
                    ["study_id", "decision_group_id", "tool", "tool_version", "domain", "reviewer_id", "human_reviewer", "judgment", "source_locator", "rationale", "conflict", "adjudication_status"]
                ),
                "risk_of_bias/decision_rules.md": (
                    "# Risk-of-Bias Decision Rules\n\n"
                    "- Selected tool and version:\n"
                    "- Applicability to eligible study designs:\n"
                    "- Domain and overall judgment rules:\n"
                    "- Source-locator requirements:\n"
                    "- Independent human reviewers:\n"
                    "- Conflict and adjudication process:\n"
                    "- Protocol-approved deviations:\n"
                ),
                "certainty/assessments.csv": csv_text(
                    ["outcome_id", "framework", "risk_of_bias", "inconsistency", "indirectness", "imprecision", "publication_bias", "other", "certainty", "reviewer_id", "human_reviewer", "approval_status", "rationale"]
                ),
                "human_review_gate.json": human_gate(project_id),
                "reporting/PRISMA_2020_checklist.md": "# PRISMA 2020 Checklist\n",
            }
        )
    return files


REQUIRED_DIRS = (
    "protocol",
    "search/strategies",
    "search/exports",
    "screening",
    "extraction",
    "risk_of_bias",
    "certainty",
    "adjudication",
    "reporting",
    "source_notes",
    "review_outputs",
    "rendered",
)


def initialize_project(
    parent: Path, slug: str, route: str, *, project_id: str | None = None
) -> Path:
    if route not in SUPPORTED_ROUTES:
        raise ProjectInitError(f"unsupported route: {route}")
    if not SAFE_SLUG.fullmatch(slug):
        raise ProjectInitError("name must be a lowercase kebab-case topic slug")
    if not parent.exists() or not parent.is_dir():
        raise ProjectInitError(f"parent directory does not exist: {parent}")
    parent = parent.resolve(strict=True)

    resolved_id = project_id or make_project_id(slug)
    exact_id = re.compile(
        rf"^{re.escape(slug)}-\d{{8}}-\d{{6}}-[a-f0-9]{{8}}$"
    )
    if not exact_id.fullmatch(resolved_id):
        raise ProjectInitError("project_id must match <slug>-YYYYMMDD-HHMMSS-<8 hex>")

    review_root = parent / "review_project"
    if review_root.is_symlink():
        raise ProjectInitError(f"review_project must not be a symbolic link: {review_root}")
    if review_root.exists() and not review_root.is_dir():
        raise ProjectInitError(f"review_project exists but is not a directory: {review_root}")
    review_root.mkdir(exist_ok=True)
    if review_root.resolve(strict=True) != review_root:
        raise ProjectInitError(f"review_project resolves outside the parent: {review_root}")

    target = review_root / resolved_id
    if target.exists() or target.is_symlink():
        raise ProjectInitError(f"refusing to overwrite existing path: {target}")

    staging = review_root / f".initializing-{resolved_id}-{uuid.uuid4().hex[:8]}"
    staging.mkdir(exist_ok=False)
    try:
        for relative in REQUIRED_DIRS:
            (staging / relative).mkdir(parents=True, exist_ok=False)
        for relative, content in project_files(resolved_id, route).items():
            destination = staging / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("x", encoding="utf-8", newline="") as stream:
                stream.write(content)
        if target.exists() or target.is_symlink():
            raise ProjectInitError(f"refusing to overwrite existing path: {target}")
        staging.rename(target)
    except Exception:
        if (
            staging.exists()
            and not staging.is_symlink()
            and staging.parent == review_root
            and staging.name.startswith(".initializing-")
        ):
            shutil.rmtree(staging)
        raise
    return target


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create a new collision-safe project below review_project/."
    )
    parser.add_argument("--parent", type=Path, default=Path.cwd())
    parser.add_argument("--name", default="medical-imaging-review", metavar="TOPIC-SLUG")
    parser.add_argument("--route", choices=SUPPORTED_ROUTES, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        target = initialize_project(args.parent.resolve(), args.name, args.route)
    except (ProjectInitError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
