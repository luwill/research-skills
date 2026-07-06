# Design System — the academic visual language

**Status: live (Stage 4).** The baseline theme is `assets/templates/themes/journal-club.css`
(+ `deck-stage/viewport-base.css`, `print.css`). Academic design is a **constraint, not a
canvas**: reviewers read flashiness as a lack of substance. Restraint is the aesthetic.

## Tokens (journal-club theme)
- **Type ramp anchored on a 32px body** (the "back-of-room squint" floor; the QA gate flags
  rendered text < 18px). Action titles are a serif (Georgia) for scholarly character; body,
  data, and captions are a clean system sans. One display + one body family per theme.
- **Color = 60-30-10, single accent** (`--accent: #15497a`, a deep academic blue — *not* the
  AI-slop indigo `#6366f1`). Generous whitespace; no gratuitous gradients / 3D / clip-art.
- **Data palette = Okabe–Ito** (color-blind-safe). Never encode meaning by color alone; keep a
  **consistent method→color mapping** across every results slide (Method A is always one color).

## Inline semantic emphasis (conference-report register — the default)
Body prose carries a **semantic** highlight layer: color encodes *meaning*, never decoration. Mark a
phrase with the inline syntax in `deck.json` (rendered by `renderText`; see `scripts/lib/emphasis.mjs`).
Titles now take the accent by default (`--title-ink`) and eyebrows render as a filled chip.

| Marker | Role | Treatment | Use for |
|---|---|---|---|
| `==text==` | metric | **bold** (weight-only, tabular-nums; no color) | numbers, deltas, complexities |
| `==k\|text==` | key | accent blue | the "so what" claim of the slide |
| `==p\|text==` | pos | green | a win: SOTA, beats X, gold |
| `==w\|text==` | warn | vermillion | a limitation / caution (critique slides) |

- **Designed, not decorated.** Cap the *added* treatments (metric/pos/warn) at **≤2 per slide** —
  `key` reuses the base accent so it is free. `qa_report` nudges (`over-highlighted`) past the cap;
  this is what stops a slide from getting over-marked. (No highlighter — `metric` is weight-only.)
- **Semantic, not per-keyword.** Highlight the number, the claim, the win — not every noun. A phrase
  that highlights nothing is fine; a slide that highlights everything is a defect.
- **Auto-applied at Stage 4** (per-slide spec): numbers→metric, the conclusion→key, critique
  points→warn. Stays vector/text and color-blind-safe (all four are Okabe–Ito hues); markers are
  stripped natively in the PPTX (parity-verified), so editability is unaffected.
- **Constraint:** a highlighted span may not straddle inline `$math$` — keep short metric labels as
  plain text (e.g. `O(L²)→O(Lk)`), and use the `equation` layout for real display math.
- **Not in titles.** Action titles already carry the accent (`--title-ink`), so emphasis inside a
  title is a no-op by design — base-theme neutralizes all four roles there (accent-on-accent `key`
  was invisible-by-accident before; now every role is deliberately inert). Put the emphasis in the
  body or the annotation; the title IS the emphasis.

## Results grammar = Assertion-Evidence / Tufte (default)
A results slide is a full-sentence **action title** (the conclusion) + one high-data-ink figure
or real table + an annotation that points at the evidence. The `assertion-evidence` layout
encodes this; the figure is the protagonist, text annotates it. Titles state conclusions, never
labels ("…cuts error 23%", not "Results").

## Anti-"AI-slop" rules (enforced by convention + the layout lock)
- No identical card-grid on every slide; vary rhythm (figure slides vs text vs divider).
- No emoji-as-icons, no purple-gradient-on-white, no chartjunk / rainbow palettes.
- Banned display fonts: Inter / Roboto / Arial-as-display, and the model's default drift to
  Space Grotesk. Titles are narrative, never "Dive into…/Explore…/A journey through…".
- **Split to a new slide rather than shrink to fit** (the QA gate flags overflow).

## Bilingual / CJK (English-default, 中文 supported)
- The body/sans stack ends in `"PingFang SC", "Microsoft YaHei"` so 中文 renders without tofu;
  KaTeX math and Latin text mix cleanly with CJK (validated). Set `meta.language` to `en` or
  `zh`. Use 中文 punctuation (（）「」——) in 中文 decks; keep notation/abbreviations Latin.
- For dense talks, add a notation/abbreviation key early (a `bullets` slide) so a symbol means
  the same thing on every slide and matches the paper.

## Speaker notes & timing (Stage 4)
- Each slide may carry `speaker_notes` — **spoken prose** (what you say), 40–120 words, not a
  re-reading of the bullets: the transition in, what to point at, the number to land, the
  expected question. Rendered into the reveal speaker view (`<aside class="notes">`, press `s`),
  hidden on-slide and in the PDF.
- `scripts/speaker_notes.mjs <deck.json> [budgetMin]` writes a `notes.md` handout and estimates
  talk length (EN ~130 wpm + CJK ~240 cpm, 0.5-min/slide floor), warning if over/under budget.
  The QA report also prints the estimated talk length and flags note-less slides (P3).

## Show-don't-tell + showcase-lock (process)
Before mass-producing a deck: render the title + the 2 most-different slide types as a
"showcase", get the visual grammar signed off, then build the rest — turning N× rework into 2×.
(Three-tier layout disclosure `_index.json → *.preview.md → *.design.md` is the Stage-5 path for
carrying many themes without blowing context; the single journal-club theme needs it less.)
