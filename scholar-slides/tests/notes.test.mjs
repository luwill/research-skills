// Stage 4 speaker-notes & timing tests (node --test tests/notes.test.mjs)
import { test } from "node:test";
import assert from "node:assert/strict";
import { countText, minutesFor, slideTimings, timingReport, notesHandout } from "../scripts/lib/notes.mjs";

test("countText separates latin words from CJK characters", () => {
  assert.deepEqual(countText("PANDA detects PDAC"), { cjkChars: 0, latinWords: 3 });
  const c = countText("PANDA 检测胰腺癌");
  assert.equal(c.latinWords, 1);
  assert.equal(c.cjkChars, 5); // 检测胰腺癌
});

test("minutesFor scales with speaking rate", () => {
  const w260 = "word ".repeat(260).trim();
  assert.ok(Math.abs(minutesFor(w260, { wpm: 130 }) - 2) < 0.01); // 260 words / 130 wpm = 2 min
  const zh = "字".repeat(240);
  assert.ok(Math.abs(minutesFor(zh, { cpm: 240 }) - 1) < 0.01); // 240 chars / 240 cpm = 1 min
});

test("slideTimings applies a floor for note-less slides", () => {
  const t = slideTimings({ slides: [{ layout: "bullets" }, { layout: "equation", speaker_notes: "word ".repeat(130) }] }, { floorMin: 0.5 });
  assert.equal(t[0].minutes, 0.5); // no notes -> floor
  assert.ok(Math.abs(t[1].minutes - 1) < 0.05); // 130 words ~ 1 min
});

test("timingReport totals and flags note-less slides", () => {
  const r = timingReport({ slides: [{ layout: "bullets" }, { layout: "bullets", speaker_notes: "hello there" }] });
  assert.ok(r.totalMinutes >= 1.0); // 0.5 floor + 0.5 floor (short notes < floor)
  assert.deepEqual(r.withoutNotes, [1]);
});

test("notesHandout renders a per-slide script with timings", () => {
  const md = notesHandout({ meta: { title: "T" }, slides: [{ layout: "paper-title", title: "X", speaker_notes: "Welcome." }] });
  assert.match(md, /# Speaker notes — T/);
  assert.match(md, /Slide 1 — X/);
  assert.match(md, /Welcome\./);
  assert.match(md, /Estimated total/);
});
