# Taxonomy Selection for Medical Imaging AI Reviews

Use this file only for narrative reviews and method surveys. For scoping and systematic reviews, let the protocol determine the Results structure; use taxonomy labels only inside extraction tables or synthesis text.

The entries below are organizational prompts, not a source of factual claims. Verify every named method, dataset, product, and performance statement through the normal evidence workflow before using it in a manuscript.

## Choose the organizing logic

Select the structure that best answers the review question. Record the choice and rejected alternatives in `<project_dir>/REVIEW_CONTEXT.md`.

| Review question | Preferred structure |
|---|---|
| How do model-design choices differ? | Architecture / inductive prior / data regime |
| How does a pipeline solve a clinical task? | Acquisition / localization / segmentation or classification / quantification / decision support |
| How mature is the evidence? | Development / internal validation / external validation / reader study / implementation |
| Where does AI enter clinical care? | Referral / acquisition / interpretation / reporting / intervention / monitoring |
| What prevents deployment? | Data / model / human factors / workflow / regulation / monitoring |

Do not force a three-axis method taxonomy onto a diagnostic-accuracy, implementation, economic, regulatory, or evidence-maturity review.

## Method-design structure

When the question is method-heavy, three complementary axes are often useful:

1. **Architecture** — how information is represented and propagated, such as convolutional, transformer, state-space, graph, temporal, or hybrid designs.
2. **Inductive prior** — what task-specific constraint is encoded, such as anatomy, topology, boundary, shape, uncertainty, multi-task, or physics constraints.
3. **Data regime** — how supervision and data access are organized, such as self-supervised, weakly supervised, semi-supervised, foundation-model adaptation, domain adaptation, federated, or continual learning.

Treat these as comparison dimensions, not mutually exclusive bins. Assign each study a primary axis for exposition and record secondary axes in the synthesis matrix.

## Domain prompts

Use only the prompts relevant to the question. They are intentionally non-exhaustive.

### Cardiovascular CT and MR

- Vessel, chamber, myocardium, plaque, flow, and tissue characterization tasks
- Centerline, topology, shape, temporal, and multi-modality priors
- Segmentation, quantification, prognosis, and decision-support stages
- Site, scanner, protocol, and patient-population transportability

### Lung CT and chest radiography

- Detection, segmentation, classification, triage, and longitudinal assessment
- Two-dimensional versus three-dimensional context
- Multi-scale, boundary, uncertainty, and report-supervision strategies
- Screening prevalence, threshold selection, and external-site validation

### Brain CT and MRI

- Multi-sequence fusion, registration, segmentation, detection, and prognosis
- Spatial, temporal, atlas, connectivity, and longitudinal priors
- Missing-sequence robustness and acquisition heterogeneity
- External validation across sites, scanners, and populations

### Cardiac imaging and ultrasound

- Cine, multi-view, Doppler, deformation, and temporal modeling
- Operator and acquisition dependence
- Shape, motion, anatomy, and uncertainty constraints
- Reader interaction, workflow timing, and repeatability

### Digital pathology

- Patch, slide, region, cell, and graph representations
- Multiple-instance, weakly supervised, self-supervised, and foundation-model regimes
- Pre-analytic variation, scanner shift, stain variation, and site generalization
- Biomarker, grading, prognosis, and clinical workflow endpoints

### Retinal and ophthalmic imaging

- Fundus, OCT, angiography, segmentation, grading, and progression tasks
- Device shift, image quality, domain adaptation, and longitudinal modeling
- Screening thresholds, subgroup performance, and referral consequences

### Cross-modality or general segmentation

- Architecture, task prior, and data regime as the initial comparison frame
- Modality-specific acquisition and annotation differences as explicit modifiers
- Dataset split integrity, benchmark comparability, and external validation as separate evidence dimensions

## Fit check before drafting

Confirm all of the following:

- The taxonomy answers the stated review question rather than merely classifying papers.
- Important studies do not require repeated or artificial placement.
- Clinical evidence and implementation evidence are not hidden inside an architecture section.
- Categories remain stable when new studies are added.
- The taxonomy supports comparison and synthesis, not a flat catalogue.

If the fit is poor, switch structures before drafting. Do not add more same-depth headings merely to preserve the initial taxonomy.

## Examples

For an illustrative, non-citable cardiovascular taxonomy, see [`../examples/ccta-taxonomy-example.md`](../examples/ccta-taxonomy-example.md). Reverify all named concepts before adapting it.
