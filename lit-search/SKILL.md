---
name: lit-search
description: Runs an exhaustive time-windowed literature search over a research topic and delivers a quality-tiered DOI list plus a matching formatted reference list, with measurable recall (gold-set recall, PRISMA counts, citation-closure saturation). Use for systematic reviews / SLR, 开题报告, 挑战赛调研, or any "把某方向近 N 年文献检索全/理一遍/梳理一遍/查全" request. Builds the corpus — not for reading or summarizing the papers themselves, and not for writing the review text. Not for casual "find me a few papers" lookups.
---

# 时间窗受限的高召回文献检索

驱动 `literature-search/` 这条流水线。核心前提：**召回率不是提示词问题，是检索工程问题。**
反复 WebSearch 得到的是"相关度排序的前若干条"，既不可复现，也无法说明漏了什么。

## 工具位置与产物去向（第一步，别跳过）

CLI 就装在**本 skill 目录里**（`src/litsearch/` + `pyproject.toml`）。
所有命令都要在这个目录下执行——它是 `uv` 找得到项目的地方：

```bash
SKILL_DIR=~/.claude/skills/lit-search     # 本 SKILL.md 所在目录
cd "$SKILL_DIR" && uv run lit --help      # 跑不通就先跑一次 ./install.sh
```

`$LITSEARCH_HOME` 若已设置则优先用它（把工具装在别处的人靠这个覆盖）。
两处都找不到 `src/litsearch/cli.py` → **问用户，不要猜**。

> **产物必须写到用户的项目里，不是 skill 目录里。**
> `--runs-root` 默认是相对路径 `runs/`，而命令的工作目录是 skill 目录——
> 不显式指定的话，几百 MB 的采集结果会堆进 `~/.claude/skills/lit-search/runs/`，
> 用户既找不到，也想不到要去那里清理。**每一条命令都要带上绝对路径**：

```bash
PROJ=/abs/path/to/用户的项目            # 开工前先跟用户确认这个位置
cd "$SKILL_DIR" && uv run lit harvest --topic "$PROJ/topics/<id>.yaml" \
                                      --runs-root "$PROJ/runs" --depth standard
```

协议 YAML 同理——写在用户项目的 `topics/` 下，不要写进 skill 目录。
本目录的 `examples/` 有两份真实协议（生物医学、纯 CS 各一份）可以照抄。
下文命令块为了可读省略了这两个路径参数，**实际执行时必须补上**。

## 判断要不要用

**用**：系统综述、开题报告、挑战赛调研——需要**说得清召回边界**的场合。
**不用**：用户只想快速看几篇代表作。那种情况直接 WebSearch 更快，别拖他走完整条流水线。

## 契约

**输入**：一句话研究主题 + 可选时间范围（不给就默认近 5 年）。
**输出**：

| 文件 | 内容 |
|---|---|
| `dois.md` | 全量 DOI 清单，按质量层分节，每条带证据标记 |
| `references.md` | 参考文献列表，顺序与 `dois.md` 一致 |
| `references.bib` | BibTeX（`--bibtex`，需额外一遍抓取） |
| `PRISMA.md` / `coverage_report.md` | 计数与召回率证据 |

**全量交付，分层只决定顺序，不决定去留。**

两份参考文件，按需读，不要预先读：
`references/topic-template.yaml`（写协议用）、
`references/evidence.md`（下面每条规则背后的实测数字，用户追问或排查时才需要）。

---

## 阶段 0｜写协议（这一步是模型的核心工作）

没有 `lit init` 命令——把主题变成协议需要判断力，不是代码。模板在
`references/topic-template.yaml`，复制到 `topics/<id>.yaml` 后按四步填。

**① 拆概念块。** 3–5 块，标出哪些 `required`。

> **第一个 required 块会成为无布尔检索能力源（CVF/OpenReview/Zenodo）的锚点短语。**
> 把区分度最高的概念放第一位——通常是疾病/对象/材料。放成 "segmentation" 这类泛词，
> 会把整届 CVPR（约 9,200 篇）拉回本地过滤。

**② 提名金标准——5–10 篇，DOI 必须先验证再写入。**

`gold_set` 是整条流水线里唯一能**证伪**的东西。所以：

```bash
curl -sI -o /dev/null -w "%{http_code}\n" -L "https://doi.org/<doi>"   # 200 才许写进协议
```

**走 doi.org，不要走 Crossref。** arXiv 的 `10.48550/arXiv.*` 注册在 DataCite，
`api.crossref.org` 对它一律 404——用 Crossref 验证会把真实存在的预印本当成编造的 DOI 拒掉，
而 CS/AI 主题的金标准**几乎全是 arXiv**。

编一个格式合法但不存在的 DOI，代价不是"少一篇文献"，是**验证链条整个失效**——
你会看到 8/9 的召回，然后花半天排查一个根本不存在的漏检。

**数量不能凑合。** 少于 5 条时 `coverage_report.md` 会自己标注"证据偏弱"：
3/3 和 9/9 印出来一模一样，但前者能证伪的检索缺陷少得多。

同时提名 1–2 篇**窗口外**的真实论文当 `out_of_window_controls`，验证日期过滤真的生效。

**③ 干跑校准量级。**

```bash
uv run lit strategies --topic topics/<id>.yaml    # 只看检索式，不发请求
uv run lit plan       --topic topics/<id>.yaml    # 各源预计命中数
```

| 命中量级 | 判断 | 动作 |
|---|---|---|
| > 50,000 | 概念太宽 | 加 required 块，或收紧通配符 |
| 200 – 20,000 | 合适 | 冻结 |
| < 200 | 太窄 | 补同义词；检查英美拼写变体（ischemic/ischaemic） |

**这是唯一允许调参的窗口。** 一旦开始采集，改术语会变更语义指纹，作废整轮。

**④ 领域判断。** 生物医学之外的主题（纯 CS / 工程 / 材料）要主动提醒用户**两件事**：

1. **摘要覆盖会下降。** 这条流水线对闭源出版商的摘要覆盖实质上是 PubMed 撑起来的
   （实测 Elsevier 95.6%、Springer 80.4%，而 Crossref 上这些条目根本没有摘要）。
   PubMed 用不上时初筛退化成只看标题。**Semantic Scholar 本该补这个位，但当前版本尚未实现**
   ——协议里写 `semantic_scholar: enabled` 会被丢弃（CLI 会红字提示）。不要向用户
   声称补上了覆盖面。
2. **捕获-再捕获会结构性不可得。** 它需要 PubMed × OpenAlex 两个源同时在场。
   关掉 PubMed 后，召回证据就**只剩金标准一个点位**——所以这类主题的 `gold_set`
   更要提满 5–10 条。

---

## 阶段 1–7｜流水线

每一步跑完都要把数字念给用户听，不要静默推进。

先让用户选深度——**代价必须先于执行可见**：

```bash
uv run lit depths     # 三档的规模、耗时、成本对照
```

| 档 | 源 | 滚雪球 | 规模 | 耗时 | API 成本 |
|---|---|---|---|---|---|
| `quick` | 主干四源 | 不跑 | ≤2,000 | ~10 min | $0.1–0.3 |
| `standard`（默认） | 全源 | 1 轮 | 2k–8k | ~40 min | $0.3–1.2 |
| `systematic` | 全源 | 至饱和 | 10k+ | 2–4 h | $3.4–10.4 |

三档的差别只在**跑多少源、滚几轮雪球**。判定规则、去重、时间窗、召回率证据
三档完全一致——**降档降的是覆盖面，不是严谨度**。
`systematic` 必须显式指定并等用户确认。

**`<run>` 从哪来**：`lit harvest` 跑完第一行会打印 run 目录，那就是它。
后续命令也接受 `<topic>/<run_id>`，或**只给协议里的 topic id 自动取最新一次**——
后者最省事。忘了跑到哪一步用 `lit show <run>`。

```bash
# 1 采集
uv run lit harvest    --topic topics/<id>.yaml --depth standard
uv run lit proceedings <run> --topic ...   # 仅 MICCAI/LNCS 类主题；语料里没有 LNCS 会自动跳过

# 2 筛选（三级放量，见下）
uv run lit screen      <run> --topic ... --limit 4
uv run lit screen      <run> --topic ... --limit 100
uv run lit screen      <run> --topic ...
# 在 human_queue.csv 填 decision/reviewer/reason 后导回（可分批）
uv run lit adjudicate  <run> --topic ... --kind screening --input human_queue.csv
# 在 boundary_cases.csv 填 decision/reviewer/reason 后导回
uv run lit adjudicate  <run> --topic ... --kind date --input boundary_cases.csv

# 3 引文闭包（必须在筛选之后）
uv run lit snowball    <run> --topic ... --seeds included
uv run lit screen      <run> --topic ... --resume     # 只补新增记录，不重判已判过的

# 4 证据与报告
uv run lit validate    <run> --topic ...
uv run lit report      <run> --topic ...
uv run lit verify      <run> --strict

# 5 分层与交付（--ccf 可选，先问用户要目录路径）
uv run lit rank        <run> --ccf CCF.pdf --included
uv run lit deliver     <run> --topic ... --ccf CCF.pdf --style gbt7714 --bibtex
```

**滚雪球循环怎么收。** `snowball` → `screen --resume` → `snowball` → …，交替进行。
三种终止，只有第一种能宣称闭包完成：

| CLI 打印 | 含义 | 动作 |
|---|---|---|
| 「已达饱和」 | 连续 2 轮新纳入 < 5% | 停，可以说闭包完成 |
| 「没有新的合格种子」 | 自然枯竭 | 停，可以说闭包完成 |
| 「已达最大轮数但尚未饱和」 | 撞上限了 | **不能说闭包完成**——要么加 `--max-rounds`，要么在报告里写明 |

`--depth quick` 不跑滚雪球，`standard` 只滚 1 轮；要滚到饱和用 `systematic`
或显式 `--max-rounds`。**不要照全量重跑 `screen`**——那会把几千条已判定的再判一遍，
钱翻倍，还可能触发"新一轮判定数少于上一轮"的护栏而拒绝写入。

**补源不能靠续跑。** `harvest --resume` 只重跑上一轮未完成的检索式，它**没有能力**
覆盖一个从没跑过的源。先跑了 quick、之后想补顶会源，用：

```bash
uv run lit harvest --topic ... --into <run> --phase stage3 --sources cvf,openreview,grey
```

## 放量前必须先冒烟、再校准

不要直接对上万条跑筛选。三级放量，每级只花上一级十倍的钱，发现的却是完全不同的问题：

- **`--limit 4`（约 $0.003）验 API 契约。** 假客户端测得了你的代码，测不了服务端约束。
  实测就是在这一步撞到 `Thinking mode does not support this tool_choice`。
- **`--limit 100`（约 $0.02）验任务设计。** 两根轴都要看，缺一根都会放过问题：

  **成因**——大量 `unclear` 且理由雷同 = 把全文阶段的标准用在了标题摘要阶段，
  该改**提示词**而不是改协议（改协议会变更语义指纹，挡住后续滚雪球并入）。
  健康的队列应以"通道分歧"和"低置信度"为主。

  **体量**——队列占比超过 **15%** 就要停下来改标准，不管成因分布多"健康"。
  实测一次 4,000 条的运行队列率 24.6%（973 条），成因分布完全正常，
  但 973 条**没有人会真去看**。`lit adjudicate` 能把裁定结果导回，
  可它是给几十条用的；上千条时正确动作是回来改判定标准，不是把队列丢给用户。
  在裁定导回之前，这些记录不进 `included`，也不进交付物。
- **放量。**

`--limit` 的结果写 `screening_trial.json`，**不占正式轮次**——否则一次校准会盖掉全量结果。

## 不能跳过的顺序

**筛选必须在滚雪球之前。** 实测：从未筛选的 13,920 条种子出发，后向候选是 134,317 条；
而最终会纳入的只有几百条。跳过筛选去滚雪球 = 把噪声放大一个数量级，还要为此付十倍筛选费。
用户催的时候也不要改成 `--seeds in_window`——先把成本讲清楚，让他自己决定。

**滚雪球与筛选必须交替。** 种子是"已纳入"，不筛就没有种子。
实测饱和曲线 34.7% → 4.1% → 0.4%，而 snowball 独有贡献占 92%——
这是纯关键词检索会漏成什么样的直接证据。

**成本必须先于执行可见。** `lit screen --dry-run` 给出 token 数与美元金额。
无凭据时是字符粗估**并明确标注**。不要替用户跳过这一步。

---

## 分层与交付

**只标注与排序，绝不过滤。** 阈值会把"没被评价过"和"质量低"变成同一个动作——
实测以 4.0 切，1,487 条只剩 390 条，其中被删的 340 条是**没有指标**而非指标低。

分层取**所有可用尺子里最好的那个**：

| 层 | 判据 |
|---|---|
| S 顶会顶刊 | CCF-A，或论文引用进入同领域前 1% |
| A 高水平 | CCF-B，或期刊指标 ≥ 8.0，或引用前 10% |
| B 优质 | CCF-C，或期刊指标 4.0–8.0 |
| C 最新预印本 | 预印本 / 仓库，≤ 18 个月 |
| D 会议（未评级） | CCF 目录里没有——**未评级，不是低等级** |
| E 其它期刊 | 期刊指标 < 4.0 |
| F 其余 | 无任何评价依据——**未被评价，不是低质量** |

四条必须讲清楚的事：

1. **CCF 与影响力指标测的不是同一件事，取较优。**
   实测 Medical Image Analysis 是 CCF-C，而它的 OpenAlex 指标 10.14 全语料最高。
2. **OpenAlex `2yr_mean_citedness` 不是 JIF。** JIF 分母只算 citable items，
   OpenAlex 分母算全部条目；发大量学会年会摘要的刊被系统性低估三到五倍
   （实测 Stroke 1.81、Neurology 1.11）。**阈值不能跨标度搬运。**
3. **排行榜数据由用户提供，不随仓库分发。** CCF 目录是公开文档但仍走 `--ccf` 槽位；
   JCR / 中科院分区是商业授权数据，**绝对不能打包进仓库**。
4. **没有目录就不猜等级。** 目录里没有的会议标"未评级"。
   编出来的 CCF-A 和真的长得一模一样，这是最危险的地方。

**引文格式化免 key**：`lit deliver` 走 doi.org 内容协商，支持
`apa / ieee / gbt7714 / nature / ama / bibtex`。

（期刊匹配走 ISSN 而非刊名、样式名发请求前先校验——这两条是 `lit rank` / `lit deliver`
内部的护栏，你没有对应操作。想知道为什么见 `references/evidence.md`。）

---

## 凭据

从 `.env` 或环境变量读（真实环境变量优先）。缺哪个的后果各不相同，要说清楚：

| 缺 | 后果 |
|---|---|
| `LITSEARCH_LLM_API_KEY` | **不致命**——用 `--model host` 走宿主模型，零配置 |
| `OPENALEX_API` | 采集中途 `QuotaExhausted`；捕获-再捕获算不出，召回证据只剩金标准一个点 |
| `CONTACT_EMAIL` | `lit fulltext` 直接拒绝跑——Unpaywall 与 Crossref 都要求声明身份 |

### 筛选后端：两条路

**API 后端**（默认）：任何 OpenAI 兼容端点。三个环境变量
`LITSEARCH_LLM_MODEL` / `_BASE_URL` / `_API_KEY`。内置 DeepSeek 的实测价目，
其它厂商的价目由 `LITSEARCH_PRICING` 提供——**没有价目时 `--dry-run` 会如实报
「无法估算」，不会报一个假的 $0.00**。

**宿主后端**（`--model host`）：调本机 `claude -p`，**不需要任何 key**。
clone 完就能跑，这是给社区用户的零配置入口。三件事要说清楚：

- 每次调用有约 **20,000 token 的框架开销**，所以批次自动放大到 60 条
- 它**不是免费的**：实测 60 条记录约 $0.30 API 等价成本（haiku；用 opus 是 $1.44）。
  订阅用户不额外付费，但会消耗额度——**别说成 "$0"**
- `--host-model` 默认 haiku。上万条规模请改用 API 后端

**OpenAlex 有日配额。** `lit deliver` 默认复用 `ranked.jsonl`，不重取元数据；
要刷新加 `--refresh`。配额耗尽时 `QuotaExhausted` 会带上重置秒数——降速无效，别重试。

---

## 报数字的纪律

- **"本次没执行的部分"必须念给用户听。** `lit report` 会把它算出来写进
  `coverage_report.md` 的第一节，终端也会黄字列出来。**不要跳过这一段去讲纳入数**：
  「跑了没成功」有 partial 告警管着，「压根没跑」曾经在整套产物里没有任何痕迹——
  实测一次交付的 manifest 声明了 4 个源、实际只访问了 2 个，而当时没有一份产物提到。
- **partial/failed 的源要点名。** 它的召回数字是下界，不是实际值。
- **标题摘要初筛通过也不是最终纳入。** 尚未筛选时，窗口内记录数不是相关文献数；
  初筛完成后，`include` 也只是进入全文资格审查的候选报告。`lit report` 在没有全文
  获取、排除理由与最终资格记录时会止于 Eligibility input，你也不要在话里补上终局。
- **被测出来的零要说出来。** "CVPR/ICCV/WACV 2021–2026 共 9,200 篇里一篇都没有"
  是有价值的结论，和"我觉得那里没有"完全不同。
- **金标准漏检必须逐条归因**到具体检索式或源缺陷，不能笼统说"召回率不错"。
- **Chapman 只用于两源重叠诊断。** PubMed 与 OpenAlex 不独立，正相关会使两源并集
  覆盖度偏乐观；它没有验证主题相关性，也不是多源流水线召回率。

## 三条硬规则

**① 200 不代表拿到的是你要的东西。** 枚举源"200 但解析出 0 条"必须报失败；
内容协商拿回 HTML 必须判定为失败。实测这两种都真实发生过，
而且第二次是我只挡了"见过的坏样本"（JSON 错误）导致的复发。
**校验要写成"确认它是我要的"，不是"排除我见过的坏样本"。**

**② 跑砸的一轮不能覆盖跑成的一轮。** 新一轮判定数少于上一轮 = 拒绝写入、非零退出。
断点续跑所需的信息（如通道号）必须在第一次跑的时候就存下来——事后要么补不出来，
要么只能靠猜，而猜出来的和真的长得一样。

> 撞到这个护栏时（退出码 1 + "不写入新轮次"）：**不要重试全量**。先看失败样例定位
> 原因（配额耗尽 / 网络 / 端点变更），修好之后用 `screen --resume` 只补缺的判定。

**③ 规则演进后不要重采。** `lit reclassify` 用当前规则从 `records*.jsonl` 重新去重
与判定窗口，一次请求都不发。某个源的解析缺陷修好后，用
`lit harvest --into <run> --phase fix --labels <那几条>` 定点补跑。
采集是昂贵的一次性动作，判定不是。

## 两个人工队列怎么交代

`human_queue.csv`（判定分歧 / 低置信度）和 `boundary_cases.csv`（日期精度不足）
现在都能经 `lit adjudicate` 回流，并保留裁定人、时间、理由与原判定。

所以跑完必须做两件事，都不能替用户代劳：

1. 把两个文件的**路径和条数**报给用户，并说明 `decision` 允许值；不要替用户裁定。
   `--kind screening` 收 `include` / `exclude`（不接受仍为 `unclear`）；
   `--kind date` 收 `in_window` / `out_of_window`，且**只受理 boundary / undated 的记录**
   ——裁定是用来消解不确定的，不是用来盖掉已有判定的。已确定的日期判错了，
   该修日期证据或 `date_priority` 再跑 `lit reclassify`。
2. 用户填写 `reviewer`、`reason` 后运行相应的 `lit adjudicate --kind ...`。导回后报告
   剩余队列，并运行 `lit report` 与 `lit verify`。队列大到不现实（>15%）时，先校准标准。

`--kind date` 把边界记录改判进严格窗口后，这些记录**还没被筛选过**，
`lit verify` 会报 `screening-corpus-mismatch`。这是正确的提醒：补跑
`lit screen <run> --topic ... --resume` 之后再出报告。

## 推送 Zotero

`lit report` 生成 `zotero_dois.txt`。逐条调 `zotero_add_by_doi`。
**推送前先确认 collection 名称——这是对外部系统的写操作，不要默认执行。**
该清单是标题摘要初筛通过的**全文候选集**，不是最终纳入研究。没有 DOI 的候选不在
清单里，不要凭空造标识符；推完要把这件事告诉用户。

## 产物

`runs/<topic>/<timestamp>/`：

| 文件 | 内容 |
|---|---|
| `raw/<阶段>/<attempt-id>/` | 每次 attempt 的 gzip 逐页原始响应，修复重跑不复用旧页 |
| `records*.jsonl` | 逐源记录，按采集阶段分文件，只追加不改写 |
| `corpus.jsonl` | 去重后的规范语料（派生产物，可随时重算） |
| `manifest.json` | 协议指纹 + 每条检索式的结局与状态 |
| `boundary_cases.csv` | 日期精度不足，需人工裁定 |
| `human_queue.csv` | 双通道分歧或低置信度，需人工裁定 |
| `PRISMA.md` | 各环节计数（不自洽会拒绝生成） |
| `coverage_report.md` | **本次未执行的部分**、严格窗口金标准召回、窗口外泄漏、独有贡献、两源重叠诊断、饱和曲线 |
| `artifacts.json` | 派生产物内容哈希与输入依赖哈希；由 `lit verify` 检查过期 |
| `ranked.jsonl` / `ranked.csv` | 分层标注（`ranked.jsonl` 是元数据缓存） |
| `tier_report.md` | 分层构成与逐级匹配率 |
| `dois.md` / `references.md` / `references.bib` | **交付物** |
