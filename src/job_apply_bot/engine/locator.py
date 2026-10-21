"""字段定位。

按优先级依次尝试，命中即返回：

1. 可见标签文本（含 aria-label / placeholder，二者由 ``get_by_label`` 一并覆盖）
2. ``name`` 属性
3. CSS 选择器（显式指定，最后的兜底）

为什么文本优先：DOM 结构随前端框架版本变化、class 名被构建工具压缩、
``name`` 常被改成 ``field_8f3a``，但「姓名」这两个字不会变。
详见 docs/adapter-spec.md。
"""

from __future__ import annotations

from playwright.sync_api import Locator, Page

# 与输入控件在同一容器内常见的祖先层级，用于「找到标签文本后反向找输入框」
_INPUT_TAGS = "input, textarea, select, [contenteditable='true']"


class FieldNotFoundError(RuntimeError):
    """所有定位策略都失败。"""


def _by_label_text(page: Page, labels: list[str]) -> Locator | None:
    for text in labels:
        # 标准关联：<label for>、aria-label、placeholder 都走 get_by_label
        linked = page.get_by_label(text, exact=True)
        if linked.count() > 0:
            return linked.first

        # 中文表单常见「无关联标签」：<div>姓名 <input></div>
        # 从标签文本出发，向上找一层容器，再在容器内找输入控件
        label_el = page.get_by_text(text, exact=True).first
        if label_el.count() == 0:
            continue
        candidate = label_el.locator("xpath=ancestor::*[1]").locator(_INPUT_TAGS).first
        if candidate.count() > 0:
            return candidate
    return None


def _by_name(page: Page, name: str) -> Locator | None:
    locator = page.locator(
        f"input[name='{name}'], textarea[name='{name}'], select[name='{name}']"
    ).first
    return locator if locator.count() > 0 else None


def _by_css(page: Page, selector: str) -> Locator | None:
    locator = page.locator(selector).first
    return locator if locator.count() > 0 else None


def find_field(
    page: Page,
    labels: list[str],
    *,
    name: str | None = None,
    selector: str | None = None,
) -> Locator:
    """按四级策略定位字段，全部失败抛 :class:`FieldNotFoundError`。"""
    if locator := _by_label_text(page, labels):
        return locator
    if name and (locator := _by_name(page, name)):
        return locator
    if selector and (locator := _by_css(page, selector)):
        return locator
    raise FieldNotFoundError(f"无法定位字段：label={labels} name={name} selector={selector}")
