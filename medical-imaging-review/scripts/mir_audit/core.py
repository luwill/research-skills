"""The audit_text orchestrator that runs every check and builds the result dict.

Part of the mir_audit package (split from the original audit_manuscript.py).
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from .constants import *  # noqa: F401,F403
from .model import *  # noqa: F401,F403
from .parsing import *  # noqa: F401,F403
from .profile import *  # noqa: F401,F403
from .checks_text import *  # noqa: F401,F403
from .checks_artifacts import *  # noqa: F401,F403
from .checks_claims import *  # noqa: F401,F403
from .report import *  # noqa: F401,F403


def audit_text(
    text: str,
    *,
    file_label: str,
    requested_route: str = "auto",
    profile_overrides: dict[str, Any] | None = None,
    profile_path: Path | None = None,
    project_dir: Path | None = None,
    manuscript_path: Path | None = None,
    fail_on: str = "critical",
) -> dict[str, Any]:
    lines = visible_lines(text)
    body_lines, ref_lines, ref_heading_found = split_body_and_refs(lines)
    inferred_route, inferred_source = infer_route(body_lines)
    route, route_source = (
        (inferred_route, inferred_source)
        if requested_route == "auto"
        else (requested_route, "explicit")
    )
    profile = effective_profile(route, profile_overrides or {})
    references = merge_references(
        parse_references(ref_lines), parse_project_bibliography(project_dir)
    )
    citations, citation_findings = scan_citation_reconciliation(body_lines, references)

    findings: list[Finding] = []
    if (
        requested_route != "auto"
        and inferred_source == "title_or_abstract"
        and inferred_route != requested_route
    ):
        findings.append(
            Finding(
                "critical",
                "route_mismatch",
                0,
                f"Explicit route {requested_route} conflicts with the title/abstract route {inferred_route}.",
            )
        )
    findings.extend(references.findings)
    findings.extend(citation_findings)
    findings.extend(scan_placeholders(lines))
    findings.extend(scan_headings(body_lines, profile))
    findings.extend(scan_equations(body_lines, profile))
    findings.extend(scan_vendor_mentions(body_lines, profile))
    findings.extend(scan_profile_layout(body_lines, profile))
    findings.extend(scan_unsupported_route_claims(body_lines))
    findings.extend(scan_structure(route, body_lines, ref_heading_found, references, citations, profile))
    findings.extend(scan_duplicate_dois(references))
    findings.extend(validate_working_manuscript_path(project_dir, manuscript_path))
    if project_dir is not None:
        numeric_citations = [citation for citation in citations if citation.identifier.isdigit()]
        if numeric_citations:
            findings.append(
                Finding(
                    "critical",
                    "mutable_numeric_citation",
                    numeric_citations[0].line,
                    "Working project manuscripts must use stable citekeys; render numeric citations only at final formatting.",
                    numeric_citations[0].raw,
                )
            )
        if ref_heading_found and parse_references(ref_lines).entries:
            findings.append(
                Finding(
                    "critical",
                    "inline_working_bibliography",
                    0,
                    "references.bib is canonical for a working project; do not maintain a second inline bibliography in manuscript.md.",
                )
            )
    findings.extend(scan_project_readiness(route, project_dir))
    claim_findings, claims_assessed = scan_claim_ledger(
        body_lines, project_dir, references
    )
    findings.extend(claim_findings)

    not_assessed = set(BASE_NOT_ASSESSED)
    if not claims_assessed:
        not_assessed.add("claim_ledger_alignment")
    style_checks = {
        "heading_numbering",
        "max_heading_depth",
        "key_points",
        "equation_location",
        "vendor_placement",
        "table_limit",
        "figure_limit",
        "citation_density",
        "section_order",
    }
    specified = set((profile_overrides or {}).get("_specified_style_checks", []))
    if not specified and profile_overrides:
        flat_mapping = {
            "allow_numbered_headings": "heading_numbering",
            "max_heading_level": "max_heading_depth",
            "require_key_points": "key_points",
            "require_box_for_display_equations": "equation_location",
            "vendors": "vendor_placement",
            "table_limit": "table_limit",
            "figure_limit": "figure_limit",
            "section_order": "section_order",
        }
        specified = {mapped for key, mapped in flat_mapping.items() if key in profile_overrides}
    for check in style_checks - specified:
        not_assessed.add(f"style.{check}")
    if "citation_density" in specified:
        not_assessed.add("style.citation_density")
    if "vendor_placement" in specified and not profile["vendors"]:
        not_assessed.add("style.vendor_placement")
    findings.sort(key=lambda item: (-severity_rank(item.severity), item.category, item.line, item.message))
    status = gate_status(findings, fail_on)
    return {
        "schema_version": SCHEMA_VERSION,
        "file": file_label,
        "route": route,
        "route_source": route_source,
        "profile": str(profile_path) if profile_path else None,
        "project_dir": str(project_dir) if project_dir else None,
        "fail_on": fail_on,
        "gate_status": status,
        "reference_count": len(references.entries),
        "citation_count": len(citations),
        "summary": stable_summary(findings),
        "findings": [asdict(finding) for finding in findings],
        "not_assessed_checks": sorted(not_assessed),
    }
