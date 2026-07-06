// Stage 5 PPTX-layout pure-logic tests (node --test tests/pptx.test.mjs)
import { test } from "node:test";
import assert from "node:assert/strict";
import { inX, inY, stripInlineMath, tableRows, collectEquations, PPT_W, PPT_H } from "../scripts/lib/pptx_layout.mjs";

test("px->inch mapping spans the 16:9 stage", () => {
  assert.equal(inX(0), 0);
  assert.equal(inX(1920), PPT_W);
  assert.equal(inY(1080), PPT_H);
  assert.ok(Math.abs(inX(960) - PPT_W / 2) < 0.01);
});

test("stripInlineMath keeps the LaTeX inner as text", () => {
  assert.equal(stripInlineMath("scaled by $1/\\sqrt{d_k}$ here"), "scaled by 1/\\sqrt{d_k} here");
  assert.equal(stripInlineMath(null), "");
});

test("tableRows builds native rows: header bold+units, best bold, row-header left", () => {
  const { rows, colCount } = tableRows({
    columns: [{ label: "Model" }, { label: "BLEU", unit: "EN-DE" }],
    row_header: true,
    rows: [["Transformer", { v: "28.4", bold: true }]],
  });
  assert.equal(colCount, 2);
  assert.equal(rows[0][1].text, "BLEU (EN-DE)"); // unit folded into header
  assert.equal(rows[0][1].options.bold, true);
  assert.equal(rows[1][0].options.align, "left"); // row header
  assert.equal(rows[1][1].text, "28.4");
  assert.equal(rows[1][1].options.bold, true); // best bolded
  assert.equal(rows[1][1].options.align, "right");
});

test("tableRows rejects malformed input", () => {
  assert.throws(() => tableRows({ columns: [] }), /needs/);
});

test("collectEquations finds every equation with its slide index", () => {
  const eqs = collectEquations({
    slides: [{ layout: "bullets" }, { layout: "equation", equations: [{ latex: "a=b", numbered: true, num: "1" }] }],
  });
  assert.equal(eqs.length, 1);
  assert.equal(eqs[0].slide, 1);
  assert.equal(eqs[0].latex, "a=b");
});
