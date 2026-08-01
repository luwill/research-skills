"""CVF Open Access（CVPR / ICCV / WACV）—— 顶会全量枚举。

为什么不靠 OpenAlex 的 venue filter：实测 CVPR 的 source 按年碎片化
（``S4363607701`` = 2022 CVPR 2082 篇，``S4363607748`` 同年另有 570 篇），
数不齐也说不清漏了什么。CVF 是官方全量存档，一个会议年份一个请求就能拿全。

代价是 CVF **没有任何检索接口**，列表页也**只有标题**（实测 CVPR 2024 共 2,716 篇）。
因此分两层：

1. 整年列表 → 用必需块的**并集**在标题上做门槛（实测每个会议年份约 150 篇命中）；
2. 只对门槛命中的论文取单篇页拿摘要，再用**全部必需块的 AND** 严格判定。

门槛用"并集"而不是"交集"，是因为标题里往往只写得下一个概念
（"…Medical Image Segmentation" 不会再写 "ischemic stroke"）。宁可多取几百个页面，
也不能因为标题没写全就漏掉。

实测参考（本课题）：CVPR/ICCV/WACV 2021–2026 共约 9,200 篇里，标题命中条件块的
只有 5 篇且**全是假阳性**——CVF 语境下的 "stroke" 是"笔触"（Neural 3D Strokes、
StrokeFaceNeRF），"penumbra" 是"半影"。这个源的价值正在于把这个"零"测出来。
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from dataclasses import dataclass

from litsearch.localfilter import build_matcher
from litsearch.normalize import DateEvidence, Record, clean_text
from litsearch.query import SourceQuery, conference_years
from litsearch.sources.base import SourceContext, SourceError, record_hash

BASE = "https://openaccess.thecvf.com"

#: 列表页是 ``<dt class="ptitle">`` + ``<dd>``（作者表单 + pdf/supp 链接）交替的 dl。
#: 每篇有 html/pdf/supp 三个链接，只有 dt.ptitle 里的那个才是论文本身——
#: 用宽泛的 ``<a href="/content/...">`` 会把条目数虚增三倍。
#: href 有两种写法：2021 起是绝对路径 ``/content/CVPR2021/html/…``，
#: 2020 及更早是相对路径 ``content_CVPR_2020/html/…``。只认前者会把整届读成 0 篇。
_ENTRY_RE = re.compile(
    r'<dt class="ptitle">.*?<a href="(?P<url>[^"]+?\.html)"[^>]*>(?P<title>.*?)</a>'
    r'(?P<tail>.*?)(?=<dt class="ptitle">|</dl>|\Z)',
    re.S,
)
_PDF_RE = re.compile(r'href="(?P<url>[^"]+?\.pdf)"')


def _absolute(url: str) -> str:
    if url.startswith("http"):
        return url
    return f"{BASE}{url}" if url.startswith("/") else f"{BASE}/{url}"


_DIV_RE = '<div id="{name}"[^>]*>(?P<body>.*?)</div>'
_AUTHORS_RE = re.compile(r"<b><i>(?P<names>.*?)</i></b>", re.S)
_BIBTEX_MONTH_RE = re.compile(r"month\s*=\s*\{(?P<month>[A-Za-z]+)\}")
_VENUE_YEAR_RE = re.compile(r"^(?P<venue>[A-Za-z]+)(?P<year>\d{4})$")
#: 老年份（实测 CVPR2020 及更早）不支持 ``?day=all``，索引页只给逐日子页面链接
_DAY_LINK_RE = re.compile(r"[?&]day=(?P<day>\d{4}-\d{2}-\d{2})")


@dataclass(frozen=True)
class CvfEntry:
    """列表页上的一篇论文。此时只有标题，摘要要另取。"""

    title: str
    url: str
    pdf_url: str


def _section(html: str, name: str) -> str:
    match = re.search(_DIV_RE.format(name=name), html, re.S)
    return match.group("body") if match else ""


def parse_listing(html: str, venue_year: str) -> list[CvfEntry]:
    entries: list[CvfEntry] = []
    for match in _ENTRY_RE.finditer(html):
        title = clean_text(match.group("title"))
        if not title:
            continue
        pdf = _PDF_RE.search(match.group("tail"))
        entries.append(
            CvfEntry(
                title=title,
                url=_absolute(match.group("url")),
                pdf_url=_absolute(pdf.group("url")) if pdf else "",
            )
        )
    return entries


def parse_day_links(html: str) -> list[str]:
    """索引页上的逐日子页面日期，按出现顺序去重。"""
    days: list[str] = []
    for match in _DAY_LINK_RE.finditer(html):
        day = match.group("day")
        if day not in days:
            days.append(day)
    return days


#: 会议年份的构造属于查询空间，定义在 query 层；此处再导出，便于按源查阅
__all__ = [
    "CvfEntry",
    "CvfSource",
    "conference_years",
    "parse_day_links",
    "parse_listing",
    "split_venue_year",
]


def split_venue_year(venue_year: str) -> tuple[str, str]:
    match = _VENUE_YEAR_RE.match(venue_year)
    if not match:
        raise ValueError(f"无法解析会议年份 {venue_year!r}，期望形如 CVPR2024")
    return match.group("venue"), match.group("year")


class CvfSource:
    name = "cvf"

    def __init__(self) -> None:
        self.last_total: int | None = None
        #: 取摘要失败的单篇页。单篇失败不该让整届会议作废，但必须留痕。
        self.skipped: list[str] = []

    async def _listing(self, venue_year: str, context: SourceContext) -> list[CvfEntry]:
        """整届论文列表。

        ``200 但解析出 0 篇`` 绝不当作"这届没有论文"——那正是本项目要消灭的静默少召回。
        两种已实测的成因分别处理：老年份要走逐日子页面；抓坏了就报失败。
        """
        try:
            body = await context.client.get_text(
                f"{BASE}/{venue_year}", {"day": "all"}, source=self.name
            )
        except SourceError as error:
            if error.status == 404:
                # 这届会议不存在（ICCV 只在奇数年办），不是采集失败
                self.last_total = 0
                return []
            raise

        page = self._store(venue_year, context, body)
        entries = parse_listing(body, venue_year)

        if not entries:
            # 实测 CVPR2020 及更早不支持 ?day=all —— 而且 ``?day=all`` 那一版
            # 连逐日链接都不带（返回的是个空壳页），必须回到**不带参数**的索引页去取。
            index = await context.client.get_text(f"{BASE}/{venue_year}", {}, source=self.name)
            page = self._store(venue_year, context, index, page)
            entries.extend(parse_listing(index, venue_year))
            for day in parse_day_links(index):
                day_body = await context.client.get_text(
                    f"{BASE}/{venue_year}", {"day": day}, source=self.name
                )
                page = self._store(venue_year, context, day_body, page)
                entries.extend(parse_listing(day_body, venue_year))

        if not entries:
            # 既没有论文也没有逐日链接：只能是抓坏了（实测网络波动会返回 200 空壳页）。
            # 静默接受会让"这届我们查过了"变成一句假话。
            raise SourceError(
                self.name,
                f"{venue_year} 返回 200 却解析出 0 篇，且没有逐日子页面链接——"
                f"按采集失败处理，不当作「这届没有论文」",
            )

        self.last_total = len(entries)
        return entries

    def _store(self, venue_year: str, context: SourceContext, body: str, page: int = 0) -> int:
        page += 1
        context.store.write(self.name, venue_year, page, body, "html")
        return page

    async def estimate(self, query: SourceQuery, context: SourceContext) -> int | None:
        """返回**门槛命中数**（即将要取的单篇页数），而不是整届论文数——
        这才是这个源真正的开销所在。"""
        matcher = build_matcher(context.topic)
        entries = await self._listing(query.query, context)
        return sum(1 for item in entries if matcher.matches_any_required(item.title))

    async def fetch(self, query: SourceQuery, context: SourceContext) -> AsyncIterator[Record]:
        venue_year = query.query
        venue, year = split_venue_year(venue_year)
        matcher = build_matcher(context.topic)
        entries = await self._listing(venue_year, context)

        page = 1
        for entry in entries:
            if not matcher.matches_any_required(entry.title):
                continue
            try:
                body = await context.client.get_text(entry.url, {}, source=self.name)
            except SourceError as error:
                self.skipped.append(f"{entry.url}: {error}")
                continue
            page += 1
            context.store.write(self.name, venue_year, page, body, "html")

            abstract = clean_text(_section(body, "abstract"))
            if not matcher.matches_all_required(f"{entry.title} {abstract}"):
                continue
            yield self._to_record(entry, body, abstract, venue, year)

    def _to_record(
        self, entry: CvfEntry, body: str, abstract: str, venue: str, year: str
    ) -> Record:
        authors_block = _section(body, "authors")
        names = _AUTHORS_RE.search(authors_block)
        authors = (
            [clean_text(part) for part in names.group("names").split(",") if clean_text(part)]
            if names
            else []
        )
        # bibtex 里有月份。只用年份会让 6 月举办的 CVPR 2021 变成"精度不足"，
        # 而它其实落在 2021-07-01 窗口下沿之外——这个区分必须保住。
        month = _BIBTEX_MONTH_RE.search(body)
        published = f"{year} {month.group('month')}" if month else year

        source_id = entry.url.rsplit("/", 1)[-1].removesuffix(".html")
        urls = {"landing": entry.url}
        if entry.pdf_url:
            urls["pdf"] = entry.pdf_url

        return Record(
            source=self.name,
            source_id=source_id,
            title=entry.title,
            abstract=abstract or None,
            authors=authors,
            venue=f"{venue} {year}",
            publication_type="conference-paper",
            language="en",
            urls=urls,
            dates=DateEvidence(published_online=published),
            raw_sha256=record_hash({"url": entry.url, "title": entry.title}),
        )
