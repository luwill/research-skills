# Phase 0: Paradigm Capture

Before writing the manuscript, extract a style spec from 2-3 exemplar reviews in the target journal tier. This anchors the draft to flagship-review style and prevents drift toward the generic "survey paper" register that LLMs default to.

---

## Why this phase exists

LLMs trained on the entire web have absorbed every register of medical writing — vendor white papers, methodological surveys, textbook chapters, narrative reviews, systematic reviews, flagship reviews — and have no built-in preference among them. By default, the register they generate is somewhere between "good survey paper" and "Wikipedia article": numbered chapters, hedging language, neutral catalogue, dense subsections.

Flagship-tier reviews (Nature Reviews / Nat Med / Lancet family / JACC) write differently:

- 2 heading levels, no number prefixes
- 1-2 sentence "verdict" closers per axis section
- Equations and dataset details in Boxes, not body
- Vendor names confined to a single Table
- Authorial position taken explicitly when evidence supports it
- 1.5-2.5 references per paragraph, well-targeted
- Often a 4-5 bullet "Key Points" box after the title

Without an exemplar anchor, even careful writing drifts toward the generic register. With one, every paragraph has a benchmark.

---

## Action 1: Select 2-3 exemplar reviews

### Selection criteria

- **Same modality or same problem family** as your topic. (For coronary AI, look at recent coronary or cardiovascular AI reviews. For brain tumor segmentation, look at neuroradiology AI reviews.)
- **Same journal tier** as your target. If aiming for Nat Med, read a recent Nat Med review. If aiming for Eur Radiol, read a recent Eur Radiol review.
- **Last 3 years**. Older exemplars may have outdated stylistic conventions.
- **Recognized authors**. Reviews authored by senior figures in the field carry the conventions of their target journals more reliably.

### Suggested exemplars by tier

**Top tier (Nature Reviews / Nat Med / Lancet family):**

- Nature Reviews Cardiology — for cardiovascular AI
- Nat Med — for AI-in-medicine narrative reviews
- Lancet Digital Health — for AI clinical translation

**Second tier (specialty journals):**

- JACC: Cardiovascular Imaging — for cardiac imaging AI
- Radiology / Eur Radiol — for general imaging AI
- IEEE TMI — for methodological reviews with clinical context

**Methodological tier:**

- Medical Image Analysis — for purely methodological reviews
- IEEE JBHI — for AI-in-healthcare methods

### Acquiring the PDFs

Most flagship reviews are accessible via:

- The user's Zotero library (check first — they likely already have them)
- PubMed Central (for open-access)
- The journal's website (subscription / institutional access)
- arXiv preprint version (sometimes available)

---

## Action 2: Read carefully — not skim

Spend 60-90 minutes per exemplar. Read the full text, including Boxes, Figure captions, and Table footnotes.

Pay attention to:

### Heading structure

- How many levels deep? (Almost always 2 for top tier.)
- Are headings numbered or unnumbered? (Almost always unnumbered for top tier.)
- How long are H2 sections? (Typically 800-1500 words.)
- How long are H3 sections? (Typically 300-800 words.)
- How are deeper subsections handled? (Bold lead-in `**Topic.**`, not H4.)

### Paragraph rhythm

- How does a paragraph open? (Topic claim — almost never "In recent years," or "It is worth noting.")
- How does evidence flow? (1-3 sentences of specifics with citations, not loose generalities.)
- How does a paragraph close? (Either with a transition or with a verdict — not with hedging.)
- How many sentences per paragraph? (Usually 4-7.)

### Citation density

- Count references per paragraph in 5 random paragraphs.
- Top tier: usually 1.5-2.5 refs per paragraph.
- Lower density suggests overclaiming; higher suggests stacking refs uncritically.

### Equation handling

- Are display equations in body or Boxes?
- If in body, is there a Box at all?
- How are metric definitions handled — formula or prose?

### Vendor handling

- Search for any commercial product name. Does it appear in body text or only in Tables?
- How are FDA / regulatory facts cited?

### Authorial voice

- Find the 3-5 strongest claims in the review. How are they phrased?
- Does the author take positions like "X is currently the best approach for Y" or stay neutral throughout?
- Where does hedging appear? (Usually only when evidence genuinely supports caution.)

### Boxes and Figures

- How many Boxes? (1-3 typical.)
- What goes in a Box? (Definitions, key trials, controversies.)
- How many Figures? (3-5 typical.)
- What kinds of Figures? (Overview / taxonomy / workflow / data-driven plot.)

### Tables

- How many Tables? (2-4 typical — rarely 5+.)
- What goes in a Table? (Datasets, methods comparison, commercial products.)
- How dense? (10-20 rows is common; 30+ is unusual.)

### Key Points box

- Is there one? (Yes for most top tier.)
- How many bullets? (4-5 typical.)
- How long is each bullet? (1-3 sentences.)

---

## Action 3: Write `PARADIGM.md` in the project root

Use this template:

```markdown
# Paradigm Spec for [Project Name]

## Target journal: [name and tier]

## Exemplars studied
1. [Author Year]. [Title]. [Journal]. [PMID/DOI]. (PDF: <path>)
2. [Author Year]. [Title]. [Journal]. [PMID/DOI]. (PDF: <path>)

## Extracted style spec

### Heading structure
- Max depth: [N] levels
- Numbering: [yes / no]
- Typical H2 length: [N-N] words
- Deeper subsections: [H4 / bold lead-in / other]

### Paragraph rhythm
- Opening: [observed pattern, e.g., "Topic claim sentence, no temporal preamble"]
- Body: [observed pattern, e.g., "2-4 sentences of specifics with citations"]
- Closing: [observed pattern, e.g., "Transition or verdict"]
- Typical length: [N-N] sentences

### Citation density
- Average refs per paragraph: [N]
- Multi-citation cap (max refs in one bracket): [N]

### Equations
- Location: [body / Box / both / none]
- Display style: [LaTeX / inline / prose]

### Vendor handling
- Body: [allowed / disallowed]
- Table: [yes / no]
- Total Tables containing vendor names: [N]

### Authorial voice
- Hedging frequency: [observed examples]
- Strong claims: [N observed across 3 reviews]
- Verdict closers per section: [observed pattern]

### Boxes and Figures
- Box count: [N]
- Box purposes: [list]
- Figure count: [N]
- Figure types: [list]

### Tables
- Count: [N]
- Density: [N-N rows]

### Key Points
- Present: [yes / no]
- Bullet count: [N]
- Bullet length: [N-N sentences]

## Manuscript style targets (binding for Phase 4 writing)

Phase 4 writing should conform to this spec. Specifically:
- Max heading depth: ...
- No numbered headings.
- Box 1 for metrics / formulas.
- Vendor names only in Table N.
- ≥ 3 verdict sentences across the manuscript.
- Citation density 1.5-2.5 refs/paragraph.
- Key Points: 4-5 bullets after title.

## Anti-patterns observed in v2 drafting (to specifically avoid)

(Copy / adapt from this skill's HALLUCINATION_PATTERNS.md to the extent the patterns are domain-relevant.)
```

---

## Action 4: Re-read PARADIGM.md before each Phase 4 writing session

Phase 4 is multi-day. Drift is the main risk. At the start of each writing session, re-read `PARADIGM.md` to re-anchor.

---

## Time budget

- Exemplar selection: 30 min
- Reading 2 exemplars: 2-3 hours
- Writing the spec: 30-45 min

Total: 3-4 hours.

This is the highest-ROI 3-4 hours in the entire project. Skipping it almost guarantees survey-paper-register drift, which is then extremely expensive to fix in revision.
