# Project File Templates

Templates for `CLAUDE.md`, `IMPLEMENTATION_PLAN.md`, route-specific protocol files, and standard tables. v3.1 updates: choose review type first; use the **3-axis structure** as a narrative/method-survey default, not as a universal rule. Bibliography target removed.

---

## CLAUDE.md Template

```markdown
# [Topic] Literature Review Writing Guidelines

## Project info
- **Topic**: [specific topic]
- **Review type**: [narrative / method survey / scoping / systematic / systematic + meta-analysis / umbrella]
- **Target journals**: [Tier 1: e.g., Nat Rev Cardiol] / [Tier 2: e.g., JACC Cardiovasc Imaging] / [Tier 3: e.g., Eur Radiol]
- **Reporting standards**: [none / PRISMA 2020 / PRISMA-ScR / CLAIM / TRIPOD+AI / QUADAS-family / other]
- **Paradigm spec**: see PARADIGM.md (Phase 0 output)
- **Review-type route**: see references/REVIEW_TYPES.md
- **Reporting standards**: see references/REPORTING_STANDARDS.md
- **Citation integrity**: see references/CITATION_INTEGRITY.md
- **Hallucination self-check**: see references/HALLUCINATION_PATTERNS.md

## Terminology Standardization

| Unified Term | Avoid Using |
|---|---|
| coronary CT angiography (CCTA) | cardiac CT, CT angio, CTA (ambiguous) |
| centerline (anatomical structure) | midline, vessel line |
| SCCT coronary segment labels | AHA 17-segment myocardium when referring to coronary artery labels |
| [add domain-specific terms] | [variants to avoid] |

## Canonical Paper / Dataset Descriptions

To prevent internal inconsistency (HALLUCINATION_PATTERNS.md ▸ Pattern 9), lock in canonical descriptions:

| Paper / Dataset | Canonical description |
|---|---|
| ImageCAS | 1000 cases, single-center, CCTA artery segmentation |
| TransCC (Xu et al.) | 3 authors: Chenchu Xu, Meng Li, Xue Wu; Dice 0.730 / IoU 0.582 on ImageCAS |
| FISH&CHIPS | NHS national CT-FFR implementation program; publication: Fairbairn TA et al. Nat Med 2025;31(6):1903-1910 |
| [add high-value papers] | [verified description] |

## Reference Sources

### Methodological preprints
Search queries used:
- "[topic] segmentation transformer" (cs.CV, eess.IV)
- "[topic] deep learning" (cs.LG)
Date range: last 3 years
Downloaded papers: [list arXiv IDs]

### PubMed / clinical literature
MeSH queries used:
- "Deep Learning"[MeSH] AND "[domain]"[MeSH]
- "[method]"[MeSH] AND "diagnosis"[MeSH]
Filters: Review, Clinical Trial

### Zotero
Relevant collections:
- [Collection name 1]: [N papers]
- [Collection name 2]: [N papers]

### Systematic/scoping search log
- Databases: [PubMed, Embase, Web of Science, IEEE Xplore, Cochrane, etc.]
- Exact search strings: see search_log.md
- Screening log: see screening_log.csv
- Extraction/charting table: see extraction_table.csv or charting_table.csv
- Risk of bias: see risk_of_bias.md

## Literature inventory (narrative/method survey default)

### Axis 1: Architectural priors
- **CNN-based**: [list verified refs]
- **Transformer-based**: [list]
- **Mamba / state-space**: [list]

### Axis 2: Inductive priors
- **Topology-aware**: [list]
- **Multi-task**: [list]
- **Graph-based**: [list]

### Axis 3: Data regime
- **Self-supervised**: [list]
- **Foundation models**: [list]
- **Federated**: [list]
- **Physics-informed**: [list]

### Clinical / downstream
- [list]

## Verdict positions to take (3-5)

Plan the 3-5 verdict sentences in advance:
- §Methods axis 1 closer: ...
- §Methods axis 2 closer: ...
- §Methods axis 3 closer: ...
- §Clinical translation closer: ...
- (optional) §Discussion closer: ...

## Writing-time guardrails (from references/)

- Per-claim verification on every `[N]` placed (CITATION_INTEGRITY ▸ Rule 1-5)
- Self-scan against hallucination patterns every 5-6 paragraphs (HALLUCINATION_PATTERNS.md)
- Vendor names table-first; sparse body mentions only when precision requires
- Equations only in Box 1
- Max 2 heading levels, no numbered headings
- If route is systematic/scoping: PRISMA/PRISMA-ScR methods must be present before drafting Results
```

---

## IMPLEMENTATION_PLAN.md Template

```markdown
# Implementation Plan: [Review Title]

## Phase -1: Review-Type Routing
**Status**: [Not Started / In Progress / Complete]

- [ ] Review type selected: [narrative / method survey / scoping / systematic / systematic + meta-analysis / umbrella]
- [ ] Required reporting standards selected
- [ ] Route-specific files listed
- [ ] Manuscript title/abstract language matches the route

## Phase 0: Paradigm Capture
**Status**: [Not Started / In Progress / Complete]

- [ ] Identify 2-3 exemplar reviews from target tier
- [ ] Read carefully (60-90 min each)
- [ ] Extract style spec to PARADIGM.md
- [ ] Re-anchor at start of each Phase 4 writing session

## Phase 1: Project Initialization
**Status**: [Not Started / In Progress / Complete]

- [ ] CLAUDE.md created with terminology + sources + literature inventory skeleton
- [ ] IMPLEMENTATION_PLAN.md (this file) created
- [ ] manuscript_draft.md created (empty)
- [ ] PARADIGM.md linked
- [ ] If scoping/systematic: PROTOCOL.md, search_log.md, screening_log.csv, and extraction/charting files created

## Phase 2: Literature Collection + Verification
**Status**: [Not Started / In Progress / Complete]

### Methodological Literature
- [ ] Search "[topic] segmentation" in cs.CV, eess.IV
- [ ] Search "[topic] transformer/attention" in cs.CV
- [ ] Download key papers (target: 50-80 — discriminate aggressively)
- [ ] Read each (abstract + methods + results)
- [ ] Note actual module names + actual numbers in working notes

### PubMed / Clinical Literature
- [ ] Search MeSH: "Deep Learning" AND "[domain]"
- [ ] Filter by publication type (Review, Clinical Trial)
- [ ] Collect clinical validation studies (target: 20-40)
- [ ] Verify metadata for each selected paper

### Zotero (User's local library)
- [ ] Check existing collections for closed-access papers
- [ ] Note Zotero item keys for later fulltext retrieval

### Additional sources
- [ ] WebSearch supplementary (IEEE Xplore, Springer)
- [ ] If systematic/scoping: exact search strings documented in search_log.md
- [ ] If systematic/scoping: deduplication and screening counts documented
- [ ] If systematic: risk-of-bias tool selected and justified

### Verification (every entry, before adding)
- [ ] DOI resolves on Crossref
- [ ] First + last author verbatim from first-source
- [ ] Journal, year, vol, issue, pages match
- [ ] No `xxx` / `[TBD]` placeholders

### Gap analysis
- [ ] Negative trials covered? (LLM bias: only positive)
- [ ] Inter-vendor reproducibility covered?
- [ ] Demographic-bias studies covered?
- [ ] Recent 6-month preprints covered?

## Phase 3: Outline + Taxonomy
**Status**: [Not Started / In Progress / Complete]

- [ ] Top-level sections defined (Introduction / Methods / Applications / Translation / Discussion)
- [ ] If narrative/method survey: Methods structured as **3 H3 subsections** when appropriate:
  - [ ] §Methods.Architectural priors
  - [ ] §Methods.Inductive priors
  - [ ] §Methods.Data regime
- [ ] If systematic/scoping: Methods/Results structure follows REVIEW_TYPES.md and journal instructions
- [ ] Each paper in literature inventory mapped to an axis
- [ ] Table 1 / 2 / 3 designs planned
- [ ] Box 1 (metrics) content planned
- [ ] Figures (3-5) planned
- [ ] Verdict positions for 3 axes selected

## Phase 4: Write with Per-Claim Verification
**Status**: [Not Started / In Progress / Complete]

For each section, micro-workflow (per CITATION_INTEGRITY.md):
- [ ] Re-read the actual cited papers
- [ ] Write 2-4 sentences with actual module names + actual numbers
- [ ] Verify each `[N]` placed (body↔bib, number, direction)
- [ ] Close axis with verdict sentence
- [ ] Equations to Box 1, not body
- [ ] Vendor names to Table 3, not body
- [ ] Self-scan against hallucination patterns every 5-6 paragraphs

### Section progress

- [ ] Introduction (Clinical background / Technical challenge / Scope)
- [ ] Datasets and evaluation metrics (Box 1, Table 1)
- [ ] Methods §Axis 1: Architectural priors
- [ ] Methods §Axis 2: Inductive priors
- [ ] Methods §Axis 3: Data regime
- [ ] Methods Table 2 finalized
- [ ] Downstream applications
- [ ] Translation to clinical practice (Table 3)
- [ ] Outstanding challenges
- [ ] Future directions
- [ ] Conclusion
- [ ] References (cross-checked with body)

## Phase 5: Multi-Agent Peer Review
**Status**: [Not Started / In Progress / Complete]

- [ ] Run `style-reviewer` pass
- [ ] Run `ref-checker` pass
- [ ] Run `peer-reviewer` pass
- [ ] Run `fact-checker` pass
- [ ] If systematic/scoping: run `methods-reviewer` pass for PRISMA/reporting-standard fit
- [ ] Run bundled `<skill_dir>/scripts/audit_manuscript.py` and save report
- [ ] Synthesize 4 reports into 00_team_synthesis.md
- [ ] Address all CRITICAL findings
- [ ] Address HIGH findings agreed by ≥ 2 reviewers

## Phase 6: Submission Prep
**Status**: [Not Started / In Progress / Complete]

- [ ] Journal selected (reach + match + safety tiers)
- [ ] Presubmission inquiries sent (reach tier, optional)
- [ ] Cover letter drafted
- [ ] Box vs body duplication scan run
- [ ] Section cross-reference scan run
- [ ] Figures produced (not placeholders)
- [ ] Citation format converted for target journal
- [ ] Final self-check checklist passed
- [ ] Required reporting checklists included if applicable

## Literature Sources Summary

| Source | Query / Collection | Papers | Verified | Status |
|---|---|---|---|---|
| ArXiv | [query 1] | N | N | [ ] |
| ArXiv | [query 2] | N | N | [ ] |
| PubMed | [MeSH query] | N | N | [ ] |
| Zotero | [collection] | N | N | [ ] |

## Change log

### [Date] - v1.0
- Initial draft completed through Phase 4
### [Date] - v1.1
- Phase 5 peer review found 8 issues; addressed
### [Date] - v1.2
- Phase 6 submission prep done; sent to [Journal]
```

---

## PROTOCOL.md Template (scoping/systematic routes)

```markdown
# Protocol: [Review title]

## Review type
[scoping / systematic / systematic + meta-analysis]

## Question
- PCC for scoping: Population / Concept / Context
- PICOS or PIRD for systematic review: Population or Participants / Intervention or Index test / Comparator or Reference standard / Outcomes or Diagnosis / Study design

## Eligibility criteria
### Include
- [criterion]

### Exclude
- [criterion]

## Information sources
| Database | Platform | Date searched | Date range | Notes |
|---|---|---|---|---|
| PubMed | NCBI | YYYY-MM-DD | 2019-2026 | [notes] |

## Search strategy
See search_log.md for exact strings.

## Selection process
Describe deduplication, title/abstract screening, full-text screening, reviewer count, and conflict handling.

## Data items
List extraction/charting variables.

## Risk of bias
Name and justify the tool if this is a systematic review.

## Synthesis
Describe narrative synthesis, evidence map, or meta-analysis approach. Do not pool metrics unless tasks and validation settings are comparable.
```

## Extraction / Charting Table Fields

Use these as CSV headers and adapt to the route:

```text
study_id, first_author, year, doi_or_pmid, country, centers, modality, anatomy, task, review_route, population, dataset_size, train_val_test_split, external_validation, reference_standard, model_family, architecture, pretraining, metrics_reported, headline_result, confidence_interval, code_available, data_available, leakage_risk, bias_tool_domain_notes, fairness_or_subgroup_notes, clinical_translation_notes
```

---

## Standard Table Templates

### Table 1: Public Datasets

```markdown
**Table 1 | Public datasets for [task].**

| Dataset | Year | Cases | Annotation type | Access |
|---|---|---|---|---|
| [Name] | 20XX | N | [type] | [link] |

*Cases = unique patients. Where multi-center, the number of sites is given in parentheses. Access notations: O = open, R = restricted (registration), C = commercial.*
```

### Table 2: Method Comparison

```markdown
**Table 2 | Representative deep learning methods for [task].**

| Reference | Modality | Family | Architecture | Dataset | Headline metric | Innovation |
|---|---|---|---|---|---|---|
| [First-author Year] [N] | CCTA | Topology-aware | nnU-Net + clDice | ImageCAS | Dice 0.812 | First clDice on CCTA |

*Performance numbers are taken from the original publications and should not be compared directly across rows; datasets, splits and metric definitions differ. Family is the most-engaged inductive prior or training regime, not the only one. CCTA = coronary CT angiography; HD95 = 95th-percentile Hausdorff distance; — = not reported.*
```

### Table 3: Commercial Products

```markdown
**Table 3 | Commercial AI tools for [domain] with regulatory clearance.**

| Manufacturer | Product | Indication | Underlying technology | Regulatory | Deployment | Key validation evidence |
|---|---|---|---|---|---|---|
| HeartFlow | CT-FFR Analysis | CT-FFR | CFD + DL hybrid | FDA cleared (CPT 75580); CE | Cloud-based SaaS | NXT, ADVANCE, PLATFORM, PACIFIC; FISH&CHIPS [N] |
| Keya Medical | DeepVessel FFR | CT-FFR | DL surrogate of CFD | FDA, NMPA Class III, CE | Cloud + on-site | Multi-centre Chinese validation [N] |

*Listed validation evidence refers to peer-reviewed primary publications, not vendor white papers. NMPA = National Medical Products Administration (China); CFD = computational fluid dynamics.*
```

---

## Notes

### Why bibliography target removed

v2 set "80-120 references" as a quality criterion. This drove Claude to **pad the bibliography**, and padding encouraged fabrication. v3 has no count target. Cite what supports the argument. If your review naturally has 60 high-quality refs, that's enough. If it needs 150, also fine. Quantity is downstream of substance.

### Why 3-axis Methods is the structural commitment

v2's coronary review produced 10 flat method H3 subsections. The resulting §Methods read as a textbook chapter, not a flagship review. Flagship reviews compress 10+ method variants into ~3 thematic axes that force comparative synthesis. The 3-axis structure is the most important structural fix in v3.
