from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DocumentContractTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_no_legacy_claude_project_artifact_contract(self):
        for relative in (
            "references/TEMPLATES.md",
            "references/WORKFLOW.md",
            "references/MCP_SETUP.md",
        ):
            with self.subTest(file=relative):
                self.assertNotIn("CLAUDE.md", self.read(relative))
        self.assertNotIn("├── CLAUDE.md", self.read("SKILL.md"))

    def test_banned_legacy_guarantees_paths_and_commands_are_absent(self):
        markdown_files = [ROOT / "SKILL.md", *sorted((ROOT / "references").glob("*.md"))]
        banned = (
            "~/.claude",
            "submission-ready",
            "pass first-round peer review",
        )
        for path in markdown_files:
            text = path.read_text(encoding="utf-8")
            for phrase in banned:
                with self.subTest(file=path.name, phrase=phrase):
                    self.assertNotIn(phrase, text)
            with self.subTest(file=path.name, phrase="python interpreter"):
                self.assertNotRegex(text, r"(?m)\bpython\s+<skill_dir>")

    def test_skill_routes_meta_analysis_and_umbrella_out_of_scope(self):
        skill = self.read("SKILL.md")
        self.assertRegex(
            skill,
            r"(?is)do not use this skill.{0,200}meta-analysis.{0,120}umbrella review",
        )
        executable_route_row = re.compile(
            r"(?im)^\|[^\n|]*(?:meta-analysis|umbrella review)[^\n|]*\|\s*"
            r"(?:meta-analysis|umbrella|systematic review route)"
        )
        self.assertNotRegex(skill, executable_route_row)


if __name__ == "__main__":
    unittest.main()
