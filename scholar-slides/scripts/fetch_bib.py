#!/usr/bin/env python3
"""Citation resolver (verifiable fallback for the Zotero-first flow).

The skill resolves citations Zotero-first at runtime via the `mcp__zotero__*` tools (the
user's library is the system of record). Anything not in the library falls through to THIS
script, which resolves a citation against arXiv / DOI / Crossref over HTTP and returns a
verified entry — so a reference is grounded in a real record, never written from memory.
An unresolved query yields {resolved: false} and the caller emits `[UNVERIFIED]`.

Pure parsers (`parse_crossref_message`, `parse_arxiv_atom`, `make_key`, `format_reference`,
`classify_query`) are unit-tested; the `fetch_*` / `resolve*` functions do the HTTP.
"""
from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET

_ARXIV_ID = re.compile(r"^(?:arxiv:)?(\d{4}\.\d{4,5})(?:v\d+)?$", re.IGNORECASE)
_DOI = re.compile(r"^(?:doi:)?(10\.\d{4,9}/\S+)$", re.IGNORECASE)


def classify_query(q):
    """Return ('arxiv'|'doi'|'title', normalized_value)."""
    q = (q or "").strip()
    m = _ARXIV_ID.match(q)
    if m:
        return ("arxiv", m.group(1))
    m = _DOI.match(q)
    if m:
        return ("doi", m.group(1))
    return ("title", q)


def _norm_title(s):
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def title_match(query, result, threshold=0.95):
    """Order-sensitive title verification, to guard against Crossref returning a
    confidently-wrong top hit (which would fabricate a citation). Accepts only: an exact
    normalized match; a prefix/subtitle extension of a sufficiently specific title; or a
    very high character-sequence ratio. Deliberately rejects same-bag reorderings like
    'Is Attention All You Need?' vs 'Attention Is All You Need'."""
    import difflib

    a, b = _norm_title(query), _norm_title(result)
    if not a or not b:
        return False
    if a == b:
        return True
    short, long = sorted((a, b), key=len)
    if len(short) >= 15 and long.startswith(short):  # subtitle extension of a specific title
        return True
    return difflib.SequenceMatcher(None, a, b).ratio() >= threshold


def make_key(authors, year):
    """A BibTeX-ish key: first author's family name (lowercased, ascii word) + year."""
    fam = ""
    if authors:
        fam = authors[0].split()[-1] if isinstance(authors[0], str) else authors[0].get("family", "")
    fam = re.sub(r"[^a-z]", "", (fam or "anon").lower()) or "anon"
    return f"{fam}{year or ''}"


def format_reference(e):
    """A human-readable reference string for the references slide."""
    authors = e.get("authors") or []
    if len(authors) > 6:
        who = ", ".join(authors[:3]) + " et al."
    else:
        who = ", ".join(authors)
    parts = [who, f"({e.get('year')})" if e.get("year") else "", f"{e.get('title')}."]
    if e.get("venue"):
        parts.append(f"{e['venue']}.")
    tail = e.get("doi") and f"https://doi.org/{e['doi']}" or (e.get("arxiv") and f"arXiv:{e['arxiv']}")
    if tail:
        parts.append(tail)
    return " ".join(p for p in parts if p).strip()


def _entry(title, authors, year, venue, doi, arxiv, source, etype="article"):
    e = {
        "key": make_key(authors, year),
        "title": title,
        "authors": authors,
        "year": str(year) if year else None,
        "venue": venue,
        "doi": doi,
        "arxiv": arxiv,
        "type": etype,
        "source": source,
        "resolved": True,
    }
    e["formatted"] = format_reference(e)
    return e


def parse_crossref_message(msg):
    """Crossref work item dict -> entry."""
    title = (msg.get("title") or ["(untitled)"])[0]
    authors = [" ".join(p for p in [a.get("given"), a.get("family")] if p) for a in msg.get("author", [])]
    year = None
    for k in ("published-print", "published-online", "issued", "created"):
        dp = (msg.get(k) or {}).get("date-parts")
        if dp and dp[0] and dp[0][0]:
            year = dp[0][0]
            break
    venue = (msg.get("container-title") or [None])[0]
    etype = "inproceedings" if (msg.get("type") or "").startswith("proceedings") else "article"
    return _entry(title, authors, year, venue, msg.get("DOI"), None, "crossref", etype)


def parse_arxiv_atom(xml_text):
    """arXiv Atom API response -> entry (first entry), or None if no entry."""
    ns = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
    root = ET.fromstring(xml_text)
    e = root.find("a:entry", ns)
    if e is None:
        return None
    title = " ".join((e.findtext("a:title", "", ns) or "").split())
    authors = [" ".join((n.text or "").split()) for n in e.findall("a:author/a:name", ns)]
    published = e.findtext("a:published", "", ns) or ""
    year = published[:4] or None
    id_url = e.findtext("a:id", "", ns) or ""
    arxiv = id_url.split("/abs/")[-1].split("v")[0] if "/abs/" in id_url else None
    doi = e.findtext("arxiv:doi", None, ns)
    venue = e.findtext("arxiv:journal_ref", None, ns) or "arXiv preprint"
    return _entry(title, authors, year, venue, doi, arxiv, "arxiv")


# ---- network ----
def fetch_arxiv(arxiv_id):
    import requests
    r = requests.get("http://export.arxiv.org/api/query", params={"id_list": arxiv_id},
                     timeout=30, headers={"User-Agent": "scholar-slides/0.1"})
    r.raise_for_status()
    return parse_arxiv_atom(r.text)


def fetch_crossref_by_doi(doi):
    import requests
    r = requests.get(f"https://api.crossref.org/works/{doi}", timeout=30,
                     headers={"User-Agent": "scholar-slides/0.1 (mailto:noreply@example.com)"})
    if r.status_code != 200:
        return None
    return parse_crossref_message(r.json()["message"])


def fetch_crossref_by_title(title):
    import requests
    r = requests.get("https://api.crossref.org/works",
                     params={"query.bibliographic": title, "rows": 1},
                     timeout=30, headers={"User-Agent": "scholar-slides/0.1 (mailto:noreply@example.com)"})
    if r.status_code != 200:
        return None
    items = r.json()["message"].get("items") or []
    if not items:
        return None
    entry = parse_crossref_message(items[0])
    # Reject a confidently-wrong top hit: only trust it if the returned title matches.
    if not title_match(title, entry.get("title")):
        return None
    return entry


def resolve(query):
    """Resolve one citation query to a verified entry, or {resolved: False, query}."""
    kind, val = classify_query(query)
    try:
        if kind == "arxiv":
            e = fetch_arxiv(val)
        elif kind == "doi":
            e = fetch_crossref_by_doi(val)
        else:
            e = fetch_crossref_by_title(val)
    except Exception as exc:  # network/parse failure -> unresolved, never fabricated
        return {"resolved": False, "query": query, "error": str(exc)}
    return e or {"resolved": False, "query": query}


def resolve_all(queries):
    return [resolve(q) for q in queries]


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(description="Resolve citations via arXiv/DOI/Crossref (Zotero-first fallback).")
    ap.add_argument("queries", nargs="*", help="arXiv ids, DOIs, or titles")
    ap.add_argument("--json", help="read a JSON array of queries from this file")
    ap.add_argument("--out", help="write resolved bib.json here")
    args = ap.parse_args(argv)

    queries = list(args.queries)
    if args.json:
        queries += json.load(open(args.json, encoding="utf-8"))
    results = resolve_all(queries)
    if args.out:
        json.dump(results, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    n_ok = sum(1 for r in results if r.get("resolved"))
    for r in results:
        if r.get("resolved"):
            print(f"  [ok]  {r['key']}: {r['formatted']}")
        else:
            print(f"  [UNVERIFIED] {r.get('query')}")
    print(f"resolved {n_ok}/{len(results)}")


if __name__ == "__main__":
    main(sys.argv[1:])
