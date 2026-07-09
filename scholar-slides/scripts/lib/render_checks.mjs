// render_checks.mjs — deterministic render-geometry checks (aesthetics program M6b).
// These operationalize the mechanical half of the aesthetics rubric
// (references/aesthetics-review.md): canvas voids and figure legibility. The 6-dimension
// judgment loop stays a model task; everything here is pure arithmetic on measurements
// that verify_slides.mjs takes in the browser, so it is testable without Playwright.

export const STAGE = { w: 1920, h: 1080 };

// Layouts whose sparse or centered composition is deliberate (cover, dividers, a lone
// equation, a short reference list) — whitespace there is design, not a defect.
const VOID_EXEMPT = new Set(["paper-title", "section", "equation", "references", "assertion-evidence"]);

/**
 * Canvas-void nudges for one slide.
 * @param {{layout: string, hasBody: boolean, bodyBottom: number, bodyRight: number}} slide
 *   bodyBottom / bodyRight: extent of the .s-body content (stage px, footer excluded).
 */
export function voidFindings(slide, { vGap = 400, hFrac = 0.62 } = {}) {
  const out = [];
  if (!slide.hasBody || VOID_EXEMPT.has(slide.layout)) return out;
  const gap = STAGE.h - slide.bodyBottom;
  if (gap > vGap) {
    out.push({ check: "vertical-void", severity: "P3",
      detail: `body content ends ${Math.round(gap)}px above the stage bottom — rebalance the slide or move detail up from speaker notes` });
  }
  if (slide.bodyRight < hFrac * STAGE.w) {
    out.push({ check: "horizontal-void", severity: "P3",
      detail: `body content reaches only ${Math.round((100 * slide.bodyRight) / STAGE.w)}% of the stage width — use the full canvas` });
  }
  return out;
}

/**
 * Figure-legibility findings for one slide's <img> measurements.
 * Exact path (trustworthy crop metadata): the smallest source text projects to
 *   min_font_pt * rendered_px / bbox_pt_width  on-slide pixels — DPI cancels out.
 * The metadata is only trusted when the shipped crop still has the bbox's shape: a manual
 * re-crop (different aspect) would make the projection lie, so it falls back to the
 * heuristic — a large source displayed far below its native pixels is likely illegible.
 * When detect_figures found labeled sub-panels, the finding says so (crop ONE panel).
 * @param {Array<{src, ok, inFigure, rendered, natural, naturalH?}>} imgs
 * @param {Map<string, {minFontPt?, bboxWpt, bboxHpt, panels}>} figMeta keyed by crop basename (no ext)
 */
export function figureFindings(imgs, figMeta = new Map(), {
  minProjectedPx = 12, compressScale = 0.45, minNaturalW = 1600, arTolerance = 0.2 } = {}) {
  const out = [];
  for (const im of imgs || []) {
    if (!im.inFigure || !im.ok || !im.rendered) continue;
    const meta = figMeta.get(cropKey(im.src));
    const panelHint = meta?.panels >= 3
      ? ` (${meta.panels} labeled panels in figures.json — crop ONE via crop_figure.py)` : "";
    let cropMatchesBbox = true;
    if (meta && im.naturalH > 0) {
      const cropAr = im.natural / im.naturalH;
      const bboxAr = meta.bboxWpt / meta.bboxHpt;
      cropMatchesBbox = Math.abs(cropAr - bboxAr) <= arTolerance * bboxAr;
    }
    if (meta?.minFontPt && cropMatchesBbox) {
      const projected = meta.minFontPt * (im.rendered / meta.bboxWpt);
      if (projected < minProjectedPx) {
        out.push({ check: "figure-text-illegible", severity: "P2",
          detail: `smallest text in ${cropKey(im.src)} projects to ~${projected.toFixed(1)}px on the stage (< ${minProjectedPx}px floor) — enlarge the figure, crop one panel, or redraw natively${panelHint}` });
      }
    } else if (im.natural >= minNaturalW && im.rendered / im.natural < compressScale) {
      out.push({ check: "figure-compressed", severity: "P2",
        detail: `${cropKey(im.src)} displayed at ${Math.round((100 * im.rendered) / im.natural)}% of its ${im.natural}px source — embedded labels are likely illegible; enlarge, crop one panel, or redraw natively${panelHint}` });
    }
  }
  return out;
}

/** figures.json entries -> Map(crop basename -> {minFontPt?, bboxWpt, bboxHpt, panels}). */
export function buildFigMeta(figures) {
  const meta = new Map();
  for (const f of figures || []) {
    if (!f?.id || !Array.isArray(f.figure_bbox)) continue;
    const w = f.figure_bbox[2] - f.figure_bbox[0];
    const h = f.figure_bbox[3] - f.figure_bbox[1];
    if (w <= 0 || h <= 0) continue;
    meta.set(f.id, {
      minFontPt: f.min_font_pt > 0 ? f.min_font_pt : null,
      bboxWpt: w, bboxHpt: h,
      panels: Array.isArray(f.panels) ? f.panels.length : 0,
    });
  }
  return meta;
}

function cropKey(src) {
  const base = String(src || "").split("/").pop() || "";
  return base.replace(/\.[a-z0-9]+$/i, "");
}
