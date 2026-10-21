"""CLI 层可测试的逻辑。

交互式 prompt 无法在测试里走通（`isatty()` 为 False 会直接跳过），
所以把"按点路径改值"抽成 ``apply_edits`` 单独测。
"""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from job_apply_bot.cli import apply_edits
from job_apply_bot.resume.schema import Profile


def _profile() -> Profile:
    return Profile(
        basic={"name_cn": "张三"},
        educations=[
            {
                "school": "某某大学",
                "major": "计算机科学与技术",
                "degree": "bachelor",
                "start": "2023-09",
                "end": "2027-06",
            }
        ],
    )


def test_date_string_is_coerced_to_date() -> None:
    """review 里输入的新值是字符串，重新校验后必须变成 date 对象。"""
    profile = apply_edits(_profile(), {"basic.birth_date": "2004-01-02"})
    assert profile.basic.birth_date == date(2004, 1, 2)


def test_invalid_phone_is_rejected() -> None:
    with pytest.raises(ValidationError):
        apply_edits(_profile(), {"contact.phone": "12345"})


def test_nested_field_is_edited() -> None:
    profile = apply_edits(_profile(), {"educations.0.school": "某某学院"})
    assert profile.educations[0].school == "某某学院"


def test_broken_education_range_is_rejected() -> None:
    with pytest.raises(ValidationError):
        apply_edits(_profile(), {"educations.0.end": "2020-01"})


def test_empty_edits_leave_profile_unchanged() -> None:
    profile = apply_edits(_profile(), {})
    assert profile.basic.name_cn == "张三"
    assert profile.educations[0].school == "某某大学"
