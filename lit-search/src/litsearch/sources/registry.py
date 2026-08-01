"""源注册表与限速配置。

每个源的间隔按其官方指引设定。写在一处，避免某个源被无意中打爆导致 IP 被封，
那会让整条流水线在半路变成"静默少召回"——这是本项目最不能接受的失败模式。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import httpx

from litsearch.sources.arxiv import ArxivSource
from litsearch.sources.base import (
    DEFAULT_MAX_ATTEMPTS,
    DEFAULT_TIMEOUT_SECONDS,
    HttpClient,
    RateLimiter,
    Source,
)
from litsearch.sources.crossref import CrossrefVolumeSource
from litsearch.sources.cvf import CvfSource
from litsearch.sources.europepmc import EuropePMCSource
from litsearch.sources.grey import GreySource
from litsearch.sources.openalex import OpenAlexSource
from litsearch.sources.openreview import OpenReviewSource
from litsearch.sources.pubmed import PubMedSource
from litsearch.sources.snowball_epmc import SnowballSource

#: 各源请求间隔（秒）。arXiv 官方明确要求 3 秒；PubMed 无 key 3 req/s、有 key 10 req/s。
RATE_LIMITS: dict[str, float] = {
    # OpenAlex 名义上 polite pool 10 req/s，但实测 0.12s 间隔连续跑会吃 429。
    # 采集是一次性的批处理任务，慢一点远比中途被限流导致静默少召回划算。
    "openalex": 0.5,
    "pubmed": 0.36,
    "pubmed_with_key": 0.11,
    "europepmc": 0.25,
    # arXiv 官方要求 3 秒；实测连续跑仍会吃 429，留一点余量
    "arxiv": 4.0,
    "crossref": 0.10,
    # 滚雪球走 Europe PMC，沿用同一限速
    "snowball": 0.25,
    "semantic_scholar": 1.1,
    "openreview": 0.5,
    "cvf": 1.0,
    "grey": 1.0,
    # doi.org 的内容协商由 Crossref 后端提供，沿用 Crossref 的礼貌间隔。
    # 并发在调用方另行限制——这里只管两次请求之间的最小间隔。
    "doi.org": 0.05,
}

#: 各源的重试次数。arXiv 会间歇性 429，多试几次比中途放弃少召回划算。
MAX_ATTEMPTS: dict[str, int] = {"arxiv": 6}

_FACTORIES: dict[str, type] = {
    "openalex": OpenAlexSource,
    "pubmed": PubMedSource,
    "europepmc": EuropePMCSource,
    "arxiv": ArxivSource,
    "cvf": CvfSource,
    "openreview": OpenReviewSource,
    "grey": GreySource,
    # crossref 的 role 是 enrich，不参与召回；由 `lit proceedings` 单独驱动
    "crossref": CrossrefVolumeSource,
    # snowball 的检索式由语料生成而非协议，由 `lit snowball` 单独驱动
    "snowball": SnowballSource,
}


#: 每个凭据可以有多个惯用名。项目自己的 `LITSEARCH_*` 排在前面，
#: 后面是各家 SDK/文档里常见的写法——用户按哪种习惯写都能被认出来。
#: 认不出来的后果是**静默降级**成匿名限速，最后表现为少召回。
KEY_ALIASES: dict[str, tuple[str, ...]] = {
    "pubmed": ("LITSEARCH_NCBI_API_KEY", "NCBI_API_KEY"),
    "openalex": ("LITSEARCH_OPENALEX_API_KEY", "OPENALEX_API_KEY", "OPENALEX_API"),
    "semantic_scholar": ("LITSEARCH_S2_API_KEY", "S2_API_KEY", "SEMANTIC_SCHOLAR_API_KEY"),
    "deepseek": ("LITSEARCH_DEEPSEEK_API_KEY", "DEEPSEEK_API_KEY", "DEEPSEEK_API"),
}
EMAIL_ALIASES = ("LITSEARCH_CONTACT_EMAIL", "CONTACT_EMAIL")
DEFAULT_ENV_FILE = ".env"


@dataclass(frozen=True)
class Credentials:
    contact_email: str | None = None
    api_keys: dict[str, str] | None = None

    @classmethod
    def from_env(cls, env_file: str | Path | None = None) -> Credentials:
        """从真实环境变量与 `.env` 读取凭据。

        真实环境变量**优先**于文件：临时导出一个 key 去试，不该被文件里的旧值盖掉。
        """
        from litsearch.envfile import load_env_file

        from_file = load_env_file(env_file or DEFAULT_ENV_FILE)

        def lookup(names: tuple[str, ...]) -> str | None:
            for name in names:
                if value := (os.environ.get(name) or from_file.get(name)):
                    return value.strip()
            return None

        keys = {
            service: value for service, names in KEY_ALIASES.items() if (value := lookup(names))
        }
        return cls(contact_email=lookup(EMAIL_ALIASES), api_keys=keys)


def available_sources() -> set[str]:
    return set(_FACTORIES)


def build_source(name: str) -> Source:
    if name not in _FACTORIES:
        raise KeyError(f"未实现的源：{name}；已实现 {sorted(_FACTORIES)}")
    return _FACTORIES[name]()


def rate_limit_for(name: str, credentials: Credentials) -> float:
    if name == "pubmed" and (credentials.api_keys or {}).get("pubmed"):
        return RATE_LIMITS["pubmed_with_key"]
    return RATE_LIMITS.get(name, 1.0)


def build_client(name: str, credentials: Credentials) -> tuple[HttpClient, httpx.AsyncClient]:
    """返回 (封装客户端, 底层 httpx 客户端)；调用方负责关闭后者。"""
    transport = httpx.AsyncHTTPTransport(retries=0)
    raw = httpx.AsyncClient(
        timeout=DEFAULT_TIMEOUT_SECONDS,
        transport=transport,
        follow_redirects=True,
        headers={"User-Agent": _user_agent(credentials)},
    )
    limiter = RateLimiter(min_interval=rate_limit_for(name, credentials))
    client = HttpClient(
        raw,
        rate_limiter=limiter,
        max_attempts=MAX_ATTEMPTS.get(name, DEFAULT_MAX_ATTEMPTS),
    )
    return client, raw


def _user_agent(credentials: Credentials) -> str:
    base = "litsearch/0.1"
    return f"{base} (mailto:{credentials.contact_email})" if credentials.contact_email else base
