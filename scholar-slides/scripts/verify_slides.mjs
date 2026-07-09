#!/usr/bin/env node
// Browser render verification (ported in spirit from frontend-slides/huashu): navigate to each
// slide and measure it. Catches what static checks can't — content overflowing the 1080 stage,
// broken/empty images, KaTeX errors actually rendered, and sub-legible font sizes.
import path from "node:path";
import { pathToFileURL } from "node:url";
import { chromium } from "playwright";
import { voidFindings, figureFindings } from "./lib/render_checks.mjs";

const STAGE_H = 1080;
const FONT_MIN = 18; // px on the 1920x1080 stage (back-of-room legibility floor)

// opts.figMeta: Map(crop basename -> {minFontPt, bboxWpt}) from figures.json, for the
// exact figure-legibility projection (see lib/render_checks.mjs).
export async function verifySlides(htmlPath, opts = {}) {
  const browser = await chromium.launch();
  const findings = [];
  try {
    const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
    await page.goto(pathToFileURL(path.resolve(htmlPath)).href, { waitUntil: "networkidle" });
    await page.waitForFunction(() => window.Reveal && window.Reveal.isReady && window.Reveal.isReady(), null, { timeout: 20000 });
    const total = await page.evaluate(() => window.Reveal.getTotalSlides());

    for (let i = 0; i < total; i++) {
      await page.evaluate((idx) => window.Reveal.slide(idx), i);
      await page.waitForTimeout(100);
      const m = await page.evaluate(() => {
        const inner = document.querySelector(".slides section.present .slide-inner") || document.querySelector(".slide-inner");
        if (!inner) return null;
        // Normalize all geometry to stage px (reveal scales the stage with a transform).
        const innerRect = inner.getBoundingClientRect();
        const sx = 1920 / innerRect.width, sy = 1080 / innerRect.height;
        let minFont = Infinity;
        for (const el of inner.querySelectorAll("*")) {
          if (el.closest(".katex")) continue; // math sizing is intentional
          if (el.children.length === 0 && el.textContent.trim()) {
            const fs = parseFloat(getComputedStyle(el).fontSize);
            if (fs && fs < minFont) minFont = fs;
          }
        }
        // Extent of the body content (footer .s-source excluded): leaf text nodes, images,
        // table cells. Feeds the canvas-void checks.
        const body = inner.querySelector(".s-body");
        let bodyBottom = 0, bodyRight = 0, hasBody = false;
        if (body) {
          for (const el of body.querySelectorAll("*")) {
            const leafText = el.children.length === 0 && el.textContent.trim();
            if (!leafText && el.tagName !== "IMG") continue;
            const r = el.getBoundingClientRect();
            if (!r.width && !r.height) continue;
            hasBody = true;
            bodyBottom = Math.max(bodyBottom, (r.bottom - innerRect.top) * sy);
            bodyRight = Math.max(bodyRight, (r.right - innerRect.left) * sx);
          }
        }
        return {
          layout: inner.parentElement.getAttribute("data-layout"),
          overflowY: inner.scrollHeight - inner.clientHeight,
          overflowX: inner.scrollWidth - inner.clientWidth,
          katexErrors: inner.querySelectorAll(".katex-error").length,
          imgs: [...inner.querySelectorAll("img")].map((im) => ({
            src: im.getAttribute("src"),
            ok: im.complete && im.naturalWidth > 0,
            natural: im.naturalWidth,
            naturalH: im.naturalHeight,
            rendered: im.getBoundingClientRect().width * sx,
            inFigure: !!im.closest(".s-figure"),
          })),
          minFont: isFinite(minFont) ? minFont : null,
          body: { hasBody, bodyBottom, bodyRight },
        };
      });
      if (!m) { findings.push({ slide: i + 1, check: "empty-slide", severity: "P1", detail: "no .slide-inner found" }); continue; }
      const at = (extra) => ({ slide: i + 1, layout: m.layout, ...extra });
      if (m.overflowY > 2) findings.push(at({ check: "overflow-y", severity: "P1", detail: `content exceeds stage by ${Math.round(m.overflowY)}px (stage ${STAGE_H})` }));
      if (m.overflowX > 2) findings.push(at({ check: "overflow-x", severity: "P1", detail: `content wider than stage by ${Math.round(m.overflowX)}px` }));
      if (m.katexErrors > 0) findings.push(at({ check: "katex-error", severity: "P1", detail: `${m.katexErrors} KaTeX error(s) on slide` }));
      for (const im of m.imgs) if (!im.ok) findings.push(at({ check: "broken-image", severity: "P1", detail: `image not loaded: ${im.src}` }));
      if (m.minFont != null && m.minFont < FONT_MIN) findings.push(at({ check: "font-too-small", severity: "P2", detail: `min font ${m.minFont}px < ${FONT_MIN}px legibility floor` }));
      // Deterministic aesthetics geometry (M6b): canvas voids + figure legibility.
      for (const v of voidFindings({ layout: m.layout, ...m.body })) findings.push(at(v));
      for (const v of figureFindings(m.imgs, opts.figMeta)) findings.push(at(v));
    }
  } finally {
    await browser.close();
  }
  return findings;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const html = process.argv[2];
  if (!html) { console.error("usage: verify_slides.mjs <deck.html>"); process.exit(1); }
  verifySlides(html).then((f) => {
    console.log(JSON.stringify(f, null, 2));
    process.exit(f.some((x) => x.severity === "P0" || x.severity === "P1") ? 1 : 0);
  }).catch((e) => { console.error(e); process.exit(2); });
}
