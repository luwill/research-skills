# litsearch

时间窗受限的高召回文献检索工具。为一个研究课题（如 MICCAI ISLES 2026 缺血性梗死病灶分割）在
指定时间范围内尽可能穷尽地检索文献，并给出**召回率的量化证据**，而不是"我尽力了"。

> 本目录既是一个 Claude Code skill，也是它驱动的完整 CLI。
> 作为 skill 使用见 [`SKILL.md`](./SKILL.md)；下面是直接用命令行的说明。

## 快速开始

需要 [uv](https://docs.astral.sh/uv/) 与 Python ≥ 3.11。

```bash
cp -r lit-search ~/.claude/skills/          # 作为 skill 安装
cd ~/.claude/skills/lit-search && ./install.sh
```

凭据**整段可以留空**：不配任何 key 时用 `lit screen --model host`，
由本机的 Claude Code 做判定。要跑上万条规模再配 API 后端（任何 OpenAI 兼容端点）。

```bash
uv run lit depths                 # 三档的规模、耗时、成本对照

# 协议与产物都放在**你自己的项目**里，不要写进 skill 目录
PROJ=/abs/path/to/your-project
cp references/topic-template.yaml "$PROJ/topics/my-topic.yaml"   # 按四步填

uv run lit plan     --topic "$PROJ/topics/my-topic.yaml"                        # 干跑看量级
uv run lit harvest  --topic "$PROJ/topics/my-topic.yaml" --runs-root "$PROJ/runs" --depth quick
uv run lit screen   my-topic --topic "$PROJ/topics/my-topic.yaml" --runs-root "$PROJ/runs" \
                    --model host --limit 100
uv run lit report   my-topic --topic "$PROJ/topics/my-topic.yaml" --runs-root "$PROJ/runs"
uv run lit deliver  my-topic --topic "$PROJ/topics/my-topic.yaml" --runs-root "$PROJ/runs" \
                    --style gbt7714
```

交付物在 `$PROJ/runs/<topic>/<timestamp>/`：`dois.md`（按质量层分节的全量 DOI 清单）、
`references.md`（同序参考文献）、`coverage_report.md`（召回率证据，**含本次没执行的部分**）。

`examples/` 里有两份跑通过的真实协议：一份生物医学（ISLES 2026 缺血性梗死分割），
一份纯 CS（Context Engineering）。写协议是整条流水线里最需要判断力的一步，
照着改比从模板从头填快得多。

## 为什么不直接用 WebSearch / Google Scholar## 为什么不直接用 WebSearch / Google Scholar

聊天式检索返回的是"相关度排序的前若干条"：不可复现，无法说明漏了什么，也无法在时间窗边界上
保证一致。litsearch 把它变成确定性流水线：

**多源 × 多查询 × 完整翻页 × 引文闭包 × 可度量的饱和判据**

## 流水线

```bash
uv run lit harvest  --topic topics/isles-2026.yaml                        # 主干四源完整翻页
uv run lit harvest  --topic ... --into <run> --phase stage3 \
                    --sources cvf,openreview,grey                         # 顶会与灰色文献并入
uv run lit proceedings <run> --topic ...                                  # MICCAI/LNCS 整卷补全
uv run lit snowball <run> --topic ... --seeds included                    # 双向引文滚雪球至饱和
uv run lit screen   <run> --topic ... --dry-run                           # 筛选成本先摆出来
uv run lit screen   <run> --topic ...                                     # LLM 双通道初筛
uv run lit adjudicate <run> --topic ... --kind screening --input decisions.csv
uv run lit adjudicate <run> --topic ... --kind date --input boundary_cases.csv
uv run lit validate <run> --topic ...                                     # 召回率证据
uv run lit report   <run> --topic ...                                     # PRISMA 计数 + 证据表
uv run lit rank     <run> --ccf CCF.pdf --included                        # 质量分层标注（不过滤）
uv run lit deliver  <run> --topic ... --style gbt7714 --bibtex            # dois.md / references.md
```

产物写入 `runs/<topic>/<timestamp>/`。每次采集 attempt 的原始响应分别保存在
`raw/<阶段>/<attempt-id>/`，并以确定性 gzip 压缩；修复重跑不会让新记录继续指向旧响应。

`lit report` 有两条硬规矩：**各环节计数对不上就拒绝出报告**——一份对不上的 PRISMA
流程图比没有更糟，它看起来像证据，而读者无从发现它是错的；**没做的事不写进图里**
——筛选没跑就只画到「进入标题摘要筛选」；只做完标题摘要初筛时则止于
「进入全文资格审查」，绝不把候选报告当作最终纳入研究。

Zotero 推送由 `.claude/skills/lit-search/SKILL.md` 驱动 MCP 完成，CLI 产出的
`zotero_dois.txt` 和 `included.csv` 是**标题摘要初筛通过、待全文资格审查的候选集**，
不是最终纳入集。没有 DOI 的候选仍留在 CSV 中人工处理。

## 分阶段采集

采集不是一次性的：主干四源 → 顶会/灰色文献 → 会议录整卷 → 引文滚雪球。
`--into <run> --phase <名字>` 把新一批并入已有 run：

- 每阶段各写一个 `records_<阶段>.jsonl`，**原始记录只追加、不改写**，
  "哪一条是哪一阶段拿到的"永远可回答；
- 语料 `corpus.jsonl` 由全部阶段合并去重**重建**——派生产物随时可重算；
- 规范语料只保存轻量 `member_refs` 与完整标识符集合，成员全文字段保留在
  `records*.jsonl`，不再把摘要和引文边重复复制一遍；
- 并入前校验**协议语义指纹**：改术语会被拒绝，加注释不会。
  按文件字节哈希判会让"写一行注释"废掉整次 run 的续接能力，那是在惩罚写注释的人。

## 三个关键设计

**时间窗"宽进严出"。** 各源日期语义不一致（PubMed `pdat` vs `edat`、OpenAlex 的 online-first
日期、arXiv 的 v1 提交日、Crossref 取印刷/在线较早者）。采集时窗口向两端放宽一年，在规范化层
按统一优先级算出 `canonical_date` 再严格过滤，边界记录写入 `boundary_cases.csv` 供人工裁定。
在 CSV 填写 `decision`（`in_window` / `out_of_window`）、`reviewer`、`reason` 后，运行
`lit adjudicate --kind date` 导回；原日期证据与人工裁定轨迹都会保留。

**顶会走专用源。** OpenAlex 的会议 source 不可靠——CVPR 按年碎片化、MICCAI 的 source 只有 38 条
（实际收录在 LNCS 下）、ICLR 只有 896 条。因此 CVPR/ICCV/WACV 走 CVF，ICLR/NeurIPS 走 OpenReview
（顺带拿到被拒稿这类灰色文献），MICCAI 走 Crossref LNCS 卷。

**Crossref 只做补全，不做召回。** 其 `query.bibliographic` 对本课题返回 23 万条模糊排序结果，
`query.container-title="Medical Image Computing…"` 返回 39 万条且排在最前的是 SPIE 的钢管缺陷检测——
都无法作为召回边界；但 DOI 元数据质量最好，且能按 ISBN 精确定向整卷。

## 没有布尔检索能力的源怎么办

主干四源都能把概念块的 AND/OR 交给服务端。阶段 3 的三个源都不能，而且失效方式很隐蔽：

| 源 | 实测行为 | 应对 |
|---|---|---|
| OpenReview | `?content.venueid=` → **403 Challenge**；`/notes/search` 多词是 **OR** 语义，`ischemic stroke lesion segmentation` 返回 `count=10000`（就是返回上限） | 逐个**加引号**的锚点短语；`"ischemic stroke"` → 210 条，有界可翻完 |
| CVF | **无检索接口**，列表页**只有标题**（CVPR 2024 共 2,716 篇） | 整届枚举 → 必需块**并集**在标题上做门槛 → 只对命中者取单篇页拿摘要 → 严格 AND |
| Zenodo | 单框检索，多词 OR；未认证每页上限 **25**（传 100 直接 HTTP 400）；宽泛查询会 504 | 同锚点短语策略，页大小 25 |

共同点是**任务块不能当锚点**：OpenReview 上 `"segmentation"` 一个词就撞上 10,000 上限。
锚点必须取最具区分度的必需块（本课题是 condition），其余必需块在本地 AND
（`localfilter.py`）。这样每条检索式的结果集都有界、都翻得完，召回边界才说得清。

刻意**不**把 MeSH 词纳入本地匹配：受控词当自由文本正则会悄悄放宽概念边界——
本课题的 `Stroke` 会命中 CVPR 的"笔触"论文。

**一个被测出来的"零"。** CVPR/ICCV/WACV 2021–2026 约 9,200 篇里，标题命中条件块的只有 5 篇，
且**全是假阳性**：CVF 语境下 "stroke" 是笔触（Neural 3D Strokes、StrokeFaceNeRF、
Stroke2Sketch），"penumbra" 是半影。缺血性卒中分割的工作都在 MICCAI/TMI/MIA，不在 CV 三大会。
这个源的价值正是把这个零**测出来**，而不是假设出来。

## 源

| 源 | 角色 | 翻页 | 备注 |
|---|---|---|---|
| OpenAlex | 召回主干 + 引文图 | `cursor=*`, 200/页 | `mailto` 进 polite pool |
| PubMed | 召回主干 | `retstart` | 提供 MeSH 受控词；`NCBI_API_KEY` 可提速 |
| Europe PMC | 召回 | `cursorMark` | 补预印本与 PMC 全文 |
| arXiv | 召回 | `start`/`max_results` | `submittedDate` 区间 |
| CVF | 顶会 | 整届枚举 | CVPR / ICCV / WACV；不存在的年份按 404 忽略（ICCV 只在奇数年） |
| OpenReview | 顶会 + 灰色 | `offset` | **全站**检索，含 MIDL、DBLP 镜像、被拒稿与匿名预印本 |
| Crossref | 元数据补全 | `cursor` | 按 ISBN 整卷定向（`lit proceedings`） |
| ~~Semantic Scholar~~ | 召回 + 引文 | — | **尚未实现**；协议里启用会被丢弃并记入未执行部分 |
| Zenodo（灰色） | 挑战赛材料 | `page`，每页 ≤25 | 赛题说明、评测协议、基线权重、数据集 |

## 引文滚雪球：种子集就是全部

关键词检索必然漏掉用词不同的论文——"core infarct estimation"、"tissue-at-risk mapping"
都不会命中 "segmentation"，但它们就是同一件事。滚雪球为此存在，
而**它从哪些论文出发，决定了它是补齐遗漏还是把噪声放大一个数量级**：

实测本课题，从 13,920 条**未筛选**的窗口内记录出发，后向候选是 **134,317** 条；
而这些记录里最终会被纳入的只有几百条。所以默认 `--seeds included`（筛选纳入），
这也是系统综述的规范做法；没跑筛选就想滚雪球会直接报错，而不是替你选一个默认值。

两个方向都走 Europe PMC（免费、无需 key，OpenAlex 匿名配额约每天 100 次请求，不够用）：

- **后向零请求**：PubMed 的 ReferenceList 在采集阶段就存进了 `referenced_works`
  （全语料 207,914 条引文边），只有取新候选的元数据才发请求；
- **前向可批量**：`CITES:<pmid>_MED` 支持 OR 批量，13,920 个种子压到 134 次请求。

批量上限是 **URL 长度**而非条数（实测 200 个 DOI = 6,907 字符 → HTTP 414），按字符预算切批。

实跑：7 条金标准种子 → 3 次请求 → 138 条语料里没有的论文（独有占比 64%）。

### MICCAI：用一篇解锁一整卷

LNCS 的 DOI 后缀里就嵌着卷 ISBN——`10.1007/978-3-031-16443-9_1` → `9783031164439`。
于是语料里**任何一篇** MICCAI 论文都能解锁它所在的整卷，把同卷兄弟篇一次补齐
（实测该卷 70 篇）。这是引文滚雪球之外的另一条闭包路径，且不消耗 OpenAlex 配额。

两个静默失效的陷阱，都已写进测试：MICCAI 在 Crossref 里的 type 是 **book-chapter**
而非 proceedings-article；`filter=isbn:` 必须传**去掉连字符**的 ISBN——
`isbn:978-3-031-16443-9` 静默返回 0 条，`isbn:9783031164439` 返回 70 条。

## 闭源全文（医工交叉领域尤其重要）

IEEE TMI、Medical Image Analysis、Radiology 这类闭源期刊，**约一半的论文有合法的免费版本**。
实测 ISLES 语料里的 53 篇：

| 刊物 | 有合法免费全文 |
|---|---|
| Medical Image Analysis | 14/25 = 56% |
| Radiology | 8/16 = 50% |
| IEEE TMI | 4/12 = 33% |
| 合计 | **26/53 = 49%** |

免费版本来自：仓库预印本/接收版 14、出版商 OA 12。

```bash
uv run lit fulltext <run> --venue "IEEE trans.*medical imaging|medical image analysis"
```

`fulltext.jsonl` 给出每条记录的全部合法位置（按"出版版 > 接收版 > 投稿版"排序）；
拿不到的写入 `institutional_access.csv`。

### 分层解析的顺序

1. **语料内已合并的 arXiv 身份** —— 零成本。方法类论文（TMI/MIA）预印本率高，
   而去重阶段已经把预印本与正式版归并到同一条规范记录上了。
2. **Unpaywall** —— DOI → 全部已知合法 OA 位置（出版商 OA、机构仓库、作者接收版）。免费，仅需邮箱。
3. **Europe PMC / PMC** —— NIH、Wellcome 等资助的论文按政策必须开放，覆盖大量临床研究。
4. **Crossref TDM 链接** —— 标记为 `tdm`，**不**当作开放全文。

### 剩下的 51%：用你自己的订阅，走出版商 TDM 接口

实测这 27 篇的 TDM 链接指向三个域名，对应三套官方接口：

| 域名 | 篇数 | 官方途径 |
|---|---|---|
| `api.elsevier.com` | 11 (MIA) | Elsevier TDM API，机构 IP 内申请 API key |
| `xplorestaging.ieee.org` | 8 (TMI) | IEEE 的 TDM 协议，由图书馆与 IEEE 签订 |
| `pubs.rsna.org` | 8 (Radiology) | RSNA/Atypon，通过机构订阅协商 TDM 权限 |

这三条都是出版商为文本挖掘**正式提供**的接口：拿你所在机构的订阅凭证申请 key，
然后按其速率与用途条款批量取全文。这是唯一可持续的自动化路径——
它不会被封、结果可复现、也不必担心合规问题。

本工具不提供绕过付费墙的功能（Sci-Hub 之类不在范围内）。除了合规问题，
那类来源本身也无法保证版本正确与可复现，不适合做严肃研究的证据基础。

### 补充手段

- **作者主页 / 课题组页面**：医学影像 AI 领域作者常自行放 PDF，`unpaywall` 已覆盖大部分
- **机构代理（EZproxy）**：用你自己的账号，适合少量精读，不适合批量
- **馆际互借**：`institutional_access.csv` 可直接作为申请清单

## 配置

课题协议写在 `topics/<id>.yaml`：时间窗、概念块、纳入排除标准、金标准种子集。
文件哈希在每次 run 时冻结，保证结果可追溯到确切的协议版本。

凭据写在 `.env`（已被 `.gitignore` 排除），或直接导出为环境变量——
**真实环境变量优先**，临时换 key 不会被文件里的旧值盖掉。见 `.env.example`：

| 变量 | 作用 | 不配的后果 |
|---|---|---|
| `LITSEARCH_LLM_API_KEY` | 筛选用的 LLM（任何 OpenAI 兼容端点；旧名 `DEEPSEEK_API_KEY` 仍认） | **不致命**——改用 `lit screen --model host` 走本机 Claude Code，零配置 |
| `OPENALEX_API` | 配额 1,000 → 10,000 信用点/天 | 采集中途 `QuotaExhausted`，捕获-再捕获算不出来 |
| `CONTACT_EMAIL` | polite pool + Unpaywall 必填 | 限速更严 |
| `NCBI_API_KEY` | PubMed 3 → 10 req/s | 只是慢 |
| `S2_API_KEY` | 为尚未实现的 Semantic Scholar 源预留 | 无影响——配上也不会生效 |

解析刻意写得宽松（`KEY = value`、`export KEY=...`、带引号都认）：
认不出来的后果不是报错，而是**静默降级**成匿名限速，最后表现为少召回。

## 筛选用 DeepSeek

模型 `deepseek-v4-pro`，三处与 Anthropic 不同且都影响架构：

- **结构化输出走 strict 工具调用**（`/beta` 端点），不走 JSON 模式——后者只保证
  "是合法 JSON"、不保证形状，官方文档还承认它"偶尔返回空内容"。strict 模式在
  服务端按 JSON Schema 校验，代价是 schema 不能有 `$ref`、每层要
  `additionalProperties: false`、`required` 要列全属性。
- **没有 Batches API**，所以没有批处理半价，只能实时调用 + 并发。
- **上下文缓存自动生效**，命中与否从 `usage.prompt_cache_hit_tokens` 读回。
  命中价 $0.003625/M 对未命中价 $0.435/M，差 120 倍。

没有 `count_tokens` 端点，所以 `--dry-run` 的估算恒为字符数粗估并**如实标注**；
真实用量在跑完后由 API 回报，命令会把两者都打出来。

另外 V4 **默认开思考模式，而思考模式拒绝一切强制 `tool_choice`**
（返回 `400 Thinking mode does not support this tool_choice`）。
默认关思考、强制工具调用：初筛是照着明确标准做分类，思考收益有限，
而"每批都拿得到可解析的判定"是刚需——拿不到就得进人工队列，
等于让人去看模型本来判得了的记录。反向取舍留成显式参数。

### 放量前先冒烟、再校准

```bash
uv run lit screen <run> --topic ... --limit 4     # 冒烟：验 API 契约（约 $0.003）
uv run lit screen <run> --topic ... --limit 100   # 校准：验任务设计（约 $0.05）
uv run lit screen <run> --topic ...               # 放量
```

`--limit` 的结果写入 `screening_trial.json`，**不占正式轮次**——
否则一次校准会盖掉全量结果，而下游只认轮次号最大的那一轮。

这两级不是流程洁癖：冒烟测试抓到了思考模式与 `tool_choice` 互斥（假客户端测不出
服务端约束）；100 条校准抓到了把**全文阶段的标准**用在标题摘要阶段——
人工队列 13% 里有 10 条是模型在等摘要给出 Dice/HD95。

**标题摘要初筛必须从宽**：错误排除不可逆，错误纳入只是多读一篇全文。
提示词里写死了这条阶段规则，只有**主题本身**判不清才判 `unclear`；
按性质只能读全文确认的标准，注明「待全文确认」后仍判 include。
改后同一批 100 条：纳入 3→6，人工队列 13→11，且剩下的全是真分歧与低置信度。

## 开发

```bash
uv sync
uv run pytest          # 单元 + 录制 fixture 集成测试，不打网络
uv run ruff check .
```
