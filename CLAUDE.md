# CLAUDE.md · 项目长期记忆

> 这份文件是给未来的 Claude Code（或任何接手者）看的。
> 它不重复 README 的"是什么"，而是讲清"为什么这样、不许怎样、踩过什么坑"。

---

## 项目愿景（一句话版）

**每天主动出击，把海外 AI 圈值得做内容的选题，扒成可直接被下游 advocate-agent 消费的标准化 source pack 文件。**

详细愿景见 `README.md` 与 `docs/specification.md`。

---

## 你最先要读的三件东西

1. `docs/source-pack-schema.md` — 接口契约（生死线）
2. `docs/upstream-context.md` — 下游怎么用你的产物（决定你应该用力做什么）
3. `docs/specification.md` — 当前 V0.1 规格

读完再写代码。**这是硬规则，不是建议。**

---

## 与 advocate-agent 的契约纪律

scout 与下游 `llmx-advocate-agent` 通过 source pack 文件通信。

### 1. Schema 是接口，改 schema = 双仓库同 commit

- `docs/source-pack-schema.md` 在两个仓库各存一份完全相同的副本
- **任何修改必须 PR 同时改两边**，否则下游会跑挂
- 兼容性变更（加可选字段）：bump 次版本（1.0 → 1.1）
- 破坏性变更（删字段、改语义）：bump 主版本（1.0 → 2.0），且 advocate 要显式声明支持哪些主版本
- CI 里加一条：scout 仓库的 schema 文件 hash ≠ advocate 仓库的 → 阻断 merge

### 2. Pack 文件一旦写盘就视为不可变

- 想"修正"已有 pack？答案是产出新版本（pack_id 加 `-v2` 后缀），不要原地改
- 原因：advocate 可能已经消费、可能已经基于它产出了内容；事后修改会让历史不可追

### 3. judgment_seed 是种子，不是结论

- 写 seed 的目的是给下游 Phase 2.5 一个起点，不是替它判断
- 必须用"表面 X 但其实 Y"格式
- pack 渲染层必须显式标注 ⚠️"这是 scout 的预判，下游可推翻"
- **宁可留空，不要硬凑** — 评分 prompt 里已强约束

### 4. 失败要诚实

- schema 字段拿不到 → 显式 null，不脑补
- 原文抓取失败 → 仍可打包评论部分，warnings 写明原因
- LLM 调用失败 → 重试 2 次后降级，记日志

---

## 不做清单（按"诱惑度"排序）

每条都附"为什么会被诱惑 + 为什么不做"，避免下次又冒出来。

### 1. ❌ Web UI / pack 浏览器

**为什么会想做**：可视化看起来"专业"。
**为什么不做**：用户只有一个，文件系统 + CLI 已经够。真要做也是"pack 浏览器"，不是"配置编辑器"，而且优先级在所有功能之后。

### 2. ❌ 多 LLM provider（LiteLLM 抽象）

**为什么会想做**：看起来"灵活"，方便用户切。
**为什么不做**：用户只用 Claude，多 provider 是开源项目讨好用户的选择，对我们是无谓复杂度。

### 3. ❌ AI 翻译模块（英文源 → 中文摘要）

**为什么会想做**：用户最终内容是中文。
**为什么不做**：下游 LLM 直接吃英文原文。翻译会降低信息保真度。

### 4. ❌ MCP 服务

**为什么会想做**：跟随趋势。
**为什么不做**：pack 文件就是输出，下游 agent 直接读文件。中间加 MCP 只是多一层运行时依赖。

### 5. ❌ Docker / GitHub Actions / S3 部署套件

**为什么会想做**：看起来"工程化"。
**为什么不做**：本地 cron + SQLite + 写盘已经覆盖所有场景。即使搬服务器也是 systemd timer。

### 6. ❌ 复杂调度系统（timeline.yaml + 5 种预设）

**为什么会想做**：TrendRadar 有，看起来灵活。
**为什么不做**：crontab 三行解决，DSL 是负担。

### 7. ❌ 任意 RSS 接入

**为什么会想做**：源越多看起来越强。
**为什么不做**：会让平台数量爆炸式增加，违背"少而精"。要扩展先评估单条 RoI，单独提 PR。

### 8. ❌ 自动推送给 advocate-agent

**为什么会想做**：减少人工。
**为什么不做**：保持文件解耦，advocate 自己 watch 文件夹即可。耦合 = 一起死。

### 9. ❌ 把"长期标题相似度去重"做成自动合并

**为什么会想做**：避免"重复话题"。
**为什么不做**：同一话题不同视角恰恰是布道者最爱的素材。最多做关联标注，不要做合并。详见 `docs/specification.md` §2.4。

### 10. ❌ 给 scout_analysis 加更多"AI 推断字段"

**为什么会想做**：LLM 看着挺能干。
**为什么不做**：scout 的输出是给下游"做判断"，加越多 AI 推断字段，越容易绑架下游。schema 里现有字段已经经过审慎设计，扩展前先想清楚下游是不是真的要。

---

## 决策日志

每个非显然的决策记一条，日期 + 决策 + 推理 + 谁拍板。

### 2026-04-26 · 选 Python 而不是 TypeScript

- **决策**：用 Python 3.12 + uv + typer + pydantic v2
- **理由**：trafilatura 是正文抽取的事实最佳，Python 独占；pydantic 与 schema 校验天然顺手；用户倾向 Python。
- **被拒方案**：TypeScript/Bun（正文抽取生态弱）；Python+Rust（增加 build 复杂度，量级不需要）
- **拍板人**：用户（待评审中）
- **完整对比**：`docs/architecture-options.md`

### 2026-04-26 · 评分提示词三维加权（已拍板）

- **决策**：把"无判断空间 → 0 分"硬约束改为三维（judgment_space / controversy / info_density）加权 + 弱降权（judgment < 3 时 final=2）
- **理由**：硬阈值会丢"高密度但低判断"的中间地带，影响 score_history 校准。降权方式更柔但仍能有效过滤纯 announcement
- **风险**：可能放进一些不该进 Harvest 的中分候选 → 用阈值（默认 7.0）兜底
- **拍板人**：用户（2026-04-26）
- **落地**：`prompts/scoring.md` v0.1 已按此实现

### 2026-04-26 · `scout pack <url>` 也跑评分（已拍板）

- **决策**：手工注入命令也跑 LLM 评分，但**不受阈值约束**（必打包）；提供 `--no-score` 让用户跳过
- **理由**：手工注入意味着用户已判断这条值得做。让 LLM 顺便给 judgment_seed 草稿是性价比高的事；强行不评分会让下游收到没有 scout_analysis 的 pack，体验差
- **拍板人**：用户（2026-04-26）
- **落地**：`docs/specification.md` §3 CLI 已更新

### 2026-04-26 · GitHub 仓库公开 + MIT（已拍板）

- **决策**：仓库公开开源，MIT 协议
- **理由**：用户认可
- **附带影响**：README 不能含敏感信息（API key、个人邮箱等）；secrets 必须走 `~/.config/scout/` 而非仓内文件
- **拍板人**：用户（2026-04-26）

### 2026-04-26 · V0.1 做今日热度补丁（已拍板）

- **决策**：实现重评机制——已知但未打包的 URL，若当前 metrics 显著上涨，重新走评分 → 可能补打包
- **理由**：用户认可"昨天没爆今天爆"的内容是布道者最不想错过的
- **设计要点**：
    - 不增加额外网络请求（数据来自 discover 已拉到的热门列表）
    - 重评只跑 LLM 评分，原文/评论的二次抓取只在过阈值后发生
    - 原 pack 不可变；补打包写新文件（pack_id 加 `-resurge-N` 后缀）
    - 提供 `scout discover --no-resurge` / `--resurge-only` 开关
- **风险**：同一 URL 可能产生多版 pack；下游 advocate 需识别同 url_hash 多版本
- **拍板人**：用户（2026-04-26）
- **落地**：`docs/specification.md` §11

### 2026-04-26 · 长期标题相似度去重不做（V0.1）

- **决策**：URL hash 强去重；标题相似度只做"标注关联"不做"合并丢弃"
- **理由**：与"同一话题不同视角应保留"原则一致；做相似度合并是高风险低回报
- **未来路径**：若做，新增 `topic_clusters` 表 + pack 间 cross-link

### 2026-04-26 · 通知是可降级层

- **决策**：所有通道默认关闭（除 macOS 本地通知）；任何通知失败仅记日志，不影响其他通道，不阻塞主流水线
- **理由**：关键路径是文件，不是通知
- **影响**：CLI / 测试 / 监控都不能假定通知成功

---

## 工作时的硬规则（给未来的 Claude Code）

### 写代码前
1. 必须先看 `docs/specification.md` 的相关章节
2. 修改 schema 一定看 §"Schema 同步纪律"
3. 加新数据源前问自己："是不是真的高 ROI？"（参考 `docs/inspiration/TrendRadar-notes.md` 的判断准则）

### 写代码时
1. 单文件 < 300 行；超了拆模块，不要堆
2. 不要为了"未来某天可能用到"加抽象层（YAGNI）
3. 不引入新依赖前在 PR 里写明"为什么不用现有的"
4. 错误处理只在系统边界（外部 API、用户输入）；内部代码相信类型契约
5. 注释只写"为什么"，不写"做什么"（identifier 已经说了 what）

### 写代码后
1. 改了流水线行为 → 更新 `docs/specification.md` 对应章节
2. 改了 prompt → bump 版本 + 归档旧版 + 跑 `scout score-tune` 看回归
3. 加了非显然决策 → 记到本文件「决策日志」

### 提交前
1. `ruff check && ruff format`
2. `pytest`
3. commit 信息英文，1-2 句，说"为什么"不是"做了什么"

---

## 关键资源指针

| 你需要 | 看这里 |
|---|---|
| 接口契约 | `docs/source-pack-schema.md` |
| 下游怎么用 | `docs/upstream-context.md` |
| V0.1 规格 | `docs/specification.md` |
| 架构选型 | `docs/architecture-options.md` |
| 评分 prompt | `prompts/scoring.md` |
| 借鉴笔记 | `docs/inspiration/TrendRadar-notes.md` |
| GitHub 主页 | `README.md` |
| 历史决策 | 本文件「决策日志」 |

---

## 用户上下文

- 角色：AI 工程布道者（B 站 LLM-X-Factors）
- 偏好：Python；简洁、不爱过度抽象；中文沟通；commit 信息英文
- 工作环境：macOS Apple Silicon，zsh，Homebrew
- GitHub: `LLM-X-Factorer`
- 公司：tenisinfinite（香港）
- 已有项目：`llmx-advocate-agent`（下游内容生产 agent）

---

## 未解决的开放问题

V0.1 设计阶段的 4 个开放问题已在 2026-04-26 全部拍板，见上方决策日志。

新发现的开放问题请追加到本节，并在拍板后移到决策日志。

（当前为空。）
