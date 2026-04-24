# 文献检索工具与策略指南

## 工具总览

| 工具 | 最适合 | 访问方式 | 速率限制 |
|------|--------|----------|----------|
| Exa Search | 语义搜索、ArXiv 论文 | exa-search MCP tool | 高 |
| Semantic Scholar | 引用分析、影响力评估 | REST API | 100次/5分钟 |
| ArXiv API | 按分类精确检索 | REST API | 无硬限制 |
| Papers With Code | SOTA 排行、代码可用性 | Exa/WebFetch | N/A |

---

## 1. Exa Search（首选工具）

### 使用方法
通过 `exa-search` MCP tool 调用。

### 学术论文搜索策略

```javascript
// 基础学术搜索
{
  query: "recent advances in vision-language models 2024",
  includeDomains: ["arxiv.org"],
  startPublishedDate: "2024-01-01",
  numResults: 20,
  contents: {
    text: { maxCharacters: 1000 },
    highlights: true
  }
}

// 特定领域搜索
{
  query: "diffusion models for protein structure generation",
  category: "research paper",
  numResults: 15,
  contents: {
    text: true,
    summary: true
  }
}

// 多查询搜索（一次最多 5 个附加查询）
{
  query: "transformer architecture improvements efficiency",
  additionalQueries: [
    "linear attention mechanisms",
    "state space models mamba",
    "mixture of experts scaling"
  ],
  includeDomains: ["arxiv.org"],
  numResults: 10
}
```

### 最佳实践
- 用自然语言描述主题，Exa 擅长语义理解
- `includeDomains: ["arxiv.org"]` 限定学术来源
- 使用 `startPublishedDate` 控制时间范围
- `contents.summary` 可快速获取论文摘要
- 分多轮搜索，每轮聚焦一个子主题

---

## 2. Semantic Scholar API

### 端点

```
搜索: GET https://api.semanticscholar.org/graph/v1/paper/search
  ?query={keywords}
  &fields=title,authors,year,citationCount,abstract,externalIds,venue
  &limit=50

论文详情: GET https://api.semanticscholar.org/graph/v1/paper/{paper_id}
  ?fields=title,authors,year,citationCount,abstract,references,citations

批量查询: POST https://api.semanticscholar.org/graph/v1/paper/batch
  Body: {"ids": ["ArXiv:2301.00001", ...]}
  ?fields=title,authors,year,citationCount
```

### 查询技巧

```bash
# 按关键词搜索
curl "https://api.semanticscholar.org/graph/v1/paper/search?query=vision+language+model&fields=title,year,citationCount&limit=20"

# 按 ArXiv ID 查单篇
curl "https://api.semanticscholar.org/graph/v1/paper/ArXiv:2301.12597?fields=title,authors,abstract,citationCount,references"

# 获取论文的引用列表
curl "https://api.semanticscholar.org/graph/v1/paper/{id}/citations?fields=title,year,citationCount&limit=50"
```

### 影响力筛选标准
| 等级 | 引用数 | 用途 |
|------|--------|------|
| 核心论文 | ≥ 50 | 必须精读 |
| 重要论文 | ≥ 20 | 应该引用 |
| 新兴论文 | 近1年，≥ 5 | 关注趋势 |
| 普通论文 | < 5 | 补充覆盖 |

### 速率限制
- 无 API Key: 100 次/5 分钟
- 有 API Key: 更高限额
- 建议每次请求间隔 3 秒
- Key 通过 Header `x-api-key` 传递

---

## 3. ArXiv API

### 端点

```
搜索: GET http://export.arxiv.org/api/query
  ?search_query={query}
  &start=0
  &max_results=50
  &sortBy=submittedDate
  &sortOrder=descending
```

### 常用分类号

| 分类 | 代码 | 描述 |
|------|------|------|
| Computer Vision | cs.CV | 图像、视频、3D |
| NLP | cs.CL | 自然语言处理 |
| Machine Learning | cs.LG | 通用机器学习 |
| AI | cs.AI | 人工智能 |
| ML (Stats) | stat.ML | 统计机器学习 |
| Robotics | cs.RO | 机器人学 |

### 查询语法

```
# 标题和摘要搜索
search_query=ti:transformer%20AND%20abs:vision

# 分类限定
search_query=cat:cs.CV%20AND%20ti:diffusion

# 作者搜索
search_query=au:vaswani

# 组合查询
search_query=(ti:attention%20AND%20abs:efficient)%20AND%20cat:cs.LG
```

### 注意事项
- 返回 Atom XML 格式，需解析
- URL 中空格用 `%20` 编码
- AND/OR 用 `%20AND%20` / `%20OR%20`
- 建议用 Exa 替代，除非需要特定分类号精确检索

---

## 4. Papers With Code

### 访问方式
通过 Exa 搜索 paperswithcode.com：

```javascript
{
  query: "state of the art object detection benchmark",
  includeDomains: ["paperswithcode.com"],
  numResults: 10,
  contents: { text: true }
}
```

### 有用信息
- SOTA 排行榜：各任务/数据集的最佳方法
- 代码实现：论文对应的 GitHub 仓库
- 数据集：基准数据集详情
- 方法趋势：随时间的方法演进

---

## 综合检索策略

### 对每个综述项目

1. **Exa 广度搜索** (Phase 1)
   - 每个子主题 2-3 个语义查询
   - 目标: 初步候选 100-200 篇

2. **Semantic Scholar 深度挖掘** (Phase 2)
   - 从核心论文出发追踪引用链
   - 筛选高影响力论文
   - 目标: 补充 20-30 篇

3. **ArXiv 精确补充** (Phase 3)
   - 按分类号检索特定子领域
   - 目标: 填补覆盖度空白

4. **Papers With Code 对标** (Phase 4)
   - 确认 SOTA 方法是否已覆盖
   - 补充遗漏的重要基准方法

### 去重流程
1. ArXiv ID 精确匹配
2. DOI 匹配
3. 标题归一化后匹配（转小写、去标点、90% 相似度）
4. 多源条目合并时保留信息最完整的版本
