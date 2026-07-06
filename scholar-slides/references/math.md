# Equations — KaTeX/LaTeX rendering, numbering, inline math

**Status: live (Stage 2).** Implemented in `scripts/lib/math.mjs`; used by every layout via
`renderText`, and by the `equation` layout via `renderMath`.

## The fidelity contract

Math is rendered **server-side by KaTeX to vector HTML + MathML** — selectable, accessible,
never a raster image. This is non-negotiable (see `references/integrity.md`): an image model
never touches an equation. The only place math becomes pixels is the PPTX export (equations
render to PNG there because PowerPoint has no KaTeX), and that degradation is **flagged**, not
silent — see `references/export.md`.

## Authoring math in `deck.json`

- **Display equations** use the `equation` layout:
  ```json
  { "layout": "equation",
    "action_title": "Attention is a scaled dot-product softmax",
    "equations": [{ "latex": "\\mathrm{Attention}(Q,K,V)=\\mathrm{softmax}\\!\\Big(\\frac{QK^{\\top}}{\\sqrt{d_k}}\\Big)V",
                    "numbered": true, "num": "1" }],
    "note": "where $d_k$ is the key dimension …",
    "source_ref": "§3.2.1" }
  ```
  `numbered: true` renders the paper's own equation number — keep it **identical to the paper**
  so the audience can cross-reference.
- **Inline math** works in any text field (`points`, `note`, `annotation`, titles): wrap in
  `$…$`; display blocks inside a text field use `$$…$$`. Rendered by `renderText`
  (`scripts/lib/math.mjs:22`).
- Errors do not crash a build: a bad macro renders as a visible red `katex-error` span, which
  `validate_deck.mjs` then reports as **P1** — fix the LaTeX, never screenshot around it.

## Rules that keep math honest and consistent

1. **Copy LaTeX from the source** (paper LaTeX/arXiv source when available via
   `prepare_source.py`) rather than re-deriving; transcription is fidelity, re-derivation is risk.
2. **One symbol set per deck.** If the paper writes $d_k$, every slide writes $d_k$ — no
   renaming, no "simplified" notation without an explicit "(notation simplified)" note.
3. **Numbers inside equations are grounded** like any other number (`qa.mjs groundNumbers`).
4. **Literal dollar amounts** in prose (`$5`) will be parsed as math if paired with another
   `$` on the same line — escape as `\$` or reword when a bullet must contain two of them.
5. Keep emphasis markers (`==…==`) **outside** `$…$` spans: emphasis runs per non-math slice
   and must not straddle a math boundary (`math.mjs:17-21`).

Theorem/algorithm blocks: not built as dedicated layouts — set them as display equations or a
`two-column` with the statement in text; a dedicated block layout is future work.
