#!/usr/bin/env node
// Emit a speaker-notes handout (the spoken script) + a timing estimate from a deck.json.
// Academic talks are spoken: timing is estimated from the notes, bilingual-aware (EN wpm + CJK cpm).
import fs from "node:fs";
import path from "node:path";
import { notesHandout, timingReport } from "./lib/notes.mjs";

const fmt = (m) => `${Math.floor(m)}:${String(Math.round((m % 1) * 60)).padStart(2, "0")}`;

if (import.meta.url === `file://${process.argv[1]}`) {
  const deckJson = process.argv[2];
  const budget = process.argv[3] ? Number(process.argv[3]) : null;
  if (!deckJson) { console.error("usage: speaker_notes.mjs <deck.json> [budgetMin]"); process.exit(1); }
  const deck = JSON.parse(fs.readFileSync(deckJson, "utf-8"));
  const opts = budget ? { budgetMin: budget } : {};
  const out = path.join(path.dirname(deckJson), "notes.md");
  fs.writeFileSync(out, notesHandout(deck, opts));

  const t = timingReport(deck, opts);
  console.log(`Speaker notes -> ${out}`);
  console.log(`Estimated total: ${fmt(t.totalMinutes)}` + (budget ? `  (budget ${budget}:00)` : ""));
  if (budget) {
    const ratio = t.totalMinutes / budget;
    console.log(ratio > 1.15 ? "  ⚠ over budget — cut content or trim notes"
      : ratio < 0.6 ? "  ⚠ well under budget — likely too thin" : "  ✓ within budget");
  }
  if (t.withoutNotes.length) console.log(`Slides without notes: ${t.withoutNotes.join(", ")}`);
  for (const s of t.slides) console.log(`  slide ${String(s.slide).padStart(2)}  ${fmt(s.minutes)}${s.hasNotes ? "" : "  (no notes)"}`);
}
