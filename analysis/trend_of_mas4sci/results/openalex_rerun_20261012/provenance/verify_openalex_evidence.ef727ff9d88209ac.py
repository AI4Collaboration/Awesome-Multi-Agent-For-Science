"""Independently verify saved OpenAlex evidence, proportions, and legacy parity.

No API access. Optional --compare-git-legacy checks the original collector from
the specified local Git revision and saves its source as provenance.
"""

from __future__ import annotations

import argparse
import getpass
import gzip
import hashlib
import json
import subprocess
import sys
import types
from collections import Counter
from dataclasses import asdict, replace
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import openalex_mas4sci_from_2024 as current
from openalex_resumable import ROOT, QUERY_IDS, FIELDS, FILTER, atomic_bytes, atomic_json, output_lock


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def rows(path):
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle]


def check_proportions(records, summary, estimate):
    checked = {}
    for period, dates in summary["period_definitions"].items():
        checked[period] = {}
        for scope in ("ai4science", "llm4science"):
            included = [r for r in records if r["publication_date"]
                        and dates["start"] <= r["publication_date"] <= dates["end"]
                        and r["is_" + scope]
                        and (r["exclude_reason"] != "out_of_scope" if estimate == "legacy_exact"
                             else r["exclude_reason"] == "")]
            numerator = sum(r["architecture_kind"] == "multi-agent" for r in included)
            count = summary["estimates"][estimate][period][scope]
            require(count["denominator"] == len(included), f"denominator:{estimate}:{period}:{scope}")
            require(count["multi_agent"] == numerator, f"numerator:{estimate}:{period}:{scope}")
            require(count["denominator"] == sum(count[k] for k in ("multi_agent", "other_agentic", "non_agentic")), "architecture_partition")
            require(count["denominator"] == sum(count[k] for k in ("survey_perspective", "benchmark_dataset", "method_system")), "document_partition")
            require(count["ma_share_all"] == (numerator / len(included) if included else 0), "fraction")
            checked[period][scope] = {"numerator": numerator, "denominator": len(included),
                                      "percent": count["ma_share_all"] * 100}
    return checked


def legacy_source(out, revision):
    relative = "analysis/trend_of_mas4sci/scripts/openalex_mas4sci_from_2024.py"
    repo = ROOT.parents[1]
    commit = subprocess.check_output(["git", "rev-parse", revision], cwd=repo, text=True).strip()
    code = subprocess.check_output(["git", "show", f"{commit}:{relative}"], cwd=repo)
    code_hash = hashlib.sha256(code).hexdigest()
    name = "provenance/openalex_original." + code_hash[:16] + ".py"
    atomic_bytes(out / name, code)
    module = types.ModuleType("openalex_historical_verification")
    module.__file__ = str(ROOT / "scripts" / "openalex_mas4sci_from_2024.py")
    sys.modules[module.__name__] = module
    exec(compile(code, name, "exec"), module.__dict__)
    return module, {"git_commit": commit, "path": name, "sha256": code_hash}


def verify_cost_estimate(out, manifest, budget):
    path = out / "cost_estimate.json"
    if not path.exists():
        return None
    plan = read(path)
    at = datetime.fromisoformat(plan["estimated_at"])
    prior = [s for s in budget["snapshots"] if datetime.fromisoformat(s["retrieved_at"]) <= at]
    require(bool(prior), "missing_preflight_budget_snapshot")
    snapshot = prior[-1]
    snapshot_at = datetime.fromisoformat(snapshot["retrieved_at"])
    attempts = [a for a in budget["attempts"] if datetime.fromisoformat(a["requested_at"]) <= at]
    unreflected = [a for a in attempts if "finished_at" not in a
                   or datetime.fromisoformat(a["finished_at"]) >= snapshot_at]
    accounted = sum(a["accounted_microdollars"] for a in attempts) / 1e6
    remaining = min(snapshot["daily_remaining_usd"], 1 - snapshot["daily_used_usd"]) - sum(
        a["accounted_microdollars"] for a in unreflected) / 1e6
    available = min(budget["run_cap_usd"] - accounted,
                    remaining - budget["free_allowance_safety_margin_usd"])
    expected = plan["additional_cost_estimate_usd"] <= available
    corrected = plan.get("fits_current_safe_budget") != expected
    plan["fits_current_safe_budget"] = expected
    plan["budget_snapshot_retrieved_at"] = snapshot["retrieved_at"]
    plan["safe_additional_allowance_at_estimate_usd"] = round(available, 6)
    if corrected:
        plan["reporting_correction"] = "Resume estimate fit flag was calculated before allowance synchronization; reconstructed from the saved rate-limit snapshot and attempt ledger. Per-request live reservations were unaffected."
    atomic_json(path, plan)
    return {"verified_from_saved_budget_evidence": True, "reporting_correction_applied": corrected,
            "run_cost_estimate_usd": plan["run_cost_estimate_usd"],
            "fits_current_safe_budget": expected}


def credential_check(out, tokens=None):
    if not tokens:
        return {"passed": None, "status": "not_checked_no_in_memory_key_provided"}
    checked, matches = 0, []
    for path in out.rglob("*"):
        if not path.is_file() or path.name == ".collector.lock":
            continue
        data = path.read_bytes()
        if path.suffix == ".gz":
            data = gzip.decompress(data)
        checked += 1
        if any(token in data for token in tokens):
            matches.append(path.relative_to(out).as_posix())
    result = {"scan_scope": "new dated output directory only; includes decompressed evidence",
              "credential_source": "in-memory values only; values never exported",
              "credential_values_checked": len(tokens), "files_checked": checked,
              "files_with_matches": matches, "passed": bool(tokens) and not matches}
    atomic_json(out / "credential_check.json", result)
    require(not matches, "credential_found_in_new_output")
    return result


def verify(out, compare_revision=None, known_tokens=None):
    manifest, summary, budget = (read(out / name) for name in ("manifest.json", "summary.json", "budget.json"))
    config = manifest["configuration"]
    require(tuple(q["query_id"] for q in config["queries"]) == QUERY_IDS, "query_ids")
    require(config["start_date"] == "2024-01-01" and config["end_date"] == "2026-04-02", "date_window")
    require(config["filter"] == FILTER and config["select"] == list(FIELDS), "filters_or_fields")
    require(1 <= config["per_page"] <= 100, "page_size")
    specs = {q["query_id"]: q for q in config["queries"]}
    current_specs = {q.query_id: asdict(q) for q in current.QUERY_SPECS}
    require(all(spec == current_specs[q] for q, spec in specs.items()), "query_texts")
    for name, metadata in manifest["artifacts"].items():
        require(digest(out / name) == metadata["sha256"], f"artifact_hash:{name}")
    for run in manifest["software_runs"]:
        for source in run["sources"]:
            require(digest(out / source["path"]) == source["sha256"], "source_hash")

    occurrences = rows(out / "classified_occurrences.jsonl.gz")
    legacy_rows = rows(out / "deduplicated_legacy.jsonl.gz")
    corrected = rows(out / "deduplicated_corrected.jsonl.gz")
    original, original_source = legacy_source(out, compare_revision) if compare_revision else (None, None)
    original_records, page_ids = [], set()
    classified_cache, source_null_adaptations = {}, []
    records_by_query = {q: [] for q in QUERY_IDS}
    page_by_query = {q: [] for q in QUERY_IDS}
    total = 0
    nulls, missing, differences = Counter(), Counter(), []
    legacy_fields = set(current.CorpusRecord.__dataclass_fields__)
    for query_id in QUERY_IDS:
        pages = sorted((p for p in manifest["pages"] if p["query_id"] == query_id), key=lambda p: p["page_number"])
        expected_cursor, expected_number = "*", 1
        used_cursors, ids, counts = set(), set(), set()
        for descriptor in pages:
            path = out / descriptor["path"]
            require(path.is_relative_to(out), "unsafe_page_path")
            require(digest(path) == descriptor["sha256"], "page_hash")
            envelope = json.loads(gzip.decompress(path.read_bytes()))
            request, payload = envelope["request"], envelope["response"]
            require(set(request) == {"search", "filter", "select", "per_page", "cursor"}, "unexpected_request_parameters")
            require(request["search"] == specs[query_id]["search_text"] and request["filter"] == FILTER, "page_query")
            require(request["select"] == ",".join(FIELDS) and request["per_page"] == config["per_page"], "page_selection")
            require(request["cursor"] == expected_cursor and expected_cursor not in used_cursors, "cursor_chain")
            require(envelope["page_number"] == expected_number, "page_sequence")
            require(envelope["attempt_id"] not in page_ids, "attempt_saved_multiple_times")
            attempt = budget["attempts"][envelope["attempt_id"] - 1]
            require(attempt["status"] == 200 and attempt["query_id"] == query_id and attempt["page_number"] == expected_number, "page_attempt")
            require(len(payload["results"]) == descriptor["raw_hits"], "page_count")
            require(len(payload["results"]) <= config["per_page"], "oversized_page")
            counts.add(payload["meta"]["count"])
            page_ids.add(envelope["attempt_id"])
            used_cursors.add(expected_cursor)
            expected_cursor, expected_number = payload["meta"]["next_cursor"], expected_number + 1
            page_by_query[query_id].append(descriptor)
            for index, item in enumerate(payload["results"]):
                require(total < len(occurrences), "missing_occurrence")
                record = occurrences[total]
                require(record["occurrence_index"] == total and record["page_path"] == descriptor["path"] and record["item_index"] == index, "occurrence_provenance")
                require(record["openalex_id"] == (item.get("id") or ""), "source_identity")
                require(record["publication_date"] == (item.get("publication_date") or ""), "source_date")
                abstract = current.reconstruct_abstract(item.get("abstract_inverted_index"))
                require(record["abstract"] == abstract, "source_abstract")
                key = (item.get("id") or "", item.get("display_name") or "",
                       item.get("publication_date") or "", item.get("publication_year"),
                       item.get("doi") or "", item.get("type") or "", abstract)
                adapted = dict(item)
                null_fields = [field for field in ("display_name", "id", "publication_date")
                               if field in item and item[field] is None]
                if original and null_fields:
                    source_null_adaptations.append({"occurrence_index": total, "fields": null_fields})
                    for field in null_fields:
                        adapted[field] = ""
                if key not in classified_cache:
                    classifier = original or current
                    classified_cache[key] = classifier.classify_record(
                        adapted, query_id, specs[query_id]["bucket"], specs[query_id]["search_text"])
                reproduced = replace(classified_cache[key], query_ids=[query_id],
                                     query_buckets=[specs[query_id]["bucket"]],
                                     matched_query_texts=[specs[query_id]["search_text"]])
                require(asdict(reproduced) == {k: record[k] for k in legacy_fields}, "classification_does_not_reproduce")
                require(record["openalex_id"] not in ids, f"duplicate_work_within_query:{query_id}")
                ids.add(record["openalex_id"])
                missing.update(k for k in FIELDS if k not in item)
                nulls.update(k for k in FIELDS if k in item and not item[k])
                publication = date.fromisoformat(item["publication_date"])
                require(date(2024, 1, 1) <= publication <= date(2026, 4, 2), "out_of_window")
                require(item.get("type") != "paratext", "paratext")
                if original:
                    original_records.append(reproduced)
                records_by_query[query_id].append(record)
                total += 1
        require(pages and expected_cursor is None, f"unfinished_query:{query_id}")
        require(len(counts) == 1 and len(ids) == next(iter(counts)), f"query_total_gap:{query_id}")
    require(total == summary["raw_retrieved"] == len(occurrences), "raw_count")
    require(len(corrected) == summary["after_dedup"], "dedup_count")
    coverage = Counter(index for record in corrected for index in record["occurrence_indices"])
    require(coverage == Counter(range(total)), "dedup_provenance_coverage")
    require(len({r["identity"] for r in corrected}) == len(corrected), "duplicate_canonical_identity")
    require(sum(len(v) for v in page_by_query.values()) == len(manifest["pages"]), "unexpected_pages")
    require(set((out / "pages").glob("*/*.json.gz")) == {out / p["path"] for p in manifest["pages"]}, "unindexed_pages")
    compatibility = None
    if original:
        deduped = original.merge_records(original_records)
        require([asdict(r) for r in deduped] == legacy_rows, "legacy_dedup_parity")
        for period, start, end in original.PERIODS:
            for scope in ("ai4science", "llm4science"):
                require(original.scope_period_summary(deduped, scope, start, end) == summary["estimates"]["legacy_exact"][period][scope], "legacy_summary_parity")
        compatibility = {"source": original_source, "compared_occurrences": total,
                         "classification_differences": differences, "deduplication_matches": True,
                         "all_period_summaries_match": True,
                         "source_null_to_empty_adaptations": source_null_adaptations,
                         "null_adapter_definition": "Only null display_name, id, or publication_date values are mapped to empty strings before executing the original collector. Raw pages retain the original values; missing-title records remain unclear."}
    bound = sum(a["accounted_microdollars"] for a in budget["attempts"])
    require(bound <= 950000 and bound / 1e6 == summary["cost"]["accounted_upper_bound_usd"], "run_budget")
    require(budget["attempt_count"] == len(budget["attempts"]), "attempt_count")
    for snapshot in budget["snapshots"]:
        require(snapshot["daily_used_usd"] <= 1, "daily_budget")
        require(snapshot["prepaid_remaining_usd"] == snapshot["prepaid_balance_usd"], "prepaid_consumed")
    attempts_without_pages = [a["attempt_id"] for a in budget["attempts"] if a["attempt_id"] not in page_ids]
    require(not [a for a in budget["attempts"] if a["status"] == 200 and a["attempt_id"] not in page_ids], "successful_response_not_saved")
    report = {"validated_complete": True, "query_count": len(QUERY_IDS), "raw_occurrences": total,
              "deduplicated_records": len(corrected), "page_count": len(manifest["pages"]),
              "search_attempts": len(budget["attempts"]), "attempts_without_pages": attempts_without_pages,
              "missing_source_fields": dict(missing), "null_or_empty_source_fields": dict(nulls),
              "legacy_compatibility": compatibility,
              "verified_proportions": {"legacy_exact": check_proportions(legacy_rows, summary, "legacy_exact"),
                                       "bookkeeping_corrected": check_proportions(corrected, summary, "bookkeeping_corrected")},
              "architecture_evidence_counts": dict(Counter(r["evidence_span"] for r in corrected if r["architecture_kind"] == "multi-agent")),
              "queries": [{"query_id": q, "raw_hits": len(records_by_query[q]),
                            "pages": len(page_by_query[q]), "terminal_cursor": None,
                            "total_reported": page_by_query[q][0]["total_reported"]} for q in QUERY_IDS],
              "validation_method": "Independent raw-page, identity, cursor, count, provenance, cost, source-hash and denominator checks; no human labeling audit."}
    report["cost_estimate_verification"] = verify_cost_estimate(out, manifest, budget)
    report["reported_request_cost_usd_exact"] = str(sum(
        (Decimal(str(a.get("reported_cost_usd", 0))) for a in budget["attempts"]), Decimal(0)))
    source = Path(__file__).read_bytes()
    source_hash = hashlib.sha256(source).hexdigest()
    source_path = f"provenance/verify_openalex_evidence.{source_hash[:16]}.py"
    atomic_bytes(out / source_path, source)
    report["verifier_source"] = {"path": source_path, "sha256": source_hash}
    report["credential_check"] = credential_check(out, known_tokens)
    atomic_json(out / "verification.json", report)
    inventory = {p.relative_to(out).as_posix(): {"sha256": digest(p), "bytes": p.stat().st_size}
                 for p in sorted(out.rglob("*")) if p.is_file()
                 and p.name not in ("evidence_index.json", ".collector.lock", "preservation_audit.json")
                 and not p.name.endswith((".tmp", ".local.json"))}
    atomic_json(out / "evidence_index.json", {"algorithm": "sha256", "files": inventory})
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--compare-git-legacy", metavar="REVISION")
    parser.add_argument("--prompt-key-check", action="store_true", help="Optionally scan new evidence for a known key without echo or API access.")
    args = parser.parse_args()
    out = args.out_dir.resolve()
    require(out.is_relative_to(ROOT), "output_outside_authorized_directory")
    known_tokens = {getpass.getpass("Known key for local scan (not echoed): ").encode()} if args.prompt_key_check else None
    with output_lock(out):
        report = verify(out, args.compare_git_legacy, known_tokens)
    print(json.dumps({key: report[key] for key in ("validated_complete", "query_count", "raw_occurrences", "deduplicated_records", "page_count", "search_attempts", "attempts_without_pages")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
