"""Fetch and preserve first pages to price an April 3--September 30 extension."""

import argparse
import asyncio
import os
from pathlib import Path
from types import SimpleNamespace

import openalex_mas4sci_from_2024 as classifier
import openalex_resumable as core


class WindowStore(core.PageStore):
    def params(self, query_id, cursor):
        return {"search": self.specs[query_id]["search_text"],
                "filter": self.config["filter"],
                "select": ",".join(self.config["select"]),
                "per_page": self.config["per_page"], "cursor": cursor}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args()
    out = args.out_dir.resolve()
    if not out.is_relative_to(core.ROOT):
        raise core.EvidenceError("output_outside_analysis_directory")
    key = os.environ.get("OPENALEX_API_KEY")
    if not key:
        raise core.EvidenceError("OPENALEX_API_KEY_required")
    config = core.configuration(classifier, 100)
    config.update(start_date="2026-04-03", end_date="2026-09-30",
                  filter="from_publication_date:2026-04-03,to_publication_date:2026-09-30,has_abstract:true,type:!paratext")
    with core.output_lock(out):
        store = WindowStore(out, config)
        store.snapshot_software(classifier)
        raw = Path(__file__).read_bytes()
        digest = core.sha(raw)
        relative = f"provenance/openalex_extension_estimate.{digest[:16]}.py"
        core.atomic_bytes(out / relative, raw)
        store.manifest["software_runs"][-1]["sources"].append(
            {"name": Path(__file__).name, "path": relative, "sha256": digest})
        store.save()
        budget = core.Budget(out, cap=0.025, margin=0.05)
        options = SimpleNamespace(timeout_seconds=60, concurrency=3, max_retries=1,
                                  request_delay_seconds=0.2, first_pages_only=True)
        asyncio.run(core.collect(store, budget, options, key))
        report = core.estimate(store, budget)
        report["purpose"] = "Incremental retrieval cost estimate; not publication statistics."
        report["publication_start"] = config["start_date"]
        report["publication_end"] = config["end_date"]
        report["daily_remaining_usd"] = budget.data["snapshots"][-1]["daily_remaining_usd"]
        core.atomic_json(out / "cost_estimate.json", report)
        if not report["all_first_pages_available"]:
            raise core.EvidenceError("not_all_query_counts_returned")
        print(core.json_bytes(report).decode())


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Stopped: {type(exc).__name__}; saved pages and budget retained.")
        raise SystemExit(1) from None
