# Medical Imaging AI Review Workflow

This workflow uses "write-with-verify + peer review" discipline. Verification is embedded throughout, not bolted on at the end.

Start by choosing the review type. Narrative/method surveys, scoping reviews, and systematic reviews have different method requirements.

---

## Phase -1: Review-Type Routing

**Goal:** Make the manuscript's label match its methods.

**Actions:**

1. Read [REVIEW_TYPES.md](REVIEW_TYPES.md).
2. Choose one route: narrative/method survey, scoping review, systematic review, systematic review with meta-analysis, or umbrella review.
3. If the route is scoping or systematic, read [REPORTING_STANDARDS.md](REPORTING_STANDARDS.md) before search design.
4. Add the chosen route to `CLAUDE.md` and `IMPLEMENTATION_PLAN.md`.

**Hard gate:** Do not write "systematic review" unless the project includes reproducible search strings, eligibility criteria, screening flow, extraction fields, and risk-of-bias methods.

**Deliverable:** Review-type declaration and route-specific file list.

---

## Phase 0: Paradigm Capture

**Goal:** Before writing anything, ground the review in 2-3 published flagship-quality exemplars from the target journal tier.

**Why:** LLMs default to a generic "survey paper" register — numbered chapters, hedging language, neutral catalogue, dense subsections. Flagship reviews (Nature Reviews / Nat Med / Lancet family) write very differently. Without an exemplar to anchor against, the draft will drift toward survey-paper style and become hard to retrofit.

**Actions:**

1. Identify 2-3 exemplar reviews from the target journal tier. Selection criterion: same modality, same problem family, or same review type, published recently enough to reflect current journal conventions.

2. Read them carefully (not just skim). Pay attention to:
   - Heading depth and numbering (flagship narrative reviews usually use 2 levels; systematic reviews may have formal Methods subheadings)
   - Paragraph rhythm (topic → evidence → verdict, not topic → list → list → list)
   - Citation density (1.5-2.5 refs per paragraph typical)
   - Equation handling (Box vs inline)
   - Vendor handling (Table-first, sparse body mentions when precision requires)
   - Authorial voice (do they take positions or stay neutral?)
   - Box and Figure usage (how many, how dense)
   - Table count (rarely more than 3)

3. Write the extracted style spec to `PARADIGM.md`. See [PARADIGM.md template](PARADIGM.md) for the exact structure.

**Deliverable:** `PARADIGM.md` in the project root.

**Time budget:** 2-3 hours (reading + spec writing).

---

## Phase 1: Project Initialization

**Goal:** Set up the project files and writing guidelines.

**Actions:**

1. Create `CLAUDE.md` from the [TEMPLATES.md - CLAUDE.md](TEMPLATES.md#claudemd-template) template. Fill in:
   - Review type and route-specific standards
   - Topic-specific terminology table
   - Reference source configurations (ArXiv / PubMed / Zotero queries)
   - Expected literature categories (don't commit yet — refine after Phase 2)

2. Create `IMPLEMENTATION_PLAN.md` from [TEMPLATES.md - IMPLEMENTATION_PLAN.md](TEMPLATES.md#implementation_planmd-template). For narrative/method surveys, note the default **3-axis** structure for Methods. For systematic/scoping reviews, use the protocol/search/screening/extraction stages in [REVIEW_TYPES.md](REVIEW_TYPES.md).

3. Create route-specific working files:
   - Narrative/method survey: `PARADIGM.md`, `CLAUDE.md`, `IMPLEMENTATION_PLAN.md`, `manuscript_draft.md`.
   - Scoping review: add `PROTOCOL.md`, `search_log.md`, `screening_log.csv`, `charting_table.csv`.
   - Systematic review: add `PROTOCOL.md`, `search_log.md`, `screening_log.csv`, `extraction_table.csv`, `risk_of_bias.md`.

4. Create empty `manuscript_draft.md`. Leave it empty until Phase 4 — don't pre-populate with placeholder text.

5. Link `PARADIGM.md`, [REVIEW_TYPES.md](REVIEW_TYPES.md), [REPORTING_STANDARDS.md](REPORTING_STANDARDS.md), [CITATION_INTEGRITY.md](CITATION_INTEGRITY.md), and [HALLUCINATION_PATTERNS.md](HALLUCINATION_PATTERNS.md) from CLAUDE.md so they're easy to refer back to.

**Deliverable:** Project skeleton with 4 files (PARADIGM.md, CLAUDE.md, IMPLEMENTATION_PLAN.md, manuscript_draft.md).

**Time budget:** 1 hour.

---

## Phase 2: Literature Collection + Verification (simultaneous)

**Goal:** Gather the corpus while verifying each entry's metadata in real time.

**Why simultaneous:** v2 separated collection from verification — collection in Phase 2, verification never. Result: 17 placeholder DOIs and many wrong-author lists shipped to the final draft. v3 verifies on the way in.

**Actions:**

### 2.1 Methodological preprints

```
Query: "[topic] AND (segmentation OR detection OR classification)"
Categories: cs.CV, eess.IV, cs.LG
Date: last 3 years
Max results: 50-80 per query (NOT 100 — discriminate aggressively)
```

For each paper added:
- Use any available arXiv/paper-search tool, direct arXiv URLs, publisher pages, or local PDFs.
- Read abstract + methods + results before writing architectural details.
- Note: actual title, full author list, exact module names, headline numbers, dataset name

### 2.2 PubMed and peer-reviewed clinical literature

```
MeSH: "Deep Learning"[MeSH] AND "[domain]"[MeSH]
Filters: Review or Clinical Study, last 5 years
```

For each paper added:
- Use available PubMed tools, NCBI/PubMed search, publisher pages, or DOI lookup.
- Note: title, full author list (first 6 + et al.), journal, year, volume, issue, pages, DOI, headline finding direction (positive/negative)

### 2.3 Zotero (user's local library — especially closed-access)

For closed-access journals (Med Image Anal, Eur Radiol, JACC, Lancet family, Nature family) the user often has PDFs in Zotero. Always check before assuming inaccessible.

Use available Zotero MCP tools, Zotero local API, or user-provided PDFs. Search first; request full text only for papers whose metadata/abstract are insufficient.

### 2.4 Systematic/scoping search additions

For scoping or systematic reviews, document:

- Databases searched, platforms, and dates.
- Exact search strings for each database.
- Filters and limits.
- Deduplication method.
- Screening stages and counts.
- Reasons for exclusion at full text.

Do not start Results prose until `search_log.md` and `screening_log.csv` exist.

### 2.5 Verification — apply CITATION_INTEGRITY rules as you collect

For each paper added to the bibliography, before committing the entry:

- [ ] DOI resolves on Crossref (`api.crossref.org/works/<DOI>`)
- [ ] First and last author names match the first-source verbatim
- [ ] Journal name, year, volume, issue, pages match
- [ ] No placeholder strings (`xxx`, `[TBD]`, `?`) anywhere in the entry

If any check fails, do not add the entry. Either resolve the metadata or drop the paper.

See [CITATION_INTEGRITY.md](CITATION_INTEGRITY.md) for the full 5-rule protocol.

### 2.6 Build the literature matrix or extraction table

For narrative/method surveys, build a synthesis matrix:

| Axis | Sub-family | Key papers (verified) | Count | Source |
|---|---|---|---|---|
| Architectural priors | CNN | [refs] | N | arXiv |
| Architectural priors | Transformer | [refs] | N | arXiv |
| Inductive priors | Topology | [refs] | N | arXiv |
| ... | ... | ... | ... | ... |
| Clinical | Validation | [refs] | N | PubMed |
| Datasets | Public | [refs] | N | mixed |

For systematic/scoping reviews, build the extraction/charting table specified in [REVIEW_TYPES.md](REVIEW_TYPES.md).

The **3 axes** are a default for narrative AI method surveys, not a universal structure for every review type. See [DOMAINS.md](DOMAINS.md).

### 2.7 Gap analysis

After initial collection:
- Are negative trials covered? (LLM tendency: only cite positive trials → over-rosy review)
- Are recent 6-month preprints covered? (LLM tendency: stale by training-cutoff date)
- Are inter-vendor reproducibility studies covered? (LLM tendency: report-only-positives)
- Are demographic-bias / fairness studies covered? (LLM tendency: ignore entirely)

For each gap, run a targeted search.

**Deliverable:** Literature matrix (in CLAUDE.md or IMPLEMENTATION_PLAN.md) with every entry verified.

**Time budget:** 1-2 days (depending on topic breadth). Most of the time is reading abstracts to discriminate relevance, not searching.

---

## Phase 3: Outline + Taxonomy

**Goal:** Lock in section structure before writing prose.

**Actions:**

1. Define top-level sections from the selected review route:
   - Narrative/method survey: use the default structure in `SKILL.md`.
   - Scoping/systematic review: use [REVIEW_TYPES.md](REVIEW_TYPES.md) and the target journal instructions.

2. For narrative AI method surveys, default to the **3-axis** grouping (rather than a flat 10-subsection list):
   - Axis 1: Architectural priors (what kind of network)
   - Axis 2: Inductive priors (what kind of geometric / structural / multi-task bias is built in)
   - Axis 3: Data regime (how is data used / pre-trained / federated)

   Each axis usually becomes one H3 subsection. Inside each axis, group method families with bold lead-ins (`**Topology-aware design.**`), not deeper H4 headings.

3. Map each paper from the literature matrix to one (or sometimes two) axes. If more than 30% of the literature does not fit, document the alternative taxonomy in `PARADIGM.md` and use it consistently.

4. For systematic/scoping reviews, plan PRISMA-style Results first: flow diagram, study characteristics, risk of bias (if applicable), and synthesis/charting tables.

5. For narrative/method surveys, plan the three tables explicitly:
   - Table 1: public datasets (name, year, cases, annotation type, access)
   - Table 2: representative methods (with modality / family / dataset / metric — pick 12-20 papers across all 3 axes)
   - Table 3: commercial products (manufacturer / product / regulatory / validation evidence)

6. Plan Box 1: evaluation metrics with formulas.

7. Plan figures (typically 3-5 for narrative reviews; PRISMA flow diagram required for systematic/scoping reviews).

**Deliverable:** Section outline and 3-axis paper mapping in `IMPLEMENTATION_PLAN.md`.

**Time budget:** 0.5-1 day.

---

## Phase 4: Write with Per-Claim Verification

**Goal:** Produce the manuscript prose, with verification embedded in every paragraph.

**Why per-claim verification:** v2 wrote first and QA'd later. The QA was structural, not factual. Result: shipped fabricated module names and wrong numbers. v3 verifies each claim before committing it.

**Actions per section:**

1. **Write an introduction paragraph** (1-2 paragraphs on motivation + scope). This is the safest part of the section — make it punchy and clear, set up the verdict that will close the section.

2. **For each method family**, repeat this micro-loop:

   a. **Re-read** the cited paper's abstract + relevant methods/results section using the best available source route. Do not skip this. If you can't access the paper, do not write its internal architecture.

   b. **Write 2-4 sentences** describing the method's actual contribution, using actual module names and actual numbers. Cite the paper as `[N]`.

   c. **Verify** the [N] you just placed:
      - Is N's bibliography entry the paper you just read? (body↔bib reconciliation)
      - Does your sentence's number (Dice / sensitivity / HR) appear in the paper?
      - Does your sentence's directional claim (lower/higher / increased/decreased) match the paper?

   d. If any verification fails, fix immediately. Do not move on with broken citations — they compound.

3. **Close narrative/method-survey sections with verdict sentences** (pick the most opinionated positions). For systematic/scoping reviews, conclusions must stay within the protocol-defined evidence base. See [SKILL.md - Verdict Sentences](../SKILL.md#verdict-sentences).

4. **Equations** go into Box 1, not the body. If you find yourself typing a `$$` outside Box 1, stop and move the equation.

5. **Vendor names** go into Table 3 by default. If a product name is necessary in body text for regulatory or comparative precision, use it once, keep the prose neutral, and cite peer-reviewed evidence for clinical claims.

6. **Update bibliography** as you go (don't batch at the end — the body↔bib reconciliation breaks down with batching).

### Self-check during writing

Every 5-6 paragraphs, pause and scan for the hallucination patterns (see [HALLUCINATION_PATTERNS.md](HALLUCINATION_PATTERNS.md)):

- Are author names sounding generic? (pattern 1)
- Are performance numbers suspiciously round or high? (pattern 2)
- Am I claiming directional findings I haven't verified? (pattern 3)
- Am I citing vendor materials as if peer-reviewed? (pattern 4)
- Are there any `xxx` or `[TBD]` strings? (pattern 5)
- Are [N] referring to what I think? (pattern 7)
- Are my metric formulas correct? (pattern 8)
- Does the manuscript use systematic/scoping/meta-analysis language without route-specific methods? (pattern 10)

**Deliverable:** `manuscript_draft.md` complete from Introduction through References, with per-claim verification trace in the writing log.

**Time budget:** 3-5 days (the largest phase).

---

## Phase 5: Multi-Agent Peer Review

**Goal:** Before delivering to the user, run a 4-perspective audit.

**Why:** Single-author self-review misses patterns. The 4 specialized agents catch what a single writer doesn't.

**Actions:**

Launch a 4-perspective audit with multi-agent tools if available. If not, run the four passes serially and save each report.

| Teammate | Focus |
|---|---|
| `style-reviewer` | Compare against PARADIGM.md spec; identify register / structural drift |
| `ref-checker` | Verify every `[N]` body↔bib match; spot-check author lists and DOIs |
| `peer-reviewer` | Roleplay as flagship-tier journal reviewer; identify missing controversies, weak verdicts, scope drift |
| `fact-checker` | Cross-check every quantitative claim (Dice, HR, sample size, p-value) against first-source |

For systematic/scoping reviews, add a fifth pass: `methods-reviewer`, focused on PRISMA items, search reproducibility, screening/extraction transparency, and risk-of-bias fit.

After all reports return, synthesize into `review_outputs/00_team_synthesis.md`. For any issue flagged by at least 2 reviewers, treat as a hard fix. For single-reviewer flags, judge based on severity.

**If the issues are minor** (handful of style nits, 1-2 minor citation issues): fix them in place and ship.

**If the issues are major** (5 or more hard factual errors, 10 or more citation drift instances, missing major controversies, or a systematic-review claim without systematic methods): stop delivery and run a factual/method reset before continuing.

**Deliverable:** 4 review reports + synthesis + a final-quality draft.

**Time budget:** 1 day for the multi-agent review, plus fix time depending on findings.

---

## Phase 6: Submission Prep

**Goal:** Format-level finalization for a specific target journal.

Prepare:

- Journal selection (3-tier reach / match / safety)
- Presubmission inquiry templates
- Cover letter template
- Box vs body duplication scan
- Figure realization (no placeholders at submission)
- Citation format conversion (`[N]` → `<sup>N</sup>` depending on journal)
- Self-check checklist
- PRISMA / PRISMA-ScR / CLAIM / TRIPOD / QUADAS checklist files when the route requires them
- bundled `<skill_dir>/scripts/audit_manuscript.py` report saved with the review outputs

**Deliverable:** Submission-ready package (manuscript + figures + cover letter + author info).

**Time budget:** 0.5-1 week including presubmission inquiry wait.

---

## Total Timeline

For a typical medical-imaging review project:

| Phase | Duration |
|---|---|
| Phase -1: Review-type routing | 15-30 min |
| Phase 0: Paradigm capture | 2-3 hours |
| Phase 1: Init | 1 hour |
| Phase 2: Collect + verify | 1-2 days |
| Phase 3: Outline + 3-axis taxonomy | 0.5-1 day |
| Phase 4: Write with per-claim verification | 3-5 days |
| Phase 5: Multi-agent peer review | 1 day + fix time |
| Phase 6: Submission prep | 0.5-1 week (incl. presubmission wait) |
| **Total** | **2-3 weeks of focused work for narrative reviews; longer for systematic reviews** |

Compare to v2 + downstream fix: typically 1 week of v2 drafting + 2-3 weeks of post-hoc revision. Net the same time, but v3 delivers a submission-ready draft instead of one needing factual reset.
