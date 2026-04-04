# Awesome Multi-Agent For Science

A curated collection of papers, systems, and resources on multi-agent AI for scientific discovery and research automation.

This repo now has two complementary parts:

- an `awesome list` structure for organizing papers and resources
- a companion `trend analysis` on how large the multi-agent share is inside `LLM4Science` and `AI4Science`

## Trend Snapshot

The companion analysis lives in [analysis/trend_of_mas4sci](./analysis/trend_of_mas4sci).

Main result from the OpenAlex-backed analysis:

| Period | LLM4Science `multi-agent / all` | AI4Science `multi-agent / all` |
| --- | --- | --- |
| `2024` | `140 / 1864 = 7.51%` | `273 / 4804 = 5.68%` |
| `2025` | `415 / 2726 = 15.22%` | `630 / 6442 = 9.78%` |
| `2026 YTD` (`2026-01-01` to `2026-04-02`) | `245 / 1145 = 21.40%` | `322 / 2158 = 14.92%` |

Shortest reading:

- `multi-agent` is gaining share over time in both slices
- the rise is steeper inside `LLM4Science` than inside broader `AI4Science`
- the analysis is query-defined and cost-constrained, so these are conservative trend estimates rather than full-universe counts

The full methodology, exact keyword families, scripts, and lightweight result artifacts are in:

- [analysis/trend_of_mas4sci/README.md](./analysis/trend_of_mas4sci/README.md)

## Repository Structure

```text
analysis/
  trend_of_mas4sci/
    README.md
    requirements.txt
    scripts/
    results/

README.md
LICENSE
PAPER_ENTRY_TEMPLATE.md
```

## Curation Scope

This awesome list is for work related to:

- multi-agent LLM systems for scientific discovery
- role-specialized scientific agents
- autonomous or semi-autonomous research workflows
- multi-agent scientific planning, review, debate, verification, and experimentation
- infrastructure, evaluation, and failure modes for scientific MAS

Organization principle:

- the main sectioning is by `research task`
- scientific discipline should be recorded as a `tag`, not as a top-level sectioning rule

## Quality Bar

Every paper entry should clear these checks before it is added:

- verify the entry against a primary source such as the official arXiv page, publisher page, conference page, or official project page
- confirm the exact title, author list, year, and paper link
- confirm that every URL in the entry is real, publicly accessible, and points to the intended destination
- confirm that the paper is actually about `multi-agent for science`, not just `agents` in some unrelated sense
- confirm that the chosen `Task`, `Tags`, and `Agent pattern` are justified by the title, abstract, or paper body
- if the paper looks ambiguous between `multi-agent`, `other-agentic`, and non-agentic, do not add it until the ambiguity is resolved
- avoid duplicate entries for the same work across preprint and venue versions; keep one canonical entry and prefer the most stable paper link
- do not add from secondary lists alone without checking the paper itself

If a paper is interesting but not yet verified, keep it out of the main list until it passes the checks above.

URL rules:

- use stable paper URLs such as an official arXiv abstract page, DOI landing page, publisher page, or official project page
- do not use search-result URLs, temporary session URLs, or redirect chains that hide the real destination
- if a code link is included, it should resolve to the actual repository or project page, not to a profile or search page

## By Research Task

Verified recent papers:

- all paper links below point to official arXiv abstract pages
- all entries below were checked against title and abstract before inclusion
- current coverage is focused on `2024` to `2026 YTD`

### Hypothesis Generation And Literature Review

Papers on idea generation, literature synthesis, and question formulation by multiple agents.

- <sub><a href="https://arxiv.org/abs/2410.09403">Two Heads Are Better Than One: A Multi-Agent System Has the Potential to Improve Scientific Idea Generation</a></sub>
  - Tags: ![task:hypothesis_generation](https://img.shields.io/badge/task-hypothesis_generation-7C3AED?style=flat-square) ![task:literature_review](https://img.shields.io/badge/task-literature_review-7C3AED?style=flat-square) ![domain:interdisciplinary](https://img.shields.io/badge/domain-interdisciplinary-2563EB?style=flat-square)
  - Task: Hypothesis generation and literature review
  - Agent pattern: collaborative ideation
  - Why it matters: VirSci organizes multiple agents to generate, evaluate, and refine research ideas for autonomous scientific discovery.

- <sub><a href="https://arxiv.org/abs/2603.08127">EvoScientist: Towards Multi-Agent Evolving AI Scientists for End-to-End Scientific Discovery</a></sub>
  - Tags: ![task:hypothesis_generation](https://img.shields.io/badge/task-hypothesis_generation-7C3AED?style=flat-square) ![task:scientific_coding](https://img.shields.io/badge/task-scientific_coding-7C3AED?style=flat-square) ![domain:interdisciplinary](https://img.shields.io/badge/domain-interdisciplinary-2563EB?style=flat-square)
  - Task: Hypothesis generation and literature review
  - Agent pattern: researcher-engineer-manager
  - Why it matters: EvoScientist combines idea generation, experiment execution, and evolutionary memory in one multi-agent AI scientist workflow.

### Experimental Design And Planning

Papers on planning experiments, choosing protocols, and coordinating scientific workflows with multiple agents.

- <sub><a href="https://arxiv.org/abs/2602.21533">Reasoning-Driven Design of Single Atom Catalysts via a Multi-Agent Large Language Model Framework</a></sub>
  - Tags: ![task:experiment_design](https://img.shields.io/badge/task-experiment_design-7C3AED?style=flat-square) ![domain:chemistry](https://img.shields.io/badge/domain-chemistry-2563EB?style=flat-square) ![domain:materials_science](https://img.shields.io/badge/domain-materials_science-2563EB?style=flat-square)
  - Task: Experimental design and planning
  - Agent pattern: specialized catalyst-design agents
  - Why it matters: MAESTRO uses specialized LLM roles to iteratively reason about and optimize single-atom catalyst candidates.

- <sub><a href="https://arxiv.org/abs/2411.08063">MatPilot: an LLM-enabled AI Materials Scientist under the Framework of Human-Machine Collaboration</a></sub>
  - Tags: ![task:experiment_design](https://img.shields.io/badge/task-experiment_design-7C3AED?style=flat-square) ![domain:materials_science](https://img.shields.io/badge/domain-materials_science-2563EB?style=flat-square) ![domain:interdisciplinary](https://img.shields.io/badge/domain-interdisciplinary-2563EB?style=flat-square)
  - Task: Experimental design and planning
  - Agent pattern: human-machine multi-agent collaboration
  - Why it matters: MatPilot explicitly uses a multi-agent materials scientist setup to generate hypotheses and experimental schemes.

- <sub><a href="https://arxiv.org/abs/2602.14926">MAC-AMP: A Closed-Loop Multi-Agent Collaboration System for Multi-Objective Antimicrobial Peptide Design</a></sub>
  - Tags: ![task:experiment_design](https://img.shields.io/badge/task-experiment_design-7C3AED?style=flat-square) ![domain:biology](https://img.shields.io/badge/domain-biology-2563EB?style=flat-square) ![domain:drug_discovery](https://img.shields.io/badge/domain-drug_discovery-2563EB?style=flat-square)
  - Task: Experimental design and planning
  - Agent pattern: closed-loop simulated peer review
  - Why it matters: MAC-AMP uses a multi-agent design-and-review loop to balance activity, toxicity, and novelty in peptide design.

### Autonomous Experimentation And Execution

Papers on agents that interface with simulators, tools, robotics, or wet-lab pipelines.

- <sub><a href="https://arxiv.org/abs/2603.27738">TianJi:An autonomous AI meteorologist for discovering physical mechanisms in atmospheric science</a></sub>
  - Tags: ![task:autonomous_execution](https://img.shields.io/badge/task-autonomous_execution-7C3AED?style=flat-square) ![domain:earth_science](https://img.shields.io/badge/domain-earth_science-2563EB?style=flat-square)
  - Task: Autonomous experimentation and execution
  - Agent pattern: meta-planner plus worker cohort
  - Why it matters: TianJi decomposes atmospheric science research into planning plus coordinated execution and analysis by specialized agents.

- <sub><a href="https://arxiv.org/abs/2603.11515">Multi-Agent Collaboration for Automated Design Exploration on High Performance Computing Systems</a></sub>
  - Tags: ![task:autonomous_execution](https://img.shields.io/badge/task-autonomous_execution-7C3AED?style=flat-square) ![domain:interdisciplinary](https://img.shields.io/badge/domain-interdisciplinary-2563EB?style=flat-square)
  - Task: Autonomous experimentation and execution
  - Agent pattern: job-management, geometry, and inverse-design agents
  - Why it matters: MADA coordinates specialized agents around simulation-driven design exploration on HPC systems.

- <sub><a href="https://arxiv.org/abs/2511.22311">Swarms of Large Language Model Agents for Protein Sequence Design with Experimental Validation</a></sub>
  - Tags: ![task:autonomous_execution](https://img.shields.io/badge/task-autonomous_execution-7C3AED?style=flat-square) ![domain:biology](https://img.shields.io/badge/domain-biology-2563EB?style=flat-square) ![domain:drug_discovery](https://img.shields.io/badge/domain-drug_discovery-2563EB?style=flat-square)
  - Task: Autonomous experimentation and execution
  - Agent pattern: decentralized swarm of residue-level agents
  - Why it matters: This work frames protein design as a distributed multi-agent search process and backs it with experimental validation.

### Data Analysis And Interpretation

Papers on multi-agent analysis, critique, and interpretation of scientific data or simulation results.

- <sub><a href="https://arxiv.org/abs/2411.16416">A Multi-agent Framework for Materials Laws Discovery</a></sub>
  - Tags: ![task:data_analysis](https://img.shields.io/badge/task-data_analysis-7C3AED?style=flat-square) ![domain:materials_science](https://img.shields.io/badge/domain-materials_science-2563EB?style=flat-square)
  - Task: Data analysis and interpretation
  - Agent pattern: multi-agent symbolic regression
  - Why it matters: This framework uses multiple LLM agents to derive interpretable materials laws from scientific data.

- <sub><a href="https://arxiv.org/abs/2508.13251">"DIVE" into Hydrogen Storage Materials Discovery with AI Agents</a></sub>
  - Tags: ![task:data_analysis](https://img.shields.io/badge/task-data_analysis-7C3AED?style=flat-square) ![task:literature_review](https://img.shields.io/badge/task-literature_review-7C3AED?style=flat-square) ![domain:materials_science](https://img.shields.io/badge/domain-materials_science-2563EB?style=flat-square)
  - Task: Data analysis and interpretation
  - Agent pattern: multi-agent extraction and inverse design workflow
  - Why it matters: DIVE organizes agents to read figures and tables from the literature, build a structured database, and support rapid materials discovery.

- <sub><a href="https://arxiv.org/abs/2603.27584">Sci-Mind: Cognitively-Inspired Adversarial Debate for Autonomous Mathematical Modeling</a></sub>
  - Tags: ![task:data_analysis](https://img.shields.io/badge/task-data_analysis-7C3AED?style=flat-square) ![domain:mathematics](https://img.shields.io/badge/domain-mathematics-2563EB?style=flat-square) ![pattern:debate](https://img.shields.io/badge/pattern-debate-D97706?style=flat-square)
  - Task: Data analysis and interpretation
  - Agent pattern: theorist-critic debate with experiential memory
  - Why it matters: Sci-Mind treats mathematical modeling as a debate-and-verification process grounded by retrieval from prior scientific cases.

### Peer Review And Validation

Papers on reviewer-critic-verifier loops, debate setups, and scientific validation agents.

- <sub><a href="https://arxiv.org/abs/2604.00149">Towards Verifiable and Self-Correcting AI Physicists for Quantum Many-Body Simulations</a></sub>
  - Tags: ![task:peer_review](https://img.shields.io/badge/task-peer_review-7C3AED?style=flat-square) ![domain:physics](https://img.shields.io/badge/domain-physics-2563EB?style=flat-square) ![infra:evaluation](https://img.shields.io/badge/infra-evaluation-059669?style=flat-square)
  - Task: Peer review and validation
  - Agent pattern: programming-verifier plus scientific-verifier
  - Why it matters: PhysVEC builds verification and error-correction directly into a multi-agent physics research workflow.

### Scientific Writing And Communication

Papers on multi-agent drafting, revision, and structured scientific reporting.

- <sub><a href="https://arxiv.org/abs/2603.07444">HLER: Human-in-the-Loop Economic Research via Multi-Agent Pipelines for Empirical Discovery</a></sub>
  - Tags: ![task:scientific_writing](https://img.shields.io/badge/task-scientific_writing-7C3AED?style=flat-square) ![task:data_analysis](https://img.shields.io/badge/task-data_analysis-7C3AED?style=flat-square) ![domain:interdisciplinary](https://img.shields.io/badge/domain-interdisciplinary-2563EB?style=flat-square)
  - Task: Scientific writing and communication
  - Agent pattern: human-in-the-loop multi-agent pipeline
  - Why it matters: HLER coordinates agents for data auditing, hypothesis generation, econometric analysis, manuscript drafting, and review in one empirical research pipeline.

### Programming And Scientific Software Development

Papers on multi-agent coding systems for scientific software, analysis pipelines, and reproducible workflows.

- <sub><a href="https://arxiv.org/abs/2603.28986">Mimosa Framework: Toward Evolving Multi-Agent Systems for Scientific Research</a></sub>
  - Tags: ![task:scientific_coding](https://img.shields.io/badge/task-scientific_coding-7C3AED?style=flat-square) ![infra:framework](https://img.shields.io/badge/infra-framework-059669?style=flat-square) ![domain:interdisciplinary](https://img.shields.io/badge/domain-interdisciplinary-2563EB?style=flat-square)
  - Task: Programming and scientific software development
  - Agent pattern: meta-orchestrator plus code-generating agents
  - Why it matters: Mimosa automatically synthesizes and refines task-specific scientific multi-agent workflows with code-generating agents and tool use.

## Tagging Convention

Use tags to capture scientific discipline and other metadata without turning the repo into a second discipline taxonomy.

Badge color convention used in the list:

- task badges: purple
- discipline badges: blue
- infrastructure and evaluation badges: green
- agent-pattern badges: orange

Suggested discipline tags:

- `physics`
- `mathematics`
- `chemistry`
- `materials-science`
- `biology`
- `life-sciences`
- `drug-discovery`
- `earth-science`
- `environmental-science`
- `interdisciplinary`

Suggested task tags:

- `hypothesis-generation`
- `literature-review`
- `experiment-design`
- `autonomous-execution`
- `data-analysis`
- `peer-review`
- `scientific-writing`
- `scientific-coding`

Suggested agent-pattern tags:

- `multi-agent`
- `other-agentic`
- `planner-executor`
- `debate`
- `reviewer-critic`
- `generator-verifier`

Suggested infrastructure tags:

- `framework`
- `platform`
- `benchmark`
- `dataset`
- `evaluation`
- `coordination`
- `failure-modes`
- `safety`

## Frameworks And Infrastructure

### General MAS Frameworks

Frameworks for role specialization, message passing, planning, debate, orchestration, and shared memory.

- <sub><a href="https://arxiv.org/abs/2505.15047">PiFlow: Principle-aware Scientific Discovery with Multi-Agent Collaboration</a></sub>
  - Tags: ![infra:framework](https://img.shields.io/badge/infra-framework-059669?style=flat-square) ![pattern:multi_agent](https://img.shields.io/badge/pattern-multi_agent-D97706?style=flat-square) ![domain:interdisciplinary](https://img.shields.io/badge/domain-interdisciplinary-2563EB?style=flat-square)
  - Agent pattern: principle-aware multi-agent discovery
  - Why it matters: PiFlow frames automated scientific discovery as structured uncertainty reduction guided by principles across multiple scientific domains.

- <sub><a href="https://arxiv.org/abs/2507.07257">Open Source Planning & Control System with Language Agents for Autonomous Scientific Discovery</a></sub>
  - Tags: ![infra:framework](https://img.shields.io/badge/infra-framework-059669?style=flat-square) ![pattern:multi_agent](https://img.shields.io/badge/pattern-multi_agent-D97706?style=flat-square) ![task:scientific_coding](https://img.shields.io/badge/task-scientific_coding-7C3AED?style=flat-square) ![domain:interdisciplinary](https://img.shields.io/badge/domain-interdisciplinary-2563EB?style=flat-square)
  - Agent pattern: planning-and-control orchestration
  - Why it matters: cmbagent presents a large multi-agent research stack with specialized roles for literature, code, interpretation, and critique.

- <sub><a href="https://arxiv.org/abs/2603.03005">OrchMAS: Orchestrated Reasoning with Multi Collaborative Heterogeneous Scientific Expert Structured Agents</a></sub>
  - Tags: ![infra:framework](https://img.shields.io/badge/infra-framework-059669?style=flat-square) ![pattern:multi_agent](https://img.shields.io/badge/pattern-multi_agent-D97706?style=flat-square) ![domain:interdisciplinary](https://img.shields.io/badge/domain-interdisciplinary-2563EB?style=flat-square)
  - Agent pattern: orchestrator with heterogeneous expert agents
  - Why it matters: OrchMAS dynamically assembles domain-aware expert agents for long-horizon scientific reasoning tasks.

### Domain-Specific Platforms

Scientific platforms, toolchains, and environments built for a specific discipline.

- <sub><a href="https://arxiv.org/abs/2512.11935">AGAPI-Agents: An Open-Access Agentic AI Platform for Accelerated Materials Design on AtomGPT.org</a></sub>
  - Tags: ![infra:framework](https://img.shields.io/badge/infra-framework-059669?style=flat-square) ![infra:platform](https://img.shields.io/badge/infra-platform-059669?style=flat-square) ![domain:materials_science](https://img.shields.io/badge/domain-materials_science-2563EB?style=flat-square)
  - Agent pattern: planner-executor-summarizer
  - Why it matters: AGAPI unifies open materials APIs, simulations, and open-source LLMs through a multi-agent orchestration layer.

### Communication And Coordination

Work on agent protocols, structured interaction, blackboards, memory, and delegation mechanisms.

- <sub><a href="https://arxiv.org/abs/2603.03780">MACC: Multi-Agent Collaborative Competition for Scientific Exploration</a></sub>
  - Tags: ![infra:framework](https://img.shields.io/badge/infra-framework-059669?style=flat-square) ![infra:coordination](https://img.shields.io/badge/infra-coordination-059669?style=flat-square) ![domain:interdisciplinary](https://img.shields.io/badge/domain-interdisciplinary-2563EB?style=flat-square)
  - Agent pattern: collaborative competition
  - Why it matters: MACC studies how cooperation and competition can be combined to improve scientific exploration across multiple agents.

## Failure Modes And Open Challenges

### Technical Failure Modes

Examples: communication breakdown, coordination overhead, agent disagreement, and cascade failures.

### Scientific Reliability Issues

Examples: hallucination, unverifiable claims, invalid methodology, poor calibration, and reproducibility failures.

### Open Problems

Examples: long-horizon planning, cross-domain integration, uncertainty handling, efficient coordination, and safety.

## Contribution Guide

Suggested paper entry format:

```markdown
- <sub><a href="paper-link">Paper title</a></sub>
  - Tags: badges
  - Task:
  - Agent pattern:
  - Why it matters:
```

If you add papers, try to tag:

- research task
- scientific discipline
- whether the system is `multi-agent`, `other-agentic`, or mixed
- whether code or benchmark artifacts are available

Try to keep discipline as a tag inside each entry rather than creating new discipline sections.
All paper and code links should be live, direct, and publicly accessible when added.

For a stricter intake workflow, use:

- [PAPER_ENTRY_TEMPLATE.md](./PAPER_ENTRY_TEMPLATE.md)

## License

This repository is licensed under Apache 2.0. See [LICENSE](./LICENSE).
