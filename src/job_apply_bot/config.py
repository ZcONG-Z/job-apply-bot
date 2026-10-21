"""路径与运行参数。

所有个人数据都落在工作目录下，且全部被 .gitignore 忽略。

工作目录布局：

    <root>/
    ├── profile.json                      # 唯一事实源
    ├── inbox/                            # 待解析的简历
    ├── resumes/                          # 归档的简历原件
    ├── files/                            # 其他附件（成绩单等）
    ├── .auth/                            # 登录态
    └── runs/<timestamp>_<site>_<slug>/   # 每次运行的截图与报告
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# 单次填写时每个字段之间的随机间隔（毫秒）。
# 既是为了不给目标站点造成压力，也是为了暴露自己脚本里的竞态问题。
FIELD_DELAY_RANGE_MS: tuple[int, int] = (150, 400)

# 单个步骤的超时。
STEP_TIMEOUT_MS: int = 30_000

# 元素出现后的稳定等待，防止 SPA 重绘把已填内容清空。
STABLE_WAIT_MS: int = 300

# 默认视口。部分网申表单在窄视口下会折叠字段。
VIEWPORT: dict[str, int] = {"width": 1440, "height": 900}


@dataclass(frozen=True)
class Workspace:
    """工作目录。布局见模块顶部说明。"""

    root: Path

    @classmethod
    def discover(cls, start: Path | None = None) -> Workspace:
        return cls(root=(start or Path.cwd()).resolve())

    @property
    def profile_file(self) -> Path:
        return self.root / "profile.json"

    @property
    def inbox(self) -> Path:
        return self.root / "inbox"

    @property
    def resumes(self) -> Path:
        return self.root / "resumes"

    @property
    def files(self) -> Path:
        return self.root / "files"

    @property
    def auth(self) -> Path:
        return self.root / ".auth"

    @property
    def runs(self) -> Path:
        return self.root / "runs"

    @property
    def ledger(self) -> Path:
        return self.root / "ledger.db"

    def ensure(self) -> Workspace:
        """创建所需目录（幂等）。"""
        for path in (self.inbox, self.resumes, self.files, self.auth, self.runs):
            path.mkdir(parents=True, exist_ok=True)
        return self
