"""填表引擎的端到端测试：在本地 HTML 表单上验证定位与动作原语。

表单是自制的、完全可控的，覆盖网申系统里真实的控件形态：
标准标签 / 无关联标签 / textarea / contenteditable / date /
原生 select / 自定义下拉 / 单选 / 复选 / 隐藏 file input。

需要 Playwright 与 Chromium（``playwright install chromium``）。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import Page

from job_apply_bot.engine.actions import fill_field
from job_apply_bot.engine.browser import BrowserSession
from job_apply_bot.engine.locator import FieldNotFoundError, find_field

FORM = Path(__file__).parent / "fixtures" / "test-form.html"


@pytest.fixture(scope="module")
def page(tmp_path_factory: pytest.TempPathFactory) -> Page:
    auth = tmp_path_factory.mktemp("auth")
    with BrowserSession(auth, headed=False) as session:
        loaded = session.new_page(FORM.as_uri())
        yield loaded


class TestLocator:
    def test_linked_label(self, page: Page) -> None:
        locator = find_field(page, ["姓名"])
        locator.fill("张三")
        assert locator.input_value() == "张三"

    def test_unlinked_label(self, page: Page) -> None:
        # 「手机号码」是 <span>，与 input 无 for 关联
        locator = find_field(page, ["手机号码"])
        locator.fill("13800138000")
        assert locator.input_value() == "13800138000"

    def test_name_attr_fallback(self, page: Page) -> None:
        # 故意给一个不存在的 label，逼它走 name 兜底
        locator = find_field(page, ["不存在的标签"], name="name")
        assert locator.get_attribute("name") == "name"

    def test_not_found_raises(self, page: Page) -> None:
        with pytest.raises(FieldNotFoundError):
            find_field(page, ["这个字段不存在"], name=None, selector="#no-such")


class TestFillField:
    def test_text(self, page: Page) -> None:
        value = fill_field(page, {"type": "text", "label": ["姓名"]}, "李四", workdir=FORM.parent)
        assert value == "李四"

    def test_textarea(self, page: Page) -> None:
        value = fill_field(
            page,
            {"type": "textarea", "label": ["自我评价"]},
            "认真负责",
            workdir=FORM.parent,
        )
        assert value == "认真负责"

    def test_contenteditable(self, page: Page) -> None:
        value = fill_field(
            page,
            {"type": "contenteditable", "label": ["项目描述"]},
            "调度平台重构",
            workdir=FORM.parent,
        )
        assert value == "调度平台重构"

    def test_date(self, page: Page) -> None:
        value = fill_field(
            page,
            {"type": "date", "label": ["出生日期"]},
            "2003-04-15",
            workdir=FORM.parent,
        )
        assert value == "2003-04-15"

    def test_native_select(self, page: Page) -> None:
        value = fill_field(
            page,
            {
                "type": "custom_select",
                "label": ["最高学历"],
                "options": {"master": ["硕士"]},
            },
            "master",
            workdir=FORM.parent,
        )
        assert value == "master"  # select 的 value 属性即 profile 键

    def test_custom_dropdown(self, page: Page) -> None:
        fill_field(
            page,
            {
                "type": "custom_select",
                "label": ["期望城市"],
                "trigger": "#city-trigger",
                "options": {"beijing": ["北京"]},
            },
            "beijing",
            workdir=FORM.parent,
        )
        trigger_text = page.locator("#city-trigger").inner_text()
        assert trigger_text == "北京"

    def test_radio(self, page: Page) -> None:
        fill_field(
            page,
            {"type": "radio", "label": ["性别"], "options": {"female": ["女"]}},
            "female",
            workdir=FORM.parent,
        )
        assert page.locator("input[name='gender'][value='female']").is_checked()

    def test_checkbox(self, page: Page) -> None:
        fill_field(page, {"type": "checkbox", "label": ["可到岗"]}, "true", workdir=FORM.parent)
        assert page.locator("#accept").is_checked()

    def test_upload(self, page: Page, tmp_path: Path) -> None:
        resume = tmp_path / "resume.pdf"
        resume.write_bytes(b"%PDF-1.4 fake resume")
        value = fill_field(
            page,
            {"type": "upload", "label": ["简历附件"]},
            str(resume),
            workdir=FORM.parent,
        )
        assert value == "1 个文件"
