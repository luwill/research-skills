# What a Purpose-Built Academic Slide-Generation Skill Must Do

A skill for academic slides is not "a pretty-deck generator that happens to accept a PDF." Academia inverts the priorities of a normal presentation tool: **fidelity to a source dominates aesthetics, evidence dominates persuasion, and editability dominates polish.** The reasoning below is derived from the requirements of the genre itself, then mapped onto the existing `paper-slide-deck` repo at the end.

---

## 1. Distinct Academic Deck TYPES and Their Differing Requirements

The single biggest first-principles error a generic tool makes is treating "academic" as one format. It is at least six, each with a different audience model, time budget, narrative arc, and information density. A real skill must ask which one it is building **before** outlining, because the same paper becomes a different deck in each.

| Type | Audience | Length / slide budget | Narrative arc | Density |
|---|---|---|---|---|
| **Conference talk (12–20 min)** | Domain peers who skim the proceedings; mixed sub-specialties; jet-lagged, post-lunch | 12 min ≈ 10–14 content slides; 20 min ≈ 16–22; budget ~45–60s/slide, never <30s | **Teaser, not survey**: one problem → one idea → strongest result → "read the paper." Motivation front-loaded in 90s | Sparse, speaker-led. One claim/slide, big figures, minimal text. Backup slides for Q&A |
| **Thesis / dissertation defense** | A committee that has (nominally) read the thesis; advisor + 3–5 examiners; adversarial-but-fair | 40–60 min talk, 30–60 slides + deep appendix; defends *years* of work | **Cumulative argument**: roadmap → background/positioning → contribution 1…N (each its own mini problem→method→result) → synthesis → limitations → future work → contributions recap | Mixed. Method/results slides denser than a conference talk; examiners will stop you and drill. Must survive interrogation, so every number traceable |
| **Lab meeting / journal club** | A handful of labmates/advisor; high trust, high scrutiny of *details* and *methods*; interruption-driven | 30–60 min, often no hard slide count; whiteboard-adjacent | **Investigative / didactic**: for journal club, "here's a paper, here's whether I believe it" (claims → method critique → results → my concerns); for lab update, "what I tried → what broke → what's next" | High. This is the *one* venue where dense tables, raw plots, failure cases, and equations in full are welcome and expected. Reading-first is fine |
| **Job talk** | A whole department across sub-fields; tenured faculty + grad students; deciding if you can teach AND research | 45–60 min, 35–50 slides; must land with non-experts and experts simultaneously | **Career arc, not one paper**: a research vision threaded through 2–3 representative works; "here's my agenda, here's why it matters, here's proof I can execute, here's where I'm going" | Medium, accessibility-forward. First 10 min must be legible to the whole room; depth back-loaded. Polish and clarity matter more than anywhere else |
| **Poster-companion** | Hallway traffic at a poster; 2–5 min drive-by or a 1-slide "lightning"/teaser | 1 teaser slide, or a 3–5 slide spotlight; sometimes a looping deck beside the poster | **Hook-only**: title + the single figure that makes someone stop walking | Extremely sparse OR extremely dense (the poster itself). The *companion* slide is sparse; it points at the poster |
| **Grant pitch** | Program officers, study-section reviewers, sometimes non-specialist panels; deciding funding | 5–15 min; 8–20 slides | **Significance → innovation → approach → feasibility/track-record → broader impact**: problem importance and *your* ability to deliver, NOT a results dump (you may have none yet) | Medium. Aims-driven, milestone/timeline heavy, preliminary-data slides. Persuasion is legitimate here in a way it is not in a results talk |

**Design consequence:** the skill needs a *deck-type selector* that sets (a) the slide-count-from-time mapping, (b) the narrative-arc template, (c) the density register, and (d) which slide archetypes are even allowed (e.g., a "Future Work / Aims timeline" is mandatory for grant/defense, absent from a conference teaser; a "Backup/Appendix" section is mandatory for defense/conference Q&A, pointless for poster-companion).

---

## 2. Content Engineering from a SOURCE PAPER

The hard part is not rendering; it is **lossy, faithful compression** of a 10–30 page artifact into 12–50 assertions. This is an information-extraction-and-restructuring problem.

### 2.1 Extraction targets (a structured "paper digest")
The skill must parse the source into a typed intermediate representation before any slide exists:
- **Contribution/claims** — the 1–4 explicit contribution bullets (usually end of intro) plus the *thesis claim* (≤15 words). These become the contributions slide and the spine of the talk.
- **Problem & gap** — the motivating problem and the specific limitation of prior work the paper attacks. This is the most under-extracted and most important element; a paper's intro buries it but the talk lives or dies on it.
- **Method** — the core mechanism, the architecture/algorithm, the key equations, the algorithm block. Distinguish *the one new idea* from supporting machinery.
- **Results** — the headline table (main comparison vs. baselines), the key figures/plots, the metric definitions and units, statistical significance markers.
- **Ablations** — what each component contributes; these answer "why does it work" and are gold for Q&A/defense backup.
- **Assets inventory** — every Figure N and Table N with caption, page location, and a flag for whether it's a *factual asset* (real data, must be reproduced verbatim) vs. a *conceptual schematic* (can be redrawn/restyled).
- **Limitations & threats to validity** — explicit ones the authors state; required for honesty slides in defenses/job talks.

### 2.2 Dense paper → story
The canonical research arc is **problem → gap → idea → method → results → takeaway**, and the skill must *re-sequence the paper into it* (papers are written in IMRaD, not in talk order). Concretely:
- A **paper-section → slide-role mapping**: Abstract/Intro → Motivation + Gap + Contributions; Related Work → "Positioning" (often a single comparison matrix, not a literature dump); Method → idea slide + method-detail slides + equation/algorithm slides; Experiments → setup + main-results + qualitative + ablation; Conclusion → takeaway + limitations + future work.
- An **arc-tension check**: the gap slide must set up a question the results slide answers. If a generated outline has results that don't visibly close the stated gap, it's broken.
- **Audience-conditioned compression**: a conference talk drops most related work and most ablations into backup; a journal club *centers* them.

### 2.3 "One message per slide" discipline
Each slide carries exactly one assertion, expressed as a **full-sentence action title** ("Method X cuts error 23% on out-of-distribution inputs"), not a topic label ("Results"). The body is the *evidence* for that title — ideally one figure/table, not bullets. The discipline:
- If you can't name the slide's single message, merge or cut it.
- Title says the conclusion; the figure *shows* it; the caption/annotation *proves* it (Assertion–Evidence / Tufte / Alley model — the correct default for a results slide).
- Hard caps: ~3–4 text elements/slide for talks; the figure is the protagonist.

### 2.4 Presenter notes / speaker script
Academic talks are *spoken*; the on-slide text is deliberately thin, so the **script lives in presenter notes** (150–400 words/slide): the transition from the previous slide, what to point at, the number to emphasize, and the anticipated question. This doubles as a defense-rehearsal artifact and a basis for timing estimates (words ÷ speaking rate → minutes, validated against the time budget). The skill must generate notes as *spoken prose*, not a re-listing of the bullets.

---

## 3. Academic-Specific Rendering Needs

This is where generic deck tools fail catastrophically, and where backend choice is decisive.

### 3.1 The non-negotiable academic primitives
- **Equations** — display + inline LaTeX, multi-line aligned environments, numbered equations, consistent symbol set across slides. Must be **vector/text, selectable, and editable** — never a glyph-garbled raster. A text-to-image model rendering `\hat{\beta}_{i}^{(t)}` is an automatic disqualifier.
- **Algorithm blocks** — `algorithm2e`/`algorithmic`-style numbered pseudocode with line numbers and indentation preserved.
- **Figures with captions & source attribution** — every reused figure needs "Figure N, [Author et al., Year]" provenance; cropping must never alter data; scientific figures default to *contain* (no cropping), unlike decorative images that get *cover*-cropped.
- **Tables** — real results tables: baselines labeled, best result bolded, units in headers, error bars / significance markers, footnotes. Not a redrawn picture of a table.
- **Citations / references** — in-text markers `[Author et al., Year]` or numeric superscripts, backed by a real bibliography, with a references slide that matches. Ideally BibTeX/DOI/arXiv-grounded so citations cannot be fabricated.
- **Theorem / proof layouts** — `theorem`/`lemma`/`proof` environments with QED, definition boxes, consistent numbering.
- **Code listings** — syntax-highlighted, monospaced, line-numbered, with overflow handled (not silently truncated).
- **Reproducibility** — a slot for code/data/model links, hyperparameters, compute, license; increasingly an expected slide.

### 3.2 Backend comparison (math / figure / citation fidelity and editability)

| Backend | Math fidelity | Figure handling | Citations/refs | Editability | Verdict for academic use |
|---|---|---|---|---|---|
| **reveal.js + MathJax/KaTeX** | Excellent (true LaTeX, selectable, numbered) | Strong: real `<img>`/SVG, captions, full CSS layout control; can embed vector plots | DIY but tractable; can script BibTeX→HTML refs + numbered markers | Source is HTML/Markdown — diff-able, version-controllable; not WYSIWYG-editable by a co-author in PowerPoint | **Top pick for math-heavy, web-delivered talks.** Best balance of fidelity + layout freedom; clean PDF via print/Decktape |
| **Marp** | Good (Markdown + MathJax/KaTeX) | Good for one-figure-per-slide; limited fine layout control | Manual; no native bib | Markdown — extremely clean to edit/version; great for batch generation | **Best for fast, clean, math-capable decks**; weaker when you need precise multi-panel composition |
| **Slidev** | Excellent (KaTeX/MathJax, code-first) | Strong; Vue components, embeds, diagrams (Mermaid), code with live highlighting | Manual/plugin | Markdown+Vue — superb for technical/CS talks, great code listings; heavier toolchain | **Best for CS/ML talks heavy on code + diagrams**; overkill for a humanities defense |
| **Beamer / LaTeX** | Reference-grade (it *is* LaTeX: equations, theorems, algorithms, `biblatex` citations all native and perfect) | Native `\includegraphics`, `figure`, `subfigure`, captions; TikZ for vector diagrams | Best-in-class: `biblatex`/`natbib`, real `.bib`, automatic numbered refs slide | Source is `.tex` — perfectly version-controlled; *not* editable by non-LaTeX co-authors; slow to restyle | **Highest fidelity, the academic default for math/theory/stats.** Cost: rigid layouts, painful aesthetics, steep edit barrier for collaborators |
| **PPTX (python-pptx / native)** | Weak: equations become OMML (limited) or, worse, rasterized images; rarely round-trips LaTeX | Native pictures + crop; real tables and editable charts | None native; manual | **Maximally editable by advisors/co-authors in PowerPoint/Keynote** — the format most committees actually want to mark up | **Best for editability/collaboration, worst for math.** Viable only with a LaTeX→vector-or-clean-image equation escape hatch and real (not redrawn) tables |
| **AI text-to-image (full-bleed raster)** | **Disqualifying**: equations, numbers, axis labels, citations garbled/hallucinated; pixels not text | Redraws figures = fabrication risk; only safe if compositing the *real* extracted figure | None; fabricates author names | **None** — a typo requires regenerating the whole slide; no alt text, fails accessibility | **Unsafe as the sole renderer for factual academic content.** Acceptable only for conceptual/title art, never for equations/tables/data |

**Principle:** the renderer must keep equations, tables, numbers, and citations as **true text/vector**. The defensible architecture is a markup backend (reveal.js+MathJax, Marp, Slidev, or Beamer) for fidelity, optionally with a PPTX export path for editability — with a hard rule that factual content is never rasterized by a generative image model. A hybrid that *extracts and composites the paper's real figures/tables* is acceptable; one that *redraws* them is not.

---

## 4. Academic Design Conventions

Academic design is a *constraint*, not a canvas. Reviewers and committees read flashiness as a lack of substance.

- **Clean and legible over flashy.** Restraint is the aesthetic: one accent color, generous whitespace, no gratuitous gradients/3D/WordArt/clip-art/animation. Chartjunk and rainbow palettes are negative signals. The "wow" comes from a clear result, not a transition.
- **Institutional / conference branding.** Title slide carries author list with affiliations and ORCID-style identifiers, advisor (for defense), institution + lab logo, venue/date, funding/acknowledgement line. Optional conference template conformance (some venues mandate aspect ratio or a footer). The skill should support a light, swappable brand layer (logo, color, footer) without letting it dominate.
- **Accessibility (a hard requirement, not a nicety).**
  - **Color-blind-safe palettes** (e.g., Okabe–Ito, Viridis/Cividis); never encode meaning by color alone — add markers/linestyles/labels.
  - **Projection-legible type**: body ≥ 24pt (28–32 ideal), axis labels and captions ≥ 18pt, nothing sub-readable; high contrast (≥ 4.5:1).
  - **Sans-serif for projection** body; consistent, limited type ramp.
  - **Alt text / real selectable text** for screen readers and for venues with accessibility mandates (government, NIH, many universities).
  - Test by the "back-of-room / squint" standard: if the key number isn't readable from the back, it's too small.
- **Figure-forward layouts.** The figure is the slide; text annotates it. Multi-panel figures get a panel-at-a-time build. Plots get axis labels, units, legends, and a one-line takeaway annotation directly on the figure. Never crop a data figure.
- **Consistent notation.** A symbol means the same thing on every slide and matches the paper; a notation/abbreviation key for dense talks; consistent baseline naming, metric naming, and color-to-method mapping across all results slides (Method A is always the same color).

---

## 5. Integrity Constraints Unique to Academia

These are the constraints that separate a *scholarly* tool from a *marketing* tool. They are non-negotiable and should be enforced by gates, not suggestions.

- **Never fabricate numbers.** Every statistic, metric, p-value, and axis value must come from the source. The skill may not "fill in" a plausible accuracy. Generated charts must be **data-bound to extracted values**, never an image model's guess at what a bar chart "should look like."
- **Never fabricate citations.** No invented author lists, years, venues, or DOIs. Citations should be grounded in the paper's own bibliography or a verifiable source (BibTeX/DOI/arXiv lookup). A references slide built by an LLM from memory is a fabrication vector and must be flagged.
- **Never fabricate figures.** Reuse the paper's *real* figures (extracted and attributed); do not have a generative model redraw a results plot, an architecture diagram with real labels, or a qualitative example. Redrawing is acceptable *only* for genuinely conceptual schematics with no factual content, and even then it must be flagged as "redrawn, not from source."
- **Faithfully represent the source.** No overclaiming beyond what the paper states; preserve hedges, scope conditions, and the authors' own stated limitations. Don't upgrade "suggests" to "proves." Don't drop the dataset/scope that bounds a claim.
- **Flag missing assets, don't invent them.** If a figure can't be extracted, a number is ambiguous, or a citation is unresolved, the skill must emit a visible `[MISSING: Figure 3 not found]` / `[UNVERIFIED]` placeholder and surface it to the user — never silently synthesize a substitute.
- **Provenance is mandatory.** Every reused figure/table carries its source; every claim is traceable back to a paper span. This makes the deck auditable and defensible under questioning.
- **Disclose generated assets.** Anything not from the source (conceptual art, redrawn schematic, AI-generated illustration) is labeled as such, consistent with venue policies on generated content.

---

## 6. Proposed End-to-End Pipeline (with Human Checkpoints)

The pipeline is **outline-first, extraction-grounded, fidelity-preserving, and self-reviewing**, with humans gating the irreversible/judgment steps.

```
INPUT  ─►  INGEST/DIGEST  ─►  [CKPT-1]  ─►  OUTLINE  ─►  [CKPT-2]  ─►  PER-SLIDE SPEC  ─►  RENDER  ─►  SELF-REVIEW  ─►  [CKPT-3]  ─►  EXPORT
```

**0. Input forms (accept all, normalize to one digest):**
- Paper **PDF** (primary): parse text layer + detect figures/tables by caption regex + extract bib.
- **arXiv / DOI link**: fetch source (LaTeX source from arXiv is ideal — equations and `.bib` come for free), else PDF.
- **Topic / no paper**: pure outline-from-knowledge mode — but with a hard "no fabricated citations/numbers" gate and explicit "unsourced" labeling.
- **Existing draft** (advisor's old `.pptx`/Markdown/Beamer): ingest, restructure, restyle, preserving real content.

**1. Ingest & digest** → the typed paper digest from §2.1 (contributions, problem/gap, method, equations, results, ablations, asset inventory with factual-vs-conceptual flags, bibliography). Run figure detection + a **bounding-box crop** (not full-page rasterization) so extracted figures are clean.

**2. Deck-type & parameters** (from §1): ask deck type, venue, time budget → slide count, audience level, language, brand assets. Map time → slide budget and pick the arc template.

> **[CHECKPOINT 1 — human]** Confirm deck type, audience, time/slide budget, and review the *extracted digest* (especially the auto-detected contributions, the headline result, and the figure→slide mapping). This is where a human catches a misread claim *before* it propagates. Cheap to fix here, expensive later.

**3. Outline** → ordered slide list, each with: narrative role (motivation/gap/method/results/...), one-sentence action title, the single message, the intended evidence (which extracted figure/table or equation), density target, and an `IMAGE_SOURCE: extract|redraw|generate|none` decision with provenance.

> **[CHECKPOINT 2 — human]** Approve the outline / story arc. Re-sequencing and cutting are *editorial* decisions a human should own; the gap→result tension and the contribution emphasis are judgment calls. (For repeat users this can be a fast "looks good.")

**4. Per-slide spec** → a self-contained spec per slide: title, body content in its final texture, exact equation LaTeX, exact table data, figure path + caption + source, citations used, layout archetype, and **speaker notes**. Specs are written to disk as the reproducible, auditable contract (and the basis for regenerating one slide without re-running everything).

**5. Render** (fidelity-first, hybrid):
- Equations → LaTeX/MathJax (vector/text).
- Tables → real text tables from extracted data.
- Charts → data-bound plotting from extracted numbers (matplotlib/Vega), never image-model guesses.
- Factual figures → composite the **real extracted figure** into an academic container with title + "Figure N [cite]".
- Conceptual/title art only → may be generated, and labeled.
- Citations → from the real `.bib`; references slide auto-built and matched.

**6. Self-review (automated)** — a genuine verification loop, not just a pre-flight checklist:
- **Integrity scan**: every number/citation/figure traces to the digest; flag any unsourced value, unresolved citation, or redrawn-factual-figure.
- **Render verification**: screenshot each slide; check no overflow/overlap, font-size minimums met, equations actually rendered (not error boxes), figures present and uncropped, contrast/color-blind-safety.
- **Narrative check**: does each results slide answer the stated gap? Are titles assertions, not labels? Is one-message-per-slide held?
- **Timing check**: notes word-count vs. time budget.
- Emit a report with severities; auto-fix what's mechanical (sizing, overflow → split), surface what's judgment.

> **[CHECKPOINT 3 — human]** Review the self-review report and the rendered deck, especially every `[MISSING]`/`[UNVERIFIED]` flag and every generated/redrawn asset. The human owns the *truth* sign-off — the machine cannot certify faithfulness to the source.

**7. Export** → primary fidelity format (reveal.js/Beamer/Slidev → PDF for projection) **plus** an editable path (PPTX with vector/text equations and real tables) for co-authors, plus speaker notes for rehearsal. Keep specs + prompts on disk for one-slide regeneration.

**Where humans belong (summary):** at **CKPT-1** (was the paper read correctly?), **CKPT-2** (is the story right?), and **CKPT-3** (is it faithful and missing nothing?). Everything between is automatable; these three are irreducibly judgment, and the integrity gate at CKPT-3 is the one that protects the user's scholarly reputation.

---

## Alignment Note: where `paper-slide-deck` (luwill/research-skills) already fits

`paper-slide-deck` is the closest of the surveyed repos to this spec, and is explicitly aimed at the right targets (conference / defense / lab-meeting). It **already aligns** on several load-bearing requirements:

**Strong alignment:**
- **Source ingestion + figure inventory (§2.1, §6.0/1):** `detect-figures.ts` parses the PDF text layer and regex-matches `Fig./Figure/FIGURE/Table` (incl. Roman-numeral tables) into a `figures.json` `{label, number, page, caption}` inventory — exactly the asset-inventory step.
- **Anti-hallucination figure path (§3.1, §5):** the hybrid `extract` route (`detect-figures → extract-figure → apply-template`) composites the **real PDF figure** into a deterministic node-canvas academic container with a "Figure N:" caption, instead of letting an image model invent it. This is the correct instinct for figure/table fidelity and directly honors "reuse real figures, never fabricate."
- **Extract-vs-generate routing with confidence (§5, §6.3):** the `// IMAGE_SOURCE {Source: extract|generate}` decision, auto-mapped by caption keywords (architecture/pipeline→Methods/extract; comparison/Table→Results/extract; conceptual→generate) with high/medium/low confidence, is precisely the factual-vs-conceptual asset distinction this spec requires.
- **Story engineering & one-message discipline (§2.2–2.3):** `analysis-framework.md` provides a ≤15-word core message, a paper-section→slide-type mapping table, narrative-flow patterns (Problem→Solution, Claim→Evidence→Implication), Keep/Simplify/Visualize/Omit triage, narrative (action) headlines, and an AI-cliché blocklist — the content-compression backbone of §2.
- **Deck-type & pacing awareness (§1):** per-talk-duration slide-count guidance and a 7-beat academic talk flow (Hook→Background→Approach→Results→Analysis→Conclusion→References); audience-adaptation matrix for defense vs. journal-club vs. lab-meeting.
- **Academic layout archetypes & design tokens (§3.1, §4):** 8 academic layouts (paper-title, methods-diagram, results-chart, equation-focus, qualitative-grid, references-list, contributions, outline-agenda); `academic-paper.md`/`scientific.md` tokens target ICML/NeurIPS/CVPR aesthetics with a capped chart palette; a results checklist (baselines labeled, best bolded, error bars, units) encoding §4 conventions.
- **Reproducibility & auditability (§6.4):** every slide's full prompt/spec is written to disk before rendering, embedded into PPTX speaker notes, with idempotent/resumable generation — matching the spec-on-disk contract.

**Where it falls short of this spec (the gaps a purpose-built skill must close):**
- **Rendering backend is the core mismatch (§3):** slides are **full-bleed AI-generated raster PNGs** (Gemini 3 Pro Image). That violates the §3 fidelity rule — equations, exact numbers, axis labels, and citations become un-editable, un-selectable pixels prone to garbling. The `equation-focus` layout is only an *instruction to an image model*, with **no LaTeX/MathJax path** — disqualifying for math-heavy papers. A purpose-built skill must swap in a markup backend (reveal.js+MathJax / Beamer / Slidev) or a vector-equation PPTX path.
- **Figure extraction is page-level, not bbox (§3.1, §6.1):** `extract-figure.ts` rasterizes the **entire PDF page**, not a cropped figure bounding box, so extracted slides may carry surrounding text/columns. Needs true figure localization.
- **No citation/reference integrity (§5):** the references slide is hand-authored from slide content — **no BibTeX/DOI/arXiv grounding** — so citations can be fabricated. This is the §5 constraint most in need of a real bibliography manager.
- **No true tables/charts (§3.1):** data tables and plots are image-model-drawn rather than text tables / data-bound charts — unsafe for results fidelity.
- **No self-review/verification loop (§6.6):** QA is a static pre-outline checklist; there is no render-screenshot verification, no integrity scan, no missing-asset flagging gate.
- **Accessibility (§4):** image-only slides have no selectable text/alt text — fails projection-editability and screen-reader requirements.

**Net:** `paper-slide-deck` already implements the *planning, extraction, narrative, and figure-provenance* half of this spec well, and is structurally the right scaffold (thin `SKILL.md` router + `references/` + `scripts/`). To become purpose-built it needs the *rendering and integrity* half rebuilt: a vector/text math + table + chart backend, bounding-box figure crops, a BibTeX-grounded citation/reference system, and an automated self-review + missing-asset gate at Checkpoint 3.