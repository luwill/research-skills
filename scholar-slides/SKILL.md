---
name: scholar-slides
description: >-
  Use when the user wants a research paper, arXiv/DOI link, or research topic turned
  into academic slides — journal club / lab meeting (组会汇报), thesis defense (答辩幻灯片),
  conference or job talk (学术报告), poster, or grant pitch — or shares a paper and asks
  to "make slides / 做成 PPT / 讲一下这篇论文", especially when equations, numbers,
  figures, and citations must stay accurate and editable. NOT for marketing/pitch decks
  with no scholarly source, and NOT for writing the paper itself.
---

# scholar-slides

Turn a research paper (or topic) into a **fidelity-first** academic slide deck. Academia
inverts the priorities of a normal deck tool: **source fidelity > polish, evidence >
persuasion, editability > flash.** Equations, tables, numbers, figures, and citations stay
**true text/vector and traceable to the source** — never rasterized by an image model,
never fabricated.

Design rationale and the survey it is built on live in `docs/`; build plan in `IMPLEMENTATION_PLAN.md`.

## Locked stack (see docs/03-design-proposal.md §0)
- **Render backend:** reveal.js + KaTeX → vector PDF (Playwright). Editable PPTX / Beamer later.
- **Default deck type:** lab meeting / journal club (组会) — reading-first, high density.
- **Citations:** Zotero-first (`mcp__zotero__*`), Crossref/arXiv/DOI fallback.
- **Language:** bilingual, English-default.

## The non-negotiable integrity gate (ALWAYS on — see references/integrity.md)
Apply at every stage; enforced at Checkpoint 3:
- **Never fabricate** numbers, citations, or figures. Everything traces to the source digest.
- **Math/tables/citations stay vector/text** — never an image model's pixels.
- **Reuse real figures** (bbox-cropped + `Figure N [cite]`); a conceptual schematic may be
  redrawn only if labeled "redrawn, not from source".
- **Flag, don't invent:** an unresolved figure/number/citation emits a visible
  `[MISSING: …]` / `[UNVERIFIED: …]` placeholder surfaced to the user — never a silent fill.
- **Provenance is mandatory:** every reused asset carries its source; every claim is traceable.

## Pipeline (7 stages, 3 human checkpoints)

```
INPUT → 1.INGEST/DIGEST → [CKPT-1] → 2.DECK-TYPE → 3.OUTLINE → [CKPT-2]
      → 4.PER-SLIDE SPEC → 5.RENDER → 6.SELF-REVIEW(QA) → [CKPT-3] → 7.EXPORT
```

1. **Ingest → typed digest** — `references/ingestion.md`. Run
   `scripts/prepare_source.py <pdf|arXiv id|arXiv URL>` to build the digest-input bundle
   (text, figure/table inventory with bboxes, cropped figures), then synthesize the typed
   **paper digest** from it (grounded in the bundle, never invented).
   **→ [CKPT-1]** confirm the digest with the user (contributions, headline result,
   figure→slide map, any FLAGGED asset).
2. **Deck-type & parameters** — `references/deck-types.md`. Pick deck type (default 组会),
   audience, time budget → slide budget, density register, required archetypes.
3. **Narrative outline** — `references/narrative.md`. Re-sequence the paper into talk order;
   action-title per slide; arc-tension check.
   **→ [CKPT-2]** approve the story arc.
4. **Per-slide spec** — `references/slide-spec.md`. One self-contained, on-disk spec per slide
   (layout, content, equations, figures, citations, speaker notes).
5. **Render** — `references/math.md`, `references/figures-tables.md`, `references/citations.md`,
   `references/charts.md`, `references/design-system.md`, `references/export.md`. reveal.js + KaTeX;
   real tables; real bbox-cropped figures (furniture-stripped; one panel per slide for multi-panel);
   data-bound redrawn charts; Zotero/BibTeX citations. Pick the visual theme via `meta.theme`
   (`journal-club` default / `conference`).
6. **Self-review QA** — `references/qa-self-review.md` + `references/integrity.md`, then the
   **aesthetics loop** in `references/aesthetics-review.md`. Integrity scan + static validator +
   render screenshots + narrative/timing checks; the render pass also measures geometry
   deterministically (canvas voids, figure-text projected below the 12px legibility floor). Then
   score the rendered *pixels* on the 6-dimension rubric (adversarial persona), **write the scores
   to `<deck>/aesthetics_report.json`** (schema in aesthetics-review.md), and rework any slide with
   a dimension ≤ 2 or total < 18 until the report's `rework` list is empty — the QA gate flags a
   missing report (P3) and an unspent rework list (P2). It also nudges on bullet-ratio and layout
   monotony.
   **→ [CKPT-3]** truth sign-off: review every `[MISSING]`/`[UNVERIFIED]` and generated asset.
7. **Export** — `references/export.md`. Vector PDF (projection) + speaker notes + editable PPTX;
   verify the PPTX preserves the spec natively with `scripts/verify_pptx_parity.py` (protects the
   minimal-manual-edits promise). Regress the whole corpus with `node scripts/run_benchmark.mjs`.

Read **only** the reference file for the stage you are in (progressive disclosure — never glob
`references/`). Each stage reads the **confirmed artifact of the prior stage** — the digest
(Stage 1, user-confirmed at CKPT-1) and then `deck.json` — rather than re-deriving from the paper.

## Scripts (`scripts/`)
Ingestion — pipeline stage 1 (Python, via `./.venv/bin/python`; deps in `requirements.txt`):
- `prepare_source.py` — **Stage 1 entry point**: PDF/arXiv → digest-input bundle.
- `ingest_pdf.py` — PyMuPDF text+layout extraction; arXiv-id detection.
- `detect_figures.py` — figure/table caption inventory + bounding-box localization.
- `crop_figure.py` — clean single-figure bbox crop (no neighbor columns).

Deck build & render — pipeline stage 5 (Node, via `node`; deps in `package.json`, `npm install` + `npx playwright install chromium`):
- `build_deck.mjs` — **render entry point**: `deck.json` → self-contained reveal.js deck.
- `render_deck.mjs` — deck → one-page-per-slide **vector PDF** (and per-slide PNGs for QA).
- `lib/` — `layouts` (registered-layout lock), `math` (KaTeX), `table`, `figure`, `escape`, `qa`.

Citations & QA — pipeline stages 5–6 (citations = Python; QA = Node):
- `fetch_bib.py` — citation resolver (arXiv/DOI/Crossref) with order-sensitive title verification.
- `qa_report.mjs` — **CKPT-3 gate**: integrity scan + `validate_deck.mjs` + `verify_slides.mjs` + timing.

Speaker notes (Node):
- `speaker_notes.mjs` — `deck.json` → `notes.md` handout + bilingual talk-length estimate.
- `lib/notes.mjs` — timing + handout pure logic; design system in `assets/templates/themes/`.

Export & charts — pipeline stage 7 (export = Node; charts = Python):
- `export_pptx.mjs` — `deck.json` → **editable PPTX** (native text/tables/notes; figures+equations as images).
- `make_chart.py` — chart spec → **data-bound** Okabe–Ito plot (values plotted verbatim).

Tests: `./.venv/bin/python -m pytest` (Python) and
`node --test tests/deck.test.mjs tests/qa.test.mjs tests/notes.test.mjs tests/pptx.test.mjs` (Node).

## Build status
The whole pipeline is implemented and validated on real papers. Not built: Beamer export,
OCR for scanned PDFs, draft-deck ingestion; conference/答辩 deck types are authoring guidance
in `references/deck-types.md` (no dedicated code). A deck is "done" only after the CKPT-3
human truth sign-off — the gate surfaces defects but cannot certify truth.
