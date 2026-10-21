"""解析层测试。

包含两部分：
1. 纯文本解析（不依赖文件，速度快）
2. 端到端：从 fixtures 里的样本简历文件解析（验证 extract + parse 的串联）
"""

from __future__ import annotations

from pathlib import Path

import pytest

from job_apply_bot.resume.extract import UnsupportedFormatError, extract_text
from job_apply_bot.resume.parse import parse_resume, split_sections
from job_apply_bot.resume.schema import Degree, ExperienceKind, Gender

FIXTURES = Path(__file__).parent / "fixtures"

RESUME_TEXT = """张三
求职意向：后端开发工程师
手机：13800138000    邮箱：zhangsan@example.com
性别：男    出生日期：2003-04-15    政治面貌：共青团员    籍贯：江苏省南京市
现居：上海市

教育经历
2023.09 - 2027.06    某某大学    计算机科学与技术    本科
GPA 3.62/4.0    排名 12/180
主修课程：数据结构、操作系统、计算机网络

实习经历
2026.07 - 2026.09    某某科技有限公司    后端开发实习生
负责订单服务重构，将核心接口 P99 从 420ms 降至 130ms。

专业技能
编程语言：Python、Go、Java

荣誉奖项
国家励志奖学金（2025.10）
"""


class TestSplitSections:
    def test_header_and_sections(self) -> None:
        header, sections = split_sections(RESUME_TEXT)
        assert "张三" in header
        assert set(sections) >= {"education", "experience", "skills", "award"}

    def test_label_line_is_not_header(self) -> None:
        """「教育经历：某某大学」是正文，不能当成小节标题。"""
        _, sections = split_sections("教育经历：某某大学 计算机专业")
        assert "education" not in sections

    @pytest.mark.parametrize(
        "header",
        ["教育经历", "一、教育经历", "【教育背景】", "1. 教育经历", "（三）实习经历"],
    )
    def test_header_variants(self, header: str) -> None:
        _, sections = split_sections(f"{header}\n某某大学 2023.09-2027.06")
        assert sections, f"未能识别标题：{header}"


class TestParseBasic:
    def test_core_fields(self) -> None:
        profile = parse_resume(RESUME_TEXT).profile
        assert profile.basic.name_cn == "张三"
        assert profile.basic.gender is Gender.male
        assert profile.basic.birth_date is not None
        assert str(profile.basic.birth_date) == "2003-04-15"
        assert profile.basic.political_status == "共青团员"

    def test_contact(self) -> None:
        profile = parse_resume(RESUME_TEXT).profile
        assert profile.contact.phone == "13800138000"
        assert profile.contact.email == "zhangsan@example.com"

    def test_job_intent(self) -> None:
        profile = parse_resume(RESUME_TEXT).profile
        assert profile.job_intent.target_role == "后端开发工程师"

    def test_name_inferred_from_first_line_is_warned(self) -> None:
        result = parse_resume(RESUME_TEXT)
        assert any("姓名" in warning for warning in result.warnings)

    def test_name_from_label_has_no_warning(self) -> None:
        result = parse_resume("姓名：李四\n手机：13900139000")
        assert result.profile.basic.name_cn == "李四"
        assert not any("按首行推断" in warning for warning in result.warnings)


class TestParseEducation:
    def test_single_entry(self) -> None:
        profile = parse_resume(RESUME_TEXT).profile
        assert len(profile.educations) == 1
        education = profile.educations[0]
        assert education.school == "某某大学"
        assert education.major == "计算机科学与技术"
        assert education.degree is Degree.bachelor
        assert education.start == "2023-09"
        assert education.end == "2027-06"

    def test_gpa_and_ranking(self) -> None:
        education = parse_resume(RESUME_TEXT).profile.educations[0]
        assert education.gpa == 3.62
        assert education.gpa_scale == 4.0
        assert education.ranking == "12/180"

    def test_courses(self) -> None:
        education = parse_resume(RESUME_TEXT).profile.educations[0]
        assert education.courses == ["数据结构", "操作系统", "计算机网络"]

    def test_multiple_entries(self) -> None:
        text = """教育经历
2023.09 - 2027.06    某某大学    计算机科学与技术    硕士
2020.09 - 2023.06    某某学院    软件工程    本科
"""
        educations = parse_resume(text).profile.educations
        assert len(educations) == 2
        assert educations[0].degree is Degree.master
        assert educations[1].degree is Degree.bachelor
        assert educations[1].school == "某某学院"


class TestParseExperience:
    def test_company_title_range(self) -> None:
        experiences = parse_resume(RESUME_TEXT).profile.experiences
        assert len(experiences) == 1
        experience = experiences[0]
        assert experience.company == "某某科技有限公司"
        assert experience.title == "后端开发实习生"
        assert experience.kind is ExperienceKind.internship
        assert experience.start == "2026-07"
        assert experience.end == "2026-09"

    def test_ongoing_experience(self) -> None:
        text = """实习经历
2026.07 - 至今    某某科技有限公司    后端开发实习生
负责订单服务。
"""
        experience = parse_resume(text).profile.experiences[0]
        assert experience.start == "2026-07"
        assert experience.end is None


class TestParseSkillsAndAwards:
    def test_programming_languages(self) -> None:
        skills = parse_resume(RESUME_TEXT).profile.skills
        assert set(skills.programming) == {"Python", "Go", "Java"}

    def test_award_name_strips_date(self) -> None:
        awards = parse_resume(RESUME_TEXT).profile.skills.awards
        assert awards[0].name == "国家励志奖学金"
        assert awards[0].date == "2025-10"
        assert awards[0].level == "国家级"


class TestWarnings:
    def test_missing_sections_are_reported(self) -> None:
        result = parse_resume("只有一行字")
        assert any("教育经历" in warning for warning in result.warnings)

    def test_empty_text_reports_everything_missing(self) -> None:
        result = parse_resume("")
        assert len(result.warnings) >= 3


class TestEndToEndFixtures:
    """从真实文件走一遍 extract + parse。"""

    @pytest.mark.parametrize("name", ["sample-resume.docx", "sample-resume.pdf"])
    def test_sample_resume(self, name: str) -> None:
        path = FIXTURES / name
        if not path.exists():
            pytest.skip(f"{name} 不存在，先跑 python scripts/make_sample_resume.py")

        text = extract_text(path)
        assert "某某大学" in text

        profile = parse_resume(text).profile
        assert profile.basic.name_cn == "张三"
        assert profile.contact.phone == "13800138000"
        assert profile.educations[0].school == "某某大学"
        assert profile.educations[0].start == "2023-09"
        assert profile.educations[0].end == "2027-06"

    def test_unsupported_format(self, tmp_path: Path) -> None:
        target = tmp_path / "resume.txt"
        target.write_text("内容", encoding="utf-8")
        with pytest.raises(UnsupportedFormatError):
            extract_text(target)

    def test_legacy_doc_has_actionable_message(self, tmp_path: Path) -> None:
        target = tmp_path / "resume.doc"
        target.write_bytes(b"\xd0\xcf\x11\xe0")
        with pytest.raises(UnsupportedFormatError, match="docx"):
            extract_text(target)

    def test_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            extract_text(tmp_path / "nope.pdf")
