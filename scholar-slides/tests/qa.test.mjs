// Stage 3 QA / integrity pure-logic tests (node --test tests/qa.test.mjs)
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  numberTokens, mapSuperscripts, collectFields, collectFlags, groundNumbers, layoutMix,
  emphasisAudit, extractDataLayouts, countKatexErrors, extractImgSrcs, findUnrenderedMath,
  findPlaceholders, figureCrowding, emojiAudit,
} from "../scripts/lib/qa.mjs";

test("mapSuperscripts + numberTokens normalize scientific notation", () => {
  assert.equal(mapSuperscripts("2.3·10¹⁹"), "2.3·1019");
  assert.deepEqual(numberTokens("28.4 and 2.3·10¹⁹"), ["28.4", "2.3", "1019"]);
});

test("collectFields flattens titles, points, and table cells", () => {
  const deck = {
    slides: [
      { layout: "bullets", action_title: "A", points: ["p1", "p2"] },
      { layout: "results-table", table: { rows: [["Model", { v: "28.4", bold: true }]] } },
    ],
  };
  const fields = collectFields(deck);
  assert.ok(fields.some((f) => f.field === "action_title" && f.text === "A"));
  assert.ok(fields.some((f) => f.text === "p2"));
  assert.ok(fields.some((f) => f.field === "table[0][1]" && f.text === "28.4"));
});

test("collectFlags surfaces integrity markers with location", () => {
  const deck = { slides: [{ layout: "references", entries: ["[UNVERIFIED] ref pending", "ok ref"] }] };
  const flags = collectFlags(deck);
  assert.equal(flags.length, 1);
  assert.match(flags[0].flag, /UNVERIFIED/);
});

test("groundNumbers flags a fabricated number, passes a real one", () => {
  const source = "Our model achieves 28.4 BLEU and 41.8 on EN-FR after 3.5 days.";
  const deck = {
    slides: [
      { layout: "results-table", table: { rows: [["big", "28.4", { v: "29.1" }]] } }, // 29.1 is fabricated
    ],
  };
  const findings = groundNumbers(deck, source);
  const flagged = findings.map((f) => f.value);
  assert.ok(flagged.includes("29.1"), "should flag the fabricated 29.1");
  assert.ok(!flagged.includes("28.4"), "should not flag the grounded 28.4");
  assert.equal(findings.find((f) => f.value === "29.1").severity, "P1");
});

test("groundNumbers ignores lone single digits", () => {
  const findings = groundNumbers({ slides: [{ layout: "bullets", points: ["N = 6 layers"] }] }, "no six here");
  assert.equal(findings.length, 0);
});

test("groundNumbers matches a decimal split across a line break in the source", () => {
  // PDF text extraction often breaks a number mid-decimal ("34.\n1%"). A value that IS in the
  // paper must still ground — otherwise a legitimate (e.g. redrawn-chart) number is false-flagged.
  const source = "outperforms the mean reader by a margin of 34.\n1% in sensitivity and 6.\n3% in specificity.";
  const deck = { slides: [{ layout: "assertion-evidence", annotation: "+34.1% sensitivity and +6.3% specificity." }] };
  const flagged = groundNumbers(deck, source).map((f) => f.value);
  assert.ok(!flagged.includes("34.1"), "34.1 split as 34.\\n1 should still ground");
  assert.ok(!flagged.includes("6.3"), "6.3 split as 6.\\n3 should still ground");
});

test("layoutMix reports bullet ratio and the longest same-layout run", () => {
  const deck = { slides: [
    { layout: "paper-title" },
    { layout: "bullets" }, { layout: "bullets" }, { layout: "bullets" },  // a 3-run of bullets
    { layout: "assertion-evidence" },
    { layout: "bullets" },
  ] };
  const m = layoutMix(deck);
  assert.equal(m.slides, 6);
  assert.equal(m.bullets, 4);
  assert.ok(Math.abs(m.bulletRatio - 4 / 6) < 1e-9);
  assert.equal(m.maxRun, 3);            // three bullets in a row
  assert.equal(m.counts.bullets, 4);
});

test("emphasisAudit counts added colors per slide; key/accent is free", () => {
  const deck = { slides: [
    // slide 1: metric + pos + key -> added = {metric,pos} = 2 (key is free) -> OK
    { layout: "bullets", points: ["==128K== and ==p|gold== and ==k|only=="] },
    // slide 2: metric + pos + warn -> added = 3 -> over the cap
    { layout: "critique-concerns", points: [{ head: "==w|risk==", body: "==5%== but ==p|wins==" }] },
    // slide 3: only key -> added = 0 -> OK
    { layout: "bullets", points: ["==k|clean=="] },
  ] };
  const a = emphasisAudit(deck);
  assert.deepEqual(a.over, [2]);
  assert.deepEqual(a.slides.find((s) => s.slide === 1).added, ["metric", "pos"]);
  assert.deepEqual(a.slides.find((s) => s.slide === 3).added, []);
});

test("layoutMix on a figure-forward deck reports a low bullet ratio", () => {
  const deck = { slides: [
    { layout: "paper-title" }, { layout: "assertion-evidence" }, { layout: "results-table" },
    { layout: "assertion-evidence" }, { layout: "bullets" }, { layout: "references" },
  ] };
  const m = layoutMix(deck);
  assert.ok(m.bulletRatio < 0.2);
  assert.equal(m.maxRun, 1);
});

test("figureCrowding flags ae slides whose caption+annotation squeeze the figure", () => {
  const long = "x".repeat(150);
  const deck = { slides: [
    { layout: "assertion-evidence", figure: { src: "f.png", caption: long }, annotation: long },   // crowded
    { layout: "assertion-evidence", figure: { src: "f.png", caption: "Fig. 1 | short." }, annotation: "one line" },
    { layout: "bullets", points: [long, long] },                                                    // not a figure slide
  ] };
  const flagged = figureCrowding(deck).map((f) => f.slide);
  assert.deepEqual(flagged, [1]);
});

test("findPlaceholders catches unfilled template tokens but not NLP vocab tokens", () => {
  // The Consistency-kill defect: "<presenter>, <date>" shipped on a cover (escaped in built HTML).
  const leaked =
    '<div class="presenter">Journal club &lt;presenter&gt;, &lt;date&gt;</div>' +
    '<div class="venue">&lt;主讲人&gt;</div>';
  const found = findPlaceholders(leaked);
  assert.deepEqual(found.sort(), ["<date>", "<presenter>", "<主讲人>"]);
  // Real NLP tokens that legitimately appear in decks must NOT trip the gate.
  const legit = "<li>the decoder emits &lt;eos&gt; and pads with &lt;pad&gt;, plus &lt;unk&gt; handling</li>";
  assert.deepEqual(findPlaceholders(legit), []);
  // Case-insensitive, tolerant of inner spaces.
  assert.equal(findPlaceholders("&lt; Presenter &gt;").length, 1);
});

test("emojiAudit flags emoji decoration in slide text, per slide with location", () => {
  // Visual AI-slop tell (anti-ai-slop): emoji as icons/bullets never belong in the
  // figure-editor register. The audit reports every field so the fix is targeted.
  const deck = { slides: [
    { layout: "bullets", action_title: "🚀 Training is 3x faster", points: ["✨ sparkles", "plain"] },
    { layout: "bullets", action_title: "Clean title", points: ["plain point"] },
    { layout: "assertion-evidence", action_title: "Also clean", figure: { src: "f.png", caption: "Fig. 1 | ⚡ speedup" } },
  ] };
  const found = emojiAudit(deck);
  assert.deepEqual([...new Set(found.map((f) => f.slide))], [1, 3]);
  const s1 = found.filter((f) => f.slide === 1);
  assert.ok(s1.some((f) => f.field === "action_title" && f.chars.includes("🚀")));
  assert.ok(s1.some((f) => f.field === "points[0]" && f.chars.includes("✨")));
});

test("emojiAudit does not false-positive on math, arrows, CJK, or integrity flags", () => {
  const deck = { slides: [
    { layout: "bullets", action_title: "损失下降 34.1% → 提速 2.3·10¹⁹", points: ["x ≤ y ± z", "[MISSING] 消融"] },
  ] };
  assert.deepEqual(emojiAudit(deck), []);
});

test("static HTML extractors", () => {
  const html =
    '<section data-layout="equation"><span class="katex-error">x</span><img src="figures/f1.png"></section>' +
    '<section data-layout="bullets">cost is $x$ unrendered</section>';
  assert.deepEqual(extractDataLayouts(html), ["equation", "bullets"]);
  assert.equal(countKatexErrors(html), 1);
  assert.deepEqual(extractImgSrcs(html), ["figures/f1.png"]);
  assert.ok(findUnrenderedMath(html).length >= 1);
});
