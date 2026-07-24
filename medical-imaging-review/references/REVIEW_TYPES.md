# Review Type Routing

Choose and freeze the review route before collecting literature or drafting conclusions. The manuscript label must match the methods actually completed.

## Contents

- Supported routes
- Common project contract
- Narrative review or method survey
- Scoping review
- Systematic review with qualitative synthesis
- Human governance
- Out-of-scope routes
- Route changes and status labels

## Supported routes

| User intent | Route token | Core output |
|---|---|---|
| Interpret a field or explain controversies | narrative | Transparent, justified corpus and evidence-linked synthesis |
| Compare method families | method-survey | Evidence-linked technical synthesis |
| Map available evidence, concepts, methods, or gaps | scoping | Protocol-driven evidence map and descriptive charting |
| Answer a focused question without statistical pooling | systematic | Qualitative included-study synthesis, risk-of-bias assessment, and certainty assessment when appropriate |

This skill supports only narrative, method-survey, scoping, and systematic. The systematic token always means a systematic review with qualitative synthesis. This skill does not perform meta-analysis or umbrella review methods.

## Common project contract

Create each persistent project with scripts/init_review_project.py. Its collision-safe path contract is:

    review_project/<topic-slug>-<YYYYMMDD-HHMMSS>-<8hex>/

Treat the generated child as <project_dir>. Never flatten artifacts into review_project/ and never reuse or overwrite an existing child.

All routes use the generated review_config.yaml, REVIEW_CONTEXT.md, IMPLEMENTATION_PLAN.md, PARADIGM.md, manuscript.md, references.bib, claim_ledger.csv, AI_USE_DISCLOSURE.md, protocol_deviations.md, EXPERT_SIGNOFF.md, and subdirectories relative to <project_dir>.

Use stable citekeys in references.bib and manuscript.md. Record each consequential claim and its source location in claim_ledger.csv. Do not draft with mutable numeric citations.

review_config.yaml must record the frozen route token, scope, evidence cutoff, target journal or audience, selected standards, human roles, AI assistance, and project status. REVIEW_CONTEXT.md holds the portable terminology, decisions, and synthesis brief; it is not a tool-specific instruction file.

## Narrative review or method survey

Use this route to interpret a field, compare approaches, explain disagreements, or develop a conceptual taxonomy. Do not imply exhaustive or reproducible coverage unless the methods actually provide it.

Required method record:

- Explicit scope, audience, evidence cutoff, and selection rationale.
- Search or discovery sources and enough query detail to explain how the corpus was assembled.
- Stable citekeys and claim-level source verification.
- Inclusion of contradictory, negative, and implementation evidence when relevant.
- Clear separation between source-supported findings and author interpretation.

Possible structure:

    # Title
    ## Abstract
    ## Scope and approach
    ## Clinical and technical context
    ## Evidence synthesis or method taxonomy
    ## Translation, limitations, and open questions
    ## Conclusions
    ## References

A three-axis architecture, inductive-prior, and data-regime taxonomy is one optional pattern for method surveys. Use it only when it fits the literature. Journal requirements, review methods, user requirements, and verified exemplars take precedence over this default.

Formal duplicate screening, duplicate extraction, risk-of-bias assessment, and certainty grading are not automatically required for a narrative review. Do not claim they occurred unless they are documented.

## Scoping review

Use this route to map the extent, characteristics, concepts, methods, or gaps in a body of evidence. Do not use it to estimate pooled effects or make certainty-graded practice recommendations.

Use the route-specific artifacts created by the initializer:

    <project_dir>/protocol/PROTOCOL.md
    <project_dir>/search/search_plan.md
    <project_dir>/search/search_log.csv
    <project_dir>/search/deduplication_log.csv
    <project_dir>/screening/screening_decisions.csv
    <project_dir>/screening/full_text_exclusions.csv
    <project_dir>/adjudication/conflict_log.csv
    <project_dir>/extraction/charting_table.csv
    <project_dir>/reporting/flow_counts.json
    <project_dir>/AI_USE_DISCLOSURE.md

Minimum methods:

- Frame the question with PCC: Population, Concept, and Context.
- Freeze eligibility criteria, information sources, search plan, and charting fields in protocol/PROTOCOL.md.
- Record complete database-specific search strings, platforms, dates, filters, and exports through search/search_log.csv and strategy files.
- Document deduplication, title/abstract screening, full-text screening, conflicts, exclusions, and flow counts.
- Pilot the charting form and record later amendments.
- Conduct descriptive mapping aligned to the question; avoid effect pooling or interpretive synthesis that changes the route.
- Follow JBI scoping-review conduct guidance where applicable and report with PRISMA-ScR plus PRISMA-S.

Human gates:

- Use two named human reviewers for title/abstract and full-text screening, with a named human adjudicator.
- Use two named humans for charting, either duplicate charting or one charter plus independent human verification, as pre-specified.
- Risk-of-bias appraisal is not automatic for a scoping review. If the protocol includes it, use the matched tool and human appraisal gate. If it is omitted, state that explicitly and constrain conclusions accordingly.

Possible manuscript structure:

    ## Introduction
    ## Methods
    ### Protocol and eligibility
    ### Information sources and search
    ### Selection process
    ### Data charting
    ### Analysis and presentation
    ## Results
    ### Selection flow
    ### Source characteristics
    ### Evidence map
    ## Discussion
    ## Limitations
    ## Conclusions

## Systematic review with qualitative synthesis

Use this route for a focused, reproducible question when the included evidence will be synthesized without statistical pooling. This is not permission to simulate a meta-analysis with averages, vote counting, or informal pooled estimates.

Use the route-specific artifacts created by the initializer:

    <project_dir>/protocol/PROTOCOL.md
    <project_dir>/search/search_log.csv
    <project_dir>/screening/screening_decisions.csv
    <project_dir>/screening/full_text_exclusions.csv
    <project_dir>/adjudication/conflict_log.csv
    <project_dir>/extraction/study_characteristics.csv
    <project_dir>/extraction/critical_data.csv
    <project_dir>/extraction/cohort_linkage.csv
    <project_dir>/risk_of_bias/assessments.csv
    <project_dir>/certainty/assessments.csv
    <project_dir>/reporting/flow_counts.json
    <project_dir>/human_review_gate.json
    <project_dir>/AI_USE_DISCLOSURE.md

Minimum methods:

- Frame the question with the framework matched to the review, such as PICOS or PIRD.
- Freeze eligibility, outcomes, grouping rules, search, screening, extraction, risk-of-bias, synthesis, and certainty methods in protocol/PROTOCOL.md.
- Register the protocol when an appropriate registry accepts the review; otherwise preserve a public or timestamped protocol and explain the choice.
- Search the databases required by the question and record exact strings, platforms, dates, filters, and exports.
- Document deduplication, duplicate screening, full-text exclusions, extraction, risk-of-bias judgments, protocol deviations, and flow counts.
- Pre-specify a transparent qualitative or structured narrative synthesis. Use SWiM reporting guidance when its intervention-without-meta-analysis scope fits.
- Apply the review-level reporting guidance, primary-study reporting frameworks, risk-of-bias tools, and certainty framework as distinct layers.
- Do not pool metrics across incompatible datasets, thresholds, reference standards, validation settings, or study designs.

Human gates:

- Two named humans independently complete title/abstract and full-text screening; a named human adjudicator resolves conflicts.
- Two named humans complete extraction, either independently or as extractor plus independent verifier, according to the frozen protocol.
- Risk-of-bias judgments require independent human assessment and documented consensus or adjudication.
- Certainty judgments, when made, require human approval and an auditable rationale.

LLM agents can prepare suggestions and consistency checks but cannot satisfy any of these human gates.

Possible manuscript structure:

    ## Introduction
    ## Methods
    ### Protocol and registration
    ### Eligibility criteria
    ### Information sources and search
    ### Selection process
    ### Data collection and data items
    ### Risk-of-bias assessment
    ### Qualitative synthesis and certainty methods
    ## Results
    ### Study selection
    ### Study characteristics
    ### Risk of bias
    ### Individual-study findings
    ### Qualitative synthesis
    ### Certainty of evidence
    ## Discussion
    ## Limitations
    ## Conclusions

## Human governance

Record the names or approved role identifiers of human screeners, extractors, adjudicator, risk-of-bias reviewers, and certainty reviewers in <project_dir>/review_config.yaml. Preserve formal-route screening in <project_dir>/screening/screening_decisions.csv. Record AI tools, tasks, dates, human oversight, validation, limitations, and corrections in <project_dir>/AI_USE_DISCLOSURE.md.

Never describe LLM agents as independent reviewers. If the required humans or records are unavailable, label outputs as provisional suggestions and stop before claiming the corresponding stage is complete.

## Out-of-scope routes

| Request | Action |
|---|---|
| Pairwise, network, Bayesian, diagnostic-accuracy, prevalence, prognostic, or individual-participant-data meta-analysis | Stop and hand off to a specialized meta-analysis workflow |
| Umbrella review or overview of reviews | Stop and hand off to a specialized review-of-reviews workflow |

For meta-analysis, do not generate pooled estimates, heterogeneity statistics, sensitivity analyses, forest plots, funnel plots, or certainty conclusions inside this skill. For umbrella reviews, do not perform review overlap calculations or review-level appraisal inside this skill.

The handoff may include the frozen question, protocol state, source registry, screening state, extraction schema, unresolved decisions, and the reason specialized methods are required. Do not present the handoff as completed analysis.

## Route changes and status labels

If a narrative project starts making exhaustive-coverage claims after collection begins, remove the claim or freeze that project and initialize a new scoping/systematic project; do not retrofit the label. If a scoping review begins answering an effectiveness question, use the same new-project rule. If a qualitative systematic review requires pooling, freeze its artifacts and hand off to the specialist workflow.

Report status precisely, for example:

- route selected; protocol not frozen
- search complete; human screening pending
- screening complete; extraction verification pending
- extraction complete; risk-of-bias consensus pending
- verified evidence map available
- qualitative synthesis available; certainty assessment pending
