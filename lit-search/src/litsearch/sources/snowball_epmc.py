"""滚雪球用的 Europe PMC 源。

检索式由 ``snowball.py`` 从语料生成（``CITES:<pmid>_MED`` 或 ``DOI:"…"`` 的 OR 批），
其余一切——cursorMark 翻页、原始响应落盘、失败必须显形——与常规检索完全相同，
因此直接继承 ``EuropePMCSource``，只换一个源名。

换源名不是为了好看：``lit validate`` 的"来源独有贡献"要能回答
"引文闭包到底补回了多少关键词检索查不到的论文"。混进 europepmc 就问不出来了。

父类的 ``_query()`` 会把检索式包上 ``FIRST_PDATE:[采集窗口]``——这对滚雪球同样正确：
窗口外的被引文献不是本次综述的纳入对象，在源头挡掉可以省下大量筛选成本。
"""

from __future__ import annotations

from litsearch.sources.europepmc import EuropePMCSource


class SnowballSource(EuropePMCSource):
    name = "snowball"
