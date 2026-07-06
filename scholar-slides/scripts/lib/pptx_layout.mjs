// Pure helpers for spec -> PowerPoint mapping. The deck.json spec drives native pptxgenjs
// shapes (editable text + real OOXML tables + images + speaker notes); equations are the only
// rasterized element (rendered to image), which the exporter flags as a fidelity degradation.

export const PPT_W = 13.333; // inches, 16:9
export const PPT_H = 7.5;

export const inX = (px) => +((px / 1920) * PPT_W).toFixed(3);
export const inY = (px) => +((px / 1080) * PPT_H).toFixed(3);

import { stripEmphasis } from "./emphasis.mjs";

const MATH_RE = /\$\$([\s\S]+?)\$\$|\$([^$\n]+?)\$/g;

// PPTX text boxes can't render LaTeX or our emphasis spans; keep the inner words as literal text
// (degraded but faithful). Strips inline math delimiters and emphasis markers so a native run
// never shows literal `$...$` or `==...==`. verify_pptx_parity.norm() mirrors this.
export function stripInlineMath(text) {
  if (text == null) return "";
  return stripEmphasis(String(text).replace(MATH_RE, (_m, a, b) => (a != null ? a : b)));
}

// Convert a table spec to pptxgenjs rows (native, editable OOXML table). Units go in the header;
// best-per-column cells stay bold + accent; the row-header column is left-aligned.
export function tableRows(t) {
  if (!t || !Array.isArray(t.columns) || !Array.isArray(t.rows)) {
    throw new Error("tableRows: needs {columns, rows}");
  }
  const header = t.columns.map((c) => ({
    text: (c.label ?? c) + (c.unit ? ` (${c.unit})` : ""),
    options: { bold: true, align: "center", fill: { color: "EEF2F7" } },
  }));
  const body = (t.rows || []).map((r) =>
    r.map((cell, ci) => {
      const v = cell && typeof cell === "object" ? cell.v : cell;
      const bold = cell && typeof cell === "object" ? !!cell.bold : false;
      const options = { align: t.row_header && ci === 0 ? "left" : "right" };
      if (bold) { options.bold = true; options.color = "15497A"; }
      return { text: String(v ?? ""), options };
    })
  );
  return { rows: [header, ...body], colCount: t.columns.length };
}

export function collectEquations(deck) {
  const out = [];
  (deck.slides || []).forEach((s, i) => {
    (s.equations || []).forEach((e, j) => out.push({ slide: i, eq: j, latex: e.latex, num: e.num, numbered: e.numbered }));
  });
  return out;
}
