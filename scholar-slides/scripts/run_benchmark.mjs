#!/usr/bin/env node
// Regression benchmark: run every deck in benchmarks/manifest.json through all three gates and
// print a one-line-per-deck dashboard. A change that improves one deck must not regress another.
//   1. integrity QA gate  (number grounding, layout lock, overflow/broken-image, KaTeX errors)
//   2. PPTX content parity (every spec text/table/note survives natively into the editable PPTX)
//   3. aesthetic layout-mix (bullet-ratio + longest same-layout run)
// Exit non-zero if any deck BLOCKs (P0) or has PPTX parity issues — the CI regression signal.
import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { qaReport } from "./qa_report.mjs";
import { layoutMix } from "./lib/qa.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, "..");
const PY = fs.existsSync(path.join(ROOT, ".venv/bin/python"))
  ? path.join(ROOT, ".venv/bin/python") : "python3";

function severityCounts(findings) {
  const c = { P0: 0, P1: 0, P2: 0, P3: 0 };
  for (const f of findings) if (c[f.severity] !== undefined) c[f.severity]++;
  return c;
}

function parityIssues(deckJson, pptx) {
  if (!fs.existsSync(pptx)) return { n: -1, skipped: 0 }; // no pptx exported
  const r = spawnSync(PY, [path.join(ROOT, "scripts/verify_pptx_parity.py"), deckJson, pptx],
    { encoding: "utf-8", env: { ...process.env, PYTHONPATH: path.join(ROOT, "scripts") } });
  const out = (r.stdout || "") + (r.stderr || "");
  // Figures whose regenerated crop is absent on disk (clean clone) degrade to a WARN skip, not a
  // hard parity failure — count them for the dashboard so the degradation is visible.
  const skipped = (out.match(/missing-figure-skipped/g) || []).length;
  if (r.status === 0) return { n: 0, skipped };
  const m = out.match(/parity: (\d+) issue/);
  return { n: m ? Number(m[1]) : 1, skipped, out };
}

async function main() {
  const manifest = JSON.parse(fs.readFileSync(path.join(ROOT, "benchmarks/manifest.json"), "utf-8"));
  const rows = [];
  let hardFail = false;
  let notBuilt = 0;

  for (const d of manifest.decks) {
    const dir = path.join(ROOT, d.dir);
    const deckJson = path.join(dir, "deck.json");
    const deckDir = path.join(dir, "deck");
    if (!fs.existsSync(deckJson)) { rows.push({ name: d.name, status: "MISSING (no deck.json)" }); hardFail = true; continue; }
    // A clean clone tracks only deck.json (the durable spec); deck/ is a build product. If a deck
    // hasn't been built, that's a rebuild step, not a regression — report it clearly, don't crash.
    if (!fs.existsSync(path.join(deckDir, "deck.html"))) {
      rows.push({ name: d.name, status: "NOT-BUILT (run build_deck + export_pptx)" }); notBuilt++; continue;
    }
    const deck = JSON.parse(fs.readFileSync(deckJson, "utf-8"));

    let sev = { P0: 0, P1: 0, P2: 0, P3: 0 }, mins = "?";
    try {
      const findings = await qaReport(deckDir, dir);
      sev = severityCounts(findings);
      mins = findings._timing ? findings._timing.totalMinutes : "?";
    } catch (e) { rows.push({ name: d.name, status: `QA-ERR ${e.message}` }); hardFail = true; continue; }

    const parity = parityIssues(deckJson, path.join(deckDir, "deck.pptx"));
    const mix = layoutMix(deck);
    const gate = sev.P0 ? "BLOCK" : sev.P1 ? "REVIEW" : "PASS";
    if (sev.P0 || parity.n > 0) hardFail = true;

    const parityLabel = parity.n < 0 ? "no-pptx"
      : parity.n === 0 ? (parity.skipped ? `ok (${parity.skipped} skip)` : "ok")
      : `${parity.n} ISSUES`;
    rows.push({
      name: d.name, slides: mix.slides, gate, p1: sev.P1, p2: sev.P2, p3: sev.P3,
      parity: parityLabel,
      bullets: `${Math.round(mix.bulletRatio * 100)}%`, mins,
    });
  }

  const pad = (s, n) => String(s).padEnd(n);
  console.log("\n=== scholar-slides benchmark ===");
  console.log(pad("deck", 18) + pad("slides", 7) + pad("gate", 8) + pad("P1/P2/P3", 10) +
    pad("pptx-parity", 13) + pad("bullets", 9) + "talk");
  for (const r of rows) {
    if (r.status) { console.log(pad(r.name, 18) + r.status); continue; }
    const fmt = typeof r.mins === "number" ? `${Math.floor(r.mins)}:${String(Math.round((r.mins % 1) * 60)).padStart(2, "0")}` : r.mins;
    console.log(pad(r.name, 18) + pad(r.slides, 7) + pad(r.gate, 8) +
      pad(`${r.p1}/${r.p2}/${r.p3}`, 10) + pad(r.parity, 13) + pad(r.bullets, 9) + fmt);
  }
  if (hardFail) {
    console.log("\n✗ regression: a deck BLOCKs or has PPTX parity issues");
  } else if (notBuilt) {
    console.log(`\n⚠ ${notBuilt} deck(s) NOT-BUILT — no regression in the built decks. Build them first, e.g.:`);
    console.log("    for d in out/*/; do node scripts/build_deck.mjs \"$d/deck.json\" && \\");
    console.log("      node scripts/export_pptx.mjs \"$d/deck.json\" \"$d/deck/deck.pptx\"; done");
    console.log("  (figure crops are build products; decks that reference absent crops degrade to a skip, not a fail).");
  } else {
    console.log("\n✓ all benchmark decks pass (no P0, PPTX parity clean)");
  }
  process.exit(hardFail ? 1 : 0);
}

main().catch((e) => { console.error(e); process.exit(2); });
