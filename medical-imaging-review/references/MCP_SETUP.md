# Tool Adapters for Literature Collection

Use this file to adapt the literature workflow to the tools available in the current environment. Do not assume a specific MCP server name exists. First inspect available tools; then choose the most direct first-source route.

The core operations are tool-independent:

| Operation | Preferred route | Fallback |
|---|---|---|
| Search method preprints | Available arXiv/paper-search MCP, Hugging Face papers, scholarly web search | arXiv website/API, publisher pages |
| Search biomedical literature | Available PubMed/NCBI MCP or web search restricted to PubMed | PubMed website by query or PMID |
| Read closed-access papers | Zotero MCP/local Zotero API/local PDFs | Ask user for PDF or use abstract-only contribution claim |
| Verify DOI metadata | Crossref API or DOI resolver | Publisher page, PubMed metadata |
| Verify author list | PubMed/Crossref/arXiv/publisher page | Zotero metadata plus manual spot-check |
| Verify numeric/directional claims | Full text or abstract/results table | Remove the numeric claim if the source cannot be read |

If a listed tool is unavailable, use the fallback. The manuscript quality standard stays the same.

---

## Tool discovery checklist

Before search:

1. List available MCP/tools in the current environment.
2. Record the actual usable tool names in `CLAUDE.md` or the project plan.
3. For each source family, record the fallback URL/API.
4. Do not write tool-specific commands into the manuscript or final notes.

---

## ArXiv / preprint route

Use arXiv for preprints and ML-method advances. If an arXiv MCP is installed, use it; otherwise use arXiv URLs directly.

### Optional Claude MCP example

Repository: https://github.com/blazickjp/arxiv-mcp-server

Configuration example:

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

Example tool names if this MCP is installed:

| Tool | Purpose |
|---|---|
| `search_papers` equivalent | Search by keywords with date range and category filters |
| `download_paper` equivalent | Download paper PDF by arXiv ID |
| `list_papers` equivalent | List downloaded papers |
| `read_paper` equivalent | Read downloaded paper content |

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

1. Search to find candidates.
2. Open the abstract page and download/read the PDF for promising ones.
3. Read full text, or at least abstract + methods + results, before writing method details.
4. Note actual first author, full author list, exact module names, headline numbers
5. Cross-check: arxiv abstract page = `https://arxiv.org/abs/<id>` for author list verification

---

## PubMed / biomedical route

Use PubMed for peer-reviewed clinical, validation, diagnostic, and implementation literature.

### Optional Claude MCP example

Repository: https://github.com/grll/pubmedmcp

Configuration example:

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

Example tool names if this MCP is installed:

| Tool | Purpose |
|---|---|
| `pubmed_search_articles` equivalent | Search PubMed with MeSH and free-text queries |

### Search tips

- Use MeSH terms for precise medical searches
- Combine with publication type filters (Review, Clinical Trial)
- Filter by date for recent literature

### Example MeSH queries

- `"Deep Learning"[MeSH] AND "Coronary Vessels"[MeSH]`
- `"Image Processing, Computer-Assisted"[MeSH] AND "Tomography, X-Ray Computed"[MeSH]`
- `"Cardiac Imaging Techniques"[MeSH] AND "Artificial Intelligence"[MeSH]`

### Direct URL/API verification

For metadata verification (CITATION_INTEGRITY.md Rules 1-2), use the PubMed page by PMID:

```
WebFetch on https://pubmed.ncbi.nlm.nih.gov/<PMID>/
  → Extract: full author list, journal, year, vol, issue, pages, DOI, finding direction
```

This is the canonical first-source metadata verification step for medical clinical papers.

---

## Zotero / local-library route

Access user's local Zotero database via Zotero-MCP.

### Direct API Access (fallback)

```bash
# List collections
curl -s "http://localhost:23119/api/users/[USER_ID]/collections"

# Get items from a collection
curl -s "http://localhost:23119/api/users/[USER_ID]/collections/[KEY]/items"
```

### Zotero-MCP (if available)

**Repository:** https://github.com/54yyyu/zotero-mcp

Possible tool names:

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

For closed-access journals (Med Image Anal, Eur Radiol, JACC family, Lancet family, Nature family), the user often has PDFs in Zotero that aren't accessible via web tools. Workflow:

```
1. Search items by author/method/topic.
2. Get item metadata and DOI.
3. Retrieve full text only when metadata and abstract are insufficient.
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

## Verification helper URLs

For Phase 4 (per-claim verification) and Phase 5 (peer review):

```
# Crossref by DOI (URL-encode the DOI if needed)
https://api.crossref.org/works/<DOI>
  → Returns JSON: title, full author list, container-title (journal), volume, issue, page, DOI, published year

# Crossref by topic search
https://api.crossref.org/works?query.bibliographic=<keywords>&rows=5
  → Returns top 5 matching entries

# PubMed by PMID
https://pubmed.ncbi.nlm.nih.gov/<PMID>/
  → Returns parsed page: title, authors, journal info, DOI, abstract

# arXiv abstract page (for author list verification)
https://arxiv.org/abs/<id>
  → Returns abstract + full author list
```

---

## When a tool is unavailable

If an MCP server is not configured or fails:

- **ArXiv fallback**: use `https://arxiv.org/abs/<id>` directly
- **PubMed fallback**: use `https://pubmed.ncbi.nlm.nih.gov/<PMID>/` directly
- **Zotero fallback**: ask the user to share PDFs directly, or use direct API access via curl
- **Crossref fallback**: use DOI resolver and publisher page

The skill is designed to work without any specific MCP. The verification standard does not change when the tool route changes.
