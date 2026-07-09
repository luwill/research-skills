// Stage 2 deck-builder unit tests (run with: node --test tests/deck.test.mjs)
import { test } from "node:test";
import assert from "node:assert/strict";
import { escapeHtml } from "../scripts/lib/escape.mjs";
import { renderMath, renderText } from "../scripts/lib/math.mjs";
import { renderTable } from "../scripts/lib/table.mjs";
import { renderFigure } from "../scripts/lib/figure.mjs";
import { renderSlide, REGISTERED, validateSpec } from "../scripts/lib/layouts.mjs";
import { buildHtml } from "../scripts/build_deck.mjs";

test("validateSpec catches an unknown layout with a clear message", () => {
  const p = validateSpec({ slides: [{ layout: "megachart", title: "x" }] });
  assert.equal(p.length, 1);
  assert.match(p[0].detail, /megachart/);
  assert.match(p[0].detail, /paper-title/); // lists the registered set
});

test("validateSpec flags a required field that is missing or empty (not a silent drop)", () => {
  const p = validateSpec({ slides: [
    { layout: "bullets", action_title: "T" },                 // no points
    { layout: "discussion-questions", questions: [] },        // empty
    { layout: "results-table" },                              // no table
  ] });
  const keys = p.filter((x) => x.severity === "error").map((x) => `${x.slide}:${x.field}`);
  assert.deepEqual(keys, ["1:points", "2:questions", "3:table"]);
});

test("validateSpec passes a well-formed deck", () => {
  assert.deepEqual(validateSpec({ slides: [
    { layout: "paper-title", title: "A" },
    { layout: "bullets", action_title: "T", points: ["a"] },
    { layout: "references", entries: ["r"] },
  ] }), []);
});

test("validateSpec warns (not errors) when a factual slide lacks source_ref", () => {
  const p = validateSpec({ slides: [{ layout: "results-table", table: { columns: [], rows: [] } }] });
  assert.ok(p.some((x) => x.field === "source_ref" && x.severity === "warn"));
});

test("escapeHtml neutralizes markup", () => {
  assert.equal(escapeHtml('<a href="x">&\'</a>'), "&lt;a href=&quot;x&quot;&gt;&amp;&#39;&lt;/a&gt;");
  assert.equal(escapeHtml(null), "");
});

test("renderMath emits vector KaTeX (not raster), with MathML for a11y", () => {
  const html = renderMath("\\sqrt{d_k}", { display: true });
  assert.match(html, /class="katex/);
  assert.match(html, /<math/); // MathML present
  assert.doesNotMatch(html, /<img/); // never an image
});

test("renderMath does not throw on bad LaTeX (renders error span)", () => {
  const html = renderMath("\\frac{", {});
  assert.match(html, /katex-error|katex/);
});

test("renderText escapes prose but renders inline $math$", () => {
  const html = renderText("score $d_k$ <b>");
  assert.match(html, /class="katex/);
  assert.match(html, /&lt;b&gt;/); // the <b> was escaped, not rendered
});

test("renderTable builds a real <table>, bolds best, puts units in header", () => {
  const html = renderTable({
    columns: [{ label: "Model" }, { label: "BLEU", unit: "EN-DE" }],
    row_header: true,
    rows: [["Transformer", { v: "28.4", bold: true }]],
    footnote: "WMT 2014",
  });
  assert.match(html, /<table class="results roomy">/); // 1 row x 2 cols: small tables set roomy
  assert.match(html, /<th>BLEU<span class="u">EN-DE<\/span><\/th>/);
  assert.match(html, /<th>Transformer<\/th>/); // row header
  assert.match(html, /<td><strong>28\.4<\/strong><\/td>/); // best bolded
  assert.match(html, /<tfoot>/);
});

test("renderTable rejects a malformed table", () => {
  assert.throws(() => renderTable({ columns: [] }), /needs/);
});

test("renderFigure embeds the real image + provenance cite, contain-fit", () => {
  const html = renderFigure({ src: "figures/figure-1.png", caption: "The Transformer", cite: "Vaswani 2017" });
  assert.match(html, /<img src="figures\/figure-1\.png"/);
  assert.match(html, /object-fit:contain/);
  assert.match(html, /\[Vaswani 2017\]/);
});

test("renderFigure requires a src", () => {
  assert.throws(() => renderFigure({ caption: "x" }), /src/);
});

test("renderSlide dispatches a registered layout and stamps data-layout", () => {
  const html = renderSlide({ layout: "discussion-questions", title: "Discussion", questions: ["Why $x$?"] });
  assert.match(html, /<section data-layout="discussion-questions"/);
  assert.match(html, /class="katex/); // inline math in a question
});

test("renderSlide throws on an unregistered layout (the layout lock)", () => {
  assert.throws(() => renderSlide({ layout: "fancy-3d-spinner" }), /unknown layout/);
});

test("renderSlide injects speaker notes as an <aside class=notes> inside the section", () => {
  const html = renderSlide({ layout: "bullets", action_title: "T", points: ["a"], speaker_notes: "Say <this>." });
  assert.match(html, /<aside class="notes">Say &lt;this&gt;\.<\/aside><\/section>$/);
  // no notes -> no aside
  assert.doesNotMatch(renderSlide({ layout: "bullets", points: ["a"] }), /aside class="notes"/);
});

test("the MVP journal-club layouts are all registered", () => {
  for (const l of [
    "paper-title", "section", "outline-agenda", "assertion-evidence", "equation",
    "results-table", "two-column", "critique-concerns", "discussion-questions", "references",
  ]) {
    assert.ok(REGISTERED.includes(l), `missing layout: ${l}`);
  }
});

test("buildHtml always loads tokens + base-theme, defaults to the journal-club flavor", () => {
  const html = buildHtml({ meta: {}, slides: [{ layout: "section", title: "X" }] });
  assert.ok(html.includes("assets/tokens.css"));
  assert.ok(html.includes("assets/base-theme.css"));
  assert.ok(html.includes("assets/journal-club.css"));
  assert.ok(!html.includes("assets/conference.css"), "default deck must not load conference flavor");
});

test("buildHtml selects the conference flavor via meta.theme", () => {
  const html = buildHtml({ meta: { theme: "conference" }, slides: [{ layout: "section", title: "X" }] });
  assert.ok(html.includes("assets/conference.css"), "conference deck loads conference flavor");
  assert.ok(html.includes("assets/base-theme.css"), "conference still loads the shared base");
  assert.ok(!html.includes("assets/journal-club.css"), "conference must not also load journal-club");
});

test("buildHtml falls back to journal-club for an unknown theme (never throws)", () => {
  const html = buildHtml({ meta: { theme: "bogus" }, slides: [{ layout: "section", title: "X" }] });
  assert.ok(html.includes("assets/journal-club.css"));
  assert.ok(!html.includes("assets/conference.css"));
});
