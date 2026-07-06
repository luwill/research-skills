// Server-side LaTeX -> vector/selectable HTML via KaTeX. This is the fidelity primitive
// that replaces ppt-master's external-web PNG and luwill's text-to-image equations: math
// stays true text/MathML, never a rasterized glyph soup.
import katex from "katex";
import { escapeHtml } from "./escape.mjs";
import { renderEmphasis } from "./emphasis.mjs";

export function renderMath(latex, { display = false } = {}) {
  return katex.renderToString(String(latex ?? ""), {
    displayMode: display,
    throwOnError: false,         // a bad macro becomes a visible red error span, not a crash
    output: "htmlAndMathml",      // MathML for accessibility + HTML for vector rendering
    strict: "ignore",
  });
}

// Render a body string that may contain inline `$...$` or display `$$...$$` math, plus inline
// semantic-emphasis markers (see emphasis.mjs). Non-math text is HTML-escaped and then has its
// emphasis markers turned into <span> tags; math is KaTeX-rendered. Emphasis runs per non-math
// slice, so a highlighted phrase must not straddle an inline-math boundary. Used for titles,
// notes, bullets, annotations, critique/discussion text.
export function renderText(text) {
  if (text == null) return "";
  const s = String(text);
  const re = /\$\$([\s\S]+?)\$\$|\$([^$\n]+?)\$/g;
  let out = "";
  let last = 0;
  let m;
  while ((m = re.exec(s))) {
    out += renderEmphasis(escapeHtml(s.slice(last, m.index)));
    if (m[1] != null) out += renderMath(m[1], { display: true });
    else out += renderMath(m[2], { display: false });
    last = re.lastIndex;
  }
  out += renderEmphasis(escapeHtml(s.slice(last)));
  return out;
}
