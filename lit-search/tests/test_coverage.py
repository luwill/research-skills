"""覆盖率证据：**没做成的事**必须和做成的事一样显形。

这一层的红线不是"算得准"，是"不许有一句话是编的"。
一份漏了半条流水线却只字不提的覆盖率报告，比没有报告更危险——
它看起来像证据，而读者无法从报告本身发现缺口。
"""

from __future__ import annotations

from datetime import date

from litsearch.coverage import Gap, coverage_markdown, find_gaps
from litsearch.dedupe import deduplicate
from litsearch.normalize import DateEvidence, Record
from litsearch.protocol import Window

WINDOW = Window(start=date(2021, 7, 1), end=date(2026, 7, 27))
PRIORITY = ["published_online", "published_print", "preprint_submitted", "source_reported"]


def make(source: str, title: str, *, doi=None, online="2023-01-01"):
    return Record(
        source=source,
        source_id=f"{source}-{title}",
        title=title,
        identifiers={"doi": doi} if doi else {},
        dates=DateEvidence(published_online=online),
    ).resolve(WINDOW, PRIORITY)


def corpus(records):
    return deduplicate(records, WINDOW, PRIORITY)


def render(gaps=(), records=None, gold=(), controls=(), rounds=()):
    return coverage_markdown(
        title="Demo",
        corpus=records if records is not None else corpus([make("openalex", "a")]),
        gold_set=list(gold),
        controls=list(controls),
        gaps=list(gaps),
        snowball_rounds=list(rounds),
    )


class TestFindGaps:
    def test_a_declared_source_that_never_ran_is_a_gap(self) -> None:
        """实测事故：续跑把 openreview/grey 写进了 manifest，却一次都没访问过。"""
        gaps = find_gaps(
            declared=["openalex", "arxiv", "openreview", "grey"],
            executed=["openalex", "arxiv"],
            enabled=["openalex", "arxiv", "openreview", "grey"],
            available={"openalex", "arxiv", "openreview", "grey"},
            depth=None,
            ran_snowball=True,
        )
        text = " ".join(f"{gap.what} {gap.why}" for gap in gaps)
        assert "openreview" in text
        assert "grey" in text

    def test_an_unimplemented_source_says_so_rather_than_vanishing(self) -> None:
        """协议里 enabled、注册表里没有 → 交集处被丢掉。丢掉可以，不吭声不行。"""
        gaps = find_gaps(
            declared=["openalex"],
            executed=["openalex"],
            enabled=["openalex", "semantic_scholar"],
            available={"openalex"},
            depth=None,
            ran_snowball=True,
        )
        assert any("semantic_scholar" in gap.what for gap in gaps)
        assert any("尚未实现" in gap.why for gap in gaps)

    def test_depth_that_skips_snowball_is_a_gap_with_the_depth_as_its_reason(self) -> None:
        gaps = find_gaps(
            declared=["openalex"],
            executed=["openalex"],
            enabled=["openalex"],
            available={"openalex"},
            depth="quick",
            ran_snowball=False,
        )
        snowball = [gap for gap in gaps if "滚雪球" in gap.what]
        assert snowball, "没跑滚雪球必须显形——它的独有贡献实测占 92%"
        assert "quick" in snowball[0].why

    def test_missing_snowball_without_a_known_depth_still_shows_up(self) -> None:
        """档位没记下来的旧 run 也要报缺口，只是理由写成未知。"""
        gaps = find_gaps(
            declared=["openalex"],
            executed=["openalex"],
            enabled=["openalex"],
            available={"openalex"},
            depth=None,
            ran_snowball=False,
        )
        assert any("滚雪球" in gap.what for gap in gaps)

    def test_a_clean_run_has_no_gaps(self) -> None:
        assert (
            find_gaps(
                declared=["openalex", "pubmed"],
                executed=["openalex", "pubmed"],
                enabled=["openalex", "pubmed"],
                available={"openalex", "pubmed"},
                depth="systematic",
                ran_snowball=True,
            )
            == []
        )


class TestGapsInTheReport:
    def test_the_section_is_always_present_even_when_clean(self) -> None:
        """ "没有缺口"必须是被写出来的结论，不能靠一个空白段落暗示。"""
        assert "## 本次运行未执行的部分" in render()

    def test_a_clean_run_says_so_explicitly(self) -> None:
        assert "无——协议声明的每一步都执行了" in render()

    def test_gaps_are_listed_with_their_reason(self) -> None:
        text = render(gaps=[Gap(what="源 openreview", why="声明了但一次都没访问")])
        assert "openreview" in text
        assert "声明了但一次都没访问" in text


class TestCaptureRecapture:
    """实测事故：这一节曾经是**无条件拼进去的字符串**，

    内容是"OpenAlex 受配额限制未纳入"。而那次运行 OpenAlex 明明跑了 3,944 条，
    真正缺席的是被协议主动关掉的 PubMed。证据文件里的硬编码叙述是最坏的一种，
    因为它长得和算出来的一模一样。
    """

    def test_it_is_computed_when_both_sources_are_present(self) -> None:
        records = corpus(
            [
                make("pubmed", "shared", doi="10.1/a"),
                make("openalex", "shared", doi="10.1/a"),
                make("pubmed", "only-pubmed", doi="10.1/b"),
                make("openalex", "only-openalex", doi="10.1/c"),
            ]
        )
        text = render(records=records)
        assert "Chapman" in text
        assert "未纳入" not in text

    def test_absence_names_the_source_that_is_actually_missing(self) -> None:
        text = render(records=corpus([make("openalex", "a"), make("arxiv", "b")]))
        assert "pubmed" in text
        assert "openalex" not in text.split("## 两源重叠诊断")[1].split("##")[0].replace(
            "pubmed × openalex", ""
        ), "缺席理由不该点名一个明明跑了的源"

    def test_the_quota_narrative_is_never_asserted_without_evidence(self) -> None:
        """回归护栏：这句硬编码曾把'用户关掉了 PubMed'说成'OpenAlex 配额不够'。"""
        assert "配额限制未纳入" not in render()

    def test_the_estimate_is_absent_rather_than_faked_on_zero_overlap(self) -> None:
        records = corpus(
            [
                make("pubmed", "x", doi="10.1/x"),
                make("openalex", "y", doi="10.1/y"),
            ]
        )
        text = render(records=records)
        assert "零重叠" in text

    def test_the_estimate_is_never_labelled_as_pipeline_recall(self) -> None:
        records = corpus(
            [
                make("pubmed", "shared", doi="10.1/a"),
                make("openalex", "shared", doi="10.1/a"),
                make("pubmed", "p", doi="10.1/b"),
                make("openalex", "o", doi="10.1/c"),
            ]
        )

        section = render(records=records).split("## 两源重叠诊断")[1].split("##")[0]
        assert "两源并集覆盖度" in section
        assert "估计召回率" not in section


class TestStrictWindowDenominator:
    def test_source_counts_exclude_wide_harvest_margin_records(self) -> None:
        records = corpus(
            [
                make("openalex", "inside", doi="10.1/in", online="2023-01-01"),
                make("pubmed", "outside", doi="10.1/out", online="2020-01-01"),
            ]
        )

        text = render(records=records)

        assert "宽采集语料 **2**" in text
        assert "严格窗口语料 **1**" in text
        contribution = text.split("## 来源独有贡献")[1].split("##")[0]
        assert "pubmed" not in contribution


class TestGoldSetStrength:
    def test_a_thin_gold_set_is_flagged_as_weak_evidence(self) -> None:
        """3/3 = 100% 和 9/9 = 100% 印出来一模一样，但证据强度差很多。"""
        from litsearch.protocol import SeedItem

        seeds = [SeedItem(doi="10.1/a"), SeedItem(doi="10.1/b")]
        records = corpus([make("openalex", "a", doi="10.1/a"), make("openalex", "b", doi="10.1/b")])
        text = render(records=records, gold=seeds)
        assert "证据偏弱" in text

    def test_a_full_gold_set_is_not_flagged(self) -> None:
        from litsearch.protocol import SeedItem

        seeds = [SeedItem(doi=f"10.1/{index}") for index in range(6)]
        records = corpus([make("openalex", str(index), doi=f"10.1/{index}") for index in range(6)])
        assert "证据偏弱" not in render(records=records, gold=seeds)
