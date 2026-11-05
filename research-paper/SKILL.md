---
name: research-paper
description: >
  Use when the user asks to write, draft or revise an ORIGINAL RESEARCH ARTICLE
  or any single section of one — abstract, introduction, methods, results,
  discussion or conclusion — for an IMRaD paper, conference paper or
  short/workshop paper reporting their own experiments, in English or Chinese
  (研究论文/期刊论文/会议论文, or one part such as 摘要, 引言, 方法, 结果, 讨论部分).
  Triggers: "write the paper", "draft our manuscript", "write the Discussion
  of our paper", "把我们这篇工作写成论文", "帮我写论文的讨论部分", "论文写作".
  Results-first: the user's actual results (tables, metrics, figures) are the
  raw material; this skill never invents an experiment or a number. NOT for
  literature reviews/surveys or their sections (use medical-imaging-review),
  NOT for proposals (use research-proposal), NOT for grant applications.
---

# Research Paper Writer

Draft an original research article from the user's **actual completed work**:
their experiments, data, figures, and references. Two disciplines govern
everything:

1. **Results-first.** Methods and Results are written from materials the user
   supplied (result tables, metrics dumps, figures, code notebooks). Anything
   not supplied is flagged `[PENDING: …]` — never filled with a plausible
   number. A fabricated result is worse than a fabricated citation: it is
   data fraud, not a style slip.
2. **Citation integrity** (this repository's shared five-rule core, instantiated
   for author-year/numeric journal styles — see
   [references/CITATION_INTEGRITY.md](references/CITATION_INTEGRITY.md)):
   every reference verified to exist before it enters the bibliography;
   `[UNVERIFIED]` flags for the rest; no invented DOIs, authors, or numbers.

## Scenario routing

| Study type | Structure | Binding checklist (Phase 1) |
|---|---|---|
| Imaging-AI method / model paper | IMRaD, methods-forward | CLAIM 2024 |
| Prediction / risk model | IMRaD + model development emphasis | TRIPOD+AI |
| Diagnostic accuracy study | IMRaD, test-vs-reference emphasis | **STARD 2015** (可与 CLAIM 并行声明) |
| Observational / cohort study | IMRaD, methods after hypotheses | STROBE |
| (Rare here) trial, systematic review | **Out of scope** — say so and stop | CONSORT / PRISMA via the right skill |
| CS/eng venue paper (CVPR/NeurIPS style) | Abstract → Intro → Related Work → Method → Experiments → Discussion → Conclusion | venue's own checklist/reproducibility statement |

Read [references/STRUCTURE_GUIDE.md](references/STRUCTURE_GUIDE.md) for
section-by-section construction and [references/REPORTING_CHECKLISTS.md](references/REPORTING_CHECKLISTS.md)
for what the binding checklist actually requires.

## Single-section requests

A request for one or two sections (for example only the Discussion, or Results +
Abstract) built from material the user supplied is bounded work: skip the
project files (`paper_plan.md`, outline approval, `paper_draft.md`) unless the
user wants them, and **write the file the user named**. The disciplines still
apply in full: every number traces to the supplied results or is
`[PENDING: …]`; every reference is verified or `[UNVERIFIED: …]`; a Discussion
claims no more than the results show (no "significantly" without a reported
test, no "every"/"all" where a baseline wins). Run the Phase 5 placeholder and
AI-tell greps on the requested file; `check_paper.py` applies once a
`results_ledger.csv` and `references.bib` exist.

## Phase 1: Intake (record, don't improvise)

Use `AskUserQuestion` to collect:

1. **Study type + target venue/journal** — routes structure and checklist (above).
2. **Materials in hand** — result tables/CSVs, metric numbers, figures, prior
   drafts/notes, code notebook. If the user has *no results yet*, stop: this
   skill writes papers about completed work, not imagined work (that is
   research-proposal territory).
3. **References pool** — user's Zotero/bib, or run the **lit-search** skill for
   a defensible related-work corpus (its `references.bib` drops straight in).
4. **Language and length** — en/zh; word limit from the venue's guide.

Record the intake as a short `paper_plan.md` (study type, venue, checklist,
materials list, citation style). Headless runs: record inline and continue.

## Phase 2: Materials audit (before any prose)

Inventory every number that will appear in Results:

- Each metric → its source artifact (file, table, cell). Untraceable numbers
  are `[PENDING]`, and the user is told before drafting starts.
- Each figure → real file or a `[PENDING: figure]` placeholder with a content
  description. Redrawing/schematics follow the same honesty rules as
  scholar-slides (label what is not data).
- This inventory becomes `results_ledger.csv` (see
  [references/QUALITY_CHECKLIST.md](references/QUALITY_CHECKLIST.md)) — the
  paper-side sibling of the review skill's claim ledger: one row per
  load-bearing number, `claim_id → section → claim_text → value`（列名以
  [references/QUALITY_CHECKLIST.md](references/QUALITY_CHECKLIST.md) 的
  schema 表头为准）.

## Phase 3: Outline + approval (red line)

Section skeleton per [references/STRUCTURE_GUIDE.md](references/STRUCTURE_GUIDE.md),
with per-section bullet content mapped to Phase 2 materials. **Present the
outline and wait for explicit approval** (same rules as research-proposal:
"你看着办" → state assumptions, re-present, proceed).

## Phase 4: Write-with-verify (per section)

Draft section by section **into a single working file `paper_draft.md`** (the
Phase 5 gates grep exactly that filename — a renamed draft makes them scan an
empty file and report a false zero-hit); after each section, before starting the next:

1. Every citation in the section is from the verified pool (rules:
   [references/CITATION_INTEGRITY.md](references/CITATION_INTEGRITY.md)),
   written as a **stable pandoc citekey** `[@smith2024model]` that has an entry
   in `references.bib` — never a hand-numbered `[17]` in the working draft.
   The venue's numeric/author-year style is rendered only at the end
   (`pandoc paper_draft.md --citeproc --bibliography references.bib --csl <venue>.csl`).
2. Every number in the section reconciles against `results_ledger.csv`.
3. Self-check against the AI-tell list and style rules
   ([references/WRITING_STYLE.md](references/WRITING_STYLE.md)) — the Phase 5
   grep gates make these checkable, not aspirational.
4. Tense/register per section (Methods: past, what was done; Results: past,
   what was found — no interpretation; Discussion: present, what it means).

## Phase 5: Gates + reporting checklist + submission pack

Mechanical gates (paste command output as evidence). Run the executable gate
first — it covers all four mechanical checks in one pass and names every
offending line:

```bash
python3 <skill_dir>/scripts/check_paper.py paper_draft.md \
    --ledger results_ledger.csv --bib references.bib
# exit 0 = no mechanical findings (not proof the paper is right); 1 = findings; 2 = bad input
# --allow-disclosed-flags : [PENDING…]/[UNVERIFIED…] already disclosed → warnings, not failures
# --allow-uncited KEY     : bib entry listed on purpose without in-text citation (venue norm)
# --skip-checklist        : drafting-stage run before checklist_<name>.md exists (warned)
```

It checks: (1) every metric-like number in the prose (decimals, percentages,
`n=`) is covered by a `results_ledger.csv` `value`/`dispersion`; (2) `[@citekey]`
↔ `references.bib` both directions; (3) the placeholder and AI-tell patterns
below (same regex, locked by tests); (4) every `checklist_*.md` row carries a
disposition. Without Python, the two grep gates are the minimum:

```bash
# 1) Placeholder gate — zero hits (or disclosed [UNVERIFIED]/[PENDING])
grep -nE "xxx|XXXX|\[TBD\]|\[PENDING|\[UNVERIFIED[^]]*\]|10\.xxxx|doi:10\.[a-z]+/x" paper_draft.md

# 2) AI-tell gate — zero hits
grep -nEi "over the past ((few|several|two|three) )?(decades?|years)|in recent years,|it is worth noting|plays a (crucial|pivotal|vital) role|sheds light on|paves the way|ever-evolving|has garnered significant attention|delves into|a testament to|众所周知|近年来，?随着|日益受到(广泛)?关注" paper_draft.md
```

Then: work through the binding reporting checklist item by item
([references/REPORTING_CHECKLISTS.md](references/REPORTING_CHECKLISTS.md));
assemble the submission pack — title page, abstract in the venue's format,
keywords, cover letter, author contributions (CRediT) / conflicts
([references/SUBMISSION_PACK.md](references/SUBMISSION_PACK.md)).

## Reference Files

Read **only** the file for the phase you are in.

| File | Read when |
|------|-----------|
| [references/STRUCTURE_GUIDE.md](references/STRUCTURE_GUIDE.md) | Phase 3 — IMRaD construction per study type |
| [references/CITATION_INTEGRITY.md](references/CITATION_INTEGRITY.md) | Phase 2/4/5 — the five rules + Phase 5 reconciliation gate |
| [references/REPORTING_CHECKLISTS.md](references/REPORTING_CHECKLISTS.md) | Phase 1/5 — checklist selection + item-by-item pass |
| [references/WRITING_STYLE.md](references/WRITING_STYLE.md) | Phase 4 — register, tense, cohesion, AI-tells |
| [references/SUBMISSION_PACK.md](references/SUBMISSION_PACK.md) | Phase 5 — abstract/cover letter/reproducibility statement |
| [references/QUALITY_CHECKLIST.md](references/QUALITY_CHECKLIST.md) | Phase 2/5 — Phase 2 reads the ledger schema; Phase 5 runs the gates |
| [assets/paper_scaffold_en.md](assets/paper_scaffold_en.md) | Phase 4 — English skeleton |
| [assets/paper_scaffold_zh.md](assets/paper_scaffold_zh.md) | Phase 4 — 中文骨架 |

## learnings：复盘先于重写

修改 references 或 scaffold 之前先扫 [`learnings/`](learnings/)；返工或发现
自相矛盾后追加一篇，日期命名（格式见 lit-search/learnings/）。

## Error handling

- **No results materials** — stop and say so; suggest research-proposal if the
  work is still planned.
- **A claimed number can't be traced** — `[PENDING]` + explicit disclosure,
  never a placeholder that looks real.
- **Reference can't be verified** — `[UNVERIFIED]` + disclosure (never dropped
  silently, never fabricated).
- **Venue requires a checklist this skill doesn't carry** — say so, point to the
  official source, and record it as a manual gate in `paper_plan.md`.
