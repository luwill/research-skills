# Paradigm Capture and Style Profiles

Paradigm capture records how relevant target-journal articles communicate. It does not define evidence quality and must not create universal style rules.

Create **review_project/<project-id>/PARADIGM.md** and, when enough evidence exists, **style_profile.json**. All resulting style checks are warnings unless current target-journal instructions explicitly make an item mandatory.

---

## Principles

1. **Match route before prestige.** A systematic exemplar is more useful for a systematic project than an unrelated narrative article from a higher-profile journal.
2. **Use current journal instructions as the authority.** Exemplars illustrate practice; they do not override author instructions.
3. **Observe variation.** Do not turn one article's heading depth, equation placement, table count, or tone into a hidden default.
4. **Separate style from science.** Search adequacy, screening, extraction, risk of bias, certainty, citation support, and human review are never style-profile settings.
5. **Record uncertainty.** If exemplars conflict or the sample is too small, mark the preference unspecified.

---

## Select exemplars

Choose one or more articles that are relevant to:

- the same route: narrative, method-survey, scoping, or systematic;
- the same target journal or explicit journal family;
- a similar clinical/technical question;
- a similar evidence unit, such as methods, diagnostic accuracy, prediction, implementation, or policy;
- current author instructions and article format.

Do not impose a fixed exemplar count or publication-year cutoff. Explain why each exemplar is informative and note any older exemplar retained for historical or methodological reasons.

Verify title, authors, venue, year, DOI/PMID or other identifier, article type, and access route. Add it to references.bib with a stable citekey if it will be cited.

---

## Read for observable conventions

Capture facts rather than assumptions.

### Article identity and route

- What article type does the journal call it?
- Does the reported method match that label?
- Is the article invited, commissioned, consensus-based, protocol-driven, or independently submitted?
- Are supplementary files essential to understanding the methods?

### Structure

- Section order and labels;
- heading depth and numbering;
- location of protocol/search/screening/appraisal content;
- abstract and key-message format;
- placement of limitations, certainty, and data/code statements.

### Evidence presentation

- How individual studies and syntheses are distinguished;
- how uncertainty, risk of bias, and certainty are communicated;
- whether comparative values show population, split, comparator, unit, threshold, and interval;
- handling of counterevidence and limitations;
- use of tables, evidence maps, flow diagrams, forest/ROC plots, boxes, and supplements.

### Citation presentation

- Citation style rendered by the journal;
- how multi-source synthesis claims are cited;
- whether primary sources are preferred over secondary summaries;
- how preprints, registries, official records, datasets, and software are labeled.

The project still drafts with stable Pandoc citekeys. Rendered numeric or author-date appearance is captured in CSL, not manually copied into manuscript.md.

### Prose and voice

- Typical paragraph organization;
- degree and placement of uncertainty language;
- distinction between observation, interpretation, and recommendation;
- whether conclusion strength tracks evidence limitations;
- terminology and abbreviation conventions.

Do not ban a phrase merely because it appears generic or machine-like. Flag vague, unsupported, or repetitive language by function, and revise it to match evidence strength.

### Equations, tables, figures, and products

- Where equations appear and why;
- table/figure purposes rather than counts alone;
- caption and footnote conventions;
- whether product/manufacturer names are necessary for precision;
- separation of regulatory, reimbursement, and clinical-evidence facts.

Vendor placement is a profile observation, not a universal prohibition. Regulatory and reimbursement source requirements remain blocking regardless of placement.

---

## PARADIGM.md template

~~~markdown
# Paradigm Notes

## Project
- Project ID: <project_id>
- Route: <narrative|method-survey|scoping|systematic>
- Target journal: <journal or undecided>
- Journal instructions URL/date: <URL and access date>

## Exemplars
| Citekey | Article type | Relevance | Important caveat |
|---|---|---|---|
| @<citekey> | <journal label/route> | <why selected> | <invited, older, different question, etc.> |

## Observed structure
| Feature | Observation | Variation | Confidence |
|---|---|---|---|
| Heading numbering | <observation> | <exceptions> | <high/medium/low> |
| Heading depth | <observation> | <exceptions> | <confidence> |
| Section order | <observation> | <exceptions> | <confidence> |
| Key messages | <observation> | <exceptions> | <confidence> |

## Observed evidence presentation
<How study-level results, appraisal, uncertainty, counterevidence, and synthesis are presented>

## Observed citation presentation
<Rendered style, multi-source claims, preprints, registries, official records, datasets, software>

## Observed prose and terminology
<Paragraph organization, uncertainty language, terminology, abbreviations>

## Observed visual/table conventions
<Purpose and placement of equations, tables, figures, boxes, flow diagrams, supplements>

## Candidate profile warnings
| Check | Expected value | Source | Confidence | Exception handling |
|---|---|---|---|---|
| <check> | <value or unspecified> | <instructions/exemplars> | <confidence> | <warning text> |

## Scientific requirements excluded from profile
Search, screening, extraction, risk of bias, certainty, claim verification, human review, AI disclosure, protocol deviations, and official-source verification remain governed by route methods and cannot be softened here.
~~~

---

## style_profile.json generation

Only encode a check when supported by current instructions or consistent exemplar evidence:

~~~json
{
  "schema_version": "1.0",
  "profile_name": "<target-or-custom-name>",
  "source": "<instructions URL/date and exemplar citekeys>",
  "checks": {
    "heading_numbering": {
      "expected": "<numbered|unnumbered|unspecified>",
      "severity": "warning",
      "rationale": "<source>"
    },
    "max_heading_depth": {
      "expected": "<integer|null>",
      "severity": "warning",
      "rationale": "<source>"
    },
    "key_points": {
      "expected": "<required|optional|absent|unspecified>",
      "severity": "warning",
      "rationale": "<source>"
    },
    "equation_location": {
      "expected": "<body|box|either|unspecified>",
      "severity": "warning",
      "rationale": "<source>"
    },
    "vendor_placement": {
      "expected": "<body|table|either|unspecified>",
      "severity": "warning",
      "rationale": "<source>"
    },
    "table_limit": {
      "expected": "<integer|null>",
      "severity": "warning",
      "rationale": "<source>"
    },
    "figure_limit": {
      "expected": "<integer|null>",
      "severity": "warning",
      "rationale": "<source>"
    },
    "citation_density": {
      "expected": "<description|null>",
      "severity": "warning",
      "rationale": "<source>"
    },
    "section_order": {
      "expected": ["<section>"],
      "severity": "warning",
      "rationale": "<source>"
    }
  },
  "notes": "<conflicts, uncertainty, and exceptions>"
}
~~~

Permitted severity is warning. A journal requirement may be labeled required_by_journal in rationale, but the profile still does not become an evidence gate.

If evidence is insufficient, omit the key or use unspecified/null. Do not invent a generic fallback.

---

## Applying the profile

At the start of a drafting session:

1. Re-read REVIEW_CONTEXT.md for scientific scope.
2. Re-read PARADIGM.md for observed communication conventions.
3. Use style_profile.json only to generate revision warnings.
4. Resolve conflicts in favor of evidence accuracy, route methods, and current journal instructions.
5. Record any profile change and its source.

Auditor example:

~~~bash
python3 <skill_dir>/scripts/audit_manuscript.py review_project/<project-id>/manuscript.md --route <narrative|method-survey|scoping|systematic> --project-dir review_project/<project-id> --fail-on critical --output review_project/<project-id>/review_outputs/audit_report.md
~~~

The --profile JSON path is optional. When omitted, profile-dependent checks are not_assessed, not violations and not passes.

---

## What paradigm capture cannot establish

Paradigm capture cannot prove:

- that a search is adequate;
- that study selection or extraction is unbiased;
- that a source supports a claim;
- that a risk-of-bias or certainty judgment is correct;
- that a strong conclusion is warranted;
- that a draft will receive editorial acceptance.

Its output is a documented set of communication preferences for an expert-signoff-ready draft, not a quality certificate.
