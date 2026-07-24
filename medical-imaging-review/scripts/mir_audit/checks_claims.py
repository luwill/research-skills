"""Claim-candidate extraction and claim-ledger reconciliation checks.

Part of the mir_audit package (split from the original audit_manuscript.py).
"""

from __future__ import annotations

import csv
import os
import re

from pathlib import Path

from .constants import *  # noqa: F401,F403
from .model import *  # noqa: F401,F403
from .parsing import *  # noqa: F401,F403
from .projectio import *  # noqa: F401,F403


def claim_candidates(body_lines: list[SourceLine]) -> list[ClaimCandidate]:
    candidates: list[ClaimCandidate] = []
    section = "preamble"
    for source in body_lines:
        heading = parse_heading(source.text)
        if heading:
            section = strip_heading_number(heading[1])
            continue
        if not source.text.strip():
            continue
        visible = INLINE_CODE_RE.sub("", source.text)
        for sentence in re.split(
            r"(?<=[。！？])\s*|(?<=[.!?])(?=\s+|$)\s*", visible
        ):
            sentence = sentence.strip()
            if not sentence:
                continue
            parsed_citations, _ = parse_citations([SourceLine(source.number, sentence)])
            citation_ids = tuple(dict.fromkeys(citation.identifier for citation in parsed_citations))
            prose = PAREN_NUMERIC_CITATION_RE.sub(
                "", BRACKET_RE.sub("", sentence)
            ).strip(" ,;，；.!?。！？")
            sentence_metrics = set(
                re.findall(
                    r"\b(?:dice|auc|accuracy|sensitivity|specificity|difference|score|mean\s+age)\b",
                    prose,
                    flags=re.I,
                )
            )
            if len(sentence_metrics) >= 2:
                candidates.append(
                    ClaimCandidate(source.number, prose, "ambiguous", section, citation_ids)
                )
                continue

            protected_spans = [match.span() for match in BRACKET_RE.finditer(sentence)]
            protected_spans.extend(
                match.span() for match in PAREN_NUMERIC_CITATION_RE.finditer(sentence)
            )
            delimiter_re = re.compile(
                r"(?:[,;，；]\s*(?:(?:and|but|whereas)\b\s*)?|\s+\b(?:and|but|whereas)\b\s+)",
                flags=re.I,
            )
            raw_clauses: list[str] = []
            cursor = 0
            for delimiter in delimiter_re.finditer(sentence):
                if any(start <= delimiter.start() < end for start, end in protected_spans):
                    continue
                clause = sentence[cursor : delimiter.start()].strip(" ,;，；.!?。！？")
                if clause:
                    raw_clauses.append(clause)
                cursor = delimiter.end()
            final_clause = sentence[cursor:].strip(" ,;，；.!?。！？")
            if final_clause:
                raw_clauses.append(final_clause)

            def signalled(fragment: str) -> bool:
                return bool(
                    QUANTITATIVE_RE.search(fragment)
                    or DIRECTIONAL_RE.search(fragment)
                    or MATERIAL_CUE_RE.search(fragment)
                )

            clause_candidates: list[tuple[str, tuple[str, ...]]] = []
            for raw_clause in raw_clauses:
                clause_citations, _ = parse_citations(
                    [SourceLine(source.number, raw_clause)]
                )
                local_ids = tuple(
                    dict.fromkeys(citation.identifier for citation in clause_citations)
                )
                clause_prose = PAREN_NUMERIC_CITATION_RE.sub(
                    "", BRACKET_RE.sub("", raw_clause)
                ).strip(" ,;，；.!?。！？")
                if clause_prose and signalled(clause_prose):
                    clause_candidates.append(
                        (clause_prose, local_ids or citation_ids)
                    )
            spans = (
                clause_candidates
                if len(clause_candidates) >= 2
                else [(prose, citation_ids)]
            )
            for span, span_citation_ids in spans:
                quantitative = bool(QUANTITATIVE_RE.search(span))
                directional = bool(DIRECTIONAL_RE.search(span))
                higher = bool(
                    re.search(
                        r"\b(?:higher|increas\w*|rose|risen|greater|more|doubled)\b|更高|增加|提高|上升|升高|翻倍",
                        span,
                        flags=re.I,
                    )
                )
                lower = bool(
                    re.search(
                        r"\b(?:lower|decreas\w*|fell|fallen|lesser|fewer|halved)\b|更低|降低|减少|下降|减小|减半",
                        span,
                        flags=re.I,
                    )
                )
                if higher and lower:
                    candidates.append(
                        ClaimCandidate(source.number, span, "ambiguous", section, span_citation_ids)
                    )
                    continue
                material_kinds = [
                    name
                    for name, pattern in (
                        ("priority", PRIORITY_CUE_RE),
                        ("regulatory", REGULATORY_CUE_RE),
                        ("reimbursement", REIMBURSEMENT_CUE_RE),
                        ("availability", AVAILABILITY_CUE_RE),
                        ("comparative", COMPARATIVE_CUE_RE),
                    )
                    if pattern.search(span)
                ]
                kinds: list[str] = []
                if quantitative:
                    kinds.append("quantitative_and_directional" if directional else "quantitative")
                elif directional:
                    kinds.append("directional")
                for material_kind in material_kinds:
                    if material_kind == "comparative" and directional:
                        kinds.append("comparative_and_directional")
                    else:
                        kinds.append(material_kind)
                if not kinds and citation_ids:
                    kinds.append("factual")
                for kind in dict.fromkeys(kinds):
                    candidates.append(
                        ClaimCandidate(source.number, span, kind, section, span_citation_ids)
                    )
    return candidates


def scan_claim_ledger(
    body_lines: list[SourceLine],
    project_dir: Path | None,
    references: ReferenceSet | None = None,
) -> tuple[list[Finding], bool]:
    claims = claim_candidates(body_lines)
    if project_dir is None:
        return [], False
    path = project_dir / "claim_ledger.csv"
    if not path.is_file():
        return [Finding("critical", "not_ready", 0, "claim_ledger.csv is required for material claims.")], False
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
            fieldnames = tuple(reader.fieldnames or [])
    except (OSError, UnicodeError, csv.Error) as exc:
        return [Finding("critical", "not_ready", 0, f"claim_ledger.csv is unreadable: {exc}")], False
    if fieldnames != CLAIM_LEDGER_COLUMNS:
        return [
            Finding(
                "critical",
                "not_ready",
                0,
                "claim_ledger.csv header must exactly match schema 2.0 in the documented order.",
            )
        ], False
    if not claims:
        return [], False
    references = references or parse_project_bibliography(project_dir)
    indexed = [(normalize_claim(row.get("claim_text", "")), row) for row in rows]
    findings: list[Finding] = []

    def real_value(row: dict[str, str], field: str) -> bool:
        value = str(row.get(field, "")).strip()
        return bool(value) and value.casefold() not in {"unknown", "tbd", "pending", "-"}

    def complete_row(
        row: dict[str, str],
        required_citekey: str | None,
        claim: ClaimCandidate,
        expected_claim_type: str | None = None,
    ) -> tuple[bool, str]:
        required_fields = (
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
        )
        missing = [field for field in required_fields if not real_value(row, field)]
        if missing:
            return False, f"missing or unresolved fields {missing}"
        for field in (
            "claim_id",
            "section",
            "claim_text",
            "claim_type",
            "citekey",
            "source_id",
            "source_locator",
            "evidence_excerpt",
            "access_uri",
            "accessed_at",
            "verified_by",
            "verified_at",
        ):
            if str(row.get(field, "")).strip().casefold() in {
                "n/a",
                "na",
                "none",
                "not_applicable",
                "not_reported",
                "inaccessible",
            }:
                return False, f"{field} cannot be not_applicable for a verified claim"
        claim_type = str(row.get("claim_type", "")).strip().casefold()
        access_level = str(row.get("access_level", "")).strip().casefold()
        source_role = str(row.get("source_role", "")).strip().casefold()
        if claim_type not in CLAIM_TYPES:
            return False, "claim_type is outside the schema 2.0 enum"
        if expected_claim_type and claim_type != expected_claim_type:
            return False, f"claim_type does not cover the detected {expected_claim_type} claim"
        if access_level not in ACCESS_LEVELS:
            return False, "access_level is outside the schema 2.0 enum"
        if access_level == "inaccessible":
            return False, "an inaccessible source cannot support a verified claim"
        if source_role not in SOURCE_ROLES:
            return False, "source_role is outside the schema 2.0 enum"
        if str(row.get("section", "")).strip().casefold() != claim.section.casefold():
            return False, f"section does not match manuscript section {claim.section}"
        if "quantitative" in claim.kind and claim_type != "quantitative":
            return False, "quantitative prose is not typed as an atomic quantitative claim"
        if "directional" in claim.kind and str(row.get("direction", "")).strip().casefold() in {
            "not_applicable",
            "not_reported",
        }:
            return False, "directional prose lacks a verified direction"
        prose = PAREN_NUMERIC_CITATION_RE.sub("", BRACKET_RE.sub("", claim.text)).casefold()
        if "quantitative" in claim.kind:
            for field in (
                "population_or_dataset",
                "data_split",
                "split_unit",
                "metric",
                "estimate",
                "unit",
            ):
                if not is_resolved_value(row.get(field, "")):
                    return False, f"quantitative claim has unresolved {field}"
            uncertainty_value = str(row.get("uncertainty_interval", "")).strip()
            if not is_resolved_value(uncertainty_value) and uncertainty_value.casefold() != "not_reported":
                return False, "quantitative claim has unresolved uncertainty_interval"
            estimate = str(row.get("estimate", "")).strip()
            estimate_tokens = re.findall(r"\d+(?:\.\d+)?", estimate)
            prose_tokens = re.findall(r"\d+(?:\.\d+)?", prose)
            if not estimate_tokens or not all(token in prose_tokens for token in estimate_tokens):
                return False, "ledger estimate does not appear in the manuscript claim"
            metric = normalize_claim(str(row.get("metric", "")))
            named_metrics = re.findall(
                r"\b(?:dice|auc|accuracy|sensitivity|specificity|difference|score|mean\s+age)\b",
                prose,
                flags=re.I,
            )
            population_count = re.search(
                r"\b(?:n\s*=\s*)?(\d+)\s*(patients?|participants?|cases?|lesions?)?\b|"
                r"(\d+)\s*(?:例|名患者|个病灶|处病灶)",
                prose,
                flags=re.I,
            )
            if named_metrics:
                expected_metric = normalize_claim(named_metrics[0])
                if expected_metric not in metric and metric not in expected_metric:
                    return False, "ledger metric does not agree with the manuscript claim"
            elif population_count and not any(
                token in metric
                for token in (
                    "sample",
                    "size",
                    "patient",
                    "participant",
                    "case",
                    "lesion",
                    "count",
                    "n",
                )
            ):
                return False, "population-count claim requires an explicit sample/count metric"
            stated_population = re.search(
                r"\b(\d+)\s*(patients?|participants?|cases?|lesions?)\b|"
                r"(\d+)\s*(?:例|名患者|个病灶|处病灶)",
                prose,
                flags=re.I,
            )
            if stated_population:
                population_number = stated_population.group(1) or stated_population.group(3)
                if population_number not in str(row.get("population_or_dataset", "")):
                    return False, "ledger population_or_dataset omits the stated population count"
            population_terms = re.findall(
                r"\b(?:adults?|children|pediatric|paediatric|infants?|women|men)\b|成人|儿童|儿科|婴儿|女性|男性",
                prose,
                flags=re.I,
            )
            population_value = normalize_claim(str(row.get("population_or_dataset", "")))
            if population_terms and not all(
                normalize_claim(term) in population_value for term in population_terms
            ):
                return False, "ledger population_or_dataset does not agree with the manuscript context"
            split_terms = re.findall(
                r"\b(?:external|internal|training|train|validation|test|holdout)\b|外部|内部|训练|验证|测试",
                prose,
                flags=re.I,
            )
            split_value = normalize_claim(str(row.get("data_split", "")))
            if split_terms and not any(
                normalize_claim(term) in split_value for term in split_terms
            ):
                return False, "ledger data_split does not agree with the manuscript context"
            unit = normalize_claim(str(row.get("unit", "")))
            unit_pattern = (
                r"\b(years?|mm|cm|points?)\b|岁|毫米|厘米|分"
                if named_metrics
                else r"\b(patients?|participants?|cases?|lesions?)\b|例|名患者|个病灶|处病灶"
            )
            explicit_unit = re.search(unit_pattern, prose, flags=re.I)
            if explicit_unit and normalize_claim(explicit_unit.group(0)) not in unit:
                return False, "ledger unit does not agree with the manuscript claim"
            interval = str(row.get("uncertainty_interval", "")).strip()
            if re.search(r"\b(?:CI|confidence\s+interval)\b|置信区间", prose, flags=re.I):
                interval_tokens = re.findall(r"\d+(?:\.\d+)?", interval)
                if not interval_tokens or not all(token in prose_tokens for token in interval_tokens):
                    return False, "ledger uncertainty_interval does not agree with the manuscript claim"
        if "directional" in claim.kind:
            direction = str(row.get("direction", "")).strip().casefold()
            direction_patterns = {
                "higher": r"higher|increase|increased|improved|better|outperform|superior|doubled|rose|risen|greater|more|更高|增加|提高|改善|优于|上升|升高|翻倍",
                "lower": r"lower|decrease|decreased|reduced|worse|inferior|halved|fell|fallen|lesser|fewer|更低|降低|减少|劣于|下降|减小|减半",
                "no_clear_difference": r"no\s+(?:clear|significant)?\s*difference|similar|comparable|无明确差异|无显著差异|相近",
                "mixed": r"mixed|inconsistent|异质|不一致|混合",
            }
            pattern = direction_patterns.get(direction)
            if pattern is None or not re.search(pattern, prose, flags=re.I):
                return False, "ledger direction does not agree with the manuscript wording"
        if access_level == "abstract_only" and claim_type in {
            "quantitative",
            "comparative",
            "directional",
            "priority",
            "regulatory",
            "reimbursement",
        }:
            return False, "abstract_only access cannot verify this claim type"
        if claim_type == "regulatory" and not (
            access_level == "official_record" and source_role == "regulator"
        ):
            return False, "regulatory claims require an official regulator record"
        if claim_type == "reimbursement" and not (
            access_level == "official_record"
            and source_role == "payer_or_coding_authority"
        ):
            return False, "reimbursement claims require an official payer/coding record"
        locator = str(row.get("source_locator", "")).strip()
        if locator.casefold() in {"n/a", "na", "none", "not_applicable"} or "?" in locator or PLACEHOLDER_RE.search(locator):
            return False, "source_locator is not a re-findable source location"
        if str(row.get("verification_status", "")).strip().casefold() != "verified":
            return False, "verification_status is not verified"
        verifier = str(row.get("verified_by", "")).strip()
        if ai_like_reviewer_id(verifier):
            return False, "verified_by is AI/automation-like"
        row_key = "@" + str(row.get("citekey", "")).strip().lstrip("@")
        if required_citekey and row_key != required_citekey:
            return False, f"citekey does not match {required_citekey}"
        if row_key not in references.entries:
            return False, f"citekey {row_key} is absent from references.bib"
        if not re.match(r"^\d{4}-\d{2}-\d{2}(?:T|$)", str(row.get("accessed_at", "")).strip()):
            return False, "accessed_at is not ISO-8601-like"
        if not re.match(r"^\d{4}-\d{2}-\d{2}(?:T|$)", str(row.get("verified_at", "")).strip()):
            return False, "verified_at is not ISO-8601-like"
        access_uri = str(row.get("access_uri", "")).strip()
        if access_uri.startswith(("/", "file://", "~/")) or re.match(r"^[A-Za-z]:[\\/]", access_uri):
            return False, "access_uri must not expose a local filesystem path"
        return True, ""

    for claim in claims:
        if claim.kind == "ambiguous":
            findings.append(
                Finding(
                    "critical",
                    "ambiguous_claim_segmentation",
                    claim.line,
                    "The sentence contains multiple quantitative or opposing directional claims; split it into atomic statements before ledger reconciliation.",
                    line_excerpt(claim.text),
                )
            )
            continue
        normalized = normalize_claim(claim.text)
        matches = [
            row
            for row_text, row in indexed
            if row_text and row_text == normalized
        ]
        if not matches:
            findings.append(
                Finding(
                    "critical",
                    "unverified_claim",
                    claim.line,
                    f"{claim.kind.replace('_', ' ').title()} claim has no matching claim_ledger.csv row.",
                    line_excerpt(claim.text),
                )
            )
            continue
        required_keys = claim.citation_ids or (None,)
        required_types = tuple(
            claim_type
            for claim_type in (
                "quantitative",
                "directional",
                "priority",
                "regulatory",
                "reimbursement",
                "availability",
                "comparative",
                "factual",
            )
            if claim.kind == claim_type or claim.kind.startswith(claim_type + "_and_")
        ) or (None,)
        row_errors: list[str] = []
        verified_all = True
        for required_key in required_keys:
            for required_type in required_types:
                results = [
                    complete_row(row, required_key, claim, required_type)
                    for row in matches
                ]
                if not any(ok for ok, _ in results):
                    verified_all = False
                    row_errors.extend(error for ok, error in results if not ok)
        if not verified_all:
            findings.append(
                Finding(
                    "critical",
                    "unverified_claim",
                    claim.line,
                    "Matching claim ledger row is incomplete or does not cover every cited source: "
                    + "; ".join(sorted(set(row_errors))[:6]),
                    line_excerpt(claim.text),
                )
            )
    return findings, not findings


def validate_working_manuscript_path(
    project_dir: Path | None, manuscript_path: Path | None
) -> list[Finding]:
    if project_dir is None or manuscript_path is None:
        return []
    expected = project_dir / "manuscript.md"
    supplied = Path(os.path.abspath(manuscript_path))
    if (
        supplied != Path(os.path.abspath(expected))
        or not path_is_project_owned_file(project_dir, supplied)
    ):
        return [
            Finding(
                "critical",
                "not_ready",
                0,
                "With --project-dir, the audited input must be the non-symlink <project_dir>/manuscript.md.",
            )
        ]
    return []
