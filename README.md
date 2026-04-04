# Awesome Multi-Agent For Science

A curated list of papers, systems, and resources on multi-agent AI for scientific discovery and research automation.

## Table of Contents

- [Trend Snapshot](#trend-snapshot)
- [Scope](#scope)
- [Quality Bar](#quality-bar)
- [By Research Phase](#by-research-phase)
  - [Literature Review](#literature-review)
  - [Hypothesis Formulation](#hypothesis-formulation)
  - [Experimentation (Dry Lab)](#experimentation-dry-lab)
  - [Experimentation (Wet-Lab)](#experimentation-wet-lab)
  - [Review](#review)
- [Frameworks And Infrastructure](#frameworks-and-infrastructure)
  - [General MAS Frameworks](#general-mas-frameworks)
  - [Domain-Specific Platforms](#domain-specific-platforms)
  - [Communication And Coordination](#communication-and-coordination)
- [Failure Modes And Open Challenges](#failure-modes-and-open-challenges)
- [License](#license)

## Trend Snapshot

OpenAlex-backed trend estimates from `2024` to `2026-04-02`.

| Period | LLM4Science `multi-agent / all` | AI4Science `multi-agent / all` |
| --- | --- | --- |
| `2024` | `140 / 1864 = 7.51%` | `273 / 4804 = 5.68%` |
| `2025` | `415 / 2726 = 15.22%` | `630 / 6442 = 9.78%` |
| `2026 YTD` (`2026-01-01` to `2026-04-02`) | `245 / 1145 = 21.40%` | `322 / 2158 = 14.92%` |

Methods, keyword families, scripts, and result files are in [analysis/trend_of_mas4sci](./analysis/trend_of_mas4sci).

## Scope

This list focuses on:

- multi-agent LLM systems for scientific discovery
- role-specialized scientific agents and research workflows
- planning, execution, and review in science
- infrastructure, evaluation, and failure modes for scientific MAS

Task tags in the list are:

- `phase: Literature Review`
- `phase: Hypothesis Formulation`
- `phase: Experimentation (Dry Lab)`
- `phase: Experimentation (Wet-Lab)`
- `phase: Review`

Scientific discipline is recorded as a `domain` tag, not a top-level section.

## Quality Bar

Every paper entry should:

- be checked against a primary source
- use a real, public, direct URL
- include at least one `phase` tag and exactly one `domain` tag
- match the stated `Agent pattern`
- clearly be about `multi-agent for science`
- avoid duplicate entries across preprint and venue versions
- include both experimentation tags if a paper genuinely covers both dry-lab and wet-lab execution
- prefer the most specific domain tag over `Interdisciplinary`

## By Research Phase

Verified recent papers, mainly from `2024` to `2026 YTD`.

### Literature Review

- **[Two Heads Are Better Than One: A Multi-Agent System Has the Potential to Improve Scientific Idea Generation](https://arxiv.org/abs/2410.09403)**
  ![phase: Literature Review](https://img.shields.io/badge/phase-Literature%20Review-5C4B8A?style=flat-square) ![phase: Hypothesis Formulation](https://img.shields.io/badge/phase-Hypothesis%20Formulation-5C4B8A?style=flat-square) ![domain: Interdisciplinary](https://img.shields.io/badge/domain-Interdisciplinary-2D6F86?style=flat-square)
  - Agent pattern: collaborative ideation
  - Why it matters: VirSci organizes multiple agents to generate, evaluate, and refine research ideas for autonomous scientific discovery.

- **["DIVE" into Hydrogen Storage Materials Discovery with AI Agents](https://arxiv.org/abs/2508.13251)**
  ![phase: Literature Review](https://img.shields.io/badge/phase-Literature%20Review-5C4B8A?style=flat-square) ![phase: Hypothesis Formulation](https://img.shields.io/badge/phase-Hypothesis%20Formulation-5C4B8A?style=flat-square) ![domain: Materials Science](https://img.shields.io/badge/domain-Materials%20Science-2D6F86?style=flat-square)
  - Agent pattern: multi-agent extraction and inverse design workflow
  - Why it matters: DIVE organizes agents to read figures and tables from the literature, build a structured database, and support rapid materials discovery.

### Hypothesis Formulation

- **[EvoScientist: Towards Multi-Agent Evolving AI Scientists for End-to-End Scientific Discovery](https://arxiv.org/abs/2603.08127)**
  ![phase: Hypothesis Formulation](https://img.shields.io/badge/phase-Hypothesis%20Formulation-5C4B8A?style=flat-square) ![phase: Experimentation (Dry Lab)](https://img.shields.io/badge/phase-Experimentation%20(Dry%20Lab)-5C4B8A?style=flat-square) ![domain: Interdisciplinary](https://img.shields.io/badge/domain-Interdisciplinary-2D6F86?style=flat-square)
  - Agent pattern: researcher-engineer-manager
  - Why it matters: EvoScientist combines idea generation, experiment execution, and evolutionary memory in one multi-agent AI scientist workflow.

- **[Reasoning-Driven Design of Single Atom Catalysts via a Multi-Agent Large Language Model Framework](https://arxiv.org/abs/2602.21533)**
  ![phase: Hypothesis Formulation](https://img.shields.io/badge/phase-Hypothesis%20Formulation-5C4B8A?style=flat-square) ![domain: Chemistry](https://img.shields.io/badge/domain-Chemistry-2D6F86?style=flat-square)
  - Agent pattern: specialized catalyst-design agents
  - Why it matters: MAESTRO uses specialized LLM roles to iteratively reason about and optimize single-atom catalyst candidates.

- **[MatPilot: an LLM-enabled AI Materials Scientist under the Framework of Human-Machine Collaboration](https://arxiv.org/abs/2411.08063)**
  ![phase: Hypothesis Formulation](https://img.shields.io/badge/phase-Hypothesis%20Formulation-5C4B8A?style=flat-square) ![domain: Materials Science](https://img.shields.io/badge/domain-Materials%20Science-2D6F86?style=flat-square)
  - Agent pattern: human-machine multi-agent collaboration
  - Why it matters: MatPilot uses a multi-agent materials scientist setup to generate hypotheses and experimental schemes.

- **[MAC-AMP: A Closed-Loop Multi-Agent Collaboration System for Multi-Objective Antimicrobial Peptide Design](https://arxiv.org/abs/2602.14926)**
  ![phase: Hypothesis Formulation](https://img.shields.io/badge/phase-Hypothesis%20Formulation-5C4B8A?style=flat-square) ![phase: Review](https://img.shields.io/badge/phase-Review-5C4B8A?style=flat-square) ![domain: Biomed](https://img.shields.io/badge/domain-Biomed-2D6F86?style=flat-square)
  - Agent pattern: closed-loop simulated paper review
  - Why it matters: MAC-AMP uses a multi-agent design-and-review loop to balance activity, toxicity, and novelty in peptide design.

- **[A Multi-agent Framework for Materials Laws Discovery](https://arxiv.org/abs/2411.16416)**
  ![phase: Hypothesis Formulation](https://img.shields.io/badge/phase-Hypothesis%20Formulation-5C4B8A?style=flat-square) ![domain: Materials Science](https://img.shields.io/badge/domain-Materials%20Science-2D6F86?style=flat-square)
  - Agent pattern: multi-agent symbolic regression
  - Why it matters: This framework uses multiple LLM agents to derive interpretable materials laws from scientific data.

- **[Sci-Mind: Cognitively-Inspired Adversarial Debate for Autonomous Mathematical Modeling](https://arxiv.org/abs/2603.27584)**
  ![phase: Hypothesis Formulation](https://img.shields.io/badge/phase-Hypothesis%20Formulation-5C4B8A?style=flat-square) ![domain: Mathematics](https://img.shields.io/badge/domain-Mathematics-2D6F86?style=flat-square)
  - Agent pattern: theorist-critic debate with experiential memory
  - Why it matters: Sci-Mind treats mathematical modeling as a debate-and-verification process grounded by retrieval from prior scientific cases.

### Experimentation (Dry Lab)

- **[TianJi:An autonomous AI meteorologist for discovering physical mechanisms in atmospheric science](https://arxiv.org/abs/2603.27738)**
  ![phase: Experimentation (Dry Lab)](https://img.shields.io/badge/phase-Experimentation%20(Dry%20Lab)-5C4B8A?style=flat-square) ![domain: Earth Science](https://img.shields.io/badge/domain-Earth%20Science-2D6F86?style=flat-square)
  - Agent pattern: meta-planner plus worker cohort
  - Why it matters: TianJi decomposes atmospheric science research into planning plus coordinated execution and analysis by specialized agents.

- **[Multi-Agent Collaboration for Automated Design Exploration on High Performance Computing Systems](https://arxiv.org/abs/2603.11515)**
  ![phase: Experimentation (Dry Lab)](https://img.shields.io/badge/phase-Experimentation%20(Dry%20Lab)-5C4B8A?style=flat-square) ![domain: Interdisciplinary](https://img.shields.io/badge/domain-Interdisciplinary-2D6F86?style=flat-square)
  - Agent pattern: job-management, geometry, and inverse-design agents
  - Why it matters: MADA coordinates specialized agents around simulation-driven design exploration on HPC systems.

- **[Mimosa Framework: Toward Evolving Multi-Agent Systems for Scientific Research](https://arxiv.org/abs/2603.28986)**
  ![phase: Experimentation (Dry Lab)](https://img.shields.io/badge/phase-Experimentation%20(Dry%20Lab)-5C4B8A?style=flat-square) ![domain: Interdisciplinary](https://img.shields.io/badge/domain-Interdisciplinary-2D6F86?style=flat-square)
  - Agent pattern: meta-orchestrator plus code-generating agents
  - Why it matters: Mimosa automatically synthesizes and refines task-specific scientific multi-agent workflows with code-generating agents and tool use.

### Experimentation (Wet-Lab)

- **[Validation of an LLM-based Multi-Agent Framework for Protein Engineering in Dry Lab and Wet Lab](https://arxiv.org/abs/2411.06029)**
  ![phase: Experimentation (Dry Lab)](https://img.shields.io/badge/phase-Experimentation%20(Dry%20Lab)-5C4B8A?style=flat-square) ![phase: Experimentation (Wet-Lab)](https://img.shields.io/badge/phase-Experimentation%20(Wet--Lab)-5C4B8A?style=flat-square) ![domain: Biomed](https://img.shields.io/badge/domain-Biomed-2D6F86?style=flat-square)
  - Agent pattern: conversational multi-agent protein engineering workflow
  - Why it matters: TourSynbio-Agent is validated across both computational and wet-lab protein engineering case studies, making it a strong bridge between dry-lab automation and experimental execution.

- **[BioMARS: A Multi-Agent Robotic System for Autonomous Biological Experiments](https://arxiv.org/abs/2507.01485)**
  ![phase: Experimentation (Wet-Lab)](https://img.shields.io/badge/phase-Experimentation%20(Wet--Lab)-5C4B8A?style=flat-square) ![domain: Biomed](https://img.shields.io/badge/domain-Biomed-2D6F86?style=flat-square)
  - Agent pattern: biologist-technician-inspector hierarchy
  - Why it matters: BioMARS integrates LLMs, VLMs, and modular robotics to design, plan, and execute biological experiments with explicit agent specialization.

- **[AutoLabs: Cognitive Multi-Agent Systems with Self-Correction for Autonomous Chemical Experimentation](https://arxiv.org/abs/2509.25651)**
  ![phase: Experimentation (Wet-Lab)](https://img.shields.io/badge/phase-Experimentation%20(Wet--Lab)-5C4B8A?style=flat-square) ![domain: Chemistry](https://img.shields.io/badge/domain-Chemistry-2D6F86?style=flat-square)
  - Agent pattern: self-correcting chemical lab agents
  - Why it matters: AutoLabs turns natural-language goals into hardware-ready liquid-handler protocols and studies why multi-agent chemistry execution works better than simpler baselines.

- **[Swarms of Large Language Model Agents for Protein Sequence Design with Experimental Validation](https://arxiv.org/abs/2511.22311)**
  ![phase: Experimentation (Dry Lab)](https://img.shields.io/badge/phase-Experimentation%20(Dry%20Lab)-5C4B8A?style=flat-square) ![phase: Experimentation (Wet-Lab)](https://img.shields.io/badge/phase-Experimentation%20(Wet--Lab)-5C4B8A?style=flat-square) ![domain: Biomed](https://img.shields.io/badge/domain-Biomed-2D6F86?style=flat-square)
  - Agent pattern: decentralized swarm of residue-level agents
  - Why it matters: This work frames protein design as a distributed multi-agent search process and backs it with experimental validation.

### Review

- **[Towards Verifiable and Self-Correcting AI Physicists for Quantum Many-Body Simulations](https://arxiv.org/abs/2604.00149)**
  ![phase: Review](https://img.shields.io/badge/phase-Review-5C4B8A?style=flat-square) ![domain: Physics](https://img.shields.io/badge/domain-Physics-2D6F86?style=flat-square)
  - Agent pattern: programming-verifier plus scientific-verifier
  - Why it matters: PhysVEC builds verification and error-correction directly into a multi-agent physics research workflow.

- **[HLER: Human-in-the-Loop Economic Research via Multi-Agent Pipelines for Empirical Discovery](https://arxiv.org/abs/2603.07444)**
  ![phase: Review](https://img.shields.io/badge/phase-Review-5C4B8A?style=flat-square) ![phase: Hypothesis Formulation](https://img.shields.io/badge/phase-Hypothesis%20Formulation-5C4B8A?style=flat-square) ![domain: Interdisciplinary](https://img.shields.io/badge/domain-Interdisciplinary-2D6F86?style=flat-square)
  - Agent pattern: human-in-the-loop multi-agent pipeline
  - Why it matters: HLER coordinates agents for data auditing, hypothesis generation, econometric analysis, manuscript drafting, and review in one empirical research pipeline.

## Frameworks And Infrastructure

### General MAS Frameworks

- **[PiFlow: Principle-aware Scientific Discovery with Multi-Agent Collaboration](https://arxiv.org/abs/2505.15047)**
  ![phase: Hypothesis Formulation](https://img.shields.io/badge/phase-Hypothesis%20Formulation-5C4B8A?style=flat-square) ![domain: Interdisciplinary](https://img.shields.io/badge/domain-Interdisciplinary-2D6F86?style=flat-square)
  - Agent pattern: principle-aware multi-agent discovery
  - Why it matters: PiFlow frames automated scientific discovery as structured uncertainty reduction guided by principles across multiple scientific domains.

- **[Open Source Planning & Control System with Language Agents for Autonomous Scientific Discovery](https://arxiv.org/abs/2507.07257)**
  ![phase: Experimentation (Dry Lab)](https://img.shields.io/badge/phase-Experimentation%20(Dry%20Lab)-5C4B8A?style=flat-square) ![domain: Interdisciplinary](https://img.shields.io/badge/domain-Interdisciplinary-2D6F86?style=flat-square)
  - Agent pattern: planning-and-control orchestration
  - Why it matters: cmbagent presents a large multi-agent research stack with specialized roles for literature, code, interpretation, and critique.

- **[OrchMAS: Orchestrated Reasoning with Multi Collaborative Heterogeneous Scientific Expert Structured Agents](https://arxiv.org/abs/2603.03005)**
  ![phase: Hypothesis Formulation](https://img.shields.io/badge/phase-Hypothesis%20Formulation-5C4B8A?style=flat-square) ![domain: Interdisciplinary](https://img.shields.io/badge/domain-Interdisciplinary-2D6F86?style=flat-square)
  - Agent pattern: orchestrator with heterogeneous expert agents
  - Why it matters: OrchMAS dynamically assembles domain-aware expert agents for long-horizon scientific reasoning tasks.

### Domain-Specific Platforms

- **[AGAPI-Agents: An Open-Access Agentic AI Platform for Accelerated Materials Design on AtomGPT.org](https://arxiv.org/abs/2512.11935)**
  ![phase: Experimentation (Dry Lab)](https://img.shields.io/badge/phase-Experimentation%20(Dry%20Lab)-5C4B8A?style=flat-square) ![domain: Materials Science](https://img.shields.io/badge/domain-Materials%20Science-2D6F86?style=flat-square)
  - Agent pattern: planner-executor-summarizer
  - Why it matters: AGAPI unifies open materials APIs, simulations, and open-source LLMs through a multi-agent orchestration layer.

### Communication And Coordination

- **[MACC: Multi-Agent Collaborative Competition for Scientific Exploration](https://arxiv.org/abs/2603.03780)**
  ![phase: Hypothesis Formulation](https://img.shields.io/badge/phase-Hypothesis%20Formulation-5C4B8A?style=flat-square) ![domain: Interdisciplinary](https://img.shields.io/badge/domain-Interdisciplinary-2D6F86?style=flat-square)
  - Agent pattern: collaborative competition
  - Why it matters: MACC studies how cooperation and competition can be combined to improve scientific exploration across multiple agents.

## Failure Modes And Open Challenges

- Technical failure modes: communication breakdown, coordination overhead, agent disagreement, and cascade failures.
- Scientific reliability issues: hallucination, unverifiable claims, invalid methodology, poor calibration, and reproducibility failures.
- Open problems: long-horizon planning, cross-domain integration, uncertainty handling, efficient coordination, and safety.

## License

This repository is licensed under Apache 2.0. See [LICENSE](./LICENSE).
