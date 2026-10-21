# 路线图

状态说明：✅ 完成 · 🚧 进行中 · 📋 计划中 · 💡 想法，未排期

当前：**v0.1.0 — 骨架与规范阶段，无可运行代码。**

---

## Phase 0 · 数据层

目标：丢一份简历进来，得到一份能用的 `profile.json`。

- [x] `profile.json` 字段设计（见 [profile-schema.md](profile-schema.md)）
- [x] 项目骨架、打包配置、`jobapply` 入口
- [ ] 📋 `resume/extract.py` — PDF（PyMuPDF）与 DOCX（python-docx）文本抽取，保留段落顺序
- [ ] 📋 `resume/parse.py` — 规则解析：正则 + 版面启发式，覆盖规整排版的简历
- [ ] 📋 `resume/parse.py` — LLM 兜底：规则失败时调用模型补全（可选依赖，默认关闭）
- [ ] 📋 `resume/normalize.py` — 日期、绩点、学历枚举、手机号、全半角归一化
- [ ] 📋 `resume/review.py` — 终端逐字段 diff 确认，支持修改、跳过、标记待补
- [ ] 📋 `tests/fixtures/` — 3 份脱敏简历样本（单栏 / 双栏 / 带表格）

**验收**：真实简历跑 `jobapply profile build`，非空字段准确率 ≥ 95%；身份证、手机、毕业年月零错误。

> `normalize.py` 是这一阶段的重点。80% 的填错都源于格式没归一，而不是解析没抽到。

## Phase 1 · 打通一个站点

目标：端到端填完一个真实岗位，停在提交前。

- [ ] 📋 `engine/browser.py` — 会话管理、`storage_state` 登录态持久化、headed 模式
- [ ] 📋 `engine/locator.py` — 四级定位策略（文本 → aria → name → css）
- [ ] 📋 `engine/actions.py` — 动作原语：`fill_text` / `fill_rich` / `custom_select` / `cascade_select` / `typeahead` / `pick_date` / `radio` / `checkbox` / `upload` / `repeat_block`
- [ ] 📋 `engine/verify.py` — 回读校验、差异报告
- [ ] 📋 `engine/artifacts.py` — 截图、DOM 快照、运行日志
- [ ] 📋 `adapters/sites/moka.yaml` — Moka 适配器（第一个，结构最规整）
- [ ] 📋 `tests/fixtures/moka-*.html` — 脱敏页面快照
- [ ] 📋 验证码中断处理：检测到验证元素时暂停，终端提示人工完成后回车继续

**验收**：对真实岗位填完全部基本信息与教育经历，核对报告无 ❌，浏览器停在提交页。

## Phase 2 · 抽象成工具

目标：新增站点只写 YAML，不改 Python。

- [ ] 📋 `adapters/base.py` — Adapter 抽象、YAML 加载与校验、locator 检查
- [ ] 📋 `adapters/registry.py` — URL 路由到适配器
- [ ] 📋 把 Phase 1 里所有硬编码外移到 YAML
- [ ] 📋 `adapters/sites/beisen.yaml` — 北森适配器
- [ ] 📋 `adapters/sites/nowcoder.yaml` — 牛客适配器
- [ ] 📋 `jobapply adapter snapshot` / `jobapply adapter check` 调试命令
- [ ] 📋 派生字段：`name_pinyin` / `age` / `gpa_100` / `work_years`

**验收**：加第二个站点时 Python 代码零改动。

> 这是"个人项目"变成"工具"的分界线。这里偷懒，后面全盘皆输。

## Phase 3 · 可用性

- [ ] 📋 `--resume` 断点续填（记录 step cursor）
- [ ] 📋 `ledger/db.py` — SQLite 投递台账：公司、岗位、时间、状态、报告路径
- [ ] 📋 `jobapply status` — 台账总览，支持按公司/时间筛选
- [ ] 📋 重复投递检测：同一公司同一岗位已投过时警告
- [ ] 📋 失败重试：区分"可重试"（超时、网络）与"不可重试"（字段找不到）
- [ ] 📋 字段覆盖率报告：跑完提示"该站还有 6 个字段本系统不认识"

**验收**：连续投 5 家不同公司，每家出报告，台账可查，中途崩溃可恢复。

## Phase 4 · 增强

- [ ] 💡 开放题辅助：从 `answers` 库匹配 + 按 JD 生成初稿（**必须人工改写，不自动提交**）
- [ ] 💡 简历多版本：一份 profile 派生不同侧重（后端版 / 算法版）
- [ ] 💡 投递复盘：按时间统计投递量、回复率
- [ ] 💡 站点改版告警：适配器定位失败率突增时提示维护
- [ ] 💡 Web UI：本地页面替代终端交互，diff 与确认更直观

---

## 想要认领某个任务？

在 Issue 里说一声，避免撞车。用 `good first issue` 标签筛选适合入门的：

| 任务 | 难度 | 说明 |
|---|---|---|
| 补充字段情报 | 低 | 把你遇到的奇葩字段开 Issue 记下来，不需要写代码 |
| 脱敏简历样本 | 低 | 排版越奇怪越好 |
| `normalize.py` 单元测试 | 低 | 已有明确输入输出，照着写用例 |
| 站点适配器 | 中 | 需要会用 devtools 看 DOM |
| 动作原语 | 中高 | 需要处理各种边界，最好有真实站点对照 |
| 回读校验 | 中高 | 归一化比对逻辑容易出细节 bug |

## 不做的事

这几项不会进入路线图，相关 PR 会被关闭。原因见 [DISCLAIMER.md](../DISCLAIMER.md)。

- 绕过验证码 / 集成打码服务
- 反检测：改 `navigator.webdriver`、伪造指纹、模拟人类操作节奏
- 批量海投、并发多账号
- 自动点击提交
- 爬取岗位数据
