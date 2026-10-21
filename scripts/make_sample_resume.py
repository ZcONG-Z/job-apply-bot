#!/usr/bin/env python3
"""生成虚构的样本简历（DOCX 与 PDF），用于测试解析器。

内容全部是假数据：手机号用 13800138000，邮箱 example.com，学校公司一律"某某"。

    python scripts/make_sample_resume.py --out tests/fixtures
"""

from __future__ import annotations

import argparse
from pathlib import Path

SAMPLE_LINES = [
    "张三",
    "求职意向：后端开发工程师",
    "手机：13800138000    邮箱：zhangsan@example.com",
    "性别：男    出生日期：2003-04-15    政治面貌：共青团员    籍贯：江苏省南京市",
    "现居：上海市",
    "",
    "教育经历",
    "2023.09 - 2027.06    某某大学    计算机科学与技术    本科",
    "GPA 3.62/4.0    排名 12/180",
    "主修课程：数据结构、操作系统、计算机网络",
    "",
    "实习经历",
    "2026.07 - 2026.09    某某科技有限公司    后端开发实习生",
    "负责订单服务重构，将核心接口 P99 从 420ms 降至 130ms。",
    "",
    "项目经历",
    "分布式任务调度平台    负责人",
    "支持百万级定时任务的调度与故障转移。",
    "",
    "专业技能",
    "编程语言：Python、Go、Java",
    "英语：CET-6（546 分）",
    "",
    "荣誉奖项",
    "国家励志奖学金（2025.10）",
    "全国大学生数学建模竞赛省级二等奖（2024.11）",
]


def write_docx(path: Path) -> None:
    from docx import Document

    document = Document()
    for line in SAMPLE_LINES:
        document.add_paragraph(line)
    document.save(str(path))


def write_pdf(path: Path) -> None:
    """用 PyMuPDF 直接排版生成 PDF，避免引入额外字体依赖。"""
    try:
        import pymupdf
    except ImportError:
        import fitz as pymupdf

    document = pymupdf.open()
    page = document.new_page()
    y = 60
    for line in SAMPLE_LINES:
        if line:
            page.insert_text((50, y), line, fontname="china-s", fontsize=11)
        y += 20
        if y > 780:
            page = document.new_page()
            y = 60
    document.save(str(path))
    document.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="生成虚构样本简历")
    parser.add_argument("--out", default="tests/fixtures", help="输出目录")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    docx_path = out_dir / "sample-resume.docx"
    pdf_path = out_dir / "sample-resume.pdf"

    write_docx(docx_path)
    print(f"wrote {docx_path} ({docx_path.stat().st_size} bytes)")

    write_pdf(pdf_path)
    print(f"wrote {pdf_path} ({pdf_path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
