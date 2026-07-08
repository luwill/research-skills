# Export — PDF (primary), editable PPTX, Beamer

**Status: live (PDF Stage 2, PPTX Stage 5).** Beamer is opt-in/deferred.

## Primary: vector PDF (projection)
```
node scripts/render_deck.mjs out/<stem>/deck/deck.html pdf        # one-page-per-slide vector PDF
node scripts/render_deck.mjs out/<stem>/deck/deck.html png slides # per-slide PNGs (for QA)
```
Text and equations stay selectable/vector. Speaker notes are NOT printed (hidden in print.css).

## Editable PPTX (co-authors / advisors mark up in PowerPoint or Keynote)
```
node scripts/export_pptx.mjs out/<stem>/deck.json out/<stem>/deck/deck.pptx
```
Built **from the deck.json spec** with pptxgenjs (not by scraping HTML), so what's editable is
genuinely native:
- **Native, editable**: titles, bullets, agenda, critique text, references, and **real OOXML
  tables** (baselines/units/best-bold preserved as table cells, not a picture). **Speaker notes**
  are native PowerPoint notes.
- **Rasterized (the honest degradation, always flagged)**: figures are images (they already are),
  and **equations are rendered to images** (KaTeX → transparent PNG). To change an equation or a
  figure, edit the `deck.json` + the reveal/PDF version and re-export.
- Inline `$math$` inside text is kept as literal LaTeX (PPTX text can't typeset it).

**Fonts in the PPTX.** Titles use a serif (Georgia); body/label text uses **Arial**. This is *not* a
violation of the design system's "no Arial as a display font" rule — Arial is used only as the
cross-platform **body** fallback that every PowerPoint/Keynote install renders identically (so a
co-author's copy doesn't reflow), never as the display/title face. The on-screen reveal.js/PDF deck
keeps the full design-system type stack; the PPTX trades exotic body faces for guaranteed portability.

Validate an export with `python-pptx`: confirm native text frames, a real `table`, embedded
pictures, and notes per slide.

## Beamer / LaTeX (opt-in, deferred)
For theory/stats talks wanting reference-grade math + `biblatex`, the same digest + deck spec can
target a Beamer `.tex` renderer (planned). Until then, use the PDF/PPTX paths.

## Reproducibility
`deck.json`, the figure crops, `bib.json`, `notes.md`, and `pptx_assets/` persist on disk, so a
single slide can be re-rendered/re-exported without re-running the pipeline.

## Parity regression — protecting "minimal manual edits"
The PPTX is only useful if it doesn't silently lose content, forcing a hand-repair.
`scripts/verify_pptx_parity.py <deck.json> <deck.pptx>` asserts that every load-bearing element in
the spec survives into the PPTX **natively**: slide count; all text (titles, bullets, annotations,
table cells, captions, questions, references, cover metadata); speaker notes as native notes; a
figure → a picture; a results-table → a native table. Figures/equations are images by design (the
flagged degradation) — parity requires the image is present, not that it carry text. This runs in
the test suite and in `run_benchmark.mjs`; keep `expected_texts()` in sync with any change to the
exporter's native-text contract in `export_pptx.buildSlide`.
