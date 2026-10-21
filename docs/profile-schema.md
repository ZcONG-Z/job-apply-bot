# profile.json 字段说明

`profile.json` 是整个项目的唯一事实源。站点适配器只读它、不改它；站点之间的格式差异由适配器在取值时转换。

配套文件：[`profile.example.json`](../profile.example.json)（虚构数据，可直接复制改用）

---

## 设计原则

1. **存事实，不存格式。** 日期一律 ISO，绩点存原始分制，展示格式由 `type: date` 的 `input_format` 决定。
2. **枚举用英文，展示用中文。** `gender: "male"` 而不是 `"男"`，页面文案的映射放在适配器的 `options` 里。
3. **宁可多存。** 绩点同时存 `gpa` / `gpa_scale` / `gpa_percent` / `ranking` 四个，因为不同系统要的形态不同，缺一个就卡住。
4. **留兜底命名空间。** `custom` 接住所有没预见的字段，比每次改 schema 便宜。

---

## 顶层字段

| 键 | 类型 | 说明 |
|---|---|---|
| `meta` | object | 版本、更新时间、来源文件 |
| `basic` | object | 基本信息 |
| `contact` | object | 联系方式 |
| `job_intent` | object | 求职意向 |
| `educations` | array | 教育经历，**按时间倒序** |
| `experiences` | array | 工作/实习经历，**按时间倒序** |
| `projects` | array | 项目经历 |
| `skills` | object | 语言、编程、证书、获奖 |
| `family` | array | 家庭成员 |
| `custom` | object | 站点特有字段兜底 |
| `answers` | object | 开放题历史回答 |

---

## meta

| 键 | 说明 |
|---|---|
| `version` | schema 版本。字段结构变更时递增，引擎据此做迁移 |
| `updated_at` | 最后修改日期，`YYYY-MM-DD` |
| `source_file` | 生成此 profile 的简历文件名，便于追溯 |

---

## basic

| 键 | 类型 | 说明 |
|---|---|---|
| `name_cn` | string | 中文姓名 |
| `name_en` | string | 英文/拼音姓名，外企必填 |
| `gender` | enum | `male` / `female` |
| `birth_date` | date | `YYYY-MM-DD`。**零容忍字段** |
| `id_number` | string | 身份证号。建议存原值（填表要真值），但文件权限要保护 |
| `political_status` | enum | `群众` / `共青团员` / `中共党员` / `中共预备党员` / `民主党派` |
| `hometown` | string | 籍贯，如 `江苏省南京市` |
| `household` | string | 户口所在地 |
| `marital_status` | enum | `single` / `married` / `divorced` |
| `health` | string | `良好` / `一般`。部分国企会问 |
| `height_cm` | number | 身高，部分岗位（空乘、军警）必填 |

## contact

| 键 | 类型 | 说明 |
|---|---|---|
| `phone` | string | 11 位手机号，不带分隔符。**零容忍字段** |
| `email` | string | 常用邮箱 |
| `wechat` | string | 微信号 |
| `current_city` | string | 现居城市 |
| `address` | string | 详细通讯地址，部分系统要求精确到门牌 |
| `postal_code` | string | 邮编 |

## job_intent

| 键 | 类型 | 说明 |
|---|---|---|
| `target_role` | string | 目标岗位名 |
| `target_city` | array | 意向城市，按优先级排列 |
| `job_type` | enum | `campus`（校招）/ `intern`（实习）/ `social`（社招） |
| `available_date` | date | 可到岗日期 |
| `expected_salary` | string\|null | 期望薪资。校招通常留空 |
| `accept_relocation` | bool | 是否接受调剂/外派 |
| `accept_shift` | bool | 是否接受倒班 |

## educations[]

| 键 | 类型 | 说明 |
|---|---|---|
| `degree` | enum | `highschool` / `associate` / `bachelor` / `master` / `phd` |
| `school` | string | 学校全称 |
| `school_en` | string | 英文校名，外企用 |
| `major` | string | 专业全称 |
| `start` / `end` | month | `YYYY-MM`。**零容忍字段** |
| `gpa` | number | 绩点原始值 |
| `gpa_scale` | number | 满分制，`4.0` 或 `5.0`。**必须存**，否则无法换算 |
| `gpa_percent` | string | 百分制或排名描述，如 `前 15%` |
| `ranking` | string | 排名，如 `12/180` |
| `city` | string | 学校所在城市 |
| `is_full_time` | bool | 是否全日制 |
| `courses` | array | 主修课程，部分系统要求列 5-8 门 |

### 绩点为什么存四个

不同系统要的形态不同，实测遇到过：

- `gpa` + `gpa_scale` → "GPA 3.62/4.0"
- 只要 `gpa_percent` → "85.5" 或 "前 15%"
- 只要 `ranking` → "12/180"
- 要"平均分" → 需要由绩点换算，没有 `gpa_scale` 就无从下手（3.6/4 ≠ 3.6/5）

存全了，适配器按需取；缺一个，那一步就填不了。

## experiences[]

| 键 | 类型 | 说明 |
|---|---|---|
| `kind` | enum | `internship` / `fulltime` / `parttime` |
| `company` | string | 公司全称 |
| `department` | string | 部门 |
| `title` | string | 职位 |
| `start` / `end` | month | `end: null` 表示**至今**，适配器据此勾选"至今" |
| `city` | string | 工作城市 |
| `description` | string | 职责描述 |
| `achievements` | array | 量化成果，一条一句 |
| `leave_reason` | string | 离职原因。社招常问，校招一般留空 |

## projects[]

| 键 | 说明 |
|---|---|
| `name` / `role` / `start` / `end` | 项目基本信息 |
| `tech` | 技术栈数组 |
| `description` | 描述 |
| `link` | 仓库或演示地址 |

## skills

| 键 | 说明 |
|---|---|
| `languages[]` | `{name, level, score}`，如 `{英语, CET-6, 546}` |
| `programming` | 编程语言数组 |
| `certificates[]` | `{name, date}` |
| `awards[]` | `{name, date, level}`，`level` 取 `国家级` / `省级` / `校级` |

## family[]

| 键 | 说明 |
|---|---|
| `relation` | `father` / `mother` / `spouse` / `sibling` |
| `name` / `phone` / `employer` / `title` | 姓名、电话、工作单位、职务 |

国企、央企、事业单位网申几乎必填。民营企业和外企一般不问。

## custom

站点特有字段的兜底空间。约定用 `站点名.字段名` 作键：

```json
"custom": {
  "beisen.is_only_child": true,
  "beisen.emergency_contact": "李四 13900139000",
  "nowcoder.gaokao_score": 612
}
```

适配器里用 `custom.beisen.is_only_child` 取值。这类字段没有跨站复用价值，但能让流程不断在这里。

## answers

开放题历史回答库。同一类问题在多家的表述大同小异，复用能省大量时间。

```json
"answers": {
  "self_intro": "……",
  "why_company": null,
  "career_plan": "……",
  "biggest_challenge": "……"
}
```

**注意**：这里的值只作为草稿起点。涉及具体公司的问题（"为什么选择我们"）必须每次改写，不能套模板——HR 一眼能看出来。

---

## 校验规则

`pydantic` 模型会做以下校验，不合规时 `jobapply profile review` 阶段就报错，不会拖到填表阶段才炸：

| 字段 | 规则 |
|---|---|
| `birth_date` | 合法日期，且在 1950-01-01 与今天之间 |
| `id_number` | 18 位，校验位算法通过 |
| `phone` | `^1[3-9]\d{9}$` |
| `email` | 基础格式校验 |
| `educations[].start/end` | `YYYY-MM`，且 `start < end` |
| `educations[].gpa` | `0 < gpa <= gpa_scale` |
| `experiences[].end` | 可为 `null`；非 null 时必须晚于 `start` |
| `meta.version` | 必须等于当前支持的版本 |

零容忍字段（身份证、手机、毕业年月）即使校验通过，`review` 阶段也会**强制要求人工确认一次**，不允许直接跳过。
