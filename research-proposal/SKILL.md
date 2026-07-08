---
name: research-proposal
description: >
  Use when the user asks to write or draft a PhD / doctoral research proposal,
  research plan, 研究计划书, or 开题报告 — a forward-looking plan of background,
  gap, research questions, methodology, timeline, and significance, in English or
  Chinese. Triggers: "write a research proposal", "PhD proposal", "doctoral
  proposal", "研究计划书", "开题报告", "写博士研究计划". Not for backward-looking
  literature reviews / 综述 / surveys (use medical-imaging-review), nor grant
  forms bound to a funder's own template (国自然/NSF).
metadata:
  author: user
  version: "2.0.0"
allowed-tools:
  - WebSearch
  - WebFetch
  - Read
  - Write
  - Edit
  - AskUserQuestion
  - Glob
  - Grep
  - mcp__zotero__zotero_search_items
  - mcp__zotero__zotero_get_item_metadata
  - mcp__zotero__zotero_get_item_fulltext
  - mcp__zotero__zotero_get_annotations
  - mcp__zotero__zotero_get_notes
  - mcp__zotero__zotero_search_notes
  - mcp__zotero__zotero_semantic_search
  - mcp__zotero__zotero_advanced_search
---

# Research Proposal Generator

Generate a forward-looking academic research proposal — a plan for research not yet done — following flagship academic writing conventions, in English or Chinese.

This skill produces the **first draft correctly**, not a template to be fixed later. Its single most important discipline is citation integrity: a proposal with a fabricated reference is an academic-integrity problem, not a style problem. Read [references/CITATION_INTEGRITY.md](references/CITATION_INTEGRITY.md) before Phase 2.

## Core Principles

**Prose first.** Proposals read as flowing, connected paragraphs — not bulleted lists. Reserve lists for a focused set of research questions/objectives (2–4 items) and timeline milestones. Never enumerate contributions, methodology, background, or significance as bullets; narrate them. Full rules and examples: [references/WRITING_STYLE_GUIDE.md](references/WRITING_STYLE_GUIDE.md).

**Every citation verified before it is committed.** Reference count follows the argument, never a quota — there is no minimum. A PhD proposal typically cites 25–50 sources (humanities often more); a tightly argued 25 beats a padded 45. Every reference must exist (DOI/PMID/arXiv resolves, or Zotero metadata), with author and year matching the source, before it enters the proposal. Unverifiable references are flagged `[UNVERIFIED]` and disclosed — never fabricated. See [references/CITATION_INTEGRITY.md](references/CITATION_INTEGRITY.md).

**Write with verification, not one-shot.** Draft section by section; verify each section's citations before moving to the next (Phase 4). Do not generate a full multi-section proposal with dozens of citations in a single pass — that is the structural cause of hallucinated references.

**Hedge to the evidence.** Use tentative language ("aims to", "may", "is expected to") for proposed work and uncertain claims; state well-established facts plainly. Do not over-claim ("will prove", "revolutionize").

**Avoid the LLM tells.** These phrases are AI-detector signatures — strip them: "Over the past decade, X has emerged as…", "In recent years,", "It is worth noting that", "plays a crucial/pivotal role", "has garnered significant attention", "delves into", "a testament to". Write specific openings grounded in the actual field instead of generic scene-setting.

## Scenario Routing

The default structure below targets **PhD/doctoral proposals and academic research plans** (Abstract → Introduction → Literature Review → Methodology → Timeline → Significance). Confirm the scenario in Phase 1 and adapt:

| Request | Structure |
|---|---|
| PhD/doctoral proposal, research plan, 研究计划书 | Default structure (this skill) |
| 开题报告 (thesis proposal / defense) | Default structure, but weight Literature Review and feasibility/existing-basis more heavily; keep methodology concrete |
| Humanities dissertation proposal | Default + a **Chapter Outline** section (see [references/DOMAIN_TEMPLATES.md](references/DOMAIN_TEMPLATES.md)) |
| 基金申请书 / 国自然 / NSF grant | **Different structure** (立项依据 / 研究内容与目标 / 研究方案与可行性 / 研究基础与工作条件 / 经费预算). Tell the user the default 5-section template is not a grant form; adapt headings to the funder's required template and confirm with the user before writing |

---

## Phase 1: Requirements Gathering

Use `AskUserQuestion` to collect:

- **Research topic / question** — core problem to investigate.
- **Scenario** — PhD proposal / 开题报告 / research plan / grant (routes structure, see above).
- **Academic domain** — STEM (and whether computational/ML — see [references/DOMAIN_TEMPLATES.md](references/DOMAIN_TEMPLATES.md)), Humanities, or Social Sciences.
- **Output language** — English or 中文.
- **Target word count** — default ~3,000 words; range 2,000–4,000 (humanities may extend to ~10,000).
- **Optional** — target institution/supervisor; existing materials or a Zotero library to draw on.

If the topic is too vague to scope a methodology, ask focused clarifying questions before proceeding.

---

## Phase 2: Literature Collection (with verification gate)

Read [references/LITERATURE_WORKFLOW.md](references/LITERATURE_WORKFLOW.md) for search strategy and organization.

**Tool portability.** Confirm which tools are available before using tool-specific names. Prefer the user's Zotero library (via the `mcp__zotero__*` tools) for closed-access papers; use `WebSearch` for landscape/trends and `WebFetch` to open DOI / PubMed / arXiv pages and confirm metadata. If a Zotero/arXiv/PubMed MCP is not connected, fall back to `WebSearch` + `WebFetch`. Remind the user to add relevant closed-access papers to Zotero.

Sources by role: `WebSearch` for trends, reviews, and terminology; `WebFetch` on arXiv / PubMed / publisher pages for open-access primary sources and metadata; Zotero MCP for the user's own library, annotations, and notes.

Organize candidates by role: background/context, current state-of-the-art, gap-identifying, methodology, and related work.

### Verification gate (do not skip)

Before any source is eligible to be cited:

1. Verify each candidate's **existence, first author, and year** against a first source (DOI/PMID/arXiv page, or Zotero metadata) — Rules 1, 2, 5 of [references/CITATION_INTEGRITY.md](references/CITATION_INTEGRITY.md).
2. Only take specific findings/numbers from sources whose full text or abstract you actually accessed. Do not write internal results for a paper you could not open.
3. Present the **verified candidate list** (title, author, year, source/DOI) to the user for a quick sanity check before outlining.

Anything that cannot be verified does not enter the reference pool; if the user insists on a half-remembered source, flag it `[UNVERIFIED]`.

---

## Phase 3: Outline Generation

Read [references/STRUCTURE_GUIDE.md](references/STRUCTURE_GUIDE.md) and [references/DOMAIN_TEMPLATES.md](references/DOMAIN_TEMPLATES.md) for section-by-section and domain guidance.

### Standard Outline (default scenario)

```markdown
# [Research Title]

## Abstract (150-300 words, 5-10%) — background, questions, methodology overview, significance
## 1. Introduction (500-800 words, 15-20%) — background, problem, questions/objectives, scope
## 2. Literature Review (500-1000 words, 20-25%) — framework, current state, gap, positioning
## 3. Methodology (500-800 words, 20-25%) — design, data collection, analysis, validity/limitations
## 4. Timeline (200-300 words, 5-10%) — phases, milestones, optional Gantt
## 5. Significance and Expected Contributions (200-400 words, 10-15%) — theoretical, practical, broader impact
## References — cite what the argument needs (see CITATION_INTEGRITY.md); no minimum, no padding
```

Add a **Chapter Outline** section for humanities proposals. Do NOT include appendices — integrate essential content into the body.

### Approval gate (RED LINE)

**Present the outline and wait for explicit user approval before Phase 4. Do not start writing content on an unapproved outline.**

Ask whether the structure, section emphasis, and scope are acceptable, and whether to add/remove/modify sections.

**If the user says "you decide" / "你看着办" / defers:** state the assumptions you are locking in (scenario, domain, section set, target length, language), present the concrete outline once more as the decision, and proceed only after that — treat silence-plus-deferral as approval of *that stated* outline, but still surface the assumptions so the user can veto.

---

## Phase 4: Content Writing (write-with-verify)

Load the scaffold as the writing skeleton and fill it section by section:

- English → [assets/proposal_scaffold_en.md](assets/proposal_scaffold_en.md)
- 中文 → [assets/proposal_scaffold_zh.md](assets/proposal_scaffold_zh.md)

Read [references/WRITING_STYLE_GUIDE.md](references/WRITING_STYLE_GUIDE.md) and apply it. Key hard rules from it: prose over lists; hedge to evidence; PEEL paragraphs (point → evidence+citation → explanation → link); define abbreviations on first use ("coronary CT angiography (CCTA)"); integrate citations into sentences.

**Write-with-verify loop — repeat per section:**

1. Draft the section as connected prose, placing `(Author, Year)` citations only from the Phase 2 verified pool.
2. Immediately verify that section's citations: each in-text `(Author, Year)` has a matching References entry (Rule 3), and every directional/quantitative claim matches its source (Rule 4). See [references/CITATION_INTEGRITY.md](references/CITATION_INTEGRITY.md).
3. Self-check against the LLM tells (Core Principles) and the hallucination red flags in CITATION_INTEGRITY.md.
4. Fix any failure in place before starting the next section. Do not accumulate unverified citations across sections.

**Citation style by domain:** STEM/Social Sciences → APA (Author, Year); Humanities → MLA or Chicago; 中文 → GB/T 7714. Keep one style consistent throughout.

**Figures:** suggest 3–5 figures at appropriate locations (not in the Abstract), each with a title, content description, and style note. Format and placement guidance is in [references/WRITING_STYLE_GUIDE.md](references/WRITING_STYLE_GUIDE.md).

**中文 output:** 规范学术语体；hedging（"本研究旨在探讨…" 而非 "本研究将证明…"）；参考文献遵循 GB/T 7714。

---

## Phase 5: Output and Review

Save as `proposal_{topic_slug}_{YYYY-MM-DD}.md` in the user's working directory.

Verify against [references/QUALITY_CHECKLIST.md](references/QUALITY_CHECKLIST.md). Before delivering, the **citation gate** must pass:

- `grep -nE "xxx|XXXX|\[TBD\]|\[UNVERIFIED\]|10\.xxxx|\[.*占位.*\]"` returns 0 hits — or every remaining `[UNVERIFIED]` has been explicitly disclosed to the user and never presented as confirmed.
- Every in-text `(Author, Year)` reconciles with the References list (no orphans either direction).
- At least 20% of references, and every quantitative/directional claim, spot-checked against sources.
- No placeholder `[brackets]` or "TBD" left in the body.

Offer format conversion:

```bash
pandoc proposal.md -o proposal.docx        # Word
pandoc proposal.md -o proposal.pdf         # PDF (needs LaTeX)
```

---

## Reference Files

| File | Read when |
|------|-----------|
| [references/CITATION_INTEGRITY.md](references/CITATION_INTEGRITY.md) | **Before Phase 2 and throughout Phase 4/5** — the 5 citation rules; non-negotiable |
| [references/STRUCTURE_GUIDE.md](references/STRUCTURE_GUIDE.md) | Phase 3 — section-by-section writing guide |
| [references/DOMAIN_TEMPLATES.md](references/DOMAIN_TEMPLATES.md) | Phase 1/3 — STEM (incl. computational/ML), humanities, social sciences differences |
| [references/WRITING_STYLE_GUIDE.md](references/WRITING_STYLE_GUIDE.md) | Phase 4 — academic writing style, hedging, transitions, figures |
| [references/QUALITY_CHECKLIST.md](references/QUALITY_CHECKLIST.md) | Phase 5 — final verification before delivery |
| [references/LITERATURE_WORKFLOW.md](references/LITERATURE_WORKFLOW.md) | Phase 2 — literature collection workflow |
| [assets/proposal_scaffold_en.md](assets/proposal_scaffold_en.md) | Phase 4 — English writing skeleton |
| [assets/proposal_scaffold_zh.md](assets/proposal_scaffold_zh.md) | Phase 4 — Chinese writing skeleton |

---

## Workflow Summary

Phase 1 Requirements (interactive) → Phase 2 Literature + verification gate → Phase 3 Outline + **approval red line** → Phase 4 Content, section-by-section **write-with-verify** → Phase 5 Output + citation gate + checklist.

---

## Error Handling

- **No Zotero results / MCP unavailable** — inform the user, fall back to `WebSearch` + `WebFetch` on open-access sources, suggest adding papers to Zotero and retrying.
- **A reference cannot be verified / looks fabricated** — do not write it into the References list. Flag `[UNVERIFIED]` inline and tell the user; never invent a DOI or author list to complete it.
- **Topic too vague** — ask clarifying questions; narrow scope; offer well-formed research-question examples.
- **Over the word limit** — prioritize Introduction and Methodology; condense the literature review to the load-bearing citations; offer an expanded version as a separate file.

---

## Version Notes

v2.0.0 was rewritten after diagnosis found the v1.0.0 skill generated many references with **zero authenticity guardrails**, a one-shot generation step, a hard "minimum 40 references" gate that incentivized padding, and internally contradictory numbers.

| Earlier failure (v1.0.0) | Current fix (v2.0.0) |
|---|---|
| No citation verification anywhere | Added [CITATION_INTEGRITY.md](references/CITATION_INTEGRITY.md) with 5 rules; gates in Phase 2/4/5 |
| Hard "minimum 40 references" | Removed; "cite what the argument needs; typically 25–50; never pad" |
| Phase 4 = one-shot generation | Replaced with section-by-section write-with-verify |
| No literature-verification gate before writing | Phase 2 verify-before-cite + user sanity check |
| Contradictory numbers (40/30-50 refs, 60%/80% recency) | Unified: no minimum; ~60% recent where the field moves fast |
| Scaffolds never loaded by the workflow | Phase 4 explicitly loads `assets/proposal_scaffold_{en,zh}.md` |
| AI-tell sentence templates provided as models | Removed; added "avoid the LLM tells" guidance |
| Outline approval implicit | Made a red line, with "你看着办" handling |
| `Task` tool declared but unused; `WebFetch` missing | Removed `Task`; added `WebFetch` |
| Coronary-imaging examples throughout | Diluted with cross-domain examples; added computational/ML sub-template |
| Bulleted contributions in scaffolds vs prose-first rule | Scaffolds now demonstrate prose contributions/implications |
