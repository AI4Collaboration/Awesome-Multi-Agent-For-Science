"""Atomic OpenAlex evidence, conservative cost accounting, and offline replay."""

from __future__ import annotations

import argparse
import asyncio
import copy
import csv
import getpass
import gzip
import hashlib
import inspect
import io
import json
import math
import os
import random
import sys
import time
from collections import Counter
from contextlib import contextmanager
from dataclasses import asdict
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx

API = "https://api.openalex.org"
ROOT = Path(__file__).resolve().parents[1]
QUERY_IDS = ("B1", "B2", "B5", "B7", "B9", "B10", "B11", "B12", "B13", "B14",
             "A1", "A2", "A3", "M1", "M3", "M4", "M5")
FIELDS = ("id", "display_name", "publication_date", "publication_year", "type",
          "abstract_inverted_index", "doi")
START, END = "2024-01-01", "2026-04-02"
FILTER = f"from_publication_date:{START},to_publication_date:{END},has_abstract:true,type:!paratext"
SAFE_HEADERS = ("x-ratelimit-limit", "x-ratelimit-remaining", "x-ratelimit-credits-used",
                "x-ratelimit-reset", "retry-after")
RATE_FIELDS = ("daily_budget_usd", "daily_used_usd", "daily_remaining_usd",
               "prepaid_balance_usd", "prepaid_remaining_usd", "resets_at",
               "endpoint_costs_usd", "credits_limit", "credits_used", "credits_remaining")
SCHEMA = 1


class EvidenceError(Exception):
    """A safe, local diagnostic, never an HTTP exception string."""


class BudgetStop(EvidenceError):
    pass


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def dollars(value: Any) -> int:
    """Integer microdollars keep concurrent reservations exact."""
    return int(Decimal(str(value)) * 1_000_000)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=True, sort_keys=True, indent=2) + "\n").encode()


def atomic_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def atomic_json(path: Path, data: Any) -> None:
    atomic_bytes(path, json_bytes(data))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_page(path: Path) -> dict:
    return json.loads(gzip.decompress(path.read_bytes()))


def compressed_jsonl(path: Path, rows: list[dict]) -> None:
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as output:
        with gzip.GzipFile(filename="", mode="wb", fileobj=output, mtime=0) as zipped:
            for row in rows:
                zipped.write((json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n").encode())
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary, path)


def write_csv(path: Path, rows: list[dict]) -> None:
    stream = io.StringIO(newline="")
    if rows:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    atomic_bytes(path, stream.getvalue().encode())


@contextmanager
def output_lock(path: Path):
    """OS locks survive crashes without a stale PID-file override."""
    path.mkdir(parents=True, exist_ok=True)
    with (path / ".collector.lock").open("a+b") as handle:
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise EvidenceError("output_directory_already_locked") from None
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def classifier_hash(classifier, out: Path | None = None) -> str:
    base_path = Path(classifier.base.__file__)
    base_source = base_path.read_bytes()
    if out is not None and (out / "manifest.json").exists():
        manifest = read_json(out / "manifest.json")
        snapshots = [source for run in manifest["software_runs"] for source in run["sources"]
                     if source["name"] == base_path.name]
        if snapshots:
            snapshot = snapshots[0]
            archived_path = (out / snapshot["path"]).resolve()
            if not archived_path.is_relative_to(out.resolve()):
                raise EvidenceError("unsafe_base_source_snapshot_path")
            archived = archived_path.read_bytes()
            if sha(archived) != snapshot["sha256"]:
                raise EvidenceError("base_source_snapshot_hash_mismatch")
            if archived.replace(b"\r\n", b"\n") != base_source.replace(b"\r\n", b"\n"):
                raise EvidenceError("base_classifier_source_mismatch")
            # Preserve the recorded hash when Git changes only checkout line endings.
            base_source = archived
    names = ("normalize_whitespace", "parse_date", "reconstruct_abstract",
             "classify_architecture_kind", "classify_record", "merge_records", "scope_period_summary")
    material = "\n".join(inspect.getsource(getattr(classifier, name)) for name in names)
    material += "\n".join(inspect.getsource(function) for function in (corrected_reason, identity, replay))
    return sha(material.encode() + base_source)


def configuration(classifier, per_page: int = 100, out: Path | None = None) -> dict:
    specs = {q.query_id: q for q in classifier.QUERY_SPECS}
    return {"schema_version": SCHEMA, "start_date": START, "end_date": END,
            "filter": FILTER, "select": list(FIELDS), "per_page": per_page,
            "queries": [asdict(specs[q]) for q in QUERY_IDS],
            "classifier_sha256": classifier_hash(classifier, out)}


class PageStore:
    def __init__(self, out: Path, config: dict):
        self.out, self.config = out, config
        self.specs = {q["query_id"]: q for q in config["queries"]}
        path = out / "manifest.json"
        if path.exists():
            self.manifest = read_json(path)
            if self.manifest["configuration"] != config:
                raise EvidenceError("resume_configuration_or_classifier_mismatch")
        else:
            if any(out.iterdir()):
                unrelated = [p for p in out.iterdir() if p.name != ".collector.lock"]
                if unrelated:
                    raise EvidenceError("refusing_nonempty_historical_output_directory")
            self.manifest = {"schema_version": SCHEMA, "created_at": utcnow(),
                             "configuration": config, "pages": [], "software_runs": [],
                             "artifacts": {}, "status": "partial"}
        self.pages = {q: [] for q in self.specs}
        self.errors: dict[str, str] = {}
        self.recover()

    def save(self) -> None:
        self.manifest["updated_at"] = utcnow()
        atomic_json(self.out / "manifest.json", self.manifest)

    def snapshot_software(self, classifier) -> None:
        files = [Path(__file__), Path(classifier.__file__), Path(classifier.base.__file__)]
        sources = []
        for file in files:
            data = file.read_bytes()
            digest = sha(data)
            name = f"provenance/{file.stem}.{digest[:16]}.py"
            if not (self.out / name).exists():
                atomic_bytes(self.out / name, data)
            sources.append({"name": file.name, "path": name, "sha256": digest})
        self.manifest["software_runs"].append({"timestamp": utcnow(), "python": sys.version,
                                               "httpx": httpx.__version__, "sources": sources})
        self.save()

    def params(self, query_id: str, cursor: str) -> dict:
        return {"search": self.specs[query_id]["search_text"], "filter": FILTER,
                "select": ",".join(FIELDS), "per_page": self.config["per_page"], "cursor": cursor}

    def recover(self) -> None:
        indexed = {p["path"]: p for p in self.manifest["pages"]}
        found = set()
        rebuilt = []
        for query_id in self.specs:
            files = sorted((self.out / "pages" / query_id).glob("*.json.gz"))
            expected_cursor = "*"
            seen_cursors = set()
            for number, path in enumerate(files, start=1):
                relative = path.relative_to(self.out).as_posix()
                digest = sha(path.read_bytes())
                if relative in indexed and indexed[relative]["sha256"] != digest:
                    raise EvidenceError(f"page_hash_mismatch:{relative}")
                page = read_page(path)
                if path.name != f"{number:05d}.json.gz" or page["page_number"] != number:
                    raise EvidenceError(f"noncontiguous_pages:{query_id}")
                if page["query_id"] != query_id or page["request"] != self.params(query_id, expected_cursor):
                    raise EvidenceError(f"page_request_or_cursor_mismatch:{query_id}:{number}")
                if expected_cursor is None or expected_cursor in seen_cursors:
                    raise EvidenceError(f"cursor_cycle_or_page_after_terminal:{query_id}")
                seen_cursors.add(expected_cursor)
                descriptor = self.descriptor(relative, digest, page)
                if descriptor["next_cursor"] in seen_cursors or (
                        descriptor["next_cursor"] is not None and descriptor["raw_hits"] == 0):
                    raise EvidenceError(f"cursor_cycle_or_empty_nonterminal_page:{query_id}")
                self.pages[query_id].append(descriptor)
                rebuilt.append(descriptor)
                found.add(relative)
                expected_cursor = page["response"]["meta"]["next_cursor"]
        if set(indexed) - found:
            raise EvidenceError("manifest_references_missing_pages")
        unexpected = set((self.out / "pages").glob("*/*.json.gz")) - {
            self.out / item["path"] for item in rebuilt}
        if unexpected:
            raise EvidenceError("unrecognized_query_pages")
        self.manifest["pages"] = rebuilt
        self.save()

    @staticmethod
    def descriptor(relative: str, digest: str, page: dict) -> dict:
        meta = page["response"]["meta"]
        return {"path": relative, "sha256": digest, "query_id": page["query_id"],
                "page_number": page["page_number"], "retrieved_at": page["retrieved_at"],
                "attempt_id": page["attempt_id"], "cursor": page["request"]["cursor"],
                "next_cursor": meta["next_cursor"], "total_reported": int(meta["count"]),
                "raw_hits": len(page["response"]["results"])}

    def commit(self, query_id: str, cursor: str, payload: dict, attempt_id: int, headers: dict) -> None:
        number = len(self.pages[query_id]) + 1
        relative = f"pages/{query_id}/{number:05d}.json.gz"
        if (self.out / relative).exists():
            raise EvidenceError("refusing_page_overwrite")
        page = {"schema_version": SCHEMA, "query_id": query_id, "page_number": number,
                "retrieved_at": utcnow(), "attempt_id": attempt_id,
                "request": self.params(query_id, cursor), "rate_headers": headers,
                "response": {"meta": payload["meta"], "results": payload["results"]}}
        data = gzip.compress(json_bytes(page), mtime=0)
        atomic_bytes(self.out / relative, data)
        descriptor = self.descriptor(relative, sha(data), page)
        self.pages[query_id].append(descriptor)
        self.manifest["pages"].append(descriptor)
        self.save()
        self.write_progress()

    def cursor(self, query_id: str) -> str | None:
        pages = self.pages[query_id]
        return pages[-1]["next_cursor"] if pages else "*"

    def query_summary(self) -> list[dict]:
        rows = []
        for query_id, spec in self.specs.items():
            pages = self.pages[query_id]
            counts = sorted({p["total_reported"] for p in pages})
            hits = sum(p["raw_hits"] for p in pages)
            exhausted = bool(pages) and pages[-1]["next_cursor"] is None
            matches = bool(counts) and len(counts) == 1 and hits == counts[0]
            rows.append({"query_id": query_id, "bucket": spec["bucket"],
                         "search_text": spec["search_text"],
                         "total_reported_first": pages[0]["total_reported"] if pages else None,
                         "total_reported_last": pages[-1]["total_reported"] if pages else None,
                         "reported_counts_seen": "|".join(map(str, counts)),
                         "pages_fetched": len(pages), "raw_hits": hits,
                         "no_more_cursor": exhausted, "fetched_matches_total": matches,
                         "complete": exhausted and matches,
                         "error": self.errors.get(query_id, "")})
        return rows

    def write_progress(self) -> dict:
        rows = self.query_summary()
        progress = {"updated_at": utcnow(), "completed_queries": sum(r["complete"] for r in rows),
                    "query_count": len(rows), "pages_saved": len(self.manifest["pages"]),
                    "raw_hits": sum(r["raw_hits"] for r in rows), "queries": rows}
        atomic_json(self.out / "progress.json", progress)
        write_csv(self.out / "query_summary.csv", rows)
        return progress


class Budget:
    def __init__(self, out: Path, cap: float, margin: float, refresh_every: int = 10):
        self.path = out / "budget.json"
        self.cap, self.margin = dollars(cap), dollars(margin)
        if not 0 < self.cap <= 950_000 or self.margin < 10_000:
            raise EvidenceError("cap_must_be_at_most_0.95_and_margin_at_least_0.01")
        self.data = read_json(self.path) if self.path.exists() else {
            "attempts": [], "rate_checks": [], "snapshots": [], "stop_reason": None}
        self.data["run_cap_usd"] = self.cap / 1e6
        self.data["free_allowance_safety_margin_usd"] = self.margin / 1e6
        # Pending attempts from a crash remain fully charged in the local bound.
        for attempt in self.data["attempts"]:
            if attempt["status"] == "reserved":
                attempt["status"] = "interrupted_unknown_charge"
        self.lock = asyncio.Lock()
        self.pending: set[int] = set()
        self.remaining = 0
        self.price = 1000
        self.credit_unit = Decimal("0.0001")
        self.day: str | None = None
        self.last_check = -refresh_every
        self.last_check_time = 0.0
        self.refresh_every = refresh_every
        self.stopped: str | None = None
        self.save()

    @property
    def spent_bound(self) -> int:
        return sum(a["accounted_microdollars"] for a in self.data["attempts"])

    def save(self) -> None:
        self.data["accounted_cost_upper_bound_usd"] = self.spent_bound / 1e6
        self.data["attempt_count"] = len(self.data["attempts"])
        atomic_json(self.path, self.data)

    def stop(self, reason: str) -> None:
        self.stopped = reason
        self.data["stop_reason"] = reason
        self.save()

    async def refresh(self, client: httpx.AsyncClient) -> None:
        for retry in range(3):
            entry = {"requested_at": utcnow(), "status": "reserved"}
            self.data["rate_checks"].append(entry)
            self.save()
            try:
                response = await client.get(API + "/rate-limit")
                entry["status"] = response.status_code
                if response.status_code != 200:
                    raise ValueError("rate_status")
                source = response.json()["rate_limit"]
                snapshot = {k: source[k] for k in RATE_FIELDS if k in source}
                snapshot["retrieved_at"] = utcnow()
                remaining = min(dollars(source["daily_remaining_usd"]),
                                1_000_000 - dollars(source["daily_used_usd"]))
                price = dollars(source["endpoint_costs_usd"]["search"])
                if price <= 0 or remaining < 0:
                    raise ValueError("invalid_allowance")
                current_day = datetime.now(timezone.utc).date().isoformat()
                if self.day is not None and self.day != current_day:
                    self.stop("UTC_day_changed_no_automatic_next_day_collection")
                    raise BudgetStop(self.stopped)
                pending = sum(self.data["attempts"][i - 1]["accounted_microdollars"] for i in self.pending)
                floor = remaining - pending
                self.remaining = floor if self.day is None else min(self.remaining, floor)
                self.day, self.price = current_day, price
                if source.get("credits_limit"):
                    self.credit_unit = Decimal(str(source["daily_budget_usd"])) / Decimal(str(source["credits_limit"]))
                self.data["snapshots"].append(snapshot)
                self.data["stop_reason"] = None
                self.last_check = len(self.data["attempts"])
                self.last_check_time = time.monotonic()
                self.save()
                return
            except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
                entry["error_type"] = type(exc).__name__
                self.save()
                if retry < 2:
                    await asyncio.sleep(2 ** retry)
        self.stop("rate_limit_check_failed")
        raise BudgetStop(self.stopped)

    async def reserve(self, client: httpx.AsyncClient, query_id: str, page: int) -> int:
        async with self.lock:
            if self.stopped:
                raise BudgetStop(self.stopped)
            if (self.day is None or len(self.data["attempts"]) - self.last_check >= self.refresh_every
                    or time.monotonic() - self.last_check_time >= 60):
                await self.refresh(client)
            if self.day != datetime.now(timezone.utc).date().isoformat():
                self.stop("UTC_day_changed_no_automatic_next_day_collection")
                raise BudgetStop(self.stopped)
            if self.spent_bound + self.price > self.cap:
                self.stop("run_cap_reached")
                raise BudgetStop(self.stopped)
            if self.remaining - self.price < self.margin:
                self.stop("free_daily_allowance_safety_margin_reached")
                raise BudgetStop(self.stopped)
            number = len(self.data["attempts"]) + 1
            self.data["attempts"].append({"attempt_id": number, "query_id": query_id,
                "page_number": page, "requested_at": utcnow(), "status": "reserved",
                "accounted_microdollars": self.price})
            self.pending.add(number)
            self.remaining -= self.price
            self.save()
            return number

    async def finish(self, number: int, status: int | str, headers: dict, meta: dict | None = None) -> None:
        async with self.lock:
            item = self.data["attempts"][number - 1]
            item.update({"status": status, "finished_at": utcnow(), "rate_headers": headers})
            self.pending.discard(number)
            costs = []
            if meta and meta.get("cost_usd") is not None:
                costs.append(dollars(meta["cost_usd"]))
            if headers.get("x-ratelimit-credits-used") is not None:
                costs.append(dollars(Decimal(headers["x-ratelimit-credits-used"]) * self.credit_unit))
            if costs:
                actual = max(costs)
                item["reported_cost_usd"] = actual / 1e6
                extra = max(0, actual - item["accounted_microdollars"])
                item["accounted_microdollars"] += extra
                self.remaining -= extra
                if extra:
                    self.stop("endpoint_cost_changed")
            if headers.get("x-ratelimit-remaining") is not None:
                header_remaining = dollars(Decimal(headers["x-ratelimit-remaining"]) * self.credit_unit)
                pending = sum(self.data["attempts"][i - 1]["accounted_microdollars"] for i in self.pending)
                self.remaining = min(self.remaining, header_remaining - pending)
            self.save()


def safe_headers(response: httpx.Response) -> dict:
    return {key: response.headers[key] for key in SAFE_HEADERS if key in response.headers}


async def fetch_page(client, store, budget, query_id, args):
    cursor = store.cursor(query_id)
    page_number = len(store.pages[query_id]) + 1
    for retry in range(args.max_retries + 1):
        attempt = await budget.reserve(client, query_id, page_number)
        status: int | str = "transport_error"
        headers, payload = {}, None
        try:
            response = await client.get(API + "/works", params=store.params(query_id, cursor))
            status, headers = response.status_code, safe_headers(response)
            if status == 200:
                payload = response.json()
                if not isinstance(payload.get("results"), list) or not isinstance(payload.get("meta"), dict):
                    raise ValueError("invalid_page_schema")
                meta = payload["meta"]
                if (not isinstance(meta.get("count"), int) or meta["count"] < 0
                        or "next_cursor" not in meta
                        or (meta["next_cursor"] is not None and not isinstance(meta["next_cursor"], str))
                        or any(not isinstance(r, dict) for r in payload["results"])):
                    raise ValueError("invalid_page_metadata")
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            status = type(exc).__name__
            payload = None
        await budget.finish(attempt, status, headers, payload.get("meta") if payload else None)
        if payload is not None and status == 200:
            store.commit(query_id, cursor, payload, attempt, headers)
            if len(store.manifest["pages"]) % 25 == 0:
                hits = sum(p["raw_hits"] for p in store.manifest["pages"])
                print(f"[checkpoint] pages={len(store.manifest['pages'])} raw={hits} "
                      f"cost_bound=${budget.spent_bound / 1e6:.4f}", flush=True)
            if payload["meta"]["next_cursor"] == cursor or (
                    payload["meta"]["next_cursor"] is not None and not payload["results"]):
                raise EvidenceError("cursor_cycle_or_empty_nonterminal_page")
            return
        if status in (401, 403):
            budget.stop(f"authentication_http_{status}")
            raise BudgetStop(budget.stopped)
        if isinstance(status, int) and status not in (408, 429, 500, 502, 503, 504):
            raise EvidenceError(f"nonretryable_http_{status}")
        if retry == args.max_retries:
            raise EvidenceError(f"retry_limit:{status}")
        delay = min(30, 2 ** retry + random.random())
        try:
            delay = min(60, max(delay, float(headers.get("retry-after", 0))))
        except ValueError:
            pass
        await asyncio.sleep(delay)


def estimate(store: PageStore, budget: Budget) -> dict:
    rows = []
    for q in store.query_summary():
        total = q["total_reported_first"]
        pages = None if total is None else max(1, math.ceil(total / store.config["per_page"]))
        # Most OpenAlex cursors require an additional empty terminal response.
        rows.append({"query_id": q["query_id"], "total_reported": total,
                     "data_pages_estimate": pages,
                     "pages_including_terminal_allowance": None if pages is None else pages + 1})
    known = all(r["total_reported"] is not None for r in rows)
    result = {"estimated_at": utcnow(), "all_first_pages_available": known, "queries": rows,
              "search_page_cost_usd": budget.price / 1e6,
              "pages_already_saved": len(store.manifest["pages"]),
              "first_pages_are_reused": True}
    if known:
        pages = sum(r["pages_including_terminal_allowance"] for r in rows)
        remaining = max(0, pages - len(store.manifest["pages"]))
        result.update({"total_hits_estimate": sum(r["total_reported"] for r in rows),
                       "pages_including_terminal_allowance": pages,
                       "additional_cost_estimate_usd": remaining * budget.price / 1e6,
                       "run_cost_estimate_usd": (budget.spent_bound + remaining * budget.price) / 1e6,
                       "fits_current_safe_budget": remaining * budget.price <= min(
                           budget.cap - budget.spent_bound, budget.remaining - budget.margin)})
    atomic_json(store.out / "cost_estimate.json", result)
    return result


async def collect(store: PageStore, budget: Budget, args, key: str, transport=None) -> None:
    timeout = httpx.Timeout(args.timeout_seconds, connect=min(args.timeout_seconds, 10))
    semaphore = asyncio.Semaphore(args.concurrency)
    async with httpx.AsyncClient(headers={"Authorization": "Bearer " + key,
                                         "User-Agent": "MAS4Sci-evidence-collector/1.0"},
                                 follow_redirects=False, timeout=timeout, transport=transport) as client:
        async with budget.lock:
            await budget.refresh(client)
        async def query(query_id: str, first_only: bool):
            async with semaphore:
                try:
                    while store.cursor(query_id) is not None:
                        await fetch_page(client, store, budget, query_id, args)
                        if first_only:
                            break
                        await asyncio.sleep(args.request_delay_seconds)
                except EvidenceError as exc:
                    store.errors[query_id] = str(exc)
                progress = store.write_progress()
                print(f"[progress] query={query_id} pages={len(store.pages[query_id])} "
                      f"raw={progress['raw_hits']} complete={progress['completed_queries']}/{len(store.specs)} "
                      f"cost_bound=${budget.spent_bound / 1e6:.4f}", flush=True)

        await asyncio.gather(*(query(q, True) for q in store.specs if not store.pages[q]))
        plan = estimate(store, budget)
        print("[estimate] " + json.dumps({k: v for k, v in plan.items() if k != "queries"}), flush=True)
        if not args.first_pages_only and not budget.stopped:
            await asyncio.gather(*(query(q, False) for q in store.specs if store.cursor(q) is not None
                                   and q not in store.errors))
        async with budget.lock:
            stopped = budget.data.get("stop_reason")
            try:
                await budget.refresh(client)
            except BudgetStop:
                pass
            if stopped:
                budget.data["stop_reason"] = stopped
                budget.save()


def valid_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def corrected_reason(record) -> str:
    if record.architecture_kind == "unclear-delete":
        return "unclear_architecture"
    if record.architecture_kind == "out-of-scope-delete":
        return "out_of_scope"
    if not (record.is_llm4science or record.is_ai4science):
        return "not_science_scope"
    return ""


def identity(record, index: int) -> str:
    if record.openalex_id:
        return "openalex:" + record.openalex_id.rstrip("/")
    if record.doi:
        doi = record.doi.lower().strip()
        for prefix in ("https://doi.org/", "http://doi.org/", "http://dx.doi.org/", "doi:"):
            if doi.startswith(prefix):
                doi = doi[len(prefix):]
        return "doi:" + doi
    if record.normalized_title:
        return "title:" + record.normalized_title
    return f"unidentified_occurrence:{index}"


def replay(store: PageStore, classifier) -> dict:
    raw, provenance = [], []
    missing_counts, null_counts = Counter(), Counter()
    query_unique, query_duplicate = {}, {}
    invalid_dates, out_of_window, paratext = [], [], []
    for query_id in store.specs:
        spec, seen = store.specs[query_id], set()
        duplicates = 0
        for descriptor in store.pages[query_id]:
            path = store.out / descriptor["path"]
            if sha(path.read_bytes()) != descriptor["sha256"]:
                raise EvidenceError("page_hash_mismatch_during_replay")
            page = read_page(path)
            for item_index, item in enumerate(page["response"]["results"]):
                missing = [field for field in FIELDS if field not in item]
                nulls = [field for field in FIELDS if field in item and not item[field]]
                missing_counts.update(missing)
                null_counts.update(nulls)
                record = classifier.classify_record(item, query_id, spec["bucket"], spec["search_text"])
                position = len(raw)
                key = identity(record, position)
                duplicates += key in seen
                seen.add(key)
                raw.append(record)
                provenance.append({"occurrence_index": position, "page_path": descriptor["path"],
                                   "item_index": item_index, "missing_source_fields": missing,
                                   "null_or_empty_source_fields": nulls, "identity": key})
                publication = valid_date(record.publication_date)
                if publication is None:
                    invalid_dates.append(position)
                elif not date.fromisoformat(START) <= publication <= date.fromisoformat(END):
                    out_of_window.append(position)
                if record.work_type == "paratext":
                    paratext.append(position)
        query_unique[query_id], query_duplicate[query_id] = len(seen), duplicates

    legacy = classifier.merge_records(copy.deepcopy(raw))
    # Normalize only fallback identities, then reuse the historical priority merge.
    keyed = copy.deepcopy(raw)
    original_ids = {}
    for i, record in enumerate(keyed):
        key = identity(record, i)
        original_ids.setdefault(key, record.openalex_id)
        record.openalex_id = key
    corrected = classifier.merge_records(keyed)
    merged_keys = []
    stale = []
    for record in corrected:
        key = record.openalex_id
        merged_keys.append(key)
        record.openalex_id = original_ids[key]
        reason = corrected_reason(record)
        if record.exclude_reason != reason:
            stale.append({"identity": key, "old_exclude_reason": record.exclude_reason,
                          "corrected_exclude_reason": reason})
        record.exclude_reason = reason

    def periods(records, include_unclear):
        usable = [r for r in records if valid_date(r.publication_date) is not None
                  and (include_unclear or r.exclude_reason == "")]
        return {name: {scope: classifier.scope_period_summary(usable, scope, start, end)
                       for scope in ("ai4science", "llm4science")}
                for name, start, end in classifier.PERIODS}

    results = {"legacy_exact": periods(legacy, True),
               "bookkeeping_corrected": periods(corrected, False)}
    raw_rows = [dict(asdict(record), **meta) for record, meta in zip(raw, provenance)]
    by_key: dict[str, list[int]] = {}
    for meta in provenance:
        by_key.setdefault(meta["identity"], []).append(meta["occurrence_index"])
    corrected_rows = []
    for record, key in zip(corrected, merged_keys):
        row = asdict(record)
        row.update({"identity": key, "occurrence_indices": by_key[key],
                    "included_ai4science": record.is_ai4science and record.exclude_reason == "",
                    "included_llm4science": record.is_llm4science and record.exclude_reason == "",
                    "missing_source_fields": sorted({field for i in by_key[key]
                                                       for field in provenance[i]["missing_source_fields"]}),
                    "null_or_empty_source_fields": sorted({field for i in by_key[key]
                        for field in provenance[i]["null_or_empty_source_fields"]})})
        corrected_rows.append(row)
    compressed_jsonl(store.out / "classified_occurrences.jsonl.gz", raw_rows)
    compressed_jsonl(store.out / "deduplicated_legacy.jsonl.gz", [asdict(r) for r in legacy])
    compressed_jsonl(store.out / "deduplicated_corrected.jsonl.gz", corrected_rows)
    rows = store.query_summary()
    for row in rows:
        row["unique_identities"] = query_unique[row["query_id"]]
        row["duplicate_occurrences_within_query"] = query_duplicate[row["query_id"]]
        row["complete"] = row["complete"] and not row["duplicate_occurrences_within_query"]
    write_csv(store.out / "query_summary.csv", rows)
    complete = all(r["complete"] for r in rows) and not invalid_dates and not out_of_window and not paratext
    audit = {"raw_occurrences": len(raw), "deduplicated_legacy": len(legacy),
             "deduplicated_corrected": len(corrected),
             "missing_source_field_occurrences": dict(missing_counts),
             "null_or_empty_source_field_occurrences": dict(null_counts),
             "invalid_date_occurrence_indices": invalid_dates, "out_of_window_occurrence_indices": out_of_window,
             "paratext_occurrence_indices": paratext, "stale_exclude_reason_repairs": stale,
             "unclear_deduplicated_legacy": sum(r.architecture_kind == "unclear-delete" for r in legacy),
             "corrected_exclude_reasons": dict(Counter(r.exclude_reason or "included" for r in corrected)),
             "classification_method": "original lexical rules; no human audit; not a strict swarm classifier",
             "rubric_changes": [], "all_queries_validated_complete": complete,
             "query_duplicate_occurrences": query_duplicate}
    atomic_json(store.out / "classification_audit.json", audit)
    budget_data = read_json(store.out / "budget.json") if (store.out / "budget.json").exists() else {}
    snapshots = budget_data.get("snapshots", [])
    summary = {"source": "openalex", "status": "complete" if complete else "partial",
               "time_window": {"start_date": START, "end_date": END},
               "period_definitions": {name: {"start": start.isoformat(), "end": end.isoformat()}
                                      for name, start, end in classifier.PERIODS},
               "query_count": len(rows), "completed_queries": sum(r["complete"] for r in rows),
               "raw_retrieved": len(raw), "after_dedup": len(corrected),
               "pages_saved": len(store.manifest["pages"]),
               "classifier_sha256": store.config["classifier_sha256"],
               "estimates": results,
               "estimate_definitions": {
                   "legacy_exact": "Original lexical classifier, priority merge (including stale exclusion), and denominator (including unclear lexical matches).",
                   "bookkeeping_corrected": "Same lexical rubric; recompute exclusion after merge; exclude unclear records; normalize DOI fallback; never merge unidentified records. Includes methods, surveys/perspectives, benchmarks/datasets."},
               "cost": {"attempt_count": budget_data.get("attempt_count"),
                        "accounted_upper_bound_usd": budget_data.get("accounted_cost_upper_bound_usd"),
                        "reported_request_cost_usd": sum(a.get("reported_cost_usd", 0) for a in budget_data.get("attempts", [])),
                        "initial_daily_used_usd": snapshots[0]["daily_used_usd"] if snapshots else None,
                        "final_daily_used_usd": snapshots[-1]["daily_used_usd"] if snapshots else None,
                        "final_daily_remaining_usd": snapshots[-1]["daily_remaining_usd"] if snapshots else None,
                        "stop_reason": budget_data.get("stop_reason")},
               "interpretation": "Keyword-defined proportions in the fixed query-retrieved corpus, not field-wide prevalence or verified swarm architectures."}
    atomic_json(store.out / "summary.json", summary)
    table = []
    for estimate_name, period_data in results.items():
        for period, scopes in period_data.items():
            for scope, values in scopes.items():
                table.append({"estimate": estimate_name, "period": period, "scope": scope,
                              "numerator": values["multi_agent"], "denominator": values["denominator"],
                              "percent": values["ma_share_all"] * 100})
    write_csv(store.out / "period_proportions.csv", table)
    store.manifest["status"] = summary["status"]
    for name in ("classified_occurrences.jsonl.gz", "deduplicated_legacy.jsonl.gz",
                 "deduplicated_corrected.jsonl.gz", "summary.json", "classification_audit.json",
                 "query_summary.csv", "period_proportions.csv"):
        data = (store.out / name).read_bytes()
        store.manifest["artifacts"][name] = {"sha256": sha(data), "bytes": len(data)}
    store.save()
    return summary


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--mode", choices=("collect", "replay", "validate"), default="collect")
    parser.add_argument("--first-pages-only", action="store_true", help="Live smoke and cost estimate; pages are reused on resume.")
    parser.add_argument("--prompt-key", action="store_true", help="Read key without echo; otherwise use OPENALEX_API_KEY.")
    parser.add_argument("--run-cap-usd", type=float, default=0.95)
    parser.add_argument("--free-margin-usd", type=float, default=0.05)
    parser.add_argument("--concurrency", type=int, choices=(1, 2, 3), default=3)
    parser.add_argument("--per-page", type=int, choices=range(1, 101), default=100)
    parser.add_argument("--timeout-seconds", type=float, default=60)
    parser.add_argument("--request-delay-seconds", type=float, default=0.2)
    parser.add_argument("--max-retries", type=int, default=4)
    parser.add_argument("--start-date", choices=(START,), default=START)
    parser.add_argument("--end-date", choices=(END,), default=END)
    parser.add_argument("--query-id", action="append", dest="query_ids", choices=QUERY_IDS)
    args = parser.parse_args(argv)
    if args.query_ids and set(args.query_ids) != set(QUERY_IDS):
        parser.error("This rerun requires exactly the original 17 query IDs.")
    if args.timeout_seconds <= 0 or args.max_retries < 0 or args.request_delay_seconds < 0:
        parser.error("Timeout must be positive; retries and delay must be nonnegative.")
    if args.mode != "collect" and args.out_dir is None:
        parser.error("Offline modes require --out-dir.")
    if args.out_dir is None:
        args.out_dir = ROOT / "results" / ("openalex_rerun_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"))
    args.out_dir = args.out_dir.resolve()
    if not args.out_dir.is_relative_to(ROOT):
        parser.error("Output must stay inside analysis/trend_of_mas4sci.")
    return args


def main(classifier, argv=None) -> int:
    args = parse_args(argv)
    try:
        if args.mode != "collect" and not (args.out_dir / "manifest.json").exists():
            raise EvidenceError("missing_manifest_for_offline_mode")
        with output_lock(args.out_dir):
            store = PageStore(args.out_dir, configuration(classifier, args.per_page, args.out_dir))
            if args.mode == "validate":
                for name, expected in store.manifest["artifacts"].items():
                    if sha((store.out / name).read_bytes()) != expected["sha256"]:
                        raise EvidenceError(f"artifact_hash_mismatch:{name}")
                for run in store.manifest["software_runs"]:
                    for source in run["sources"]:
                        if sha((store.out / source["path"]).read_bytes()) != source["sha256"]:
                            raise EvidenceError("source_snapshot_hash_mismatch")
                expected = read_json(store.out / "summary.json")
                actual = replay(store, classifier)
                if actual != expected:
                    raise EvidenceError("summary_does_not_reproduce")
                print(json.dumps({"validated": True, "status": actual["status"],
                                  "queries": actual["completed_queries"], "raw_hits": actual["raw_retrieved"]}))
                return 0 if actual["status"] == "complete" else 2
            if args.mode == "collect":
                store.snapshot_software(classifier)
                budget = Budget(store.out, args.run_cap_usd, args.free_margin_usd)
                key = getpass.getpass("OpenAlex key (not echoed): ") if args.prompt_key else os.getenv("OPENALEX_API_KEY")
                if not key:
                    raise EvidenceError("missing_key_use_prompt_key_or_OPENALEX_API_KEY")
                try:
                    asyncio.run(collect(store, budget, args, key))
                finally:
                    key = None
            summary = replay(store, classifier)
            print(json.dumps(summary, indent=2), flush=True)
            print(f"OUTPUT_DIR={store.out}", flush=True)
            return 0 if summary["status"] == "complete" or args.first_pages_only else 2
    except KeyboardInterrupt:
        print("Stopped; saved pages and reserved costs are resumable.", file=sys.stderr)
        return 130
    except EvidenceError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        # HTTP error representations may contain URLs or headers. Never print them.
        print(f"ERROR: {type(exc).__name__}; evidence retained for inspection.", file=sys.stderr)
        return 1
