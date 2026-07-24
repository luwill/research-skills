"""Core dataclasses (Finding, Citation, ReferenceSet, ...) and the input-error type.

Part of the mir_audit package (split from the original audit_manuscript.py).
"""

from __future__ import annotations

from dataclasses import dataclass

from .constants import *  # noqa: F401,F403


class AuditInputError(ValueError):
    """Raised for a user-correctable input or configuration problem."""


@dataclass
class SourceLine:
    number: int
    text: str


@dataclass
class Finding:
    """One audit result.

    ``category`` is the stable, machine-readable code (e.g. ``unverified_claim``,
    ``route_mismatch``); script against it rather than the human-readable
    ``message``. ``severity`` is one of ``SEVERITIES`` and drives the
    ``--fail-on`` gate. ``gate_relevant`` marks findings that can block delivery.
    """

    severity: str
    category: str
    line: int
    message: str
    excerpt: str = ""
    gate_relevant: bool = True


@dataclass(frozen=True)
class Citation:
    identifier: str
    line: int
    raw: str


@dataclass
class ReferenceSet:
    entries: dict[str, str]
    entry_lines: dict[str, int]
    findings: list[Finding]


@dataclass(frozen=True)
class ClaimCandidate:
    line: int
    text: str
    kind: str
    section: str
    citation_ids: tuple[str, ...]


def severity_rank(severity: str) -> int:
    return SEVERITY_RANK.get(severity, 0)
