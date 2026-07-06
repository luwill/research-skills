// Speaker notes & timing. Academic talks are spoken: the on-slide text is thin and the
// script lives in the notes. Timing is estimated from the notes (the actual spoken words),
// not the slide text, and is bilingual-aware (English words/min + CJK characters/min).

import { stripInlineMath } from "./pptx_layout.mjs";

const CJK = /[㐀-鿿豈-﫿぀-ヿ]/g;        // CJK ideographs + kana
const CJK_PUNCT = /[　-〿＀-￯]/g;               // CJK/full-width punctuation

export function countText(s) {
  s = String(s ?? "");
  const cjkChars = (s.match(CJK) || []).length;
  const latinWords = (s.replace(CJK, " ").replace(CJK_PUNCT, " ").match(/[A-Za-z0-9][A-Za-z0-9'’\-]*/g) || []).length;
  return { cjkChars, latinWords };
}

// English ~130 wpm spoken; Mandarin ~240 chars/min spoken.
export function minutesFor(text, { wpm = 130, cpm = 240 } = {}) {
  const { cjkChars, latinWords } = countText(text);
  return latinWords / wpm + cjkChars / cpm;
}

export function slideTimings(deck, opts = {}) {
  const floor = opts.floorMin ?? 0.5; // a slide with no notes still takes ~30s to present
  return (deck.slides || []).map((s, i) => {
    const notes = s.speaker_notes || "";
    const spoken = notes ? minutesFor(notes, opts) : 0;
    return { slide: i + 1, layout: s.layout, hasNotes: !!notes, words: countText(notes), minutes: Math.max(spoken, floor) };
  });
}

export function timingReport(deck, opts = {}) {
  const slides = slideTimings(deck, opts);
  const totalMinutes = slides.reduce((a, x) => a + x.minutes, 0);
  return { slides, totalMinutes, budgetMinutes: opts.budgetMin ?? null, withoutNotes: slides.filter((s) => !s.hasNotes).map((s) => s.slide) };
}

function title(s) {
  return stripInlineMath(s.action_title || s.title || `(${s.layout})`);
}

export function notesHandout(deck, opts = {}) {
  const t = timingReport(deck, opts);
  const fmt = (m) => `${Math.floor(m)}:${String(Math.round((m % 1) * 60)).padStart(2, "0")}`;
  const lines = [`# Speaker notes — ${deck.meta?.title || "deck"}`, ""];
  lines.push(`**Estimated total: ${fmt(t.totalMinutes)}**` + (t.budgetMinutes ? ` (budget ${t.budgetMinutes} min)` : ""), "");
  (deck.slides || []).forEach((s, i) => {
    const st = t.slides[i];
    lines.push(`## Slide ${i + 1} — ${title(s)}  _(${fmt(st.minutes)})_`);
    lines.push(s.speaker_notes ? s.speaker_notes : "_[no notes — add a spoken script]_");
    lines.push("");
  });
  return lines.join("\n");
}
