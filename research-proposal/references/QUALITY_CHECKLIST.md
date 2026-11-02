# Quality Checklist for Research Proposals

Use this checklist to verify the quality of generated research proposals.

---

## Structure Verification

### Overall Document
- [ ] Title is concise (10-15 words / 中文 15-25 字) and informative
- [ ] All required sections present
- [ ] Sections in logical order
- [ ] Word counts within specified ranges (英文 `wc -w`；中文 `wc -m`，粘贴读数为证)
- [ ] Consistent formatting throughout

### Section Completeness

#### Abstract (150-300 words)
- [ ] Background/context provided
- [ ] Research problem clearly stated
- [ ] Objectives/questions articulated
- [ ] Methodology briefly described
- [ ] Expected significance mentioned
- [ ] No citations in abstract
- [ ] No undefined abbreviations

#### Introduction (500-800 words)
- [ ] Background establishes context
- [ ] Problem statement is specific
- [ ] Research questions/objectives clear
- [ ] Scope defined appropriately
- [ ] Logical flow from broad to specific

#### Literature Review (500-1000 words)
- [ ] Theoretical framework established
- [ ] Current research state summarized
- [ ] Research gap clearly identified
- [ ] Study positioned within literature
- [ ] Synthesis, not just summary
- [ ] Recent sources included (last 5 years)

#### Methodology (500-800 words)
- [ ] Research design justified
- [ ] Data collection methods described
- [ ] Analysis approach explained
- [ ] Limitations acknowledged
- [ ] Ethical considerations addressed (if applicable)

#### Timeline (200-300 words)
- [ ] Major phases identified
- [ ] Milestones specified
- [ ] Timeline realistic for PhD duration
- [ ] Dependencies considered

#### Significance (200-400 words)
- [ ] Theoretical contributions stated
- [ ] Practical implications described
- [ ] Broader impact discussed
- [ ] Claims appropriately hedged

#### References (see [CITATION_INTEGRITY.md](CITATION_INTEGRITY.md) — the delivery gate)
- [ ] **Every reference verified to exist** — DOI/PMID/arXiv resolves, or Zotero metadata confirms it (Rule 1)
- [ ] **First author and year match the source** for every entry (Rule 2)
- [ ] No fabricated or padded references; **count follows the argument, no minimum** (typically 25–50, humanities often more)
- [ ] No placeholder strings — the **canonical gate regex in SKILL.md Phase 5** (placeholder gate) returns 0; any `[UNVERIFIED]` was disclosed to the user, never presented as confirmed. Do not re-transcribe the pattern here — a shrunken copy drifts.
- [ ] Every in-text `(Author, Year)` has a matching References entry, and every entry is cited (no orphans either direction) (Rule 3)
- [ ] Every quantitative/directional claim matches its source; ≥20% of references spot-checked (Rule 4)
- [ ] Primary sources cited for findings, not blogs / press releases / other reviews (Rule 5)
- [ ] Citation format consistent (APA / MLA / Chicago / GB/T 7714)
- [ ] Mix of foundational and recent works (~60% from the last 5 years where the field moves fast)
- [ ] Balance across different research groups/institutions

#### Figures (3-5 suggested)
- [ ] Figure suggestions included at appropriate locations
- [ ] Each suggestion includes: title, content description, style recommendation
- [ ] Figures distributed across sections (Introduction, Methodology, Timeline)
- [ ] No figure in Abstract
- [ ] Each figure serves clear communicative purpose

---

## Content Quality

### Research Design
- [ ] Research questions are answerable
- [ ] Questions align with methodology
- [ ] Scope achievable within PhD timeframe
- [ ] Original contribution evident
- [ ] Builds on existing research appropriately

### Argumentation
- [ ] Claims supported by evidence
- [ ] Logic is sound and traceable
- [ ] Counterarguments acknowledged
- [ ] Gap justifies proposed research
- [ ] Conclusions follow from premises

### Literature Engagement
- [ ] Key works in field cited
- [ ] Seminal papers included
- [ ] Recent developments covered
- [ ] Critical analysis present
- [ ] Theoretical framework appropriate

### Methodology Rigor
- [ ] Methods match research questions
- [ ] Data collection feasible
- [ ] Analysis approach appropriate
- [ ] Validity/reliability addressed
- [ ] Limitations honestly stated

---

## Academic Writing Quality

### Writing Style (CRITICAL)
- [ ] **Prose-based writing** - content flows as connected paragraphs
- [ ] **Minimal bullet points** - lists used ONLY where truly necessary
- [ ] Appropriate list usage limited to: research questions, timeline milestones, technical specs
- [ ] No point-by-point enumeration of ideas that should be narrated
- [ ] Smooth transitions between ideas within paragraphs
- [ ] **No appendix sections** - all content in main body
- [ ] **No LLM tells** — the Phase 5 AI-tell grep (SKILL.md) returns 0 hits: no "Over the past decade/years…" openings, no "随着…的发展/近年来…日益受到关注" (中文), no "It is worth noting / pivotal role / delves into / a testament to"

### Language and Tone
- [ ] Formal academic register
- [ ] No colloquialisms or slang
- [ ] Consistent tense usage
- [ ] Appropriate voice (active/passive)
- [ ] Technical terms defined

### Hedging
- [ ] No absolute claims without evidence
- [ ] Modal verbs used appropriately (may, might, could)
- [ ] Tentative language for predictions
- [ ] Phrases like "suggests," "indicates" for findings
- [ ] No overstatement of significance

### Sentence Structure
- [ ] Topic sentences clear
- [ ] Varied sentence length
- [ ] Complex ideas broken down
- [ ] No run-on sentences
- [ ] No sentence fragments

### Paragraph Structure
- [ ] One main idea per paragraph
- [ ] 4-8 sentences typical length
- [ ] Clear topic sentence
- [ ] Supporting evidence present
- [ ] Smooth transitions

### Transitions
- [ ] Logical flow between paragraphs
- [ ] Appropriate connectors used
- [ ] Signposting for reader
- [ ] No abrupt topic changes
- [ ] Section transitions explicit

---

## Technical Accuracy

### Citations
- [ ] Format matches discipline standard (APA/MLA/Chicago)
- [ ] In-text citations correct
- [ ] Reference list complete
- [ ] DOIs/URLs included where available
- [ ] Author names accurate

### Abbreviations and Terms
- [ ] All abbreviations defined at first use
- [ ] Acronyms used consistently
- [ ] Technical terms explained
- [ ] Discipline-specific jargon appropriate
- [ ] No unexplained symbols

### Numbers and Data
- [ ] Consistent number formatting
- [ ] Units specified correctly
- [ ] Statistics reported properly
- [ ] Percentages calculated correctly
- [ ] Sample sizes justified

### Formatting
- [ ] Heading hierarchy consistent
- [ ] Font and spacing uniform
- [ ] Lists formatted properly
- [ ] Tables/figures labeled (if any)
- [ ] Markdown syntax correct

---

## Domain-Specific Checks

### STEM Proposals
- [ ] Hypotheses specific and testable
- [ ] Variables operationally defined
- [ ] Equipment/software specified
- [ ] Protocols detailed
- [ ] Validation approach described
- [ ] Preliminary data included (if applicable)
- [ ] Reproducibility considered

### Humanities Proposals
- [ ] Central argument clear
- [ ] Theoretical sophistication demonstrated
- [ ] Primary sources identified
- [ ] Archive/field access addressed
- [ ] Chapter outline provided
- [ ] Language requirements noted
- [ ] Interpretive framework justified

### Social Sciences Proposals
- [ ] Research questions theory-linked
- [ ] Sampling strategy justified
- [ ] Instruments described
- [ ] Ethics approval pathway identified
- [ ] Mixed methods rationale (if applicable)
- [ ] Generalizability discussed
- [ ] Practical significance clear

---

## Language-Specific Checks

### English Proposals
- [ ] British/American English consistent (`grep -nEi "colou?r|analys[ei]s|behavio?r"` shows one variant only)
- [ ] Grammar/spelling run through a checker if available; otherwise the draft is explicitly flagged for human proofreading — "grammar correct" cannot be self-certified by the writer
- [ ] Articles (a/an/the) and subject-verb agreement spot-checked in the sections you revised last (recency bias: latest edits hide the most errors)

### Chinese Proposals (中文)
- [ ] 学术语体规范
- [ ] 无口语化表达
- [ ] 标点符号正确
- [ ] 适当使用连接词
- [ ] Hedging 表达适当
- [ ] 引用格式符合 GB/T 7714

---

## Final Review

### Coherence
- [ ] Title matches content
- [ ] Abstract summarizes accurately
- [ ] Research questions answered by methodology
- [ ] Timeline matches scope
- [ ] Significance matches contributions

### Completeness
- [ ] All sections address their purpose
- [ ] No placeholder text remaining
- [ ] All [brackets] filled in — applicant-specific scaffold fields (`[University/Institution Name]`, `[Your Field]`, `[Month Year]`) are filled from what the user said or their line is deleted and listed in the delivery message; only `[Figure N Suggestion]` labels may remain
- [ ] No "TBD" or similar markers
- [ ] No missing references

### Readability
- [ ] Clear for intended audience
- [ ] Jargon explained or minimized
- [ ] Logical progression
- [ ] Key points emphasized
- [ ] Every major section's final paragraph links back to a research question or bridges to the next section (checkable per section, not a vague "satisfying")

### Professionalism
- [ ] Typo pass done: spellchecker if available, plus `grep` for doubled words (`grep -nE '\b(\w+) \1\b'`) and stray CJK punctuation in English text
- [ ] Consistent formatting
- [ ] Appropriate length
- [ ] Citations complete
- [ ] All gates above pass and any residual known limitations are disclosed to the user in the delivery message (this checklist has no "ready for submission" self-certification — readiness is the conjunction of the gates, nothing more)

---

## Scoring Guide

Score each weighted dimension on the anchors below. An unanchored 1-5 is a noise generator — the anchors define what a 3 vs a 4 actually means, and a score without anchor evidence is invalid.

### Rating Scale (anchored, per dimension)
- **5 (Excellent)**: A domain expert reading only this section would not reorder, delete, or caveat anything; every claim carries verified evidence; zero gate violations.
- **4 (Good)**: At most one paragraph needs reweighting or one claim needs a stronger source; all mechanical gates pass.
- **3 (Satisfactory)**: The section does its job but a supervisor would return it with specific line comments (e.g. two unsupported claims, one list that should be prose); all mechanical gates still pass.
- **2 (Needs Work)**: Structural problem — e.g. methodology doesn't match the questions, literature is summary-not-synthesis, or any mechanical gate fails.
- **1 (Inadequate)**: Missing, boilerplate, or fabricated content; or the citation gate fails (any unverified/unreconciled reference caps the whole proposal at 1 regardless of other strengths).

### Section Weights (sum = 100%)

| Section | Weight |
|---------|--------|
| Research Questions | 15% |
| Literature Review | 15% |
| Methodology | 25% |
| Academic Writing | 15% |
| Overall Coherence | 10% |
| Technical Accuracy | 10% |
| Significance & original contribution | 5% |
| Abstract & title fidelity | 5% |

### Minimum Standards
- No dimension rated below 3, each with the anchor evidence named
- Overall weighted average ≥ 3.5
- **Zero unverified or fabricated references** (CITATION_INTEGRITY.md gate passed)
- No critical errors in citations or methodology
- Appropriate hedging throughout

---

## Quick Reference

### Critical Requirements (Must Pass)
1. Research questions are clear and answerable
2. Gap in literature identified
3. Methodology matches questions
4. No absolute claims without evidence
5. All citations verified to exist, correctly attributed, and reconciled (CITATION_INTEGRITY.md)
6. Word count within range (±10%)

### Common Issues to Check
1. Vague research questions
2. Literature review as list, not synthesis
3. Methodology-question mismatch
4. Overstated significance
5. Missing or inconsistent citations
6. Informal language
7. Lack of hedging
8. Poor transitions
9. Undefined abbreviations
10. Unrealistic timeline
11. **Excessive bullet points** instead of flowing prose
12. **Unverified or fabricated references** (the single most serious defect — see CITATION_INTEGRITY.md)
13. **Padded bibliography** (references added to hit a number, not to support a claim)
14. **Missing figure suggestions**
15. **Appendix included** (should not have appendix)
16. **LLM-tell openings** ("Over the past decade…", "In recent years,", 近年来/随着…的发展 套话开场) — grep-gated in Phase 5; also banned in every reference and scaffold
17. **中文两制混排** (正文"（作者，年份）" + 文末编号文献表) — GB/T 7714 顺序编码制 must be used end-to-end in 中文 output
