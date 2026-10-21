"""填值动作原语与回读校验。

每个原语只做一件事，且都对应网申系统里真实存在的控件形态。
回读校验是「不出错」的最后一道防线：填完读回来，和期望值比对。

已知陷阱（来自 docs/design.md）：
- React/Vue 受控组件：用 Playwright 原生 ``fill``，不要直接改 DOM value
- ``contenteditable`` 富文本：要 click + 清空 + type + 失焦，否则不触发 onChange
- 隐藏的 ``<input type=file>``：直接 ``set_input_files``，不要点可见的「上传」按钮
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from playwright.sync_api import Locator, Page

from job_apply_bot.engine.locator import find_field


class ActionError(RuntimeError):
    """动作执行失败（填不进、选不中等）。"""


def fill_text(locator: Locator, value: str) -> None:
    """普通输入框 / 文本域。"""
    locator.fill(value)


def fill_contenteditable(locator: Locator, value: str) -> None:
    """contenteditable 富文本：聚焦、全选清空、输入、失焦。"""
    locator.click()
    locator.press("Control+A")
    locator.press("Backspace")
    locator.type(value, delay=15)
    locator.press("Tab")  # 失焦触发 change


def select_option(page: Page, trigger: Locator, option_text: str) -> None:
    """自定义下拉：点开触发器，按文本点选项。"""
    trigger.click()
    page.get_by_text(option_text, exact=True).first.click()


def set_radio(page: Page, labels: list[str], option_text: str) -> None:
    """单选：点选项文本。优先命中 <label>男</label> 这种包裹式标签。"""
    option = page.get_by_label(option_text, exact=True)
    if option.count() > 0:
        option.first.click()
        return
    page.get_by_text(option_text, exact=True).first.click()


def set_checkbox(
    page: Page, labels: list[str], checked: bool, option_text: str | None = None
) -> None:
    """勾选/取消勾选。option_text 用于「是/否」这类需要点文字的场景。"""
    if option_text:
        set_radio(page, labels, option_text)
        return
    field = find_field(page, labels)
    if field.is_checked() != checked:
        field.click()


def upload_file(locator: Locator, path: Path) -> None:
    """对隐藏的 file input 直接注入文件。"""
    locator.set_input_files(str(path))


def read_back(locator: Locator) -> str | None:
    """回读当前值，用于核对。返回 None 表示读不到或该类型无值。"""
    tag = locator.evaluate("el => el.tagName.toLowerCase()")
    if tag == "input":
        input_type = locator.evaluate("el => (el.type || '').toLowerCase()")
        if input_type in ("checkbox", "radio"):
            return "checked" if locator.is_checked() else None
        if input_type == "file":
            files = locator.evaluate("el => el.files?.length || 0")
            return f"{files} 个文件" if files else None
        return locator.input_value()
    if tag in ("textarea", "select"):
        return locator.input_value()
    # contenteditable 或其它
    return locator.evaluate("el => (el.innerText || el.textContent || '').trim()")


def fill_field(
    page: Page,
    field: Mapping,
    value: str,
    *,
    workdir: Path,
) -> str | None:
    """按字段类型填值，返回回读值（供核对）。field 是适配器里的一段字段声明。"""
    field_type = field.get("type", "text")
    labels = field.get("label") or []
    locator = find_field(page, labels, name=field.get("name"), selector=field.get("selector"))

    if field_type in ("text", "textarea", "date"):
        fill_text(locator, value)  # text/textarea 原生 fill；date input 直接填 YYYY-MM-DD
    elif field_type == "contenteditable":
        fill_contenteditable(locator, value)
    elif field_type == "custom_select":
        options = field.get("options") or {}
        option_text = _pick_option_text(options, value)
        if _is_native_select(locator):
            locator.select_option(label=option_text)
        else:
            # 自定义下拉：触发器可能是显式 selector，否则退化为字段本身或其祖先
            trigger = page.locator(field["trigger"]).first if field.get("trigger") else locator
            select_option(page, trigger, option_text)
    elif field_type == "radio":
        options = field.get("options") or {}
        option_text = _pick_option_text(options, value)
        set_radio(page, labels, option_text)
    elif field_type == "checkbox":
        options = field.get("options") or {}
        option_text = _pick_option_text(options, value)
        checked = value not in ("false", "no", "否", "不接受", "不服从")
        set_checkbox(page, labels, checked, option_text)
    elif field_type == "upload":
        path = workdir / value if not Path(value).is_absolute() else Path(value)
        upload_file(locator, path)
    else:
        raise ActionError(f"未知字段类型：{field_type}")

    return read_back(locator)


def _pick_option_text(options: Mapping, value: str) -> str:
    """从 options 映射取页面文案。options = {profile值: [页面候选文案...]}。"""
    candidates = options.get(value)
    if not candidates:
        # 没配置映射时退化为直接用值当文案
        return value
    if isinstance(candidates, str):
        return candidates
    return candidates[0]


def _is_native_select(locator: Locator) -> bool:
    return locator.evaluate("el => el.tagName.toLowerCase() === 'select'")
