---
name: medical-imaging-review
description: Use when the user asks to plan, conduct, document, synthesize, or draft a medical imaging AI narrative review or method survey, scoping review, or systematic review with qualitative synthesis, including protocol design, literature search, screening, extraction, risk-of-bias appraisal, or evidence synthesis. Do not use this skill to perform a meta-analysis or umbrella review; route those requests to a specialized evidence-synthesis methods workflow.
---

# Medical Imaging AI Review

Build traceable review artifacts whose claims can be audited back to first sources. Report the actual project state and unresolved human gates. Do not promise editorial outcomes or describe an incomplete project as a completed review.

## Scope and hard boundary

Support exactly four route tokens across three methodological families:

| User intent | Route token | Route |
|---|---|---|
| Interpret a field | narrative | Narrative review |
| Compare method families | method-survey | Method survey |
| Map available evidence and research gaps | scoping | Scoping review |
| Answer a focused question without statistical pooling | systematic | Systematic review with qualitative synthesis |

Do not perform a meta-analysis, network meta-analysis, individual-participant-data meta-analysis, or umbrella review with this skill. If the request requires pooled estimates, heterogeneity statistics, forest or funnel plots, review-overlap analysis, or review-level appraisal, stop and prepare a handoff to a specialized methods workflow. Do not approximate those methods with prose or simple averaging.

Read [references/REVIEW_TYPES.md](references/REVIEW_TYPES.md) before collecting literature or drafting. Use only narrative, method-survey, scoping, or systematic as route tokens; systematic always means qualitative synthesis in this skill. Before evidence collection begins, a corrected route may be recorded with an explicit decision note. After collection begins, the project route is immutable: freeze the old project and initialize a new project for a different route, carrying forward only logged, provenance-preserving artifacts.

## Intake gate

Before starting a multi-step review, confirm and record:

1. Review route and research question.
2. Population, modality, anatomy, task, setting, and outcomes or concepts in scope.
3. Target journal or audience and any binding instructions.
4. Search date range, language limits, databases, grey-literature policy, and evidence cutoff.
5. Expected deliverable and current project stage.
6. Named human roles for screening, extraction or charting, adjudication, risk-of-bias assessment, and certainty assessment when applicable.
7. Planned AI assistance and disclosure.

For scoping and systematic routes, read [references/REPORTING_STANDARDS.md](references/REPORTING_STANDARDS.md) before protocol or search design. If a required decision is missing, continue only with clearly labeled planning options; do not silently choose a consequential protocol rule.

## Project contract

Initialize every new multi-step project with the bundled script:

    python3 <skill_dir>/scripts/init_review_project.py --parent <workspace-root> --name <topic-slug> --route <narrative|method-survey|scoping|systematic>

Use a lowercase kebab-case topic slug. The initializer prints the newly created project path:

    review_project/<topic-slug>-<YYYYMMDD-HHMMSS>-<8hex>/

Treat that printed path as <project_dir> for the rest of the workflow. The initializer refuses an existing target and never writes into another project directory. Do not pre-create, reuse, rename, or flatten the generated child. When resuming work, select the exact existing <project_dir> instead of running initialization again.

Core generated artifacts include:

    <project_dir>/
    ├── review_config.yaml
    ├── REVIEW_CONTEXT.md
    ├── IMPLEMENTATION_PLAN.md
    ├── PARADIGM.md
    ├── manuscript.md
    ├── references.bib
    ├── claim_ledger.csv
    ├── AI_USE_DISCLOSURE.md
    └── route-specific subdirectories

Use REVIEW_CONTEXT.md as the portable project brief and review_config.yaml as the source of truth for route, scope, standards, human roles, AI use, evidence cutoff, and status. Re-read both at the start of each work session. Do not depend on a tool-specific instruction filename.

Before changing an artifact, inspect <project_dir>. Never overwrite, truncate, reset, or replace existing content. Preserve unrelated content and apply a narrow patch or merge. Ask before resolving a material conflict. A bounded advisory answer can remain inline; do not initialize a project unless the task needs persistent artifacts.

When a first-stage plan requires persistent artifacts, the response must explicitly show the initializer command that was run, the collision-safe <project_dir> printed by the initializer, and the current project status; do not imply that a project exists before the initializer succeeds.

## Stable citations and claim ledger

Use stable citekeys during research and drafting, for example [@smith2024model]. Keep `references.bib` as the project bibliography used for drafting and rendering. Preserve any user-approved RIS, EndNote, Zotero, or other export as an immutable import artifact, then normalize accepted records into `references.bib` without changing their stable source identifiers. Do not use mutable numeric citations such as [17] in the working draft. Render the target journal's numeric or author-date style only from stable citekeys at the final formatting stage.

Keep the initializer's exact claim_ledger.csv header. Each row is one atomic claim-source pair: one material claim type, metric, direction, and locally bound citekey set; split compound sentences before verification rather than assigning every sentence-level citation to every clause.

    claim_id,section,claim_text,claim_type,citekey,source_id,source_locator,evidence_excerpt,population_or_dataset,data_split,split_unit,comparator,metric,estimate,unit,uncertainty_interval,direction,access_level,source_role,access_uri,accessed_at,verification_status,verified_by,verified_at,notes

Do not rename, reorder, remove, or append columns without a schema-versioned migration.

Treat any pre-vNext 22-column ledger as an immutable legacy import, not as schema 2.0. Create a fresh schema-2.0 ledger, map values by named columns in a dated migration manifest, explicitly populate or mark unresolved the new evidence_excerpt, split_unit, and source_role fields, and preserve the legacy file. Never pad, reorder, or reinterpret a legacy row silently; migrated claims remain pending until a named human verifies the mapped record.

For every factual, quantitative, directional, novelty, regulatory, or comparative claim:

1. Link one or more stable citekeys.
2. Record the exact supporting page, table, figure, section, or abstract passage.
3. Verify metadata and claim support against a first source.
4. Record who verified it and when.
5. Keep the claim out of polished prose while verification_status is unresolved.

If only an abstract is accessible, restrict the claim to what the abstract directly supports. Do not infer internal architecture, exact performance, causal direction, or priority claims such as first from inaccessible text. See [references/CITATION_INTEGRITY.md](references/CITATION_INTEGRITY.md).

## Human governance gates

LLM agents may assist with search translation, deduplication suggestions, prioritization, extraction drafts, consistency checks, and prose. They do not count as independent human reviewers and must never be listed as such.

For a formal scoping or systematic review:

- Two named human reviewers must independently complete title/abstract and full-text screening. A named human adjudicator resolves conflicts.
- Data charting or extraction must use two named humans, either independent duplicate extraction or one extractor plus independent human verification, as pre-specified in the protocol.
- Risk-of-bias judgments require independent human assessment and documented consensus or adjudication.
- Certainty-of-evidence judgments, when used, require human approval.
- Formal-route screening decisions must be preserved in <project_dir>/screening/screening_decisions.csv.
- AI assistance, model or tool identity, task, date, human oversight, and any validation sample must be recorded in <project_dir>/AI_USE_DISCLOSURE.md according to journal and institutional requirements.

If the human team or required records are unavailable, stop at a clearly labeled provisional protocol, search set, screening suggestion, extraction draft, or appraisal draft. Do not claim that formal screening, extraction, risk-of-bias assessment, or the review itself is complete.

## Standards roles

Keep four layers separate:

1. Conduct guidance defines how the review is carried out.
2. Review reporting guidance defines what the review reports.
3. Primary-study reporting frameworks help extract reporting completeness; they are not risk-of-bias tools.
4. Risk-of-bias and certainty frameworks judge different levels of evidence and are not interchangeable.

Select and version these layers in review_config.yaml. Use [references/REPORTING_STANDARDS.md](references/REPORTING_STANDARDS.md) for the route-specific matrix.

## Style hierarchy

Resolve style decisions in this order:

1. Target-journal requirements.
2. Review-method and reporting requirements.
3. Explicit user requirements.
4. Patterns observed in verified exemplars.
5. This skill's defaults.

Style preferences such as heading depth, numbered headings, boxes, table count, citation density, vendor placement, key-points format, and phrasing are warnings only. They never override the hierarchy above and never fail a review by themselves. Factual integrity, route validity, reproducibility, human provenance, and unresolved bias or certainty gates can block progress.

Read [references/PARADIGM.md](references/PARADIGM.md) only when exemplar analysis is useful. Treat an exemplar as evidence of style, not evidence for scientific claims.

## Route-aware workflow

1. Route and configure. Complete intake, choose one supported route, record the decision, standards, roles, and evidence cutoff.
2. Initialize safely. Run init_review_project.py once and capture the printed <project_dir>.
3. Design methods. For scoping or systematic work, freeze the protocol and database-specific search plan before screening.
4. Collect and register sources. Preserve exact queries, platforms, dates, exports, deduplication decisions, stable citekeys, and source provenance.
5. Pass human gates. Complete and log screening, charting or extraction, risk-of-bias, and certainty steps required by the route.
6. Synthesize within scope. Narrative reviews interpret a justified corpus; scoping reviews map evidence; systematic qualitative reviews synthesize without statistical pooling.
7. Draft from verified records. Write <project_dir>/manuscript.md from REVIEW_CONTEXT.md, extraction or charting tables, and claim_ledger.csv rather than model memory.
8. Validate and report status. Run relevant checks, list unresolved gates, and label the deliverable accurately.

Do not convert a qualitative systematic review into a meta-analysis inside this workflow. If pooling becomes necessary, freeze the current artifacts and hand them to the specialized workflow.

## Evidence and source access

Discover the tools available in the current session before selecting a route. Prefer purpose-built literature connectors, the user's authorized Zotero library, local PDFs, and first-source pages. Do not assume a particular MCP server is installed. Do not edit tool configuration or install a connector unless the user explicitly asks.

For tool adapters and fallbacks, read [references/MCP_SETUP.md](references/MCP_SETUP.md). Search breadth, dates, and result counts must follow the research question and frozen protocol; this skill sets no universal count or recency quota.

## Audit interface

After a working manuscript exists, run:

    python3 <skill_dir>/scripts/audit_manuscript.py <project_dir>/manuscript.md --route <narrative|method-survey|scoping|systematic> --project-dir <project_dir> --fail-on critical --output <project_dir>/review_outputs/audit_report.md

Add --profile <project_dir>/style_profile.json only when that profile was populated from current journal requirements or verified exemplars. The profile controls warning-only style checks.

The positional manuscript path, --route, and --project-dir must describe the same generated project. --fail-on critical returns a failing status for critical automated findings; --output writes the Markdown report. Zero automated findings must be reported as not_assessed for substantive checks, never as a compliance pass, a draft ready for journal submission, or expert approval. Automated success does not prove source support, route compliance, human-gate completion, or expert approval.

## Delivery language

State what is complete and what is not. Useful status labels include:

- protocol draft awaiting human approval
- search executed; deduplication pending
- screening suggestions awaiting two-human decisions
- extraction draft awaiting human verification
- risk-of-bias draft awaiting human consensus
- qualitative synthesis ready from verified included studies
- narrative or method-survey draft in manuscript.md with unresolved claims listed in claim_ledger.csv

Never collapse engineering completion, scientific-method completion, and human adjudication into one status.

## Reference files

| File | Read when |
|---|---|
| [references/REVIEW_TYPES.md](references/REVIEW_TYPES.md) | Before starting or changing route |
| [references/REPORTING_STANDARDS.md](references/REPORTING_STANDARDS.md) | Selecting conduct, reporting, primary-reporting, risk-of-bias, or certainty guidance |
| [references/WORKFLOW.md](references/WORKFLOW.md) | Executing the selected route phase by phase |
| [references/TEMPLATES.md](references/TEMPLATES.md) | Understanding the generated <project_dir> artifact contracts |
| [references/CITATION_INTEGRITY.md](references/CITATION_INTEGRITY.md) | Registering sources and verifying claims |
| [references/MCP_SETUP.md](references/MCP_SETUP.md) | Discovering available tools and choosing source fallbacks |
| [references/PARADIGM.md](references/PARADIGM.md) | Deriving non-binding style guidance from exemplars |
| [references/DOMAINS.md](references/DOMAINS.md) | Considering a domain taxonomy for narrative or method surveys |
| [references/HALLUCINATION_PATTERNS.md](references/HALLUCINATION_PATTERNS.md) | Checking factual and attribution failure modes |
| [references/QUALITY_CHECKLIST.md](references/QUALITY_CHECKLIST.md) | Auditing a route-specific deliverable and unresolved gates |
