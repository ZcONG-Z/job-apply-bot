"""归一化函数的单元测试。

这一层的每个函数都对应一类真实的简历写法，用例就是那些写法的样本。
"""

from __future__ import annotations

import pytest

from job_apply_bot.resume.normalize import (
    clean,
    is_present,
    parse_gpa,
    parse_range,
    split_items,
    strip_label,
    to_degree,
    to_email,
    to_gender,
    to_month,
    to_phone,
)
from job_apply_bot.resume.schema import Degree, Gender


class TestToMonth:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("2023.09", "2023-09"),
            ("2023/9", "2023-09"),
            ("2023-09", "2023-09"),
            ("2023年9月", "2023-09"),
            ("2023 年 09 月", "2023-09"),
            ("２０２３．０９", "2023-09"),
            ("教育经历 2023.09 - 2027.06", "2023-09"),
        ],
    )
    def test_variants(self, raw: str, expected: str) -> None:
        assert to_month(raw) == expected

    @pytest.mark.parametrize("raw", ["", "没有日期", "2023", "202309"])
    def test_invalid(self, raw: str) -> None:
        assert to_month(raw) is None

    def test_rejects_impossible_month(self) -> None:
        assert to_month("2023.13") is None


class TestParseRange:
    @pytest.mark.parametrize("sep", ["-", "–", "—", "~", "～", "至", "到", " - "])
    def test_all_separators(self, sep: str) -> None:
        assert parse_range(f"2023.09{sep}2027.06") == ("2023-09", "2027-06")

    def test_present_marker(self) -> None:
        assert parse_range("2026.07 - 至今") == ("2026-07", None)

    def test_reversed_input_is_swapped(self) -> None:
        assert parse_range("2027.06 - 2023.09") == ("2023-09", "2027-06")

    def test_single_month(self) -> None:
        assert parse_range("2025.10") == ("2025-10", None)

    def test_no_date(self) -> None:
        assert parse_range("某某大学 计算机科学与技术") == (None, None)


class TestIsPresent:
    @pytest.mark.parametrize("raw", ["至今", "现在", "Present", "2026.07 - 今"])
    def test_present(self, raw: str) -> None:
        assert is_present(raw)

    def test_not_present(self) -> None:
        assert not is_present("2026.07 - 2026.09")


class TestPhoneAndEmail:
    @pytest.mark.parametrize(
        "raw",
        [
            "13800138000",
            "手机：13800138000",
            "电话 138-0013-8000",
            "138 0013 8000",
        ],
    )
    def test_phone_variants(self, raw: str) -> None:
        assert to_phone(raw) == "13800138000"

    @pytest.mark.parametrize("raw", ["", "12345", "23800138000", "1380013800"])
    def test_phone_invalid(self, raw: str) -> None:
        assert to_phone(raw) is None

    def test_email(self) -> None:
        assert to_email("邮箱 zhangsan@example.com 谢谢") == "zhangsan@example.com"

    def test_email_absent(self) -> None:
        assert to_email("没有邮箱") is None


class TestGenderAndDegree:
    def test_gender(self) -> None:
        assert to_gender("性别：男") is Gender.male
        assert to_gender("性别：女") is Gender.female

    def test_gender_ambiguous(self) -> None:
        assert to_gender("男女不限") is None

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("本科", Degree.bachelor),
            ("学士学位", Degree.bachelor),
            ("硕士研究生", Degree.master),
            ("博士", Degree.phd),
            ("大专", Degree.associate),
            ("Master", Degree.master),
        ],
    )
    def test_degree(self, raw: str, expected: Degree) -> None:
        assert to_degree(raw) is expected

    def test_degree_absent(self) -> None:
        assert to_degree("某某大学") is None


class TestGpa:
    def test_ratio(self) -> None:
        assert parse_gpa("GPA 3.62/4.0") == (3.62, 4.0, None)

    def test_percent_rank(self) -> None:
        assert parse_gpa("绩点排名 前 15%") == (None, None, "前15%")

    def test_hundred_scale(self) -> None:
        assert parse_gpa("平均分 85.5") == (85.5, 100.0, None)

    def test_five_scale(self) -> None:
        assert parse_gpa("GPA 4.2") == (4.2, None, None)

    def test_absent(self) -> None:
        assert parse_gpa("某某大学") == (None, None, None)


class TestTextHelpers:
    def test_clean_keeps_chinese_punctuation(self) -> None:
        """NFKC 会把中文逗号转成半角，这里必须保持原样。"""
        assert clean("重构，将 P99 降至 130ms。") == "重构，将 P99 降至 130ms。"

    def test_clean_normalizes_fullwidth_digits(self) -> None:
        assert clean("２０２３．０９") == "2023.09"

    def test_split_items(self) -> None:
        assert split_items("Python、Go,Java；Rust") == ["Python", "Go", "Java", "Rust"]

    def test_split_items_empty(self) -> None:
        assert split_items("") == []

    def test_strip_label(self) -> None:
        assert strip_label("专业：计算机科学与技术") == "计算机科学与技术"
        assert strip_label("计算机科学与技术") == "计算机科学与技术"
