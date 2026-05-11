# Domain-Specific Method Taxonomies (3-Axis Grouping)

**This file replaces the v2 "flat 10-subsection list" approach.** For each medical imaging domain, methods are organized along **3 thematic axes**, not as a long flat list. These axes are **subsection structure** (the H3 organization in §Methods), with **bold lead-ins** for individual method families inside each axis.

The 3 axes are universal:
1. **Architectural priors** — what kind of network (CNN, Transformer, Mamba, etc.)
2. **Inductive priors** — what kind of geometric / structural / multi-task bias is built in (topology, multi-task, graph, etc.)
3. **Data regime** — how data is used / pre-trained / federated (self-supervised, foundation models, federated, etc.)

**Critical:** These 3 axes are how the §Methods section is structured. Do NOT bullet 10 method categories as 10 H3 subsections. Use 3 axis subsections, with bold lead-ins inside each axis for the method families.

---

## How to use this file

When writing the §Methods section:

1. Open this file to find your domain.
2. Use the 3-axis grouping as your H3 structure.
3. Inside each axis subsection, use bold lead-ins for the individual method families.
4. End each axis subsection with a verdict sentence.

Example for coronary segmentation §Methods:

```markdown
## Methods

### Architectural priors

**CNN-based design.** ... 2-3 paragraphs ...
**Transformer-based design.** ... 2-3 paragraphs ...
**Mamba and state-space design.** ... 1-2 paragraphs ...

Verdict: CNN-based design remains the operational default; transformer
hybrids are starting to show convincing gains in centerline-vs-mask hybrid
problems but have yet to displace U-Net on pure segmentation.

### Inductive priors

**Topology-aware design.** ... 2-3 paragraphs ...
**Multi-task design.** ... 2-3 paragraphs ...
**Graph neural network design.** ... 1-2 paragraphs ...

Verdict: Topology-aware losses are the single most cost-effective design
choice for coronary segmentation when paired with any decent backbone.

### Data regime

**Self-supervised pre-training.** ... 2-3 paragraphs ...
**Foundation models.** ... 2-3 paragraphs ...
**Federated learning.** ... 1-2 paragraphs ...
**Physics-informed models.** ... 1 paragraph ...

Verdict: Foundation models are the next 2-3 years' wild card; their gap to
domain-tuned specialists has narrowed substantially but is not yet closed.
```

---

## Coronary Artery / Cardiovascular CT (CCTA)

### Axis 1: Architectural priors
- **CNN-based**: U-Net, V-Net, nnU-Net variants
- **Transformer-based**: ViT, SwinUNETR, TransUNet, TransCC, FocusUNETR
- **Mamba / state-space**: VM-UNet, U-Mamba for vessels
- **Hybrid CNN-Transformer**: nnFormer, hybrid encoders

### Axis 2: Inductive priors
- **Topology-aware**: clDice loss, VCP loss, persistent-homology losses
- **Multi-task**: joint segmentation + centerline, joint segmentation + bifurcation detection
- **Graph neural network**: vessel graph extraction, GNN-based labeling

### Axis 3: Data regime
- **Self-supervised pre-training**: contrastive, masked-image-modeling for vessels
- **Foundation models**: SAM-Med, vesselFM, generalist segmentation models
- **Semi-supervised**: pseudo-labeling for CCTA datasets
- **Federated learning**: multi-center coronary segmentation without data sharing
- **Physics-informed**: PDE-constrained losses for vessel topology

### Downstream tasks (separate section, not part of methods axis structure)
- Centerline extraction
- Vessel labeling (SCCT 18-segment / AHA 17-segment myocardium)
- Stenosis detection
- CT-FFR computation
- Plaque analysis
- Calcium scoring
- Pericoronary fat analysis (FAI)

### Key datasets
- CAT08 (32 cases, centerline)
- ASOCA (40 cases, segmentation)
- ImageCAS (1000 cases, single-center, segmentation)
- PCCTA120 (120 cases, artery + plaque)

---

## Lung Imaging (CT / X-ray)

### Axis 1: Architectural priors
- **Anchor-based detection**: Faster R-CNN, RetinaNet
- **Anchor-free detection**: CenterNet, FCOS, YOLO variants
- **Transformer-based detection**: DETR family
- **3D detection**: 3D nodule detection networks
- **U-Net variants for segmentation**

### Axis 2: Inductive priors
- **Multi-scale feature pyramids**: FPN-based, PSP
- **Attention mechanisms**: SE blocks, CBAM, axial attention
- **Boundary-aware**: edge-loss formulations
- **Uncertainty quantification**: MC dropout, ensembles

### Axis 3: Data regime
- **Self-supervised**: contrastive learning on chest CT
- **Weakly-supervised**: from radiology reports
- **Foundation models**: chest X-ray foundation models

### Tasks
- Nodule detection / segmentation / malignancy classification
- COVID-19 detection
- Interstitial lung disease characterization

### Key datasets
- LUNA16 (888 CT scans)
- LIDC-IDRI (1018 cases)
- ChestX-ray14 (112,120 X-rays)

---

## Brain Imaging (MRI / CT)

### Axis 1: Architectural priors
- **CNN-based**: U-Net, V-Net
- **Transformer-based**: SwinUNETR, UNETR for BraTS
- **Hybrid**

### Axis 2: Inductive priors
- **Attention mechanisms**: spatial, channel, self-attention
- **Graph neural networks**: brain connectivity GNNs
- **Multi-atlas-informed**: deep atlas registration

### Axis 3: Data regime
- **Self-supervised pre-training**: masked-image-modeling on MRI
- **Foundation models**: medSAM, BrainSAM
- **Multi-modal fusion**: T1/T2/FLAIR fusion strategies
- **Federated learning**: cross-institutional MRI federation

### Tasks
- Brain tissue segmentation
- Tumor segmentation (BraTS)
- Lesion detection (stroke, MS)
- Cerebrovascular segmentation
- Age / disease estimation

### Key datasets
- BraTS (brain tumor)
- ADNI (Alzheimer's)
- IXI (healthy brains)
- ISLES (stroke lesions)

---

## Cardiac Imaging (MRI / CT / Echo)

### Axis 1: Architectural priors
- **CNN-based**: nnU-Net, V-Net cine MRI
- **Temporal modeling**: RNN, 3D CNN, transformer-based temporal
- **Multi-view fusion**: SA + LA cine fusion

### Axis 2: Inductive priors
- **Shape priors**: SSM-constrained networks
- **Anatomical loss formulations**
- **Uncertainty estimation**: ensembles, MC dropout

### Axis 3: Data regime
- **Multi-modal fusion**: cine + LGE + perfusion
- **Foundation models**: cardiac generalists
- **Self-supervised pre-training**

### Tasks
- Chamber segmentation
- Wall motion analysis
- Scar / fibrosis detection (LGE)
- Valve assessment
- Strain analysis

### Key datasets
- ACDC (100 patients)
- M&Ms (320 subjects)
- CAMUS (500 patients, echo)

---

## Pathology (Whole Slide Images)

### Axis 1: Architectural priors
- **Patch-based CNN**: ResNet, EfficientNet
- **Transformer-based**: ViT, hierarchical transformers
- **Graph neural networks**: nuclei-level graphs

### Axis 2: Inductive priors
- **Multiple Instance Learning (MIL)**: attention-MIL, max-pooling
- **Attention-based aggregation**: TransMIL
- **Topology-aware**: persistent homology of histological structures

### Axis 3: Data regime
- **Self-supervised pre-training**: SimCLR / MoCo / DINO on patches
- **Foundation models**: PathLM, CONCH, UNI, Virchow
- **Weakly-supervised**: from slide-level labels

### Tasks
- Cancer detection / grading / staging
- Biomarker prediction
- Survival prediction

### Key datasets
- CAMELYON (lymph node)
- TCGA (multi-cancer)
- PANDA (prostate)

---

## Retinal Imaging (Fundus / OCT)

### Axis 1: Architectural priors
- **CNN-based**: multi-scale networks
- **Transformer-based**: ViT for fundus
- **Hybrid**

### Axis 2: Inductive priors
- **Attention mechanisms**: dual-attention for vessels
- **Domain adaptation**: between fundus camera types

### Axis 3: Data regime
- **Self-supervised**: on large unlabeled fundus image sets
- **Foundation models**: RETFound, FLAIR
- **Federated learning**: privacy-preserving DR screening

### Tasks
- Diabetic retinopathy grading
- Glaucoma detection
- Age-related macular degeneration
- Vessel segmentation

### Key datasets
- EyePACS (88,702 images)
- DRIVE (40 images, vessels)
- REFUGE (1200 images, glaucoma)

---

## Universal Medical Image Segmentation (Fallback Axis Structure)

When the domain is generic or your topic spans multiple modalities, use this universal 3-axis grouping:

### Axis 1: Architectural priors
- Encoder-Decoder (U-Net, V-Net, nnU-Net)
- Transformer-based (SwinUNETR, UNETR, TransUNet)
- Mamba / state-space
- Hybrid CNN-Transformer

### Axis 2: Inductive priors
- Attention mechanisms (SE, CBAM, axial, deformable)
- Multi-scale processing (FPN, PSP, ASPP)
- Boundary-aware (active contours, edge losses)
- Topology-preserving (clDice, persistent homology)
- Uncertainty quantification (MC Dropout, ensembles)

### Axis 3: Data regime
- Self-supervised pre-training (contrastive, masked)
- Foundation models (SAM, MedSAM)
- Few-shot / zero-shot (prototypical, foundation models)
- Domain adaptation (adversarial, self-training)
- Federated learning
- Efficient architectures (MobileNet, EfficientNet, Mamba — when efficiency is the focus)

### Universal evaluation metrics (Box 1 content)
- **Overlap**: Dice, IoU / Jaccard
- **Distance**: Hausdorff (HD, HD95), ASSD
- **Topology**: clDice, Betti numbers
- **Clinical**: Sensitivity, Specificity, AUC, PPV / NPV

---

## What to do when a method family doesn't fit cleanly into 3 axes

Some methods span axes (e.g., a foundation-model-based topology-aware Mamba would touch all 3). In such cases:

- Place the method in the axis it's most centrally about.
- Cross-reference from the other 2 axes ("see also: this method type combines architectural and data-regime innovations").
- Don't create a 4th axis to accommodate it. Three axes is the structural commitment.

If 30%+ of your methods don't fit, you may be in a sub-domain where the 3-axis structure needs adaptation. In that case, document the alternative structure in PARADIGM.md and use it consistently — but stay disciplined to 3 axes.

---

## Why 3 axes, not 10 flat subsections

The v2 skill's coronary section listed 10 flat method categories. The resulting draft had a §3 with 10 nearly-equal H3 subsections, each ~500 words. The effect on the reader: **a textbook chapter, not a flagship review**.

Flagship reviews compress 10+ method variants into 3 thematic axes. The 3-axis structure also forces explicit comparison ("CNN-based vs Transformer-based vs Mamba-based architectures all aim to capture spatial inductive bias differently") which is what a real review reader wants — synthesis, not catalogue.

If your editor / reviewer feedback says "the methods section reads as a flat list", this file's structure is the fix.
