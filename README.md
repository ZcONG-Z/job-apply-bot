<div align="center">

# job-apply-bot

**把网申表单里那些重复录入的活，交给脚本。**

[![Status](https://img.shields.io/badge/status-early%20design-orange)](docs/roadmap.md)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-3776AB)](pyproject.toml)
[![PRs](https://img.shields.io/badge/PRs-welcome-brightgreen)](CONTRIBUTING.md)

[设计文档](docs/design.md) · [适配器规范](docs/adapter-spec.md) · [路线图](docs/roadmap.md) · [English](README.en.md)

</div>

---

## 这是什么

一份结构化简历（`profile.json`）驱动多个网申系统的表单自动填写。

你把简历丢进来，脚本解析成结构化数据、让你确认一遍，然后在真实浏览器里把姓名、联系方式、教育经历、实习经历、附件这些东西填进去，**最后停在提交按钮前等你点**。

```
简历 PDF/DOCX  →  结构化解析  →  你确认  →  profile.json
                                              ↓
                                    站点适配器（YAML）
                                              ↓
                                     Playwright 填表
                                              ↓
                              逐字段回读核对 + 截图存档
                                              ↓
                                    ⏸  停在提交前
```

## 它做什么 / 不做什么

这个界线写在最前面，因为越界之后工具的性质就变了。

**✅ 做**

- 把同一套信息从简历里提取一次，复用到所有已适配的网申系统
- 处理国内网申系统里那些反人类的表单控件：自定义下拉、级联选择、中文日期面板、隐藏的附件上传框、动态增删的经历块
- 填完逐字段读回比对，输出一份可核查的报告
- 记录投递台账，避免重复投同一家公司同一个岗位

**❌ 不做**

- **不绕过验证码**。遇到滑块/图形验证码就停下来，交给人过
- **不代你点提交**。永远停在提交页
- **不做指纹伪装、不加随机鼠标轨迹**。不做任何对抗平台风控的改造
- **不做批量刷投**。单账号串行、限速执行
- **不替你编主观题答案**。开放题可以给草稿，但必须你自己改

如果你在找一个能一键海投几百家公司的工具，这个项目不是。

## 为什么值得做

网申的痛点不是"投得慢"，是这三件事：

1. **同一套信息录十遍**。姓什么、几号生的、哪个学校、绩点多少、哪年哪月入学——一天投十家就录十遍。
2. **每家的字段颗粒度都不一样**。有的要 `YYYY-MM`，有的要 `YYYY-MM-DD`，"至今"有的是复选框有的是下拉，绩点有的百分制有的四分制有的只让填排名。
3. **填错代价高且常常不可逆**。毕业时间错一个月、绩点把 3.6/4 填成 3.6/5，提交后简历就锁了，得去求 HR 改。

所以这个项目的价值排序是 **不出错 > 不漏填 > 填得快**。所有设计取舍都服从这个排序——宁可慢半拍让人确认，也不要一次误提交。

## 当前状态

> **⚠️ 早期阶段：仓库当前是骨架与规范，尚无可运行代码。**
>
> 已完成：目录结构、数据模型设计、适配器规范、数据安全策略、贡献流程。
> 进行中：Phase 0（简历解析与 `profile.json` 生成）。
> 具体进度见 [docs/roadmap.md](docs/roadmap.md)。

这个阶段欢迎的是**设计讨论**和**字段清单补充**——比如你遇到的某个系统问了哪些奇葩字段。这些信息比代码更稀缺。

## 快速开始（Phase 0 完成后生效）

```bash
git clone https://github.com/YOUR_NAME/job-apply-bot.git
cd job-apply-bot

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
playwright install chromium

# 1. 生成结构化简历
cp profile.example.json profile.json
jobapply profile build inbox/我的简历.pdf

# 2. 确认字段（逐项 diff，可改可跳）
jobapply profile review

# 3. 填表（浏览器会打开，填完停在提交前）
jobapply apply https://app.mokahr.com/campus_apply/xxx

# 4. 看投递台账
jobapply status
```

## 支持的站点

适配器是声明式 YAML，加一个站点不需要改 Python 代码。

| 系统 | 覆盖范围 | 状态 |
|---|---|---|
| **Moka** | `*.mokahr.com` 及其白标站点 | 🚧 Phase 1 |
| **北森 Beisen** | `*.zhiye.com` / `*.italent.cn` / `hotjob.cn` | 📋 计划中 |
| **牛客 NowCoder** | `nowcoder.com` 校招网申 | 📋 计划中 |
| 其他 | — | 欢迎提交适配器 |

"📋 计划中"表示字段清单已调研、适配器未写。想加速其中某个，见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 数据安全

**这个项目会接触你的身份证号和家庭住址。请认真读这一节。**

- `profile.json`、`.auth/`（登录态）、`resumes/`、`inbox/`、`runs/` 全部在 `.gitignore` 里，不会被提交
- `runs/` 里的截图会包含真实表单内容，同样不入库
- 日志输出时身份证、手机号统一打码，只保留前后各若干位
- CI 里有一道检查：如果发现有个人数据文件被 add 进暂存区，直接失败

但工具能做的有限，剩下靠你：

```bash
# 提交前自查，比什么都可靠
git status
git diff --cached | grep -iE "身份证|[0-9]{17}[0-9Xx]|1[3-9][0-9]{9}"
```

如果你不小心把简历推上去了，记住：**git 历史里的东西删不干净**。GitHub 的提交会被缓存、被 fork、被爬。正确处理方式是先让 GitHub Support 清除缓存，同时把仓库转私有——详见 [SECURITY.md](SECURITY.md)。

## 开发适配器

社区贡献的主要形态是适配器，不是核心代码。写一个适配器 = 写一份 YAML + 一份脱敏 HTML 快照 + 一个测试。

```yaml
site: moka
match:
  url_patterns: ["*.mokahr.com/campus_apply/*"]
steps:
  - name: 基本信息
    fields:
      - key: basic.name_cn
        label: ["姓名", "真实姓名"]
        type: text
        required: true
      - key: basic.gender
        label: ["性别"]
        type: custom_select
        options: { male: ["男"], female: ["女"] }
```

完整字段类型、定位策略、测试写法见 [docs/adapter-spec.md](docs/adapter-spec.md)。

## 贡献

欢迎 Issue 和 PR。特别需要这几类帮助：

- **字段清单**：你投过的系统问了哪些字段？尤其是那些想不到的（"是否独生子女"、"紧急联系人"、"身高体重"）
- **适配器**：按规范写一个站点，附脱敏 HTML 快照
- **简历样本**：排版奇怪的、双栏的、带表格的——解析器的鲁棒性靠样本量喂出来。**请务必先脱敏**

流程见 [CONTRIBUTING.md](CONTRIBUTING.md)，行为准则见 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)。

## 免责声明

本项目仅用于**减少自己信息的重复录入工作量**。使用者需自行确保：

- 遵守目标网站的服务条款与 robots 协议
- 不将本工具用于批量投递、刷量或任何破坏招聘公平性的行为
- 对最终提交的简历内容负责

作者不对因使用本工具导致的账号封禁、投递异常或信息泄露承担责任。完整条款见 [DISCLAIMER.md](DISCLAIMER.md)。

## License

[MIT](LICENSE) © 2026 Zhou Cong
