"""Route defaults and style-profile loading/merging (warning-only style checks).

Part of the mir_audit package (split from the original audit_manuscript.py).
"""

from __future__ import annotations

import json

from pathlib import Path
from typing import Any

from .model import *  # noqa: F401,F403


def route_defaults(route: str) -> dict[str, Any]:
    del route
    return {
        "vendors": [],
        "allow_numbered_headings": None,
        "heading_numbering_expected": None,
        "max_heading_level": None,
        "require_key_points": False,
        "key_points_expected": None,
        "require_references": True,
        "require_abstract": True,
        "require_box_for_display_equations": False,
        "allow_vendor_body_mentions": True,
        "table_limit": None,
        "figure_limit": None,
        "section_order": None,
    }


def load_profile(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AuditInputError(f"cannot read profile {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise AuditInputError("profile JSON must contain an object at the top level")
    checks = payload.get("checks")
    if not isinstance(checks, dict):
        raise AuditInputError(
            "profile must use the canonical top-level checks object; flat and audit profiles are unsupported"
        )
    if payload.get("schema_version") != "2.0":
        raise AuditInputError("profile.schema_version must be exactly 2.0")
    overrides: dict[str, Any] = {"_specified_style_checks": []}
    mappings = {
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
    for name, rule in checks.items():
        if name not in mappings:
            raise AuditInputError(f"unsupported profile check: {name}")
        if not isinstance(rule, dict) or rule.get("severity") != "warning" or "expected" not in rule:
            raise AuditInputError(
                f"profile.checks.{name} must contain expected and severity='warning'"
            )
        expected = rule["expected"]
        overrides["_specified_style_checks"].append(name)
        if name == "heading_numbering":
            if expected not in {"numbered", "unnumbered", "unspecified"}:
                raise AuditInputError("heading_numbering.expected is invalid")
            overrides["allow_numbered_headings"] = (
                None if expected == "unspecified" else expected == "numbered"
            )
            overrides["heading_numbering_expected"] = expected
        elif name == "max_heading_depth":
            overrides["max_heading_level"] = expected
        elif name == "key_points":
            if expected not in {"required", "optional", "absent", "unspecified"}:
                raise AuditInputError("key_points.expected is invalid")
            overrides["key_points_expected"] = expected
            overrides["require_key_points"] = expected == "required"
        elif name == "equation_location":
            if expected not in {"body", "box", "either", "unspecified"}:
                raise AuditInputError("equation_location.expected is invalid")
            overrides["require_box_for_display_equations"] = expected == "box"
        elif name == "vendor_placement":
            if expected not in {"body", "table", "either", "unspecified"}:
                raise AuditInputError("vendor_placement.expected is invalid")
            vendor_names = payload.get("vendor_names", [])
            if expected == "table" and vendor_names:
                overrides["vendors"] = vendor_names
                overrides["allow_vendor_body_mentions"] = False
        elif name == "table_limit":
            overrides["table_limit"] = expected
        elif name == "figure_limit":
            overrides["figure_limit"] = expected
        elif name == "section_order":
            overrides["section_order"] = expected
    return overrides


def effective_profile(route: str, overrides: dict[str, Any]) -> dict[str, Any]:
    profile = route_defaults(route)
    # Structural manuscript requirements are not style preferences and cannot
    # be disabled by a profile or direct override.
    supported = set(profile) - {"require_references", "require_abstract"}
    for key, value in overrides.items():
        if key in supported:
            profile[key] = value
    if "vendors" in overrides and "allow_vendor_body_mentions" not in overrides:
        profile["allow_vendor_body_mentions"] = False
    if not isinstance(profile["vendors"], list) or not all(
        isinstance(item, str) and item.strip() for item in profile["vendors"]
    ):
        raise AuditInputError("profile.vendors must be an array of non-empty strings")
    for key in (
        "require_key_points",
        "require_references",
        "require_abstract",
        "require_box_for_display_equations",
        "allow_vendor_body_mentions",
    ):
        if not isinstance(profile[key], bool):
            raise AuditInputError(f"profile.{key} must be true or false")
    if profile["allow_numbered_headings"] is not None and not isinstance(
        profile["allow_numbered_headings"], bool
    ):
        raise AuditInputError("profile.allow_numbered_headings must be true or false")
    if profile["heading_numbering_expected"] not in {None, "numbered", "unnumbered", "unspecified"}:
        raise AuditInputError("profile.heading_numbering_expected is invalid")
    if profile["max_heading_level"] is not None and (
        not isinstance(profile["max_heading_level"], int)
        or not 2 <= profile["max_heading_level"] <= 6
    ):
        raise AuditInputError("profile.max_heading_level must be an integer from 2 to 6")
    if profile["key_points_expected"] not in {None, "required", "optional", "absent", "unspecified"}:
        raise AuditInputError("profile.key_points_expected is invalid")
    for key in ("table_limit", "figure_limit"):
        if profile[key] is not None and (
            not isinstance(profile[key], int) or profile[key] < 0
        ):
            raise AuditInputError(f"profile.{key} must be a non-negative integer or null")
    if profile["section_order"] is not None and (
        not isinstance(profile["section_order"], list)
        or not all(isinstance(item, str) and item.strip() for item in profile["section_order"])
    ):
        raise AuditInputError("profile.section_order must be an array of non-empty strings or null")
    return profile
