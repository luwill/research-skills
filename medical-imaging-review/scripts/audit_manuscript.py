#!/usr/bin/env python3
"""Audit a medical-imaging review manuscript without claiming factual sign-off.

The auditor is deliberately limited to reproducible static checks and project
artifact readiness.  Source existence, author metadata, and factual agreement
with full text remain human/source-level checks and are always reported as not
assessed rather than silently treated as passed.

This file is a thin entry point.  The implementation lives in the ``mir_audit``
package next to it, split into strictly-layered submodules
(constants -> model -> parsing/profile -> projectio -> checks_* -> report ->
core -> cli).  The full public API is re-exported here so existing callers that
``import audit_manuscript`` keep working unchanged.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make the sibling ``mir_audit`` package importable whether this file is run as a
# script (python3 scripts/audit_manuscript.py) or loaded by path in tests.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mir_audit import *  # noqa: E402,F401,F403  (re-export the public audit API)
from mir_audit.cli import main  # noqa: E402,F401

if __name__ == "__main__":
    raise SystemExit(main())
