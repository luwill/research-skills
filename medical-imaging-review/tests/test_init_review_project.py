from __future__ import annotations

import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).parents[1] / "scripts" / "init_review_project.py"
SPEC = importlib.util.spec_from_file_location("init_review_project", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

PROJECT_ID = "ccta-review-20260723-120000-1234abcd"


class InitReviewProjectTests(unittest.TestCase):
    def test_narrative_project_uses_collision_safe_contract(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            target = MODULE.initialize_project(
                Path(raw), "ccta-review", "narrative", project_id=PROJECT_ID
            )
            self.assertEqual(
                target, Path(raw).resolve() / "review_project" / PROJECT_ID
            )
            for required in (
                "review_config.yaml",
                "REVIEW_CONTEXT.md",
                "claim_ledger.csv",
                "references.bib",
                "manuscript.md",
                "PARADIGM.md",
                "AI_USE_DISCLOSURE.md",
                "search/narrative_exploration_log.csv",
                "search/selection_rationale.md",
            ):
                self.assertTrue((target / required).exists(), required)
            self.assertFalse((target / "CLAUDE.md").exists())
            self.assertFalse((target / "human_review_gate.json").exists())
            config = (target / "review_config.yaml").read_text(encoding="utf-8")
            self.assertIn(f'project_id: "{PROJECT_ID}"', config)
            self.assertIn('project_dir: "."', config)
            self.assertIn('project_dir_base: "review_config_directory"', config)
            self.assertIn('route: "narrative"', config)
            self.assertIn('used: "unknown"', config)
            disclosure = (target / "AI_USE_DISCLOSURE.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("## Tools", disclosure)
            self.assertIn("## Prohibited substitutions", disclosure)
            rationale = (target / "search/selection_rationale.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("## Selection logic", rationale)
            self.assertIn("## Likely blind spots", rationale)
            with (target / "claim_ledger.csv").open(
                encoding="utf-8", newline=""
            ) as stream:
                headers = next(csv.reader(stream))
            for field in (
                "claim_text",
                "source_id",
                "source_locator",
                "population_or_dataset",
                "data_split",
                "split_unit",
                "comparator",
                "metric",
                "unit",
                "uncertainty_interval",
                "direction",
                "access_level",
                "source_role",
                "access_uri",
                "accessed_at",
                "verification_status",
                "verified_by",
            ):
                self.assertIn(field, headers)

    def test_method_survey_is_supported_without_formal_human_gate(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            target = MODULE.initialize_project(
                Path(raw),
                "method-survey",
                "method-survey",
                project_id="method-survey-20260723-120000-1234abcd",
            )
            self.assertTrue((target / "search/narrative_exploration_log.csv").exists())
            self.assertFalse((target / "human_review_gate.json").exists())

    def test_systematic_project_starts_not_ready_with_route_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            target = MODULE.initialize_project(
                Path(raw), "ccta-review", "systematic", project_id=PROJECT_ID
            )
            gate = json.loads(
                (target / "human_review_gate.json").read_text(encoding="utf-8")
            )
            self.assertEqual(gate["status"], "not_ready")
            self.assertEqual(gate["reviewer_ids"], [])
            self.assertEqual(gate["route"], "systematic")
            self.assertEqual(
                gate["checks"]["title_abstract_screening"], "not_ready"
            )
            self.assertEqual(
                gate["evidence"]["title_abstract_screening"],
                "screening/screening_decisions.csv",
            )
            config = (target / "review_config.yaml").read_text(encoding="utf-8")
            self.assertIn('gate_path: "human_review_gate.json"', config)
            protocol = (target / "protocol/PROTOCOL.md").read_text(
                encoding="utf-8"
            )
            for heading in (
                "## Administrative information",
                "## Selection process",
                "## Appraisal",
                "## Reporting bias and certainty",
                "## Data, code, funding, conflicts, and AI assistance",
            ):
                self.assertIn(heading, protocol)
            for required in (
                "protocol/PROTOCOL.md",
                "search/search_log.csv",
                "screening/screening_decisions.csv",
                "extraction/critical_data.csv",
                "risk_of_bias/assessments.csv",
                "certainty/assessments.csv",
                "adjudication/conflict_log.csv",
                "reporting/PRISMA_2020_checklist.md",
                "protocol_deviations.md",
            ):
                self.assertTrue((target / required).exists(), required)

    def test_scoping_project_has_charting_and_reporting_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            target = MODULE.initialize_project(
                Path(raw), "ccta-review", "scoping", project_id=PROJECT_ID
            )
            for required in (
                "protocol/PROTOCOL.md",
                "screening/screening_decisions.csv",
                "extraction/charting_table.csv",
                "reporting/PRISMA_ScR_checklist.md",
                "reporting/flow_counts.json",
            ):
                self.assertTrue((target / required).exists(), required)
            self.assertFalse((target / "human_review_gate.json").exists())

    def test_existing_project_is_never_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            existing = Path(raw) / "review_project" / PROJECT_ID
            existing.mkdir(parents=True)
            sentinel = existing / "sentinel.txt"
            sentinel.write_text("keep", encoding="utf-8")
            with self.assertRaises(MODULE.ProjectInitError):
                MODULE.initialize_project(
                    Path(raw), "ccta-review", "scoping", project_id=PROJECT_ID
                )
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")

    def test_existing_review_root_contents_are_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw) / "review_project"
            root.mkdir()
            sentinel = root / "existing-project"
            sentinel.mkdir()
            (sentinel / "keep.txt").write_text("keep", encoding="utf-8")
            MODULE.initialize_project(
                Path(raw), "ccta-review", "scoping", project_id=PROJECT_ID
            )
            self.assertEqual(
                (sentinel / "keep.txt").read_text(encoding="utf-8"), "keep"
            )

    def test_project_name_cannot_escape_parent(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            with self.assertRaises(MODULE.ProjectInitError):
                MODULE.initialize_project(Path(raw), "../escape", "narrative")

    def test_review_project_symlink_is_rejected_without_external_write(self) -> None:
        with tempfile.TemporaryDirectory() as raw, tempfile.TemporaryDirectory() as outside:
            review_root = Path(raw) / "review_project"
            review_root.symlink_to(Path(outside), target_is_directory=True)
            with self.assertRaises(MODULE.ProjectInitError):
                MODULE.initialize_project(
                    Path(raw), "ccta-review", "narrative", project_id=PROJECT_ID
                )
            self.assertEqual(list(Path(outside).iterdir()), [])

    def test_failed_write_leaves_no_visible_or_staging_project(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            with mock.patch.object(Path, "open", side_effect=OSError("injected")):
                with self.assertRaises(OSError):
                    MODULE.initialize_project(
                        Path(raw), "ccta-review", "narrative", project_id=PROJECT_ID
                    )
            review_root = Path(raw) / "review_project"
            self.assertEqual(list(review_root.iterdir()), [])

    def test_invalid_project_id_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            with self.assertRaises(MODULE.ProjectInitError):
                MODULE.initialize_project(
                    Path(raw), "ccta-review", "narrative", project_id="../escape"
                )

    def test_project_id_topic_must_exactly_match_slug(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            with self.assertRaises(MODULE.ProjectInitError):
                MODULE.initialize_project(
                    Path(raw),
                    "ccta",
                    "narrative",
                    project_id="ccta-review-20260723-120000-1234abcd",
                )

    def test_unsupported_routes_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            for route in ("meta-analysis", "umbrella"):
                with self.subTest(route=route):
                    with self.assertRaises(MODULE.ProjectInitError):
                        MODULE.initialize_project(Path(raw), "ccta-review", route)


if __name__ == "__main__":
    unittest.main()
