/**
 * extract-figure.ts
 * Render a full PDF page to a high-resolution PNG (optionally cropped to a region).
 *
 * NOTE: This renders the WHOLE page — it does not auto-detect or crop the
 * bounding box of a single figure. For a clean single figure, pass --crop with
 * a pixel region (in the rendered/scaled coordinate space) or crop the result
 * manually before running apply-template.ts.
 *
 * Usage:
 *   npx -y bun extract-figure.ts --pdf paper.pdf --page 4 --output figure.png
 *   npx -y bun extract-figure.ts --pdf paper.pdf --page 4 --crop 100,200,1400,900 --output figure.png
 *
 * Options:
 *   --pdf     Path to source PDF file (required)
 *   --page    Page number to render, 1-indexed (required)
 *   --output  Output PNG file path (required)
 *   --scale   Render scale factor, default 2.0 for high quality (optional)
 *   --crop    Crop region "x,y,width,height" in rendered pixels (optional)
 */

import { existsSync, writeFileSync, mkdirSync } from "fs";
import { dirname, resolve, join } from "path";

interface Args {
  pdf: string;
  page: number;
  output: string;
  scale: number;
  crop?: { x: number; y: number; w: number; h: number };
}

/**
 * Dynamically load a third-party dependency, printing an actionable install
 * hint (instead of an opaque stack trace) if node_modules is missing.
 */
async function loadDep<T>(name: string, load: () => Promise<T>): Promise<T> {
  try {
    return await load();
  } catch (err: any) {
    const msg = String(err?.message ?? err);
    if (err?.code === "ERR_MODULE_NOT_FOUND" || /Cannot find (module|package)/i.test(msg)) {
      console.error(`\nError: missing Node dependency "${name}".`);
      console.error(`Install the script dependencies first:\n  cd ${import.meta.dir} && npm install`);
      process.exit(1);
    }
    throw err;
  }
}

function parseArgs(): Args {
  const args = process.argv.slice(2);
  let pdf = "";
  let page = 0;
  let output = "";
  let scale = 2.0;
  let crop: Args["crop"];

  for (let i = 0; i < args.length; i++) {
    switch (args[i]) {
      case "--pdf":
        pdf = args[++i];
        break;
      case "--page":
        page = parseInt(args[++i], 10);
        break;
      case "--output":
        output = args[++i];
        break;
      case "--scale":
        scale = parseFloat(args[++i]);
        break;
      case "--crop": {
        const parts = (args[++i] || "").split(",").map((n) => parseFloat(n.trim()));
        if (parts.length !== 4 || parts.some((n) => Number.isNaN(n))) {
          console.error('Error: --crop expects "x,y,width,height" in rendered pixels');
          process.exit(1);
        }
        crop = { x: parts[0], y: parts[1], w: parts[2], h: parts[3] };
        break;
      }
    }
  }

  if (!pdf || !page || !output) {
    console.error("Usage: bun extract-figure.ts --pdf <pdf-path> --page <number> --output <output.png>");
    console.error("\nOptions:");
    console.error("  --pdf     Path to source PDF file (required)");
    console.error("  --page    Page number to render, 1-indexed (required)");
    console.error("  --output  Output PNG file path (required)");
    console.error("  --scale   Render scale factor, default 2.0 (optional)");
    console.error('  --crop    Crop region "x,y,width,height" in rendered pixels (optional)');
    process.exit(1);
  }

  return { pdf, page, output, scale, crop };
}

async function extractPage(args: Args) {
  const { pdf: pdfPath, page: pageNum, output: outputPath, scale, crop } = args;

  // Load third-party deps dynamically so a missing install produces a clear hint.
  const pdfjsLib = await loadDep("pdfjs-dist", () => import("pdfjs-dist/legacy/build/pdf.mjs"));
  const { createCanvas } = await loadDep("canvas", () => import("canvas"));

  // Validate PDF exists
  const absolutePdfPath = resolve(pdfPath);
  if (!existsSync(absolutePdfPath)) {
    throw new Error(`PDF file not found: ${absolutePdfPath}`);
  }

  console.log(`Loading PDF: ${absolutePdfPath}`);

  // Resolve the bundled standard fonts relative to THIS script, not the CWD
  // (the skill runs with CWD set to the output dir, which has no node_modules).
  const standardFontDataUrl = join(import.meta.dir, "node_modules", "pdfjs-dist", "standard_fonts") + "/";

  // Load the PDF document
  const loadingTask = pdfjsLib.getDocument({
    url: absolutePdfPath,
    useSystemFonts: true,
    standardFontDataUrl,
  });

  const pdfDoc = await loadingTask.promise;
  const totalPages = pdfDoc.numPages;

  console.log(`PDF loaded: ${totalPages} pages`);

  // Validate page number
  if (pageNum < 1 || pageNum > totalPages) {
    throw new Error(`Page ${pageNum} out of range (1-${totalPages})`);
  }

  // Get the page
  const page = await pdfDoc.getPage(pageNum);
  const viewport = page.getViewport({ scale });

  console.log(`Page ${pageNum}: ${Math.round(viewport.width)}x${Math.round(viewport.height)} px (scale: ${scale})`);

  // Create canvas
  const canvas = createCanvas(viewport.width, viewport.height);
  const ctx = canvas.getContext("2d");

  // Fill white background
  ctx.fillStyle = "#FFFFFF";
  ctx.fillRect(0, 0, viewport.width, viewport.height);

  // Render page to canvas
  const renderContext = {
    canvasContext: ctx as any,
    viewport: viewport,
  };

  console.log("Rendering page...");
  await page.render(renderContext).promise;

  // Optionally crop to a region of the rendered page
  let outputCanvas = canvas;
  if (crop) {
    const x = Math.max(0, Math.min(crop.x, viewport.width));
    const y = Math.max(0, Math.min(crop.y, viewport.height));
    const w = Math.max(1, Math.min(crop.w, viewport.width - x));
    const h = Math.max(1, Math.min(crop.h, viewport.height - y));
    console.log(`Cropping to: ${Math.round(w)}x${Math.round(h)} at (${Math.round(x)}, ${Math.round(y)})`);
    const cropped = createCanvas(w, h);
    cropped.getContext("2d").drawImage(canvas, x, y, w, h, 0, 0, w, h);
    outputCanvas = cropped;
  }

  // Ensure output directory exists
  const outputDir = dirname(outputPath);
  if (outputDir && !existsSync(outputDir)) {
    mkdirSync(outputDir, { recursive: true });
  }

  // Save as PNG
  const buffer = outputCanvas.toBuffer("image/png");
  writeFileSync(outputPath, buffer);

  console.log(`\nSaved: ${outputPath}`);
  console.log(`Size: ${Math.round(buffer.length / 1024)} KB`);
}

async function main() {
  const args = parseArgs();

  try {
    await extractPage(args);
    console.log("\nExtraction complete!");
  } catch (error) {
    console.error("\nError:", error instanceof Error ? error.message : error);
    process.exit(1);
  }
}

main();
