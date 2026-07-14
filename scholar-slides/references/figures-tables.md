# Figures & Tables — bbox crop, provenance, real tables

How Stage-1 assets become slide content. Figures: reuse the bbox-cropped real image in a
deterministic figure container with `Figure N: caption [cite]`, `fit: contain` (never crop a data
figure). Tables: rebuild as **real text/HTML tables** from extracted numbers (baselines labeled,
best bolded, units in headers, significance markers) — never a picture of a table; the Stage-1 crop
is only a reference snapshot.

## Clean crops (no source-paper furniture)  — implemented

A figure crop must look like a figure, not a screenshot of a journal page. `detect_figures.py`
localizes the tightest figure region and **strips page furniture** before the crop:

- `strip_margin_bands(rects, page_rect, header_frac=0.06, footer_frac=0.06)` drops any content rect
  lying *entirely* within the page's top or bottom margin band (the running head — e.g.
  `Article  https://doi.org/…` — and the running foot / page number). Without this, the
  region-grower bridges the small gap between the header and the first panel and swallows the header
  and DOI band into the crop (the PANDA bug: crop tops sat at y≈20pt, the page top).
- "Entirely within" is deliberate: a figure that only *dips* into the margin straddles the band edge
  and is kept — furniture is removed, real figure content is never clipped.
- Geometric and journal-agnostic (no journal-name allow-list). Runs in `detect()` before
  `grow_figure_region`.

Rendering side (theme): every crop gets one unified **matting** treatment (mat background, hairline
border, radius, soft shadow) so figures from different pages read as one system, and figure
annotations are a flow row *below* the image (never floated on top → no collision). See
`aesthetics-review.md` dimension 4 (figures) for the scoreable bar.

## Multi-panel figures — one panel per slide  — implemented

A dense multi-panel figure (e.g. a Nature Fig with panels a–f) shown whole is illegible from the
back row and scores ≤2 on the figures dimension. Rule: **one panel per point.** Show the single
panel that carries the slide's assertion, enlarged; put other panels on their own slides or drop
them.

- `detect_figures.detect_panels(label_spans, figure_bbox)` finds panels by their labels: it picks
  the one style group (font, size) whose single letters form the longest contiguous a,b,c… run
  (this rejects caption sub-labels, which are a different, smaller font), then derives each panel's
  bbox by nearest-neighbour row/column boundaries. `detect()` emits `panels:[{label,bbox}]` per
  localized figure. Anchors are reliable; a panel bordered by a tall multi-row neighbour may
  over-grow — pick a panel that crops cleanly (corner/edge panels do).
- `crop_figure.crop_panel(pdf, record, label, out)` crops one panel tight (no fractional padding,
  300 dpi) so it doesn't bleed into the neighbour's label.
- **Which** panel to show is the presenter's judgment — set `figure.src` to the panel crop in the
  deck spec, and make the caption/annotation describe *that panel* (fidelity: don't caption panel a
  with panel b's numbers). Rendering stays deterministic.
- When a panel's underlying data is extractable, prefer a **native redraw** (`make_chart.py`, deck
  palette, values verbatim through the number-grounding gate) over cropping the bitmap.

## Provenance & fidelity invariants

- Every reused figure carries its `[cite]`; never present a crop without provenance.
- Never redraw a figure's data by hand or by image model — reuse the real crop, or redraw a chart
  only from **extracted, grounded** numbers (fidelity-first; the QA gate rejects ungrounded numbers).
- Tables are real data tables, not pictures; the crop is a reference snapshot only.

## Figure display size (the protagonist rule)

- The layout, not the source bitmap, decides display size: `--fig-cap` / `--fig-cap-ae` render
  every figure at a fixed target height (tokens.css). A small crop or a DPI-stamped PNG must
  never make the figure shrink — if a crop looks small on the slide, the space budget is the
  cause, not the pixels.
- **Vertical budget on the 1080px stage (assertion-evidence):** title + caption + annotation +
  source leave roughly 560px for the figure. Keep the caption to **one line** and the annotation
  to **≤2 lines (~240 chars combined)** — longer detail belongs in `speaker_notes`. The QA report
  nudges (`figure-crowded`) past that threshold.
- **Hero mode (`figure.hero: true`) — when the figure carries the slide alone.** The caption
  folds into the source footer, the annotation is **banned** (`validateSpec` errors; move the
  text to `speaker_notes`), the chrome tightens, and the image cap rises to `--fig-cap-hero`
  (700px). This is the fix when the QA legibility projection fires on a dense diagram: on the
  GLM-5 deck it took Fig. 7's smallest label from a projected 8.7px to 12px. Use it whenever the
  title states the claim and the figure is the whole evidence — most headline-result slides.
- **Banner crops (aspect ≥ 2.2) size by width, automatically.** The build probes each crop's
  PNG dimensions and hands wide ones `--fig-ar`, so CSS sizes them to the `--fig-wide-w` budget
  (1382px ≈ 80% of the content width) instead of starving them under the height cap.
- Crop at **300 dpi** (`crop_figure.py` default) so the protagonist-height rendering stays crisp
  on a projector; `figure_clip` stops the crop above the paper's own caption band, so the deck
  never shows a double caption.

## When the legibility check still fires — the escalation ladder

`figure-text-illegible` / `figure-compressed` (P2, see `references/aesthetics-review.md`) mean
the audience cannot read the figure's own labels. Escalate in this order:
1. **Hero mode** (above) — free if the annotation is expendable.
2. **Crop ONE panel** — when the finding mentions labeled panels (detect_figures found an
   a/b/c… grid), crop the single panel that carries the slide's point
   (`crop_figure.crop_panel`); never show six illegible panels when one legible panel wins.
3. **Redraw natively** — when the "figure" is really a chart and its numbers are in the digest
   (or otherwise grounded in the paper text), rebuild it with `make_chart.py`: deck palette,
   deck type ramp, arbitrarily legible. Caption must say it is a re-plot, not a paper figure
   (e.g. the GLM-5 AA-index slide). Numbers that appear ONLY inside a raster figure cannot be
   redrawn — they would not ground; fall back to 1–2.

## Native-chart discipline (make_chart.py defaults; keep specs within them)

- **Bar lengths are computed, never eyeballed** — the spec's values are plotted verbatim
  (`chart_data` is unit-tested on this). Never post-edit a rendered chart image.
- **Category labels stay horizontal** (≤8 short categories). Rotated ticks read off-register
  next to the deck's upright type; `tick_rotation` falls back to 15° only when the axis is
  genuinely crowded (>8 categories or a >14-char label). If labels are long, shorten the
  *labels* (e.g. "Transformer (LLaMA)" → "Llama"), don't rotate the axis.
- **Every data point carries a visible value label**, placed OUTSIDE the bar (a label inside a
  fixed-height bar clips exactly when the bar is short — the worst case). `render` does this
  automatically up to 12 bars; past that labels collide, so denser charts drop them — prefer
  plotting a *subset* (disclosed in the caption) over an unlabeled forest.
