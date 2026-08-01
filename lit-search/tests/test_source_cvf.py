"""CVF（CVPR/ICCV/WACV）源：整年枚举 + 标题门槛 + 逐篇取摘要。

CVF 没有任何检索接口，只有按会议年份的完整论文列表页，且列表页**只有标题**。
因此策略是：整年列表一次拿全（每个会议年份 1 个请求），用必需块的**并集**
在标题上做门槛，只对门槛命中的论文去取单篇页拿摘要，再做严格 AND 判定。

fixture 取自 CVPR 2024 的真实列表页与真实单篇页。
"""

from __future__ import annotations

import httpx
import pytest

from litsearch.query import SourceQuery
from litsearch.sources.base import SourceError, collect
from litsearch.sources.cvf import (
    CvfSource,
    conference_years,
    parse_day_links,
    parse_listing,
)

from .conftest import fixture_text, make_topic

LISTING_URL = "https://openaccess.thecvf.com/CVPR2024"
PAPER = (
    "https://openaccess.thecvf.com/content/CVPR2024/html/"
    "Fan_Bi-level_Learning_of_Task-Specific_Decoders_for_Joint_Registration_"
    "and_One-Shot_CVPR_2024_paper.html"
)
VIDEO = (
    "https://openaccess.thecvf.com/content/CVPR2024/html/"
    "Lee_Guided_Slot_Attention_for_Unsupervised_Video_Object_Segmentation_"
    "CVPR_2024_paper.html"
)
MAPSEG = (
    "https://openaccess.thecvf.com/content/CVPR2024/html/"
    "Zhang_MAPSeg_Unified_Unsupervised_Domain_Adaptation_for_Heterogeneous_"
    "Medical_Image_Segmentation_CVPR_2024_paper.html"
)

#: 让门槛与严格判定都能被测到：标题里带 medical image + segmentation 的那篇应当留下
TOPIC = make_topic(
    concepts={
        "condition": {"required": True, "terms": ["medical image"]},
        "task": {"required": True, "terms": ["segmentation"]},
    },
    known_items=[],
    query_plan={"combinations": [["condition", "task"]]},
)


@pytest.fixture
def context(stage3_context):
    stage3_context.topic = TOPIC
    return stage3_context


def query() -> SourceQuery:
    return SourceQuery(source="cvf", query="CVPR2024", kind="enumeration", label="CVPR2024")


class TestListingParser:
    def test_extracts_title_and_links_from_the_real_page(self):
        entries = parse_listing(fixture_text("cvf_listing.html"), "CVPR2024")

        assert len(entries) == 5
        first = next(item for item in entries if "Bi-level" in item.title)
        assert first.title.startswith("Bi-level Learning of Task-Specific Decoders")
        assert first.url.startswith("https://openaccess.thecvf.com/content/CVPR2024/html/")
        assert first.pdf_url.endswith(".pdf")

    def test_ignores_the_pdf_and_supplemental_links(self):
        """列表页里每篇有 html/pdf/supp 三个链接，只有 dt.ptitle 里的才是论文标题。"""
        entries = parse_listing(fixture_text("cvf_listing.html"), "CVPR2024")

        assert len({item.url for item in entries}) == len(entries)
        assert all("/html/" in item.url for item in entries)

    def test_empty_page_yields_nothing(self):
        assert parse_listing("<html><body>no papers</body></html>", "CVPR2024") == []

    def test_the_2020_era_relative_hrefs_are_resolved(self):
        """2020 年代的页面用 ``content_CVPR_2020/html/…`` 这种**相对**路径，
        而 2021 起改成了 ``/content/CVPR2021/html/…``。只认后者会把整届读成 0 篇。"""
        entries = parse_listing(fixture_text("cvf_listing_2020.html"), "CVPR2020")

        assert entries
        assert all(item.url.startswith("https://openaccess.thecvf.com/") for item in entries)
        assert any("content_CVPR_2020/html/" in item.url for item in entries)


class TestSilentEmptyListing:
    """200 但解析出 0 篇，绝不能当成"这届没有论文"。

    实测两种情况都会这样：
    - CVPR2020 及更早的年份不支持 ``?day=all``，索引页只列出
      ``CVPR2020.py?day=2020-06-16`` 这样的逐日子页面（实测 3 天、共 483+ 篇）；
    - 网络波动时同一个 URL 会返回一个 200 的空壳页（本项目实测在 WACV2020 上撞到过，
      同一 URL 事后重取有 378 篇）。

    静默接受任何一种，都会让"这届会议我们查过了"变成一句假话。
    """

    def test_day_links_are_extracted_from_the_index(self):
        days = parse_day_links(fixture_text("cvf_day_index.html"))

        assert days == ["2020-06-16", "2020-06-17", "2020-06-18"]

    def test_a_page_without_day_links_yields_none(self):
        assert parse_day_links(fixture_text("cvf_listing.html")) == []

    async def test_empty_listing_falls_back_to_day_subpages(self, respx_mock, context):
        """``?day=all`` 那一版连逐日链接都不带（实测是个空壳页），
        必须回到**不带参数**的索引页才能拿到 day 列表。"""

        def responder(request: httpx.Request) -> httpx.Response:
            day = request.url.params.get("day")
            if day and day.startswith("2020-06"):
                return httpx.Response(200, text=fixture_text("cvf_listing.html"))
            if day == "all":
                return httpx.Response(200, text="<html><body>空壳</body></html>")
            return httpx.Response(200, text=fixture_text("cvf_day_index.html"))

        route = respx_mock.get("https://openaccess.thecvf.com/CVPR2020").mock(side_effect=responder)
        self._mock_papers(respx_mock)
        item = SourceQuery(source="cvf", query="CVPR2020", kind="enumeration", label="CVPR2020")

        records = [record async for record in CvfSource().fetch(item, context)]

        assert records, "逐日子页面里的论文必须被取到"
        assert [call.request.url.params.get("day") for call in route.calls[:5]] == [
            "all",
            None,
            "2020-06-16",
            "2020-06-17",
            "2020-06-18",
        ]

    async def test_empty_listing_without_day_links_is_a_failure(self, respx_mock, context):
        """没有逐日链接又解析不出论文——只能是抓坏了，必须记为失败而不是 0 篇。"""
        respx_mock.get(LISTING_URL).mock(
            return_value=httpx.Response(200, text="<html><body>正在维护</body></html>")
        )

        outcome = await collect(CvfSource(), query(), context)

        assert outcome.status == "failed"
        assert "0 篇" in (outcome.error or "")

    def _mock_papers(self, respx_mock) -> None:
        for url in (PAPER, VIDEO, MAPSEG):
            respx_mock.get(url.replace("CVPR2024", "CVPR2020")).mock(
                return_value=httpx.Response(200, text=fixture_text("cvf_paper.html"))
            )
            respx_mock.get(url).mock(
                return_value=httpx.Response(200, text=fixture_text("cvf_paper.html"))
            )


class TestConferenceYears:
    def test_covers_every_year_the_harvest_window_touches(self):
        years = conference_years(TOPIC.window, ["CVPR"])

        assert years[0] == "CVPR2020" and years[-1] == "CVPR2027"

    def test_multiple_venues_are_all_enumerated(self):
        years = conference_years(TOPIC.window, ["CVPR", "WACV"])

        assert any(item.startswith("CVPR") for item in years)
        assert any(item.startswith("WACV") for item in years)


class TestFetch:
    def _mock_listing(self, respx_mock, body: str = "") -> None:
        respx_mock.get(LISTING_URL).mock(
            return_value=httpx.Response(200, text=body or fixture_text("cvf_listing.html"))
        )

    def _mock_others(self, respx_mock) -> None:
        """非重点的两篇门槛命中页，用最小响应占位。"""
        respx_mock.get(VIDEO).mock(return_value=httpx.Response(200, text="<html></html>"))
        respx_mock.get(MAPSEG).mock(return_value=httpx.Response(200, text="<html></html>"))

    async def test_only_gate_hits_trigger_a_paper_request(self, respx_mock, context):
        """2716 篇里只有约 150 篇标题命中必需块——不能对每篇都去取摘要。"""
        self._mock_listing(respx_mock)
        paper = respx_mock.get(PAPER).mock(
            return_value=httpx.Response(200, text=fixture_text("cvf_paper.html"))
        )
        video = respx_mock.get(VIDEO).mock(
            return_value=httpx.Response(200, text="<div id='abstract'>video objects</div>")
        )
        respx_mock.get(MAPSEG).mock(return_value=httpx.Response(200, text="<html></html>"))

        records = [item async for item in CvfSource().fetch(query(), context)]

        assert paper.called and video.called
        assert len(respx_mock.calls) == 4  # 1 个列表页 + 3 个门槛命中（5 篇里有 2 篇不命中）
        # 只有标题+摘要同时满足全部必需块的才留下——视频分割那篇命中任务块但没有条件块
        assert [item.title.split(":")[0].split(" of ")[0] for item in records] == [
            "Bi-level Learning",
            "MAPSeg",
        ]

    async def test_abstract_and_authors_come_from_the_paper_page(self, respx_mock, context):
        self._mock_listing(respx_mock)
        respx_mock.get(PAPER).mock(
            return_value=httpx.Response(200, text=fixture_text("cvf_paper.html"))
        )
        self._mock_others(respx_mock)

        record = [item async for item in CvfSource().fetch(query(), context)][0]

        assert record.abstract.startswith("One-shot medical image segmentation")
        assert "Xin Fan" in record.authors
        assert record.venue == "CVPR 2024"

    async def test_conference_month_is_taken_from_bibtex_not_guessed(self, respx_mock, context):
        """CVPR 2021 在 6 月举行，落在 2021-07-01 的窗口下沿之外。
        只用年份会让整届会议变成"精度不足"，必须从 bibtex 取到月份。"""
        self._mock_listing(respx_mock)
        respx_mock.get(PAPER).mock(
            return_value=httpx.Response(200, text=fixture_text("cvf_paper.html"))
        )
        self._mock_others(respx_mock)

        record = [item async for item in CvfSource().fetch(query(), context)][0]

        assert record.dates.published_online == "2024 June"

    async def test_nonexistent_conference_year_is_not_a_failure(self, respx_mock, context):
        """ICCV 只在奇数年举办，ICCV2024 返回 404——那是"没这届"，不是采集失败。"""
        respx_mock.get("https://openaccess.thecvf.com/ICCV2024").mock(
            return_value=httpx.Response(404, text="Not Found")
        )
        item = SourceQuery(source="cvf", query="ICCV2024", kind="enumeration", label="ICCV2024")

        outcome = await collect(CvfSource(), item, context)

        assert outcome.status == "complete"
        assert outcome.records == []

    async def test_a_broken_paper_page_does_not_kill_the_whole_year(self, respx_mock, context):
        """单篇页 500 不能让整届会议的采集作废——记下并继续。"""
        self._mock_listing(respx_mock)
        respx_mock.get(PAPER).mock(return_value=httpx.Response(500, text="boom"))
        self._mock_others(respx_mock)
        source = CvfSource()

        records = [item async for item in source.fetch(query(), context)]

        assert [item.title.split(":")[0] for item in records] == ["MAPSeg"]
        assert any("500" in note for note in source.skipped)

    async def test_listing_failure_is_a_real_failure(self, respx_mock, context):
        respx_mock.get(LISTING_URL).mock(return_value=httpx.Response(500, text="boom"))

        with pytest.raises(SourceError):
            [item async for item in CvfSource().fetch(query(), context)]

    async def test_raw_pages_are_persisted_for_audit(self, respx_mock, context):
        self._mock_listing(respx_mock)
        respx_mock.get(PAPER).mock(
            return_value=httpx.Response(200, text=fixture_text("cvf_paper.html"))
        )
        self._mock_others(respx_mock)

        [item async for item in CvfSource().fetch(query(), context)]

        saved = list((context.store.root / "cvf").rglob("*.html.gz"))
        assert len(saved) == 4
