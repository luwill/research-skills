#!/usr/bin/env node
// Static validator for a built deck (no browser). Ported in spirit from guizang's
// validate-deck.mjs: enforce the layout lock and catch render defects the build can't.
import fs from "node:fs";
import path from "node:path";
import { REGISTERED } from "./lib/layouts.mjs";
import { extractDataLayouts, countKatexErrors, extractImgSrcs, findUnrenderedMath, findPlaceholders } from "./lib/qa.mjs";

export function validateDeck(deckDir) {
  const findings = [];
  const html = fs.readFileSync(path.join(deckDir, "deck.html"), "utf-8");

  for (const l of extractDataLayouts(html)) {
    if (!REGISTERED.includes(l)) {
      findings.push({ check: "layout-lock", severity: "P0", detail: `unregistered layout "${l}"` });
    }
  }
  const ph = [...new Set(findPlaceholders(html))];
  if (ph.length) {
    findings.push({ check: "placeholder-leak", severity: "P1",
      detail: `unfilled template placeholder(s) shipped: ${ph.join(", ")} — fill with real values or remove` });
  }

  const ke = countKatexErrors(html);
  if (ke > 0) findings.push({ check: "katex-error", severity: "P1", detail: `${ke} KaTeX error span(s) — an equation failed to render` });

  const um = findUnrenderedMath(html);
  if (um.length) findings.push({ check: "unrendered-math", severity: "P2", detail: `possible unrendered math: ${um.slice(0, 3).join(" ")}` });

  for (const src of extractImgSrcs(html)) {
    if (/^https?:/.test(src)) continue;
    if (!fs.existsSync(path.join(deckDir, src))) {
      findings.push({ check: "missing-figure", severity: "P1", detail: `figure file not found: ${src}` });
    }
  }
  return findings;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const dir = process.argv[2];
  if (!dir) { console.error("usage: validate_deck.mjs <deckDir>"); process.exit(1); }
  const findings = validateDeck(dir);
  console.log(JSON.stringify(findings, null, 2));
  process.exit(findings.some((f) => f.severity === "P0" || f.severity === "P1") ? 1 : 0);
}
