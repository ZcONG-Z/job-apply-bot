"""简历文本 → 结构化 profile。

策略是**规则优先**：

1. 按小节标题切块（教育经历、实习经历……）
2. 块内用正则与版面启发式提取字段
3. 每一处"抽到了但不确定"都记进 warnings，交给 review 环节人工确认

为什么不用大模型一步到位：规则能覆盖规整排版，且结果**可解释**——错了能定位是哪条正则。
大模型适合兜底规则失败的部分（见 roadmap 中的 LLM 兜底），不适合当主力。

这个模块的产出是**草稿**，不是终稿。任何字段都可能抽错，所以必须过 review。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from job_apply_bot.resume import normalize as nz
from job_apply_bot.resume.schema import (
    Award,
    Basic,
    Certificate,
    Contact,
    Education,
    Experience,
    ExperienceKind,
    JobIntent,
    Language,
    Profile,
    Project,
    Skills,
)

# ---------------------------------------------------------------------------
# 小节识别
# ---------------------------------------------------------------------------

SECTION_KEYWORDS: dict[str, tuple[str, ...]] = {
    "basic": ("基本信息", "个人信息", "个人资料", "联系方式", "基本情况"),
    "education": ("教育经历", "教育背景", "学习经历", "教育情况"),
    "experience": ("实习经历", "工作经历", "职业经历", "工作经验", "实践经历"),
    "project": ("项目经历", "项目经验", "科研经历", "科研项目"),
    "skills": ("专业技能", "技能特长", "技能证书", "语言能力", "IT技能", "技能"),
    "award": ("荣誉奖项", "获奖情况", "奖励荣誉", "所获荣誉", "荣誉"),
    "certificate": ("资格证书", "证书"),
    "self": ("自我评价", "个人总结", "自我介绍", "个人评价"),
}

# 标题行特征：去掉编号后很短，且不含冒号（含冒号基本是 "教育经历：XX大学" 这种正文）
_HEADER_NOISE = re.compile(r"^[\s【\[（(]*[一二三四五六七八九十\d]{1,2}[\s、.．)）\]】]*")
_MAX_HEADER_LEN = 12

# 标题两侧的装饰性字符，如「【教育背景】」「（三）实习经历」
_DECOR = " \u3000【】[]（）()、.．:："


def _normalize_headers(line: str) -> str:
    text = nz.clean(line).strip(_DECOR)
    text = _HEADER_NOISE.sub("", text)
    return text.strip(_DECOR)


_SCHOOL = re.compile(r"[\u4e00-\u9fa5]{2,16}(?:大学|学院|学校|职业技术学院|研究院)")
# 后缀按"从长到短"排列且用贪婪匹配：否则 "某某科技有限公司" 会被截成 "某某科技"。
# 曾经把 "科技" 当后缀，正是它导致公司名截断。
_COMPANY = re.compile(
    r"[\u4e00-\u9fa5A-Za-z（）()]{2,24}"
    r"(?:股份有限公司|有限责任公司|有限公司|集团|公司|银行|研究院|研究所|事务所)"
)
_TITLE_HINT = re.compile(
    r"(?:实习生|工程师|经理|助理|专员|主管|分析师|研究员|设计师|架构师|开发|顾问)$"
)
_ROLE_HINT = re.compile(r"(负责人|组长|组员|成员|主程|核心开发|队长|开发者)")
_INTENT = re.compile(r"(?:求职意向|应聘岗位|意向岗位|目标岗位)\s*[:：]\s*([^\s，,；;]{2,20})")
_NAME_LABEL = re.compile(r"姓\s*名\s*[:：]\s*([\u4e00-\u9fa5·]{2,6})")
_GENDER_LABEL = re.compile(r"性\s*别\s*[:：]?\s*(男|女)")
_FULL_DATE = re.compile(r"((?:19|20)\d{2})\s*[年./\-]\s*(\d{1,2})\s*[月./\-]\s*(\d{1,2})")
_POLITICAL = ("中共党员", "中共预备党员", "共青团员", "群众", "民主党派")
_RANKING = re.compile(r"排名\s*[:：]?\s*(\d+\s*/\s*\d+)")
_MAJOR_LABEL = re.compile(r"专\s*业\s*[:：]\s*([^\s，,、;；]+)")
_TITLE_LABEL = re.compile(r"(?:职\s*位|岗\s*位|职\s*务)\s*[:：]\s*([^\s，,、;；]+)")
_WECHAT = re.compile(r"微信\s*[:：]?\s*([\w-]{3,30})")
_CITY_LABEL = re.compile(r"(?:现居|所在城市|现居住地)\s*[:：]?\s*([\u4e00-\u9fa5]{2,12})")
_HOMETOWN = re.compile(r"籍\s*贯\s*[:：]?\s*([\u4e00-\u9fa5]{2,15})")
_ID_NUMBER = re.compile(r"(?<!\d)(\d{17}[\dXx])(?!\d)")

_PROGRAMMING = (
    "Python",
    "Java",
    "Go",
    "Golang",
    "C++",
    "C#",
    "C",
    "Rust",
    "TypeScript",
    "JavaScript",
    "Kotlin",
    "Swift",
    "PHP",
    "Ruby",
    "Scala",
    "SQL",
    "Shell",
)
_LANGUAGE_TESTS = (
    ("CET-6", ("cet-6", "cet6", "六级")),
    ("CET-4", ("cet-4", "cet4", "四级")),
    ("IELTS", ("雅思", "ielts")),
    ("TOEFL", ("托福", "toefl")),
    ("N1", ("n1",)),
    ("N2", ("n2",)),
)


@dataclass
class ParseResult:
    """解析产物：一份草稿，加一串需要人看一眼的问题。"""

    profile: Profile
    warnings: list[str] = field(default_factory=list)
    sections_found: list[str] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return not self.warnings and not self.sections_found


def _section_of(line: str) -> str | None:
    """判断这一行是不是小节标题。"""
    text = _normalize_headers(line)
    if not text or len(text) > _MAX_HEADER_LEN:
        return None
    if ":" in text or "：" in text:
        return None
    for key, words in SECTION_KEYWORDS.items():
        if any(word == text or text.endswith(word) for word in words):
            return key
    return None


def split_sections(text: str) -> tuple[list[str], dict[str, list[str]]]:
    """切成"表头块"与"各小节内容"。表头块在第一个标题之前。"""
    header_block: list[str] = []
    sections: dict[str, list[str]] = {}
    current: str | None = None

    for raw in text.split("\n"):
        line = nz.clean(raw)
        if not line:
            continue
        found = _section_of(line)
        if found:
            current = found
            sections.setdefault(current, [])
            continue
        if current is None:
            header_block.append(line)
        else:
            sections[current].append(line)

    return header_block, sections


# ---------------------------------------------------------------------------
# 各小节解析
# ---------------------------------------------------------------------------


def _parse_basic(header_block: list[str], basic_lines: list[str], result: ParseResult) -> Basic:
    pool = " \n ".join(header_block + basic_lines)
    basic = Basic()

    match = _NAME_LABEL.search(pool)
    if match:
        basic.name_cn = match.group(1)
    else:
        # 没写"姓名："时，第一行短中文名多半就是名字
        for line in header_block[:3]:
            candidate = _normalize_headers(line)
            if 2 <= len(candidate) <= 4 and re.fullmatch(r"[\u4e00-\u9fa5]{2,4}", candidate):
                basic.name_cn = candidate
                result.warnings.append(f"姓名按首行推断为「{candidate}」，请确认")
                break

    if match := _GENDER_LABEL.search(pool):
        basic.gender = nz.to_gender(match.group(1))

    for word in _POLITICAL:
        if word in pool:
            basic.political_status = word
            break

    if match := _FULL_DATE.search(pool):
        try:
            basic.birth_date = date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            result.warnings.append(f"出生日期无法解析：{match.group(0)}")
    elif month := nz.to_month(pool):
        # 只有年月时，日填 1 并在 warnings 里挑明 —— 猜出来的日期比没有更危险
        year, mon = month.split("-")
        basic.birth_date = date(int(year), int(mon), 1)
        result.warnings.append(f"出生日期只精确到月，日暂填 1，请核对（原始：{month}）")

    if match := _ID_NUMBER.search(pool):
        basic.id_number = match.group(1).upper()
    if match := _HOMETOWN.search(pool):
        basic.hometown = match.group(1)

    contact = Contact()
    contact.phone = nz.to_phone(pool)
    contact.email = nz.to_email(pool)
    if match := _WECHAT.search(pool):
        contact.wechat = match.group(1)
    if match := _CITY_LABEL.search(pool):
        contact.current_city = match.group(1)

    result.profile.contact = contact
    return basic


def _tokens(line: str) -> list[str]:
    """按空白与常见分隔符切成词元。"""
    return [token.strip("，,、;；|") for token in re.split(r"[\s\t|｜/]+", line) if token.strip()]


def _major_from_layout(block: list[str], school: str | None) -> str | None:
    """没有"专业："标签时，取学校后面第一个不是学历/时间/绩点的词元。

    中国简历最常见的排法是 ``2023.09 - 2027.06  某某大学  计算机科学与技术  本科``，
    学校和专业之间靠位置而非标签区分，只能按词序推断。
    """
    if not school:
        return None
    for line in block:
        if school not in line:
            continue
        tokens = _tokens(line)
        index = next((i for i, token in enumerate(tokens) if school in token), None)
        if index is None:
            continue
        for candidate in tokens[index + 1 :]:
            if not candidate or re.search(r"\d", candidate):
                continue
            if nz.to_degree(candidate) or nz.to_month(candidate):
                continue
            if not 2 <= len(candidate) <= 20:
                continue
            return candidate
    return None


def _title_from_layout(block: list[str], company: str | None) -> str | None:
    """没有"职位："标签时，取同一行里符合职位后缀特征的词元。"""
    for line in block:
        if company and company not in line:
            continue
        for candidate in reversed(_tokens(line)):
            if _TITLE_HINT.search(candidate) and 2 <= len(candidate) <= 20:
                return candidate
    return None


def _parse_educations(lines: list[str], result: ParseResult) -> list[Education]:
    """教育经历按"含时间区间的行"切块，每块一条。"""
    educations: list[Education] = []
    buffer: list[str] = []

    def flush(block: list[str]) -> None:
        text = " ".join(block)
        start, end = nz.parse_range(text)
        school_match = _SCHOOL.search(text)
        if not start and not school_match:
            return
        education = Education(start=start, end=end)
        if school_match:
            education.school = school_match.group(0)
        if match := _MAJOR_LABEL.search(text):
            education.major = match.group(1)
        if not education.major:
            education.major = _major_from_layout(block, education.school)
        education.degree = nz.to_degree(text)
        gpa, scale, percent = nz.parse_gpa(text)
        education.gpa = gpa
        education.gpa_scale = scale
        education.gpa_percent = percent
        if match := _RANKING.search(text):
            education.ranking = match.group(1).replace(" ", "")
        for line in block:
            if re.search(r"主修课程|主要课程|专业课程|相关课程", line):
                education.courses = nz.split_items(nz.strip_label(line))
                break
        educations.append(education)

    for line in lines:
        has_range = bool(nz.parse_range(line)[0]) or nz.is_present(line)
        if has_range and buffer:
            flush(buffer)
            buffer = [line]
        elif has_range:
            buffer = [line]
        else:
            buffer.append(line)
    if buffer:
        flush(buffer)

    for education in educations:
        if not education.degree:
            result.warnings.append(f"教育经历未识别出学历：{education.school or '未知学校'}")
        if not education.major:
            result.warnings.append(f"教育经历未识别出专业：{education.school or '未知学校'}")
    return educations


def _parse_experiences(lines: list[str], result: ParseResult) -> list[Experience]:
    experiences: list[Experience] = []
    buffer: list[str] = []

    def flush(block: list[str]) -> None:
        if not block:
            return
        text = " ".join(block)
        start, end = nz.parse_range(text)
        company = _COMPANY.search(text)
        if not start and not company:
            return
        experience = Experience(start=start, end=end)
        if company:
            experience.company = company.group(0)
        if match := _TITLE_LABEL.search(text):
            experience.title = match.group(1)
        if not experience.title:
            experience.title = _title_from_layout(block, experience.company)
        experience.kind = ExperienceKind.internship if "实习" in text else ExperienceKind.fulltime
        description = " ".join(
            line for line in block if not nz.parse_range(line)[0] and not _COMPANY.search(line)
        ).strip()
        experience.description = description or None
        experiences.append(experience)

    for line in lines:
        has_range = bool(nz.parse_range(line)[0]) or nz.is_present(line)
        if has_range and buffer:
            flush(buffer)
            buffer = [line]
        elif has_range:
            buffer = [line]
        else:
            buffer.append(line)
    if buffer:
        flush(buffer)

    for experience in experiences:
        if not experience.title:
            result.warnings.append(f"经历未识别出职位：{experience.company or '未知单位'}")
    return experiences


def _parse_projects(lines: list[str]) -> list[Project]:
    projects: list[Project] = []
    buffer: list[str] = []

    def flush(block: list[str]) -> None:
        if not block:
            return
        text = " ".join(block)
        start, end = nz.parse_range(text)
        project = Project(start=start, end=end)

        first_line = block[0]
        if role := _ROLE_HINT.search(first_line):
            project.role = role.group(1)
        # 项目名取首行里第一个不像"角色"的词元，避免把"负责人"当成项目名
        project.name = next(
            (
                token
                for token in _tokens(first_line)
                if not _ROLE_HINT.search(token) and not re.search(r"\d", token) and len(token) >= 2
            ),
            None,
        )
        # 描述只取标题行之后的内容，否则项目名会被重复写进描述
        project.description = " ".join(block[1:]).strip() or None
        projects.append(project)

    for line in lines:
        if re.search(r"项目|系统|平台", line) and len(line) <= 40:
            if buffer:
                flush(buffer)
            buffer = [line]
        else:
            buffer.append(line)
    if buffer:
        flush(buffer)
    return projects


def _parse_skills(lines: list[str], result: ParseResult) -> Skills:
    text = " ".join(lines)
    skills = Skills()

    found = [
        lang
        for lang in _PROGRAMMING
        if re.search(rf"(?<![A-Za-z]){re.escape(lang)}(?![A-Za-z])", text)
    ]
    if "Golang" in found and "Go" in found:
        found.remove("Go")
    skills.programming = found

    lowered = text.lower()
    for label, keywords in _LANGUAGE_TESTS:
        if any(keyword in lowered for keyword in keywords):
            skills.languages.append(
                Language(
                    name="英语" if label.startswith(("CET", "IELTS", "TOEFL")) else "日语",
                    level=label,
                )
            )

    for line in lines:
        if "证书" in line or "资格" in line:
            for item in nz.split_items(nz.strip_label(line)):
                if 2 <= len(item) <= 20:
                    skills.certificates.append(Certificate(name=item))
    return skills


def _strip_paren(text: str) -> str:
    """去掉括号里的补充说明，如 "国家励志奖学金(2025.10)" → "国家励志奖学金"。"""
    return re.sub(r"[（(][^）)]*[）)]", "", text).strip()


def _parse_awards(lines: list[str]) -> list[Award]:
    awards: list[Award] = []
    for line in lines:
        if not re.search(r"奖学金|竞赛|大赛|奖|荣誉", line):
            continue
        for item in nz.split_items(line):
            if not re.search(r"奖学金|竞赛|大赛|奖", item):
                continue
            award = Award(name=_strip_paren(item), date=nz.to_month(item))
            if "国家" in item:
                award.level = "国家级"
            elif "省" in item:
                award.level = "省级"
            elif "校" in item:
                award.level = "校级"
            awards.append(award)
    return awards


def _parse_job_intent(header_block: list[str], basic_lines: list[str]) -> JobIntent:
    """求职意向通常在表头，一行写完。"""
    pool = " ".join(header_block + basic_lines)
    intent = JobIntent()
    if match := _INTENT.search(pool):
        intent.target_role = match.group(1)
    return intent


def parse_resume(text: str) -> ParseResult:
    """把简历文本解析成 profile 草稿。"""
    result = ParseResult(profile=Profile())
    header_block, sections = split_sections(text)
    result.sections_found = sorted(sections)

    result.profile.basic = _parse_basic(header_block, sections.get("basic", []), result)
    result.profile.educations = _parse_educations(sections.get("education", []), result)
    result.profile.experiences = _parse_experiences(sections.get("experience", []), result)
    result.profile.projects = _parse_projects(sections.get("project", []))
    result.profile.skills = _parse_skills(sections.get("skills", []), result)
    result.profile.skills.awards = _parse_awards(sections.get("award", []))
    result.profile.job_intent = _parse_job_intent(header_block, sections.get("basic", []))

    if not result.profile.educations:
        result.warnings.append("未识别到教育经历小节，请检查简历里是否有「教育经历」标题")
    if not result.profile.basic.name_cn:
        result.warnings.append("未识别到姓名")
    if not result.profile.contact.phone:
        result.warnings.append("未识别到手机号")

    return result
