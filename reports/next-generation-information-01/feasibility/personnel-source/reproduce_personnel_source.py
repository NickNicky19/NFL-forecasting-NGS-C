"""Reproduce permitted status projection checks; never downloads or fits.

Optional --source-gzip rechecks a locally supplied source against the receipt's
exact hash, reconstructs the projection independently, and enforces byte caps.
The original full source was temporary in memory and is not bundled here.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import gzip
import hashlib
import io
import json
import resource
from collections import Counter
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-gzip", type=Path)
    args = parser.parse_args()
    base = Path(__file__).resolve().parent
    manifest = json.loads((base / "CURRENT_INJURY_SOURCE_RECEIPT.json").read_text())
    projection = (base / "INJURY_STATUS_CLOCK_2026.csv").read_bytes()
    projection_hash = hashlib.sha256(projection).hexdigest()
    assert projection_hash == manifest["projection_SHA256"]
    rows = list(csv.DictReader(io.StringIO(projection.decode())))
    assert len(rows) == 3097 == manifest["rows"]
    prior = [row for row in rows if 1 <= int(row["week"]) <= 8]
    assert len(prior) == 2459
    assert sum(row["position"] in ("WR", "TE") for row in prior) == 446
    keys = [tuple(row[col] for col in ("season", "game_type", "week", "team", "gsis_id")) for row in rows]
    assert len(keys) == len(set(keys))
    assert all(row["season"] == "2026" and row["gsis_id"] for row in rows)
    raw_verification = "NOT_REEXECUTED_RAW_NOT_DURABLY_RETAINED"
    if args.source_gzip:
        raw = args.source_gzip.read_bytes()
        assert len(raw) <= 131072
        assert hashlib.sha256(raw).hexdigest() == manifest["compressed_SHA256"]
        with gzip.GzipFile(fileobj=io.BytesIO(raw)) as source:
            decoded = source.read(2097153)
        assert len(decoded) <= 2097152
        assert hashlib.sha256(decoded).hexdigest() == manifest["decoded_SHA256"]
        raw_rows = list(csv.DictReader(io.StringIO(decoded.decode("utf-8-sig"))))
        assert list(raw_rows[0]) == manifest["all_source_fields"]
        reconstructed = io.StringIO(newline="")
        writer = csv.DictWriter(reconstructed, fieldnames=manifest["projection_fields"], lineterminator="\n")
        writer.writeheader()
        writer.writerows({field: row[field] for field in manifest["projection_fields"]} for row in raw_rows)
        assert reconstructed.getvalue().encode() == projection
        raw_verification = "EXACT_RAW_HASH_AND_INDEPENDENT_PROJECTION_PASS"
    root = base.parents[3]
    current = {tuple(row[col] for col in ("season", "week", "team", "gsis_id")): row for row in rows}
    vintage_results = []
    paths = [
        ("sources/current-pregame-v9-20261102-1930/availability.csv", 26, 0),
        ("sources/current-pregame-closure02-20261105-jax-bal/injuries.json", 266, 187),
    ]
    for relative, expected_count, expected_changed in paths:
        path = root / relative
        if path.suffix == ".json":
            old = json.loads(path.read_text())
        else:
            old = list(csv.DictReader(io.StringIO(path.read_text())))
        assert len(old) == expected_count
        changed = 0
        for row in old:
            key = tuple(str(row.get(col) or "") for col in ("season", "week", "team", "gsis_id"))
            latest = current[key]
            changed += any((row.get(col) or "") != (latest.get(col) or "") for col in ("report_status", "practice_status"))
        assert changed == expected_changed
        vintage_results.append({"source": relative, "rows": len(old), "changed": changed})
    receipt = {
        "schema": "C-NEXTINFO-PERSONNEL-REPRODUCTION-v1",
        "executed_UTC": dt.datetime.now(dt.timezone.utc).isoformat(),
        "command": "python reports/next-generation-information-01/feasibility/personnel-source/reproduce_personnel_source.py",
        "projection_hash": projection_hash,
        "projection_rows": len(rows),
        "W1_8_rows": len(prior),
        "W1_8_WR_TE_rows": sum(row["position"] in ("WR", "TE") for row in prior),
        "weekly_rows": dict(sorted(Counter(int(row["week"]) for row in rows).items())),
        "raw_source_verification": raw_verification,
        "vintage_comparisons": vintage_results,
        "source_clock_fields": [],
        "clock_scope": "Manifest inspected schema lacks row clocks; current retrieval does not authenticate past availability.",
        "fits": 0,
        "CPU_seconds": resource.getrusage(resource.RUSAGE_SELF).ru_utime + resource.getrusage(resource.RUSAGE_SELF).ru_stime,
        "max_RSS_KiB": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "verdict": "PASS_PROJECTION_AGGREGATION_AND_RETAINED_VINTAGE_COMPARISON_ONLY",
        "limits": "No independent original source restoration, pregame personnel universe, model fit, predictive result or release qualification is established.",
    }
    (base / "REPRODUCTION_RECEIPT.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
