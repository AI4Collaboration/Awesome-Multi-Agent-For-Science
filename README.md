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

## By Research Task

### Hypothesis Generation And Literature Review

Papers on idea generation, literature synthesis, and question formulation by multiple agents.

### Experimental Design And Planning

Papers on planning experiments, choosing protocols, and coordinating scientific workflows with multiple agents.

### Autonomous Experimentation And Execution

Papers on agents that interface with simulators, tools, robotics, or wet-lab pipelines.

### Data Analysis And Interpretation

Papers on multi-agent analysis, critique, and interpretation of scientific data or simulation results.

### Peer Review And Validation

Papers on reviewer-critic-verifier loops, debate setups, and scientific validation agents.

### Scientific Writing And Communication

Papers on multi-agent drafting, revision, and structured scientific reporting.

### Programming And Scientific Software Development

Papers on multi-agent coding systems for scientific software, analysis pipelines, and reproducible workflows.

## By Scientific Discipline

### Physics

Includes theoretical, computational, experimental, quantum, particle, and astrophysics settings.

### Mathematics

Includes theorem proving, formal reasoning, numerical analysis, and scientific mathematical modeling.

### Chemistry And Materials Science

Includes molecular design, reaction planning, catalysts, solvents, materials discovery, and computational chemistry.

### Biology And Life Sciences

Includes drug discovery, protein engineering, genomics, systems biology, synthetic biology, and neuroscience.

### Earth And Environmental Sciences

Includes climate, atmospheric science, geoscience, oceanography, ecology, and environmental modeling.

### Cross-Domain And Interdisciplinary Systems

Includes general AI scientists, cross-domain discovery systems, and multi-domain scientific platforms.

## Frameworks And Infrastructure

### General MAS Frameworks

Frameworks for role specialization, message passing, planning, debate, orchestration, and shared memory.

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
- **Paper title**. Authors. Venue or year. [paper](link) [code](link)
  - Task:
  - Domain:
  - Agent pattern:
  - Why it matters:
```

If you add papers, try to tag:

- research task
- scientific domain
- whether the system is `multi-agent`, `other-agentic`, or mixed
- whether code or benchmark artifacts are available

## License

This repository is licensed under Apache 2.0. See [LICENSE](./LICENSE).
