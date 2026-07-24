from __future__ import annotations

import csv
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "audit_manuscript.py"
SPEC = importlib.util.spec_from_file_location("audit_manuscript", SCRIPT)
assert SPEC and SPEC.loader
audit = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = audit
SPEC.loader.exec_module(audit)


def source_lines(text: str):
    return audit.visible_lines(text)


def categories(result: dict) -> list[str]:
    return [finding["category"] for finding in result["findings"]]


def project_manuscript(text: str) -> str:
    match = re.search(r"(?im)^##\s+(?:references|参考文献)\s*$", text)
    return (text[: match.start()] if match else text).rstrip() + "\n"


NARRATIVE = """# A Narrative Review of Imaging AI

## Key Points
- One substantive point about design choices.
- One substantive point about data quality.
- One substantive point about evaluation.
- One substantive point about translation.

## Abstract
This narrative review describes imaging AI methods and evidence boundaries.

## Methods
We selected representative primary sources using an explicit rationale.

## Discussion
The literature contains several distinct design families [@garcia2024].

## References
[@garcia2024] García M, O’Connor P. A verified paper. doi:10.1000/example
"""


SYSTEMATIC = """# Imaging AI: A Systematic Review

## Abstract
We conducted a systematic review of imaging AI evidence.

## Methods
The question used PICOS to define participants, intervention, comparator, outcomes, and study design.

### Protocol and registration
The protocol and any deviations were recorded before screening began.

### Eligibility criteria
Explicit inclusion and exclusion criteria defined eligible reports.

### Information sources and search strategy
Database-specific complete strategies and search dates were preserved.

### Selection process
Two human reviewers screened reports and adjudicated conflicts.

### Data collection and data items
Two reviewers extracted all prespecified critical data items.

### Risk of bias assessment
A question-matched tool was applied independently by two reviewers.

### Synthesis methods
The synthesis followed the prespecified comparison framework.

## Results
Included evidence is summarized by outcome [@muller2024].

## References
[@muller2024] Müller A, García B. Primary study. doi:10.1000/systematic
"""


SCOPING_ZH = """# 医学影像人工智能范围综述

## 摘要
本范围综述绘制医学影像人工智能研究的证据图谱。

## 方法
研究问题采用 PCC，明确人群、概念与情境。

### 方案与注册
方案在检索和筛选开始前完成并记录偏离。

### 纳入与排除标准
预先规定纳入和排除标准并用于全部记录。

### 信息来源与检索策略
保存每个数据库的完整检索式、平台和日期。

### 文献筛选
两名研究者完成人工筛选并解决分歧。

### 数据整理
使用校准后的表格整理全部预设变量。

### 证据综合
按人群、概念和情境生成证据图谱。

## 结果
研究按预设维度汇总 [@zhang2024]。

## 参考文献
[@zhang2024] 张伟, Müller A. 一项原始研究. doi:10.1000/scoping
"""


class ParsingTests(unittest.TestCase):
    def test_fenced_code_is_ignored_and_does_not_split_references(self):
        text = """# Narrative Review
```markdown
# References
[TBD]
```
Body claim [1].
## References
1. Smith J. Real paper.
"""
        lines = source_lines(text)
        body, refs, found = audit.split_body_and_refs(lines)
        self.assertTrue(found)
        self.assertIn("Body claim [1].", [line.text for line in body])
        self.assertEqual([], audit.scan_placeholders(lines))
        self.assertEqual({"1"}, set(audit.parse_references(refs).entries))

    def test_reference_headings_support_english_and_chinese(self):
        for heading in ("References", "Reference", "Bibliography", "参考文献", "文献"):
            with self.subTest(heading=heading):
                lines = source_lines(f"Claim [1].\n## {heading}\n1. Smith J. Paper.")
                _, refs, found = audit.split_body_and_refs(lines)
                self.assertTrue(found)
                self.assertEqual({"1"}, set(audit.parse_references(refs).entries))

    def test_plain_reference_heading_is_supported(self):
        body, refs, found = audit.split_body_and_refs(
            source_lines("Claim [1].\nReferences\n1) Smith J. Paper.")
        )
        self.assertTrue(found)
        self.assertEqual(1, len(body))
        self.assertIn("1", audit.parse_references(refs).entries)

    def test_reference_entry_formats_and_duplicate_identifier(self):
        refs = audit.parse_references(
            source_lines(
                "[1] García M. One.\n2. Müller A. Two.\n3) 张伟. Three.\n"
                "[@stable-key] O’Connor P. Four.\n[1] Duplicate."
            )
        )
        self.assertEqual({"1", "2", "3", "@stable-key"}, set(refs.entries))
        self.assertIn("duplicate_reference_identifier", [f.category for f in refs.findings])

    def test_numeric_and_citekey_citations(self):
        citations, findings = audit.parse_citations(
            source_lines("Evidence [1, 2; 4-5; 7–8] and [@müller2024; @zhang-ai].")
        )
        self.assertEqual([], findings)
        self.assertEqual(
            ["1", "2", "4", "5", "7", "8", "@müller2024", "@zhang-ai"],
            [citation.identifier for citation in citations],
        )

    def test_fullwidth_citations_references_locators_and_textual_citekeys(self):
        citations, findings = audit.parse_citations(
            source_lines(
                "证据见［１–２］和【@张2024, p. 4; @müller2025, 表 2】，另见 @garcía2026。"
            )
        )
        self.assertEqual([], findings)
        self.assertEqual(
            ["1", "2", "@张2024", "@müller2025", "@garcía2026"],
            [citation.identifier for citation in citations],
        )
        refs = audit.parse_references(
            source_lines("［１］ 张伟. 第一篇。\n【@张2024】 张伟. 第二篇。")
        )
        self.assertEqual({"1", "@张2024"}, set(refs.entries))

    def test_confidence_interval_brackets_are_not_treated_as_citations(self):
        citations, findings = audit.parse_citations(
            source_lines("Sensitivity was 0.80 [95% CI 0.70-0.88].")
        )
        self.assertEqual([], citations)
        self.assertEqual([], findings)

    def test_bibtex_parser_ignores_comments_detects_truncation_and_duplicate_doi(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            (project / "references.bib").write_text(
                "% @article{fake, title={Comment only}}\n"
                "@string{jmi = \"Journal of Imaging\"}\n"
                "@article{one, title={Nested {Title}}, doi={10.1000/same}}\n"
                "@article(two, title={Second}, doi={10.1000/same})\n",
                encoding="utf-8",
            )
            references = audit.parse_project_bibliography(project)
            self.assertEqual({"@one", "@two"}, set(references.entries))
            self.assertNotIn("@fake", references.entries)
            self.assertEqual(1, len(audit.scan_duplicate_dois(references)))

            (project / "references.bib").write_text(
                "@article{broken,\n title={Never closed}\n", encoding="utf-8"
            )
            broken = audit.parse_project_bibliography(project)
            self.assertIn(
                "malformed_bibliography_entry",
                [finding.category for finding in broken.findings],
            )

    def test_malformed_numeric_citation_is_reported(self):
        citations, findings = audit.parse_citations(source_lines("Broken [1, x] and [4-2]."))
        self.assertEqual([], citations)
        self.assertEqual(2, sum(f.category == "malformed_citation" for f in findings))

    def test_unicode_multi_author_reference_does_not_use_ascii_heuristic(self):
        result = audit.audit_text(NARRATIVE, file_label="unicode.md", requested_route="narrative")
        self.assertNotIn("author_citation_mismatch", categories(result))
        self.assertIn("author_attribution_alignment", result["not_assessed_checks"])

    def test_auto_route_uses_title_and_abstract_not_bibliography(self):
        text = NARRATIVE.replace(
            "A verified paper", "A systematic review of an unrelated topic"
        )
        result = audit.audit_text(text, file_label="narrative.md", requested_route="auto")
        self.assertEqual("narrative", result["route"])
        self.assertNotIn("unsupported_systematic_claim", categories(result))

    def test_negated_systematic_phrase_does_not_change_auto_route(self):
        text = NARRATIVE.replace(
            "This narrative review describes imaging AI methods and evidence boundaries.",
            "This is a narrative rather than a systematic review.",
        )
        result = audit.audit_text(text, file_label="negated.md", requested_route="auto")
        self.assertEqual("narrative", result["route"])

    def test_pandoc_prefix_suffix_negative_and_fullwidth_citekeys(self):
        citations, findings = audit.parse_citations(
            source_lines(
                "Evidence [e.g., @smith2024; @jones2025]. "
                "证据［见 @张2024，页4］；另见 [-@excluded2023]. "
                "[link @not-a-citation](https://example.org) "
                "![image @also-not](figure.png)"
            )
        )
        self.assertEqual([], findings)
        self.assertEqual(
            ["@smith2024", "@jones2025", "@张2024", "@excluded2023"],
            [citation.identifier for citation in citations],
        )

    def test_parenthetical_numeric_citations_and_year_guard(self):
        citations, findings = audit.parse_citations(
            source_lines("Evidence (1), (2, 4), and (5–7), published in (2024), section (1.2).")
        )
        self.assertEqual([], findings)
        self.assertEqual(
            ["1", "2", "4", "5", "6", "7"],
            [citation.identifier for citation in citations],
        )


class RouteAndStyleTests(unittest.TestCase):
    def test_narrative_positive_example_has_no_gate_relevant_findings(self):
        result = audit.audit_text(
            NARRATIVE, file_label="narrative.md", requested_route="narrative"
        )
        self.assertEqual("not_assessed", result["gate_status"])
        self.assertFalse(
            any(finding["gate_relevant"] for finding in result["findings"])
        )
        self.assertTrue(
            {
                "prisma_reporting_completeness",
                "risk_of_bias_domain_completeness",
                "search_strategy_recall_and_completeness",
                "search_export_completeness_and_record_counts",
                "human_identity_and_independence",
            }.issubset(result["not_assessed_checks"])
        )

    def test_keyword_shell_does_not_satisfy_systematic_methods(self):
        shell = """# A Systematic Review
## Abstract
We conducted a systematic review.
## Methods
PRISMA eligibility criteria search strategy screening risk of bias data extraction.
## References
1. Smith J. Paper.
"""
        result = audit.audit_text(shell, file_label="shell.md", requested_route="systematic")
        self.assertIn("missing_methods_element", categories(result))
        self.assertEqual("fail", result["gate_status"])

    def test_complete_structured_systematic_methods_have_no_method_findings(self):
        body, _, _ = audit.split_body_and_refs(source_lines(SYSTEMATIC))
        findings = audit.scan_evidence_route_methods("systematic", body)
        self.assertEqual([], findings)

    def test_chinese_scoping_methods_are_recognized(self):
        body, _, _ = audit.split_body_and_refs(source_lines(SCOPING_ZH))
        findings = audit.scan_evidence_route_methods("scoping", body)
        self.assertEqual([], findings)

    def test_scoping_auto_route_is_inferred_from_title(self):
        result = audit.audit_text(SCOPING_ZH, file_label="范围综述.md", requested_route="auto")
        self.assertEqual("scoping", result["route"])

    def test_explicit_route_conflicting_with_title_is_critical(self):
        result = audit.audit_text(
            NARRATIVE,
            file_label="mismatch.md",
            requested_route="systematic",
        )
        self.assertIn("route_mismatch", categories(result))
        self.assertEqual("fail", result["gate_status"])

    def test_meta_analysis_and_umbrella_titles_are_rejected(self):
        for title in (
            "# A Meta-analysis of Imaging AI",
            "# An Umbrella Review of Imaging AI",
            "# 医学影像人工智能荟萃分析",
            "# 医学影像人工智能伞形综述",
        ):
            with self.subTest(title=title):
                text = title + "\n\n## Abstract\nThis review summarizes evidence.\n"
                result = audit.audit_text(
                    text, file_label="unsupported.md", requested_route="auto"
                )
                self.assertEqual("fail", result["gate_status"])
                self.assertIn("unsupported_route_claim", categories(result))

    def test_operational_meta_and_umbrella_methods_are_rejected_outside_front_matter(self):
        for sentence in (
            "We fit a random-effects model and report pooled estimates.",
            "We used a meta-analysis to combine study results.",
            "A meta-analysis synthesized the eligible studies.",
            "Review overlap was quantified with the corrected covered area.",
            "This umbrella review compares prior systematic reviews.",
        ):
            with self.subTest(sentence=sentence):
                text = NARRATIVE.replace(
                    "We selected representative primary sources using an explicit rationale.",
                    sentence,
                )
                result = audit.audit_text(
                    text, file_label="unsupported-body.md", requested_route="narrative"
                )
                self.assertIn("unsupported_route_claim", categories(result))

    def test_negated_meta_analysis_language_is_not_rejected(self):
        text = NARRATIVE.replace(
            "This narrative review describes imaging AI methods and evidence boundaries.",
            "No meta-analysis was performed, and no pooled estimate was calculated.",
        )
        result = audit.audit_text(
            text, file_label="negated-meta.md", requested_route="narrative"
        )
        self.assertNotIn("unsupported_route_claim", categories(result))

    def test_additional_operational_meta_phrases_and_background_guard(self):
        operational = (
            "We meta-analyzed the eligible studies.",
            "The data were meta-analysed.",
            "Quantitative pooling was performed.",
            "Quantitative pooling was undertaken using inverse-variance weighting.",
            "Effect sizes were meta-analysed using inverse variance.",
            "We used inverse-variance weighting.",
            "本综述采用随机效应模型合并效应量。",
            "采用随机效应模型合并效应量。",
        )
        for sentence in operational:
            with self.subTest(sentence=sentence):
                text = NARRATIVE.replace(
                    "We selected representative primary sources using an explicit rationale.",
                    sentence,
                )
                self.assertIn(
                    "unsupported_route_claim",
                    categories(audit.audit_text(text, file_label="meta.md", requested_route="narrative")),
                )
        background = NARRATIVE.replace(
            "We selected representative primary sources using an explicit rationale.",
            "Prior reviews used random-effects models and inverse-variance methods; this review only describes them.",
        )
        self.assertNotIn(
            "unsupported_route_claim",
            categories(audit.audit_text(background, file_label="background.md", requested_route="narrative")),
        )
        discussion_background = NARRATIVE.replace(
            "The literature contains several distinct design families [@garcia2024].",
            "Prior reviews reported that effect sizes were meta-analysed using inverse variance [@garcia2024].",
        )
        self.assertNotIn(
            "unsupported_route_claim",
            categories(
                audit.audit_text(
                    discussion_background,
                    file_label="discussion-background.md",
                    requested_route="narrative",
                )
            ),
        )

    def test_box_context_does_not_leak_from_body_mention_or_sandbox(self):
        profile = audit.effective_profile(
            "narrative", {"require_box_for_display_equations": True}
        )
        mention = audit.scan_equations(
            source_lines("## Metrics\nSee Box 1 for details.\n$$x=1$$"), profile
        )
        sandbox = audit.scan_equations(
            source_lines("## Sandbox analysis\n$$x=1$$"), profile
        )
        self.assertEqual(1, len(mention))
        self.assertEqual(1, len(sandbox))

    def test_explicit_box_contains_equation_and_two_delimiters_report_once(self):
        profile = audit.effective_profile(
            "narrative", {"require_box_for_display_equations": True}
        )
        inside = audit.scan_equations(
            source_lines("## Box 1 Metrics\n$$\nx=1\n$$\n## Discussion"), profile
        )
        outside = audit.scan_equations(source_lines("## Metrics\n$$\nx=1\n$$"), profile)
        self.assertEqual([], inside)
        self.assertEqual(1, len(outside))

    def test_heading_rules_are_route_and_profile_aware(self):
        lines = source_lines("## 1. Methods\n##### Deep heading")
        narrative = audit.scan_headings(
            lines,
            audit.effective_profile(
                "narrative", {"allow_numbered_headings": False, "max_heading_level": 3}
            ),
        )
        systematic = audit.scan_headings(
            lines,
            audit.effective_profile(
                "systematic", {"allow_numbered_headings": True, "max_heading_level": 4}
            ),
        )
        custom = audit.scan_headings(
            lines,
            audit.effective_profile(
                "narrative", {"allow_numbered_headings": True, "max_heading_level": 5}
            ),
        )
        self.assertEqual({"numbered_heading", "heading_depth"}, {f.category for f in narrative})
        self.assertEqual(["heading_depth"], [f.category for f in systematic])
        self.assertEqual([], custom)

    def test_vendor_table_case_and_profile_override(self):
        lines = source_lines("Vendor | Evidence\nheartflow | peer reviewed\n\nHEARTFLOW is discussed.")
        default = audit.scan_vendor_mentions(
            lines,
            audit.effective_profile(
                "narrative", {"vendors": ["HeartFlow"], "allow_vendor_body_mentions": False}
            ),
        )
        allowed = audit.scan_vendor_mentions(
            lines,
            audit.effective_profile("narrative", {"allow_vendor_body_mentions": True}),
        )
        self.assertEqual(1, len(default))
        self.assertEqual([], allowed)

    def test_placeholder_doi_variants_and_fenced_examples(self):
        text = """doi:10.1234/?
DOI: 10.1234/TBD
doi: 10.1234/x
10.1234/to-be-filled
```
doi:10.1234/xxx
```
"""
        findings = audit.scan_placeholders(source_lines(text))
        self.assertEqual(4, len(findings))
        self.assertTrue(all(f.severity == "critical" for f in findings))

    def test_empty_and_no_reference_manuscripts_never_have_zero_findings(self):
        empty = audit.audit_text("", file_label="empty.md", requested_route="narrative")
        no_refs = audit.audit_text("# Title\n## Abstract\nText.", file_label="no-refs.md", requested_route="narrative")
        self.assertIn("empty_manuscript", categories(empty))
        self.assertIn("missing_references_section", categories(no_refs))

    def test_profile_can_disable_key_points_requirement(self):
        no_key_points = NARRATIVE.replace(
            "## Key Points\n- One substantive point about design choices.\n- One substantive point about data quality.\n- One substantive point about evaluation.\n- One substantive point about translation.\n\n",
            "",
        )
        result = audit.audit_text(
            no_key_points,
            file_label="profile.md",
            requested_route="narrative",
            profile_overrides={"require_key_points": False},
        )
        self.assertNotIn("missing_key_points", categories(result))


class ProjectGateTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.project = Path(self.tempdir.name) / "example-20260723-120000-acde1234"
        self.project.mkdir()

    def tearDown(self):
        self.tempdir.cleanup()

    def write(self, relative: str, content: str = "ready\n") -> Path:
        path = self.project / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def write_csv(self, relative: str, columns: tuple[str, ...], rows: list[dict[str, str]]) -> Path:
        path = self.project / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
        return path

    def config_text(self, route: str) -> str:
        return f'''schema_version: "2.0"
project_id: "{self.project.name}"
project_dir: "."
project_dir_base: "review_config_directory"
route: "{route}"
schemas:
  claim_ledger: "2.0"
  human_review_gate: "2.0"
review:
  title_working: "Evidence review"
  question_framework: "PCC" 
  question: "What evidence is available?"
  population: "Adults"
  concept_or_index_test: "Imaging AI"
  comparator_or_reference_standard: "not_applicable"
  outcomes_or_target_condition: "Evidence characteristics"
  context: "Clinical imaging"
  modality: "CT"
  anatomy: "Thorax"
  task: "Diagnosis"
  setting: "Multicentre care"
  audience: "Clinicians and researchers"
  target_journal: "not_applicable"
  language: "English"
coverage:
  start: "database inception"
  end: "2026-07-23"
  evidence_cutoff: "2026-07-23"
  databases_available: [MEDLINE]
  eligibility_languages: [English]
  grey_literature_policy: "Include registries; exclude unverified marketing"
methods:
  conduct_guidance:
    - title: "JBI evidence synthesis guidance"
      version: "2024"
      url: "https://example.org/conduct"
      accessed_at: "2026-07-23"
      applicability: "Route conduct"
      replaces: "null"
  review_reporting_guidance:
    - title: "PRISMA route guidance"
      version: "2020"
      url: "https://example.org/reporting"
      accessed_at: "2026-07-23"
      applicability: "Review reporting"
      replaces: "null"
  risk_of_bias_tools:
    - title: "QUADAS-3"
      version: "2024"
      url: "https://example.org/rob"
      accessed_at: "2026-07-23"
      applicability: "Diagnostic accuracy studies"
      replaces: "QUADAS-2"
  certainty_framework: null
citations:
  bibliography: "references.bib"
  working_syntax: "pandoc-citekey"
human_review:
  gate_path: {('"human_review_gate.json"' if route == 'systematic' else 'null')}
ai_assistance:
  used: true
  human_decision_authority_confirmed: true
delivery:
  format: "markdown"
  project_status: "verification"
'''

    @staticmethod
    def disclosure_text() -> str:
        return """# AI Assistance Disclosure

## Tools
| Tool/model | Version or access date | Provider | Data sent | Retention/privacy notes |
|---|---|---|---|---|
| Example LLM | 2026-07-23 | Provider | Public metadata | No patient data |

## Assisted tasks
| Task | Assistance provided | Human decision-maker | Verification performed | Known limitations |
|---|---|---|---|---|
| Citation triage | Suggested candidates | human-a | Full-text human check | May miss sources |

## Prohibited substitutions
AI did not replace human decisions.
"""

    @staticmethod
    def claim_row(claim_text: str, citekey: str, source_id: str) -> dict[str, str]:
        row = {column: "not_applicable" for column in audit.CLAIM_LEDGER_COLUMNS}
        row.update(
            {
                "claim_id": "claim-1",
                "section": "Results",
                "claim_text": claim_text,
                "claim_type": "factual",
                "citekey": citekey,
                "source_id": source_id,
                "source_locator": "Results, page 4, paragraph 2",
                "evidence_excerpt": "The source reports the summarized evidence.",
                "population_or_dataset": "Included clinical cohort",
                "data_split": "external_test",
                "split_unit": "patient",
                "comparator": "not_applicable",
                "metric": "not_applicable",
                "estimate": "not_applicable",
                "unit": "not_applicable",
                "uncertainty_interval": "not_applicable",
                "direction": "not_applicable",
                "access_level": "full_text",
                "source_role": "primary_study",
                "access_uri": "https://doi.org/" + source_id.removeprefix("doi:"),
                "accessed_at": "2026-07-23",
                "verification_status": "verified",
                "verified_by": "human-a",
                "verified_at": "2026-07-23",
                "notes": "",
            }
        )
        return row

    def make_common(self, route: str = "narrative"):
        for relative in (
            "REVIEW_CONTEXT.md",
            "IMPLEMENTATION_PLAN.md",
            "PARADIGM.md",
            "protocol_deviations.md",
            "EXPERT_SIGNOFF.md",
        ):
            self.write(relative, "# Record\n\nA substantive human-owned project record is maintained here.\n")
        self.write("review_config.yaml", self.config_text(route))
        self.write("AI_USE_DISCLOSURE.md", self.disclosure_text())
        self.write("references.bib", "% canonical bibliography\n")
        self.write_csv("claim_ledger.csv", audit.CLAIM_LEDGER_COLUMNS, [])

    def make_systematic(self, gate: dict | None = None):
        self.make_common("systematic")
        for alternatives in audit.SYSTEMATIC_PROJECT_FILES:
            self.write(alternatives[0])
        self.write("protocol/PROTOCOL.md", "# Protocol\n\n" + "This protocol prespecifies eligibility, information sources, human screening, data extraction, risk of bias, qualitative synthesis, reporting, amendments, and disclosure. " * 4)
        self.write("search/search_plan.md", "# Search Plan\n\n" + "The search uses controlled vocabulary, database-specific syntax, inception coverage, immutable exports, deduplication, peer review, and an update trigger. " * 3)
        self.write("screening/calibration_log.md", "# Calibration\n\nTwo human reviewers piloted records, discussed disagreements, froze interpretation rules, documented changes, and obtained approval before formal screening began.")
        self.write("reporting/PRISMA_2020_checklist.md", "# PRISMA 2020 Checklist\n\n- [x] Title and methods checked against the completed evidence package.\n")
        self.write("risk_of_bias/decision_rules.md", "# Risk-of-Bias Decision Rules\n\nTwo human reviewers independently apply the named tool and version, cite exact source locations, preserve domain judgments, resolve conflicts through a tracked adjudicator, and document protocol deviations.")
        self.write("search/strategies/medline.txt", "1 exp Artificial Intelligence/\n2 exp Tomography, X-Ray Computed/\n3 1 and 2\n")
        self.write("search/exports/medline.ris", "TY  - JOUR\nID  - record-1\nER  -\n")
        self.write_csv(
            "search/search_log.csv",
            audit.SEARCH_LOG_COLUMNS,
            [{
                "source": "MEDLINE", "platform": "Ovid", "coverage": "inception-2026-07-23",
                "search_date": "2026-07-23", "strategy_file": "search/strategies/medline.txt",
                "filters": "none", "result_count": "2", "export_file": "search/exports/medline.ris",
                "searcher_id": "human-a", "notes": "peer reviewed",
            }],
        )
        self.write_csv(
            "search/deduplication_log.csv",
            audit.DEDUPLICATION_COLUMNS,
            [{"record_id": "record-duplicate", "duplicate_group": "dup-1", "decision": "remove", "rule": "same DOI", "reviewer_id": "human-a", "decided_at": "2026-07-23"}],
        )
        self.write(
            "reporting/flow_counts.json",
            json.dumps(
                {
                    "identified": 2,
                    "deduplicated": 1,
                    "screened": 1,
                    "full_text_assessed": 1,
                    "included": 1,
                }
            ),
        )
        screening_rows = []
        for stage in ("title_abstract", "full_text"):
            for reviewer in ("human-a", "human-b"):
                screening_rows.append({
                    "record_id": "record-1", "stage": stage, "reviewer_id": reviewer,
                    "human_reviewer": "true", "decision": "include", "exclusion_reason": "not_applicable",
                    "conflict": "false", "adjudication_status": "not_applicable", "decided_at": "2026-07-23",
                })
        self.write_csv("screening/screening_decisions.csv", audit.SCREENING_COLUMNS, screening_rows)
        self.write_csv("screening/full_text_exclusions.csv", audit.FULL_TEXT_EXCLUSION_COLUMNS, [])
        critical_rows = []
        for reviewer in ("human-a", "human-b"):
            row = {column: "not_applicable" for column in audit.CRITICAL_DATA_COLUMNS}
            row.update({
                "study_id": "study-1", "outcome_id": "outcome-1", "decision_group_id": "extract-1",
                "citekey": "muller2024", "dataset_or_cohort": "cohort-1", "dataset_split": "external_test",
                "split_unit": "patient", "subgroup": "all", "threshold": "prespecified",
                "comparator": "radiologist", "metric": "sensitivity", "time_point": "index visit",
                "estimate": "0.80", "unit": "probability", "uncertainty_interval": "95% CI 0.70-0.88",
                "source_locator": "Table 2, page 4", "extractor_id": reviewer, "human_reviewer": "true",
                "decision_status": "complete", "notes": "",
            })
            critical_rows.append(row)
        self.write_csv("extraction/critical_data.csv", audit.CRITICAL_DATA_COLUMNS, critical_rows)
        rob_rows = []
        for reviewer in ("human-a", "human-b"):
            rob_rows.append({
                "study_id": "study-1", "decision_group_id": "rob-1", "tool": "QUADAS-3",
                "tool_version": "2024", "domain": "participants", "reviewer_id": reviewer,
                "human_reviewer": "true", "judgment": "low", "source_locator": "Methods, page 2",
                "rationale": "Consecutive eligible participants were enrolled.", "conflict": "false",
                "adjudication_status": "not_applicable",
            })
        self.write_csv("risk_of_bias/assessments.csv", audit.RISK_OF_BIAS_COLUMNS, rob_rows)
        self.write_csv("certainty/assessments.csv", audit.CERTAINTY_COLUMNS, [])
        self.write_csv("adjudication/conflict_log.csv", audit.CONFLICT_COLUMNS, [])
        study_row = {column: "not_applicable" for column in audit.STUDY_CHARACTERISTICS_COLUMNS}
        study_row.update({
            "study_id": "study-1", "report_id": "record-1", "citekey": "muller2024",
            "study_design": "diagnostic accuracy", "population": "adults", "modality": "CT",
            "task": "diagnosis", "dataset_or_cohort": "cohort-1", "split_method": "external",
            "split_unit": "patient", "reference_standard": "pathology", "external_validation": "yes",
            "extractor_id": "human-a", "verification_status": "verified", "notes": "",
        })
        self.write_csv("extraction/study_characteristics.csv", audit.STUDY_CHARACTERISTICS_COLUMNS, [study_row])
        cohort_row = {column: "not_applicable" for column in audit.COHORT_LINKAGE_COLUMNS}
        cohort_row.update({
            "cohort_id": "cohort-1", "dataset_name": "clinical cohort", "study_id": "study-1",
            "report_id": "record-1", "site": "site-a", "date_range": "2020-2022",
            "participant_overlap_status": "none_identified", "shared_test_set_status": "none_identified",
            "linkage_evidence": "Methods and supplement", "decision_for_synthesis": "include_once",
            "reviewer_id": "human-a", "notes": "",
        })
        self.write_csv("extraction/cohort_linkage.csv", audit.COHORT_LINKAGE_COLUMNS, [cohort_row])
        self.write("references.bib", "@article{muller2024,\n title={Primary study},\n doi={10.1000/systematic}\n}\n")
        self.write_csv("claim_ledger.csv", audit.CLAIM_LEDGER_COLUMNS, [self.claim_row("Included evidence is summarized by outcome", "muller2024", "doi:10.1000/systematic")])
        if gate is not None:
            self.write("human_review_gate.json", json.dumps(gate))

    def make_scoping(self, *, populated: bool) -> None:
        self.make_common("scoping")
        for alternatives in audit.SCOPING_PROJECT_FILES:
            self.write(alternatives[0])
        self.write("protocol/PROTOCOL.md", "# Protocol\n\n" + ("The protocol defines PCC eligibility, reproducible searching, dual human screening, charting verification, mapping, reporting, deviations, and disclosure. " * 5 if populated else ""))
        self.write("search/search_plan.md", "# Search Plan\n\n" + ("Controlled vocabulary and database syntax are preserved with coverage, limits, exports, deduplication, peer review, and an update trigger. " * 4 if populated else ""))
        self.write("screening/calibration_log.md", "# Calibration\n\n" + ("Two human reviewers piloted the same records, resolved disagreements, froze eligibility rules, and documented approval before screening." if populated else ""))
        self.write("reporting/PRISMA_ScR_checklist.md", "# PRISMA-ScR Checklist\n\n" + ("- [x] Required report items checked.\n" if populated else ""))
        if populated:
            self.write("search/strategies/medline.txt", "1 exp Artificial Intelligence/\n2 exp Pathology/\n3 1 and 2\n")
            self.write("search/exports/medline.ris", "TY  - JOUR\nID  - record-1\nER  -\n")
        self.write_csv("search/search_log.csv", audit.SEARCH_LOG_COLUMNS, ([{
            "source": "MEDLINE", "platform": "Ovid", "coverage": "inception-2026-07-23",
            "search_date": "2026-07-23", "strategy_file": "search/strategies/medline.txt", "filters": "none",
            "result_count": "2", "export_file": "search/exports/medline.ris", "searcher_id": "human-a", "notes": "peer reviewed",
        }] if populated else []))
        self.write_csv("search/deduplication_log.csv", audit.DEDUPLICATION_COLUMNS, ([{
            "record_id": "record-duplicate", "duplicate_group": "dup-1", "decision": "remove",
            "rule": "same DOI", "reviewer_id": "human-a", "decided_at": "2026-07-23",
        }] if populated else []))
        self.write(
            "screening/screening_decisions.csv",
            ",".join(audit.SCREENING_COLUMNS) + "\n"
            + (
                "record-1,title_abstract,human-a,true,include,not_applicable,false,not_applicable,2026-07-23\n"
                "record-1,title_abstract,human-b,true,include,not_applicable,false,not_applicable,2026-07-23\n"
                "record-1,full_text,human-a,true,include,not_applicable,false,not_applicable,2026-07-23\n"
                "record-1,full_text,human-b,true,include,not_applicable,false,not_applicable,2026-07-23\n"
                if populated
                else ""
            ),
        )
        self.write_csv("screening/full_text_exclusions.csv", audit.FULL_TEXT_EXCLUSION_COLUMNS, [])
        self.write(
            "extraction/charting_table.csv",
            ",".join(audit.CHARTING_COLUMNS) + "\n"
            + ("record-1,zhang2024,adults,foundation models,clinical pathology,scoping evidence,digital pathology,mapping,model and validation fields,human-a,human-b,verified,none\n" if populated else ""),
        )
        self.write(
            "reporting/flow_counts.json",
            json.dumps(
                {
                    "identified": 2 if populated else None,
                    "deduplicated": 1 if populated else None,
                    "screened": 1 if populated else None,
                    "full_text_assessed": 1 if populated else None,
                    "included": 1 if populated else None,
                }
            ),
        )
        self.write_csv("adjudication/conflict_log.csv", audit.CONFLICT_COLUMNS, [])
        self.write("references.bib", "@article{zhang2024,\n title={Scoping source},\n doi={10.1000/scoping}\n}\n")
        scoping_claim = self.claim_row("研究按预设维度汇总", "zhang2024", "doi:10.1000/scoping")
        scoping_claim["section"] = "结果"
        self.write_csv("claim_ledger.csv", audit.CLAIM_LEDGER_COLUMNS, ([scoping_claim] if populated else []))

    def complete_gate(self) -> dict:
        return {
            "schema_version": "2.0",
            "project_id": self.project.name,
            "route": "systematic",
            "status": "complete",
            "reviewer_ids": ["human-a", "human-b"],
            "checks": {
                "title_abstract_screening": "complete",
                "full_text_screening": "complete",
                "critical_data_extraction": "complete",
                "risk_of_bias": "complete",
                "certainty_approval": "not_applicable",
                "conflicts_adjudicated": True,
                "ai_assistance_disclosed": True,
            },
            "evidence": audit.EXPECTED_GATE_EVIDENCE,
            "completed_at": "2026-07-23T12:00:00Z",
            "completed_by": "human-a",
        }

    def test_systematic_missing_project_dir_is_critical_not_ready(self):
        findings = audit.scan_project_readiness("systematic", None)
        self.assertEqual([("critical", "not_ready")], [(f.severity, f.category) for f in findings])

    def test_systematic_missing_human_gate_is_not_ready(self):
        self.make_systematic(gate=None)
        findings = audit.scan_project_readiness("systematic", self.project)
        self.assertTrue(any(f.category == "not_ready" and "human_review_gate" in f.message for f in findings))

    def test_header_only_scoping_scaffold_is_not_ready(self):
        self.make_scoping(populated=False)
        findings = audit.scan_project_readiness("scoping", self.project)
        self.assertEqual(1, len(findings))
        self.assertEqual("not_ready", findings[0].category)
        self.assertIn("executed-search row", findings[0].message)

    def test_populated_scoping_artifacts_are_machine_ready(self):
        self.make_scoping(populated=True)
        self.assertEqual([], audit.scan_project_readiness("scoping", self.project))

    def test_scoping_positive_example_reaches_not_assessed(self):
        self.make_scoping(populated=True)
        result = audit.audit_text(
            project_manuscript(SCOPING_ZH),
            file_label="scoping.md",
            requested_route="scoping",
            project_dir=self.project,
        )
        self.assertEqual("not_assessed", result["gate_status"])
        self.assertFalse(
            any(finding["gate_relevant"] for finding in result["findings"])
        )

    def test_systematic_positive_example_reaches_not_assessed(self):
        self.make_systematic(self.complete_gate())
        result = audit.audit_text(
            project_manuscript(SYSTEMATIC),
            file_label="systematic.md",
            requested_route="systematic",
            project_dir=self.project,
        )
        self.assertEqual("not_assessed", result["gate_status"])
        self.assertFalse(
            any(finding["gate_relevant"] for finding in result["findings"])
        )

    def test_human_gate_requires_two_distinct_reviewers_and_all_checks(self):
        gate = self.complete_gate()
        gate["reviewer_ids"] = ["same", "same"]
        gate["checks"]["risk_of_bias"] = False
        self.make_systematic(gate)
        findings = audit.validate_human_gate(self.project)
        self.assertEqual(1, len(findings))
        self.assertIn("two distinct", findings[0].message)
        self.assertIn("risk_of_bias", findings[0].message)

    def test_complete_human_gate_requires_strict_template_values(self):
        gate = self.complete_gate()
        self.make_systematic(gate)
        self.assertEqual([], audit.scan_project_readiness("systematic", self.project))

    def test_screening_requires_two_humans_at_each_stage(self):
        self.make_systematic(self.complete_gate())
        with (self.project / "screening/screening_decisions.csv").open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        rows = [row for row in rows if not (row["stage"] == "full_text" and row["reviewer_id"] == "human-b")]
        self.write_csv("screening/screening_decisions.csv", audit.SCREENING_COLUMNS, rows)
        findings = audit.validate_human_gate(self.project)
        self.assertEqual(1, len(findings))
        self.assertIn("stage=full_text", findings[0].message)

    def test_each_screening_record_requires_two_human_decisions(self):
        self.make_systematic(self.complete_gate())
        with (self.project / "screening/screening_decisions.csv").open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        extra = dict(rows[0])
        extra["record_id"] = "record-2"
        rows.append(extra)
        self.write_csv("screening/screening_decisions.csv", audit.SCREENING_COLUMNS, rows)
        self.write(
            "reporting/flow_counts.json",
            json.dumps({"identified": 3, "deduplicated": 2, "screened": 2, "full_text_assessed": 1, "included": 1}),
        )
        findings = audit.validate_human_gate(self.project)
        self.assertEqual(1, len(findings))
        self.assertIn("record_id=record-2", findings[0].message)

    def test_each_extraction_and_rob_group_requires_two_humans(self):
        self.make_systematic(self.complete_gate())
        with (self.project / "extraction/critical_data.csv").open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        rows[1]["decision_group_id"] = "extract-2"
        self.write_csv("extraction/critical_data.csv", audit.CRITICAL_DATA_COLUMNS, rows)
        findings = audit.validate_human_gate(self.project)
        self.assertEqual(1, len(findings))
        self.assertIn("decision_group_id=extract-1", findings[0].message)
        self.assertIn("decision_group_id=extract-2", findings[0].message)

    def test_role_specific_teams_may_differ_when_gate_lists_union(self):
        gate = self.complete_gate()
        gate["reviewer_ids"] = [
            "screen-a",
            "screen-b",
            "extract-a",
            "extract-b",
            "rob-a",
            "rob-b",
        ]
        gate["completed_by"] = "screen-a"
        self.make_systematic(gate)
        mappings = (
            ("screening/screening_decisions.csv", audit.SCREENING_COLUMNS, "reviewer_id", ["screen-a", "screen-b", "screen-a", "screen-b"]),
            ("extraction/critical_data.csv", audit.CRITICAL_DATA_COLUMNS, "extractor_id", ["extract-a", "extract-b"]),
            ("risk_of_bias/assessments.csv", audit.RISK_OF_BIAS_COLUMNS, "reviewer_id", ["rob-a", "rob-b"]),
        )
        for relative, columns, id_field, identifiers in mappings:
            with (self.project / relative).open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            for row, identifier in zip(rows, identifiers):
                row[id_field] = identifier
            self.write_csv(relative, columns, rows)
        self.assertEqual([], audit.validate_human_gate(self.project))

    def test_claim_ledger_requires_verified_locator_for_each_material_claim(self):
        self.make_common()
        sentence = "Dice increased to 0.85 in 100 patients [@smith2024]."
        body = source_lines(sentence)
        self.write("references.bib", "@article{smith2024,\n title={Example},\n doi={10.1000/example}\n}\n")
        good_row = self.claim_row("Dice increased to 0.85 in 100 patients", "smith2024", "doi:10.1000/example")
        good_row["section"] = "preamble"
        good_row.update({"claim_type": "quantitative", "population_or_dataset": "100 patients", "metric": "Dice", "estimate": "0.85", "unit": "probability", "uncertainty_interval": "not_reported", "direction": "higher"})
        with (self.project / "claim_ledger.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=audit.CLAIM_LEDGER_COLUMNS)
            writer.writeheader()
            writer.writerow(good_row)
        findings, assessed = audit.scan_claim_ledger(body, self.project)
        self.assertTrue(assessed)
        self.assertEqual([], findings)

        good_row.update(
            {"source_locator": "", "verification_status": "draft", "verified_by": ""}
        )
        with (self.project / "claim_ledger.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=audit.CLAIM_LEDGER_COLUMNS)
            writer.writeheader()
            writer.writerow(good_row)
        findings, assessed = audit.scan_claim_ledger(body, self.project)
        self.assertFalse(assessed)
        self.assertEqual("unverified_claim", findings[0].category)
        self.assertEqual("critical", findings[0].severity)

    def test_false_human_rows_are_not_silently_dropped(self):
        self.make_systematic(self.complete_gate())
        with (self.project / "screening/screening_decisions.csv").open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        rows[0]["human_reviewer"] = "false"
        self.write_csv("screening/screening_decisions.csv", audit.SCREENING_COLUMNS, rows)
        findings = audit.validate_human_gate(self.project)
        self.assertEqual(1, len(findings))
        self.assertIn("not a complete human screening decision", findings[0].message)

    def test_screening_unique_records_must_match_flow_counts(self):
        self.make_systematic(self.complete_gate())
        self.write(
            "reporting/flow_counts.json",
            json.dumps({"identified": 3, "deduplicated": 2, "screened": 2, "full_text_assessed": 1, "included": 1}),
        )
        findings = audit.validate_human_gate(self.project)
        self.assertEqual(1, len(findings))
        self.assertIn("do not match flow count", findings[0].message)

    def test_full_text_maybe_or_unclear_is_not_a_completed_decision(self):
        for value in ("maybe", "unclear"):
            with self.subTest(value=value):
                self.make_systematic(self.complete_gate())
                with (self.project / "screening/screening_decisions.csv").open(encoding="utf-8", newline="") as handle:
                    rows = list(csv.DictReader(handle))
                for row in rows:
                    if row["stage"] == "full_text":
                        row["decision"] = value
                self.write_csv("screening/screening_decisions.csv", audit.SCREENING_COLUMNS, rows)
                findings = audit.validate_human_gate(self.project)
                self.assertIn("not a complete human screening decision", findings[0].message)

    def test_title_abstract_resolution_must_be_terminal_and_link_to_full_text(self):
        self.make_systematic(self.complete_gate())
        with (self.project / "screening/screening_decisions.csv").open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        for row in rows:
            if row["stage"] == "title_abstract":
                row["decision"] = "maybe"
        self.write_csv("screening/screening_decisions.csv", audit.SCREENING_COLUMNS, rows)
        message = audit.validate_human_gate(self.project)[0].message
        self.assertIn("screening disagreement", message)

        rows = [row for row in rows if row["stage"] != "full_text"]
        for row in rows:
            row["decision"] = "include"
        self.write_csv("screening/screening_decisions.csv", audit.SCREENING_COLUMNS, rows)
        self.write(
            "reporting/flow_counts.json",
            json.dumps({"identified": 2, "deduplicated": 1, "screened": 1, "full_text_assessed": 0, "included": 0}),
        )
        message = audit.validate_human_gate(self.project)[0].message
        self.assertIn("title/abstract include record IDs", message)

    def test_human_gate_must_be_owned_non_symlink_file(self):
        self.make_systematic(self.complete_gate())
        gate = self.project / "human_review_gate.json"
        outside = Path(self.tempdir.name) / "outside-gate.json"
        outside.write_text(gate.read_text(encoding="utf-8"), encoding="utf-8")
        gate.unlink()
        gate.symlink_to(outside)
        findings = audit.validate_human_gate(self.project)
        self.assertEqual(1, len(findings))
        self.assertIn("symlinked", findings[0].message)

    def test_screening_conflict_resolution_must_be_terminal(self):
        self.make_systematic(self.complete_gate())
        with (self.project / "screening/screening_decisions.csv").open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        for row in rows:
            if row["stage"] == "full_text":
                row["conflict"] = "true"
                row["adjudication_status"] = "complete"
        self.write_csv("screening/screening_decisions.csv", audit.SCREENING_COLUMNS, rows)
        conflict = {column: "" for column in audit.CONFLICT_COLUMNS}
        conflict.update({
            "conflict_id": "screen-1", "artifact": "screening", "record_id": "record-1",
            "reviewer_1_decision": "include", "reviewer_2_decision": "exclude",
            "resolution": "maybe", "adjudicator_id": "human-a", "resolved_at": "2026-07-23",
            "rationale": "full_text disagreement was discussed",
        })
        self.write_csv("adjudication/conflict_log.csv", audit.CONFLICT_COLUMNS, [conflict])
        findings = audit.validate_human_gate(self.project)
        self.assertIn("unresolved", findings[0].message)

    def test_extraction_and_rob_groups_are_entity_scoped(self):
        self.make_systematic(self.complete_gate())
        with (self.project / "extraction/critical_data.csv").open(encoding="utf-8", newline="") as handle:
            critical = list(csv.DictReader(handle))
        critical[1]["study_id"] = "study-2"
        self.write_csv("extraction/critical_data.csv", audit.CRITICAL_DATA_COLUMNS, critical)
        with (self.project / "risk_of_bias/assessments.csv").open(encoding="utf-8", newline="") as handle:
            rob = list(csv.DictReader(handle))
        rob[1]["domain"] = "index_test"
        self.write_csv("risk_of_bias/assessments.csv", audit.RISK_OF_BIAS_COLUMNS, rob)
        message = audit.validate_human_gate(self.project)[0].message
        self.assertIn("study_id=study-1", message)
        self.assertIn("domain=participants", message)
        self.assertIn("maps to multiple", message)

    def test_all_critical_extraction_fields_trigger_disagreement(self):
        for field, value in (
            ("metric", "specificity"),
            ("threshold", "post_hoc"),
            ("comparator", "no comparator"),
            ("dataset_split", "internal_test"),
        ):
            with self.subTest(field=field):
                self.make_systematic(self.complete_gate())
                with (self.project / "extraction/critical_data.csv").open(encoding="utf-8", newline="") as handle:
                    rows = list(csv.DictReader(handle))
                rows[1][field] = value
                self.write_csv("extraction/critical_data.csv", audit.CRITICAL_DATA_COLUMNS, rows)
                self.assertIn(
                    "critical-data disagreement",
                    audit.validate_human_gate(self.project)[0].message,
                )

    def test_duplicate_dedup_rows_cannot_reconcile_flow_counts(self):
        self.make_scoping(populated=True)
        with (self.project / "search/deduplication_log.csv").open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        rows.append(dict(rows[0]))
        self.write_csv("search/deduplication_log.csv", audit.DEDUPLICATION_COLUMNS, rows)
        message = audit.scan_project_readiness("scoping", self.project)[0].message
        self.assertIn("repeats a removed record_id", message)

    def test_duplicate_config_sections_and_contract_keys_are_blocked(self):
        self.make_scoping(populated=True)
        config_path = self.project / "review_config.yaml"
        original = config_path.read_text(encoding="utf-8")
        config_path.write_text(original.replace('  question: "What evidence is available?"', '  question: "What evidence is available?"\n  question: "shadow"'), encoding="utf-8")
        self.assertIn("duplicate", audit.scan_project_readiness("scoping", self.project)[0].message)
        config_path.write_text(original + "\ncoverage:\n  start: shadow\n", encoding="utf-8")
        self.assertIn("duplicate", audit.scan_project_readiness("scoping", self.project)[0].message)

    def test_structured_extraction_and_rob_adjudication_must_agree(self):
        self.make_systematic(self.complete_gate())
        with (self.project / "extraction/critical_data.csv").open(encoding="utf-8", newline="") as handle:
            critical = list(csv.DictReader(handle))
        critical[1]["estimate"] = "0.55"
        for row in critical:
            row["adjudicated_value"] = "0.55"
            row["adjudicator_id"] = "human-a"
            row["decision_status"] = "adjudicated"
        self.write_csv("extraction/critical_data.csv", audit.CRITICAL_DATA_COLUMNS, critical)
        with (self.project / "risk_of_bias/assessments.csv").open(encoding="utf-8", newline="") as handle:
            rob = list(csv.DictReader(handle))
        rob[1]["judgment"] = "high"
        for row in rob:
            row["conflict"] = "true"
            row["adjudication_status"] = "complete"
        self.write_csv("risk_of_bias/assessments.csv", audit.RISK_OF_BIAS_COLUMNS, rob)
        conflicts = []
        for conflict_id, artifact, resolution, group in (
            ("extract-1", "extraction", '{"adjudicated_value":"0.55"}', "extract-1"),
            ("rob-1", "risk_of_bias", '{"final_judgment":"low"}', "rob-1"),
        ):
            row = {column: "" for column in audit.CONFLICT_COLUMNS}
            row.update({
                "conflict_id": conflict_id, "artifact": artifact, "decision_group_id": group,
                "reviewer_1_decision": "first", "reviewer_2_decision": "second",
                "resolution": resolution, "adjudicator_id": "human-a",
                "resolved_at": "2026-07-23", "rationale": "Human adjudication",
            })
            conflicts.append(row)
        self.write_csv("adjudication/conflict_log.csv", audit.CONFLICT_COLUMNS, conflicts)
        self.assertEqual([], audit.validate_human_gate(self.project))

        conflicts[0]["resolution"] = '{"adjudicated_value":"0.80"}'
        conflicts[1]["resolution"] = "N/A"
        self.write_csv("adjudication/conflict_log.csv", audit.CONFLICT_COLUMNS, conflicts)
        message = audit.validate_human_gate(self.project)[0].message
        self.assertIn("agrees with", message)
        self.assertIn("unresolved", message)

    def test_quantitative_candidate_expansion_and_false_positive_guards(self):
        positives = (
            "Mean age was 63.2 years.",
            "n=123.",
            "The difference was 12 mm.",
            "The score was 14.2.",
            "There were 42 lesions.",
        )
        for sentence in positives:
            with self.subTest(sentence=sentence):
                kinds = [candidate.kind for candidate in audit.claim_candidates(source_lines(sentence))]
                self.assertTrue(any("quantitative" in kind for kind in kinds))
        for sentence in ("The study was published in 2024.", "See Section 14.2."):
            with self.subTest(sentence=sentence):
                self.assertEqual([], audit.claim_candidates(source_lines(sentence)))

    def test_directional_candidate_and_alignment_expansion(self):
        examples = (
            ("The rate doubled.", "higher"),
            ("Sensitivity rose.", "higher"),
            ("Specificity fell.", "lower"),
            ("The error was greater.", "higher"),
            ("敏感性上升。", "higher"),
            ("特异性下降。", "lower"),
        )
        self.make_common()
        self.write("references.bib", "@article{smith2024, title={Example}}\n")
        for sentence, direction in examples:
            with self.subTest(sentence=sentence):
                claim_text = sentence.rstrip(".。")
                row = self.claim_row(claim_text, "smith2024", "local:smith")
                row.update({"section": "preamble", "claim_type": "directional", "direction": direction})
                self.write_csv("claim_ledger.csv", audit.CLAIM_LEDGER_COLUMNS, [row])
                findings, assessed = audit.scan_claim_ledger(source_lines(sentence), self.project)
                self.assertEqual([], findings)
                self.assertTrue(assessed)

    def test_atomic_quantitative_spans_require_two_bound_rows(self):
        self.make_common()
        self.write("references.bib", "@article{smith2024, title={Example}}\n")
        sentence = "In 100 patients, Dice=0.85 [@smith2024]."
        population = self.claim_row("In 100 patients", "smith2024", "local:smith")
        population.update({
            "claim_id": "claim-pop", "section": "preamble", "claim_type": "quantitative",
            "population_or_dataset": "100 patients", "metric": "sample_size", "estimate": "100",
            "unit": "patients", "uncertainty_interval": "not_reported",
        })
        dice = self.claim_row("Dice=0.85", "smith2024", "local:smith")
        dice.update({
            "claim_id": "claim-dice", "section": "preamble", "claim_type": "quantitative",
            "metric": "Dice", "estimate": "0.85", "unit": "probability",
            "uncertainty_interval": "not_reported",
        })
        self.write_csv("claim_ledger.csv", audit.CLAIM_LEDGER_COLUMNS, [population, dice])
        findings, assessed = audit.scan_claim_ledger(source_lines(sentence), self.project)
        self.assertEqual([], findings)
        self.assertTrue(assessed)
        self.write_csv("claim_ledger.csv", audit.CLAIM_LEDGER_COLUMNS, [dice])
        findings, assessed = audit.scan_claim_ledger(source_lines(sentence), self.project)
        self.assertFalse(assessed)
        self.assertIn("In 100 patients", findings[0].excerpt)

        for field in (
            "population_or_dataset",
            "data_split",
            "split_unit",
            "metric",
            "unit",
            "uncertainty_interval",
        ):
            with self.subTest(unresolved_field=field):
                broken = dict(dice)
                broken[field] = "not_applicable"
                self.write_csv("claim_ledger.csv", audit.CLAIM_LEDGER_COLUMNS, [population, broken])
                findings, assessed = audit.scan_claim_ledger(source_lines(sentence), self.project)
                self.assertFalse(assessed)
                self.assertTrue(any("unresolved" in finding.message for finding in findings))

    def test_multiple_metrics_are_ambiguous_even_with_one_value_or_direction(self):
        candidates = audit.claim_candidates(
            source_lines("Sensitivity higher, specificity lower [@smith2024].")
        )
        self.assertEqual("ambiguous", candidates[0].kind)
        for sentence in (
            "AUC and Dice were 0.85.",
            "Sensitivity and specificity were higher.",
            "Sensitivity was higher while specificity was lower.",
        ):
            with self.subTest(sentence=sentence):
                ambiguous = audit.claim_candidates(source_lines(sentence))
                self.assertEqual("ambiguous", ambiguous[0].kind)

    def test_unsegmented_multiple_metrics_are_critical(self):
        self.make_common()
        findings, assessed = audit.scan_claim_ledger(
            source_lines("AUC/Dice were 0.85/0.90."), self.project
        )
        self.assertFalse(assessed)
        self.assertEqual("ambiguous_claim_segmentation", findings[0].category)

    def test_regulatory_and_quantitative_claims_require_separate_provenance(self):
        self.make_common()
        self.write(
            "references.bib",
            "@misc{fda, title={FDA record}}\n@article{study, title={Study}}\n",
        )
        regulatory = self.claim_row("FDA cleared Model X", "fda", "official:fda")
        regulatory.update({
            "claim_id": "claim-reg", "section": "preamble", "claim_type": "regulatory",
            "access_level": "official_record", "source_role": "regulator",
            "access_uri": "https://www.fda.gov/example",
        })
        quantitative = self.claim_row("AUC was 0.85", "study", "local:study")
        quantitative.update({
            "claim_id": "claim-auc", "section": "preamble", "claim_type": "quantitative",
            "metric": "AUC", "estimate": "0.85", "unit": "probability",
            "uncertainty_interval": "not_reported",
        })
        self.write_csv("claim_ledger.csv", audit.CLAIM_LEDGER_COLUMNS, [regulatory, quantitative])
        body = source_lines("FDA cleared Model X [@fda]. AUC was 0.85 [@study].")
        findings, assessed = audit.scan_claim_ledger(body, self.project)
        self.assertEqual([], findings)
        self.assertTrue(assessed)
        same_sentence = source_lines(
            "FDA cleared Model X [@fda], and AUC was 0.85 [@study]."
        )
        candidates = audit.claim_candidates(same_sentence)
        self.assertEqual(
            [("regulatory", ("@fda",)), ("quantitative", ("@study",))],
            [(candidate.kind, candidate.citation_ids) for candidate in candidates],
        )
        findings, assessed = audit.scan_claim_ledger(same_sentence, self.project)
        self.assertEqual([], findings)
        self.assertTrue(assessed)
        self.write_csv("claim_ledger.csv", audit.CLAIM_LEDGER_COLUMNS, [regulatory])
        self.assertFalse(audit.scan_claim_ledger(body, self.project)[1])

    def test_regulatory_and_reimbursement_phrase_coverage(self):
        expected = {
            "The device received FDA clearance.": "regulatory",
            "The device obtained 510(k) clearance.": "regulatory",
            "The device was CE marked.": "regulatory",
            "The device received PMA approval.": "regulatory",
            "The service was assigned CPT 75574.": "reimbursement",
            "The examination is covered by Medicare.": "reimbursement",
        }
        for sentence, kind in expected.items():
            with self.subTest(sentence=sentence):
                self.assertIn(
                    kind,
                    [candidate.kind for candidate in audit.claim_candidates(source_lines(sentence))],
                )

    def test_generic_claim_row_cannot_be_reused_across_populations(self):
        self.make_common()
        self.write("references.bib", "@article{smith2024, title={Example}}\n")
        generic = self.claim_row("Performance improved", "smith2024", "local:smith")
        generic.update({"section": "preamble", "claim_type": "directional", "direction": "higher"})
        self.write_csv("claim_ledger.csv", audit.CLAIM_LEDGER_COLUMNS, [generic])
        body = source_lines(
            "Performance improved in adults [@smith2024]. Performance improved in children [@smith2024]."
        )
        findings, assessed = audit.scan_claim_ledger(body, self.project)
        self.assertFalse(assessed)
        self.assertEqual(2, len(findings))

    def test_project_identity_and_route_are_exact(self):
        self.make_scoping(populated=True)
        config = self.config_text("systematic").replace(
            self.project.name, "wrong-20260723-120000-acde1234"
        )
        self.write("review_config.yaml", config)
        findings = audit.scan_project_readiness("scoping", self.project)
        self.assertEqual(1, len(findings))
        self.assertIn("project_id", findings[0].message)
        self.assertIn("route", findings[0].message)

    def test_ai_like_reviewer_and_unresolved_conflict_block_gate(self):
        gate = self.complete_gate()
        gate["reviewer_ids"].append("llm-agent")
        self.make_systematic(gate)
        conflict = {column: "" for column in audit.CONFLICT_COLUMNS}
        conflict.update(
            {
                "conflict_id": "conflict-1",
                "artifact": "screening",
                "record_id": "record-1",
                "reviewer_1_decision": "include",
                "reviewer_2_decision": "exclude",
                "adjudicator_id": "llm-agent",
            }
        )
        self.write_csv("adjudication/conflict_log.csv", audit.CONFLICT_COLUMNS, [conflict])
        findings = audit.validate_human_gate(self.project)
        self.assertEqual(1, len(findings))
        self.assertIn("AI/automation-like", findings[0].message)
        self.assertIn("unresolved or non-human", findings[0].message)

    def test_disagreements_cannot_pass_without_adjudication(self):
        self.make_systematic(self.complete_gate())
        changes = (
            ("screening/screening_decisions.csv", audit.SCREENING_COLUMNS, "decision", "exclude"),
            ("extraction/critical_data.csv", audit.CRITICAL_DATA_COLUMNS, "estimate", "0.55"),
            ("risk_of_bias/assessments.csv", audit.RISK_OF_BIAS_COLUMNS, "judgment", "high"),
        )
        for relative, columns, field, value in changes:
            with (self.project / relative).open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            rows[1][field] = value
            self.write_csv(relative, columns, rows)
        findings = audit.validate_human_gate(self.project)
        self.assertEqual(1, len(findings))
        self.assertIn("screening disagreement", findings[0].message)
        self.assertIn("critical-data disagreement", findings[0].message)
        self.assertIn("risk-of-bias disagreement", findings[0].message)

    def test_resolved_included_ids_must_link_across_artifacts(self):
        self.make_systematic(self.complete_gate())
        with (self.project / "extraction/study_characteristics.csv").open(encoding="utf-8", newline="") as handle:
            studies = list(csv.DictReader(handle))
        studies[0]["report_id"] = "unrelated-record"
        self.write_csv("extraction/study_characteristics.csv", audit.STUDY_CHARACTERISTICS_COLUMNS, studies)
        with (self.project / "extraction/critical_data.csv").open(encoding="utf-8", newline="") as handle:
            critical = list(csv.DictReader(handle))
        for row in critical:
            row["study_id"] = "unrelated-study"
        self.write_csv("extraction/critical_data.csv", audit.CRITICAL_DATA_COLUMNS, critical)
        with (self.project / "risk_of_bias/assessments.csv").open(encoding="utf-8", newline="") as handle:
            rob = list(csv.DictReader(handle))
        for row in rob:
            row["study_id"] = "unrelated-study"
        self.write_csv("risk_of_bias/assessments.csv", audit.RISK_OF_BIAS_COLUMNS, rob)
        findings = audit.scan_project_readiness("systematic", self.project)
        message = " ".join(finding.message for finding in findings)
        self.assertIn("report IDs", message)
        self.assertIn("critical_data.csv", message)
        self.assertIn("risk_of_bias/assessments.csv", message)

    def test_scoping_chart_ids_must_equal_resolved_included_records(self):
        self.make_scoping(populated=True)
        with (self.project / "extraction/charting_table.csv").open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        rows[0]["record_id"] = "unrelated-record"
        self.write_csv("extraction/charting_table.csv", audit.CHARTING_COLUMNS, rows)
        findings = audit.scan_project_readiness("scoping", self.project)
        self.assertIn("charting record IDs", findings[0].message)

    def test_scoping_screening_disagreement_requires_human_adjudication(self):
        self.make_scoping(populated=True)
        with (self.project / "screening/screening_decisions.csv").open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        rows[-1]["decision"] = "exclude"
        self.write_csv("screening/screening_decisions.csv", audit.SCREENING_COLUMNS, rows)
        findings = audit.scan_project_readiness("scoping", self.project)
        self.assertIn("screening conflict", findings[0].message)

    def test_scoping_title_include_cannot_disappear_before_full_text(self):
        self.make_scoping(populated=True)
        with (self.project / "screening/screening_decisions.csv").open(encoding="utf-8", newline="") as handle:
            rows = [
                row for row in csv.DictReader(handle) if row["stage"] == "title_abstract"
            ]
        self.write_csv("screening/screening_decisions.csv", audit.SCREENING_COLUMNS, rows)
        self.write(
            "reporting/flow_counts.json",
            json.dumps({"identified": 2, "deduplicated": 1, "screened": 1, "full_text_assessed": 0, "included": 0}),
        )
        message = audit.scan_project_readiness("scoping", self.project)[0].message
        self.assertIn("title/abstract include record IDs", message)

    def test_full_text_exclude_decisions_cannot_claim_an_included_record(self):
        self.make_systematic(self.complete_gate())
        with (self.project / "screening/screening_decisions.csv").open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        for row in rows:
            if row["stage"] == "full_text":
                row["decision"] = "exclude"
        self.write_csv("screening/screening_decisions.csv", audit.SCREENING_COLUMNS, rows)
        findings = audit.scan_project_readiness("systematic", self.project)
        self.assertTrue(any("include records" in finding.message for finding in findings))

    def test_nested_shadow_route_cannot_override_top_level_route(self):
        self.make_scoping(populated=True)
        config = self.config_text("scoping")
        config = "shadow:\n  route: systematic\n" + config
        self.write("review_config.yaml", config)
        self.assertEqual([], audit.scan_project_readiness("scoping", self.project))

    def test_search_paths_cannot_escape_project(self):
        self.make_scoping(populated=True)
        outside = Path(self.tempdir.name) / "outside.ris"
        outside.write_text("external", encoding="utf-8")
        with (self.project / "search/search_log.csv").open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        rows[0]["export_file"] = "../outside.ris"
        self.write_csv("search/search_log.csv", audit.SEARCH_LOG_COLUMNS, rows)
        findings = audit.scan_project_readiness("scoping", self.project)
        self.assertIn("immutable source export", findings[0].message)

    def test_claim_ledger_requires_exact_header_and_all_cited_sources(self):
        self.make_common()
        self.write(
            "references.bib",
            "@article{one, title={One}}\n@article{two, title={Two}}\n",
        )
        sentence = "A cited synthesis is reported [@one; @two]."
        first = self.claim_row("A cited synthesis is reported", "one", "local:one")
        first["section"] = "preamble"
        self.write_csv("claim_ledger.csv", audit.CLAIM_LEDGER_COLUMNS, [first])
        findings, assessed = audit.scan_claim_ledger(source_lines(sentence), self.project)
        self.assertFalse(assessed)
        self.assertIn("@two", findings[0].message)

        second = self.claim_row("A cited synthesis is reported", "two", "local:two")
        second.update({"claim_id": "claim-2", "section": "preamble"})
        self.write_csv("claim_ledger.csv", audit.CLAIM_LEDGER_COLUMNS, [first, second])
        findings, assessed = audit.scan_claim_ledger(source_lines(sentence), self.project)
        self.assertEqual([], findings)
        self.assertTrue(assessed)

        path = self.project / "claim_ledger.csv"
        path.write_text(
            ",".join((*audit.CLAIM_LEDGER_COLUMNS, "unexpected")) + "\n",
            encoding="utf-8",
        )
        findings, assessed = audit.scan_claim_ledger(source_lines(sentence), self.project)
        self.assertFalse(assessed)
        self.assertIn("exactly match schema 2.0", findings[0].message)

    def test_claim_ledger_rejects_not_applicable_provenance_and_value_drift(self):
        self.make_common()
        self.write("references.bib", "@article{smith2024, title={Example}}\n")
        body = source_lines("Dice increased to 0.85 [@smith2024].")
        row = self.claim_row("Dice increased to 0.85", "smith2024", "local:smith")
        row.update({
            "section": "preamble", "claim_type": "quantitative", "metric": "Dice",
            "estimate": "0.12", "unit": "probability", "uncertainty_interval": "not_reported",
            "direction": "lower", "source_id": "not_applicable", "evidence_excerpt": "not_applicable",
            "access_uri": "not_applicable", "verified_by": "not_applicable",
        })
        self.write_csv("claim_ledger.csv", audit.CLAIM_LEDGER_COLUMNS, [row])
        findings, assessed = audit.scan_claim_ledger(body, self.project)
        self.assertFalse(assessed)
        self.assertIn("cannot be not_applicable", findings[0].message)

        row.update({
            "source_id": "local:smith", "evidence_excerpt": "The source reports Dice 0.85.",
            "access_uri": "opaque:source-smith", "verified_by": "human-a",
        })
        self.write_csv("claim_ledger.csv", audit.CLAIM_LEDGER_COLUMNS, [row])
        findings, assessed = audit.scan_claim_ledger(body, self.project)
        self.assertFalse(assessed)
        self.assertIn("estimate does not appear", findings[0].message)

    def test_no_material_claim_candidates_remains_not_assessed(self):
        self.make_common()
        findings, assessed = audit.scan_claim_ledger(
            source_lines("Background prose without a citation or material assertion."),
            self.project,
        )
        self.assertEqual([], findings)
        self.assertFalse(assessed)

    def test_uncited_regulatory_or_priority_claim_is_a_ledger_candidate(self):
        self.make_common()
        body = source_lines(
            "This was the first commercially available system cleared for clinical use."
        )
        findings, assessed = audit.scan_claim_ledger(body, self.project)
        self.assertFalse(assessed)
        self.assertEqual("unverified_claim", findings[0].category)

    def test_project_working_draft_rejects_numeric_and_inline_bibliography(self):
        self.make_common()
        result = audit.audit_text(
            NARRATIVE.replace("[@garcia2024]", "[1]"),
            file_label="manuscript.md",
            requested_route="narrative",
            project_dir=self.project,
        )
        self.assertIn("mutable_numeric_citation", categories(result))
        self.assertIn("inline_working_bibliography", categories(result))

    def test_working_manuscript_path_must_be_exact_and_non_symlink(self):
        wrong = self.project / "draft.md"
        wrong.write_text("draft", encoding="utf-8")
        findings = audit.validate_working_manuscript_path(self.project, wrong)
        self.assertEqual("not_ready", findings[0].category)

    def test_project_bibtex_resolves_working_citekeys_without_inline_references(self):
        self.make_common()
        self.write(
            "references.bib",
            "@article{garcía2024,\n  title={Verified primary study}\n}\n",
        )
        narrative_claim = self.claim_row("The source defines the method family", "garcía2024", "local:garcia")
        narrative_claim["section"] = "Discussion"
        self.write_csv(
            "claim_ledger.csv",
            audit.CLAIM_LEDGER_COLUMNS,
            [narrative_claim],
        )
        manuscript = """# Narrative Review
## Abstract
This narrative review describes the evidence boundary.
## Methods
Sources were selected using an explicit rationale.
## Discussion
The source defines the method family [@garcía2024].
"""
        result = audit.audit_text(
            manuscript,
            file_label="manuscript.md",
            requested_route="narrative",
            project_dir=self.project,
        )
        self.assertNotIn("missing_reference", categories(result))
        self.assertNotIn("missing_references_section", categories(result))
        self.assertEqual(1, result["reference_count"])


class CliAndSchemaTests(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_default_critical_threshold_fails_and_none_opt_out_does_not(self):
        with tempfile.TemporaryDirectory() as temp:
            manuscript = Path(temp) / "manuscript.md"
            manuscript.write_text("# Review\n[TBD]\n", encoding="utf-8")
            default = self.run_cli(str(manuscript), "--route", "narrative", "--json")
            opted_out = self.run_cli(
                str(manuscript), "--route", "narrative", "--json", "--fail-on", "none"
            )
        self.assertEqual(1, default.returncode)
        self.assertEqual("fail", json.loads(default.stdout)["gate_status"])
        self.assertEqual(0, opted_out.returncode)
        self.assertEqual("warning", json.loads(opted_out.stdout)["gate_status"])

    def test_json_schema_is_stable_and_never_reports_pass(self):
        result = audit.audit_text(NARRATIVE, file_label="clean.md", requested_route="narrative")
        self.assertEqual(
            {"critical", "high", "medium", "low"}, set(result["summary"])
        )
        self.assertIn(result["gate_status"], {"fail", "warning", "not_assessed"})
        self.assertNotIn(result["gate_status"], {"pass", "passed", "compliant"})
        self.assertTrue(result["not_assessed_checks"])

    def test_json_and_output_are_mutually_exclusive(self):
        with tempfile.TemporaryDirectory() as temp:
            manuscript = Path(temp) / "manuscript.md"
            manuscript.write_text(NARRATIVE, encoding="utf-8")
            result = self.run_cli(
                str(manuscript), "--json", "--output", str(Path(temp) / "report.md")
            )
        self.assertEqual(2, result.returncode)
        self.assertIn("mutually exclusive", result.stderr)

    def test_missing_file_error_is_friendly(self):
        result = self.run_cli("/tmp/audit-manuscript-file-that-does-not-exist.md", "--json")
        self.assertEqual(2, result.returncode)
        self.assertIn("error: cannot read manuscript", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_profile_json_is_applied_through_cli(self):
        with tempfile.TemporaryDirectory() as temp:
            manuscript = Path(temp) / "manuscript.md"
            profile = Path(temp) / "profile.json"
            manuscript.write_text(
                NARRATIVE.replace("## Key Points\n", "## Optional Points\n"),
                encoding="utf-8",
            )
            profile.write_text(
                json.dumps(
                    {
                        "schema_version": "2.0",
                        "checks": {
                            "key_points": {
                                "expected": "optional",
                                "severity": "warning",
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            result = self.run_cli(
                str(manuscript),
                "--route",
                "narrative",
                "--profile",
                str(profile),
                "--json",
            )
        self.assertEqual(0, result.returncode)
        self.assertNotIn("missing_key_points", categories(json.loads(result.stdout)))

    def test_flat_or_legacy_audit_profile_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            profile = Path(temp) / "profile.json"
            profile.write_text(
                json.dumps({"schema_version": "2.0", "audit": {"require_references": False}}),
                encoding="utf-8",
            )
            with self.assertRaises(audit.AuditInputError):
                audit.load_profile(profile)

    def test_structural_reference_checks_cannot_be_disabled_by_override(self):
        result = audit.audit_text(
            "# Review\n\n## Abstract\nSubstantive abstract.\n\n## Methods\nA method is described.\n",
            file_label="no-references.md",
            requested_route="narrative",
            profile_overrides={"require_references": False},
        )
        self.assertIn("missing_references_section", categories(result))
        self.assertEqual("fail", result["gate_status"])

    def test_project_output_must_stay_inside_review_outputs(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "example-20260723-120000-acde1234"
            project.mkdir()
            manuscript = project / "manuscript.md"
            manuscript.write_text(NARRATIVE, encoding="utf-8")
            outside = Path(temp) / "outside.md"
            result = self.run_cli(
                str(manuscript),
                "--route",
                "narrative",
                "--project-dir",
                str(project),
                "--output",
                str(outside),
            )
        self.assertEqual(2, result.returncode)
        self.assertIn("review_outputs", result.stderr)

    def test_project_output_dotdot_cannot_escape_review_outputs(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "example-20260723-120000-acde1234"
            project.mkdir()
            manuscript = project / "manuscript.md"
            manuscript.write_text(NARRATIVE, encoding="utf-8")
            escaped = project / "review_outputs" / ".." / ".." / "escaped.md"
            result = self.run_cli(
                str(manuscript), "--route", "narrative", "--project-dir", str(project),
                "--output", str(escaped),
            )
            self.assertFalse((Path(temp) / "escaped.md").exists())
        self.assertEqual(2, result.returncode)
        self.assertIn("review_outputs", result.stderr)

    def test_profile_warnings_never_trip_fail_threshold(self):
        result = audit.audit_text(
            NARRATIVE.replace("## Methods", "## 1. Methods"),
            file_label="style.md",
            requested_route="narrative",
            profile_overrides={
                "allow_numbered_headings": False,
                "_specified_style_checks": ["heading_numbering"],
            },
            fail_on="low",
        )
        numbered = [f for f in result["findings"] if f["category"] == "numbered_heading"]
        self.assertEqual(1, len(numbered))
        self.assertFalse(numbered[0]["gate_relevant"])
        self.assertNotEqual("fail", result["gate_status"])

    def test_no_profile_marks_every_style_check_not_assessed(self):
        result = audit.audit_text(NARRATIVE, file_label="plain.md", requested_route="narrative")
        self.assertIn("style.heading_numbering", result["not_assessed_checks"])
        self.assertIn("style.vendor_placement", result["not_assessed_checks"])


if __name__ == "__main__":
    unittest.main()
