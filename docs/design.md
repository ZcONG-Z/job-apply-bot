# 网申简历自动填写系统 · 实施计划

> 形态：本地 Python + Playwright（headed）
> 目标站点：主流国内网申系统（北森 / 牛客 / Moka 及其白标站点）
> 信息源：PDF / Word 自动解析 + 人工确认

---

## 一、先把问题对准

### 真问题不是"填得快"

网申真正消耗人的，是这三件事：

1. **同一套信息重复录入**。姓名、身份证、手机、教育经历、绩点、起止月份，一天投十家就要录十遍。
2. **每个系统的字段名和颗粒度都不一样**。有的要 `YYYY-MM`，有的要 `YYYY-MM-DD`，"至今"有的用复选框有的用下拉。
3. **填错代价高且不可逆**。毕业时间填错一个月、绩点写成 3.5/5 而实际是 3.5/4，提交后要联系 HR 改，很多时候改不了。

所以这个工具的价值排序是：**不出错 > 不漏填 > 填得快**。这个排序直接决定了后面所有设计取舍——宁可慢半拍让人确认，也不要一次误提交。

### 目标 / 非目标

| | 内容 |
|---|---|
| **目标** | 一份 profile.json 驱动任意已适配站点；一次操作完成 80% 以上字段录入；填完给出逐字段核对报告；全程留痕可回溯 |
| **非目标** | 不做全自动批量刷投；不绕过验证码；不模拟人机对抗；不代填任何需要主观判断且无事实依据的内容（如"你最大的缺点"） |

### 验收标准（可量化，避免"感觉能用"）

- 结构化抽取：在 3 份不同排版的真实简历上，字段准确率 ≥ 95%，且**零容忍**字段（身份证、手机、毕业年月）全部正确
- 单站点端到端：必填字段填写成功率 ≥ 90%（不含验证码中断）
- 回读校验覆盖率：100% 必填字段
- 新增一个同厂商站点：只写 YAML，不改 Python 代码，半小时内跑通

---

## 二、三个决定成败的设计决策

### 决策 1：适配层必须是声明式配置，不是一堆脚本

最直觉的写法是"一个站点一个 Python 脚本"。第一家很快，第三家就开始复制粘贴，第五家时改一个字段要改五个文件，且每次 DOM 变动都要重写逻辑。

正确做法：**站点适配 = 一份 YAML**，描述"哪个字段，从 profile 的哪个路径取值，怎么在这一页上定位并填入"。Python 只提供动作原语。这样新增站点是纯数据工作，也便于出错时快速定位。

### 决策 2：profile.json 是唯一事实源

简历解析结果、人工修正、站点特殊格式，最终都收敛到一份 `profile.json`。站点适配器只读不算、不改数据。任何"这家公司要英文名"这类差异，用 `derived` 派生字段解决，而不是在适配器里写 if。

### 决策 3：填到提交按钮前停下

不是技术做不到，是**不该做**。原因有三：
- 验证码/滑块必须人工过，硬闯就是违反平台协议
- 提交前是唯一能低成本纠错的时刻
- 部分系统提交后简历进入锁定状态

所以流程设计成：脚本填 → 自动核对报告 → 浏览器停在提交页 → 人扫一眼点提交。这个"半自动"不是妥协，是正确形态。

---

## 三、目录结构

```
applybot/
├── profile.json                  # 唯一事实源（gitignore）
├── schema/profile.schema.json    # pydantic 模型导出的校验规则
├── inbox/                        # 简历丢这里，脚本自动消费
│   └── 我的简历.pdf
├── resumes/                      # 归档的简历原件（上传附件用）
├── src/applybot/
│   ├── cli.py                    # typer 命令入口
│   ├── config.py                 # 路径、模型、限速参数
│   ├── resume/
│   │   ├── extract.py            # PDF/DOCX → 带版面信息的纯文本
│   │   ├── parse.py              # 文本 → profile 草稿（规则 + LLM 兜底）
│   │   ├── normalize.py          # 日期/电话/绩点/学历枚举归一化
│   │   └── review.py             # 终端逐字段确认 + diff 展示
│   ├── engine/
│   │   ├── browser.py            # 会话、storage_state 登录态持久化
│   │   ├── locator.py            # 多策略定位：label → aria → name → css
│   │   ├── actions.py            # 动作原语（见第五节）
│   │   ├── verify.py             # 回读校验 + 差异报告
│   │   └── artifacts.py          # 截图、DOM 快照、运行日志
│   ├── adapters/
│   │   ├── base.py               # Adapter 抽象 + YAML 解析
│   │   ├── registry.py           # URL → adapter 路由
│   │   └── sites/
│   │       ├── _common.yaml      # 共用字段定义（教育/实习块）
│   │       ├── moka.yaml
│   │       ├── beisen.yaml
│   │       └── nowcoder.yaml
│   └── ledger/
│       └── db.py                 # SQLite 投递台账（公司/岗位/时间/状态/截图路径）
├── runs/2026-10-21_1430_moka_xxx/   # 每次运行的产出
│   ├── step1.png  step2.png
│   ├── verify_report.md
│   └── run.log
└── tests/
    ├── fixtures/                 # 脱敏简历样本 + 保存的 HTML 快照
    └── test_parse.py  test_normalize.py
```

设计要点：`runs/` 每次一目录。出问题时能回看"那一刻页面长什么样、填了什么、读回来是什么"——这比看日志快十倍。

---

## 四、数据模型：profile.json

这是整个项目最容易被低估的部分。字段设计得不够，后面每个站点都要打补丁。核心原则：**存事实，不存格式**。日期一律 ISO 格式，具体展示格式由适配器转换。

```json
{
  "meta": { "version": 1, "updated_at": "2026-10-21", "source_file": "我的简历.pdf" },

  "basic": {
    "name_cn": "张三",
    "name_en": "Zhang San",
    "gender": "male",
    "birth_date": "2003-04-15",
    "id_number": "3101**********1234",
    "political_status": "共青团员",
    "hometown": "江苏省南京市",
    "household": "江苏省南京市",
    "marital_status": "single",
    "health": "良好",
    "height_cm": 175
  },

  "contact": {
    "phone": "13800138000",
    "email": "zhangsan@example.com",
    "wechat": "zs_wechat",
    "current_city": "上海市",
    "address": "上海市杨浦区XXX路XX号",
    "postal_code": "200093"
  },

  "job_intent": {
    "target_role": "后端开发工程师",
    "target_city": ["上海", "杭州", "深圳"],
    "job_type": "campus",            // campus | intern | social
    "available_date": "2027-07-01",
    "expected_salary": null,          // 校招常留空
    "accept_relocation": true,
    "accept_shift": false
  },

  "educations": [
    {
      "degree": "bachelor",           // 枚举：highschool/associate/bachelor/master/phd
      "school": "某某大学",
      "school_en": "XX University",
      "major": "计算机科学与技术",
      "start": "2023-09",
      "end": "2027-06",
      "gpa": 3.62,
      "gpa_scale": 4.0,
      "gpa_percent": "前 15%",
      "ranking": "12/180",
      "city": "上海",
      "is_full_time": true,
      "courses": ["数据结构", "操作系统", "计算机网络"]
    }
  ],

  "experiences": [
    {
      "kind": "internship",           // internship | fulltime | parttime
      "company": "某某科技有限公司",
      "department": "基础架构部",
      "title": "后端开发实习生",
      "start": "2026-07",
      "end": "2026-09",               // null 表示至今
      "city": "杭州",
      "description": "负责订单服务重构，QPS 从 800 提升至 3200……",
      "achievements": ["……"],
      "leave_reason": null
    }
  ],

  "projects": [ { "name": "", "role": "", "start": "", "end": "", "tech": [], "description": "", "link": "" } ],

  "skills": {
    "languages": [{ "name": "英语", "level": "CET-6", "score": 546 }],
    "programming": ["Python", "Go", "Java"],
    "certificates": [{ "name": "软件设计师", "date": "2026-05" }],
    "awards": [{ "name": "国家励志奖学金", "date": "2025-10", "level": "国家级" }]
  },

  "family": [ { "relation": "father", "name": "", "phone": "", "employer": "", "title": "" } ],

  "custom": {},                       // 站点特有字段的兜底命名空间

  "answers": {                        // 开放题历史回答库，可复用
    "self_intro": "……",
    "why_company": null
  }
}
```

**几个必须想清楚的细节：**

- `gpa` + `gpa_scale` + `gpa_percent` 三个都存。有的系统只让填百分制，有的让填 4 分制，有的让填排名。缺一个就卡住。
- 日期统一 `YYYY-MM`。网申里"日"极少需要精确到天（除出生日期），用 `YYYY-MM` 减少错误面。
- `id_number` 存脱敏值还是原值？→ 存原值但文件加密/权限保护，日志输出时统一打码。填表需要真值。
- `custom` 兜底很重要。总有你没预见的字段（"是否独生子女"、"紧急联系人"），有个命名空间比改 schema 便宜。

---

## 五、适配层规范：一份 YAML 长什么样

这是整个项目最需要设计好的接口。

```yaml
site: moka
match:
  url_patterns:
    - "*.mokahr.com/campus_apply/*"
    - "app.mokahr.com/su/*"
  detect: "text=个人基本信息"        # 页面就绪判断

login:
  mode: manual                       # manual | storage_state
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
        type: custom_select            # 非原生 select，需要点开再选
        options: { male: ["男", "男性"], female: ["女", "女性"] }

      - key: basic.birth_date
        label: ["出生日期", "出生年月"]
        type: date
        input_format: "YYYY-MM-DD"     # 引擎负责把 ISO 转成这个格式

      - key: contact.phone
        label: ["手机号码", "手机", "联系电话"]
        type: text
        validate: "^1[3-9]\\d{9}$"

      - key: educations.0.school
        label: ["毕业院校", "学校名称"]
        type: typeahead                # 输入后需等联想列表并点第一项
        wait_options: 800

  - name: 教育经历
    repeat: educations                 # 数组字段，自动处理"新增一条"
    add_button: ["text=新增教育经历", "text=+ 添加"]
    fields:
      - key: "{item}.school"
        label: ["学校"]
        type: typeahead
      - key: "{item}.start"
        label: ["开始时间", "入学时间"]
        type: date
        input_format: "YYYY-MM"

  - name: 附件
    actions:
      - type: upload
        label: ["上传简历", "附件"]
        source: "$resume_file"         # 指向 resumes/ 下的原件
      - type: upload
        label: ["成绩单"]
        source: "$files.transcript"
        optional: true

  - name: 提交
    guard: manual                      # 关键：停在这里，等人确认
    submit_button: ["text=提交", "text=确认投递"]
```

### 定位策略优先级（重要）

1. **可见标签文本**（`label: ["姓名"]`）——最稳。DOM 结构会变，但"姓名"这两个字不会变
2. **`aria-label` / `placeholder`**——次稳
3. **`name` 属性**——React 项目里常被压缩成乱码，但仍是有效补充
4. **CSS 路径 / XPath**——最后兜底，且必须写在注释里说明"仅当以上全部失效时使用"

引擎按顺序尝试，第一个命中的就用。这一步能让适配器在系统小改版后**自动存活**，而不是直接崩。

**实操技巧**：写选择器时不要靠肉眼扒 DOM。用 `playwright codegen <url>` 手动填一遍，录制出来的脚本直接就是可用选择器的草稿，再把它转成 YAML 配置。这一步能省掉大量试错。

---

## 六、执行引擎：必须处理的七个坑

这些是实际做过才知道的，也是"看起来很简单"的脚本最容易死的地方。

| 原语 | 坑 | 处理方式 |
|---|---|---|
| `fill_text` | React/Vue 受控组件直接改 `value` 不触发 `onChange`，后端收不到值 | 用 Playwright 的 `fill()`（内部触发原生事件）；对 `contenteditable` 用 `type()` 并补 `blur()` |
| `custom_select` | 下拉不是 `<select>`，是 `div` 弹层，选项可能虚拟滚动 | 点击触发器 → 等弹层可见 → 在弹层作用域内按文本匹配 → 虚拟滚动时循环滚动找目标 → 点中后等弹层消失 |
| `cascade_select` | 省/市/区三级联动，选完上级才能加载下级 | 逐级等待选项列表更新，每级之间 `wait_for` 选项数量变化 |
| `pick_date` | 有"至今"复选框、有 `YYYY-MM` 与 `YYYY-MM-DD` 两种、有中文日期面板 | 优先直接填输入框（多数组件支持）；实在只能点面板时，按年月翻页定位；`end: null` 时勾选"至今" |
| `upload` | 上传按钮是自定义组件，真实 `<input type=file>` 被隐藏 | 直接对隐藏 input 用 `set_input_files()`，不点可见按钮；多文件传数组 |
| `repeat_block` | 教育/实习"新增一条"后，新增块的字段选择器与第一块重复 | 按容器 `nth()` 定位整个块，块内相对定位字段，避免全局匹配串位 |
| `wait_ready` | SPA 路由切换后元素短暂存在又重绘，导致填到一半被清空 | 每步开始前等 `networkidle` + 目标标签可见 + 稳定 300ms，再开始填 |

此外还有两个通用机制：

- **断点续填**：每次填完一个 step 就在 `runs/` 记 cursor。中途崩了能 `--resume` 从该步重来，不用从头再填一遍。
- **限速**：单次填写按字段数注入 150–400ms 随机间隔，同一账号串行执行。这既是绕过风控的必要动作，也是压测出自己脚本问题的手段。

---

## 七、安全网：回读校验

填完不验证，等于没做。校验逻辑：

1. 对每个已填字段，用同一套定位策略**读回当前值**
2. 用 `normalize()` 把读回值和期望值归一到同一形态（去空格、日期统一、全半角统一、下拉值反查映射）
3. 三者对比：`expected` / `actual` / `是否必填`
4. 输出报告：

```
## 填写核对报告 · Moka · 某某科技 后端开发
页面: https://app.mokahr.com/campus_apply/xxx
时间: 2026-10-21 14:32

✅ 已正确填写 23 项
⚠️  值不一致 2 项
   - 毕业时间: 期望 2027-06 / 实际 2027-09（日期面板默认落点错误）
   - 绩点: 期望 3.62 / 实际 3.6（输入被截断到一位小数）
❌ 必填但未找到 1 项
   - 紧急联系人电话（页面上未见该字段，可能在其他 tab）
⏸  提交按钮未点击 —— 请人工确认后提交
```

截图同时存档 `step*.png`。这份报告 + 截图，就是这个工具"可被信任"的全部依据。

---

## 八、分阶段落地

不追求一次做完。每阶段结束都有一个能真实用起来的东西。

### Phase 0 · 骨架与数据层
**交付**：项目结构、profile schema、简历解析 + 人工确认流程、`profile.json` 生成
**验收**：丢一份 PDF 进 `inbox/`，终端跑 `applybot profile build`，能得到一份字段基本正确的 JSON，人工修正后落盘
**这一阶段的重点**：把 `normalize.py` 写扎实。日期、绩点、学历枚举、手机号去空格——80% 的填错都源于这里

### Phase 1 · 打通一个站点（端到端）
**交付**：browser 会话 + 登录态持久化、7 个动作原语、第一份站点 YAML（建议选 Moka，其结构最规整）、回读校验
**验收**：对一个真实岗位，脚本填完全部基本信息和教育经历，报告无 ❌，浏览器停在提交页
**这一阶段的重点**：动作原语的健壮性。每个原语都要写重试与超时，宁慢勿错

### Phase 2 · 抽象与第二个系统
**交付**：`base.py` + `registry.py` 成型、把 Phase 1 里硬编码的东西全部外移到 YAML、新增北森或牛客适配
**验收**：新增第二个站点时，Python 代码零改动，只加一个 YAML 文件
**这一阶段的重点**：这是"项目"变成"工具"的分界线。如果这里偷懒，后面全盘皆输

### Phase 3 · 可用性与台账
**交付**：`--resume` 断点续填、投递台账 SQLite（公司/岗位/时间/状态/报告路径）、失败重试、`applybot status` 看总览、重复投递检测
**验收**：连续投 5 家不同公司，每家都能出报告，台账可查，中途崩溃可恢复

### Phase 4 · 增强（可选，按需做）
- 开放题辅助：从 `answers` 库匹配 + LLM 按岗位 JD 生成初稿，**但必须人工改写**，不自动提交
- 简历版本管理：一份 profile 派生多个侧重版本（后端版/算法版）
- 字段覆盖率统计：跑完提示"该站还有 6 个字段本系统不认识，建议补充 profile"

---

## 九、风险清单

| 风险 | 影响 | 对策 |
|---|---|---|
| 站点 DOM 改版 | 适配器失效，字段错位填入（最危险） | 多策略定位 + 回读校验必开；错位会在报告里暴露；`runs/` 留 DOM 快照便于快速修 |
| 自定义组件行为差异 | 下拉选不中、日期填不进 | 原语层统一兜底：先试输入框直填，失败降级为模拟点击 |
| 验证码/滑块 | 流程中断 | 设计上就允许中断：headed 模式 + 终端提示"请手动完成验证后按回车"，然后继续 |
| 风控限频/封号 | 账号不可用 | 严格限速、单账号串行、不做批量刷投；异常时立即停手不重试 |
| 敏感信息泄露 | 身份证、住址外泄 | `profile.json` 与 `.auth/` 加入 `.gitignore`；日志统一脱敏；台账只存路径不存内容 |
| 简历解析误判 | 填错关键字段 | 零容忍字段强制人工确认（身份证、手机、毕业年月、绩点）；review 环节默认逐项过 |
| 平台条款风险 | 账号或投递被判定异常 | 明确只做"代录入"，最终提交由人完成；不做规避检测的对抗性改造 |

---

## 十、边界写明白

这个工具做的是**把自己的信息更准更快地录进去**，不是"帮人抢投"。所以三条硬边界：

1. **不破验证码**。遇到就交给人。
2. **不代提交**。脚本永远停在提交按钮前。
3. **不降速对抗**。不加随机鼠标轨迹、不做指纹伪造。看着像人不是目标，别把账号搞进风控名单才是。

一旦越过这三条，工具的性质就变了，收益远小于风险。

---

## 十一、技术栈

| 用途 | 选择 | 理由 |
|---|---|---|
| 浏览器自动化 | Playwright (Python) | 自带等待机制、支持 `storage_state` 持久化登录态、headed 模式便于人工接管、`codegen` 辅助写选择器 |
| 数据校验 | pydantic v2 | schema 即文档，解析结果不合规直接报错而非静默填错 |
| 简历解析 | PyMuPDF（PDF）+ python-docx | 比通用抽取库更能保住版面顺序，教育经历这类结构化信息依赖顺序 |
| 文本→结构 | 规则优先 + LLM 兜底 | 规则处理 90% 的规整简历，LLM 只处理规则失败的段落，成本可控且结果可解释 |
| CLI | typer + rich | 终端里的 diff 与确认交互体验直接影响你愿不愿意用它 |
| 台账 | SQLite | 单文件、零运维、能直接 SQL 查"哪些投过" |

---

## 十二、开始前需要你提供

1. **一份（或几份）真实简历**——最好有 PDF 和 Word 两种，我能据此把解析规则和 `normalize` 调到能用的程度
2. **一个目标岗位的网申链接**——用来确定第一个适配的站点和实际字段清单
3. **投递范围说明**——校招/实习/社招，主要投哪几类公司，这决定 profile 里哪些字段必须做全

拿到这三样，Phase 0 可以当场开始写。
