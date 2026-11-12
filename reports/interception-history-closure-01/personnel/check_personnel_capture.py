"""Local owner check of the immutable personnel source-fact packet. No GETs."""
import csv
import datetime as dt
import hashlib
import io
import json
import resource
from collections import Counter
from pathlib import Path

base = Path(__file__).resolve().parent
root = base.parents[2]
source = root / "sources/current-personnel-interception-closure-20261112-was-nyg"
manifest = json.loads((source / "SOURCE_MANIFEST.json").read_text())
event = json.loads((source / "EVENT_STATUS.json").read_text())
projection = (source / "INJURY_STATUS_FACTS.csv").read_bytes()
rows = list(csv.DictReader(io.StringIO(projection.decode())))
assert hashlib.sha256(projection).hexdigest() == manifest["projection"]["SHA256"]
assert len(projection) == manifest["projection"]["bytes"] == 1429
assert len(rows) == manifest["projection"]["rows"] == 20
assert {row["team"] for row in rows} == {"WAS", "NYG"}
assert all(row["season"] == "2026" and row["week"] == "10" for row in rows)
keys = [(row["team"], row["gsis_id"]) for row in rows]
assert len(keys) == len(set(keys))
assert list(rows[0]) == manifest["projection"]["columns"]
assert not {"full_name", "first_name", "last_name", "report_primary_injury", "practice_primary_injury"} & rows[0].keys()
assert not manifest["source_row_clocks"]
assert event["state"] == "pre" and event["completed"] is False
assert event["game_id"] == "2026_10_WAS_NYG" and event["espn_event_id"] == "401873052"
kickoff = dt.datetime.fromisoformat(event["kickoff_UTC"])
issue = dt.datetime.fromisoformat(manifest["source_only_issue_UTC"])
assert kickoff.utcoffset() is not None and issue.utcoffset() is not None
assert issue < kickoff - dt.timedelta(seconds=300)
assert all(dt.datetime.fromisoformat(receipt["observed_UTC"]) <= issue for receipt in manifest["sources"])
assert all(receipt["HTTP_status"] == 200 and receipt["body_bytes"] <= 131072 for receipt in manifest["sources"])
assert manifest["source_read_count"] == 2
assert manifest["persistence"]["forecast_count"] == manifest["persistence"]["actual_offer_count"] == manifest["persistence"]["selected_decision_count"] == 0
assert manifest["persistence"]["state"] == "LOCAL_CAPTURE_AWAITING_ROOT_GITHUB_COMMIT_AND_SERVER_RECEIPT"
counts = Counter(row["report_status"] or "EMPTY_UNKNOWN" for row in rows)
assert counts == {"EMPTY_UNKNOWN": 17, "Questionable": 1, "Out": 2}
receipt = {
    "schema": "C-PERSONNEL-OWNER-LOCAL-CHECK-v1",
    "executed_UTC": dt.datetime.now(dt.timezone.utc).isoformat(),
    "command": "python reports/interception-history-closure-01/personnel/check_personnel_capture.py",
    "verdict": "PASS_RETAINED_PACKET_IDENTITY_HASH_CLOCK_AND_SCOPE",
    "projection_rows": len(rows), "projection_SHA256": hashlib.sha256(projection).hexdigest(),
    "event_status_SHA256": hashlib.sha256((source / "EVENT_STATUS.json").read_bytes()).hexdigest(),
    "manifest_SHA256": hashlib.sha256((source / "SOURCE_MANIFEST.json").read_bytes()).hexdigest(),
    "report_status_counts": dict(counts), "team_counts": dict(Counter(row["team"] for row in rows)),
    "WR_TE_rows": sum(row["position"] in ("WR", "TE") for row in rows),
    "source_only_issue_UTC": issue.isoformat(), "kickoff_UTC": kickoff.isoformat(),
    "source_only_lead_seconds": (kickoff - issue).total_seconds(),
    "remote_persistence": "UNVERIFIED_IN_THIS_LOCAL_CHECK",
    "scope_limits": ["Owner recheck, not independent review", "Raw response hashes/field list were measured only during original extraction; cannot reverify from projection", "Full roster/expected role/health/participation and predictive improvement unestablished", "No forecast or exact-line selections"],
    "CPU_seconds": resource.getrusage(resource.RUSAGE_SELF).ru_utime + resource.getrusage(resource.RUSAGE_SELF).ru_stime,
    "max_RSS_KiB": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
}
(base / "OWNER_LOCAL_CHECK.json").write_text(json.dumps(receipt, indent=2) + "\n")
print(json.dumps(receipt, indent=2))
