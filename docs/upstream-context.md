# Upstream Context: 下游 advocate-agent 如何使用 Source Pack

> 这份文件让 scout-agent 的开发者（包括你，Claude Code）理解：你产出的源文件最终被怎么消费。
> 这决定了 scout 应该"用力"做什么、可以"省力"做什么。

## 下游项目简介

`llmx-advocate-agent` 是另一个独立项目，职责：消费 source pack 文件，跑一套 8 阶段的内容生产 SOP，产出 B 站视频脚本（Video JSON）+ 发布配套（标题 / 简介 / 标签）。

定位：AI 工程布道者（AI 工程领域的"有独特判断的分析师"）。
核心理念："你是分析师，不是搬运工。" 每条内容必须有独特判断。

## 下游 Phase 概览

advocate-agent 的状态机（来自 chinese-content-workflow skill）：

| Phase | 名称 | scout 的输出会怎么用 |
|-------|------|---------------------|
| 1 | Source Pack Loading & Validation | 读取 + schema 校验 |
| 1.5 | Topic Angle Discovery | **直接消费** `scout_analysis.controversy_signals` |
| 2 | Content Layer Analysis | **参考** `scout_analysis.suggested_layer` |
| 2.5 | ⭐ Core Judgment Extraction | **种子来自** `scout_analysis.judgment_seed`，但必须验证/深化/可推翻 |
| 3 | Three-Layer Deep Thinking | 基于原文 + 评论 + 相关讨论做 WHY/MEANS 追问 |
| 4 | Core Information Extraction | 从原文抽 3-5 个核心 finding + 关键数据 + 故事 |
| 5 | Video JSON Generation | 不直接用 pack，但前面 phase 的产出都源自 pack |
| 6 | Auxiliary Output | 同上 |

## 这意味着 scout 应该用力做什么

### 高优先级（直接决定下游质量）

**1. 把原文完整、干净地 markdown 化**
- Phase 3 的"WHY/MEANS 追问"需要反复读原文，正文质量差 = 下游全废
- 广告、导航、评论嵌入码必须清理
- 代码块、表格、引用要保留结构

**2. 把评论/讨论扒全**
- Phase 1.5 的争议信号、Phase 3 的多视角思考都靠这个
- HN/Reddit 顶部 5-10 条 + 后续高分回复
- 评论里的 reply 关系如果能保留更好（用缩进或显式 `replies_to` 字段）

**3. judgment_seed 写好但不要写死**
- 这是给 advocate 的"礼物"，让 Phase 2.5 有起点
- 必须是"表面 X 但其实 Y"的格式（参考 SKILL.md Phase 2.5 的判断公式）
- 但要清楚标注"这是 scout 的预判，下游可推翻"——不要让你的种子绑架下游

**4. controversy_signals 找全找准**
- Phase 1.5 高度依赖这个（"找争议、找反常识"是病毒传播的关键）
- 不要硬凑——没有就留空数组，比脑造一个假的强

### 中优先级（影响下游效率但不致命）

**5. suggested_layer 给个有依据的判断**
- 引流层 / 留存层 / 转化层的判定标准在 SKILL.md Phase 2
- 拿不准就填 `unsure`，advocate 自己会判

**6. 相关讨论的交叉链接**
- Phase 3 的"专家分歧"很需要这个
- 找到 1-2 条对立观点的链接 + 一句话总结即可，不要展开

### 低优先级（advocate 完全不依赖）

- 优雅的渲染（advocate 不读你的 Markdown 段落，只读 frontmatter + 提取正文/评论）
- 美观的元数据展示

## 这意味着 scout 可以省力的地方

- **不需要做最终判断**——judgment_seed 是种子不是结论
- **不需要写视频脚本**——这是下游的事，scout 完全不碰输出形态
- **不需要决定层级**——unsure 是合法答案
- **不需要识别所有引用关系**——评论区扁平化拿到就行，复杂的引用图不必构建

## 下游不会做的事（所以 scout 必须负责）

- **不会回到 URL 重新抓取**——pack 自包含是硬要求
- **不会调研评论区**——pack 必须把高价值评论扒下来
- **不会判断信息真伪**——但 scout 也不需要判断，只要忠实抓取并标注来源

## 一个失败案例

某天 scout 推送了一个 pack：标题"GPT-5 发布"，judgment_seed 写"OpenAI 又赢了"。

- ❌ 标题准确但毫无深度
- ❌ judgment_seed 不符合"表面 X 但其实 Y"格式
- ❌ 没扒评论区，advocate 无法做 Phase 1.5

advocate 跑这个 pack 会在 Phase 2.5 强制 4 项质检的"判断独特"那关失败，要么打回让 scout 重做，要么我手工补 pack。**这种 pack 不该被产出**——scout 应当在 Filter 阶段就给低分（< 阈值）。

> **scout 的成功标准不是"发现选题"，而是"发现有判断空间且把素材准备好让下游能产出有判断的内容的选题"。**
