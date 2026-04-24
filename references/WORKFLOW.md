# 6-Phase Multi-Agent Survey Workflow

## Overview

```
Phase 1: 项目初始化 (研究主管)
  → Phase 2: 文献收集 (文献侦查员)
    → Phase 3: 深度分析 (论文分析师)
      → Phase 4: 章节撰写 (论文撰写员)
        → Phase 5: 审校打磨 (质量编辑员)
          → Phase 6: 终审定稿 (研究主管)
```

---

## Phase 1: 项目初始化

**负责人**: 研究主管
**输入**: 用户选题需求
**输出**: 项目目录 + IMPLEMENTATION_PLAN.md + AGENTS.md

### 动作
1. 分析选题，确定综述范围、目标文献量、分类框架
2. 创建项目目录结构（见 TEMPLATES.md）
3. 创建 AGENTS.md（术语统一表 + 写作风格 + 引用格式 + 交接协议）
4. 创建 IMPLEMENTATION_PLAN.md（6 阶段计划 + 检索策略 + 论文大纲）
5. @mention 文献侦查员，启动 Phase 2

### 质量门控
- [ ] 选题范围明确
- [ ] 分类框架合理（MECE）
- [ ] 检索策略具体可执行
- [ ] 大纲结构符合顶会标准

---

## Phase 2: 文献收集

**负责人**: 文献侦查员
**输入**: IMPLEMENTATION_PLAN.md（检索策略 + 分类框架）
**输出**: literature_matrix.md

### 动作
1. 按检索策略从多源收集文献（Exa + ArXiv + Semantic Scholar + Papers With Code）
2. 去重与质量筛选
3. 按分类框架组织文献
4. 覆盖度分析，必要时补充检索
5. 生成 literature_matrix.md
6. @mention 论文分析师，启动 Phase 3

### 质量门控
- [ ] 总文献量达标（目标量的 80%+）
- [ ] 每个分类 ≥ 5 篇（新兴方向 ≥ 2 篇）
- [ ] 近 3 年文献占 50%+
- [ ] 多源覆盖
- [ ] Top 20 核心论文已标注

---

## Phase 3: 深度分析

**负责人**: 论文分析师
**输入**: literature_matrix.md + IMPLEMENTATION_PLAN.md
**输出**: paper_analyses/ + comparison_tables.md

### 动作
1. 精读 Top 20 核心论文，生成分析卡片
2. 快速扫描其余论文，提取关键信息
3. 构建跨论文对比表
4. 分析技术趋势和研究空白
5. @mention 论文撰写员，启动 Phase 4

### 质量门控
- [ ] Top 20 核心论文全部精读
- [ ] 每篇分析卡片完整（方法、实验、优势、局限）
- [ ] 对比表覆盖所有主要方法
- [ ] 趋势分析有数据支撑

---

## Phase 4: 章节撰写

**负责人**: 论文撰写员
**输入**: paper_analyses/ + comparison_tables.md + IMPLEMENTATION_PLAN.md（大纲）
**输出**: manuscript_draft.md

### 动作
1. 按大纲逐节撰写
2. 整合论文分析到叙事结构
3. 生成对比表和汇总表
4. 管理引用编号
5. @mention 质量编辑员，启动 Phase 5

### 质量门控
- [ ] 所有章节完成
- [ ] 每个方法类别有对比表
- [ ] 引用覆盖核心论文
- [ ] 学术写作规范
- [ ] 60-120 篇参考文献

---

## Phase 5: 审校打磨

**负责人**: 质量编辑员
**输入**: manuscript_draft.md + literature_matrix.md + AGENTS.md
**输出**: review_report.md + 修订后的 manuscript_draft.md

### 动作
1. 术语一致性检查
2. 引用完整性检查
3. 结构完整性检查
4. 语言规范检查
5. 数据准确性抽查
6. 生成审校报告
7. 自动修正明确的低风险问题
8. @mention 研究主管，启动 Phase 6

### 质量门控
- [ ] 术语一致性通过
- [ ] 引用完整性通过
- [ ] 无遗漏的大纲章节
- [ ] 语言规范性通过

---

## Phase 6: 终审定稿

**负责人**: 研究主管
**输入**: review_report.md + manuscript_draft.md
**输出**: manuscript_final.md

### 动作
1. 通读全文，评估整体连贯性
2. 核查审校报告中所有问题是否已修正
3. 验证创新点和贡献充分体现
4. 检查摘要、引言、结论一致性
5. 确认参考文献格式统一
6. 生成 manuscript_final.md
7. 通知用户终稿完成

### 质量门控
- [ ] 审校报告所有高严重度问题已修正
- [ ] 全文连贯、叙事清晰
- [ ] 贡献点充分体现
- [ ] 参考文献格式统一
- [ ] 终稿可直接提交

---

## 异常处理

### 阶段不合格
- 负责 Agent @mention 研究主管说明问题
- 研究主管决定：打回修订 / 调整要求 / 跳过

### Agent 无响应
- 研究主管在 IMPLEMENTATION_PLAN.md 中重新 @mention
- 或手动执行该阶段

### 需求变更
- 用户随时可通知研究主管
- 研究主管更新 IMPLEMENTATION_PLAN.md
- 通知当前阶段 Agent 注意变更
