# Evidence-Integrity Failure Patterns in Medical Imaging Reviews

Use these patterns during collection, extraction, drafting, QA, and expert sign-off. They are failure modes to investigate, not claims about how often an error occurs.

Detection can be automated in part; resolution requires source-level and route-level human review.

---

## Pattern 1: Real title, wrong source identity

The paper or record exists, but authors, venue, year, identifier, version, or publication status are wrong.

### Signals

- generic or incomplete author metadata;
- preprint and journal version treated as independent studies;
- DOI resolves to a different title;
- registry, conference, and journal reports conflated;
- correction, expression of concern, or retraction not reflected;
- one source appears under multiple citekeys.

### Required fix

Verify against the appropriate publisher/repository/registry record, update references.bib, preserve version relationships, and update every linked claim-ledger row. A DOI is not mandatory when another stable identifier exists.

---

## Pattern 2: Number detached from its evaluation context

A reported value is real or plausible, but its population, dataset split, unit of analysis, comparator, threshold, metric definition, or uncertainty is wrong or missing.

### Signals

- a value appears without internal/external/temporal/prospective test status;
- patient-, image-, slice-, lesion-, or patch-level units are mixed;
- validation and test sets are conflated;
- percent and proportion are confused;
- only a point estimate is reported when the source provides an interval;
- adjusted and unadjusted effects are mixed.

### Required fix

Verify the full results table/figure/supplement and populate data_split, split_unit, comparator, metric, estimate, unit, uncertainty_interval, and source_locator in claim_ledger.csv. Remove the detail if it cannot be verified.

---

## Pattern 3: Direction, comparator, or uncertainty reversal

The source is relevant, but higher/lower, better/worse, positive/negative, or no-clear-difference language is reversed or overstated.

### Signals

- the comparator changes between source and manuscript;
- a confidence interval compatible with no clear difference is described as superiority;
- subgroup direction is generalized to the full population;
- unadjusted direction is reported as an adjusted result;
- abstract wording conflicts with the full results.

### Required fix

Check the estimand, comparator, interval, adjustment set, subgroup, and time point at the exact source locator. Record direction and uncertainty in the ledger. Use verified, bounded language; do not copy abstract direction without context.

---

## Pattern 4: Source-role laundering

A source supports one type of fact but is cited as evidence for another.

### Common confusions

- product documentation used as clinical-effectiveness evidence;
- regulatory authorization treated as outcome benefit;
- reimbursement/coding treated as regulatory authorization;
- a registry/protocol used as if it reports final results;
- a reporting checklist treated as a risk-of-bias tool;
- a secondary review used for a precise primary-study result when the primary report is available.

### Required fix

Create separate claim-ledger rows for scientific results, protocol facts, regulatory status, reimbursement status, and product descriptions. Use official current regulator/payer records for current status and peer-reviewed primary evidence for clinical results.

---

## Pattern 5: Placeholder, stale, or unverifiable current fact

An unfinished token or old status survives into the evidence package.

### Signals

- placeholder identifiers, authors, dates, page ranges, URLs, figures, tables, or values;
- future tense for an already completed search;
- regulator or reimbursement status without jurisdiction, source, and checked date;
- dataset size/version copied from memory;
- unresolved status represented as confirmed.

### Required fix

Replace the placeholder with verified information or explicitly report not_verified/not_reported. Recheck current regulatory and reimbursement records immediately before expert sign-off.

---

## Pattern 6: Citekey, bibliography, and claim-ledger drift

The manuscript citekey resolves, but not to the source supporting the sentence, or the supporting claim has no traceable ledger row.

### Signals

- manuscript citekey absent from references.bib;
- duplicate bibliography records;
- claim citekey differs between prose and table;
- source locator does not contain the stated result;
- material claim has no claim_id;
- manual numeric references appear in working manuscript text;
- citekey renamed after drafting.

### Required fix

Exhaustively reconcile manuscript.md, references.bib, claim_ledger.csv, tables, figures, and supplements. Preserve stable citekeys and render final numbering only through Pandoc/CSL.

---

## Pattern 7: False independence and dataset leakage

Multiple reports, models, or papers are treated as independent confirmations even though they reuse participants, datasets, test sets, labels, or development pipelines.

### Signals

- many studies evaluate on the same public benchmark;
- preprint, conference, and journal versions all appear in a count;
- companion analyses share a cohort and date range;
- patient overlap or slice-level splitting is unclear;
- test set influenced model selection or hyperparameter tuning;
- foundation-model pretraining may contain the evaluation benchmark.

### Required fix

Populate extraction/cohort_linkage.csv, identify the report/study/cohort unit, document split integrity and contamination uncertainty, and avoid double counting. Paper count alone does not establish independent replication.

---

## Pattern 8: Metric, formula, or unit corruption

A familiar metric is defined, calculated, transformed, or interpreted incorrectly.

### Signals

- overlap, distance, calibration, discrimination, and clinical-utility metrics are mixed;
- mean Hausdorff distance is called Hausdorff distance;
- macro, micro, per-class, per-patient, and pooled metrics are not distinguished;
- threshold-dependent and threshold-free summaries are conflated;
- confidence intervals, standard deviations, and interquartile ranges are interchanged;
- effect measures or units change between extraction and prose.

### Required fix

Verify the definition against the original method/source and the study-specific implementation. Record source locator, aggregation, threshold, unit, and uncertainty. A style profile may influence equation placement, but never its definition.

---

## Pattern 9: Internal contradiction across artifacts

The same study, dataset, product, protocol, or conclusion is described differently in different project files.

### Signals

- participant count or center count changes by section;
- the same dataset is both internal and external;
- claim ledger and extraction table disagree;
- regulatory and reimbursement columns contain the same assertion;
- manuscript describes a conflict as resolved while adjudication log remains open;
- protocol version and deviation log disagree.

### Required fix

Use stable entity IDs and canonical descriptions in REVIEW_CONTEXT.md. Reconcile every occurrence and preserve the adjudication or deviation record explaining the final value.

---

## Pattern 10: Route, method, human-review, or AI-use overclaim

The manuscript label or conclusion outruns the project artifacts.

### Signals

- narrative or method-survey route claims exhaustive or systematic coverage;
- scoping route estimates effects or claims efficacy;
- systematic language appears without protocol, exact searches, selection records, extraction, appraisal, certainty, and flow artifacts;
- systematic Results prose exists while human_review_gate.json is missing or incomplete;
- AI agents are listed as independent human reviewers;
- protocol deviations or AI assistance are omitted;
- zero automated findings are described as factual or methodological approval;
- unsupported quantitative pooling or overview-of-reviews language appears in the supported-route project.

### Required fix

Stop forward writing. Restore the route-appropriate artifacts or narrow the manuscript claim. For systematic reviews, satisfy the exact human_review_gate.json contract in TEMPLATES.md; missing human work cannot be waived as a limitation. Disclose AI assistance and protocol deviations.

---

## Writing-quality signals are not hallucination proof

Vague, repetitive, promotional, or formulaic language may deserve revision, but no phrase is automatically an AI error. Do not ban cautious language merely for sounding generic. Ask instead:

- Is the claim supported?
- Does strength match risk of bias, uncertainty, consistency, directness, and applicability?
- Is the population/comparator/metric visible?
- Is interpretation clearly separated from fact?

Style-profile warnings never replace evidence checks and never force a strong conclusion.

---

## Self-check workflow

### During collection

1. Verify identity/version/status and assign a stable citekey.
2. Record access route and source role.
3. Start cohort/report linkage.

### During extraction

4. Capture dataset split, split unit, comparator, metric, unit, uncertainty, direction, and source locator.
5. Preserve independent human decisions where required.
6. Log conflicts instead of silently averaging or choosing values.

### During drafting

7. Create or update a claim-ledger row for every material claim.
8. Use only verified quantitative/directional rows.
9. Reconcile prose, tables, figures, abstract, and key points.
10. Bound language to the selected route.

### Before expert sign-off

11. Check corrections/retractions/versions and current official records.
12. Reconcile cohort overlap and unresolved conflicts.
13. Confirm protocol deviations and AI assistance disclosure.
14. Validate systematic human_review_gate.json where applicable.
15. Run the route-aware auditor.

~~~bash
python3 <skill_dir>/scripts/audit_manuscript.py review_project/<project-id>/manuscript.md --route <narrative|method-survey|scoping|systematic> --project-dir review_project/<project-id> --fail-on critical --output review_project/<project-id>/review_outputs/audit_report.md
~~~

The --profile JSON path is optional. Zero automated findings still leaves substantive checks as not_assessed until completed by humans or named experts.
