/**
 * apply-template.ts
 * Apply the academic-paper figure container template to an extracted figure.
 *
 * Usage:
 *   npx -y bun apply-template.ts --figure figure.png --title "Title" --caption "Figure 1: Caption" --output slide.png
 *
 * Options:
 *   --figure   Path to extracted figure image (required)
 *   --title    Slide title/headline (required)
 *   --caption  Figure caption, e.g., "Figure 1: Description" (required)
 *   --output   Output slide PNG file path (required)
 *   --width    Output width, default 1920 (optional)
 *   --height   Output height, default 1080 (optional)
 */

import { existsSync, writeFileSync, mkdirSync } from "fs";
import { dirname, resolve } from "path";

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

// Color palette from academic-paper style
const COLORS = {
  background: "#FFFFFF",
  titleText: "#1E3A5F",
  captionText: "#6B7280",
  border: "#E5E7EB",
  shadow: "rgba(0, 0, 0, 0.1)",
};

// Layout constants
const LAYOUT = {
  titleY: 80,
  titleFontSize: 48,
  captionFontSize: 24,
  figureMaxWidthRatio: 0.85,
  figureMaxHeightRatio: 0.65,
  padding: 20,
  borderRadius: 8,
  marginBottom: 80,
};

interface Args {
  figure: string;
  title: string;
  caption: string;
  output: string;
  width: number;
  height: number;
  font: string;
}

function parseArgs(): Args {
  const args = process.argv.slice(2);
  let figure = "";
  let title = "";
  let caption = "";
  let output = "";
  let width = 1920;
  let height = 1080;
  // Default sans-serif stack. Override with --font for CJK titles/captions,
  // e.g. --font "Noto Sans CJK SC, Arial, sans-serif" on Linux.
  let font = "Arial, Helvetica, sans-serif";

  for (let i = 0; i < args.length; i++) {
    switch (args[i]) {
      case "--figure":
        figure = args[++i];
        break;
      case "--title":
        title = args[++i];
        break;
      case "--caption":
        caption = args[++i];
        break;
      case "--output":
        output = args[++i];
        break;
      case "--width":
        width = parseInt(args[++i], 10);
        break;
      case "--height":
        height = parseInt(args[++i], 10);
        break;
      case "--font":
        font = args[++i];
        break;
    }
  }

  if (!figure || !title || !caption || !output) {
    console.error("Usage: bun apply-template.ts --figure <image> --title <title> --caption <caption> --output <output.png>");
    console.error("\nOptions:");
    console.error("  --figure   Path to extracted figure image (required)");
    console.error("  --title    Slide title/headline (required)");
    console.error("  --caption  Figure caption (required)");
    console.error("  --output   Output slide PNG file path (required)");
    console.error("  --width    Output width, default 1920 (optional)");
    console.error("  --height   Output height, default 1080 (optional)");
    console.error('  --font     CSS font-family stack, default "Arial, Helvetica, sans-serif" (optional; set for CJK)');
    process.exit(1);
  }

  return { figure, title, caption, output, width, height, font };
}

function wrapText(ctx: any, text: string, maxWidth: number): string[] {
  const words = text.split(" ");
  const lines: string[] = [];
  let currentLine = "";

  for (const word of words) {
    const testLine = currentLine ? `${currentLine} ${word}` : word;
    const metrics = ctx.measureText(testLine);

    if (metrics.width > maxWidth && currentLine) {
      lines.push(currentLine);
      currentLine = word;
    } else {
      currentLine = testLine;
    }
  }

  if (currentLine) {
    lines.push(currentLine);
  }

  return lines;
}

function drawRoundedRect(
  ctx: any,
  x: number,
  y: number,
  width: number,
  height: number,
  radius: number
) {
  ctx.beginPath();
  ctx.moveTo(x + radius, y);
  ctx.lineTo(x + width - radius, y);
  ctx.quadraticCurveTo(x + width, y, x + width, y + radius);
  ctx.lineTo(x + width, y + height - radius);
  ctx.quadraticCurveTo(x + width, y + height, x + width - radius, y + height);
  ctx.lineTo(x + radius, y + height);
  ctx.quadraticCurveTo(x, y + height, x, y + height - radius);
  ctx.lineTo(x, y + radius);
  ctx.quadraticCurveTo(x, y, x + radius, y);
  ctx.closePath();
}

async function applyTemplate(args: Args) {
  const { figure, title, caption, output, width, height, font } = args;

  // Load canvas dynamically so a missing install produces a clear hint.
  const { createCanvas, loadImage } = await loadDep("canvas", () => import("canvas"));

  // Validate figure exists
  const absoluteFigurePath = resolve(figure);
  if (!existsSync(absoluteFigurePath)) {
    throw new Error(`Figure image not found: ${absoluteFigurePath}`);
  }

  console.log(`Loading figure: ${absoluteFigurePath}`);

  // Load the figure image
  const figureImage = await loadImage(absoluteFigurePath);
  console.log(`Figure size: ${figureImage.width}x${figureImage.height}`);

  // Create output canvas
  const canvas = createCanvas(width, height);
  const ctx = canvas.getContext("2d");

  // Scale factors for different resolutions
  const scaleFactor = width / 1920;
  const titleFontSize = Math.round(LAYOUT.titleFontSize * scaleFactor);
  const captionFontSize = Math.round(LAYOUT.captionFontSize * scaleFactor);
  const padding = Math.round(LAYOUT.padding * scaleFactor);
  const borderRadius = Math.round(LAYOUT.borderRadius * scaleFactor);

  // Fill background
  ctx.fillStyle = COLORS.background;
  ctx.fillRect(0, 0, width, height);

  // Draw title
  ctx.fillStyle = COLORS.titleText;
  ctx.font = `bold ${titleFontSize}px ${font}`;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";

  const titleMaxWidth = width * 0.9;
  const titleLines = wrapText(ctx, title, titleMaxWidth);
  const titleLineHeight = titleFontSize * 1.3;
  const titleStartY = Math.round(LAYOUT.titleY * scaleFactor);

  titleLines.forEach((line, index) => {
    ctx.fillText(line, width / 2, titleStartY + index * titleLineHeight);
  });

  // Calculate figure area
  const titleBottomY = titleStartY + titleLines.length * titleLineHeight + padding * 2;
  const captionY = height - Math.round(LAYOUT.marginBottom * scaleFactor);
  const figureAreaHeight = captionY - titleBottomY - padding * 2;

  const maxFigureWidth = width * LAYOUT.figureMaxWidthRatio;
  const maxFigureHeight = Math.min(height * LAYOUT.figureMaxHeightRatio, figureAreaHeight);

  // Calculate scaled figure dimensions
  const figureAspect = figureImage.width / figureImage.height;
  let scaledWidth: number;
  let scaledHeight: number;

  if (figureAspect > maxFigureWidth / maxFigureHeight) {
    // Width constrained
    scaledWidth = maxFigureWidth;
    scaledHeight = scaledWidth / figureAspect;
  } else {
    // Height constrained
    scaledHeight = maxFigureHeight;
    scaledWidth = scaledHeight * figureAspect;
  }

  // Center figure horizontally and vertically in available space
  const figureX = (width - scaledWidth) / 2;
  const figureY = titleBottomY + (figureAreaHeight - scaledHeight) / 2;

  // Draw figure container with shadow and border
  const containerX = figureX - padding;
  const containerY = figureY - padding;
  const containerWidth = scaledWidth + padding * 2;
  const containerHeight = scaledHeight + padding * 2;

  // Shadow
  ctx.save();
  ctx.shadowColor = COLORS.shadow;
  ctx.shadowBlur = 12 * scaleFactor;
  ctx.shadowOffsetX = 0;
  ctx.shadowOffsetY = 4 * scaleFactor;
  ctx.fillStyle = COLORS.background;
  drawRoundedRect(ctx, containerX, containerY, containerWidth, containerHeight, borderRadius);
  ctx.fill();
  ctx.restore();

  // Border
  ctx.strokeStyle = COLORS.border;
  ctx.lineWidth = 1;
  drawRoundedRect(ctx, containerX, containerY, containerWidth, containerHeight, borderRadius);
  ctx.stroke();

  // Draw figure
  ctx.drawImage(figureImage, figureX, figureY, scaledWidth, scaledHeight);

  // Draw caption
  ctx.fillStyle = COLORS.captionText;
  ctx.font = `italic ${captionFontSize}px ${font}`;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";

  const captionMaxWidth = width * 0.85;
  const captionLines = wrapText(ctx, caption, captionMaxWidth);
  const captionLineHeight = captionFontSize * 1.4;

  captionLines.forEach((line, index) => {
    ctx.fillText(line, width / 2, captionY + index * captionLineHeight);
  });

  // Ensure output directory exists
  const outputDir = dirname(output);
  if (outputDir && !existsSync(outputDir)) {
    mkdirSync(outputDir, { recursive: true });
  }

  // Save as PNG
  const buffer = canvas.toBuffer("image/png");
  writeFileSync(output, buffer);

  console.log(`\nSaved: ${output}`);
  console.log(`Size: ${width}x${height}`);
  console.log(`File size: ${Math.round(buffer.length / 1024)} KB`);
}

async function main() {
  const args = parseArgs();

  try {
    await applyTemplate(args);
    console.log("\nTemplate applied successfully!");
  } catch (error) {
    console.error("\nError:", error instanceof Error ? error.message : error);
    process.exit(1);
  }
}

main();
