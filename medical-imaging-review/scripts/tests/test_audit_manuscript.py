#!/usr/bin/env python3
"""Fixture tests for audit_manuscript.py.

These lock in the P0 fixes (author↔citation mismatch under standard "Author et al. [N]"
typesetting, and internationalised reference-section detection) plus the P1/P2 hardening
(equation box-context, systematic self-claim gating, input robustness).

Run either way:
    python3 -m pytest scripts/tests/test_audit_manuscript.py
    python3 scripts/tests/test_audit_manuscript.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "audit_manuscript.py"


def run(text: str) -> dict:
    """Write `text` to a temp manuscript and return the parsed --json audit payload."""
    with tempfile.NamedTemporaryFile("w", suffix=".md", encoding="utf-8", delete=False) as fh:
        fh.write(text)
        tmp = fh.name
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), tmp, "--json"],
        capture_output=True,
        text=True,
    )
    Path(tmp).unlink(missing_ok=True)
    assert proc.returncode == 0, f"unexpected exit {proc.returncode}: {proc.stderr}"
    return json.loads(proc.stdout)


def categories(payload: dict) -> list[str]:
    return [f["category"] for f in payload["findings"]]


# --------------------------------------------------------------------------------------
# (a) Three known author↔citation mismatches under standard "Author et al. [N]" spacing.
# --------------------------------------------------------------------------------------

FIXTURE_MISMATCH = """# A Narrative Review of Vessel Segmentation

## Introduction

Wang et al. [1] introduced the clDice topology loss for tubular structures.
Zhang et al. [2] proposed a transformer backbone for coronary segmentation.
Later, Wang et al. [3] extended federated averaging to multi-centre cohorts.
Xu et al. [4] reported a Dice of 0.730 on ImageCAS.

## References

[1] Shit S, Paetzold JC, Sekuboyina A, et al. clDice - a novel topology-preserving loss. CVPR 2021.
[2] Liu H, Chen G, Zhao P, et al. A survey of medical image transformers. Med Image Anal. 2023.
[3] Kumar A, Singh P, Sharma N. Federated learning for imaging. IEEE TMI. 2022.
[4] Xu C, Li M, Wu X. TransCC coronary segmentation. arXiv preprint 2023.
"""


def test_three_author_mismatches_detected():
    payload = run(FIXTURE_MISMATCH)
    mism = [f for f in payload["findings"] if f["category"] == "author_citation_mismatch"]
    assert len(mism) == 3, f"expected 3 mismatches, got {len(mism)}: {mism}"
    # The correct citation (Xu -> [4] Xu) must NOT be flagged.
    assert all("[4]" not in f["message"] for f in mism), "false positive on correct citation [4]"
    # All four references resolve -> no missing_reference noise.
    assert "missing_reference" not in categories(payload)
    assert payload["reference_count"] == 4


# --------------------------------------------------------------------------------------
# (b) Chinese "参考文献" heading parses; no missing_reference / references_not_detected.
# --------------------------------------------------------------------------------------

FIXTURE_CHINESE = """# 冠状动脉分割的深度学习综述

## 引言

拓扑保持损失函数在管状结构分割中表现突出 [1]。多中心联邦学习方法随后被提出 [2]。

## 参考文献

[1] Shit S, Paetzold JC, et al. clDice. CVPR 2021.
[2] Kumar A, Singh P. Federated learning for imaging. IEEE TMI. 2022.
"""


def test_chinese_reference_section_parsed_cleanly():
    payload = run(FIXTURE_CHINESE)
    assert payload["reference_count"] == 2, f"refs not parsed: {payload['reference_count']}"
    cats = categories(payload)
    assert "missing_reference" not in cats, f"false missing_reference: {payload['findings']}"
    assert "references_not_detected" not in cats
    assert payload["findings"] == [], f"expected clean, got {payload['findings']}"


# --------------------------------------------------------------------------------------
# (c) Clean manuscript -> zero findings (no false positives across all scanners).
# --------------------------------------------------------------------------------------

FIXTURE_CLEAN = """# Deep Learning for Coronary Segmentation

## Key Points
- Topology-aware losses improve tubular continuity across datasets.

## Introduction

Shit et al. [1] introduced the clDice loss. Xu et al. [2] reported strong results on ImageCAS.

## Box 1: Evaluation metrics

$$ DSC = \\frac{2|A \\cap B|}{|A| + |B|} $$

## References

[1] Shit S, Paetzold JC, Sekuboyina A, et al. clDice loss. CVPR 2021.
[2] Xu C, Li M, Wu X. TransCC segmentation network. arXiv preprint 2023.
"""


def test_clean_manuscript_zero_findings():
    payload = run(FIXTURE_CLEAN)
    assert payload["findings"] == [], f"expected zero findings, got {payload['findings']}"
    assert payload["reference_count"] == 2


# --------------------------------------------------------------------------------------
# Regression guards for the P1/P2 hardening.
# --------------------------------------------------------------------------------------

def test_missing_reference_still_detected():
    payload = run(
        "## Body\n\nA claim with no backing reference [7].\n\n"
        "## References\n\n[1] Shit S, et al. clDice. CVPR 2021.\n"
    )
    assert "missing_reference" in categories(payload)


def test_references_not_detected_is_single_low_note():
    # No recognised reference heading, but body has citations -> one triage note, not spam.
    payload = run("## Body\n\nClaim one [1]. Claim two [2]. Claim three [3].\n")
    not_detected = [f for f in payload["findings"] if f["category"] == "references_not_detected"]
    assert len(not_detected) == 1, f"expected exactly one note, got {payload['findings']}"
    assert not_detected[0]["severity"] == "low"
    assert "missing_reference" not in categories(payload)


def test_equation_box_mention_does_not_silence_body_equation():
    payload = run(
        "## Methods\n\nSee Box 1 for the definition of Dice.\n\n"
        "$$ stray = equation + in + body $$\n\n"
        "## Box 1: Metrics\n\n$$ DSC = 2|A n B| / (|A| + |B|) $$\n"
    )
    eqs = [f for f in payload["findings"] if f["category"] == "display_equation_outside_box"]
    assert len(eqs) == 1, f"expected exactly the body equation flagged, got {eqs}"


def test_prior_systematic_reviews_reference_is_exempt():
    payload = run(
        "# A Narrative Review of Segmentation\n\n## Introduction\n\n"
        "Unlike earlier systematic reviews [1], this is a narrative synthesis, "
        "not a systematic review.\n\n"
        "## References\n\n[1] Shit S, et al. A prior systematic review. J. 2022.\n"
    )
    assert "unsupported_systematic_claim" not in categories(payload)


def test_systematic_self_claim_without_methods_flagged():
    payload = run(
        "# Deep Learning in Radiology\n\n## Abstract\n\n"
        "We conducted a systematic review of deep learning methods for segmentation.\n\n"
        "## References\n\n[1] Shit S, et al. clDice. CVPR 2021.\n"
    )
    assert "unsupported_systematic_claim" in categories(payload)


def test_systematic_self_claim_with_methods_not_flagged():
    payload = run(
        "# Deep Learning in Radiology\n\n## Methods\n\n"
        "We conducted a systematic review following PRISMA 2020. The search strategy "
        "queried PubMed with explicit eligibility criteria; screening and data extraction "
        "were performed in duplicate and risk of bias was appraised with QUADAS-2.\n\n"
        "## References\n\n[1] Shit S, et al. clDice. CVPR 2021.\n"
    )
    assert "unsupported_systematic_claim" not in categories(payload)


def test_missing_input_returns_nonzero_without_traceback():
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "/nonexistent/does_not_exist.md", "--json"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 2, f"expected exit 2, got {proc.returncode}"
    assert "Traceback" not in proc.stderr, "should fail gracefully, not raise"
    assert "error:" in proc.stderr.lower()


# --------------------------------------------------------------------------------------
# Direct-run harness (no pytest required).
# --------------------------------------------------------------------------------------

def _main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failures = 0
    for test in tests:
        try:
            test()
            print(f"PASS  {test.__name__}")
        except AssertionError as exc:
            failures += 1
            print(f"FAIL  {test.__name__}: {exc}")
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"ERROR {test.__name__}: {exc!r}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(_main())
