---
name: research-proposal
description: >
  Use when the user asks to write or draft a PhD / doctoral research proposal,
  research plan, 研究计划书, or 开题报告 — a forward-looking plan of background,
  gap, research questions, methodology, timeline, and significance, in English or
  Chinese. Triggers: "write a research proposal", "PhD proposal", "doctoral
  proposal", "研究计划书", "开题报告", "写博士研究计划". The literature-corpus half
  of 开题报告 (exhaustive, reproducible retrieval with recall evidence) belongs
  to the lit-search skill; this skill consumes its outputs (dois.md /
  references.md — the default formatted list; references.bib only when lit-search ran
  with --bibtex). Not for backward-looking literature reviews / 综述 / surveys
  (use medical-imaging-review). For grant applications (国自然/NSF) it drafts and
  structures the CONTENT (立项依据/研究内容/…) but never fills a funder's own
  form system or budget tables.
metadata:
  author: user
  version: "2.0.1"
allowed-tools:
  - WebSearch
  - WebFetch
  - Read
  - Write
  - Edit
  - AskUserQuestion
  - Glob
  - Grep
  - Bash
  - mcp__zotero__zotero_search_items
  - mcp__zotero__zotero_get_item_metadata
  - mcp__zotero__zotero_get_item_fulltext
  - mcp__zotero__zotero_get_annotations
  - mcp__zotero__zotero_get_notes
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

**Avoid the LLM tells.** These phrases are AI-detector signatures — strip them: "Over the past decade, X has emerged as…", "In recent years,", "It is worth noting that", "plays a crucial/pivotal role", "has garnered significant attention", "delves into", "a testament to"; 中文: "近年来，随着……的飞速发展", "……日益受到广泛关注". Write specific openings grounded in the actual field instead of generic scene-setting.

## Scenario Routing

The default structure below targets **PhD/doctoral proposals and academic research plans** (Abstract → Introduction → Literature Review → Methodology → Timeline → Significance). Confirm the scenario in Phase 1 and adapt:

| Request | Structure |
|---|---|
| PhD/doctoral proposal, research plan, 研究计划书 | Default structure (this skill) |
| 开题报告 (thesis proposal / defense) | Default structure, but weight Literature Review more heavily and open Methodology with a **研究基础/可行性分析 (existing basis & feasibility)** subsection — the reviewer's prior work, preliminary results, and access to data/compute; keep methodology concrete |
| Humanities dissertation proposal | Default + a **Chapter Outline** section (see [references/DOMAIN_TEMPLATES.md](references/DOMAIN_TEMPLATES.md)) |
| 基金申请书 / 国自然 / NSF grant | **Different structure** (立项依据 / 研究内容与目标 / 研究方案与可行性 / 研究基础与工作条件). This skill drafts the *content* adapted to the funder's required sections — it does **not** fill the funder's own form system, budget tables, or NSF-specific fields (Intellectual Merit / Broader Impacts). Tell the user the default 5-section template is not a grant form; adapt headings to the funder's required template and confirm with the user before writing |

---

## Phase 1: Requirements Gathering

Use `AskUserQuestion` to collect:

- **Research topic / question** — core problem to investigate.
- **Scenario** — PhD proposal / 开题报告 / research plan / grant (routes structure, see above).
- **Academic domain** — STEM (and whether computational/ML — see [references/DOMAIN_TEMPLATES.md](references/DOMAIN_TEMPLATES.md)), Humanities, or Social Sciences.
- **Output language** — English or 中文.
- **Target length** — PhD proposal / research plan: default ~3,000 words, range 2,000–4,000 (humanities may extend to ~10,000). **开题报告 is set by the institution, not by this default** — ask for the school's template and required length (常见 10,000–30,000 字，文献综述部分往往占一半); Chinese length counts characters (`wc -m`), not whitespace words. If the user has no requirement, default 中文开题报告 to ~15,000 字 and state it as a locked assumption.
- **Optional** — target institution/supervisor; existing materials or a Zotero library to draw on.

If the topic is too vague to scope a methodology, ask focused clarifying questions before proceeding. **Headless run** (no interactive user, e.g. called from another agent's pipeline): extract the requirements above from the calling prompt instead of asking, and record them as **locked assumptions** in the outline the way Phase 3 does — never invent a requirement the prompt did not state.

---

## Phase 2: Literature Collection (with verification gate)

Read [references/LITERATURE_WORKFLOW.md](references/LITERATURE_WORKFLOW.md) for search strategy and organization.

**Tool portability.** Confirm which tools are available before using tool-specific names. Prefer the user's Zotero library (via the `mcp__zotero__*` tools) for closed-access papers; use `WebSearch` for landscape/trends and `WebFetch` to open DOI / PubMed / arXiv pages and confirm metadata. If a Zotero/arXiv/PubMed MCP is not connected, fall back to `WebSearch` + `WebFetch`. Remind the user to add relevant closed-access papers to Zotero.

Sources by role: `WebSearch` for trends, reviews, and terminology; `WebFetch` on arXiv / PubMed / publisher pages for open-access primary sources and metadata; Zotero MCP for the user's own library, annotations, and notes. For journal articles the **Crossref REST API** (`WebFetch https://api.crossref.org/works/<DOI>`) is the highest-signal existence+metadata check — it returns clean JSON (title / first author / year / venue), more reliable than parsing a publisher HTML page.

Organize candidates by role: background/context, current state-of-the-art, gap-identifying, methodology, and related work.

### Verification gate (do not skip)

Before any source is eligible to be cited:

1. Verify each candidate's **existence, first author, and year** against a first source (DOI/PMID/arXiv page, or Zotero metadata) — Rules 1, 2, 5 of [references/CITATION_INTEGRITY.md](references/CITATION_INTEGRITY.md).
2. Only take specific findings/numbers from sources whose full text or abstract you actually accessed. Do not write internal results for a paper you could not open.
3. Present the **verified candidate list** (title, author, year, source/DOI) to the user for a quick sanity check before outlining.

Anything that cannot be verified does not enter the reference pool; if the user insists on a half-remembered source, flag it `[UNVERIFIED]`.

**Non-interactive / headless runs.** If the skill is invoked without an interactive user (a background agent or pipeline), do not deadlock on step 3: record the verified candidate list inline in the deliverable (or a companion `citation_verification_log.md`) and continue. The recorded list is the audit trail in lieu of a live sanity check.

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

**If there is no interactive user at all** (headless/agent run): record the locked assumptions and the outline inline in the deliverable and treat that recorded outline as approved. This keeps the audit trail without deadlocking on an approval that no one can give.

---

## Phase 4: Content Writing (write-with-verify)

Load the scaffold as the writing skeleton and fill it section by section:

- English → [assets/proposal_scaffold_en.md](assets/proposal_scaffold_en.md)
- 中文 → [assets/proposal_scaffold_zh.md](assets/proposal_scaffold_zh.md)

Read [references/WRITING_STYLE_GUIDE.md](references/WRITING_STYLE_GUIDE.md) and apply it. Key hard rules from it: prose over lists; hedge to evidence; PEEL paragraphs (point → evidence+citation → explanation → link); define abbreviations on first use ("coronary CT angiography (CCTA)"); integrate citations into sentences.

**Write-with-verify loop — repeat per section:**

1. Draft the section as connected prose, placing in-text citations **only from the Phase 2 verified pool**, in the chosen style: `(Author, Year)` for APA/MLA-style, numeric `[N]` for GB/T 7714 顺序编码制 (中文默认).
2. Immediately verify that section's citations: each in-text citation has a matching References entry (Rule 3), and every directional/quantitative claim matches its source (Rule 4). See [references/CITATION_INTEGRITY.md](references/CITATION_INTEGRITY.md).
3. Self-check against the LLM tells (Core Principles) and the hallucination red flags in CITATION_INTEGRITY.md.
4. Fix any failure in place before starting the next section. Do not accumulate unverified citations across sections.

**Citation style by domain:** STEM/Social Sciences → APA (Author, Year); Humanities → MLA or Chicago; 中文 → GB/T 7714. Keep one style consistent throughout.

**Figures:** suggest 3–5 figures at appropriate locations (not in the Abstract), each with a title, content description, and style note. Format and placement guidance is in [references/WRITING_STYLE_GUIDE.md](references/WRITING_STYLE_GUIDE.md).

**中文 output:** 规范学术语体；hedging（"本研究旨在探讨…" 而非 "本研究将证明…"）；参考文献遵循 GB/T 7714。

---

## Phase 5: Output and Review

Save as `proposal_{topic_slug}_{YYYY-MM-DD}.md` in the user's working directory.

Verify against [references/QUALITY_CHECKLIST.md](references/QUALITY_CHECKLIST.md). Before delivering, the **citation gate** must pass. Run the executable gate first and paste its output — it performs every mechanical check below in one pass and names each offending line:

```bash
python3 <skill_dir>/scripts/check_proposal.py proposal_{topic_slug}_{YYYY-MM-DD}.md
# --style auto|apa|numeric (auto: numeric when References entries start with [N])
# --allow-disclosed-flags : every remaining [UNVERIFIED…] has been disclosed → warnings, not failures
# exit 0 = no mechanical findings (not proof the proposal is right); 1 = findings; 2 = bad input
```

It reconciles in-text citations ↔ References both directions (APA `(Smith, 2024)` / `Smith et al. (2024)` keyed by first-author surname + year; GB/T 7714 `[1]` / `[2-4]` ↔ `[N]` entries), runs the placeholder and AI-tell patterns below (same regex, locked by tests), and flags leftover scaffold `[instructions]` while allowing the exempt personalization fields. One text uses one citation style — a mix of `[N]` and author-year fails rather than being half-checked. Chinese narrative author-year (`张伟（2020）提出`) cannot be segmented reliably, so 中文稿 use GB/T 7714 顺序编码制 (the default) for the gate to cover every citation. The bullets below define what each check means and remain the manual fallback:

- `grep -nE "xxx|XXXX|\[TBD\]|\[UNVERIFIED[^]]*\]|10\.xxxx|doi:10\.[a-z]+/x|forthcoming DOI|\[.*占位.*\]"` returns 0 hits — or every remaining `[UNVERIFIED]` has been explicitly disclosed to the user and never presented as confirmed. (This regex is the single canonical version; [references/CITATION_INTEGRITY.md](references/CITATION_INTEGRITY.md) links to it rather than restating a variant.)
- Every in-text citation reconciles with the References list (no orphans either direction).
- At least 20% of references, and every quantitative/directional claim, spot-checked against sources.
- **AI-tell gate**: `grep -nEi "over the past ((few|several|two|three) )?(decades?|years)|in recent years,|it is worth noting|plays a (crucial|pivotal|vital) role|sheds light on|paves the way|ever-evolving|has garnered significant attention|delves into|a testament to|众所周知|近年来，?随着|日益受到(广泛)?关注"` returns 0 hits in the body (see Core Principles; the same patterns are banned in every reference file and scaffold).
- No placeholder `[brackets]` or "TBD" left in the body. `[Figure N Suggestion]` labels may remain. The applicant-specific scaffold fields (`[University/Institution Name]`, `[Your Field]`, `[Month Year]`; 中文 scaffold 表头的 `[所属学科]`、`[大学/研究机构名称]`、`[年月]`) are **not** left as brackets either: fill each from what the user said; if the user never said it, delete that header line and list it under "请你补充 / To add" in your delivery message — a deliverable with `[年月]` in it looks unfinished. The gate prints a WARN (not a FAIL) for any that remain. Also make the header match the scenario: a 硕士开题报告 never keeps the scaffold's 博士研究生 line.

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

## learnings：复盘先于重写

修改 references 或 scaffold 之前先扫 [`learnings/`](learnings/)——v1→v2 的重写
诊断证明这类教训有值但从未沉淀。返工或发现自相矛盾后追加一篇，日期命名。

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

v2.0.1 hardening: the v2.0.0 "AI-tell templates removed" pass had only cleaned WRITING_STYLE_GUIDE — STRUCTURE_GUIDE, DOMAIN_TEMPLATES, and the Chinese scaffold still recommended banned openings; they are now cleaned and the AI-tell grep gate added to Phase 5. 中文 scaffold switched to GB/T 7714 顺序编码制 end-to-end with realistic character counts; `Bash` added to allowed-tools so the citation gate and pandoc conversion are actually executable; 国自然/NSF boundary stated identically in description and routing; Phase 2 now routes corpus-building to the lit-search skill instead of duplicating it.
