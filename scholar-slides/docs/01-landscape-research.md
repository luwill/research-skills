# Cross-Repo Synthesis: 6 Open-Source AI Slide/PPT Projects

All six are Claude skills built on the canonical Anthropic layout (SKILL.md + YAML frontmatter + progressive-disclosure `references/`). They split cleanly into three rendering camps: **LLM-hand-authored vector/markup** (ppt-master writes SVG; frontend-slides, guizang, huashu write HTML), **native-PPTX transpilation** (ppt-master's `svg_to_pptx`, huashu's `html2pptx`), and **delegated text-to-image rasterization** (baoyu and luwill let an external T2I model paint each slide). That render-backend choice is the single axis that predicts almost every strength and gap below.

---

## 1. Comparison Matrix

| repo | output / render backend | skill? | core methodology (one phrase) | design-system strength | best single idea to steal | biggest gap |
|---|---|---|---|---|---|---|
| **ppt-master** (hugohe3) | LLM hand-writes 1 SVG/slide → deterministic SVG→OOXML transpile → **native editable PPTX** | Yes (+ CC plugin v2.7.0) | Strict serial Strategist→Executor pipeline governed by a dual-artifact spec re-read before every slide | **Highest.** `spec_lock` + `page_rhythm` + visual-style spectrum + body-anchored type ramp; 71 chart templates, 18 styles, 11,600 icons | Dual-artifact spec (`design_spec.md` + machine `spec_lock.md`) re-read **before every slide** to defeat context-drift on long decks | No citation/bibliography system; equations are **rasterized PNGs via external web LaTeX services** (not OMML, network-dependent) |
| **frontend-slides** (zarazhangrui) | Hand-authored single-file **HTML+inline CSS/JS**, fixed 1920×1080 stage | Yes (+ CC plugin v2.1.0) | Interactive Phases 0–6 with "show, don't tell" style discovery + density-mode contract | Anti-AI-slop banned lists + 34-template **three-tier progressive disclosure** + `design.md` recipe schema | "Show, don't tell": generate 3 real title slides (safe + bold + wildcard) and open them, instead of asking taste questions | **Zero** math/LaTeX, zero citations, zero paper parsing |
| **huashu-design** (alchaincyf) | HTML-first multi-file iframe deck engine; **dual export**: vector PDF (Playwright) + editable PPTX (`html2pptx`) | Yes (agent-agnostic) | Checkpoint-gated, **divergent-then-converge**: 3 anti-convergence subagents + 2-page grammar lock | Anti-slop framed as **reasoning chains**; 40-style library with honest HTML-fidelity %, incl. Assertion-Evidence/Tufte | 2-page "showcase" to lock visual grammar **before** mass-producing N slides (turns N× rework into 2×) | No math/citations/paper parsing; slides are 1 of 5 use cases (not paper-grounded) |
| **guizang-ppt** (op7418) | Single-file **HTML+WebGL+vanilla-JS** web deck, two locked aesthetics (e-magazine / Swiss) | Yes | **Constraint-first**, template-locked: 22 registered layouts + executable validator + P0–P3 checklist | Constraint-as-quality; Carbon design tokens; named anchors (Monocle; Vignelli/Müller-Brockmann); theme-rhythm planning | **Executable static validator** (`validate-swiss-deck.mjs`) that programmatically blocks unregistered layouts / SVG text / centered titles | No math, no citations, no real charts/tables; hard-coded author machine path |
| **baoyu-slide-deck** (JimLiu) | **AI text-to-image** raster PNG per slide → merge to PPTX/PDF (image containers) | Yes (multi-runtime) | 9-step pipeline, hard confirmation gate, `STYLE_INSTRUCTIONS` single source of truth | **4-axis design-token system** (texture×mood×typography×density ≈ 525 combos) + 17 presets | 4-axis token system + prompt-written-to-disk-before-render reproducibility (backend-swappable) | **Fatal for academia:** all text baked into pixels — equations/numbers/citations garbled, nothing editable |
| **paper-slide-deck** (luwill) | **AI text-to-image** (Gemini 3 Pro Image) + **hybrid figure extraction** via deterministic node-canvas compositing → PPTX/PDF | Yes | 8-step outline-first **hybrid extract-or-generate** routing per slide | 17 style specs incl. `academic-paper` (ICML/NeurIPS/CVPR); paper-section→slide map; 8 academic layouts | **Extract-vs-generate routing**: composite *real* PDF figures/tables deterministically; only generate *conceptual* visuals | Extraction rasterizes the **whole PDF page** (no bbox crop); equations still go through T2I (garbled); no citation integrity |

---

## 2. Convergent Patterns (what almost all do the same way)

1. **Canonical skill architecture + progressive disclosure — all six.** Thin SKILL.md as a router, deep content lazily loaded from `references/`, with explicit "read only the file you locked, never glob" discipline. ppt-master ("Cross-Cutting Authorities table"), frontend-slides ("give the agent a map first"), huashu ("References路由表"), guizang (explicit load-order list), baoyu ("load that file only when this branch is selected"), luwill (References table). This is the most uniform convergence in the set.

2. **Outline-first / spec-first planning before any rendering — all six.** Every pipeline is `input → outline → per-slide content → render`. ppt-master writes `design_spec.md §IX Content Outline`; frontend-slides Phases 1–3; huashu's ≥500-word design spec; guizang's 5-beat narrative arc + 3 alignment tables; baoyu's `outline.md`; luwill's 3 outline variants. None do one-shot generation.

3. **A single-source-of-truth design contract injected/re-read into every slide.** ppt-master's `spec_lock.md` (re-read before each page), baoyu and luwill's `<STYLE_INSTRUCTIONS>` block (injected into every prompt instead of re-reading style files), frontend-slides' one chosen `design.md`, guizang's template `<style>` block declared "the SINGLE source of truth for class names." Same insight everywhere: long decks drift unless one locked contract is re-asserted per slide.

4. **Explicit anti-"AI-slop" design doctrine — five of six, and arguably all six.** frontend-slides ships a literal "DO NOT USE" list (#6366f1 indigo, banned Inter/Roboto, plus a meta-warning that "the model converges on Space Grotesk"). huashu frames anti-slop as reasoning chains ("AI default output = the visual mean of the corpus = no brand recognizable"). guizang bans emoji/box-shadow/gradient/border-radius and user-supplied hex. baoyu/luwill enforce an "AI-cliché blocklist" (no "dive into/explore/journey") and narrative-not-label headlines. ppt-master attacks it structurally via `page_rhythm` ("forbid every page being a card grid") and a safe/shifted/bold visual-style spectrum.

5. **Design-token systems with locked type ramp + disciplined color.** All six commit to single-accent or 60-30-10 color (never evenly distributed) and a locked typographic scale. ppt-master anchors the whole ramp on one `body` baseline; guizang imports Carbon 8px tokens + a "bigger=thinner" weight ladder; huashu uses oklch palettes; baoyu/luwill express palettes as role|hex|usage tables. Typography is treated as *identity*, not decoration, in every repo.

6. **Density as an explicit, named control knob tied to audience/purpose/duration.** ppt-master's `delivery_purpose` (text/balanced/presentation) + `page_rhythm`; frontend-slides' low/high "Content Density Modes" table; huashu's "1 core message + 3–4 points per page"; guizang's duration→page-count mapping; baoyu/luwill's density dimension auto-selected from audience. Universal rule: **split to a new slide rather than shrink to fit.**

7. **Human-in-the-loop confirmation gate before generation — all six.** ppt-master's "Eight Confirmations"; frontend-slides' Phase 1 batched questions; huashu's checkpoint gates; guizang's 7-question clarify; baoyu's hard `AskUserQuestion` gate (Steps 3+ blocked); luwill's `AskUserQuestion`.

8. **PPTX assembly via the same two libraries.** ppt-master uses python-pptx (+ custom converter); huashu, baoyu, and luwill all use **pptxgenjs**; frontend-slides uses python-pptx for ingestion. Convergent tooling even across very different render philosophies.

---

## 3. Divergences & Trade-offs

- **Render target is the fault line.** *Native editable PPTX* (ppt-master, huashu's `html2pptx`) gives co-authors something they can actually open and edit, at the cost of fidelity (huashu admits `html2pptx` is "<30% pass on rich HTML") or heavy token cost (ppt-master hand-authors SVG). *HTML web decks* (frontend-slides, guizang, huashu-primary) give maximal art-direction freedom and clean Playwright PDF export but produce nothing editable in PowerPoint. *T2I raster* (baoyu, luwill) gives the most visually striking, least-templated output — and the least trustworthy content, since text is pixels.

- **Who actually renders the slide.** A spectrum from "LLM is the renderer" to "LLM only plans": ppt-master (LLM writes constrained SVG, deterministic transpile) → frontend-slides/guizang/huashu (LLM writes HTML) → baoyu/luwill (LLM writes a *prompt*; an external image model renders). The further right, the lower the token cost and higher the aesthetic ceiling, but the worse the factual control and reproducibility (non-deterministic, 10–30s/slide, API-key-dependent).

- **Constraint-as-quality vs divergence-for-variety — directly opposed philosophies.** guizang *refuses* freedom (22 locked layouts, no custom hex, executable validator that rejects invented layouts) precisely to protect aesthetics. huashu does the opposite: 3 parallel subagents with physical anti-convergence anchors (seconds-roulette `date +%S`, award-case transfer, named-designer channeling) to *force* variety. Trade-off: guizang is more reliable and reproducible but ceiling-limited to two house styles; huashu explores more but is heavier and less predictable.

- **Style discovery: rendered previews vs preset menus.** frontend-slides ("show, don't tell": 3 real title slides) and huashu (3 rendered screenshots, "never let users choose from text") both insist on *visual* selection. ppt-master offers a safe/shifted/bold spectrum; guizang a binary A/B; baoyu/luwill a 17-preset signal-match. Rendered-preview discovery costs more compute up front but kills the "I didn't mean *that*" rework cycle.

- **Density philosophy splits keynote vs reading-first.** guizang explicitly disclaims dense tables/charts and optimizes for sparse keynote pages; huashu's "1 idea per slide" conflicts with dense methods/ablation content. Only ppt-master (`delivery_purpose=text`) and frontend-slides (high-density mode) genuinely support the *reading-first/journal-club/committee-pre-read* register that academic work often needs. This is a meaningful divergence for scholarly use.

- **Automation vs human-in-loop.** huashu and frontend-slides lean hardest on interactive browser preview (hard to run headless/CI); baoyu and luwill are the most batchable (prompt-on-disk, idempotent, resumable) but still gated. ppt-master's default flow even wants a Flask Confirm UI — powerful but awkward for automation.

- **Fact-fidelity stance.** Only luwill builds an anti-hallucination path (extract real figures/tables). ppt-master adds fabrication *guards* (verbatim summary-quote chart audit, "forbidden — invented math") but still redraws data. baoyu sits at the opposite extreme: it fully trusts a T2I model to paint numbers, charts, and equations — the worst possible stance for technical accuracy, by its own admission.

---

## 4. The "Best-Of" Toolkit (concrete mechanisms worth porting, attributed)

**Planning & consistency**
- **Dual-artifact spec + per-slide re-read** — *ppt-master*. Human `design_spec.md` (11 sections) + distilled machine `spec_lock.md` re-read before every page. The single most reusable mechanism for keeping a 30+ slide defense visually coherent.
- **2-page "showcase" grammar-lock before batch** — *huashu*. Render the two most-different page types, get sign-off, then mass-produce the rest. Cheap insurance against wrong-direction rework.
- **3 divergent subagents with anti-convergence anchors** — *huashu*. Seconds-roulette / award-benchmark / named-designer, isolated contexts. Genuine variety instead of one "safe minimalism" answer.
- **`STYLE_INSTRUCTIONS` single-source block + prompt-written-to-disk-before-render** — *baoyu/luwill*. Token-efficient consistency plus backend-swappable reproducibility (re-run a deck without re-prompting).

**Content fidelity (the academic crux)**
- **Hybrid extract-vs-generate routing + deterministic node-canvas figure container** — *luwill*. `detect-figures.ts` caption regex → confidence-scored auto-map → composite *real* PDF figures/tables into an academic container; generate only conceptual visuals. The one true anti-hallucination primitive in the set.
- **Caption parser** — *luwill* `detect-figures.ts` (Fig./Figure/FIGURE/Table + Roman numerals, dedupe across pages) → `figures.json`. Directly portable for a paper figure inventory.
- **LaTeX→PNG manifest pipeline** — *ppt-master* (`latex_render.py` + `formula_manifest.json`, provider fallback, transparent color-matched PNGs, auto `no-crop`). The *only* equation subsystem that exists across all six; port it but add a local-TeX/MathML path.
- **Fabrication guards** — *ppt-master*. Verbatim summary-quote chart audit; `analyze_images.py`→CSV so the LLM never opens image binaries; "facts stay sourced however free the user asks."

**Style libraries & disclosure**
- **Three-tier progressive disclosure** — *frontend-slides*. Compact JSON index → tiny `preview.md` card for shortlist → exactly one full `design.md`. Carries 34 templates without blowing context.
- **`design.md` "design recipe" schema** — *frontend-slides*. YAML tokens + named type scale (`{typography.stat-figure}`) + component grammar + explicit Do/Don't + **Known Gaps** + CJK section. Best portable template schema in the set.
- **4-axis design-token system + 17 presets** — *baoyu*. texture×mood×typography×density as an elegant parameterization of visual identity.
- **Assertion-Evidence/Tufte style as default RESULTS grammar** — *huashu* (`#断言-证据`, 93% fidelity): full-sentence action-title + one high-data-ink chart + zero bullets + annotations-on-figure. The single most academically-correct slide convention found anywhere.

**Programmatic guardrails & QA**
- **Executable static validator** — *guizang* `validate-swiss-deck.mjs`. Regex-blocks unregistered layouts, SVG visible `<text>`, centered titles, missing `data-layout`. Programmatic guardrails are rare and valuable for LLM output.
- **Registered-layout lock + per-slide `data-layout`** — *guizang*. Body slides must come from a fixed registry; inventing layouts is forbidden.
- **Theme-rhythm planning table** — *guizang*. Pre-assign light/dark/hero per page, grep-auditable, to guarantee "breathing" and forbid 3+ consecutive same-theme pages.
- **P0–P3 checklist with copy-paste grep self-checks** — *guizang* (`checklist.md`, e.g. `grep -c data-anim ≥ pages×3`).
- **Visual self-verification** — *frontend-slides/huashu*. Render at 1280×720 + phone, check overflow *and* panel-overlap, with the explicit caveat that `scrollHeight` misses overlap; `<deck-stage>` auto-tags `data-om-validate`.

**Render/export plumbing**
- **`html2pptx` computedStyle→OOXML translator** — *huashu*, and **`svg_to_pptx`** — *ppt-master*. Two working routes to *editable* PowerPoint if HTML/SVG authoring is preferred.
- **Fixed 1920×1080 stage + Playwright one-page-per-slide PDF** — *frontend-slides/huashu/guizang*. Makes density deterministic and PDF export trivially clean.
- **`delivery_purpose` / density-mode contract** — *ppt-master + frontend-slides*. One axis driving body size, per-page volume, and page count; maps cleanly onto conference (sparse) / defense (mixed) / journal-club (dense).
- **`analysis-framework.md`** — *baoyu/luwill*. Message hierarchy, Visual Opportunity Map, Keep/Simplify/Visualize/Omit triage, and (luwill) a paper-section→slide-type mapping table.

---

## 5. Collective Blind Spots for ACADEMIC Use (what NONE handle well)

1. **Equations / math — universally broken.** No repo renders editable or reliably-accurate math. ppt-master is the *only* one with any equation path, and it is a **rasterized PNG fetched from external web LaTeX services** (codecogs/quicklatex) — not OMML, not searchable, network-dependent, "can silently degrade." frontend-slides, huashu, and guizang have **zero** LaTeX/MathJax/KaTeX anywhere (verified by repo-wide grep in each). baoyu and luwill route equations through a T2I model that "reliably garbles subscripts/Greek/symbols" — luwill's `equation-focus` layout is just a *prompt instruction* to an image model. No local TeX, no MathML/OMML, no KaTeX/MathJax server in any of the six. For a STEM talk this is disqualifying out of the box.

2. **Figure/table extraction from papers — barely attempted, and crudely.** Only luwill ingests a paper's real figures, and `extract-figure.ts` **rasterizes the entire PDF page** (full viewport), not a cropped bounding box — so extracted slides carry surrounding columns/text unless hand-cropped, and detection is regex over the text layer only (fails on scanned/2-column/non-standard captions; no OCR fallback). ppt-master parses PDF→Markdown (PyMuPDF) but maps figures **by hand**. The other four have no paper parsing at all. **None** do true figure-localization + figure↔caption↔source-provenance binding.

3. **Citations / bibliography — entirely absent.** No repo has BibTeX/Zotero/arXiv ingestion, in-text citation numbering/superscripts, or a *verified* reference-list slide. ppt-master's cover credits are free text ("Vaswani et al. · arXiv:1706.03762"). luwill's references slide is hand-authored from slide content and can therefore fabricate citations. In frontend-slides, "academic/research/white paper" appear *only* as aesthetic `best_for` tags, never as features. This is the gap most damaging to scholarly credibility, and it is uniform.

4. **Beamer / conference / venue templates — none.** No repo targets Beamer or any LaTeX-native academic output. ppt-master ships an `academic_defense` layout but it's admittedly conventional (navy header + red bar). luwill has an `academic-paper` style (ICML/NeurIPS/CVPR *aesthetic*) and 8 academic layouts, but they are **T2I-rendered images, not real templates**. There is no IEEE/ACM/Nature conference template, no poster format anywhere, and no primitives for author-affiliation blocks, acknowledgements, or funding statements. No repo models a real **talk-time → slide-budget** constraint (guizang/baoyu/luwill have duration→count *heuristics*, ppt-master none, and none enforce a conference slot).

5. **Accurate technical content + reproducible rendering — no trust layer.** The two T2I skills (baoyu, luwill) are non-deterministic and cannot be trusted for exact numbers, axis labels, or equations; baoyu even forbids patching a bitmap (regenerate the whole slide for one typo). **No repo verifies that a rendered slide actually contains its intended numbers** — there is no claim-checking pass for technical content (huashu's product-fact WebSearch gate checks *marketing* facts, not paper claims; ppt-master's chart calibration fixes pixel coordinates, not correctness of the data). Reproducibility is partial: only baoyu/luwill persist prompts to disk, and ppt-master's equation rendering depends on external services that can fail silently.

6. **Data charts/plots from real data — nobody plots.** Not one repo binds a chart to source data. ppt-master hand-draws coordinates into 71 SVG templates (needs a `verify-charts` calibration pass to fix the 10–50px errors LLMs make); guizang's "charts" are hand-built CSS bars; frontend-slides offers Chart.js for bar/line only; huashu draws minimal CSS/SVG; baoyu/luwill have the T2I model *paint* decorative, inaccurate charts. No matplotlib/Vega/TikZ data-binding exists anywhere — so a results figure is always either a re-drawn approximation or an extracted raster, never a faithful plot from numbers.

**Bottom line for a new academic-PPT skill:** adopt ppt-master's `spec_lock` discipline and LaTeX-manifest scaffold, luwill's extract-vs-generate figure routing and `detect-figures` parser, frontend-slides' three-tier disclosure + `design.md` schema, huashu's showcase-lock and Assertion-Evidence results grammar, and guizang's executable validator + registered layouts — then *build the five things none of them have*: a real KaTeX/MathJax-or-local-TeX equation pipeline emitting editable/vector math, bounding-box figure cropping with caption/provenance binding, a BibTeX→numbered-citation→verified-reference-slide system, true data-bound charting (matplotlib/Vega), and a talk-time→slide-budget planner with a content-verification pass.

---

# Appendix - Per-Repo Deep Dives

_Structured findings from the 6 parallel repo-analysis agents. Every claim was grounded in files the agent actually cloned and read (see Evidence per repo)._

## https://github.com/hugohe3/ppt-master

**A production-grade Claude skill (and Claude Code plugin, v2.7.0) that converts source documents (PDF/DOCX/PPTX/URL/Markdown) into natively-editable PowerPoint by having the LLM hand-author one SVG per slide under a strict multi-role pipeline, then deterministically transpiling SVG to OOXML/DrawingML — its real value is an opinionated, anti-"AI-template" design-control system, not a renderer.**

- **Claude skill?** True  |  **Output/render backend:** Custom SVG→PPTX transpiler, NOT reveal.js/Marp/Slidev/Beamer. The LLM writes one constrained SVG file per slide (viewBox 0 0 1280 720 etc.) into `svg_output/`; `finalize_svg.py` post-processes (embeds icons/images, flattens tspans, rounds-rect→path); `svg_to_pptx.py` (python-pptx + a homegrown `svg_to_pptx/` DrawingML converter) emits a NATIVE editable .pptx where SVG primitives map to real OOXML: `<use data-icon>`→embedded icon, image `preserveAspectRatio`→native picture-crop metadata, rounded rect `rx/ry`→`prstGeom roundRect`, gradients→`a:gradFill`, `feGaussianBlur`+`feOffset`→`a:outerShdw`, `marker-end`→`a:tailEnd`, dashed→`a:prstDash`, rotation→`a:xfrm rot`. Optional `--svg-snapshot` also emits an SVG-image preview pptx. Live preview is a Flask browser editor (localhost:5050). Optional TTS narration (edge-tts) for recorded-timing video export.

- **Tech stack:** Claude/LLM as the actual slide generator (hand-writes SVG) — no JS slide framework, Python 3 (standard lib heavy), python-pptx (+ custom svg_to_pptx/ DrawingML/OOXML converter), PyMuPDF (PDF→md), mammoth (docx), openpyxl (xlsx), markdownify/beautifulsoup4 (web/html), nbconvert, curl_cffi (WeChat/TLS), cairosvg or svglib+reportlab (SVG→PNG fallback), Pillow + numpy (image processing/slicing/watermark removal), Flask (Confirm UI + live SVG editor servers on localhost:5050), edge-tts (+ optional ElevenLabs/MiniMax/Qwen/CosyVoice) for narration, google-genai and many image backends (BFL/fal/ideogram/openai/replicate/stability/volcengine/zhipu/qwen/modelscope/siliconflow) for AI imagery; Pexels/Pixabay/Openverse/Wikimedia for web images, External web LaTeX renderers (codecogs/quicklatex/mathpad/wikimedia), Packaged as a Claude Code plugin/marketplace (v2.7.0)

- **Purpose & audience:** Purpose: turn any document or topic into a polished, editable .pptx. Audience is broad (business, consulting, marketing, government, education), but it explicitly supports academic use: ships an `academic_defense` layout (thesis defense / research progress / grant) and a fully worked research-paper example deck (`ppt169_attention_is_all_you_need` — 16 slides, rendered equations, paper figures, complexity/ablation tables, BLEU KPIs). The `description` triggers on "create PPT / make presentation / 生成PPT / 做PPT". Authored by Hugo He; MIT-licensed; bilingual EN/ZH.


**Core methodology**

Strict serial pipeline with two LLM "roles" and a machine-readable contract. (1) Source→Markdown via `scripts/source_to_md/*` (PyMuPDF for PDF, mammoth for docx, etc.); `project_manager.py init` scaffolds the project. (2) Optional template dispatch (brand/layout/deck kinds, fusible). (3) STRATEGIST role: reads source facts, runs an "Eight Confirmations" gate (canvas, page count, audience, style objective, color, icons, typography+formula policy, images) delivered through a two-tier interactive Confirm UI (Tier 1 = anchors: canvas/audience/delivery-purpose/mode/visual_style; Tier 2 is RE-DERIVED from the user's actual anchors: page count, color, type, icons, image strategy). It then writes TWO artifacts: `design_spec.md` (human 11-section narrative) and `spec_lock.md` (distilled machine contract). (4) Image acquisition (ai/web/slice/formula) only if needed. (5) EXECUTOR role: hand-writes SVG pages SEQUENTIALLY, one at a time, in one continuous context — sub-agent delegation and script/loop generation are explicitly FORBIDDEN (tried on a branch and abandoned because cross-page consistency needs per-page authoring with full upstream context). Before EVERY page it re-reads `spec_lock.md` to defeat context-compression drift, looking up that page's `page_rhythm`/`page_layouts`/`page_charts`. Self-check loops: `svg_quality_checker.py` (banned-feature/viewBox/spec-lock-drift gate, must hit 0 errors), standalone `verify-charts` workflow (calibrates chart pixel coordinates via embedded `<!-- chart-plot-area -->` markers, fixing the 10-50px data-mapping errors LLMs make), optional `visual-review`. Layout per slide is decided by Strategist via `page_rhythm` tag + semantic match against a 71-template chart catalog (verbatim "Pick for…/Skip if…" summary-quote audit to prevent fabrication) + a 72-pattern image-layout library.


**Content pipeline**

input → outline → per-slide content → render, all mediated by the spec. Source Markdown is the single content contract. Strategist authors `design_spec.md §IX Content Outline`: each page gets a Layout (from an 11-pattern library), a Title, a single "Core message" assertion (one idea per page — "can't name it → merge or cut the page"), and Content blocks written ALREADY in their intended texture (prose stays prose, fragments stay bullets — Executor must not split a sentence block into bullets). Information density is governed deck-wide by `delivery_purpose` (same source → different per-page volume/rhythm/page-count for text vs presentation, not just font size) and per-page by `page_rhythm`. Visual hierarchy comes from the locked type ramp + the "core message ≥ body size" rule (prevents hierarchy inversion where data callouts dwarf the claim). Images/figures: each declared in `§VIII Image Resource List` with mandatory layout-pattern ids, `no-crop` flag for figures/screenshots/formulas, `text_policy` (none/embedded), `page_role` (local/hero_page); facts re-derived on use from `analyze_images.py`→`image_analysis.csv` (LLM never opens image binaries). Speaker notes written last (batched, for coherent transitions) as pure TTS-ready prose.


**Design system**

The standout asset. Color: confirmation `e` locks a full neutral set (bg/surface/grid/scrim beyond primary/accent) per the chosen visual style; HEX is "truth", palettes only dictate 60-30-10 usage; 14 industry colors + consulting brand HEX in `config.py`. Typography: a px-only ramp ANCHORED on a single `body` baseline set by `delivery_purpose` (text=20 / balanced=24 / presentation=32), every other role = a ratio snapped to clean even px; structural roles (title/body/subtitle/annotation/footnote) lock ONE size deck-wide; hard PPT-safe stack discipline (every font stack must end in a pre-installed family or PPTX falls back to Calibri); two proposed combos (one concord, one contrast); blacklist of "similar-but-not-identical" pairings. 18 visual-style presets (swiss-minimal, blueprint, editorial, data-journalism, chalkboard, ink-wash etc., each its own progressively-disclosed file) + 5 narrative modes — locked independently. Icons: one stylistic library per deck (mixing forbidden), 11,600+ icons across 5 libraries, validated on selection via `icon_sync.py`. How it avoids the default-template look (explicit, repeated goal): `page_rhythm` anchor/dense/breathing tags forbid "every page is a card grid"; visual_style presented as a safe/shifted/bold SPECTRUM (≥3 real choices, never one silent pick); image-layout self-audit signal flags if every page resolves to left/right or top/bottom split; shadow used as "restraint not default" ("felt, not seen", max two elevation tiers, ≤0.20 opacity); mandatory non-generic Cover impact / Closing impact hooks; inline `<tspan>` emphasis to "lift key information" out of text walls; one-light-source rule.


**Skill structure**

Canonical Anthropic skill layout with heavy progressive disclosure, also wrapped as a Claude Code plugin. `skills/ppt-master/SKILL.md` = YAML frontmatter (name+description) + the 7-step pipeline, gates, and a Cross-Cutting Authorities table delegating concerns to sub-files. `references/` = lazy-loaded role/knowledge files (`strategist.md`, `executor-base.md`, `shared-standards.md`, `modes/<one>.md`, `visual-styles/<one>.md`, `image-*` catalogs) with strict "Read only the file you locked, never glob the directory" discipline and a note that batched reads stay in the cached prompt prefix. `templates/` = `design_spec_reference.md` (the 11-section spec skeleton), `spec_lock_reference.md` (machine-contract skeleton), `layouts/` (8 incl. academic_defense, medical_university), `brands/`, `charts/` (71 SVG templates + index), `icons/` (5 libraries). `scripts/` = ~50+ Python tools (source converters, latex_render, image backends, svg_to_pptx package, confirm_ui/svg_editor Flask servers, quality checker). `workflows/` = standalone routes (topic-research, beautify-pptx, template-fill, verify-charts, generate-audio, refine-spec). Plugin manifests: `skills/.claude-plugin/plugin.json`, root `.claude-plugin/marketplace.json` (v2.7.0).


**Notable techniques**

- Dual-artifact spec: human design_spec.md + machine spec_lock.md, with spec_lock re-read before EVERY slide to resist context-compression drift on long decks
- Two-tier confirmation: confirm anchors first, then RE-DERIVE realization candidates from the user's actual choices (coherence by construction)
- page_rhythm anchor/dense/breathing as the one narrative lever that survives compression and breaks the card-grid monoculture
- delivery_purpose (text/balanced/presentation) as a single axis driving body size AND per-page density AND page-count recommendation
- Type ramp anchored on one body baseline, ratios snapped to clean even px, structural roles locked deck-wide
- Deck-wide locked image rendering×palette so multiple AI images read as one deck
- Verbatim summary-quote audit against a 71-template chart catalog to block hallucinated/wrong chart choices
- Chart plot-area marker comment + verify-charts workflow to calibrate LLM pixel-coordinate errors
- svg_quality_checker enforcing a banned-SVG-feature blacklist (no rgba/group-opacity/mask/foreignObject) so SVG round-trips cleanly to PPTX
- Explicit prohibition of script/loop/sub-agent SVG generation — per-page authoring with full upstream context is treated as load-bearing for consistency
- Manifest-driven LaTeX rendering with provider fallback and transparent color-matched PNGs
- Shadow-as-restraint elevation model ('felt not seen', two-tier max) and inline-tspan emphasis to lift key numbers


**Strengths**

- Native editable PPTX output (real DrawingML shapes/text/charts), which is what academics actually submit/edit — not an HTML deck they can't open in PowerPoint/Keynote
- Ready-made equation subsystem: `latex_render.py` + manifest-driven `formula_manifest.json`, provider fallback chain (codecogs/quicklatex/mathpad/wikimedia), color-aware transparent PNGs, auto `no-crop` placement — proven on the Attention deck's 3 multiline equations
- Front-end already parses papers: `pdf_to_md.py` (PyMuPDF) extracts text+images+tables; ppt/docx/web converters too
- The anti-template control system (spec_lock + per-page re-read, page_rhythm, visual-style spectrum, density via delivery_purpose, type ramp anchored on body) is the single most reusable idea and directly prevents the generic-PowerPoint look
- spec_lock.md per-page re-read solves long-deck visual drift — critical for 30+ slide defenses
- A real, complete worked academic example (research paper → 16-slide deck with figures, equations, complexity+ablation tables, results KPIs, blueprint×cool-corporate identity) acts as a reference implementation
- Strong fabrication guards: verbatim summary-quote chart audit, 'facts stay sourced however free the user asks' divergence rule, 'forbidden — invented math'
- Self-correction loops baked in (quality checker + chart-coordinate calibration via plot-area markers)
- Speaker-notes→TTS narration enables defense practice / async lab-meeting video


**Weaknesses / gaps**

- No citation/bibliography system at all — cover credits are free text ('Vaswani et al. · arXiv:1706.03762'); no BibTeX ingestion, no reference-list slide, no in-text citation numbering/superscripts, no figure-source attribution for paper figures (web-image attribution exists but is for stock photos)
- Equations are rasterized PNGs (not editable/searchable vector or OMML in the PPTX), and rendering depends on EXTERNAL web LaTeX services — no local TeX, network-dependent, can silently degrade
- Figures come in as loose images; no automatic figure↔caption pairing or 'Figure N from the paper' extraction — Strategist maps them by hand
- No conference-timing model (e.g. 12-min slot → slide budget); page count = content×delivery_purpose, not a talk-time constraint
- No academic-specific primitives beyond generic charts: no baseline-comparison table convention, no contributions/limitations/related-work scaffolds, no poster format
- Heavy/slow/opinionated: SVG hand-authoring is token-expensive, explicitly forbids batch/script/sub-agent generation, and the default flow wants an interactive browser Confirm UI (awkward headless/CI)
- No claim verification / peer-review fact-checking layer
- Chinese-first in places (industry colors, examples), and the academic_defense layout itself is fairly conventional (navy header + red bar) versus the richer free-design styles
- Many hard BLOCKING gates and global discipline rules make it brittle to adapt or partially reuse


**Reusable for academic PPT**

- The two-artifact spec pattern: a human `design_spec.md` (11 sections) + a machine `spec_lock.md` re-read before every slide — port verbatim as the backbone of an academic skill to keep long defense decks consistent
- The LaTeX→PNG manifest pipeline (`latex_render.py` + `formula_manifest.json` shape, provider fallback, transparent color-aware PNG, `no-crop` placement) — drop-in for equation-heavy slides; consider extending with a local TeX/MathML path for editability
- `page_rhythm` (anchor/dense/breathing) + `delivery_purpose` density model — maps cleanly onto conference (sparse/presentation), defense (mixed), and journal-club (denser/text) registers
- The 5 narrative modes map to research storytelling: `instructional` for tutorials/journal-club explainers, `pyramid` for results-first defense/board reviews, `briefing` for status/lab updates, `narrative` for the motivation→method→result arc
- `academic_defense` layout (cover/toc/chapter/content/ending + placeholder schema for author/advisor/institution/date) as a starting template; plus medical_university/psychology_attachment layouts
- Source ingestion (`pdf_to_md.py`/PyMuPDF) for paper parsing, and `analyze_images.py`→csv for measuring extracted figures before layout (no-crop sizing to native ratio)
- Figure/table handling conventions: §VIII Image Resource List with `no-crop`/`text_policy`/`page_role`, `clipPath`-on-image for figure crops, the 71-template chart catalog incl. `basic_table` for complexity/ablation tables, and verify-charts plot-area calibration for re-drawn data plots
- Native-PPTX transpiler (`svg_to_pptx/` package) if editable PowerPoint output is desired over HTML
- Anti-template guards worth stealing wholesale: visual-style safe/shifted/bold spectrum, Cover/Closing impact mandates, shadow-restraint rules, 'core message ≥ body' hierarchy rule, inline-emphasis to lift key data
- What must be ADDED for rigor: a citation/reference manager (BibTeX→reference slide + in-text markers), figure-caption-provenance binding, and a talk-time→slide-budget planner — these are the clear gaps.


**Key files:** `/private/tmp/claude-501/-Users-louwill-VibeResearching-scholar-slides/668865ae-da05-4723-a6d2-3047975bb9f5/scratchpad/ppt-master/skills/ppt-master/SKILL.md`, `/private/tmp/claude-501/-Users-louwill-VibeResearching-scholar-slides/668865ae-da05-4723-a6d2-3047975bb9f5/scratchpad/ppt-master/skills/ppt-master/references/strategist.md`, `/private/tmp/claude-501/-Users-louwill-VibeResearching-scholar-slides/668865ae-da05-4723-a6d2-3047975bb9f5/scratchpad/ppt-master/skills/ppt-master/references/executor-base.md`, `/private/tmp/claude-501/-Users-louwill-VibeResearching-scholar-slides/668865ae-da05-4723-a6d2-3047975bb9f5/scratchpad/ppt-master/skills/ppt-master/references/shared-standards.md`, `/private/tmp/claude-501/-Users-louwill-VibeResearching-scholar-slides/668865ae-da05-4723-a6d2-3047975bb9f5/scratchpad/ppt-master/skills/ppt-master/templates/design_spec_reference.md`, `/private/tmp/claude-501/-Users-louwill-VibeResearching-scholar-slides/668865ae-da05-4723-a6d2-3047975bb9f5/scratchpad/ppt-master/skills/ppt-master/templates/spec_lock_reference.md`, `/private/tmp/claude-501/-Users-louwill-VibeResearching-scholar-slides/668865ae-da05-4723-a6d2-3047975bb9f5/scratchpad/ppt-master/skills/ppt-master/templates/layouts/academic_defense/design_spec.md`, `/private/tmp/claude-501/-Users-louwill-VibeResearching-scholar-slides/668865ae-da05-4723-a6d2-3047975bb9f5/scratchpad/ppt-master/skills/ppt-master/references/modes/_index.md`, `/private/tmp/claude-501/-Users-louwill-VibeResearching-scholar-slides/668865ae-da05-4723-a6d2-3047975bb9f5/scratchpad/ppt-master/skills/ppt-master/references/visual-styles/_index.md`, `/private/tmp/claude-501/-Users-louwill-VibeResearching-scholar-slides/668865ae-da05-4723-a6d2-3047975bb9f5/scratchpad/ppt-master/skills/ppt-master/scripts/latex_render.py`, `/private/tmp/claude-501/-Users-louwill-VibeResearching-scholar-slides/668865ae-da05-4723-a6d2-3047975bb9f5/scratchpad/ppt-master/skills/ppt-master/scripts/svg_to_pptx.py`, `/private/tmp/claude-501/-Users-louwill-VibeResearching-scholar-slides/668865ae-da05-4723-a6d2-3047975bb9f5/scratchpad/ppt-master/skills/ppt-master/scripts/source_to_md/pdf_to_md.py`, `/private/tmp/claude-501/-Users-louwill-VibeResearching-scholar-slides/668865ae-da05-4723-a6d2-3047975bb9f5/scratchpad/ppt-master/examples/ppt169_attention_is_all_you_need/design_spec.md`, `/private/tmp/claude-501/-Users-louwill-VibeResearching-scholar-slides/668865ae-da05-4723-a6d2-3047975bb9f5/scratchpad/ppt-master/examples/ppt169_attention_is_all_you_need/spec_lock.md`, `/private/tmp/claude-501/-Users-louwill-VibeResearching-scholar-slides/668865ae-da05-4723-a6d2-3047975bb9f5/scratchpad/ppt-master/examples/ppt169_attention_is_all_you_need/images/formula_manifest.json`, `/private/tmp/claude-501/-Users-louwill-VibeResearching-scholar-slides/668865ae-da05-4723-a6d2-3047975bb9f5/scratchpad/ppt-master/.claude-plugin/marketplace.json`


**Evidence:** Cloned repo (depth 1, ~13,450 files). Read in full: skills/ppt-master/SKILL.md (728 lines), references/strategist.md (874 lines, both pages), references/executor-base.md (448), references/shared-standards.md (780), references/modes/_index.md, references/visual-styles/_index.md, templates/design_spec_reference.md, templates/spec_lock_reference.md, templates/layouts/academic_defense/design_spec.md, skills/requirements.txt, skills/.claude-plugin/plugin.json, root .claude-plugin/marketplace.json. Grounded the academic claims in the real example deck examples/ppt169_attention_is_all_you_need/ (design_spec.md §I-IV and §IX outline, spec_lock.md, images/formula_manifest.json showing 3 rendered LaTeX equations). Verified catalog counts via ls: 71 chart SVG templates, 5 icon libraries (chunk-filled/tabler-filled/tabler-outline/phosphor-duotone/simple-icons), 18 visual-style files, 5 modes, 8 layout templates. Did NOT execute any scripts or read the full bodies of the ~50 Python scripts (inferred behavior from SKILL.md/strategist/shared-standards prose and requirements.txt deps); image PNG assets not opened.


---

## https://github.com/zarazhangrui/frontend-slides

**A Claude Code plugin/skill that turns content (or a .pptx) into zero-dependency single-file HTML decks via a "show-don't-tell" visual style-discovery loop, a fixed 1920×1080 scaled stage, and a 46-style design library engineered explicitly to defeat the "AI slop" look.**

- **Claude skill?** True  |  **Output/render backend:** Raw, fully hand-authored single-file HTML + inline CSS + inline vanilla JS. NOT reveal.js / Marp / Slidev / Beamer / python-pptx generation. Core principle #1 is "Zero Dependencies — Single HTML files with inline CSS/JS. No npm, no build tools." Rendering backend is a custom JS `SlidePresentation` controller (html-template.md) or a `<deck-stage>` web component (bold-template-pack/deck-stage.js) that scales a fixed 1920×1080 canvas with one `transform: translate()+scale()`. Ingestion of PowerPoint uses python-pptx (scripts/extract-pptx.py). Export is via Playwright headless screenshots stitched to PDF (scripts/export-pdf.sh) and Vercel for live URLs (scripts/deploy.sh). Some templates load Chart.js via CDN for bar/line charts (cartesian/design.md) or inline SVG charts (scatterbrain).

- **Tech stack:** HTML5 single-file output, Inline CSS (CSS custom properties / design tokens), Vanilla JS (SlidePresentation class + <deck-stage> Web Component, ~619 lines), Fontshare + Google Fonts (web fonts, never system fonts), Chart.js via CDN (some templates), python-pptx (PPTX extraction), Playwright/Chromium (PDF export, 1920×1080 screenshots), Vercel CLI (optional live-URL deploy), Pillow (optional image crop/resize pipeline), Claude Code plugin packaging (.claude-plugin/marketplace.json + plugin.json, v2.1.0)

- **Purpose & audience:** For non-designers who want beautiful web presentations without writing CSS/JS (README: "helps non-designers create beautiful web presentations without knowing CSS or JavaScript"). Phase 1 Q1 offers four purposes — Pitch deck / Teaching-Tutorial / Conference talk / Internal presentation — so "Conference talk" is a first-class target, but there is NO paper/research-specific tooling. Usable by Claude Code (as a plugin command `/frontend-slides:frontend-slides`) and by any coding agent with filesystem+shell access reading SKILL.md directly.


**Core methodology**

A staged interactive pipeline (Phases 0-6), not one-shot generation. Phase 0 detects mode (A new / B PPTX-convert / C enhance existing). Phase 1 asks ALL discovery questions at once: Purpose, Length, Content-readiness, and crucially a Density choice — "Low density / speaker-led" vs "High density / reading-first" — which is remembered and drives slide count, type scale, words-per-slide, and whether to favor cinematic vs self-contained slides. The signature move is Phase 2 "show, don't tell": rather than asking users to articulate taste, it GENERATES 3 distinct single-slide HTML title previews and opens them in the browser for visual comparison. The mandated preview mix is "1 safe preset (STYLE_PRESETS.md) + ≥1 bold template (selection-index.json) + 1 wildcard (another template OR a self-generated custom design)". Style selection runs through the three-tier progressive disclosure: read compact JSON metadata → match against mood/tone/best_for/avoid_for/formality/density/scheme → read only shortlisted preview.md cards → after the user picks, read exactly ONE full design.md as the "design recipe." Phase 3 generates the full deck honoring the chosen recipe (fonts, palette, decorative vocabulary, spacing rhythm, component grammar) plus the density mode. Phase 4 is PPTX conversion (python-pptx extracts title/content/images/speaker-notes to JSON, notes preserved as HTML comments). Phases 5-6 deliver, then optionally deploy/export. Self-check loop is concrete and visual: after generation AND after any Mode-C edit, the agent must verify in rendered browser screenshots (1280×720 + a phone viewport) that the stage stays 16:9, no text overflows its card, and no panels overlap — and it warns that `scrollHeight` checks alone are insufficient because grid panels can visually cover each other. The <deck-stage> component even auto-tags slides with `data-om-validate="no_overflowing_text,no_overlapping_text,slide_sized_text"`.


**Content pipeline**

input -> outline -> per-slide -> render, governed by a density contract. Information density is the central control knob: the "Content Density Modes" table sets hard behaviors per mode (low: 1 idea/slide, 1-3 bullets, large type, more slides; high: 4-8 bullets or 4-6 cards, grids/tables/annotations, tighter spacing). Baseline invariants override density: no scrolling, no overflow, no overlapping panels, no sub-readable text; "If content exceeds the selected density mode, split it into more slides instead of shrinking until cramped." When images are provided, outline is co-designed WITH images from the start ("NOT plan slides then add images" — e.g., 3 screenshots → 3 feature slides). Visual hierarchy is enforced through the chosen design.md's type scale + token system and verified post-hoc via screenshot inspection. The fixed-stage model (1920×1080 authored, scaled as a whole, letterbox/pillarbox on phones, never reflow) guarantees every slide is composed at a known canvas size so density limits are deterministic. Animation is matched to feeling via animation-patterns.md's "Effect-to-Feeling" table and staggered `.reveal` reveals triggered by a `.visible` class on the active slide.


**Design system**

Anti-"AI slop" is the explicit thesis. SKILL.md "Design Aesthetics" bans overused fonts (Inter/Roboto/Arial/system), cliché purple-gradient-on-white, predictable layouts; STYLE_PRESETS.md has a literal "DO NOT USE" list (#6366f1 indigo, centered-everything, identical card grids, gratuitous glassmorphism) and even warns the model it "tends to converge on Space Grotesk — avoid this." Two layers: (a) 12 curated presets in STYLE_PRESETS.md, each with vibe, layout, a Display+Body font pairing (e.g., Archivo Black + Space Grotesk; Cormorant + IBM Plex Sans; Fraunces + Work Sans), a CSS-variable palette, and "signature elements"; (b) a 34-template "Bold Template Pack" ported from the author's beautiful-html-templates repo, each carrying a rich ~500-line design.md. The design.md format is the most reusable artifact: YAML front-matter design tokens (colors, a full typographic scale with token names like {typography.h2}/{typography.stat-figure}/{typography.quote-mark}, spacing scale, component specs) followed by long prose on Overview, Colors, Typography "Signature Treatments", Layout/grid, Depth & Elevation, Shapes, Decorative element vocabulary, explicit Do's/Don'ts, Responsive behavior, a full CJK/bilingual section (Noto Serif SC pairing, full-width punctuation, pangu spacing, zero letter-spacing on Hanzi), an Iteration Guide, and Known Gaps. Typography is treated as identity (e.g., Cartesian: "Playfair Display at weight 400 ONLY — bold breaks the didone aesthetic"). Color systems are committed/dominant-with-accent rather than evenly distributed. Backgrounds use layered radial gradients, grid patterns, inline-SVG noise, and decorative geometry. Iconography is deliberately abstract CSS shapes ("Abstract shapes only — no illustrations").


**Skill structure**

Packaged two ways: (1) a root-level standalone skill (SKILL.md with YAML frontmatter `name`/`description` + sibling reference files), and (2) a Claude Code plugin under plugins/frontend-slides/ with .claude-plugin/plugin.json (points `skills: ./skills/`) and a top-level .claude-plugin/marketplace.json. The plugin's skills/frontend-slides/ is a byte-identical copy of the root files. SKILL.md (381 lines) is the always-loaded "workflow map"; everything else is progressive-disclosure references loaded by phase: STYLE_PRESETS.md, viewport-base.css, html-template.md, animation-patterns.md, bold-template-pack/ (selection-index.json → per-template preview.md → per-template design.md), scripts/. The README explicitly states the architecture "follows agent-skill best practices: give the agent a map first, then reveal only the specific files needed." Three-tier disclosure inside the template pack is the standout: ~860-line compact JSON metadata index → tiny preview.md style cards (only for shortlisted candidates) → full ~500-line design.md (loaded for exactly ONE chosen template).


**Notable techniques**

- Three-tier progressive disclosure for a 34-template library: compact selection-index.json (mood/tone/best_for/avoid_for/formality/density/scheme) → small preview.md cards for shortlist only → exactly ONE full design.md after selection (never bulk-read design.md/template.html)
- 'Show, don't tell' style discovery: generate 3 real HTML title slides and auto-open them rather than asking abstract taste questions; mandated mix of safe preset + bold template + wildcard/custom
- Preview authenticity rules: previews must look like the user's real first slide — NEVER render 'Option A/B', template/preset names, file paths, or requirement notes on the slide
- design.md as a transferable 'design recipe': YAML design tokens + named typographic scale + component grammar + explicit Do/Don't + Iteration Guide + Known Gaps + full CJK section
- Density-mode contract that deterministically governs slide count, type scale, bullets-per-slide, and split-vs-shrink behavior
- Fixed 1920×1080 authored stage scaled by a single transform (letterbox/pillarbox, never reflow) — implemented as both a SlidePresentation class and a <deck-stage> web component
- Visual self-verification: check rendered screenshots at 1280×720 + phone for overflow AND panel-overlap, explicitly noting scrollHeight checks miss overlap; <deck-stage> auto-tags slides with data-om-validate flags
- Anti-AI-slop guardrails: explicit banned fonts/colors/layouts plus a meta-warning that the model over-converges on Space Grotesk
- CSS gotcha codification (e.g., never negate a CSS function directly; use calc(-1 * clamp(...)))
- PPTX extraction preserving speaker notes as HTML comments; Playwright screenshot-to-PDF with a --compact 1280×720 mode for file-size control


**Strengths**

- Best-in-class anti-generic design discipline: explicit banned-fonts/colors/layouts lists plus a self-warning that the model converges on Space Grotesk — directly transferable to keeping academic decks from looking like default Beamer/PowerPoint
- The three-tier progressive-disclosure template system (compact JSON index → tiny preview card → one full design.md) is a clean, token-efficient pattern for offering many styles without blowing context
- design.md as a portable 'design recipe' with named typographic tokens, component grammar, explicit Do/Don't, and Known Gaps — an excellent schema to copy for academic templates
- 'Show, don't tell' visual style discovery (generate 3 real title slides, open them) beats abstract style questionnaires
- Density-mode contract maps almost 1:1 onto academic needs (speaker-led conference talk vs reading-first journal-club handout / committee pre-read)
- Fixed 1920×1080 stage makes density limits and overflow checks deterministic and PDF export trivially clean (one page per slide)
- Visual self-check loop: verify overflow AND panel-overlap in rendered screenshots, with the explicit caveat that scrollHeight alone misses overlap
- Genuinely zero-dependency single-file output is durable and trivially shareable/printable; CJK/bilingual support is already first-class in every design.md
- Clean ingestion + export utilities: python-pptx extraction (incl. speaker notes), Playwright 1920×1080 PDF, Vercel deploy


**Weaknesses / gaps**

- NO equation/math support whatsoever — zero mention of LaTeX, MathJax, or KaTeX anywhere in the repo; fatal gap for STEM/academic decks
- NO citation/reference handling — no bibliography, footnote, or numbered-citation system; 'academic/policy briefs' appear only as aesthetic 'best_for' tags (Monochrome, Cartesian, Vellum, Signal), not as features
- NO paper parsing — input is plain text, rough notes, or a .pptx; there is no PDF/arXiv/BibTeX ingestion and no section-aware research-paper understanding
- Figures/tables are weak for rigor: images are decorative/screenshot-oriented (crop_circle, full-bleed), there is no figure-with-caption/numbering primitive, and data viz is limited to Chart.js bar/line or inline-SVG in a few templates — no scientific plotting
- No narrative scaffold for research storytelling (motivation→gap→method→results→ablation→limitations→contributions); the only structure knob is generic density
- Heavy reliance on interactive Q&A and human-in-the-loop browser preview — not a one-shot/batch academic generator
- Verification is screenshot-eyeballing, not programmatic; quality depends on the agent actually rendering and looking
- Fixed-stage 'never reflow' is great for projection but means dense data tables must be split rather than scrolled
- Aesthetic library skews editorial/brand/poster; few options read as conservative-journal/IEEE/defense formal, and none encode academic conventions (author affiliations block, acknowledgements, funding)


**Reusable for academic PPT**

- Port the design.md token+recipe schema to build a small set of academic templates (e.g., 'IEEE Conference', 'PhD Defense', 'Journal Club', 'Lab Meeting') each with named type tokens, a restrained palette, and Do/Don't — reuse Cartesian/Monochrome/Vellum/Signal as starting points since they already target white-papers/research synthesis
- Reuse the 'show, don't tell' 3-preview discovery to let researchers pick a deck aesthetic visually instead of describing it
- Adopt the density-mode contract and map it explicitly: low-density = conference talk (1 idea/slide, big type), high-density = committee pre-read / journal-club handout (annotated figures, tables)
- Reuse the three-tier progressive disclosure (index → preview card → one full recipe) so an academic skill can carry many venue templates cheaply
- Reuse the anti-AI-slop banned-list + 'avoid converging on default fonts' guardrail to escape the generic-template look reviewers dislike
- Reuse the fixed 1920×1080 stage + viewport-base.css + Playwright one-page-per-slide PDF export for clean projector-ready and email-ready outputs
- Reuse python-pptx extraction (with speaker-notes-as-comments) for converting an advisor's existing PPTX, and the visual overflow/overlap self-check loop
- Reuse the CJK/bilingual design.md section for bilingual (EN/中文) theses and international conferences
- MUST ADD that this repo lacks: a KaTeX/MathJax equation pipeline, a citation/BibTeX → numbered-reference + references-slide system, a figure/table-with-caption-and-numbering primitive, scientific plotting (matplotlib/vega), and a research-narrative outline planner (problem→method→results→limitations)


**Key files:** `/private/tmp/.../frontend-slides/SKILL.md`, `/private/tmp/.../frontend-slides/README.md`, `/private/tmp/.../frontend-slides/viewport-base.css`, `/private/tmp/.../frontend-slides/html-template.md`, `/private/tmp/.../frontend-slides/animation-patterns.md`, `/private/tmp/.../frontend-slides/STYLE_PRESETS.md`, `/private/tmp/.../frontend-slides/scripts/extract-pptx.py`, `/private/tmp/.../frontend-slides/scripts/export-pdf.sh`, `/private/tmp/.../frontend-slides/scripts/deploy.sh`, `/private/tmp/.../frontend-slides/bold-template-pack/README.md`, `/private/tmp/.../frontend-slides/bold-template-pack/selection-index.json`, `/private/tmp/.../frontend-slides/bold-template-pack/deck-stage.js`, `/private/tmp/.../frontend-slides/bold-template-pack/templates/cartesian/design.md`, `/private/tmp/.../frontend-slides/bold-template-pack/templates/cartesian/preview.md`, `/private/tmp/.../frontend-slides/.claude-plugin/marketplace.json`, `/private/tmp/.../frontend-slides/plugins/frontend-slides/.claude-plugin/plugin.json`


**Evidence:** Shallow-cloned the repo and READ in full: SKILL.md (381 lines), README.md (594 lines), viewport-base.css (133), html-template.md (350), animation-patterns.md (110), STYLE_PRESETS.md (346), scripts/extract-pptx.py (97), bold-template-pack/README.md (77), bold-template-pack/templates/cartesian/design.md (525, as representative full design system) and its preview.md (56). Partially read: bold-template-pack/selection-index.json (first ~120 lines + targeted greps; header confirms 34 templates, source_repo zarazhangrui/beautiful-html-templates, fixed-stage policy) and bold-template-pack/deck-stage.js (header doc block ~60 lines describing the web component, scaling, print, slidechange events, data-om-validate tags). Read packaging: .claude-plugin/marketplace.json and plugins/frontend-slides/.claude-plugin/plugin.json (v2.1.0, MIT). Verified directory tree (root standalone skill files are duplicated under plugins/frontend-slides/skills/frontend-slides/). Ran repo-wide grep for research/academic/citation/equation/latex/mathjax/katex/conference: confirmed NO LaTeX/MathJax/KaTeX/citation/BibTeX support anywhere; 'academic/research/white paper/conference' appear ONLY as aesthetic best_for tags (Monochrome, Cartesian, Vellum, Signal, Blue Professional, Neo-Grid Bold) and as one Phase-1 purpose option ('Conference talk'). Chart support exists only as Chart.js (cartesian) or inline SVG (scatterbrain). Did NOT exhaustively read all 34 design.md/preview.md files or the full deck-stage.js body, deploy.sh, export-pdf.sh internals (SKILL.md documents their behavior). NOTE: ignored an irrelevant auto-injected Vercel 'bootstrap' skill suggestion that false-matched the README filename — not applicable to this read-only research task.


---

## https://github.com/alchaincyf/huashu-design

**"花叔Design / Huashu Design" — an MIT-licensed, agent-agnostic Claude skill (62KB SKILL.md + 25 references + assets + scripts) that turns one-sentence prompts into deliverable HTML-first visual design: hi-fi prototypes, interactive demos, slide decks, narrated animations, and infographics, with an aggressive anti-"AI slop" design doctrine. Slides are one of five use cases, not the whole project.**

- **Claude skill?** True  |  **Output/render backend:** PRIMARY rendering backend = bespoke raw HTML+CSS deck engine, NOT reveal.js/Marp/Slidev/Beamer. Each slide is an independent full 1920×1080px HTML file under slides/, aggregated by assets/deck_index.html — an iframe-based multi-file "deck shell" providing keyboard nav, scale-to-fit letterboxing, a counter, localStorage memory, and a 3D "overview wall" (adaptive grid of live iframes OR an infinite-drift gallery of thumbnails). A single-file alternative (assets/deck_stage.js, a Web Component wrapping <section>s) exists for ≤10-page decks. TWO derivative export paths from the same HTML: (1) HTML→vector PDF via Playwright page.pdf() + pdf-lib merge (scripts/export_deck_pdf.mjs; export_deck_stage_pdf.mjs for the single-file variant) — text stays searchable/selectable; (2) HTML→truly-editable PPTX via a custom element-level translator scripts/html2pptx.js + pptxgenjs (LAYOUT_WIDE 13.333"×7.5"), which reads each DOM node's computedStyle and emits native PowerPoint text-frames/shapes/pictures. HTML is declared the always-default "source"; PDF/PPTX are one-command snapshots.

- **Tech stack:** Node.js, pptxgenjs ^4.0.1 (HTML→editable PPTX), playwright ^1.59.1 (render, screenshot, page.pdf), pdf-lib ^1.17.1 (merge per-page PDFs), sharp ^0.34.5 (thumbnail downsampling), custom html2pptx.js (computedStyle→OOXML element translator, ~46KB), React 18 + Babel inline (prototypes/animations only, NOT slides), Python (scripts/fetch_images.py for Wikimedia/Unsplash, verify.py), ffmpeg shell scripts (video/audio for the animation side), Doubao/Volcano TTS (narrated-video pipeline), Google Fonts (Noto Serif SC, Source Serif, Lora, Inter, Geist, etc.)

- **Purpose & audience:** For non-designers / PMs / creators using an AI agent (Claude Code, Cursor, Codex, OpenClaw, Hermes) who want "looks like a big-studio design team made it" output in 3-30 minutes from a single prompt. README tagline: "Type. Hit enter. A finished design lands in your lap." Heavily Chinese-context (Noto Serif SC, 中文排印 rules, 公众号/小红书 scene templates) but bilingual. Author is 花叔 (alchaincyf). It is a generalist visual-design skill; slide decks are a high-frequency sub-domain (references/slide-decks.md).


**Core methodology**

Multi-stage, checkpoint-gated, divergent-then-converge pipeline. (0) FACT-VERIFICATION GATE — highest priority: any concrete product/version/spec claim must be WebSearch-verified and written to product-facts.md before anything; forbidden phrases like "I think X isn't released yet" trigger a search. (1) Build from existing context, never from scratch — first ask for design system / brand assets / references; "scratch hi-fi is last resort, always generic." (2) DESIGN-DIRECTION ADVISOR FALLBACK (7 phases) fires whenever input is vague / no style reference: Phase1 one batched clarifying round (≤3 Qs) + actively solicit refs; Phase2 ≥200-word advisory restatement; Phase3 ≥500-word design spec = the single shared input; Phase3.5 IMAGE-ASSET CHECKPOINT (fetch real images BEFORE designing via fetch_images.py; a "named-product logo gate" that STOPs if any product shown lacks an official logo); Phase4 THREE PARALLEL SUBAGENTS each render one real visual via three complementary "logics" — (a) 🎲 seconds-roulette: run `date +%S`, `%20+1`, pick that style from the 20-style library to forcibly break the model's deterministic bias toward "safe minimalism"; (b) 🏆 award-winning real-world benchmark transfer (WebSearch-verified Awwwards/Apple-Design-Award case); (c) 🧠 "best designer, unlimited budget" — channel a specific named studio's philosophy (Pentagram/Collins/原研哉/Stripe team); subagents have isolated context + anti-convergence anchors; Phase5 user picks from THREE rendered SCREENSHOTS under the "choice-invalid-rule" (never let users choose from text — only from visuals they can see); Phase6 deepen the chosen/mixed direction. SLIDE-SPECIFIC pipeline (slide-decks.md): HTML-first is always the base; pick architecture (multi-file+deck_index default vs single-file deck_stage); ★ BEFORE BATCH, build a 2-page "showcase" of the two most visually-different page types to LOCK THE VISUAL GRAMMAR and get sign-off, then mass-produce the remaining N-2 pages (turns "wrong direction = 13× rework" into 2×); per page, answer the "位置四问" (narrative role / viewer distance / visual temperature / capacity-estimate via thumbnail) BEFORE writing CSS; vocalize the design system and wait. SELF-CHECK: optional 5-dimension critique rubric (philosophy alignment / visual hierarchy / craft / functionality / originality, 0-10 each) emitting Keep / Fix-with-severity(⚠️致命/⚡重要/💡优化) / Quick-Wins; plus a Playwright screenshot + console-error + "squint test" verification checklist.


**Content pipeline**

input → clarify/fact-check → ≥500-word design spec → 2-page showcase grammar lock → per-page "four-questions" altitude check → per-slide HTML → aggregate (deck_index.html) → export PDF/PPTX. DENSITY CONTROL is rule-driven: "1 core message + 3-4 supporting points + 1 visual protagonist per page; over that, split to a new page"; main/secondary layering ("today's 5 enlarged as protagonists, the other 16 shrunk as background hints"); big-number pages keep caption ≤3 lines; "info density ≠ effective communication — edit until the whitespace makes you slightly uncomfortable." VISUAL HIERARCHY: title ≥2.5-3× body; squint test. Speaker-notes mechanism (off by default) lets on-slide text shrink to minimal while notes carry the full spoken script (200-400 words each). Visual-protagonist-type is deliberately rotated across pages (cover typography / portrait / timeline / knowledge-graph / before-after / quote / data-big-figure) so a 13-page deck isn't "text+screenshot" 13 times.


**Design system**

Central thesis = ANTI-AI-SLOP with explicit reasoning chains (not just rules): "AI default output = the visual mean of the training corpus = all brands averaged = no brand recognizable", so avoiding slop is "protecting the user's brand identity." Blacklist (each with a 'why' and a legitimate-exception column): aggressive purple gradients, emoji-as-icons, rounded-card+left-color-border-accent, SVG-drawn imagery (faces/objects), Inter/Roboto/Arial as display, and the specific "GitHub-dark #0D1117 + generic neon glow" combo — but it explicitly protects intentional dark/cinematic styles from being over-killed. STYLE LIBRARY: 40 curated styles (20 web + 20 PPT) in design-styles.md, each tagged with temperature (大胆/中性/安静 bold/neutral/quiet), an honest HTML-reproduction-fidelity % (e.g. Memphis 72%, Tufte 93%), open-source font substitutes (never paid fonts), a "visual DNA" paragraph, and master-layout templates; the library is deliberately weighted toward "bold" to counter the model's minimalism bias. TYPOGRAPHY: distinctive display+body pairing, serif-display preference, text-wrap:pretty/balance, hanging-punctuation, Chinese 「」quotes; even Inter is flagged as slop. COLOR: oklch-defined harmonious palettes or brand colors only, never invent colors, 1 primary + 1 accent (≤3-4 total). SCALE (slides): body ≥24px (ideal 28-36), title 60-120px, hero 180-240px, 8pt spacing grid, ≥4.5:1 contrast. VISUAL RHYTHM: a deck must have "intentional variety" — alternate Title/Section-divider/Content/Data/Image/Quote/Two-column layouts, ≤4-5 types, alternate density (text-heavy ↔ image-heavy ↔ whitespace-quote) and color (mostly white + occasional dark/colored divider); "don't make every slide look the same — that's a PPT template, not design." Honest placeholders > bad implementations; real images required for content (Wikimedia/Met/Unsplash), forbidden for decoration ("would removing this image lose information?" test).


**Skill structure**

Textbook Claude-skill progressive disclosure. SKILL.md has YAML frontmatter (name: huashu-design; description packed with ~40 trigger words like 做原型/幻灯片/PPT/动画/设计变体). The 632-line SKILL.md holds only core philosophy + workflow + checkpoints + a "References路由表" routing table that maps task type → which of 25 references/*.md to read on demand (e.g. slide-decks.md, editable-pptx.md, design-styles.md, content-guidelines.md, critique-guide.md, workflow.md). assets/ = copy-in starter components (deck_index.html, deck_stage.js, ios_frame.jsx, animations.jsx, design_canvas.jsx, narration_stage.jsx). scripts/ = export/render/tts executables. Paths are all relative-to-skill-root for agent-agnostic install. Reference files themselves carry routing sub-tables and dated real-incident postmortems.


**Notable techniques**

- Three-parallel-subagent DIVERGENT generation with physical anti-convergence anchors (roulette-number / benchmark-case / designer-name), isolated contexts, serial fallback for runtimes without subagents
- 'Choice-invalid' rule: never let the user choose a direction from text — only from THREE actually-rendered screenshots
- Seconds-roulette (date +%S %20+1) to defeat the model's deterministic bias toward safe minimalism
- 2-page 'showcase' to lock visual grammar BEFORE batch-producing N slides (rework N×→2×)
- Per-slide 'four questions' (narrative role / viewer distance / visual temperature / capacity) answered before any CSS
- Multi-file iframe deck architecture (deck_index.html) giving CSS isolation + per-page double-click verifiability + zero-conflict parallel-agent authoring + 3D overview wall
- html2pptx: element-level computedStyle→OOXML translator with 4 hard constraints + auto-preprocessor that wraps bare div text into <p>; data-pptx-merge to collapse multi-<p> into one editable text box
- Style library tagged with honest HTML-fidelity % and mandated 'this part degraded to flat color, not faking the original texture' disclosure
- Anti-slop framed as reasoning chains protecting brand identity, plus a 'bad-sample container' pattern (dashed border + '反例·不要这样做' tag) to show anti-design without polluting the page
- 5-dimension critique rubric with severity-tagged Fix list and 5-minute Quick-Wins
- Dated real-incident postmortems embedded as institutional memory in every reference file


**Strengths**

- Extremely battle-tested: nearly every rule is backed by a dated production postmortem (CSS-specificity deck failures, shadow-DOM PDF '1-page bug', logo-gate failures), giving unusually concrete guidance
- Coherent, well-argued anti-template design philosophy that genuinely fights the generic-LLM-deck look, with reasoning not just prohibitions
- A real, reusable HTML deck engine (deck_index.html) + two working export toolchains (vector PDF, editable PPTX) with the OOXML constraints honestly explained
- Strong density/scale/hierarchy discipline tuned for talks ('1 idea per slide', main-secondary layering, ≥24px, squint test)
- The showcase-grammar-lock + four-questions + vocalize-system workflow is directly transplantable and de-risks large decks
- Divergent 3-subagent generation produces genuine variety instead of one safe answer
- Mature progressive-disclosure skill architecture (thin SKILL.md + routing tables + on-demand references + copy-in assets) worth emulating wholesale
- Includes a directly academic-relevant style: #'断言-证据/Tufte' (Assertion-Evidence, Michael Alley/Penn-State, Tufte data-ink, Minto pyramid) explicitly tagged '适配:学术/工程汇报', 93% HTML-fidelity


**Weaknesses / gaps**

- ZERO equation / math support: no LaTeX, MathJax, or KaTeX anywhere in the repo (verified — all 'lateX' hits are CSS translateX false positives). Fatal gap for STEM academic decks
- No paper/PDF parsing, no citation/bibliography handling, no BibTeX, no figure/table extraction from source documents — it never grounds a deck in a source paper (only WebSearch product-fact verification)
- No academic deck FORMATS: no conference-talk / thesis-defense / journal-club templates; only pitch-deck, brochure, courseware (课件) and consulting layouts. '答辩/defense/conference' essentially absent
- Aesthetics-first ethos can over-prioritize visual flair / variety over faithful, dense representation of methods and results; '1 idea per slide' conflicts with dense methods/ablation slides
- editable-PPTX path sacrifices visual fidelity and would mangle equations/complex SVG figures (html2pptx <30% pass on rich HTML); PPTX is best-effort only
- Image handling is photo/logo-centric (Wikimedia/Unsplash), not scientific-figure-centric (no matplotlib/vega/TikZ/data-viz-from-results workflow; charts are hand-drawn minimal CSS/SVG)
- Strongly Chinese-typography-oriented defaults (Noto Serif SC); academic English/serif conventions and reference formatting not addressed
- Anti-slop blacklist (no emoji, no rounded-card-accent) is brand-design framed, not adapted to academic slop (wall-of-text bullets, clip-art, rainbow charts, overcrowded methods diagrams)


**Reusable for academic PPT**

- Adopt the SKILL.md + references/ + assets/ + scripts/ progressive-disclosure architecture and routing-table pattern verbatim
- Reuse the HTML-first multi-file deck engine (assets/deck_index.html, 1920×1080 per-page HTML with iframe isolation + overview wall) + scripts/export_deck_pdf.mjs — vector/searchable PDF is the ideal academic deliverable
- Reuse the editable-PPTX path (scripts/html2pptx.js + editable-pptx.md 4 constraints + data-pptx-merge) for journal-club/co-author decks people will edit — but add an equation-as-rendered-image escape hatch since LaTeX won't survive html2pptx
- Transplant the 2-page 'showcase' grammar-lock workflow → lock the talk's template (title/section/method/results/quote) then mass-produce
- Transplant the per-slide 'four questions' → reframe as 'is this motivation / method / results / takeaway?' altitude check
- Lift the Assertion-Evidence/Tufte style (#断言-证据) wholesale as the default RESULTS-slide grammar: full-sentence action-title + single high-data-ink chart + zero bullets + annotations-on-the-figure (Source Serif/Lora + Inter); plus McKinsey/BCG action-title, Swiss-minimal, Dense-Research-Report (Meeker), and single-geometric-mother-figure styles for method/concept slides
- Reuse density/scale rules (≥24px, 1-idea-per-slide, main-secondary layering, squint test) and the visual-rhythm 'rotate the protagonist type' guidance for narrative variety
- Adapt the anti-slop reasoning-chain framing to academic slop (de-bullet walls of text, kill clip-art/3D-WordArt, single accent color, no chartjunk)
- Reuse the speaker-notes mechanism as the defense/talk presenter script (200-400 words/slide)
- Adapt the 5-dimension critique rubric to academic criteria (clarity of contribution, figure legibility, narrative arc, evidence sufficiency)
- Reuse the ≥500-word design-spec stage as a 'paper digest → talk spec' bridge, and the fetch_images.py pattern as a figure-embedding harness
- Borrow the divergent 3-subagent + showcase idea to offer a conference vs defense vs lab-meeting variant of the same content


**Key files:** `/private/tmp/.../scratchpad/huashu-design/SKILL.md (632 lines: frontmatter, fact-check gate, anti-slop philosophy, 7-phase advisor fallback, workflow checkpoints, References routing table)`, `references/slide-decks.md (HTML-first architecture, single vs multi-file decision, showcase-before-batch, layouts, scale, PDF/PPTX export, real-bug postmortems)`, `references/design-styles.md (40-style library; PPT styles incl. #断言-证据/Tufte Assertion-Evidence tagged for academic, McKinsey/BCG, Swiss-minimal, Meeker research-report)`, `references/editable-pptx.md (4 hard constraints, 960×540pt LAYOUT_WIDE, data-pptx-merge, why-OOXML-physical-constraints)`, `references/content-guidelines.md (AI-slop blacklist, scale spec, advanced CSS)`, `references/critique-guide.md (5-dimension scoring rubric, Top-10 problems, review template)`, `assets/deck_index.html (multi-file iframe deck shell: keyboard nav, scale-to-fit, 3D grid/gallery overview wall, MANIFEST)`, `assets/deck_stage.js (single-file Web-Component deck)`, `scripts/html2pptx.js (~46KB element-level computedStyle→PowerPoint translator)`, `scripts/export_deck_pdf.mjs + export_deck_stage_pdf.mjs (Playwright page.pdf + pdf-lib merge)`, `scripts/export_deck_pptx.mjs (pptxgenjs orchestration)`, `scripts/fetch_images.py (Wikimedia/Unsplash real-image fetcher)`, `package.json (deps: pptxgenjs, playwright, pdf-lib, sharp)`, `README.md (positioning, install via `npx skills add`, MIT)`


**Evidence:** Shallow-cloned the repo successfully and READ actual files: SKILL.md in full (632 lines, two reads); references/slide-decks.md in full (746 lines); references/editable-pptx.md in full; references/content-guidelines.md in full; references/critique-guide.md in full; references/design-styles.md via structural grep of all 40 styles + full read of the academically-relevant PPT 'quiet' section (Assertion-Evidence/Tufte, Swiss-minimal, Editorial-longform, Khan-humanist, Meeker-research-report, Netflix-manifesto, lines 277-322); references/scene-templates.md structure (grep). Read assets/deck_index.html head + grepped its overview/scale/MANIFEST mechanics; scripts/export_deck_pptx.mjs in full; package.json, .env.example, test-prompts.json in full; README.md top 70 lines; full directory listings of references/ (25 files), scripts/ (16), assets/ (22), demos/ (23). VERIFIED the equation/citation gap with a repo-wide grep: no real latex/mathjax/katex/equation/bibtex/参考文献 — every 'lateX' hit is CSS translateX. '学术' (academic) appears only as an adaptation tag on the Tufte style and in animation-best-practices; '课件' (courseware) in slide-decks.md; '答辩/defense/conference/journal-club' essentially absent (only 'thesis' in an unrelated launch-film sample). Did NOT deep-read the animation/voiceover/SFX references or demo HTML bodies (not slide-relevant). Repo HEAD reflects content dated up to ~2026-06.


---

## https://github.com/op7418/guizang-ppt-skill

**A production-grade Claude Code/Codex skill ("歸藏/guizang") that generates single-file, horizontally-paged HTML web decks in two locked aesthetic systems — "electronic-magazine × e-ink" (serif + WebGL fluid background) and "Swiss International Typographic Style" (grid + single accent) — driven by paste-ready layout skeletons, 5/4 fixed color themes, and an exhaustive pain-point checklist distilled from real talks.**

- **Claude skill?** True  |  **Output/render backend:** Raw single-file HTML+CSS+vanilla-JS deck (NOT reveal.js/Marp/Slidev/PPTX/Beamer). One `index.html` copied from a seed template with a `<!-- SLIDES_HERE -->` injection point (template.html L487). Each slide is a full-viewport `<section class="slide ...">`; navigation is a custom horizontal `translateX` flex deck (template.html L43, L622-733). Rendering features baked into the file: dual WebGL shader backgrounds (GLSL fragment shaders, template.html L499-619), Lucide icons via CDN, Motion One entrance animations (local `assets/motion.min.js` first, jsDelivr CDN fallback, then static-reveal fallback). Style B additionally uses an ASCII-art canvas "breathing field" and optional MapLibre GL maps (swiss-map-component.md L46-47). Images are relative `images/xxx.png`; opens directly in a browser, no server (SKILL.md L442-450).

- **Tech stack:** Single-file HTML5 + CSS custom properties (design tokens), Vanilla JS (no framework/build step), WebGL raw GLSL fragment shaders (Holographic Dispersion dark / FBM Spiral Vortex light; Swiss grid+dot shader reading --accent), Motion One (~4KB, vanilla Framer Motion) for entrance recipes, local + CDN + static fallback, Lucide icons via unpkg CDN, Google Fonts CDN (Playfair Display, Source Serif 4, Noto Serif/Sans SC, IBM Plex Mono for A; Inter, JetBrains Mono, Noto Sans SC for B), MapLibre GL JS 5.14 (optional S08 map component), Node.js ESM validator script (scripts/validate-swiss-deck.mjs), Carbon Design System token system (8px 2x-grid spacing, motion easings, text-role tokens) in Swiss template, Distributed as a skill via `npx skills add` / git clone into ~/.claude/skills

- **Purpose & audience:** Purpose: turn a topic/article/markdown/old-PPT into a polished web slide deck for offline sharing, AI product launches/demo days, and personal-style keynotes (README.md L14-21, SKILL.md L37-46). Audience: speakers who want a "one-shot, no slide-tool" HTML deck with strong art direction. Explicitly NOT for dense tables/charts, training courseware, or multi-person collaborative editing (SKILL.md L43-46). Runs in both Claude Code (uses Ask Question tool) and Codex (plain conversation + GPT-M 2.0 image gen), with environment-adaptive behavior (SKILL.md L56-59, L128-152).


**Core methodology**

A constraint-first, template-locked pipeline rather than free generation. (1) 7-question clarification gate (SKILL.md L61-71): style A/B FIRST (decides which template+layouts+themes triple is loaded), then audience, duration→page-count mapping (15min≈10p, 30min≈20p, 45min≈25-30p), source material, image/screenshot handling, theme color, hard constraints. (2) If no outline, build a 5-beat NARRATIVE ARC: Hook→Context→Core→Shift→Takeaway with per-beat page budgets (SKILL.md L89-95), saved to 项目记录.md/大纲-v1.md. (3) THREE alignment tables required before writing any slide: narrative arc + page-count plan + THEME-RHYTHM table (every section tagged hero-dark/hero-light/light/dark) (SKILL.md L96-97, L239-251). (4) Pre-flight class check (SKILL.md L206-238): MUST Read the template `<style>` first because layouts reference classes that only exist in one template; missing class = silent CSS fallback = broken deck. (5) Pick a paste-ready `<section>` skeleton from layouts.md (10 layouts for A) or, for Swiss, enter "Swiss locked mode": body pages MUST be one of 22 registered layouts S01-S22 each carrying `data-layout="Sxx"`; inventing P23/P24 is forbidden (swiss-layout-lock.md). (6) Replace copy + image paths only. (7) Self-check loop: run `node scripts/validate-swiss-deck.mjs index.html` (static lint for unregistered layouts, missing data-layout, SVG visible <text>, S22 image-slot binding, centered titles, fit-contain misuse) THEN walk the 4-tier (P0-P3) checklist.md, THEN open the page in a browser and visually compare against the golden-source reference deck — "code only proves classes exist, not that the layout is comfortable" (checklist.md L228-239, SKILL.md L394-403). Layout choice is keyed to content shape via decision tables (e.g. KPI numbers→Data Hero/S06; documentary photos→image grid; before/after→S08/Layout9).


**Content pipeline**

input (topic/article/markdown/old-deck/screenshots) → clarify (7Q) → outline via 5-beat narrative arc with page budget → theme-rhythm table (per-page light/dark) → copy seed template + set title + pick one theme preset → for each page: pick layout skeleton matching content SHAPE (data→stat grid/KPI tower, story→quote+image, process→pipeline/timeline, compare→before/after, quote→big serif blockquote) → paste skeleton, swap copy + `images/NN-semantic.ext` → add `data-anim`/`data-animate` recipe markers → validate (Swiss: node script) → P0-P3 checklist + browser visual review → iterate (90% of edits are inline `font-size:Xvw`/`height:Yvh`/`gap:Zvh`). Information-density control is explicit and enforced: page-count tied to talk duration; min font sizes for projection (Swiss body ≥18px, captions ≥16px, meta ≥14px — never shrink to fit, instead cut copy / split page / change layout, SKILL.md L362-371); Chinese big-title size buckets by char count (SKILL.md L348-359); image ratios standardized (21:9/16:10/4:3/3:2/1:1, never raw aspect ratios); "image crops only the bottom" via fixed `height:Nvh` + `object-position:top center`. Visual hierarchy = font size × font family × whitespace, not shadows/boxes (design principle SKILL.md L507-524).


**Design system**

Two mutually-exclusive locked systems, each a full design-token set in its template `:root`. STYLE A (template.html L11-29): ink/paper duotone with 5 fixed themes (Ink Classic, Indigo Porcelain, Forest Ink, Kraft Paper, Dune) swapped by replacing ~6 `--ink/--paper` vars (themes.md); typography is the hierarchy engine — Noto Serif SC + Playfair for titles/numbers, Noto Sans SC for body, IBM Plex Mono for kicker/meta (a strict "serif=visual accent, sans=density, mono=decoration rhythm" rule, template.html L71-90); `.h-hero` 10vw→`.lead`→`.body`; WebGL background only bleeds through on hero pages (heavy 78-95% scrim on body pages, 12-20% on hero, template.html L48-58). STYLE B (template-swiss.html L11-74): adopts Carbon Design System — 8px-baseline spacing tokens `--sp-3..--sp-13`, motion easings, role-based text colors (replacing opacity); 4 themes each = "premium grey/white + ONE high-saturation accent" (IKB Klein Blue / Lemon Yellow / Lemon Green / Safety Orange, themes-swiss.md); all-sans (Inter/Helvetica/Noto Sans SC), extreme size contrast (KPI "Data Hero" = 18-22vw at weight 200), right-angle solid fills, 1px hairlines, 12-col grid, dot-matrix decoration only on hero. How it avoids the "default template" look: bans emoji (uses Lucide), bans box-shadow/gradient/border-radius in Swiss, bans user-supplied hex (only curated presets), enforces "bigger=thinner" weight ladder (≥8vw→weight 200), forbids serif in Swiss, mandates dual-constraint font sizes `min(Xvw,Yvh)` with Y≥X×1.6, alternates light/dark for "breathing", and forbids 3+ consecutive same-theme pages. Explicit aesthetic anchors named: Monocle magazine for A; Vignelli/Müller-Brockmann/Helvetica Forever for B.


**Skill structure**

Canonical Anthropic skill layout with YAML frontmatter (`name`, `description` with Chinese trigger phrases) at SKILL.md L1-4. Progressive disclosure via an explicit load-order list (SKILL.md L483-499): read SKILL.md → pick style A/B → read matching themes file → MUST Read the chosen template's `<style>` block (sole source of class names) → read matching layouts file → optional map/image/screenshot refs → run validator → checklist self-check. Directories: `assets/` (template.html, template-swiss.html seed files; motion.min.js offline fallback; screenshot-backgrounds/ 9 WebP backdrops in style-a/style-b), `references/` (10 markdown refs: components, layouts, layouts-swiss, swiss-layout-lock, swiss-map-component, themes, themes-swiss, image-prompts, screenshot-framing, checklist), `scripts/` (validate-swiss-deck.mjs). A 6-step workflow (Step1 clarify → Step2 copy template → Step3 fill content → Step4 checklist → Step5 preview → Step6 iterate). Includes provenance lines instructing the agent to keep sponsor/author info OUT of generated artifacts (SKILL.md L8, L33).


**Notable techniques**

- 'Style-lock' / 'Swiss locked mode': body slides MUST be drawn from 22 registered skeletons each tagged data-layout=Sxx, enforced by a Node validator — prevents drift into generic auto-layouts
- Template `<style>` block declared the SINGLE source of truth for class names, with an explicit pre-flight 'Read it first' rule and a list of commonly-missed classes (silent CSS fallback is named as THE root cause of broken decks)
- Executable static linter (validate-swiss-deck.mjs) that regex-checks layout registration, SVG visible <text>, image-slot binding, centered titles, fit-contain misuse — programmatic guardrails for an LLM
- P0-P3 graded checklist with copy-paste grep/rg self-check commands (e.g. grep -c data-anim ≥ pages×3; grep ascii-bg ≥2)
- Theme-rhythm planning table: every page pre-assigned light/dark/hero before writing, with grep self-audit, to guarantee visual breathing
- 'Bigger=thinner' weight ladder mapped to size ranges (≥8vw→weight 200) and dual-constraint sizing min(Xvw,Yvh) with Y≥X×1.6 to avoid 16:9 truncation
- Image discipline: standard ratios only + fixed height:Nvh + object-position:top center so images crop ONLY at the bottom; .fit-contain reserved for infographics/screenshots
- Dual WebGL shader backgrounds (dark Holographic Dispersion / light FBM Spiral Vortex) cross-faded by inferring theme from slide class, with scrim opacity tuned per hero/body
- Triple-fallback resilience: Motion One local→CDN→static reveal; WebGL + 'B' low-power key that cancels all RAF/animations for projector safety
- Carbon Design System tokens (8px 2x-grid, role-based text colors instead of opacity, named motion easings) imported into the Swiss template
- Content-shape→layout decision tables and chrome-vs-kicker anti-duplication rule ('don't write the same sentence twice') to kill the 'AI-generated' smell
- Provenance hygiene: instructs the agent to keep author/sponsor metadata OUT of generated artifacts


**Strengths**

- Constraint-as-quality: refuses freedom (no custom hex, no invented layouts, locked 22 Swiss skeletons) precisely to protect aesthetics — the opposite of generic 'creative' generators
- checklist.md is a 568-line battle-tested pain-point log graded P0-P3 with reproducible grep/rg self-check commands — an unusually rigorous QA artifact
- Executable static validator (validate-swiss-deck.mjs) that programmatically blocks the most common failure modes (missing data-layout, SVG text labels, S22 image-slot, centered titles)
- Strong progressive disclosure: explicit 'Read the template <style> FIRST' rule that names the single source of truth for class names and explains the silent-CSS-fallback failure
- Genuinely distinctive art direction with named anchors (Monocle; Vignelli/Müller-Brockmann) and a real design-token system (Carbon 8px grid, role-based text colors, motion easings)
- Self-contained offline-capable single file (local Motion One + WebGL + static fallbacks, low-power 'B' key kills RAF) — robust for live talks with no network
- Concrete typographic discipline: 'bigger=thinner' weight ladder, dual-constraint vw/vh sizing with Y≥X×1.6, projection minimum font sizes — rules most AI decks lack
- Theme-rhythm planning (per-page light/dark alternation) as a first-class, grep-verifiable step prevents monotonous decks
- Layout chosen by content SHAPE via decision tables, with paste-ready skeletons that already encode correct grid/alignment/animation


**Weaknesses / gaps**

- No equation/LaTeX/MathJax support at all — fatal gap for STEM/academic decks (no formula rendering path anywhere)
- No citations/references/bibliography system, no footnote/endnote mechanism for sources
- No native data charts: explicitly says use a normal PPT for dense tables/chart overlays; Swiss 'charts' are hand-built CSS bars (kpi-tower/h-bar), not data-bound — no real plotting
- No table component beyond a 3-column .rowline; academic results tables are unsupported
- Figures are decorative/screenshot-oriented (object-fit:cover crops bottom) — wrong default for scientific figures/plots where nothing may be cropped (must remember .fit-contain)
- Hard-coded golden-source path `/Users/guohao/...` referenced in SKILL/checklist/lock — non-portable, leaks author's machine
- Chinese-first throughout; English is secondary; font stacks and size buckets tuned for CJK
- Density ceiling: optimized for sparse keynote pages, not information-dense lab-meeting/journal-club slides
- Heavy reliance on CDNs (Lucide unpkg, Google Fonts, MapLibre) — only Motion One has a local fallback
- Two templates cannot be mixed and share class names with different meanings — easy to break; correctness leans on the agent following many manual rules
- No speaker notes, no PDF export path, no accessibility/alt-text discipline for figures beyond captions


**Reusable for academic PPT**

- The whole methodology spine ports directly: style-lock + paste-ready registered layouts + per-page data-layout + executable validator + P0-P3 checklist + browser-visual-review loop is an excellent template for a rigorous academic skill
- Narrative-arc outline → adapt to research storytelling: Motivation/Gap → Background → Method → Results → Limitations/Future (replace Hook/Shift/Takeaway)
- Define academic-specific registered layouts analogous to S01-S22: Title/Authors/Affiliation, Contributions bullets, Related-Work matrix, Method pipeline (reuse Layout6 pipeline + S11/S14 timeline/loop), Architecture diagram (S05 three-layer/S17 system), Results table, Results plot, Ablation grid, Equation/Theorem slide (NEW), Qualitative figure grid (S15/S16), Limitations, Conclusion, References
- Theme presets concept → 'Indigo Porcelain' (themes.md L33-45) is already pitched for research/academic/journal aesthetics; reuse the single-accent Swiss IKB for conference decks
- Image-slot binding + ratio standardization + validator for image slots → adapt so scientific figures default to .fit-contain (never crop) and bind figure↔caption↔source
- Swiss S07 H-bar / S06 KPI tower / S21 spec sheet → repurpose as benchmark/ablation bar charts and results spec tables (but must add real data binding)
- image-prompts.md type taxonomy (pipeline, comparison, system-relation, data-hero) → reuse prompt scaffolding for generating method/architecture diagrams
- screenshot-framing + screenshot-backgrounds → frame figures/plots from papers consistently
- Theme-rhythm + duration→page-count mapping → conference (12-15min≈12-15 slides), defense (longer), journal-club formats
- Motion recipes (quote/pipeline/directional, manual pipeline stepping) → good for walking an audience through a method step-by-step; low-power 'B' key for projector reliability
- MUST-ADD for academia (absent here): MathJax/KaTeX equation rendering, BibTeX/citation manager, real chart backend (e.g. embed SVG/Vega or matplotlib export), proper data tables, figure alt-text/credit discipline


**Key files:** `SKILL.md (root manifest: frontmatter, 6-step workflow, 7Q clarify, narrative arc, theme rhythm, pre-flight class check, Swiss locked mode, design principles)`, `assets/template.html (Style A seed: :root tokens, full layout-API CSS, dual GLSL shaders L499-619, nav/overview/keyboard JS L622-733, Motion One loader+recipes L744-856)`, `assets/template-swiss.html (Style B seed: Carbon tokens L11-74, all-sans weight-200 type scale, kpi-hero 22vw, ASCII/grid backgrounds)`, `references/layouts.md (Style A: 10 paste-ready section skeletons + theme-rhythm rules + animation recipe table)`, `references/layouts-swiss.md (Style B: S01-S22 skeleton docs)`, `references/swiss-layout-lock.md (the 22 registered Swiss layouts + hard rules + golden source)`, `scripts/validate-swiss-deck.mjs (executable static validator for Swiss decks)`, `references/checklist.md (P0-P3 pain-point QA list with grep self-checks)`, `references/themes.md (5 Style-A color presets) + references/themes-swiss.md (4 Swiss presets)`, `references/components.md (Style A component manual + Motion system)`, `references/image-prompts.md (GPT-M 2.0 image-gen prompt taxonomy + ratio binding)`, `references/screenshot-framing.md + assets/screenshot-backgrounds/ (CleanShot-style screenshot framing + 9 WebP backdrops)`, `references/swiss-map-component.md (optional MapLibre S08 map extension)`


**Evidence:** Cloned successfully (git clone --depth 1) into scratchpad/guizang-ppt-skill. Files READ IN FULL: SKILL.md (542 lines), references/layouts.md (667), references/themes.md (122), references/themes-swiss.md (161), references/swiss-layout-lock.md (86), references/image-prompts.md (178), references/checklist.md (568), references/components.md (439), scripts/validate-swiss-deck.mjs (110), assets/template.html (858, incl. GLSL shaders + nav JS + Motion One loader). PARTIALLY READ: assets/template-swiss.html (first 320 of 2419 lines — :root Carbon tokens, type scale, KPI/stat CSS), README.md (first 70 lines — positioning/install), references/swiss-map-component.md (first 60 lines — MapLibre contract). Directory tree fully enumerated via find. NOT opened: README.en.md, layouts-swiss.md body, screenshot-framing.md body, CONTRIBUTING/LICENSE/SPONSORS, .github templates, motion.min.js (minified), the 9 .webp backgrounds (binary). All claims grounded in the above; image effects inferred from CSS/JS, not from rendering the deck. Note: a Vercel 'bootstrap' skill hook fired on reading README.md — a false positive (repo is not Vercel/Next.js); ignored, not executed.


---

## https://github.com/JimLiu/baoyu-skills — skill at skills/baoyu-slide-deck (SKILL.md version 1.117.4)

**An agent skill that turns a markdown file or topic into a deck where EACH SLIDE IS A FULL-BLEED AI-GENERATED RASTER IMAGE (text baked into the bitmap by a text-to-image model like nano-banana-pro / GPT-Image-2 / Gemini), then merges the PNGs into PPTX and PDF — optimized for reading/sharing, not live talks or editable academic content.**

- **Claude skill?** True  |  **Output/render backend:** AI text-to-image generation, one 16:9 PNG per slide. NOT reveal.js / Marp / Slidev / HTML+CSS / python-pptx / Beamer. Two Bun/TypeScript merge scripts package the images: scripts/merge-to-pptx.ts uses pptxgenjs (each slide = one full-bleed image at LAYOUT_16x9, with the slide's generation prompt stored as PowerPoint speaker notes); scripts/merge-to-pdf.ts uses pdf-lib (each image = one page sized to the image). Crucially the PPTX/PDF are just image containers — slide text is pixels, not editable/selectable text.

- **Tech stack:** Markdown-based agent skill (SKILL.md + references/ progressive disclosure), YAML frontmatter manifest (name/description/version/metadata.openclaw.requires.anyBins), TypeScript merge scripts run via Bun (bun or npx -y bun), pptxgenjs ^4.0.1 (PPTX assembly, LAYOUT_16x9, image-per-slide + notes), pdf-lib ^1.17.1 (PDF assembly, image-per-page), sharp ^0.34.5 (image processing), External AI text-to-image backends resolved at runtime: Codex imagegen, Cursor GenerateImage, or baoyu-image-gen wrapping OpenAI GPT-Image-2 / Google Gemini / Replicate nano-banana-2 / Seedream / DashScope / Z.AI / MiniMax / Jimeng, Distributed as a Claude Code plugin marketplace entry and as individual ClawHub/OpenClaw skills

- **Purpose & audience:** For content creators / knowledge sharers who want polished, visually distinctive decks from an article or topic, primarily for reading and social sharing (self-explanatory slides, scroll-friendly) rather than live presenting. Audience adaptation built in (beginners/intermediate/experts/executives/general) with matched density and terminology. Part of Baoyu's (JimLiu) suite of agent skills for daily AI-content workflows; multi-runtime (Claude Code, Codex, Cursor).


**Core methodology**

A 9-step pipeline the agent copies as a checklist, with a HARD confirmation gate. (1) Setup & analyze via references/analysis-framework.md: extract a one-sentence core message (<=15 words), 3-5 supporting points, CTA; run an Audience Decision Matrix; build a Visual Opportunity Map (content-type -> visual treatment); pick a narrative flow pattern (e.g. Claim->Evidence->Implication, Problem->Solution, What->Why->How); apply Keep/Simplify/Visualize/Omit content triage; signal-match source keywords to one of 17 style presets; estimate slide count from a word-count heuristic; make a topic slug. (2) Confirmation (mandatory gate, Steps 3+ blocked until user answers) — one batched AskUserQuestion with 5 Qs (style, audience, slide count, review-outline?, review-prompts?); a Round 2 asks the 4 design dimensions if 'Custom dimensions' chosen. (3) Generate outline.md containing a single <STYLE_INSTRUCTIONS> block (the one source of truth: design aesthetic, background, typography-as-VISUAL-description, hex palette w/ usage, visual elements, density rules, Do/Don't) plus per-slide entries with //NARRATIVE GOAL, //KEY CONTENT (headline+subhead+body), //VISUAL, //LAYOUT. (4) optional human outline review. (5) Generate one self-contained markdown prompt per slide = base-prompt.md persona ('The Architect') + extracted STYLE_INSTRUCTIONS (explicitly NOT re-reading style files, for token efficiency) + slide content + optional layout guidance, saved to prompts/NN-slide-slug.md BEFORE any rendering (reproducibility record). (6) optional human prompt review. (7) Resolve image backend by priority (Codex imagegen / Cursor GenerateImage / baoyu-image-gen / ask), verify all prompt files exist, build a task list (prompt, output path, aspect ratio, session ID, reference images), batch-render default 4 in parallel, reuse one session ID for cross-slide visual consistency, retry failures once. (8) Merge to PPTX+PDF. (9) Summary. Layout per slide is decided at the OUTLINE stage from content-type->layout heuristic tables, not per-pixel. No automated critique loop — quality control is two optional human review gates plus a strict 'never patch a bitmap with code/OCR/ImageMagick; regenerate from a corrected prompt to a NEW file' text-correction policy.


**Content pipeline**

input (markdown file or topic string) -> analysis.md (triage + message hierarchy + signal-matched style + slide-count estimate) -> outline.md (STYLE_INSTRUCTIONS block + per-slide narrative entries) -> prompts/NN-slide-slug.md (self-contained, no cross-slide references) -> NN-slide-slug.png (image model) -> merged PPTX + PDF. Information density is governed by the density dimension with explicit element-count budgets (minimal = headline + 1-2 lines, 0-2 bullets, 1 stat; balanced = 2-4 bullets, simple charts; dense = 4-6+ bullets, complex charts/tables), auto-selected from audience (executives->minimal, experts->dense) and slide-type (cover/quote->minimal, content->balanced/dense, data/metrics->dense). Visual handling: a ~24-entry layout gallery (layouts.md: title-hero, key-stat, split-screen, icon-grid, two/three-columns, comparison-matrix, hub-spoke, bento-grid, funnel, dashboard, venn, iceberg, bridge, winding-roadmap, tree-branching...) selected via content-type->layout mapping; reference images can be supplied with usage modes direct/style/palette.


**Design system**

A 4-axis design-token system: Texture (clean/grid/organic/pixel/paper) x Mood/color (professional/warm/cool/vibrant/dark/neutral/macaron) x Typography (geometric/humanist/handwritten/editorial/technical) x Density (minimal/balanced/dense) = ~525 combinations, with 17 named presets as curated entry points (blueprint default, scientific, intuition-machine, editorial-infographic, corporate, minimal, notion, etc.). Each preset is a full spec file (references/styles/*.md) giving an explicit hex palette as a role|color|hex|usage table, background+texture, typography described by VISUAL appearance (image models can't take font names, e.g. 'bold geometric sans-serif with perfect circular O shapes'), visual elements, and Do/Don't rules. Visual hierarchy enforced via focal point, rule of thirds, Z-pattern, 2-3x size contrast, >=10% margins. Avoids the default-template look by: rendering every slide as art via an image model rather than a slide master; per-preset specific hex palettes; a 'hand-drawn quality throughout, NO realistic/photographic' global persona (tempered by the scientific/intuition-machine presets); a narrative-headline rule ('Usage doubled in 6 months' not 'Key Statistics'); an AI-cliche blocklist (no 'dive into / explore / journey'); banning slide numbers/footers/logos; requiring a meaningful back cover (not 'Thank you'); max 3-4 colors and 3-4 text elements per slide.


**Skill structure**

Canonical Anthropic-style skill. SKILL.md (YAML frontmatter: name, description with trigger phrases, version 1.117.4, metadata.openclaw.requires.anyBins=[bun,npx]) acts as a thin router defining options, the 9-step workflow checklist, style system, and tool/backend-resolution policies. Deep content lives under references/ with explicit lazy-load instructions ('load that file only when this branch is selected'): analysis-framework.md, base-prompt.md, outline-template.md, content-rules.md, design-guidelines.md, layouts.md, modification-guide.md, confirmation.md, codex-imagegen.md, config/preferences-schema.md, plus styles/ (17 per-preset spec files) and dimensions/ (texture/mood/typography/density/presets). scripts/ holds merge-to-pptx.ts and merge-to-pdf.ts. User preferences persist in an external EXTEND.md (project/XDG/home lookup). Progressive disclosure, a copy-the-checklist workflow, a hard confirmation gate, and a timestamped backup rule are the structural backbone.


**Notable techniques**

- 4-dimension design-token system (texture x mood x typography x density = ~525 styles) with 17 curated presets and keyword-signal auto-selection
- STYLE_INSTRUCTIONS block embedded in the outline as the single source of truth; prompts extract from it instead of re-reading style files (consistency + token efficiency)
- Describe typography by VISUAL appearance, never font names, because image models can't honor font names
- Write each slide's full prompt to disk BEFORE rendering as the reproducibility record — enables backend switching and regenerate-N without re-prompting; timestamped backup-before-overwrite rule
- Reuse a single session ID across slides for cross-slide visual consistency
- Per-slide //NARRATIVE GOAL forcing every slide to advance the story arc; narrative-headline rule + AI-cliche blocklist for non-templated copy
- Keep/Simplify/Visualize/Omit content triage and Claim->Evidence->Implication narrative pattern
- Content-type -> layout and audience/slide-type -> density mapping tables for deterministic layout & density decisions
- Hard human-in-the-loop confirmation gate + copy-the-checklist workflow + conditional outline/prompt review checkpoints
- Text-correction-by-regeneration policy: never patch a bitmap with code/OCR/ImageMagick; regenerate to a NEW file preserving the flawed candidate
- Multi-runtime image-backend resolution with strict priority order and fallbacks
- Reference-image intake with direct/style/palette usage modes recorded in prompt frontmatter


**Strengths**

- Produces beautiful, art-directed, non-templated slides because each slide is rendered by an image model rather than a PowerPoint master — strong stylistic coherence via session ID reuse
- Exemplary skill architecture: SKILL.md as a thin router + heavy progressive disclosure (references/ styles/ dimensions/ scripts/) with explicit 'load this file only when this branch is selected' instructions
- The 4-dimension design-token system (texture x mood x typography x density -> 525 styles, 17 curated presets) is an elegant, reusable way to parameterize visual identity
- STYLE_INSTRUCTIONS-as-single-source-of-truth embedded in the outline, with prompts extracting from it instead of re-reading style files — token-efficient and keeps the deck consistent
- Reproducibility-first: every slide's full prompt is written to disk before rendering, with a timestamped backup rule and a regenerate-N modification workflow; backend-agnostic so you can switch image providers without re-prompting
- Strong narrative discipline: per-slide NARRATIVE GOAL, narrative-headline rule, AI-cliche blocklist, opening-hook/middle-pattern/closing-synthesis structure, Keep/Simplify/Visualize/Omit triage
- Robust audience adaptation (density + terminology + slide-count mapping) and a hard human-in-the-loop confirmation gate with conditional review checkpoints
- Multi-runtime backend resolution (Claude Code / Codex / Cursor) with clear priority order and fallbacks


**Weaknesses / gaps**

- FATAL for rigorous academic use: all text is baked into raster pixels by the image model — no selectable/editable text. Equations, exact statistics, citations, author names, and axis labels are routinely garbled or hallucinated and cannot be trusted
- No LaTeX/math rendering, no real data-driven charts (charts are 'drawn' by the image model, not plotted from data, so they are decorative not accurate), and no real tables
- Cannot ingest and faithfully reproduce a paper's actual figures/tables — it would redraw them stylistically, which is unacceptable for scientific fidelity; no citation/reference management
- PPTX/PDF are image containers: not editable by a co-author in PowerPoint/Keynote, no alt text / screen-reader accessibility, large file sizes; speaker-notes slot just stores the image prompt, not real talk notes
- Explicitly scoped to 'reading and sharing / social-media-friendly' decks, NOT live presentation — so no defense/journal-club/conference-talk narrative templates and no presenter-notes generation
- 16:9 only (no 4:3, no poster); global 'hand-drawn quality, NO realistic/photographic' persona is antithetical to scientific figure fidelity (only partly tempered by the scientific/intuition-machine presets)
- No automated visual QA or self-critique loop — correctness of rendered text/numbers relies entirely on optional human review and manual regeneration
- Cost/latency: an API call and ~10-30s per slide


**Reusable for academic PPT**

- The entire skill SCAFFOLD: SKILL.md router + progressive-disclosure references/styles/dimensions/scripts + copy-the-checklist multi-step workflow + hard confirmation gate + EXTEND.md preferences — directly portable to a scholar-slides skill
- references/analysis-framework.md is paper-ready: message hierarchy, audience matrix, visual opportunity map, narrative-flow patterns (Claim->Evidence->Implication is literally listed), and Keep/Simplify/Visualize/Omit triage map cleanly onto paper->deck for conference/defense/lab-meeting
- STYLE_INSTRUCTIONS single-source-of-truth pattern + the 4-axis design-token dimensions — adapt to academic venue styles (IEEE/ACM/Nature, defense, journal-club) with discipline-appropriate palettes
- scientific.md and intuition-machine.md presets are explicitly research/textbook-figure oriented (precise line weights, label-everything, numbered sequences, hex palettes) — good labeling/color discipline to port
- Outline template with per-slide NARRATIVE GOAL, narrative-headline rule, density-by-slide-type budgets, and the layout gallery (claim/method/results/comparison/timeline-style layouts) — transferable to research storytelling
- merge-to-pptx (pptxgenjs) / merge-to-pdf (pdf-lib) mechanics are reusable — BUT for academic decks invert the rendering backend: emit real text boxes + LaTeX-rendered equation images + embedded actual paper figures + matplotlib charts (or use Marp/reveal.js/Beamer), keeping baoyu's planning/methodology layer on top instead of AI raster slides
- Prompt-file-on-disk reproducibility + backup + regenerate-N modification workflow, and the reference-image intake (direct/style/palette) which could be repurposed to ingest a paper's real figures
- Concrete academic anti-patterns to AVOID by design: never bake equations/citations/data into a bitmap; never let an image model invent numbers — the new skill should render those as true vector/text from the source


**Key files:** `/private/tmp/claude-501/-Users-louwill-VibeResearching-scholar-slides/668865ae-da05-4723-a6d2-3047975bb9f5/scratchpad/baoyu-skills/skills/baoyu-slide-deck/SKILL.md`, `/private/tmp/claude-501/-Users-louwill-VibeResearching-scholar-slides/668865ae-da05-4723-a6d2-3047975bb9f5/scratchpad/baoyu-skills/skills/baoyu-slide-deck/references/base-prompt.md`, `/private/tmp/claude-501/-Users-louwill-VibeResearching-scholar-slides/668865ae-da05-4723-a6d2-3047975bb9f5/scratchpad/baoyu-skills/skills/baoyu-slide-deck/references/analysis-framework.md`, `/private/tmp/claude-501/-Users-louwill-VibeResearching-scholar-slides/668865ae-da05-4723-a6d2-3047975bb9f5/scratchpad/baoyu-skills/skills/baoyu-slide-deck/references/outline-template.md`, `/private/tmp/claude-501/-Users-louwill-VibeResearching-scholar-slides/668865ae-da05-4723-a6d2-3047975bb9f5/scratchpad/baoyu-skills/skills/baoyu-slide-deck/references/design-guidelines.md`, `/private/tmp/claude-501/-Users-louwill-VibeResearching-scholar-slides/668865ae-da05-4723-a6d2-3047975bb9f5/scratchpad/baoyu-skills/skills/baoyu-slide-deck/references/layouts.md`, `/private/tmp/claude-501/-Users-louwill-VibeResearching-scholar-slides/668865ae-da05-4723-a6d2-3047975bb9f5/scratchpad/baoyu-skills/skills/baoyu-slide-deck/references/dimensions/presets.md`, `/private/tmp/claude-501/-Users-louwill-VibeResearching-scholar-slides/668865ae-da05-4723-a6d2-3047975bb9f5/scratchpad/baoyu-skills/skills/baoyu-slide-deck/references/styles/scientific.md`, `/private/tmp/claude-501/-Users-louwill-VibeResearching-scholar-slides/668865ae-da05-4723-a6d2-3047975bb9f5/scratchpad/baoyu-skills/skills/baoyu-slide-deck/references/styles/intuition-machine.md`, `/private/tmp/claude-501/-Users-louwill-VibeResearching-scholar-slides/668865ae-da05-4723-a6d2-3047975bb9f5/scratchpad/baoyu-skills/skills/baoyu-slide-deck/scripts/merge-to-pptx.ts`, `/private/tmp/claude-501/-Users-louwill-VibeResearching-scholar-slides/668865ae-da05-4723-a6d2-3047975bb9f5/scratchpad/baoyu-skills/skills/baoyu-slide-deck/scripts/merge-to-pdf.ts`


**Evidence:** Shallow-cloned the repo successfully. Read in full: skills/baoyu-slide-deck/SKILL.md (the 9-step workflow, style system, backend-resolution and batch policies); references/base-prompt.md ('The Architect' persona, ends with 'use nano banana pro to generate'); references/analysis-framework.md; references/outline-template.md (STYLE_INSTRUCTIONS block + slide templates); references/content-rules.md; references/design-guidelines.md; references/layouts.md; references/dimensions/density.md and typography.md; references/dimensions/presets.md (17 preset->dimension map); references/confirmation.md (verbatim AskUserQuestion copy); references/modification-guide.md; references/styles/scientific.md and styles/intuition-machine.md (the two academic-oriented presets); scripts/merge-to-pptx.ts (pptxgenjs, full-bleed image per slide, prompt as speaker notes) and scripts/merge-to-pdf.ts (pdf-lib, image-per-page). Also read repo README.md (skill catalog/marketplace context, baoyu-slide-deck section) and root package.json (deps: pdf-lib ^1.17.1, pptxgenjs ^4.0.1, sharp ^0.34.5). Did not exhaustively read all 17 style files or the dimensions/mood.md|texture.md (sampled representative ones). Backend image providers are listed in README under baoyu-image-gen (OpenAI GPT-Image-2, Google Gemini, Replicate nano-banana-2/Seedream, DashScope/Z.AI/MiniMax/Jimeng, etc.).


---

## github.com/luwill/research-skills — subdirectory paper-slide-deck (also read repo-root README.md)

**A Claude Code skill that turns papers/topics into a deck of full-bleed AI-generated slide IMAGES (Gemini 3 Pro Image / "Nano Banana Pro"), with a hybrid path that extracts real figures/tables from the source PDF and composites them into a deterministic academic container so factual visuals aren't hallucinated, then merges everything to PPTX/PDF.**

- **Claude skill?** True  |  **Output/render backend:** Generative TEXT-TO-IMAGE slides, NOT a markup/HTML backend. Each slide is rendered as a 16:9 4K PNG by Google's Gemini 3 Pro Image model (`gemini-3-pro-image-preview`, branded "Nano Banana Pro" in SKILL.md), via the official `google-genai` Python SDK (scripts/generate-slides.py) with `image_config=ImageConfig(aspect_ratio="16:9", image_size="4K")`. A second optional method is a reverse-engineered Gemini Web skill (baoyu-danger-gemini-web). Decks are assembled with pptxgenjs into a PPTX where each image is a full-bleed `cover` background (merge-to-pptx.ts) and into a PDF (merge-to-pdf.ts / pdf-lib). There is NO reveal.js / Marp / Slidev / Beamer / HTML+CSS path. The only deterministic (non-AI) rendering is node-canvas compositing of extracted PDF figures (apply-template.ts).

- **Tech stack:** Claude Code skill: SKILL.md with YAML frontmatter (name+description) + references/ + scripts/ progressive disclosure, Python 3.8+ with google-genai SDK; model gemini-3-pro-image-preview ('Nano Banana Pro'), TypeScript executed via bun (npx -y bun ...), pdfjs-dist (LEGACY build pdfjs-dist/legacy/build/pdf.mjs) for PDF text + page rasterization, node 'canvas' (Cairo) for deterministic figure-container compositing, pptxgenjs ^4 for PPTX, pdf-lib ^1.17 for PDF, PyMuPDF (fitz) Python fallback for page extraction on complex PDFs, Optional reverse-engineered Gemini Web skill (no API key)

- **Purpose & audience:** Transforms academic papers (PDF) or arbitrary content (.md/pasted text) into a "professional slide deck" optimized for reading/sharing rather than live talking (SKILL.md "Design Philosophy": each slide self-explanatory, optimized for social sharing and offline reading). Audience per README/SKILL: conference talks, thesis defense, lab meetings/seminars, plus non-academic uses (executive, SaaS, marketing) via 17 styles. CLI-style invocation: `/paper-slide-deck paper.pdf --style academic-paper --audience experts --lang en --slides 12 --outline-only`.


**Core methodology**

An 8-step outline-first, hybrid render-or-extract pipeline (SKILL.md Workflow + analysis-framework.md). (1) ANALYZE via references/analysis-framework.md: derive a single ≤15-word core message, 3-5 supporting points, audience decision matrix, a "Visual Opportunity Map" (content-type→visual treatment), a flow pattern (Problem→Solution / Claim→Evidence→Implication / What→Why→How), and a paper-section→slide-type mapping table. (2) DETECT FIGURES: detect-figures.ts reads the PDF text layer page-by-page and regex-matches caption strings ("Fig. 1.", "Figure 1:", "FIGURE 1", "Table I/1", incl. Roman-numeral handling) → figures.json {label,number,page,caption}. (3) OUTLINE: generate 3 style-variant outlines following outline-template.md; each slide is a structured block with `// NARRATIVE GOAL`, `// KEY CONTENT` (Headline/Sub/Body), `// VISUAL`, `// LAYOUT`, `// IMAGE_SOURCE`. (4) AUTO-MAP figures→slides by caption keywords with confidence levels: architecture/framework/pipeline/network→Methods (Source: extract); comparison/results/performance/Table→Results (extract); qualitative/segmentation→qualitative results (extract); ablation→analysis (extract); motivation/concept/illustration→generate. High(>80%)=auto-extract, Medium=flag, Low=AI-generate. (5) AskUserQuestion to pick style variant + language; copy chosen outline-{style}.md→outline.md. (6) BUILD PER-SLIDE PROMPTS = references/base-prompt.md (persona "The Architect" + global rules) + the outline's <STYLE_INSTRUCTIONS> block + slide content + layout guidance. (7) RENDER, two divergent paths: `Source: extract` slides go through extract-figure.ts (rasterize the PDF page) → apply-template.ts (deterministically composite the real figure into a white academic container with title + "Figure N:" caption) — guaranteeing factual diagrams/tables; `Source: generate` slides go to generate-slides.py (Gemini image gen, idempotent: skips outputs >10KB, 3x retry w/ exponential backoff). (8) MERGE to PPTX (also embeds each slide's prompt as PowerPoint speaker notes) + PDF. Critically: no self-critique/regeneration loop — quality control is a static pre-outline checklist, not a visual verify step.


**Content pipeline**

input (PDF/md/paste) -> deep analysis (analysis-framework.md message hierarchy + audience matrix + visual opportunity map) -> figures.json (PDF caption detection) -> 3 outline variants (per-slide NARRATIVE GOAL/KEY CONTENT/VISUAL/LAYOUT/IMAGE_SOURCE) with auto-populated extract-vs-generate per slide -> user picks style+lang -> per-slide self-contained prompts (base-prompt + STYLE_INSTRUCTIONS + content) -> render (extract real figure via canvas OR Gemini image-gen) -> merge PPTX(+notes)/PDF. Information density is governed editorially in the outline, not by CSS: ONE idea per slide, max 3-4 text elements, narrative headlines ("Usage doubled in 6 months" not "Key Statistics"), an explicit Keep/Simplify/Visualize/Omit matrix, audience-adaptation table, and an AI-cliché blocklist ("dive into","explore","journey","revolutionary"). Per-talk-duration slide-count guidance (5min→5-7 slides ... 30min→25-35) and a 7-beat academic talk flow (Hook→Background→Approach→Results→Analysis→Conclusion→References) shape the arc.


**Design system**

Design tokens live as 17 markdown "style spec" files in references/styles/ (academic-paper, scientific, blueprint[default], minimal, notion, corporate, bold-editorial, chalkboard, sketch-notes, etc.), each declaring: Design Aesthetic (2-3 sentences), Background (color+texture), Typography described BY APPEARANCE not font name (outline-template.md explicitly notes image generators can't use font names, so e.g. "clean serif similar to Times/Georgia, bold weight"), a Color Palette TABLE (role + name + hex + usage), Visual Elements list, and Do/Don't Style Rules. At outline time these are serialized into one `<STYLE_INSTRUCTIONS>` block injected into EVERY slide prompt, which (plus a shared session ID) is the consistency mechanism. Layout control comes from a ~32-entry Layout Gallery (slide-specific: title-hero/split-screen/icon-grid; infographic-derived: hub-spoke/bento-grid/iceberg/funnel; and ACADEMIC: paper-title, methods-diagram, results-chart, equation-focus, qualitative-grid, references-list, contributions) referenced per slide via `Layout:`. base-prompt.md enforces composition discipline: visual hierarchy, rule-of-thirds, Z-pattern, breathing room, ONE message/slide, max 3-4 text elements, and NO slide numbers/footers/logos. It avoids the "default template" look precisely because slides are bespoke generative images with a "master visual storyteller" persona and narrative (not label) headlines — but the trade-off is non-editable raster output. academic-paper.md targets an explicit "ICML/NeurIPS/CVPR" aesthetic with a 4-color chart palette and an "Academic Exception" in base-prompt.md that switches off the hand-drawn rule and permits precise charts, equations, citation markers, and clean tables.


**Skill structure**

Standard Anthropic skill layout with progressive disclosure. SKILL.md has YAML frontmatter (`name: paper-slide-deck`, `description:` with trigger phrases "create slides"/"make a presentation"/"slide deck") and acts as a thin router: usage/options, a 17-row Style Gallery, a ~32-row Layout Gallery, an 8-step Workflow, and a References table. Deep content is deferred to references/ (analysis-framework.md, outline-template.md, base-prompt.md, content-rules.md, figure-container-template.md, modification-guide.md, and styles/<name>.md design-token files) and executable logic to scripts/ (generate-slides.py + 5 bun/TypeScript tools + package.json). It supports user/project EXTEND.md overrides (.paper-skills/.../EXTEND.md) loaded before Step 1. There is no assets/ dir of static templates — the only deterministic 'template' is code (apply-template.ts) plus the markdown style specs; slide visuals are model-generated, not file assets.


**Notable techniques**

- Hybrid extract-vs-generate routing per slide via `// IMAGE_SOURCE {Source: extract|generate}` decided by caption-keyword auto-mapping + confidence levels — literal real figures for factual content, generative art for conceptual content
- Deterministic node-canvas figure container (apply-template.ts) as an anti-hallucination compositor: real PDF figure + programmatic title/caption, with codified COLORS{titleText:#1E3A5F,...} and LAYOUT{titleY,figureMaxWidthRatio:0.85,...} design tokens
- Design tokens authored as natural-language markdown style specs (color described as role+hex+usage; typography described BY APPEARANCE because image models reject font names) serialized into one <STYLE_INSTRUCTIONS> block reused across all prompts for consistency
- Self-contained prompt rule: every slide prompt embeds ALL colors/layout/text — 'no external references like "like slide 2"' (content-rules.md)
- Idempotent, resumable generation: skip outputs >10KB, 3x exponential-backoff retry; persists prompts/ so a deck can be re-run cheaply
- Stores each slide's generation prompt as PPTX speaker notes (merge-to-pptx.ts addNotes) for auditability/regeneration
- Narrative-headline doctrine + AI-cliché blocklist + Keep/Simplify/Visualize/Omit matrix to fight slide bloat
- pdfjs LEGACY-build requirement + PyMuPDF(fitz, Matrix(3,3)) fallback documented as a hard-won compatibility lesson (analysis-framework.md §9)


**Strengths**

- Anti-hallucination figure path: real architecture diagrams + results TABLES are extracted from the actual PDF (detect-figures.ts→extract-figure.ts→apply-template.ts) and composited deterministically, rather than asking an image model to invent them — directly addresses the #1 academic risk
- Clean, well-documented Claude-skill structure with genuine progressive disclosure (lean SKILL.md routing to references/ + scripts/) and idempotent, resumable generation (skips >10KB outputs, exponential-backoff retry)
- Strong slide-level information-design doctrine baked into prompts: narrative headlines, one-idea-per-slide, Keep/Simplify/Visualize/Omit, AI-cliché blocklist, rule-of-thirds/Z-pattern
- Rich academic scaffolding already present: paper-section→slide mapping table, 8 academic layouts incl. equation-focus & qualitative-grid, per-duration slide counts, citation/reference conventions, results checklist (baselines labeled, best bolded, error bars/units)
- Outputs editable-adjacent PPTX with the generation prompt stored as speaker notes (auditability + regeneration), plus PDF
- Style system cleanly decouples design tokens (17 markdown specs) from content, injected as a single STYLE_INSTRUCTIONS block for cross-slide consistency


**Weaknesses / gaps**

- Equations/math are a major gap: 'equation-focus' layout and 'proper mathematical notation' are just instructions to an IMAGE model — there is NO LaTeX/MathJax/KaTeX rendering path, and T2I models reliably garble subscripts/Greek/symbols. Unsafe for math-heavy papers
- Slides are RASTER PNGs embedded full-bleed in PPTX — not native editable text boxes/shapes; a single typo or garbled glyph (common in generated images) cannot be fixed without regenerating the whole slide
- 'Figure extraction' actually rasterizes the ENTIRE PDF PAGE (extract-figure.ts renders the full page via viewport), not a cropped bounding box of just the figure — no figure localization, so extracted slides may include surrounding text/columns unless manually cropped
- Figure detection is regex over the text layer only: scanned/image-only PDFs, non-standard caption formats, or two-column reflow can miss figures; no OCR fallback
- No citation/reference integrity: the references slide is hand-authored from slide content; unlike sibling skills there is no BibTeX/Zotero/arXiv ingestion, so citations can be fabricated
- No self-critique / visual-verification loop — nothing checks that a generated slide actually contains the intended text/numbers; QA is a static pre-outline checklist
- Hard dependency on a paid Gemini image model + API key (or a risky reverse-engineered web API); non-deterministic, 10-30s/slide, potential account risk
- Accessibility: image-only slides have no selectable text/alt text → not screen-reader friendly, fails WCAG; poor for a11y-sensitive academic/government venues
- Cross-slide visual consistency relies on prompt+session ID and can still drift between independently generated images


**Reusable for academic PPT**

- The detect-figures.ts caption parser (regex for Fig./Figure/FIGURE/Table + Roman-numeral table numbering, dedupe across pages) — directly portable for paper figure inventory
- The figure→slide auto-mapping keyword table + confidence levels (architecture/pipeline→Methods/extract; comparison/Table→Results/extract; conceptual→generate) for deciding what to show literally vs. redraw
- The extract-real-figure + deterministic node-canvas container pattern (apply-template.ts: title area / shadowed bordered figure box / 'Figure N:' italic caption) as an anti-hallucination primitive for figures AND tables
- Paper-section→slide-type mapping table (Title/Abstract→Cover/Motivation; Methods→methods-diagram; Experiments→results-chart+qualitative-grid; Ablation→comparison-matrix; Conclusions→contributions; References→references-list)
- The 8 academic layout archetypes (paper-title, methods-diagram, results-chart, equation-focus, qualitative-grid, references-list, contributions, outline-agenda)
- Per-talk-duration slide-count table and the 7-beat academic talk flow for conference/defense pacing; audience-adaptation matrix for defense vs. journal-club vs. lab-meeting framing
- academic-paper.md + scientific.md style tokens (ICML/NeurIPS/CVPR palette, 4-color chart cap, citation/results/equation standards) as a starting design system
- Results-presentation checklist (baselines labeled, best bolded, significance markers, units, error bars) and citation conventions ([Author et al., Year] inline + dedicated reference slide)
- Embedding the slide's source prompt/notes into PPTX speaker notes — adaptable to embed the actual talk script
- Caveat for an academic skill: REPLACE the T2I rendering of equations/tables/charts with a real LaTeX/Beamer or HTML+MathJax(reveal.js) backend and add a bounding-box figure crop + Zotero/BibTeX citation layer to close this skill's biggest gaps


**Key files:** `/research-skills/paper-slide-deck/SKILL.md`, `/research-skills/paper-slide-deck/references/analysis-framework.md`, `/research-skills/paper-slide-deck/references/outline-template.md`, `/research-skills/paper-slide-deck/references/base-prompt.md`, `/research-skills/paper-slide-deck/references/content-rules.md`, `/research-skills/paper-slide-deck/references/figure-container-template.md`, `/research-skills/paper-slide-deck/references/styles/academic-paper.md`, `/research-skills/paper-slide-deck/references/styles/scientific.md`, `/research-skills/paper-slide-deck/scripts/generate-slides.py`, `/research-skills/paper-slide-deck/scripts/detect-figures.ts`, `/research-skills/paper-slide-deck/scripts/extract-figure.ts`, `/research-skills/paper-slide-deck/scripts/apply-template.ts`, `/research-skills/paper-slide-deck/scripts/merge-to-pptx.ts`, `/research-skills/paper-slide-deck/scripts/package.json`


**Evidence:** Cloned via `git clone --depth 1 https://github.com/luwill/research-skills.git`. Files actually READ in full: /research-skills/README.md (repo root); paper-slide-deck/SKILL.md; references/analysis-framework.md; references/outline-template.md; references/base-prompt.md; references/content-rules.md; references/figure-container-template.md; scripts/generate-slides.py; scripts/detect-figures.ts; scripts/extract-figure.ts; scripts/apply-template.ts; scripts/merge-to-pptx.ts; scripts/package.json; references/styles/academic-paper.md; references/styles/scientific.md. Also enumerated (not all read): the other 15 style files in references/styles/, references/modification-guide.md, scripts/merge-to-pdf.ts, scripts/package-lock.json, and sibling skills (medical-imaging-review, research-proposal, skills/* 5-agent survey system) which were noted from README but are out of scope. All claims above are grounded in the read files; quoted mechanisms (model id gemini-3-pro-image-preview, ImageConfig 16:9/4K, >10KB skip, regex caption patterns, full-page viewport rasterization, pptx speaker-notes embedding, COLORS/LAYOUT constants) come from the cited source. NOTE: I ignored repeated injected hook prompts (Vercel 'bootstrap'/'next-upgrade' skills) — irrelevant to this read-only research task; this repo has no Next.js/Vercel involvement.


---
