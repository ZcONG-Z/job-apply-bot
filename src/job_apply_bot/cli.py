"""命令行入口。

已实现：``profile build`` / ``profile validate`` / ``profile review``
未实现：``apply`` / ``status`` / ``adapter *``（见 docs/roadmap.md）
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import typer
from pydantic import ValidationError
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from job_apply_bot import __version__
from job_apply_bot.resume.extract import UnsupportedFormatError, extract_text
from job_apply_bot.resume.parse import ParseResult, parse_resume
from job_apply_bot.resume.schema import Profile

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

DEFAULT_PROFILE = Path("profile.json")


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


# ---------------------------------------------------------------------------
# profile build
# ---------------------------------------------------------------------------


def _print_result(result: ParseResult) -> None:
    profile = result.profile

    table = Table(title="抽取结果", show_header=True, header_style="bold")
    table.add_column("字段")
    table.add_column("值")
    table.add_column("来源")

    def add(field_name: str, value: object, source: str = "regex") -> None:
        shown = "—" if value in (None, "", []) else str(value)
        table.add_row(field_name, f"[red]{shown}[/red]" if shown == "—" else shown, source)

    add("姓名", profile.basic.name_cn)
    add("性别", profile.basic.gender.value if profile.basic.gender else None)
    add("出生日期", profile.basic.birth_date, "regex（零容忍）")
    add("身份证", profile.basic.id_number, "regex（零容忍）")
    add("手机", profile.contact.phone, "regex（零容忍）")
    add("邮箱", profile.contact.email)
    for index, education in enumerate(profile.educations):
        label = "教育经历" if index == 0 else f"教育经历[{index}]"
        add(f"{label} 学校", education.school, "regex（零容忍）")
        add(f"{label} 专业", education.major)
        add(
            f"{label} 起止",
            f"{education.start or '?'} ~ {education.end or '至今'}" if education.start else None,
            "normalize（零容忍）",
        )
        add(f"{label} 绩点", education.gpa)
    for index, experience in enumerate(profile.experiences):
        add(f"经历[{index}] 单位", experience.company)
        add(f"经历[{index}] 职位", experience.title)
    if profile.skills.programming:
        add("编程语言", "、".join(profile.skills.programming))

    console.print(table)
    if result.sections_found:
        console.print(f"[dim]识别到的小节：{', '.join(result.sections_found)}[/dim]")


def _print_warnings(result: ParseResult) -> None:
    if not result.warnings:
        return
    body = "\n".join(f"  • {item}" for item in result.warnings)
    console.print(Panel(body, title=f"需要你确认 {len(result.warnings)} 项", border_style="yellow"))


@profile_app.command("build")
def profile_build(
    source: Path = typer.Argument(..., help="简历文件（PDF / DOCX）。"),
    out: Path = typer.Option(DEFAULT_PROFILE, "--out", "-o", help="输出路径。"),
    yes: bool = typer.Option(False, "--yes", "-y", help="不询问，直接写入。"),
    force: bool = typer.Option(False, "--force", help="覆盖已存在的输出文件。"),
) -> None:
    """从简历文件生成 profile.json 草稿。"""
    try:
        text = extract_text(source)
    except (UnsupportedFormatError, FileNotFoundError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc

    if not text.strip():
        console.print("[red]文件里没有可提取的文字。扫描件需要先做 OCR。[/red]")
        raise typer.Exit(code=1)

    result = parse_resume(text)
    _print_result(result)
    _print_warnings(result)

    missing = result.profile.missing_required()
    if missing:
        console.print(f"[yellow]仍缺少 {len(missing)} 个常用字段：[/yellow] {', '.join(missing)}")

    if out.exists() and not force:
        console.print(f"[red]{out} 已存在。[/red]用 --force 覆盖，或换个 --out 路径。")
        raise typer.Exit(code=1)

    if not yes:
        console.print(
            "\n[bold]写入前请核对上表。[/bold]"
            "零容忍字段（出生日期、身份证、学校、起止时间）填错后很难在系统里改。"
        )
        if not typer.confirm(f"确认写入 {out}？", default=False):
            console.print("已取消。")
            raise typer.Exit(code=1)

    result.profile.meta.source_file = source.name
    result.profile.meta.updated_at = date.today().isoformat()
    out.write_text(
        json.dumps(result.profile.to_json_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    console.print(f"[green]已写入 {out}[/green]")
    console.print(f"下一步：jobapply profile review -f {out}")


# ---------------------------------------------------------------------------
# profile validate / review
# ---------------------------------------------------------------------------


def _load_profile(path: Path) -> Profile:
    if not path.exists():
        console.print(f"[red]找不到 {path}[/red]")
        raise typer.Exit(code=1)
    try:
        return Profile.model_validate_json(path.read_text(encoding="utf-8"))
    except ValidationError as exc:
        console.print(f"[red]{path} 不符合 schema：[/red]")
        for error in exc.errors():
            location = ".".join(str(part) for part in error["loc"])
            console.print(f"  • {location}: {error['msg']}")
        raise typer.Exit(code=1) from exc


@profile_app.command("validate")
def profile_validate(
    path: Path = typer.Option(DEFAULT_PROFILE, "--file", "-f", help="要校验的 profile 文件。"),
) -> None:
    """校验 profile 是否符合 schema。"""
    profile = _load_profile(path)
    missing = profile.missing_required()
    console.print(f"[green]格式校验通过[/green]：{path}")
    if missing:
        console.print(f"[yellow]以下常用字段为空：[/yellow] {', '.join(missing)}")
    else:
        console.print("[green]常用字段齐全[/green]")


@profile_app.command("review")
def profile_review(
    path: Path = typer.Option(DEFAULT_PROFILE, "--file", "-f", help="要确认的 profile 文件。"),
) -> None:
    """逐项确认高风险字段。无法交互时只列出待确认项。"""
    profile = _load_profile(path)
    pending: list[tuple[str, object]] = [
        ("basic.birth_date", profile.basic.birth_date),
        ("basic.id_number", profile.basic.id_number),
        ("basic.name_cn", profile.basic.name_cn),
        ("contact.phone", profile.contact.phone),
    ]
    for index, education in enumerate(profile.educations):
        pending.append((f"educations.{index}.school", education.school))
        pending.append((f"educations.{index}.start", education.start))
        pending.append((f"educations.{index}.end", education.end))

    table = Table(title="待确认的高风险字段", header_style="bold")
    table.add_column("路径")
    table.add_column("当前值")
    for key, value in pending:
        table.add_row(key, "—" if value is None else str(value))
    console.print(table)

    if not sys.stdin.isatty():
        console.print("[yellow]当前不是交互式终端，跳过逐项确认。[/yellow]")
        console.print("请人工核对上表，或用 --file 指定其他文件。")
        return

    console.print("\n[bold]直接回车表示确认，输入新值则替换。[/bold]")
    edits: dict[str, str] = {}
    for key, value in pending:
        answer = typer.prompt(f"{key} [{value}]", default="", show_default=False).strip()
        if answer and answer != str(value):
            edits[key] = answer

    if not edits:
        console.print("未做修改。")
        return

    try:
        profile = apply_edits(profile, edits)
    except ValidationError as exc:
        console.print("[red]修改后的值不符合 schema，未写回文件：[/red]")
        for error in exc.errors():
            location = ".".join(str(part) for part in error["loc"])
            console.print(f"  • {location}: {error['msg']}")
        raise typer.Exit(code=1) from exc

    path.write_text(
        json.dumps(profile.to_json_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    console.print(f"[green]已更新 {len(edits)} 个字段并写回 {path}[/green]")


def _set_in_dict(data: dict[str, object], path: str, value: str) -> None:
    """在纯 dict 上按点路径赋值。"""
    parts = path.split(".")
    target: object = data
    for part in parts[:-1]:
        target = (
            target[int(part)] if isinstance(target, list) else target.setdefault(part, {})  # type: ignore[union-attr]
        )
    last = parts[-1]
    if isinstance(target, list):
        target[int(last)] = value
    else:
        target[last] = value  # type: ignore[index]


def apply_edits(profile: Profile, edits: dict[str, str]) -> Profile:
    """按 ``{点路径: 新值}`` 修改并重新校验。

    不在模型对象上直接 ``setattr``：pydantic 默认不在属性赋值时校验，
    把字符串塞进 ``birth_date`` 这种日期字段会让模型内部出现错误类型
    （序列化时还会报警告）。正确做法是先在纯 dict 上改，再整体校验一次，
    让类型转换和约束统一生效。

    校验失败抛 ``ValidationError``，调用方负责提示，且不要写入磁盘。
    """
    data = profile.to_json_dict()
    for path, value in edits.items():
        _set_in_dict(data, path, value)
    return Profile.model_validate(data)


# ---------------------------------------------------------------------------
# 未实现
# ---------------------------------------------------------------------------


@app.command("apply")
def apply(
    url: str = typer.Argument(..., help="网申页面地址。"),
    profile_path: Path = typer.Option(
        DEFAULT_PROFILE, "--profile", "-p", help="使用的 profile 文件。"
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
