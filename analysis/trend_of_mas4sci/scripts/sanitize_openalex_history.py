"""Redact historical URL credentials without changing retrieval evidence counts.

The original file is not copied. Its digest and redaction audit remain in an
ignored local file. Known credentials stay in memory for the scoped text scan
and optional independent evidence verification.
"""

import argparse
import csv
import hashlib
import io
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote

from openalex_resumable import ROOT, atomic_bytes, atomic_json, output_lock
from verify_openalex_evidence import verify


def sanitize(out):
    path = ROOT / "results/openalex_from_2024_cost_conscious/query_summary.csv"
    original = path.read_bytes()
    text = original.decode("utf-8")
    pattern = re.compile(r"([?&]api_key=)([^&\s'\"<>]+)")
    values = {match.group(2) for match in pattern.finditer(text)
              if match.group(2) != "[REDACTED]"}
    tokens = {value.encode() for value in values} | {unquote(value).encode() for value in values}
    replacement_count = sum(match.group(2) in values for match in pattern.finditer(text))
    redacted = pattern.sub(lambda match: match.group(1) + "[REDACTED]", text)
    before = list(csv.DictReader(io.StringIO(text)))
    after = list(csv.DictReader(io.StringIO(redacted)))
    if len(before) != len(after):
        raise ValueError("redaction_changed_row_count")
    for previous, current in zip(before, after):
        if {k: v for k, v in previous.items() if k != "errors"} != {k: v for k, v in current.items() if k != "errors"}:
            raise ValueError("redaction_changed_counts_or_query_fields")
        if bool(previous["errors"]) != bool(current["errors"]):
            raise ValueError("redaction_changed_error_status")
        expected = pattern.sub(lambda match: match.group(1) + "[REDACTED]", previous["errors"])
        if current["errors"] != expected:
            raise ValueError("redaction_changed_error_content_beyond_credentials")
    updated = redacted.encode("utf-8")
    atomic_bytes(path, updated)
    repo = ROOT.parents[1]
    tracked = subprocess.check_output(["git", "ls-files", "-z", "--", "analysis/trend_of_mas4sci"], cwd=repo).decode().split("\0")
    checked, matches = 0, []
    for name in tracked:
        if not name:
            continue
        file = repo / name
        if not file.is_file():
            continue
        data = file.read_bytes()
        checked += 1
        if any(token in data for token in tokens):
            matches.append(name)
    report = {"historical_file": path.relative_to(ROOT).as_posix(),
              "original_sha256_local_only": hashlib.sha256(original).hexdigest(),
              "redacted_sha256": hashlib.sha256(updated).hexdigest(),
              "credential_values_found": len(values), "url_values_redacted": replacement_count,
              "query_rows": len(after), "counts_unchanged": True, "error_statuses_unchanged": True,
              "error_query_ids": [row["query_id"] for row in after if row["errors"]],
              "tracked_analysis_files_scanned": checked, "known_key_match_paths": matches,
              "scan_status": "passed" if tokens and not matches else "not_checked_no_key" if not tokens else "failed",
              "git_history_rewritten": False,
              "private_followup": "Rotate the exposed credential. Working-tree redaction does not remove copies in Git history or the separate repository; those are outside this write scope."}
    audit_path = out / "security_audit.local.json"
    if audit_path.exists():
        previous = json.loads(audit_path.read_text(encoding="utf-8"))
        report = {"previous_audit": previous, "latest_audit": report}
    atomic_json(audit_path, report)
    if matches:
        raise ValueError("known_key_remains_in_tracked_analysis_files")
    print(json.dumps({"url_values_redacted": replacement_count, "query_rows_preserved": len(after),
                      "tracked_analysis_files_scanned": checked, "known_key_matches": len(matches)}), flush=True)
    return tokens


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--compare-git-legacy")
    args = parser.parse_args()
    out = args.out_dir.resolve()
    if not out.is_relative_to(ROOT):
        raise ValueError("output_outside_authorized_directory")
    with output_lock(out):
        tokens = sanitize(out)
        if args.compare_git_legacy:
            report = verify(out, args.compare_git_legacy, tokens)
            print(json.dumps({key: report[key] for key in ("validated_complete", "query_count", "raw_occurrences", "deduplicated_records", "page_count", "search_attempts")}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
