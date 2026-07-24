# Medical Imaging AI Review Workflow

This workflow can produce an **expert-signoff-ready draft and evidence package** after all blocking gates are complete. Until then, it produces a draft awaiting expert assessment. Editorial outcomes, publication decisions, and statistical approval remain with the required humans and target venue.

Supported routes are:

- **narrative**: a transparent, non-exhaustive narrative review;
- **method-survey**: a transparent, non-exhaustive survey of methods;
- **scoping**: a protocol-driven evidence map;
- **systematic**: a protocol-driven systematic review with qualitative synthesis.

Quantitative pooling and overviews of reviews require a separate specialist workflow. Stop and request methods/statistical support rather than relabeling this workflow.

All project artifacts live below **review_project/**. Never write review artifacts into the skill directory.

---

## Phase -1: Route and collision-safe project allocation

### Choose the route

Read REVIEW_TYPES.md and REPORTING_STANDARDS.md. Record exactly one supported route in both **review_config.yaml** and **REVIEW_CONTEXT.md**.

Do not upgrade a narrative or method-survey exploration to scoping or systematic language after drafting. A route correction is allowed only before evidence collection and must be logged. After collection begins, freeze the original project, initialize a new project for the new route, and carry forward only explicitly logged sources or artifacts with preserved provenance; then restart the route-specific protocol, search, and selection process.

### Allocate a fresh project directory

Use this layout:

~~~text
review_project/
└── <topic-slug>-<YYYYMMDD-HHMMSS>-<8hex>/
~~~

Allocate the project through the canonical initializer:

~~~bash
python3 <skill_dir>/scripts/init_review_project.py --parent . --name <topic-slug> --route <narrative|method-survey|scoping|systematic>
~~~

The topic slug must be lowercase kebab case. The initializer adds a UTC timestamp and eight lowercase hexadecimal characters. It refuses to overwrite an existing target. After it returns:

1. Resolve the full path.
2. Confirm it matches **review_project/<topic-slug>-<YYYYMMDD-HHMMSS>-<8hex>/**.
3. Never reuse, merge, overwrite, or delete an existing review project automatically.
4. Preserve the generated project_dir in **review_config.yaml**.

The route and project identifier are immutable after collection begins.

If a first-stage plan requires persistent artifacts, show the exact initializer command, the collision-safe project_dir printed after successful initialization, and the current project status in the user-facing plan or handoff. Do not substitute an expected path pattern for the path actually printed by the initializer.

**Deliverable:** a newly initialized collision-safe project and a declared route.

---

## Phase 0: Context, protocol boundary, and style profile

Create these route-independent files from TEMPLATES.md:

- **review_config.yaml**: machine-readable route, project, coverage, methods, citation, reviewer, AI-assistance, and delivery settings;
- **REVIEW_CONTEXT.md**: human-readable question, scope, terminology, decisions, and unresolved issues;
- **IMPLEMENTATION_PLAN.md**: task stages and status;
- **PARADIGM.md**: observations from relevant exemplars;
- **AI_USE_DISCLOSURE.md**: tools, models, assisted tasks, human decision authority, and limitations;
- **protocol_deviations.md**: append-only deviations from the planned route or protocol;
- **references.bib**: the canonical bibliographic database;
- **claim_ledger.csv**: one row per claim-source pair.

### Style is profile-driven

Optionally capture journal or exemplar conventions in **style_profile.json** and set delivery.audit_profile in review_config.yaml to its path. The initializer does not create this optional file. Heading depth, numbered headings, key-points boxes, equations, vendor placement, table/figure counts, citation density, and preferred sentence patterns are **warnings only** unless the target journal explicitly requires them.

If no profile exists, omit the auditor's --profile argument. The auditor must report profile-dependent checks as not_assessed rather than enforce a hidden default.

No style preference may weaken protocol, citation, screening, extraction, risk-of-bias, or human-review requirements.

**Deliverable:** initialized context and configuration with no manuscript prose.

---

## Phase 1: Search design — keep narrative exploration separate

### Narrative and method-survey routes: exploratory discovery

Narrative discovery is transparent but not exhaustive. Maintain:

- **search/narrative_exploration_log.csv** with source, query, date, result page or export, and selection note;
- **search/selection_rationale.md** explaining why sources were emphasized or omitted;
- backward/forward citation-chasing notes where used.

Use controlled vocabulary, free text, known-item searching, citation chaining, local libraries, and relevant preprint sources as appropriate. Do not impose a default year, paper-count, language, publication-type, or database filter. Any limit must be justified in REVIEW_CONTEXT.md.

A narrative or method-survey route must not use the terms systematic, comprehensive search, PRISMA flow, included studies, or quantitative pooling. A request for a different evidence-synthesis route requires a new route decision and the applicable specialist workflow.

### Scoping and systematic routes: protocol-driven retrieval

Before searching, create and approve:

- **protocol/PROTOCOL.md**;
- **search/search_plan.md**;
- **search/search_log.csv**;
- **search/strategies/**, one exact strategy per database/platform;
- **search/exports/** for immutable raw exports;
- **search/deduplication_log.csv**;
- **protocol_deviations.md**.

The search plan must specify:

- question framework and eligibility criteria;
- all databases, platforms, registers, websites, conference or grey-literature sources;
- controlled vocabulary and text-word concepts;
- exact syntax, filters, limits, and the justification for every limit;
- planned citation chasing and supplementary searches;
- deduplication tool, version, and decision rules;
- search peer review or information-specialist review where available;
- initial search date and update-search trigger.

There are no default recency, result-count, language, publication-type, or study-design filters. Do not start screening until the protocol and search plan are frozen or their provisional status is explicitly recorded.

**Deliverable:** narrative/method-survey exploration artifacts or an approved scoping/systematic search package.

---

## Phase 2: Collect sources and verify claims

### Stable working citations

Use Pandoc/CSL citekeys during all drafting, for example:

~~~markdown
The evaluation used an institutionally independent cohort [@surname2024-shorttopic].
~~~

Never use manually assigned numeric citations as the working format. Store each source once in **references.bib**. Generate a stable citekey from normalized first-author surname, year, and a short title token; resolve collisions with a deterministic identifier suffix derived from DOI, PMID, arXiv ID, or another stable source identifier. Once assigned, a citekey must not change.

Final numeric or author-date formatting is produced by Pandoc with the target CSL file. See CITATION_INTEGRITY.md.

### Claim ledger

Create a claim-ledger row before committing a factual, quantitative, comparative, directional, priority, regulatory, reimbursement, or availability claim. Use the complete schema in TEMPLATES.md.

One claim supported by multiple sources receives multiple rows with the same claim_id. Source locators must identify the relevant page, section, table, figure, supplement, abstract field, registry field, or official record.

Only verification_status=verified rows may support precise numeric or directional prose. Inaccessible or abstract-only evidence must be labeled; it cannot support architecture internals, priority claims, subgroup claims, adjusted effects, or precise performance values.

### Bibliographic and integrity checks

For every source:

- confirm title, authors, venue, year, identifier, publication status, and version;
- check for corrections, expressions of concern, retractions, duplicate reports, and shared cohorts;
- record access type, URI, and access date;
- distinguish peer-reviewed evidence, preprints, registries, regulator records, reimbursement sources, and vendor materials.

Do not drop an otherwise eligible study merely because it lacks a DOI or is not indexed by Crossref. Use another stable identifier and document the verification route.

**Deliverable:** references.bib, source notes, and a populated claim ledger.

---

## Phase 3: Selection, extraction, and human review

### Narrative and method-survey routes

Maintain the exploration log and selection rationale. A narrative synthesis or method survey may be selective, but the selection logic and important counterevidence must be visible. Negative evidence, contradictory evidence, external-validation failures, leakage concerns, and equity limitations receive the same verification discipline as positive findings.

### Scoping route

Create:

~~~text
protocol/PROTOCOL.md
search/search_log.csv
search/strategies/
search/exports/
search/deduplication_log.csv
screening/screening_decisions.csv
screening/full_text_exclusions.csv
screening/calibration_log.md
extraction/charting_table.csv
adjudication/conflict_log.csv
reporting/PRISMA_ScR_checklist.md
reporting/flow_counts.json
AI_USE_DISCLOSURE.md
protocol_deviations.md
~~~

Record reviewer identities, independence, calibration, conflict handling, and any use of automation. Human reviewers retain decision authority.

### Systematic route

Create all scoping search/screening artifacts plus:

~~~text
extraction/study_characteristics.csv
extraction/critical_data.csv
extraction/cohort_linkage.csv
risk_of_bias/assessments.csv
risk_of_bias/decision_rules.md
certainty/assessments.csv
adjudication/conflict_log.csv
human_review_gate.json
reporting/PRISMA_2020_checklist.md
reporting/flow_counts.json
~~~

The following are mandatory before Results prose:

1. Two distinct human reviewers independently complete title/abstract and full-text screening. Every title/abstract record resolved to `include` must enter full-text screening; provisional `maybe`/`unclear` decisions are not terminal, and records may not disappear between stages.
2. Two distinct human reviewers independently extract critical outcome/performance data.
3. Two distinct human reviewers independently assess risk of bias using the protocol-specified tool.
4. Conflicts are resolved by documented discussion or a named human adjudicator. Preserve the original rows and record a terminal, machine-auditable resolution in `adjudication/conflict_log.csv`: `include`/`exclude` for screening, `{"adjudicated_value":"..."}` for critical extraction, and `{"final_judgment":"..."}` for risk of bias. Placeholder or non-terminal values do not close a conflict.
5. AI assistance is disclosed; an AI agent cannot occupy either human reviewer slot.
6. Protocol deviations are dated, explained, impact-assessed, and human-approved.

The initializer creates human_review_gate.json with status not_ready and canonical evidence paths. The gate must be a regular file owned by the generated project, never a symlink or an external path. The exact initial and terminal contracts are defined in TEMPLATES.md. Its status must be complete before systematic Results prose or expert-signoff packaging. A missing, malformed, externally supplied, or incomplete gate is blocking, not a limitation to waive.

**Deliverable:** route-complete selection, extraction, adjudication, and human-gate artifacts.

---

## Phase 4: Synthesis and drafting

Draft into **manuscript.md** using stable citekeys.

### Per-claim loop

1. Read the source at the locator recorded in claim_ledger.csv.
2. State the population/cohort, dataset split, comparator, metric, unit, uncertainty, and direction that are material to interpretation.
3. Cite with the stable citekey.
4. Update verification status and human verifier fields.
5. If evidence is incomplete, weaken or remove the claim; do not infer missing details.

Cross-study performance values may be tabulated, but must not be ranked as directly comparable unless dataset, split, unit of analysis, reference standard, threshold, and evaluation conditions support that comparison.

### Route-bounded synthesis

- Narrative conclusions are bounded by the disclosed exploratory corpus.
- Method-survey conclusions are bounded by the disclosed exploratory corpus and compared method dimensions.
- Scoping conclusions describe the mapped evidence and gaps; they do not estimate effects.
- Systematic conclusions are bounded by the protocol, included evidence, risk-of-bias assessments, and certainty judgments.

Style-profile findings are revision prompts, not scientific gates. Do not manufacture strong positions, verdict counts, table counts, boxes, figures, or vendor mentions to satisfy a generic template.

**Deliverable:** manuscript.md with traceable claim-ledger support.

---

## Phase 5: Independent QA and audit

Run separate passes for:

- source and citekey reconciliation;
- quantitative/directional claim verification;
- route and reporting-standard fit;
- search/screening/extraction/RoB/certainty artifacts;
- scope, counterevidence, and overclaiming;
- target-profile warnings.

LLM or automated review is supplementary. It does not satisfy independent human screening, extraction, risk-of-bias, adjudication, or expert sign-off.

Use the expected auditor interface:

~~~bash
python3 <skill_dir>/scripts/audit_manuscript.py review_project/<project-id>/manuscript.md --route <narrative|method-survey|scoping|systematic> --project-dir review_project/<project-id> --fail-on critical --output review_project/<project-id>/review_outputs/audit_report.md
~~~

The --profile argument is optional and accepts a JSON profile path. Omit it when no explicit profile exists.

Automated checks can find contradictions or missing artifacts; they cannot establish source support, methodological correctness, or reporting compliance. Even with zero automated findings, the report must retain substantive checks as **not_assessed** and require human/expert review.

**Deliverable:** review reports, a resolved-issues log, and an audit report whose global status is only fail, warning, or not_assessed, with separate finding severities.

---

## Phase 6: Expert-signoff packaging

Render citations only after citekeys and references.bib are frozen:

~~~bash
pandoc review_project/<project-id>/manuscript.md --citeproc --bibliography review_project/<project-id>/references.bib --output review_project/<project-id>/rendered/manuscript.docx
~~~

Append `--csl <verified-csl-file>` only when `citations.target_csl` is populated from a current user- or journal-supplied file.

Produce:

- **manuscript.md** and rendered preview;
- **references.bib** and an optional verified CSL file when the target requires one;
- **claim_ledger.csv**;
- route-specific protocol/search/screening/extraction/RoB/certainty/adjudication artifacts;
- **human_review_gate.json** for systematic reviews;
- completed reporting checklist and flow counts;
- **AI_USE_DISCLOSURE.md** and **protocol_deviations.md**;
- audit report and unresolved-issues register;
- **EXPERT_SIGNOFF.md** listing required clinical, information-specialist, methods, statistics, regulatory, and authorship approvals as applicable.

Use the final state **expert-signoff-ready draft + evidence package** only after every blocking route/integrity gate is complete and each remaining `not_assessed` item has a named expert owner. Otherwise use **draft awaiting expert assessment**. Acceptance, compliance, validation, publication, and downstream submission decisions remain with the named experts, authors, and target venue.
