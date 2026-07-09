# PANDA deck — aesthetic audit v1 (against references/aesthetics-review.md)

Scored on rendered pixels (`out/pancreatic/deck/slides/slide-*.png`, 14 slides), persona =
Nature figure editor. Target register: Nature/Science figure-editor. This is the baseline the
design-system upgrade is measured against.

## Deck-level score

| metric | value |
|---|---|
| mean slide total | ~15/24 (**acceptable-but-flat**) |
| bullet-slide ratio | **5/14 (36%)** — over the 30% smell threshold |
| weakest 3 | slide 8 (reader-study fig), slide 5 (overview fig), slide 1 (title) |
| per-dim deck means | hierarchy 3 · type 2.5 · space 2 · **figures 1.5** · color 2.5 · consistency 3 |

The deck is *correct and clean* (integrity gate passes) but flat. The score is dragged down almost
entirely by **figures (1.5)** and **space (2)** — and both trace to a single upstream bug.

## Root cause behind the worst findings (one bug, four bad slides)

The figure crops carry the **source paper's page furniture**: every figure slide (5, 7, 8, 9)
shows the journal's running header "Article" and the DOI band inside the image. Confirmed in
`figures.json`: `figure-1.figure_bbox = [39.7, 20.3, 561.3, 343.5]` — y starts at 20pt (top of the
Nature page) across the full two-column width. The region-growing localizer
(`detect_figures.grow_figure_region`) **grew to the whole page block**, not the figure proper, so it
swallowed the header, the DOI, and every sub-panel. Result: figures look like PDF screenshots and
multi-panel figures (slide 8 = panels a–f) are shrunk to illegibility. This is the #1 lever.

## Top defects (ranked → fix → milestone)

| # | defect | dimension | sev | fix | lands in |
|---|---|---|---|---|---|
| 1 | Figure crops include paper's "Article" header + DOI band | figures | **CRIT** | ✅ **FIXED (M2a)** `detect_figures.strip_margin_bands` drops top/bottom margin furniture before region-growing; PANDA crop tops moved y≈20→y≈51, header/DOI gone on slides 5/7/8/9 | done 2026-07-02 |
| 2 | Multi-panel figures (slide 8 a–f) shown whole → illegible | figures | **CRIT** | ✅ **FIXED (M2b)** `detect_figures.detect_panels` emits per-panel bboxes; `crop_figure.crop_panel` crops one panel tight; slide 8 now shows Fig 3a (lesion-detection ROC, PANDA ★ above all 33 readers) — legible, on-message, caption/annotation rewritten to match | done 2026-07-02 |
| 3 | Annotation box overlaps figure bottom (slides 5, 8, 9) | space | **CRIT** | reserve annotation as a grid row below the figure; figure `max-height` accounts for it — no float/overlap | **M1 (this pass, CSS)** |
| 4 | Inconsistent figure framing (aspect/border/bg vary slide-to-slide) | figures/consistency | HIGH | unified figure matting token: fixed frame, consistent bg + hairline + radius + centered | **M1 (this pass, CSS)** |
| 5 | 36% pure-bullet slides (3,4,6,10,11) | deck rhythm | HIGH | ✅ **ADDRESSED (M3b)** `qa.layoutMix` + P3 nudge (bullet-ratio >1/3, run ≥4); purpose-built conference deck (`out/pancreatic_conf/`) is **0% bullets** — bullets → figures/chart/results-table + section rhythm | done 2026-07-02 |
| 6 | Action titles wrap mid-phrase ("detect &\nclassify", "both\nsensitivity…") | typography | HIGH | tune title measure + `text-wrap: balance`; slightly smaller title step on the scale | **M1 (this pass, CSS)** |
| 7 | Title slide: content clustered mid-left, vast dead canvas, weak anchor | hierarchy/space | HIGH | composed cover: eyebrow + accent rule + baseline-gridded block; use the canvas | **M1 (this pass, CSS)** |
| 8 | Caption + annotation say overlapping things (redundant) | consistency | MED | annotation = the *takeaway*, caption = provenance only; de-dupe | content pass |
| 9 | Ad-hoc px sizes throughout theme (no shared scale) | typography | MED | design tokens: modular scale + 8pt grid; layouts reference tokens only | **M1 (this pass)** |
| 10 | Body bullets are full sentences (slide 3, 12) | typography | LOW | tighten to phrases; move detail to speaker notes | content pass |

## What this pass (M1) fixes now (CSS/tokens only, no crop rewrite)

Defects **3, 4, 6, 7, 9** are pure design-system issues, fixable without touching the figure
pipeline: introduce `tokens.css` (modular scale + 8pt grid + measure + matting), refactor the
theme to reference tokens, kill the annotation/figure collision, unify figure matting, fix title
wrap, and recompose the cover. Re-render and re-score to confirm the loop converts audit → gain.

Defects **1, 2** (the figure-furniture bug — the biggest lever) are algorithmic and get their own
TDD milestone (M2): a failing test that asserts a cropped PANDA figure contains no "Article"/DOI
band and, for multi-panel figures, a panel-level crop.
