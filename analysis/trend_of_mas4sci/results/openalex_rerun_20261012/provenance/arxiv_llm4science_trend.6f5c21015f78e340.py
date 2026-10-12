"""Collect recent LLM4Science papers from arXiv with async pagination.

This script is intentionally source-specific for the first pilot:
- Source: arXiv API only
- Window: configurable, defaults to 2025-01-01 through today's date
- Scope: LLM4Science, with additional agentic and multi-agent recall queries

Outputs:
- raw_results.csv: one row per arXiv hit per query
- deduped_results.csv: one row per deduplicated paper
- query_summary.csv: per-query retrieval stats
- summary.json: aggregate counts and the preliminary multi-agent share
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import random
import re
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import httpx


ARXIV_API_URL = "http://export.arxiv.org/api/query"
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
DATE_FMT = "%Y-%m-%d"

MODEL_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"\blarge language models?\b",
        r"\bllms?\b",
        r"\bchatgpt\b",
        r"\bgpt[- ]?4(?:o(?: mini)?)?\b",
        r"\bgpt[- ]?5\b",
        r"\bllama\b",
        r"\bclaude\b",
        r"\bgemini\b",
    ]
]

AI_MODEL_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"\bartificial intelligence\b",
        r"\bai4science\b",
        r"\bai for science\b",
        r"\bmachine learning\b",
        r"\bdeep learning\b",
        r"\breinforcement learning\b",
        r"\bmulti[- ]agent reinforcement learning\b",
        r"\bmarl\b",
        r"\bgraph neural networks?\b",
        r"\bgnns?\b",
        r"\bdiffusion models?\b",
        r"\bgenerative models?\b",
        r"\bneural networks?\b",
        r"\blarge language models?\b",
        r"\bllms?\b",
        r"\bchatgpt\b",
        r"\bgpt[- ]?4(?:o(?: mini)?)?\b",
        r"\bgpt[- ]?5\b",
        r"\bllama\b",
        r"\bclaude\b",
        r"\bgemini\b",
    ]
]

SCIENCE_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"\bscientific\b",
        r"\bscience\b",
        r"\bscientist\b",
        r"\bscientists\b",
        r"\bresearch\b",
        r"\bdiscovery\b",
        r"\bhypothesis\b",
        r"\bexperiment(?:al|s)?\b",
        r"\blaboratory\b",
        r"\bsimulation\b",
        r"\bworkflow\b",
        r"\bpeer review\b",
        r"\bliterature mining\b",
    ]
]

AGENTIC_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"\bagentic\b",
        r"\bagent[s]?\b",
        r"\bscientific agent\b",
        r"\bresearch agent\b",
        r"\bai scientist\b",
        r"\bautonomous\b",
        r"\bautonomously\b",
        r"\bllm agent\b",
        r"\bagentic workflow\b",
    ]
]

MULTI_AGENT_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"\bmulti[- ]agent\b",
        r"\bmulti agent\b",
        r"\bagent team\b",
        r"\bteam of agents\b",
        r"\bmultiple agents\b",
        r"\bplanner[- ]executor\b",
        r"\bcoordination\b",
        r"\bdelegation\b",
        r"\bdebate\b",
    ]
]

MULTI_ROLE_WORDS = [
    "planner",
    "executor",
    "reviewer",
    "critic",
    "verifier",
    "generator",
    "scientist",
    "researcher",
    "coder",
]

COLLABORATION_WORDS = [
    "collaborate",
    "collaboration",
    "coordinate",
    "coordination",
    "communicate",
    "communication",
    "delegate",
    "delegation",
    "debate",
    "review",
]

SURVEY_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"\bsurvey\b",
        r"\breview\b",
        r"\bperspective\b",
        r"\boverview\b",
        r"\broadmap\b",
    ]
]

BENCHMARK_DATASET_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"\bbenchmark\b",
        r"\bbenchmarking\b",
        r"\bdataset\b",
        r"\bcorpus\b",
        r"\bresource\b",
        r"\bevaluation suite\b",
        r"\bleaderboard\b",
    ]
]

COMMON_HARD_NEGATIVE_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"\bchemical agent\b",
        r"\bcontrast agent\b",
        r"\bbiological agent\b",
        r"\binfectious agent\b",
        r"\bagent[- ]based model(?:ing)?\b",
    ]
]

LLM_HARD_NEGATIVE_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"\bmulti[- ]agent reinforcement learning\b",
        r"\bmarl\b",
    ]
]


@dataclass(frozen=True)
class QuerySpec:
    query_id: str
    bucket: str
    arxiv_query: str
    human_text: str


@dataclass
class QueryResult:
    query_id: str
    bucket: str
    total_reported: int = 0
    pages_fetched: int = 0
    raw_hits: int = 0
    in_window_hits: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass
class PaperRecord:
    source: str
    arxiv_id: str
    entry_id: str
    title: str
    authors: str
    published: str
    updated: str
    abstract: str
    primary_category: str
    categories: str
    url: str
    query_ids: list[str]
    query_buckets: list[str]
    matched_query_texts: list[str]
    normalized_title: str
    document_type: str
    architecture_label: str
    label_confidence: str
    evidence_span: str
    exclude_reason: str


@dataclass
class ProgressSnapshot:
    started_at: str
    updated_at: str
    start_date: str
    end_date: str
    total_queries: int
    completed_queries: int
    percent_complete: float
    raw_records_collected: int
    deduped_placeholder: int
    latest_completed_query: str
    completed_query_ids: list[str]
    error_query_ids: list[str]


LLM_QUERY_SPECS = [
    QuerySpec("B1", "broad", 'all:"large language model" AND all:"scientific discovery"', '"large language model" "scientific discovery"'),
    QuerySpec("B2", "broad", 'all:"large language model" AND all:"scientific research"', '"large language model" "scientific research"'),
    QuerySpec("B3", "broad", 'all:"large language model" AND all:"hypothesis generation"', '"large language model" "hypothesis generation"'),
    QuerySpec("B4", "broad", 'all:"large language model" AND all:"experiment design"', '"large language model" "experiment design"'),
    QuerySpec("B5", "broad", 'all:"large language model" AND all:"scientific workflow"', '"large language model" "scientific workflow"'),
    QuerySpec("B6", "broad", 'all:LLM AND all:"scientific discovery"', 'LLM "scientific discovery"'),
    QuerySpec("B7", "broad", 'all:LLM AND all:"scientific research"', 'LLM "scientific research"'),
    QuerySpec("B8", "broad", 'all:"LLM4Science"', '"LLM4Science"'),
    QuerySpec("B9", "broad", 'all:"LLM for Science"', '"LLM for Science"'),
    QuerySpec("B10", "broad", 'all:"large language model" AND all:"AI for Science"', '"large language model" "AI for Science"'),
    QuerySpec("B11", "broad", 'all:"large language model" AND all:AI4Science', '"large language model" AI4Science'),
    QuerySpec("A1", "agentic", 'all:"scientific agent" AND all:"large language model"', '"scientific agent" "large language model"'),
    QuerySpec("A2", "agentic", 'all:"research agent" AND all:"large language model"', '"research agent" "large language model"'),
    QuerySpec("A3", "agentic", 'all:"AI scientist" AND all:"large language model"', '"AI scientist" "large language model"'),
    QuerySpec("A4", "agentic", 'all:agentic AND all:"large language model" AND all:scientific', 'agentic "large language model" scientific'),
    QuerySpec("A5", "agentic", 'all:autonomous AND all:"large language model" AND all:scientific', 'autonomous "large language model" scientific'),
    QuerySpec("A6", "agentic", 'all:"LLM agent" AND all:scientific', '"LLM agent" scientific'),
    QuerySpec("M1", "multi-agent", 'all:"multi-agent" AND all:"large language model" AND all:scientific', '"multi-agent" "large language model" scientific'),
    QuerySpec("M2", "multi-agent", 'all:"multi agent" AND all:"large language model" AND all:scientific', '"multi agent" "large language model" scientific'),
    QuerySpec("M3", "multi-agent", 'all:"agent team" AND all:"large language model" AND all:scientific', '"agent team" "large language model" scientific'),
    QuerySpec("M4", "multi-agent", 'all:"planner executor" AND all:"large language model" AND all:scientific', '"planner executor" "large language model" scientific'),
    QuerySpec("M5", "multi-agent", 'all:critic AND all:reviewer AND all:"large language model" AND all:scientific', 'critic reviewer "large language model" scientific'),
    QuerySpec("M6", "multi-agent", 'all:coordination AND all:delegation AND all:"large language model" AND all:scientific', 'coordination delegation "large language model" scientific'),
]

AI_QUERY_SPECS = [
    QuerySpec("B1", "broad", 'all:"AI for Science"', '"AI for Science"'),
    QuerySpec("B2", "broad", 'all:AI4Science', 'AI4Science'),
    QuerySpec("B3", "broad", 'all:"artificial intelligence" AND all:"scientific discovery"', '"artificial intelligence" "scientific discovery"'),
    QuerySpec("B4", "broad", 'all:"artificial intelligence" AND all:"scientific research"', '"artificial intelligence" "scientific research"'),
    QuerySpec("B5", "broad", 'all:"machine learning" AND all:"scientific discovery"', '"machine learning" "scientific discovery"'),
    QuerySpec("B6", "broad", 'all:"machine learning" AND all:"scientific research"', '"machine learning" "scientific research"'),
    QuerySpec("B7", "broad", 'all:"deep learning" AND all:"scientific discovery"', '"deep learning" "scientific discovery"'),
    QuerySpec("B8", "broad", 'all:"deep learning" AND all:"scientific research"', '"deep learning" "scientific research"'),
    QuerySpec("B9", "broad", 'all:"reinforcement learning" AND all:"scientific discovery"', '"reinforcement learning" "scientific discovery"'),
    QuerySpec("B10", "broad", 'all:"graph neural network" AND all:"scientific discovery"', '"graph neural network" "scientific discovery"'),
    QuerySpec("B11", "broad", 'all:"diffusion model" AND all:"scientific discovery"', '"diffusion model" "scientific discovery"'),
    QuerySpec("B12", "broad", 'all:"generative model" AND all:"scientific discovery"', '"generative model" "scientific discovery"'),
    QuerySpec("A1", "agentic", 'all:"scientific agent" AND all:scientific', '"scientific agent" scientific'),
    QuerySpec("A2", "agentic", 'all:"research agent" AND all:scientific', '"research agent" scientific'),
    QuerySpec("A3", "agentic", 'all:"AI scientist"', '"AI scientist"'),
    QuerySpec("A4", "agentic", 'all:agentic AND all:scientific', 'agentic scientific'),
    QuerySpec("A5", "agentic", 'all:autonomous AND all:"scientific discovery"', 'autonomous "scientific discovery"'),
    QuerySpec("A6", "agentic", 'all:"AI agent" AND all:scientific', '"AI agent" scientific'),
    QuerySpec("M1", "multi-agent", 'all:"multi-agent" AND all:"scientific discovery"', '"multi-agent" "scientific discovery"'),
    QuerySpec("M2", "multi-agent", 'all:"multi agent" AND all:scientific', '"multi agent" scientific'),
    QuerySpec("M3", "multi-agent", 'all:"agent team" AND all:scientific', '"agent team" scientific'),
    QuerySpec("M4", "multi-agent", 'all:"planner executor" AND all:scientific', '"planner executor" scientific'),
    QuerySpec("M5", "multi-agent", 'all:critic AND all:reviewer AND all:scientific', 'critic reviewer scientific'),
    QuerySpec("M6", "multi-agent", 'all:coordination AND all:delegation AND all:scientific', 'coordination delegation scientific'),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scope",
        choices=["llm4science", "ai4science"],
        default="llm4science",
        help="Experiment scope to query and classify",
    )
    parser.add_argument("--start-date", default="2025-01-01", help="Inclusive start date, YYYY-MM-DD")
    parser.add_argument(
        "--end-date",
        default=date.today().isoformat(),
        help="Inclusive end date, YYYY-MM-DD",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=100,
        help="arXiv max_results page size per API call",
    )
    parser.add_argument(
        "--max-results-per-query",
        type=int,
        default=0,
        help="Maximum raw hits to keep per query before date filtering; 0 means no cap",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=4,
        help="Maximum concurrent arXiv API requests",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=30.0,
        help="Per-request timeout in seconds",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=4,
        help="Retry count for timeout and transient HTTP errors",
    )
    parser.add_argument(
        "--request-delay-seconds",
        type=float,
        default=3.0,
        help="Delay between API requests to reduce throttling pressure",
    )
    parser.add_argument(
        "--query-id",
        action="append",
        dest="query_ids",
        help="Optional query_id filter. Can be supplied multiple times.",
    )
    parser.add_argument(
        "--out-dir",
        default=None,
        help="Directory to write results into. Defaults to sample_data/llm4science_arxiv/<timestamp>",
    )
    parser.add_argument(
        "--progress-file",
        default=None,
        help="Optional JSON file path for live progress updates",
    )
    return parser.parse_args()


def normalize_whitespace(text: str) -> str:
    return " ".join(text.split())


def normalize_title(title: str) -> str:
    lowered = title.lower()
    stripped = re.sub(r"[^a-z0-9]+", " ", lowered)
    return normalize_whitespace(stripped)


def parse_date(date_text: str) -> date:
    return datetime.strptime(date_text[:10], DATE_FMT).date()


def format_arxiv_datetime(value: date, end_of_day: bool = False) -> str:
    return value.strftime("%Y%m%d") + ("2359" if end_of_day else "0000")


def build_arxiv_search_query(base_query: str, start_date: date, end_date: date) -> str:
    date_clause = (
        f"submittedDate:[{format_arxiv_datetime(start_date)} TO "
        f"{format_arxiv_datetime(end_date, end_of_day=True)}]"
    )
    return f"({base_query}) AND {date_clause}"


def contains_any(patterns: list[re.Pattern[str]], text: str) -> bool:
    return any(pattern.search(text) for pattern in patterns)


def count_role_words(text: str) -> int:
    lowered = text.lower()
    return sum(1 for word in MULTI_ROLE_WORDS if re.search(rf"\b{re.escape(word)}\b", lowered))


def classify_document_type(title: str, abstract: str) -> str:
    text = f"{title}\n{abstract}"
    if contains_any(SURVEY_PATTERNS, text):
        return "survey-perspective"
    if contains_any(BENCHMARK_DATASET_PATTERNS, text):
        return "benchmark-dataset"
    return "method-system"


def get_query_specs(scope: str) -> list[QuerySpec]:
    return LLM_QUERY_SPECS if scope == "llm4science" else AI_QUERY_SPECS


def get_hard_negative_patterns(scope: str) -> list[re.Pattern[str]]:
    if scope == "llm4science":
        return [*COMMON_HARD_NEGATIVE_PATTERNS, *LLM_HARD_NEGATIVE_PATTERNS]
    return COMMON_HARD_NEGATIVE_PATTERNS


def is_scope_candidate(title: str, abstract: str, scope: str) -> bool:
    text = f"{title}\n{abstract}"
    model_patterns = MODEL_PATTERNS if scope == "llm4science" else AI_MODEL_PATTERNS
    has_model = contains_any(model_patterns, text)
    has_science = contains_any(SCIENCE_PATTERNS, text)
    return has_model and has_science


def non_agentic_label(scope: str) -> str:
    return "non-agentic-llm4science" if scope == "llm4science" else "non-agentic-ai4science"


def classify_architecture(title: str, abstract: str, scope: str) -> tuple[str, str, str]:
    text = normalize_whitespace(f"{title}\n{abstract}")
    lowered = text.lower()

    if not title.strip() or not abstract.strip():
        return ("unclear-delete", "low", "missing title or abstract")

    for pattern in get_hard_negative_patterns(scope):
        match = pattern.search(text)
        if match:
            return ("out-of-scope-delete", "high", match.group(0))

    if not is_scope_candidate(title, abstract, scope):
        return ("out-of-scope-delete", "medium", f"missing {scope} lexical signals")

    for pattern in MULTI_AGENT_PATTERNS:
        match = pattern.search(text)
        if match:
            return ("multi-agent", "high", match.group(0))

    role_count = count_role_words(text)
    has_plural_agents = re.search(r"\bagents\b", lowered) is not None
    has_collaboration = any(word in lowered for word in COLLABORATION_WORDS)
    if role_count >= 2 and (has_plural_agents or has_collaboration):
        return ("multi-agent", "medium", f"{role_count} multi-agent role words")

    for pattern in AGENTIC_PATTERNS:
        match = pattern.search(text)
        if match:
            return ("other-agentic", "medium", match.group(0))

    return (non_agentic_label(scope), "medium", f"{scope} without agentic signal")


def parse_feed_entries(xml_text: str) -> list[dict[str, Any]]:
    root = ET.fromstring(xml_text)
    entries: list[dict[str, Any]] = []
    for entry in root.findall("atom:entry", ATOM_NS):
        entry_id = entry.findtext("atom:id", default="", namespaces=ATOM_NS)
        title = normalize_whitespace(entry.findtext("atom:title", default="", namespaces=ATOM_NS))
        summary = normalize_whitespace(entry.findtext("atom:summary", default="", namespaces=ATOM_NS))
        published = entry.findtext("atom:published", default="", namespaces=ATOM_NS)
        updated = entry.findtext("atom:updated", default="", namespaces=ATOM_NS)
        authors = [
            normalize_whitespace(author.findtext("atom:name", default="", namespaces=ATOM_NS))
            for author in entry.findall("atom:author", ATOM_NS)
        ]
        categories = sorted({category.attrib.get("term", "") for category in entry.findall("atom:category", ATOM_NS)})
        primary_category = ""
        primary = entry.find("arxiv:primary_category", ATOM_NS)
        if primary is not None:
            primary_category = primary.attrib.get("term", "")
        url = entry_id
        for link in entry.findall("atom:link", ATOM_NS):
            if link.attrib.get("rel") == "alternate":
                url = link.attrib.get("href", url)
                break
        arxiv_id = entry_id.rsplit("/", 1)[-1]
        entries.append(
            {
                "entry_id": entry_id,
                "arxiv_id": arxiv_id,
                "title": title,
                "abstract": summary,
                "published": published,
                "updated": updated,
                "authors": ", ".join(author for author in authors if author),
                "primary_category": primary_category,
                "categories": ", ".join(category for category in categories if category),
                "url": url,
            }
        )
    return entries


def parse_total_results(xml_text: str) -> int:
    root = ET.fromstring(xml_text)
    value = root.findtext("{http://a9.com/-/spec/opensearch/1.1/}totalResults")
    return int(value or 0)


async def fetch_with_retries(
    client: httpx.AsyncClient,
    params: dict[str, Any],
    timeout_seconds: float,
    max_retries: int,
    request_delay_seconds: float,
) -> str:
    backoff = 1.0
    for attempt in range(max_retries + 1):
        try:
            response = await client.get(ARXIV_API_URL, params=params, timeout=timeout_seconds)
            response.raise_for_status()
            if request_delay_seconds > 0:
                await asyncio.sleep(request_delay_seconds)
            return response.text
        except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
            if attempt >= max_retries:
                raise exc
            await asyncio.sleep(backoff + random.uniform(0.0, 0.5))
            backoff *= 2.0
    raise RuntimeError("unreachable retry loop")


async def collect_query(
    client: httpx.AsyncClient,
    spec: QuerySpec,
    scope: str,
    start_date: date,
    end_date: date,
    page_size: int,
    max_results_per_query: int,
    timeout_seconds: float,
    max_retries: int,
    request_delay_seconds: float,
) -> tuple[list[PaperRecord], QueryResult]:
    result = QueryResult(query_id=spec.query_id, bucket=spec.bucket)
    collected: list[PaperRecord] = []
    start = 0

    while True:
        remaining = None
        if max_results_per_query > 0:
            remaining = max_results_per_query - start
            if remaining <= 0:
                break
        params = {
            "search_query": build_arxiv_search_query(spec.arxiv_query, start_date, end_date),
            "start": start,
            "max_results": min(page_size, remaining) if remaining is not None else page_size,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
        try:
            xml_text = await fetch_with_retries(
                client=client,
                params=params,
                timeout_seconds=timeout_seconds,
                max_retries=max_retries,
                request_delay_seconds=request_delay_seconds,
            )
        except Exception as exc:  # noqa: BLE001
            result.errors.append(f"page_start={start}: {type(exc).__name__}: {exc}")
            break

        result.pages_fetched += 1
        if result.total_reported == 0:
            result.total_reported = parse_total_results(xml_text)

        entries = parse_feed_entries(xml_text)
        if not entries:
            break

        result.raw_hits += len(entries)

        stop_for_date = False
        for entry in entries:
            published_date = parse_date(entry["published"])
            if published_date < start_date:
                stop_for_date = True
                continue
            if published_date > end_date:
                continue

            result.in_window_hits += 1
            architecture_label, label_confidence, evidence_span = classify_architecture(
                entry["title"], entry["abstract"], scope
            )
            exclude_reason = ""
            if architecture_label == "unclear-delete":
                exclude_reason = "unclear_architecture"
            elif architecture_label == "out-of-scope-delete":
                exclude_reason = "out_of_scope"

            collected.append(
                PaperRecord(
                    source="arxiv",
                    arxiv_id=entry["arxiv_id"],
                    entry_id=entry["entry_id"],
                    title=entry["title"],
                    authors=entry["authors"],
                    published=entry["published"],
                    updated=entry["updated"],
                    abstract=entry["abstract"],
                    primary_category=entry["primary_category"],
                    categories=entry["categories"],
                    url=entry["url"],
                    query_ids=[spec.query_id],
                    query_buckets=[spec.bucket],
                    matched_query_texts=[spec.human_text],
                    normalized_title=normalize_title(entry["title"]),
                    document_type=classify_document_type(entry["title"], entry["abstract"]),
                    architecture_label=architecture_label,
                    label_confidence=label_confidence,
                    evidence_span=evidence_span,
                    exclude_reason=exclude_reason,
                )
            )

        if result.total_reported and (start + len(entries) >= result.total_reported):
            break
        if stop_for_date:
            break
        start += page_size

    return collected, result


async def collect_query_with_spec(
    client: httpx.AsyncClient,
    spec: QuerySpec,
    scope: str,
    start_date: date,
    end_date: date,
    page_size: int,
    max_results_per_query: int,
    timeout_seconds: float,
    max_retries: int,
    request_delay_seconds: float,
) -> tuple[QuerySpec, list[PaperRecord], QueryResult]:
    records, result = await collect_query(
        client=client,
        spec=spec,
        scope=scope,
        start_date=start_date,
        end_date=end_date,
        page_size=page_size,
        max_results_per_query=max_results_per_query,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        request_delay_seconds=request_delay_seconds,
    )
    return spec, records, result


def deduplicate_records(records: list[PaperRecord]) -> list[PaperRecord]:
    deduped: dict[str, PaperRecord] = {}
    for record in records:
        key = record.arxiv_id or record.normalized_title
        if key not in deduped:
            deduped[key] = record
            continue

        existing = deduped[key]
        merged_query_ids = sorted({*existing.query_ids, *record.query_ids})
        merged_buckets = sorted({*existing.query_buckets, *record.query_buckets})
        merged_texts = sorted({*existing.matched_query_texts, *record.matched_query_texts})

        chosen = existing
        if len(record.abstract) > len(existing.abstract):
            chosen = record

        chosen.query_ids = merged_query_ids
        chosen.query_buckets = merged_buckets
        chosen.matched_query_texts = merged_texts

        if label_priority(record.architecture_label) > label_priority(existing.architecture_label):
            chosen.architecture_label = record.architecture_label
            chosen.label_confidence = record.label_confidence
            chosen.evidence_span = record.evidence_span
            chosen.exclude_reason = record.exclude_reason

        if document_type_priority(record.document_type) > document_type_priority(existing.document_type):
            chosen.document_type = record.document_type

        deduped[key] = chosen
    return list(deduped.values())


def label_priority(label: str) -> int:
    order = {
        "multi-agent": 5,
        "other-agentic": 4,
        "non-agentic-llm4science": 3,
        "non-agentic-ai4science": 3,
        "unclear-delete": 2,
        "out-of-scope-delete": 1,
    }
    return order.get(label, 0)


def document_type_priority(document_type: str) -> int:
    order = {
        "survey-perspective": 3,
        "benchmark-dataset": 2,
        "method-system": 1,
    }
    return order.get(document_type, 0)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_progress(path: Path | None, snapshot: ProgressSnapshot) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(snapshot), indent=2), encoding="utf-8")


def records_to_rows(records: list[PaperRecord]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in records:
        payload = asdict(record)
        payload["query_ids"] = "|".join(record.query_ids)
        payload["query_buckets"] = "|".join(record.query_buckets)
        payload["matched_query_texts"] = " || ".join(record.matched_query_texts)
        rows.append(payload)
    return rows


def query_results_to_rows(results: list[QueryResult]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for result in results:
        rows.append(
            {
                "query_id": result.query_id,
                "bucket": result.bucket,
                "total_reported": result.total_reported,
                "pages_fetched": result.pages_fetched,
                "raw_hits": result.raw_hits,
                "in_window_hits": result.in_window_hits,
                "errors": " || ".join(result.errors),
            }
        )
    return rows


def build_summary(
    records: list[PaperRecord],
    deduped_records: list[PaperRecord],
    query_results: list[QueryResult],
    start_date: str,
    end_date: str,
    scope: str,
) -> dict[str, Any]:
    noise_filtered = [record for record in records if record.architecture_label != "out-of-scope-delete"]
    non_agentic_key = non_agentic_label(scope)
    denominator_records = [
        record
        for record in deduped_records
        if record.architecture_label
        in {"multi-agent", "other-agentic", non_agentic_key}
    ]
    architecture_counts = Counter(record.architecture_label for record in deduped_records)
    document_type_counts = Counter(record.document_type for record in denominator_records)
    multi_agent = architecture_counts.get("multi-agent", 0)
    denominator = len(denominator_records)
    ma_share_all = (multi_agent / denominator) if denominator else 0.0

    return {
        "source": "arxiv",
        "scope": scope,
        "time_window": {"start_date": start_date, "end_date": end_date},
        "query_count": len(query_results),
        "raw_retrieved": len(records),
        "after_noise_filter": len(noise_filtered),
        "after_dedup": len(deduped_records),
        "multi_agent": multi_agent,
        "other_agentic": architecture_counts.get("other-agentic", 0),
        f"non_agentic_{scope}": architecture_counts.get(non_agentic_key, 0),
        "survey_perspective": document_type_counts.get("survey-perspective", 0),
        "benchmark_dataset": document_type_counts.get("benchmark-dataset", 0),
        "method_system": document_type_counts.get("method-system", 0),
        "unclear_deleted": architecture_counts.get("unclear-delete", 0),
        "out_of_scope_deleted": architecture_counts.get("out-of-scope-delete", 0),
        "ma_share_all": ma_share_all,
        "architecture_counts": dict(sorted(architecture_counts.items())),
        "document_type_counts": dict(sorted(document_type_counts.items())),
        "queries_with_errors": [result.query_id for result in query_results if result.errors],
    }


def build_manual_review_rows(records: list[PaperRecord]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in records:
        needs_review = record.architecture_label in {
            "multi-agent",
            "unclear-delete",
            "out-of-scope-delete",
        } or (
            record.architecture_label == "other-agentic" and record.label_confidence != "high"
        )
        if not needs_review:
            continue
        rows.append(
            {
                "arxiv_id": record.arxiv_id,
                "title": record.title,
                "published": record.published,
                "query_ids": "|".join(record.query_ids),
                "document_type": record.document_type,
                "architecture_label": record.architecture_label,
                "label_confidence": record.label_confidence,
                "evidence_span": record.evidence_span,
                "exclude_reason": record.exclude_reason,
                "url": record.url,
            }
        )
    return rows


async def run_collection(args: argparse.Namespace) -> tuple[list[PaperRecord], list[PaperRecord], list[QueryResult]]:
    start_date = datetime.strptime(args.start_date, DATE_FMT).date()
    end_date = datetime.strptime(args.end_date, DATE_FMT).date()

    selected_queries = get_query_specs(args.scope)
    if args.query_ids:
        requested = set(args.query_ids)
        selected_queries = [spec for spec in selected_queries if spec.query_id in requested]
        missing = requested - {spec.query_id for spec in selected_queries}
        if missing:
            raise ValueError(f"unknown query ids: {sorted(missing)}")

    timeout = httpx.Timeout(args.timeout_seconds, connect=min(10.0, args.timeout_seconds))
    progress_path = Path(args.progress_file) if args.progress_file else None
    started_at = datetime.now().isoformat(timespec="seconds")
    total_queries = len(selected_queries)
    write_progress(
        progress_path,
        ProgressSnapshot(
            started_at=started_at,
            updated_at=started_at,
            start_date=args.start_date,
            end_date=args.end_date,
            total_queries=total_queries,
            completed_queries=0,
            percent_complete=0.0,
            raw_records_collected=0,
            deduped_placeholder=0,
            latest_completed_query="",
            completed_query_ids=[],
            error_query_ids=[],
        ),
    )
    limits = httpx.Limits(max_connections=args.concurrency, max_keepalive_connections=args.concurrency)
    async with httpx.AsyncClient(
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            )
        },
        timeout=timeout,
        limits=limits,
        follow_redirects=True,
    ) as client:
        tasks = [
            asyncio.create_task(
                collect_query_with_spec(
                    client=client,
                    spec=spec,
                    scope=args.scope,
                    start_date=start_date,
                    end_date=end_date,
                    page_size=args.page_size,
                    max_results_per_query=args.max_results_per_query,
                    timeout_seconds=args.timeout_seconds,
                    max_retries=args.max_retries,
                    request_delay_seconds=args.request_delay_seconds,
                )
            )
            for spec in selected_queries
        ]
        raw_records: list[PaperRecord] = []
        query_results: list[QueryResult] = []
        completed_query_ids: list[str] = []
        error_query_ids: list[str] = []
        for task in asyncio.as_completed(tasks):
            spec, records, query_result = await task
            raw_records.extend(records)
            query_results.append(query_result)
            completed_query_ids.append(spec.query_id)
            if query_result.errors:
                error_query_ids.append(spec.query_id)
            percent_complete = (len(completed_query_ids) / total_queries * 100.0) if total_queries else 100.0
            write_progress(
                progress_path,
                ProgressSnapshot(
                    started_at=started_at,
                    updated_at=datetime.now().isoformat(timespec="seconds"),
                    start_date=args.start_date,
                    end_date=args.end_date,
                    total_queries=total_queries,
                    completed_queries=len(completed_query_ids),
                    percent_complete=percent_complete,
                    raw_records_collected=len(raw_records),
                    deduped_placeholder=0,
                    latest_completed_query=spec.query_id,
                    completed_query_ids=sorted(completed_query_ids),
                    error_query_ids=sorted(error_query_ids),
                ),
            )
            print(
                f"[progress] {len(completed_query_ids)}/{total_queries} "
                f"({percent_complete:5.1f}%) latest={spec.query_id} raw={len(raw_records)}",
                flush=True,
            )

    deduped_records = deduplicate_records(raw_records)
    write_progress(
        progress_path,
        ProgressSnapshot(
            started_at=started_at,
            updated_at=datetime.now().isoformat(timespec="seconds"),
            start_date=args.start_date,
            end_date=args.end_date,
            total_queries=total_queries,
            completed_queries=total_queries,
            percent_complete=100.0,
            raw_records_collected=len(raw_records),
            deduped_placeholder=len(deduped_records),
            latest_completed_query="deduped",
            completed_query_ids=sorted(completed_query_ids),
            error_query_ids=sorted(error_query_ids),
        ),
    )
    return raw_records, deduped_records, query_results


def main() -> int:
    args = parse_args()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dataset_dir = "llm4science_arxiv" if args.scope == "llm4science" else "ai4science_arxiv"
    out_dir = (
        Path(args.out_dir)
        if args.out_dir
        else Path("sample_data") / dataset_dir / f"pilot_{timestamp}"
    )

    try:
        raw_records, deduped_records, query_results = asyncio.run(run_collection(args))
    except KeyboardInterrupt:
        return 130
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    summary = build_summary(
        records=raw_records,
        deduped_records=deduped_records,
        query_results=query_results,
        start_date=args.start_date,
        end_date=args.end_date,
        scope=args.scope,
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(out_dir / "raw_results.csv", records_to_rows(raw_records))
    write_csv(out_dir / "deduped_results.csv", records_to_rows(deduped_records))
    write_csv(out_dir / "query_summary.csv", query_results_to_rows(query_results))
    write_csv(out_dir / "manual_review.csv", build_manual_review_rows(deduped_records))
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(json.dumps(summary, indent=2))
    print(f"OUTPUT_DIR={out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
