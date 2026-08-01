"""`.env` 读取。

不引第三方依赖：需要的只是几行容错解析，而容错本身才是重点。
用户手写的 `.env` 里 `KEY = value`（等号两边有空格）、`export KEY=...`、
带引号的值都很常见。解析不到的后果不是报错，而是**静默降级**——
源退回匿名限速、配额提前耗尽，最后表现为少召回。所以宁可解析得宽一点。
"""

from __future__ import annotations

from pathlib import Path


def load_env_file(path: str | Path) -> dict[str, str]:
    """读取 `.env`。文件不存在返回空字典——没配凭据不是错误。"""
    target = Path(path)
    try:
        text = target.read_text(encoding="utf-8")
    except OSError:
        return {}

    values: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        line = line.removeprefix("export ").lstrip()
        # 只按**第一个**等号切：base64 值常以 = 结尾
        key, _, value = line.partition("=")
        key = key.strip()
        if not key:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key] = value
    return values
