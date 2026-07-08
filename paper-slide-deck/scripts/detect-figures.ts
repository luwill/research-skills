/**
 * detect-figures.ts
 * Automatically detect figures and tables from academic PDF papers.
 *
 * Usage:
 *   npx -y bun detect-figures.ts --pdf paper.pdf --output figures.json
 *
 * Options:
 *   --pdf     Path to source PDF file (required)
 *   --output  Output JSON file path (optional, prints to stdout if omitted)
 *
 * Detection is heuristic (text-based): it locates "Figure N"/"Table N" caption
 * lines. To reduce false positives from inline references (e.g. "as shown in
 * Figure 3"), when a label appears more than once the candidate with the
 * longest caption text is chosen — real captions are descriptive, inline
 * mentions are short. Always eyeball the page numbers before extracting.
 *
 * Output JSON format:
 * {
 *   "figures": [
 *     { "type": "figure", "number": "1", "page": 2, "caption": "...", "label": "Figure 1" },
 *     { "type": "table", "number": "I", "page": 5, "caption": "...", "label": "Table I" }
 *   ],
 *   "totalPages": 10
 * }
 */

import { existsSync, writeFileSync } from "fs";
import { resolve, join } from "path";

interface FigureInfo {
  type: "figure" | "table";
  number: string;
  page: number;
  caption: string;
  label: string;
}

interface DetectionResult {
  figures: FigureInfo[];
  totalPages: number;
  pdfPath: string;
}

interface Args {
  pdf: string;
  output: string | null;
}

// Below this caption length a match is treated as a likely inline reference
// rather than a real caption (used only when a richer candidate exists).
const MIN_CAPTION_LENGTH = 12;

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
  let output: string | null = null;

  for (let i = 0; i < args.length; i++) {
    switch (args[i]) {
      case "--pdf":
        pdf = args[++i];
        break;
      case "--output":
        output = args[++i];
        break;
    }
  }

  if (!pdf) {
    console.error("Usage: bun detect-figures.ts --pdf <pdf-path> [--output <output.json>]");
    console.error("\nOptions:");
    console.error("  --pdf     Path to source PDF file (required)");
    console.error("  --output  Output JSON file path (optional)");
    process.exit(1);
  }

  return { pdf, output };
}

/**
 * Extract text content from a PDF page
 */
async function getPageText(page: any): Promise<string> {
  const textContent = await page.getTextContent();
  const items = textContent.items as any[];

  // Sort by y position (top to bottom), then x position (left to right)
  items.sort((a, b) => {
    const yDiff = b.transform[5] - a.transform[5]; // y is inverted in PDF
    if (Math.abs(yDiff) > 5) return yDiff;
    return a.transform[4] - b.transform[4];
  });

  // Group items by line (similar y position)
  const lines: string[][] = [];
  let currentLine: string[] = [];
  let lastY = items[0]?.transform[5] ?? 0;

  for (const item of items) {
    const y = item.transform[5];
    if (Math.abs(y - lastY) > 8) {
      if (currentLine.length > 0) {
        lines.push(currentLine);
      }
      currentLine = [];
      lastY = y;
    }
    if (item.str.trim()) {
      currentLine.push(item.str);
    }
  }
  if (currentLine.length > 0) {
    lines.push(currentLine);
  }

  return lines.map(line => line.join(" ")).join("\n");
}

/**
 * Parse figure and table references from text. Returns ALL candidate matches on
 * the page (deduplication/selection happens globally in detectFigures).
 */
function parseFiguresFromText(text: string, pageNum: number): FigureInfo[] {
  const figures: FigureInfo[] = [];

  // Patterns for figure captions
  // Match: "Fig. 1.", "Figure 1:", "Fig. 1 ", "FIGURE 1."
  const figurePatterns = [
    /(?:^|\n)\s*(?:Fig(?:ure|\.)?)\s*(\d+)[.:\s]+([^\n]+(?:\n(?![A-Z]{2,}|\d+\.|Fig|Table)[^\n]+)*)/gi,
    /(?:^|\n)\s*FIGURE\s+(\d+)[.:\s]+([^\n]+(?:\n(?![A-Z]{2,}|\d+\.|Fig|Table)[^\n]+)*)/g,
  ];

  // Patterns for table captions
  // Match: "Table I", "TABLE 1", "Table 1:"
  const tablePatterns = [
    /(?:^|\n)\s*(?:Table|TABLE)\s+([IVXLCDM\d]+)[.:\s]+([^\n]+(?:\n(?![A-Z]{2,}|\d+\.|Fig|Table)[^\n]+)*)/gi,
  ];

  const pushMatches = (patterns: RegExp[], type: "figure" | "table") => {
    for (const pattern of patterns) {
      let match;
      while ((match = pattern.exec(text)) !== null) {
        const number = match[1];
        const caption = match[2].trim().replace(/\s+/g, " ").substring(0, 300);
        const label = `${type === "figure" ? "Figure" : "Table"} ${number}`;
        figures.push({ type, number, page: pageNum, caption, label });
      }
    }
  };

  pushMatches(figurePatterns, "figure");
  pushMatches(tablePatterns, "table");

  return figures;
}

/**
 * Pick the best candidate for a label: prefer descriptive captions (>= MIN
 * length); among the eligible pool, the longest caption wins. This favours the
 * real caption line over short inline references on earlier pages.
 */
function pickBest(candidates: FigureInfo[]): FigureInfo {
  const rich = candidates.filter(c => c.caption.trim().length >= MIN_CAPTION_LENGTH);
  const pool = rich.length > 0 ? rich : candidates;
  return pool.reduce((best, c) => (c.caption.length > best.caption.length ? c : best), pool[0]);
}

/**
 * Detect all figures and tables in a PDF
 */
async function detectFigures(pdfPath: string): Promise<DetectionResult> {
  const pdfjsLib = await loadDep("pdfjs-dist", () => import("pdfjs-dist/legacy/build/pdf.mjs"));

  const absolutePath = resolve(pdfPath);

  if (!existsSync(absolutePath)) {
    throw new Error(`PDF file not found: ${absolutePath}`);
  }

  console.error(`Loading PDF: ${absolutePath}`);

  // Resolve the bundled standard fonts relative to THIS script, not the CWD.
  const standardFontDataUrl = join(import.meta.dir, "node_modules", "pdfjs-dist", "standard_fonts") + "/";

  const loadingTask = pdfjsLib.getDocument({
    url: absolutePath,
    useSystemFonts: true,
    standardFontDataUrl,
  });

  const pdfDoc = await loadingTask.promise;
  const totalPages = pdfDoc.numPages;

  console.error(`PDF loaded: ${totalPages} pages`);
  console.error("Scanning for figures and tables...\n");

  // Collect every candidate per label, then choose the best.
  const candidatesByLabel = new Map<string, FigureInfo[]>();

  for (let pageNum = 1; pageNum <= totalPages; pageNum++) {
    const page = await pdfDoc.getPage(pageNum);
    const text = await getPageText(page);
    const pageFigures = parseFiguresFromText(text, pageNum);

    for (const fig of pageFigures) {
      const list = candidatesByLabel.get(fig.label) ?? [];
      list.push(fig);
      candidatesByLabel.set(fig.label, list);
    }
  }

  const allFigures: FigureInfo[] = [];
  for (const [label, candidates] of candidatesByLabel) {
    const best = pickBest(candidates);
    allFigures.push(best);
    const extra = candidates.length > 1 ? ` (chosen from ${candidates.length} mentions)` : "";
    console.error(`  Found: ${label} on page ${best.page}${extra}`);
  }

  // Sort by type then number
  allFigures.sort((a, b) => {
    if (a.type !== b.type) {
      return a.type === "figure" ? -1 : 1;
    }
    // Handle Roman numerals for tables
    const numA = romanToInt(a.number) || parseInt(a.number, 10) || 0;
    const numB = romanToInt(b.number) || parseInt(b.number, 10) || 0;
    return numA - numB;
  });

  console.error(`\nTotal: ${allFigures.length} figures/tables detected`);

  return {
    figures: allFigures,
    totalPages,
    pdfPath: absolutePath,
  };
}

/**
 * Convert Roman numeral to integer
 */
function romanToInt(roman: string): number | null {
  const romanMap: { [key: string]: number } = {
    I: 1, V: 5, X: 10, L: 50, C: 100, D: 500, M: 1000,
  };

  const upper = roman.toUpperCase();
  if (!/^[IVXLCDM]+$/.test(upper)) {
    return null;
  }

  let result = 0;
  for (let i = 0; i < upper.length; i++) {
    const current = romanMap[upper[i]];
    const next = romanMap[upper[i + 1]] || 0;
    if (current < next) {
      result -= current;
    } else {
      result += current;
    }
  }
  return result;
}

async function main() {
  const { pdf, output } = parseArgs();

  try {
    const result = await detectFigures(pdf);
    const json = JSON.stringify(result, null, 2);

    if (output) {
      writeFileSync(output, json);
      console.error(`\nSaved to: ${output}`);
    } else {
      console.log(json);
    }
  } catch (error) {
    console.error("\nError:", error instanceof Error ? error.message : error);
    process.exit(1);
  }
}

main();
