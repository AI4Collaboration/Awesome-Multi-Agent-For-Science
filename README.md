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

First verified batch:

- all paper links below point to official arXiv abstract pages
- all entries below were checked against title and abstract before inclusion

### Hypothesis Generation And Literature Review

Papers on idea generation, literature synthesis, and question formulation by multiple agents.

- **Two Heads Are Better Than One: A Multi-Agent System Has the Potential to Improve Scientific Idea Generation**. Haoyang Su et al. 2024. [paper](https://arxiv.org/abs/2410.09403)
  - Task: Hypothesis generation and literature review
  - Tags: `hypothesis-generation`, `literature-review`, `interdisciplinary`
  - Agent pattern: collaborative ideation
  - Why it matters: VirSci organizes multiple agents to generate, evaluate, and refine research ideas for autonomous scientific discovery.

- **EvoScientist: Towards Multi-Agent Evolving AI Scientists for End-to-End Scientific Discovery**. Yougang Lyu et al. 2026. [paper](https://arxiv.org/abs/2603.08127)
  - Task: Hypothesis generation and literature review
  - Tags: `hypothesis-generation`, `interdisciplinary`, `scientific-coding`
  - Agent pattern: researcher-engineer-manager
  - Why it matters: EvoScientist combines idea generation, experiment execution, and evolutionary memory in one multi-agent AI scientist workflow.

### Experimental Design And Planning

Papers on planning experiments, choosing protocols, and coordinating scientific workflows with multiple agents.

- **Reasoning-Driven Design of Single Atom Catalysts via a Multi-Agent Large Language Model Framework**. Dong Hyeon Mok et al. 2026. [paper](https://arxiv.org/abs/2602.21533)
  - Task: Experimental design and planning
  - Tags: `experiment-design`, `chemistry`, `materials-science`
  - Agent pattern: specialized catalyst-design agents
  - Why it matters: MAESTRO uses specialized LLM roles to iteratively reason about and optimize single-atom catalyst candidates.

- **MatPilot: an LLM-enabled AI Materials Scientist under the Framework of Human-Machine Collaboration**. Ziqi Ni et al. 2024. [paper](https://arxiv.org/abs/2411.08063)
  - Task: Experimental design and planning
  - Tags: `experiment-design`, `materials-science`, `interdisciplinary`
  - Agent pattern: human-machine multi-agent collaboration
  - Why it matters: MatPilot explicitly uses a multi-agent materials scientist setup to generate hypotheses and experimental schemes.

### Autonomous Experimentation And Execution

Papers on agents that interface with simulators, tools, robotics, or wet-lab pipelines.

- **TianJi:An autonomous AI meteorologist for discovering physical mechanisms in atmospheric science**. Kaikai Zhang et al. 2026. [paper](https://arxiv.org/abs/2603.27738)
  - Task: Autonomous experimentation and execution
  - Tags: `autonomous-execution`, `earth-science`
  - Agent pattern: meta-planner plus worker cohort
  - Why it matters: TianJi decomposes atmospheric science research into planning plus coordinated execution and analysis by specialized agents.

- **Multi-Agent Collaboration for Automated Design Exploration on High Performance Computing Systems**. Harshitha Menon et al. 2026. [paper](https://arxiv.org/abs/2603.11515)
  - Task: Autonomous experimentation and execution
  - Tags: `autonomous-execution`, `interdisciplinary`
  - Agent pattern: job-management, geometry, and inverse-design agents
  - Why it matters: MADA coordinates specialized agents around simulation-driven design exploration on HPC systems.

### Data Analysis And Interpretation

Papers on multi-agent analysis, critique, and interpretation of scientific data or simulation results.

- **A Multi-agent Framework for Materials Laws Discovery**. Bo Hu et al. 2024. [paper](https://arxiv.org/abs/2411.16416)
  - Task: Data analysis and interpretation
  - Tags: `data-analysis`, `materials-science`
  - Agent pattern: multi-agent symbolic regression
  - Why it matters: This framework uses multiple LLM agents to derive interpretable materials laws from scientific data.

- **"DIVE" into Hydrogen Storage Materials Discovery with AI Agents**. Di Zhang et al. 2025. [paper](https://arxiv.org/abs/2508.13251)
  - Task: Data analysis and interpretation
  - Tags: `data-analysis`, `materials-science`, `literature-review`
  - Agent pattern: multi-agent extraction and inverse design workflow
  - Why it matters: DIVE organizes agents to read figures and tables from the literature, build a structured database, and support rapid materials discovery.

### Peer Review And Validation

Papers on reviewer-critic-verifier loops, debate setups, and scientific validation agents.

- **Towards Verifiable and Self-Correcting AI Physicists for Quantum Many-Body Simulations**. Ken Deng et al. 2026. [paper](https://arxiv.org/abs/2604.00149)
  - Task: Peer review and validation
  - Tags: `peer-review`, `physics`, `evaluation`
  - Agent pattern: programming-verifier plus scientific-verifier
  - Why it matters: PhysVEC builds verification and error-correction directly into a multi-agent physics research workflow.

### Scientific Writing And Communication

Papers on multi-agent drafting, revision, and structured scientific reporting.

### Programming And Scientific Software Development

Papers on multi-agent coding systems for scientific software, analysis pipelines, and reproducible workflows.

## Tagging Convention

Use tags to capture scientific discipline and other metadata without turning the repo into a second discipline taxonomy.

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
- `benchmark`
- `dataset`
- `evaluation`
- `failure-modes`
- `safety`

## Frameworks And Infrastructure

### General MAS Frameworks

Frameworks for role specialization, message passing, planning, debate, orchestration, and shared memory.

- **PiFlow: Principle-aware Scientific Discovery with Multi-Agent Collaboration**. Yingming Pu, Tao Lin, Hongyu Chen. 2025. [paper](https://arxiv.org/abs/2505.15047)
  - Tags: `framework`, `multi-agent`, `interdisciplinary`
  - Agent pattern: principle-aware multi-agent discovery
  - Why it matters: PiFlow frames automated scientific discovery as structured uncertainty reduction guided by principles across multiple scientific domains.

- **Open Source Planning & Control System with Language Agents for Autonomous Scientific Discovery**. Licong Xu et al. 2025. [paper](https://arxiv.org/abs/2507.07257)
  - Tags: `framework`, `multi-agent`, `scientific-coding`, `interdisciplinary`
  - Agent pattern: planning-and-control orchestration
  - Why it matters: cmbagent presents a large multi-agent research stack with specialized roles for literature, code, interpretation, and critique.

### Domain-Specific Platforms

Scientific platforms, toolchains, and environments built for a specific discipline.

### Communication And Coordination

Work on agent protocols, structured interaction, blackboards, memory, and delegation mechanisms.

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
- **Paper title**. Authors. Venue or year. [paper](link) Optional: [code](link)
  - Task:
  - Tags:
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
