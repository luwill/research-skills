"""`.env` 加载与凭据解析。

凭据只从环境或 `.env` 读，绝不写进代码或协议文件。``.env`` 的容错要足够——
用户手写的文件里 `KEY = value`（等号两边有空格）、行尾注释、引号都很常见，
解析不到就会变成"没配 key"，然后源静默降级成匿名限速，最后表现为少召回。
"""

from __future__ import annotations

from litsearch.envfile import load_env_file
from litsearch.sources.registry import Credentials


class TestLoadEnvFile:
    def test_reads_plain_pairs(self, tmp_path):
        path = tmp_path / ".env"
        path.write_text("A=1\nB=2\n", encoding="utf-8")

        assert load_env_file(path) == {"A": "1", "B": "2"}

    def test_tolerates_spaces_around_the_equals_sign(self, tmp_path):
        """手写的 .env 里 `KEY = value` 很常见，按裸 split 会得到带空格的 key。"""
        path = tmp_path / ".env"
        path.write_text("OPENALEX_API = axJ123\n", encoding="utf-8")

        assert load_env_file(path) == {"OPENALEX_API": "axJ123"}

    def test_strips_quotes_and_export_prefix(self, tmp_path):
        path = tmp_path / ".env"
        path.write_text("export A=\"q\"\nB='s'\n", encoding="utf-8")

        assert load_env_file(path) == {"A": "q", "B": "s"}

    def test_ignores_comments_and_blank_lines(self, tmp_path):
        path = tmp_path / ".env"
        path.write_text("# 注释\n\nA=1\n", encoding="utf-8")

        assert load_env_file(path) == {"A": "1"}

    def test_a_line_without_an_equals_sign_is_skipped(self, tmp_path):
        path = tmp_path / ".env"
        path.write_text("garbage\nA=1\n", encoding="utf-8")

        assert load_env_file(path) == {"A": "1"}

    def test_a_missing_file_is_not_an_error(self, tmp_path):
        assert load_env_file(tmp_path / "nope.env") == {}

    def test_values_containing_equals_are_preserved(self, tmp_path):
        """base64 结尾的 `=` 很常见，只能按第一个等号切。"""
        path = tmp_path / ".env"
        path.write_text("A=abc==\n", encoding="utf-8")

        assert load_env_file(path) == {"A": "abc=="}


class TestCredentials:
    def test_openalex_key_is_picked_up_from_the_env_file(self, tmp_path, monkeypatch):
        monkeypatch.delenv("LITSEARCH_OPENALEX_API_KEY", raising=False)
        path = tmp_path / ".env"
        path.write_text("OPENALEX_API = axJsecret\n", encoding="utf-8")

        credentials = Credentials.from_env(env_file=path)

        assert credentials.api_keys["openalex"] == "axJsecret"

    def test_the_real_environment_wins_over_the_file(self, tmp_path, monkeypatch):
        """显式导出的环境变量优先——临时换 key 不该被文件里的旧值盖掉。"""
        monkeypatch.setenv("LITSEARCH_OPENALEX_API_KEY", "from-env")
        path = tmp_path / ".env"
        path.write_text("OPENALEX_API=from-file\n", encoding="utf-8")

        credentials = Credentials.from_env(env_file=path)

        assert credentials.api_keys["openalex"] == "from-env"

    def test_deepseek_key_is_read(self, tmp_path, monkeypatch):
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        path = tmp_path / ".env"
        path.write_text("DEEPSEEK_API_KEY=sk-abc\n", encoding="utf-8")

        assert Credentials.from_env(env_file=path).api_keys["deepseek"] == "sk-abc"

    def test_absent_keys_simply_do_not_appear(self, tmp_path):
        credentials = Credentials.from_env(env_file=tmp_path / "nope.env")

        assert "openalex" not in credentials.api_keys


class TestTypesafeKey:
    """判定 API 的密钥走和各检索源一样的别名机制。

    认不出 key 的后果在这里比在检索源更糟：检索源会静默降级成匿名限速，
    而判定 API 直接 401——整轮中止，白跑一次 dry-run。
    """

    def test_the_project_prefixed_name_wins(self, tmp_path, monkeypatch):
        monkeypatch.setenv("LITSEARCH_TYPESAFE_API_KEY", "project")
        monkeypatch.setenv("TYPESAFE_API_KEY", "vendor")

        creds = Credentials.from_env(tmp_path / "missing.env")

        assert creds.api_keys["typesafe"] == "project"

    def test_the_vendor_name_is_accepted_too(self, tmp_path, monkeypatch):
        """TypeSafe 官方文档教的就是 TYPESAFE_API_KEY，用户多半已经这么配了。"""
        monkeypatch.delenv("LITSEARCH_TYPESAFE_API_KEY", raising=False)
        monkeypatch.setenv("TYPESAFE_API_KEY", "vendor")

        creds = Credentials.from_env(tmp_path / "missing.env")

        assert creds.api_keys["typesafe"] == "vendor"

    def test_it_can_come_from_the_env_file(self, tmp_path, monkeypatch):
        monkeypatch.delenv("LITSEARCH_TYPESAFE_API_KEY", raising=False)
        monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
        path = tmp_path / ".env"
        path.write_text("TYPESAFE_API_KEY=from-file\n", encoding="utf-8")

        creds = Credentials.from_env(path)

        assert creds.api_keys["typesafe"] == "from-file"

    def test_absent_key_is_simply_absent_not_an_empty_string(self, tmp_path, monkeypatch):
        monkeypatch.delenv("LITSEARCH_TYPESAFE_API_KEY", raising=False)
        monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)

        creds = Credentials.from_env(tmp_path / "missing.env")

        assert "typesafe" not in (creds.api_keys or {})
