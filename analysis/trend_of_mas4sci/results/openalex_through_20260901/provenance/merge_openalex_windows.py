"""Combine verified, adjacent OpenAlex windows without changing lexical labels."""

import argparse
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import gzip
from hashlib import sha256
import io
import json
from pathlib import Path
import csv


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def table(path, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def combine(initial, extension, output):
    sources = [initial, extension]
    manifests = [read(s / "manifest.json") for s in sources]
    reports = [read(s / "verification.json") for s in sources]
    assert all(r["validated_complete"] for r in reports)
    assert len(manifests[0]["configuration"]["queries"]) == 17
    configs = [m["configuration"] for m in manifests]
    assert date.fromisoformat(configs[0]["end_date"]) + timedelta(days=1) == date.fromisoformat(configs[1]["start_date"])
    assert configs[0]["start_date"] == "2024-01-01"
    assert configs[0]["select"] == configs[1]["select"]
    assert configs[0]["classifier_sha256"] == configs[1]["classifier_sha256"]
    expected_union = " OR ".join("(" + q["search_text"] + ")" for q in configs[0]["queries"])
    assert len(configs[1]["queries"]) == 1
    assert configs[1]["queries"][0]["search_text"] == expected_union
    assert {q["query_id"] for q in configs[0]["queries"]}.isdisjoint(q["query_id"] for q in configs[1]["queries"])
    for s, m in zip(sources, manifests):
        for name, item in m["artifacts"].items():
            path = s / name
            if path.exists():
                assert digest(path) == item["sha256"], name
        assert digest(s / "deduplicated_corrected.jsonl.gz") == m["artifacts"]["deduplicated_corrected.jsonl.gz"]["sha256"]
    assert not (output / "manifest.json").exists(), "Use a fresh output directory."
    output.mkdir(parents=True, exist_ok=True)
    counts = {p: {s: Counter() for s in ("ai4science", "llm4science")}
              for p in ("2024", "2025", "2026_ytd")}
    identities, occurrences, query_membership = set(), set(), Counter()
    reasons, offset = Counter(), 0
    target = output / "deduplicated_corrected.jsonl.gz"
    with target.open("wb") as binary, gzip.GzipFile(filename="", mode="wb", fileobj=binary, mtime=0) as encoded:
        with io.TextIOWrapper(encoded, encoding="utf-8", newline="\n") as stream:
            for s, cfg, report in zip(sources, configs, reports):
                batch_count = 0
                with gzip.open(s / target.name, "rt", encoding="utf-8") as records:
                    for line in records:
                        row = json.loads(line)
                        assert row["identity"] not in identities, "A work occurs in both nonoverlapping windows; inspect date drift."
                        identities.add(row["identity"])
                        assert cfg["start_date"] <= row["publication_date"] <= cfg["end_date"]
                        row["occurrence_indices"] = [i + offset for i in row["occurrence_indices"]]
                        assert len(row["query_ids"]) == len(row["occurrence_indices"])
                        assert not occurrences.intersection(row["occurrence_indices"])
                        occurrences.update(row["occurrence_indices"])
                        query_membership.update(row["query_ids"])
                        reasons[row["exclude_reason"] or "included"] += 1
                        year = row["publication_date"][:4]
                        period = "2026_ytd" if year == "2026" else year
                        for scope in counts[period]:
                            included = row["is_" + scope] and not row["exclude_reason"]
                            assert included == row["included_" + scope]
                            if included:
                                c = counts[period][scope]
                                c["denominator"] += 1
                                c[row["architecture_kind"].replace("-", "_")] += 1
                                c[row["document_type"].replace("-", "_")] += 1
                        stream.write(json.dumps(row, sort_keys=True, ensure_ascii=True) + "\n")
                        batch_count += 1
                assert batch_count == report["deduplicated_records"]
                offset += report["raw_occurrences"]
    assert occurrences == set(range(offset))
    queries = [q for r in reports for q in r["queries"]]
    assert query_membership == Counter({q["query_id"]: q["raw_hits"] for q in queries})
    assert all(q["raw_hits"] == q["total_reported"] and q["terminal_cursor"] is None for q in queries)
    proportions, summary_counts, rows = {}, {}, []
    for p, scopes in counts.items():
        proportions[p], summary_counts[p] = {}, {}
        for scope, c in scopes.items():
            n, d = c["multi_agent"], c["denominator"]
            proportions[p][scope] = {"numerator": n, "denominator": d, "percent": 100*n/d}
            summary_counts[p][scope] = dict(c, after_dedup_in_scope=d, ma_share_all=n/d)
            rows.append(dict(estimate="bookkeeping_corrected", period=p, scope=scope, **proportions[p][scope]))
    for p in ("2024", "2025"):
        for scope, values in proportions[p].items():
            original = reports[0]["verified_proportions"]["bookkeeping_corrected"][p][scope]
            assert (values["numerator"], values["denominator"]) == (original["numerator"], original["denominator"])
            assert abs(values["percent"] - original["percent"]) < 1e-10
    pages = sum(r["page_count"] for r in reports)
    cost = sum(Decimal(r["reported_request_cost_usd_exact"]) for r in reports)
    result = {
        "validated_complete": True, "logical_query_count": 17, "query_count": len(queries),
        "queries": queries, "page_count": pages, "raw_occurrences": offset,
        "deduplicated_records": len(identities), "cross_window_duplicate_identities": 0,
        "verified_proportions": {"bookkeeping_corrected": proportions},
        "reported_request_cost_usd_exact": str(cost),
        "validation_method": "Verified adjacent source batches, exact OR expression, frozen classifier hash, unique identities, occurrence provenance, and recomputed denominators. No human labeling audit.",
    }
    summary = {
        "source": "openalex", "status": "complete", "time_window": {"start_date": configs[0]["start_date"], "end_date": configs[1]["end_date"]},
        "logical_query_count": 17, "query_count": len(queries), "completed_queries": len(queries),
        "raw_retrieved": offset, "after_dedup": len(identities), "pages_saved": pages,
        "estimates": {"bookkeeping_corrected": summary_counts},
        "interpretation": "Title/abstract keyword frequencies in the fixed-query corpus; not field-wide adoption or manually validated swarm architecture.",
    }
    write(output / "verification.json", result)
    write(output / "summary.json", summary)
    write(output / "classification_audit.json", {"corrected_exclude_reasons": dict(reasons), "rubric_changes": [], "cross_window_duplicate_identities": 0})
    table(output / "period_proportions.csv", rows)
    table(output / "query_summary.csv", queries)
    manifest = {
        "schema_version": 2, "status": "complete", "updated_at": datetime.now(timezone.utc).isoformat(),
        "configuration": {"start_date": configs[0]["start_date"], "end_date": configs[1]["end_date"], "queries": configs[0]["queries"], "select": configs[0]["select"], "classifier_sha256": configs[0]["classifier_sha256"]},
        "batches": [], "software_runs": [], "pages": [], "supporting_evidence": [], "artifacts": {},
    }
    for batch_name, s, m, r, cfg in zip(("initial", "extension"), sources, manifests, reports, configs):
        manifest["batches"].append({"id": batch_name, "start_date": cfg["start_date"], "end_date": cfg["end_date"], "validated_complete": r["validated_complete"], "manifest_sha256": digest(s / "manifest.json"), "verification_sha256": digest(s / "verification.json")})
        for name in ("manifest.json", "verification.json"):
            relative = f"batches/{batch_name}/{name}"
            (output / relative).parent.mkdir(parents=True, exist_ok=True)
            (output / relative).write_bytes((s / name).read_bytes())
            manifest["supporting_evidence"].append(relative)
        for page in m["pages"]:
            manifest["pages"].append(dict(page, path=f"../{s.name}/" + page["path"], batch=batch_name))
    # The frozen screening modules are shared by both batches. Preserve the merger too.
    for item in manifests[0]["software_runs"][-1]["sources"]:
        raw = (initial / item["path"]).read_bytes()
        relative = "provenance/" + item["name"]
        (output / relative).parent.mkdir(parents=True, exist_ok=True)
        (output / relative).write_bytes(raw)
        manifest["software_runs"].append({"sources": [dict(item, path=relative)]})
    own = Path(__file__)
    own_relative = "provenance/" + own.name
    (output / own_relative).parent.mkdir(parents=True, exist_ok=True)
    (output / own_relative).write_bytes(own.read_bytes())
    manifest["software_runs"].append({"sources": [{"name": own.name, "path": own_relative, "sha256": digest(own)}]})
    for name in ("verification.json", "summary.json", "classification_audit.json", "period_proportions.csv", "query_summary.csv", target.name):
        manifest["artifacts"][name] = {"sha256": digest(output / name), "bytes": (output / name).stat().st_size}
    write(output / "manifest.json", manifest)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("initial", type=Path)
    parser.add_argument("extension", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = combine(args.initial, args.extension, args.output)
    print(json.dumps(result, indent=2))
