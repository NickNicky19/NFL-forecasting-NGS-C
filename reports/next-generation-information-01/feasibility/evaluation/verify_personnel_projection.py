"""Independent stdlib check of permitted status projections; no model or source GET."""
from pathlib import Path
from collections import Counter
import csv
import hashlib
import json
import resource
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
NEW = ROOT / "reports/next-generation-information-01/feasibility/personnel-source"


def key(row):
    return tuple(str(row[k]) for k in ["season", "week", "team", "gsis_id"])


def status(row):
    # Null/empty equivalence is comparison-only; never rewrite original states.
    return tuple("" if row.get(k) is None else row[k] for k in ["report_status", "practice_status"])


def main():
    started = time.process_time()
    current_path = NEW / "INJURY_STATUS_CLOCK_2026.csv"
    with current_path.open() as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames
        rows = list(reader)
    current = {key(r): r for r in rows}
    assert len(current) == len(rows)
    clock_terms = ["date_modified", "report_date", "available", "observed", "published", "updated", "timestamp"]
    projection_clocks = [f for f in fields if any(t in f.lower() for t in clock_terms)]
    source_receipt = json.loads((NEW / "CURRENT_INJURY_SOURCE_RECEIPT.json").read_text())
    declared_full_fields = source_receipt["all_source_fields"]
    declared_source_clocks = [f for f in declared_full_fields if any(t in f.lower() for t in clock_terms)]
    eligible = [r for r in rows if 1 <= int(r["week"]) <= 8]
    reports = []
    paths = [ROOT / "sources/current-pregame-v9-20261102-1930/availability.csv",
             ROOT / "sources/current-pregame-closure02-20261105-jax-bal/injuries.json"]
    for p in paths:
        with p.open() as stream:
            old = list(csv.DictReader(stream)) if p.suffix == ".csv" else json.load(stream)
        assert len({key(r) for r in old}) == len(old)
        same = changed = missing = 0
        changed_fields = Counter()
        for r in old:
            latest = current.get(key(r))
            if latest is None:
                missing += 1
                continue
            if status(r) == status(latest):
                same += 1
            else:
                changed += 1
                for field, left, right in zip(["report_status", "practice_status"], status(r), status(latest)):
                    changed_fields[field] += int(left != right)
        reports.append({"path": str(p.relative_to(ROOT)), "SHA256": hashlib.sha256(p.read_bytes()).hexdigest(),
                        "retained_rows": len(old), "same_status": same, "changed_status": changed,
                        "no_current_match": missing, "changed_field_counts": dict(changed_fields)})
    output = {"id": "C-NEXTINFO-PERSONNEL-PROJECTION-INDEPENDENT-v1", "checked_UTC": datetime.now(timezone.utc).isoformat(),
              "status": "PASS_RETAINED_PROJECTION_ARITHMETIC;HISTORICAL_INPUT_SOURCE_BLOCKED",
              "method": "Separate standard-library CSV/JSON parser and direct identity/status comparisons; no author summary functions imported.",
              "projection": {"path": str(current_path.relative_to(ROOT)), "bytes": current_path.stat().st_size,
                             "SHA256": hashlib.sha256(current_path.read_bytes()).hexdigest(), "fields": fields,
                             "rows": len(rows), "unique_keys": len(current), "W1_W8_rows": len(eligible),
                             "W1_W8_WR_TE_rows": sum(r["position"] in ["WR", "TE"] for r in eligible),
                             "weekly": {str(w): dict(Counter(r["position"] for r in rows if int(r["week"]) == w)) for w in range(1, 11)},
                             "row_clock_fields": projection_clocks},
              "source_header_receipt": {"path": str((NEW / "CURRENT_INJURY_SOURCE_RECEIPT.json").relative_to(ROOT)),
                                        "SHA256": hashlib.sha256((NEW / "CURRENT_INJURY_SOURCE_RECEIPT.json").read_bytes()).hexdigest(),
                                        "all_source_fields_as_recorded_by_source_executor": declared_full_fields,
                                        "clock_fields": declared_source_clocks,
                                        "observed_UTC": source_receipt["observed_UTC"]},
              "independent_comparisons": reports,
              "interpretation": "Differences between actual retained snapshots demonstrate source revisions/updates for these same row identities. They do not reconstruct the intervening original statuses or row availability. The latest snapshot cannot be backdated to an earlier forecast. No absence of an injury row establishes health, active status, roster membership or participation.",
              "limits": "Full original upstream body not newly downloaded by reviewer; absence of clock fields in the full source schema is bound to the source executor header receipt. The permitted projection independently shows its own clock absence. Comparison-only null/empty normalization does not change source or grading states.",
              "resources": {"CPU_seconds": time.process_time() - started, "peak_RSS_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
                            "network": 0, "fits": 0, "inference": 0, "NFL_scoring": 0}}
    p = OUT / "PERSONNEL_PROJECTION_INDEPENDENT.json"
    p.write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps({"rows": len(rows), "W1_W8": len(eligible), "WR_TE": output["projection"]["W1_W8_WR_TE_rows"],
                      "comparisons": reports, "path": str(p.relative_to(ROOT)), "SHA256": hashlib.sha256(p.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
