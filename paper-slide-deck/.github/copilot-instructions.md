# Copilot Instructions: Paper Slide Deck Generator

This skill transforms academic papers and content into professional slide deck images with automatic figure extraction.

## Architecture Overview

**Core Workflow**: Content Analysis → Outline Generation → Prompt Creation → Image Generation → Merge to PPTX/PDF

- **Input**: PDF papers or markdown content
- **Output**: PNG slide images, PPTX, PDF
- **Key Components**:
  - `generate-slides.py`: Python script using Gemini API for image generation
  - `detect-figures.ts` / `extract-figure.ts`: PDF figure detection and extraction
  - `apply-template.ts`: Figure container templating for academic style
  - `merge-to-pptx.ts` / `merge-to-pdf.ts`: Output assembly
  - `references/`: Analysis framework, style specs, templates

## Essential Workflows

### 1. Paper-to-Slides (Academic Papers)

**Entry Point**: User provides PDF or markdown content

```bash
npx -y bun scripts/detect-figures.ts --pdf source-paper.pdf --output figures.json
# Outputs detected figures, tables, page numbers, captions
```

**Figure Mapping**: Automatically populate `IMAGE_SOURCE` blocks in outlines:
- Check `references/analysis-framework.md` Section 8 for mapping rules
- Architecture/pipeline figures → Methods slides (use `Source: extract`)
- Results tables/charts → Results slides (use `Source: extract`)
- Conceptual diagrams → Leave for AI generation (use `Source: generate`)

**Image Extraction**:
```bash
npx -y bun scripts/extract-figure.ts --pdf source-paper.pdf --page N --output figures/figure-N.png
npx -y bun scripts/apply-template.ts --figure figures/figure-N.png --title "Headline" --caption "Figure N: Caption" --output NN-slide-slug.png
```

**Fallback**: If extraction fails with "Image or Canvas expected", use PyMuPDF for page extraction.

### 2. Image Generation Method Selection

User chooses between two methods:

**Option 1: Gemini API (Recommended)**
- Requires: `GOOGLE_API_KEY` or `GEMINI_API_KEY` environment variable
- Command: `python scripts/generate-slides.py <slide-deck-dir> --model gemini-3-pro-image-preview`
- Auto-installs `google-genai` package
- Retry logic: 3 attempts with exponential backoff
- Feature: Skips slides >10KB (resumable)

**Option 2: Gemini Web (Reverse-engineered)**
- Requires: Chrome browser with logged-in Google account
- Run per-slide: `npx -y bun GEMINI_WEB_SKILL_DIR/scripts/main.ts --promptfiles prompts/01-slide-cover.md --image 01-slide-cover.png`
- Warning: May break; account risk
- Check consent at: `$APPDATA/baoyu-skills/gemini-web/consent.json`

### 3. Style Selection & Variants

**Auto-detection**: Check content for keywords (e.g., "paper" → `academic-paper`, "tutorial" → `sketch-notes`)

**Style Specifications**: Located in `references/styles/<style>.md` — each file contains:
- Color palette (primary, secondary, accent colors)
- Typography (fonts, sizes, weights for titles/body/captions)
- Layout patterns (spacing, grid, composition rules)
- Visual texture/effects (shadows, borders, patterns)
- Persona/tone descriptors for AI generation

**Key Styles**:
- `academic-paper`: Precise charts, citations allowed (`[1]`, `[Author et al., 2024]`), proper equation formatting, clean borders on tables, axis labels required on all charts
- `blueprint`: Default, technical schematics with grid texture, architectural diagrams, monochrome with blue accents
- `sketch-notes`: Hand-drawn, warm, educational, loose strokes, friendly colors, illustrated elements
- `corporate`: Navy/gold, structured layouts, professional photos allowed, bold typography
- `minimal`: Ultra-clean, maximum whitespace, sans-serif, high contrast, geometric shapes
- `bold-editorial`: Magazine style, large bold headlines, dark backgrounds, dramatic typography
- `chalkboard`: Black background, colorful chalk textures, hand-written feel
- `notion`: SaaS dashboard aesthetic, card-based layouts, soft colors, clean UI elements
- `dark-atmospheric`: Cinematic dark mode, glowing accents, moody colors, lighting effects
- `scientific`: Precise diagrams, proper axis/legend labels, accurate data visualization, notation symbols
- `vector-illustration`: Flat vectors, retro palette, cute/playful style
- `sketch-notes`: Hand-drawn warmth, friendly educational tone

## Project-Specific Conventions

### Outline Structure & Metadata

**File**: `outline.md` (after user selection from variants)

**Required Sections** (from `references/outline-template.md`):
- `# Outline`: Slide list with headlines
- `## STYLE_INSTRUCTIONS`: Full style specification (typography, colors, layouts)
- `// LAYOUT: <layout-name>`: Optional per-slide layout hint (e.g., `hub-spoke`, `split-screen`)
- `// IMAGE_SOURCE`: Metadata for extracted figures:
  ```
  Figure: 3
  Page: 14
  Caption: "System architecture diagram"
  Source: extract
  ```

### Prompt Structure

**File**: `prompts/NN-slide-*.md`

**Required Elements** (from `references/base-prompt.md`):
- Image specs: 16:9 aspect ratio, 4K size
- Style persona: "The Architect" (visual storyteller)
- Core rule: Hand-drawn quality (except `academic-paper` style)
- Academic exception: Precise diagrams, charts, equations for `academic-paper` style
- NO slide numbers, logos, or realistic photos

**Layout Integration**: If outline specifies `Layout: hub-spoke`, prompt must include:
- Visual description: "Central concept in middle with related items radiating outward"

### Output Directory Structure

```
slide-deck/{topic-slug}/
├── outline.md               # Final selected outline
├── prompts/                 # Per-slide prompts
│   ├── 01-slide-cover.md
│   ├── 02-slide-intro.md
│   └── NN-slide-slug.md
├── figures/                 # Extracted academic figures
│   ├── figure-1.png
│   └── figure-2.png
├── 01-slide-cover.png       # Generated slide images
├── 02-slide-intro.png
├── {topic-slug}.pptx        # Final outputs
└── {topic-slug}.pdf
```

**Slug Generation**: Extract 2-4 word topic in kebab-case (e.g., "intro-ml")

**Conflict Resolution**: If directory exists, append timestamp: `{slug}-YYYYMMDD-HHMMSS`

### Content Rules

**Check**: `references/content-rules.md` for:
- Self-explanatory slides (no verbal commentary needed)
- Logical flow for scrolling/sharing
- All necessary context within slides
- Social media optimization

### Slide Modification Workflow

**File**: `references/modification-guide.md`

**Operations**:
- **Edit**: Regenerate specific slide(s) by re-running image generation
- **Add**: Insert new prompt file, renumber slides
- **Delete**: Remove slide, renumber remaining
- **File naming**: Always use `NN-slide-<slug>.png` (NN = 2-digit zero-padded index)

## Critical Dependencies & Integration

### Python Dependencies (generate-slides.py)
- `google-genai`: Google Gemini API client (auto-installed)
- Python 3.8+

### TypeScript/Node Dependencies (scripts/package.json)
- `canvas`: Figure extraction and templating
- `pdfjs-dist`: PDF parsing (legacy build for Node.js)
- `pdf-lib`: PDF assembly
- `pptxgenjs`: PowerPoint generation
- **Fallback**: `pymupdf` (Python) for complex PDF page extraction

### Environment Variables
- `GOOGLE_API_KEY` or `GEMINI_API_KEY`: For Gemini API option
- `HTTP_PROXY` / `HTTPS_PROXY`: For restricted networks (prefix Gemini Web commands)

## Key Files & Their Roles

| File | Purpose |
|------|---------|
| `references/analysis-framework.md` | Core message, audience analysis, figure mapping rules |
| `references/outline-template.md` | Outline format, STYLE_INSTRUCTIONS structure |
| `references/base-prompt.md` | Image generation principles, style persona |
| `references/content-rules.md` | Content guidelines, slide structure |
| `references/modification-guide.md` | Edit/add/delete slide workflows |
| `references/figure-container-template.md` | Visual specs for extracted figure containers |
| `references/styles/` | Full style specifications (color, typography, layouts) |

## Style Specifications Guide

Each style file (`references/styles/<style>.md`) documents:
- **Palette**: Primary, secondary, accent colors with hex values
- **Typography**: Font families, sizes (titles 48-72px, body 24-32px), weights (bold/regular)
- **Layouts**: Grid structure, spacing rules, composition patterns
- **Effects**: Shadows, borders, textures, patterns, gradients
- **Constraints**: Unique rules (e.g., academic-paper prohibits hand-drawn elements)

### Style Selection Decision Tree

1. **Academic/Research Content** → `academic-paper`
   - Precise diagrams required, charts with accurate data, equation notation
   - Allow citations like "[1]", "[Smith et al., 2024]"
   - Tables with clean borders, proper axis labels

2. **Technical/Architecture** → `blueprint` (default)
   - System diagrams, flow charts, infrastructure
   - Grid textures, monochrome with blue accents
   - Geometric shapes, technical precision

3. **Educational/Tutorials** → `sketch-notes`
   - Step-by-step learning, conceptual explanations
   - Hand-drawn strokes, warm color palette
   - Friendly, approachable tone

4. **Executive/Business** → `corporate` or `minimal`
   - Business impact, ROI, strategic outcomes
   - Navy/gold or clean white/black contrast
   - Professional, high-impact typography

5. **Creative/Entertainment** → `dark-atmospheric`, `fantasy-animation`, `vector-illustration`
   - Storytelling, emotional engagement
   - Cinematic/artistic visual effects
   - Hand-drawn or flat vector styles

### When Extracting Academic Figures

**Always use** `academic-paper` style when:
- Source is peer-reviewed paper (PDF with figures)
- Figures are scientific diagrams, charts, or results
- Citations or mathematical notation present
- Precision and accuracy are critical

Apply template via `apply-template.ts` with:
```bash
npx -y bun scripts/apply-template.ts \
  --figure figures/figure-N.png \
  --title "Methods Overview" \
  --caption "Figure 2: System architecture from [1]" \
  --output NN-slide-methods.png
```

Caption should preserve original figure numbering and reference style from paper.

## Common Patterns & Anti-Patterns

✅ **Correct**: Use `Source: extract` for detected academic figures, apply-template.ts for templating

❌ **Wrong**: Regenerating academic figures with AI when extraction is available

✅ **Correct**: Maintain session ID across all slides for style consistency: `slides-{slug}-{timestamp}`

❌ **Wrong**: Regenerating individual slides without session ID changes style

✅ **Correct**: Per-slide layout hints via `// LAYOUT:` guide AI composition

❌ **Wrong**: Relying on AI to infer layout without explicit guidance

## Extension Points

**Custom Styles & Configurations**: Check for `EXTEND.md` at (priority order):
1. `.paper-skills/paper-slide-deck/EXTEND.md` (project)
2. `~/.paper-skills/paper-slide-deck/EXTEND.md` (user)

Loads before analysis step, overrides defaults.

## Debug Tips

- **Image generation failures**: Script auto-retries; re-run to skip completed (>10KB) slides
- **Figure extraction fails**: Try PyMuPDF fallback for complex PDFs
- **Style inconsistency**: Verify session ID is same for all slides
- **Missing layout effect**: Check outline specifies `// LAYOUT:` and prompt includes layout description
