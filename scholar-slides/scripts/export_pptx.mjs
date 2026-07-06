#!/usr/bin/env node
// Editable PPTX export: deck.json -> native PowerPoint via pptxgenjs.
// Editable: titles, bullets, tables (real OOXML), and speaker notes are native shapes/text.
// Rasterized (the honest degradation, flagged): figures are images (they already are), and
// equations are rendered to transparent PNGs (KaTeX). No factual content is fabricated.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import pptxgen from "pptxgenjs";
import katex from "katex";
import { inX, inY, stripInlineMath, tableRows, collectEquations } from "./lib/pptx_layout.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, "..");
const KATEX_CSS = path.join(ROOT, "node_modules/katex/dist/katex.min.css");

const ACCENT = "15497A", INK = "1A1D21", INK_SOFT = "515860", RULE = "D7DBE0";
const SERIF = "Georgia", SANS = "Arial";

async function renderEquationPNGs(equations, outDir) {
  const map = new Map();
  if (!equations.length) return map;
  fs.mkdirSync(outDir, { recursive: true });
  // Equations need Chromium to rasterize KaTeX. If it (or its browser binary) is unavailable,
  // degrade THIS content only — every other slide still exports natively and a PPTX is still
  // produced, with a clear warning — rather than aborting the whole export.
  let browser;
  try {
    const { chromium } = await import("playwright");
    browser = await chromium.launch();
  } catch (e) {
    console.warn(`WARN: equation rendering skipped (no Chromium: ${e.message}). ` +
      `${equations.length} equation slide(s) will export without the equation image — ` +
      `run \`npx playwright install chromium\` and re-export for full fidelity.`);
    return map;
  }
  try {
    const page = await browser.newPage({ deviceScaleFactor: 3 });
    for (const e of equations) {
      const inner = katex.renderToString(String(e.latex ?? ""), { displayMode: true, throwOnError: false, output: "html" });
      const html = `<!doctype html><html><head><meta charset="utf-8">
        <link rel="stylesheet" href="${pathToFileURL(KATEX_CSS).href}">
        <style>html,body{margin:0;background:transparent}#eq{display:inline-block;padding:10px 16px;font-size:34px;color:#1a1d21}</style>
        </head><body><div id="eq">${inner}</div></body></html>`;
      await page.setContent(html, { waitUntil: "networkidle" });
      const el = await page.$("#eq");
      const box = el && (await el.boundingBox());
      if (!el || !box) continue; // guard: skip an equation that failed to lay out, keep exporting
      const out = path.join(outDir, `eq-${e.slide}-${e.eq}.png`);
      await el.screenshot({ path: out, omitBackground: true });
      map.set(`${e.slide}-${e.eq}`, { path: out, w: box.width, h: box.height });
    }
  } finally {
    await browser.close();
  }
  return map;
}

function titleBar(slide, s) {
  let y = 0.5;
  if (s.eyebrow) {
    slide.addText(String(s.eyebrow).toUpperCase(), { x: 0.67, y: 0.42, w: 12, h: 0.3, fontSize: 11, bold: true, color: ACCENT, charSpacing: 2, fontFace: SANS });
    y = 0.78;
  }
  slide.addText(stripInlineMath(s.action_title || s.title || ""), { x: 0.67, y, w: 12, h: 1.0, fontSize: 24, bold: true, color: INK, fontFace: SERIF, valign: "top" });
  slide.addShape("rect", { x: 0.67, y: 1.78, w: 12, h: 0.028, fill: { color: ACCENT } });
}

function sourceLine(slide, s) {
  if (s.source_ref) slide.addText(String(s.source_ref), { x: 0.67, y: 7.05, w: 12, h: 0.3, fontSize: 10, italic: true, color: INK_SOFT, fontFace: SANS });
}

function bulletText(points) {
  return (points || []).map((p) => ({ text: stripInlineMath(p), options: { bullet: { indent: 18 }, paraSpaceAfter: 10, breakLine: true } }));
}

function figurePath(deckJsonDir, src) {
  return path.resolve(deckJsonDir, src);
}

function buildSlide(pptx, slide, s, ctx) {
  slide.background = { color: "FFFFFF" };
  const L = s.layout;

  if (L === "paper-title") {
    slide.addText(stripInlineMath(s.title || ""), { x: 0.67, y: 1.9, w: 12, h: 2.2, fontSize: 34, bold: true, color: INK, fontFace: SERIF, valign: "top" });
    const meta = [];
    if (s.authors) meta.push({ text: Array.isArray(s.authors) ? s.authors.join(", ") : s.authors, options: { fontSize: 16, color: INK, breakLine: true, paraSpaceAfter: 6 } });
    if (s.affiliation) meta.push({ text: s.affiliation, options: { fontSize: 13, color: INK_SOFT, breakLine: true } });
    if (s.venue) meta.push({ text: s.venue, options: { fontSize: 13, color: ACCENT, bold: true, breakLine: true, paraSpaceBefore: 8 } });
    if (s.presenter) meta.push({ text: s.presenter, options: { fontSize: 12, color: INK_SOFT, breakLine: true, paraSpaceBefore: 10 } });
    if (meta.length) slide.addText(meta, { x: 0.67, y: 4.3, w: 12, h: 2.4, fontFace: SANS, valign: "top" });
    return;
  }
  if (L === "section") {
    if (s.num) slide.addText(String(s.num), { x: 0.67, y: 2.6, w: 12, h: 0.7, fontSize: 22, color: ACCENT, fontFace: SERIF });
    slide.addText(stripInlineMath(s.title || ""), { x: 0.67, y: 3.2, w: 12, h: 1.6, fontSize: 40, bold: true, color: INK, fontFace: SERIF });
    return;
  }

  titleBar(slide, s);

  if (L === "bullets") {
    slide.addText(bulletText(s.points), { x: 0.9, y: 2.05, w: 11.5, h: 4.7, fontSize: 17, color: INK, fontFace: SANS, valign: "top" });
  } else if (L === "outline-agenda") {
    const items = (s.items || []).map((it, i) => ({ text: `${String(i + 1).padStart(2, "0")}   ${stripInlineMath(it)}`, options: { color: i === s.current ? ACCENT : INK, fontSize: 20, breakLine: true, paraSpaceAfter: 12 } }));
    slide.addText(items, { x: 0.9, y: 2.1, w: 11.5, h: 4.6, fontFace: SANS, valign: "top" });
  } else if (L === "assertion-evidence") {
    if (s.figure) {
      const p = figurePath(ctx.deckJsonDir, s.figure.src);
      if (fs.existsSync(p)) slide.addImage({ path: p, x: 2.0, y: 1.95, w: 9.3, h: 4.0, sizing: { type: "contain", w: 9.3, h: 4.0 } });
      const cap = (s.figure.caption || "") + (s.figure.cite ? ` [${s.figure.cite}]` : "");
      if (cap.trim()) slide.addText(cap, { x: 1.0, y: 6.05, w: 11.3, h: 0.4, fontSize: 11, color: INK_SOFT, align: "center", fontFace: SANS });
    }
    if (s.annotation) slide.addText(stripInlineMath(s.annotation), { x: 0.9, y: 6.45, w: 11.5, h: 0.5, fontSize: 13, color: INK, fontFace: SANS, fill: { color: "EEF2F7" }, valign: "middle" });
    sourceLine(slide, s);
  } else if (L === "equation") {
    let y = 2.4;
    (s.equations || []).forEach((e, j) => {
      const img = ctx.eqMap.get(`${ctx.index}-${j}`);
      if (img) {
        const maxW = 9.0, maxH = 1.8;
        const ar = img.w / img.h;
        let w = maxW, h = w / ar;
        if (h > maxH) { h = maxH; w = h * ar; }
        slide.addImage({ path: img.path, x: (13.333 - w) / 2, y, w, h });
        if (e.numbered) slide.addText(`(${e.num || j + 1})`, { x: 11.0, y: y + h / 2 - 0.15, w: 1.5, h: 0.3, fontSize: 12, color: INK_SOFT, fontFace: SANS });
        y += h + 0.3;
      }
    });
    if (s.note) slide.addText(stripInlineMath(s.note), { x: 1.5, y: y + 0.1, w: 10.3, h: 0.8, fontSize: 14, color: INK_SOFT, align: "center", fontFace: SANS });
    sourceLine(slide, s);
  } else if (L === "results-table") {
    const { rows } = tableRows(s.table);
    if (s.table.caption) slide.addText(String(s.table.caption), { x: 0.9, y: 1.95, w: 11.5, h: 0.35, fontSize: 12, color: INK_SOFT, fontFace: SANS });
    slide.addTable(rows, { x: 1.4, y: 2.45, w: 10.5, fontSize: 13, fontFace: SANS, color: INK, valign: "middle", border: { type: "solid", pt: 0.5, color: RULE }, align: "right" });
    if (s.table.footnote) slide.addText(String(s.table.footnote), { x: 0.9, y: 6.6, w: 11.5, h: 0.3, fontSize: 10, italic: true, color: INK_SOFT, fontFace: SANS });
    sourceLine(slide, s);
  } else if (L === "two-column") {
    if (s.points) slide.addText(bulletText(s.points), { x: 0.9, y: 2.05, w: 5.6, h: 4.5, fontSize: 16, color: INK, fontFace: SANS, valign: "top" });
    else if (s.text) slide.addText(stripInlineMath(s.text), { x: 0.9, y: 2.05, w: 5.6, h: 4.5, fontSize: 16, color: INK, fontFace: SANS, valign: "top" });
    if (s.figure) {
      const p = figurePath(ctx.deckJsonDir, s.figure.src);
      if (fs.existsSync(p)) slide.addImage({ path: p, x: 6.9, y: 2.05, w: 5.5, h: 4.4, sizing: { type: "contain", w: 5.5, h: 4.4 } });
    } else if (s.points2) slide.addText(bulletText(s.points2), { x: 6.9, y: 2.05, w: 5.6, h: 4.5, fontSize: 16, color: INK, fontFace: SANS, valign: "top" });
    sourceLine(slide, s);
  } else if (L === "critique-concerns") {
    const runs = [];
    (s.points || []).forEach((p) => {
      runs.push({ text: stripInlineMath(p.head) + "  ", options: { bold: true, color: ACCENT, fontSize: 16, breakLine: false } });
      runs.push({ text: stripInlineMath(p.body), options: { color: INK, fontSize: 13, breakLine: true, paraSpaceAfter: 10 } });
    });
    slide.addText(runs, { x: 0.9, y: 2.0, w: 11.5, h: 4.9, fontFace: SANS, valign: "top" });
  } else if (L === "discussion-questions") {
    const qs = (s.questions || []).map((q) => ({ text: stripInlineMath(q), options: { bullet: { characterCode: "003F" }, fontSize: 19, color: INK, breakLine: true, paraSpaceAfter: 16, indent: 22 } }));
    slide.addText(qs, { x: 1.0, y: 2.2, w: 11.3, h: 4.4, fontFace: SANS, valign: "top" });
  } else if (L === "references") {
    const refs = (s.entries || []).map((e) => ({ text: stripInlineMath(e), options: { fontSize: 12, color: INK, breakLine: true, paraSpaceAfter: 8 } }));
    slide.addText(refs, { x: 0.9, y: 2.05, w: 11.5, h: 4.6, fontFace: SANS, valign: "top" });
  }
}

export async function exportPptx(deckJsonPath, outPath) {
  const deckJsonDir = path.dirname(deckJsonPath);
  const deck = JSON.parse(fs.readFileSync(deckJsonPath, "utf-8"));
  const equations = collectEquations(deck);
  const eqMap = await renderEquationPNGs(equations, path.join(deckJsonDir, "pptx_assets"));

  const pptx = new pptxgen();
  pptx.defineLayout({ name: "S16x9", width: 13.333, height: 7.5 });
  pptx.layout = "S16x9";
  pptx.author = "scholar-slides";
  pptx.title = deck.meta?.title || "scholar-slides";

  (deck.slides || []).forEach((s, i) => {
    const slide = pptx.addSlide();
    buildSlide(pptx, slide, s, { deckJsonDir, eqMap, index: i });
    if (s.speaker_notes) slide.addNotes(String(s.speaker_notes));
  });

  const out = outPath || path.join(deckJsonDir, "deck.pptx");
  await pptx.writeFile({ fileName: out });

  const nFig = (deck.slides || []).filter((s) => s.figure).length;
  return { out, nSlides: (deck.slides || []).length, nEquationsRasterized: equations.length, nFigures: nFig };
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const deckJson = process.argv[2];
  const outPath = process.argv[3];
  if (!deckJson) { console.error("usage: export_pptx.mjs <deck.json> [out.pptx]"); process.exit(1); }
  exportPptx(deckJson, outPath).then((r) => {
    console.log(`PPTX -> ${r.out}  (${r.nSlides} slides)`);
    console.log("Editable: titles, bullets, tables, and speaker notes are native PowerPoint text/shapes.");
    console.log(`Rasterized (fidelity note): ${r.nFigures} figure image(s)` + (r.nEquationsRasterized ? `, ${r.nEquationsRasterized} equation(s) rendered to image` : "") + " — edit the deck.json + reveal/PDF version for those.");
  }).catch((e) => { console.error(e); process.exit(1); });
}
