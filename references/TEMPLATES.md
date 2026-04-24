# 项目文件模板

## 项目目录结构

```
{space}/{project-name}/
├── AGENTS.md                    # 项目级规则
├── IMPLEMENTATION_PLAN.md       # 分阶段执行计划
├── literature_matrix.md         # 文献矩阵
├── paper_analyses/              # 逐篇分析
│   ├── {arxiv-id-1}.md
│   └── ...
├── comparison_tables.md         # 对比表汇总
├── manuscript_draft.md          # 综述草稿
├── review_report.md             # 审校报告
└── manuscript_final.md          # 终稿
```

---

## AGENTS.md 模板（项目级规则）

```markdown
# [项目名] — 写作规范

## 术语统一

| 统一用语 | 避免使用 |
|---------|---------|
| [term1] | [variant1], [variant2] |
| [term2] | [variant1], [variant2] |

## 写作风格
- 学术严谨，使用 hedging language
  - 推荐: may, suggests, appears to, has shown promising results
  - 禁止: is the best, proves, definitely, always
- 每个论断需引用支撑
- 段落结构: 主题句 → 支撑证据 → 分析 → 过渡

## 方法描述模板
[Author] et al. [ref] proposed [method], which [innovation].
The key components include: (1) [comp1]; (2) [comp2].
Evaluated on [dataset], the method achieves [metric] of [value].

## 引用格式
- 数据引用: "...achieved 0.89 [23]"
- 方法引用: "Gu et al. [45] proposed..."
- 多引用: "Several studies [12, 15, 23]"
- 对比引用: "While [12] focused on..., [15] addressed..."

## Agent 交接协议
- 完成阶段后更新 IMPLEMENTATION_PLAN.md 状态
- 在输出文件末尾 @mention 下一位 Agent
- 如遇问题 @mention 研究主管
```

---

## IMPLEMENTATION_PLAN.md 模板

```markdown
# Implementation Plan: [综述标题]

## 项目概览
- **选题**: [具体主题]
- **范围**: [时间范围] | [目标顶会] | [子领域]
- **目标文献量**: [N] 篇
- **分类框架**: [简述]

---

## Phase 1: 项目初始化 ✅
**负责人**: 研究主管
**状态**: 已完成
**输出**: 本文件 + AGENTS.md

---

## Phase 2: 文献收集
**负责人**: [@文献侦查员](mention://agent/177704336830000)
**状态**: 待启动
**输入**: 本计划中的检索策略
**输出**: literature_matrix.md

### 质量门控
- [ ] 总文献量 ≥ [N] 篇
- [ ] 每个分类 ≥ 5 篇（新兴 ≥ 2 篇）
- [ ] 近 3 年占比 ≥ 50%
- [ ] 多源覆盖

### 检索策略

#### 关键词
- [keyword1]
- [keyword2]
- [keyword3]

#### Exa 语义查询
1. "[natural language query 1]" (includeDomains: arxiv.org)
2. "[natural language query 2]"
3. "[natural language query 3]"

#### ArXiv 分类
- cs.XX, cs.YY

#### Semantic Scholar
- 核心查询: "[keywords]"
- 引用追踪起点: [seed papers]

---

## Phase 3: 深度分析
**负责人**: [@论文分析师](mention://agent/177704340589000)
**状态**: 待启动
**输入**: literature_matrix.md
**输出**: paper_analyses/ + comparison_tables.md

### 质量门控
- [ ] Top 20 核心论文精读完成
- [ ] 每篇分析卡片完整
- [ ] 对比表覆盖所有主要方法

---

## Phase 4: 章节撰写
**负责人**: [@论文撰写员](mention://agent/177704343200000)
**状态**: 待启动
**输入**: paper_analyses/ + comparison_tables.md + 本文件大纲
**输出**: manuscript_draft.md

### 质量门控
- [ ] 所有章节完成
- [ ] 每个方法类别有对比表
- [ ] 引用覆盖核心论文
- [ ] 学术写作规范

---

## Phase 5: 审校打磨
**负责人**: [@质量编辑员](mention://agent/177704346680000)
**状态**: 待启动
**输入**: manuscript_draft.md
**输出**: review_report.md

### 质量门控
- [ ] 术语一致性通过
- [ ] 引用完整性通过
- [ ] 语言规范性通过

---

## Phase 6: 终审定稿
**负责人**: [@研究主管](mention://agent/177704332823000)
**状态**: 待启动
**输入**: review_report.md + manuscript_draft.md
**输出**: manuscript_final.md

---

## 论文大纲

### 标题: [Title]: A Comprehensive Survey

1. **Abstract** (150-250 words)
2. **Introduction**
   - 1.1 背景与动机
   - 1.2 现有综述的局限
   - 1.3 本文贡献
3. **Background**
   - 2.1 问题定义
   - 2.2 基础技术
   - 2.3 评估指标
4. **Taxonomy of Methods**
   - 3.1 [Category 1]
   - 3.2 [Category 2]
   - 3.3 [Category 3]
   - 3.4 [Category 4]
5. **Experimental Comparison**
   - 4.1 数据集与基准
   - 4.2 方法对比 (Table)
   - 4.3 分析与讨论
6. **Applications**
   - 5.1 [Application 1]
   - 5.2 [Application 2]
7. **Challenges and Future Directions**
   - 6.1 当前局限
   - 6.2 未来方向
8. **Conclusion**
9. **References**
```

---

## literature_matrix.md 模板

```markdown
---
stats:
  total_collected: 0
  after_screening: 0
  by_category: {}
  top20_ready: false
---

# Literature Matrix: [综述标题]

## 概览
- 检索日期: YYYY-MM-DD
- 总收集: N 篇
- 筛选后: N 篇
- 来源分布: Exa N% | ArXiv N% | S2 N% | PwC N%

## 分类汇总

| 分类 | 子分类 | 论文数 | 核心论文 |
|------|--------|--------|----------|
| [Cat1] | [Sub1] | N | [paper1], [paper2] |

## 详细文献列表

### [Category 1]

| # | 标题 | 作者 | 年份 | 来源 | 引用数 | ArXiv ID | 类别标签 |
|---|------|------|------|------|--------|----------|----------|
| 1 | | | | | | | |

## Top 20 核心论文

| 排名 | 标题 | 理由 |
|------|------|------|
| 1 | | |

## 覆盖度分析

| 分类 | 目标 | 实际 | 状态 |
|------|------|------|------|
| [Cat1] | ≥5 | N | ✅/⚠️ |

## 检索日志

| 工具 | 查询 | 结果数 | 筛选后 |
|------|------|--------|--------|
| | | | |
```

---

## 论文分析卡片模板

```markdown
# {Paper Title}

## 基本信息
- **作者**: 
- **年份**: 
- **来源**: 
- **ArXiv ID**: 
- **引用数**: 
- **代码**: 

## 一句话总结

## 问题定义
- **任务**: 
- **挑战**: 
- **动机**: 

## 方法
### 核心思路
### 关键组件
### 技术细节

## 实验
### 数据集
### 主要结果
### 消融实验要点

## 优势与局限
### 优势
### 局限

## 与综述的关联
- **所属分类**: 
- **在综述中的位置**: 
- **与其他论文的关系**: 
```

---

## 对比表模板

### 方法总览对比
```markdown
| 方法 | 年份 | 类别 | 核心创新 | 数据集 | 主要指标 | 代码 |
|------|------|------|----------|--------|----------|------|
```

### 性能对比（按数据集）
```markdown
| 方法 | [Metric1] | [Metric2] | 参数量 | 推理速度 |
|------|-----------|-----------|--------|----------|
```

### 方法特征对比
```markdown
| 方法 | 预训练 | 多模态 | 可解释性 | 计算成本 | 数据需求 |
|------|--------|--------|----------|----------|----------|
```

---

## review_report.md 模板

```markdown
# Review Report: [综述标题]

## 审校概览
- **审校日期**: YYYY-MM-DD
- **稿件版本**: v1.0
- **总体评价**: [优秀/良好/需修订/需大改]

## 统计摘要
| 检查项 | 状态 | 问题数 |
|--------|------|--------|
| 术语一致性 | | |
| 引用完整性 | | |
| 结构完整性 | | |
| 语言规范 | | |
| 数据准确性 | | |

## 详细问题列表
### 术语一致性
### 引用完整性
### 结构完整性
### 语言规范
### 数据准确性

## 修订建议摘要
### 必须修改 (高)
### 建议修改 (中)
### 可选改进 (低)
```
