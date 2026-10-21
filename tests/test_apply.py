"""apply 端到端测试：适配器 + profile + 引擎 → 填表 → 停在提交前。

覆盖三层：
1. ``runner`` 纯函数：点路径取值、回读校验规则
2. ``runner`` 端到端：在自制表单上跑完整 apply，验证每个控件都填对、
   提交按钮被检测到且从未被点击
3. CLI：``jobapply apply`` 接线（适配器解析、脱敏报告、台账写入、退出码）
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from playwright.sync_api import Page

from job_apply_bot.adapters.base import FieldSpec, load_adapter
from job_apply_bot.cli import _mask
from job_apply_bot.engine.browser import BrowserSession
from job_apply_bot.engine.runner import (
    ApplyReport,
    _verify,
    find_submit,
    resolve_value,
    run_apply,
)
from job_apply_bot.ledger import recorder

FIXTURES = Path(__file__).parent / "fixtures"
FORM = FIXTURES / "test-form.html"
SITE = FIXTURES / "test-site.yaml"
PROFILE_EXAMPLE = Path(__file__).parent.parent / "profile.example.json"


@pytest.fixture(scope="module")
def session(tmp_path_factory: pytest.TempPathFactory) -> BrowserSession:
    """整个模块共用一个浏览器会话。

    Playwright 同步 API 同一线程同时只能有一个会话在跑，
    第二个会话会报 "inside the asyncio loop"——所以浏览器测试必须共享。
    """
    auth = tmp_path_factory.mktemp("auth")
    with BrowserSession(auth, headed=False) as browser:
        yield browser


@pytest.fixture(scope="module")
def page(session: BrowserSession) -> Page:
    return session.new_page(FORM.as_uri())


@pytest.fixture(scope="module")
def report(page: Page) -> ApplyReport:
    adapter = load_adapter(SITE)
    profile = json.loads(PROFILE_EXAMPLE.read_text(encoding="utf-8"))
    return run_apply(adapter, profile, page, workdir=FIXTURES)


def _result(report: ApplyReport, key: str):
    for item in report.results:
        if item.key == key:
            return item
    raise AssertionError(f"报告里没有字段 {key}")


# ---------------------------------------------------------------------------
# resolve_value：点路径取值
# ---------------------------------------------------------------------------


class TestResolveValue:
    PROFILE = {
        "basic": {"name_cn": "张三", "birth_date": None},
        "educations": [{"degree": "bachelor"}, {"degree": "master"}],
        "job_intent": {"accept_relocation": True, "target_city": ["上海", "杭州"]},
        "contact": {"height_cm": 175},
    }

    def test_plain_key(self) -> None:
        assert resolve_value(self.PROFILE, "basic.name_cn") == "张三"

    def test_list_index(self) -> None:
        assert resolve_value(self.PROFILE, "educations.1.degree") == "master"

    def test_bool_to_string(self) -> None:
        assert resolve_value(self.PROFILE, "job_intent.accept_relocation") == "true"

    def test_number_to_string(self) -> None:
        assert resolve_value(self.PROFILE, "contact.height_cm") == "175"

    def test_none_falls_back_to_default(self) -> None:
        assert resolve_value(self.PROFILE, "basic.birth_date", "2000-01-01") == "2000-01-01"

    def test_missing_key_falls_back_to_default(self) -> None:
        assert resolve_value(self.PROFILE, "basic.id_number", "无") == "无"

    def test_missing_without_default_is_none(self) -> None:
        assert resolve_value(self.PROFILE, "not.exist") is None

    def test_index_out_of_range(self) -> None:
        assert resolve_value(self.PROFILE, "educations.9.degree", "x") == "x"

    def test_scalar_mid_path(self) -> None:
        # 走到一半发现是标量而不是容器——按缺失处理
        assert resolve_value(self.PROFILE, "basic.name_cn.deeper", "x") == "x"


# ---------------------------------------------------------------------------
# _verify：回读校验规则
# ---------------------------------------------------------------------------


class TestVerify:
    def test_native_select_compares_value(self) -> None:
        spec = FieldSpec(
            key="k", label=["学历"], type="custom_select", options={"bachelor": "本科"}
        )
        assert _verify(spec, "bachelor", "bachelor")

    def test_custom_select_compares_display_text(self) -> None:
        spec = FieldSpec(key="k", label=["城市"], type="custom_select", options={"beijing": "北京"})
        assert _verify(spec, "beijing", "北京")
        assert not _verify(spec, "beijing", "上海")

    def test_checkbox_checked(self) -> None:
        spec = FieldSpec(key="k", label=["x"], type="checkbox")
        assert _verify(spec, "true", "checked")
        assert not _verify(spec, "true", None)

    def test_checkbox_unchecked(self) -> None:
        spec = FieldSpec(key="k", label=["x"], type="checkbox")
        assert _verify(spec, "false", None)
        assert not _verify(spec, "false", "checked")

    def test_upload_counts_files(self) -> None:
        spec = FieldSpec(key="k", label=["x"], type="upload")
        assert _verify(spec, "resume.pdf", "1 个文件")
        assert not _verify(spec, "resume.pdf", "0 个文件")

    def test_radio_checked(self) -> None:
        spec = FieldSpec(key="k", label=["x"], type="radio", options={"male": "男"})
        assert _verify(spec, "male", "checked")
        assert not _verify(spec, "male", None)

    def test_text_exact_match(self) -> None:
        spec = FieldSpec(key="k", label=["x"], type="text")
        assert _verify(spec, "张三", "张三")
        assert not _verify(spec, "张三", "李四")


# ---------------------------------------------------------------------------
# 端到端：完整 apply
# ---------------------------------------------------------------------------


class TestApplyEndToEnd:
    def test_required_fields_filled_and_verified(self, report: ApplyReport) -> None:
        for key in ("basic.name_cn", "contact.phone", "basic.birth_date"):
            item = _result(report, key)
            assert item.status == "filled", f"{key}: {item.status}（{item.detail}）"
            assert item.verified, f"{key} 回读不一致：期望 {item.expected}，实际 {item.actual}"

    def test_no_failed_fields(self, report: ApplyReport) -> None:
        failed = [item.key for item in report.results if item.status == "failed"]
        assert failed == []

    def test_defaults_used_when_profile_empty(self, report: ApplyReport) -> None:
        # profile 里 answers.self_intro 为 null，应回退到适配器 default
        item = _result(report, "answers.self_intro")
        assert item.status == "filled"
        assert item.expected is not None and item.expected.startswith("示例")

    def test_optional_without_default_is_skipped(self, report: ApplyReport) -> None:
        item = _result(report, "answers.why_company")
        assert item.status == "skipped"

    def test_list_index_value_fills_custom_select(self, report: ApplyReport, page: Page) -> None:
        # job_intent.target_city.0 = "上海" → 自定义下拉触发器文案变为「上海」
        item = _result(report, "job_intent.target_city.0")
        assert item.status == "filled" and item.verified
        assert page.locator("#city-trigger").inner_text() == "上海"

    def test_native_select_value(self, page: Page) -> None:
        assert page.locator("#degree").input_value() == "bachelor"

    def test_checkbox_and_radio_checked(self, page: Page) -> None:
        assert page.locator("#accept").is_checked()
        assert page.locator("input[name='gender'][value='male']").is_checked()

    def test_upload_injected(self, page: Page) -> None:
        assert page.evaluate("document.getElementById('resume-file').files.length") == 1

    def test_date_filled(self, page: Page) -> None:
        assert page.locator("#birth").input_value() == "2003-04-15"

    def test_stops_before_submit(self, report: ApplyReport, page: Page) -> None:
        """铁律：提交按钮必须被检测到，且从未被点击。"""
        assert report.submit_found
        assert report.submit_text == "确认投递"
        assert page.evaluate("document.body.dataset.submitted || null") is None
        assert page.url == FORM.as_uri()

    def test_report_serializable(self, report: ApplyReport) -> None:
        data = report.to_dict()
        assert json.dumps(data, ensure_ascii=False)  # 不能抛异常
        assert data["counts"].get("filled", 0) >= 8


# ---------------------------------------------------------------------------
# find_submit：只检测，不点击
# ---------------------------------------------------------------------------


class TestFindSubmit:
    def test_found_on_fixture(self, page: Page) -> None:
        assert find_submit(page) == (True, "确认投递")

    def test_not_found_on_blank(self, session: BrowserSession) -> None:
        # 同一会话里新开页面，不开第二个 Playwright 会话
        blank = session.new_page("about:blank")
        try:
            assert find_submit(blank) == (False, "")
        finally:
            blank.close()


# ---------------------------------------------------------------------------
# 台账
# ---------------------------------------------------------------------------


class TestLedger:
    def test_record_and_read(self, tmp_path: Path) -> None:
        path = tmp_path / "ledger.jsonl"
        recorder.record(
            path, site="test", url="https://example.test/1", status=recorder.STATUS_FILLED
        )
        recorder.record(
            path, site="test", url="https://example.test/2", status=recorder.STATUS_ABORTED
        )
        entries = recorder.read_all(path)
        assert len(entries) == 2
        assert entries[0]["site"] == "test"
        assert entries[1]["status"] == recorder.STATUS_ABORTED
        assert entries[0]["ts"]  # 时间戳非空

    def test_read_missing_file(self, tmp_path: Path) -> None:
        assert recorder.read_all(tmp_path / "nope.jsonl") == []

    def test_corrupt_line_skipped(self, tmp_path: Path) -> None:
        path = tmp_path / "ledger.jsonl"
        path.write_text('{"site": "ok"}\n不是 json\n\n{"site": "ok2"}\n', encoding="utf-8")
        entries = recorder.read_all(path)
        assert [entry["site"] for entry in entries] == ["ok", "ok2"]

    def test_summarize_and_duplicates(self, tmp_path: Path) -> None:
        path = tmp_path / "ledger.jsonl"
        recorder.record(path, site="a", url="u1", status=recorder.STATUS_FILLED)
        recorder.record(path, site="a", url="u1", status=recorder.STATUS_FILLED)
        recorder.record(path, site="b", url="u2", status=recorder.STATUS_ABORTED)
        entries = recorder.read_all(path)
        assert recorder.summarize(entries) == {
            recorder.STATUS_FILLED: 2,
            recorder.STATUS_ABORTED: 1,
        }
        assert recorder.duplicate_urls(entries) == {"u1"}


# ---------------------------------------------------------------------------
# CLI 接线（子进程跑真实入口：python -m job_apply_bot）
# ---------------------------------------------------------------------------


def _run_cli(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "job_apply_bot", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=120,
    )


class TestMask:
    def test_sensitive_masked(self) -> None:
        assert _mask("contact.phone", "13800138000", debug=False) == "138****8000"

    def test_id_number_masked(self) -> None:
        assert _mask("basic.id_number", "310101********1234", debug=False) == "310****1234"

    def test_debug_shows_full(self) -> None:
        assert _mask("contact.phone", "13800138000", debug=True) == "13800138000"

    def test_non_sensitive_untouched(self) -> None:
        assert _mask("basic.name_cn", "张三", debug=False) == "张三"

    def test_none_shows_dash(self) -> None:
        assert _mask("contact.phone", None, debug=False) == "—"


class TestApplyCli:
    def test_apply_local_fixture(self, tmp_path: Path) -> None:
        # 子进程独立进程：不共享 pytest 里的 Playwright 会话，也更接近用户真实用法
        result = _run_cli(
            [
                "apply",
                FORM.as_uri(),
                "--profile",
                str(PROFILE_EXAMPLE),
                "--adapter",
                str(SITE),
                "--headless",
                "--workdir",
                str(FIXTURES),
            ],
            cwd=tmp_path,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert "已停在提交按钮前" in result.stdout
        assert "确认投递" in result.stdout

        # 台账写入
        ledger = tmp_path / ".jobapply" / "ledger.jsonl"
        assert ledger.exists()
        entry = json.loads(ledger.read_text(encoding="utf-8").strip())
        assert entry["status"] == recorder.STATUS_FILLED
        assert entry["url"] == FORM.as_uri()

        # 截图产物
        artifacts = list((tmp_path / ".jobapply" / "artifacts").glob("*.png"))
        assert len(artifacts) == 1

    def test_apply_without_adapter_fails(self, tmp_path: Path) -> None:
        result = _run_cli(
            [
                "apply",
                "https://unknown.example.test/job/1",
                "--profile",
                str(PROFILE_EXAMPLE),
                "--headless",
            ],
            cwd=tmp_path,
        )
        assert result.returncode == 1
        assert "没有适配器" in result.stdout
