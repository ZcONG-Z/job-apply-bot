"""适配器注册表：按 URL 路由到适配器。"""

from __future__ import annotations

from fnmatch import fnmatch
from pathlib import Path
from urllib.parse import urlparse

from job_apply_bot.adapters.base import Adapter, load_adapter


def match_url(patterns: list[str], url: str) -> bool:
    """URL 是否命中任一 glob 模式。

    同时尝试整条 URL 与仅主机名（不带协议）匹配，覆盖
    ``*.mokahr.com/campus_apply/*`` 和 ``app.mokahr.com`` 两种写法。
    """
    host = urlparse(url).netloc
    return any(fnmatch(url, pattern) or fnmatch(host, pattern) for pattern in patterns)


class AdapterRegistry:
    """加载站点目录下的所有适配器，并按 URL 查找。"""

    def __init__(self, site_dir: Path) -> None:
        self.site_dir = site_dir
        self._adapters: dict[str, Adapter] = {}
        self._errors: dict[str, str] = {}

    def load(self) -> None:
        self._adapters = {}
        self._errors = {}
        if not self.site_dir.is_dir():
            return
        for path in sorted(self.site_dir.glob("*.yaml")):
            try:
                self._adapters[path.stem] = load_adapter(path)
            except Exception as exc:  # noqa: BLE001 - 单个适配器坏掉不应拖垮整个注册表
                self._errors[path.name] = str(exc)

    def find(self, url: str) -> Adapter | None:
        for adapter in self._adapters.values():
            if match_url(adapter.url_patterns, url):
                return adapter
        return None

    def names(self) -> list[str]:
        return sorted(self._adapters)

    @property
    def errors(self) -> dict[str, str]:
        return dict(self._errors)
