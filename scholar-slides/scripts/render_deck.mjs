#!/usr/bin/env node
// Render a built deck.html to a one-page-per-slide vector PDF (projection) and/or per-slide
// PNG screenshots (for the QA self-review stage) using Playwright + Chromium.
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { chromium } from "playwright";

async function withReveal(htmlPath, fn) {
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
    await page.goto(pathToFileURL(path.resolve(htmlPath)).href, { waitUntil: "networkidle" });
    await page.waitForFunction(() => window.Reveal && window.Reveal.isReady && window.Reveal.isReady(), null, {
      timeout: 20000,
    });
    return await fn(page);
  } finally {
    await browser.close();
  }
}

// PDF comes from the static print HTML (deck.print.html): no reveal runtime, real CSS @page
// paging -> one vector page per slide, text/equations selectable.
export async function renderPdf(htmlPath, pdfPath) {
  const printPath = htmlPath.replace(/deck\.html$/, "deck.print.html");
  const target = printPath !== htmlPath ? printPath : htmlPath;
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage();
    await page.goto(pathToFileURL(path.resolve(target)).href, { waitUntil: "networkidle" });
    await page.evaluate(() => (document.fonts ? document.fonts.ready : null));
    await page.pdf({ path: pdfPath, preferCSSPageSize: true, printBackground: true });
  } finally {
    await browser.close();
  }
  return pdfPath;
}

export async function screenshotSlides(htmlPath, outDir, max = 0) {
  const fs = await import("node:fs");
  fs.mkdirSync(outDir, { recursive: true });
  return withReveal(htmlPath, async (page) => {
    // The screenshots ARE the deliverable pixels the aesthetics rubric scores — presentation
    // chrome (nav chevrons, progress bar, page chip) must not be baked into them.
    await page.evaluate(() =>
      window.Reveal.configure({ controls: false, progress: false, slideNumber: false }));
    await page.addStyleTag({
      content: ".reveal .controls, .reveal .progress, .reveal .slide-number { display: none !important; }",
    });
    const total = await page.evaluate(() => window.Reveal.getTotalSlides());
    const n = max > 0 ? Math.min(max, total) : total;
    const shots = [];
    for (let i = 0; i < n; i++) {
      await page.evaluate((idx) => window.Reveal.slide(idx), i);
      await page.waitForTimeout(120);
      const p = path.join(outDir, `slide-${String(i + 1).padStart(2, "0")}.png`);
      await page.screenshot({ path: p });
      shots.push(p);
    }
    return shots;
  });
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const [, , htmlPath, mode, outArg] = process.argv;
  if (!htmlPath) {
    console.error("usage: render_deck.mjs <deck.html> [pdf|png] [outPath]");
    process.exit(1);
  }
  const run = async () => {
    if (mode === "png") {
      const dir = outArg || path.join(path.dirname(htmlPath), "slides");
      const shots = await screenshotSlides(htmlPath, dir);
      console.log(`screenshot ${shots.length} slides -> ${dir}`);
    } else {
      const pdf = outArg || path.join(path.dirname(htmlPath), "deck.pdf");
      await renderPdf(htmlPath, pdf);
      console.log(`rendered PDF -> ${pdf}`);
    }
  };
  run().catch((e) => {
    console.error(e);
    process.exit(1);
  });
}
