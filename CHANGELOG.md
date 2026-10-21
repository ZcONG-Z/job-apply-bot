# Changelog

本项目的所有重要变更都记录在这里。

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### Added

- `docs/profile-schema.md`：`profile.json` 全字段说明与格式约定

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

[Unreleased]: https://github.com/YOUR_GITHUB_NAME/job-apply-bot/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/YOUR_GITHUB_NAME/job-apply-bot/releases/tag/v0.1.0
