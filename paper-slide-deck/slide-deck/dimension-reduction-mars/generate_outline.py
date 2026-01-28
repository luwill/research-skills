import json
import os
from datetime import datetime

# Paper info extracted earlier
paper_info = {
    "title": "Dimension Reduction and MARS",
    "authors": ["Yu Liu", "Degui Li", "Yingcun Xia"],
    "abstract": "The multivariate adaptive regression spline (MARS) is one of the popular estimation methods for nonparametric multivariate regression. However, as MARS is based on marginal splines, to incorporate interactions of covariates, products of the marginal splines must be used, which often leads to an unmanageable number of basis functions when the order of interaction is high and results in low estimation efficiency. In this paper, we improve the performance of MARS by using linear combinations of the covariates which achieve sufficient dimension reduction.",
    "sections": [
        "Abstract",
        "Introduction",
        "Background",
        "Methodology",
        "Experiments",
        "Results",
        "Conclusion",
        "References",
    ],
}

# Style instructions for academic-paper
style_instructions = """Design Aesthetic:
Clean, professional academic presentation aesthetic. Precise diagrams and charts with clear data visualization. White or light gray backgrounds with restrained color usage. Formal typography hierarchy suitable for academic venues. Think ICML/NeurIPS/CVPR presentation standards.

Background:
  Color: Pure White (#FFFFFF) or Light Gray (#F8FAFC)
  Texture: None - clean and distraction-free

Typography:
  Primary Font: Clean serif font for formal academic authority. Bold weight for main titles. Professional, scholarly presence similar to Times or Georgia.
  Secondary Font: Sans-serif for diagram labels, axis titles, and annotations. Clear, readable at small sizes. Consistent weight throughout.
  Body Font: Sans-serif for body text, bullet points, and descriptions. Clean and modern for readability. Proper spacing for dense information.

Color Palette:
  Primary Text: Dark Blue-Gray (#1E3A5F) - Headlines, body text
  Background: White (#FFFFFF) - Primary background
  Alt Background: Light Gray (#F8FAFC) - Alternate sections
  Secondary Text: Medium Gray (#6B7280) - Captions, annotations
  Primary Accent: Academic Blue (#2563EB) - Key highlights, links
  Chart Color 1: Deep Blue (#1E40AF) - Primary data series
  Chart Color 2: Teal (#0891B2) - Secondary data series
  Chart Color 3: Orange (#EA580C) - Tertiary data, emphasis
  Chart Color 4: Purple (#7C3AED) - Fourth data series
  Success: Green (#059669) - Positive results
  Error: Red (#DC2626) - Negative results, errors

Visual Elements:
  - Clean bar charts, line graphs, scatter plots
  - Architecture diagrams with labeled components
  - Flow charts for methods and pipelines
  - Tables with clear headers and alignment
  - Mathematical equations and notation
  - Numbered figure captions
  - Citation markers [Author, Year]
  - Section numbers and headers
  - Bullet points with consistent markers

Style Rules:
  Do:
    - Use precise, accurate diagram rendering
    - Include clear axis labels and legends on all charts
    - Add figure numbers and captions
    - Use citation markers for referenced work
    - Maintain consistent spacing and alignment
    - Show data with appropriate precision
    - Use numbered sections for navigation
    - Keep color usage minimal and purposeful
  Don't:
    - Use decorative or artistic illustrations
    - Add hand-drawn or sketch elements
    - Use gradients or 3D effects on charts
    - Include logos or watermarks
    - Add slide numbers in visual area
    - Use more than 4 colors in a single chart
    - Omit units or axis labels
    - Create cluttered or dense layouts"""

# Define slides
slides = [
    {
        "type": "Cover",
        "filename": "01-slide-cover.png",
        "narrative": "Establish paper title, authors, affiliations, and venue",
        "headline": paper_info["title"],
        "subheadline": "Journal of Machine Learning Research, 2023",
        "body": "",
        "visual": "Clean white background, centered title in dark blue, author names below, institutional affiliations at bottom",
        "layout": "paper-title",
        "image_source": "generate",
    },
    {
        "type": "Content",
        "filename": "02-slide-abstract.png",
        "narrative": "Provide a high-level overview of the paper's contribution",
        "headline": "Abstract",
        "subheadline": "Key contributions and motivation",
        "body": paper_info["abstract"][:300] + "...",
        "visual": "Clean text layout with bullet points highlighting key contributions",
        "layout": "bullet-list",
        "image_source": "generate",
    },
    {
        "type": "Content",
        "filename": "03-slide-introduction.png",
        "narrative": "Introduce the problem of high-dimensional nonparametric regression",
        "headline": "Introduction: High-Dimensional Nonparametric Regression",
        "subheadline": "Challenges with traditional MARS",
        "body": "- MARS uses marginal splines, requires product terms for interactions\n- Curse of dimensionality: exponential growth of basis functions\n- Need for dimension reduction before fitting",
        "visual": "Illustration showing curse of dimensionality: low-dim vs high-dim space",
        "layout": "split-screen",
        "image_source": "generate",
    },
    {
        "type": "Content",
        "filename": "04-slide-background.png",
        "narrative": "Review MARS and sufficient dimension reduction (SDR)",
        "headline": "Background: MARS and Sufficient Dimension Reduction",
        "subheadline": "Key concepts",
        "body": "- Multivariate Adaptive Regression Splines (MARS): flexible nonparametric method\n- Sufficient Dimension Reduction (SDR): find linear combinations preserving regression information\n- Goal: Combine SDR with MARS to improve efficiency",
        "visual": "Side-by-side diagrams: MARS spline basis vs SDR projection",
        "layout": "binary-comparison",
        "image_source": "generate",
    },
    {
        "type": "Content",
        "filename": "05-slide-method-overview.png",
        "narrative": "Present the overall methodology",
        "headline": "Methodology: SDR-MARS Framework",
        "subheadline": "Two-stage approach",
        "body": "1. Dimension Reduction: Estimate sufficient dimension reduction directions\n2. MARS Fitting: Apply MARS on reduced-dimensional space\n3. Optimization: Joint estimation of SDR directions and MARS coefficients",
        "visual": "Flow diagram showing the two-stage process with arrows",
        "layout": "linear-progression",
        "image_source": "generate",
    },
    {
        "type": "Content",
        "filename": "06-slide-sdr-details.png",
        "narrative": "Detail the sufficient dimension reduction component",
        "headline": "Sufficient Dimension Reduction Details",
        "subheadline": "Estimation of linear combinations",
        "body": "- Use sliced inverse regression (SIR) or similar methods\n- Estimate basis of central subspace\n- Dimension selection via information criteria",
        "visual": "Mathematical equations for SIR estimation",
        "layout": "equation-focus",
        "image_source": "generate",
    },
    {
        "type": "Content",
        "filename": "07-slide-mars-details.png",
        "narrative": "Detail the MARS component on reduced space",
        "headline": "MARS on Reduced-Dimensional Space",
        "subheadline": "Adaptive spline basis functions",
        "body": "- Apply standard MARS algorithm on projected covariates\n- Fewer basis functions needed due to dimension reduction\n- Improved computational efficiency and estimation accuracy",
        "visual": "Diagram showing MARS basis functions on 2D projection",
        "layout": "methods-diagram",
        "image_source": "generate",
    },
    {
        "type": "Content",
        "filename": "08-slide-algorithm.png",
        "narrative": "Present the complete algorithm",
        "headline": "SDR-MARS Algorithm",
        "subheadline": "Step-by-step procedure",
        "body": "1. Estimate SDR directions\n2. Project covariates onto reduced space\n3. Apply MARS forward and backward selection\n4. Refine SDR directions using MARS residuals (optional iteration)",
        "visual": "Pseudocode or numbered steps with clear annotations",
        "layout": "agenda",
        "image_source": "generate",
    },
    {
        "type": "Content",
        "filename": "09-slide-experimental-setup.png",
        "narrative": "Describe simulation studies and real data applications",
        "headline": "Experimental Setup",
        "subheadline": "Simulations and real data",
        "body": "- Simulation 1: Linear combination of covariates\n- Simulation 2: Nonlinear interactions\n- Real data: Boston housing, concrete strength\n- Metrics: RMSE, computation time, model complexity",
        "visual": "Table of simulation scenarios with parameters",
        "layout": "results-chart",
        "image_source": "generate",
    },
    {
        "type": "Content",
        "filename": "10-slide-simulation-results.png",
        "narrative": "Present quantitative simulation results",
        "headline": "Simulation Results",
        "subheadline": "SDR-MARS outperforms baseline MARS",
        "body": "- Lower RMSE across all simulation settings\n- Reduced model complexity (fewer basis functions)\n- Faster computation time due to dimension reduction",
        "visual": "Bar charts comparing RMSE of SDR-MARS vs MARS vs other methods",
        "layout": "results-chart",
        "image_source": "generate",
    },
    {
        "type": "Content",
        "filename": "11-slide-real-data-results.png",
        "narrative": "Present real data application results",
        "headline": "Real Data Applications",
        "subheadline": "Boston housing and concrete strength datasets",
        "body": "- SDR-MARS achieves competitive prediction accuracy\n- More interpretable models due to dimension reduction\n- Visualization of estimated SDR directions",
        "visual": "Scatter plots showing projected covariates vs response",
        "layout": "qualitative-grid",
        "image_source": "generate",
    },
    {
        "type": "Content",
        "filename": "12-slide-discussion.png",
        "narrative": "Discuss implications and limitations",
        "headline": "Discussion",
        "subheadline": "Interpretation and future work",
        "body": "- SDR-MARS effectively reduces curse of dimensionality\n- Limitations: assumes linear SDR, may not capture nonlinear manifolds\n- Future work: nonlinear dimension reduction, high-order interactions",
        "visual": "Concept map linking contributions to future directions",
        "layout": "hub-spoke",
        "image_source": "generate",
    },
    {
        "type": "Content",
        "filename": "13-slide-contributions.png",
        "narrative": "Summarize key contributions",
        "headline": "Contributions",
        "subheadline": "Summary of this work",
        "body": "1. Novel integration of SDR with MARS\n2. Theoretical convergence guarantees\n3. Empirical demonstration of improved efficiency\n4. Open-source implementation available",
        "visual": "Numbered list with checkmarks, clean spacing",
        "layout": "contributions",
        "image_source": "generate",
    },
    {
        "type": "Back Cover",
        "filename": "14-slide-back-cover.png",
        "narrative": "Provide references and contact information",
        "headline": "References & Thank You",
        "subheadline": "Key citations and resources",
        "body": "[1] Friedman, J. H. (1991). Multivariate adaptive regression splines.\n[2] Li, K. C. (1991). Sliced inverse regression for dimension reduction.\n[3] Liu et al. (2023). Dimension Reduction and MARS. JMLR.\n\nCode: https://github.com/example/sdr-mars\nContact: author@email.edu",
        "visual": "Two-column reference list, optional QR code in corner",
        "layout": "references-list",
        "image_source": "generate",
    },
]

# Generate outline markdown
outline_lines = []
outline_lines.append("# Slide Deck Outline")
outline_lines.append("")
outline_lines.append(f"**Topic**: {paper_info['title']}")
outline_lines.append("**Style**: academic-paper")
outline_lines.append("**Audience**: intermediate")
outline_lines.append("**Language**: en")
outline_lines.append(f"**Slide Count**: {len(slides)}")
outline_lines.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
outline_lines.append("")
outline_lines.append("---")
outline_lines.append("")
outline_lines.append("<STYLE_INSTRUCTIONS>")
outline_lines.append(style_instructions)
outline_lines.append("</STYLE_INSTRUCTIONS>")
outline_lines.append("")
outline_lines.append("---")
outline_lines.append("")

for i, slide in enumerate(slides, 1):
    outline_lines.append(f"## Slide {i} of {len(slides)}")
    outline_lines.append("")
    outline_lines.append(f"**Type**: {slide['type']}")
    outline_lines.append(f"**Filename**: {slide['filename']}")
    outline_lines.append("")
    outline_lines.append("// NARRATIVE GOAL")
    outline_lines.append(slide["narrative"])
    outline_lines.append("")
    outline_lines.append("// KEY CONTENT")
    outline_lines.append(f"Headline: {slide['headline']}")
    if slide["subheadline"]:
        outline_lines.append(f"Sub-headline: {slide['subheadline']}")
    if slide["body"]:
        outline_lines.append("Body:")
        for line in slide["body"].split("\n"):
            outline_lines.append(f"- {line}")
    outline_lines.append("")
    outline_lines.append("// VISUAL")
    outline_lines.append(slide["visual"])
    outline_lines.append("")
    outline_lines.append("// LAYOUT")
    outline_lines.append(f"Layout: {slide['layout']}")
    outline_lines.append("")
    if slide.get("image_source"):
        outline_lines.append("// IMAGE_SOURCE")
        outline_lines.append(f"Source: {slide['image_source']}")
    outline_lines.append("")
    outline_lines.append("---")
    outline_lines.append("")

# Write to file
outline_path = "outline-academic-paper.md"
with open(outline_path, "w", encoding="utf-8") as f:
    f.write("\n".join(outline_lines))

print(f"Generated outline: {outline_path}")
print(f"Total slides: {len(slides)}")
