"""apply 编排：适配器 + profile + 引擎 = 一次完整的填表。

铁律：**永远停在提交按钮前**。本模块只负责检测提交按钮并报告它的位置，
任何代码路径都不点击它——提交是唯一必须由人完成动作的时刻。

回读校验的策略按字段类型区分（见 ``_verify``）：
- 文本类：回读值应等于期望值
- 原生 select：回读的是 option 的 value（如 ``bachelor``），与 profile 值一致
- 自定义下拉：回读的是触发器文案（如 ``北京``），与 options 映射的展示文案一致
- 复选框：回读 ``checked`` / ``None``
- 上传：回读 ``N 个文件``
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from playwright.sync_api import Page

from job_apply_bot.adapters.base import Adapter, FieldSpec, Step
from job_apply_bot.engine.actions import ActionError, fill_field
from job_apply_bot.engine.locator import FieldNotFoundError

# 提交按钮的常见文案（中文网申为主）。只用于「检测并停下」，不点击。
SUBMIT_BUTTON_TEXTS = ("提交", "确认投递", "立即投递", "马上投递", "投递简历", "apply", "submit")

# 视为「否」的复选框取值
_FALSE_VALUES = ("false", "no", "否", "不接受", "不服从", "0")


@dataclass
class FieldResult:
    """单个字段的填写结果。"""

    key: str
    label: str
    status: str  # filled / skipped / missing / failed
    expected: str | None = None
    actual: str | None = None
    verified: bool = False
    detail: str = ""


@dataclass
class ApplyReport:
    """一次 apply 的完整结果。"""

    site: str
    url: str
    started_at: str
    results: list[FieldResult] = field(default_factory=list)
    submit_found: bool = False
    submit_text: str = ""
    screenshot: str | None = None

    @property
    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for item in self.results:
            out[item.status] = out.get(item.status, 0) + 1
        return out

    def to_dict(self) -> dict[str, Any]:
        return {
            "site": self.site,
            "url": self.url,
            "started_at": self.started_at,
            "submit_found": self.submit_found,
            "submit_text": self.submit_text,
            "screenshot": self.screenshot,
            "counts": self.counts,
            "results": [
                {
                    "key": item.key,
                    "label": item.label,
                    "status": item.status,
                    "expected": item.expected,
                    "actual": item.actual,
                    "verified": item.verified,
                    "detail": item.detail,
                }
                for item in self.results
            ],
        }


def resolve_value(profile: dict[str, Any], key: str, default: str | None = None) -> str | None:
    """按点路径从 profile 取值，支持 ``educations.0.degree`` 这种列表索引。

    键不存在或值为 ``None`` 时退到 ``default``；再没有则返回 ``None``（调用方决定跳过还是报缺失）。
    布尔转成 ``"true"`` / ``"false"``——复选框分支按这两个值判断勾选状态。
    """
    current: Any = profile
    for part in key.split("."):
        if isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return default
        elif isinstance(current, dict):
            if part not in current:
                return default
            current = current[part]
        else:
            return default
    return _to_str(current) if current is not None else default


def _to_str(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def _display_text(spec: FieldSpec, value: str) -> str:
    """profile 值对应的页面展示文案（自定义下拉/单选用）。"""
    candidates = spec.options.get(value)
    if not candidates:
        return value
    if isinstance(candidates, str):
        return candidates
    return candidates[0]


def _verify(spec: FieldSpec, value: str, actual: str | None) -> bool:
    """回读值是否能证明「填对了」。类型相关的比对逻辑集中在这里。

    ``custom_select`` 同时覆盖原生 ``<select>`` 与 div 下拉两种形态，回读值
    因此有两种正确样子：原生 select 回读 option 的 value（``bachelor``），
    div 下拉回读触发器文案（``北京``）——两者都算填对，其余情况一律不认。
    """
    if spec.type == "upload":
        return actual is not None and actual.endswith("个文件") and not actual.startswith("0")
    if spec.type == "checkbox":
        want_checked = value not in _FALSE_VALUES
        return (actual == "checked") if want_checked else (actual is None)
    if spec.type == "radio":
        # 定位到的是组内第一个 input，点中正确选项时它处于 checked
        return actual == "checked"
    if spec.type == "custom_select":
        # 原生 select 回读 option 的 value（bachelor），div 下拉回读触发器文案（北京）
        return actual in (value, _display_text(spec, value))
    return actual == value


def _wait_ready(page: Page, step: Step) -> None:
    """等待步骤就绪。ready 支持 ``text=xxx`` / ``css=xxx`` 前缀，裸字符串按 CSS 处理。"""
    condition = step.ready
    if not condition:
        return
    if condition.startswith("text="):
        page.get_by_text(condition.removeprefix("text=")).first.wait_for(state="visible")
    elif condition.startswith("css="):
        page.wait_for_selector(condition.removeprefix("css="), state="visible")
    else:
        page.wait_for_selector(condition, state="visible")


def find_submit(page: Page) -> tuple[bool, str]:
    """检测提交按钮。只检测，不点击——这是本工具的铁律。"""
    native = page.locator("button[type=submit], input[type=submit]")
    if native.count() > 0:
        return True, (
            native.first.inner_text() or native.first.get_attribute("value") or ""
        ).strip()
    for text in SUBMIT_BUTTON_TEXTS:
        button = page.get_by_role("button", name=text)
        if button.count() > 0:
            return True, text
    return False, ""


def take_screenshot(page: Page, path: Path) -> str:
    """填表后截图留证，返回路径字符串。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(path), full_page=True)
    return str(path)


def run_apply(
    adapter: Adapter,
    profile: dict[str, Any],
    page: Page,
    *,
    workdir: Path,
    screenshot_dir: Path | None = None,
) -> ApplyReport:
    """执行一次填表。返回报告；提交按钮一定留在最后且绝不点击。"""
    report = ApplyReport(
        site=adapter.site,
        url=page.url,
        started_at=datetime.now().isoformat(timespec="seconds"),
    )

    for step in adapter.steps:
        try:
            _wait_ready(page, step)
        except Exception as exc:  # noqa: BLE001 - 步骤没就绪是页面问题，不该中断整个流程
            report.results.append(
                FieldResult(
                    key=f"step:{step.name}",
                    label=step.name,
                    status="failed",
                    detail=f"步骤就绪等待失败：{exc}",
                )
            )
            continue

        for spec in step.fields:
            value = resolve_value(profile, spec.key, spec.default)
            if value is None:
                report.results.append(
                    FieldResult(
                        key=spec.key,
                        label=spec.label[0],
                        status="missing" if spec.required else "skipped",
                        detail="profile 中无此字段" if spec.required else "非必填且无默认值，跳过",
                    )
                )
                continue
            try:
                actual = fill_field(page, spec.model_dump(), value, workdir=workdir)
            except (ActionError, FieldNotFoundError) as exc:
                report.results.append(
                    FieldResult(
                        key=spec.key,
                        label=spec.label[0],
                        status="failed",
                        expected=value,
                        detail=str(exc),
                    )
                )
                continue
            report.results.append(
                FieldResult(
                    key=spec.key,
                    label=spec.label[0],
                    status="filled",
                    expected=value,
                    actual=actual,
                    verified=_verify(spec, value, actual),
                )
            )

    report.submit_found, report.submit_text = find_submit(page)
    if screenshot_dir is not None:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        report.screenshot = take_screenshot(page, screenshot_dir / f"{adapter.site}-{stamp}.png")
    return report
