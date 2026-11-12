"""One registered manual source-fact capture; no model, offer or scheduler.

Executed only under REGISTRATION.json. Raw full responses remain in memory.
Rerunning does not have authority to overwrite this first immutable snapshot.
"""
from __future__ import annotations

import csv
import datetime as dt
import gzip
import hashlib
import io
import json
import re
import resource
import urllib.parse
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
REPORT = Path(__file__).resolve().parent
SOURCE = ROOT / "sources/current-personnel-interception-closure-20261112-was-nyg"
UTC = dt.timezone.utc
READS = []


def now():
    return dt.datetime.now(UTC)


def save(path, value):
    if path.exists():
        raise RuntimeError(f"Immutable capture already exists: {path.name}")
    path.write_text(json.dumps(value, indent=2) + "\n")


def get(source_id, url):
    assert len(READS) < 6
    started = now()
    req = urllib.request.Request(url, headers={"User-Agent": "C-registered-personnel-observation/1.0"})
    with urllib.request.urlopen(req, timeout=45) as response:
        body = response.read(131073)
        assert len(body) <= 131072, "Response exceeds registered128KiB bound"
        receipt = {
            "id": source_id, "url": url, "started_UTC": started.isoformat(),
            "observed_UTC": now().isoformat(), "HTTP_status": response.status,
            "HTTP_headers": {key: response.headers.get(key) for key in (
                "Date", "Age", "Last-Modified", "Content-Length", "Content-Type", "ETag", "Cache-Control")},
            "final_host": urllib.parse.urlparse(response.url).hostname,
            "body_bytes": len(body), "body_SHA256": hashlib.sha256(body).hexdigest(),
            "raw_retention": "Full raw response temporary in memory only; minimal factual projection retained.",
        }
    READS.append(receipt)
    return body, receipt


def main():
    assert (REPORT / "REGISTRATION.json").exists()
    assert not (SOURCE / "SOURCE_MANIFEST.json").exists()
    native, native_receipt = get("NATIVE_WAS_NYG_PRECHECK", "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates=20261112&limit=100")
    data = json.loads(native)
    matches = [event for event in data.get("events", []) if str(event.get("id")) == "401873052"]
    assert len(matches) == 1, "Expected native event absent or ambiguous"
    event = matches[0]
    comp = event["competitions"][0]
    status, comp_status = event["status"]["type"], comp["status"]["type"]
    kickoff = dt.datetime.fromisoformat(event["date"].replace("Z", "+00:00"))
    comp_kickoff = dt.datetime.fromisoformat(comp["date"].replace("Z", "+00:00"))
    aliases = {"WSH": "WAS", "WAS": "WAS", "NYG": "NYG"}
    teams = {entry["homeAway"]: aliases.get(entry["team"]["abbreviation"], entry["team"]["abbreviation"]) for entry in comp["competitors"]}
    assert teams == {"home": "NYG", "away": "WAS"}
    assert kickoff == comp_kickoff == dt.datetime(2026, 11, 13, 1, 15, tzinfo=UTC)
    assert status["state"] == comp_status["state"] == "pre"
    assert status["completed"] is False and comp_status["completed"] is False
    assert now() < kickoff - dt.timedelta(seconds=300)
    event_fact = {
        "schema": "C-NATIVE-PERSONNEL-EVENT-v1", "game_id": "2026_10_WAS_NYG",
        "espn_event_id": str(event["id"]), "competition_id": str(comp["id"]),
        "season": event["season"]["year"], "season_type": event["season"]["type"],
        "week": event["week"]["number"], "kickoff_UTC": kickoff.isoformat(),
        "kickoff_Chicago": kickoff.astimezone(ZoneInfo("America/Chicago")).isoformat(),
        "home_team": "NYG", "away_team": "WAS", "state": status["state"],
        "status_name": status["name"], "completed": status["completed"],
        "event_competition_agreement": True, "source_observed_UTC": native_receipt["observed_UTC"],
        "source_receipt_id": native_receipt["id"],
        "scope": "Current native event identity, schedule and pregame state only; no roster/starter or model admission.",
    }
    assert event_fact["season"] == 2026 and event_fact["week"] == 10 and event_fact["season_type"] == 2
    save(SOURCE / "EVENT_STATUS.json", event_fact)
    compressed, injury_receipt = get("NFLVERSE_INJURY_2026", "https://github.com/nflverse/nflverse-data/releases/download/injuries/injuries_2026.csv.gz")
    with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as source:
        decoded = source.read(2097153)
    assert len(decoded) <= 2097152
    rows = list(csv.DictReader(io.StringIO(decoded.decode("utf-8-sig"))))
    fields = list(rows[0])
    injury_receipt.update({"decoded_bytes": len(decoded), "decoded_SHA256": hashlib.sha256(decoded).hexdigest(), "all_source_fields": fields, "all_source_rows": len(rows)})
    selected = [row for row in rows if row.get("season") == "2026" and row.get("week") == "10" and row.get("team") in ("WAS", "WSH", "NYG")]
    columns = [name for name in ("season", "week", "season_type", "game_type", "team", "gsis_id", "position", "report_status", "practice_status", "date_modified") if name in fields]
    assert selected, "No matching current week/team report facts"
    seen = set()
    for row in selected:
        assert re.fullmatch(r"00-\d{7}", row["gsis_id"])
        key = (row["team"], row["gsis_id"])
        assert key not in seen, "Multiple source versions need explicit disambiguation"
        seen.add(key)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows({name: row.get(name, "") for name in columns} for row in selected)
    projection = stream.getvalue().encode()
    target = SOURCE / "INJURY_STATUS_FACTS.csv"
    assert not target.exists()
    target.write_bytes(projection)
    issued = now()
    assert issued < kickoff - dt.timedelta(seconds=300)
    manifest = {
        "schema": "C-PROSPECTIVE-PERSONNEL-SOURCE-v1", "snapshot_id": "C-PERSONNEL-WASNYG-20261112-01",
        "source_only_issue_UTC": issued.isoformat(), "source_only_issue_Chicago": issued.astimezone(ZoneInfo("America/Chicago")).isoformat(),
        "event": event_fact, "sources": READS,
        "projection": {"path": str(target.relative_to(ROOT)), "bytes": len(projection), "SHA256": hashlib.sha256(projection).hexdigest(), "rows": len(selected), "columns": columns},
        "source_row_clocks": [field for field in ("date_modified", "report_date", "published_at", "observed_at") if field in fields],
        "source_effective_scope": "Source-tagged2026W10 WAS/NYG report facts observed before current native scheduled kickoff. Complete event-effective roster, expected roles and per-row original availability remain UNKNOWN.",
        "state_contract": "Empty/null/notlisted is not healthy, starter, active or DNP; no statistic zeros inferred. Practice participation differs from game participation. All missing roster players remain unknown rather than healthy.",
        "rights": "Existing ordinary nflverse CC-BY-4.0 minimal facts plus native public event facts. Names, injury descriptions, narratives, images and market data excluded.",
        "persistence": {"state": "LOCAL_CAPTURE_AWAITING_ROOT_GITHUB_COMMIT_AND_SERVER_RECEIPT", "local_persistence_UTC": issued.isoformat(), "requirement": "Root must bind exact commit/blob hashes plus real GitHub server timing before actual kickoff; local issue does not prove remote durable pregame persistence.", "forecast_count": 0, "actual_offer_count": 0, "selected_decision_count": 0},
        "historical_status": "W1–8_SOURCE_BLOCKED_UNCHANGED; no current source value is assigned an earlier historical availability.",
        "source_read_count": len(READS), "CPU_seconds": resource.getrusage(resource.RUSAGE_SELF).ru_utime + resource.getrusage(resource.RUSAGE_SELF).ru_stime,
        "max_RSS_KiB": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    }
    save(SOURCE / "SOURCE_MANIFEST.json", manifest)
    save(REPORT / "LOCAL_CAPTURE_RECEIPT.json", {"schema": "C-PERSONNEL-LOCAL-CAPTURE-RECEIPT-v1", "snapshot": str(SOURCE.relative_to(ROOT)), "manifest_SHA256": hashlib.sha256((SOURCE / "SOURCE_MANIFEST.json").read_bytes()).hexdigest(), "projection": manifest["projection"], "issued_UTC": issued.isoformat(), "kickoff_UTC": kickoff.isoformat(), "source_reads": len(READS), "remote_persistence": "NOT_YET_VERIFIED", "fits": 0, "forecasts": 0})
    print(json.dumps({"event": event_fact, "injury_receipt": injury_receipt, "projection": manifest["projection"], "source_only_issue_UTC": issued.isoformat(), "remote_persistence": manifest["persistence"]["state"], "source_reads": len(READS)}, indent=2))


if __name__ == "__main__":
    main()
