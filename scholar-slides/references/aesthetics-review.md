# Aesthetics Review — the visual QA loop (Nature/Science figure-editor register)

The integrity gate (`qa-self-review.md`) proves a deck is *correct*: numbers grounded, no
overflow, no broken images, no bad LaTeX. It says nothing about whether the deck is *good-looking*.
This file is the missing half: a **scoreable rubric** that turns "it feels a bit flat" into a
ranked, fixable backlog, plus the loop that spends that backlog down.

Design target (locked): **Nature / Science figure-editor.** Precise, restrained, data-forward,
publication-grade. Not keynote-flashy, not Tufte-austere. One accent, disciplined type scale,
figures are protagonists and are legible, every mark earns its place. When in doubt, remove.

> This is a **rigid** loop for the RENDER→SELF-REVIEW stage. Run it on rendered pixels
> (screenshots), never on the JSON — the whole point is to see what the audience sees.

---

## How to run it

1. Render per-slide PNGs (`render_deck.mjs <deck.html> png <dir>`).
2. Score **every slide** on the six dimensions below (0–4 each). Look at the *pixels*.
3. **Forced critique (anti-inflation):** for each deck you MUST name the **weakest 3 slides**
   and at least one concrete defect per scored dimension, even if the deck looks fine. A pass
   with no named defects is an invalid pass — re-look.
4. Any slide with a **dimension ≤ 2** or a **total < 18/24** is a *rework* slide. Fix, re-render,
   re-score that slide. Repeat until no rework slides remain OR two passes yield no gain.
5. Report deck-level score = mean of slide totals, plus the weakest-3 list.

Use a **different persona** for scoring than for generating ("You are a Nature figure editor
preparing this for print — be unkind"). Same-model self-review has correlated blind spots; the
persona shift is what makes the second look find anything.

---

## The six dimensions (0–4 each, 24 max)

Anchors: **0** = broken/embarrassing · **1** = amateur · **2** = acceptable-but-flat ·
**3** = polished · **4** = publication-grade (indistinguishable from a Nature figure editor's work).

### 1. Hierarchy & focus — "what do I look at first?"
One clear entry point per slide; the eye lands on the assertion or the key mark, then flows.
- **4** Instant focal point; title→evidence→takeaway reads in one sweep; supporting elements recede.
- **≤2** Competing elements, no clear first-read, or the point is buried in a wall of equal-weight text.
- Kills: >1 focal element; body text same visual weight as the title; decorative elements louder than data.

### 2. Typography — scale, measure, rhythm
- **4** Modular scale (one ratio), consistent leading, controlled measure (EN ≤ ~65 chars/line,
  CJK ≤ ~35), no orphans/widows, no awkward 2-line title breaks, tabular figures in tables.
- **≤2** Ad-hoc sizes; titles wrap mid-phrase ("detect &\nclassify"); lines run edge-to-edge;
  ragged leading; body text below projection-legible floor.
- Kills: mixed font sizes off the scale; title measure so wide it wraps to an ugly 2 lines;
  paragraph-length "bullets."

### 3. Space & grid — alignment and breathing room
- **4** Everything on one grid; consistent margins; deliberate whitespace; nothing floats;
  no element touches or overlaps another; content is optically centered, not dumped.
- **≤2** Elements off-grid; inconsistent gutters; big dead zones with cramped content elsewhere;
  **any collision or overlap** (e.g. an annotation box sitting on top of a figure).
- Kills: overlap/collision (auto-cap this dimension at 1); content clustered in one corner with
  vast empty canvas; misaligned left edges across elements.

### 4. Figures & data ink — the protagonist test
This is where Nature/Science decks are won or lost.
- **4** One figure/panel per point, blown up and legible from the back row; clean matting
  consistent across the deck; **no source-paper furniture** (no captured "Article" header,
  running head, DOI band, page number, journal column rules); redrawn natively when data is
  extractable (matches deck palette/type); a single guided annotation.
- **≤2** Multi-panel figure shrunk until labels are unreadable; the crop carries the paper's own
  header/DOI/page furniture; inconsistent framing (different borders/backgrounds/aspect discipline);
  raw screenshot look.
- Kills (each caps this dimension at 1): illegible embedded text; visible captured page furniture;
  the figure is obviously "a screenshot from a PDF."

### 5. Color & contrast — discipline and accessibility
- **4** One accent used with intent; Okabe-Ito (or equivalent) categorical data palette applied
  consistently (method→color stable deck-wide); AA contrast on all text; color never the sole
  carrier of meaning; imported figure colors reconciled with the deck (not clashing).
- **≤2** Accent sprinkled decoratively; palette drifts slide to slide; low-contrast gray-on-white
  body; imported figure's colors fight the theme.
- Kills: banned "AI-slop" indigo (#6366f1) or unmotivated gradients; <4.5:1 text contrast.

### 6. Consistency & finish — does it read as one system?
- **4** Titles, rules, captions, sources, page numbers identical in placement and style on every
  slide; layouts feel like one family; export (PPTX) preserves it. Zero placeholder leakage
  in a *final* deck.
- **≤2** Caption style varies; source line drifts; accent thickness/positions wander;
  HTML looks designed but PPTX degrades.
- Kills: same logical element styled two ways across slides; `<presenter>`/`<date>` left in a final deck.

---

## Deck-level checks (beyond per-slide)

- **Bullet-slide ratio.** Count layouts. In the figure-editor register, > ~30% pure-bullet slides
  is a smell — the deck is telling, not showing. Prefer assertion-evidence, results-table, and
  redrawn charts over bullets. This is enforced deterministically: `qa.layoutMix(deck)` computes the
  ratio and `qa_report` emits a P3 nudge when bullet-ratio > 1/3 (and when ≥4 identical layouts run
  consecutively). The worked conference deck (`out/pancreatic_conf/`) is 0% bullets.
- **Rhythm.** No 3 consecutive slides of the same layout; section dividers break long runs.
- **Cover & close.** Title and references/questions slides get the same design care as the middle —
  they book-end the talk and set expectation.
- **One-system test.** Shuffle thumbnails; a stranger should see them as obviously one deck.

---

## Scoring output (what the loop emits)

```
deck: <name>   mean: <x.x>/24   bullet-ratio: <n/N>
weakest-3: [slide k (t/24, worst dim), slide j (...), slide i (...)]
rework:   [slides with any dim ≤2 or total <18]
per-dim deck means: hierarchy .. typography .. space .. figures .. color .. consistency
top defects (ranked, each -> concrete fix):
  1. <defect>  ->  <fix>  (dimension, severity)
  ...
```

**Persist the scores as `<deckDir>/aesthetics_report.json`** — this is what makes the loop a
gate instead of a suggestion. `qa_report.mjs` reads it (render-review stage): missing report →
P3 `aesthetics-not-run`; non-empty `rework` → P2 `aesthetics-rework-open`; the benchmark
dashboard surfaces `mean` in its `aes/24` column. Minimum schema (extra fields welcome):

```json
{ "deck": "<name>", "mean": 21.4, "outOf": 24,
  "slides": [ { "slide": 1, "dims": { "hierarchy": 4, "...": 3 }, "total": 19, "outOf": 20 } ],
  "weakest3": [ { "slide": 11, "total": 18, "worst": "figures" } ],
  "rework":   [ { "slide": 7, "reason": "figures 1 — smallest text projects ~9px" } ] }
```

Slides with no figure/data element score 5 dimensions (`"figures": null`, `outOf: 20`); a real
worked example lives at `out/glm5/deck/aesthetics_report.json`.

## Deterministic geometry checks (run automatically, before you score)

The render-verification pass measures what needs no judgment, so your scoring pass can spend
attention on what does. Emitted by `verify_slides.mjs` via `lib/render_checks.mjs`:

- **`figure-text-illegible` (P2, exact):** smallest source-text span inside the crop
  (`min_font_pt` in figures.json, from `detect_figures.py`) projected to stage px
  (`min_font_pt × rendered_px / bbox_pt_width`) falls below **12px**. DPI cancels out.
- **`figure-compressed` (P2, fallback):** no crop metadata (e.g. a manual crop) and a ≥1600px
  source is displayed below **45%** of its native pixels — labels almost certainly illegible.
- **`vertical-void` / `horizontal-void` (P3):** body content ends > **400px** above the stage
  bottom, or reaches < **62%** of the stage width, on layouts that are supposed to fill the
  canvas (covers, dividers, equations, references are exempt — their whitespace is composition).

These are floors, not the rubric: a slide can pass all four and still be flat. Score it.

Severity maps to the same ladder as code review: **CRITICAL** (collision, illegible figure,
captured page furniture, placeholder leak) blocks; **HIGH** (off-grid, title mis-wrap, bullet
overload) should fix; **MEDIUM/LOW** polish.

## Relationship to the integrity gate

Aesthetics review runs **after** the integrity gate passes and **never overrides it**: a
redraw/reframe that would drop a grounded number or alter data fails integrity and is rejected.
Fidelity first, then beauty. A slide must be *right* before it is allowed to be *pretty*.
