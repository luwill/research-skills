"""LLM 提供方解析。**不绑定单一厂商。**

任何 OpenAI 兼容端点都可以用：DeepSeek / Kimi / Qwen / OpenRouter / 本地 Ollama。
DeepSeek 只是 README 里的推荐默认值，不是依赖——绑定单一厂商的工具，
那个厂商改一次 API 就死一次。

三个环境变量：

- ``LITSEARCH_LLM_MODEL``    模型名
- ``LITSEARCH_LLM_BASE_URL`` 端点（内置模型可省略）
- ``LITSEARCH_LLM_API_KEY``  密钥

**价目只内置实测过的。** 猜出来的价格会让 ``--dry-run`` 给出一个看起来
精确的假数字，而人是照着那个数字决定跑不跑的。不知道就报"未知"。
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

#: 兼容旧配置：这些键名仍然认，但新配置一律用 LITSEARCH_LLM_API_KEY
LEGACY_KEY_ENV = ("DEEPSEEK_API_KEY",)

ENV_MODEL = "LITSEARCH_LLM_MODEL"
ENV_BASE_URL = "LITSEARCH_LLM_BASE_URL"
ENV_API_KEY = "LITSEARCH_LLM_API_KEY"
ENV_PRICING = "LITSEARCH_PRICING"


class ProviderError(RuntimeError):
    """提供方配置不完整或无法解析。"""


@dataclass(frozen=True, slots=True)
class Pricing:
    """每百万 token 美元价。三档缺任意一档即视为价目未知。"""

    input_hit: float
    input_miss: float
    output: float


@dataclass(frozen=True, slots=True)
class Provider:
    """一个可用的模型端点。"""

    model: str
    base_url: str
    #: ``None`` 表示价目未知——估算必须如实报"未知"，不能当成 0
    pricing: Pricing | None = None
    #: v4 系列默认开思考，而思考模式与强制工具调用互斥，必须显式关掉
    disable_thinking: bool = False
    #: 端点是否支持自动前缀缓存。不支持时估算不能把 system 前缀算成命中
    prefix_cache: bool = True

    @property
    def priced(self) -> bool:
        return self.pricing is not None


#: 内置价目。**只有实测跑过的才写在这里。**
#: 其它厂商用 LITSEARCH_LLM_BASE_URL 指过去即可，价目走 --pricing 文件补。
BUILTIN: dict[str, Provider] = {
    "deepseek-v4-pro": Provider(
        model="deepseek-v4-pro",
        # strict 工具调用只在 beta 端点可用
        base_url="https://api.deepseek.com/beta",
        pricing=Pricing(input_hit=0.003625, input_miss=0.435, output=0.87),
        disable_thinking=True,
    ),
    "deepseek-v4-flash": Provider(
        model="deepseek-v4-flash",
        base_url="https://api.deepseek.com/beta",
        pricing=Pricing(input_hit=0.0028, input_miss=0.14, output=0.28),
        disable_thinking=True,
    ),
}

DEFAULT_MODEL = "deepseek-v4-flash"

#: 宿主模型：不走 API，由 Claude Code 本身判定。零配置，不需要任何 key。
HOST_MODEL = "host"


def load_pricing(path: Path) -> dict[str, Pricing]:
    """从 JSON 载入用户自备价目表。

    格式：``{"<model>": {"input_hit": 0.01, "input_miss": 1.0, "output": 2.0}}``
    """
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ProviderError(f"无法读取价目表 {path}：{error}") from error
    table: dict[str, Pricing] = {}
    for model, row in payload.items():
        try:
            table[model] = Pricing(
                input_hit=float(row["input_hit"]),
                input_miss=float(row["input_miss"]),
                output=float(row["output"]),
            )
        except (KeyError, TypeError, ValueError) as error:
            raise ProviderError(
                f"价目表里 {model!r} 缺字段或类型不对，需要 input_hit/input_miss/output"
            ) from error
    return table


def api_key_from(env: Mapping[str, str]) -> str | None:
    """取密钥。新键名优先，旧键名仍然认。"""
    if key := env.get(ENV_API_KEY):
        return key
    for name in LEGACY_KEY_ENV:
        if key := env.get(name):
            return key
    return None


def resolve_provider(
    model: str | None = None,
    *,
    env: Mapping[str, str] | None = None,
    pricing: Mapping[str, Pricing] | None = None,
) -> Provider:
    """解析出要用哪个模型、哪个端点、什么价目。

    优先级：显式参数 > 环境变量 > 内置默认。
    未知模型必须配 ``LITSEARCH_LLM_BASE_URL``，否则报错而不是猜一个端点。
    """
    env = os.environ if env is None else env
    name = model or env.get(ENV_MODEL) or DEFAULT_MODEL
    if name == HOST_MODEL:
        return Provider(model=HOST_MODEL, base_url="", pricing=None, prefix_cache=False)

    base_url = env.get(ENV_BASE_URL)
    extra = dict(pricing or {})
    if path := env.get(ENV_PRICING):
        extra = {**load_pricing(Path(path)), **extra}

    if builtin := BUILTIN.get(name):
        return Provider(
            model=name,
            base_url=base_url or builtin.base_url,
            pricing=extra.get(name, builtin.pricing),
            disable_thinking=builtin.disable_thinking,
            prefix_cache=builtin.prefix_cache,
        )

    if not base_url:
        raise ProviderError(
            f"不认识模型 {name!r}，且没有设 {ENV_BASE_URL}。\n"
            f"内置：{', '.join(sorted(BUILTIN))}、{HOST_MODEL}\n"
            f"用其它厂商请设 {ENV_BASE_URL}（任何 OpenAI 兼容端点都可以）。"
        )
    # 未知端点：不猜它支不支持前缀缓存，也不猜价目。
    return Provider(model=name, base_url=base_url, pricing=extra.get(name), prefix_cache=False)


def describe(provider: Provider) -> str:
    """一行说明，用在 --dry-run 抬头。"""
    if provider.model == HOST_MODEL:
        return "宿主模型（Claude Code 本身判定，无需 API key）"
    price = (
        f"未命中 ${provider.pricing.input_miss}/M · 输出 ${provider.pricing.output}/M"
        if provider.pricing
        else "**价目未知**（未内置且未提供价目表，无法估算金额）"
    )
    return f"{provider.model} @ {provider.base_url} ｜ {price}"
