"""Findings summary, gate-status decision, and Markdown report rendering.

Part of the mir_audit package (split from the original audit_manuscript.py).
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from .constants import *  # noqa: F401,F403
from .model import *  # noqa: F401,F403


def stable_summary(findings: list[Finding]) -> dict[str, int]:
    counts = Counter(finding.severity for finding in findings)
    return {severity: counts[severity] for severity in SEVERITIES}


def gate_status(findings: list[Finding], fail_on: str) -> str:
    if fail_on != "none":
        threshold = severity_rank(fail_on)
        if any(
            finding.gate_relevant and severity_rank(finding.severity) >= threshold
            for finding in findings
        ):
            return "fail"
    if findings:
        return "warning"
    return "not_assessed"


def render_markdown(result: dict[str, Any]) -> str:
    summary = result["summary"]
    lines = [
        "# Manuscript Audit Report",
        "",
        f"File: `{result['file']}`",
        f"Route: `{result['route']}` ({result['route_source']})",
        f"Gate status: **{result['gate_status']}**",
        f"References parsed: {result['reference_count']}",
        f"Citations parsed: {result['citation_count']}",
        "",
        "## Summary",
        "",
        f"- Critical: {summary['critical']}",
        f"- High: {summary['high']}",
        f"- Medium: {summary['medium']}",
        f"- Low: {summary['low']}",
        "",
        "## Findings",
        "",
    ]
    if result["findings"]:
        for finding in result["findings"]:
            location = f"line {finding['line']}" if finding["line"] else "global"
            lines.append(
                f"- **{finding['severity'].upper()}** `{finding['category']}` ({location}): {finding['message']}"
            )
            if finding["excerpt"]:
                lines.append(f"  - `{finding['excerpt']}`")
    else:
        lines.append("- No automated findings.")
    lines.extend(["", "## Not assessed", ""])
    lines.extend(f"- `{check}`" for check in result["not_assessed_checks"])
    lines.extend(
        [
            "",
            "Automated findings are triage signals. Source-level and human checks above remain unresolved unless separately evidenced.",
            "",
        ]
    )
    return "\n".join(lines)
