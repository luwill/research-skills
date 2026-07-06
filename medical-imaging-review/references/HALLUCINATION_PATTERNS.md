# 10 Patterns of LLM Hallucination in Medical Imaging Reviews

Use this as a checklist during Phase 4 (writing) and Phase 5 (peer review). Every paragraph should be self-scanned against these patterns. The first 9 patterns are derived from the actual failure modes observed in the `coronary-cta-paper` v2 draft; Pattern 10 addresses review-type overclaiming.

Examples are drawn from coronary imaging but the patterns are domain-general.

---

## Pattern 1: Real paper, fabricated author list

**Most common.** The paper exists, but the author list is a generic 4-name pattern (or only includes 1-2 real authors mixed with fabricated co-authors).

### Detection signals

- Author list looks like "Liu Y, Zhang H, Chen X, Wang J" — 4 of the most common surnames in a language paired with most common initials.
- First-author initial doesn't match real first author (e.g., "Wittmann F" vs. real Bastian Wittmann).
- Author count obviously wrong for the journal (Nature paper with 3 authors is unusual; methods paper with 12 authors is unusual).
- Author list looks suspiciously "alphabetical" or "rhythmic" — real lists are messy.

### Example from coronary-cta-paper

- v2 reference [30]: "Liu Y, Zhang H, Chen X, Wang J. TransCC..."
- Reality: Chenchu Xu, Meng Li, Xue Wu (3 actual authors of the real TransCC paper)

### Fix

Replace entire author list with verbatim from arXiv / PubMed / Crossref / Zotero.

---

## Pattern 2: Inflated performance numbers

The cited paper is real, the topic is right, but the specific Dice / sensitivity / specificity / HR is fabricated and typically inflated.

### Detection signals

- Dice values ending in `.891`, `.917`, `.943` — suspiciously specific 3-decimal numbers
- Performance numbers consistently above field benchmarks
- Round-looking numbers when papers usually report messier values
- Multiple methods all reporting "Dice 0.89" when the real distribution should span 0.70-0.85

### Example from coronary-cta-paper

- v2: "TransCC achieves Dice 0.891 / HD95 1.72 mm on 120 cases"
- Reality: Dice 0.730 / IoU 0.582 on ImageCAS (not "120 cases")

### Fix

Open the actual paper. Quote the actual numbers from abstract or results table. If the paper isn't accessible, drop the specific numeric claim and only cite the contribution level ("first to apply X to Y").

---

## Pattern 3: Conclusion-direction flip

Most pernicious. Real paper, real authors, real finding — but the direction (higher/lower, increased/decreased) is reversed.

### Detection signals

- Look for any body sentence with directional language: "higher", "lower", "increased", "decreased", "better", "worse", "more", "less"
- These all need explicit verification against the source

### Example from coronary-cta-paper

- v2: "Lv et al. showed collateral circulation is associated with **higher** FAI"
- Reality: collaterals associated with **lower** FAI

### Fix

Always quote directional claims verbatim from the source abstract. Don't paraphrase quantitative directional language.

---

## Pattern 4: Vendor / agency material cited as peer-reviewed

Vendor white papers, FDA clearance letters, NHS reports cited with fabricated journal attribution.

### Detection signals

- References that look like: "Company X. Product Y Whitepaper. Major Journal. 2024"
- "Study Investigators. Findings. BMJ Open. 2024" (when no such BMJ Open paper exists)
- Citations of clinical findings backed by a regulatory document rather than a peer-reviewed trial

### Example from coronary-cta-paper

- v2: "NHS England. FISH&CHIPS Study Implementation Report. BMJ Open. 2024"
- Reality: real publication is Fairbairn TA, et al. Nat Med. 2025;31(6):1903-1910

### Fix

Search PubMed for the actual peer-reviewed publication of the study. Use vendor materials only for regulatory / programmatic facts (clearance dates, indications), never for clinical claims.

---

## Pattern 5: Placeholder DOIs

`xxx`, `[TBD]`, `x):xxx-xxx` stubs left in the bibliography.

### Detection

```bash
grep -nE "xxx|\[TBD\]|x\):xxx|doi:10\.[a-z]+/x" manuscript_draft.md
```

### Example from coronary-cta-paper

- v2 had 17 entries like: `Eur Radiol. 2026;36(x):xxx-xxx. doi:10.1007/s00330-025-xxx`
- Reality: each has a real DOI resolvable via PubMed by PMID

### Fix

For each placeholder, WebFetch on PubMed by PMID to extract real metadata. If the paper genuinely doesn't have a DOI yet (true preprint), use the arXiv ID or accept the "online ahead of print" notation — but never `xxx`.

---

## Pattern 6: Generic 4-author hallucination (subset of pattern 1, called out separately)

Specifically the "4 common surnames + common initials" pattern. So distinctive it deserves its own watch.

### Examples

- "Zhang H, Wang L, Chen Y, Liu Q" (Chinese)
- "Smith J, Johnson A, Williams M, Brown D" (English)
- "Patel R, Kumar A, Singh P, Sharma N" (Indian)
- "Sato K, Tanaka T, Suzuki M, Watanabe H" (Japanese)

### Fix

Any time you see exactly 4 authors with this pattern, verify all 4 against the source. Real 4-author papers usually have at least one less-common name.

---

## Pattern 7: Citation number drift

Body says "[43]" but bibliography [43] is the wrong paper. The correct paper is at [10] (or wherever).

### Detection

For every paragraph, check 1-2 random `[N]` against bibliography:
- Is the body sentence's topic congruent with bibliography [N]'s title?
- Is the body sentence's author name (if mentioned) the bibliography [N] author?

### Example from coronary-cta-paper

- v2: "Shit et al. [43] introduced clDice"
- v2 bibliography [43]: a centerline DRL paper (unrelated)
- v2 bibliography [10]: Shit S, Paetzold JC. clDice — CVPR 2021 (correct)
- Total drift instances in v2: 30-40

### Fix

For each affected `[N]`, grep for the correct number and edit body in place.

---

## Pattern 8: Metric formula errors

Definitions of standard metrics are wrong. Often: clDice written as "sum-divided-by", actually defined as "harmonic mean".

### Common confusions

- clDice: actually harmonic mean of topological precision and recall (HM(Tprec, Tsens)), often mis-written as "sum / 2" or "average"
- Hausdorff distance: actually `max(d(A→B), d(B→A))`, often mis-written as "average distance"
- IoU vs Dice: `|A∩B|/|A∪B|` vs `2|A∩B|/(|A|+|B|)` — sometimes swapped
- FedAvg: weighted by client-data-size, often mis-described as simple averaging

### Fix

For every metric or method formula displayed, verify against the original paper. Don't rely on memory — these are textbook formulas with subtle precise definitions.

---

## Pattern 9: Internal inconsistency across sections

The same paper is cited in §3.2 with one author list and in §3.5 with a different author list. Or the same dataset appears with different patient counts in different sections.

### Detection

Pick the 5 most-cited papers in the manuscript. For each, grep for every appearance:

```bash
grep -n "TransCC\|Wittmann\|FISH&CHIPS\|ORFAN\|<key-paper-name>" manuscript_draft.md
```

Check: every appearance of the same paper should attribute to the same author list with the same numbers.

### Example from coronary-cta-paper

- v2: ImageCAS described as "1000 cases" in §2, "multi-center 1500 cases" in §3.2, "single-center 1000 cases" in Table 3
- Reality: ImageCAS is single-center, 1000 cases

### Fix

For each high-value paper or dataset, lock in a canonical description in CLAUDE.md terminology table. All sections must conform.

---

## Pattern 10: Systematic-review label without systematic methods

The manuscript calls itself a systematic review, meta-analysis, or scoping review, but the methods are really narrative: no exact search strings, no eligibility criteria, no screening flow, no extraction table, and no risk-of-bias method.

### Detection signals

- Title or abstract says "systematic review" but Methods lacks PRISMA, eligibility criteria, search strategy, screening, data extraction, or risk-of-bias assessment.
- The manuscript claims "comprehensive search" without naming databases, dates, and exact strings.
- Results discuss "included studies" without a flow diagram or exclusion reasons.
- Meta-analysis language appears without pooling method, heterogeneity handling, and comparable outcomes.

### Fix

Either add the route-specific methods files and rewrite to PRISMA/PRISMA-ScR standards, or downgrade the label to "narrative review", "method survey", or "scoping review" as appropriate. Never preserve the systematic label by cosmetic wording alone.

---

## Self-Check Workflow

Every 5-6 paragraphs during writing:

1. Scan the last block for direction language → verify pattern 3.
2. Look at any new citations → verify patterns 1, 2, 5, 6.
3. Cross-check any vendor/agency references → verify pattern 4.
4. Random-sample 1-2 `[N]` body↔bib → verify pattern 7.
5. Check any metric formula displayed → verify pattern 8.
6. If the title/abstract uses systematic/scoping/meta-analysis language → verify pattern 10.

Every section completion:

7. Search the section for the manuscript's top 5 cited papers → verify pattern 9 (internal consistency).

This adds ~10-15% to writing time. Catches >90% of hallucinations before they leave the writer's desk.
