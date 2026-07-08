# DESIGN PROPOSAL — `scholar-slides`: an academic slide-deck skill

## 0. Locked Decisions (2026-06-29)

Confirmed by the user; these override the generic recommendations in §H/§I below.

| Axis | Decision | Consequence for the build |
|---|---|---|
| **Render backend** | **reveal.js + KaTeX** (HTML → vector PDF). Editable PPTX (`html2pptx`) deferred to a later phase; Beamer opt-in later. | Equations/tables/citations stay true selectable vector. All ported HTML-native plumbing (guizang validator, frontend-slides stage+PDF, huashu anti-slop) applies directly. |
| **First deck type (MVP)** | **组会 / journal club** — *not* conference. | MVP register is **reading-first / high-density**: dense results tables, full equations, ablations, and failure cases are first-class on-slide content, **not** relegated to an appendix. The universal "one message per slide" rule is *relaxed* for this register. Arc = investigative/didactic: context → the paper's claims & contributions → method (in depth) → results (dense, real tables) → **critical analysis / my concerns / limitations** → takeaway + discussion questions. A **critique/concerns** slide and a **discussion-questions** slide become required archetypes; a hard time→slide budget is soft (30–60 min, interruption-driven) but still estimated. |
| **Citations** | **Zotero-first, Crossref fallback.** | `fetch_bib` binds to the Zotero MCP toolchain available in this environment as system-of-record (best dedup/provenance), falling back to arXiv/DOI/Crossref for anything not in the library. Unresolved → `[UNVERIFIED]` flag, never fabricated. |
| **Default language** | **Bilingual, English-default.** | English display/body fonts and notation conventions are the default register; 中文 + CJK typography fully supported and selectable. |

Everything below is the original proposal; read §H/§I through the lens of the table above (deck-type ordering and backend are now fixed).

---

## A. Executive Summary

**Thesis.** `scholar-slides` is a Claude skill that turns a *source* (paper PDF, arXiv/DOI, a topic, or an existing draft deck) into a **fidelity-first academic slide deck** whose equations, tables, numbers, figures, and citations stay **true text/vector** and **traceable to the source** — never rasterized, never fabricated. Where the six surveyed projects optimize for *aesthetic ceiling* and treat "academic" as a visual flavor, `scholar-slides` inverts the priorities the genre actually demands: **source fidelity > polish, evidence > persuasion, editability > flash.** It keeps the best planning and design machinery the field already built (ppt-master's spec-lock, luwill's extract-vs-generate figure routing, frontend-slides' three-tier disclosure, huashu's showcase-lock + Assertion-Evidence grammar, guizang's executable validator) and adds the five things *none* of them have: a real KaTeX/LaTeX equation pipeline, bounding-box figure extraction with caption/provenance binding, a BibTeX-grounded citation/reference system, data-bound charting, and a talk-time→slide-budget planner with an automated integrity + render QA gate.

- **Deck-type aware, not one-size:** a selector that sets slide-budget-from-time, narrative arc, density register, and which slide archetypes are legal — across conference / defense (答辩) / lab-meeting-journal-club (组会) / job-talk / poster-companion / grant.
- **Markup render backend (reveal.js + KaTeX), not text-to-image:** equations/tables/citations are selectable vector text; clean Playwright PDF for projection; `html2pptx` export for co-author editing. T2I is allowed *only* for conceptual/title art, and labeled.
- **Integrity is a gate, not a guideline:** no fabricated numbers, citations, or figures; real figures reused with bounding-box crops + source attribution; missing assets emit visible `[MISSING]`/`[UNVERIFIED]` flags instead of silent synthesis.
- **Bilingual EN/中文 triggers and output**, including 组会/答辩/会议报告 registers and CJK typography.
- **Three human checkpoints** (digest correct? story right? faithful & complete?) bracket an otherwise automatable pipeline.

---

## B. Positioning vs the Landscape

| Surveyed repo | What we borrow (port + attribute) | What we deliberately do differently |
|---|---|---|
| **ppt-master** (hugohe3) | Dual-artifact spec: human `design_spec.md` + machine `spec_lock.md` **re-read before every slide**; LaTeX→render manifest + provider fallback; PyMuPDF paper ingestion; fabrication guards ("facts stay sourced"); `delivery_purpose` density axis | Equations rendered as **vector KaTeX/MathML, not external-web rasterized PNG**; add citations/bibliography (it has none); add conference-timing→slide-budget; markup backend instead of hand-authored SVG (cheaper, math-native) |
| **frontend-slides** (zarazhangrui) | Three-tier progressive disclosure (JSON index → `preview.md` card → one `design.md`); the `design.md` "design recipe" schema; "show, don't tell" 3-preview style discovery; density-mode contract; fixed 1920×1080 stage + Playwright one-page-per-slide PDF; anti-AI-slop banned lists | Add the entire scholarly layer it lacks: math, citations, figure/table primitives, paper parsing, research narrative scaffold |
| **huashu-design** (alchaincyf) | **2-page "showcase" grammar-lock before batch**; Assertion-Evidence/Tufte as default RESULTS grammar; `html2pptx` computedStyle→OOXML editable-PPTX export; anti-slop-as-reasoning-chains; speaker-notes mechanism | Reject "1 idea/slide" as a *universal* rule — support reading-first dense registers (journal-club/defense methods); ground in a real source paper, not WebSearch product facts |
| **guizang-ppt** (op7418) | **Executable static validator** (`validate-deck.mjs`) blocking unregistered layouts/SVG text/centered titles; registered-layout lock + per-slide `data-layout`; theme-rhythm planning; duration→page mapping; P0–P3 grep checklist | Add academic registered layouts (equation, theorem, results-table, contributions, references); raise the density ceiling for data-dense talks; remove hard-coded author paths; English-first parity |
| **baoyu-slide-deck** (JimLiu) | 4-axis design-token system + curated presets; `STYLE_INSTRUCTIONS` single-source block; **prompt/spec-written-to-disk-before-render** reproducibility; analysis-framework (message hierarchy, Keep/Simplify/Visualize/Omit, narrative-headline rule, AI-cliché blocklist); confirmation gate | **Invert the renderer**: never bake equations/numbers/citations into pixels; real text + vector math + embedded real figures instead of full-bleed T2I |
| **paper-slide-deck** (luwill) | **Extract-vs-generate routing** (`IMAGE_SOURCE: extract\|generate`); `detect-figures.ts` caption parser → `figures.json`; deterministic figure-container compositing; paper-section→slide-type map; 8 academic layouts; per-duration slide counts; 7-beat talk flow; prompt-as-speaker-notes | **bbox figure crop** (not full-page raster); **BibTeX-grounded** citations (not hand-authored); **vector math** (not T2I `equation-focus`); **data-bound charts** (not painted); add **self-review/verification loop** |

---

## C. Skill Name + `description`

**Name:** `scholar-slides`

**SKILL.md `description` (trigger sentence):**

> Generate faithful, presentation-ready **academic slide decks** from a research paper, arXiv/DOI link, a topic, or an existing draft — with real vector equations (LaTeX/KaTeX), extracted source figures and tables with citations, and a BibTeX-grounded reference slide. Use this skill whenever the user wants to turn a paper or research topic into slides for a **conference talk, thesis/PhD defense, job talk, lab meeting, journal club, poster, or grant pitch**; whenever they share a paper **PDF / arXiv / DOI** and ask to "make slides / a talk / a presentation / 讲一下这篇论文"; whenever they mention **组会汇报 / 答辩 / 论文答辩 / 会议报告 / 学术报告 / 开题 / 文献分享 / 把这篇论文做成 PPT / slides for my talk**; whenever they need equation-heavy or results-heavy slides where numbers, citations, and figures must stay accurate and editable. Triggers on EN ("slides for my defense", "conference talk from this paper", "journal club deck") and 中文 ("把这篇论文做成幻灯片", "组会 PPT", "答辩幻灯片", "会议报告 slides"). **Not** for marketing/pitch decks with no scholarly source (use a general slide skill), and **not** for writing the paper itself.

---

## D. Architecture & File Layout

Canonical Anthropic layout with strict progressive disclosure ("read only the file you locked, never glob the directory" — ported from all six). Thin `SKILL.md` router; deep content lazily loaded.

```
scholar-slides/
├── SKILL.md                      # router: trigger, 7-stage pipeline, checkpoints,
│                                 #   References routing table, integrity gate (always-on)
├── references/
│   ├── deck-types.md             # the 6 deck types: time→slide-budget, arc template,
│   │                             #   density register, legal/required archetypes
│   ├── ingestion.md              # PDF/arXiv-source/DOI/topic/draft intake; digest schema
│   ├── narrative.md              # paper-section→slide-role map, arc-tension check,
│   │                             #   one-message discipline, narrative-headline rule (luwill+baoyu)
│   ├── slide-spec.md             # the per-slide spec schema (§E) + speaker-notes spec
│   ├── design-system.md          # typography/color/layout tokens, anti-slop rules (§F)
│   ├── layouts/                  # registered academic layouts (guizang-style lock)
│   │   ├── _index.json           #   compact selection index (tier 1)
│   │   ├── <layout>.preview.md   #   tiny card (tier 2)
│   │   └── <layout>.design.md    #   one full recipe (tier 3, frontend-slides schema)
│   ├── math.md                   # KaTeX/LaTeX policy, numbered eqns, theorem/algo blocks
│   ├── figures-tables.md         # bbox extraction, caption/provenance binding, table fidelity
│   ├── citations.md              # BibTeX/arXiv/DOI grounding, in-text markers, refs slide
│   ├── charts.md                 # data-bound plotting (matplotlib/Vega) from extracted numbers
│   ├── integrity.md              # the guardrails (§G), MISSING/UNVERIFIED flag taxonomy
│   ├── qa-self-review.md         # automated integrity + render + narrative + timing checks
│   └── export.md                 # PDF (Playwright/Decktape), html2pptx, Beamer alt path
├── assets/
│   └── templates/
│       ├── deck-stage/           # fixed 1920×1080 reveal.js stage, viewport-base.css
│       ├── themes/               # restrained academic themes (Conference/Defense/JournalClub/JobTalk)
│       └── figure-container.html # deterministic figure+caption+source container
└── scripts/
    ├── ingest_pdf.py             # PyMuPDF text+layout; arXiv LaTeX-source fetch; DOI→BibTeX
    ├── detect_figures.ts         # caption-regex inventory → figures.json  (port luwill)
    ├── crop_figure.py            # bbox localization + crop (NEW; fixes luwill's page-raster)
    ├── render_math.ts            # LaTeX→KaTeX/MathML vector (NEW; replaces ppt-master PNG)
    ├── make_chart.py             # data-bound matplotlib/Vega from extracted values (NEW)
    ├── fetch_bib.py              # arXiv/DOI/Crossref → verified .bib (NEW)
    ├── render_deck.mjs           # reveal.js → vector PDF (Playwright/Decktape)
    ├── html2pptx.mjs             # editable-PPTX export   (port huashu)
    ├── validate_deck.mjs         # executable static validator (port guizang)
    └── verify_slides.mjs         # screenshot QA: overflow/overlap/font-min/eqn-rendered/contrast
```

### Rendering backend — decision

**Primary: reveal.js + KaTeX, fixed 1920×1080 stage, exported to vector PDF via Playwright/Decktape.** Justification (from the backend comparison in the needs analysis):
- **Math fidelity:** KaTeX/MathJax renders true selectable LaTeX with numbered equations and aligned environments — the single disqualifying gap in *all six* repos. This is non-negotiable for STEM.
- **Figures/tables/citations as real text/vector:** real `<img>`/SVG figures with captions, real `<table>` results, scriptable BibTeX→numbered-refs — none of which survive a T2I or pure-PPTX path.
- **Layout freedom + deterministic density:** the fixed-stage model (frontend-slides/huashu/guizang all converged here) makes overflow checks and one-page-per-slide PDF export trivially clean.
- **Reuses ported plumbing:** guizang's validator, frontend-slides' stage + PDF, huashu's anti-slop are all HTML-native.

**Editable fallback: `html2pptx` → PPTX** (ported from huashu) for co-authors/advisors who mark up in PowerPoint — with the honest caveat (huashu: <30% fidelity on rich HTML) that **equations export as vector/MathML or color-matched vector images**, tables export as real OOXML tables, and the deck warns when fidelity degrades.

**Opt-in alternate backend: Beamer/LaTeX** for theory/stats talks and users who want `.tex` source — reference-grade math, theorems, `biblatex`. Selected at Stage 2 when the source is arXiv LaTeX or the user requests it; shares the same digest + spec, swapping only the renderer.

**Explicitly rejected as primary:** full-bleed AI text-to-image (baoyu/luwill) — disqualifying for factual academic content (pixels not text); pure python-pptx authoring (weak math). T2I is quarantined to conceptual/title art and always labeled.

---

## E. Core Methodology / Pipeline

Outline-first, extraction-grounded, fidelity-preserving, self-reviewing. Three human checkpoints gate the irreversible/judgment steps.

```
INPUT → 1.INGEST/DIGEST → [CKPT-1] → 2.DECK-TYPE → 3.OUTLINE → [CKPT-2]
      → 4.PER-SLIDE SPEC → 5.RENDER → 6.SELF-REVIEW(QA) → [CKPT-3] → 7.EXPORT
```

**Stage 1 — Source ingestion → typed digest.** Accept and normalize all input forms:
- **arXiv link → fetch LaTeX source** (equations + `.bib` come for free — strongly preferred); else PDF.
- **Paper PDF** → `ingest_pdf.py` (PyMuPDF, ported from ppt-master): text layer, layout, `detect_figures.ts` caption inventory → `figures.json` (label/number/page/caption), `crop_figure.py` bbox crop, `fetch_bib.py` → verified `.bib`.
- **DOI** → Crossref/arXiv → BibTeX + PDF.
- **Topic / no paper** → knowledge-outline mode with a hard "no fabricated citations/numbers" gate and explicit "unsourced" labels.
- **Existing draft** (`.pptx`/Markdown/Beamer) → ingest (python-pptx, ported from frontend-slides), restructure, restyle, preserving real content.

Output the **digest**: thesis claim (≤15 words), 1–4 contributions, problem/gap, method + key equations + algorithm blocks, results (headline table, key figures, metrics+units, significance), ablations, **asset inventory** (each Figure/Table flagged *factual* vs *conceptual*), limitations, bibliography.

> **[CKPT-1 — human]** Confirm the *digest*: auto-detected contributions, headline result, figure→slide mapping. Catch a misread claim before it propagates (cheap here, expensive later).

**Stage 2 — Deck-type selection & parameters.** Pick deck type (conference/defense/lab-journal-club/job-talk/poster-companion/grant), venue, time budget, audience level, language, brand assets. This *sets*: (a) time→slide-budget (12min≈10–14 slides @45–60s; defense 40–60min/30–60+appendix; etc.), (b) narrative-arc template, (c) density register (sparse keynote ↔ reading-first dense — ported from ppt-master `delivery_purpose` + frontend-slides density modes), (d) **legal/required archetypes** (defense/grant require Future-Work/Aims-timeline; defense/conference require Backup/Appendix; poster-companion forbids them).

**Stage 3 — Narrative outline.** Re-sequence IMRaD → talk order via the paper-section→slide-role map (ported luwill). Each slide: narrative role, one-sentence **action title** (the conclusion, not a label), the single message, intended evidence (which extracted figure/table/equation), density target, and `IMAGE_SOURCE: extract|redraw|generate|none` with provenance. Run the **arc-tension check**: every results slide must visibly answer the stated gap. Then write the **dual-artifact spec** (ported ppt-master): human `design_spec.md` + machine `spec_lock.md` (re-read before every slide). Style chosen via **3 rendered title previews** ("show don't tell", frontend-slides) + a **2-page showcase grammar-lock** (huashu) before batch.

> **[CKPT-2 — human]** Approve story arc / sequencing / contribution emphasis (editorial judgment the human owns).

**Stage 4 — Per-slide spec.** Self-contained, written to disk (reproducible, auditable — baoyu/luwill), the basis for regenerating one slide. Schema:

```yaml
slide_id: 07
narrative_role: results            # motivation|gap|method|results|ablation|limitations|...
layout: results-table              # MUST be a registered layout (guizang lock)
action_title: "FlashAttn-2 cuts wall-clock 1.8× at equal perplexity"  # assertion, not label
single_message: "Our method matches accuracy while ~halving runtime"
density: balanced                  # sparse|balanced|dense  (from deck-type register)
body:
  - type: table                    # text|table|equation|figure|chart|bullets|callout
    source_ref: "Table 3, p.7"     # provenance (mandatory for factual content)
    data_path: digest/tables/t3.csv
    emphasis: {bold: "best-per-column", units_in_header: true, sig_markers: true}
equations:                         # rendered as KaTeX/MathML vector (never raster)
  - id: eq:attn
    latex: "\\mathrm{Attn}(Q,K,V)=\\mathrm{softmax}\\!\\left(\\tfrac{QK^\\top}{\\sqrt{d_k}}\\right)V"
    numbered: true
figures:
  - kind: extract                  # extract|redraw(flagged)|generate(flagged)
    asset: figures/fig4_crop.png   # bbox-cropped real figure
    caption: "Figure 4: latency vs. seq-length"
    source_cite: "[Dao 2023, arXiv:2307.08691]"
    fit: contain                   # scientific figures NEVER cropped/cover
citations: [dao2023, vaswani2017]  # keys into verified .bib
speaker_notes: |                   # spoken prose, 150–400 words; NOT a re-list of bullets
  "Having shown the gap, here's the headline: equal perplexity, 1.8× faster…
   point at the orange curve; the number to land is 1.8×; expect a question on memory."
integrity:
  unsourced_values: []             # must be empty for factual slides
  flags: []                        # [MISSING: ...] / [UNVERIFIED: ...] surfaced here
```

**Stage 5 — Render (fidelity-first, hybrid).** Equations → `render_math.ts` (KaTeX vector). Tables → real text tables from extracted CSV. Charts → `make_chart.py` data-bound from extracted numbers (never painted). Factual figures → real bbox-cropped image in the deterministic figure-container with title + "Figure N [cite]". Conceptual/title art only → may be generated, labeled. Citations → from verified `.bib`; references slide auto-built and matched. `spec_lock.md` re-read per slide.

**Stage 6 — Self-review QA gate (automated; the academic crux).**
- **Integrity scan** (`integrity.md`): every number/citation/figure traces to the digest; flag any unsourced value, unresolved citation, redrawn-factual-figure.
- **Static validator** (`validate_deck.mjs`, ported guizang): unregistered layouts, SVG visible text, centered titles, missing `data-layout`, equation error boxes.
- **Render verification** (`verify_slides.mjs`, ported frontend-slides/huashu): screenshot each slide @1280×720; no overflow/overlap (note: `scrollHeight` misses overlap), font-min met, equations actually rendered, figures present + uncropped, contrast/color-blind-safe.
- **Narrative check:** results answer the gap; titles are assertions; one-message held.
- **Timing check:** notes word-count ÷ speaking rate vs time budget.
- Auto-fix mechanical issues (sizing, overflow→split); surface judgment ones with severities (P0–P3, ported guizang).

> **[CKPT-3 — human]** Review QA report + rendered deck, especially every `[MISSING]`/`[UNVERIFIED]` and every generated/redrawn asset. The human owns the **truth sign-off** — the machine cannot certify faithfulness.

**Stage 7 — Export.** Primary vector PDF (projection) + editable PPTX (`html2pptx`, co-authors) + speaker-notes (rehearsal). Specs/prompts persist on disk for one-slide regeneration. Beamer `.tex` if that backend was chosen.

---

## F. Design System

Academic design is a **constraint, not a canvas** — reviewers read flashiness as lack of substance. Tokens authored in the frontend-slides `design.md` recipe schema (YAML tokens + named type scale + component grammar + Do/Don't + Known Gaps + CJK section), parameterized loosely on baoyu's 4-axis idea but pinned to a restrained academic register.

**Typography (identity, not decoration — ported ppt-master type-ramp-anchored-on-body):**
- Locked ramp anchored on one body baseline by `delivery_purpose`: **body ≥24pt (28–32 ideal)**, captions/axis labels ≥18pt, never sub-readable ("back-of-room squint test").
- Sans-serif body for projection; one display+body pairing per theme. **Banned defaults** (frontend-slides): Inter/Roboto/Arial as display, and the model's convergence toward Space Grotesk.
- Consistent **notation**: a symbol means the same thing on every slide and matches the paper; abbreviation/notation key for dense talks.

**Color (60-30-10, single accent — universal across all six):**
- One accent; generous whitespace; no gratuitous gradients/3D/WordArt/clip-art.
- **Color-blind-safe only** (Okabe–Ito / Viridis); never encode meaning by color alone — add markers/linestyles; ≥4.5:1 contrast.
- **Consistent method→color mapping** across all results slides (Method A is always the same color).

**Layout templates per slide-type** (registered layouts, guizang lock; `data-layout` per slide; validator-enforced):
- `paper-title` (authors + affiliations + ORCID + advisor + institution/lab logo + venue/date + funding line), `outline-agenda`, `motivation`, `gap`, `contributions`, `related-work-matrix` (a comparison table, not a literature dump), `method-pipeline`, `architecture`, `equation` / `theorem-proof` (NEW), `algorithm` (NEW), `results-table`, `results-chart`, `ablation-grid`, `qualitative-grid`, `limitations`, `future-work` / `aims-timeline`, `conclusion`, `references`, `backup/appendix`.

**Math/figure/table styling:**
- **Results grammar = Assertion-Evidence/Tufte by default** (ported huashu, the single most academically-correct convention found): full-sentence action title + one high-data-ink figure + zero bullets + annotation-on-figure.
- Figures **default to `contain` (never crop a data figure)**; decorative images may `cover`. Multi-panel figures get a panel-at-a-time build.
- Tables: baselines labeled, **best bolded**, units in headers, error bars/significance markers, footnotes — real tables, never a picture of a table.

**Anti-"AI-slop" rules** (consolidated best-of):
- Explicit banned-list (frontend-slides) + anti-slop-as-reasoning (huashu): no #6366f1 indigo, no identical card grids, no emoji-as-icons, no purple-gradient-on-white, no clip-art/chartjunk/rainbow palettes.
- `page_rhythm` / theme-rhythm planning (ppt-master + guizang): forbid every page being the same; pre-assign light/dark/hero; no 3+ consecutive same-theme pages.
- Narrative-headline rule + AI-cliché blocklist (baoyu/luwill): no "dive into / explore / journey"; titles are conclusions.
- "Split to a new slide rather than shrink to fit" (universal density rule).

---

## G. Integrity & Accuracy Guardrails

Enforced by **gates at CKPT-3**, not suggestions (`integrity.md`). These separate a *scholarly* tool from a *marketing* tool.

1. **Never fabricate numbers.** Every statistic/metric/p-value/axis value comes from the source digest. Charts are **data-bound to extracted values** (`make_chart.py`), never an image model's guess. The skill may not "fill in" a plausible accuracy.
2. **Never fabricate citations.** No invented authors/years/venues/DOIs. Citations grounded in the paper's `.bib` or verified via arXiv/DOI/Crossref (`fetch_bib.py`). An LLM-from-memory references slide is a fabrication vector and is **blocked**; unresolved keys emit `[UNVERIFIED: cite]`.
3. **Never fabricate figures.** Reuse the paper's real figures (bbox-cropped, attributed). Redrawing allowed *only* for genuinely conceptual schematics with no factual content — and **labeled "redrawn, not from source."** Generative T2I is quarantined to title/conceptual art, labeled.
4. **Faithful representation.** No overclaiming beyond the paper; preserve hedges/scope/stated limitations. Don't upgrade "suggests" to "proves"; don't drop the dataset/scope bounding a claim.
5. **Flag, don't invent.** Un-extractable figure / ambiguous number / unresolved citation → visible `[MISSING: Figure 3 not found]` / `[UNVERIFIED]` placeholder surfaced to the user — never a silent substitute.
6. **Provenance mandatory.** Every reused figure/table carries its source; every claim traces to a paper span (`source_ref` in the spec). Deck is auditable/defensible under questioning.
7. **Disclose generated assets.** Anything not from the source is labeled, consistent with venue generated-content policies.
8. **Reproducibility.** Specs + prompts + chart data persist on disk; one-slide regeneration without re-running the pipeline (ported baoyu/luwill).

---

## H. Phased Build Plan

**Phase 1 — MVP: faithful single-paper conference deck (HTML).** Ingest PDF + arXiv-LaTeX → digest; deck-type = conference only; outline → reveal.js deck with **vector KaTeX equations**, real extracted figures (bbox crop), real results tables; Playwright vector-PDF export; CKPT-1/2/3 + `STYLE_INSTRUCTIONS`/`spec_lock` consistency.
*Validate:* equations render as selectable vector; figures are clean bbox crops with correct captions; zero fabricated numbers in a 5-paper test set; PDF is one-page-per-slide.

**Phase 2 — Integrity + citations + QA gate.** `fetch_bib.py` BibTeX grounding → in-text markers + auto references slide; `integrity.md` scan; `validate_deck.mjs` + `verify_slides.mjs` automated QA; MISSING/UNVERIFIED flag taxonomy.
*Validate:* every citation resolves or is flagged; QA catches overflow/overlap/unrendered-eqn/contrast; integrity scan flags every injected fabrication in an adversarial test.

**Phase 3 — Deck-type matrix + design system.** All 6 deck types with time→slide-budget, arc templates, density registers, legal archetypes; registered academic layouts + themes (Conference/Defense/JournalClub/JobTalk); Assertion-Evidence results grammar; "show don't tell" previews + 2-page showcase lock; speaker-notes generation + timing check.
*Validate:* defense vs conference vs journal-club produce visibly different decks from the same paper; back-of-room legibility; timing estimate within budget.

**Phase 4 — Editable export + data-bound charts.** `html2pptx` PPTX with vector/MathML equations + real tables; `make_chart.py` data-bound plotting; opt-in Beamer backend for theory talks.
*Validate:* PPTX opens editable in PowerPoint with equations/tables intact (or honest degradation warning); charts match extracted numbers exactly; Beamer `.tex` compiles with `biblatex` refs.

**Phase 5 — Robustness + breadth.** OCR fallback for scanned/2-column PDFs; algorithm/theorem-proof layouts; poster-companion + grant arcs; bilingual EN/中文 + CJK typography polish; draft-deck ingestion/restyle.
*Validate:* scanned-PDF figure detection; CJK rendering; round-trip restyle preserves real content.

---

## I. Open Questions / Decisions for the User

Decisive recommendations given; flag where your preference changes the build.

1. **Primary render backend — recommend reveal.js + KaTeX (HTML→vector PDF), with `html2pptx` editable fallback and opt-in Beamer.** Decision needed: is **editable PPTX a first-class requirement** for your advisors/committee? If yes, we invest early in `html2pptx` fidelity (and accept its limits); if your community lives in LaTeX/Beamer, we may promote Beamer to co-primary. *Recommendation: ship reveal.js primary; treat PPTX as Phase 4.*

2. **Single deck-type vs full matrix at launch.** Recommend **MVP = conference only**, then expand. Decision: is **defense (答辩) or 组会/journal-club** your actual first use case? That reorders Phase 1's arc template (defense needs appendix + cumulative argument; journal-club needs dense reading-first register).

3. **PDF parsing approach.** Recommend **arXiv-LaTeX-source-first** (equations + `.bib` free), PyMuPDF for born-digital PDFs, **OCR deferred to Phase 5.** Decision: how often are your sources **scanned/2-column/non-arXiv**? Heavy scanned use pulls OCR forward.

4. **Degree of automation.** Recommend **3 human checkpoints** (digest / story / truth-signoff). Decision: do you want a **`--fast` repeat-user mode** that collapses CKPT-1/2 to a quick "looks good", or **strict gates always** (safer for unfamiliar papers)?

5. **Citation grounding source.** Recommend **arXiv/DOI/Crossref auto-fetch → verified `.bib`.** Decision: do you use **Zotero** (a `mcp__zotero__*` toolchain is available in this environment) as your library of record? If so we bind to Zotero instead of/alongside Crossref, which improves accuracy and dedup.

6. **Generated/conceptual art policy.** Recommend **T2I allowed only for title/conceptual art, always labeled.** Decision: some venues (Nature/Science/Cell-adjacent) **prohibit generated raster art** — do you want a **`--no-generated-assets` strict mode** that forbids T2I entirely and only ever reuses real figures or code-drawn diagrams?

7. **Output language.** Recommend **bilingual EN/中文 with CJK typography parity.** Decision: is your **default 中文** (组会/答辩) or **English** (international conference)? Sets default theme fonts and the notation/abbreviation conventions.