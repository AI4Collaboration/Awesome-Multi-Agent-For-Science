"""Build an OpenAlex-backed science corpus and summarize LLM4Science/AI4Science ratios.

This script is cost-conscious:
- one shared candidate corpus for 2024-01-01 through the target end date
- one local labeling pass for both LLM4Science and AI4Science
- period summaries derived locally instead of re-querying per period
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import random
import sys
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import httpx

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import arxiv_llm4science_trend as base


OPENALEX_API_URL = "https://api.openalex.org/works"
DATE_FMT = "%Y-%m-%d"


@dataclass(frozen=True)
class QuerySpec:
    query_id: str
    bucket: str
    search_text: str


@dataclass
class QueryResult:
    query_id: str
    bucket: str
    total_reported: int = 0
    pages_fetched: int = 0
    raw_hits: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass
class CorpusRecord:
    source: str
    openalex_id: str
    title: str
    publication_date: str
    publication_year: int
    doi: str
    work_type: str
    abstract: str
    normalized_title: str
    query_ids: list[str]
    query_buckets: list[str]
    matched_query_texts: list[str]
    document_type: str
    architecture_kind: str
    architecture_confidence: str
    evidence_span: str
    is_llm4science: bool
    is_ai4science: bool
    exclude_reason: str


QUERY_SPECS = [
    QuerySpec("B1", "broad", '"AI for Science"'),
    QuerySpec("B2", "broad", "AI4Science"),
    QuerySpec("B3", "broad", '"artificial intelligence" "scientific discovery"'),
    QuerySpec("B4", "broad", '"artificial intelligence" "scientific research"'),
    QuerySpec("B5", "broad", '"machine learning" "scientific discovery"'),
    QuerySpec("B6", "broad", '"machine learning" "scientific research"'),
    QuerySpec("B7", "broad", '"deep learning" "scientific discovery"'),
    QuerySpec("B8", "broad", '"deep learning" "scientific research"'),
    QuerySpec("B9", "broad", '"reinforcement learning" "scientific discovery"'),
    QuerySpec("B10", "broad", '"graph neural network" "scientific discovery"'),
    QuerySpec("B11", "broad", '"diffusion model" "scientific discovery"'),
    QuerySpec("B12", "broad", '"generative model" "scientific discovery"'),
    QuerySpec("B13", "broad", '"large language model" "scientific discovery"'),
    QuerySpec("B14", "broad", '"large language model" "scientific research"'),
    QuerySpec("A1", "agentic", '"AI scientist"'),
    QuerySpec("A2", "agentic", '"scientific agent" scientific'),
    QuerySpec("A3", "agentic", '"research agent" scientific'),
    QuerySpec("A4", "agentic", "agentic scientific"),
    QuerySpec("A5", "agentic", '"AI agent" scientific'),
    QuerySpec("M1", "multi-agent", '"multi-agent" scientific'),
    QuerySpec("M2", "multi-agent", '"multi agent" scientific'),
    QuerySpec("M3", "multi-agent", '"agent team" scientific'),
    QuerySpec("M4", "multi-agent", '"planner executor" scientific'),
    QuerySpec("M5", "multi-agent", "critic reviewer scientific"),
]


PERIODS = [
    ("2024", date(2024, 1, 1), date(2024, 12, 31)),
    ("2025", date(2025, 1, 1), date(2025, 12, 31)),
    ("2026_ytd", date(2026, 1, 1), date(2026, 4, 2)),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-date", default="2024-01-01")
    parser.add_argument("--end-date", default="2026-04-02")
    parser.add_argument("--api-key", default=os.environ.get("OPENALEX_API_KEY"))
    parser.add_argument(
        "--query-id",
        action="append",
        dest="query_ids",
        help="Optional query_id filter. Can be supplied multiple times.",
    )
    parser.add_argument("--per-page", type=int, default=100)
    parser.add_argument("--request-delay-seconds", type=float, default=0.4)
    parser.add_argument("--timeout-seconds", type=float, default=60.0)
    parser.add_argument("--max-retries", type=int, default=5)
    parser.add_argument("--out-dir", default=None)
    return parser.parse_args()


def normalize_whitespace(text: str) -> str:
    return " ".join(text.split())


def parse_date(value: str) -> date:
    return datetime.strptime(value[:10], DATE_FMT).date()


def reconstruct_abstract(inverted_index: dict[str, list[int]] | None) -> str:
    if not inverted_index:
        return ""
    max_pos = -1
    for positions in inverted_index.values():
        if positions:
            max_pos = max(max_pos, max(positions))
    if max_pos < 0:
        return ""
    words = [""] * (max_pos + 1)
    for token, positions in inverted_index.items():
        for pos in positions:
            if 0 <= pos < len(words) and not words[pos]:
                words[pos] = token
    return normalize_whitespace(" ".join(word for word in words if word))


def classify_architecture_kind(title: str, abstract: str) -> tuple[str, str, str]:
    text = normalize_whitespace(f"{title}\n{abstract}")
    lowered = text.lower()

    if not title.strip() or not abstract.strip():
        return ("unclear-delete", "low", "missing title or abstract")

    for pattern in base.get_hard_negative_patterns("ai4science"):
        match = pattern.search(text)
        if match:
            return ("out-of-scope-delete", "high", match.group(0))

    for pattern in base.MULTI_AGENT_PATTERNS:
        match = pattern.search(text)
        if match:
            return ("multi-agent", "high", match.group(0))

    role_count = base.count_role_words(text)
    has_plural_agents = "agents" in lowered
    has_collaboration = any(word in lowered for word in base.COLLABORATION_WORDS)
    if role_count >= 2 and (has_plural_agents or has_collaboration):
        return ("multi-agent", "medium", f"{role_count} multi-agent role words")

    for pattern in base.AGENTIC_PATTERNS:
        match = pattern.search(text)
        if match:
            return ("other-agentic", "medium", match.group(0))

    return ("non-agentic", "medium", "non-agentic")


def classify_record(item: dict[str, Any], query_id: str, bucket: str, search_text: str) -> CorpusRecord:
    title = normalize_whitespace(item.get("display_name", ""))
    abstract = reconstruct_abstract(item.get("abstract_inverted_index"))
    architecture_kind, confidence, evidence_span = classify_architecture_kind(title, abstract)
    is_llm = base.is_scope_candidate(title, abstract, "llm4science")
    is_ai = base.is_scope_candidate(title, abstract, "ai4science")
    exclude_reason = ""
    if architecture_kind == "unclear-delete":
        exclude_reason = "unclear_architecture"
    elif architecture_kind == "out-of-scope-delete":
        exclude_reason = "out_of_scope"
    elif not (is_llm or is_ai):
        exclude_reason = "not_science_scope"

    return CorpusRecord(
        source="openalex",
        openalex_id=item.get("id", ""),
        title=title,
        publication_date=item.get("publication_date", ""),
        publication_year=int(item.get("publication_year") or 0),
        doi=item.get("doi") or "",
        work_type=item.get("type") or "",
        abstract=abstract,
        normalized_title=base.normalize_title(title),
        query_ids=[query_id],
        query_buckets=[bucket],
        matched_query_texts=[search_text],
        document_type=base.classify_document_type(title, abstract),
        architecture_kind=architecture_kind,
        architecture_confidence=confidence,
        evidence_span=evidence_span,
        is_llm4science=is_llm,
        is_ai4science=is_ai,
        exclude_reason=exclude_reason,
    )


async def fetch_with_retries(
    client: httpx.AsyncClient,
    params: dict[str, Any],
    timeout_seconds: float,
    max_retries: int,
    request_delay_seconds: float,
) -> dict[str, Any]:
    backoff = 1.0
    for attempt in range(max_retries + 1):
        try:
            response = await client.get(OPENALEX_API_URL, params=params, timeout=timeout_seconds)
            response.raise_for_status()
            payload = response.json()
            if request_delay_seconds > 0:
                await asyncio.sleep(request_delay_seconds)
            return payload
        except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
            if attempt >= max_retries:
                raise exc
            await asyncio.sleep(backoff + random.uniform(0.0, 0.5))
            backoff *= 2.0
    raise RuntimeError("unreachable retry loop")


async def collect_query(
    client: httpx.AsyncClient,
    spec: QuerySpec,
    api_key: str,
    start_date: str,
    end_date: str,
    per_page: int,
    timeout_seconds: float,
    max_retries: int,
    request_delay_seconds: float,
) -> tuple[list[CorpusRecord], QueryResult]:
    result = QueryResult(query_id=spec.query_id, bucket=spec.bucket)
    collected: list[CorpusRecord] = []
    cursor = "*"

    while True:
        params = {
            "search": spec.search_text,
            "filter": (
                f"from_publication_date:{start_date},"
                f"to_publication_date:{end_date},"
                "has_abstract:true,"
                "type:!paratext"
            ),
            "select": "id,display_name,publication_date,publication_year,type,abstract_inverted_index,doi",
            "per_page": per_page,
            "cursor": cursor,
            "api_key": api_key,
        }
        try:
            payload = await fetch_with_retries(
                client=client,
                params=params,
                timeout_seconds=timeout_seconds,
                max_retries=max_retries,
                request_delay_seconds=request_delay_seconds,
            )
        except Exception as exc:  # noqa: BLE001
            result.errors.append(f"cursor={cursor}: {type(exc).__name__}: {exc}")
            break

        result.pages_fetched += 1
        meta = payload.get("meta", {})
        if result.total_reported == 0:
            result.total_reported = int(meta.get("count") or 0)
        items = payload.get("results", [])
        if not items:
            break

        result.raw_hits += len(items)
        for item in items:
            collected.append(classify_record(item, spec.query_id, spec.bucket, spec.search_text))

        next_cursor = meta.get("next_cursor")
        if not next_cursor:
            break
        cursor = next_cursor

    return collected, result


def merge_records(records: list[CorpusRecord]) -> list[CorpusRecord]:
    deduped: dict[str, CorpusRecord] = {}
    for record in records:
        key = record.openalex_id or record.doi or record.normalized_title
        if key not in deduped:
            deduped[key] = record
            continue

        existing = deduped[key]
        existing.query_ids = sorted({*existing.query_ids, *record.query_ids})
        existing.query_buckets = sorted({*existing.query_buckets, *record.query_buckets})
        existing.matched_query_texts = sorted({*existing.matched_query_texts, *record.matched_query_texts})
        existing.is_llm4science = existing.is_llm4science or record.is_llm4science
        existing.is_ai4science = existing.is_ai4science or record.is_ai4science

        if len(record.abstract) > len(existing.abstract):
            existing.abstract = record.abstract
            existing.document_type = record.document_type

        priority = {"multi-agent": 3, "other-agentic": 2, "non-agentic": 1, "unclear-delete": 0, "out-of-scope-delete": -1}
        if priority.get(record.architecture_kind, -1) > priority.get(existing.architecture_kind, -1):
            existing.architecture_kind = record.architecture_kind
            existing.architecture_confidence = record.architecture_confidence
            existing.evidence_span = record.evidence_span

        deduped[key] = existing
    return list(deduped.values())


def records_to_rows(records: list[CorpusRecord]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in records:
        payload = asdict(record)
        payload["query_ids"] = "|".join(record.query_ids)
        payload["query_buckets"] = "|".join(record.query_buckets)
        payload["matched_query_texts"] = " || ".join(record.matched_query_texts)
        rows.append(payload)
    return rows


def query_results_to_rows(results: list[QueryResult]) -> list[dict[str, Any]]:
    return [
        {
            "query_id": result.query_id,
            "bucket": result.bucket,
            "total_reported": result.total_reported,
            "pages_fetched": result.pages_fetched,
            "raw_hits": result.raw_hits,
            "errors": " || ".join(result.errors),
        }
        for result in results
    ]


def scope_period_summary(records: list[CorpusRecord], scope: str, start: date, end: date) -> dict[str, Any]:
    scope_flag = "is_llm4science" if scope == "llm4science" else "is_ai4science"
    period_records = [
        record
        for record in records
        if start <= parse_date(record.publication_date) <= end
        and getattr(record, scope_flag)
        and record.exclude_reason != "out_of_scope"
    ]
    architecture_counts = Counter()
    document_type_counts = Counter()
    for record in period_records:
        if record.architecture_kind == "multi-agent":
            architecture_counts["multi_agent"] += 1
        elif record.architecture_kind == "other-agentic":
            architecture_counts["other_agentic"] += 1
        else:
            architecture_counts["non_agentic"] += 1
        document_type_counts[record.document_type] += 1

    denominator = (
        architecture_counts["multi_agent"]
        + architecture_counts["other_agentic"]
        + architecture_counts["non_agentic"]
    )
    return {
        "multi_agent": architecture_counts["multi_agent"],
        "other_agentic": architecture_counts["other_agentic"],
        "non_agentic": architecture_counts["non_agentic"],
        "denominator": denominator,
        "ma_share_all": (architecture_counts["multi_agent"] / denominator) if denominator else 0.0,
        "after_dedup_in_scope": len(period_records),
        "survey_perspective": document_type_counts["survey-perspective"],
        "benchmark_dataset": document_type_counts["benchmark-dataset"],
        "method_system": document_type_counts["method-system"],
    }


async def run_collection(args: argparse.Namespace) -> tuple[list[CorpusRecord], list[QueryResult]]:
    if not args.api_key:
        raise ValueError("missing OpenAlex API key; pass --api-key or set OPENALEX_API_KEY")

    selected_queries = QUERY_SPECS
    if args.query_ids:
        requested = set(args.query_ids)
        selected_queries = [spec for spec in QUERY_SPECS if spec.query_id in requested]
        missing = requested - {spec.query_id for spec in selected_queries}
        if missing:
            raise ValueError(f"unknown query ids: {sorted(missing)}")

    timeout = httpx.Timeout(args.timeout_seconds, connect=min(10.0, args.timeout_seconds))
    async with httpx.AsyncClient(
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=timeout,
        follow_redirects=True,
    ) as client:
        records: list[CorpusRecord] = []
        query_results: list[QueryResult] = []
        for index, spec in enumerate(selected_queries, start=1):
            batch_records, query_result = await collect_query(
                client=client,
                spec=spec,
                api_key=args.api_key,
                start_date=args.start_date,
                end_date=args.end_date,
                per_page=args.per_page,
                timeout_seconds=args.timeout_seconds,
                max_retries=args.max_retries,
                request_delay_seconds=args.request_delay_seconds,
            )
            records.extend(batch_records)
            query_results.append(query_result)
            print(
                f"[progress] {index}/{len(selected_queries)} "
                f"({index / len(selected_queries) * 100:5.1f}%) latest={spec.query_id} raw={len(records)}",
                flush=True,
            )
    return records, query_results


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = parse_args()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = (
        Path(args.out_dir)
        if args.out_dir
        else Path("sample_data") / "openalex_science" / f"from_2024_{timestamp}"
    )

    try:
        raw_records, query_results = asyncio.run(run_collection(args))
    except KeyboardInterrupt:
        return 130
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    deduped_records = merge_records(raw_records)
    period_summaries: dict[str, Any] = {}
    for period_name, period_start, period_end in PERIODS:
        period_summaries[period_name] = {
            "llm4science": scope_period_summary(deduped_records, "llm4science", period_start, period_end),
            "ai4science": scope_period_summary(deduped_records, "ai4science", period_start, period_end),
        }

    summary = {
        "source": "openalex",
        "time_window": {"start_date": args.start_date, "end_date": args.end_date},
        "query_count": len(query_results),
        "raw_retrieved": len(raw_records),
        "after_dedup": len(deduped_records),
        "queries_with_errors": [result.query_id for result in query_results if result.errors],
        "period_summaries": period_summaries,
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(out_dir / "raw_results.csv", records_to_rows(raw_records))
    write_csv(out_dir / "deduped_results.csv", records_to_rows(deduped_records))
    write_csv(out_dir / "query_summary.csv", query_results_to_rows(query_results))
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(json.dumps(summary, indent=2))
    print(f"OUTPUT_DIR={out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
