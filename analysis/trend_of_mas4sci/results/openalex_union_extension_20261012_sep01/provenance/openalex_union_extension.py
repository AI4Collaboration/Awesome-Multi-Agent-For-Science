"""Budgeted OR-union extension of the frozen 17-query OpenAlex corpus."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import time
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote

import httpx

import openalex_mas4sci_from_2024 as classifier
from openalex_resumable import (atomic_bytes, atomic_json, classifier_hash, compressed_jsonl,
                               identity, output_lock, read_json, sha, utcnow)

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "results/openalex_rerun_20261012"
API = "https://api.openalex.org"
REVISION = "d6a37e4cae69b95efe85ed5467ad2fe519046b34"
HISTORY = "analysis/trend_of_mas4sci/results/openalex_from_2024_cost_conscious/query_summary.csv"
START, DEFAULT_END = "2026-04-03", "2026-09-01"
QUERY_IDS = ("B1", "B2", "B5", "B7", "B9", "B10", "B11", "B12", "B13", "B14",
             "A1", "A2", "A3", "M1", "M3", "M4", "M5")
SAFE_RATE = ("daily_budget_usd", "daily_used_usd", "daily_remaining_usd",
             "prepaid_balance_usd", "prepaid_remaining_usd", "resets_at", "endpoint_costs_usd")
SAFE_HEADERS = ("x-ratelimit-limit", "x-ratelimit-remaining", "x-ratelimit-credits-used",
                "x-ratelimit-reset", "retry-after")


class SafeStop(Exception):
    pass


def require(condition, message):
    if not condition:
        raise SafeStop(message)


def micro(value):
    from decimal import Decimal
    return int(Decimal(str(value)) * 1_000_000)


def load_key():
    value = os.environ.get("OPENALEX_API_KEY")
    if value:
        return value, "process_environment:OPENALEX_API_KEY"
    data = subprocess.check_output(["git", "show", f"{REVISION}:{HISTORY}"], cwd=ROOT.parents[1])
    values = {unquote(m.decode()) for m in re.findall(rb"[?&]api_key=([^&\s'\"<>]+)", data)
              if m != b"[REDACTED]"}
    require(len(values) == 1, "historical_key_missing_or_ambiguous")
    return values.pop(), "explicitly_authorized_historical_git_blob_in_memory"


def frozen_configuration():
    manifest = read_json(BASE / "manifest.json")
    config = manifest["configuration"]
    require(tuple(q["query_id"] for q in config["queries"]) == QUERY_IDS, "logical_query_ids_changed")
    return {"physical_query_id": "U1", "logical_queries": config["queries"],
            "search": " OR ".join("(" + q["search_text"] + ")" for q in config["queries"]),
            "select": config["select"], "start_date": START,
            "classification": "Original lexical classifier and bookkeeping-corrected inclusion; no semantic changes.",
            "query_membership": "U1 identifies the OR union; individual clause membership is not inferred.",
            "base_manifest_sha256": sha((BASE / "manifest.json").read_bytes()),
            "base_classifier_sha256": config["classifier_sha256"]}


def params(config, start, end, per_page, cursor="*"):
    return {"search": config["search"],
            "filter": f"from_publication_date:{start},to_publication_date:{end},has_abstract:true,type:!paratext",
            "select": ",".join(config["select"]), "per_page": per_page, "cursor": cursor}


class Run:
    def __init__(self, out, client):
        self.out, self.client = out, client
        out.mkdir(parents=True, exist_ok=True)
        self.config = frozen_configuration()
        path = out / "configuration.json"
        if path.exists():
            require(read_json(path) == self.config, "resume_configuration_mismatch")
        else:
            atomic_json(path, self.config)
            atomic_bytes(out / ".gitattributes", b"* -text\n** -text\n")
        self.ledger = read_json(out / "budget.json") if (out / "budget.json").exists() else {
            "attempts": [], "snapshots": [], "utc_day": datetime.now(timezone.utc).date().isoformat(),
            "overall_daily_cap_usd": 0.99, "free_margin_usd": 0.01}
        self.price = max([1000] + [a["accounted_microdollars"] for a in self.ledger["attempts"]])

    def save(self):
        self.ledger["accounted_extension_cost_usd"] = self.spent / 1e6
        atomic_json(self.out / "budget.json", self.ledger)

    @property
    def spent(self):
        return sum(a["accounted_microdollars"] for a in self.ledger["attempts"])

    def refresh(self):
        require(datetime.now(timezone.utc).date().isoformat() == self.ledger["utc_day"], "UTC_day_changed_stop")
        response = self.client.get(API + "/rate-limit")
        require(response.status_code == 200, f"rate_limit_http_{response.status_code}")
        source = response.json()["rate_limit"]
        snapshot = {k: source[k] for k in SAFE_RATE if k in source}
        snapshot["retrieved_at"] = utcnow()
        self.ledger["snapshots"].append(snapshot)
        self.ledger.setdefault("initial_daily_used_microdollars", micro(source["daily_used_usd"]))
        require(micro(source.get("prepaid_remaining_usd", 0)) == micro(source.get("prepaid_balance_usd", 0)), "prepaid_already_consumed_stop")
        self.price = max(self.price, micro(source["endpoint_costs_usd"]["search"]))
        self.save()
        used_bound = max(micro(source["daily_used_usd"]), self.ledger["initial_daily_used_microdollars"] + self.spent)
        return max(0, min(990_000 - used_bound, micro(source["daily_remaining_usd"]) - 10_000))

    def fetch(self, purpose, number, request):
        path = self.out / "pages" / purpose / f"{number:05d}.json.gz"
        if path.exists():
            page = json.loads(gzip.decompress(path.read_bytes()))
            require(page["request"] == request, "saved_page_request_mismatch")
            attempt = self.ledger["attempts"][page["attempt_id"] - 1]
            require(not attempt.get("saved_sha256") or sha(path.read_bytes()) == attempt["saved_sha256"], "saved_page_hash_mismatch")
            return page
        available = self.refresh()
        require(available >= self.price, "insufficient_safe_free_allowance")
        attempt = {"attempt_id": len(self.ledger["attempts"]) + 1, "purpose": purpose,
                   "page_number": number, "requested_at": utcnow(), "status": "reserved",
                   "accounted_microdollars": self.price}
        self.ledger["attempts"].append(attempt)
        self.save()
        try:
            response = self.client.get(API + "/works", params=request)
            attempt["status"] = response.status_code
            attempt["rate_headers"] = {k: response.headers[k] for k in SAFE_HEADERS if k in response.headers}
            require(response.status_code == 200, f"search_http_{response.status_code}")
            payload = response.json()
            require(isinstance(payload.get("results"), list) and "next_cursor" in payload["meta"], "malformed_page")
            actual_cost = micro(payload["meta"].get("cost_usd", self.price / 1e6))
            attempt["reported_cost_usd"] = actual_cost / 1e6
            attempt["accounted_microdollars"] = max(attempt["accounted_microdollars"], actual_cost)
            self.price = max(self.price, actual_cost)
            page = {"schema_version": 1, "query_id": "U1", "purpose": purpose,
                    "page_number": number, "request": request, "retrieved_at": utcnow(),
                    "attempt_id": attempt["attempt_id"], "cost_usd": actual_cost / 1e6,
                    "rate_headers": {k: response.headers[k] for k in SAFE_HEADERS if k in response.headers},
                    "response": {"meta": payload["meta"], "results": payload["results"]}}
            data = gzip.compress((json.dumps(page, sort_keys=True, ensure_ascii=True) + "\n").encode(), mtime=0)
            atomic_bytes(path, data)
            attempt["saved_path"] = path.relative_to(self.out).as_posix()
            attempt["saved_sha256"] = sha(data)
            return page
        except httpx.HTTPError as exc:
            attempt["status"] = type(exc).__name__
            raise SafeStop("search_transport_" + type(exc).__name__) from None
        finally:
            attempt["finished_at"] = utcnow()
            self.save()

    def saved(self, end, per_page):
        purpose = "incremental_" + end
        pages, seen, used_cursors = [], set(), set()
        cursor, total = "*", None
        for number, path in enumerate(sorted((self.out / "pages" / purpose).glob("*.json.gz")), 1):
            require(path.name == f"{number:05d}.json.gz", "noncontiguous_pages")
            page = self.fetch(purpose, number, params(self.config, START, end, per_page, cursor))
            require(cursor is not None and cursor not in used_cursors, "cursor_cycle")
            used_cursors.add(cursor)
            self.check_page(page, total, seen, end, per_page)
            total = page["response"]["meta"]["count"]
            cursor = page["response"]["meta"]["next_cursor"]
            require(cursor not in used_cursors, "cursor_cycle")
            pages.append(page)
        return pages, seen, cursor, total

    @staticmethod
    def check_page(page, total, seen, end, per_page):
        meta, rows = page["response"]["meta"], page["response"]["results"]
        require(total is None or total == meta["count"], "reported_count_changed")
        require(meta["per_page"] == per_page and len(rows) <= per_page, "page_size_changed")
        require(bool(rows) or meta["next_cursor"] is None, "empty_nonterminal_page")
        for row in rows:
            identifier = row.get("id")
            require(isinstance(identifier, str) and identifier.startswith("https://openalex.org/W"), "missing_or_invalid_work_id")
            require(identifier not in seen, "duplicate_work_id")
            require(START <= row.get("publication_date", "") <= end, "publication_outside_window")
            require(row.get("type") != "paratext", "paratext_in_results")
            seen.add(identifier)

    def checkpoint(self, end, per_page, pages, seen, total):
        descriptors = []
        for page in pages:
            relative = f"pages/incremental_{end}/{page['page_number']:05d}.json.gz"
            descriptors.append({"path": relative, "sha256": sha((self.out / relative).read_bytes()),
                                "query_id": "U1", "page_number": page["page_number"],
                                "retrieved_at": page["retrieved_at"], "attempt_id": page["attempt_id"],
                                "cursor": page["request"]["cursor"],
                                "next_cursor": page["response"]["meta"]["next_cursor"],
                                "total_reported": page["response"]["meta"]["count"],
                                "raw_hits": len(page["response"]["results"])})
        config = {"start_date": START, "end_date": end, "select": self.config["select"],
                  "filter": params(self.config, START, end, per_page)["filter"], "per_page": per_page,
                  "classifier_sha256": self.config["base_classifier_sha256"],
                  "queries": [{"query_id": "U1", "bucket": "union", "search_text": self.config["search"]}],
                  "logical_queries": self.config["logical_queries"]}
        complete = bool(pages) and pages[-1]["response"]["meta"]["next_cursor"] is None and len(seen) == total
        manifest = {"schema_version": 1, "configuration": config, "pages": descriptors,
                    "status": "retrieved_complete" if complete else "partial", "artifacts": {},
                    "updated_at": utcnow(), "probe_pages_excluded_from_corpus": True}
        atomic_json(self.out / "manifest.json", manifest)
        progress = {"pages_saved": len(pages), "raw_hits": len(seen), "total_reported": total,
                    "terminal_cursor": pages[-1]["response"]["meta"]["next_cursor"] if pages else "*",
                    "retrieval_complete": complete, "validated_complete": False,
                    "extension_cost_bound_usd": self.spent / 1e6}
        atomic_json(self.out / "progress.json", progress)
        return manifest

    def collect(self, end, per_page):
        pages, seen, cursor, total = self.saved(end, per_page)
        require(bool(pages), "first_page_required")
        manifest = self.checkpoint(end, per_page, pages, seen, total)
        used_cursors = {p["request"]["cursor"] for p in pages}
        while cursor is not None:
            page = None
            for retry in range(2):
                try:
                    page = self.fetch("incremental_" + end, len(pages) + 1,
                                      params(self.config, START, end, per_page, cursor))
                    break
                except SafeStop as exc:
                    retryable = str(exc).startswith("search_transport_") or str(exc) in {
                        "search_http_429", "search_http_500", "search_http_502", "search_http_503", "search_http_504"}
                    failures = sum(a["status"] != 200 for a in self.ledger["attempts"])
                    if not retryable or retry or failures > 2:
                        raise
                    time.sleep(3)
            self.check_page(page, total, seen, end, per_page)
            require(cursor not in used_cursors, "cursor_cycle")
            used_cursors.add(cursor)
            cursor = page["response"]["meta"]["next_cursor"]
            require(cursor not in used_cursors, "cursor_cycle")
            pages.append(page)
            manifest = self.checkpoint(end, per_page, pages, seen, total)
            if len(pages) % 5 == 0 or cursor is None:
                print(f"[progress] pages={len(pages)} records={len(seen)}/{total} extension_cost=${self.spent / 1e6:.3f}", flush=True)
        require(len(seen) == total, "terminal_count_gap")
        self.refresh()
        return self.export(end, per_page, manifest)

    def export(self, end, per_page, manifest):
        require(classifier_hash(classifier, BASE) == self.config["base_classifier_sha256"], "classifier_changed")
        records = []
        for descriptor in manifest["pages"]:
            page = json.loads(gzip.decompress((self.out / descriptor["path"]).read_bytes()))
            for item in page["response"]["results"]:
                record = classifier.classify_record(item, "U1", "union", self.config["search"])
                row = asdict(record)
                row.update({"identity": identity(record, len(records)), "occurrence_indices": [len(records)],
                            "included_ai4science": record.is_ai4science and record.exclude_reason == "",
                            "included_llm4science": record.is_llm4science and record.exclude_reason == "",
                            "missing_source_fields": [k for k in self.config["select"] if k not in item],
                            "null_or_empty_source_fields": sorted(k for k in self.config["select"] if k in item and not item[k])})
                records.append(row)
        compressed_jsonl(self.out / "deduplicated_corrected.jsonl.gz", records)
        proportions = {}
        for scope in ("ai4science", "llm4science"):
            included = [r for r in records if r["included_" + scope]]
            numerator = sum(r["architecture_kind"] == "multi-agent" for r in included)
            proportions[scope] = {"numerator": numerator, "denominator": len(included),
                                   "percent": 100 * numerator / len(included) if included else 0}
        corpus_attempts = [a for a in self.ledger["attempts"] if a["purpose"] == "incremental_" + end]
        corpus_cost = sum(a["accounted_microdollars"] for a in corpus_attempts)
        last = self.ledger["snapshots"][-1]
        summary = {"status": "pending_independent_validation", "time_window": {"start_date": START, "end_date": end},
                   "physical_query_count": 1, "logical_query_count": 17, "raw_occurrences": len(records),
                   "deduplicated_records": len(records), "page_count": len(manifest["pages"]),
                   "proportions": proportions, "corpus_request_cost_usd": corpus_cost / 1e6,
                   "noncorpus_probe_cost_usd": (self.spent - corpus_cost) / 1e6,
                   "extension_total_cost_usd": self.spent / 1e6, "daily_used_usd": last["daily_used_usd"],
                   "daily_remaining_usd": last["daily_remaining_usd"],
                   "query_definition": self.config["search"], "logical_queries": self.config["logical_queries"],
                   "classifier_sha256": self.config["base_classifier_sha256"],
                   "classification_method": self.config["classification"],
                   "individual_clause_membership": "unknown; query_ids contains only U1",
                   "records_file": "deduplicated_corrected.jsonl.gz", "record_schema": sorted(records[0]) if records else []}
        atomic_json(self.out / "summary.json", summary)
        for source in (Path(__file__), Path(classifier.__file__), Path(classifier.base.__file__)):
            data = source.read_bytes()
            atomic_bytes(self.out / "provenance" / source.name, data)
        self.verify(end, per_page, manifest, summary)
        return summary

    def verify(self, end, per_page, manifest, summary):
        with gzip.open(self.out / "deduplicated_corrected.jsonl.gz", "rt", encoding="utf-8") as handle:
            records = [json.loads(line) for line in handle]
        seen, cursor, offset = set(), "*", 0
        field_names = set(classifier.CorpusRecord.__dataclass_fields__)
        for number, descriptor in enumerate(manifest["pages"], 1):
            path = self.out / descriptor["path"]
            require(sha(path.read_bytes()) == descriptor["sha256"], "independent_page_hash_mismatch")
            page = json.loads(gzip.decompress(path.read_bytes()))
            require(page["request"] == params(self.config, START, end, per_page, cursor), "independent_request_mismatch")
            require(page["page_number"] == number, "independent_page_gap")
            require(page["response"]["meta"]["count"] == summary["raw_occurrences"], "independent_total_mismatch")
            cursor = page["response"]["meta"]["next_cursor"]
            for item in page["response"]["results"]:
                require(item["id"] not in seen, "independent_duplicate_work")
                seen.add(item["id"])
                row = records[offset]
                expected = classifier.classify_record(item, "U1", "union", self.config["search"])
                require(asdict(expected) == {k: row[k] for k in field_names}, "independent_classification_mismatch")
                require(row["identity"] == identity(expected, offset) and row["occurrence_indices"] == [offset], "independent_identity_or_provenance")
                require(START <= item["publication_date"] <= end, "independent_date_mismatch")
                for scope in ("ai4science", "llm4science"):
                    require(row["included_" + scope] == (row["is_" + scope] and row["exclude_reason"] == ""), "independent_inclusion_mismatch")
                offset += 1
        require(cursor is None and offset == len(records) == summary["raw_occurrences"], "independent_incomplete_corpus")
        require(sha((BASE / "manifest.json").read_bytes()) == self.config["base_manifest_sha256"], "frozen_base_changed")
        require(all(s["daily_used_usd"] <= 0.99 and s["daily_remaining_usd"] >= 0.01 for s in self.ledger["snapshots"]), "daily_budget_violation")
        report = {"validated_complete": True, "queries": [{"query_id": "U1", "pages": len(manifest["pages"]),
                  "raw_hits": offset, "total_reported": offset, "terminal_cursor": None}],
                  "page_count": len(manifest["pages"]), "raw_occurrences": offset,
                  "deduplicated_records": len(records),
                  "reported_request_cost_usd_exact": f"{summary['corpus_request_cost_usd']:.3f}",
                  "noncorpus_probe_cost_usd": summary["noncorpus_probe_cost_usd"],
                  "extension_total_cost_usd": summary["extension_total_cost_usd"],
                  "daily_used_usd": summary["daily_used_usd"], "daily_remaining_usd": summary["daily_remaining_usd"],
                  "duplicate_ids": 0, "classification_records_reproduced": offset,
                  "frozen_base_manifest_unchanged": True,
                  "union_equivalence": read_json(self.out / "union_equivalence.json")}
        summary["status"] = "complete"
        atomic_json(self.out / "summary.json", summary)
        atomic_json(self.out / "verification.json", report)
        manifest["status"] = "complete"
        for name in ("deduplicated_corrected.jsonl.gz", "summary.json", "verification.json", "budget.json", "union_equivalence.json"):
            path = self.out / name
            manifest["artifacts"][name] = {"sha256": sha(path.read_bytes()), "bytes": path.stat().st_size}
        atomic_json(self.out / "manifest.json", manifest)
        progress = read_json(self.out / "progress.json")
        progress["validated_complete"] = True
        atomic_json(self.out / "progress.json", progress)
        atomic_json(self.out / "evidence_index.json", {"algorithm": "sha256", "files": {
            p.relative_to(self.out).as_posix(): {"sha256": sha(p.read_bytes()), "bytes": p.stat().st_size}
            for p in sorted(self.out.rglob("*")) if p.is_file() and p.name not in ("evidence_index.json", ".collector.lock")
            and not p.name.endswith(".tmp")}})
        print("[validated] " + json.dumps(report), flush=True)

    def probe(self, end, per_page):
        by_day = defaultdict(set)
        with gzip.open(BASE / "deduplicated_corrected.jsonl.gz", "rt", encoding="utf-8") as handle:
            for line in handle:
                row = json.loads(line)
                if row["publication_date"].startswith("2024-"):
                    by_day[row["publication_date"]].add(row["openalex_id"])
        day = next(d for d in sorted(by_day) if 100 <= len(by_day[d]) < 190)
        smoke = self.fetch("equivalence_" + day, 1, params(self.config, day, day, per_page))
        ids = [r["id"] for r in smoke["response"]["results"]]
        expected = by_day[day]
        report = {"date": day, "expected_count": len(expected), "retrieved_count": len(ids),
                  "reported_count": smoke["response"]["meta"]["count"],
                  "missing_ids": sorted(expected - set(ids)), "extra_ids": sorted(set(ids) - expected),
                  "duplicate_ids": len(ids) - len(set(ids)),
                  "exact_set_match": expected == set(ids) and len(ids) == len(expected)}
        atomic_json(self.out / "union_equivalence.json", report)
        require(report["exact_set_match"] and report["reported_count"] == len(expected), "union_equivalence_failed")
        print("[equivalence] " + json.dumps(report), flush=True)
        purpose = "incremental_" + end
        first = self.fetch(purpose, 1, params(self.config, START, end, per_page))
        meta = first["response"]["meta"]
        actual_size = int(meta["per_page"])
        require(actual_size == per_page and len(first["response"]["results"]) == min(int(meta["count"]), per_page), "requested_page_size_not_honored")
        available = self.refresh()
        pages = max(1, math.ceil(meta["count"] / actual_size))
        saved, seen, cursor, total = self.saved(end, per_page)
        remaining_pages = max(0, math.ceil((meta["count"] - len(seen)) / actual_size))
        terminal_allowance = int(cursor is not None and (meta["count"] % actual_size == 0 or len(seen) == meta["count"]))
        required = (remaining_pages + terminal_allowance + 2) * self.price
        plan = {"start_date": START, "end_date": end, "physical_query_id": "U1", "logical_query_count": 17,
                "total_reported": meta["count"], "requested_per_page": per_page, "actual_per_page": actual_size,
                "first_page_records": len(first["response"]["results"]), "estimated_data_pages": pages,
                "remaining_pages": remaining_pages, "terminal_page_allowance": terminal_allowance,
                "retry_allowance_requests": 2, "price_per_page_usd": self.price / 1e6,
                "safe_additional_allowance_usd": available / 1e6,
                "remaining_cost_with_allowances_usd": required / 1e6, "fits": required <= available,
                "daily_used_usd": self.ledger["snapshots"][-1]["daily_used_usd"],
                "daily_remaining_usd": self.ledger["snapshots"][-1]["daily_remaining_usd"],
                "extension_accounted_cost_usd": self.spent / 1e6, "estimated_at": utcnow()}
        atomic_json(self.out / ("feasibility_" + end + ".json"), plan)
        print("[feasibility] " + json.dumps(plan), flush=True)
        return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("probe", "collect"), default="probe")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "results/openalex_union_extension_20261012_sep01")
    parser.add_argument("--end-date", default=DEFAULT_END, choices=("2026-09-01", "2026-09-30", "2026-08-31", "2026-07-31", "2026-06-30", "2026-05-31", "2026-04-30"))
    parser.add_argument("--per-page", type=int, choices=(100, 200), default=200)
    args = parser.parse_args()
    out = args.out_dir.resolve()
    require(out.parent == ROOT / "results" and out.name.startswith("openalex_union_extension_"), "output_outside_exclusive_scope")
    key, source = load_key()
    try:
        with httpx.Client(headers={"Authorization": "Bearer " + key},
                          timeout=httpx.Timeout(60, connect=10), follow_redirects=False) as client:
            with output_lock(out):
                run = Run(out, client)
                plan = run.probe(args.end_date, args.per_page)
                atomic_json(out / "authentication_method.json", {"source": source, "method": "Authorization Bearer header; value not persisted"})
                if args.mode == "collect" and plan["fits"]:
                    run.collect(args.end_date, args.per_page)
            (out / ".collector.lock").unlink(missing_ok=True)
            return 0 if plan["fits"] else 2
    finally:
        key = None


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SafeStop as exc:
        print("STOP: " + str(exc), file=sys.stderr)
        raise SystemExit(2)
    except Exception as exc:
        print("STOP: " + type(exc).__name__ + "; saved evidence retained", file=sys.stderr)
        raise SystemExit(1)
