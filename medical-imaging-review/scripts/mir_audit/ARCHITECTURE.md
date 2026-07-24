# mir_audit — package architecture

`audit_manuscript.py` is a thin entry point. The auditor implementation lives here,
split from a single 3,900-line module into strictly-layered submodules so each file
stays small and cohesive and the dependency graph is acyclic. Imports flow **downward
only** — a module may import from lower layers, never from a sibling or higher one.

| Layer | Module | Responsibility |
|---|---|---|
| 1 | `constants.py` | Data tables, severity ranks, project-file sets, compiled regexes |
| 2 | `model.py` | Dataclasses (`Finding`, `Citation`, `ReferenceSet`, …) + `AuditInputError` |
| 3 | `parsing.py` | Markdown / citation / reference parsing (pure readers) |
| 3 | `profile.py` | Route defaults and style-profile load/merge |
| 4 | `projectio.py` | Project-directory CSV/YAML readers and resolution predicates |
| 5 | `checks_text.py` | Manuscript-level checks (headings, citations, equations, route claims) |
| 6 | `checks_config.py` | `review_config.yaml` validation and screening-flow arithmetic |
| 7 | `checks_human.py` | Human-governance gate validator |
| 8 | `checks_artifacts.py` | Formal-artifact-content validation + project-readiness aggregation |
| 9 | `checks_claims.py` | Claim-candidate extraction and claim-ledger reconciliation |
| 10 | `report.py` | Findings summary, gate-status decision, Markdown rendering |
| 11 | `core.py` | `audit_text()` — runs every check, builds the result dict |
| 12 | `cli.py` | Argument parsing, safe report writing, `main()` |

`__init__.py` re-exports the full public API, and `audit_manuscript.py` re-exports that
in turn, so `import audit_manuscript` and `python3 scripts/audit_manuscript.py` behave
exactly as before the split. The layering above is enforced by construction (each module
imports `*` only from strictly-lower layers).

## Conventions

- **Findings** are `model.Finding` records. `category` is the stable machine code;
  `severity` (one of `constants.SEVERITIES`) drives the `--fail-on` gate.
- **Exit codes:** `0` clean, `1` failing gate at/above `--fail-on`, `2` input error.
- **No silent passes:** anything the static auditor cannot prove (source support, factual
  agreement, human judgments) is reported as `not_assessed`, never as a pass.

## Tests

`../../tests/` loads `audit_manuscript.py` by path and also drives the CLI as a subprocess,
so both the import surface and the entry point are covered. Run: `python3 -m pytest tests/ -q`.
