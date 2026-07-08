# IMPLEMENTATION_PLAN — `scholar-slides`

Academic slide-deck Claude skill. Build spec: [`03-design-proposal.md`](03-design-proposal.md).
Research basis: [`01-landscape-research.md`](01-landscape-research.md), [`02-academic-needs.md`](02-academic-needs.md).

> Development-history doc, kept in the project repo under `docs/scholar-slides-design/` — not
> shipped inside the installable `scholar-slides/` skill.

## Locked decisions (2026-06-29)
- **Backend:** reveal.js + KaTeX → vector PDF (Playwright). Editable PPTX & Beamer deferred.
- **MVP deck type:** 组会 / journal club — **reading-first, high-density**. Arc: context → claims/contributions → method (deep) → results (dense, real tables) → **critical analysis / concerns / limitations** → takeaway + discussion questions.
- **Citations:** Zotero-first (MCP `mcp__zotero__*`), Crossref/arXiv/DOI fallback; unresolved → `[UNVERIFIED]`.
- **Language:** bilingual, English-default; 中文 + CJK supported.

## Non-negotiable invariants (every stage upholds)
- **No fabrication.** Numbers, citations, figures come from the source. Missing → visible `[MISSING]`/`[UNVERIFIED]` flag, never a silent substitute.
- **Math/tables/citations stay vector/text**, never rasterized or T2I-generated.
- **Figures reused, never redrawn** when factual; bbox crop + `Figure N [cite]` provenance; `fit: contain` (never crop a data figure).
- **Specs persist to disk** before render (reproducible, one-slide regeneration).
- **Scripts are tested first** (TDD per CLAUDE.md); the skill is validated end-to-end on a real paper at each stage.

---

## Stage 1 — Skeleton + ingestion → typed digest ✅ DONE (2026-06-29)
**Goal:** a paper goes in, a faithful structured digest comes out; the skill shell routes correctly.
**Delivered:**
- `SKILL.md` router (frontmatter `name`/`description`; 7-stage pipeline; References routing table; always-on integrity gate; build-status note).
- `references/`: `ingestion.md` (full digest schema + CKPT-1) and `integrity.md` fleshed out; 10 planned-stage stubs.
- `scripts/ingest_pdf.py` (PyMuPDF): text+layout blocks; `detect_arxiv_id`.
- `scripts/detect_figures.py` — **deviation from plan: Python, not TS.** Rationale: doing
  caption-regex *and* bbox localization in one PyMuPDF pass (text + image rects + vector-drawing
  clusters) is what fixes luwill's full-page-raster gap; a TS regex-only port could not localize.
  Adds a region-growing localizer (grows over text+vector+image, stops at the paragraph gap) +
  caption-quality scoring (beats inline "Table N summarizes…" false positives) + plausibility
  guard (drops over-captured regions, flags them).
- `scripts/crop_figure.py` (**new**): bbox pad/clamp + clean region crop (no neighbor columns).
- `scripts/prepare_source.py` (**new orchestrator**): PDF / arXiv-id / arXiv-URL → digest-input
  bundle (`ingest.json`, `figures.json`, `figures/*.png`, `manifest.json`) for CKPT-1.
- **Digest schema + CKPT-1 prompt** in `references/ingestion.md`.
- 30 unit+integration tests (TDD); demo grounded digest at `out/attention/digest.md`.
**Validated:** *Attention Is All You Need* (9/9 figures+tables detected, 5/5 figures cleanly
bbox-cropped — visually verified incl. the Transformer diagram; over-captured tables honestly
flagged) and *FlashAttention-2* via arXiv-id auto-download (14 pp, 7 figs). `pytest` 30 passed.
**Known limits (documented in ingestion.md):** minor heading/caption bleed on some figure crops;
tables flush against prose get no bbox (handled as data); no OCR for scanned/2-col PDFs yet.

## Stage 2 — Render core: reveal.js + KaTeX, dense 组会 register ✅ DONE (2026-06-29)
**Goal:** digest → a rendered reading-first journal-club deck with vector math, real tables, real figures.
**Delivered:** `deck.json` spec format + deterministic builder. `scripts/build_deck.mjs` (deck.json
→ self-contained reveal.js `deck.html` + static `deck.print.html`), `scripts/render_deck.mjs`
(Playwright → one-page-per-slide **vector PDF** + per-slide PNG screenshots), `scripts/lib/`
(`layouts` with the registered-layout lock + 11 MVP 组会 layouts incl. required `critique-concerns`
& `discussion-questions`; `math` = server-side KaTeX vector/MathML; `table` = real `<table>`,
best-bolded, units-in-header; `figure` = contain-fit crop + provenance cite; `escape`). Academic
baseline theme (`assets/templates/themes/journal-club.css` + `deck-stage/viewport-base.css` +
`print.css`). `references/slide-spec.md` fleshed out (deck.json schema + layout catalog + CKPT-2).
11 node:test unit tests. **Deviation:** `.mjs` (plain ESM) instead of `.ts` to avoid a build step;
KaTeX folded into `lib/math.mjs` rather than a separate `render_math.ts`.
**Validated:** built a real 12-slide journal-club deck for *Attention Is All You Need*
(`out/attention/deck/`) — visually verified (contact sheet) that equations are crisp selectable
vector KaTeX, the results table is a real `<table>` with the true Table-2 numbers (28.4/41.8
bolded), figures are the clean bbox crops, and the two required journal-club archetypes render.
PDF = **12 pages, one per slide, text selectable** (vector, not raster). `node --test` 11 passed.
**Deliverables (original plan):**
- `assets/templates/deck-stage/` fixed 1920×1080 reveal.js stage + `viewport-base.css` (ported frontend-slides/huashu/guizang convergence).
- `scripts/render_math.ts` (**new** — replaces ppt-master's external-web PNG): LaTeX → **KaTeX vector/MathML**, numbered + aligned environments, consistent symbol set.
- Real text **results tables** from extracted data (baselines labeled, best **bold**, units in headers, significance markers).
- `assets/templates/figure-container.html`: bbox-cropped real figure + `Figure N: caption [cite]`.
- **组会/journal-club layouts** (registered, `data-layout`): `paper-title`, `outline-agenda`, `context-motivation`, `claims-contributions`, `method-deep` (multi-element OK), `equation`, `algorithm`, `results-table` (dense), `results-chart`, `ablation-grid`, `qualitative-grid`, `critique-concerns` (**MVP-required**), `limitations`, `takeaway`, `discussion-questions` (**MVP-required**), `references`.
  *(As built: the registry is **11 layouts** — `paper-title`, `section`, `outline-agenda`, `assertion-evidence`, `equation`, `results-table`, `two-column`, `critique-concerns`, `discussion-questions`, `bullets`, `references`; the other planned names are content roles expressed through these. `scripts/lib/layouts.mjs` is the source of truth.)*
- Outline stage (paper-section→slide-role map, ported luwill) + **per-slide spec** written to disk (schema in §E of design doc) + **CKPT-2** (approve arc/sequencing).
- ~~Consistency: dual-artifact `design_spec.md` + machine `spec_lock.md` re-read before each slide (ported ppt-master).~~ *(Not built — the inter-stage contract as shipped is the confirmed digest + `deck.json`; SKILL.md documents that. Revisit only if cross-slide consistency drift shows up in practice.)*
- `scripts/render_deck.mjs`: reveal.js → one-page-per-slide vector PDF (Playwright/Decktape).
**Validate:** equations render as selectable vector (no error boxes, no raster); tables are real `<table>` matching source numbers exactly; figures are clean bbox crops with correct captions; PDF is one-page-per-slide; dense slides don't overflow the stage.

## Stage 3 — Integrity gate + citations + automated QA ✅ DONE (2026-06-29)
**Goal:** the deck is trustworthy and self-checked; nothing fabricated slips through.
**Delivered:** `scripts/lib/qa.mjs` (number grounding vs source text w/ scientific-notation
normalization, flag collection, static HTML extractors); `validate_deck.mjs` (layout lock,
KaTeX-error, unrendered-math, missing-figure); `verify_slides.mjs` (Playwright per-slide:
overflow, broken images, KaTeX errors, sub-18px font); `qa_report.mjs` (consolidated **CKPT-3
gate**, P0–P3, exit 2/1/0); `fetch_bib.py` (arXiv/DOI/Crossref resolver with **order-sensitive
title verification** — rejects Crossref's wrong "Is Attention All You Need?" hit, prefers exact
ids, unresolved → `[UNVERIFIED]`). Fleshed `references/citations.md` + `qa-self-review.md`.
14 tests (6 node qa + 8 pytest fetch_bib) + live smokes.
**Validated:** QA gate on the good Attention deck → clean except the known `[UNVERIFIED]` ref.
Adversarial deck (fabricated `99.9` / broken figure / bad LaTeX / 115px overflow) → **all four
caught** (integrity + static + render) while real `28.4` stayed grounded; layout lock fails the
build. Resolver live: arXiv → `vaswani2017`; ambiguous title → `[UNVERIFIED]` (not fabricated).
**Deviation:** QA in Node (`lib/qa.mjs`) over deck.json/ingest.json/HTML, unified with the
browser checks; Zotero-first stays an agent-runtime MCP step (not subprocess-reachable);
`fetch_bib.py` is the verifiable Crossref/arXiv fallback.
**Deliverables (original plan):**
- `scripts/fetch_bib.py`: **Zotero-first** (`mcp__zotero__*` search by title/DOI/arXiv) → verified `.bib`; Crossref/arXiv/DOI fallback; in-text markers + auto references slide matched to used keys.
- `references/integrity.md` + integrity scan: every number/citation/figure traces to the digest; unsourced value / unresolved cite / redrawn-factual-figure → flag.
- `scripts/validate_deck.mjs` (ported guizang): block unregistered layouts, visible SVG `<text>`, centered titles, missing `data-layout`, KaTeX error boxes.
- `scripts/verify_slides.mjs` (ported frontend-slides/huashu): screenshot each slide; overflow/overlap (note `scrollHeight` misses overlap), font-min, equations actually rendered, figures present+uncropped, contrast / color-blind-safety.
- `[MISSING]`/`[UNVERIFIED]` flag taxonomy surfaced at **CKPT-3** (truth sign-off).
**Validate:** adversarial test — inject a fabricated number and an unresolved citation; integrity scan + QA must flag both. Every citation resolves (Zotero or Crossref) or is flagged. QA catches a deliberately overflowing/low-contrast slide.

## Stage 4 — Design system, narrative polish, bilingual ✅ DONE (2026-06-30)
**Goal:** the deck looks like a restrained scholarly deck, reads as a journal-club critique, and works in EN + 中文.
**Delivered:** `scripts/lib/notes.mjs` (bilingual-aware timing — EN wpm + CJK cpm + 0.5-min floor —
+ notes handout); `scripts/speaker_notes.mjs` (`deck.json` → `notes.md` + talk-length estimate +
budget warning); `speaker_notes` field wired into the deck as reveal `<aside class="notes">`
(speaker view; hidden on-slide and in PDF via print.css); timing folded into `qa_report.mjs`
(prints estimated talk length, flags note-less slides P3). `references/design-system.md` fleshed
(type ramp / 60-30-10 single accent / Okabe–Ito / Assertion-Evidence default / anti-AI-slop /
CJK / speaker-notes / showcase-lock); `slide-spec.md` documents `speaker_notes`. 5 node:test.
**Validated:** authored grounded speaker notes for all 12 PANDA slides → handout + 6:17 estimate
(tool correctly flags it as thin for a 15-min budget); notes verified absent from the printed PDF.
**Bilingual:** built/rendered a 中文 deck (`out/zh_smoke/`) — CJK glyphs (PingFang SC), mixed CN/EN,
KaTeX math beside Chinese, and 中文 punctuation all render cleanly with no tofu.
**Deviation:** conference-vs-组会 visual-distinctness check deferred to Stage 5 (needs the
conference deck type); the design system + 组会 register are in place. Three-tier theme disclosure
deferred (single theme needs it less).
**Deliverables (original plan):**
- `references/design-system.md`: type ramp anchored on body (≥24pt; back-of-room test), 60-30-10 single accent, **Okabe–Ito/Viridis color-blind-safe**, consistent method→color mapping, anti-AI-slop banned lists (frontend-slides) + page/theme-rhythm (ppt-master/guizang).
- **Assertion-Evidence/Tufte** results grammar default (ported huashu); dense reading-first allowance for method/results in this register.
- Three-tier layout disclosure (`_index.json` → `*.preview.md` → one `*.design.md`, ported frontend-slides); "show don't tell" 3 title previews + 2-page showcase grammar-lock (huashu).
- Speaker notes as spoken prose (150–400w) + timing estimate (words ÷ rate vs soft budget).
- English-default themes + CJK typography parity; notation/abbreviation key for dense talks.
**Validate:** same paper → a 组会 deck visibly distinct from a (stub) conference deck; back-of-room legibility; EN and 中文 both render cleanly; timing estimate produced.

## Stage 5 — Editable export, data-bound charts, breadth ✅ CORE DONE (2026-06-30)
**Goal:** co-author editability + true plots + expand beyond 组会.
**Delivered:** `scripts/export_pptx.mjs` — **editable PPTX** from the deck.json spec via pptxgenjs
(native titles/bullets/critique/agenda/references text + **real OOXML tables** + **native speaker
notes**; figures and equations rasterized to images, flagged as the honest degradation; inline
math kept as literal LaTeX). `scripts/lib/pptx_layout.mjs` (px→inch, table→rows, strip-inline-math,
collect-equations). `scripts/make_chart.py` — **data-bound** matplotlib charts (Okabe–Ito, values
plotted verbatim, length-mismatch is a hard error). `references/export.md`/`charts.md` fleshed;
`deck-types.md` fleshed with conference & 答辩 arcs/registers (authoring guidance — layouts already
support them). 5 node:test (pptx) + 5 pytest (make_chart).
**Validated:** exported PANDA → PPTX and inspected with python-pptx: 37 native text boxes, 4 figure
images, 12 native speaker-note slides. Exported Attention → PPTX: a **real editable OOXML table**
with the true numbers (`Transformer (big) | 28.4 | 41.8 | 2.3·10¹⁹`) + the equation as an image.
Rendered a data-bound BLEU bar chart — heights match the extracted values exactly, max highlighted.
**Deviation:** PPTX is built **spec→pptxgenjs**, not huashu's HTML→OOXML scrape (more reliable;
equations become images rather than OMML). **Deferred / not built:** conference & 答辩 are guidance
only (no demo deck authored); **Beamer** export, **OCR** for scanned/2-column PDFs, and **draft-deck
ingestion/restyle** are not implemented.
**Deliverables (original plan):**
- `scripts/html2pptx.mjs` (ported huashu): editable PPTX with vector/MathML equations + real OOXML tables; honest fidelity-degradation warning.
- `scripts/make_chart.py` (**new**): data-bound matplotlib/Vega plots from extracted numbers (never painted).
- Additional deck types (conference, 答辩) with their arcs/registers/required archetypes; opt-in Beamer backend; OCR fallback for scanned/2-column PDFs; draft-deck ingestion/restyle.
**Validate:** PPTX opens editable with equations/tables intact (or warns); charts match extracted numbers exactly; conference vs 答辩 vs 组会 produce visibly different decks from one paper.

---

## Suggested first action
Stage 1 is self-contained and provides the strongest signal (faithful digest is the foundation everything else rests on). Recommend building Stage 1 against a concrete test paper — propose **"Attention Is All You Need"** (ppt-master already ships a worked example deck for it, giving a reference to compare narrative/figure choices against) plus one equation-heavy paper of your choice from your Zotero library.

---

# AESTHETICS PROGRAM (post-Stage-5, started 2026-07-02)

North-star: the best-looking **and** most usable academic-PPT skill, with minimal manual edits.
Calibration (locked with user 2026-07-02): visual register = **Nature/Science figure-editor**;
next deck type after 组会 = **conference report**; **no hard time/token ceiling** on the aesthetic loop.

Thesis: the pipeline had no step measuring *beauty* — the QA gate only checks correctness, so decks
converge on "clean but flat." Fix = engineer aesthetics into a scoreable feedback loop (rubric →
screenshot review → rework), a real design-token system, and content-adaptive layout. Every change
is regressed on a multi-paper benchmark to avoid single-paper overfit.

## M1 — Design-system 2.0  ✅ DONE (2026-07-02)
- `references/aesthetics-review.md`: 6-dimension scoreable rubric (hierarchy, typography, space,
  figures, color, consistency; 0–4 each; forced weakest-3 anti-inflation; run on *rendered pixels*
  with a different persona than generation). Runs after the integrity gate, never overrides it.
- `04-panda-aesthetic-audit.md`: scored PANDA baseline (~15/24; figures dim 1.5; bullet-ratio 36%)
  → ranked defect backlog mapped to milestones.
- `assets/templates/deck-stage/tokens.css` (NEW): modular 1.25 type scale, 8pt spacing grid, line
  measure, figure-matting tokens. Wired into `build_deck.mjs` (loads before viewport-base + theme).
- `journal-club.css` refactored to reference tokens; **fixed** the annotation↔figure collision
  (annotation is now a normal flow row below the figure, never floated), unified figure matting
  (consistent mat/hairline/radius/shadow deck-wide), title mid-phrase wrap (`text-wrap: balance`),
  and recomposed the cover (editorial accent bar).
- **Validated:** all fixes are CSS/token-level → PANDA EN + ZH improved on rebuild with **zero
  deck.json edits** (proves the minimal-manual-edit promise). 28 node + 39 py tests green.

## M2 — Figure pipeline (the biggest lever)
Root cause (confirmed): `detect_figures.grow_figure_region` grew to the whole page block, so crops
carried the paper's running head ("Article") + DOI band and shrank multi-panel figures to illegible
(`figures.json`: `figure_bbox` y≈20pt = page top, full 2-col width).

### M2a — furniture strip  ✅ DONE (2026-07-02)
- TDD: added `TestStripMarginBands` (5 tests, RED→GREEN) including a PANDA-regression case asserting
  the grown figure region excludes the running head.
- `detect_figures.strip_margin_bands(rects, page_rect, header_frac=.06, footer_frac=.06)`: drops any
  rect lying *entirely* within the top/bottom margin band (a figure that only dips in straddles the
  edge and is kept — never clipped). Applied in `detect()` before growing.
- **Validated on the real Zotero PDF:** all 5 PANDA figure crop-tops moved from y≈20 (page header) to
  y≈47–54 (below the band); re-cropped, both EN+ZH decks rebuilt, PDFs+PPTX regenerated, QA PASS
  (EN 14:27 / ZH 12:55), 28 node + 44 py green. Header/DOI gone on slides 5/7/8/9.

### M2b — panel extraction  ✅ DONE (2026-07-02)
- TDD: `TestDetectPanels` (5) + `TestPanelBbox` (3), RED→GREEN.
- `detect_figures.detect_panels(label_spans, figure_bbox)`: picks the style group (font,size) whose
  single-letter labels form the longest contiguous a,b,c… run (rejects caption sub-labels by
  style/position), then derives each panel's bbox by nearest-neighbour row/column boundaries.
  `detect()` now emits `panels:[{label,bbox}]` per localized figure (via new `_page_letter_spans`).
- `crop_figure.panel_bbox()` + `crop_panel()` crop one panel tight (no fractional pad → no neighbour
  bleed, 300 dpi). *Which* panel is the presenter's judgment (set in the spec); crop is deterministic.
- **Validated:** slide 8 swapped from the illegible 6-panel Fig 3 to **Fig 3a** (lesion-detection ROC,
  PANDA ★ operating point above all 33 readers) — legible + on-message; caption/annotation rewritten
  to match the panel (still grounded: 0.996 / 34.1 / 6.3). EN+ZH rebuilt, PDFs+PPTX regenerated,
  QA PASS, 28 node + 52 py green.
- Note: left-column ROC panels (b,c) over-grow when a tall right panel (d,e) spans rows — anchor
  partitioning is best-effort; clean panels (a, f) crop perfectly and the agent picks one that does.

### M2c — native chart redraw  ✅ DONE (2026-07-02)
- Resolved the split-decimal blocker at the *grounding* layer (the right place): `qa.groundNumbers`
  now rejoins decimals the PDF split across whitespace (`/(\d+\.)\s+(\d+)/`→`$1$2`) so a value that
  IS in the paper still grounds — a redrawn-chart number can't be false-flagged. TDD (RED→GREEN),
  new test in qa.test.mjs. (Also hardens the gate generally.)
- Built a native grouped-bar chart via `make_chart.py` from the authoritative grounded sentence
  ("outperformed the average reader by 14.7% sens / 6.8% spec for lesion detection, and 34.1% /
  6.3% for PDAC identification") — values verbatim, Okabe-Ito, deck palette. Inserted as an
  assertion-evidence slide (chart PNG = `figure.src`, caption notes it's a re-plot, not a paper
  figure); numbers echoed in the annotation are grounded.
- Also fixed a task-mixing bug this surfaced: slide 8's ROC is *lesion detection* (Fig 3a), so its
  annotation now states the lesion-detection story; the *PDAC-identification* margins live on the
  new chart slide — each slide is task-consistent.
- **Validated:** EN 14→15 slides (15:07, on the 15-min target), ZH 15 slides (13:33), both QA PASS
  (all 4 chart values grounded), 29 node + 52 py green, PDFs+PPTX regenerated (15 slides each).
- Known polish: the chart's own axis labels/legend stay English in the ZH deck (matplotlib CJK font
  not wired); title/caption/annotation are Chinese. Common in practice; localized chart labels = later.

## M3 — Content-adaptive layout + conference theme

### M3a — theme architecture + conference theme  ✅ DONE (2026-07-02)
- Refactored the CSS into a clean 3-layer system (the payoff of the M1 token work):
  `tokens.css` (palette + modular scale + 8pt grid + matting + **flavor hooks**
  `--title-font`/`--marker-font`/`--divider-*`/`--fig-cap*`) → `base-theme.css` (all structural
  component rules, referencing tokens) → thin **flavor** files. `journal-club.css` is now ~10 lines
  (its values equal the token defaults → **byte-identical render, zero regression**, verified on the
  PANDA cover).
- New **conference.css** (~40 lines, almost all token overrides): larger scale for a big room,
  figures dominate (`--fig-cap` 780 / `--fig-cap-ae` 660), full-bleed deep-blue **cover + section
  dividers** (high-impact, `print-color-adjust: exact` so they print). Same Nature/Science DNA,
  punchier register.
- `build_deck.mjs`: `meta.theme` selects the flavor (`journal-club` default, `conference`); unknown
  → journal-club (never throws). Always loads tokens + base-theme + one flavor. TDD: 3 node tests
  (default loads journal-club not conference; `theme:conference` loads conference not journal-club;
  bogus → journal-club).
- **Validated:** rendered the PANDA content under `theme:conference` (`out/pancreatic_conf/`) —
  dark full-bleed cover in both HTML and **PDF** (`printBackground:true`), bigger figures; journal-club
  decks unchanged and still QA PASS. 32 node + 52 py green.

### M3b — content-adaptive layout + purpose-built conference deck  ✅ DONE (2026-07-02)
- **Deck-level layout metric (deterministic, TDD):** `qa.layoutMix(deck)` → {slides, bullets,
  bulletRatio, maxRun, counts}. `qa_report.mjs` emits P3 aesthetic nudges: bullet-ratio > 1/3
  ("prefer figures/tables/charts") and ≥4 identical layouts in a row ("vary the rhythm"). Operationalizes
  the rubric's deck-level check. 2 new node tests.
- **Purpose-built conference PANDA deck** (`out/pancreatic_conf/`, `theme:conference`, 11 slides):
  restructured from the 15-slide 组会 deck into one-idea-per-slide — dropped critique/discussion/
  model-evolution, converted every bullet slide to a figure / the redrawn chart / a real-world
  **results-table**, and added three `section` dividers (Problem / Evidence / Takeaway) for rhythm.
  **Bullet-ratio 33% → 0%**; mix = paper-title·1, section·3, assertion-evidence·5, results-table·1,
  references·1 (maxRun 3). QA PASS, all numbers grounded (reused the QA-passed set), dark cover +
  section dividers print in PDF; PDF + PPTX rendered. 34 node + 52 py green.
- Note: conf deck currently estimates 5:30 (concise notes) — a demo of structure/theme; expand notes
  to fill a 12–15 min slot. Leftover stale PNGs (slide-12..15) sit in its `deck/slides/` from the
  earlier theme demo (deck.html/pdf are the canonical 11 slides).

### M3c — content-shape auto-suggest (optional, later)
A `suggest_layout(content-signals)` helper + multi-candidate generation with rubric pick, to make
layout selection assisted rather than hand-authored. Deferred — hand-authoring + the layoutMix nudge
already gets the quality; auto-suggest is a convenience.

## M4 — Benchmark + export parity

### M4a — PPTX content-parity regression  ✅ DONE (2026-07-02)
No LibreOffice here (and a pixel diff is flaky), so parity is checked as **content/structure**, which
is what actually protects "minimal manual edits": every load-bearing element in the spec must survive
into the PPTX *natively*. `scripts/verify_pptx_parity.py`: pure `check_parity(deck, extracted)`
(unit-tested) + `extract_from_pptx` (python-pptx adapter). Verifies per slide — slide count; every
expected text (titles, bullets, annotations, **table cells**, captions, questions, references, cover
metadata) present natively; speaker notes native; a figure → a picture shape; a results-table → a
native table. Figures/equations are images *by design* (parity requires the image present, not text).
TDD: 11 unit tests (dropped annotation / notes / figure / table / slide-count all flagged) + an
integration test on real decks. **Validated: attention, pancreatic, pancreatic_zh, pancreatic_conf
all parity-clean.** 70 py + 34 node green.

### M4b — benchmark harness  ✅ DONE (2026-07-02)
`benchmarks/manifest.json` (seed = 4 real decks: Transformer NLP + PANDA en/zh/conference) +
`scripts/run_benchmark.mjs`: one command runs every deck through all three gates (integrity QA gate,
PPTX parity, layout-mix) and prints a dashboard; exits non-zero on any P0 or parity issue (CI signal).
`benchmarks/README.md` documents the set and how to grow toward 15+ cross-discipline papers. First
run: all 4 PASS/REVIEW, parity clean; dashboard surfaced that the journal-club PANDA decks are 33%
bullets (vs conference 0%) — a real content-pass target.

### M4c — grow to 15+ papers  ▶ ONGOING
Add CV / theory / biology / more-NLP papers (esp. equation-dense, scanned/2-column, many-panel,
table-rich) so the harness exercises every archetype. Each: prepare_source → author → build → add to
manifest → must reach PASS + clean parity.

## M5 — Polish + external eval  ✅ DONE (harness + polish; competitor run pending samples)
- **Skill integration (the polish that matters most):** wired M1–M4 into `SKILL.md` so the skill
  actually invokes them — step 5 picks `meta.theme`; step 6 runs the `aesthetics-review.md` rubric
  loop on rendered pixels + bullet/monotony nudges; step 7 runs `verify_pptx_parity.py` and
  `run_benchmark.mjs`. Routing table gains aesthetics-review + themes rows; figures-tables marked live.
- **Two-axis eval scorecard** (`benchmarks/eval/scorecard.md`): **aesthetics** (6-dim rubric, aim to
  be competitive) scored *separately* from **academic fidelity** (F1–F7 pass/fail: grounded numbers,
  vector equations, real tables, cited crops, resolved refs, flags-not-fills, PPTX parity — where
  generic tools structurally lose). Includes the honest M1→M4 self-assessment (PANDA journal-club
  **~15 → ~22 / 24**, biggest lever Figures 1.5→3.5; conference ~23/24) and a turnkey blind
  competitor protocol (same inputs → anonymize → ≥3 raters → aggregate both axes).
- **Top-level `README.md`**: front door + worked-example gallery + run/test/benchmark commands.
- **Pending (needs the user):** actually run Gamma / Canva AI / PowerPoint Copilot on the benchmark
  papers and record `benchmarks/eval/results-<date>.md` — no accounts here to generate competitor
  decks. Aesthetics self-scores are builder-directional, not external blind ratings.

## Beyond M5 (backlog)
- Grow the benchmark toward 15+ cross-discipline papers (M4c).
- Apply the M3b bullet-reduction to the journal-club decks (dashboard shows them at 33%).
- Expand the conference deck's speaker notes to fill a 12–15 min slot.
- Deferred capabilities: Beamer export, OCR for scanned/2-column PDFs, draft-deck restyle,
  content-shape auto-suggest (M3c), CJK-labeled charts.
