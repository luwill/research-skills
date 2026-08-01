"""交付层的测试。

两条红线：
- **全量**：文档里的记录数必须等于输入数。
- **不伪装**：本地拼的引文绝不能看起来像出版商登记数据。
"""

from __future__ import annotations

from datetime import date

import httpx
import pytest

from litsearch.deliver import (
    BIBTEX,
    Citation,
    DeliverError,
    accept_header,
    bibtex_document,
    dois_markdown,
    fetch_citations,
    local_citation,
    references_markdown,
    resolve_style,
)
from litsearch.rank import RankedRecord, VenueKind
from litsearch.sources.base import HttpClient, RateLimiter

TODAY = date(2026, 7, 30)


def _ranked(key: str = "k", **kwargs) -> RankedRecord:
    payload = {
        "key": key,
        "title": kwargs.pop("title", f"标题 {key}"),
        "doi": kwargs.pop("doi", f"10.1/{key}"),
        "venue": kwargs.pop("venue", "某刊"),
        "kind": kwargs.pop("kind", VenueKind.JOURNAL),
        "band": kwargs.pop("band", "—"),
        **kwargs,
    }
    return RankedRecord(**payload)


class TestResolveStyle:
    @pytest.mark.parametrize("name", ["apa", "ieee", "gbt7714", "nature", "ama", BIBTEX])
    def test_known_styles(self, name: str) -> None:
        assert resolve_style(name)

    def test_gbt7714_maps_to_the_real_csl_name(self) -> None:
        """实测 ``gb-t-7714-2015-numeric`` 不存在，正确的名字带 china-national-standard 前缀。"""
        assert resolve_style("gbt7714") == "china-national-standard-gb-t-7714-2015-numeric"

    def test_unknown_style_fails_immediately(self) -> None:
        """样式名写错时 doi.org 对每条都返回 200 + JSON 错误——必须在发请求前就拦下。"""
        with pytest.raises(DeliverError):
            resolve_style("vancouver")

    def test_accept_header(self) -> None:
        assert "style=apa" in accept_header("apa")
        assert accept_header(BIBTEX) == "application/x-bibtex"


class TestDoisMarkdown:
    def test_contains_every_record(self) -> None:
        records = [_ranked(f"k{i}", metric=float(i)) for i in range(12)]
        text = dois_markdown(records, today=TODAY, title="T")
        for item in records:
            assert item.doi in text

    def test_declares_full_delivery(self) -> None:
        text = dois_markdown([_ranked()], today=TODAY, title="T")
        assert "全量交付" in text

    def test_warns_the_metric_is_not_jif(self) -> None:
        text = dois_markdown([_ranked()], today=TODAY, title="T")
        assert "不是 JIF" in text

    def test_lists_records_without_a_doi_separately(self) -> None:
        records = [_ranked("a"), _ranked("b", doi=None)]
        text = dois_markdown(records, today=TODAY, title="T")
        assert "无 DOI" in text
        assert "不为它们编造标识符" in text

    def test_empty_tiers_are_still_shown(self) -> None:
        """ "这一层一条都没有"是有信息量的，不能悄悄省掉。"""
        text = dois_markdown([_ranked(metric=1.0)], today=TODAY, title="T")
        assert "本层没有记录" in text

    def test_evidence_marks_explain_placement(self) -> None:
        record = _ranked(ccf_rank="B", metric=9.5, cited_by_count=120, in_top_10_percent=True)
        text = dois_markdown([record], today=TODAY, title="T")
        assert "CCF-B" in text
        assert "引用前 10%" in text
        assert "被引 120" in text

    def test_pipes_in_titles_do_not_break_the_table(self) -> None:
        text = dois_markdown([_ranked(title="A | B")], today=TODAY, title="T")
        assert r"A \| B" in text


class TestReferences:
    def test_unverified_citations_are_marked(self) -> None:
        records = [_ranked("a"), _ranked("b")]
        citations = {
            "a": Citation("a", "登记引文", verified=True),
            "b": Citation("b", "本地引文", verified=False),
        }
        text = references_markdown(records, citations, today=TODAY, title="T", style="apa")
        assert "登记引文" in text
        assert "⚠️ 本地引文" in text
        assert "⚠️ 登记引文" not in text

    def test_numbering_covers_every_record(self) -> None:
        records = [_ranked(f"k{i}") for i in range(5)]
        text = references_markdown(records, {}, today=TODAY, title="T", style="apa")
        assert "[5]" in text and "[6]" not in text

    def test_local_citation_leaves_missing_fields_blank(self) -> None:
        record = _ranked(venue=None, date_text=None, title="只有标题")
        assert local_citation(record) == "只有标题."


class TestBibtex:
    def test_only_registered_entries_are_written(self) -> None:
        """本地拼的 BibTeX 字段不全，混进 .bib 会污染整个文件。"""
        records = [_ranked("a"), _ranked("b")]
        citations = {
            "a": Citation("a", "@article{x, title={T}}", verified=True),
            "b": Citation("b", "本地", verified=False),
        }
        text = bibtex_document(records, citations, today=TODAY)
        assert "@article{x" in text
        assert "本地" not in text
        assert "另有 1 条" in text


class TestFetchCitations:
    @pytest.fixture
    def client(self) -> HttpClient:
        return HttpClient(
            httpx.AsyncClient(timeout=5.0, follow_redirects=True),
            rate_limiter=RateLimiter(min_interval=0.0),
            max_attempts=1,
            backoff_base=0.0,
        )

    @pytest.mark.asyncio
    async def test_sends_the_accept_header(self, respx_mock, client) -> None:
        route = respx_mock.get("https://doi.org/10.1/k").mock(
            return_value=httpx.Response(200, text="Author, A. (2024). Title.")
        )
        result = await fetch_citations(client, [_ranked("k")], style="apa")
        assert route.calls[0].request.headers["accept"] == "text/x-bibliography; style=apa"
        assert result["k"].verified is True

    @pytest.mark.asyncio
    async def test_json_error_body_is_not_treated_as_a_citation(self, respx_mock, client) -> None:
        """doi.org 用 200 + JSON 报 style-not-found——状态码不会告诉你。"""
        respx_mock.get("https://doi.org/10.1/k").mock(
            return_value=httpx.Response(200, text='{"code":"style-not-found"}')
        )
        result = await fetch_citations(client, [_ranked("k")], style="apa")
        assert result["k"].verified is False
        assert result["k"].error

    @pytest.mark.asyncio
    async def test_one_failure_does_not_sink_the_batch(self, respx_mock, client) -> None:
        respx_mock.get("https://doi.org/10.1/a").mock(return_value=httpx.Response(500))
        respx_mock.get("https://doi.org/10.1/b").mock(
            return_value=httpx.Response(200, text="好引文")
        )
        result = await fetch_citations(client, [_ranked("a"), _ranked("b")], style="apa")
        assert result["a"].verified is False
        assert result["b"].verified is True

    @pytest.mark.asyncio
    async def test_records_without_a_doi_get_a_local_citation(self, client) -> None:
        result = await fetch_citations(client, [_ranked("a", doi=None)], style="apa")
        assert result["a"].verified is False
        assert result["a"].text


class TestCleanCitation:
    def test_strips_the_styles_own_numbering(self) -> None:
        """gbt7714 / ieee 是编号样式，自带 ``[1]``；文档也要编号，不去掉就成了 ``[1] [1]``。"""
        from litsearch.deliver import clean_citation

        assert clean_citation("[1]BILLOT B, et al. SynthSeg[J].").startswith("BILLOT")

    def test_unescapes_html_entities(self) -> None:
        from litsearch.deliver import clean_citation

        assert "&" in clean_citation("Biomedicine &amp; Pharmacotherapy")
        assert "&amp;" not in clean_citation("Biomedicine &amp; Pharmacotherapy")

    def test_leaves_unnumbered_styles_alone(self) -> None:
        from litsearch.deliver import clean_citation

        text = "Billot, B. (2023). SynthSeg. Medical Image Analysis."
        assert clean_citation(text) == text

    @pytest.mark.asyncio
    async def test_bibtex_is_not_stripped(self, respx_mock) -> None:
        """BibTeX 不是编号样式，去前缀的正则不该碰它。"""
        from litsearch.deliver import BIBTEX, fetch_citations

        client = HttpClient(
            httpx.AsyncClient(timeout=5.0, follow_redirects=True),
            rate_limiter=RateLimiter(min_interval=0.0),
            max_attempts=1,
            backoff_base=0.0,
        )
        body = "@article{x_2023, title={T &amp; U}}"
        respx_mock.get("https://doi.org/10.1/k").mock(return_value=httpx.Response(200, text=body))
        result = await fetch_citations(client, [_ranked("k")], style=BIBTEX)
        assert result["k"].text == body


class TestValidateCitation:
    """HTTP 200 但内容不是引文——这是这个项目里反复出现的同一类错误。"""

    def test_rejects_a_publisher_landing_page(self) -> None:
        """实测：部分 DOI 解析到出版商页面，200 返回整页 HTML，内容协商没被遵守。"""
        from litsearch.deliver import NotACitation, validate_citation

        with pytest.raises(NotACitation):
            validate_citation('<!DOCTYPE html>\n<html lang="en">…', style="apa")

    def test_rejects_html_without_a_doctype(self) -> None:
        from litsearch.deliver import NotACitation, validate_citation

        with pytest.raises(NotACitation):
            validate_citation('<div class="bg_div"></div><span>关闭</span>', style="apa")

    def test_rejects_a_json_error_body(self) -> None:
        from litsearch.deliver import NotACitation, validate_citation

        with pytest.raises(NotACitation):
            validate_citation('{"code":"style-not-found"}', style="apa")

    def test_rejects_something_far_too_long_to_be_a_citation(self) -> None:
        from litsearch.deliver import NotACitation, validate_citation

        with pytest.raises(NotACitation):
            validate_citation("A" * 9000, style="apa")

    def test_rejects_non_bibtex_when_bibtex_was_asked_for(self) -> None:
        from litsearch.deliver import BIBTEX, NotACitation, validate_citation

        validate_citation("@article{x, title={T}}", style=BIBTEX)
        with pytest.raises(NotACitation):
            validate_citation("Author, A. (2024). Title.", style=BIBTEX)

    def test_accepts_a_real_citation(self) -> None:
        from litsearch.deliver import validate_citation

        text = "[1]BILLOT B, et al. SynthSeg[J/OL]. Medical Image Analysis, 2023, 86: 102789."
        assert validate_citation(text, style="apa") == text

    def test_double_escaped_entities_are_fully_unescaped(self) -> None:
        """Crossref 里存在 ``&amp;amp;`` 这类双重转义，解一次不够。"""
        from litsearch.deliver import clean_citation

        assert clean_citation("Electrical Engineering &amp;amp; Communication") == (
            "Electrical Engineering && Communication".replace("&&", "& ").replace("& ", "& ")
        ) or "&amp;" not in clean_citation("Electrical Engineering &amp;amp; Communication")

    @pytest.mark.asyncio
    async def test_html_response_degrades_to_local_citation(self, respx_mock) -> None:
        from litsearch.deliver import fetch_citations

        client = HttpClient(
            httpx.AsyncClient(timeout=5.0, follow_redirects=True),
            rate_limiter=RateLimiter(min_interval=0.0),
            max_attempts=1,
            backoff_base=0.0,
        )
        respx_mock.get("https://doi.org/10.1/k").mock(
            return_value=httpx.Response(200, text="<!DOCTYPE html><html><body>x</body></html>")
        )
        result = await fetch_citations(client, [_ranked("k")], style="apa")
        assert result["k"].verified is False
        assert "<" not in result["k"].text
