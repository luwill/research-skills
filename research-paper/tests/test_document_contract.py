r"""research-paper 的文档契约测试。

锁住「文档声称的纪律」与「门禁实际检查的模式」之间的等价性。第三轮评审
RP-01 的教训：门禁正则 `\[UNVERIFIED\]` 只匹配裸旗标，而 CITATION_INTEGRITY
Rule 3 规定的格式是 `[UNVERIFIED: …]`——严格按文档打旗标的未核验引用对
zero-hits 门禁完全隐形。此测试让那类漂移在 CI 变红。
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: 两处占位符门禁 grep 的形状（SKILL.md Phase 5 与 QUALITY_CHECKLIST 各一份）
GATE_GREP_RE = re.compile(r'grep -nE "([^"]+)" paper_draft\.md')

#: 测试必须用**真实 grep**执行提取出的模式——codex 评审 CB-1：`[^\]]`
#: 在 Python re / ugrep 里语义正确，在 BSD/POSIX grep 里不匹配。用 re 验证
#: 一个 grep 门禁等于用错的引擎证明对的结论。
GREP = "/usr/bin/grep" if Path("/usr/bin/grep").exists() else shutil.which("grep")


def run_gate_grep(pattern: str, text: str) -> bool:
    """用系统 grep -E 判断 pattern 是否命中 text（引擎=门禁引擎）。"""
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as handle:
        handle.write(text)
        name = handle.name
    try:
        result = subprocess.run(
            [GREP, "-nE", pattern, name], capture_output=True, text=True, check=False
        )
    finally:
        Path(name).unlink(missing_ok=True)
    return result.returncode == 0


def placeholder_gate_patterns() -> list[tuple[str, str]]:
    """返回 (文件, 模式) 列表——所有写着占位符门禁的位置。"""
    found: list[tuple[str, str]] = []
    for relative in ("SKILL.md", "references/QUALITY_CHECKLIST.md"):
        text = (ROOT / relative).read_text(encoding="utf-8")
        for match in GATE_GREP_RE.finditer(text):
            found.append((relative, match.group(1)))
    return found


class PlaceholderGateContract(unittest.TestCase):
    def test_gate_exists_in_both_declared_locations(self):
        locations = {relative for relative, _ in placeholder_gate_patterns()}
        self.assertEqual(
            locations, {"SKILL.md", "references/QUALITY_CHECKLIST.md"},
            "占位符门禁应在 SKILL.md Phase 5 与 QUALITY_CHECKLIST 两处声明",
        )

    def test_gate_matches_the_documented_colon_flag_form(self):
        """CITATION_INTEGRITY Rule 3 规定旗标格式为 `[UNVERIFIED: …]`。

        门禁正则必须**在真实 grep 下**命中它，否则按文档打旗标的未核验
        引用逃过 zero-hits 门禁（CB-1：Python re 验证不等于 grep 验证）。
        """
        for relative, pattern in placeholder_gate_patterns():
            with self.subTest(file=relative, engine=GREP):
                self.assertTrue(
                    run_gate_grep(
                        pattern, "We compare against [UNVERIFIED: Smith et al. 2024]."
                    ),
                    f"{relative} 的门禁在真实 grep 下放走了文档规定的冒号形旗标",
                )

    def test_gate_still_matches_the_bare_flag_form(self):
        for relative, pattern in placeholder_gate_patterns():
            with self.subTest(file=relative, engine=GREP):
                self.assertTrue(run_gate_grep(pattern, "Pending entry [UNVERIFIED]."))
                self.assertTrue(run_gate_grep(pattern, "Value [PENDING: user to supply]."))
                self.assertTrue(run_gate_grep(pattern, "Value [PENDING]."))


class AiTellGateContract(unittest.TestCase):
    def _gate_pattern(self) -> str:
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        match = re.search(r'grep -nEi "([^"]*over the past[^"]*)"', text)
        assert match, "SKILL.md Phase 5 应包含 AI-tell 门禁 grep"
        return match.group(1)

    def test_gate_covers_the_banned_opening_family(self):
        """WRITING_STYLE 禁用表列出的家族必须全部被门禁命中（RP-04）。"""
        pattern = self._gate_pattern()
        for phrase in (
            "Over the past few years, segmentation has improved.",
            "Over the past decade, X has emerged.",
            "over the past three decades",
            "众所周知",
        ):
            with self.subTest(phrase=phrase):
                self.assertTrue(re.search(pattern, phrase, re.I), phrase)

    def test_gate_keeps_legitimate_numbered_spans_out(self):
        pattern = self._gate_pattern()
        self.assertIsNone(re.search(pattern, "over the past 5 years, incidence fell."))


class CitationIntegrityContract(unittest.TestCase):
    def test_variant_declares_derivation_from_the_shared_core(self):
        text = (ROOT / "references/CITATION_INTEGRITY.md").read_text(encoding="utf-8")
        self.assertRegex(text, r"Derived from[\s\S]*?citation-integrity-core")

    def test_documented_flag_forms_use_the_shared_taxonomy_shape(self):
        """共享旗标分类（docs/citation-integrity-core.md）规定 `[UNVERIFIED: …]`。"""
        text = (ROOT / "references/CITATION_INTEGRITY.md").read_text(encoding="utf-8")
        self.assertIn("`[UNVERIFIED: …]`", text)


class TriggerContract(unittest.TestCase):
    def test_description_triggers_on_single_sections(self):
        # 评测（haiku，5 次）：只请它写「讨论」部分时 0/5 加载本 skill；锁住这些触发词。
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        description = re.search(r"(?ms)^description: >\n(.*?)^---", skill).group(1)
        self.assertLessEqual(len(" ".join(description.split())), 1024)
        for term in ("single section", "discussion", "introduction", "讨论部分", "引言", "摘要"):
            with self.subTest(term=term):
                self.assertIn(term, description)

    def test_single_section_request_writes_the_named_file(self):
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertRegex(skill, r"(?s)## Single-section requests.{0,400}write the file the user named")


if __name__ == "__main__":
    unittest.main()
