# Stage 1 — Source Ingestion → Typed Paper Digest

**Goal:** turn a source paper into a faithful, typed **digest** — the single grounded
intermediate every later stage builds on. The scripts assemble raw material; *you* (the
model) synthesize the digest from that material, and you may use **only** what is in it.
No outside facts, no remembered numbers, no invented citations.

## 1. Run the bundler

```
./.venv/bin/python scripts/prepare_source.py <pdf path | arXiv id | arXiv URL> [--out-dir DIR] [--dpi 200]
```

Produces in `out/<stem>/`:
- `ingest.json` — `{path, n_pages, meta:{title, arxiv_id}, full_text}`
- `figures.json` — figure/table inventory (schema below)
- `figures/<id>.png` — clean bbox crops of figures (+ reliable table reference snapshots)
- `manifest.json` — counts + any FLAGGED assets

Read `ingest.json` (`full_text`) and `figures.json`, and look at the cropped images. If the
source is an arXiv paper, prefer fetching the **arXiv LaTeX source** when you need exact
equations or the `.bib` (Stage 1 uses the PDF text layer; arXiv-source ingestion is a
planned refinement — until then, transcribe equations from the PDF text carefully and mark
any you cannot read confidently as `[UNVERIFIED]`).

### figures.json record
```json
{
  "id": "figure-1", "kind": "figure|table", "number": "1", "label": "Figure 1",
  "caption": "Figure 1: ...", "page": 3,
  "render_as": "image|data",        // figures reused as image; tables rebuilt as real data tables
  "caption_bbox": [x0,y0,x1,y1],
  "figure_bbox": [x0,y0,x1,y1] | null,
  "bbox_source": "region|none",
  "confidence": "high|low",          // low / null bbox => FLAGGED: confirm or crop manually
  "factual": true                    // figures/tables are factual: reuse, never redraw
}
```
- `render_as:"data"` (tables) means **do not** present the crop as the asset — extract the
  table's numbers from `full_text` and rebuild a real table later. The crop is only a
  reference snapshot for verifying your extraction.
- `confidence:"low"` or `figure_bbox:null` ⇒ localization was unreliable; surface it at CKPT-1
  for the user to confirm a region or accept it as data-only. Never silently drop it.

## 2. Synthesize the typed digest

Write `out/<stem>/digest.json` (and a readable `digest.md`) with this schema. Every field is
**grounded**: cite the page/section it came from; if you cannot find it, write `null` and add
a `[MISSING: …]` note rather than guessing.

```yaml
thesis_claim: ""                 # <=15 words, the one-sentence contribution
contributions: []                # 1-4 explicit contributions (usually end of intro)
problem: ""                      # the motivating problem
gap: ""                          # the specific limitation of prior work this attacks (often under-stated; extract it)
method:
  one_idea: ""                   # the single new idea, distinguished from supporting machinery
  mechanism: ""                  # how it works
  equations:                     # transcribe LaTeX; keep symbols consistent with the paper
    - {id: "", latex: "", source_ref: ""}
  algorithms: []                 # pseudocode blocks if any
results:
  headline_table: {source_ref: "", note: ""}   # the main comparison vs baselines
  key_metrics: []                # {name, value, unit, source_ref} — exact, from source only
  significance: ""               # error bars / p-values if reported
ablations: []                    # {component, effect, source_ref}
asset_inventory:                 # mirror figures.json, tagging factual vs conceptual
  - {id, kind, label, caption, page, render_as, factual: true|false, source_ref}
limitations: []                  # the authors' own stated limitations / threats to validity
bibliography:                    # references the talk will cite; resolve later (Zotero-first)
  - {key: "", raw: "", doi_or_arxiv: "", resolved: false}
language: "en"
notes_flags: []                  # every [MISSING]/[UNVERIFIED] you raised
```

Discipline:
- **Distinguish the one new idea** from supporting machinery in `method`.
- **Extract the gap explicitly** — the talk lives or dies on it; the paper buries it.
- `key_metrics` and table values are copied verbatim from the source. Do not round, infer,
  or "fill in" a plausible number. If a value is unreadable, mark `[UNVERIFIED]`.
- Tag each asset `factual` (real data → reuse) vs `conceptual` (schematic → may be redrawn,
  labeled). Default factual.

## 3. [CHECKPOINT 1 — human]

Present the digest to the user **before** any outline. This is the cheapest place to catch a
misread; a wrong claim here propagates into every slide. Show and ask to confirm:
- the **thesis claim** and the 1-4 **contributions**,
- the **problem** and especially the **gap**,
- the **headline result** and key metrics (exact values),
- the **figure→slide intent** and every **FLAGGED** asset (low-confidence bbox / data-only
  table / `[MISSING]` / `[UNVERIFIED]`),
- the detected **language** and **deck type** assumption (default 组会 / journal club).

Only proceed to Stage 2 after the user confirms or corrects the digest. Persist the confirmed
digest to disk; later stages read it rather than re-deriving.

## Known Stage-1 limitations (be honest about these at CKPT-1)
- Figure bbox may include a section heading directly above or the first caption line below
  (minor bleed); confirm crops look right.
- Tables that sit flush against body text get no reliable bbox (flagged) — they are handled as
  data extraction anyway.
- Scanned / non-text-layer PDFs and 2-column caption edge cases are not yet handled (OCR is a
  later stage). If `full_text` looks empty or garbled, stop and tell the user.
