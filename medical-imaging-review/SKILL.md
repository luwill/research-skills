---
name: medical-imaging-review
description: Use when the user asks to write a "综述", narrative review, method survey, scoping review, systematic review, meta-analysis, evidence map, or journal-submission review manuscript in a medical imaging AI context — segmentation, detection, classification, diagnosis, prognosis, or clinical translation across CT, MRI, X-ray, ultrasound, pathology, and related modalities. Not for revising an existing AI-drafted review draft (use ai-review-revision) or for original research.
---

# Medical Imaging AI Literature Review Skill (v3.2.0)

Produce comprehensive reviews that pass first-round peer review on factual grounds, not just structural grounds.

This is **not** a template-filling skill. It is a write-with-verify discipline.

---

## Quick Start

First choose the review type. Read [references/REVIEW_TYPES.md](references/REVIEW_TYPES.md) before collecting literature or drafting prose.

Default narrative/method-survey projects live in 4 files:

```
project_root/
├── PARADIGM.md            # Style spec from 2-3 exemplar reviews (Phase 0)
├── CLAUDE.md              # Project-specific terminology + literature inventory
├── IMPLEMENTATION_PLAN.md # 3-axis outline + per-claim verification checklist
└── manuscript_draft.md    # The actual manuscript
```

Scoping and systematic reviews add protocol, search, screening, extraction, and risk-of-bias files; see [references/REVIEW_TYPES.md](references/REVIEW_TYPES.md) and [references/REPORTING_STANDARDS.md](references/REPORTING_STANDARDS.md).

Follow the workflow in [references/WORKFLOW.md](references/WORKFLOW.md). The phases are: review-type routing -> paradigm capture -> init -> collect-and-verify -> outline/taxonomy -> write-with-per-claim-verification -> peer review -> submission prep.

---

## Review Type Routing

Do not let the title outrun the methods.

| If the user asks for... | Route to... | Read |
|---|---|---|
| flagship "综述", narrative synthesis, method survey | Narrative review / method survey | [REVIEW_TYPES.md](references/REVIEW_TYPES.md), [DOMAINS.md](references/DOMAINS.md) |
| evidence map, "what exists", gap mapping | Scoping review | [REVIEW_TYPES.md](references/REVIEW_TYPES.md), [REPORTING_STANDARDS.md](references/REPORTING_STANDARDS.md) |
| systematic review, meta-analysis, diagnostic-accuracy evidence | Systematic review route | [REVIEW_TYPES.md](references/REVIEW_TYPES.md), [REPORTING_STANDARDS.md](references/REPORTING_STANDARDS.md) |

If the manuscript uses the phrase "systematic review", it must contain reproducible search strings, eligibility criteria, screening flow, extraction fields, and risk-of-bias methods. Otherwise, call it a narrative review, method survey, or scoping review.

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

Every `[N]` citation must satisfy these checks (the full 5-rule protocol is in [references/CITATION_INTEGRITY.md](references/CITATION_INTEGRITY.md)):

1. The cited paper **exists** (DOI / PMID resolves on PubMed or Crossref) with **no placeholder DOI**.
2. The **author list** matches the first-source (especially first and last author).
3. The **numeric claim** in the body sentence (Dice, HR, sample size, etc.) appears in the cited paper's abstract or results section.
4. The **directional claim** in the body sentence (higher/lower, increased/decreased) matches the source's stated direction.
5. Clinical claims cite a **peer-reviewed primary source**, not a vendor white paper or regulatory letter.

If any check fails, the citation is broken — fix before continuing. This is a hard gate: even a single broken citation must be fixed before delivery.

### Method descriptions — read first, write after

Do **not** fill in a template like `[Author] et al. [ref] proposed [method]... Achieves Dice of X.XX`. That template is a hallucination trap.

Use this discipline instead:

1. **Read** the actual paper (abstract + methods + results). Use whatever first-source route is available: PubMed/DOI pages, arXiv pages or PDFs, Zotero full text, local PDFs, institutional copies, or journal pages. Confirm available tools before assuming a specific MCP name.
2. **Note** the actual module names, the actual benchmark, the actual numbers, in your own working notes — not in the manuscript yet.
3. **Write** the method description from those notes, citing specific numbers and module names verbatim from the paper.
4. **Verify** by spot-checking 1-2 of the numbers against the paper one more time before moving on.

If you can't access the paper, do not write about its internal architecture or specific performance numbers — and do not assert **priority or novelty** ("first to", "首个", "earliest", "novel"). Priority claims are strong, falsifiable, and frequently wrong; asserting one you haven't verified is a hallucination. Instead, cite it for a neutral, non-priority contribution ("applied X to Y") and, if useful, note the claim is unverified — or leave it out.

### Heading depth — match the target article type

- **H2** (`##`) for top-level sections (Introduction, Methods, Applications, Discussion, ...).
- **H3** (`###`) for subsections.
- In flagship narrative reviews, avoid H4 in body; use bold lead-in `**Topic.**` paragraph starters for deeper grouping.
- In systematic/scoping reviews, method subheadings may follow journal or PRISMA conventions even if that creates a more formal Methods section.
- Avoid number prefixes (`1.`, `1.1`, `1.2.3`) unless the target journal explicitly requires numbered sections.

### Equations — in a Box, not in body

Display equations (DSC, IoU, clDice, FedAvg, GCN propagation, ...) appear in **Boxes**, not inline in body paragraphs. Textbook formulas can be referenced ("the Dice similarity coefficient — see Box 1") but should not be displayed inline.

If a formula has no methodological insight worth displaying (e.g., FedAvg averaging), describe it in prose instead of showing it.

### Vendor names — table-first, sparing in prose

Vendor names (HeartFlow, Cleerly, Caristo, Keya, Shukun, ...) belong primarily in the Commercial Products / Regulatory & Validation table. In body text use category descriptors unless the product name is necessary to define a regulatory fact, trial population, or head-to-head distinction.

- ✗ "HeartFlow's CT-FFR product was validated in NXT, ADVANCE, and PACIFIC..."
- ✓ "The first FDA-cleared CT-FFR product (Table N, row 1) was validated in NXT, ADVANCE, and PACIFIC..."
- ✓ "The table lists HeartFlow, Cleerly, Caristo, and other products with their regulatory status and peer-reviewed validation evidence."

Reason: repeated product names in body text read like marketing copy. Use exact product names when precision matters; cite peer-reviewed evidence for clinical claims.

---

## Default Narrative / Method Survey Structure

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

## Methods                              # 3-axis grouping is the default for method surveys
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
- No number prefixes on headings unless the journal requires them.
- In narrative AI method surveys, §Methods is usually 3 H3 subsections (the three axes), with bold lead-ins for each method family inside.
- In systematic/scoping reviews, use the structure in [references/REVIEW_TYPES.md](references/REVIEW_TYPES.md) instead of forcing the 3-axis method taxonomy.
- Tables 1, 2, 3 are typically enough. Box 1 (metrics) is typical. Avoid 5+ tables.
- Verdict sentences cluster at the end of §Methods axis subsections and at the end of clinical translation discussions — not after every paragraph.

---

## Verdict Sentences

For narrative reviews and method surveys, each major method-axis subsection (Architectural priors / Inductive priors / Data regime) should close with **one verdict sentence** expressing authorial position. Choose the 3-5 most opinionated positions across the whole manuscript — don't put verdicts on every paragraph.

For systematic and scoping reviews, verdicts must be constrained by the protocol and evidence map. Prefer "the included studies show..." over broad field-wide claims unless the search was designed to support the broader claim.

Verdict templates:
- "[Family] is currently the most cost-effective design choice for [problem]."
- "[Family] has yet to demonstrate clear advantage over [alternative] in clinical-grade evaluations."
- "[Family] is best understood as complementary to [alternative], not a replacement."
- "The next [N] years will determine whether [family] becomes the default backbone or remains a research curiosity."

Neutral catalogue is the LLM default and exactly what flagship review editors push back on. Force yourself to take 3-5 positions.

---

## Required Elements

- **Review type declaration** before writing starts.
- **Key Points box** (4-5 bullets, 1-3 sentences each) after the title for narrative/flagship-style manuscripts.
- **Tables 1-3** for narrative/method surveys: datasets, methods, commercial products.
- **Systematic/scoping tables** when applicable: search strategy, study characteristics, extraction variables, risk-of-bias summary.
- **Box 1**: evaluation metrics with formulas when useful; for systematic reviews, move formal methods definitions into Methods if the target journal prefers that.
- **Figures**: typically 3-5 for narrative reviews; systematic/scoping reviews require a PRISMA-style flow diagram.
- **References**: cite only what supports the argument. Quantity is downstream of substance — don't pad to a target count.
- **Verdict sentences**: 3-5 across narrative/method surveys, clustered at axis-section ends.
- **Audit report**: run the bundled `scripts/audit_manuscript.py` before delivery (resolve the path relative to this skill directory). The script is a **triage** tool — it flags likely issues from surface patterns; it does not prove any citation or number is correct. Delivery requires **both** a clean script pass (0 critical/high) **and** a manual source-level spot-check of quantitative and directional claims. A green script alone is not sufficient.

---

## Formatting Quick Reference

Full rationale is in [Core Principles](#core-principles) above; this is the at-a-glance recap.

- **Heading depth** — max 2 body levels (H2/H3); no number prefixes unless journal-required; deeper grouping via bold lead-in `**Topic.**`; systematic/scoping Methods may follow PRISMA/journal conventions. ([details](#heading-depth--match-the-target-article-type))
- **Equations** — display equations (`$$…$$`) live in Box 1 (rarely additional Boxes); textbook formulas with no methodological insight go in prose, not inline. ([details](#equations--in-a-box-not-in-body))
- **Vendor names** — Table 3 by default; sparse body mentions only where regulatory or comparative precision requires them. ([details](#vendor-names--table-first-sparing-in-prose))

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

Use source types in combination. Confirm which tools are available in the current environment before using tool-specific names.

| Source | Best for | Preferred route | Fallback |
|---|---|---|---|
| **ArXiv** | Methodological preprints, ML/AI advances | Available arXiv MCP or paper search | arXiv abstract/PDF URLs |
| **PubMed** | Peer-reviewed clinical / validation studies | PubMed MCP or NCBI/PubMed search | PubMed URL by PMID |
| **Zotero** | User's local library (closed-access journals) | Available Zotero MCP or local Zotero API | user-provided PDFs |
| **Crossref** | DOI verification | Crossref API/WebFetch | DOI resolver and publisher page |
| **Local PDFs** | Exemplar reviews and closed-access papers | PDF text extraction | visual/manual reading |

For closed-access journals (Med Image Anal, Eur Radiol, Lancet family) the user's local Zotero library is often the only path. Always check Zotero before assuming a paper is inaccessible.

For tool-adapter guidance, see [references/MCP_SETUP.md](references/MCP_SETUP.md).

---

## Reference Files

| File | Read when |
|---|---|
| [references/REVIEW_TYPES.md](references/REVIEW_TYPES.md) | Before starting — choose narrative, scoping, systematic, meta-analysis, or umbrella route |
| [references/REPORTING_STANDARDS.md](references/REPORTING_STANDARDS.md) | Whenever the manuscript claims systematic/scoping methods or appraises AI studies |
| [references/WORKFLOW.md](references/WORKFLOW.md) | Starting a new review or moving between phases |
| [references/PARADIGM.md](references/PARADIGM.md) | Phase 0: capturing exemplar review style spec |
| [references/CITATION_INTEGRITY.md](references/CITATION_INTEGRITY.md) | Phase 2 (collection) and Phase 4 (write) — every citation must follow the 5 rules |
| [references/HALLUCINATION_PATTERNS.md](references/HALLUCINATION_PATTERNS.md) | Phase 4 (write) and Phase 5 (peer review) — checklist of 10 LLM hallucination indicators to self-check against |
| [references/DOMAINS.md](references/DOMAINS.md) | Phase 3 (outline) — 3-axis method groupings per domain |
| [references/TEMPLATES.md](references/TEMPLATES.md) | Phase 1 (init) — CLAUDE.md, IMPLEMENTATION_PLAN.md, table templates |
| [references/QUALITY_CHECKLIST.md](references/QUALITY_CHECKLIST.md) | Before delivering a draft to the user |
| [references/MCP_SETUP.md](references/MCP_SETUP.md) | Tool adapters and fallbacks for arXiv / PubMed / Zotero / Crossref |

---

## Related Skills

For revising an existing AI-drafted review (whether your own previous output or someone else's draft), use `ai-review-revision` if it is installed. That skill is the dedicated tool for fixing draft-quality issues — multi-agent diagnostic, factual reset, structural reset, content polish, submission prep.

This skill (`medical-imaging-review`) is the dedicated tool for producing draft-quality content correctly the first time. They are complementary:

- **medical-imaging-review** = write-side (produce submission-quality first draft)
- **ai-review-revision** = revise-side (rescue a draft that already has quality issues)

If a draft produced by this skill still ends up needing the `ai-review-revision` workflow to land, that's a bug — flag it so this skill can be improved.

---

## Version Notes

v3.0.0 was rewritten after the `coronary-cta-paper` draft exposed recurring failure modes: placeholder DOIs, citation drift, fabricated method modules, wrong performance numbers, vendor-style citations, flat method taxonomy, and AI-tone hedging.

v3.1.0 adds review-type routing, reporting-standard guidance, tool portability, softer structure rules, CCTA terminology correction, and an executable manuscript audit script.

v3.2.0 hardens the guardrails: the audit script now detects author↔citation mismatches under standard "Author et al. [N]" typesetting and recognises internationalised reference headings (`## 参考文献`, etc.) so Chinese drafts no longer mis-flag every citation; a fixture test suite (`scripts/tests/`) locks these in. Hard factual errors are now zero-tolerance (not gated behind a "5-or-more" threshold), unverified priority/novelty claims are forbidden, Phase 5 peer review is rewritten as executable sub-agent passes, and DOMAINS.md gains a generative/multimodal (VLM, diffusion, promptable-segmentation) paradigm section.

Consolidated fix ledger (v3.0.0 → v3.2.0):

| Earlier failure | Current fix |
|---|---|
| Hedging mandate; 80-120 reference target | Removed — match voice to evidence; cite what supports the argument |
| Method fill-in template; flat 10-subsection taxonomy | Read-first/write-after discipline; 3-axis grouping default |
| Structural-only QA; no source verification | Per-claim verification (Phase 4) + CITATION_INTEGRITY 5 rules + HALLUCINATION_PATTERNS |
| Systematic label without methods; hard-coded MCP names | Review-type routing (PRISMA/QUADAS/CLAIM/TRIPOD) + tool-adapter fallbacks |
| Numbered headings; scattered vendors; inline equations; neutral catalogue | Bold lead-ins; Table-3-first; Box-1 equations; 3-5 required verdicts; Phase 0 PARADIGM |
| Audit gate ineffective on standard/Chinese citations | Marker-anchored author check + i18n reference headings + fixture tests (v3.2.0) |
