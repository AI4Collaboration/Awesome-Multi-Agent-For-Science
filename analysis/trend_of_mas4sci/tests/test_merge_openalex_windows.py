import gzip
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/merge_openalex_windows.py"
spec = importlib.util.spec_from_file_location("window_merge", SCRIPT)
merge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(merge)


class WindowMergeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.logical = [{"query_id": f"Q{i}", "bucket": "broad", "search_text": f'"term {i}"'} for i in range(17)]
        self.initial = self.root / "initial"
        self.extension = self.root / "extension"
        self.output = self.root / "combined"
        self.build(self.initial, "2024-01-01", "2026-04-02", self.logical,
                   [self.record("old24", "2024-03-01", "Q0", 0), self.record("old25", "2025-03-01", "Q0", 1), self.record("old26", "2026-03-01", "Q0", 2)])
        union = " OR ".join("(" + q["search_text"] + ")" for q in self.logical)
        self.build(self.extension, "2026-04-03", "2026-09-01", [{"query_id": "U1", "bucket": "union", "search_text": union}],
                   [self.record("new26", "2026-05-01", "U1", 0)])

    def record(self, key, when, query, index):
        return {"identity": key, "publication_date": when, "query_ids": [query], "occurrence_indices": [index],
                "exclude_reason": "", "is_ai4science": True, "included_ai4science": True,
                "is_llm4science": True, "included_llm4science": True, "architecture_kind": "multi-agent", "document_type": "method-system"}

    def build(self, path, start, end, queries, rows):
        path.mkdir()
        raw = gzip.compress(b"".join((json.dumps(row) + "\n").encode() for row in rows), mtime=0)
        (path / "deduplicated_corrected.jsonl.gz").write_bytes(raw)
        manifest = {"configuration": {"start_date": start, "end_date": end, "queries": queries, "select": ["id"], "classifier_sha256": "fixed"},
                    "artifacts": {"deduplicated_corrected.jsonl.gz": {"sha256": sha256(raw).hexdigest()}}, "pages": [], "software_runs": [{"sources": []}]}
        summary = {p: {s: {"numerator": 1, "denominator": 1, "percent": 100.0} for s in ("ai4science", "llm4science")} for p in ("2024", "2025", "2026_ytd")}
        report = {"validated_complete": True, "deduplicated_records": len(rows), "raw_occurrences": len(rows), "page_count": len(queries),
                  "reported_request_cost_usd_exact": str(len(queries)/1000), "verified_proportions": {"bookkeeping_corrected": summary},
                  "queries": [{"query_id": q["query_id"], "pages": 1, "raw_hits": sum(q["query_id"] in r["query_ids"] for r in rows),
                               "total_reported": sum(q["query_id"] in r["query_ids"] for r in rows), "terminal_cursor": None} for q in queries]}
        merge.write(path / "manifest.json", manifest)
        merge.write(path / "verification.json", report)

    def change_manifest(self, function):
        path = self.extension / "manifest.json"
        data = merge.read(path)
        function(data)
        merge.write(path, data)

    def test_adjacent_merge_offsets_provenance_and_counts(self):
        result = merge.combine(self.initial, self.extension, self.output)
        self.assertEqual(result["deduplicated_records"], 4)
        self.assertEqual(result["verified_proportions"]["bookkeeping_corrected"]["2026_ytd"]["ai4science"]["denominator"], 2)
        with gzip.open(self.output / "deduplicated_corrected.jsonl.gz", "rt") as stream:
            rows = [json.loads(line) for line in stream]
        self.assertEqual(rows[-1]["occurrence_indices"], [3])

    def test_rejects_date_gap(self):
        self.change_manifest(lambda m: m["configuration"].update(start_date="2026-04-04"))
        with self.assertRaises(AssertionError):
            merge.combine(self.initial, self.extension, self.output)

    def test_rejects_changed_query(self):
        self.change_manifest(lambda m: m["configuration"]["queries"][0].update(search_text="other"))
        with self.assertRaises(AssertionError):
            merge.combine(self.initial, self.extension, self.output)

    def test_rejects_changed_classifier(self):
        self.change_manifest(lambda m: m["configuration"].update(classifier_sha256="changed"))
        with self.assertRaises(AssertionError):
            merge.combine(self.initial, self.extension, self.output)

    def test_rejects_corrupted_records(self):
        with (self.extension / "deduplicated_corrected.jsonl.gz").open("ab") as stream:
            stream.write(b"corrupt")
        with self.assertRaises(AssertionError):
            merge.combine(self.initial, self.extension, self.output)

    def test_rejects_incomplete_batch(self):
        path = self.extension / "verification.json"
        data = merge.read(path)
        data["validated_complete"] = False
        merge.write(path, data)
        with self.assertRaises(AssertionError):
            merge.combine(self.initial, self.extension, self.output)

    def test_rejects_cross_window_duplicate_identity(self):
        path = self.extension / "deduplicated_corrected.jsonl.gz"
        row = self.record("old26", "2026-05-01", "U1", 0)
        raw = gzip.compress((json.dumps(row) + "\n").encode(), mtime=0)
        path.write_bytes(raw)
        self.change_manifest(lambda m: m["artifacts"][path.name].update(sha256=sha256(raw).hexdigest()))
        with self.assertRaisesRegex(AssertionError, "both nonoverlapping windows"):
            merge.combine(self.initial, self.extension, self.output)


if __name__ == "__main__":
    unittest.main()
