// Registered academic layouts (the guizang-style lock: a slide MUST use a registered
// layout; inventing one throws). Each renderer returns a <section data-layout="..."> whose
// CSS lives in assets/templates/themes/. This is the MVP set for a 组会 / journal-club deck.
import { escapeHtml } from "./escape.mjs";
import { renderText, renderMath } from "./math.mjs";
import { renderTable } from "./table.mjs";
import { renderFigure } from "./figure.mjs";

// reveal.js sets `display:block` inline on the active <section>, which would override a flex
// layout placed directly on it. So the full-stage flex column lives on an inner wrapper.
function section(layout, cls, inner) {
  return `<section data-layout="${layout}"><div class="slide-inner ${cls}">${inner}</div></section>`;
}

function titleBar(s) {
  const eyebrow = s.eyebrow ? `<div class="s-eyebrow">${escapeHtml(s.eyebrow)}</div>` : "";
  const title = s.action_title || s.title || "";
  return `<div class="s-title-bar">${eyebrow}<h2 class="s-action-title">${renderText(title)}</h2></div>`;
}

function source(s) {
  return s.source_ref
    ? `<div class="s-source"><span class="cite">${escapeHtml(s.source_ref)}</span></div>`
    : "";
}

function list(points) {
  return `<ul>${(points || []).map((p) => `<li>${renderText(p)}</li>`).join("")}</ul>`;
}

const L = {
  "paper-title": (s) =>
    section(
      "paper-title",
      "s-paper-title",
      `<h1>${renderText(s.title)}</h1>` +
        (s.authors
          ? `<div class="authors">${escapeHtml(
              Array.isArray(s.authors) ? s.authors.join(", ") : s.authors
            )}</div>`
          : "") +
        (s.affiliation ? `<div class="affil">${escapeHtml(s.affiliation)}</div>` : "") +
        (s.venue ? `<div class="venue">${escapeHtml(s.venue)}</div>` : "") +
        (s.presenter ? `<div class="presenter">${escapeHtml(s.presenter)}</div>` : "")
    ),

  section: (s) =>
    section(
      "section",
      "s-section",
      (s.num ? `<div class="num">${escapeHtml(s.num)}</div>` : "") +
        `<h2>${renderText(s.title)}</h2>`
    ),

  "outline-agenda": (s) =>
    section(
      "outline-agenda",
      "s-agenda",
      titleBar(s) +
        `<div class="s-body"><ol>${(s.items || [])
          .map((it, i) => `<li class="${i === s.current ? "cur" : ""}">${renderText(it)}</li>`)
          .join("")}</ol></div>`
    ),

  // figure.hero: the figure IS the slide — its caption folds into the source footer and the
  // annotation is banned (validateSpec), returning the whole vertical budget to the image.
  "assertion-evidence": (s, ctx) => {
    const hero = !!s.figure?.hero;
    const fig = hero ? { ...s.figure, caption: null } : s.figure;
    let foot = source(s);
    if (hero && (s.figure.caption || s.source_ref)) {
      const cite = s.figure.cite ? ` <span class="cite">[${escapeHtml(s.figure.cite)}]</span>` : "";
      const cap = s.figure.caption ? `${escapeHtml(s.figure.caption)}${cite}` : "";
      const ref = s.source_ref ? `<span class="cite">${escapeHtml(s.source_ref)}</span>` : "";
      foot = `<div class="s-source">${[cap, ref].filter(Boolean).join(" · ")}</div>`;
    }
    return section(
      "assertion-evidence",
      hero ? "s-ae s-ae--hero" : "s-ae",
      titleBar(s) +
        `<div class="s-body">${s.figure ? renderFigure(fig, ctx) : ""}${
          s.annotation ? `<div class="s-annotation">${renderText(s.annotation)}</div>` : ""
        }</div>` +
        foot
    );
  },

  equation: (s) =>
    section(
      "equation",
      "s-equation",
      titleBar(s) +
        `<div class="s-body">${(s.equations || [])
          .map(
            (e) =>
              `<div class="eq">${renderMath(e.latex, { display: true })}${
                e.numbered ? `<span class="eq-num">(${escapeHtml(e.num || "")})</span>` : ""
              }</div>`
          )
          .join("")}${s.note ? `<div class="note">${renderText(s.note)}</div>` : ""}</div>` +
        source(s)
    ),

  "results-table": (s) =>
    section(
      "results-table",
      "s-results",
      titleBar(s) + `<div class="s-body">${renderTable(s.table)}</div>` + source(s)
    ),

  "two-column": (s, ctx) =>
    section(
      "two-column",
      "s-two-col",
      titleBar(s) +
        `<div class="s-body"><div class="cols">` +
        `<div class="col-text">${s.points ? list(s.points) : renderText(s.text || "")}</div>` +
        `<div class="col-fig">${s.figure ? renderFigure(s.figure, ctx) : list(s.points2 || [])}</div>` +
        `</div></div>` +
        source(s)
    ),

  "critique-concerns": (s) =>
    section(
      "critique-concerns",
      "s-critique",
      titleBar(s) +
        `<div class="s-body">${(s.points || [])
          .map(
            (p) =>
              `<div class="pt"><div class="head">${renderText(p.head)}</div>` +
              `<div class="body">${renderText(p.body)}</div></div>`
          )
          .join("")}</div>` +
        source(s)
    ),

  "discussion-questions": (s) =>
    section(
      "discussion-questions",
      "s-discussion",
      titleBar(s) +
        `<div class="s-body"><ul>${(s.questions || [])
          .map((q) => `<li>${renderText(q)}</li>`)
          .join("")}</ul></div>`
    ),

  bullets: (s) =>
    section("bullets", "s-bullets", titleBar(s) + `<div class="s-body">${list(s.points)}</div>` + source(s)),

  references: (s) =>
    section(
      "references",
      "s-references",
      titleBar(s) +
        // < 4 entries: two CSS columns read as scattered fragments — set them as one list.
        `<div class="s-body"><ol${(s.entries || []).length < 4 ? ' class="single"' : ""}>${(s.entries || [])
          .map((e) => `<li>${renderText(e)}</li>`)
          .join("")}</ol></div>`
    ),
};

export const LAYOUTS = L;
export const REGISTERED = Object.keys(L);

// The core field each layout needs to render meaningful content. Renderers throw for a few
// (figure.src, table shape); this catches the rest BEFORE build so a missing/misspelled field is
// a clear error, not a silently empty slide. Returns [] for a valid spec.
const REQUIRED = {
  "paper-title": ["title"], section: ["title"], "outline-agenda": ["items"],
  equation: ["equations"], "results-table": ["table"], "critique-concerns": ["points"],
  "discussion-questions": ["questions"], bullets: ["points"], references: ["entries"],
  // assertion-evidence (figure.src enforced by renderer) and two-column are intentionally lenient.
};
// Layouts that present data from the paper: they should carry a provenance ref (warn, not block).
const FACTUAL = new Set(["assertion-evidence", "results-table", "equation", "two-column"]);

const isEmpty = (v) =>
  v == null || (Array.isArray(v) && v.length === 0) || (typeof v === "string" && v.trim() === "");

export function validateSpec(deck) {
  const problems = [];
  (deck?.slides || []).forEach((s, i) => {
    const slide = i + 1;
    if (!L[s.layout]) {
      problems.push({ slide, layout: s.layout, field: "layout", severity: "error",
        detail: `unknown layout "${s.layout}". Registered: ${REGISTERED.join(", ")}` });
      return; // field checks are meaningless without a known layout
    }
    for (const f of REQUIRED[s.layout] || []) {
      if (isEmpty(s[f])) {
        problems.push({ slide, layout: s.layout, field: f, severity: "error",
          detail: `${s.layout} slide ${slide} is missing required field "${f}"` });
      }
    }
    if (FACTUAL.has(s.layout) && isEmpty(s.source_ref)) {
      problems.push({ slide, layout: s.layout, field: "source_ref", severity: "warn",
        detail: `${s.layout} slide ${slide} has no source_ref — provenance is expected on a factual slide` });
    }
    if (s.figure?.hero && !isEmpty(s.annotation)) {
      problems.push({ slide, layout: s.layout, field: "annotation", severity: "error",
        detail: `slide ${slide}: a hero figure cannot carry an annotation — the mode exists to return that vertical budget to the image; move the text to speaker_notes` });
    }
  });
  return problems;
}

export function renderSlide(slide, ctx) {
  const fn = L[slide.layout];
  if (!fn) {
    throw new Error(
      `unknown layout "${slide.layout}". Registered: ${REGISTERED.join(", ")}`
    );
  }
  let html = fn(slide, ctx);
  if (slide.speaker_notes) {
    // reveal.js convention: notes live in an <aside class="notes"> inside the section,
    // hidden on-slide and shown in the speaker view ('s'). Hidden in print too (print.css).
    const aside = `<aside class="notes">${escapeHtml(slide.speaker_notes)}</aside>`;
    html = html.replace(/<\/section>$/, `${aside}</section>`);
  }
  return html;
}
