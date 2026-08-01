# litsearch 实施计划

目标：为一个课题在指定时间窗内尽可能穷尽地检索文献，并给出**召回率的量化证据**。

## 2026-07-31 审查整改

本轮不删除或改写历史 run；所有格式升级保持旧产物可读。

| 阶段 | 内容 | 状态 |
|---|---|---|
| R1 | 协议快照、消费者兼容性校验、筛选审计元数据 | ✅ 完成 |
| R2 | 双通道全失败不丢记录、付费参数范围校验 | ✅ 完成 |
| R3 | 严格窗口覆盖指标、捕获估计降级、PRISMA 中间态、人工裁定回流 | ✅ 完成 |
| R4 | 原子写入、阶段事务、raw 按阶段版本化、`lit verify` | ✅ 完成 |
| R5 | 规范记录瘦身、测试退避注入、CI 与快速开始文档 | ✅ 完成 |

验收标准：新增问题均有回归测试；`pytest`、`ruff`、`uv lock --check`、wheel 构建全部通过；
现有 run 不迁移也能继续读取，并能被 `lit verify` 标出历史产物的缺失元数据或陈旧状态。

## 2026-07-31 历史 run 瘦身

用户已授权清理历史 run。采用“每个 topic 保留最新 run、旧 run 先归档校验再移除”的
可恢复方案，不删除唯一副本。

| 阶段 | 内容 | 状态 |
|---|---|---|
| C1 | 盘点 run，确定每个 topic 的保留点与旧 run 清单 | ✅ 完成 |
| C2 | 将 6 个旧/失败 run 归档，校验归档成员与压缩完整性 | ✅ 完成 |
| C3 | 删除已归档的原目录，清理空目录与无关元数据 | ✅ 完成 |
| C4 | 对 2 个保留 run 精简 corpus、gzip 原始页、重建可验证报告 | ✅ 完成 |
| C5 | 运行 `lit verify`、计数核验与空间对比 | ✅ 完成 |

结果：`runs/` 从 2,096,448 KiB 降至 589,948 KiB，释放 1,506,500 KiB（71.9%）。
保留的 context-engineering / ISLES run 分别为 4,018 / 26,258 条，均与 manifest 一致；
`lit verify` 均为 0 error，仅保留无法从旧哈希恢复原始协议文本的 1 个诚实 warning。
归档与恢复命令见 `runs/archive/README.md`。

## 阶段

| # | 阶段 | 状态 |
|---|---|---|
| 1 | 骨架 + 协议 + 查询构造 | ✅ 完成 |
| 2 | 四个主干源 + 规范化去重 + `lit plan` / `lit validate` | ✅ 完成 |
| 3 | 顶会与灰色文献源（CVF / OpenReview / Crossref-LNCS / grey） | ✅ 完成 |
| 4a | 双通道 LLM 筛选（`lit screen`） | ✅ 完成 |
| 4b | 引文滚雪球（`lit snowball`） | ✅ 完成 |
| 5 | PRISMA 报告 + Zotero 交接 + Claude Code skill | ✅ 完成 |
| 6 | 换用 DeepSeek + 补上 OpenAlex（捕获-再捕获） | ✅ 完成 |

额外完成：`lit fulltext`（合法全文位置解析）、`lit reclassify`（规则演进后免重采重判）、
`lit proceedings`（LNCS 整卷补全）、`lit harvest --into --phase`（分阶段并入同一 run）。

测试：**612 项全通过**（2026-07-31 整改后，约 3 秒），`ruff` 无告警，语句覆盖率 85%。
源解析用录制的真实响应 fixture，不打网络；真实限速与退避通过注入点在测试中禁用。

**ISLES 2026 语料**（run `20260727T092741Z`，阶段 2 + 阶段 3 全部并入）：

| 指标 | 阶段 2 后 | 阶段 3 后 | 阶段 6 后（含 OpenAlex） |
|---|---|---|---|
| 识别 → 去重后 | 18,320 → 16,685 | 19,413 → 17,484 | 25,020 → **19,221** |
| 窗口内 | 13,478 | 13,920 | **15,425** |
| 待人工裁定 | 109 (0.7%) | 112 (0.6%) | 120 (0.6%) |
| 双通道初筛成本 | $65.59 | $67.69（Claude 批处理半价） | **$9.13**（deepseek-v4-pro） |
| **金标准召回** | 9/9 = 100% | 9/9 = 100% | **9/9 = 100%** |
| 窗口外对照泄漏 | 0/2 | 0/2 | **0/2** |
| PubMed∪OpenAlex 两源并集覆盖度 | 无（缺 OpenAlex） | 无 | **探索性估计 71%** |

来源独有贡献（阶段 6 后）：

| 源 | 总贡献 | 独有 | 独有占比 |
|---|---:|---:|---:|
| pubmed | 16,589 | 13,416 | 81% |
| openalex | 4,833 | 1,601 | 33% |
| crossref（LNCS 整卷） | 668 | **646** | **97%** |
| snowball | 215 | 134 | 62% |
| grey（Zenodo） | 105 | 68 | 65% |
| openreview | 103 | 33 | 32% |
| arxiv | 114 | 13 | 11% |
| europepmc | 975 | 1 | 0% |
| cvf | 1 | 1 | 100% |

补上 OpenAlex 后 arXiv 与 Europe PMC 的独有贡献双双塌到个位数——它们被 OpenAlex
覆盖了。这不是删掉它们的理由（预印本与 PMC 全文覆盖仍有用），但它们**不构成召回边界**，
这是测出来的。

**LNCS 整卷补全的独有占比 97%** 是这一阶段最大的意外收获：仅 17 卷就补回 648 条
别处查不到的 MICCAI 论文——因为关键词检索只命中卷里的少数几篇，同卷兄弟篇
（同一挑战赛的其他方法论文）根本不在检索式的召回范围内。

Europe PMC 的独有贡献仍是 2 条——与 PubMed 高度重复。这是**测出来的**，不是假设的；
保留它是为了预印本与 PMC 全文覆盖，但它不构成召回边界。上述 Chapman 数字只描述
PubMed∪OpenAlex 两源并集相对其估计总体的覆盖度，不代表多源检索流水线的相关文献召回率。

---

## 实测发现（这些都是跑出来的，不是设计时想到的）

### 1. 协议校验抓出了初版 YAML 的召回边界缺陷

初版 `combinations` 含 `[condition, modality, method]`，漏掉 required 的 `task` 块，
等价于"卒中 + 影像 + 深度学习"，召回边界失控。校验器强制 required 块出现在每个组合中。

### 2. PubMed 硬上限 9,999 条——`usehistory` 也绕不过

实测 `retstart=9999` 返回：

> `'retstart' cannot be larger than 9998. For PubMed, ESearch can only retrieve
> the first 9,999 records matching the query.`

本课题的 `condition AND task` 命中 **16,725** 条。若不处理就静默少召回 **40%**，
而这正是本项目要消灭的失败模式。**解法**：按发表日期递归二分，切成命中数低于上限的
子区间分别取全。实测切成 2 段（9,766 + 7,528）。单日仍超限时显式报 partial，不假装取全。

### 3. OpenAlex 已改为信用点配额，降速无用

```
x-ratelimit-limit: 1000        x-ratelimit-remaining: 5
x-ratelimit-credits-required: 10        retry-after: 53780   ← 约 15 小时
```

匿名用户每天约 100 次请求。**两个后果**：
- `Retry-After` 必须设上限（120 秒），否则流水线会静默睡 15 小时。超过上限即判定为
  `QuotaExhausted`，立刻失败并说明何时恢复；该源剩余检索式直接记为 failed，不再白打。
- 必须把请求数压到最低：见下面两条。

### 4. 窄组合对召回零增量，却把配额乘以 N

`[condition, task, modality]` 的结果是 `[condition, task]` 的**真子集**。
在完整翻页的前提下跑它对召回毫无增量。`effective_combinations()` 自动剔除被包含的组合，
把 4 个组合降为 1 个。只有当某个源会截断结果时窄组合才有意义（`include_subsumed=True`）。

### 5. 采集时不再单独调用 estimate

各源翻第一页时本来就返回总数（`meta.count` / `hitCount` / `totalResults` / esearch `count`），
多打一次请求纯属浪费配额。`estimate` 只在 `lit plan` 干跑时使用。

### 6. 按 ±180 天盲标边界，会把 45% 的记录送进人工队列

首次全量跑：1,914 条记录里 **864 条**被标为待人工裁定，其中 **833 条精确到日**——
那种队列没人会看，等于没有把关。**改为只标真歧义**：

- 日期精度不足以判定内外（只知道年份、而窗口从年中开始）
- 不同日期证据把记录指向窗口**不同侧**（预印本 2021-03 在窗外、正式版 2021-09 在窗内）
- 完全没有日期证据

但第一版的冲突判定仍然过激：把**跨字段**分歧（`published_online=2021-12-22` 配
`published_print=2021`）也当成歧义，1,778 条记录进队列、其中 94% 的主日期精确到日。
可 `date_priority` 本来就规定了 online 说了算——这不是歧义，是规则在正常工作。

**最终规则**：真歧义只有两种——
(a) 主日期字段的精度不足以判定内外；(b) **多个源对同一个字段**各执一词且跨了窗口边界
（OpenAlex 说 2021-06-20、PubMed 说 2021-08-01）。

同一批数据的人工队列：45% → 10.7% → **0.7%（109 条）**。这才是人真能逐条看的量。
`near_edge` 仍然计算，但只作报告标注。

### 7. PubMed 的 `.//ArticleIdList` 会取到参考文献的 DOI

`article.findall(".//ArticleIdList/ArticleId")` 会钻进 `PubmedData/ReferenceList`。
实测一篇综述有 156 条参考文献 ID，本文 DOI 被最后一条参考文献覆盖。
必须用直接路径 `PubmedData/ArticleIdList/ArticleId`。
**顺带收获**：这些参考文献是免费的后向滚雪球燃料，已接入 `referenced_works`。

### 8. arXiv 的 DataCite DOI 与 arXiv ID 是同一身份的两种写法

首次验证报"金标准 7/9 = 78%"，漏检两篇 arXiv 论文——但它们**就在库里**，
只是 gold set 用 `10.48550/arXiv.<id>`（arXiv 给每篇论文分配的 DataCite DOI，已实测可解析），
而 Atom feed 的 `arxiv:doi` 字段存的是**期刊 DOI**。打通两种写法后召回 9/9 = 100%。
这也是跨源去重的必要条件——OpenAlex 存的正是 arXiv 的 DataCite DOI。

### 9. 一个源被限流，不该让整批采集作废

arXiv 在连续跑了几轮后开始 429（短查询也拒），一条检索式失败就意味着丢掉已成功的 300MB。
加了 `lit harvest --resume <run>`：只重跑 partial/failed 的检索式，其余从上次的
`records.jsonl` 读回。协议哈希不一致时拒绝续跑——否则一批结果会对应两个协议版本。

### 10. pydantic 默认静默忽略未知配置键

改名 `boundary_days` → `near_edge_days` 后，测试里的旧键名仍然"通过"——因为未知键被默默丢弃。
配置驱动的工具里这等于让整套设置无声失效。所有协议模型已改为 `extra="forbid"`。

### 11. 各源查询语法与命中数（采集窗口 2020-07-01 ~ 2027-07-27）

| 源 | `condition AND task` | 翻页机制 | 备注 |
|---|---|---|---|
| PubMed | 16,725 | 日期二分 + History + efetch | `querytranslation` 确认 MeSH 正确展开 |
| OpenAlex | 5,152 | cursor 200/页 | 受信用点配额限制 |
| Europe PMC | 938 | cursorMark 500/页 | |
| arXiv | 102 | start/max_results | 已验证命中两篇金标准预印本 |

通配符与宽松术语的召回/精确率代价（PubMed）：完整 16,725 → 去掉 `ischemi*` 14,119
→ 去掉全部通配符 5,447 → 再去掉 `infarct volume`/`volumetry` 2,502。
保留（召回优先），代价由 `lit plan` 提前暴露、由筛选阶段的排除标准 X2 处理。

---

### 12. 三个没有布尔检索能力的源，失效方式都很隐蔽

**OpenReview**：`/notes?content.venueid=ICLR.cc/2024/Conference` 返回 **403 Challenge**，
按会场枚举走不通。而 `/notes/search` 的多词查询是 **OR** 语义：

| 检索式 | count |
|---|---|
| `ischemic stroke lesion segmentation`（不加引号） | **10000**（就是返回上限） |
| `"stroke lesion segmentation"` | 69 |
| `"ischemic stroke"` | 210 |
| `"segmentation"` | **10000** |

不加引号会静默退化成"一万条噪声里取前几页"——看起来有结果，召回边界完全失控。
且**任务块不能当锚点**（`"segmentation"` 单独一词就撞上限）。

**CVF**：完全没有检索接口，列表页**只有标题**（CVPR 2024 共 2,716 篇）。
策略是整届枚举 → 必需块**并集**在标题上做门槛 → 只对门槛命中者取单篇页拿摘要 →
严格 AND。门槛用并集而非交集，因为标题里往往只写得下一个概念
（"…Medical Image Segmentation" 不会再写 "ischemic stroke"）。

**Zenodo**：未认证每页上限 **25**，传 100 返回
`HTTP 400 Page size cannot be greater than 25`——而 400 不在可重试状态里，
26 条检索式**整批**失败。这个已写成回归测试。

共同解法：锚点短语（逐条加引号）+ 本地 AND（`localfilter.py`）。
刻意**不**把 MeSH 纳入本地匹配——受控词当自由文本正则会悄悄放宽概念边界。

### 13. CVF 上"卒中"是笔触：一个被测出来的零

CVPR/ICCV/WACV 2021–2026 约 9,200 篇里，标题命中条件块的只有 5 篇，且**全是假阳性**：

- `Neural 3D Strokes: Creating Stylized 3D Scenes with Vectorized 3D Strokes`
- `StrokeFaceNeRF: Stroke-based Facial Appearance Editing`
- `Stroke2Sketch: Harnessing Stroke Attributes for Training-Free Sketch Generation`
- `VQ-SGen: A Vector Quantized Stroke Representation`
- `SoftShadow: Leveraging Soft Masks for Penumbra-Aware Shadow Removal`

缺血性卒中分割的工作都在 MICCAI/TMI/MIA，不在 CV 三大会。这个源的价值正是把这个零
**测出来**，而不是假设出来——"我们查过 CVPR/ICCV/WACV 全部 9,200 篇，没有"
和"我们觉得那里没有"是两回事。

### 14. MICCAI：DOI 后缀里嵌着卷 ISBN

`10.1007/978-3-031-16443-9_1` → ISBN `9783031164439`。语料里**任何一篇** MICCAI 论文
都能解锁整卷（实测 70 篇），把同卷兄弟篇一次补齐。这是引文滚雪球之外的另一条闭包路径，
且不消耗 OpenAlex 配额。

两个静默失效的陷阱：MICCAI 在 Crossref 里的 type 是 **book-chapter** 而非
proceedings-article；`filter=isbn:` 必须传**去掉连字符**的 ISBN——
`isbn:978-3-031-16443-9` 静默返回 **0** 条，`isbn:9783031164439` 返回 70 条。

### 15. CVF 的"这届 0 篇"里藏着两个静默少召回

首轮 CVF 采集后，CVPR2020 与 WACV2020 都记为"整届 0 篇、状态 complete"。查证发现两个成因：

1. **`?day=all` 对 2020 及更早的年份无效**，返回的是个既无论文、**也无逐日链接**的
   空壳页（2,641 字节）。逐日链接只在**不带参数**的索引页上
   （`CVPR2020.py?day=2020-06-16` 等 3 天）。
2. **2020 年代的 href 是相对路径** `content_CVPR_2020/html/…`，2021 起才改成
   `/content/CVPR2021/html/…`。解析器只认后者，整届被读成 0 篇。

（WACV2020 则是网络波动：同一 URL 事后重取有 378 篇。）

**规则**：枚举式源返回 200 却解析出 0 篇，一律**不当作"这届没有论文"**——
先回索引页找逐日子页面，仍然为 0 就报 failed。修复后实测
CVPR2020 = 1,466 篇、WACV2020 = 378 篇。

顺带加了 `--labels`：修好解析缺陷后定点补跑这两届即可，不必把 24 个会议年份
整体重跑一遍（147 次请求 vs 约 2,000 次）。打错 label 会报错而不是静默跑出 0 条。

### 16. 协议一致性该按语义判，不是按字节

`--into` 用协议哈希拒绝跨协议拼接。但哈希原先是按**文件字节**算的，于是
"给 topic.yaml 加一行注释"就会废掉整次 run 的续接能力——那是在惩罚写注释的人。
改为对**校验后的 Topic 模型**做规范化哈希（映射键排序、列表顺序保留，
因为 `max_terms_per_block` 按术语顺序截断）：加注释、调整概念块书写顺序不影响，
改一个术语会被拦下。字节哈希保留在 manifest 里用于精确溯源。

---

## 阶段 3 ✅ 顶会与灰色文献

- `cvf.py` — 整届枚举 + 标题门槛 + 逐篇取摘要
- `openreview.py` — 锚点短语 + 本地 AND，含 MIDL / DBLP 镜像 / 被拒稿 / 匿名预印本
- `grey.py` — Zenodo，挑战赛赛题、评测协议、基线权重、数据集
- `crossref.py` + `lit proceedings` — 按 ISBN 整卷补全 MICCAI/LNCS
- `localfilter.py` — 无布尔能力源的共享概念过滤器
- `harvest_into()` + `lit harvest --into --phase` — 分阶段并入同一 run

`semanticscholar.py` 未做：需 API key，环境中没有。

**不要**用 OpenAlex 的 venue filter 覆盖顶会——实测 CVPR 的 source 按年碎片化、
MICCAI 的 source 仅 38 条（实际收录在 LNCS 下）、ICLR 的 source 仅 896 条。

## 阶段 4a ✅ 双通道筛选

`screen.py`（纯逻辑）+ `screen_runner.py`（API 层）。设计要点：

- **两个通道用不同的思路框架**，不是同一段提示词跑两遍——后者只是把同一个偏差重复两次，
  看起来像双重确认，实际毫无独立性。通道 0 从纳入标准出发，通道 1 主动找排除理由。
- **保留 `unclear` 选项**。逼模型二选一只会把不确定伪装成确定。
- **分歧 / 低置信度 / 任一通道漏判 → 人工队列**，模型不能单方面拍板。
- **编造或串批的 `record_key` 一律丢弃**——判定挂到错误记录上比漏判更糟；
  丢弃后该记录会因"通道缺少判定"进人工队列，正是想要的行为。
- **判定按轮次不可变**（`ScreeningRound` frozen），改判开新一轮并记录协议哈希。
- **成本先于执行可见**：`lit screen --dry-run` 用 `count_tokens` 实测一个代表性批次再外推；
  无凭据时退回字符数粗估并**如实标注**。实测 ISLES 全量 **$65.59**（Batches 半价）。
- 纳排标准放 system 块并开 `cache_control`——标准逐字不变，是天然缓存前缀。

## 阶段 4b ✅ 引文滚雪球

原计划"OpenAlex `referenced_works` + `cites:`"在配额面前不成立：匿名每天约 100 次请求，
而窗口内种子有 13,920 条。改走 Europe PMC，两个方向都能**批量**：

**后向：燃料已经在手，零请求。** PubMed 的 ReferenceList 在阶段 2 就被抓下并存入
`referenced_works`——全语料 **6,840 条记录、207,914 条引文边**，形如 `doi:10.1007/...`
（有 `doi:` 前缀，不剥掉就永远匹配不上语料，会把候选量静默翻好几倍）。
只有取**新候选**的元数据才要发请求。

**前向：`CITES:<pmid>_MED` 可以 OR 批量。** 这是关键解锁——原以为要逐个种子打
（13,920 次请求），实测 200 个种子一批仍可用，压到 134 次。

**批量的上限是 URL 长度，不是条数。** 实测 200 个 DOI（6,907 字符）返回
`HTTP 414 Request-URI Too Large`，100 个（3,475 字符）正常。所以按**字符预算**切批。

### 种子集才是这一步的全部

实测：从 13,920 条**未筛选**的窗口内记录出发，后向候选是 **134,317** 条；
而这 13,920 条里最终会被纳入的大约只有几百条。绝大多数候选来自"本来就该被排除"的
论文的参考文献列表——滚雪球从"补齐遗漏"变成"把噪声放大一个数量级"，
还要为此付十倍筛选费用。

所以默认 `--seeds included`（筛选纳入），这也是系统综述的规范做法。
没跑筛选就想滚雪球会**直接报错**，而不是替用户选一个看起来能跑的默认值。
另有 `gold`（验证链路）、`matched`（本地概念 AND，确定性替代）、`in_window`（召回上限）。

各模式的请求规模（实测 dry-run）：

| 种子模式 | 种子数 | 前向批 | 后向批 |
|---|---:|---:|---:|
| gold | 7 | 1 | 2 |
| in_window | 13,920 | 134 | 1,187 |

### 金标准种子的实跑结果

7 条种子 → 3 次请求 → 取回 215 条 → **138 条是语料里没有的**（独有占比 64%），
其中窗口内 122 条（占轮前语料 0.9%）。7 篇论文就能补回 138 篇关键词检索查不到的，
这正是引文闭包存在的理由。

滚雪球用的是**既有的采集机制**：检索式由语料生成而非协议，其余（cursorMark 翻页、
原始响应落盘、manifest 结局、分阶段并入）全部复用。每轮写
`records_snowball<N>.jsonl`，轮次统计写 `snowball_rounds.jsonl`。

饱和判据用"连续 N 轮"而非"某一轮"：单轮产出会抖动，一轮偶然很少不说明挖到底了；
一轮丰收会把连续计数清零。达到最大轮数仍未饱和会**明确告警**——
那批结果不能声称做到了引文闭包。

## 阶段 5 ✅ 报告与集成

`report.py` + `lit report` 产出 `PRISMA.md` / `evidence_table.md` / `included.csv` /
`coverage_report.md` / `zotero_dois.txt`。

### 两条硬规矩

**对不上就拒绝出报告。** 识别 − 去重 = 规范记录；窗口判定之和 = 规范记录；
筛选各类之和 = 筛选输入。任何一条不成立都抛 `ReportInconsistency`。
一份各环节对不上的 PRISMA 流程图比没有更糟——它看起来像证据，
而读者没有办法从报告本身发现它是错的。

**没做的事不写进图里。** 筛选还没跑，流程图就只画到"进入标题摘要筛选"，
并显式写明为什么。绝不把窗口内记录数（14,042）当作纳入研究数——那是数量级的高估。
证据表同理：方法/数据集/指标要读全文才知道，统一标为"需全文提取"而不是从标题猜。

### 17. PRISMA 自洽性检查当场抓出一个静默少算

首次生成报告时，识别数是 18,962，但语料里明明有 crossref 整卷补全的 670 条。
原因是 `lit proceedings` 自己写了一套采集循环，**没有把检索式结局写进 manifest**，
而识别数是按 manifest 结局统计的。

两处都修了：
- 识别数改为**按实际落盘的逐源记录**统计——记录文件是去重的输入，也就是唯一真相；
- `lit proceedings` 改走与滚雪球相同的 `harvest_into`，不再自己写采集循环。
  重复实现同一件事，迟早会有一份忘记记账。

修后：识别 19,632 → 去重 17,622 → 窗口内 14,042，各环节自洽。

### Zotero：CLI 出数据，skill 做推送

`lit report` 生成 `zotero_dois.txt`（纳入研究里**有 DOI 的**，去重后）。
推送由 `.claude/skills/lit-search/SKILL.md` 驱动 Zotero MCP 完成——
CLI 不该直接调 MCP，那是会话层的能力。

没有 DOI 的纳入研究**不进这个清单**：凭空造一个标识符去推送，比漏推一条糟得多。
它们留在 `included.csv` 里等人工处理，skill 要求把这件事明确告诉用户。

## 阶段 6 ✅ 换 DeepSeek + 补上 OpenAlex

### 18. DeepSeek 的三处差异都影响架构，不是换个 base_url 了事

| | Anthropic | DeepSeek |
|---|---|---|
| 结构化输出 | `messages.parse()` + schema | **strict 工具调用**（`/beta` 端点） |
| 批处理 | Message Batches，半价 | **没有**，只能实时 + 并发 |
| 缓存 | 显式 `cache_control` | 自动，只能从 `usage` 读回命中 |
| token 计数 | `count_tokens` 端点 | **没有**，只能字符数近似 |

**不用 JSON 模式**是关键取舍：`response_format={"type":"json_object"}` 只保证
"是一段合法 JSON"，不保证形状——判定少一个字段、`confidence` 变成字符串都不会被拦下；
官方文档还明确写着这个模式"偶尔返回空内容"。strict 工具调用在**服务端**按 JSON Schema
校验参数，这才是结构化输出。代价是 schema 必须满足三条硬要求（无 `$ref`、每层
`additionalProperties: false`、`required` 列全属性），所以 schema 手写而非从 pydantic 导出。

**缓存必须建模进估算。** 命中价 $0.003625/M 对未命中价 $0.435/M，差 120 倍。
每个通道的 system 前缀完全相同，只有该通道首次请求算未命中。不建模会高估成本——
而高估让人误以为跑不起，和低估同样有害。

成本对比（15,425 条窗口内记录 × 双通道）：Claude Opus 5 批处理半价 **$67.69**
→ deepseek-v4-pro **$9.13**（粗估）。

### 19. 思考模式与强制工具调用互斥——冒烟测试当场撞上

4 条记录的冒烟测试直接返回 400：

> `Thinking mode does not support this tool_choice`

DeepSeek V4 **默认开思考模式**，而思考模式同时拒绝 `tool_choice="required"`
与指定函数两种形式。必须显式 `extra_body={"thinking": {"type": "disabled"}}`。

取舍是明确的：标题摘要初筛是照着 8 条明确标准做的分类，思考带来的判断力提升有限；
而**每一批都能拿到可解析的结构化判定**是刚需——拿不到就得进人工队列，
等于让人去看模型本来判得了的记录。开思考必须放弃强制，这个取舍留给调用方显式做
（`run_screening(..., thinking=True)`）。

**这就是冒烟测试的价值**：4 条记录、$0.003，换来的是没有在 1,234 个请求上
撞同一堵墙。

### 20. 100 条试跑改掉了一个协议与阶段的错配

首轮试跑：纳入 3 / 排除 84 / **人工队列 13**。查看队列发现 10 条都是 `unclear`，
理由高度一致——模型在等摘要给出 Dice/HD95，而那是标准 I3 的要求：

> I3：报告了可复现的方法描述或定量结果（Dice/HD95/AVD/lesion-wise F1 等任一）

**这是把全文阶段的标准用在了标题摘要阶段。** 摘要本来就很少写 Dice。
按 13% 外推，全量会有约 2,000 条进人工队列，其中绝大多数不是真的模棱两可。

修的不是协议（改协议会变更语义指纹，挡住后续的滚雪球并入），而是**提示词里的阶段规则**：

> 这是标题摘要初筛，不是全文评估。错误排除**不可逆**，错误纳入只是多读一篇全文——
> 拿不准就倾向 include。只有当**主题本身**判不清才判 unclear；若某条标准按其性质
> 只能读全文确认，而其余标准已明确满足，就判 include 并注明「待全文确认」。

这是系统综述的标准做法，也是 PRISMA 把 screening 与 eligibility 分成两步的原因。

改后同一批 100 条：纳入 3 → **6**，人工队列 13 → **11**，且成因变成
8 条通道分歧 + 3 条低置信度——**全是真该人工裁的**，再没有"模型在等指标"那类。

### 21. `.env` 解析要宽松，因为失败模式是静默降级

`.env` 里 `OPENALEX_API = axJ...`（等号两边有空格）按裸 `split("=")` 会得到带空格的 key，
认不出来的后果不是报错，而是**源退回匿名限速**、配额提前耗尽，最后表现为少召回。
所以解析容忍空格、`export` 前缀、引号；每个凭据支持多个惯用名；
真实环境变量优先于文件。

### 22. 补上 OpenAlex 后，捕获-再捕获终于能算——结果并不好看

配 key 后配额从 1,000 提到 10,000 信用点/天（每请求 10 点）。OpenAlex 补回
**5,388 条**逐源记录，独有贡献 1,601 条（33%）——不是冗余源。

```
捕获-再捕获（pubmed × openalex）：16,589 / 4,833，重叠 3,099
  估计总体 25,869，已捕获 18,323，估计召回 71%（Chapman 95% CI ±492）
```

**这个 71% 要谨慎解读，而且它偏乐观。** 捕获-再捕获假设两个源相互独立，
但 PubMed 与 OpenAlex 索引的是同一批文献、我们的检索式又高度相关，
正相关会让重叠偏大 → 总体被低估 → 召回被**高估**。所以真实召回不会高于 71%，
很可能更低。

这恰恰说明引文滚雪球（从已纳入研究出发）是必须做的一步，而不是可选项——
关键词检索的天花板就在这里。

### 23. 已经修好的失败，报告却一直挂着告警

Zenodo 因页大小超限整批 400、改成 25 后全部成功。但 PRISMA 报告仍然写着
"grey 采集不完整，其识别数是下界"——因为 `degraded_sources` 把**历史上**
出现过的失败结局也算进来了。

先失败、后补跑成功是常态（改限速、修解析缺陷之后都会这样）。
改为按 `(源, 检索式)` 取**最新**结局。反方向更要命：一条至今仍失败的检索式
必须继续告警，否则"这个源采全了"就是一句假话。

**告警一旦变成噪声，真出问题时就没人看了。**

### 24. 全量筛选的第一轮不可用——以及跑砸的一轮覆盖了跑成的一轮

并发 16 跑全量：1,234 个请求里 **359 个 `APIConnectionError`**，几乎全在通道 0。
结果是 8,915 条记录（**58%**）只拿到一个通道的判定，那份"纳入 373 篇"
不是筛出来的结果，是只有 42% 记录过了双通道的结果。**没有拿它出 PRISMA。**

安全网起作用了（漏判进人工队列，没被当成"这批没有相关文献"），但暴露出真缺口：
**筛选没有断点续跑**。这和采集侧早有的 `--resume` 是同一个教训。

补 `lit screen --resume` 时又踩了两个坑：

1. **判据需要的信息之前没存。** 判定里没有通道号，"通道 0 缺判"和"通道 1 缺判"
   长得一样。补了 `Verdict.channel`，**由驱动层盖**——通道是请求的属性，
   让模型填只会多一个出错的地方。旧判定按位置归位（`merge_verdicts` 按通道顺序
   追加，数量齐了时第 i 个就是通道 i），救回 42% 已花的钱；不齐时不猜，整条重判。
   猜错会让一条记录拿着两份来自**同一视角**的判定，双通道名存实亡——
   而它看起来和真的完全一样。
2. **一次全灭的续跑仍然写出了新轮次。** 余额耗尽导致 718 个请求全失败，
   新轮次里 0 条判定，而下游只认轮次号最大的那一轮——15,375 条判定被一份空文件遮蔽。
   现在**判定数退步就拒绝写入**：跑砸了就保留上一轮，非零退出。

续跑的判据是"这条记录**在这个通道**有没有判定"，不是"进没进人工队列"——
通道分歧和低置信度是**已经判过**的结论，重跑它们既浪费钱，
也会把一个本该由人裁定的分歧变成掷第二次骰子。

并发从 16 降到 6（续跑用 4）。慢一点远比"跑完了但 58% 没判"划算。

### 25. 补上的缺口

- `lit fulltext --included`：之前只能对全语料跑（一万多次请求，还是在给会被排除的
  论文找 PDF）。筛选之后只跑纳入研究才是正确用法。
- `lit screen --limit` 写 `screening_trial.json`，**不占正式轮次**；
  正式轮次号自动递增（原先固定写 round 1，一次校准就会盖掉全量结果）。
- `_load_decisions` 原先读的是从不存在的 `screening_decisions.jsonl`，
  而 `lit screen` 写的是 `screening_round_N.json`——**判定根本传不到滚雪球和报告**。
  即使筛选跑完，`--seeds included` 也会报"没有筛选结果"。现在读轮次号最大的那一轮。

## 未完成：`lit update --since last`

滚动窗口的增量更新**没有做**，因为它有一个尚未解决的语义问题：

- 若把 window 往前滚（2021-07 → 2021-10），那是**新的协议版本**，
  按语义指纹的规则不能与旧 run 合并——这是对的，但用户想要的是"接着上次继续"。
- 若保持协议不变、只取"上次之后新索引的记录"，各源的支持程度不一致：
  PubMed 有 `datetype=edat`、OpenAlex 有 `from_created_date`、
  Europe PMC 与 arXiv 没有对等语义。混着用会造成**跨源不一致的静默少召回**，
  正是本项目要消灭的那类失败。

在想清楚"滚动窗口的协议版本如何与历史 run 建立可追溯关系"之前，
不做一个半对的版本。当前可用的替代：重新 `lit harvest` 一次，
再与旧 run 的 `included.csv` 做差集。

---

## 阶段 7：质量分层与交付（已完成 2026-07-30）

新增三个模块，把"检索完了"变成"能交付"：

| 模块 | 职责 |
|---|---|
| `ccf.py` | CCF 推荐目录解析（PDF/JSON）+ ISSN/全称/简称匹配 |
| `rank.py` | OpenAlex 元数据回填、期刊级指标、分层标注 |
| `order.py` | 质量层判定与排序（S/A/B/C/D/E/F） |
| `deliver.py` | `dois.md` + `references.md` + `references.bib` |

新增命令：`lit rank`、`lit deliver`。

### 26｜阈值筛选被否决，改为分层排序

实测：1,487 篇纳入集以 OpenAlex 指标 4.0 为界，只剩 390 篇（26%），
其中 340 篇是**没有指标**而非指标低——阈值把"数据缺失"和"质量低"执行成了同一个动作。
改为全量交付 + 分层排序，**分层只决定顺序**。

### 27｜分层取所有尺子里最好的那个

CCF 与影响力指标测的不是同一件事：Medical Image Analysis 是 CCF-C，
而它的 OpenAlex `2yr_mean_citedness` = 10.14 是全语料最高。压成一个轴两边都失真。

### 28｜OpenAlex 的 2yr_mean_citedness 不是 JIF

JIF 分母只算 citable items，OpenAlex 分母算全部条目。
发大量学会年会摘要的刊被系统性低估三到五倍——实测 Stroke 1.81、Neurology 1.11。
**阈值不能跨标度搬运。** 报告顶部三行专门声明这件事。

### 29｜排行榜数据不随仓库分发

CCF 目录走 `--ccf` 槽位由用户提供；JCR / 中科院分区是商业授权数据，
仓库里只能有匹配器和 schema。这不是保守，是法律问题。

### 30｜刊名匹配错 2 本、漏 6 本，必须走 ISSN

实测 26 本刊：Neuroradiology→AJNR、Brain Sciences→Behavioral and Brain Sciences。
**错配不报错**，它返回一个看起来完全合理的等级。

### 31｜HTTP 200 但返回 HTML（旧错误复发）

doi.org 内容协商时，部分 DOI 解析到出版商落地页，200 返回整页 HTML，
88 段 HTML 以"已校验"身份写进了参考文献。根因：我只挡了**见过的**失败形态（JSON 错误）。
修法是把校验写成"确认它是我要的格式"。
暴露它的是一个算术不变量：`已校验 + 已降级 == 总条数`。

### 32｜OpenAlex 有日配额，渲染不该重取

`lit deliver` 默认复用 `ranked.jsonl`；`--refresh` 才重取。
实测同一天跑第四遍时 `QuotaExhausted`（重置等待 9.4 小时）。

## 阶段 8：开源化（已完成 2026-07-31）

| 模块 | 职责 |
|---|---|
| `providers.py` | 模型/端点/价目解析。任何 OpenAI 兼容端点可用 |
| `screen_host.py` | 宿主后端：调 `claude -p`，**不需要任何 key** |
| `profiles.py` | quick / standard / systematic 三档 |

新增命令：`lit depths`。`lit screen` 新增 `--model host` 与 `--host-model`，
`lit harvest` / `lit snowball` 新增 `--depth`。

### 33｜价目未知必须报"未知"，不能当 0

`Usage.cost(pricing)` 在价目为 `None` 时返回 `None`。
一个说 $0.00 的 dry-run 比一个说"算不出来"的危险得多——人是照着那个数字决定跑不跑的。
未知模型且没设 `LITSEARCH_LLM_BASE_URL` 直接报错，不猜端点。

### 34｜宿主后端的框架开销是按次算的

实测 `claude -p` 每次调用约 20,000 token 开销（禁用全部工具后仍有
9,410 创建 + 10,589 读取）。因此宿主后端批次从 25 放大到 60。

### 35｜"零配置" ≠ "零成本"

最初把宿主后端写成 "$0（宿主模型）"，实测后改掉：60 条记录
Opus $1.44、Haiku $0.30。订阅用户是**额度内不另计费**，不是不消耗。
`profiles.py` 现在分列 `api_cost` 与 `host_cost` 两栏，
且有测试钉死 `host_cost` 不得为 "$0"。
宿主后端默认 `--host-model haiku`——不指定时 `claude -p` 用 Opus，贵 5 倍。

### 36｜档位只做减法

`sources_for` 与协议启用的源取交集。档位不会打开协议里没声明的源——
否则用户会拿到一份自己没声明过的检索策略。
滚雪球轮数同理：`min(档位上限, 协议 max_rounds)`。

### 37｜两条后端必须产出同构的判定

宿主后端没有工具调用可用，schema 写进提示词；字段名与 API 后端的工具
schema 保持一致（`record_key`）。否则同一个 run 里会出现两种格式的判定文件。
臆造的 key 会被丢弃——一条挂在不存在 key 上的判定永远匹配不上记录，
表现为"筛完了但计数对不上"，比直接漏判更难查。

## 阶段 9｜让"没做的事"和做了的事一样显形

触发：审视 skill 时翻出仓库里第二次真实运行（`context-engineering-2026`，纯 CS 主题）。
产物看起来完整——4,018 条语料、金标准 3/3 = 100%、2,301 篇分层交付——
实际上三件事没做，而**没有任何一份产物提到**。

### 38｜续跑不能扩源（真实 bug）

`031038Z` 是 `030330Z` 的续跑。`harvest()` 用**当前**算出的源清单建 manifest，
于是 `sources` 从 `[openalex, arxiv]` 变成 `[openalex, arxiv, openreview, grey]`——
而续跑**按定义**只重跑上一轮未完成的检索式（这里是 1 条 arxiv），
它没有能力覆盖一个从没跑过的源。

修法：续跑时源清单从上一轮的 manifest 继承，被挡下的写进 notes 并给出补源命令
（`--into <run> --phase <名字> --sources ...`）。

### 39｜"压根没跑"需要自己的表示形式

`partial`/`failed` 有 `degraded_sources` 管着；"声明了但一次都没访问"
在整套产物里没有任何痕迹——它唯一的迹象是 `sources` 与 `outcomes` 对不上，
而没有人会去比对这两个字段。

新增 `run.unrun_sources()` 与 `coverage.find_gaps()`，产出三类缺口：
声明了却没执行结局的源、协议启用但尚未实现的源、跳过的滚雪球。
写进 `coverage_report.md` 的**第一节**，缺口为空也要写出"无"——
「无缺口」必须是结论，不能靠空白段落暗示。

### 40｜证据文件里的硬编码叙述是最坏的一种

`cli.py` 里有一句无条件拼进覆盖率报告的
"捕获-再捕获需 PubMed 与 OpenAlex 同时在场；OpenAlex 受配额限制未纳入"。
那次运行 OpenAlex 明明跑了 3,944 条，缺的是被协议主动关掉的 PubMed。

同一份报告的终端输出（`lit validate`）是**诚实**的，落盘的证据文件是错的——
而留存给人看的是后者。

抽出 `coverage.py`，缺席时点名真正缺的那个源；测试钉死
"配额限制未纳入" 这串字不得在无依据时出现。顺带把
"Google Scholar 抽查未执行"从"尚未完成的验证"改成"本工具不覆盖的验证"——
前者暗示会补上，后者是事实。

### 41｜档位必须进 manifest

`depth` 决定跑几个源、滚几轮雪球，但从没被记录。于是 `quick` 档的产物
和全量跑的产物长得一模一样，只有"缺了什么"这一个区别，而那时缺失是沉默的。
`RunManifest.depth` 现在会落盘（旧 run 为 `None`，表示"早于该字段"而非"没有档位"）。

### 42｜推荐一个不存在的源，比不推荐更糟

`semantic_scholar` 在限速表和 key 别名表里都有位置，`.env.example`、README、
SKILL.md 三处建议非生物医学主题配上它——但 `available_sources()` 里没有它，
协议里写 `enabled: true` 会在交集处被**静默丢弃**。

这条路径的终点是向用户声称"已补上闭源出版商的摘要覆盖"，而实际什么都没发生。
现在 `lit harvest` / `lit plan` 会红字提示，报告记为未执行，三处文档改口。

### 43｜金标准 3 条和 9 条印出来一样

`3/3 = 100%` 与 `9/9 = 100%` 在报告里格式完全相同，读者分辨不出证据强度。
少于 5 条时报告自己标注"证据偏弱"。

### 44｜校准规则查了成因，漏了体量

`--limit 100` 阶段原本只看人工队列的**成因分布**。CE 那次的分布完全"健康"
（70% 是通道分歧与低置信度），但队列有 973 条、占 24.6%——**没有人会真去看**。
而人工队列在流水线里只有出口没有入口，CLI 没有任何命令能把裁定回流。
SKILL.md 增加 15% 的体量红线，并要求把这件事对用户讲明白。

### 45｜验证命令会误杀 arXiv

SKILL.md 让用 `api.crossref.org` 验证金标准 DOI。arXiv 的
`10.48550/arXiv.*` 注册在 DataCite，Crossref 一律 404——
而 CS/AI 主题的金标准几乎全是 arXiv。改走 `doi.org`。

### 开源阻塞项

补 LICENSE（MIT，并声明**不**再分发 JCR/中科院分区与 CCF 目录）；
`CCF.pdf` 与 `.DS_Store` 进 `.gitignore`；README 补快速开始、补
`rank`/`deliver` 两步、修 `RH_NCBI_API_KEY` 笔误、凭据表与 `.env.example` 对齐；
删掉未使用的 `anthropic` 运行时依赖。

**仓库根目录的 `.env` 含真实密钥，且当前不是 git 仓库——
开源前必须轮换该 key 并确认 `git status --ignored` 把它排除在外。**

## 阶段 10｜review codex 的完整性层后的修补

codex 补了原子写、`topic.yaml` 快照、`phases` 提交记录、`artifacts.json` 依赖哈希、
`lit verify` 与 `lit adjudicate`。整体是对的，review 后修了三处。

### 46｜溯源层没覆盖真正的交付物

`verify.py` 的 `KNOWN_DERIVED` 列了 `dois.md` / `references.*` / `ranked.*` /
`tier_report.md`，但 `lit rank` 与 `lit deliver` 用的是普通 `write_text`——
于是**刚生成**的交付物被标成"旧格式产物，没有依赖哈希"，
且这个警告永远清不掉，一条走完全流程的正确 run 必然过不了 `verify --strict`。
工具说了一句关于自己产出的假话。

改：抽出 `_derived_inputs()` 共用依赖清单，`rank`/`deliver` 全部改走 `write_artifact`。
`deliver` 里**调整了写盘顺序**——`dois.md` 把 `ranked.jsonl` 登记为输入，
所以缓存必须先落盘；反过来写记下的是上一次的哈希，产物刚生成就被判过期。
`write_jsonl` 与 `write_artifact` 共用 `jsonl_text()`，保证两条路径逐字节相同。

### 47｜删掉交付物是正当操作，不是完整性损坏

`dois.md` 295 KB、`references.md` 1.7 MB，为腾空间删掉它们是常态。
原实现把"登记过但已不在"报成 **error**，等于把用户的一次正当清理叫做损坏，
真正的损坏（内容被改、输入变了）会淹没在同级噪声里。
改成 warning（`artifact-deleted`）并提示可重建；`artifact-modified` /
`artifact-stale` 保持 error。

### 48｜裁定只消解不确定，不覆盖证据

`apply_dates` 原本不检查记录当前状态，可以把一条已筛选的 `in_window` 记录
改成 `out_of_window`。此时严格窗口条数减 1 而筛选轮次条数不变，
`lit verify` 会报 `screening-corpus-mismatch` 并建议"需重新筛选"——
而重新筛选消除不了这个偏差。改成只受理 `boundary` / `undated`，
并在报错里指出正确路径（修日期证据 → `lit reclassify`）。

### 49｜SKILL.md 曾自相矛盾

`lit adjudicate` 落地后，SKILL.md 一处仍写着人工队列"只有出口没有入口……
永远停在待人工裁定格"，与另一处的"现在都能回流"互斥。已改。
同时补上两类裁定各自的取值域与适用范围。

## 未完成

- `lit update --since last`（见上）
- Semantic Scholar 源（需 key）——**在此之前，三处文档已改口说明它不可用**
- 证据表的全文提取
