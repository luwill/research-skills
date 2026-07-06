// Reused source figure: the real bbox-cropped image + caption + mandatory provenance cite.
// fit defaults to "contain" — a scientific figure is NEVER cropped/cover-fit.
import { escapeHtml } from "./escape.mjs";

export function renderFigure(f) {
  if (!f || !f.src) throw new Error("renderFigure: figure needs a src");
  const cite = f.cite ? ` <span class="cite">[${escapeHtml(f.cite)}]</span>` : "";
  const caption = f.caption ? `<figcaption>${escapeHtml(f.caption)}${cite}</figcaption>` : "";
  const alt = escapeHtml(f.alt || f.caption || "figure");
  const fit = f.fit === "cover" ? "cover" : "contain";
  return (
    `<figure class="s-figure">` +
    `<img src="${escapeHtml(f.src)}" alt="${alt}" style="object-fit:${fit}">` +
    `${caption}</figure>`
  );
}
