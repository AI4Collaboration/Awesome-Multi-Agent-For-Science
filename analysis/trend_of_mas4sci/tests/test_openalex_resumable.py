"""Offline tests; all temporary evidence stays within the authorized directory."""

import asyncio
import copy
import gzip
import json
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from contextlib import redirect_stdout

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import openalex_mas4sci_from_2024 as legacy
import openalex_resumable as collector
import verify_openalex_evidence as verifier
import sanitize_openalex_history as sanitizer


def work(identifier="W1", title="Multi-agent LLM scientific discovery", abstract="Large language models for scientific research"):
    inverted = {}
    for index, token in enumerate(abstract.split()):
        inverted.setdefault(token, []).append(index)
    return {"id": "https://openalex.org/" + identifier if identifier else None,
            "display_name": title, "publication_date": "2024-04-01", "publication_year": 2024,
            "type": "article", "abstract_inverted_index": inverted or None, "doi": None}


def payload(items, total=None, cursor=None):
    return {"meta": {"count": len(items) if total is None else total,
                     "next_cursor": cursor, "cost_usd": 0.001}, "results": items}


def rate(remaining=1, used=0):
    return {"api_key": "DO_NOT_SAVE", "rate_limit": {
        "daily_budget_usd": 1, "daily_used_usd": used, "daily_remaining_usd": remaining,
        "prepaid_balance_usd": 50, "prepaid_remaining_usd": 50,
        "resets_at": "2099-01-01T00:00:00Z", "credits_limit": 10000,
        "endpoint_costs_usd": {"search": 0.001}}}


class LocalFixture:
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix=".openalex-test-", dir=ROOT / "tests")
        self.out = Path(self.temp.name)
        self.config = collector.configuration(legacy)

    def tearDown(self):
        self.temp.cleanup()

    def store(self):
        return collector.PageStore(self.out, self.config)


class LocalCase(LocalFixture, unittest.TestCase):
    def test_protocol_is_exact(self):
        self.assertEqual(tuple(q["query_id"] for q in self.config["queries"]), collector.QUERY_IDS)
        self.assertEqual(len(self.config["queries"]), 17)
        self.assertEqual(self.config["end_date"], "2026-04-02")
        self.assertEqual(self.config["queries"][-1]["search_text"], "critic reviewer scientific")
        self.assertNotIn("api_key", self.store().params("B1", "*"))

    def test_atomic_orphan_recovery_and_cursor(self):
        store = self.store()
        original = copy.deepcopy(store.manifest)
        store.commit("B1", "*", payload([work()], 2, "cursor2"), 1, {})
        collector.atomic_json(self.out / "manifest.json", original)
        resumed = self.store()
        self.assertEqual(resumed.cursor("B1"), "cursor2")
        resumed.commit("B1", "cursor2", payload([work("W2")], 2), 2, {})
        final = self.store()
        self.assertTrue(final.query_summary()[0]["complete"])
        self.assertIsNone(final.cursor("B1"))

    def test_corrupt_or_missing_pages_fail_closed(self):
        store = self.store()
        store.commit("B1", "*", payload([work()]), 1, {})
        path = self.out / store.manifest["pages"][0]["path"]
        path.write_bytes(b"broken")
        with self.assertRaisesRegex(collector.EvidenceError, "hash_mismatch"):
            self.store()
        path.unlink()
        with self.assertRaisesRegex(collector.EvidenceError, "missing_pages"):
            self.store()

    def test_changed_config_refused(self):
        self.store()
        config = copy.deepcopy(self.config)
        config["per_page"] = 50
        with self.assertRaisesRegex(collector.EvidenceError, "configuration"):
            collector.PageStore(self.out, config)

    def test_archived_hash_survives_checkout_line_endings(self):
        store = self.store()
        store.snapshot_software(legacy)
        original = Path(legacy.base.__file__).read_bytes()
        alternate = original.replace(b"\r\n", b"\n") if b"\r\n" in original else original.replace(b"\n", b"\r\n")
        self.assertNotEqual(original, alternate)
        checkout = self.out / "checkout" / Path(legacy.base.__file__).name
        collector.atomic_bytes(checkout, alternate)
        with patch.object(legacy.base, "__file__", str(checkout)):
            self.assertEqual(collector.configuration(legacy, out=self.out), self.config)
            self.assertNotEqual(collector.configuration(legacy), self.config)

    def test_changed_base_source_refused_even_with_snapshot(self):
        store = self.store()
        store.snapshot_software(legacy)
        checkout = self.out / "checkout" / Path(legacy.base.__file__).name
        collector.atomic_bytes(checkout, Path(legacy.base.__file__).read_bytes() + b"\n# changed\n")
        with patch.object(legacy.base, "__file__", str(checkout)):
            with self.assertRaisesRegex(collector.EvidenceError, "base_classifier_source_mismatch"):
                collector.configuration(legacy, out=self.out)

    def test_corrupt_archived_base_source_refused(self):
        store = self.store()
        store.snapshot_software(legacy)
        snapshot = next(s for s in store.manifest["software_runs"][0]["sources"]
                        if s["name"] == Path(legacy.base.__file__).name)
        collector.atomic_bytes(self.out / snapshot["path"], b"corrupt")
        with self.assertRaisesRegex(collector.EvidenceError, "base_source_snapshot_hash_mismatch"):
            collector.configuration(legacy, out=self.out)

    def test_cursor_cycle_refused_on_resume(self):
        store = self.store()
        store.commit("B1", "*", payload([work()], 2, "*"), 1, {})
        with self.assertRaisesRegex(collector.EvidenceError, "cursor_cycle"):
            self.store()

    def test_historical_output_refused(self):
        collector.atomic_json(self.out / "summary.json", {"old": True})
        with self.assertRaisesRegex(collector.EvidenceError, "historical"):
            self.store()

    def test_duplicate_gap_and_total_drift_not_complete(self):
        store = self.store()
        store.commit("B1", "*", payload([work(), work()], 2), 1, {})
        result = collector.replay(store, legacy)
        self.assertEqual(result["status"], "partial")
        audit = collector.read_json(self.out / "classification_audit.json")
        self.assertEqual(audit["query_duplicate_occurrences"]["B1"], 1)

    def test_empty_terminal_page_count_and_count_drift(self):
        store = self.store()
        store.commit("B1", "*", payload([work()], 1, "terminal"), 1, {})
        store.commit("B1", "terminal", payload([], 1), 2, {})
        self.assertTrue(store.query_summary()[0]["complete"])
        store.commit("B2", "*", payload([work()], 1, "terminal"), 3, {})
        store.commit("B2", "terminal", payload([], 2), 4, {})
        self.assertFalse(store.query_summary()[1]["complete"])

    def test_out_of_window_and_paratext_fail_completeness(self):
        store = self.store()
        item = work()
        item["publication_date"] = "2026-04-03"
        item["type"] = "paratext"
        for i, query in enumerate(collector.QUERY_IDS):
            store.commit(query, "*", payload([item]), i + 1, {})
        summary = collector.replay(store, legacy)
        self.assertEqual(summary["status"], "partial")
        self.assertEqual(summary["estimates"]["legacy_exact"]["2026_ytd"]["ai4science"]["denominator"], 0)

    def test_unclear_and_stale_exclusion_separately_audited(self):
        store = self.store()
        negative = work("W1", abstract="LLM scientific chemical agent")
        positive = work("W1")
        unclear = work("W2", abstract="")
        store.commit("B1", "*", payload([negative, unclear]), 1, {})
        store.commit("B2", "*", payload([positive]), 2, {})
        result = collector.replay(store, legacy)
        original = result["estimates"]["legacy_exact"]["2024"]["llm4science"]
        corrected = result["estimates"]["bookkeeping_corrected"]["2024"]["llm4science"]
        self.assertEqual((original["multi_agent"], original["denominator"]), (0, 1))
        self.assertEqual((corrected["multi_agent"], corrected["denominator"]), (1, 1))
        audit = collector.read_json(self.out / "classification_audit.json")
        self.assertEqual(len(audit["stale_exclude_reason_repairs"]), 1)
        self.assertEqual(audit["unclear_deduplicated_legacy"], 1)

    def test_missing_fields_and_date_are_explicit(self):
        store = self.store()
        item = work()
        item.pop("doi")
        item["display_name"] = None
        item["publication_date"] = None
        store.commit("B1", "*", payload([item]), 1, {})
        collector.replay(store, legacy)
        audit = collector.read_json(self.out / "classification_audit.json")
        self.assertEqual(audit["missing_source_field_occurrences"], {"doi": 1})
        self.assertEqual(audit["invalid_date_occurrence_indices"], [0])

    def test_inclusive_document_types_and_no_swarm_rubric_change(self):
        for text, kind in (("A survey of LLM scientific agents", "survey-perspective"),
                           ("A dataset for LLM scientific agents", "benchmark-dataset"),
                           ("LLM scientific agents", "method-system")):
            record = legacy.classify_record(work(title=text), "B1", "broad", "x")
            self.assertTrue(record.is_ai4science)
            self.assertEqual(record.document_type, kind)
        # Broad historical triggers are deliberately preserved, not labeled strict swarms.
        record = legacy.classify_record(work(title="Coordination in LLM science"), "B1", "broad", "x")
        self.assertEqual(record.architecture_kind, "multi-agent")

    def test_fallback_keys(self):
        record = legacy.classify_record(work(identifier=""), "B1", "broad", "x")
        record.doi = "https://doi.org/10.1234/ABC"
        self.assertEqual(collector.identity(record, 0), "doi:10.1234/abc")
        record.doi = ""
        self.assertTrue(collector.identity(record, 0).startswith("title:"))
        record.normalized_title = ""
        self.assertNotEqual(collector.identity(record, 0), collector.identity(record, 1))

    def test_complete_replay_is_deterministic(self):
        store = self.store()
        for i, query in enumerate(collector.QUERY_IDS):
            store.commit(query, "*", payload([work("W" + str(i))]), i + 1, {})
        first = collector.replay(store, legacy)
        hashes = copy.deepcopy(store.manifest["artifacts"])
        (self.out / "classified_occurrences.jsonl.gz").unlink()
        second = collector.replay(store, legacy)
        self.assertTrue((self.out / "classified_occurrences.jsonl.gz").exists())
        self.assertEqual(first, second)
        self.assertEqual(hashes, store.manifest["artifacts"])
        self.assertEqual(first["status"], "complete")
        self.assertEqual(first["raw_retrieved"], 17)
        self.assertEqual(first["period_definitions"]["2026_ytd"]["end"], "2026-04-02")

    def test_independent_validation_and_tamper_detection(self):
        store = self.store()
        budget = collector.Budget(self.out, 0.95, 0.05)
        for i, query in enumerate(collector.QUERY_IDS):
            store.commit(query, "*", payload([work("W" + str(i))]), i + 1, {})
            budget.data["attempts"].append({"attempt_id": i + 1, "query_id": query,
                                          "page_number": 1, "status": 200,
                                          "accounted_microdollars": 1000})
        budget.save()
        collector.replay(store, legacy)
        result = verifier.verify(self.out)
        self.assertTrue(result["validated_complete"])
        self.assertEqual(result["raw_occurrences"], 17)
        self.assertEqual(collector.read_json(self.out / "evidence_index.json")["optional_regenerable_files"],
                         ["classified_occurrences.jsonl.gz"])
        summary = collector.read_json(self.out / "summary.json")
        summary["estimates"]["bookkeeping_corrected"]["2024"]["ai4science"]["denominator"] += 1
        collector.atomic_json(self.out / "summary.json", summary)
        with self.assertRaisesRegex(ValueError, "artifact_hash"):
            verifier.verify(self.out)

    def test_credential_scan_uses_only_supplied_in_memory_values(self):
        collector.atomic_json(self.out / "test.json", {"safe": True})
        report = verifier.credential_check(self.out, {b"synthetic-test-credential"})
        self.assertTrue(report["passed"])
        collector.atomic_json(self.out / "test.json", {"bad": "synthetic-test-credential"})
        with self.assertRaisesRegex(ValueError, "credential_found"):
            verifier.credential_check(self.out, {b"synthetic-test-credential"})
        self.assertIsNone(verifier.credential_check(self.out)["passed"])

    def test_historical_redaction_preserves_counts_and_errors(self):
        root = self.out / "project" / "analysis" / "trend_of_mas4sci"
        history = root / "results/openalex_from_2024_cost_conscious/query_summary.csv"
        history.parent.mkdir(parents=True)
        history.write_text('query_id,bucket,total_reported,pages_fetched,raw_hits,errors\n'
                           'B1,broad,10,1,10,\n'
                           'M1,multi-agent,20,1,10,HTTPStatusError 429 https://api.openalex.org/works?api_key=synthetic-test-credential\n', encoding="utf-8")
        with patch.object(sanitizer, "ROOT", root), patch.object(
                sanitizer.subprocess, "check_output",
                return_value=b"analysis/trend_of_mas4sci/results/openalex_from_2024_cost_conscious/query_summary.csv\0"), redirect_stdout(io.StringIO()):
            tokens = sanitizer.sanitize(self.out)
        self.assertEqual(tokens, {b"synthetic-test-credential"})
        self.assertNotIn("synthetic-test-credential", history.read_text())
        self.assertIn("[REDACTED]", history.read_text())
        audit = collector.read_json(self.out / "security_audit.local.json")
        self.assertEqual(audit["url_values_redacted"], 1)
        self.assertTrue(audit["counts_unchanged"])
        self.assertEqual(audit["error_query_ids"], ["M1"])
        self.assertEqual(audit["known_key_match_paths"], [])


class AsyncCase(LocalFixture, unittest.IsolatedAsyncioTestCase):
    async def test_resumed_estimate_refreshes_allowance_without_refetch(self):
        store = self.store()
        for i, query in enumerate(collector.QUERY_IDS):
            store.commit(query, "*", payload([work("W" + str(i))]), i + 1, {})
        budget = collector.Budget(self.out, 0.95, 0.05)
        calls = []
        def handler(request):
            calls.append(request.url.path)
            self.assertEqual(request.url.path, "/rate-limit")
            return httpx.Response(200, json=rate())
        args = collector.parse_args(["--out-dir", str(self.out), "--first-pages-only"])
        with redirect_stdout(io.StringIO()):
            await collector.collect(store, budget, args, "testing-only", httpx.MockTransport(handler))
        plan = collector.read_json(self.out / "cost_estimate.json")
        self.assertTrue(plan["fits_current_safe_budget"])
        self.assertEqual(calls, ["/rate-limit", "/rate-limit"])
        self.assertEqual(budget.spent_bound, 0)

    async def test_inflight_reservations_cannot_exceed_cap(self):
        budget = collector.Budget(self.out, 0.002, 0.05)
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=rate()))) as client:
            results = await asyncio.gather(*(budget.reserve(client, "B1", i) for i in range(3)), return_exceptions=True)
        self.assertEqual(sum(isinstance(r, collector.BudgetStop) for r in results), 1)
        self.assertEqual(budget.spent_bound, 2000)
        saved = collector.read_json(self.out / "budget.json")
        self.assertNotIn("DO_NOT_SAVE", json.dumps(saved))
        self.assertEqual(saved["attempt_count"], 2)

    async def test_prepaid_never_expands_free_allowance(self):
        budget = collector.Budget(self.out, 0.95, 0.05)
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=rate(0.0505, 0.9495)))) as client:
            with self.assertRaises(collector.BudgetStop):
                await budget.reserve(client, "B1", 1)
        self.assertEqual(budget.spent_bound, 0)

    async def test_unknown_failed_request_keeps_full_reservation(self):
        budget = collector.Budget(self.out, 0.003, 0.05)
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=rate()))) as client:
            number = await budget.reserve(client, "B1", 1)
            await budget.finish(number, "ReadTimeout", {})
        restarted = collector.Budget(self.out, 0.003, 0.05)
        self.assertEqual(restarted.spent_bound, 1000)

    async def test_interrupted_reservation_is_not_refunded_on_restart(self):
        budget = collector.Budget(self.out, 0.001, 0.05)
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=rate()))) as client:
            await budget.reserve(client, "B1", 1)
            restarted = collector.Budget(self.out, 0.001, 0.05)
            self.assertEqual(restarted.data["attempts"][0]["status"], "interrupted_unknown_charge")
            with self.assertRaises(collector.BudgetStop):
                await restarted.reserve(client, "B1", 1)

    async def test_external_usage_reduces_allowance(self):
        values = iter([rate(), rate(0.05, 0.95)])
        budget = collector.Budget(self.out, 0.95, 0.05, refresh_every=1)
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=next(values)))) as client:
            first = await budget.reserve(client, "B1", 1)
            await budget.finish(first, 200, {})
            with self.assertRaises(collector.BudgetStop):
                await budget.reserve(client, "B1", 2)
        self.assertEqual(budget.spent_bound, 1000)

    async def test_rate_header_reduces_available_budget(self):
        budget = collector.Budget(self.out, 0.95, 0.05)
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=rate()))) as client:
            first = await budget.reserve(client, "B1", 1)
            await budget.finish(first, 200, {"x-ratelimit-remaining": "500", "x-ratelimit-credits-used": "10"})
            with self.assertRaises(collector.BudgetStop):
                await budget.reserve(client, "B1", 2)

    async def test_budget_api_failure_stops_without_search(self):
        calls = []
        def handler(request):
            calls.append(request.url.path)
            return httpx.Response(503)
        budget = collector.Budget(self.out, 0.95, 0.05)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with patch.object(collector.asyncio, "sleep", new=unittest.mock.AsyncMock()):
                with self.assertRaises(collector.BudgetStop):
                    await budget.reserve(client, "B1", 1)
        self.assertEqual(calls, ["/rate-limit"] * 3)
        self.assertEqual(budget.spent_bound, 0)

    async def test_budget_cost_increase_is_recorded_and_stops(self):
        budget = collector.Budget(self.out, 0.95, 0.05)
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=rate()))) as client:
            first = await budget.reserve(client, "B1", 1)
            await budget.finish(first, 200, {}, {"cost_usd": 0.002})
            with self.assertRaises(collector.BudgetStop):
                await budget.reserve(client, "B1", 2)
        self.assertEqual(budget.spent_bound, 2000)

    async def test_retry_header_auth_and_resume_do_not_refetch_pages(self):
        calls = []
        def handler(request):
            self.assertEqual(request.headers.get("Authorization"), "Bearer testing-only")
            self.assertNotIn("api_key", request.url.params)
            if request.url.path == "/rate-limit":
                return httpx.Response(200, json=rate())
            calls.append(str(request.url.params["cursor"]))
            if len(calls) == 1:
                return httpx.Response(503)
            return httpx.Response(200, json=payload([work()], 1, "end" if request.url.params["cursor"] == "*" else None))

        args = collector.parse_args(["--out-dir", str(self.out), "--max-retries", "1"])
        store, budget = self.store(), collector.Budget(self.out, 0.01, 0.05)
        async with httpx.AsyncClient(headers={"Authorization": "Bearer testing-only"}, transport=httpx.MockTransport(handler)) as client:
            with patch.object(collector.asyncio, "sleep", new=unittest.mock.AsyncMock()):
                await collector.fetch_page(client, store, budget, "B1", args)
            resumed = self.store()
            self.assertEqual(resumed.cursor("B1"), "end")
            await collector.fetch_page(client, resumed, budget, "B1", args)
        self.assertEqual(calls, ["*", "*", "end"])
        self.assertEqual(budget.spent_bound, 3000)

    async def test_errors_never_store_exception_urls(self):
        def handler(request):
            if request.url.path == "/rate-limit":
                return httpx.Response(200, json=rate())
            raise httpx.ReadTimeout("PRIVATE_URL_OR_TOKEN", request=request)
        args = collector.parse_args(["--out-dir", str(self.out), "--max-retries", "0"])
        store, budget = self.store(), collector.Budget(self.out, 0.01, 0.05)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with self.assertRaisesRegex(collector.EvidenceError, "ReadTimeout"):
                await collector.fetch_page(client, store, budget, "B1", args)
        self.assertNotIn("PRIVATE_URL_OR_TOKEN", (self.out / "budget.json").read_text())


if __name__ == "__main__":
    unittest.main()
