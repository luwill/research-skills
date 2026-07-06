// Inline semantic emphasis — the "designed, not decorated" layer.
// A tiny, collision-proof markup that maps a phrase to ONE of four meanings, each rendered in a
// fixed color drawn from the deck's existing Okabe-Ito palette (color-blind safe). The discipline
// (≤2 emphasis roles per slide) is enforced in qa.mjs, not here.
//
//   ==text==     metric   weight-only bold   — numbers, deltas, complexities (no color added)
//   ==k|text==   key      accent bold        — the "so what" claim of the slide
//   ==p|text==   pos      green              — a win: SOTA, beats X, gold
//   ==w|text==   warn     vermillion         — a limitation / caution (critique slides)
//
// `==` is used because it never appears in academic prose; a `role|` prefix disambiguates the
// three colored roles from the default highlight. Content may not itself contain `==`.

export const ROLE_CLASS = { k: "key", p: "pos", w: "warn" };

// One canonical pattern shared by the renderer and the strippers (PPTX + notes + parity mirror it).
export const EMPHASIS_RE = /==(?:([kpw])\|)?([\s\S]+?)==/g;

// Render markers in an ALREADY-HTML-ESCAPED string into <span> tags. The captured content is the
// escaped text, and the only `<` we introduce is our own span — so this stays XSS-safe.
export function renderEmphasis(escaped) {
  if (escaped == null) return "";
  return String(escaped).replace(EMPHASIS_RE, (_m, role, txt) => {
    const cls = ROLE_CLASS[role] || "metric";
    return `<span class="${cls}">${txt}</span>`;
  });
}

// Drop the markers, keep the inner words — for any plain-text sink (PPTX runs, speaker-notes
// headings). Python's verify_pptx_parity.norm() mirrors this so parity stays exact.
export function stripEmphasis(text) {
  if (text == null) return "";
  return String(text).replace(EMPHASIS_RE, (_m, _role, txt) => txt);
}

// Which semantic roles does a raw string use? (metric | key | pos | warn) — for the QA discipline.
export function rolesIn(text) {
  const set = new Set();
  if (text == null) return set;
  const s = String(text);
  EMPHASIS_RE.lastIndex = 0;
  let m;
  while ((m = EMPHASIS_RE.exec(s))) set.add(ROLE_CLASS[m[1]] || "metric");
  return set;
}
