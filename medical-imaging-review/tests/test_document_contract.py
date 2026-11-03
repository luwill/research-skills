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

    def test_reference_json_templates_declare_supported_schema_version(self):
        # profile.py rejects any style_profile whose schema_version != "2.0";
        # every JSON template embedded in the references must therefore say 2.0,
        # or an agent following the template would produce a rejected profile.
        fence = re.compile(r"~~~json\s*\n(.*?)~~~", re.DOTALL)
        version = re.compile(r'"schema_version"\s*:\s*"([^"]+)"')
        checked = 0
        for path in sorted((ROOT / "references").glob("*.md")):
            for match in fence.finditer(path.read_text(encoding="utf-8")):
                found = version.search(match.group(1))
                if not found:
                    continue
                checked += 1
                with self.subTest(file=path.name, version=found.group(1)):
                    self.assertEqual(found.group(1), "2.0")
        self.assertGreater(checked, 0)

    def test_review_types_artifact_lists_match_the_initializer(self):
        # "Use the route-specific artifacts created by the initializer" is only true
        # if the lists name every route file the initializer actually writes (the
        # scoping list was missing calibration_log/PRISMA_ScR, the systematic list
        # was missing search_plan/deduplication_log/calibration_log/decision_rules/
        # PRISMA_2020). Lock the two against init_review_project.project_files().
        import importlib.util

        script = ROOT / "scripts" / "init_review_project.py"
        spec = importlib.util.spec_from_file_location("init_review_project", script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        common_core = {
            "review_config.yaml",
            "REVIEW_CONTEXT.md",
            "IMPLEMENTATION_PLAN.md",
            "PARADIGM.md",
            "manuscript.md",
            "references.bib",
            "claim_ledger.csv",
        }
        text = self.read("references/REVIEW_TYPES.md")
        heading = re.compile(r"(?m)^## (.+)$")
        artifact_line = re.compile(r"^    <project_dir>/(.+)$", re.MULTILINE)
        heads = list(heading.finditer(text))
        sections = {
            heads[i].group(1).strip(): text[heads[i].end() : heads[i + 1].start() if i + 1 < len(heads) else len(text)]
            for i in range(len(heads))
        }
        for route, section_title in (
            ("scoping", "Scoping review"),
            ("systematic", "Systematic review with qualitative synthesis"),
        ):
            with self.subTest(route=route):
                documented = set(artifact_line.findall(sections[section_title]))
                created = set(module.project_files("proj", route)) - common_core
                self.assertEqual(
                    created,
                    documented,
                    f"REVIEW_TYPES {section_title} list and initializer files disagree",
                )


    def test_description_triggers_on_sections_chinese_requests_and_pooling(self):
        # Evaluation found the skill loaded in 1/5 runs for "write the introduction of my
        # narrative review" and 3/5 for a Chinese section request; keep these triggers.
        description = re.search(r"(?m)^description: (.*)$", self.read("SKILL.md")).group(1)
        self.assertLessEqual(len(description), 1024)
        for term in ("section", "introduction", "综述", "系统综述", "范围综述", "pool"):
            with self.subTest(term=term):
                self.assertIn(term, description)

    def test_skill_delivers_to_the_path_the_user_names(self):
        # Evaluation found every scoping run wrote only <project_dir>/protocol/PROTOCOL.md
        # and never the protocol.md the user asked for.
        skill = self.read("SKILL.md")
        self.assertRegex(skill, r"(?s)Deliver where the user asked.{0,400}write it there")
        self.assertIn("ask before replacing it", skill)


if __name__ == "__main__":
    unittest.main()
