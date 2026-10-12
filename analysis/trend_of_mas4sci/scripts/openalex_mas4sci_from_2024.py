"""Collect the fixed 17-query OpenAlex corpus with resumable, budgeted pages.

The original lexical classifier, merge, and denominator functions below remain
available for exact legacy replay. Collection and audited exports are implemented
in openalex_resumable.py. Run with --help for collection and offline replay.
"""

from __future__ import annotations

import sys
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

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
    title = normalize_whitespace(item.get("display_name") or "")
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
        openalex_id=item.get("id") or "",
        title=title,
        publication_date=item.get("publication_date") or "",
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


def merge_records(records: list[CorpusRecord]) -> list[CorpusRecord]:
    """Historical merge, intentionally retaining stale exclude_reason for replay."""
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
    """Historical denominator, including unclear records with lexical scope flags."""
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


def main() -> int:
    import openalex_resumable

    return openalex_resumable.main(sys.modules[__name__])


if __name__ == "__main__":
    raise SystemExit(main())
