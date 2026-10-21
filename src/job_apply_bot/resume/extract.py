"""从简历文件抽取纯文本。

只解决一件事：把文件变成**保留原有顺序**的文本行。不做结构识别，那是 parse 层的事。

为什么不用通体 PDF 转文本库：教育经历这类信息的正确性依赖行序，
版面顺序一旦被打乱（比如双栏简历被按阅读框重排），后面的解析就全错。
"""

from __future__ import annotations

from pathlib import Path

PDF_SUFFIX = ".pdf"
DOCX_SUFFIX = ".docx"
LEGACY_DOC_SUFFIX = ".doc"

SUPPORTED_SUFFIXES = frozenset({PDF_SUFFIX, DOCX_SUFFIX})


class UnsupportedFormatError(ValueError):
    """文件格式不受支持。"""


class ResumeFileNotFoundError(FileNotFoundError):
    """简历文件不存在。"""


def extract_text(path: Path) -> str:
    """抽取简历正文，返回用换行连接的文本。"""
    path = Path(path)
    if not path.exists():
        raise ResumeFileNotFoundError(f"找不到简历文件：{path}")

    suffix = path.suffix.lower()
    if suffix == PDF_SUFFIX:
        return _extract_pdf(path)
    if suffix == DOCX_SUFFIX:
        return _extract_docx(path)
    if suffix == LEGACY_DOC_SUFFIX:
        raise UnsupportedFormatError(
            "不支持旧版 .doc 格式。请用 Word 另存为 .docx 或导出 PDF —— "
            "旧版二进制格式没有可靠的跨平台解析方案。"
        )
    raise UnsupportedFormatError(
        f"不支持的格式 {suffix!r}，目前支持：{', '.join(sorted(SUPPORTED_SUFFIXES))}"
    )


def _open_pdf(path: Path):
    """兼容 pymupdf 1.x 的 ``fitz`` 与 2.x 的 ``pymupdf`` 两种导入名。"""
    try:
        import pymupdf  # type: ignore[import-not-found]

        return pymupdf.open(path)
    except ImportError:
        import fitz  # type: ignore[import-not-found]

        return fitz.open(path)


def _extract_pdf(path: Path) -> str:
    document = _open_pdf(path)
    try:
        pages = [page.get_text("text") for page in document]
    finally:
        document.close()
    return _tidy("\n".join(pages))


def _extract_docx(path: Path) -> str:
    from docx import Document

    document = Document(str(path))
    lines: list[str] = [paragraph.text for paragraph in document.paragraphs]

    for table in document.tables:
        for row in table.rows:
            cells: list[str] = []
            for cell in row.cells:
                text = cell.text.strip()
                # 合并单元格会让同一段文字在相邻 cell 重复出现，去重后再拼接
                if text and (not cells or cells[-1] != text):
                    cells.append(text)
            if cells:
                lines.append("\t".join(cells))

    return _tidy("\n".join(lines))


def _tidy(text: str) -> str:
    """清掉连续空行与行尾空白，保留行序。"""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    result: list[str] = []
    for line in lines:
        if not line and (not result or not result[-1]):
            continue
        result.append(line)
    return "\n".join(result).strip()
