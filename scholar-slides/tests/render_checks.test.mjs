// M6b deterministic render-geometry checks + M6a render-review gate (node --test).
// Pure logic: verify_slides feeds browser measurements into these; no Playwright needed here.
import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { voidFindings, figureFindings, buildFigMeta } from "../scripts/lib/render_checks.mjs";
import { renderReviewFindings } from "../scripts/qa_report.mjs";
import { LAYOUTS } from "../scripts/lib/layouts.mjs";
import { renderTable } from "../scripts/lib/table.mjs";

// ---- voidFindings ----------------------------------------------------------

test("voidFindings flags a top-clustered slide (vertical void)", () => {
  const f = voidFindings({ layout: "results-table", hasBody: true, bodyBottom: 620, bodyRight: 1500 });
  assert.equal(f.length, 1);
  assert.equal(f[0].check, "vertical-void");
  assert.equal(f[0].severity, "P3");
});

test("voidFindings flags a half-canvas slide (horizontal void)", () => {
  const f = voidFindings({ layout: "critique-concerns", hasBody: true, bodyBottom: 960, bodyRight: 1100 });
  assert.equal(f.length, 1);
  assert.equal(f[0].check, "horizontal-void");
});

test("voidFindings passes a well-filled slide and exempts deliberate-whitespace layouts", () => {
  assert.equal(voidFindings({ layout: "bullets", hasBody: true, bodyBottom: 820, bodyRight: 1400 }).length, 0);
  // covers/sections/equations/references compose around whitespace on purpose
  for (const layout of ["paper-title", "section", "equation", "references"]) {
    assert.equal(voidFindings({ layout, hasBody: true, bodyBottom: 400, bodyRight: 900 }).length, 0, layout);
  }
  // a slide with no measurable body must not crash or fire
  assert.equal(voidFindings({ layout: "bullets", hasBody: false, bodyBottom: 0, bodyRight: 0 }).length, 0);
});

// ---- figureFindings --------------------------------------------------------

test("figureFindings: exact path — source font projects below the legibility floor", () => {
  // crop bbox 400pt wide, smallest embedded text 6pt, displayed 780px wide:
  // projected = 6 * 780/400 = 11.7px < 12px floor -> P2
  const meta = new Map([["figure-7", { minFontPt: 6, bboxWpt: 400 }]]);
  const f = figureFindings(
    [{ src: "figures/figure-7.png", ok: true, inFigure: true, rendered: 780, natural: 2400 }],
    meta
  );
  assert.equal(f.length, 1);
  assert.equal(f[0].check, "figure-text-illegible");
  assert.equal(f[0].severity, "P2");
});

test("figureFindings: exact path passes when the same figure is displayed large enough", () => {
  const meta = new Map([["figure-7", { minFontPt: 6, bboxWpt: 400 }]]);
  const f = figureFindings(
    [{ src: "figures/figure-7.png", ok: true, inFigure: true, rendered: 1400, natural: 2400 }],
    meta
  );
  assert.equal(f.length, 0);
});

test("figureFindings: fallback heuristic — big crop squeezed below scale floor", () => {
  const f = figureFindings(
    [{ src: "figures/figure-2.png", ok: true, inFigure: true, rendered: 700, natural: 2400 }],
    new Map()
  );
  assert.equal(f.length, 1);
  assert.equal(f[0].check, "figure-compressed");
});

test("figureFindings: fallback ignores small sources, non-figure imgs, broken imgs", () => {
  const imgs = [
    { src: "figures/small.png", ok: true, inFigure: true, rendered: 600, natural: 1200 }, // small source
    { src: "logo.png", ok: true, inFigure: false, rendered: 100, natural: 2000 },          // not in .s-figure
    { src: "figures/broken.png", ok: false, inFigure: true, rendered: 0, natural: 0 },     // broken (P1 elsewhere)
  ];
  assert.equal(figureFindings(imgs, new Map()).length, 0);
});

test("buildFigMeta maps figures.json ids to min-font + bbox shape + panel count", () => {
  const meta = buildFigMeta([
    { id: "figure-7", figure_bbox: [100, 50, 500, 300], min_font_pt: 6.5 },
    { id: "figure-9", figure_bbox: null, min_font_pt: null },   // unlocalized: skipped
    { id: "table-1", figure_bbox: [0, 0, 100, 50] },            // no min_font_pt: heuristic-only entry
  ]);
  assert.deepEqual(meta.get("figure-7"), { minFontPt: 6.5, bboxWpt: 400, bboxHpt: 250, panels: 0 });
  assert.equal(meta.has("figure-9"), false);
  assert.deepEqual(meta.get("table-1"), { minFontPt: null, bboxWpt: 100, bboxHpt: 50, panels: 0 });
});

// ---- renderReviewFindings (M6a gate) ----------------------------------------

function tmpDeckDir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), "ss-aes-"));
}

test("renderReviewFindings nudges (P3) when the rubric loop never ran", () => {
  const dir = tmpDeckDir();
  const f = renderReviewFindings(dir);
  assert.equal(f.length, 1);
  assert.equal(f[0].check, "aesthetics-not-run");
  assert.equal(f[0].severity, "P3");
});

test("renderReviewFindings blocks-for-review (P2) while rework slides remain open", () => {
  const dir = tmpDeckDir();
  fs.writeFileSync(path.join(dir, "aesthetics_report.json"), JSON.stringify({
    mean: 20.5,
    slides: [{ slide: 7, total: 17 }],
    rework: [{ slide: 7, reason: "figures 2" }, { slide: 11, reason: "figures 2" }],
  }));
  const f = renderReviewFindings(dir);
  assert.equal(f.length, 1);
  assert.equal(f[0].check, "aesthetics-rework-open");
  assert.equal(f[0].severity, "P2");
  assert.match(f[0].detail, /7, 11/);
});

test("renderReviewFindings is silent when the loop ran and spent the rework list", () => {
  const dir = tmpDeckDir();
  fs.writeFileSync(path.join(dir, "aesthetics_report.json"),
    JSON.stringify({ mean: 22.1, slides: [{ slide: 1, total: 22 }], rework: [] }));
  assert.equal(renderReviewFindings(dir).length, 0);
});

test("renderReviewFindings reports an unreadable report as P2, never throws", () => {
  const dir = tmpDeckDir();
  fs.writeFileSync(path.join(dir, "aesthetics_report.json"), "not json {");
  const f = renderReviewFindings(dir);
  assert.equal(f.length, 1);
  assert.equal(f[0].check, "aesthetics-report-invalid");
  assert.equal(f[0].severity, "P2");
});

// ---- M7 layout changes -------------------------------------------------------

test("references render single-column below 4 entries, two-column at 4+", () => {
  const few = LAYOUTS.references({ layout: "references", title: "References", entries: ["a", "b"] });
  assert.match(few, /<ol class="single">/);
  const many = LAYOUTS.references({ layout: "references", title: "References", entries: ["a", "b", "c", "d"] });
  assert.doesNotMatch(many, /class="single"/);
});

test("small tables render roomy (bigger type), wide/long tables stay compact", () => {
  const small = renderTable({ columns: ["m", "a", "b"], rows: [["x", "1", "2"], ["y", "3", "4"]] });
  assert.match(small, /<table class="results roomy">/);
  const long = renderTable({
    columns: ["m", "a", "b"],
    rows: Array.from({ length: 8 }, (_, i) => [`r${i}`, "1", "2"]),
  });
  assert.match(long, /<table class="results">/);
  const wide = renderTable({ columns: ["m", "a", "b", "c", "d", "e"], rows: [["x", "1", "2", "3", "4", "5"]] });
  assert.match(wide, /<table class="results">/);
});
