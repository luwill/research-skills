# Tool Discovery and Literature Adapters

Adapt the review workflow to capabilities actually available in the current session, whatever the host environment. Do not assume an MCP server, connector, local service, subscription, or logged-in browser exists.

Here <project_dir> means the collision-safe review_project/<topic-slug>-<YYYYMMDD-HHMMSS>-<8hex>/ child printed by scripts/init_review_project.py. Use only narrative, method-survey, scoping, or systematic as route tokens; systematic means qualitative synthesis.

## Contents

- Discovery before selection
- Capability map
- Route-aware search
- Source and access rules
- Stable citekeys and claim ledger
- Reproducibility record
- Fallbacks and blocked states
- Privacy and configuration boundaries

## Discovery before selection

Before searching:

1. Inspect the active tools, installed skills, connected apps, local files, and authorized browser state.
2. Identify which capabilities can search, export, read full text, verify metadata, and preserve provenance.
3. Prefer a purpose-built connected source over generic web search when both provide the needed evidence.
4. Record database availability in the generated review_config.yaml and actual capability provenance in the applicable search log or REVIEW_CONTEXT.md.
5. Test one representative query or record before committing the protocol to that route.

Do not edit tool, browser, Zotero, or MCP configuration and do not install a connector unless the user explicitly requests that change. Never write environment-specific tool commands into the manuscript.

## Capability map

| Operation | Preferred capability | Fallback |
|---|---|---|
| Search biomedical literature | Authorized bibliographic database or PubMed-capable connector | PubMed web/API; request an export from a required unavailable database |
| Search method preprints | arXiv or scholarly-paper connector | arXiv web/API or verified publisher/preprint pages |
| Search subscribed databases | User-authorized database session or exported search results | Mark the database unavailable and request a reproducible export |
| Search a local library | Authorized Zotero connector or local Zotero access | User-provided RIS/BibTeX export or PDFs |
| Read full text | Authorized local PDF, repository, publisher page, or connected library | Use only the accessible abstract-level claims or request the document |
| Verify identifiers and metadata | Publisher, PubMed, Crossref, arXiv, or repository record | Reconcile two independent metadata sources and log uncertainty |
| Verify quantitative or directional claims | Full text with page, table, figure, or section location | Remove or narrow the claim until supporting text is accessible |

Search, metadata verification, and claim verification are different operations. A search result snippet is not a source for a scientific claim.

## Route-aware search

### Narrative review or method survey

Use searches broad enough to support the stated scope and controversy map. Record discovery sources, query concepts, evidence cutoff, and selection rationale. Do not imply exhaustive coverage.

There is no universal date window or result-count target. Choose limits from the topic, field maturity, user requirements, and evidence cutoff in <project_dir>/review_config.yaml.

### Scoping review

Translate the frozen concept blocks into each database's syntax. Preserve:

- database and platform
- complete query exactly as run
- search date and coverage dates
- filters and limits with rationale
- export filename or stable record identifier
- deduplication inputs and decisions
- supplementary search methods

Web search can supplement but cannot silently replace a protocol-required bibliographic database.

### Systematic review with qualitative synthesis

Use the databases and supplementary methods required by the frozen question and conduct guidance. Ask an information specialist or qualified human to review the strategy when required or feasible. Preserve every executable search and update.

Do not claim the search is complete when a required database, export, date, or query record is missing. Do not start pooled analysis; meta-analysis is outside this skill.

## Source and access rules

Prefer sources in this order for the claim being made:

1. Full primary-study text and its tables, figures, supplements, or appendices.
2. Official primary-study abstract and bibliographic record.
3. Registry, regulator, or dataset owner for facts within that source's authority.
4. Secondary synthesis for context, discovery, or a claim about that synthesis.

Use vendor materials only for facts they authoritatively establish, such as product documentation or a stated regulatory filing. Do not use them as clinical-effectiveness evidence when a primary study is required.

If only an abstract is accessible:

- record abstract-only access in <project_dir>/claim_ledger.csv
- limit claims to information explicitly present there
- do not infer architecture internals, exact unreported results, causal claims, or novelty priority
- do not fabricate page, table, or figure locations

Do not bypass access controls or use unauthorized copies. Ask the user for an authorized document or export when necessary.

## Stable citekeys and claim ledger

Assign a stable citekey as soon as a source is accepted, for example smith2024model. Keep that key stable even if author order, publication status, or citation style is later corrected.

Preserve user-approved reference-manager exports as immutable import artifacts. Normalize accepted records into <project_dir>/references.bib, which is the project bibliography used by stable draft citekeys such as [@smith2024model] in <project_dir>/manuscript.md. Render numeric or author-date styles only at formatting time.

For each claim in <project_dir>/claim_ledger.csv, preserve the initializer's schema and record:

- claim identifier and exact text
- citekey or citekeys
- source type and access level
- supporting page, table, figure, section, or abstract location
- verification status, verifier, and date
- uncertainty or conflict notes

If metadata sources disagree, preserve the conflict in the ledger and block polished use until resolved.

## Reproducibility record

For each search or source operation, preserve enough information for another human to repeat it using the generated artifacts rather than a second ad hoc schema. Narrative and method-survey discovery goes in `search/narrative_exploration_log.csv`; formal searches go in `search/search_log.csv`; source-specific metadata/full-text decisions go in `source_notes/<citekey>.md`; tool availability and blocked fallbacks go in `review_config.yaml` or `REVIEW_CONTEXT.md`. Use the existing `searcher_id` and `notes` fields for the human operator and environment-specific capability. Record exact dates rather than words such as today or recent.

## Fallbacks and blocked states

When a capability is unavailable:

- PubMed or biomedical connector unavailable: use the authorized web/API route or ask for an export.
- Required subscribed database unavailable: request a search export; do not substitute a general web search without a protocol amendment.
- Zotero unavailable: request RIS, BibTeX, CSV, or PDFs from the user.
- Full text unavailable: narrow or remove unsupported claims and record the access limitation.
- Metadata conflict unresolved: retain the source as pending and do not cite it in polished prose.
- Human screening, extraction, or appraisal gate unavailable: provide provisional AI-assisted suggestions only.

Record the blocked state, attempted fallback, owner, and next action in REVIEW_CONTEXT.md and IMPLEMENTATION_PLAN.md; set delivery.project_status in review_config.yaml consistently. A tool failure does not lower the evidence standard.

## Privacy and configuration boundaries

- Access only libraries, files, accounts, and browser sessions the user has authorized for this task.
- Do not upload local PDFs, annotations, or library metadata to an external service without authorization.
- Do not expose tokens, local paths, private collection names, or unpublished manuscript content in search queries or reports.
- Do not install or reconfigure tools as an implicit fallback.
- Keep tool provenance in project records and scientific claims in the manuscript; do not mix them.

Useful public fallbacks:

- PubMed: https://pubmed.ncbi.nlm.nih.gov/
- Crossref: https://api.crossref.org/
- arXiv: https://arxiv.org/
- DOI resolver: https://doi.org/
