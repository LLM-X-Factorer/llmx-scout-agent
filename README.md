# llmx-scout-agent

> 为 AI 工程布道者准备的"每日选题侦察兵"。从海外 AI 圈的高质量信息源主动寻找有判断空间的选题，扒原文、扒讨论、写预判，输出标准化 source pack 文件给下游内容生产 agent 消费。

**状态**：V0.1 设计阶段（spec 已完成，代码尚未开始）

---

## 它解决什么问题

每天人工刷 Hacker News / GitHub Trending / Reddit + 复制原文 + 翻评论区找争议点 —— 这套流程在内容创作者身上是最大的隐性时间黑洞。

scout 的目标是把这件事自动化到"每天产出几个整理好的资料卡"，让创作者直接进入"判断与表达"阶段。

## 它不替你做的事

- ❌ 不替你做最终判断（最多给一个"判断种子"作为起点）
- ❌ 不写视频脚本 / 文章（那是下游 [llmx-advocate-agent](#) 的事）
- ❌ 不发布到任何平台

scout 是分析师的素材准备员，不是分析师本身。

---

## 核心架构

```
[ Discover ] → [ Filter & Score ] → [ Harvest & Pack ] → [ Notify (可选) ]
```

- **Discover**：HN Firebase API、GitHub Trending、Reddit JSON 端点
- **Filter & Score**：关键词初筛（语法借鉴 [TrendRadar](https://github.com/sansan0/TrendRadar)） → Claude LLM 三维评分
- **Harvest & Pack**：原文 markdown 化、评论 Top 5、相关讨论交叉链接，组装成符合 schema 的 source pack 文件
- **Notify**：可选层（macOS 本地通知 / 钉钉 / 邮件），任何通道失败都不影响主流水线

> **关键路径是文件，不是通知**。所有通知关掉，scout 仍完整工作。

详细规格：[`docs/specification.md`](./docs/specification.md)

---

## 输出长这样

每个候选写到 `output/packs/YYYY-MM-DD/<slug>.md`，是一份带 YAML frontmatter 的 Markdown：

```yaml
---
schema_version: "1.0"
pack_id: "hn-2026-04-26-43891234"
source:
  platform: "hacker_news"
  primary_url: "https://news.ycombinator.com/item?id=43891234"
  title: "RAG is dead, long live agents"
metrics:
  hn_score: 423
  hn_comments: 187
scout_analysis:
  llm_score: 8.5
  judgment_seed: "表面是 RAG 被 agent 取代，实则是检索范式从『一次性召回』转向『迭代式探索』"
  suggested_layer: "留存层"
  controversy_signals:
    - type: "expert_disagreement"
      evidence: "Andrej K. 与 Jerry Liu 在 X 上观点对立"
---

# RAG is dead, long live agents

## 原文正文
... (markdown 化的完整正文)

## 评论区精华
### @user1（234 分）
...
```

完整 schema：[`docs/source-pack-schema.md`](./docs/source-pack-schema.md)

---

## 设计原则

1. **少而精**：V0.1 只接 3 个高 ROI 源，不追求覆盖
2. **失败优于撒谎**：拿不到的字段显式 null，禁止脑补
3. **去重不去同质**：同一 URL 不重复处理；同一话题不同视角全保留（这恰恰是布道者的素材）
4. **schema 是接口**：与下游 agent 之间通过文件 + schema 解耦
5. **手工可注入**：`scout pack <url>` 让你刷推时看到的好文章直接进流水线

---

## 它和 TrendRadar 的关系

[TrendRadar](https://github.com/sansan0/TrendRadar)（46k stars）是 scout 在采集 + 关键词过滤 + 推送主线上的远房亲戚。

| 维度 | TrendRadar | llmx-scout-agent |
|------|-----------|------------------|
| 用户数量 | 几万人，各种场景 | 1 个人，单一布道者场景 |
| 输出形态 | 推送消息 + HTML | **结构化源文件** |
| 下游 | 用户的眼睛 | 另一个 agent 程序 |
| 关注点 | 信息覆盖广 | 信息深度足、判断空间大 |
| 平台数 | 11+ | 3（V0.1） |
| 推送渠道 | 8 个 | 1-2 个，且非关键路径 |
| 部署 | Docker + Actions + S3 | 本地 cron + SQLite |
| 目标代码量 | / | < 2000 行 |

我们借鉴它的关键词语法、URL 标准化思路、单源失败容忍机制。我们**不复刻**它的部署套件、多 provider、Web 编辑器、MCP 服务、翻译模块、HTML 报告等。

详细借鉴清单：[`docs/inspiration/TrendRadar-notes.md`](./docs/inspiration/TrendRadar-notes.md)

---

## 项目状态与路线图

### V0.1 — 当前阶段

- [x] 接口契约：`docs/source-pack-schema.md`
- [x] 下游契约理解：`docs/upstream-context.md`
- [x] 规格说明：`docs/specification.md`
- [x] 架构选型：`docs/architecture-options.md`
- [x] 评分提示词草案：`prompts/scoring.md`
- [ ] 真实样本校准评分提示词（→ v0.2）
- [ ] 代码：HN → 关键词 → 评分 → pack 端到端最短闭环
- [ ] 代码：加 GitHub、Reddit
- [ ] 代码：正文抽取阶梯（trafilatura → readability → playwright）
- [ ] 代码：去重 + score_history
- [ ] 代码：`scout pack <url>` 手工注入
- [ ] 代码：通知层（macOS 本地通知优先）
- [ ] 代码：`scout doctor`
- [ ] cron 上线

### 不在路线图前列

- Web UI / pack 浏览器
- 多 LLM provider
- 翻译模块
- MCP 服务
- 任意 RSS 接入

详见 [`CLAUDE.md`](./CLAUDE.md) "不做清单"。

---

## 技术栈（候选 — 推荐方案）

- Python 3.12+ / `uv` / `typer`
- `httpx` / `trafilatura` / `readability-lxml` / `playwright`（兜底）
- `anthropic` 官方 SDK
- `pydantic v2`（schema 校验）
- `sqlite3`（标准库）
- `structlog`
- `pytest` + `respx`

完整对比与理由：[`docs/architecture-options.md`](./docs/architecture-options.md)

---

## 开始之前

如果你是接手这个项目的人（包括 Claude Code），按顺序读：

1. [`README.md`](./README.md) — 你在这里
2. [`docs/source-pack-schema.md`](./docs/source-pack-schema.md) — 接口契约
3. [`docs/upstream-context.md`](./docs/upstream-context.md) — 下游怎么用
4. [`docs/specification.md`](./docs/specification.md) — V0.1 规格
5. [`docs/architecture-options.md`](./docs/architecture-options.md) — 架构与选型
6. [`CLAUDE.md`](./CLAUDE.md) — 长期记忆与决策日志
7. [`prompts/scoring.md`](./prompts/scoring.md) — 评分提示词

---

## License

MIT — 见 [`LICENSE`](./LICENSE)

---

## 致谢

- [TrendRadar](https://github.com/sansan0/TrendRadar) — 关键词配置语法、URL 标准化、单源失败容忍机制的灵感来源
- [trafilatura](https://github.com/adbar/trafilatura) — 正文抽取的事实最佳
