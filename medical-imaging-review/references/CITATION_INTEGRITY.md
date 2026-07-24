# Citation and Claim Integrity Protocol

This protocol governs **references.bib**, stable working citekeys, **claim_ledger.csv**, manuscript citations, tables, figures, and evidence-package outputs.

The goal is traceability: a human verifier must be able to move from each material claim to the correct source, exact locator, dataset split, comparator, metric, uncertainty, and source role.

Use five rules. A syntactically valid citation is not necessarily an evidentially valid citation.

---

## Rule 1: Verify source identity, version, and publication status

Before adding a source to references.bib, verify:

- title;
- complete author metadata required by the selected citation style;
- journal, venue, repository, registry, regulator, or payer;
- year and publication status;
- DOI, PMID, arXiv ID, registry ID, regulator record ID, or another stable identifier;
- correction, expression-of-concern, retraction, and superseding-version status;
- relationship to companion reports or duplicate publications.

Use the publisher record, repository record, bibliographic database, registry, regulator, or payer appropriate to the source type. Crossref and PubMed are valuable metadata routes but are not mandatory for every eligible source.

A source without a DOI is not automatically broken or ineligible. Use another stable identifier and record the verification route. If metadata conflict, preserve the conflict in source notes and resolve it before using the source.

Never leave placeholder identifiers, dates, pagination, authors, URLs, or publication status in an expert-signoff package.

---

## Rule 2: Use one canonical bibliography record and a stable citekey

The canonical bibliography is **references.bib**. Draft with Pandoc citekeys:

~~~markdown
The model was evaluated on a temporally independent cohort [@surname2024-shorttopic].
~~~

Do not draft with manually assigned numeric references. Numeric or author-date formatting is a final rendering concern.

Create a citekey from:

~~~text
<normalized-first-author-surname><year>-<short-title-token>
~~~

For collisions, append a deterministic suffix derived from a stable identifier. Never use current bibliography order because order changes during revision. Once assigned, the citekey is immutable.

Every manuscript citekey must resolve to exactly one references.bib entry. Every cited bibliography entry must be represented in the evidence package. Do not create two citekeys for different reports without recording whether they share a cohort, dataset, model, or outcome.

Render final citations with Pandoc. The base command works without a custom CSL:

~~~bash
pandoc review_project/<project-id>/manuscript.md --citeproc --bibliography review_project/<project-id>/references.bib --output review_project/<project-id>/rendered/manuscript.docx
~~~

Add `--csl <verified-csl-file>` only after the user or target journal supplies a current CSL file and `review_config.yaml` records it in `citations.target_csl`.

Inspect the rendered bibliography for author truncation, title capitalization, identifiers, duplicate entries, and target-style conformance. Fix references.bib or CSL inputs; do not hand-edit rendered numbering as the source of truth.

---

## Rule 3: Reconcile manuscript, bibliography, and claim ledger

Every material factual claim must form a three-way link:

~~~text
manuscript claim
  -> stable citekey in references.bib
  -> claim-source row in claim_ledger.csv
~~~

Use the exact claim-ledger header and enum values defined in TEMPLATES.md. One row represents one claim-source pair. If three sources support one synthesis claim, create three rows with the same claim_id.

Each row must include:

- atomic claim text and claim type;
- citekey and stable source identifier;
- exact source locator;
- dataset or cohort, dataset split, and split unit when applicable;
- comparator, metric, value, unit, confidence interval or other uncertainty;
- direction;
- access type, URI, and date;
- human verifier identity or identities;
- verification status and notes.

Reconciliation checks:

1. Every manuscript citekey exists in references.bib.
2. Every precise factual, quantitative, comparative, directional, priority, regulatory, reimbursement, or availability claim has a claim-ledger row.
3. The citekey in the ledger resolves to the source actually supporting the claim.
4. The locator re-finds the evidence without relying on memory.
5. Tables, figure captions, abstracts, key points, and supplements receive the same treatment as body prose.

Do not rely on random citation spot checks as the final gate. Automated reconciliation can find missing keys and rows; source support remains a human task.

---

## Rule 4: Verify quantitative, directional, and comparative context

For any number or directional/comparative statement, verify the full context from the most informative accessible source location, normally the full results text, table, figure, supplement, or registry result:

- population and eligibility;
- dataset/cohort and exact evaluation split;
- unit of analysis, such as patient, examination, image, slice, lesion, or patch;
- comparator or reference standard;
- metric definition and threshold;
- point estimate, unit, and confidence/credible interval or other uncertainty;
- adjusted versus unadjusted estimate and adjustment set;
- time point and subgroup;
- stated direction and whether the interval supports a clear difference.

Do not copy a direction from an abstract without checking whether the abstract omits relevant qualifiers. Use the claim ledger's evidence_excerpt field for a short support note; avoid unnecessary verbatim copying.

Verification-status rules:

- **verified**: source and context support the claim at the recorded locator;
- **partially_verified**: only part of the claim is supported; rewrite before use;
- **contradicted**: source conflicts with the claim; remove or correct it;
- **inaccessible**: evidence could not be inspected at the required level;
- **superseded**: a correction, later version, or preferred report replaces it;
- **pending**: not yet checked.

Only verified rows may support precise numeric or directional prose. Abstract-only or metadata-only access cannot verify:

- internal architecture or preprocessing details;
- priority claims such as first or only;
- subgroup or adjusted-effect claims;
- exact dataset split or leakage claims unless explicitly reported there;
- precise performance numbers lacking sufficient context.

When verification is incomplete, remove the unsupported detail or state the access limitation. Do not infer missing values.

---

## Rule 5: Match the source to the claim and track dependence

Different source types support different claims:

| Claim | Appropriate source |
|---|---|
| Scientific result or clinical effectiveness | Peer-reviewed primary report, with preprint status disclosed where applicable |
| Protocol or prespecified outcome | Registry/protocol record |
| Regulatory authorization, indication, or current status | Current official jurisdiction-specific regulator record |
| Reimbursement, coding, or coverage | Current official payer/coding authority record |
| Product description | Official product documentation, clearly labeled and not treated as effectiveness evidence |
| Dataset specification | Dataset paper, repository, data dictionary, or official version record |
| Reporting completeness | Applicable reporting guideline used as a descriptive framework, not a substitute for risk-of-bias assessment |

Regulatory authorization, reimbursement, and clinical effectiveness are separate claims and require separate ledger rows and source classes. Verify regulator and payer status again immediately before expert sign-off.

Track scientific dependence:

- multiple reports from one study;
- reused public test sets;
- overlapping institutional cohorts;
- repeated thresholds or outcomes;
- model updates derived from the same development data;
- conference/preprint/journal versions of the same work.

Record these relationships in **extraction/cohort_linkage.csv** or REVIEW_CONTEXT.md. Multiple papers are not automatically independent confirmations.

---

## Human verification requirements

Narrative, method-survey, and scoping projects must identify the human responsible for each verified material claim in verified_by.

For systematic projects:

- critical outcome/performance data require two distinct human extraction decisions in extraction/critical_data.csv;
- the human IDs must match traceable screening, extraction, risk-of-bias, and adjudication artifacts;
- AI agents may assist discovery or checking but cannot occupy a human verifier slot;
- a disagreement remains unresolved until documented adjudication.

Do not change verifier IDs merely to satisfy a gate. The evidence package must preserve original decisions, conflicts, and resolutions.

---

## Integration by phase

| Phase | Required integrity work |
|---|---|
| Context/protocol | Define citation syntax, source roles, reviewer policy, and critical claims |
| Discovery/search | Create source records, immutable exports, and stable identifiers |
| Collection | Assign citekeys, verify metadata/version/status, start claim ledger |
| Selection/extraction | Track cohort/report relationships and dual verification where required |
| Drafting | Link every material claim to citekey and ledger locator |
| QA | Exhaustively reconcile manuscript, references.bib, ledger, and route artifacts |
| Expert-signoff packaging | Render with Pandoc/CSL; recheck official current claims and unresolved statuses |

---

## Auditor use and limitations

Run the route-aware auditor:

~~~bash
python3 <skill_dir>/scripts/audit_manuscript.py review_project/<project-id>/manuscript.md --route <narrative|method-survey|scoping|systematic> --project-dir review_project/<project-id> --fail-on critical --output review_project/<project-id>/review_outputs/audit_report.md
~~~

The --profile JSON path is optional.

The auditor may detect missing citekeys, missing project artifacts, placeholders, duplicate identifiers, malformed ledger rows, or an incomplete systematic human gate. It cannot prove that a source supports a claim, that a risk-of-bias judgment is correct, or that a review is compliant.

Claim reconciliation is deliberately strict and one-directional. The auditor normalizes each material prose sentence (lowercase, citation and citekey markers removed, collapsed to word tokens) and requires an exact-token match against a `claim_text` in `claim_ledger.csv`. A paraphrased or unlogged claim is surfaced as a finding, never silently passed, so keep each ledger `claim_text` a faithful copy of the sentence it supports. Expect flags on prose that drifts from the ledger — reconcile the two rather than loosening the check.

Each finding carries a stable machine-readable `category` (for example `unverified_claim`, `mutable_numeric_citation`, `inline_working_bibliography`, `route_mismatch`); consume that field, not the human-readable message text, when scripting on the JSON output. A `--fail-on` threshold returns exit code 1 on a failing gate, 2 on an input error, and 0 otherwise.

Zero automated findings must still leave substantive source support, methods correctness, and expert judgments as **not_assessed** until humans complete them.

---

## Failure response

When a failure is found:

1. Freeze forward drafting for the affected claim or artifact.
2. Preserve the original source, decision, and conflict record.
3. Correct references.bib, claim_ledger.csv, manuscript text, and affected tables/figures together.
4. Search for the same error pattern in related claims or reports.
5. Record material corrections in IMPLEMENTATION_PLAN.md or the adjudication/deviation log.
6. Re-run reconciliation and the route-aware audit.

After all blocking citation gates are complete, the deliverable may be labeled an expert-signoff-ready draft and evidence package with explicit unresolved items. Otherwise label it a draft awaiting expert assessment; publication and methodological approval remain external human decisions.
