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
  if (!fs.existsSync(pptx)) return { n: -1 }; // no pptx exported
  const r = spawnSync(PY, [path.join(ROOT, "scripts/verify_pptx_parity.py"), deckJson, pptx],
    { encoding: "utf-8", env: { ...process.env, PYTHONPATH: path.join(ROOT, "scripts") } });
  const out = (r.stdout || "") + (r.stderr || "");
  if (r.status === 0) return { n: 0 };
  const m = out.match(/parity: (\d+) issue/);
  return { n: m ? Number(m[1]) : 1, out };
}

async function main() {
  const manifest = JSON.parse(fs.readFileSync(path.join(ROOT, "benchmarks/manifest.json"), "utf-8"));
  const rows = [];
  let hardFail = false;

  for (const d of manifest.decks) {
    const dir = path.join(ROOT, d.dir);
    const deckJson = path.join(dir, "deck.json");
    const deckDir = path.join(dir, "deck");
    if (!fs.existsSync(deckJson)) { rows.push({ name: d.name, status: "MISSING" }); hardFail = true; continue; }
    const deck = JSON.parse(fs.readFileSync(deckJson, "utf-8"));

    let sev = { P0: 0, P1: 0, P2: 0, P3: 0 }, mins = "?", aes = "—";
    try {
      const findings = await qaReport(deckDir, dir);
      sev = severityCounts(findings);
      mins = findings._timing ? findings._timing.totalMinutes : "?";
      if (typeof findings._aesthetics?.mean === "number") aes = findings._aesthetics.mean.toFixed(1);
    } catch (e) { rows.push({ name: d.name, status: `QA-ERR ${e.message}` }); hardFail = true; continue; }

    const parity = parityIssues(deckJson, path.join(deckDir, "deck.pptx"));
    const mix = layoutMix(deck);
    const gate = sev.P0 ? "BLOCK" : sev.P1 ? "REVIEW" : "PASS";
    if (sev.P0 || parity.n > 0) hardFail = true;

    rows.push({
      name: d.name, slides: mix.slides, gate, p1: sev.P1, p2: sev.P2, p3: sev.P3,
      parity: parity.n < 0 ? "no-pptx" : parity.n === 0 ? "ok" : `${parity.n} ISSUES`,
      bullets: `${Math.round(mix.bulletRatio * 100)}%`, aes, mins,
    });
  }

  const pad = (s, n) => String(s).padEnd(n);
  console.log("\n=== scholar-slides benchmark ===");
  console.log(pad("deck", 18) + pad("slides", 7) + pad("gate", 8) + pad("P1/P2/P3", 10) +
    pad("pptx-parity", 13) + pad("bullets", 9) + pad("aes/24", 8) + "talk");
  for (const r of rows) {
    if (r.status) { console.log(pad(r.name, 18) + r.status); continue; }
    const fmt = typeof r.mins === "number" ? `${Math.floor(r.mins)}:${String(Math.round((r.mins % 1) * 60)).padStart(2, "0")}` : r.mins;
    console.log(pad(r.name, 18) + pad(r.slides, 7) + pad(r.gate, 8) +
      pad(`${r.p1}/${r.p2}/${r.p3}`, 10) + pad(r.parity, 13) + pad(r.bullets, 9) + pad(r.aes, 8) + fmt);
  }
  console.log(`\n${hardFail ? "✗ regression: a deck BLOCKs or has PPTX parity issues" : "✓ all benchmark decks pass (no P0, PPTX parity clean)"}`);
  process.exit(hardFail ? 1 : 0);
}

main().catch((e) => { console.error(e); process.exit(2); });
