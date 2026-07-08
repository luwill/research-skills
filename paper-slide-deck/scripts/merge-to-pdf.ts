import { existsSync, readdirSync, readFileSync } from "fs";
import { join, basename, resolve } from "path";

interface SlideInfo {
  filename: string;
  path: string;
  index: number;
  promptPath?: string;
}

const SLIDE_PATTERN = /^(\d+)-slide-.*\.(png|jpg|jpeg)$/i;

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

/** Detect image format from magic bytes rather than the (possibly wrong) extension. */
function detectImageFormat(buf: Buffer): "png" | "jpg" {
  if (buf.length >= 4 && buf[0] === 0x89 && buf[1] === 0x50 && buf[2] === 0x4e && buf[3] === 0x47) {
    return "png";
  }
  if (buf.length >= 3 && buf[0] === 0xff && buf[1] === 0xd8 && buf[2] === 0xff) {
    return "jpg";
  }
  // Unknown signature — fall back to PNG (pdf-lib will surface a clear error).
  return "png";
}

function parseArgs(): { dir: string; output?: string } {
  const args = process.argv.slice(2);
  let dir = "";
  let output: string | undefined;

  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--output" || args[i] === "-o") {
      output = args[++i];
    } else if (!args[i].startsWith("-")) {
      dir = args[i];
    }
  }

  if (!dir) {
    console.error("Usage: bun merge-to-pdf.ts <slide-deck-dir> [--output filename.pdf]");
    process.exit(1);
  }

  return { dir, output };
}

function findSlideImages(dir: string): SlideInfo[] {
  if (!existsSync(dir)) {
    console.error(`Directory not found: ${dir}`);
    process.exit(1);
  }

  const promptsDir = join(dir, "prompts");
  const hasPrompts = existsSync(promptsDir);

  // Scan the deck root plus an optional slides/ subdirectory. Root wins on
  // duplicate filenames so both AI-generated and extracted slides are covered.
  const sources: Array<{ base: string; files: string[] }> = [
    { base: dir, files: readdirSync(dir) },
  ];
  const slidesSubdir = join(dir, "slides");
  if (existsSync(slidesSubdir)) {
    sources.push({ base: slidesSubdir, files: readdirSync(slidesSubdir) });
  }

  const seen = new Set<string>();
  const slides: SlideInfo[] = [];

  for (const { base, files } of sources) {
    for (const f of files) {
      if (!SLIDE_PATTERN.test(f) || seen.has(f)) continue;
      seen.add(f);
      const match = f.match(SLIDE_PATTERN)!;
      const baseName = f.replace(/\.(png|jpg|jpeg)$/i, "");
      const promptPath = hasPrompts ? join(promptsDir, `${baseName}.md`) : undefined;
      slides.push({
        filename: f,
        path: join(base, f),
        index: parseInt(match[1], 10),
        promptPath: promptPath && existsSync(promptPath) ? promptPath : undefined,
      });
    }
  }

  slides.sort((a, b) => a.index - b.index);

  if (slides.length === 0) {
    console.error(`No slide images found in: ${dir}`);
    console.error("Expected format: 01-slide-*.png, 02-slide-*.png, etc.");
    console.error("(Searched the deck root and an optional slides/ subdirectory.)");
    process.exit(1);
  }

  return slides;
}

async function createPdf(PDFDocument: any, slides: SlideInfo[], outputPath: string) {
  const pdfDoc = await PDFDocument.create();
  pdfDoc.setAuthor("paper-slide-deck");
  pdfDoc.setSubject("Generated Slide Deck");

  for (const slide of slides) {
    const imageData = readFileSync(slide.path);
    const format = detectImageFormat(imageData);
    const image = format === "png"
      ? await pdfDoc.embedPng(imageData)
      : await pdfDoc.embedJpg(imageData);

    const { width, height } = image;
    const page = pdfDoc.addPage([width, height]);

    page.drawImage(image, {
      x: 0,
      y: 0,
      width,
      height,
    });

    console.log(`Added: ${slide.filename} [${format}]${slide.promptPath ? " (prompt available)" : ""}`);
  }

  const pdfBytes = await pdfDoc.save();
  await Bun.write(outputPath, pdfBytes);

  console.log(`\nCreated: ${outputPath}`);
  console.log(`Total pages: ${slides.length}`);
}

async function main() {
  const { dir, output } = parseArgs();
  const slides = findSlideImages(dir);

  const { PDFDocument } = await loadDep("pdf-lib", () => import("pdf-lib"));

  // Resolve first: basename(".") is "." (yielding "..pdf"); resolve() gives the real dir name.
  const absDir = resolve(dir);
  const dirName = basename(absDir) === "slide-deck" ? basename(resolve(absDir, "..")) : basename(absDir);
  const outputPath = output || join(dir, `${dirName}.pdf`);

  console.log(`Found ${slides.length} slides in: ${dir}\n`);

  await createPdf(PDFDocument, slides, outputPath);
}

main().catch((err) => {
  console.error("Error:", err.message);
  process.exit(1);
});
