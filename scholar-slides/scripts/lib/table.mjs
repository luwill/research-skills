// Real results tables (never a picture of a table). Baselines labeled, best bolded,
// units in headers, optional footnote. Cells are strings/numbers, or {v, bold} to emphasize.
import { escapeHtml } from "./escape.mjs";

function cellHtml(cell) {
  const v = cell && typeof cell === "object" ? cell.v : cell;
  const inner = escapeHtml(v);
  return cell && typeof cell === "object" && cell.bold ? `<strong>${inner}</strong>` : inner;
}

export function renderTable(t) {
  if (!t || !Array.isArray(t.columns) || !Array.isArray(t.rows)) {
    throw new Error("renderTable: table needs {columns, rows}");
  }
  const caption = t.caption ? `<caption>${escapeHtml(t.caption)}</caption>` : "";
  const head =
    `<thead><tr>` +
    t.columns
      .map((c) => {
        const label = escapeHtml(c.label ?? c);
        const unit = c.unit ? `<span class="u">${escapeHtml(c.unit)}</span>` : "";
        return `<th>${label}${unit}</th>`;
      })
      .join("") +
    `</tr></thead>`;
  const body =
    `<tbody>` +
    t.rows
      .map(
        (r) =>
          `<tr>` +
          r
            .map((cell, ci) => {
              const tag = t.row_header && ci === 0 ? "th" : "td";
              return `<${tag}>${cellHtml(cell)}</${tag}>`;
            })
            .join("") +
          `</tr>`
      )
      .join("") +
    `</tbody>`;
  const foot = t.footnote
    ? `<tfoot><tr><td colspan="${t.columns.length}">${escapeHtml(t.footnote)}</td></tr></tfoot>`
    : "";
  return `<table class="results">${caption}${head}${body}${foot}</table>`;
}
