"""profile.json 的 pydantic 模型。

字段含义见 docs/profile-schema.md。这里负责结构校验与基础约束：

- 月份统一 ``YYYY-MM``
- 手机号、身份证号格式
- 教育/经历的起止时间先后关系
- 绩点不得超过满分制

"零容忍字段"（身份证、手机、毕业年月）即使校验通过，review 阶段也会强制人工确认，
校验只能保证"格式对"，保证不了"是不是你的"。
"""

from __future__ import annotations

import re
from datetime import date
from enum import StrEnum
from typing import Annotated, Any

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator, model_validator

PHONE_RE = re.compile(r"^1[3-9]\d{9}$")
MONTH_RE = re.compile(r"^\d{4}-(?:0[1-9]|1[0-2])$")
ID_RE = re.compile(r"^\d{17}[\dXx]$")

# 只有 * 代表脱敏。不能把 x/X 也算进来：身份证末位校验码就是 X，
# 早先把 x 当脱敏字符，导致小写 x 没有转成大写的 bug。
MASK_CHARS = ("*",)


def _validate_month(value: str) -> str:
    if not MONTH_RE.match(value):
        raise ValueError(f"月份格式必须是 YYYY-MM，收到 {value!r}")
    return value


Month = Annotated[str, AfterValidator(_validate_month)]


class Gender(StrEnum):
    male = "male"
    female = "female"


class Degree(StrEnum):
    highschool = "highschool"
    associate = "associate"
    bachelor = "bachelor"
    master = "master"
    phd = "phd"


class MaritalStatus(StrEnum):
    single = "single"
    married = "married"
    divorced = "divorced"


class JobType(StrEnum):
    campus = "campus"
    intern = "intern"
    social = "social"


class ExperienceKind(StrEnum):
    internship = "internship"
    fulltime = "fulltime"
    parttime = "parttime"


class _Base(BaseModel):
    # 允许 profile.json 里出现 _readme、注释性字段等额外键，不因此报错。
    model_config = ConfigDict(extra="ignore")


class Meta(_Base):
    version: int = 1
    updated_at: str | None = None
    source_file: str | None = None


class Basic(_Base):
    name_cn: str | None = None
    name_en: str | None = None
    gender: Gender | None = None
    birth_date: date | None = None
    id_number: str | None = None
    political_status: str | None = None
    hometown: str | None = None
    household: str | None = None
    marital_status: MaritalStatus | None = None
    health: str | None = None
    height_cm: int | None = Field(default=None, ge=100, le=250)

    @field_validator("birth_date")
    @classmethod
    def _check_birth_date(cls, value: date | None) -> date | None:
        if value is None:
            return value
        if not (date(1950, 1, 1) <= value <= date.today()):
            raise ValueError(f"出生日期不在合理范围：{value}")
        return value

    @field_validator("id_number")
    @classmethod
    def _check_id_number(cls, value: str | None) -> str | None:
        if value is None or any(ch in value for ch in MASK_CHARS):
            return value
        if not ID_RE.match(value):
            raise ValueError("身份证号应为 18 位（末位可为 X）")
        return value.upper()


class Contact(_Base):
    phone: str | None = None
    email: str | None = None
    wechat: str | None = None
    current_city: str | None = None
    address: str | None = None
    postal_code: str | None = None

    @field_validator("phone")
    @classmethod
    def _check_phone(cls, value: str | None) -> str | None:
        if value is None or any(ch in value for ch in MASK_CHARS):
            return value
        if not PHONE_RE.match(value):
            raise ValueError("手机号应为 11 位中国大陆号码")
        return value


class JobIntent(_Base):
    target_role: str | None = None
    target_city: list[str] = Field(default_factory=list)
    job_type: JobType | None = None
    available_date: str | None = None
    expected_salary: str | None = None
    accept_relocation: bool | None = None
    accept_shift: bool | None = None


class Education(_Base):
    degree: Degree | None = None
    school: str | None = None
    school_en: str | None = None
    major: str | None = None
    start: Month | None = None
    end: Month | None = None
    gpa: float | None = None
    gpa_scale: float | None = None
    gpa_percent: str | None = None
    ranking: str | None = None
    city: str | None = None
    is_full_time: bool | None = None
    courses: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_range_and_gpa(self) -> Education:
        """一次报出全部问题，不要遇到第一个就中断——否则用户改一轮只发现一个错。"""
        problems: list[str] = []
        if self.start and self.end and self.start > self.end:
            problems.append(f"开始时间晚于结束时间：{self.start} > {self.end}")
        if self.gpa is not None and self.gpa_scale is not None and self.gpa > self.gpa_scale:
            problems.append(f"绩点 {self.gpa} 超过满分制 {self.gpa_scale}")
        if problems:
            raise ValueError("；".join(problems))
        return self


class Experience(_Base):
    kind: ExperienceKind | None = None
    company: str | None = None
    department: str | None = None
    title: str | None = None
    start: Month | None = None
    end: Month | None = None  # None 表示"至今"
    city: str | None = None
    description: str | None = None
    achievements: list[str] = Field(default_factory=list)
    leave_reason: str | None = None

    @model_validator(mode="after")
    def _check_range(self) -> Experience:
        if self.start and self.end and self.start > self.end:
            raise ValueError(f"经历开始时间晚于结束时间：{self.start} > {self.end}")
        return self


class Project(_Base):
    name: str | None = None
    role: str | None = None
    start: Month | None = None
    end: Month | None = None
    tech: list[str] = Field(default_factory=list)
    description: str | None = None
    link: str | None = None


class Language(_Base):
    name: str | None = None
    level: str | None = None
    score: int | None = None


class Certificate(_Base):
    name: str | None = None
    date: Month | None = None


class Award(_Base):
    name: str | None = None
    date: Month | None = None
    level: str | None = None


class Skills(_Base):
    languages: list[Language] = Field(default_factory=list)
    programming: list[str] = Field(default_factory=list)
    certificates: list[Certificate] = Field(default_factory=list)
    awards: list[Award] = Field(default_factory=list)


class FamilyMember(_Base):
    relation: str | None = None
    name: str | None = None
    phone: str | None = None
    employer: str | None = None
    title: str | None = None


class Profile(_Base):
    """profile.json 根对象。"""

    meta: Meta = Field(default_factory=Meta)
    basic: Basic = Field(default_factory=Basic)
    contact: Contact = Field(default_factory=Contact)
    job_intent: JobIntent = Field(default_factory=JobIntent)
    educations: list[Education] = Field(default_factory=list)
    experiences: list[Experience] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    skills: Skills = Field(default_factory=Skills)
    family: list[FamilyMember] = Field(default_factory=list)
    custom: dict[str, Any] = Field(default_factory=dict)
    answers: dict[str, str | None] = Field(default_factory=dict)

    def to_json_dict(self) -> dict[str, Any]:
        """导出为可写入磁盘的 dict（枚举转值、日期转字符串、去掉 None）。"""
        return self.model_dump(mode="json", exclude_none=True)

    def missing_required(self) -> list[str]:
        """列出网申几乎一定会问、但当前为空的字段。"""
        checks: list[tuple[str, Any]] = [
            ("basic.name_cn", self.basic.name_cn),
            ("basic.gender", self.basic.gender),
            ("basic.birth_date", self.basic.birth_date),
            ("contact.phone", self.contact.phone),
            ("contact.email", self.contact.email),
            ("job_intent.target_role", self.job_intent.target_role),
        ]
        missing = [name for name, value in checks if not value]
        if not self.educations:
            missing.append("educations")
        else:
            first = self.educations[0]
            for field in ("school", "major", "degree", "start", "end"):
                if not getattr(first, field):
                    missing.append(f"educations.0.{field}")
        return missing
