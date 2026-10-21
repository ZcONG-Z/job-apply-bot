"""仓库层面的冒烟测试：命令可用、示例数据合法、安全边界没被改坏。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from job_apply_bot import __version__
from job_apply_bot.cli import app

REPO_ROOT = Path(__file__).resolve().parent.parent

runner = CliRunner()


def test_version_is_exposed() -> None:
    assert __version__
    assert isinstance(__version__, str)


def test_cli_help_works() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0, result.output
    assert "jobapply" in result.output


def test_cli_reports_unimplemented_commands_gracefully() -> None:
    # apply / status 已实现；adapter 调试命令仍在路线图里，应优雅地提示未实现
    result = runner.invoke(app, ["adapter", "list"])
    assert result.exit_code == 1
    assert "尚未实现" in result.output


def test_status_command_reads_empty_ledger() -> None:
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "台账" in result.output


def test_example_profile_is_valid_json() -> None:
    data = json.loads((REPO_ROOT / "profile.example.json").read_text(encoding="utf-8"))
    assert data["meta"]["version"] == 1


@pytest.mark.parametrize(
    "key",
    ["meta", "basic", "contact", "job_intent", "educations", "experiences", "skills"],
)
def test_example_profile_has_core_sections(key: str) -> None:
    data = json.loads((REPO_ROOT / "profile.example.json").read_text(encoding="utf-8"))
    assert key in data, f"profile.example.json 缺少 {key}"


def test_example_profile_contains_no_real_looking_id() -> None:
    """示例文件里的身份证必须是脱敏形态，防止有人照着填错。"""
    data = json.loads((REPO_ROOT / "profile.example.json").read_text(encoding="utf-8"))
    id_number = data["basic"]["id_number"]
    assert "*" in id_number, "示例身份证号必须脱敏"


GITIGNORE_MUST_CONTAIN = [
    "profile.json",
    ".auth/",
    "resumes/",
    "inbox/",
    "runs/",
    "*.pdf",
    "*.docx",
]


@pytest.mark.parametrize("pattern", GITIGNORE_MUST_CONTAIN)
def test_gitignore_protects_personal_data(pattern: str) -> None:
    """这条测试是安全边界的一部分：别让人顺手删掉 .gitignore 里的规则。"""
    content = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    lines = {line.strip() for line in content.splitlines()}
    assert pattern in lines, f".gitignore 缺少敏感数据规则：{pattern}"


def test_license_is_mit() -> None:
    header = (REPO_ROOT / "LICENSE").read_text(encoding="utf-8")[:32]
    assert "MIT License" in header
