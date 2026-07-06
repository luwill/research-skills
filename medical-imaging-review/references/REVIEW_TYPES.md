# Review Type Routing

Choose the review type before collecting literature or drafting prose. Do not call a manuscript a "systematic review" unless the methods actually support that claim.

## Decision route

| User intent | Use this route | Required method features |
|---|---|---|
| Interpret a field, compare method families, write a flagship-style "综述" | Narrative review / method survey | Exemplar-driven style, selective but justified corpus, citation integrity, explicit synthesis |
| Map what has been published, identify gaps, avoid pooled effect claims | Scoping review | PCC question, reproducible search, eligibility criteria, screening log, charting table, PRISMA-ScR reporting |
| Answer a focused effectiveness/diagnostic/performance question | Systematic review | PICOS/PIRD question, protocol, multi-database search, deduplication, duplicate screening when feasible, extraction table, risk-of-bias assessment, PRISMA 2020 reporting |
| Quantitatively pool comparable outcomes | Systematic review with meta-analysis | All systematic-review requirements plus pre-specified effect measures, heterogeneity assessment, sensitivity/subgroup analyses |
| Summarize reviews rather than primary studies | Umbrella review | Review-level eligibility, AMSTAR-2 or equivalent review-quality appraisal, overlap assessment |

## Narrative review / method survey

Use the skill's default "write with verification" workflow.

Recommended structure:

```markdown
# [Title]: [substantive subtitle]

## Key Points
## Abstract
## Introduction
## Datasets and evaluation metrics
## Methods
### Architectural priors
### Inductive priors
### Data regime
## Downstream applications
## Translation to clinical practice
## Outstanding challenges
## Future directions
## References
```

The 3-axis methods section is a strong default for AI method surveys. Adapt it when the literature is primarily diagnostic accuracy, implementation science, economics, or regulatory policy rather than method design.

## Scoping review

Use when the goal is breadth and gap mapping, not effect estimation.

Minimum project files:

```text
PROTOCOL.md
search_log.md
screening_log.csv
charting_table.csv
manuscript_draft.md
```

Required content:

- PCC question: Population, Concept, Context.
- Databases and date ranges.
- Complete search strings for each database.
- Inclusion and exclusion criteria.
- Deduplication method.
- Screening workflow and conflict handling.
- Charting variables and calibration process.
- PRISMA-ScR checklist and flow diagram.

Recommended structure:

```markdown
## Introduction
## Methods
### Protocol and eligibility criteria
### Information sources and search strategy
### Selection of sources
### Data charting
### Synthesis of results
## Results
### Search results
### Characteristics of included studies
### Evidence map
## Discussion
## Limitations
## Conclusions
```

## Systematic review

Use when the manuscript makes a focused, reproducible claim about model performance, diagnostic accuracy, patient outcomes, robustness, or clinical implementation.

Minimum project files:

```text
PROTOCOL.md
search_log.md
screening_log.csv
extraction_table.csv
risk_of_bias.md
manuscript_draft.md
```

Required content:

- PICOS or PIRD question. Use PIRD for diagnostic accuracy reviews: Participants, Index test, Reference standard, Diagnosis/target condition.
- Protocol registration or explicit explanation if registration is not possible.
- Multi-database search with exact strings, dates, filters, and platform names.
- Deduplication method.
- Screening workflow. Use two independent reviewers when the journal expects it; otherwise disclose single-reviewer screening as a limitation.
- Extraction table with study design, population, imaging modality, dataset split, reference standard, external validation, performance metrics, and clinical outcome fields where applicable.
- Risk-of-bias tool matched to the question: QUADAS-family tools for diagnostic accuracy, PROBAST/TRIPOD-family considerations for prediction models, or a domain-specific AI appraisal tool if the target journal requires it.
- Synthesis method. Do not pool metrics unless tasks, thresholds, reference standards, and validation settings are comparable enough to justify pooling.
- PRISMA 2020 checklist and flow diagram.

Recommended structure:

```markdown
## Introduction
## Methods
### Protocol and registration
### Eligibility criteria
### Information sources and search strategy
### Selection process
### Data collection process and data items
### Risk-of-bias assessment
### Synthesis methods
## Results
### Study selection
### Study characteristics
### Risk of bias
### Results of individual studies
### Synthesis of results
## Discussion
## Limitations
## Conclusions
```

## When the route changes mid-project

If the project starts as a narrative review but the manuscript later claims systematic coverage, stop and retrofit the methods before writing further. Add the missing protocol/search/screening/extraction/risk-of-bias files, or downgrade the claim back to a narrative or scoping review.
