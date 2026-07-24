# Standards for Medical Imaging AI Reviews

Select standards after freezing the review route. Record the exact title, version, URL, access date, applicability, and any journal-specific replacement in <project_dir>/review_config.yaml, where <project_dir> matches review_project/<topic-slug>-<YYYYMMDD-HHMMSS>-<8hex>/.

## Contents

- Four distinct standards layers
- Route matrix
- Conduct guidance
- Review reporting guidance
- Primary-study reporting frameworks
- Risk-of-bias tools
- Certainty frameworks
- Human and AI governance
- Official sources

## Four distinct standards layers

Do not collapse these layers:

| Layer | Question answered | Examples |
|---|---|---|
| Conduct guidance | How should the review be designed and carried out? | JBI Manual for Evidence Synthesis; Cochrane handbooks |
| Review reporting guidance | What must the review report transparently? | PRISMA 2020, PRISMA-ScR, PRISMA-S, PRISMA-DTA, SWiM |
| Primary-study reporting framework | What did each included primary study report? | CLAIM 2024, TRIPOD+AI |
| Risk of bias and certainty | How trustworthy is each study, and how certain is the body of evidence? | QUADAS-3, question-matched RoB tools, GRADE |

Reporting completeness is not risk of bias. A study can report every CLAIM or TRIPOD+AI item and still have high risk of bias. Risk-of-bias judgments are not certainty judgments; certainty is assessed across the body of evidence for a specified outcome or conclusion.

## Route matrix

| Route | Conduct | Review reporting | Primary-study reporting | Risk of bias and certainty |
|---|---|---|---|---|
| narrative or method-survey | Transparent scope and selection rationale; use topic-appropriate methodological guidance if claimed | Target-journal requirements; no systematic label | Use CLAIM 2024 or TRIPOD+AI fields only when relevant to extraction | Not automatic; do not imply formal appraisal or certainty grading unless performed |
| scoping | JBI scoping-review guidance | PRISMA-ScR; use PRISMA-S items to make searches reproducible | Use relevant fields for charting, not as a quality score | Critical appraisal is protocol-dependent; GRADE is normally not used for evidence mapping |
| systematic | Question-matched JBI or Cochrane conduct guidance; qualitative synthesis only | PRISMA 2020 plus PRISMA-S; add PRISMA-DTA for diagnostic-accuracy reviews; use SWiM when its scope fits | Use CLAIM 2024 and/or TRIPOD+AI to capture reporting details | Use a question-matched RoB tool and GRADE when the review makes certainty-of-evidence conclusions |

Meta-analysis and umbrella-review standards are outside this skill. If statistical pooling or review-of-reviews methods are required, hand off before analysis.

## Conduct guidance

### JBI Manual for Evidence Synthesis

Use the JBI chapter matched to the review type, especially for scoping-review question framing, protocol development, searching, screening, charting, and descriptive mapping. Do not treat JBI conduct guidance as a reporting checklist.

### Cochrane handbooks

Use the question-matched Cochrane handbook or chapter for systematic review conduct, including scope, eligibility, search, study selection, data collection, synthesis without statistical pooling, risk of bias, and interpretation. The intervention handbook is not a universal substitute for diagnostic-accuracy or other question-specific guidance.

For all formal scoping and systematic routes, pre-specify screening, extraction or charting, conflict resolution, protocol deviations, AI use, and human oversight.

## Review reporting guidance

### PRISMA 2020

Use as the base reporting guideline for a systematic review with qualitative synthesis. PRISMA is a reporting guideline, not a conduct manual or risk-of-bias tool.

### PRISMA-ScR

Use for scoping-review reporting, including objectives, eligibility, information sources, selection, charting, evidence mapping, limitations, and flow.

### PRISMA-S

Use to report literature searches reproducibly: databases and platforms, full search strategies, dates, limits, deduplication, supplementary methods, and search updating. Apply it alongside PRISMA 2020 and use compatible items alongside PRISMA-ScR.

### PRISMA-DTA

Add for a systematic review of diagnostic test accuracy. It is a review reporting extension; it does not replace diagnostic-accuracy conduct guidance, QUADAS-3, or certainty assessment.

### SWiM

Use Synthesis Without Meta-analysis reporting guidance when its intervention-review scope fits the planned qualitative or structured synthesis. Do not use SWiM as permission for vote counting, informal pooling, or unplanned synthesis.

### Protocol reporting

Use PRISMA-P or the target registry or journal protocol requirements when applicable. Preserve a timestamped protocol and log amendments even when formal registration is unavailable.

## Primary-study reporting frameworks

### CLAIM 2024

Use the Checklist for Artificial Intelligence in Medical Imaging 2024 Update to extract reporting completeness for AI medical-imaging primary studies, including data provenance, reference standard, model development, evaluation, external validation, availability, and clinical context.

CLAIM 2024 is a primary-study reporting framework. Do not use it as a risk-of-bias score, certainty framework, or review reporting checklist.

### TRIPOD+AI

Use TRIPOD+AI for primary studies that develop or evaluate diagnostic or prognostic prediction models using regression or machine-learning methods. Extract model-development, validation, calibration, performance, and intended-use reporting as applicable.

TRIPOD+AI is a primary-study reporting guideline. Do not substitute it for PROBAST-family risk-of-bias assessment, GRADE, or PRISMA.

## Risk-of-bias tools

Choose the tool from the review question and eligible study designs before extraction. Do not choose a tool because its acronym mentions AI.

| Question or study design | Preferred direction |
|---|---|
| Diagnostic test accuracy | QUADAS-3; use an older or comparative QUADAS-family tool only when the frozen protocol or target journal justifies it |
| Diagnostic or prognostic prediction models | Current PROBAST-family tool appropriate to the model and review question |
| Randomized intervention studies | RoB 2 or the question-specific current tool |
| Non-randomized intervention studies | ROBINS-I or the question-specific current tool |
| Prognostic-factor studies | QUIPS or the protocol-specified current tool |
| Pure segmentation or method-comparison evidence | Pre-specify a defensible domain framework covering selection, reference standard or annotation, split integrity, leakage, comparability, and external validation; do not label an ad hoc checklist as a validated RoB tool |

QUADAS-3 is a risk-of-bias and applicability tool for diagnostic-accuracy studies. It is not a reporting checklist and does not assess certainty across studies.

Record signaling-question support, domain judgments, overall rules, reviewer identities, conflicts, consensus, and deviations. Risk-of-bias judgments require human assessment and adjudication.

## Certainty frameworks

Use GRADE when the systematic review makes outcome-level claims about certainty or confidence in an evidence body. Use the GRADE approach matched to the question, including diagnostic test accuracy when applicable.

Do not infer certainty from:

- the number of studies
- reporting-checklist adherence
- average risk-of-bias score
- statistical significance
- agreement among LLM agents

Pre-specify the starting point, domains, upgrading or downgrading rationale, and decision rules. Certainty judgments require human approval. Scoping reviews normally map evidence rather than grade certainty; narrative reviews must not use GRADE language unless a documented assessment was performed.

## Human and AI governance

For formal scoping and systematic work:

- LLM agents do not count as independent human screeners, extractors, risk-of-bias reviewers, or certainty assessors.
- Record two-human screening and two-human extraction or verification roles when required by the protocol or conduct guidance.
- Record the human adjudicator and the resolution of conflicts.
- Preserve screening decisions in <project_dir>/screening/screening_decisions.csv.
- Log each AI tool, task, date, human oversight step, validation procedure, limitation, and correction in <project_dir>/AI_USE_DISCLOSURE.md.
- Disclose AI assistance according to the target journal and institution.
- Label AI-produced screening, extraction, risk-of-bias, and certainty outputs as provisional until the required human gate is complete.

## Official sources

Verify the current version at project start:

- PRISMA 2020: https://www.prisma-statement.org/prisma-2020
- PRISMA-ScR: https://www.prisma-statement.org/scoping
- PRISMA-S: https://www.prisma-statement.org/prisma-search
- PRISMA-DTA: https://www.prisma-statement.org/dta
- PRISMA extensions and SWiM routing: https://www.prisma-statement.org/extensions
- JBI Manual for Evidence Synthesis: https://jbi-global-wiki.refined.site/space/MANUAL
- Cochrane handbooks: https://training.cochrane.org/handbooks
- CLAIM 2024: https://www.equator-network.org/reporting-guidelines/checklist-for-artificial-intelligence-in-medical-imaging-claim-a-guide-for-authors-and-reviewers/
- TRIPOD+AI: https://www.equator-network.org/reporting-guidelines/tripod-statement/
- QUADAS-3: https://www.bristol.ac.uk/population-health-sciences/projects/quadas/quadas-3/quadas-3-tool/
- GRADE Working Group: https://www.gradeworkinggroup.org/
