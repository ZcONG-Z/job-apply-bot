"""站点适配器：YAML 声明与校验。

适配器是**配置，不是脚本**。它只描述「哪个字段、取什么值、怎么在这一页找到它」，
逻辑在引擎里。规范见 docs/adapter-spec.md。
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

# 引擎支持的字段类型，与 adapter-spec 保持一致
FIELD_TYPES = {
    "text",
    "textarea",
    "contenteditable",
    "custom_select",
    "date",
    "radio",
    "checkbox",
    "upload",
}


class FieldSpec(BaseModel):
    """一个字段的声明。"""

    model_config = ConfigDict(extra="ignore")

    key: str
    label: list[str] = Field(min_length=1, description="页面上可见的标签候选，按顺序尝试")
    type: str = "text"
    required: bool = False
    name: str | None = None
    selector: str | None = None
    options: dict[str, str | list[str]] = Field(default_factory=dict)
    default: str | None = None

    @field_validator("type")
    @classmethod
    def _check_type(cls, value: str) -> str:
        if value not in FIELD_TYPES:
            raise ValueError(f"未知字段类型 {value!r}，可选：{sorted(FIELD_TYPES)}")
        return value


class Step(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    ready: str | None = None  # 进入该步的等待条件，如 "text=姓名"
    fields: list[FieldSpec] = Field(default_factory=list)


class Adapter(BaseModel):
    model_config = ConfigDict(extra="ignore")

    site: str
    display_name: str = ""
    match: dict = Field(default_factory=dict)  # {"url_patterns": [...]}
    login: dict = Field(default_factory=dict)  # {"mode": "manual", "state_file": "..."}
    steps: list[Step] = Field(default_factory=list)

    @property
    def url_patterns(self) -> list[str]:
        return self.match.get("url_patterns", [])

    def all_fields(self) -> list[tuple[Step, FieldSpec]]:
        return [(step, field) for step in self.steps for field in step.fields]

    def missing_locators(self, page) -> list[str]:
        """在给定页面上检查哪些必填字段定位不到，返回字段 key 列表。"""
        from job_apply_bot.engine.locator import FieldNotFoundError, find_field

        missing: list[str] = []
        for _step, field in self.all_fields():
            try:
                find_field(
                    page,
                    field.label,
                    name=field.name,
                    selector=field.selector,
                )
            except FieldNotFoundError:
                missing.append(field.key)
        return missing


def load_adapter(path: Path) -> Adapter:
    """从 YAML 文件加载适配器，结构不合法时抛 ValueError（ValidationError 为其子类）。"""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError("适配器必须是 YAML 映射，而不是列表或标量")
    adapter = Adapter.model_validate(data)
    if adapter.site != path.stem:
        raise ValueError(f"site 字段应为 {path.stem!r}，实际是 {adapter.site!r}")
    return adapter
