"""提供方解析与深度分档的测试。

红线：**价目未知必须报"未知"，不能当成 0。**
一个说 $0.00 的 dry-run 比一个说"算不出来"的危险得多——人是照着它决定跑不跑的。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from litsearch.profiles import (
    DEFAULT_DEPTH,
    TRUNK_SOURCES,
    Depth,
    profile_for,
    sources_for,
    summary_table,
)
from litsearch.providers import (
    BUILTIN,
    DEFAULT_MODEL,
    ENV_API_KEY,
    ENV_BASE_URL,
    ENV_MODEL,
    ENV_PRICING,
    HOST_MODEL,
    Pricing,
    ProviderError,
    api_key_from,
    describe,
    load_pricing,
    resolve_provider,
)


class TestResolveProvider:
    def test_default_is_a_builtin(self) -> None:
        provider = resolve_provider(env={})
        assert provider.model == DEFAULT_MODEL
        assert provider.priced

    def test_explicit_model_wins_over_env(self) -> None:
        provider = resolve_provider("deepseek-v4-pro", env={ENV_MODEL: "deepseek-v4-flash"})
        assert provider.model == "deepseek-v4-pro"

    def test_env_model(self) -> None:
        assert resolve_provider(env={ENV_MODEL: "deepseek-v4-pro"}).model == "deepseek-v4-pro"

    def test_base_url_override(self) -> None:
        provider = resolve_provider(
            "deepseek-v4-flash", env={ENV_BASE_URL: "https://proxy.example/v1"}
        )
        assert provider.base_url == "https://proxy.example/v1"

    def test_unknown_model_needs_a_base_url(self) -> None:
        """不猜端点。猜错会把请求发到一个不存在的地方，报错信息还毫无线索。"""
        with pytest.raises(ProviderError) as error:
            resolve_provider("kimi-k3", env={})
        assert ENV_BASE_URL in str(error.value)

    def test_unknown_model_with_base_url_works_but_is_unpriced(self) -> None:
        provider = resolve_provider("kimi-k3", env={ENV_BASE_URL: "https://api.moonshot.cn/v1"})
        assert provider.pricing is None
        assert not provider.priced

    def test_unknown_endpoint_does_not_assume_prefix_caching(self) -> None:
        """不知道对方支不支持前缀缓存时，不能把 system 前缀算成命中——那会低估成本。"""
        provider = resolve_provider("x", env={ENV_BASE_URL: "https://e.example/v1"})
        assert provider.prefix_cache is False

    def test_host_model_needs_no_endpoint(self) -> None:
        provider = resolve_provider(HOST_MODEL, env={})
        assert provider.base_url == ""
        assert provider.pricing is None

    def test_thinking_flag_is_carried(self) -> None:
        """v4 默认开思考，而思考模式与强制工具调用互斥。"""
        assert resolve_provider("deepseek-v4-pro", env={}).disable_thinking is True


class TestPricing:
    def test_user_pricing_fills_an_unknown_model(self, tmp_path: Path) -> None:
        path = tmp_path / "pricing.json"
        path.write_text(
            json.dumps({"kimi-k3": {"input_hit": 0.01, "input_miss": 1.0, "output": 2.0}}),
            encoding="utf-8",
        )
        provider = resolve_provider(
            "kimi-k3", env={ENV_BASE_URL: "https://e.example/v1", ENV_PRICING: str(path)}
        )
        assert provider.pricing == Pricing(0.01, 1.0, 2.0)

    def test_user_pricing_overrides_a_builtin(self, tmp_path: Path) -> None:
        """厂商降价时用户能自己改，不用等仓库更新。"""
        path = tmp_path / "pricing.json"
        path.write_text(
            json.dumps(
                {"deepseek-v4-flash": {"input_hit": 0.0, "input_miss": 0.07, "output": 0.14}}
            ),
            encoding="utf-8",
        )
        provider = resolve_provider("deepseek-v4-flash", env={ENV_PRICING: str(path)})
        assert provider.pricing.input_miss == 0.07

    def test_incomplete_pricing_row_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "pricing.json"
        path.write_text(json.dumps({"m": {"input_miss": 1.0}}), encoding="utf-8")
        with pytest.raises(ProviderError):
            load_pricing(path)

    def test_unreadable_pricing_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ProviderError):
            load_pricing(tmp_path / "nope.json")


class TestApiKey:
    def test_new_env_name(self) -> None:
        assert api_key_from({ENV_API_KEY: "sk-new"}) == "sk-new"

    def test_legacy_name_still_works(self) -> None:
        assert api_key_from({"DEEPSEEK_API_KEY": "sk-old"}) == "sk-old"

    def test_new_name_wins(self) -> None:
        assert api_key_from({ENV_API_KEY: "sk-new", "DEEPSEEK_API_KEY": "sk-old"}) == "sk-new"

    def test_absent(self) -> None:
        assert api_key_from({}) is None


class TestDescribe:
    def test_unpriced_provider_says_so_loudly(self) -> None:
        provider = resolve_provider("x", env={ENV_BASE_URL: "https://e.example/v1"})
        assert "价目未知" in describe(provider)

    def test_priced_provider_shows_the_numbers(self) -> None:
        assert "0.435" in describe(resolve_provider("deepseek-v4-pro", env={}))

    def test_host_needs_no_key(self) -> None:
        assert "无需 API key" in describe(resolve_provider(HOST_MODEL, env={}))


class TestDepthProfiles:
    def test_every_depth_has_a_profile(self) -> None:
        for depth in Depth:
            assert profile_for(depth).label

    def test_quick_does_not_snowball(self) -> None:
        assert profile_for(Depth.QUICK).runs_snowball is False

    def test_systematic_runs_to_saturation(self) -> None:
        assert profile_for(Depth.SYSTEMATIC).snowball_rounds is None

    def test_depths_are_monotonic_in_coverage(self) -> None:
        quick = set(profile_for(Depth.QUICK).sources)
        standard = set(profile_for(Depth.STANDARD).sources)
        systematic = set(profile_for(Depth.SYSTEMATIC).sources)
        assert quick <= standard <= systematic

    def test_default_is_standard(self) -> None:
        assert DEFAULT_DEPTH is Depth.STANDARD

    def test_unknown_depth_raises(self) -> None:
        with pytest.raises(ValueError):
            profile_for("deep")

    def test_profile_states_its_cost(self) -> None:
        """选档时要看到的是时间和钱，不是源清单。"""
        item = profile_for(Depth.SYSTEMATIC)
        assert item.wall_clock and item.api_cost and item.scale

    def test_host_cost_is_never_advertised_as_free(self) -> None:
        """宿主后端不需要 key，但**不是免费的**——实测 60 条 $0.295 等价成本。
        写 "$0" 会让人按一个假前提去选 systematic。"""
        for depth in Depth:
            assert profile_for(depth).host_cost
            assert profile_for(depth).host_cost.strip() != "$0"

    def test_summary_table_covers_all_depths(self) -> None:
        table = summary_table()
        assert all(depth.value in table for depth in Depth)


class TestSourcesFor:
    def test_intersects_with_what_the_protocol_enabled(self) -> None:
        assert sources_for(Depth.QUICK, enabled=["openalex", "cvf"]) == ["openalex"]

    def test_never_enables_a_source_the_protocol_disabled(self) -> None:
        """档位只做减法——否则用户会拿到一份自己没声明过的检索策略。"""
        assert sources_for(Depth.SYSTEMATIC, enabled=["openalex"]) == ["openalex"]

    def test_preserves_the_protocol_order(self) -> None:
        enabled = ["pubmed", "openalex", "arxiv"]
        assert sources_for(Depth.STANDARD, enabled=enabled) == enabled

    def test_quick_keeps_only_trunk_sources(self) -> None:
        every = [*TRUNK_SOURCES, "cvf", "openreview", "grey"]
        assert sources_for(Depth.QUICK, enabled=every) == list(TRUNK_SOURCES)


def test_builtin_models_are_all_priced() -> None:
    """内置的必须有实测价目；不确定的就别写进 BUILTIN。"""
    assert all(provider.priced for provider in BUILTIN.values())
