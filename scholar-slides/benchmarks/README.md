# scholar-slides regression benchmark

A small corpus of real papers built end-to-end, re-run through every gate on each change so a fix
that helps one deck cannot silently regress another. This is the guard behind the "world-class *and*
minimal-manual-edits" goal: quality is measured on a corpus, not on the one deck in front of you.

## Run it

```bash
node scripts/run_benchmark.mjs
```

Each deck in `manifest.json` is scored on three gates and printed as one row:

| gate | what it proves | tool |
|------|----------------|------|
| **integrity QA** | numbers grounded in the source, layout lock, no overflow / broken image / KaTeX error | `qa_report.mjs` |
| **PPTX parity** | every spec text/table/caption/note survives *natively* into the editable PPTX (protects "minimal manual edits") | `verify_pptx_parity.py` |
| **layout-mix** | bullet-ratio and longest same-layout run (the figure-editor register wants < ~1/3 bullets) | `qa.layoutMix` |

Exit is non-zero if any deck **BLOCK**s (a P0 integrity defect) or has **PPTX parity issues** — the CI
regression signal. P1 (REVIEW) and P3 (nudges) are reported, not failed.

## Reading the dashboard

- `gate`: PASS / REVIEW (P1 — acknowledge at CKPT-3) / BLOCK (P0 — must fix).
- `pptx-parity`: `ok` / `N ISSUES` / `no-pptx` (deck wasn't exported).
- `bullets`: pure-bullet-slide ratio. > ~33% is a smell — prefer figures / tables / redrawn charts.
- `talk`: estimated speaking time (bilingual rate model).

## The current set (seed)

Six real decks across register and language (see `manifest.json`): a Transformer NLP deck
(equation + real BLEU table); DeepSeek-V3.2 in two cuts — a dense journal-club deck (emphasis
layer, figures, results table, critique) and a conference-theme re-cut (0% bullets, section
rhythm, dark dividers); GLM-5 in English and 中文 journal-club form (ablation + scoreboard tables,
CJK typography); and a 中文 smoke deck for full-width punctuation.

## Growing toward 15+

Add cross-discipline papers so the harness exercises every archetype and both languages. Target a
spread: **CV, NLP, medical, theory (proof/equation-heavy), biology**. For each new paper:

1. `python scripts/prepare_source.py <pdf-or-arxiv-id> --out out/<name>` (ingest → figures → bundle).
2. Author `out/<name>/deck.json`; `node scripts/build_deck.mjs` + `render_deck.mjs pdf` + `export_pptx.mjs`.
3. Add a `{name, dir, field, register, note}` row to `manifest.json`.
4. `node scripts/run_benchmark.mjs` — the new deck must reach PASS (or a documented REVIEW) with
   clean PPTX parity before it counts as part of the benchmark.

Bias the additions toward papers that stress a weak spot: equation-dense proofs (KaTeX), scanned /
two-column PDFs (ingestion), many-panel figures (panel extraction), and data-rich tables (redraw).
