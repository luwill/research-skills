// M8 figure levers: PNG size probe, true-wide width-driven sizing, hero figure mode,
// and the stale-crop-metadata guard for the QA legibility projection (node --test).
import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { probeImageSize } from "../scripts/lib/img_size.mjs";
import { renderFigure } from "../scripts/lib/figure.mjs";
import { LAYOUTS, validateSpec, renderSlide } from "../scripts/lib/layouts.mjs";
import { figureFindings, buildFigMeta } from "../scripts/lib/render_checks.mjs";

// Minimal valid-enough PNG: signature + IHDR with the given dimensions.
function pngBytes(w, h) {
  const buf = Buffer.alloc(33);
  Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]).copy(buf, 0);
  buf.writeUInt32BE(13, 8);
  buf.write("IHDR", 12);
  buf.writeUInt32BE(w, 16);
  buf.writeUInt32BE(h, 20);
  return buf;
}

function tmpPng(w, h) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ss-img-"));
  const p = path.join(dir, "figures", "fig.png");
  fs.mkdirSync(path.dirname(p));
  fs.writeFileSync(p, pngBytes(w, h));
  return { dir, rel: "figures/fig.png" };
}

// ---- probeImageSize ---------------------------------------------------------

test("probeImageSize reads PNG IHDR dimensions", () => {
  const { dir, rel } = tmpPng(1757, 534);
  assert.deepEqual(probeImageSize(path.join(dir, rel)), { w: 1757, h: 534 });
});

test("probeImageSize returns null for missing or non-PNG files", () => {
  assert.equal(probeImageSize("/nonexistent/x.png"), null);
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "ss-img-"));
  const p = path.join(dir, "not-a-png.png");
  fs.writeFileSync(p, "just text");
  assert.equal(probeImageSize(p), null);
});

// ---- true-wide sizing (build-time class) -------------------------------------

test("renderFigure classes a >=2.2 aspect crop as wide and passes its ratio to CSS", () => {
  const { dir, rel } = tmpPng(1757, 534); // ar 3.29
  const html = renderFigure({ src: rel, caption: "c" }, { baseDir: dir });
  assert.match(html, /class="wide"/);
  assert.match(html, /--fig-ar:3\.29/);
});

test("renderFigure leaves normal-aspect crops and ctx-less renders untouched", () => {
  const { dir, rel } = tmpPng(1750, 987); // ar 1.77
  assert.doesNotMatch(renderFigure({ src: rel }, { baseDir: dir }), /wide/);
  assert.doesNotMatch(renderFigure({ src: "figures/none.png" }), /wide/); // no ctx -> no probe
});

// ---- hero figure mode ---------------------------------------------------------

test("hero folds the caption into the footer and modifies the section class", () => {
  const s = {
    layout: "assertion-evidence",
    action_title: "T",
    figure: { src: "figures/none.png", caption: "Fig. 7 | Modes.", cite: "GLM-5 Team 2026", hero: true },
    source_ref: "§3.1",
  };
  const html = LAYOUTS["assertion-evidence"](s, {});
  assert.match(html, /s-ae--hero/);
  assert.doesNotMatch(html, /<figcaption>/);                    // no caption row above the fold
  assert.match(html, /s-source[^>]*>.*Fig\. 7 \| Modes\./);     // caption text lives in the footer
  assert.match(html, /§3\.1/);                                  // provenance kept
});

test("a non-hero figure keeps its figcaption (regression)", () => {
  const s = { layout: "assertion-evidence", action_title: "T",
    figure: { src: "figures/none.png", caption: "Fig. 1" }, source_ref: "§1" };
  assert.match(LAYOUTS["assertion-evidence"](s, {}), /<figcaption>/);
});

test("validateSpec rejects hero + annotation (the budget the mode exists to reclaim)", () => {
  const deck = { slides: [{ layout: "assertion-evidence", action_title: "T",
    figure: { src: "f.png", hero: true }, annotation: "text", source_ref: "x" }] };
  const errs = validateSpec(deck).filter((p) => p.severity === "error");
  assert.equal(errs.length, 1);
  assert.match(errs[0].detail, /hero/);
});

test("renderSlide threads ctx to the layout renderers", () => {
  const { dir, rel } = tmpPng(2400, 600); // ar 4
  const html = renderSlide(
    { layout: "assertion-evidence", action_title: "T", figure: { src: rel }, source_ref: "x" },
    { baseDir: dir }
  );
  assert.match(html, /class="wide"/);
});

// ---- stale-crop-metadata guard + panel suggestion -----------------------------

test("figureFindings skips the exact path when the crop no longer matches the bbox shape", () => {
  // bbox 398x514pt (portrait) but the shipped crop is a 1855x1030 manual re-crop (landscape):
  // projecting min_font_pt against the wrong bbox width lies, so fall back to the heuristic.
  const meta = buildFigMeta([{ id: "figure-1", figure_bbox: [108, 161, 506, 675], min_font_pt: 4.2 }]);
  const f = figureFindings(
    [{ src: "figures/figure-1.png", ok: true, inFigure: true, rendered: 855, natural: 1855, naturalH: 1030 }],
    meta
  );
  // heuristic: 855/1855 = 46% > 45% floor -> no finding (and crucially no bogus exact projection)
  assert.equal(f.length, 0);
});

test("figureFindings suggests panel crops when detect_figures found labeled panels", () => {
  const meta = buildFigMeta([{
    id: "figure-3", figure_bbox: [0, 0, 400, 200], min_font_pt: 5,
    panels: [{ label: "a" }, { label: "b" }, { label: "c" }],
  }]);
  const f = figureFindings(
    [{ src: "figures/figure-3.png", ok: true, inFigure: true, rendered: 700, natural: 1600, naturalH: 800 }],
    meta
  );
  assert.equal(f.length, 1);
  assert.equal(f[0].check, "figure-text-illegible");
  assert.match(f[0].detail, /3 labeled panels/);
});
