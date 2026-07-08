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
  and DOI band into the crop (a real regression on a journal-formatted medical paper: crop tops sat
  at y≈20pt, the page top — see `TestStripMarginBands` for the pinned regression case).
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
- Crop at **300 dpi** (`crop_figure.py` default) so the protagonist-height rendering stays crisp
  on a projector; `figure_clip` stops the crop above the paper's own caption band, so the deck
  never shows a double caption.
