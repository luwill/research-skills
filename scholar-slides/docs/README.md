# scholar-slides - Research & Design

Deep research synthesizing 6 open-source AI slide/PPT projects, and a design proposal for an
academic-PPT Claude skill. Produced by a 9-agent research workflow (2026-06-29).

## Documents
1. [docs/01-landscape-research.md](docs/01-landscape-research.md) - cross-repo synthesis (comparison matrix, convergent patterns, divergences, best-of toolkit, collective blind spots for academic use) + per-repo deep-dive appendix.
2. [docs/02-academic-needs.md](docs/02-academic-needs.md) - first-principles requirements for an academic slide skill (6 deck types, paper->story content engineering, rendering-backend fidelity comparison, design conventions, integrity constraints, end-to-end pipeline).
3. [docs/03-design-proposal.md](docs/03-design-proposal.md) - the build spec for scholar-slides (positioning, skill description, file layout, pipeline, design system, integrity gates, phased plan, open decisions).

## Repos surveyed
- hugohe3/ppt-master, zarazhangrui/frontend-slides, alchaincyf/huashu-design
- op7418/guizang-ppt-skill, JimLiu/baoyu-skills (baoyu-slide-deck), luwill/research-skills (paper-slide-deck)

## One-line conclusion
All 6 optimize aesthetic ceiling and treat "academic" as a visual flavor. None handle the 5 things
academia actually demands: vector/text equations, bbox figure extraction with provenance,
BibTeX-grounded citations, data-bound charts, and a talk-time->slide-budget planner + integrity QA gate.
scholar-slides borrows their best planning/design machinery and builds those 5 missing primitives.
