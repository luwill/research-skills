# Citations — Zotero-first, Crossref fallback, references slide

**Status: live (Stage 3).** Grounds every citation in a real record; an unresolved citation
is flagged `[UNVERIFIED]`, never written from memory.

## Resolution order (per cite query: a DOI, arXiv id, or title)
1. **Zotero first (agent runtime).** Search the user's library with `mcp__zotero__*`
   (`zotero_search_items` / `zotero_advanced_search` / `zotero_search_by_citation_key`). The
   library is the system of record — best dedup and provenance. Take a hit only if it clearly
   matches (title + author/year).
2. **Crossref / arXiv / DOI fallback (script).** For anything not in Zotero:
   ```
   ./.venv/bin/python scripts/fetch_bib.py 1706.03762 10.1145/3292500.3330701 "Some Title" --out out/<stem>/bib.json
   ```
   `fetch_bib.resolve(query)` returns a verified entry `{key, title, authors, year, venue, doi,
   arxiv, formatted, resolved:true}` or `{resolved:false}`.
3. **Unresolved → `[UNVERIFIED: <query>]`.** Surface it; never invent authors/year/venue/DOI.

## Integrity guards built into the resolver
- **Prefer exact identifiers.** arXiv id and DOI resolve deterministically. A **title-only**
  query is accepted only if the returned title matches order-sensitively (`title_match`):
  exact, a subtitle extension of a specific title, or ratio ≥ 0.95. This deliberately rejects
  same-word reorderings (e.g. Crossref returning *"Is Attention All You Need?"* for *"Attention
  Is All You Need"* — a different paper). An ambiguous title yields `[UNVERIFIED]`, by design.
- Network/parse failure → `{resolved:false}`, never a guessed entry.

## Building the references slide
- Collect every work the deck cites (figure `cite`, in-text `[Author Year]`, baseline rows).
- Resolve each (Zotero → Crossref). Use `fetch_bib.format_reference(entry)` for the display
  string and `make_key` for a stable in-text key.
- Render the `references` layout with the resolved entries; keep any `[UNVERIFIED]` entries
  visible (the QA gate counts them; they are acknowledged at CKPT-3).
- Baseline references inside a paper (e.g. the comparison table's `[9,18,32,38,39]`) come from
  the paper's own bibliography; extract their titles/DOIs from the source before resolving.

## Discipline
- A citation on a slide must correspond to a resolved entry or an explicit `[UNVERIFIED]`.
- Do not upgrade a tentative title match into a confident citation — when unsure, flag it and
  ask the user (or point them to add it to Zotero).
