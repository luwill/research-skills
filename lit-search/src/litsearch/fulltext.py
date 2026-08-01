"""全文位置解析：按合法来源分层查找，查不到的如实交给机构访问。

医工交叉领域（IEEE TMI / Medical Image Analysis / Radiology）大量论文是闭源的，
但**约一半有合法的免费版本**——预印本、作者接收版、出版商 OA、PMC。实测 ISLES 语料
53 篇：MIA 56%、Radiology 50%、TMI 33%。

因此自动化的正确形态是**位置解析器**，而不是下载器：
逐级查合法来源 → 能开放获取的直接拿 → 拿不到的进 `institutional_access.csv`，
由用户用自己的机构订阅或出版商 TDM API 处理。

本模块**不**绕过付费墙，也不抓取任何需要认证才能看的内容。
剩余部分的正规路径见 README「闭源全文」一节：出版商的 TDM（文本数据挖掘）接口，
用订阅方自己的 key，例如 Elsevier TDM（MIA）、Wiley TDM、Springer Nature TDM、IEEE。
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from dataclasses import dataclass

from pydantic import BaseModel, Field

from litsearch.dedupe import CanonicalRecord
from litsearch.sources.base import HttpClient, SourceError

UNPAYWALL = "https://api.unpaywall.org/v2"
EUROPEPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
CROSSREF = "https://api.crossref.org/works"

#: 版本可信度：出版版 > 接收版 > 投稿版（预印本）
VERSION_RANK = {
    "publishedVersion": 3,
    "acceptedVersion": 2,
    "submittedVersion": 1,
}
HOST_RANK = {"publisher": 3, "pmc": 3, "repository": 2, "arxiv": 1}


class FullTextLocation(BaseModel):
    """一个可合法获取的全文位置。"""

    url: str
    host: str  # publisher | repository | pmc | arxiv
    version: str = "unknown"
    is_pdf: bool = False
    license: str | None = None
    #: 哪个解析器找到的，便于回溯
    found_by: str = ""

    @property
    def rank(self) -> tuple[int, int, int]:
        return (
            VERSION_RANK.get(self.version, 0),
            HOST_RANK.get(self.host, 0),
            1 if self.is_pdf else 0,
        )


class Resolution(BaseModel):
    """一条记录的全文可获取性结论。"""

    key: str
    doi: str | None = None
    title: str = ""
    venue: str | None = None
    locations: list[FullTextLocation] = Field(default_factory=list)
    #: open = 有合法免费全文；tdm = 需订阅方 TDM 接口；unavailable = 两者皆无
    status: str = "unavailable"
    notes: list[str] = Field(default_factory=list)

    @property
    def best(self) -> FullTextLocation | None:
        return max(self.locations, key=lambda item: item.rank) if self.locations else None


def _dedupe_locations(locations: Iterable[FullTextLocation]) -> list[FullTextLocation]:
    seen: dict[str, FullTextLocation] = {}
    for location in locations:
        if not location.url:
            continue
        key = location.url.rstrip("/")
        if key not in seen or location.rank > seen[key].rank:
            seen[key] = location
    return sorted(seen.values(), key=lambda item: item.rank, reverse=True)


class UnpaywallResolver:
    """Unpaywall：DOI → 全部已知的合法 OA 位置。免费，仅需邮箱。"""

    name = "unpaywall"

    def __init__(self, email: str) -> None:
        self.email = email

    async def resolve(self, record: CanonicalRecord, client: HttpClient) -> list[FullTextLocation]:
        doi = record.identifiers.get("doi")
        if not doi:
            return []
        try:
            payload = await client.get_json(
                f"{UNPAYWALL}/{doi}", {"email": self.email}, source=self.name
            )
        except SourceError:
            return []
        if not isinstance(payload, dict) or not payload.get("is_oa"):
            return []

        locations = []
        for item in payload.get("oa_locations") or []:
            url = item.get("url_for_pdf") or item.get("url")
            if not url:
                continue
            locations.append(
                FullTextLocation(
                    url=url,
                    host=str(item.get("host_type") or "repository"),
                    version=str(item.get("version") or "unknown"),
                    is_pdf=bool(item.get("url_for_pdf")),
                    license=item.get("license"),
                    found_by=self.name,
                )
            )
        return locations


class EuropePMCResolver:
    """Europe PMC：PMC 全文与开放获取链接，覆盖 NIH/Wellcome 资助的论文。"""

    name = "europepmc"

    async def resolve(self, record: CanonicalRecord, client: HttpClient) -> list[FullTextLocation]:
        doi, pmid = record.identifiers.get("doi"), record.identifiers.get("pmid")
        if not (doi or pmid):
            return []
        query = f'DOI:"{doi}"' if doi else f"EXT_ID:{pmid} AND SRC:MED"
        try:
            payload = await client.get_json(
                EUROPEPMC,
                {"query": query, "format": "json", "pageSize": 1, "resultType": "core"},
                source=self.name,
            )
        except SourceError:
            return []

        results = (payload.get("resultList") or {}).get("result") or []
        if not results:
            return []
        item = results[0]
        if item.get("isOpenAccess") != "Y" and not item.get("pmcid"):
            return []

        locations = []
        for link in (item.get("fullTextUrlList") or {}).get("fullTextUrl") or []:
            if url := link.get("url"):
                locations.append(
                    FullTextLocation(
                        url=url,
                        host="pmc" if "pmc" in url.lower() else "publisher",
                        version="publishedVersion",
                        is_pdf=link.get("documentStyle") == "pdf",
                        found_by=self.name,
                    )
                )
        return locations


class ArxivLinkResolver:
    """语料里已合并的 arXiv 身份直接给出预印本全文——无需再打网络。

    这是医工交叉领域最划算的一条：方法类论文（TMI/MIA）大量有预印本，
    而合并阶段已经把预印本与正式版归并到同一条规范记录上了。
    """

    name = "arxiv"

    async def resolve(self, record: CanonicalRecord, client: HttpClient) -> list[FullTextLocation]:
        arxiv_id = record.identifiers.get("arxiv")
        if not arxiv_id:
            return []
        return [
            FullTextLocation(
                url=f"https://arxiv.org/pdf/{arxiv_id}",
                host="arxiv",
                version="submittedVersion",
                is_pdf=True,
                license="arxiv",
                found_by=self.name,
            )
        ]


class CrossrefTdmResolver:
    """Crossref 的 text-mining 链接。

    这些链接本身通常仍需订阅方凭证才能取到正文，因此只用来把记录标为
    ``tdm``——即"你的机构有订阅就能自动化拿到"，而不是当作开放全文。
    """

    name = "crossref-tdm"

    def __init__(self, email: str | None = None) -> None:
        self.email = email

    async def resolve_tdm(self, record: CanonicalRecord, client: HttpClient) -> list[str]:
        doi = record.identifiers.get("doi")
        if not doi:
            return []
        try:
            payload = await client.get_json(
                f"{CROSSREF}/{doi}", {"mailto": self.email}, source=self.name
            )
        except SourceError:
            return []
        message = payload.get("message") or {}
        return [
            link["URL"]
            for link in (message.get("link") or [])
            if link.get("URL")
            and link.get("intended-application") in {"text-mining", "similarity-checking"}
        ]


@dataclass
class FullTextSummary:
    total: int
    open_access: int
    tdm_only: int
    unavailable: int

    @property
    def open_rate(self) -> float:
        return self.open_access / self.total if self.total else 0.0


async def resolve_fulltext(
    records: list[CanonicalRecord],
    clients: dict[str, HttpClient],
    *,
    email: str,
    concurrency: int = 4,
) -> list[Resolution]:
    """对每条记录逐级解析合法全文位置。"""
    unpaywall = UnpaywallResolver(email)
    europepmc = EuropePMCResolver()
    arxiv = ArxivLinkResolver()
    crossref = CrossrefTdmResolver(email)
    semaphore = asyncio.Semaphore(concurrency)

    async def one(record: CanonicalRecord) -> Resolution:
        async with semaphore:
            resolution = Resolution(
                key=record.key,
                doi=record.identifiers.get("doi"),
                title=record.title,
                venue=record.venue,
            )
            found: list[FullTextLocation] = []
            found += await arxiv.resolve(record, clients["arxiv"])
            found += await unpaywall.resolve(record, clients["unpaywall"])
            if not found:
                found += await europepmc.resolve(record, clients["europepmc"])

            resolution.locations = _dedupe_locations(found)
            if resolution.locations:
                resolution.status = "open"
                return resolution

            if tdm := await crossref.resolve_tdm(record, clients["crossref"]):
                resolution.status = "tdm"
                resolution.notes.append(
                    f"出版商提供 TDM 链接 {len(tdm)} 条，需订阅方凭证：{tdm[0]}"
                )
                return resolution

            resolution.status = "unavailable"
            return resolution

    return list(await asyncio.gather(*(one(record) for record in records)))


def summarize(resolutions: list[Resolution]) -> FullTextSummary:
    counts = {"open": 0, "tdm": 0, "unavailable": 0}
    for item in resolutions:
        counts[item.status] = counts.get(item.status, 0) + 1
    return FullTextSummary(
        total=len(resolutions),
        open_access=counts["open"],
        tdm_only=counts["tdm"],
        unavailable=counts["unavailable"],
    )


def institutional_access_csv(resolutions: list[Resolution]) -> str:
    """拿不到开放全文的清单，交给机构订阅或出版商 TDM 接口处理。"""
    lines = ["status,doi,venue,title,note"]
    for item in resolutions:
        if item.status == "open":
            continue
        title = item.title.replace('"', "'")
        venue = (item.venue or "").replace('"', "'")
        note = (item.notes[0] if item.notes else "").replace('"', "'")
        lines.append(f'{item.status},{item.doi or ""},"{venue}","{title}","{note}"')
    return "\n".join(lines) + "\n"
