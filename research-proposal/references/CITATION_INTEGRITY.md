# Citation Integrity Protocol

This is the most important reference file in the skill. Citation fabrication / drift is the #1 failure mode of LLM-drafted research proposals. A proposal that reaches an admissions committee, supervisor, or funding panel with a fabricated reference is not a stylistic slip — it is an **academic-integrity violation** that can end an application.

This protocol adapts the discipline of the sister skill `medical-imaging-review` to the **author–year (Author, Year)** citation convention used in proposals (APA / MLA / Chicago / GB/T 7714), not the numbered `[N]` convention of review manuscripts.

**The governing principle: 宁可少，不可假 — better fewer references than one fake.** Reference count follows the argument, never a quota. A proposal that supports every claim with 22 verified sources is stronger than one padded to 45 with three fabrications.

Every reference must satisfy all 5 rules before it is allowed into the References list.

---

## Rule 1: No unverifiable or placeholder references

A reference may enter the References list **only after** its existence is confirmed against a first source: a resolvable DOI, a PMID on PubMed, an arXiv ID, or the item's full metadata in the user's Zotero library.

Any reference that cannot be verified this way **must not be silently written into the bibliography**. Instead:

- Keep the claim, but mark the citation `[UNVERIFIED: author/topic/year as recalled]` inline, and
- Tell the user explicitly: "I could not verify N reference(s); they are flagged `[UNVERIFIED]` and must be confirmed or removed before submission."

Never invent a DOI, a journal name, a volume/issue, or page numbers to make a reference "look real."

### Detection

```bash
# Placeholder / stub markers that must never survive to delivery
grep -nE "xxx|XXXX|\[TBD\]|\[UNVERIFIED\]|doi:10\.[a-z]+/x|forthcoming DOI|10\.xxxx" proposal_draft.md
```

Expected at delivery: 0 hits, OR every `[UNVERIFIED]` explicitly disclosed to the user and never presented as a confirmed source.

### Resolution

| The reference has… | Verify by |
|---|---|
| a DOI | Open `https://api.crossref.org/works/<DOI>` or `https://doi.org/<DOI>` (WebFetch) → confirm title, authors, year, venue |
| a PMID | Open `https://pubmed.ncbi.nlm.nih.gov/<PMID>/` (WebFetch) |
| an arXiv ID | Open `https://arxiv.org/abs/<id>` (WebFetch) |
| only a title | WebSearch the exact title; if no authoritative hit resolves, treat as **unverifiable** → `[UNVERIFIED]` |
| a PDF in Zotero | `mcp__zotero__zotero_get_item_metadata` (confirm the tool is available first) |

### Why this is Rule 1

Padding a bibliography to hit a number is the single most common way LLM-drafted proposals fabricate. Removing the count target (there is none — see the governing principle) plus this verification gate together eliminate the incentive and the mechanism.

---

## Rule 2: Author and year must match the source

For every reference, the **first author's surname** and the **publication year** that appear in the in-text citation `(Author, Year)` must match the first source verbatim. For 3+ authors using `(Author et al., Year)`, the first author and year must still be exact.

### LLM failure mode

LLMs attach **plausible-but-wrong** author–year pairs to real topics:

- ✗ Citing a well-known finding to `(Smith, 2023)` when the actual paper is `(Chen et al., 2019)` — right topic, invented attribution.
- ✗ Generic 4-surname lists (`Liu, Zhang, Chen, Wang` / `Smith, Johnson, Williams, Brown`) — a strong fabrication signal.
- ✗ Year drift: the real paper is 2021, the citation says 2024 (so it "counts" as recent).

### Detection

For each reference, ask: *Have I actually seen this author list and year on a source page, or did I reconstruct it from memory?* If reconstructed → verify or flag.

### Resolution

Open the DOI / PMID / arXiv page and copy the first author and year exactly. If the source disagrees with your draft, the source wins — fix both the in-text citation and the References entry.

---

## Rule 3: In-text ↔ References reconciliation

In author–year style there are two failure directions, both of which must be zero at delivery:

1. **Orphan in-text citation** — `(Kumar & Alvarez, 2022)` appears in the body but has no matching References entry.
2. **Orphan reference** — an entry sits in the References list but is never cited in the body.

### Detection

```bash
# In-text citations (rough pass — author-year parenthetical)
grep -noE "\([A-Z][A-Za-z]+( et al\.| & [A-Z][A-Za-z]+)?,? [0-9]{4}[a-z]?\)" proposal_draft.md

# Cross-check every parenthetical author-year against the References section by hand.
```

Every in-text `(Author, Year)` must have exactly one References entry, and every References entry must be cited at least once. Same-author-same-year collisions get `2023a` / `2023b` suffixes consistently in both places.

### Resolution

- Orphan in-text citation → verify the source exists (Rule 1/2) and add the entry, or remove the claim.
- Orphan reference → cite it where it supports a claim, or delete it (do not keep it just to raise the count).

---

## Rule 4: Claim-direction and number verification

For every cited **finding** — an effect size, accuracy/Dice/AUC number, "higher/lower", "improved/reduced", "significant" claim — the direction and magnitude in the body sentence must match what the source actually reports.

### LLM failure mode

LLMs flip directions and invent numbers when paraphrasing. The source says a method "reduced error by 12%"; the paraphrase becomes "improved accuracy by 20% (Author, Year)." The paper is real, the author is real, but the claim is wrong — and any reader who knows the paper spots it instantly.

### Detection

For every body sentence with directional or quantitative language, confirm: (1) what direction/number the source reports, (2) what you are about to write, (3) that they match.

### Resolution

Cite numbers and directions verbatim from the abstract/results. Do **not** write a specific internal number you have not read in the source. If you have not accessed the paper's full text, cite it only at the contribution level ("among the first to apply X to Y") — never for a specific performance figure.

---

## Rule 5: First source over secondary material

Blog posts, press releases, vendor pages, Wikipedia, lecture slides, and other **review/survey articles** are not primary evidence. Cite them, if at all, only for what they legitimately are (a definition, a news fact, a landscape overview) — never as the primary source of an empirical finding.

### LLM failure mode

Attributing an empirical result to a secondary summary ("as reported in [a blog / a review]") rather than the original study, or fabricating a journal attribution for a program/report that has a different real publication.

### Resolution

Trace the claim to the original peer-reviewed paper and cite that. When you genuinely rely on a review for a synthesis-level statement, frame it as such ("a recent review summarizes … (Author, Year)").

---

## Verification workflow integration

These rules are applied at three gates in the SKILL.md workflow, not once at the end:

| Gate | Rules | How |
|---|---|---|
| **Phase 2 — collection (write-before-verify)** | 1, 2, 5 | Verify each source's existence, author, and year *at the moment it enters the candidate list*, before it is eligible to be cited. Present the verified candidate list to the user. |
| **Phase 4 — writing (per-section)** | 1, 3, 4 | As each section is drafted, verify every citation placed in it before moving to the next section. Never accumulate unverified citations across sections. |
| **Phase 5 — delivery (spot-check)** | all 5 | Before handing over: run the grep detections, reconcile in-text ↔ References, and spot-check at least 20% of references (and every quantitative claim) against sources. |

---

## Hallucination self-check (LLM tells)

When a citation "feels" convenient, treat these as red flags and re-verify:

1. A round, impressive number you did not read in the source.
2. A generic 4-surname author list.
3. A recent year (2023–2025) on a claim you associate with older foundational work.
4. A DOI you "reconstructed" rather than copied.
5. A perfectly on-topic paper you cannot actually locate when you search its title.
6. A famous result attributed to a plausible name you did not confirm.
7. A specific journal/volume/pages for a paper you only know by title.

Any one of these → stop, verify against a first source, fix or flag.

---

## What to do when a rule fails

Failures are expected — these are guardrails, not aspirations.

1. **Stop forward writing.** Do not accumulate broken citations.
2. **Look up the correct metadata** using the resolution steps above.
3. **Fix in place** — both the in-text `(Author, Year)` and the References entry.
4. **Check for siblings.** The same fabricated paper is often cited in 2–3 places; fix all.
5. **If it cannot be verified**, flag `[UNVERIFIED]` and disclose to the user. Do not fabricate to make it "complete."

This protocol costs 10–20% of writing time and removes the great majority of credibility-killing defects. It is non-negotiable.
