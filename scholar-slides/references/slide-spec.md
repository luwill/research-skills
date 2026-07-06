# Stage 2 — Deck Spec & Rendering (reveal.js + KaTeX)

**Status: live (Stage 2).** The model produces a **deck spec** (`deck.json`); the builder
renders it deterministically. Judgment lives in the spec (narrative, which figure, what the
title asserts); fidelity is guaranteed by the renderer (math → KaTeX vector, tables → real
`<table>`, figures → the real crop, every slide a registered layout).

## Pipeline
```
digest.json  --(you author)-->  deck.json  --build_deck.mjs-->  deck/deck.html (+ deck.print.html)
                                                  --render_deck.mjs--> deck.pdf (vector) / slides/*.png
```
```
node scripts/build_deck.mjs  out/<stem>/deck.json
node scripts/render_deck.mjs out/<stem>/deck/deck.html pdf            # one-page-per-slide vector PDF
node scripts/render_deck.mjs out/<stem>/deck/deck.html png slides     # per-slide screenshots (for QA)
```

## deck.json
```jsonc
{
  "meta": { "title": "...", "deck_type": "journal-club", "language": "en",
            "theme": "journal-club",             // visual flavor: "journal-club" (default) | "conference"
            "figures_dir": "figures",            // copied into deck/figures/ ; figure src = "figures/<id>.png"
            "source": { "title": "...", "arxiv_id": "..." } },
  "slides": [ { "layout": "<registered>", ... }, ... ]
}
```

Common slide fields: `action_title` (a full-sentence **assertion**, not a label), `eyebrow`
(small kicker), `source_ref` (provenance, shown bottom-left — mandatory for any factual slide),
`speaker_notes` (spoken script — see below). Inline `$math$` / `$$math$$` is allowed in any text
field and is KaTeX-rendered.

**`speaker_notes`** (Stage 4): spoken prose for the slide (40–120 words; the transition, what to
point at, the number to land, the expected question — not a re-reading of the bullets). Rendered
into the reveal speaker view (hidden on-slide and in the PDF). Run
`node scripts/speaker_notes.mjs out/<stem>/deck.json [budgetMin]` for a `notes.md` handout + a
talk-length estimate (bilingual-aware); the QA report also reports timing and flags note-less slides.

## Registered layouts (the layout lock — an unregistered layout throws)

| layout | key fields | use |
|---|---|---|
| `paper-title` | `title, authors, affiliation, venue, presenter` | opening slide |
| `section` | `num, title` | divider |
| `outline-agenda` | `title, items[], current` | agenda (highlights `current`) |
| `bullets` | `action_title, points[], source_ref` | motivation / contributions / generic |
| `assertion-evidence` | `action_title, figure{src,caption,cite}, annotation, source_ref` | **figure-forward** result/method (the default for evidence) |
| `equation` | `action_title, equations[{latex,numbered,num}], note, source_ref` | vector math |
| `results-table` | `action_title, table{...}, source_ref` | real data table |
| `two-column` | `action_title, points[]\|text, figure\|points2[], source_ref` | method / qualitative |
| `critique-concerns` | `action_title, points[{head,body}]` | **required for journal club** |
| `discussion-questions` | `title, questions[]` | **required for journal club** |
| `references` | `title, entries[]` | reference list |

`table` object: `{caption?, columns:[{label,unit?}], row_header?:bool, rows:[[cell]], footnote?}`
where a cell is a string/number or `{v, bold:true}` (bold the best per column). Units go in the
header, never in cells.

`figure` object: `{src, caption?, cite?, alt?, fit?}` — `fit` defaults to `contain` (a data
figure is NEVER cropped). `src` is the bbox crop from Stage 1; `cite` is mandatory provenance.

## Authoring discipline (per the locked 组会 register)
- Titles are **assertions** ("The big Transformer beats prior SOTA at a fraction of the cost"),
  never labels ("Results").
- Reading-first / high density is OK here: dense tables, full equations, ablations, failure
  cases belong on-slide (not pushed to an appendix).
- A journal-club deck MUST include a `critique-concerns` slide and a `discussion-questions`
  slide. Distinguish the paper's own stated limitations from *your* analysis (label "my analysis").
- Every factual slide carries a `source_ref`; numbers/figures come from the digest only.
- Integrity flags (`[MISSING]`, `[UNVERIFIED]`) are written as literal text and stay visible.

## CKPT-2 (before rendering the full deck)
Approve the **outline / arc** first (the ordered list of `action_title`s + which evidence each
uses). Re-sequencing and contribution emphasis are editorial calls the user owns. Optionally
render the title + 2 most-different slides as a "showcase" to lock the visual grammar before
building all N. Then render the full deck and proceed to the QA gate (Stage 3).

## Known Stage-2 limits
- Themes: `meta.theme` = `journal-club` (default, reading-first) or `conference` (big-room, punchy).
  Both share `base-theme.css`; a flavor is a thin token-override file. Unknown theme → journal-club.
- No automatic overflow detection yet (Stage 3 QA screenshots each slide and checks). For now,
  eyeball the `png` screenshots; split a slide rather than shrink to fit.
- Data-bound charts (`results-chart`) and editable PPTX export are later stages.
- Speaker notes + timing estimate are specified for Stage 4 (the spec already has room for them).
