# MCP Server Configuration for Literature Collection

Set up arxiv-mcp / pubmedmcp / zotero-mcp for use in Phase 2 (Literature Collection + Verification). For each server, this file documents installation, tools available, and the searches that match the workflow.

---

## ArXiv MCP (Preprints & Latest Research)

**Repository:** https://github.com/blazickjp/arxiv-mcp-server

### Configuration

Add to `~/.claude/mcp.json` (or your MCP config file):

```json
{
  "mcpServers": {
    "arxiv": {
      "command": "uvx",
      "args": ["arxiv-mcp-server"],
      "env": {
        "ARXIV_STORAGE_PATH": "~/.arxiv-mcp-server/papers"
      }
    }
  }
}
```

### Available tools

| Tool | Purpose |
|---|---|
| `mcp__arxiv-mcp-server__search_papers` | Search by keywords with date range and category filters |
| `mcp__arxiv-mcp-server__download_paper` | Download paper PDF by arXiv ID |
| `mcp__arxiv-mcp-server__list_papers` | List all downloaded papers |
| `mcp__arxiv-mcp-server__read_paper` | Read downloaded paper content (Markdown) |

### Search strategy

```
Query: "[topic] AND (segmentation OR detection OR classification)"
Categories: cs.CV, eess.IV, cs.LG
Date: Last 3 years for current state of the art
Max results: 50-80 per query (discriminate aggressively — quality over breadth)
```

### Example queries

- `"medical image segmentation transformer"` (cs.CV, eess.IV)
- `"coronary artery deep learning"` (cs.CV)
- `"CT scan neural network"` (eess.IV)
- `"foundation model medical segmentation"` (cs.CV, cs.LG)

### Workflow integration

Per CITATION_INTEGRITY.md Rule 2, when adding an arXiv paper to bibliography:

1. `search_papers` to find candidates
2. `download_paper(paper_id)` for promising ones
3. `read_paper(paper_id)` to read full text (or at least abstract + methods + results)
4. Note actual first author, full author list, exact module names, headline numbers
5. Cross-check: arxiv abstract page = `https://arxiv.org/abs/<id>` for author list verification

---

## PubMed MCP (Biomedical Literature)

**Repository:** https://github.com/grll/pubmedmcp

Access 35+ million biomedical literature citations.

### Configuration

```json
{
  "mcpServers": {
    "pubmedmcp": {
      "command": "uvx",
      "args": ["pubmedmcp@latest"],
      "env": {
        "UV_PRERELEASE": "allow",
        "UV_PYTHON": "3.12"
      }
    }
  }
}
```

### Available tools

| Tool | Purpose |
|---|---|
| `mcp__pubmed-mcp-server__pubmed_search_articles` | Search PubMed with MeSH and free-text queries |

### Search tips

- Use MeSH terms for precise medical searches
- Combine with publication type filters (Review, Clinical Trial)
- Filter by date for recent literature

### Example MeSH queries

- `"Deep Learning"[MeSH] AND "Coronary Vessels"[MeSH]`
- `"Image Processing, Computer-Assisted"[MeSH] AND "Tomography, X-Ray Computed"[MeSH]`
- `"Cardiac Imaging Techniques"[MeSH] AND "Artificial Intelligence"[MeSH]`

### Direct WebFetch for verification

`pubmed_search_articles` returns PMIDs. For metadata verification (CITATION_INTEGRITY.md Rules 1-2):

```
WebFetch on https://pubmed.ncbi.nlm.nih.gov/<PMID>/
  → Extract: full author list, journal, year, vol, issue, pages, DOI, finding direction
```

This is the canonical first-source verification step for medical clinical papers.

---

## Zotero Integration

Access user's local Zotero database via Zotero-MCP.

### Direct API Access (fallback)

```bash
# List collections
curl -s "http://localhost:23119/api/users/[USER_ID]/collections"

# Get items from a collection
curl -s "http://localhost:23119/api/users/[USER_ID]/collections/[KEY]/items"
```

### Zotero-MCP (recommended)

**Repository:** https://github.com/54yyyu/zotero-mcp

Provides structured access:

| Tool | Purpose |
|---|---|
| `mcp__zotero__zotero_search_collections` | Find collections by name / keyword |
| `mcp__zotero__zotero_get_collection_items` | List items in a collection |
| `mcp__zotero__zotero_search_items` | Search items by keyword |
| `mcp__zotero__zotero_get_item_metadata` | Get full metadata for an item |
| `mcp__zotero__zotero_get_item_fulltext` | Get full paper text from attached PDF |
| `mcp__zotero__zotero_get_annotations` | Get user highlights / notes |
| `mcp__zotero__zotero_semantic_search` | Semantic search across library |

### Workflow integration

For closed-access journals (Med Image Anal, Eur Radiol, JACC family, Lancet family, Nature family), the user often has PDFs in Zotero that aren't accessible via WebFetch. Workflow:

```
1. mcp__zotero__zotero_search_items(query: "<author> <method>", limit: 5)
2. mcp__zotero__zotero_get_item_metadata(item_key: "<key>")
3. mcp__zotero__zotero_get_item_fulltext(item_key: "<key>") for body content
```

### Extractable fields

- title
- abstractNote
- date
- creators (author list — verify against first-source per Rule 2)
- publicationTitle
- DOI
- tags
- collections

---

## Source Selection Guide

| Source | Best for | Strengths | Workflow phase |
|---|---|---|---|
| **ArXiv** | Methodological preprints, ML/AI advances | Fast access, CS/AI focus, full text | Phase 2.1 |
| **PubMed** | Peer-reviewed clinical / validation, MeSH-indexed | Authoritative for medical, free metadata access | Phase 2.2 |
| **Zotero** | Closed-access journals where user has PDFs | Local, supports fulltext extraction | Phase 2.3 |
| **Crossref** | DOI verification | API gives canonical metadata | All phases (verification) |

---

## Verification helper commands

For Phase 4 (per-claim verification) and Phase 5 (peer review):

```
# Crossref by DOI
WebFetch on https://api.crossref.org/works/<DOI>
  → Returns JSON: title, full author list, container-title (journal), volume, issue, page, DOI, published year

# Crossref by topic search
WebFetch on https://api.crossref.org/works?query.bibliographic=<keywords>&rows=5
  → Returns top 5 matching entries

# PubMed by PMID
WebFetch on https://pubmed.ncbi.nlm.nih.gov/<PMID>/
  → Returns parsed page: title, authors, journal info, DOI, abstract

# arXiv abstract page (for author list verification)
WebFetch on https://arxiv.org/abs/<id>
  → Returns abstract + full author list
```

---

## When MCP servers fail

If an MCP server is not configured or fails:

- **ArXiv fallback**: WebFetch on `https://arxiv.org/abs/<id>` directly
- **PubMed fallback**: WebFetch on `https://pubmed.ncbi.nlm.nih.gov/<PMID>/` directly
- **Zotero fallback**: ask the user to share PDFs directly, or use direct API access via curl

The skill is designed to work even without MCP — WebFetch on the underlying APIs is always available.
