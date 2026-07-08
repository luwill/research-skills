# External eval — scorecard & blind protocol (M5)

Goal: measure whether scholar-slides is *world-class on design* while *dominating on academic
fidelity* — the crossing generic AI-PPT tools (Gamma, Canva AI, PowerPoint Copilot) can't reach.
Two axes, scored separately because they answer different questions:

- **Aesthetics** (6 dimensions from `references/aesthetics-review.md`, 0–4 each → /24): is it
  beautiful? Here we aim to be *competitive* with the best design tools.
- **Academic fidelity** (below, pass/fail per check): is every number, equation, figure, and
  citation accurate, vector/text, and traceable? Here we should *win outright* — generic tools
  rasterize equations, silently round or invent numbers, and drop citations.

A tool can score 24/24 on aesthetics and still be useless for a journal club if it fabricates a
BLEU score or renders an equation as a fuzzy image. That is the whole thesis of this project.

---

## Academic-fidelity checklist (per deck, pass/fail)

| # | Check | scholar-slides | why generic tools fail it |
|---|-------|:--:|---|
| F1 | Every displayed number appears in the source paper (no fabrication/rounding drift) | ✅ enforced by `groundNumbers` | LLM decks paraphrase and drift digits |
| F2 | Equations are selectable vector/MathML text (not a raster image) | ✅ KaTeX | image-model or screenshot equations |
| F3 | Tables are real editable tables with the true cell values | ✅ OOXML/`<table>` | tables painted as pictures |
| F4 | Figures are the real source crop, cited, never redrawn by an image model | ✅ bbox crop + `[cite]` | figures hallucinated / restyled |
| F5 | Every reused asset carries provenance; a references slide resolves each citation | ✅ Zotero/Crossref | no citations at all |
| F6 | Unresolved items are flagged (`[MISSING]`/`[UNVERIFIED]`), never silently filled | ✅ flag taxonomy | silent plausible fills |
| F7 | Editable PPTX preserves all of the above natively (verified) | ✅ `verify_pptx_parity.py` | export flattens to images |

scholar-slides passes F1–F7 *by construction* (the integrity gate + parity regression). The eval's
job is to confirm the competitors' decks on the same papers and count how many they fail.

---

## Aesthetics self-assessment — the M1→M4 arc (honest, builder-scored)

Scored on rendered pixels against the 6-dimension rubric. **Caveat: this is a self-assessment by the
builder — directional, not a blind rating.** Each score is justified by concrete before/after
evidence (the audit + screenshots across M1–M4). True calibration needs the external raters below.

> **Historical baseline.** The M1→M4 arc below was measured on the original PANDA/pancreatic
> development decks, which have since been retired from the benchmark corpus (now DeepSeek-V3.2 +
> GLM-5; see `manifest.json`). The full audit is archived at
> `docs/scholar-slides-design/04-panda-aesthetic-audit.md`. The scores are kept as the record of the
> design program's before/after gains; re-score the *current* corpus decks with the loop in
> `references/aesthetics-review.md` when a fresh rating is needed.

**PANDA journal-club deck (historical — original `pancreatic` dev deck):**

| dimension | M1 baseline | after M4 | what moved it |
|-----------|:-----------:|:--------:|---------------|
| Hierarchy & focus | 3 | 3.5 | action titles + section rhythm |
| Typography | 2.5 | 3.5 | modular scale, balanced titles, controlled measure |
| Space & grid | 2 | **4** | annotation↔figure collision fixed; 8pt grid; matting |
| Figures & data-ink | **1.5** | **3.5** | page-furniture stripped; panel extraction; redrawn chart; unified matting |
| Color & contrast | 2.5 | 3.5 | token discipline, Okabe-Ito, one accent |
| Consistency & finish | 3 | 4 | one system via tokens/base-theme; PPTX parity verified |
| **total** | **~15 / 24** | **~22 / 24** | |

**PANDA conference cut (historical):** ~23/24 — same gains plus 0% bullets, section-divider
rhythm, and full-bleed cover/dividers give hierarchy 4 and space 4. The current-corpus analogue is
`out/deepseek_conf` (conference theme, 0% bullets).

The biggest single lever was **Figures** (1.5 → 3.5): the M2 furniture-strip + panel extraction turned
"screenshots of a PDF" into figures. Space (2 → 4) came from the M1 collision fix + matting.

---

## Blind competitor protocol (turnkey — run when samples are available)

I cannot generate Gamma / Canva AI / Copilot decks here (no accounts). When you export them, this
protocol makes the comparison rigorous:

1. **Same inputs.** Feed each tool the *same* 3–5 benchmark papers (start with the DeepSeek-V3.2 and
   Transformer papers — both in `benchmarks/manifest.json`).
2. **Anonymize.** Render every deck (ours + each competitor) to PDF → PNG per slide; strip tool
   branding/footers; assign random deck IDs. Raters must not know which tool made which.
3. **Raters.** ≥3 independent raters, ideally domain readers (someone who runs journal clubs). Each
   scores every deck on the 6 aesthetic dimensions (0–4) and runs the F1–F7 fidelity checklist.
4. **Aggregate.** Mean aesthetic score ± spread per tool; fidelity = count of F-checks passed /7.
   Report both. Expectation to test: competitors may match or beat us on raw aesthetics but fail
   several fidelity checks; we should be close on aesthetics and 7/7 on fidelity.
5. **Ship-quality bar.** The headline metric for "world-class": ≥ X% of raters would use our deck
   *as-is* for a real journal club with no manual edits.

Record results in `benchmarks/eval/results-<date>.md` using the table shapes above.

## What this tells us to build next
- If competitors beat us on a specific aesthetic dimension, that dimension becomes the next
  design pass (feed it back into `aesthetics-review.md`).
- Fidelity failures competitors have that we don't = the marketing/positioning story.
