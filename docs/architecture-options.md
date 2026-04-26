# 架构候选方案 v0.1

> 状态：草案 · 等待评审
> 范围：V0.1 MVP 的技术栈与架构。
> 上下文：已有 `docs/specification.md` 定下的功能边界，此处只关心"用什么/怎么组织"。

---

## 决策需要满足的硬约束

1. **代码量 < 2000 行**（用户明确目标）
2. **关键路径是文件**：通知、UI 都是可降级层
3. **本地 cron + SQLite**，不上 Docker / Actions / S3
4. **LLM 仅 Anthropic Claude**，不引入 LiteLLM 一类抽象
5. **下游接口只有 source pack 文件**，不开放 API
6. **运行在用户的 Mac 上**（Apple Silicon, zsh），未来可能搬到 Linux 服务器

---

## 候选方案 A · Python 单体（推荐）

### 选型

| 角色 | 选择 | 理由 |
|---|---|---|
| 语言 | Python 3.12+ | 爬虫/抓取生态最厚，pydantic 校验 schema 顺手 |
| 依赖管理 | `uv` | 比 poetry/pipenv 快一个数量级，单文件 lockfile 干净 |
| CLI 框架 | `typer` | 装饰器式声明，5 行起一个命令 |
| HTTP 客户端 | `httpx` | 同步/异步双形态，自带超时与重试 |
| 正文抽取 | `trafilatura`（主） + `readability-lxml`（备） + `playwright`（兜底） | 阶梯式降级 |
| 评论抓取 | 直接调 HN/Reddit JSON 端点，自写薄封装 | 不引入额外 SDK |
| LLM SDK | `anthropic` 官方 SDK | 唯一 provider，无需抽象 |
| Schema 校验 | `pydantic v2` | 顺手生成 JSON Schema 给 advocate-agent 对照 |
| 持久化 | `sqlite3`（标准库）+ 极薄手写 ORM | 三张表不值得引入 sqlalchemy |
| 调度 | macOS `crontab` / `launchd` | 不内嵌 scheduler |
| 日志 | `structlog` → JSON Lines | 落到 `logs/` |
| 测试 | `pytest` + `respx`（mock HTTP）| 标配 |
| 格式/Lint | `ruff` | 一个工具搞定 format + lint |

### 项目布局

```
llmx-scout-agent/
├── pyproject.toml
├── uv.lock
├── README.md
├── CLAUDE.md
├── LICENSE
├── .gitignore
├── config/
│   ├── keywords.txt
│   ├── notify.toml
│   └── scout.toml          # 全局配置（阈值、API key 引用、source 列表）
├── prompts/
│   ├── scoring.md
│   └── archive/
├── docs/                    # 已有
├── output/
│   ├── packs/
│   └── quarantine/
├── logs/
├── data/
│   └── scout.sqlite
├── src/
│   └── scout/
│       ├── __init__.py
│       ├── cli.py             # typer 入口
│       ├── config.py          # 加载 toml + 环境变量
│       ├── models.py          # pydantic Candidate / Pack / DedupRecord
│       ├── pipeline.py        # discover → filter → harvest → notify 编排
│       ├── sources/
│       │   ├── base.py
│       │   ├── hacker_news.py
│       │   ├── github.py
│       │   └── reddit.py
│       ├── filter/
│       │   ├── keywords.py    # 解析 keywords.txt + 匹配
│       │   └── scoring.py     # 调用 prompts/scoring.md
│       ├── harvest/
│       │   ├── fulltext.py    # trafilatura → readability → playwright
│       │   ├── comments.py    # HN/Reddit 评论
│       │   └── packer.py      # 组装 + schema 校验 + 写盘
│       ├── notify/
│       │   ├── dingtalk.py
│       │   ├── email.py
│       │   └── macos.py
│       ├── store/
│       │   ├── db.py          # sqlite3 极薄封装
│       │   └── schema.sql
│       └── utils/
│           ├── url_norm.py
│           ├── slug.py
│           └── retry.py
└── tests/
    ├── fixtures/              # 各 source 的样本响应
    └── test_*.py
```

### 优劣

✅ 生态最熟、上线最快
✅ trafilatura 是 Python 唯一选择（Node 端 readability 系列差一截）
✅ pydantic v2 对 schema 很顺手
⚠️ 单进程跑全流水线，未来要并行需要少量重构（不影响 V0.1）
⚠️ Playwright 在 Mac 上首次安装较慢（一次性成本）

---

## 候选方案 B · TypeScript（Bun runtime）

### 选型

| 角色 | 选择 |
|---|---|
| 语言 | TypeScript |
| Runtime | Bun（自带 SQLite、HTTP、test） |
| CLI | `clipanion` 或 `commander` |
| HTTP | `fetch`（Bun 原生） |
| 正文抽取 | `@mozilla/readability` + `jsdom` |
| LLM SDK | `@anthropic-ai/sdk` |
| Schema 校验 | `zod` |
| 调度 | crontab |

### 优劣

✅ 与下游 advocate-agent 假如是 TypeScript 的话技术栈一致
✅ Bun 内置 SQLite、test runner，依赖少
✅ schema 用 zod 类型推断比 pydantic 更顺
❌ **正文抽取生态明显落后**：trafilatura 在 benchmark 里平均高 readability 10-15% 准确率
❌ 评论 / 爬虫场景的工具/示例 < Python
❌ Bun 在 Apple Silicon 稳定但不是默认 toolchain，cron 调度时环境激活要小心

---

## 候选方案 C · Python + Rust 抽取层（不推荐）

提一下作为对照：用 `trafilatura` Python，但把 SQLite 操作和 URL 标准化用 Rust 写绑定。

❌ 三张表的负载根本不需要 Rust
❌ 增加 build 复杂度（需要 maturin）
❌ 违反"< 2000 行"目标

不推荐，列在这里只是为了把"性能极致"这条路显式排除。

---

## 推荐：方案 A（Python + uv）

### 推荐理由（按重要性）

1. **正文抽取的质量是 scout 价值的瓶颈**——trafilatura 在 Python 是事实最佳，TS 端没有等价物。这一项足以决定语言。
2. **pydantic + JSON Schema 导出**让 schema 同步给 advocate-agent 几乎零摩擦。
3. **uv 让"Python 慢"的老问题消失**：依赖装得比 npm 快，启动也快。
4. **生态熟悉度**让 < 2000 行真的能做完。

### 推荐理由（不重要但加分）

- 你倾向 Python（明确说过）
- 未来如要做"PDF 论文摘要"附加层，Python 端 PDF 工具（pypdf/pdfplumber）也强

### 可能的妥协

- 如果 advocate-agent 是 TypeScript 项目，且想共享 schema 定义文件，需要做一次"pydantic → JSON Schema → zod"的同步流程。我建议在 `docs/source-pack-schema.md` 里以 JSON Schema 为准，两边各自实现校验，**不共享代码层 schema**，避免跨语言耦合。

---

## 部署形态

```
[crontab]
0 9,15,21 * * *   /usr/bin/env -i HOME=$HOME PATH=$HOME/.local/bin:/usr/bin /Users/liu/Projects/llmx-scout-agent/.venv/bin/scout discover >> /Users/liu/Projects/llmx-scout-agent/logs/cron.log 2>&1
```

每天 9 / 15 / 21 跑三次。理由：
- 9 点：覆盖前一晚海外动态（HN 北美夜间、欧洲早晨）
- 15 点：覆盖海外早晨
- 21 点：覆盖海外白天高产时段

未来如果搬服务器，换成 systemd timer，逻辑不变。

---

## API key 与 secrets

- `ANTHROPIC_API_KEY` 走环境变量，不写 config 文件
- `~/.config/scout/env` 存敏感配置，shell 启动时 source（或 `direnv`）
- 推送 webhook 之类敏感值放 `~/.config/scout/notify.local.toml`（gitignore），仓库里只留 `notify.toml.example`

---

## 风险与缓解

| 风险 | 缓解 |
|---|---|
| Reddit JSON 端点被限流 | User-Agent 必填 + 失败退避 + 单源失败不阻塞 |
| Playwright 首次较慢/占空间 | 仅当 trafilatura 与 readability 都失败时才唤起；可选关闭 |
| LLM 单价上涨 / 成本失控 | 关键词初筛兜底；单次跑设 `--limit`；评分批量化（一次给多条）按需启用 |
| Schema 与 advocate 漂移 | 见 CLAUDE.md「Schema 同步纪律」章节 |
| Mac 笔记本休眠错过 cron | 配 `caffeinate` 或迁移到 launchd（带唤醒）；V0.1 接受偶尔漏跑 |

---

## 落地顺序（推荐 V0.1 sprint）

1. 骨架：`pyproject.toml` + `models.py`（先把 Pack/Candidate 类型定义与 schema 校验跑通）
2. 单源打通：HN discover → 关键词 → LLM 评分 → 写 pack（端到端最短闭环）
3. 加 GitHub、Reddit
4. 加正文抽取阶梯（trafilatura → readability → playwright）
5. 加去重 + score_history
6. 加 `scout pack <url>` 手工注入
7. 加通知层（macOS 本地通知优先）
8. 加 `scout doctor` 与日志可观测
9. 真实样本校准 prompt → bump 到 v0.2

每步一个 git commit，每步可独立 demo。
