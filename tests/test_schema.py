"""schema 校验测试。

重点验证"该拦的拦住"：手机号、绩点、时间区间这些错了必须报错，
而不是静默存进去等填表时才暴露。
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from job_apply_bot.resume.schema import Contact, Education, Experience, Profile

VALID_ID = "310101200304151234"


class TestPhone:
    def test_valid(self) -> None:
        assert Contact(phone="13800138000").phone == "13800138000"

    @pytest.mark.parametrize("phone", ["1380013800", "23800138000", "138001380000", "abcdefghijk"])
    def test_invalid(self, phone: str) -> None:
        with pytest.raises(ValidationError):
            Contact(phone=phone)

    def test_masked_is_allowed(self) -> None:
        """待补字段可能存脱敏值，不应因此报错。"""
        assert Contact(phone="138****8000").phone == "138****8000"


class TestIdNumber:
    def test_valid(self) -> None:
        assert Profile(basic={"id_number": VALID_ID}).basic.id_number == VALID_ID

    def test_lowercase_x_uppercased(self) -> None:
        assert Profile(basic={"id_number": "31010120030415123x"}).basic.id_number == (
            "31010120030415123X"
        )

    def test_too_short(self) -> None:
        with pytest.raises(ValidationError):
            Profile(basic={"id_number": "31010120030415"})

    def test_masked_is_allowed(self) -> None:
        assert "***" in Profile(basic={"id_number": "310101********1234"}).basic.id_number


class TestBirthDate:
    def test_valid(self) -> None:
        assert Profile(basic={"birth_date": "2003-04-15"}).basic.birth_date == date(2003, 4, 15)

    def test_future_rejected(self) -> None:
        future = (date.today() + timedelta(days=1)).isoformat()
        with pytest.raises(ValidationError):
            Profile(basic={"birth_date": future})

    def test_too_old_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Profile(basic={"birth_date": "1900-01-01"})


class TestEducation:
    def test_month_format_enforced(self) -> None:
        with pytest.raises(ValidationError):
            Education(start="2023-9")  # 必须是两位月份

    def test_start_after_end_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Education(start="2027-06", end="2023-09")

    def test_gpa_over_scale_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Education(gpa=5.0, gpa_scale=4.0)

    def test_gpa_equal_scale_ok(self) -> None:
        assert Education(gpa=4.0, gpa_scale=4.0).gpa == 4.0


class TestExperience:
    def test_ongoing_has_no_end(self) -> None:
        experience = Experience(start="2026-07", end=None)
        assert experience.end is None

    def test_start_after_end_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Experience(start="2026-09", end="2026-07")


class TestProfile:
    def test_extra_keys_ignored(self) -> None:
        """profile.json 里允许 _readme 之类的额外键。"""
        profile = Profile.model_validate(
            {"_readme": "说明文字", "custom": {"beisen.is_only_child": True}}
        )
        assert profile.basic.name_cn is None
        assert profile.custom["beisen.is_only_child"] is True

    def test_missing_required_lists_empty_fields(self) -> None:
        missing = Profile().missing_required()
        assert "basic.name_cn" in missing
        assert "educations" in missing

    def test_complete_profile_has_no_missing(self) -> None:
        profile = Profile(
            basic={"name_cn": "张三", "gender": "male", "birth_date": "2003-04-15"},
            contact={"phone": "13800138000", "email": "zhangsan@example.com"},
            job_intent={"target_role": "后端开发工程师"},
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
        assert profile.missing_required() == []

    def test_to_json_dict_drops_none(self) -> None:
        data = Profile(basic={"name_cn": "张三"}).to_json_dict()
        assert data["basic"]["name_cn"] == "张三"
        assert "birth_date" not in data["basic"]
