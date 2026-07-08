# Academic Writing Style Guide

Based on Nature Reviews journal conventions and academic writing best practices.

---

## Core Principles

### 1. Prose-Based Writing (CRITICAL)

**Academic proposals must read as flowing, connected prose—not as bulleted lists or enumerated points.**

The hallmark of excellent academic writing is the ability to present complex ideas through coherent paragraphs with smooth transitions. Point-by-point enumeration (bullet points, numbered lists) should be used sparingly and only where truly necessary.

**When lists ARE appropriate:**
- Research questions/objectives (a focused set of 2-4 items)
- Timeline milestones (where tabular format genuinely aids clarity)
- Technical specifications requiring precise enumeration

**When to avoid lists:**
- Describing contributions (narrate them in context instead)
- Explaining methodology (use flowing prose with transitions)
- Presenting background information (integrate into paragraphs)
- Discussing implications (weave into coherent narrative)

**Transformation example:**

*Poor (point-by-point):*
> The main contributions include:
> - A novel segmentation algorithm
> - A multi-modal fusion framework
> - Clinical validation results

*Better (prose-based):*
> This research is expected to advance the field through several interconnected contributions. A new annotated corpus of multilingual policy debates will provide the first shared resource for studying argument structure across languages. Building on this resource, a discourse-analysis framework will make it possible to trace how rhetorical strategies migrate between political contexts. Finally, an empirical study linking these strategies to measured shifts in public opinion will establish whether, and under what conditions, framing choices affect persuasion.

### 2. Precision Over Impression
- Say exactly what you mean
- Avoid vague language
- Define terms clearly
- Quantify when possible

### 3. Evidence-Based Claims
- Support assertions with citations
- Distinguish fact from interpretation
- Acknowledge uncertainty appropriately

### 4. Logical Flow
- Clear paragraph structure
- Explicit transitions
- Coherent argumentation

### 5. Reader-Centered
- Anticipate reader questions
- Provide necessary context
- Guide through complexity

### 6. Avoid the LLM Tells (防 AI 味)

These openers and phrases are AI-detector signatures and mark a draft as machine-written. Strip them and write a specific opening grounded in the actual field instead.

| Avoid (AI tell) | Do instead |
|---|---|
| "Over the past decade, X has emerged as…" | Open with the specific problem, finding, or number that motivates the work |
| "In recent years, X has garnered significant attention" | State *what* changed and cite it: "Since the 2020 release of X, …" |
| "It is worth noting that…" / "Importantly, it should be noted…" | Just make the point; the emphasis word adds nothing |
| "plays a crucial/pivotal/vital role" | Say the specific mechanism or effect |
| "delves into" / "sheds light on" / "paves the way for" | "examines" / "shows" / "enables" |
| "a testament to" / "the ever-evolving landscape of" | Delete; state the fact |
| "This paper/proposal aims to explore the fascinating world of…" | "This research investigates [specific question]." |

Chinese equivalents to avoid: "近年来，随着……的飞速发展，……日益受到广泛关注"（套话开头）、"众所周知"、"不言而喻"、"具有重要的理论意义和现实意义"（空泛）。改为具体、可核验的陈述。

The goal is not a banned-word list to route around, but specificity: an opening a domain expert could not have written from the topic title alone signals real engagement.

---

## Hedging Language (学术谦逊表达)

### Why Hedging Matters
Academic writing requires appropriate epistemic humility. Hedging:
- Reflects genuine uncertainty in research
- Protects against overgeneralization
- Maintains scholarly credibility
- Invites scholarly dialogue

### Hedging Strategies

#### Modal Verbs
| Strength | Verbs | Example |
|----------|-------|---------|
| Strong | will, must | Rarely appropriate |
| Medium | would, should, can | "This approach can improve..." |
| Weak | may, might, could | "Results might indicate..." |

#### Hedging Verbs
```
Strong claim:  "X proves Y"
Hedged:        "X suggests/indicates/implies Y"
               "X appears to demonstrate Y"
               "X provides evidence for Y"
```

**Recommended hedging verbs:**
- suggest, indicate, imply
- appear, seem, tend
- propose, hypothesize, speculate

#### Hedging Adverbs
```
Strong:  "X is important"
Hedged:  "X is potentially/possibly/arguably important"
         "X may be particularly significant"
```

**Recommended adverbs:**
- possibly, potentially, perhaps
- apparently, seemingly
- generally, typically, often
- largely, mostly, primarily

#### Hedging Phrases
```
"It is possible that..."
"Evidence suggests that..."
"This finding indicates that..."
"The data appear to show..."
"One interpretation is that..."
"It could be argued that..."
```

### Hedging Examples by Section

**Introduction:**
```
Too strong:  "AI will transform healthcare."
Hedged:      "AI has the potential to transform healthcare."

Too strong:  "This gap must be addressed."
Hedged:      "This gap warrants further investigation."
```

**Methodology:**
```
Too strong:  "This method will produce accurate results."
Hedged:      "This method is expected to yield reliable results."

Too strong:  "We will prove the hypothesis."
Hedged:      "We aim to test the hypothesis."
```

**Results/Expected Outcomes:**
```
Too strong:  "The results will show..."
Hedged:      "The results are anticipated to reveal..."
             "We expect the findings to indicate..."

Too strong:  "This proves that..."
Hedged:      "This provides evidence that..."
             "This suggests that..."
```

**Significance:**
```
Too strong:  "This research will revolutionize..."
Hedged:      "This research has the potential to advance..."
             "This work may contribute to..."

Too strong:  "The findings will definitely impact..."
Hedged:      "The findings could have implications for..."
```

### Chinese Hedging (中文学术谦逊表达)

| 过强表达 | 适当表达 |
|----------|----------|
| 必将证明 | 有望表明、可能揭示 |
| 肯定会 | 预期将、有可能 |
| 彻底解决 | 有助于解决、为...提供新思路 |
| 完全正确 | 基本合理、大体上 |
| 已经证实 | 研究表明、证据显示 |

**常用谦逊表达:**
- 初步探讨、尝试分析
- 可能存在、似乎表明
- 在一定程度上、从某种意义上说
- 有待进一步研究、需要更多证据支持

---

## Sentence Structure

### Topic Sentence First
Every paragraph should begin with a clear topic sentence stating the main point.

```
Good:
"Recent advances in transformer architectures have significantly improved
natural language processing capabilities. [Evidence 1]. [Evidence 2].
[Synthesis]."

Avoid:
"[Evidence 1]. [Evidence 2]. Therefore, recent advances in transformer
architectures have significantly improved NLP capabilities."
```

### Sentence Templates by Function

#### Introducing Background/Context

Do **not** open with generic scene-setting ("Over the past decade, X has emerged…", "近年来，随着…日益受到关注") — those are AI tells (see Core Principle 6). Open with a specific, citable anchor: a concrete problem, a measured gap, a pivotal result. The templates below are *structures*, not fill-in-the-blank phrases; ground each in a real fact.

```
English (ground each in a specific, cited fact):
- "[Specific measurable problem or statistic] motivates growing interest in [X] (Author, Year)."
- "[Named advance/result] (Author, Year) made [previously infeasible task] tractable, raising the question of [gap]."
- "Although [established approach] achieves [specific result], it fails when [specific condition] (Author, Year)."

中文（每句须落到具体、可引用的事实）:
- "[具体问题或数据]促使[领域]研究者转向[X]（作者，年份）。"
- "[某项具体进展]（作者，年份）使[原本难以实现的任务]成为可能，但[具体空白]仍未解决。"
```

#### Identifying Problems/Gaps
```
English:
- "However, [X] remains poorly understood."
- "Despite these advances, significant challenges persist in [area]."
- "A critical gap exists in our understanding of [phenomenon]."
- "Current approaches fail to adequately address [issue]."
- "The relationship between [A] and [B] has not been systematically examined."

中文:
- "然而，[X]仍缺乏系统深入的研究。"
- "尽管如此，[领域]仍面临[问题]的挑战。"
- "目前研究对[问题]的关注相对不足。"
- "[A]与[B]之间的关系尚未得到充分探讨。"
```

#### Stating Objectives
```
English:
- "This research aims to address [X] by [approach]."
- "The primary objective of this study is to [verb] [what]."
- "This proposal seeks to investigate [question] through [method]."
- "Specifically, this study will [objective 1], [objective 2], and [objective 3]."

中文:
- "本研究旨在通过[方法]探讨[问题]。"
- "本文的主要目标是[动词][内容]。"
- "具体而言，本研究将：第一，...；第二，...；第三，..."
```

#### Justifying Methodology
```
English:
- "Building on previous work, this study proposes to [approach]."
- "This approach was selected because [justification]."
- "[Method] offers several advantages for studying [phenomenon]."
- "[Method] is particularly suited to [research question] because [reasons]."

中文:
- "在前人研究基础上，本研究拟采用[方法]。"
- "选择该方法的原因在于：[理由]。"
- "[方法]对于研究[现象]具有以下优势：..."
```

#### Describing Expected Contributions
```
English:
- "This work has the potential to advance [field/understanding]."
- "The findings may contribute to [theoretical/practical area]."
- "This research could provide insights into [phenomenon]."
- "The results are expected to have implications for [application]."

中文:
- "本研究有望推进[领域]的发展。"
- "研究结果可能为[理论/实践]提供新的视角。"
- "本研究预期将为[问题]的理解提供新的启示。"
```

### Sentence Variety

**Vary sentence length:**
- Mix short (10-15 words) and longer (20-30 words) sentences
- Use short sentences for key points
- Use longer sentences for complex relationships

**Vary sentence structure:**
- Simple: Subject-Verb-Object
- Compound: Clause + Conjunction + Clause
- Complex: Main clause + Subordinate clause
- Periodic: Build to main point at end

---

## Transitions and Connectors

### Addition
- Moreover, Furthermore, In addition, Additionally
- Also, Besides, Equally important
- 此外，另外，同时，与此同时

### Contrast
- However, Nevertheless, Nonetheless
- Conversely, On the other hand, In contrast
- Yet, Still, Although, While
- 然而，但是，尽管如此，相反

### Causation
- Therefore, Consequently, As a result, Thus
- Hence, Accordingly, For this reason
- 因此，由此可见，正因如此

### Emphasis (use sparingly)
- Notably, Particularly, In particular
- Indeed, In fact
- 尤其是，特别是
- Avoid "It is worth noting that" and "Importantly," as sentence openers — they are AI tells (Core Principle 6). If a point matters, its content should carry the emphasis; a flag word rarely helps.

### Sequence
- First, Second, Third, Finally
- Initially, Subsequently, Eventually
- Following this, Prior to, After
- 首先，其次，最后，随后

### Example
- For example, For instance, Specifically
- Such as, Including, Namely
- To illustrate, As demonstrated by
- 例如，具体而言，以...为例

### Summary
- In summary, To summarize, In conclusion
- Overall, In brief, To conclude
- 综上所述，总之，概言之

### Using Transitions Effectively

**Start of paragraph:**
```
"Moreover, recent studies have shown..."
"However, this approach has limitations..."
"In addition to these theoretical contributions..."
```

**Mid-paragraph:**
```
"This finding is particularly important because..."
"Consequently, researchers have begun to..."
```

**Between paragraphs:**
```
"Building on these observations, the next section..."
"Having established the theoretical framework, we now turn to..."
```

---

## Paragraph Structure

### The PEEL Structure
```
P - Point (topic sentence)
E - Evidence (supporting data/citations)
E - Explanation (analysis of evidence)
L - Link (connection to next idea or main argument)
```

### Example Paragraph

```
[Point] Machine learning approaches have shown considerable promise for
medical image analysis. [Evidence] Recent studies have demonstrated that
convolutional neural networks can achieve diagnostic accuracy comparable
to expert radiologists in detecting certain conditions (Smith et al., 2023;
Jones, 2024). [Evidence] Furthermore, these systems have been successfully
deployed in clinical settings, with one large-scale trial reporting a 15%
reduction in diagnostic errors (Chen et al., 2024). [Explanation] These
advances suggest that AI-assisted diagnosis could address the growing
shortage of medical imaging specialists while maintaining high standards
of care. [Link] However, significant challenges remain in ensuring the
generalizability of these systems across diverse patient populations.
```

### Paragraph Length
- Academic writing: 4-8 sentences per paragraph
- Aim for 100-200 words per paragraph
- One main idea per paragraph

### Paragraph Cohesion Techniques

**Repetition of key terms:**
```
"The study examined neural network architectures. These architectures..."
```

**Pronouns:**
```
"Researchers proposed a new framework. They demonstrated that it..."
```

**Synonyms and related terms:**
```
"...machine learning algorithms. These computational approaches..."
```

**Transitional phrases:**
```
"Building on this foundation... In light of these findings..."
```

---

## Citation Integration

### Citation Styles in Text

**Integral citations** (author as subject):
```
"Smith et al. (2023) demonstrated that..."
"According to Jones (2024), the relationship between..."
"As Chen and colleagues (2024) argue, ..."
```

**Non-integral citations** (parenthetical):
```
"Recent studies have shown significant improvements (Smith et al., 2023)."
"This relationship has been well-documented (Jones, 2024; Chen, 2024)."
```

### Reporting Verbs by Strength

| Strength | Verbs | Use When |
|----------|-------|----------|
| Strong | demonstrate, establish, prove | Well-supported findings |
| Medium | show, indicate, suggest, reveal | Typical research findings |
| Weak | propose, speculate, claim, argue | Contested or preliminary |
| Neutral | report, describe, state, note | Describing without evaluation |

### Citation Density Guidelines
- Introduction: Moderate (support key claims)
- Literature Review: High (comprehensive coverage)
- Methodology: Low-Moderate (cite established methods)
- Discussion: Moderate (compare with prior work)

### Synthesizing Multiple Sources

**Agreement:**
```
"Multiple studies have confirmed this relationship (Smith, 2022; Jones,
2023; Chen, 2024)."

"Researchers consistently report that... (Author1, Year; Author2, Year)."
```

**Disagreement:**
```
"While Smith (2022) argues that X, Jones (2023) presents evidence for Y."

"The evidence is mixed, with some studies supporting X (Author1, Year)
and others finding Y (Author2, Year)."
```

**Building on prior work:**
```
"Extending the work of Smith (2022), this study..."

"Building on Jones's (2023) framework, we propose..."
```

---

## Academic Vocabulary

### Words to Avoid

| Avoid | Use Instead |
|-------|-------------|
| a lot of | numerous, considerable, substantial |
| big | significant, substantial, major |
| get | obtain, acquire, achieve |
| thing | factor, element, aspect, component |
| good | effective, beneficial, advantageous |
| bad | detrimental, adverse, problematic |
| very | highly, particularly, considerably |
| really | significantly, substantially |
| kind of / sort of | somewhat, to some extent |
| basically | fundamentally, essentially |

### Precision in Word Choice

**Quantity:**
```
Vague:    "many studies"
Precise:  "numerous studies" / "several studies" / "a substantial body of research"
```

**Degree:**
```
Vague:    "very important"
Precise:  "crucial" / "essential" / "fundamental"
```

**Time:**
```
Vague:    "recently"
Precise:  "in the past five years" / "since 2020"
```

### Academic Verb Choices

| Purpose | Strong Verbs |
|---------|--------------|
| Showing | demonstrate, illustrate, reveal |
| Arguing | contend, assert, maintain |
| Analyzing | examine, investigate, assess |
| Comparing | contrast, differentiate, distinguish |
| Explaining | elucidate, clarify, account for |
| Increasing | enhance, augment, amplify |
| Decreasing | diminish, reduce, attenuate |

---

## Common Errors to Avoid

### Informal Language
```
Avoid:    "Scientists have been looking into this problem."
Better:   "Researchers have investigated this problem."

Avoid:    "This method is way better than the old one."
Better:   "This method demonstrates significant improvements over previous approaches."
```

### Absolute Claims
```
Avoid:    "This proves that X causes Y."
Better:   "This provides evidence that X may influence Y."

Avoid:    "It is obvious that..."
Better:   "Evidence suggests that..."
```

### Colloquialisms
```
Avoid:    "at the end of the day" / "in a nutshell"
Better:   "ultimately" / "in summary"

Avoid:    "a game-changer"
Better:   "a significant advancement"
```

### Redundancy
```
Avoid:    "past history" / "future plans" / "basic fundamentals"
Better:   "history" / "plans" / "fundamentals"

Avoid:    "in order to"
Better:   "to"
```

### Anthropomorphism (attributing human qualities to non-human things)
```
Avoid:    "The data wants to show..."
Better:   "The data indicate..."

Avoid:    "This study tries to..."
Better:   "This study aims to..."
```

### First Person Overuse
```
Avoid:    "I think this is important because..."
Better:   "This is significant because..."

Acceptable: "We propose..." / "Our study..."
```

---

## Writing Checklist

### Before Writing
- [ ] Research question clearly defined
- [ ] Key literature identified
- [ ] Outline prepared
- [ ] Target audience understood

### During Writing
- [ ] Topic sentence for each paragraph
- [ ] Evidence supports all claims
- [ ] Hedging used appropriately
- [ ] Transitions connect ideas
- [ ] Citations integrated smoothly

### After Writing
- [ ] Formal academic tone throughout
- [ ] No colloquialisms or informal language
- [ ] Appropriate hedging (not over-claiming)
- [ ] Clear logical flow
- [ ] Consistent citation format
- [ ] Abbreviations defined on first use
- [ ] No grammatical errors
- [ ] Word count within target range
- [ ] **Prose-based writing** (minimal bullet points)
- [ ] **Figure suggestions included** (3-5 for typical proposal)
- [ ] **No appendix sections**

---

## Figure Suggestions

### Purpose of Figures in Proposals

Figures significantly enhance research proposals by:
- Communicating complex ideas visually
- Breaking up dense text for improved readability
- Demonstrating the applicant's communication skills
- Providing concrete visualization of methodology

### Figure Suggestion Format

Include figure suggestions at appropriate locations using this format:

```markdown
> **[Figure 1 Suggestion]** *Title: Overview of the proposed research framework*
>
> Content: A flowchart illustrating the three-phase research design, showing how
> the primary data sources feed each processing stage and lead to the study's
> outputs/outcomes. Include distinct visual elements for each phase with
> connecting arrows indicating flow and dependencies.
>
> Recommended style: Clean vector graphics using a consistent color palette
> (e.g., blues for inputs, greens for processing, oranges for outputs).
> Use icons to distinguish the different data sources or components.
```

### Recommended Figures by Section

| Section | Figure Type | Example |
|---------|-------------|---------|
| **Introduction** | Conceptual diagram | Research scope and positioning within the field |
| **Literature Review** | Timeline or taxonomy | Evolution of methods; Classification of approaches |
| **Methodology** | Flowchart/Architecture | Research framework; Network architecture; Data pipeline |
| **Timeline** | Gantt chart | Research phases with milestones and dependencies |
| **Significance** | Impact diagram | Connections between contributions and beneficiaries |

### Figure Suggestion Principles

1. **Strategic placement**: 3-5 figures for a 3,000-word proposal
2. **No figure in Abstract**: Abstract should stand alone without visual elements
3. **Self-explanatory**: Each figure should convey key information clearly
4. **Consistent style**: Unified visual language throughout
5. **Professional tools**: Suggest appropriate tools (Illustrator, draw.io, BioRender)
6. **Accessibility**: Colorblind-friendly palettes, sufficient contrast

### Example Figure Suggestions

**For Methodology Section (example — a multimodal ML architecture):**
> **[Figure 2 Suggestion]** *Title: Model architecture for the proposed multimodal task*
>
> Content: A schematic showing the architecture with one encoder branch per input
> modality, a fusion module in the center, and the output head(s) for the target
> task. Annotate where the novel component sits relative to adopted baselines.
>
> Style: Technical diagram with layer/block representations, dimension annotations,
> and data-flow arrows. Use consistent shapes for similar operations.

*(Adapt the figure content to your own domain — a qualitative study might instead
show a coding/analysis pipeline; a humanities project, a source-corpus map.)*

**For Timeline Section:**
> **[Figure 3 Suggestion]** *Title: Research timeline and milestones*
>
> Content: Gantt chart showing four research phases across 48 months, with
> overlapping periods for parallel activities. Include diamond markers for
> key milestones (model completion, validation study, thesis submission).
>
> Style: Horizontal bar chart with color-coded phases, clear date markers,
> and milestone annotations.
