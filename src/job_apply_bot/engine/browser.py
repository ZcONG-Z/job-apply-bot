"""Playwright 会话管理。

设计要点：

- 用 ``launch_persistent_context`` 而不是普通 context：它自带 user_data_dir，
  cookie / localStorage 会落到磁盘，人工登录一次之后下次自动带上。
- ``headed`` 模式用于人工登录和人工核对；测试里用 headless。
- 登录态还额外提供 ``save_state`` 导出 storage_state，便于适配器复用。
"""

from __future__ import annotations

from pathlib import Path
from typing import Self

from playwright.sync_api import BrowserContext, Page, Playwright, sync_playwright

DEFAULT_VIEWPORT = {"width": 1440, "height": 900}


class BrowserSession:
    """管理浏览器生命周期与会话状态。可用作上下文管理器。"""

    def __init__(
        self,
        auth_dir: Path,
        *,
        headed: bool = True,
        viewport: dict[str, int] | None = None,
    ) -> None:
        self.auth_dir = auth_dir
        self.headed = headed
        self.viewport = viewport or DEFAULT_VIEWPORT
        self._playwright: Playwright | None = None
        self.context: BrowserContext | None = None

    def __enter__(self) -> Self:
        self.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def start(self) -> None:
        self.auth_dir.mkdir(parents=True, exist_ok=True)
        self._playwright = sync_playwright().start()
        # persistent context：cookie 落盘到 auth_dir/profile，人工登录可跨运行复用
        self.context = self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.auth_dir / "profile"),
            headless=not self.headed,
            viewport=self.viewport,
        )

    def new_page(self, url: str | None = None) -> Page:
        assert self.context is not None, "先调用 start()"
        page = self.context.new_page()
        if url:
            page.goto(url, wait_until="domcontentloaded")
        return page

    def save_state(self, name: str) -> Path:
        """把当前登录态导出为 storage_state 文件，供适配器声明复用。"""
        assert self.context is not None, "先调用 start()"
        path = self.auth_dir / f"{name}.json"
        self.context.storage_state(path=str(path))
        return path

    def close(self) -> None:
        if self.context is not None:
            self.context.close()
            self.context = None
        if self._playwright is not None:
            self._playwright.stop()
            self._playwright = None
