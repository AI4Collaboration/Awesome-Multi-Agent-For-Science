# Trend-of-MAS4Sci

This directory contains the companion analysis behind the `Trend Snapshot` shown in the repo root.

Question:

`How large is the multi-agent share inside LLM4Science and AI4Science, and how is that share changing over time?`

## Main Result

The main result comes from a cost-conscious OpenAlex candidate corpus covering `2024-01-01` to `2026-04-02`, followed by local labeling into `LLM4Science` and `AI4Science`.

| Period | LLM4Science `multi-agent / all` | AI4Science `multi-agent / all` |
| --- | --- | --- |
| `2024` | `140 / 1864 = 7.51%` | `273 / 4804 = 5.68%` |
| `2025` | `415 / 2726 = 15.22%` | `630 / 6442 = 9.78%` |
| `2026 YTD` (`2026-01-01` to `2026-04-02`) | `245 / 1145 = 21.40%` | `322 / 2158 = 14.92%` |

We also keep a narrower `arXiv-only` sanity check for `LLM4Science`:

| Period | LLM4Science `multi-agent / all` |
| --- | --- |
| `2024` | `21 / 229 = 9.17%` |
| `2025` | `142 / 603 = 23.55%` |
| `2026 YTD` (`2026-01-01` to `2026-04-02`) | `48 / 247 = 19.43%` |

## Matching Rules

The main reporting unit is:

`multi-agent / all in-scope papers`

where:

- `all in-scope = multi-agent + other-agentic + non-agentic`
- we exclude `out-of-scope-delete` and `unclear-delete`

### LLM4Science

A paper is in `LLM4Science` if title or abstract has:

- an LLM signal such as `large language model`, `LLM`, `ChatGPT`, `GPT-4`, `GPT-5`, `Llama`, `Claude`, or `Gemini`
- and a science signal such as `scientific`, `science`, `scientist`, `research`, `discovery`, `hypothesis`, `experiment`, `laboratory`, `simulation`, `workflow`, `peer review`, or `literature mining`

### AI4Science

`AI4Science` uses the same science-side signals, but expands the model-side signals to include:

- `artificial intelligence`
- `AI for Science`
- `AI4Science`
- `machine learning`
- `deep learning`
- `reinforcement learning`
- `graph neural network` / `GNN`
- `diffusion model`
- `generative model`
- `neural network`
- plus all of the LLM-side signals above

### Architecture Labels

- `multi-agent`
- `other-agentic`
- `non-agentic`

`multi-agent` is triggered by explicit signals such as:

- `multi-agent`
- `multi agent`
- `agent team`
- `team of agents`
- `multiple agents`
- `planner-executor`
- `coordination`
- `delegation`
- `debate`

It can also be triggered by at least two role words plus collaboration evidence.

Role words:

- `planner`
- `executor`
- `reviewer`
- `critic`
- `verifier`
- `generator`
- `scientist`
- `researcher`
- `coder`

Collaboration words:

- `collaborate`
- `collaboration`
- `coordinate`
- `coordination`
- `communicate`
- `communication`
- `delegate`
- `delegation`
- `debate`
- `review`

`other-agentic` is triggered by signals such as:

- `agentic`
- `agent`
- `scientific agent`
- `research agent`
- `AI scientist`
- `autonomous`
- `autonomously`
- `LLM agent`
- `agentic workflow`

Hard negatives:

- `chemical agent`
- `contrast agent`
- `biological agent`
- `infectious agent`
- `agent-based model`
- `agent based modeling`

For the narrower arXiv `LLM4Science` run, we also remove:

- `multi-agent reinforcement learning`
- `MARL`

## Exact Query Families

### arXiv LLM4Science Query Family

Broad denominator:

- `"large language model" "scientific discovery"`
- `"large language model" "scientific research"`
- `"large language model" "hypothesis generation"`
- `"large language model" "experiment design"`
- `"large language model" "scientific workflow"`
- `LLM "scientific discovery"`
- `LLM "scientific research"`
- `"LLM4Science"`
- `"LLM for Science"`
- `"large language model" "AI for Science"`
- `"large language model" AI4Science`

Agentic recall:

- `"scientific agent" "large language model"`
- `"research agent" "large language model"`
- `"AI scientist" "large language model"`
- `agentic "large language model" scientific`
- `autonomous "large language model" scientific`
- `"LLM agent" scientific`

Multi-agent recall:

- `"multi-agent" "large language model" scientific`
- `"multi agent" "large language model" scientific`
- `"agent team" "large language model" scientific`
- `"planner executor" "large language model" scientific`
- `critic reviewer "large language model" scientific`
- `coordination delegation "large language model" scientific`

### OpenAlex Queries Used In The Canonical Run

The cost-conscious OpenAlex run used these `17` query strings:

- `"AI for Science"`
- `AI4Science`
- `"machine learning" "scientific discovery"`
- `"deep learning" "scientific discovery"`
- `"reinforcement learning" "scientific discovery"`
- `"graph neural network" "scientific discovery"`
- `"diffusion model" "scientific discovery"`
- `"generative model" "scientific discovery"`
- `"large language model" "scientific discovery"`
- `"large language model" "scientific research"`
- `"AI scientist"`
- `"scientific agent" scientific`
- `"research agent" scientific`
- `"multi-agent" scientific`
- `"agent team" scientific`
- `"planner executor" scientific`
- `critic reviewer scientific`

To stay within budget, the canonical OpenAlex run omitted these broader queries:

- `"artificial intelligence" "scientific discovery"`
- `"artificial intelligence" "scientific research"`
- `"machine learning" "scientific research"`
- `"deep learning" "scientific research"`
- `agentic scientific`
- `"AI agent" scientific`
- `"multi agent" scientific`

## Directory Layout

```text
analysis/trend_of_mas4sci/
  README.md
  requirements.txt
  scripts/
    arxiv_llm4science_trend.py
    openalex_mas4sci_from_2024.py
  results/
    final_trend_table.csv
    openalex_from_2024_cost_conscious/
      summary.json
      query_summary.csv
    arxiv_llm4science/
      2024/
      2025/
      2026_ytd/
```

Only lightweight final artifacts are included here. Large raw retrieval dumps and exploratory recovery runs are intentionally left out of the public repo.

## Reproduce

Install the only required external dependency:

```bash
python -m pip install -r analysis/trend_of_mas4sci/requirements.txt
```

Run the arXiv `LLM4Science` yearly analysis:

```bash
python analysis/trend_of_mas4sci/scripts/arxiv_llm4science_trend.py --scope llm4science --start-date 2024-01-01 --end-date 2024-12-31 --page-size 50 --concurrency 1 --timeout-seconds 90 --max-retries 8 --request-delay-seconds 2 --out-dir analysis/trend_of_mas4sci/results/arxiv_llm4science/2024
```

Run the OpenAlex expanded candidate corpus:

```bash
$env:OPENALEX_API_KEY="YOUR_KEY_HERE"
python analysis/trend_of_mas4sci/scripts/openalex_mas4sci_from_2024.py --start-date 2024-01-01 --end-date 2026-04-02 --per-page 100 --request-delay-seconds 0.2 --timeout-seconds 90 --max-retries 5 --out-dir analysis/trend_of_mas4sci/results/openalex_from_2024_cost_conscious --query-id B1 --query-id B2 --query-id B5 --query-id B7 --query-id B9 --query-id B10 --query-id B11 --query-id B12 --query-id B13 --query-id B14 --query-id A1 --query-id A2 --query-id A3 --query-id M1 --query-id M3 --query-id M4 --query-id M5
```

## Notes

- The OpenAlex run is the main result.
- The arXiv run is a narrower sanity check.
- Some OpenAlex `multi-agent` recall queries hit rate limits during backfill, so the reported `multi-agent` counts are likely conservative.
