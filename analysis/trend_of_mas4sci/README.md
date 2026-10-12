# Trend-of-MAS4Sci

This directory contains the companion analysis behind the `Trend Snapshot` shown in the repo root.

Question:

`How large is the multi-agent share inside LLM4Science and AI4Science, and how is that share changing over time?`

## Auditable OpenAlex Rerun

The repaired collector uses exactly the original 17 queries and the publication
window `2024-01-01` through `2026-04-02`. It saves every response page before
advancing its cursor, reserves request costs before sending, and resumes from
saved pages. Results are written to a new directory; historical outputs are not
overwritten. The 2026 period is January 1 through April 2, not exact Q1.

The primary outputs are compressed raw pages, record-level classifications,
deduplicated corpora, per-query completion counts, period proportions, cost
accounting, and SHA-256 manifests. `legacy_exact` retains the original merge and
denominator behavior. `bookkeeping_corrected` uses the same lexical rules but
recomputes exclusions after merging and removes unclear records from denominators.
Methods, surveys/perspectives, and benchmarks/datasets remain eligible. These are
keyword-defined multi-agent proportions in a query-retrieved corpus, not verified
swarm architectures or field-wide prevalence.

See `results/openalex_rerun_20261012/` for the new evidence and run report.
All 17 queries completed, yielding 84,106 query hits and 59,449 distinct records.
The corrected screen retains 21,248 AI4Science records, including 8,331 LLM4Science records.
All six fractions were independently reproduced from the saved response pages.

| Publication period | LLM4Science multi-agent / all | AI4Science multi-agent / all |
| --- | --- | --- |
| 2024 | 146 / 2,031 = 7.19% | 367 / 5,911 = 6.21% |
| 2025 | 571 / 3,924 = 14.55% | 1,044 / 10,301 = 10.13% |
| 2026 Jan 1-Apr 2 | 499 / 2,376 = 21.00% | 767 / 5,036 = 15.23% |

Its 850 compressed raw pages and both deduplicated corpora are retained for Git.
The reproducible `classified_occurrences.jsonl.gz` intermediate stays local and is
ignored by Git; `--mode replay` regenerates it before validation. The evidence
index retains its expected hash and marks it optional. Scoped Git attributes
preserve the exact bytes covered by archived evidence hashes.

## Historical Partial Result

The historical cost-conscious OpenAlex run covered `2024-01-01` to `2026-04-02`.
It completed 13 queries, retrieved 5,700 of the 19,541 then-reported M1 hits, and
did not retrieve M3, M4, or M5. Its saved summary contains 47,050 query hits and
29,910 deduplicated records; the original raw records were not found in either
local repository. The following table preserves that partial result.

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
- the corrected estimate excludes `out-of-scope-delete` and `unclear-delete`
- the legacy estimate reproduces the original code, which included some unclear
  lexical matches and could retain a stale exclusion after a priority merge

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

Historical directories contain lightweight summaries. The new dated OpenAlex
directory retains compressed record-level evidence and its source-code snapshots.

## Reproduce

Install the only required external dependency:

```bash
python -m pip install -r analysis/trend_of_mas4sci/requirements.txt
```

Run the arXiv `LLM4Science` yearly analysis:

```bash
python analysis/trend_of_mas4sci/scripts/arxiv_llm4science_trend.py --scope llm4science --start-date 2024-01-01 --end-date 2024-12-31 --page-size 50 --concurrency 1 --timeout-seconds 90 --max-retries 8 --request-delay-seconds 2 --out-dir analysis/trend_of_mas4sci/results/arxiv_llm4science/2024
```

From this directory, run the offline tests:

```powershell
& C:/Python313/python.exe -B -m unittest discover -s tests -v
```

Collect reusable first pages and estimate the cost in a new directory:

```powershell
& C:/Python313/python.exe -B scripts/openalex_mas4sci_from_2024.py --out-dir results/openalex_rerun_NEW --first-pages-only --prompt-key --run-cap-usd 0.95 --free-margin-usd 0.05 --concurrency 3
```

Resume collection by repeating the command without `--first-pages-only`. The key
is read without echo or supplied through `OPENALEX_API_KEY`; it is sent only in
the authorization header. There is no key-in-URL or command-line-key option.
The collector stops at its run cap or the remaining free allowance minus the
safety margin. It does not buy credits, use prepaid funds, or schedule another day.

Rebuild and validate the saved 2026-10-12 evidence without API access:

```powershell
& C:/Python313/python.exe -B scripts/openalex_mas4sci_from_2024.py --mode replay --out-dir results/openalex_rerun_20261012
& C:/Python313/python.exe -B scripts/openalex_mas4sci_from_2024.py --mode validate --out-dir results/openalex_rerun_20261012
& C:/Python313/python.exe -B scripts/verify_openalex_evidence.py --out-dir results/openalex_rerun_20261012 --compare-git-legacy d6a37e4cae69b95efe85ed5467ad2fe519046b34
```

## Notes

- The arXiv run is a separate, narrower sanity check.
- Missing queries in the historical OpenAlex run can affect both numerator and
  denominator; they do not establish a conservative bound on the proportion.
