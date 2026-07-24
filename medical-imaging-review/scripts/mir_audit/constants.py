"""Static data tables, severity ranks, project-file sets, and compiled regexes.

Part of the mir_audit package (split from the original audit_manuscript.py).
"""

from __future__ import annotations

import csv
import json
import re


SCHEMA_VERSION = "2.0"


SUPPORTED_ROUTES = ("auto", "narrative", "method-survey", "scoping", "systematic")


SEVERITIES = ("critical", "high", "medium", "low")


SEVERITY_RANK = {"critical": 4, "high": 3, "medium": 2, "low": 1}


REFERENCE_TITLES = {
    "reference",
    "references",
    "bibliography",
    "参考文献",
    "文献",
}


BASE_NOT_ASSESSED = {
    "source_existence_resolution",
    "doi_and_registry_resolution",
    "full_author_and_metadata_verification",
    "author_attribution_alignment",
    "quantitative_claim_source_agreement",
    "directional_claim_source_agreement",
    "peer_review_and_source_type_verification",
    "search_strategy_recall_and_completeness",
    "search_export_completeness_and_record_counts",
    "human_identity_and_independence",
    "risk_of_bias_judgment_validity",
    "risk_of_bias_domain_completeness",
    "certainty_judgment_validity",
    "prisma_reporting_completeness",
}


COMMON_PROJECT_FILES = (
    ("review_config.yaml",),
    ("REVIEW_CONTEXT.md",),
    ("IMPLEMENTATION_PLAN.md",),
    ("PARADIGM.md",),
    ("claim_ledger.csv",),
    ("references.bib",),
    ("AI_USE_DISCLOSURE.md",),
    ("protocol_deviations.md",),
    ("EXPERT_SIGNOFF.md",),
)


NARRATIVE_PROJECT_FILES = (
    ("search/narrative_exploration_log.csv",),
    ("search/selection_rationale.md",),
)


SCOPING_PROJECT_FILES = (
    ("protocol/PROTOCOL.md",),
    ("search/search_plan.md",),
    ("search/search_log.csv",),
    ("search/deduplication_log.csv",),
    ("screening/screening_decisions.csv",),
    ("screening/full_text_exclusions.csv",),
    ("screening/calibration_log.md",),
    ("extraction/charting_table.csv",),
    ("adjudication/conflict_log.csv",),
    ("reporting/flow_counts.json",),
    ("reporting/PRISMA_ScR_checklist.md",),
)


SYSTEMATIC_PROJECT_FILES = (
    ("protocol/PROTOCOL.md",),
    ("search/search_plan.md",),
    ("search/search_log.csv",),
    ("search/deduplication_log.csv",),
    ("screening/screening_decisions.csv",),
    ("screening/full_text_exclusions.csv",),
    ("screening/calibration_log.md",),
    ("extraction/study_characteristics.csv",),
    ("extraction/critical_data.csv",),
    ("extraction/cohort_linkage.csv",),
    ("risk_of_bias/assessments.csv",),
    ("risk_of_bias/decision_rules.md",),
    ("certainty/assessments.csv",),
    ("adjudication/conflict_log.csv",),
    ("reporting/flow_counts.json",),
    ("reporting/PRISMA_2020_checklist.md",),
)


HUMAN_GATE_CHECKS = (
    "title_abstract_screening",
    "full_text_screening",
    "critical_data_extraction",
    "risk_of_bias",
    "certainty_approval",
    "conflicts_adjudicated",
    "ai_assistance_disclosed",
)


EXPECTED_GATE_EVIDENCE = {
    "title_abstract_screening": "screening/screening_decisions.csv",
    "full_text_screening": "screening/screening_decisions.csv",
    "critical_data_extraction": "extraction/critical_data.csv",
    "risk_of_bias": "risk_of_bias/assessments.csv",
    "certainty_approval": "certainty/assessments.csv",
    "conflicts": "adjudication/conflict_log.csv",
    "ai_disclosure": "AI_USE_DISCLOSURE.md",
}


CLAIM_LEDGER_COLUMNS = (
    "claim_id",
    "section",
    "claim_text",
    "claim_type",
    "citekey",
    "source_id",
    "source_locator",
    "evidence_excerpt",
    "population_or_dataset",
    "data_split",
    "split_unit",
    "comparator",
    "metric",
    "estimate",
    "unit",
    "uncertainty_interval",
    "direction",
    "access_level",
    "source_role",
    "access_uri",
    "accessed_at",
    "verification_status",
    "verified_by",
    "verified_at",
    "notes",
)


CLAIM_TYPES = {
    "factual",
    "quantitative",
    "comparative",
    "directional",
    "priority",
    "regulatory",
    "reimbursement",
    "availability",
    "synthesis",
}


ACCESS_LEVELS = {
    "full_text",
    "abstract_only",
    "metadata_only",
    "official_record",
    "registry",
    "inaccessible",
}


SOURCE_ROLES = {
    "primary_study",
    "secondary_review",
    "preprint",
    "protocol",
    "conduct_guideline",
    "reporting_guideline",
    "primary_study_reporting_guideline",
    "risk_of_bias_tool",
    "certainty_guidance",
    "registry",
    "regulator",
    "payer_or_coding_authority",
    "dataset_owner",
    "vendor_documentation",
    "software_or_code",
    "correction_or_retraction_notice",
    "other",
}


SCREENING_COLUMNS = (
    "record_id",
    "stage",
    "reviewer_id",
    "human_reviewer",
    "decision",
    "exclusion_reason",
    "conflict",
    "adjudication_status",
    "decided_at",
)


CRITICAL_DATA_COLUMNS = (
    "study_id",
    "outcome_id",
    "decision_group_id",
    "citekey",
    "dataset_or_cohort",
    "dataset_split",
    "split_unit",
    "subgroup",
    "threshold",
    "comparator",
    "metric",
    "time_point",
    "estimate",
    "unit",
    "uncertainty_interval",
    "numerator",
    "denominator",
    "source_locator",
    "extractor_id",
    "human_reviewer",
    "decision_status",
    "adjudicated_value",
    "adjudicator_id",
    "notes",
)


RISK_OF_BIAS_COLUMNS = (
    "study_id",
    "decision_group_id",
    "tool",
    "tool_version",
    "domain",
    "reviewer_id",
    "human_reviewer",
    "judgment",
    "source_locator",
    "rationale",
    "conflict",
    "adjudication_status",
)


CERTAINTY_COLUMNS = (
    "outcome_id",
    "framework",
    "risk_of_bias",
    "inconsistency",
    "indirectness",
    "imprecision",
    "publication_bias",
    "other",
    "certainty",
    "reviewer_id",
    "human_reviewer",
    "approval_status",
    "rationale",
)


CONFLICT_COLUMNS = (
    "conflict_id",
    "artifact",
    "record_id",
    "decision_group_id",
    "reviewer_1_decision",
    "reviewer_2_decision",
    "resolution",
    "adjudicator_id",
    "resolved_at",
    "rationale",
)


SEARCH_LOG_COLUMNS = (
    "source",
    "platform",
    "coverage",
    "search_date",
    "strategy_file",
    "filters",
    "result_count",
    "export_file",
    "searcher_id",
    "notes",
)


DEDUPLICATION_COLUMNS = (
    "record_id",
    "duplicate_group",
    "decision",
    "rule",
    "reviewer_id",
    "decided_at",
)


CHARTING_COLUMNS = (
    "record_id",
    "citekey",
    "population",
    "concept",
    "context",
    "study_design",
    "modality",
    "task",
    "data_items",
    "charter_id",
    "independent_verifier_id",
    "verification_status",
    "notes",
)


STUDY_CHARACTERISTICS_COLUMNS = (
    "study_id",
    "report_id",
    "citekey",
    "study_design",
    "population",
    "modality",
    "task",
    "dataset_or_cohort",
    "split_method",
    "split_unit",
    "reference_standard",
    "external_validation",
    "extractor_id",
    "verification_status",
    "notes",
)


FULL_TEXT_EXCLUSION_COLUMNS = (
    "record_id",
    "citekey",
    "exclusion_reason",
    "reviewer_id",
    "adjudication_status",
)


COHORT_LINKAGE_COLUMNS = (
    "cohort_id",
    "dataset_name",
    "study_id",
    "report_id",
    "site",
    "date_range",
    "participant_overlap_status",
    "shared_test_set_status",
    "linkage_evidence",
    "decision_for_synthesis",
    "reviewer_id",
    "notes",
)


NARRATIVE_EXPLORATION_COLUMNS = (
    "source",
    "query_or_navigation",
    "searched_at",
    "result_reference",
    "decision",
    "rationale",
)


HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$")


FENCE_RE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")


INLINE_CODE_RE = re.compile(r"`+[^`\n]*`+")


BRACKET_RE = re.compile(r"[\[［【]([^\]］】\n]+)[\]］】]")


PAREN_NUMERIC_CITATION_RE = re.compile(
    r"(?<![\w])\((\d{1,3}(?:\s*(?:[,;，；]|[-–—])\s*\d{1,3})*)\)"
)


REF_ENTRY_RE = re.compile(
    r"^\s*(?:[-*+]\s+)?(?:[\[［【](?P<bracket_num>\d+)[\]］】]|"
    r"(?P<plain_num>\d+)[.)]|[\[［【](?P<citekey>@[^\]］】\s]+)[\]］】])"
    r"\s*:?[ \t]*(?P<entry>.*?)\s*$"
)


DOI_RE = re.compile(r"\b10\.\d{4,9}/[^\s<>\"\]]+", flags=re.I)


DOI_CANDIDATE_RE = re.compile(
    r"(?:https?://(?:dx\.)?doi\.org/|doi\s*:\s*)?"
    r"10\.[A-Za-z0-9_.-]+/[^\s<>\"\]]+",
    flags=re.I,
)


PLACEHOLDER_RE = re.compile(
    r"\bxxx\b|\[\s*tbd\s*\]|\bto[-\s]+be[-\s]+filled\b|"
    r"\bto\s+be\s+(?:added|declared)\b|"
    r"\[?\s*figure\s+placeholder\s*\]?",
    flags=re.I,
)


BOX_TITLE_RE = re.compile(r"^(?:box|框)\s*\d+\b", flags=re.I)


BOLD_BOX_RE = re.compile(r"^\s*\*\*\s*(?:box|框)\s*\d+\b.*\*\*\s*$", flags=re.I)


SCOPING_METHOD_ELEMENTS = {
    "protocol": (r"protocol|registration|方案|注册",),
    "eligibility": (r"eligibility|inclusion|exclusion|纳入|排除|资格",),
    "information_sources_search": (r"information sources|search strategy|检索|信息来源",),
    "selection": (r"selection|screening|筛选|文献选择",),
    "charting": (r"charting|data chart|资料整理|数据整理|数据提取",),
    "synthesis": (r"synthesis|analysis|综合|证据图谱",),
}


SYSTEMATIC_METHOD_ELEMENTS = {
    "protocol_registration": (r"protocol|registration|方案|注册",),
    "eligibility": (r"eligibility|inclusion|exclusion|纳入|排除|资格",),
    "information_sources_search": (r"information sources|search strategy|检索|信息来源",),
    "selection": (r"selection|screening|筛选|文献选择",),
    "data_collection_items": (r"data collection|data items|extraction|数据收集|数据提取",),
    "risk_of_bias": (r"risk of bias|quality assessment|偏倚风险|质量评价",),
    "synthesis": (r"synthesis|analysis|综合",),
}


NON_VALUE_TOKENS = {
    "",
    "-",
    "[]",
    "{}",
    "n/a",
    "na",
    "none",
    "not_applicable",
    "not applicable",
    "not_reported",
    "unknown",
    "unclear",
    "maybe",
    "pending",
    "null",
    "tbd",
    "todo",
    "placeholder",
}


CONTRACT_CONFIG_SECTIONS = {
    "review",
    "coverage",
    "delivery",
    "methods",
    "ai_assistance",
    "schemas",
    "citations",
    "human_review",
}


DIRECTIONAL_RE = re.compile(
    r"\b(?:higher|lower|increas(?:ed|es|ing)|decreas(?:ed|es|ing)|improv(?:ed|es|ing)|"
    r"reduc(?:ed|es|ing)|better|worse|outperform(?:ed|s|ing)?|superior|inferior|associated)\b|"
    r"\b(?:doubled|halved|rose|risen|fell|fallen|greater|lesser|more|fewer)\b|"
    r"更高|更低|增加|降低|改善|提高|减少|优于|劣于|相关|上升|下降|升高|减小|翻倍|减半",
    flags=re.I,
)


QUANTITATIVE_RE = re.compile(
    r"\b\d+(?:\.\d+)?\s*%|\b0\.\d+\b|"
    r"\b(?:dice|auc|accuracy|sensitivity|specificity|hazard ratio|odds ratio|hr|or|p)\s*(?:=|:|of|was|is)?\s*\d|"
    r"\bmean\s+age\s+(?:was|is|=|:)\s*\d+(?:\.\d+)?\s*years?\b|"
    r"\bn\s*=\s*\d+\b|"
    r"\b(?:difference|score)\s+(?:was|is|=|:)\s*\d+(?:\.\d+)?(?:\s*(?:mm|cm|points?))?\b|"
    r"\b\d+(?:\.\d+)?\s*(?:patients?|participants?|cases?|studies|images?|scans?|lesions?)\b|"
    r"\d+(?:\.\d+)?\s*(?:例|名患者|项研究|幅图像|个病灶|处病灶)",
    flags=re.I,
)


MATERIAL_CUE_RE = re.compile(
    r"\b(?:first|earliest|novel|state[-\s]of[-\s]the[-\s]art|approved|approval|cleared|clearance|"
    r"authorized|available|commercial(?:ly)?|reimburs(?:ed|ement)|coverage|covered|"
    r"CE[-\s]?marked|PMA|510\s*\(k\)|CPT|Medicare|"
    r"compared\s+with|versus|vs\.?|more\s+than|less\s+than)\b|"
    r"首次|最早|首个|新颖|领先|批准|许可|获批|上市|可用|商业化|报销|支付|覆盖|相比|比较",
    flags=re.I,
)


PRIORITY_CUE_RE = re.compile(
    r"\b(?:first|earliest|novel|state[-\s]of[-\s]the[-\s]art)\b|首次|最早|首个|新颖|领先",
    flags=re.I,
)


REGULATORY_CUE_RE = re.compile(
    r"\b(?:approved|approval|cleared|clearance|authorized|CE[-\s]?marked|PMA|510\s*\(k\))\b|批准|许可|获批|取得认证",
    flags=re.I,
)


REIMBURSEMENT_CUE_RE = re.compile(
    r"\b(?:reimburs(?:ed|ement)|coverage|covered|billing|coding|CPT|Medicare)\b|报销|支付|医保|编码",
    flags=re.I,
)


AVAILABILITY_CUE_RE = re.compile(
    r"\b(?:available|commercial(?:ly)?|marketed)\b|上市|可用|商业化",
    flags=re.I,
)


COMPARATIVE_CUE_RE = re.compile(
    r"\b(?:compared\s+with|versus|vs\.?|more\s+than|less\s+than)\b|相比|比较|优于|劣于",
    flags=re.I,
)
