"""命令行入口。

当前阶段只提供命令骨架：`jobapply --help` 可用，具体子命令会在对应 Phase 实现。
见 docs/roadmap.md。
"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from job_apply_bot import __version__

console = Console()

app = typer.Typer(
    name="jobapply",
    help="把网申表单里那些重复录入的活交给脚本。填完停在提交前，不代你提交。",
    no_args_is_help=True,
    add_completion=False,
)

profile_app = typer.Typer(help="结构化简历的生成与确认。", no_args_is_help=True)
adapter_app = typer.Typer(help="站点适配器的调试工具。", no_args_is_help=True)

app.add_typer(profile_app, name="profile")
app.add_typer(adapter_app, name="adapter")


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"job-apply-bot {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool | None = typer.Option(
        None,
        "--version",
        "-V",
        callback=_version_callback,
        is_eager=True,
        help="显示版本号并退出。",
    ),
) -> None:
    """job-apply-bot —— 本地运行、半自动、永远停在提交前。"""


def _todo(phase: str, module: str) -> None:
    console.print(f"[yellow]该功能尚未实现[/yellow]（{phase} · {module}）")
    console.print("进度见 [bold]docs/roadmap.md[/bold]")
    raise typer.Exit(code=1)


# --------------------------------------------------------------------------
# profile
# --------------------------------------------------------------------------


@profile_app.command("build")
def profile_build(
    source: Path = typer.Argument(..., help="简历文件（PDF / DOCX）。"),
    out: Path = typer.Option(Path("profile.json"), "--out", "-o", help="输出路径。"),
    llm: bool = typer.Option(
        False, "--llm", help="规则解析失败时用大模型兜底（会把简历文本发出去）。"
    ),
) -> None:
    """从简历文件生成 profile.json。"""
    _ = (source, out, llm)
    _todo("Phase 0", "resume/parse.py")


@profile_app.command("review")
def profile_review(
    path: Path = typer.Option(Path("profile.json"), "--file", "-f", help="要确认的 profile 文件。"),
) -> None:
    """逐字段确认简历信息，支持修改与标记待补。"""
    _ = path
    _todo("Phase 0", "resume/review.py")


@profile_app.command("validate")
def profile_validate(
    path: Path = typer.Option(Path("profile.json"), "--file", "-f", help="要校验的 profile 文件。"),
) -> None:
    """校验 profile 是否符合 schema。"""
    _ = path
    _todo("Phase 0", "resume/schema.py")


# --------------------------------------------------------------------------
# apply
# --------------------------------------------------------------------------


@app.command("apply")
def apply(
    url: str = typer.Argument(..., help="网申页面地址。"),
    profile_path: Path = typer.Option(
        Path("profile.json"), "--profile", "-p", help="使用的 profile 文件。"
    ),
    resume: Path | None = typer.Option(None, "--resume", "-r", help="上传用的简历原件。"),
    resume_run: bool = typer.Option(False, "--resume-run", help="从上次中断的步骤继续。"),
    debug: bool = typer.Option(False, "--debug", help="调试模式，输出完整字段值（含敏感信息）。"),
) -> None:
    """填写指定网站的网申表单，填完停在提交按钮前。"""
    _ = (url, profile_path, resume, resume_run, debug)
    _todo("Phase 1", "engine/actions.py")


@app.command("status")
def status(
    limit: int = typer.Option(20, "--limit", "-n", help="显示最近多少条。"),
) -> None:
    """查看投递台账。"""
    _ = limit
    _todo("Phase 3", "ledger/db.py")


# --------------------------------------------------------------------------
# adapter
# --------------------------------------------------------------------------


@adapter_app.command("list")
def adapter_list() -> None:
    """列出已安装的站点适配器。"""
    _todo("Phase 2", "adapters/registry.py")


@adapter_app.command("check")
def adapter_check(
    site: str = typer.Argument(..., help="适配器标识，如 moka。"),
) -> None:
    """检查适配器声明的字段能否全部定位到。"""
    _ = site
    _todo("Phase 2", "adapters/base.py")


@adapter_app.command("snapshot")
def adapter_snapshot(
    url: str = typer.Argument(..., help="要抓取快照的页面地址。"),
    out: Path = typer.Option(
        ..., "--out", "-o", help="快照输出路径（需放在 tests/fixtures/ 下）。"
    ),
) -> None:
    """抓取脱敏后的页面 HTML 快照，用于写离线测试。"""
    _ = (url, out)
    _todo("Phase 2", "engine/artifacts.py")


if __name__ == "__main__":
    app()
