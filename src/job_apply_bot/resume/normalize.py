"""字段归一化。

简历里的时间写法千奇百怪：``2023.09``、``2023/9``、``2023年9月``、``23年9月``。
网申系统的输入格式又各不相同。这一层负责把它们收敛成统一形态，
是"填错"问题的第一道防线——统计下来，填错的字段大部分源于格式没归一。

原则：**存事实，不存格式**。这里只产出 ``YYYY-MM``，页面要什么格式由适配器转换。
"""

from __future__ import annotations

import re

from job_apply_bot.resume.schema import Degree, Gender

# 年份 + 分隔符 + 月份。分隔符涵盖 . / - 年月 以及空白。
_MONTH = re.compile(r"(?<!\d)((?:19|20)\d{2})\s*[年./\-]\s*(\d{1,2})(?!\d)")

# 区间分隔符：- – — ~ ～ 至 到
_RANGE_SEP = re.compile(r"\s*(?:-|–|—|~|～|至|到|－)\s*")

_PRESENT_WORDS = ("至今", "现在", "今", "present", "now", "current")

_PHONE = re.compile(r"(?<!\d)(1[3-9]\d{9})(?!\d)")
_PHONE_LOOSE = re.compile(r"(?<!\d)(1[3-9]\d)[\s\-]?(\d{4})[\s\-]?(\d{4})(?!\d)")

_FULLWIDTH_SPACE = "\u3000"

# 只转换会影响正则匹配的全角字符。
# 不用 unicodedata.normalize("NFKC", ...)：那会把中文逗号「，」也转成半角「,」，
# 简历正文的标点会整体变样，写回 profile 后读起来很别扭。
_FULLWIDTH_MAP: dict[int, str] = {ord("０") + i: str(i) for i in range(10)}
_FULLWIDTH_MAP.update(
    {
        ord("．"): ".",
        ord("／"): "/",
        ord("－"): "-",
        ord("～"): "~",
        ord("％"): "%",
        ord("＠"): "@",
        _FULLWIDTH_SPACE: " ",
    }
)


def clean(text: str) -> str:
    """统一全角数字与空白，去掉多余空格。

    只动数字、数值符号和全角空格，中文标点保持原样。
    """
    if not text:
        return ""
    text = text.translate(_FULLWIDTH_MAP)
    return re.sub(r"[ \t]+", " ", text).strip()


def to_month(text: str) -> str | None:
    """从任意写法提取单个月份，返回 ``YYYY-MM``。"""
    match = _MONTH.search(clean(text))
    if not match:
        return None
    year, month = int(match.group(1)), int(match.group(2))
    if not 1 <= month <= 12:
        return None
    return f"{year:04d}-{month:02d}"


def parse_range(text: str) -> tuple[str | None, str | None]:
    """解析时间段。

    >>> parse_range("2023.09 - 2027.06")
    ('2023-09', '2027-06')
    >>> parse_range("2026年7月 - 至今")
    ('2026-07', None)

    返回 ``(start, end)``，``end`` 为 ``None`` 表示至今，或只有一个时间点时无法判断结束。
    """
    cleaned = clean(text)
    months = [f"{int(y):04d}-{int(m):02d}" for y, m in _MONTH.findall(cleaned)]
    months = [m for m in months if 1 <= int(m[-2:]) <= 12]

    if not months:
        return None, None
    if len(months) == 1:
        return months[0], None

    start, end = months[0], months[1]
    if start > end:  # 防御倒序写法
        start, end = end, start
    return start, end


def is_present(text: str) -> bool:
    """判断这段文字是否表示"至今"。"""
    lowered = clean(text).lower()
    return any(word in lowered for word in _PRESENT_WORDS)


def to_phone(text: str) -> str | None:
    """提取 11 位手机号，容忍中间有空格或连字符。"""
    cleaned = clean(text)
    match = _PHONE.search(cleaned)
    if match:
        return match.group(1)
    loose = _PHONE_LOOSE.search(cleaned)
    if loose:
        return "".join(loose.groups())
    return None


def to_email(text: str) -> str | None:
    match = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", clean(text))
    return match.group(0) if match else None


def to_gender(text: str) -> Gender | None:
    cleaned = clean(text)
    if re.search(r"(性别\s*[:：]?\s*)?男", cleaned) and "女" not in cleaned:
        return Gender.male
    if re.search(r"(性别\s*[:：]?\s*)?女", cleaned) and "男" not in cleaned:
        return Gender.female
    return None


_DEGREE_RULES: tuple[tuple[tuple[str, ...], Degree], ...] = (
    (("博士", "phd", "ph.d"), Degree.phd),
    (("硕士", "研究生", "master"), Degree.master),
    (("本科", "学士", "bachelor"), Degree.bachelor),
    (("大专", "专科", "associate"), Degree.associate),
    (("高中", "中专", "highschool"), Degree.highschool),
)


def to_degree(text: str) -> Degree | None:
    """把学历文案映射到枚举。按"学历从高到低"匹配，先命中博士再命中硕士。"""
    cleaned = clean(text).lower()
    for keywords, degree in _DEGREE_RULES:
        if any(keyword in cleaned for keyword in keywords):
            return degree
    return None


def parse_gpa(text: str) -> tuple[float | None, float | None, str | None]:
    """解析绩点，返回 ``(gpa, gpa_scale, percent_text)``。

    >>> parse_gpa("GPA 3.62/4.0")
    (3.62, 4.0, None)
    >>> parse_gpa("平均分 85.5")
    (85.5, 100.0, None)
    >>> parse_gpa("前 15%")
    (None, None, '前 15%')
    """
    cleaned = clean(text)

    ratio = re.search(r"(\d(?:\.\d+)?)\s*/\s*(\d(?:\.\d+)?)", cleaned)
    if ratio:
        return float(ratio.group(1)), float(ratio.group(2)), None

    percent = re.search(r"(前\s*\d+(?:\.\d+)?\s*%)", cleaned)
    if percent:
        return None, None, percent.group(1).replace(" ", "")

    score = re.search(
        r"(?:GPA|绩点|平均分|均分)[:：]?\s*(\d{1,3}(?:\.\d+)?)", cleaned, re.IGNORECASE
    )
    if score:
        value = float(score.group(1))
        # 大于 5 基本可以断定是百分制
        return value, (100.0 if value > 5 else None), None

    return None, None, None


def split_items(text: str) -> list[str]:
    """按常见分隔符切分列表型字段（技能、课程、技术栈）。"""
    cleaned = clean(text)
    if not cleaned:
        return []
    parts = re.split(r"[,，、;；/|]", cleaned)
    return [part.strip() for part in parts if part.strip()]


def strip_label(text: str) -> str:
    """去掉 "姓名：张三" 里的标签前缀，返回 "张三"。"""
    return re.sub(r"^[^:：]{1,8}[:：]\s*", "", clean(text)).strip()
