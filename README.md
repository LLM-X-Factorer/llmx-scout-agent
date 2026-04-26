# llmx-scout-agent

> 为 AI 工程布道者准备的"每日选题侦察兵"。从海外 AI 圈的高质量信息源主动寻找有判断空间的选题，扒原文、扒讨论、写预判，输出标准化 source pack 文件给下游内容生产 agent 消费。

**状态**：[v0.1.0](https://github.com/LLM-X-Factorer/llmx-scout-agent/releases) 已发布。HN + GitHub Trending + Reddit 三源端到端跑通；macOS launchd 每天 9/15/21 自动跑；pack 自动 push 到独立仓库 [`llmx-scout-packs`](https://github.com/LLM-X-Factorer/llmx-scout-packs)（私有）。剩余工作见 [issues](https://github.com/LLM-X-Factorer/llmx-scout-agent/issues)。

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

- **Discover**：HN Firebase API、GitHub Trending（HTML scrape）、Reddit JSON（默认 r/LocalLLaMA, r/MachineLearning, r/singularity，可在 `config/scout.toml` 改）
- **Filter & Score**：关键词初筛（语法借鉴 [TrendRadar](https://github.com/sansan0/TrendRadar)） → Claude LLM 三维评分
- **Harvest & Pack**：原文 markdown 化、评论 Top 5、相关讨论交叉链接，组装成符合 schema 的 source pack 文件
- **Notify**：可选层（macOS 本地通知 / 钉钉 / 邮件），任何通道失败都不影响主流水线

> **关键路径是文件，不是通知**。所有通知关掉，scout 仍完整工作。

详细规格：[`docs/specification.md`](./docs/specification.md)

---

## Quick Start

```bash
# 1. 安装依赖（uv 自动建虚拟环境）
uv sync

# 2. 配 LLM key —— 二选一
cp .env.example .env
# 然后编辑 .env，填入 ANTHROPIC_API_KEY（生产）
# 或开发期用 OpenRouter：取消注释 SCOUT_LLM_PROVIDER + OPENROUTER_API_KEY + SCOUT_LLM_MODEL

# 3. 自检
uv run scout doctor

# 4. 跑一次：自动发现（HN + GitHub + Reddit）→ 关键词初筛 → LLM 评分 → 写 pack
uv run scout discover --limit 30
# 限定单源：--source hacker_news / --source github / --source reddit（可重复）

# 5. 看结果
uv run scout list --since today
ls output/packs/

# 6. 手工注入一个 URL（跳过发现，直接打包）
uv run scout pack 'https://news.ycombinator.com/item?id=12345'

# 7. 校准评分提示词
uv run scout score-tune -v

# 8. 上线定时任务（macOS launchd，每天 9 / 15 / 21 跑）
bash scripts/install_launchd.sh
launchctl start com.llmxfactors.scout.discover   # 立刻跑一次验证
tail -f logs/cron.log
# 卸载：bash scripts/uninstall_launchd.sh
```

## 部署到一台全新 Mac（例如 24h Mac mini）

```bash
# 在新机器上：
git clone https://github.com/LLM-X-Factorer/llmx-scout-agent
cd llmx-scout-agent

# 一条命令完成依赖 + .env + doctor + 烟测 + launchd 安装
bash scripts/bootstrap.sh --packs-repo git@github.com:LLM-X-Factorer/llmx-scout-packs.git

# 第一次跑会创建 .env，让你填好后再跑一次。
# --packs-repo 可省略，但开启后 scout 会把每次产出的 pack 自动 push 到独立仓库
# --no-launchd 跳过定时任务安装（适合本地开发）
```

脚本是幂等的：再跑一次只会修复漂移（重装 plist、重跑 uv sync、重做 doctor），不会破坏已有数据。

## Pack 投递（可选，但推荐用于多机部署）

scout 默认把 pack 写到 `output/packs/`（gitignored）。如果你想让下游 agent 在
另一台机器上消费 pack，最干净的方式是建一个独立仓库 `llmx-scout-packs`，
让 scout 跑完自动 commit & push。

```bash
# 1. 在 GitHub 上建 llmx-scout-packs 仓库（公开或私有都行）
gh repo create LLM-X-Factorer/llmx-scout-packs --public

# 2. 在 scout 同级目录 clone 它
cd ..
git clone git@github.com:LLM-X-Factorer/llmx-scout-packs.git
cd llmx-scout-agent

# 3. 在 config/scout.local.toml 里指 output_dir
echo 'output_dir = "../llmx-scout-packs/packs"' >> config/scout.local.toml
# (scout.local.toml 已经在 .gitignore，本机配置)

# 4. 跑一次，看到 ↑ pushed 行说明成功
uv run scout discover --limit 10
```

行为：
- `deliver_on_write = true` 默认开启（在 `config/scout.toml` 可改）
- 每次 `discover` / `pack` 跑完自动 commit + push
- push 失败不影响主流程（commit 留在本地，下次自动追上）
- `--no-deliver` 临时关闭单次投递

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

### V0.1 — 已完成

- [x] 接口契约：`docs/source-pack-schema.md`
- [x] 下游契约理解：`docs/upstream-context.md`
- [x] 规格说明：`docs/specification.md`
- [x] 架构选型：`docs/architecture-options.md`
- [x] 评分提示词 v0.1：`prompts/scoring.md`（三维加权）
- [x] HN → 关键词 → 评分 → pack 端到端最短闭环（含真实运行验证）
- [x] 正文抽取（trafilatura）+ HN 评论扒取
- [x] 去重 + `score_history` 持久化
- [x] `scout pack <url>` 手工注入
- [x] `scout discover` 自动发现 + 评论预览喂 LLM
- [x] `scout score-tune` 校准 harness + `fixtures/calibration/` 样本目录
- [x] `scout doctor` 自检
- [x] OpenRouter 开发期客户端 + `.env` 自动加载
- [x] 51 单元测试 + 真跑端到端 + 真跑校准

### 已规划（GitHub issues 跟踪）

**已完成**
- [x] [#2](https://github.com/LLM-X-Factorer/llmx-scout-agent/issues/2) GitHub Trending source
- [x] [#3](https://github.com/LLM-X-Factorer/llmx-scout-agent/issues/3) Reddit source
- [x] [#5](https://github.com/LLM-X-Factorer/llmx-scout-agent/issues/5) cron / launchd 上线
- [x] [#8](https://github.com/LLM-X-Factorer/llmx-scout-agent/issues/8) Pack delivery via git push 到独立仓库
- [x] [#9](https://github.com/LLM-X-Factorer/llmx-scout-agent/issues/9) launchd plist 模板化
- [x] [#10](https://github.com/LLM-X-Factorer/llmx-scout-agent/issues/10) Bootstrap script for new host

**等数据积累 / 用户输入**
- [ ] [#1](https://github.com/LLM-X-Factorer/llmx-scout-agent/issues/1) Score 阈值边界波动 ±0.4（等 ~30 条 score_history）
- [ ] [#4](https://github.com/LLM-X-Factorer/llmx-scout-agent/issues/4) 重评机制（spec §11，等 dedup 攒一周）
- [ ] [#6](https://github.com/LLM-X-Factorer/llmx-scout-agent/issues/6) Prompt v0.2（等用户提供 20 条真实历史样本）
- [ ] [#7](https://github.com/LLM-X-Factorer/llmx-scout-agent/issues/7) Floor rule 触发与 judgment_space 不一致（配合 #6 一起改）

### 不在路线图前列

- Web UI / pack 浏览器
- 多 LLM provider 抽象（LiteLLM 等；Anthropic 主，OpenRouter 仅开发用）
- 翻译模块
- MCP 服务
- 任意 RSS 接入

详见 [`CLAUDE.md`](./CLAUDE.md) "不做清单"。

---

## 项目布局

```
llmx-scout-agent/
├── src/scout/
│   ├── cli.py              # typer 入口（discover / pack / list / show / score-tune / doctor）
│   ├── config.py           # 配置 + .env 自动加载
│   ├── models.py           # pydantic 模型（schema 校验）
│   ├── pipeline 模块/
│   │   ├── sources/hacker_news.py
│   │   ├── filter/keywords.py    # TrendRadar 风格 DSL
│   │   ├── filter/scoring.py     # Anthropic + OpenRouter clients
│   │   └── harvest/{fulltext,comments,packer}.py
│   ├── store/db.py         # 极薄 sqlite 封装
│   ├── calibration.py      # score-tune harness
│   └── utils/{url_norm,slug,retry}.py
├── prompts/scoring.md      # 评分提示词（带 frontmatter 版本号）
├── fixtures/calibration/   # 校准金标样本（YAML）
├── config/
│   ├── keywords.txt        # 关键词配置
│   └── scout.toml          # 阈值 / 路径 / 模型
├── docs/                   # spec / schema / architecture / decisions
├── tests/                  # pytest（51 用例）
└── output/packs/           # 运行时产出（gitignored）
```

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
