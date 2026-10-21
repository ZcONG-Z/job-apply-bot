# 适配器规范

一个站点适配器 = 一份 YAML，放在 `src/job_apply_bot/adapters/sites/<site>.yaml`。

适配器只描述**"哪个字段、取什么值、怎么在这一页找到它"**，不写任何逻辑。逻辑在引擎里，站点差异在配置里。

---

## 目录

- [最小示例](#最小示例)
- [顶层结构](#顶层结构)
- [字段声明](#字段声明)
- [字段类型](#字段类型)
- [定位策略](#定位策略)
- [取值绑定语法](#取值绑定语法)
- [数组字段（教育/实习经历）](#数组字段教育实习经历)
- [校验与测试](#校验与测试)
- [已知陷阱](#已知陷阱)

---

## 最小示例

```yaml
site: moka
display_name: Moka 招聘云
match:
  url_patterns:
    - "*.mokahr.com/campus_apply/*"

login:
  mode: manual
  state_file: ".auth/moka.json"

steps:
  - name: 基本信息
    ready: "text=姓名"
    fields:
      - key: basic.name_cn
        label: ["姓名", "真实姓名"]
        type: text
        required: true

      - key: basic.gender
        label: ["性别"]
        type: custom_select
        options:
          male: ["男", "男性"]
          female: ["女", "女性"]
```

## 顶层结构

| 键 | 必填 | 说明 |
|---|---|---|
| `site` | ✅ | 唯一标识，与文件名一致 |
| `display_name` | | 给人看的名字，出现在报告里 |
| `match.url_patterns` | ✅ | 通配符或 glob，决定这个适配器何时生效。`*` 匹配任意字符 |
| `match.detect` | | 额外确认条件（选择器），防止 URL 相同但页面不同 |
| `login.mode` | ✅ | `manual`（人工登录，推荐）或 `storage_state`（复用已保存状态） |
| `login.state_file` | | 登录态持久化路径，必须在 `.auth/` 下 |
| `steps[]` | ✅ | 按顺序执行的步骤 |

### step 结构

| 键 | 说明 |
|---|---|
| `name` | 步骤名，出现在日志和报告里 |
| `ready` | 进入该步的判断条件，等它出现才开始填。**必填**，否则 SPA 重绘会把已填内容清空 |
| `fields[]` | 字段声明列表 |
| `repeat` | 标记为数组字段，见下文 |
| `add_button` | "新增一条"按钮的定位器 |
| `actions[]` | 非填值的动作（上传文件等） |
| `guard` | 设为 `manual` 时，执行到该步停下等人确认 |

---

## 字段声明

```yaml
- key: contact.phone            # profile.json 中的路径
  label: ["手机号码", "手机", "联系电话"]   # 页面上可见的标签文本，多个候选
  type: text
  required: true
  validate: "^1[3-9]\\d{9}$"
  default: null                # profile 中缺失时的兜底值
  skip_if_empty: true          # 值为空时跳过还是报错（默认 true）
```

| 键 | 必填 | 说明 |
|---|---|---|
| `key` | ✅ | `profile.json` 的点路径，如 `educations.0.school` |
| `label` | ✅ | 页面上该字段的可见标签候选列表，按顺序尝试 |
| `type` | ✅ | 见下节 |
| `required` | | 是否必填。会影响未命中时的报告级别 |
| `validate` | | 正则，值不匹配时在确认阶段就报错，不到浏览器阶段才炸 |
| `default` | | profile 缺该字段时的兜底 |
| `skip_if_empty` | | 默认 `true`。设为 `false` 时即使值为空也尝试填（用于"必须留空"的陷阱字段） |

**注意**：`key` 不存在于 profile 时，引擎报 warning 并跳过，不中断整个流程。

---

## 字段类型

### `text`

普通文本框。引擎会优先用原生 `fill()` 触发 `input` 事件。

```yaml
type: text
input_format: null         # 可选，如 "{value} 元"
```

### `textarea`

多行文本。若元素是 `contenteditable`（富文本），引擎自动切换到 `type()` + `blur()` 模式。

### `custom_select`

非原生 `<select>` 的下拉框——国内网申系统里基本都是这种。需要"点开触发器 → 等弹层 → 按文本点选项"。

```yaml
type: custom_select
options:
  male: ["男", "男性"]       # profile 值 → 页面上可能出现的文案（多个候选）
  female: ["女", "女性"]
trigger: null               # 可选，触发器选择器；不填则从 label 自动推导
container: null             # 可选，弹层容器选择器；不填则在全局作用域找
```

`options` 必须把 profile 里的枚举值映射到页面文案。**不要**依赖文案完全一致——写多个候选，按顺序匹配第一个命中的。

### `cascade_select`

省/市/区等多级联动。

```yaml
type: cascade_select
levels: ["省", "市", "区"]
separator: "/"              # profile 中值的分隔符，如 "江苏省/南京市/玄武区"
```

引擎逐级选择，每级之间等待选项列表刷新。

### `typeahead`

输入后弹出联想列表，需要点中某一项（学校名称、公司名称常见）。

```yaml
type: typeahead
wait_options: 800           # 等待联想列表出现的毫秒数
pick: first                 # first | exact | contains
```

`pick: exact` 时按文本完全匹配，找不到就报错而不是随便选一个。**涉及学校、公司这类字段建议用 `exact`**，选错了比不选更糟。

### `date`

```yaml
type: date
input_format: "YYYY-MM-DD"  # 或 YYYY-MM / YYYY/MM/DD / YYYY年MM月
render: auto                # auto | input | panel
present_label: ["至今", "现在"]   # profile 中 end 为 null 时勾选的文案
```

`render: auto` 时引擎先试直接填输入框，失败再降级为操作日期面板。绝大多数情况走第一条路径。

### `radio`

```yaml
type: radio
options:
  male: ["男"]
  female: ["女"]
```

### `checkbox`

用于多选或单个勾选。单选场景（如"接受调剂"）的 `options` 写 `true/false`。

```yaml
type: checkbox
options:
  "true": ["接受", "是"]
  "false": ["不接受", "否"]
```

### `upload`

```yaml
type: upload
source: "$resume_file"       # 特殊变量，见下
optional: true
```

引擎直接对隐藏的 `<input type="file">` 调用 `set_input_files()`，不点可见按钮——可见按钮往往带额外的上传弹窗。

特殊变量：

| 变量 | 含义 |
|---|---|
| `$resume_file` | 本次投递使用的那份简历原件 |
| `$files.transcript` | `files/` 目录下的具名附件 |
| `$profile_file` | 生成的 profile.json 本身（少数系统要求上传） |

---

## 定位策略

引擎按以下顺序尝试，**第一个命中的就使用**：

1. **可见标签文本** — 找到文本匹配的元素，再顺 DOM 关系找它的输入控件
2. `aria-label` / `placeholder` 属性匹配
3. `name` 属性匹配
4. CSS 选择器（`selector:` 显式指定）

```yaml
- key: basic.name_cn
  label: ["姓名"]
  selector: "input[name='username']"   # 兜底，仅当前三者失效
  note: "该站点 name 属性被压缩成乱码，label 结构也无规律，只能硬编码"
```

如果必须写第 4 种，**在 `note` 里说明为什么**。review 会问这个。

### 为什么是文本优先

DOM 结构会随前端框架版本变化，class 名会被构建工具压缩，`name` 属性经常被改成 `field_8f3a`。但**"姓名"这两个字不会变**——除非产品改文案，而改文案的频率远低于改结构。

文本定位让适配器在站点小改版后自动存活，这是把适配器从"消耗品"变成"资产"的关键。

---

## 取值绑定语法

| 写法 | 含义 |
|---|---|
| `basic.name_cn` | 直接取 profile 中的值 |
| `educations.0.school` | 数组索引 |
| `{item}.school` | 在 `repeat` 上下文中取当前元素 |
| `$resume_file` | 特殊变量（见 upload） |
| `derived:full_name_en` | 派生字段，由引擎计算（如姓名转拼音） |

派生字段目前支持：

| 派生 | 说明 |
|---|---|
| `derived:name_pinyin` | 中文名转拼音，姓与名首字母大写 |
| `derived:age` | 由出生日期算周岁 |
| `derived:gpa_100` | 由 `gpa` 与 `gpa_scale` 换算百分制 |
| `derived:work_years` | 由经历起止时间算总年限（不含实习） |

---

## 数组字段（教育/实习经历）

用 `repeat` 声明，引擎自动处理"条数不足时点新增、条数超出时删除多余"。

```yaml
- name: 教育经历
  repeat: educations
  add_button: ["text=新增教育经历", "text=+ 添加"]
  block: "[data-section='education'] .item"   # 单条经历的容器
  fields:
    - key: "{item}.school"
      label: ["学校"]
      type: typeahead
      pick: exact
    - key: "{item}.start"
      label: ["开始时间", "入学时间"]
      type: date
      input_format: "YYYY-MM"
```

**`block` 必须写。** 它把定位限定在单条经历的容器内。不写的话第二个块会和第一个块的字段重复匹配，导致值填串位——这是这类脚本最常见的 bug。

---

## 校验与测试

适配器必须配一个基于 HTML 快照的离线测试。

### 1. 保存快照

```bash
jobapply adapter snapshot <url> --step 基本信息 --out tests/fixtures/moka-basic-info.html
```

**快照必须脱敏**：删掉 `value` 属性、清空 `<script>` 里的用户数据、去掉 token、把文字内容换成占位值。

### 2. 写测试

```python
from job_apply_bot.adapters import load_adapter
from job_apply_bot.testing import render_snapshot


def test_moka_basic_info_all_locators_hit():
    adapter = load_adapter("moka")
    page = render_snapshot("tests/fixtures/moka-basic-info.html")
    missing = adapter.check_locators(page, step="基本信息")
    assert missing == [], f"未定位到: {missing}"
```

### 3. 验收标准

- 所有 `required: true` 的字段都能定位到
- 所有 `custom_select` / `typeahead` 的 `options` 映射在快照里能找到对应文案
- 快照不含任何真实个人数据

---

## 已知陷阱

写适配器时最容易踩的：

| 现象 | 原因 | 处理 |
|---|---|---|
| `fill()` 之后后端收不到值 | React/Vue 受控组件，直接改 value 不触发 `onChange` | 用 Playwright 原生 `fill()`；`contenteditable` 用 `type()` + `blur()` |
| 下拉点不开 / 选不中 | 触发器与弹层不在同一 DOM 层级，或用 Portal 挂到 body | 显式指定 `trigger` 和 `container` |
| 选项在虚拟列表里找不到 | 只渲染可视区域的若干项 | 引擎循环滚动查找；实在找不到就报错，不猜 |
| 填到一半内容被清空 | SPA 路由切换后重绘 | 每个 step 的 `ready` 必须写，且等 `networkidle` |
| 日期选了但差一个月 | 日期面板默认落点或 0-based 月份 | 优先直填输入框；必须点面板时校验回读值 |
| 第二个经历块的字段填到了第一个 | 缺少 `block` 容器限定 | 必须写 `block` |
| 上传没反应 | 真实 `input[file]` 是隐藏的，点可见按钮会弹自建弹窗 | 直接 `set_input_files()` 到隐藏 input |

---

## 提交适配器

1. YAML 放 `src/job_apply_bot/adapters/sites/`
2. 快照放 `tests/fixtures/`（脱敏）
3. 测试放 `tests/test_adapter_<site>.py`
4. 在 `docs/roadmap.md` 的支持列表里把状态改成 ✅
5. 提 PR，标题用 `feat(adapter): 新增 XXX 适配器`

清单见 [CONTRIBUTING.md](../CONTRIBUTING.md)。
