# Citation Integrity Protocol

This is the most important reference file in the skill. Citation drift / fabrication is the #1 failure mode of LLM-drafted reviews.

5 rules. Every citation must satisfy all 5.

---

## Rule 1: No placeholder DOIs

Any DOI containing `xxx`, `[TBD]`, `?`, stub patterns, or "to-be-filled" notation **must be resolved before the manuscript advances to the next section**.

### Detection

```bash
grep -nE "xxx|\[TBD\]|x\):xxx|doi:10\.[a-z]+/x" manuscript_draft.md
```

Expected: 0 hits at any milestone.

### Resolution

For papers with a PMID:

```
Open https://pubmed.ncbi.nlm.nih.gov/<PMID>/ with an available web/PubMed tool.
  → Extract: title, full author list, journal, year, volume, issue, pages, DOI
```

For papers without a PMID but a known DOI:

```
Open https://api.crossref.org/works/<DOI> with an available web/API tool.
  → Extract: same fields from JSON
```

For papers in a closed-access journal where the user has the PDF:

```
Search Zotero by "<author> <method>".
Retrieve item metadata and attached full text if available.
```

### Why this is Rule 1

v2 of this skill shipped 17 placeholder DOIs in the coronary-cta-paper draft. Editors at any medical journal will reject a manuscript with `xxx` in the DOI on first sight. This is the lowest-effort, highest-impact rule.

---

## Rule 2: Author list verification

Every reference in the bibliography must have its first and last author verified against the first-source. For references with > 6 authors, list first 6 + et al. — but the first author (and last author for medical clinical papers) must be verbatim.

### LLM failure mode

LLMs generate **generic-sounding 4-author lists** when they don't know the actual authors:

- ✗ "Liu Y, Zhang H, Chen X, Wang J. TransCC..." (these are common Chinese surnames in 4-author pattern — strong fabrication signal)
- ✗ "Smith J, Johnson A, Williams M, Brown D" (English equivalent)
- ✗ "Patel R, Kumar A, Singh P, Sharma N"

### Detection

For each reference in the bibliography, ask:
- Are these 4 of the most common surnames in a major language?
- Do the initials look suspiciously "average" (J / A / M / D)?
- Is this a paper where I might have looked up the title but never the authors?

For any "yes" answer, treat as suspect and verify.

### Resolution

```
Open https://pubmed.ncbi.nlm.nih.gov/<PMID>/
  OR
Open https://api.crossref.org/works/<DOI>
  → Replace the entire author list verbatim.
```

For arXiv papers:

```
Open https://arxiv.org/abs/<id>
```

### Why this matters

A wrong author list reads as obvious fabrication to anyone in the field. Real reviewers know the principal investigators in their area, and seeing "Liu Y, Zhang H, Chen X, Wang J" attached to a high-profile method paper is an instant credibility kill.

---

## Rule 3: Body ↔ Bibliography reconciliation

The `[N]` in the body must (a) exist in the bibliography and (b) be the paper the body sentence is actually attributing the claim to.

### LLM failure mode — "citation drift"

When LLM reorganizes sections or merges paragraphs, it often forgets to renumber citations. The body sentence says "Shit et al. introduced clDice [43]" but bibliography entry [43] is a completely different paper (e.g., a centerline DRL paper). Bibliography entry [10] is actually the clDice paper.

### Detection

```bash
# Find all citations in body
grep -nE "\[([0-9]+)\]" manuscript_draft.md | head -50

# Find bibliography entries
grep -nE "^[0-9]+\." manuscript_draft.md
```

For each body citation `[N]`, verify:
- Is there a bibliography entry numbered N?
- Does that entry attribute to the right paper?

### Resolution

Two patterns:

**Pattern A: Single-author misattribution.** Body says "Shit et al. [43]" but [43] is wrong. Action: `grep -n "Shit"` to find the correct number, edit body to point there.

**Pattern B: Numerical drift across many citations.** Body [60] should be [36] (after section reorganization shifted 24 entries). Action: list affected range, manually re-number.

For a typical 120-reference review, expect 5-15 drift instances if you're careful and 30-40 if you're not.

### Detection at scale

Run the bundled audit script:

```bash
python <skill_dir>/scripts/audit_manuscript.py manuscript_draft.md --output review_outputs/audit_report.md
```

The script flags missing bibliography entries, duplicate DOI entries, likely author-citation mismatches, placeholder strings, numbered headings, H4 headings, vendor-name body mentions, display equations outside Box context, and systematic-review claims without methods support. Treat script output as triage; final citation correctness still requires source-level reading.

---

## Rule 4: Conclusion-direction verification

For every cited **finding** (HR, OR, p-value, effect size, "higher" / "lower" claim), the body sentence's directional claim must match the source's stated direction.

### LLM failure mode

LLMs flip directions when paraphrasing. The paper says "patients with collateral circulation had **lower** FAI values." LLM paraphrase becomes: "Lv et al. [N] showed collateral circulation is associated with **higher** FAI."

This is one of the worst failures because the cited paper genuinely exists, the author is real, and the topic is right — but the conclusion direction is reversed. Catches eye of any reviewer in the area.

### Detection

For every body sentence that contains directional language (higher / lower / increased / decreased / better / worse), the writer must have explicitly verified the direction against the source.

Quick checklist when writing such a sentence:
1. What direction does the source actually report?
2. What direction am I about to write?
3. Do those match?

### Resolution

Always cite directions verbatim from the abstract. Don't paraphrase quantitative directional claims.

✗ "Lv et al. [N] showed collaterals are associated with higher FAI."
✓ "Patients with collateral circulation had lower FAI values than those without (Lv et al. [N])."

---

## Rule 5: First-source over vendor materials

Vendor white papers, NHS England reports, FDA 510(k) clearance letters, and company press releases are **not** peer-reviewed primary sources for clinical findings. Cite them only for regulatory facts (clearance date, indication), not for clinical evidence (trial results, performance numbers).

### LLM failure mode

LLM cites "NHS England. FISH&CHIPS Study Implementation Report. BMJ Open. 2024" as if it's a peer-reviewed trial. Reality: there is no such BMJ Open paper. The FISH&CHIPS study is a real NHS program, and its peer-reviewed publication is:

> Fairbairn TA, Mullen L, Nicol E, Lip GYH, Schmitt M, Shaw M, et al. Implementation of a national AI technology program on cardiovascular outcomes and the health system. **Nat Med**. 2025;31(6):1903-1910.

The body sentence was right about the study existing, but the citation was a fabricated journal attribution.

### Detection

For every reference that looks like:
- "[Company name]. [Product] White Paper. ..."
- "[Agency]. [Study]. ..."
- "[Study Investigators]. [Findings]. [Major journal]. 2024."

Treat as **suspect** and search for the actual peer-reviewed publication.

### Resolution

For each vendor- or agency-style citation, search PubMed:

```
Search PubMed or the journal site for "<study acronym> implementation OR validation".
```

If a peer-reviewed publication exists, use it. If not, use the vendor material **only for regulatory / programmatic facts**, never for clinical performance claims.

---

## Verification Workflow Integration

These 5 rules are applied at multiple points:

| Phase | Rules applied | How |
|---|---|---|
| Phase 2 (collection) | Rules 1, 2, 5 | At entry time, before adding to bibliography |
| Phase 4 (writing) | Rules 1, 3, 4 | Per-paragraph as citations are placed |
| Phase 5 (peer review) | All 5 | `ref-checker` pass runs a systematic body↔bib + author + DOI sweep (see WORKFLOW.md Phase 5) |
| Phase 6 (submission) | All 5 | Final checklist before submission |

---

## What to do when a rule failure is found

Failures are normal — these are guardrails, not aspirational goals.

For each failure:

1. **Stop forward writing immediately.** Don't accumulate broken citations.
2. **Look up the correct metadata** using the resolution steps above.
3. **Fix the citation in place** — body sentence + bibliography entry both.
4. **Check for related failures.** A misattribution in one place often signals the same error in 2-3 other places where the same paper was cited.
5. **Log the fix** in `IMPLEMENTATION_PLAN.md` change log — this protects the next person editing the manuscript.

---

## Why this protocol exists

The single largest source of credibility damage in LLM-drafted reviews is citation infrastructure failure. A draft can have brilliant analysis and miss editor first-glance if the bibliography is fabricated, drifted, or misattributed.

This protocol takes 10-20% of total writing time but eliminates 80%+ of the credibility-killer issues. It is non-negotiable.
