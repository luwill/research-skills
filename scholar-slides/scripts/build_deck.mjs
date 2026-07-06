#!/usr/bin/env node
// Deck spec (JSON) -> self-contained reveal.js + KaTeX deck (deck.html + assets/ + figures/).
// The model produces the spec (where judgment lives); rendering is deterministic, so equations
// always go through KaTeX, tables are always real <table>, figures are always the real crop,
// and every slide uses a registered layout.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { renderSlide, validateSpec } from "./lib/layouts.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, ".."); // skill root

function copyAssets(deckDir) {
  const a = path.join(deckDir, "assets");
  fs.mkdirSync(a, { recursive: true });
  const cp = (src, dst) => fs.cpSync(src, path.join(a, dst), { recursive: true });
  cp(path.join(ROOT, "node_modules/reveal.js/dist/reveal.css"), "reveal.css");
  cp(path.join(ROOT, "node_modules/reveal.js/dist/reveal.js"), "reveal.js");
  // Notes plugin: enables the in-browser speaker view (press 'S') with notes + timer. Bundle the
  // plugin AND its speaker-view popup so the deck is self-contained (no CDN, works offline).
  cp(path.join(ROOT, "node_modules/reveal.js/plugin/notes/notes.js"), "notes.js");
  cp(path.join(ROOT, "node_modules/reveal.js/plugin/notes/speaker-view.html"), "speaker-view.html");
  cp(path.join(ROOT, "node_modules/katex/dist/katex.min.css"), "katex.min.css");
  cp(path.join(ROOT, "node_modules/katex/dist/fonts"), "fonts");
  cp(path.join(ROOT, "assets/templates/deck-stage/tokens.css"), "tokens.css");
  cp(path.join(ROOT, "assets/templates/deck-stage/viewport-base.css"), "viewport-base.css");
  cp(path.join(ROOT, "assets/templates/deck-stage/print.css"), "print.css");
  cp(path.join(ROOT, "assets/templates/themes/base-theme.css"), "base-theme.css");
  cp(path.join(ROOT, "assets/templates/themes/journal-club.css"), "journal-club.css");
  cp(path.join(ROOT, "assets/templates/themes/conference.css"), "conference.css");
}

// mode: "interactive" -> reveal.js deck for presenting; "print" -> static paged deck for vector PDF.
// Registered theme flavors. A deck picks one via meta.theme; unknown -> journal-club (never throw).
const THEMES = { "journal-club": "journal-club.css", conference: "conference.css" };

export function buildHtml(deck, mode = "interactive") {
  const lang = deck.meta?.language || "en";
  const title = (deck.meta?.title || "scholar-slides").replace(/[<>]/g, "");
  const themeCss = THEMES[deck.meta?.theme] || THEMES["journal-club"];
  const slides = (deck.slides || []).map(renderSlide).join("\n");
  const isPrint = mode === "print";
  const links = [
    isPrint ? "" : `<link rel="stylesheet" href="assets/reveal.css">`,
    `<link rel="stylesheet" href="assets/katex.min.css">`,
    `<link rel="stylesheet" href="assets/tokens.css">`,
    `<link rel="stylesheet" href="assets/viewport-base.css">`,
    `<link rel="stylesheet" href="assets/base-theme.css">`,
    `<link rel="stylesheet" href="assets/${themeCss}">`,
    isPrint ? `<link rel="stylesheet" href="assets/print.css">` : "",
  ].filter(Boolean).join("\n");
  const script = isPrint
    ? ""
    : `<script src="assets/reveal.js"></script>
<script src="assets/notes.js"></script>
<script>
Reveal.initialize({ width: 1920, height: 1080, margin: 0.0, center: false,
  controls: true, progress: true, hash: true, slideNumber: 'c/t', transition: 'none',
  plugins: [ RevealNotes ] });
</script>`;
  return `<!doctype html>
<html lang="${lang}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${title}</title>
${links}
</head>
<body>
<div class="reveal"><div class="slides">
${slides}
</div></div>
${script}
</body>
</html>`;
}

export function buildDeck(deckJsonPath, outDir) {
  const deck = JSON.parse(fs.readFileSync(deckJsonPath, "utf-8"));
  const problems = validateSpec(deck);
  const errors = problems.filter((p) => p.severity === "error");
  if (errors.length) {
    throw new Error(
      `deck.json spec is invalid — fix these before building:\n` +
        errors.map((e) => `  • slide ${e.slide}: ${e.detail}`).join("\n")
    );
  }
  for (const w of problems.filter((p) => p.severity === "warn")) {
    console.warn(`WARN: ${w.detail}`);
  }
  const deckDir = outDir || path.join(path.dirname(deckJsonPath), "deck");
  fs.mkdirSync(deckDir, { recursive: true });
  copyAssets(deckDir);

  const figSrc = path.resolve(path.dirname(deckJsonPath), deck.meta?.figures_dir || "figures");
  if (fs.existsSync(figSrc)) fs.cpSync(figSrc, path.join(deckDir, "figures"), { recursive: true });

  const htmlPath = path.join(deckDir, "deck.html");
  const printPath = path.join(deckDir, "deck.print.html");
  fs.writeFileSync(htmlPath, buildHtml(deck, "interactive"));
  fs.writeFileSync(printPath, buildHtml(deck, "print"));
  return { deckDir, htmlPath, printPath, nSlides: (deck.slides || []).length };
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const [, , deckJson, outDir] = process.argv;
  if (!deckJson) {
    console.error("usage: build_deck.mjs <deck.json> [outDir]");
    process.exit(1);
  }
  const r = buildDeck(deckJson, outDir);
  console.log(`built ${r.nSlides} slides -> ${r.htmlPath}`);
}
