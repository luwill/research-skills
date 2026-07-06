# Reporting Standards for Medical Imaging AI Reviews

Use this file after selecting the review type in REVIEW_TYPES.md. Reporting standards do not replace judgment; they define the minimum methods transparency expected for the manuscript's claim.

## Standard selection

| Manuscript claim | Required or default standard | Use for |
|---|---|---|
| Systematic review or meta-analysis | PRISMA 2020 | Search, screening, selection, synthesis, flow diagram, checklist |
| Scoping review | PRISMA-ScR | Mapping evidence, charting variables, identifying gaps |
| Protocol for a systematic review | PRISMA-P or journal protocol instructions | Pre-specifying question, eligibility, search, outcomes, bias tools |
| Diagnostic accuracy review | PRISMA 2020 plus QUADAS-3 or journal-specified QUADAS-family risk-of-bias assessment | Index test vs reference standard, sensitivity/specificity/AUC claims |
| AI medical-imaging primary-study appraisal | CLAIM 2024 | Imaging AI reporting completeness: data, model, validation, code, clinical context |
| Prediction/prognostic model review | TRIPOD+AI / PROBAST-family considerations | Prediction model development, validation, calibration, transportability |
| Umbrella review | AMSTAR-2 or journal-required review appraisal | Quality appraisal of included reviews |

Check the target journal instructions before submission. If a journal specifies a newer variant or extension, follow the journal.

## Minimum extraction fields for AI imaging reviews

For each included study, capture:

- Bibliographic metadata: title, first author, year, DOI/PMID/arXiv ID.
- Imaging context: modality, anatomy, task, acquisition setting, scanner/vendor if relevant.
- Data provenance: country, centers, number of patients, number of images or studies, inclusion/exclusion criteria.
- Ground truth: reference standard, annotator type and count, adjudication method, inter-reader information if reported.
- Data split: training/validation/test sizes, patient-level split status, external validation status.
- Model: architecture family, key inductive priors, pretraining/foundation-model use, input representation.
- Metrics: Dice/IoU/HD95 for segmentation; sensitivity/specificity/AUC/PPV/NPV for diagnosis; calibration metrics for prediction; confidence intervals if available.
- Leakage risk: duplicated patients, slice-level split, test-set tuning, public-test leakage, benchmark contamination.
- Generalizability: external site, scanner/protocol shift, demographic subgroup analysis, failure modes.
- Clinical translation: deployment setting, reader study, workflow impact, time/cost, regulatory status if applicable.
- Availability: code, weights, data, license, reproducibility package.

## Risk-of-bias matching

| Question type | Preferred appraisal focus |
|---|---|
| Diagnostic accuracy | Patient selection, index test conduct, reference standard, flow/timing; use QUADAS-3 when possible, or QUADAS-2/QUADAS-C when the protocol, target journal, or comparative design requires it |
| Prediction/prognosis | Participant selection, predictors, outcome definition, analysis, calibration, validation; use TRIPOD+AI / PROBAST-family concepts |
| Segmentation method survey | Dataset representativeness, annotation reliability, split integrity, external validation, benchmark comparability |
| Clinical implementation | Selection bias, workflow integration, outcome definition, confounding, monitoring and drift |
| Equity/fairness | Subgroup availability, subgroup performance, missingness, measurement bias, deployment population mismatch |

## Claims that require methods support

- Do not write "systematic review" unless search strings, databases, screening, eligibility criteria, and flow counts are documented.
- Do not write "meta-analysis" unless pooling methods, comparable outcomes, and heterogeneity handling are documented.
- Do not claim "external validation" unless the test set is institutionally, temporally, geographically, or operationally independent as stated by the source.
- Do not compare headline metrics across studies as if they share the same test set, annotation standard, or threshold.
- Do not treat regulatory clearance, vendor materials, or reimbursement codes as clinical-effectiveness evidence.

## Useful official sources

- PRISMA 2020: https://www.prisma-statement.org/prisma-2020
- PRISMA-ScR: https://www.prisma-statement.org/scoping
- EQUATOR Network reporting guideline library: https://www.equator-network.org/
- CLAIM: https://www.equator-network.org/reporting-guidelines/checklist-for-artificial-intelligence-in-medical-imaging-claim-a-guide-for-authors-and-reviewers/
- TRIPOD: https://www.tripod-statement.org/
- QUADAS project: https://www.bristol.ac.uk/population-health-sciences/projects/quadas/
- PROSPERO: https://www.crd.york.ac.uk/prospero/
