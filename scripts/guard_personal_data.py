#!/usr/bin/env python3
"""提交前的个人数据检查。

用法：
    python scripts/guard_personal_data.py            # 检查暂存区
    python scripts/guard_personal_data.py --all      # 检查全部已跟踪文件

检查两件事：
1. 文件名 —— 敏感路径被 add 进版本库
2. 文件内容 —— 出现疑似真实身份证号、手机号

这是最后一道自动防线，不是唯一一道。它能拦住形态规整的数字，
拦不住"张三"这样的人名。真正的把关还是你自己 git diff 一遍。

退出码：0 通过，1 发现问题。
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# 这些路径一旦被提交就是事故。
FORBIDDEN_PATHS = {
    "profile.json",
    "ledger.db",
}

FORBIDDEN_DIRS = {
    ".auth",
    "inbox",
    "resumes",
    "runs",
    "files",
    "artifacts",
}

FORBIDDEN_SUFFIXES = {
    ".db",
    ".sqlite",
    ".sqlite3",
}

# 允许的例外：示例文件、测试用脱敏样本。
ALLOWED_NAMES = {
    "profile.example.json",
}

# 文档与测试里用到的、明确是虚构的数据，不该报警。
# 新增白名单前请确认该值确实是编造的（比如来源是测试用例或示例文档）。
FAKE_VALUES = {
    "13800138000",
    "13900139000",
    "310101********1234",
    # tests/test_schema.py 里的校验用例，末尾分别覆盖纯数字与 X 两种形态
    "310101200304151234",
    "31010120030415123x",
    "31010120030415123X",
}

PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "疑似身份证号",
        re.compile(
            r"(?<!\d)[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx](?!\d)"
        ),
    ),
    ("疑似手机号", re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")),
]

TEXT_SUFFIXES = {
    ".py",
    ".md",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".txt",
    ".cfg",
    ".ini",
    ".html",
    ".htm",
    ".css",
    ".js",
    ".ts",
    ".sh",
    ".log",
    ".env",
}

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".mypy_cache", ".ruff_cache"}


def _git(*args: str) -> list[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        return []
    return [line for line in result.stdout.splitlines() if line.strip()]


def staged_files() -> list[str]:
    return _git("diff", "--cached", "--name-only", "--diff-filter=ACM")


def tracked_files() -> list[str]:
    return _git("ls-files")


def is_forbidden_path(rel: str) -> str | None:
    parts = Path(rel).parts
    if not parts:
        return None
    if Path(rel).name in ALLOWED_NAMES:
        return None
    if Path(rel).name in FORBIDDEN_PATHS:
        return "个人数据文件"
    if any(part in FORBIDDEN_DIRS for part in parts[:-1]):
        return "个人数据目录"
    if Path(rel).suffix in FORBIDDEN_SUFFIXES:
        return "数据库文件"
    return None


def scan_content(path: Path) -> list[tuple[str, int, str]]:
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []

    hits: list[tuple[str, int, str]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for label, pattern in PATTERNS:
            for match in pattern.finditer(line):
                value = match.group(0)
                if value in FAKE_VALUES:
                    continue
                hits.append((label, lineno, value))
    return hits


def collect(files: list[str]) -> list[str]:
    problems: list[str] = []

    for rel in files:
        category = is_forbidden_path(rel)
        if category:
            problems.append(f"[路径] {rel} —— {category}，不应进入版本库")

        target = REPO_ROOT / rel
        if not target.is_file():
            continue
        for label, lineno, value in scan_content(target):
            masked = f"{value[:4]}***{value[-2:]}"
            problems.append(f"[内容] {rel}:{lineno} —— {label}（{masked}）")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="检查个人数据是否被误提交")
    parser.add_argument("--all", action="store_true", help="检查全部已跟踪文件，而不只是暂存区")
    args = parser.parse_args()

    files = tracked_files() if args.all else staged_files()

    if not files:
        print("没有待检查的文件。")
        return 0

    problems = collect(files)

    if not problems:
        print(f"检查通过：{len(files)} 个文件，未发现个人数据。")
        return 0

    print("发现疑似个人数据，已阻止提交：\n", file=sys.stderr)
    for item in problems:
        print(f"  {item}", file=sys.stderr)
    print(
        "\n如果确认是虚构数据，请加入 scripts/guard_personal_data.py 的 FAKE_VALUES 白名单。\n"
        "如果是真实数据，先 git restore --staged <file>，再确认它已被 .gitignore 覆盖。",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
