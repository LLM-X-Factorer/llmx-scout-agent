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

第四件（如果你要改 prompt 或评分逻辑）：
4. `prompts/scoring.md` 与 `fixtures/calibration/README.md`

---

## 当前进度速览（截至 2026-04-28 v0.1.1）

**生产就绪 + 已部署**：
- 三源 discover：HN + GitHub Trending + Reddit（每日 9/15/21 HK 自动）
- 评分（Anthropic 生产，OpenRouter 开发）
- Harvest：trafilatura 正文抽取 + 平台特定评论抓取
- 自动 git delivery 到独立仓库 `llmx-scout-packs`（HTTPS push 通过 collaborator 权限）
- `scout score-tune` 校准 harness + 5 条种子样本
- `bootstrap.sh` + plist 模板 → 任意 macOS host 一条命令上线
- 75 单元测试 + 真跑校准 + 远程心跳监测（packs 仓 GitHub Actions）

**生产实测数据（< 48 小时）**：
- 26 packs / 2 天，全部 schema 合法
- 平均 7.35 分，6/26 高分（≥ 8.0）
- 平均 2.23 个 controversy_signals/pack
- 0 抓取或推送故障

**契约已验证**（2026-04-29）：advocate v0.2.0 端到端通过 P1-P6，从 scout pack 产出 18 scenes / 6m22s 视频脚本。schema_version 1.0 在两个版本化端点之间正式 honor。

**当前模式**：维护中。仓库不主动开发，等触发条件（README 有清单）。所有 5 个 open issue 都阻塞在用户输入 / 数据积累 / 下游反馈。

**未来工作走 GitHub issues**，不走本文件。决策日志只记"已经定下来"的设计选择。

当前 open issues: `gh issue list`

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

### 2026-04-29 · 项目进入维护模式（已拍板）

- **决策**：scout 仓库进入"操作中、按需响应"状态。**不主动开发 / 不发新 release / 不预防性优化**
- **理由**：
    - 生产已部署且健康（HK Mac mini 自主跑、26 packs 经验证、心跳监测覆盖故障场景）
    - 端到端契约已验证（advocate v0.2.0 实战通过 P1-P6）
    - 5 个 open issue 全部阻塞在数据积累 / 用户输入 / 下游反馈，**没有任何一个能由 scout 单方启动**
    - 在 B 站观众数据回流前，所有内部优化都是猜测
- **重新激活的触发条件**（README "当前模式" 段有完整表格）：
    - 用户提供 20 条历史样本 → 启动 #6 prompt v0.2
    - 用户拿到 Anthropic key → #15 自动消失
    - Cron 跑满一周 → #1 #4 有数据基础
    - Heartbeat 报警 → 故障响应
    - advocate 后续 phase 暴露新契约摩擦 → schema 微调
    - B 站观众反馈 → 反推 prompt 方向
- **不属于"维护模式"的工作**：写新 source（HN/GH/Reddit 已够）、加 LiteLLM 抽象、Web UI、MCP server 等"看着优雅但没需求"的东西
- **拍板人**：用户（2026-04-29）

### 2026-04-29 · 端到端流水线首次产出真实视频脚本（里程碑）

- **结果**：advocate 用 pack `hacker-news-2026-04-28-47921626`（GPU 监控工具）跑完 P1 → P6，产出 18 scenes / 6m22s 视频脚本 + 2 个标题候选 + 159 字简介 + 时间戳。质量评估"看了想录"
- **scout 端的关键确认**：
    - `judgment_seed` 真的成了视频核心论点（"100% 利用率掩盖 90% 计算浪费"几乎一对一传承）
    - `suggested_layer=留存` 是正确判断；advocate 的 tier-drift 机制（spec §5.7）反而是错的，强制改回留存才一次跑通
    - trafilatura 抓的英文原文被 P3 准确消费（"Manya Ghobadi, MIT 教授"权威锚点真的进了视频）
- **scout 字段权重重排**：`suggested_layer` 比我们之前认知的更重要 —— advocate 的 retry-driven tier-drift 不如 scout 的初始判断可靠
- **意义**：scout → packs → advocate → 视频脚本 → 人 → B 站，完整链路验证通过。剩下的环节都是人工录制 + 上传，已不在工程化范围
- **拍板人**：用户（2026-04-29）

### 2026-04-29 · 端到端契约验证通过 + 5 issues 解锁（已完成）

- **决策**：advocate-agent 用 `deepseek/deepseek-chat` 真实跑 pack `reddit-2026-04-28-1sxch39` 通过 P1 → P1.5 → P2.5。Schema 通过、controversy_signals 被 P1.5 真实消费、judgment_seed 被 P2.5 真实启发
- **暴露的两个真问题**：
    - α: `judgment_seed` 同时进 frontmatter 和 body 的 hint 段，advocate uniqueness gate 把 hint 当 source 比对，attempt 1 必失败
    - β: `overrode_seed: bool` 表达不了"采用主题但换视角"的中间态
- **修复策略**：α 是 advocate 内部修（uniqueness 只看 source 段落），β 是 advocate 内部修（改 4 态枚举）。**scout 端不动代码，只在 schema doc 加 hint vs source 段落约定**（c2cff95）
- **advocate 端实测后回归**：同 pack 同 attempt 1 现在 uniqueness 直接 PASS，218 → 226 单测全过
- **意义**：scout 输出契约**实战验证通过**。所有此前被 #16 阻塞的 5 个 issue（#15 / #7 / #1 / #6 / #4）正式解锁可以推进
- **拍板人**：用户（2026-04-29）

### 2026-04-28 · 心跳监测放在 packs 仓而非 scout 仓（已拍板）

- **决策**：每天 22:00 HK 跑 GitHub Actions 检查 packs 仓当天有无新 commit；0 commit 则失败 + 开 issue + 默认邮件
- **为什么放 packs 仓而非 scout 仓**：心跳要观察的"产出"在 packs 仓；scout 仓的 main 不会因 mini 故障而变化
- **不引入 push notification / Slack / Discord**：邮件已经是用户最常看的渠道，加多通道是过度工程
- **拍板人**：用户（2026-04-28）
- **落地**：`llmx-scout-packs/.github/workflows/heartbeat.yml`

### 2026-04-28 · Cloud 迁移延后，mini 出问题再启动（已拍板）

- **决策**：用户暂时无法操作 HK Mac mini（人不在 HK），但 mini 仍在自主跑。**不**预防性迁到 Railway / 腾讯云 Lighthouse 香港 / 等
- **理由**：
    - 实测 < 48h 产出 26 个高质量 packs，0 故障
    - 已加心跳监测，故障立刻知情
    - 提前迁是给已经能跑的系统瞎加复杂度
- **真挂了再做**的两个候选方案，详见 issue 评论里的对比表：
    - **Railway**（推荐）：原生 cron + 原生 secrets + git push 部署，1-2 小时上线，~$5/mo
    - **腾讯云 Lighthouse 香港**：~25 RMB/mo，但要自配 docker / supercronic / SSH key
- **代码冻结风险**：mini 上跑的代码就是 PR #14 之后的版本；今天后任何新 commit 到不了 mini，除非用户回 HK SSH 上去 git pull。可接受 — 当前没有阻塞性的代码改动等待
- **拍板人**：用户（2026-04-28）

### 2026-04-26 · 部署目标 = HK Mac mini，不上 docker / Lighthouse（已拍板）

- **决策**：scout 部署在用户位于香港的 24h Mac mini 上，**不**走 docker + 阿里云 Lighthouse 路线
- **理由**：
    - HK 节点天然解决 Reddit / Anthropic 在大陆的网络问题
    - 同 launchd / uv / Python 工具链零迁移成本
    - 已经是 24/7 在跑的机器，零基础设施成本
    - docker/Lighthouse 的复杂度（镜像构建 / CI / 容器化）对单用户场景过度
- **配套实现**（在同一天完成）：
    - `scripts/com.llmxfactors.scout.discover.plist.template` — plist 模板化，install 时按 host 填充 `@@HOME@@/@@PROJECT_ROOT@@/@@UV_BIN@@`
    - `scripts/bootstrap.sh` — 新机器一键初始化，幂等
- **拍板人**：用户（2026-04-26 晚）
- **如果将来 HK Mac mini 不够用**：先优化（多 host 复制部署即可），再考虑容器化

### 2026-04-26 · Pack 投递走独立私有 git 仓库（已拍板）

- **决策**：scout 产出的 pack **不**留在 scout 代码仓库，而是 push 到独立仓库 `LLM-X-Factorer/llmx-scout-packs`（私有）
- **理由**：
    - scout 代码仓保持干净，不被几百几千个运行时产物污染 commit history
    - 下游 advocate-agent 只需 clone packs 仓库，不必碰 scout 代码
    - GitHub UI 直接渲染 markdown，自带浏览/搜索/审计
    - 跨机器同步的最简方案：`git pull`，无需任何外部存储
- **隐私边界**：私有仓库 — 用户的选题倾向不该公开（它揭示编辑判断与目标受众）
- **实现**：`src/scout/delivery/git.py` 在每次 discover/pack 完成后自动 commit + push；push 失败留地commit、下次重试；`output_dir` 不在 git 仓内则静默 no-op（开发体验不变）
- **拍板人**：用户（2026-04-26）

### 2026-04-26 · 待办与风险走 GitHub issues，不走 CLAUDE.md（已拍板）

- **决策**：本文件「决策日志」只记**已经定下来**的设计选择。"待办 / 风险 / 未来工作"全部开 GH issue 跟踪
- **理由**：用户明确偏好（"问题记录到 github issue 里面好"）；issue 有状态/标签/评论比 markdown 段落好维护
- **How to apply**：发现新风险 → `gh issue create`；新设计想法 → 也开 issue 走讨论；只在拍板后回填到本文件
- **拍板人**：用户（2026-04-26）

### 2026-04-26 · 校准 fixture 默认不锁 seed 关键词（已拍板）

- **决策**：`fixtures/calibration/*.yaml` 中 `judgment_seed_keywords` 默认 `[]`，只校验 `final_score` 和 `layer`
- **理由**：实测同一话题模型能产出多个等效有效的 X-but-Y 角度（datalog-gpu 两次跑给出"稠密 vs 稀疏访存"和"批处理 vs 递归收敛"两个完全不同但都正确的视角）。强制关键词把 LLM 创造力当成失败
- **How to apply**：写新 fixture 时 `judgment_seed_keywords: []`；只在"想阻止具体误读"或"强回归 known-good 概念"时才加
- **拍板人**：用户（2026-04-26）
- **落地**：`fixtures/calibration/README.md` "On seed keywords" 章节

### 2026-04-26 · OpenRouter 作为开发期 LLM 客户端（已拍板）

- **决策**：在 `scout.filter.scoring` 中提供 `OpenRouterClient`，通过 `SCOUT_LLM_PROVIDER=openrouter` + `OPENROUTER_API_KEY` + 可选 `SCOUT_LLM_MODEL` 切换。默认仍是 Anthropic
- **为什么破例**：用户没有 Anthropic API key，需要先看真实 pack 输出做 prompt 校准
- **边界**：
    - 这是 dev/test 路径，**不替代** Claude 作为生产 provider
    - 不引入新的依赖（直接用 httpx，OpenRouter 走 OpenAI 兼容 API）
    - 不引入抽象层（不上 LiteLLM）—— 与"不做多 provider"的核心精神保持一致
    - 不在 `scout doctor` 里把 OpenRouter 当一等公民检测
- **如果未来想再加第三个 provider**：先回答"为什么 Anthropic + OpenRouter 不够"，再开 PR
- **拍板人**：用户（2026-04-26）
- **落地**：`src/scout/filter/scoring.py` `OpenRouterClient`；`cli._llm_client()` 切换逻辑

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
