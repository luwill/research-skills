# QA Self-Review — the CKPT-3 gate (integrity + static + render)

**Status: live (Stage 3).** One command runs all three layers and emits a consolidated
P0–P3 report. The gate **surfaces** defects and flags; it does not certify truth — only the
human does, at Checkpoint 3.

```
node scripts/qa_report.mjs out/<stem>/deck out/<stem>     # deckDir + sourceDir
```
Writes `out/<stem>/deck/qa_report.json` and prints the report. Exit: `2` if any **P0**, `1`
if any **P1** (review required), `0` if only P2/P3.

## The four layers
1. **Integrity scan** (`lib/qa.mjs`, deck.json vs source paper text):
   - **Ungrounded number** — every number on a content slide must appear in the source paper
     text (`ingest.json` full_text). A number that does not is a likely fabrication
     (table/equation = P1, other = P2). Scientific notation is normalized (`10²⁰` → `1020`).
   - **Flags** — every literal `[MISSING]` / `[UNVERIFIED]` / `[REDRAWN]` / `[GENERATED]` is
     collected (P1) and must be acknowledged at CKPT-3.
2. **Static validation** (`validate_deck.mjs`, on built `deck.html`):
   - layout lock (every `data-layout` is a registered layout — P0), KaTeX error spans (P1),
     unrendered `$math$` (P2), missing figure files (P1).
3. **Render verification** (`verify_slides.mjs`, Playwright, per slide):
   - content overflow beyond the 1080 stage (P1), broken/empty images (P1), KaTeX errors
     actually rendered (P1), sub-legible font (< 18px on stage — P2);
   - deterministic aesthetics geometry (`lib/render_checks.mjs`): figure text projected below
     the 12px legibility floor (P2, exact via figures.json `min_font_pt`, else a compression
     heuristic) and canvas voids on fill-the-canvas layouts (P3) — details in
     `references/aesthetics-review.md`.
4. **Render review gate** (`renderReviewFindings` in `qa_report.mjs`):
   - the 6-dimension rubric loop must have run and written `<deckDir>/aesthetics_report.json`;
     a missing report is P3 `aesthetics-not-run`, a non-empty `rework` list is P2
     `aesthetics-rework-open`. The rubric itself lives in `references/aesthetics-review.md`.

## Severity → action
| sev | meaning | action |
|---|---|---|
| P0 | structural defect (unregistered layout) | **BLOCK** — cannot ship |
| P1 | likely-fabrication / broken render / unresolved flag | **REVIEW REQUIRED** at CKPT-3 |
| P2 | legibility / minor | consider fixing |
| P3 | note | optional |

Auto-fix the mechanical P1/P2s where possible (split an overflowing slide rather than shrink;
re-resolve a citation; re-crop a figure). Surface the judgment ones.

## [CHECKPOINT 3 — human truth sign-off]
Show the user the QA report and the rendered deck (PDF or PNG screenshots). They own the
**truth** decision the machine cannot make: review every `[MISSING]`/`[UNVERIFIED]`, every
flagged number, and every generated/redrawn asset. A deck ships only after the user accepts
each remaining flag. (Narrative arc-tension and speaker-notes timing checks are added in Stage 4.)

## Known Stage-3 limits
- Number grounding is substring-based against the PDF text layer: it catches fabricated
  distinctive values but can miss a number that coincidentally appears elsewhere in the paper.
  It is a safety net, not a proof of correctness — the human still verifies.
- Color-contrast / color-blind-safety checks are specified for Stage 4 (the theme is already
  Okabe–Ito + high-contrast by construction).
