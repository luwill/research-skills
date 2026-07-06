# Quality Checklist for Medical Imaging AI Reviews

This checklist runs at multiple checkpoints — end of each section, end of each writing day, before peer-review phase, before submission.

**v3 changes from v2:** Dropped "hedging language used", "80-120 references", and format-only metric checks. Replaced with substance checks (citation integrity, conclusion direction, verdict presence, structural discipline).

---

## Citation Integrity (Hard Gate)

These are non-negotiable. Any failure must be fixed before continuing.

- [ ] No placeholder DOIs (grep `xxx`, `[TBD]`, `x):xxx`)
- [ ] Every reference's first and last author verified against first-source
- [ ] Body↔bibliography `[N]` reconciliation — spot-check 10 random citations per section
- [ ] Every directional claim (higher/lower, increased/decreased) verified against source
- [ ] No vendor white papers cited as if peer-reviewed
- [ ] No duplicate references (same paper listed under two numbers)

See [CITATION_INTEGRITY.md](CITATION_INTEGRITY.md) for the full 5-rule protocol.

---

## Review-Type And Reporting-Standard Fit (Hard Gate)

- [ ] Review type is declared before drafting: narrative, method survey, scoping, systematic, systematic + meta-analysis, or umbrella.
- [ ] Title, abstract, and Methods use language consistent with the route.
- [ ] If "systematic review" appears, PRISMA 2020 items are present: search strings, databases, eligibility criteria, screening flow, extraction fields, and risk-of-bias methods.
- [ ] If "scoping review" appears, PRISMA-ScR items are present: PCC question, charting table, evidence map, and flow diagram.
- [ ] If diagnostic accuracy is reviewed, QUADAS-family risk-of-bias domains are addressed.
- [ ] If AI primary studies are appraised, CLAIM/TRIPOD+AI-style fields are extracted where relevant.
- [ ] No meta-analysis language appears unless pooling methods, heterogeneity, and comparable outcomes are documented.

See [REVIEW_TYPES.md](REVIEW_TYPES.md) and [REPORTING_STANDARDS.md](REPORTING_STANDARDS.md).

---

## Structural Discipline

- [ ] Heading depth ≤ 2 levels (H2 + H3 only in body)
- [ ] No numbered headings (no `## 1.`, `### 1.1`)
- [ ] H4 (`####`) absent from narrative body sections — deeper grouping via bold lead-in `**Topic.**`
- [ ] Narrative/method-survey Methods uses the 3-axis grouping where appropriate; systematic/scoping reviews follow protocol-driven structure
- [ ] Verdict sentences present in 3-5 places for narrative/method surveys (not on every paragraph, not absent entirely)
- [ ] Key Points box has 4-5 bullets, 1-3 sentences each
- [ ] Standard sections match the selected review route

---

## Voice and Register

- [ ] No "has shown promising results" / "may suggest" / "interestingly" / "in recent years," / "it is worth noting" anywhere
- [ ] Hedging used only when evidence genuinely supports caution, not as default register
- [ ] Strong findings (≥2 independent groups confirming) stated strongly
- [ ] Each major method axis (3 axes in §Methods) closes with a verdict sentence
- [ ] No "neutral catalogue" stretches longer than 3 paragraphs without a verdict / position

---

## Equations and Boxes

- [ ] Display equations (`$$...$$`) appear only in Boxes, not in body paragraphs
- [ ] Textbook formulas (DSC, IoU, FedAvg) handled in prose if not in Box 1, not displayed inline
- [ ] Box 1 (metrics) present and complete
- [ ] Total Box count appropriate for target journal (typically 1-3)

---

## Vendor Names

- [ ] Vendor names (HeartFlow, Cleerly, Caristo, Keya, Shukun, etc.) appear primarily in the commercial/regulatory table
- [ ] Any body mention of a vendor/product is necessary for regulatory, trial, or comparative precision
- [ ] Clinical-effectiveness claims use peer-reviewed evidence, not vendor white papers or clearance letters
- [ ] Body uses category descriptors with table cross-reference when product names are not necessary

```bash
# Quick check
python <skill_dir>/scripts/audit_manuscript.py manuscript_draft.md --output review_outputs/audit_report.md
# Inspect "Vendor body mentions"; justify or rewrite each hit.
```

---

## Tables

- [ ] Table 1: Public datasets (year, cases, annotation type, access)
- [ ] Table 2: Method comparison (modality / family / dataset / metric — pick 12-20 papers)
- [ ] Table 3: Commercial products with regulatory evidence
- [ ] Total tables ≤ 4 (typical flagship reviews stay at 2-3)
- [ ] Each table has a title, body, and footnote explaining abbreviations / caveats

---

## Figures

- [ ] Figure 1: Review overview / taxonomy
- [ ] Figure 2: Representative architectures or method evolution
- [ ] Figure 3: Clinical workflow or downstream applications
- [ ] (Optional) Figure 4: Data-driven plot (e.g., performance landscape, trial effect sizes)
- [ ] All figures have ≤ 100-word captions following Nature style: bold lead-in title sentence + body sentences
- [ ] No `[Figure placeholder]` strings before submission

---

## Content Coverage

- [ ] Narrative/method surveys cover all relevant method axes (Architectural / Inductive / Data regime) or document a better taxonomy
- [ ] Systematic/scoping reviews cover all protocol-specified outcomes, concepts, and extraction/charting domains
- [ ] Negative trials included where they exist (LLM bias: only positive)
- [ ] Inter-vendor reproducibility / cross-site validation discussed where relevant
- [ ] Demographic bias / fairness considerations addressed where relevant
- [ ] Dataset leakage, split integrity, external validation, calibration, and benchmark comparability discussed where relevant
- [ ] Code/model/data availability and reproducibility addressed where relevant
- [ ] Controversies and unresolved questions engaged, not glossed
- [ ] Future directions specific and actionable (not "more research is needed" platitudes)

---

## Self-check Commands

```bash
# Full audit
python <skill_dir>/scripts/audit_manuscript.py manuscript_draft.md --output review_outputs/audit_report.md

# Numbered headings
grep -cE "^#{2,4} [0-9]" manuscript_draft.md
# Expected: 0

# Heading depth violation
grep -c "^#### " manuscript_draft.md
# Expected: 0

# Placeholder DOIs
grep -c "xxx\|x):xxx\|\[TBD\]" manuscript_draft.md
# Expected: 0

# LLM tell phrases
for tell in "has shown promising" "may suggest" "interestingly," "in recent years," "it is worth noting"; do
  echo "=== $tell ==="
  grep -nF "$tell" manuscript_draft.md
done
# Expected: 0 per tell

# Vendor names in body
for vendor in HeartFlow Cleerly Caristo; do
  count=$(grep -c "$vendor" manuscript_draft.md)
  in_table=$(grep "| $vendor " manuscript_draft.md | wc -l)
  echo "$vendor: total $count, in table $in_table, in body $((count - in_table))"
done
# Expected: in body == 0 for each

# Inline equations
grep -n '\$\$' manuscript_draft.md
# All hits should be inside Box context (check 2 lines before)

# Verdict-sentence presence
grep -nE "currently the most|has yet to demonstrate|best understood as|next [0-9]+ years will" manuscript_draft.md
# Expected: ≥ 3 hits

# Citation count (no quantity target — but useful for sanity)
grep -cE "^[0-9]+\." manuscript_draft.md
# Use as input for body↔bib reconciliation
```

---

## What's NOT on this checklist (intentional removals from v2)

- ❌ "Hedging language used" — was actively harmful; hedging-by-default is the LLM tell, not the flagship-review voice
- ❌ "80-120 references" — was driving Claude to pad the bibliography, which encouraged fabrication
- ❌ "Performance metrics consistent (Dice: 0.XXX format)" — checking format ≠ checking correctness
- ❌ "All major methods covered" — was driving exhaustive enumeration over selective synthesis
- ❌ "Recent literature included (>50% from last 3 years)" — date-based filter has no relationship to quality

These were structural illusions of quality. They've been replaced with substantive checks above.

---

## Severity Levels for Failures

When a checklist item fails during writing:

| Severity | Examples | Action |
|---|---|---|
| **CRITICAL** | Placeholder DOI, wrong-author list on real paper, citation direction flipped, systematic-review label without systematic methods | **STOP and fix immediately**. These are reviewer-facing trust-killers. |
| **HIGH** | Body↔bib drift, vendor name in body, verdict absent in axis section | Fix before completing the current section. |
| **MEDIUM** | Heading numbered, equation inline | Fix at section end. |
| **LOW** | Multi-citation bracket > 4 refs, table > 20 rows | Note and address during peer-review phase. |
