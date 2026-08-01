"""CCF 目录解析与匹配的测试。

匹配层的红线：**宁可漏，不可错。** 错误的等级不会报错，
它给你一个看起来完全合理的 CCF-A。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from litsearch.ccf import (
    CcfEntry,
    CcfError,
    CcfMatcher,
    dump_catalog,
    load_catalog,
    normalize_name,
    parse_pdf,
)

CATALOG = Path("CCF.pdf")
needs_catalog = pytest.mark.skipif(not CATALOG.exists(), reason="需要 CCF.pdf")


def _entry(**kwargs) -> CcfEntry:
    payload = {"kind": "conference", "rank": "B", "full_name": "Some Conference", **kwargs}
    return CcfEntry(**payload)


class TestNormalizeName:
    @pytest.mark.parametrize(
        ("left", "right"),
        [
            ("IEEETransactionsonMedicalImaging", "IEEE transactions on medical imaging"),
            ("Computer-AssistedIntervention", "computer assisted intervention"),
            ("ACM SIGPLAN", "acmsigplan"),
        ],
    )
    def test_collapses_spacing_and_punctuation(self, left: str, right: str) -> None:
        assert normalize_name(left) == normalize_name(right)

    def test_empty(self) -> None:
        assert normalize_name(None) == ""


class TestMatcher:
    @pytest.fixture
    def matcher(self) -> CcfMatcher:
        return CcfMatcher(
            [
                _entry(
                    kind="journal",
                    rank="B",
                    abbrev="TMI",
                    full_name="IEEETransactionsonMedicalImaging",
                ),
                _entry(kind="journal", rank="C", full_name="MedicalImageAnalysis"),
                _entry(
                    kind="conference",
                    rank="B",
                    abbrev="MICCAI",
                    full_name="InternationalConferenceonMedicalImageComputing",
                ),
                _entry(
                    kind="conference",
                    rank="A",
                    abbrev="CVPR",
                    full_name="IEEE/CVFComputerVisionandPatternRecognitionConference",
                ),
                _entry(
                    kind="conference",
                    rank="B",
                    abbrev="ICASSP",
                    full_name="IEEEInternationalConferenceonAcoustics",
                ),
                _entry(
                    kind="conference", rank="C", abbrev="SC", full_name="SomeShortAbbrevConference"
                ),
            ]
        )

    def test_matches_full_name_across_spacing(self, matcher: CcfMatcher) -> None:
        hit = matcher.match("IEEE transactions on medical imaging")
        assert hit is not None and hit.rank == "B"

    def test_matches_entry_without_an_abbrev(self, matcher: CcfMatcher) -> None:
        hit = matcher.match("Medical Image Analysis")
        assert hit is not None and hit.rank == "C"

    def test_matches_bare_abbrev(self, matcher: CcfMatcher) -> None:
        assert matcher.match("MICCAI") is not None

    def test_matches_abbrev_embedded_with_a_year(self, matcher: CcfMatcher) -> None:
        """``IEEE ICASSP 2023`` 这类写法只能靠 token 匹配命中。"""
        hit = matcher.match("IEEE ICASSP 2023")
        assert hit is not None and hit.abbrev == "ICASSP"

    def test_short_abbrevs_do_not_match_inside_other_names(self, matcher: CcfMatcher) -> None:
        """``SC`` 长度不足，不能在任意刊名里命中——错配比漏配危险得多。"""
        assert matcher.match("Journal of SC Research and Practice") is None

    def test_short_abbrev_still_matches_when_the_whole_name_equals_it(
        self, matcher: CcfMatcher
    ) -> None:
        assert matcher.match("SC") is not None

    def test_tries_candidates_in_order(self, matcher: CcfMatcher) -> None:
        hit = matcher.match(None, "不认识的载体", "MICCAI")
        assert hit is not None and hit.abbrev == "MICCAI"

    def test_returns_none_when_absent(self, matcher: CcfMatcher) -> None:
        """目录里没有 = 未评级，不是低等级。"""
        assert matcher.match("International Symposium on Biomedical Imaging") is None

    def test_duplicate_abbrev_keeps_the_better_rank(self) -> None:
        matcher = CcfMatcher(
            [
                _entry(rank="C", abbrev="XYZW", full_name="Low"),
                _entry(rank="A", abbrev="XYZW", full_name="High"),
            ]
        )
        hit = matcher.match("XYZW")
        assert hit is not None and hit.rank == "A"


class TestRoundTrip:
    def test_json_round_trip(self, tmp_path: Path) -> None:
        entries = [_entry(abbrev="MICCAI", rank="B")]
        path = tmp_path / "ccf.json"
        path.write_text(dump_catalog(entries), encoding="utf-8")
        assert load_catalog(path) == entries

    def test_bad_json_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "ccf.json"
        path.write_text("{ not json", encoding="utf-8")
        with pytest.raises(CcfError):
            load_catalog(path)


@pytest.fixture(scope="module")
def real_entries() -> list[CcfEntry]:
    return parse_pdf(CATALOG)


@needs_catalog
class TestRealCatalog:
    """对真目录的锚点校验。解析器一旦跑偏，这些断言会立刻失败。"""

    def test_parses_a_plausible_number_of_entries(self, real_entries: list[CcfEntry]) -> None:
        assert 500 < len(real_entries) < 900

    def test_every_entry_is_well_formed(self, real_entries: list[CcfEntry]) -> None:
        assert all(item.rank in ("A", "B", "C") for item in real_entries)
        assert all(item.kind in ("journal", "conference") for item in real_entries)
        # PDF 抽取吃掉了词间空格；全称里再出现空格说明行拼接出了问题
        assert not [item for item in real_entries if " " in item.full_name]

    @pytest.mark.parametrize(
        ("abbrev", "kind", "rank"),
        [
            ("TPAMI", "journal", "A"),
            ("TMI", "journal", "B"),
            ("TIP", "journal", "A"),
            ("MICCAI", "conference", "B"),
            ("CVPR", "conference", "A"),
            ("ICLR", "conference", "A"),
            ("ECCV", "conference", "B"),
        ],
    )
    def test_known_anchors(
        self, real_entries: list[CcfEntry], abbrev: str, kind: str, rank: str
    ) -> None:
        hit = [item for item in real_entries if (item.abbrev or "").upper() == abbrev]
        assert hit, f"{abbrev} 没解析出来"
        assert hit[0].kind == kind
        assert hit[0].rank == rank

    def test_medical_image_analysis_has_no_abbrev_but_is_found(
        self, real_entries: list[CcfEntry]
    ) -> None:
        """MedIA 在目录里没有简称，只能靠全称匹配——这类条目共 47 条。"""
        matcher = CcfMatcher(real_entries)
        hit = matcher.match("Medical Image Analysis")
        assert hit is not None and hit.rank == "C"
