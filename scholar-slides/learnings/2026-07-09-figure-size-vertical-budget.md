# Figures render too small on slides — the constraint is vertical budget, not width

**Problem (one line):** four GLM-5 slides showed paper figures so small their embedded labels
were illegible (~8.7px projected), and the planned fix ("width-driven CSS for wide figures")
would not have fixed three of them.

## The approach

1. **Measure before designing.** Probed the actual crop PNGs: the "too wide" figures were
   aspect ≈ 1.8, not banner-wide (≥ 2.2). Only 1 of 4 qualified for the planned width fix.
2. **Find the real binding constraint.** Instrumented one slide with Playwright
   (`getBoundingClientRect` on title-bar / body / figure / footer): the image was
   flex-squeezed by *chrome* — eyebrow + title + caption + annotation + footer left ~450px of
   a 936px stage for the figure. Width had nothing to do with it.
3. **Fix the constraint, not the symptom.** Built `figure.hero` mode: caption folds into the
   source footer, annotation becomes a *spec validation error* (its text moves to
   speaker_notes), chrome margins tighten. The reclaimed ~200px went straight to the image
   (projection 8.7px → 12.0px).
4. **Keep the width fix for the case it actually fits.** Build-time PNG-IHDR probe (26 bytes,
   no decoder) classes ar ≥ 2.2 crops `wide` and passes `--fig-ar` to CSS:
   `height: min(cap, widthBudget / ar)`.
5. **Make the detector arithmetic-honest.** Legibility projection
   `min_font_pt × rendered_px / bbox_pt_width` — DPI cancels, no calibration needed. But the
   projection lies when the shipped crop is a manual re-crop (different shape than the
   detected bbox), so: **compare crop aspect vs bbox aspect; >20% off → distrust metadata,
   fall back to the pixel-compression heuristic.**
6. **When display size can't win, change the artifact:** if the "figure" is a chart whose
   numbers are grounded in the paper *text*, redraw it natively (deck palette, any size);
   caption must declare it a re-plot. Numbers that exist only inside a raster figure cannot
   be redrawn — they would fail number-grounding.

## Judgment calls (deliberately NOT done)

- **Did not filter the 4.4pt spans** to make the 12px check pass — inspected them first; they
  were real content labels ("User message 1"), so the flag was honest. The final 12.0px
  borderline P2 was *accepted and documented*, not gamed away (e.g. by shrinking figure
  matting, which would break deck-wide consistency).
- **Did not center bullet slides** to fill their bottom void — that reverts a previously
  locked decision (top-anchor); the void is an authoring nudge instead.
- **Did not redraw the 30-model leaderboard** with all its bars — only 2 of the 30 values
  appear in the paper text; a full redraw would fabricate 28 numbers. Redrew exactly the
  grounded pair.

## Reusable rule

When rendered content is "too small", measure which axis actually binds before writing the
fix — in a fixed-stage layout it is usually the *other* axis's chrome, and the durable fix is
a mode that deletes chrome, not a bigger size token. And any "exact" quality check built on
stored metadata needs a cheap consistency guard (shape/aspect match) that demotes it to a
heuristic when the metadata no longer describes the artifact.
