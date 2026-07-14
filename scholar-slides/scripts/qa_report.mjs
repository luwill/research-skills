#!/usr/bin/env node
// Stage 3 QA self-review gate: integrity scan + static validation + render verification ->
// one consolidated P0-P3 report. This is what the model and the user review at Checkpoint 3.
// It does NOT certify truth (only a human can) — it surfaces every defect and every flag.
import fs from "node:fs";
import path from "node:path";
import { groundNumbers, collectFlags, layoutMix, emphasisAudit, figureCrowding, emojiAudit } from "./lib/qa.mjs";
import { buildFigMeta } from "./lib/render_checks.mjs";
import { timingReport } from "./lib/notes.mjs";
import { validateDeck } from "./validate_deck.mjs";
import { verifySlides } from "./verify_slides.mjs";

// render-review stage (aesthetics program M6a): the 6-dimension rubric loop
// (references/aesthetics-review.md) must RUN and spend its rework list down before CKPT-3.
// The loop itself is a model task; this gate makes skipping it, or leaving rework slides
// open, visible in the report instead of silent.
export function renderReviewFindings(deckDir) {
  const p = path.join(deckDir, "aesthetics_report.json");
  if (!fs.existsSync(p)) {
    return [{ stage: "render-review", check: "aesthetics-not-run", severity: "P3",
      detail: "no aesthetics_report.json — run the 6-dimension rubric on the rendered slides (references/aesthetics-review.md) and write the report next to deck.html" }];
  }
  let report;
  try {
    report = JSON.parse(fs.readFileSync(p, "utf-8"));
    if (typeof report !== "object" || report === null || !Array.isArray(report.rework)) throw new Error("missing rework list");
  } catch (e) {
    return [{ stage: "render-review", check: "aesthetics-report-invalid", severity: "P2",
      detail: `aesthetics_report.json unreadable (${e.message}) — regenerate it from the rubric loop` }];
  }
  if (report.rework.length) {
    const slides = report.rework.map((r) => r.slide).join(", ");
    return [{ stage: "render-review", check: "aesthetics-rework-open", severity: "P2",
      detail: `${report.rework.length} slide(s) below the rubric floor (dim <=2 or total <18): ${slides} — fix, re-render, re-score` }];
  }
  return [];
}

export async function qaReport(deckDir, sourceDir) {
  sourceDir = sourceDir || path.resolve(deckDir, "..");
  const deck = JSON.parse(fs.readFileSync(path.join(sourceDir, "deck.json"), "utf-8"));
  const ingestPath = path.join(sourceDir, "ingest.json");
  const sourceText = fs.existsSync(ingestPath) ? JSON.parse(fs.readFileSync(ingestPath, "utf-8")).full_text || "" : "";

  const findings = [];
  if (sourceText) {
    for (const g of groundNumbers(deck, sourceText)) {
      findings.push({ stage: "integrity", check: "ungrounded-number", severity: g.severity, slide: g.slide,
        detail: `"${g.value}" (${g.layout} ${g.field}) not found in the source paper text` });
    }
  } else {
    findings.push({ stage: "integrity", check: "no-source", severity: "P2", detail: "no ingest.json — number grounding skipped" });
  }
  for (const fl of collectFlags(deck)) {
    findings.push({ stage: "integrity", check: "flag", severity: "P1", slide: fl.slide,
      detail: `${fl.flag} (${fl.field}) — must be acknowledged at CKPT-3` });
  }
  const timing = timingReport(deck);
  if (timing.withoutNotes.length) {
    findings.push({ stage: "notes", check: "missing-speaker-notes", severity: "P3",
      detail: `${timing.withoutNotes.length} slide(s) without speaker notes: ${timing.withoutNotes.join(", ")}` });
  }
  // Aesthetic nudge (figure-editor register): flag a bullet-heavy or monotonous layout mix.
  const mix = layoutMix(deck);
  if (mix.bulletRatio > 1 / 3) {
    findings.push({ stage: "aesthetics", check: "bullet-heavy", severity: "P3",
      detail: `${mix.bullets}/${mix.slides} slides are pure bullets (${Math.round(mix.bulletRatio * 100)}%) — prefer figures, tables, or redrawn charts` });
  }
  if (mix.maxRun >= 4) {   // 3 figure slides in a row is fine; 4+ reads monotonous
    findings.push({ stage: "aesthetics", check: "monotonous-layout", severity: "P3",
      detail: `${mix.maxRun} identical layouts in a row — vary the rhythm (a section divider or a different archetype)` });
  }
  // Figure-protagonist discipline: long caption+annotation squeezes the figure below legibility.
  for (const fc of figureCrowding(deck)) {
    findings.push({ stage: "aesthetics", check: "figure-crowded", severity: "P3", slide: fc.slide,
      detail: `caption+annotation = ${fc.chars} chars (> ${fc.maxChars}) — the figure loses protagonist space; move detail to speaker_notes` });
  }
  // Visual AI-slop tell: emoji decoration in slide text (icons belong to the type system,
  // meaning to the emphasis roles). Near-always wrong in this register — P2, not a block,
  // because a quoted source could legitimately contain one (acknowledge at CKPT-3).
  for (const em of emojiAudit(deck)) {
    findings.push({ stage: "aesthetics", check: "emoji-decoration", severity: "P2", slide: em.slide,
      detail: `${em.chars.join(" ")} in ${em.field} — emoji reads as AI-slop in the figure-editor register; use the emphasis roles or plain type` });
  }
  // Emphasis discipline (designed, not decorated): cap the added colored roles at <=2 per slide.
  const emph = emphasisAudit(deck);
  if (emph.over.length) {
    findings.push({ stage: "aesthetics", check: "over-highlighted", severity: "P3",
      detail: `slide(s) ${emph.over.join(", ")} use >${emph.maxAdded} added emphasis treatments — reads as over-marked; keep metric/positive/warn to <=2 per slide (key/accent is free)` });
  }
  for (const v of validateDeck(deckDir)) findings.push({ stage: "validate", ...v });
  // Exact figure-legibility projection needs the crop metadata detect_figures emitted.
  const figuresPath = path.join(sourceDir, "figures.json");
  const figMeta = fs.existsSync(figuresPath)
    ? buildFigMeta(JSON.parse(fs.readFileSync(figuresPath, "utf-8")))
    : new Map();
  for (const v of await verifySlides(path.join(deckDir, "deck.html"), { figMeta })) findings.push({ stage: "verify", ...v });
  for (const v of renderReviewFindings(deckDir)) findings.push(v);
  const aesPath = path.join(deckDir, "aesthetics_report.json");
  if (fs.existsSync(aesPath)) {
    try { findings._aesthetics = { mean: JSON.parse(fs.readFileSync(aesPath, "utf-8")).mean }; } catch { /* reported above */ }
  }
  findings._timing = timing; // carried for the summary line (non-finding metadata)
  return findings;
}

function summarize(findings) {
  const order = ["P0", "P1", "P2", "P3"];
  const by = Object.fromEntries(order.map((s) => [s, findings.filter((f) => f.severity === s)]));
  const lines = [];
  lines.push("=== scholar-slides QA report ===");
  for (const sev of order) {
    if (!by[sev].length) continue;
    lines.push(`\n[${sev}] ${by[sev].length}`);
    for (const f of by[sev]) {
      const where = f.slide ? `slide ${f.slide}` : "deck";
      lines.push(`  • (${f.stage}/${f.check}) ${where}: ${f.detail}`);
    }
  }
  const realFindings = findings.filter(Boolean);
  if (!realFindings.length) lines.push("\n✓ no defects found.");
  const t = findings._timing;
  if (t) {
    const fmt = (m) => `${Math.floor(m)}:${String(Math.round((m % 1) * 60)).padStart(2, "0")}`;
    lines.push(`\nEstimated talk length: ${fmt(t.totalMinutes)} over ${t.slides.length} slides` +
      (t.withoutNotes.length ? ` (${t.withoutNotes.length} without notes)` : ""));
  }
  const p0 = by.P0.length, p1 = by.P1.length;
  lines.push(
    `\nGate: ${p0 ? "BLOCK (P0 defects)" : p1 ? "REVIEW REQUIRED (P1 — acknowledge at CKPT-3)" : "PASS (no P0/P1)"}`
  );
  return { text: lines.join("\n"), p0, p1 };
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const deckDir = process.argv[2];
  const sourceDir = process.argv[3];
  if (!deckDir) { console.error("usage: qa_report.mjs <deckDir> [sourceDir]"); process.exit(1); }
  qaReport(deckDir, sourceDir).then((findings) => {
    const { text, p0, p1 } = summarize(findings);
    console.log(text);
    fs.writeFileSync(path.join(deckDir, "qa_report.json"), JSON.stringify(findings, null, 2));
    process.exit(p0 ? 2 : p1 ? 1 : 0);
  }).catch((e) => { console.error(e); process.exit(3); });
}
