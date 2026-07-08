# Research Skills

A collection of Claude Code skills for academic research workflows.

## Skills

| Skill | Description | Trigger |
|-------|-------------|---------|
| [medical-imaging-review](./medical-imaging-review/) | Write comprehensive literature reviews for medical imaging AI | `/medical-imaging-review`, "review paper", "survey", "综述" |
| [paper-slide-deck](./paper-slide-deck/) | Stylized slide **images** (17 T2I aesthetic styles) for reading & sharing — any content | `/paper-slide-deck content.md --style watercolor` |
| [research-proposal](./research-proposal/) | Generate PhD research proposals with Nature Reviews-style academic writing | `/research-proposal`, "research proposal", "PhD proposal", "研究计划" |
| [scholar-slides](./scholar-slides/) | Fidelity-first academic decks for a live talk — vector equations, extracted figures, grounded citations, editable PPTX | "make slides", "组会 PPT", "答辩幻灯片", a paper PDF / arXiv / DOI |

> **Slides from a paper? Two different tools, on purpose.** Use **scholar-slides** for a faithful,
> editable *live talk* — equations, numbers, tables, and citations stay exact and projector-ready.
> Use **paper-slide-deck** for *stylized visual images* to read or share, where look-and-feel
> matters more than editable precision (its slides are AI-generated images, so math and data are
> not editable and can be garbled — don't use it for a defense or a results-heavy talk).

## Installation

Copy the desired skill folder into your Claude Code skills directory:

```bash
cp -r medical-imaging-review ~/.claude/skills/
cp -r paper-slide-deck       ~/.claude/skills/
cp -r research-proposal      ~/.claude/skills/
cp -r scholar-slides         ~/.claude/skills/
```

`scholar-slides` carries Python + Node toolchains; after copying, provision them once:

```bash
cd ~/.claude/skills/scholar-slides && ./install.sh
```

---

## Medical Imaging Review Skill

A systematic workflow for writing survey papers, systematic reviews, and literature analyses on medical imaging AI topics.

### Features

- **Structured 8-phase write-with-verify workflow** (review-type routing → paradigm capture → init → collect-and-verify → outline/taxonomy → per-claim-verified writing → peer review → submission prep)
- **Review-type routing** — narrative / method survey / scoping / systematic, with matching reporting standards (PRISMA 2020, QUADAS-3, CLAIM 2024, TRIPOD+AI)
- **Citation integrity as a hard gate** — every `[N]` verified for existence, author, number, and direction before commit; an executable audit script (`scripts/audit_manuscript.py`) locked by a fixture test suite
- **Evidence-calibrated writing voice** — match claim strength to evidence; the default-hedging register is explicitly removed as an AI tell
- **Domain-specific 3-axis method taxonomy** across multiple medical imaging domains
- **Quality checklists** and **Zotero-first literature collection** with tool-portable fallbacks

### Supported Domains

- Coronary Artery Analysis (CCTA)
- Lung Imaging (CT/X-ray)
- Brain Imaging (MRI/CT)
- Cardiac Imaging (MRI/CT/Echo)
- Pathology (Whole Slide Images)
- Retinal Imaging (Fundus/OCT)

### Files

| Path | Description |
|------|-------------|
| `SKILL.md` | Main skill definition and quick reference |
| `references/REVIEW_TYPES.md` | Review-type routing (narrative / scoping / systematic / meta-analysis) |
| `references/REPORTING_STANDARDS.md` | PRISMA / QUADAS-3 / CLAIM / TRIPOD+AI standards fit |
| `references/WORKFLOW.md` | Detailed 8-phase workflow guide |
| `references/PARADIGM.md` | Phase 0 exemplar-review style capture |
| `references/CITATION_INTEGRITY.md` | The citation verification protocol (5 rules) |
| `references/HALLUCINATION_PATTERNS.md` | 10 LLM hallucination indicators to self-check |
| `references/TEMPLATES.md` | Project file templates |
| `references/DOMAINS.md` | Domain-specific method categories and datasets |
| `references/MCP_SETUP.md` | ArXiv, PubMed, Zotero MCP configuration and fallbacks |
| `references/QUALITY_CHECKLIST.md` | Pre-submission quality checklist |
| `scripts/audit_manuscript.py` | Executable manuscript audit (with `scripts/tests/` fixtures) |

---

## Paper Slide Deck Skill

Transform any content into stylized, shareable slide **images** (AI-generated), with figure detection and high-resolution page rendering from PDFs.

> Text, math, and data are baked into each image and **not editable** — for a faithful, editable academic talk (组会/答辩/results-heavy) use **scholar-slides** instead.

### Features

- **Caption-based figure detection** from PDF papers (locates the page; human confirmation recommended for dense two-column layouts)
- **Figure-to-slide mapping** with full-page high-res render + template container (not per-figure bbox cropping)
- **17 visual styles** (academic-paper, sketch-notes, minimal, etc.)
- **Gemini API integration** (`gemini-3-pro-image`) for AI slide generation, with a post-generation garbled-text proofread pass
- **PPTX/PDF export** with merge scripts

### Workflow

1. Analyze paper and detect figures/tables
2. Generate outline with auto IMAGE_SOURCE mapping
3. Extract figures from PDF (or AI-generate)
4. Apply academic templates
5. Merge to PPTX/PDF

### Files

| Path | Description |
|------|-------------|
| `SKILL.md` | Main skill definition and workflow |
| `references/` | Analysis framework, templates, style definitions |
| `scripts/` | Python/TypeScript automation scripts |

### Scripts

| Script | Purpose |
|--------|---------|
| `generate-slides.py` | Gemini API image generation |
| `detect-figures.ts` | PDF figure/table detection |
| `extract-figure.ts` | PDF page extraction |
| `apply-template.ts` | Academic figure container template |
| `merge-to-pptx.ts` | PPTX generation |
| `merge-to-pdf.ts` | PDF generation |

---

## Research Proposal Skill

Generate high-quality academic research proposals — PhD applications, research plans, 研究计划书 / 开题报告 — following Nature Reviews-style academic writing conventions.

### Features

- **Structured 5-phase workflow** with a **write-with-verify** content stage: Requirements → Literature (+verification gate) → Outline (approval red line) → Content (section-by-section) → Output
- **Citation-integrity guardrails**: every reference verified to exist (DOI/PMID/arXiv or Zotero) with author and year matching the source — unverifiable entries are flagged, never fabricated
- **Multi-source literature integration**: WebSearch, Zotero MCP, arXiv, PubMed (with tool-portable fallbacks)
- **Bilingual support**: English and Chinese (中文)
- **Domain adaptation**: STEM (incl. computational / ML / AI-for-Science), Humanities, Social Sciences
- **Academic writing style**: prose-based, evidence-calibrated language; reference count follows the argument (no padding quota)

### Workflow

1. Gather requirements (topic, domain, language, word count)
2. Collect literature from multiple sources
3. Generate outline for user approval
4. Write full proposal based on approved outline
5. Output Markdown with quality checklist

### Files

| Path | Description |
|------|-------------|
| `SKILL.md` | Main skill definition and 5-phase workflow |
| `references/STRUCTURE_GUIDE.md` | Section-by-section writing guide |
| `references/DOMAIN_TEMPLATES.md` | STEM vs Humanities differences |
| `references/WRITING_STYLE_GUIDE.md` | Nature Reviews academic writing style |
| `references/CITATION_INTEGRITY.md` | Reference verification protocol (5 rules, author-year style) |
| `references/QUALITY_CHECKLIST.md` | Quality verification checklist |
| `references/LITERATURE_WORKFLOW.md` | Literature collection workflow |
| `assets/proposal_scaffold_en.md` | English template scaffold |
| `assets/proposal_scaffold_zh.md` | Chinese template scaffold |

### Output

- Target: 2,000-4,000 words (default ~3,000)
- References: count follows the argument (typically 25–50; no minimum, no padding), each verified
- 3-5 figure suggestions
- Markdown format (convertible to DOCX/PDF via pandoc)

---

## Scholar Slides Skill

Turn a research paper (or arXiv/DOI link, or a topic) into a **fidelity-first** slide deck — one where every equation, table, number, figure, and citation stays true vector/text and **traceable to the source**, never rasterized by an image model and never fabricated. Where `paper-slide-deck` optimizes visual style via text-to-image, scholar-slides inverts the priority for scholarly work: **source fidelity > polish**, behind an executable integrity gate.

### Features

- **Fidelity-first rendering** — KaTeX vector equations, real `<table>`/OOXML tables, cited figure crops; numbers grounded against the source, no fabrication
- **Integrity QA gate** — number grounding, `[MISSING]`/`[UNVERIFIED]` flags instead of silent fills, PPTX-parity regression, a scoreable aesthetics rubric
- **Two registers** — journal-club (组会, reading-first) and conference (big-room), via a token-based theme system
- **Bilingual** — English default, full 中文 / CJK support
- **Zotero-first citations** with Crossref / arXiv / DOI fallback

### Outputs

- Interactive reveal.js deck (with browser speaker view)
- One-page-per-slide **vector PDF**
- **Editable PPTX** (native text, bullets, tables, speaker notes; equations/figures as flagged images)
- Speaker notes with a bilingual talk-time estimate

### Install & run

```bash
cd ~/.claude/skills/scholar-slides && ./install.sh   # .venv + npm + Chromium, then self-checks
```

Prereqs: **Python 3.11+, Node 18+.** For Chinese decks on Linux: `sudo apt-get install fonts-noto-cjk` (macOS/Windows already have CJK fonts).

### Known limitation

Figure localization is layout-dependent — ~95–100% on single-column / arXiv / Nature-style papers, ~75% on dense IEEE/TPAMI two-column pages. Low-confidence crops are **flagged for you to confirm**, never silently wrong. Stress-tested over 9 cross-layout papers: 0 crashes, 98% of figures localized. See [scholar-slides/README.md](./scholar-slides/README.md) for the full story.

---

## License

MIT License
