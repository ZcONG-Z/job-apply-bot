# 贡献指南

感谢你愿意帮忙。这个项目最稀缺的不是代码，是**真实站点的字段情报**和**排版奇怪的简历样本**。

## 目录

- [先说最重要的一条](#先说最重要的一条)
- [最有价值的四类贡献](#最有价值的四类贡献)
- [开发环境](#开发环境)
- [写一个站点适配器](#写一个站点适配器)
- [代码规范](#代码规范)
- [提交与 PR](#提交与-pr)

---

## 先说最重要的一条

**任何 PR 里都不允许出现真实的个人数据。**

包括但不限于：真实姓名、身份证号、手机号、家庭住址、真实公司名与学校名、真实简历文件、含真实内容的表单截图、带 token 的登录态文件。

提交前自查：

```bash
git diff --cached | grep -iE "身份证|[0-9]{17}[0-9Xx]|1[3-9][0-9]{9}|@(qq|163|gmail|outlook)\."
```

CI 还有一道自动检查（`scripts/guard_personal_data.py`），但它只能拦住明显形态，拦不住"张三"这种。**这一关靠你自己。**

需要脱敏时：姓名换 `张三`，手机换 `13800138000`，身份证留前后几位其余打码，公司换 `某某科技有限公司`，学校换 `某某大学`。

## 最有价值的四类贡献

### 1. 字段清单（成本最低，价值最高）

投过某家公司的网申，把你遇到的字段记下来开个 Issue。尤其需要那些想不到的：

> "是否独生子女"、"紧急联系人及关系"、"身高体重"、"是否接受加班"、"父母工作单位及职务"、"高考分数"、"是否第一志愿"、"家庭成员是否有亲属在本单位"

这些字段决定了 `profile.json` 的覆盖面。漏一个，整套流程就在那一步断掉。

### 2. 站点适配器

按 [docs/adapter-spec.md](docs/adapter-spec.md) 写一份 YAML。不需要写 Python。

### 3. 脱敏简历样本

解析器的鲁棒性只能靠样本量喂出来。特别需要：双栏排版、带表格、带图标、扫描版（OCR 场景）、教育经历与实习经历混排、时间格式不统一的。

放到 `tests/fixtures/sample-*.pdf`，**必须脱敏**。

### 4. 核心代码

认领 [docs/roadmap.md](docs/roadmap.md) 里未开始的任务，先在 Issue 里说一声避免撞车。

---

## 开发环境

```bash
git clone https://github.com/ZcONG-Z/job-apply-bot.git
cd job-apply-bot

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
playwright install chromium

pre-commit install                 # 推荐，会自动跑 ruff
pytest                             # 应该全绿
```

需要 Python 3.11+。Windows / macOS / Linux 都支持。

## 写一个站点适配器

流程：

1. **摸清页面**。用 `playwright codegen <url>` 手动填一遍，录出来的脚本就是可用选择器的草稿
2. **写 YAML**。放到 `src/job_apply_bot/adapters/sites/<site>.yaml`
3. **存快照**。把页面 HTML 保存到 `tests/fixtures/<site>-<step>.html`，**删掉所有真实填写值、隐藏 token、去掉 script 里的用户数据**
4. **写测试**。用快照跑定位逻辑，不联网

```python
def test_moka_basic_info_locates_all_fields(html_snapshot):
    adapter = load_adapter("moka")
    page = render_snapshot(html_snapshot("moka-basic-info"))
    missing = adapter.check_locators(page, step="基本信息")
    assert missing == [], f"未定位到: {missing}"
```

适配器的验收标准就一条：**在一个真实页面上，能定位到所有声明的字段**。填得对不对由回读校验管，那是引擎的事。

### 定位策略（必须遵守优先级）

1. 可见标签文本 `label: ["姓名", "真实姓名"]`
2. `aria-label` / `placeholder`
3. `name` 属性
4. CSS 路径（最后兜底，必须在注释里说明为什么前三者都不可用）

原因：DOM 结构会改版，但"姓名"这两个字不会。用标签文本定位的适配器能在站点小改版后自动存活。

## 代码规范

- 格式化与 lint 交给 `ruff`，别手工调格式。`pre-commit install` 之后自动跑
- 类型标注尽量写，`mypy` 不强制但新代码别留明显窟窿
- **新增逻辑必须有测试**。解析、归一化、定位这三块尤其
- 注释写"为什么"，不写"是什么"。`# 遍历列表` 这种删掉
- 面向用户的文案用中文，代码标识符用英文

### 一个硬性约束

不要在 `engine/` 里加任何形式的**反检测**逻辑——改 `navigator.webdriver`、伪造指纹、随机鼠标轨迹、模拟人类打字节奏。这不是偏好问题，是项目边界，相关 PR 会被直接关闭。原因见 [DISCLAIMER.md](DISCLAIMER.md)。

## 提交与 PR

提交信息用 [Conventional Commits](https://www.conventionalcommits.org/)：

```
feat(adapter): 新增北森校招网申适配器
fix(engine): 修复日期面板默认落点导致月份偏移
docs: 补充 gpa 字段的三种格式说明
refactor(resume): 把日期归一化拆成独立模块
test: 补充双栏简历的解析用例
```

PR 前自查：

- [ ] `pytest` 全绿
- [ ] `ruff check .` 无告警
- [ ] 没有真实个人数据（再自查一遍）
- [ ] 新增行为有测试
- [ ] 涉及适配器的，附了脱敏 HTML 快照

PR 描述里说清楚**为什么**改，而不只是改了什么。如果是为了适配某个站点的特殊控件，贴一段脱敏后的 DOM 结构，review 会快很多。

只有一个维护者，响应可能不及时，但每个 PR 都会看。
