# Changelog

本项目的所有重要变更都记录在这里。

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### Fixed

- **绩点解析把日期当成绩点**：`2021/9 - 2025/6` 会被识别成 `1.0/9.0`，导致完全没写绩点的简历
  凭空出现一个绩点。现在要求分母是常见满分制（4 / 4.3 / 4.5 / 5 / 100）且分子不超过分母，
  否则不认。这个 bug 是演示时用一份"排版随意"的简历发现的，单元测试没覆盖到
- **教育经历的多项校验只报第一个错**：`model_validator` 遇到第一个问题就抛异常，
  后面的检查跑不到。改为收集后一次报出，避免用户改一轮只发现一个错

### Added

- `docs/implementation-notes.md`：Phase 0 的实现细节、设计取舍与实测修复记录

## [0.2.0] - 2026-10-21

**第一个可运行版本：简历 → `profile.json`。填表链路仍未实现。**

### Added

- `resume/extract.py`：PDF（PyMuPDF）与 DOCX（python-docx）文本抽取，保留段落与表格顺序；
  旧版 `.doc` 给出可操作的报错而非静默失败
- `resume/normalize.py`：月份、时间段、手机号、邮箱、学历、性别、绩点的归一化
- `resume/parse.py`：按小节切块的规则解析，含"无标签时按词序推断专业/职位"的版面启发式；
  每一处不确定都写入 warnings
- `resume/schema.py`：pydantic 数据模型与校验（身份证、手机号、月份格式、起止先后、绩点上限）
- `profile build` / `profile validate` / `profile review` 三个命令实际可用
- `scripts/make_sample_resume.py`：生成虚构样本简历（DOCX + PDF）
- 108 个新测试：`test_normalize.py`、`test_schema.py`、`test_parse.py`

### Fixed

- 全角归一化误把中文逗号转成半角：不再使用 `NFKC`，改为精确字符映射
- 身份证末位小写 `x` 未转大写：脱敏字符集误含 `x/X`，导致校验被跳过
- 公司名被截断（如"某某科技"）：正则懒惰量词 + 不当后缀导致，改为贪婪匹配
- `【教育背景】` 等带装饰字符的小节标题无法识别

### Changed

- 枚举类改用 `StrEnum`（需要 Python 3.11+）
- README 状态说明更新：明确区分"已实现"与"仅有设计"

## [0.1.0] - 2026-10-21

项目骨架与规范阶段。**此版本无可运行代码。**

### Added

- 项目目录结构、打包配置（`pyproject.toml`，`jobapply` 命令行入口占位）
- `profile.example.json`：结构化简历示例，覆盖基本信息、联系方式、求职意向、教育经历、实习经历、项目、技能、家庭信息
- `docs/design.md`：系统设计文档，含五层架构、7 个动作原语及其已知陷阱、5 个 Phase 的落地路径与验收标准
- `docs/adapter-spec.md`：站点适配器 YAML 规范，含字段类型、定位策略优先级、测试写法
- `docs/roadmap.md`：路线图与任务认领清单
- 数据安全策略：`.gitignore` 覆盖 `profile.json`、`.auth/`、`resumes/`、`runs/` 等全部敏感路径
- `scripts/guard_personal_data.py`：CI 前置检查，阻止个人数据文件进入版本库
- 社区规范：`CONTRIBUTING.md`、`CODE_OF_CONDUCT.md`、`SECURITY.md`、`DISCLAIMER.md`
- GitHub 配置：CI 工作流、Issue 模板（缺陷 / 适配器需求 / 字段情报）、PR 模板

### Notes

- 明确三条项目边界：不绕过验证码、不代提交、不做反检测对抗
- 许可证选定 MIT

[Unreleased]: https://github.com/ZcONG-Z/job-apply-bot/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/ZcONG-Z/job-apply-bot/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/ZcONG-Z/job-apply-bot/releases/tag/v0.1.0
