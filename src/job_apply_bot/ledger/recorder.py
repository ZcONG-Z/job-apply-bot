"""投递台账：每次 apply 留一行记录。

JSONL 追加式——一行一次投递，人肉可读、``git`` 友好、崩溃最多损失最后一行。
设计文档里的 SQLite 台账排在 Phase 3；到期迁移时只需换掉本模块内部实现，
对外的 ``record`` / ``read_all`` / ``summarize`` 不变。

台账只存路径与状态，**不存任何字段内容**（身份证、手机号不进台账）。
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

# 状态取值。注意没有 "submitted"——本工具永不提交，
# 人工提交后的回填由用户自己维护（或 Phase 3 的 status 命令扩展）。
STATUS_FILLED = "filled_pending_submit"  # 已填完，停在提交前，等人工核对
STATUS_ABORTED = "aborted"  # 中途放弃（必填字段失败、用户取消等）


def default_path() -> Path:
    """默认台账位置：当前目录下 ``.jobapply/ledger.jsonl``。"""
    return Path.cwd() / ".jobapply" / "ledger.jsonl"


def record(
    path: Path,
    *,
    site: str,
    url: str,
    status: str,
    report_path: str | None = None,
    note: str = "",
) -> dict[str, Any]:
    """追加一条记录，返回写入的条目。"""
    entry: dict[str, Any] = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "site": site,
        "url": url,
        "status": status,
        "report_path": report_path,
        "note": note,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def read_all(path: Path) -> list[dict[str, Any]]:
    """读取全部记录（旧 → 新）。文件不存在返回空列表。"""
    if not path.exists():
        return []
    entries: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # 坏行跳过：台账损坏不应让 status 命令挂掉
    return entries


def summarize(entries: list[dict[str, Any]]) -> dict[str, int]:
    """按状态计数。"""
    out: dict[str, int] = {}
    for entry in entries:
        status = str(entry.get("status", "unknown"))
        out[status] = out.get(status, 0) + 1
    return out


def duplicate_urls(entries: list[dict[str, Any]]) -> set[str]:
    """出现多次的 URL——重复投递检测用。"""
    seen: dict[str, int] = {}
    for entry in entries:
        url = str(entry.get("url", ""))
        seen[url] = seen.get(url, 0) + 1
    return {url for url, count in seen.items() if count > 1}
