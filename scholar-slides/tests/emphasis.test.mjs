import { test } from "node:test";
import assert from "node:assert/strict";
import { renderEmphasis, stripEmphasis, rolesIn } from "../scripts/lib/emphasis.mjs";
import { renderText } from "../scripts/lib/math.mjs";

test("renderEmphasis maps each role to its class", () => {
  assert.equal(renderEmphasis("==128K=="), '<span class="metric">128K</span>');
  assert.equal(renderEmphasis("==k|linearly=="), '<span class="key">linearly</span>');
  assert.equal(renderEmphasis("==p|gold=="), '<span class="pos">gold</span>');
  assert.equal(renderEmphasis("==w|only internal data=="), '<span class="warn">only internal data</span>');
});

test("renderEmphasis leaves un-marked text untouched", () => {
  assert.equal(renderEmphasis("plain text, no markers"), "plain text, no markers");
});

test("stripEmphasis keeps inner words, drops markers (PPTX/notes sink)", () => {
  assert.equal(stripEmphasis("retains ==128K== context"), "retains 128K context");
  assert.equal(stripEmphasis("==k|only== change; took ==p|gold=="), "only change; took gold");
});

test("stripEmphasis is a faithful inverse of the markup for plain runs", () => {
  const raw = "==p|Matches or beats== V3.1 on ==MMLU-Pro==";
  assert.equal(stripEmphasis(raw), "Matches or beats V3.1 on MMLU-Pro");
});

test("renderText applies emphasis on escaped text (XSS-safe)", () => {
  // the angle bracket must be escaped; our span is the only real tag introduced
  const html = renderText("attack ==<script>== here");
  assert.match(html, /<span class="metric">&lt;script&gt;<\/span>/);
  assert.doesNotMatch(html, /<script>/);
});

test("renderText keeps inline math intact alongside emphasis", () => {
  const html = renderText("the cost ==k|drops== and $E=mc^2$ holds");
  assert.match(html, /<span class="key">drops<\/span>/);
  assert.match(html, /katex/); // KaTeX still rendered the math
});

test("rolesIn reports the distinct semantic roles in a string", () => {
  assert.deepEqual([...rolesIn("==128K== and ==p|gold== and ==2048==")].sort(), ["metric", "pos"]);
  assert.deepEqual([...rolesIn("no markers here")], []);
});
