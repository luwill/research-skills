---
name: medical-imaging-review
description: Write peer-review-quality comprehensive reviews for medical imaging AI research (segmentation, detection, classification across CT, MRI, X-ray, ultrasound, pathology). Use this skill whenever the user wants to produce a survey paper, systematic review, literature analysis, or "综述" on deep learning for medical imaging; whenever they mention writing a "review paper" / "literature review" / "系统综述" / "narrative review" / "scoping review" in a medical-AI context; whenever they want a draft suitable for journal submission rather than internal notes; whenever they need help organizing a multi-section method survey with vendor / regulatory / clinical translation coverage. This skill enforces fact-checking, citation integrity, and flagship-review writing voice — NOT a fill-in-the-blank template that invites hallucination. Use it especially when the goal is a publishable manuscript and not just a draft to discuss.
metadata:
  author: louwill
  version: 3.0.0
  prior_version_lessons: "v2.0.0 produced drafts that needed extensive multi-day fact-check revision (coronary-cta-paper case): 17 placeholder DOIs, 30-40 [N] drift errors, fabricated method modules, vendor-style citations, 10-subsection flat method taxonomy, AI-tone hedging throughout. v3.0.0 directly addresses these failure modes."
---

# Medical Imaging AI Literature Review Skill (v3.0.0)

Produce comprehensive reviews that pass first-round peer review on factual grounds, not just structural grounds.

This is **not** a template-filling skill. It is a write-with-verify discipline.

---

## Quick Start

A review project lives in 4 files (3 you write, 1 the skill provides):

```
project_root/
├── PARADIGM.md            # Style spec from 2-3 exemplar reviews (Phase 0)
├── CLAUDE.md              # Project-specific terminology + literature inventory
├── IMPLEMENTATION_PLAN.md # 3-axis outline + per-claim verification checklist
└── manuscript_draft.md    # The actual manuscript
```

Follow the 6-phase workflow in [references/WORKFLOW.md](references/WORKFLOW.md). The phases are: paradigm capture → init → collect-and-verify → 3-axis outline → write-with-per-claim-verification → multi-agent peer review.

---

## Core Principles

### Writing voice — match strength to evidence, not hedge by default

Calibrate language to evidence strength, not to a fixed hedging register.

When ≥2 independent peer-reviewed groups confirm a finding, state it strongly. When evidence is single-source or contested, state it cautiously. When evidence is absent, say so.

**Avoid the LLM tells:**
- "has shown promising results"
- "may suggest"
- "interestingly,"
- "it is worth noting that"
- "in recent years,"
- "demonstrates the effectiveness of"
- "may offer significant advantages"

These phrases are AI-detector top features. Real flagship-review authors don't use them. Strip them.

**Take a position when evidence supports it.** Neutral catalogue is the LLM default and the failure mode to avoid. See [Verdict sentences](#verdict-sentences) below.

### Citations — every claim verified before commit

Every `[N]` citation must satisfy four checks:

1. The cited paper **exists** (DOI / PMID resolves on PubMed or Crossref).
2. The **author list** matches the first-source (especially first and last author).
3. The **numeric claim** in the body sentence (Dice, HR, sample size, etc.) appears in the cited paper's abstract or results section.
4. The **directional claim** in the body sentence (higher/lower, increased/decreased) matches the source's stated direction.

If any check fails, the citation is broken — fix before continuing. See [references/CITATION_INTEGRITY.md](references/CITATION_INTEGRITY.md) for the full protocol.

### Method descriptions — read first, write after

Do **not** fill in a template like `[Author] et al. [ref] proposed [method]... Achieves Dice of X.XX`. That template is a hallucination trap.

Use this discipline instead:

1. **Read** the actual paper (abstract + methods + results). For arXiv, use `read_paper`. For closed-access, use Zotero MCP to access the user's library.
2. **Note** the actual module names, the actual benchmark, the actual numbers, in your own working notes — not in the manuscript yet.
3. **Write** the method description from those notes, citing specific numbers and module names verbatim from the paper.
4. **Verify** by spot-checking 1-2 of the numbers against the paper one more time before moving on.

If you can't access the paper, do not write about its internal architecture or specific performance numbers. Cite it for the contribution-level claim only ("first to apply X to Y") and move on.

### Heading depth — Nature Reviews uses two levels

- **H2** (`##`) for top-level sections (Introduction, Methods, Applications, Discussion, ...).
- **H3** (`###`) for subsections.
- **H4** (`####`) is forbidden in body. Use bold lead-in `**Topic.**` paragraph starters for deeper grouping.
- **Number prefixes** (`1.`, `1.1`, `1.2.3`) are forbidden in section titles. Nature Reviews / Nat Med / Lancet / JACC don't use them in narrative reviews.

### Equations — in a Box, not in body

Display equations (DSC, IoU, clDice, FedAvg, GCN propagation, ...) appear in **Boxes**, not inline in body paragraphs. Textbook formulas can be referenced ("the Dice similarity coefficient — see Box 1") but should not be displayed inline.

If a formula has no methodological insight worth displaying (e.g., FedAvg averaging), describe it in prose instead of showing it.

### Vendor names — only in the regulatory/products table

Vendor names (HeartFlow, Cleerly, Caristo, Keya, Shukun, ...) appear ONLY in the Commercial Products / Regulatory & Validation table. In body text use category descriptors:

- ✗ "HeartFlow's CT-FFR product was validated in NXT, ADVANCE, and PACIFIC..."
- ✓ "The first FDA-cleared CT-FFR product (Table N, row 1) was validated in NXT, ADVANCE, and PACIFIC..."

Reason: scatter-cited vendor names look like marketing copy and undermine the review's authority.

---

## Standard Review Structure

```markdown
# [Title]: <evocative subtitle>

## Key Points
- 4-5 bullets, each 1-3 sentences, expressing the main conclusions.

## Abstract

## Introduction
### Clinical background
### Technical challenge
### Scope and contributions

## Datasets and evaluation metrics
(Table 1: public datasets)
(Box 1: evaluation metrics with equations)

## Methods                              # 3-axis grouping, NOT flat 10-subsection list
### Architectural priors
**CNN-based design.** ... (bold lead-in for sub-grouping)
**Transformer-based design.** ...
**Mamba and state-space design.** ...

### Inductive priors
**Topology-aware design.** ...
**Multi-task design.** ...
**Graph-based design.** ...

### Data regime
**Self-supervised pre-training.** ...
**Foundation models.** ...
**Federated learning.** ...
**Physics-informed models.** ...

(Table 2: representative methods with modality / family / dataset / metric)

## Downstream applications
### [Application 1]
### [Application 2]
### [Application 3]

## Translation to clinical practice
(Table 3: commercial products with regulatory + validation)

## Outstanding challenges

## Future directions

## References
```

Notes:
- No number prefixes on headings.
- §Methods is 3 H3 subsections (the three axes), with bold lead-ins for each method family inside.
- Tables 1, 2, 3 are typically enough. Box 1 (metrics) is typical. Avoid 5+ tables.
- Verdict sentences cluster at the end of §Methods axis subsections and at the end of clinical translation discussions — not after every paragraph.

---

## Verdict Sentences

Each H3 method-axis subsection (Architectural priors / Inductive priors / Data regime) should close with **one verdict sentence** expressing authorial position. Choose the 3-5 most opinionated positions across the whole manuscript — don't put verdicts on every paragraph.

Verdict templates:
- "[Family] is currently the most cost-effective design choice for [problem]."
- "[Family] has yet to demonstrate clear advantage over [alternative] in clinical-grade evaluations."
- "[Family] is best understood as complementary to [alternative], not a replacement."
- "The next [N] years will determine whether [family] becomes the default backbone or remains a research curiosity."

Neutral catalogue is the LLM default and exactly what flagship review editors push back on. Force yourself to take 3-5 positions.

---

## Required Elements

- **Key Points box** (4-5 bullets, 1-3 sentences each) after the title.
- **Tables 1-3**: datasets, methods, commercial products.
- **Box 1**: evaluation metrics with formulas.
- **Figures**: typically 3-5 (overview/taxonomy, representative architectures, workflow, performance landscape).
- **References**: cite only what supports the argument. Quantity is downstream of substance — don't pad to a target count.
- **Verdict sentences**: 3-5 across the whole manuscript, clustered at axis-section ends.

---

## Heading Depth

See [Core Principles ▸ Heading depth](#heading-depth--nature-reviews-uses-two-levels) above. Hard rules:

- Max 2 heading levels in body.
- No number prefixes.
- Use bold lead-in `**Topic.**` for deeper subsubsections.

---

## Equations

See [Core Principles ▸ Equations](#equations--in-a-box-not-in-body) above. All display equations go in Box 1 (or rare additional Boxes for specific protocols). Textbook formulas with no methodological insight should be described in prose, not displayed.

---

## Vendor Names

See [Core Principles ▸ Vendor names](#vendor-names--only-in-the-regulatoryproducts-table) above. Vendor names live in Table 3 only; body text uses category descriptors with table cross-reference.

---

## Citation Style

```markdown
# Data citation
"...achieved Dice of 0.730 on ImageCAS [N]"

# Method citation
"Xu et al. [N] introduced..."

# Multi-citation (max 4 in one bracket — beyond that, regroup the claim)
"Multiple groups demonstrated this effect [N1, N2, N3]"

# Comparative
"While [N1] focused on architecture, [N2] addressed the data side"
```

`[N]` in body must match the bibliography entry [N], and bibliography [N] must be the paper the body sentence is actually attributing the claim to. See [references/CITATION_INTEGRITY.md](references/CITATION_INTEGRITY.md) Rule 3.

---

## Literature Sources

Use all three in combination:

| Source | Best for | Tools |
|---|---|---|
| **ArXiv** | Methodological preprints, ML/AI advances | `mcp__arxiv-mcp-server__search_papers`, `read_paper` |
| **PubMed** | Peer-reviewed clinical / validation studies | `mcp__pubmed-mcp-server__pubmed_search_articles` + WebFetch on PubMed |
| **Zotero** | User's local library (closed-access journals) | `mcp__zotero__zotero_search_items`, `zotero_get_item_fulltext` |
| **Crossref** | DOI verification | WebFetch on `api.crossref.org/works/<DOI>` |

For closed-access journals (Med Image Anal, Eur Radiol, Lancet family) the user's local Zotero library is often the only path. Always check Zotero before assuming a paper is inaccessible.

For MCP server configuration, see [references/MCP_SETUP.md](references/MCP_SETUP.md).

---

## Reference Files

| File | Read when |
|---|---|
| [references/WORKFLOW.md](references/WORKFLOW.md) | Starting a new review or moving between phases |
| [references/PARADIGM.md](references/PARADIGM.md) | Phase 0: capturing exemplar review style spec |
| [references/CITATION_INTEGRITY.md](references/CITATION_INTEGRITY.md) | Phase 2 (collection) and Phase 4 (write) — every citation must follow the 5 rules |
| [references/HALLUCINATION_PATTERNS.md](references/HALLUCINATION_PATTERNS.md) | Phase 4 (write) and Phase 5 (peer review) — checklist of 9 LLM hallucination indicators to self-check against |
| [references/DOMAINS.md](references/DOMAINS.md) | Phase 3 (outline) — 3-axis method groupings per domain |
| [references/TEMPLATES.md](references/TEMPLATES.md) | Phase 1 (init) — CLAUDE.md, IMPLEMENTATION_PLAN.md, table templates |
| [references/QUALITY_CHECKLIST.md](references/QUALITY_CHECKLIST.md) | Before delivering a draft to the user |
| [references/MCP_SETUP.md](references/MCP_SETUP.md) | Setting up arxiv-mcp / pubmedmcp / zotero-mcp |

---

## Related Skills

For revising an existing AI-drafted review (whether your own previous output or someone else's draft), use `ai-review-revision`. That skill is the dedicated tool for fixing draft-quality issues — multi-agent diagnostic, factual reset, structural reset, content polish, submission prep.

This skill (`medical-imaging-review`) is the dedicated tool for producing draft-quality content correctly the first time. They are complementary:

- **medical-imaging-review** = write-side (produce submission-quality first draft)
- **ai-review-revision** = revise-side (rescue a draft that already has quality issues)

If a draft produced by this skill still ends up needing the `ai-review-revision` workflow to land, that's a bug — flag it so this skill can be improved.

---

## Why this skill was rewritten (v3 vs v2)

v2.0.0 produced the `coronary-cta-paper` initial draft. That draft needed extensive multi-day revision before submission-readiness: 17 placeholder DOIs, 30-40 [N] citation drift errors, fabricated method module names with wrong performance numbers, vendor-style citations attributed to peer-reviewed journals, a 10-subsection flat method taxonomy where 3 thematic axes would have served better, AI-tone hedging language throughout.

v3 directly addresses each of these failure modes:

| v2 failure | v3 fix |
|---|---|
| Hedging mandate in Core Principles | Removed; replaced with "match voice to evidence" |
| 80-120 reference count target | Removed; replaced with "cite what supports the argument" |
| Method fill-in template | Removed; replaced with "read-first, write-after" discipline |
| 10-flat method subsection taxonomy | Replaced with 3-axis grouping in DOMAINS.md |
| QA = formal structural check | Replaced with per-claim verification embedded in Phase 4 |
| No DOI / author / direction verification | Added as CITATION_INTEGRITY.md with 5 rules |
| No hallucination self-check | Added as HALLUCINATION_PATTERNS.md (9 patterns) |
| Numbered headings | Banned; max 2 levels, bold lead-in for deeper |
| Vendor names scattered | Confined to Table 3 only |
| Equations inline | Confined to Box 1 only |
| Verdict-free neutral catalogue | Required 3-5 verdict sentences |
| No exemplar paradigm capture | Added Phase 0 PARADIGM.md |
