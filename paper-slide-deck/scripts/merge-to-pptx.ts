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

/** Detect image MIME type from magic bytes rather than the (possibly wrong) extension. */
function detectMimeType(buf: Buffer): string {
  if (buf.length >= 4 && buf[0] === 0x89 && buf[1] === 0x50 && buf[2] === 0x4e && buf[3] === 0x47) {
    return "image/png";
  }
  if (buf.length >= 3 && buf[0] === 0xff && buf[1] === 0xd8 && buf[2] === 0xff) {
    return "image/jpeg";
  }
  return "image/png";
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
    console.error("Usage: bun merge-to-pptx.ts <slide-deck-dir> [--output filename.pptx]");
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

function findBasePrompt(): string | undefined {
  const scriptDir = import.meta.dir;
  const basePromptPath = join(scriptDir, "..", "references", "base-prompt.md");
  if (existsSync(basePromptPath)) {
    return readFileSync(basePromptPath, "utf-8");
  }
  return undefined;
}

async function createPptx(PptxGenJS: any, slides: SlideInfo[], outputPath: string) {
  const pptx = new PptxGenJS();

  pptx.layout = "LAYOUT_16x9";
  pptx.author = "paper-slide-deck";
  pptx.subject = "Generated Slide Deck";

  const basePrompt = findBasePrompt();
  let notesCount = 0;

  for (const slide of slides) {
    const s = pptx.addSlide();
    const imageData = readFileSync(slide.path);
    const base64 = imageData.toString("base64");
    const mimeType = detectMimeType(imageData);

    s.addImage({
      data: `data:${mimeType};base64,${base64}`,
      x: 0,
      y: 0,
      w: "100%",
      h: "100%",
      sizing: { type: "cover", w: "100%", h: "100%" },
    });

    if (slide.promptPath) {
      const slidePrompt = readFileSync(slide.promptPath, "utf-8");
      const fullNotes = basePrompt ? `${basePrompt}\n\n---\n\n${slidePrompt}` : slidePrompt;
      s.addNotes(fullNotes);
      notesCount++;
    }

    console.log(`Added: ${slide.filename}${slide.promptPath ? " (with notes)" : ""}`);
  }

  await pptx.writeFile({ fileName: outputPath });
  console.log(`\nCreated: ${outputPath}`);
  console.log(`Total slides: ${slides.length}`);
  if (notesCount > 0) {
    console.log(`Slides with notes: ${notesCount}${basePrompt ? " (includes base prompt)" : ""}`);
  }
}

async function main() {
  const { dir, output } = parseArgs();
  const slides = findSlideImages(dir);

  const PptxGenJS = (await loadDep("pptxgenjs", () => import("pptxgenjs"))).default;

  // Resolve first: basename(".") is "." (yielding "..pptx"); resolve() gives the real dir name.
  const absDir = resolve(dir);
  const dirName = basename(absDir) === "slide-deck" ? basename(resolve(absDir, "..")) : basename(absDir);
  const outputPath = output || join(dir, `${dirName}.pptx`);

  console.log(`Found ${slides.length} slides in: ${dir}\n`);

  await createPptx(PptxGenJS, slides, outputPath);
}

main().catch((err) => {
  console.error("Error:", err.message);
  process.exit(1);
});
