"""pytest configuration for scholar-slides.

Integration tests marked ``@pytest.mark.integration`` that depend on the real test PDF
(``tests/fixtures/attention.pdf``) are SKIPPED — not failed — when that fixture is absent. The PDF
is git-ignored and not shipped, so a clean clone has no fixture; on such a machine the affected
tests should skip with actionable guidance rather than error out with a bare "no such file".

The modules that need the fixture declare a module-level ``FIX`` pointing at its path; this hook
keys off that, so only genuinely fixture-dependent integration tests skip. Integration tests that
need only the network (e.g. the live citation resolver) or a prebuilt deck (PPTX parity) are left
untouched and manage their own availability.
"""
import os

import pytest

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "attention.pdf")

_GUIDANCE = (
    "missing test fixture tests/fixtures/attention.pdf (git-ignored, not shipped). "
    "To enable the PDF-backed integration tests, fetch the paper once and drop it there, e.g.:\n"
    "  ./.venv/bin/python scripts/prepare_source.py 1706.03762 --out-dir /tmp/attn && \\\n"
    "  cp /tmp/attn/1706.03762.pdf tests/fixtures/attention.pdf"
)


def pytest_runtest_setup(item):
    """Skip a fixture-backed integration test when its PDF fixture is not on disk."""
    if item.get_closest_marker("integration") is None:
        return
    fix = getattr(item.module, "FIX", None)
    if fix and not os.path.exists(fix):
        pytest.skip(_GUIDANCE)
