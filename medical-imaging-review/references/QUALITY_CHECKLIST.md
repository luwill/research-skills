# Quality Checklist for Medical Imaging AI Reviews

Use this checklist at route selection, after search/selection/extraction, during drafting, before automated audit, and before expert sign-off.

The checklist separates:

- **blocking integrity gates**: evidence or method requirements that cannot be waived by style;
- **route gates**: artifacts required by narrative, method-survey, scoping, or systematic methods;
- **profile warnings**: target-journal or exemplar preferences;
- **not_assessed items**: substantive judgments automation cannot make.

The target output may be labeled **expert-signoff-ready draft and evidence package** only after the blocking gates below are complete; otherwise it remains a draft awaiting expert assessment.

---

## Project identity and collision safety — blocking

- [ ] All review artifacts are under review_project/<project-id>/.
- [ ] Project ID matches <topic-slug>-<YYYYMMDD-HHMMSS>-<8hex>.
- [ ] The project was created by scripts/init_review_project.py and the generated target was not reused.
- [ ] review_config.yaml contains the same immutable project ID, path, and route.
- [ ] REVIEW_CONTEXT.md states the question, scope, route claim boundary, terminology, and unresolved issues.
- [ ] Existing review projects were not silently reused, merged, overwritten, or deleted.

---

## Citation and claim integrity — blocking

- [ ] references.bib is the single canonical bibliography.
- [ ] Working manuscript citations use stable Pandoc citekeys.
- [ ] Citekeys are immutable and collision-safe; manual numeric working citations are absent.
- [ ] Every manuscript citekey resolves to exactly one bibliography entry.
- [ ] Every material claim has one or more claim_ledger.csv rows.
- [ ] Ledger rows use the initializer header and contain source_locator, population_or_dataset, data_split, split_unit, comparator, metric, estimate, unit, uncertainty_interval, direction, access_level, source_role, access_uri, accessed_at, verification_status, verified_by, verified_at, and notes as applicable.
- [ ] Precise numeric and directional claims use only verification_status=verified rows.
- [ ] Critical systematic data preserve two distinct human extraction decisions in extraction/critical_data.csv.
- [ ] Abstract-only or metadata-only access is not used for architecture internals, priority, subgroup, adjusted-effect, or insufficiently contextualized performance claims.
- [ ] Corrections, expressions of concern, retractions, versions, companion reports, shared cohorts, and reused test sets were checked.
- [ ] A missing DOI did not cause automatic exclusion when another stable identifier exists.
- [ ] Tables, figure captions, abstract, key points, and supplements are reconciled with the same rigor as body prose.

See CITATION_INTEGRITY.md.

---

## Route and search boundary — blocking

- [ ] Route is exactly narrative, method-survey, scoping, or systematic.
- [ ] Quantitative pooling or an overview-of-reviews request was stopped and handed to a specialist workflow.
- [ ] Route was chosen before collection; after collection began, any different route used a newly initialized project rather than an in-place protocol/deviation change.
- [ ] No route inherited a default paper count, recency window, language, publication type, or study-design filter.
- [ ] Every deliberate search limit has a question-specific rationale and consequence.

### Narrative and method-survey

- [ ] search/narrative_exploration_log.csv records source, query/navigation, date, result reference, decision, and rationale.
- [ ] search/selection_rationale.md discloses discovery routes, selection logic, limits, and blind spots.
- [ ] Manuscript language describes a transparent, non-exhaustive exploration.
- [ ] Important counterevidence, negative findings, validation failures, leakage risks, and equity limitations were actively sought.
- [ ] Narrative or method-survey text does not claim systematic/comprehensive coverage or PRISMA-style inclusion.

### Scoping

- [ ] PCC or another justified scoping framework is explicit.
- [ ] Protocol and exact database/platform strategies exist.
- [ ] Immutable exports and exact strategies exist, and search/search_log.csv, search/deduplication_log.csv, screening/screening_decisions.csv, screening/full_text_exclusions.csv, screening/calibration_log.md, adjudication/conflict_log.csv, and extraction/charting_table.csv are populated.
- [ ] Reviewer number, independence, automation, calibration, and conflict handling are reported.
- [ ] Evidence map/charting answers the protocol question without estimating effects.
- [ ] PRISMA-ScR checklist and flow counts are completed.
- [ ] AI assistance and protocol deviations are disclosed.

### Systematic

- [ ] Protocol/registration status and amendments are transparent.
- [ ] Exact search strategies, sources, platforms, dates, limits, peer review, raw exports, deduplication, and update search are documented.
- [ ] Two distinct humans independently screened full texts; title/abstract screening also follows the protocol-defined dual process.
- [ ] Two distinct humans independently extracted critical data.
- [ ] Two distinct humans independently assessed risk of bias with the design-matched tool.
- [ ] Original decisions and all conflicts/adjudications are preserved.
- [ ] Study/report/cohort linkage prevents duplicate counting and pseudo-replication.
- [ ] Certainty and reporting-bias methods/results are present when applicable.
- [ ] PRISMA checklist, flow counts, and protocol deviations are complete.
- [ ] human_review_gate.json satisfies the exact TEMPLATES.md contract.
- [ ] human_review_gate.json status is complete and its reviewer_ids are two or more distinct, non-empty human IDs.
- [ ] Gate evidence paths remain screening/screening_decisions.csv, extraction/critical_data.csv, risk_of_bias/assessments.csv, adjudication/conflict_log.csv, and AI_USE_DISCLOSURE.md.
- [ ] AI assistance is disclosed and no AI identity occupies a human reviewer or adjudicator slot.

An incomplete systematic gate is blocking. It cannot be downgraded to a limitation.

---

## Study appraisal and synthesis — blocking

- [ ] Risk-of-bias tool matches the primary-study design and review question.
- [ ] Reporting-completeness guidelines are not presented as risk-of-bias tools.
- [ ] Appraisal judgments include source locators, rationale, reviewer IDs, and adjudication status.
- [ ] External validation terminology matches the source and the protocol definition.
- [ ] Dataset split and unit of analysis are visible beside performance values.
- [ ] Cross-study metrics are not ranked as comparable without comparable cohort, split, unit, reference standard, threshold, and evaluation conditions.
- [ ] Multiple reports, model versions, thresholds, outcomes, and shared datasets are handled explicitly.
- [ ] Synthesis statements are bounded by the narrative/method-survey corpus, scoping map, or systematic protocol and certainty judgments.
- [ ] Conclusions distinguish absence of evidence, evidence of no clear difference, and evidence of harm or inferiority.
- [ ] Clinical effectiveness is not inferred from regulatory authorization, reimbursement, product documentation, or benchmark accuracy alone.

---

## Regulatory, reimbursement, and commercial claims — blocking

- [ ] Regulatory status and reimbursement status occupy separate fields/columns.
- [ ] Each regulatory claim uses a current official jurisdiction-specific regulator record.
- [ ] Each reimbursement/coding/coverage claim uses a current official payer or coding-authority record.
- [ ] Regulatory and reimbursement facts have access dates and are rechecked immediately before expert sign-off.
- [ ] Product documentation is labeled as such and is not used as clinical-effectiveness evidence.
- [ ] Peer-reviewed clinical evidence is cited separately.
- [ ] Unverified current status is reported as not_verified, not inferred.

---

## AI assistance, privacy, and human authority — blocking

- [ ] AI_USE_DISCLOSURE.md names tools/models, versions or dates, providers, data shared, tasks, human decision-makers, checks, and limitations.
- [ ] Sensitive or restricted source content was handled according to access, privacy, and license requirements.
- [ ] AI assistance did not replace required human screening, extraction, risk-of-bias assessment, adjudication, or expert sign-off.
- [ ] Material AI errors and corrections are logged.
- [ ] protocol_deviations.md records timing, rationale, impact, corrective action, and human approval for every deviation.

---

## Style and presentation — profile-driven warnings only

Evaluate these only against style_profile.json or current target-journal instructions:

- [ ] Heading depth and numbering.
- [ ] Section order and labels.
- [ ] Key-points presence and length.
- [ ] Equation placement and notation.
- [ ] Box, table, and figure count.
- [ ] Caption length and format.
- [ ] Vendor/product placement.
- [ ] Citation density and grouping.
- [ ] Paragraph length and rhetorical pattern.
- [ ] Terminology, spelling, and abbreviation style.

These are warnings unless a documented target requirement says otherwise. There is no universal ban on numbered headings, H4 headings, equations in body text, vendor names in prose, cautious wording, or any fixed number of tables, figures, boxes, citations, or conclusion sentences.

Style warnings cannot block evidence work and cannot force stronger language than the evidence supports.

---

## Automated audit

Run:

~~~bash
python3 <skill_dir>/scripts/audit_manuscript.py review_project/<project-id>/manuscript.md --route <narrative|method-survey|scoping|systematic> --project-dir review_project/<project-id> --fail-on critical --output review_project/<project-id>/review_outputs/audit_report.md
~~~

The --profile argument is optional and accepts a JSON profile path. Omit it when no explicit profile exists.

Required auditor semantics:

- Individual findings may use **critical/high/medium/low** severities.
- The global `gate_status` is only **fail**, **warning**, or **not_assessed**; it is never `pass`.
- Profile-dependent findings are warning-only and cannot fail the gate.
- Factual support, full-text interpretation, search adequacy, appraisal correctness, synthesis validity, certainty, and other substantive judgments remain **not_assessed** unless the appropriate humans complete them outside the auditor.

Zero automated findings must still report substantive checks as not_assessed. The phrase no findings must not be rendered as compliant, validated, approved, or factually correct.

---

## Evidence-package inventory

- [ ] review_config.yaml
- [ ] REVIEW_CONTEXT.md
- [ ] IMPLEMENTATION_PLAN.md
- [ ] PARADIGM.md and optional style_profile.json
- [ ] manuscript.md and rendered preview
- [ ] references.bib and, when required, a current verified target CSL file
- [ ] claim_ledger.csv
- [ ] route-specific search/selection/extraction/appraisal artifacts
- [ ] human_review_gate.json for systematic route
- [ ] reporting checklist and flow counts where applicable
- [ ] AI_USE_DISCLOSURE.md
- [ ] protocol_deviations.md
- [ ] audit report with not_assessed items
- [ ] unresolved-issues register
- [ ] EXPERT_SIGNOFF.md

---

## Expert sign-off

Before handoff, name the people or roles still required to review:

- clinical/domain interpretation;
- information retrieval/search;
- evidence-synthesis methods;
- statistics, if any quantitative analysis appears;
- risk of bias and certainty;
- regulatory/reimbursement claims, if present;
- authorship, conflicts, funding, data/code availability, and journal requirements.

Use the label **expert-signoff-ready draft + evidence package** only after every blocking integrity and route gate above is complete and all `not_assessed` items have a named expert owner for sign-off. Otherwise label the output **draft awaiting expert assessment** and list the unresolved gates. Approval, compliance, validation, publication, and submission decisions remain with the named humans and target journal.
