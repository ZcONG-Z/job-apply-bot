# 安全策略

## 报告漏洞

**不要开公开 Issue。** 涉及凭据泄露、任意代码执行、个人数据外泄的问题，请走以下任一渠道：

- GitHub 的 [Private vulnerability reporting](https://github.com/YOUR_GITHUB_NAME/job-apply-bot/security/advisories/new)
- 邮件：YOUR_EMAIL

请在报告中包含：复现步骤、影响范围、你的环境（OS / Python 版本 / 浏览器版本）。如果涉及敏感数据，请用虚构数据复现。

一般 72 小时内响应。修复前请勿公开细节。

## 支持版本

项目处于 Pre-Alpha，只有 `main` 分支接受安全修复。

| 版本 | 支持 |
|---|---|
| `main` | ✅ |
| 已发布标签 | ❌（早期阶段，请跟进 main） |

---

## 个人数据处理

这个项目会接触身份证号、手机号、家庭住址，所以数据处理是安全策略的一部分，不只是功能设计。

### 数据留在哪

**全部在本机。** 项目不上传任何数据到任何服务器。唯一的网络行为是：

1. 你主动访问的网申页面（浏览器发出）
2. 如果你配置了 LLM 做简历解析兜底，简历文本会发给对应模型服务商——**这一步是可选的、默认关闭的，开启时会显式提示**

没有遥测、没有埋点、没有崩溃上报。

### 哪些文件含敏感信息

| 路径 | 内容 | 是否入库 |
|---|---|---|
| `profile.json` | 身份证、手机、住址、全部经历 | ❌ 已忽略 |
| `.auth/` | 登录 cookie、token | ❌ 已忽略 |
| `inbox/`、`resumes/` | 简历原件 | ❌ 已忽略 |
| `runs/` | 表单截图、DOM 快照 | ❌ 已忽略 |
| `*.db` | 投递台账 | ❌ 已忽略 |

### 脱敏

日志和终端输出中，身份证与手机号按以下规则打码，不做完整打印：

```
身份证  3101**********1234
手机号  138****8000
住址    上海市杨浦区***
```

调试模式（`--debug`）会输出完整值，用之前请确认终端不是共享的、截图不在录屏。

---

## 如果你不小心把个人数据提交了

按顺序做，**不要**以为删掉文件再提交一次就完事——git 历史里还在。

### 1. 先止血，别让爬虫抓到

把仓库临时转为 Private：`Settings → General → Danger Zone → Change visibility`。

GitHub 上的公开提交会被第三方镜像、爬虫、fork 缓存。删掉 `main` 分支上的文件不会让已被索引的内容消失。

### 2. 清理历史

```bash
# 简单场景：刚提交、还没 push
git reset --soft HEAD~1
git restore --staged profile.json
rm profile.json

# 已经 push 了：用 git-filter-repo 重写历史
pip install git-filter-repo
git filter-repo --path profile.json --invert-paths
git push --force --all
```

`git filter-repo` 会改写所有 commit hash，协作者需要重新 clone。个人项目影响不大。

### 3. 让 GitHub 清缓存

历史改写后，旧内容仍可能通过 commit hash 直接访问，且 CDN 有缓存。联系 [GitHub Support](https://support.github.com/contact) 请求清理缓存，说明是敏感数据误提交。

### 4. 改凭据

如果泄露的是 token / cookie / 密码：**立刻作废并重建**。清理历史不能挽回已经泄露的凭据——假设它已经被人拿走了。

### 5. 事后检查

```bash
git log --all --diff-filter=A --name-only | sort -u | grep -E "profile|resume|\.auth"
```

---

## 依赖安全

CI 里跑 `pip-audit` 检查已知漏洞。发现高危依赖漏洞会尽快升级，适配器可能因此短暂失效，请以 `main` 为准。
