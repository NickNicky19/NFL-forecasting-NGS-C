"""The one predeclared later event observation, only on root's safe checkpoint.

This command never waits, polls, fits or selects. It cannot overwrite an earlier
response. Source flags remain unqualified until an explicit semantics review.
"""
import datetime as dt
import hashlib
import json
import resource
import urllib.parse
import urllib.request
from pathlib import Path

UTC = dt.timezone.utc
REPORT = Path(__file__).resolve().parent
ROOT = REPORT.parents[2]
SOURCE = ROOT / "sources/current-personnel-information-first-20261112-was-nyg"
EARLIEST = dt.datetime(2026, 11, 12, 23, 50, tzinfo=UTC)
KICKOFF = dt.datetime(2026, 11, 13, 1, 15, tzinfo=UTC)


def main():
    now = dt.datetime.now(UTC)
    assert EARLIEST <= now < KICKOFF - dt.timedelta(seconds=300), "Outside predeclared safe observation window; do not wait or poll"
    assert not (REPORT / "LATE_SOURCE_RECEIPT.json").exists(), "Single later read already used"
    url = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event=401873052"
    req = urllib.request.Request(url, headers={"User-Agent": "C-registered-information-first-personnel/1.0"})
    with urllib.request.urlopen(req, timeout=45) as response:
        body = response.read(4194305)
        assert len(body) <= 4194304
        receipt = {
            "id": "NATIVE_EVENT_DETAIL_SINGLE_LATER_OBSERVATION", "url": url,
            "started_UTC": now.isoformat(), "observed_UTC": dt.datetime.now(UTC).isoformat(),
            "HTTP_status": response.status, "bytes": len(body), "SHA256": hashlib.sha256(body).hexdigest(),
            "headers": {key: response.headers.get(key) for key in ("Date", "Age", "Last-Modified", "ETag", "Content-Length", "Cache-Control")},
            "final_host": urllib.parse.urlparse(response.url).hostname,
            "raw_retention": "Temporary memory only; no names/news/media/odds/articles retained",
        }
    data = json.loads(body)
    header = data["header"]
    assert str(header["id"]) == "401873052"
    competition = header["competitions"][0]
    status = competition["status"]["type"]
    event = {
        "event_id": str(header["id"]), "competition_id": str(competition["id"]),
        "kickoff_UTC": competition["date"], "state": status["state"],
        "completed": status["completed"], "observed_UTC": receipt["observed_UTC"],
        "season": header.get("season"), "week": header.get("week"),
        "teams": [{"id": entry.get("id"), "team_id": entry.get("team", {}).get("id"), "abbreviation": entry.get("team", {}).get("abbreviation"), "homeAway": entry.get("homeAway")} for entry in competition["competitors"]],
    }
    assert status["state"] == "pre" and not status["completed"]
    assert dt.datetime.fromisoformat(competition["date"].replace("Z", "+00:00")) == KICKOFF
    structure = {
        "schema": "C-NATIVE-EVENT-LATE-ROSTER-SCHEMA-PROBE-v1", "event_id": "401873052",
        "observed_UTC": receipt["observed_UTC"], "root_fields": list(data),
        "roster_blocks": [], "player_box_blocks": [], "candidate_rows": [],
        "meaning": "Provider flags are observed facts only, not automatically game-active/starter/healthy/complete roster or future participation.",
    }
    blocks = data.get("rosters", [])
    if isinstance(blocks, dict):
        blocks = [blocks]
    for index, block in enumerate(blocks):
        if not isinstance(block, dict):
            continue
        team_id = block.get("teamId", block.get("team", {}).get("id"))
        structure["roster_blocks"].append({"index": index, "keys": list(block), "team_id": team_id, "array_counts": {k: len(v) for k, v in block.items() if isinstance(v, list)}})
        for field in ("roster", "athletes", "entries"):
            for entry in block.get(field, []):
                if not isinstance(entry, dict):
                    continue
                athlete = entry.get("athlete", entry)
                raw_status = athlete.get("status")
                status_fact = {key: value for key, value in raw_status.items() if key in ("id", "name", "type", "abbreviation")} if isinstance(raw_status, dict) else raw_status
                structure["candidate_rows"].append({"team_source_id": team_id, "athlete_source_id": athlete.get("id"), "position": athlete.get("position", {}).get("abbreviation"), "status": status_fact, "entry_active": entry.get("active"), "athlete_active": athlete.get("active"), "starter": entry.get("starter"), "didNotPlay": entry.get("didNotPlay")})
    for block in data.get("boxscore", {}).get("players", []):
        structure["player_box_blocks"].append({"keys": list(block), "team_id": block.get("team", {}).get("id"), "group_counts": [len(x.get("athletes", [])) for x in block.get("statistics", [])]})
    (SOURCE / "LATE_EVENT_STATUS.json").write_text(json.dumps(event, indent=2) + "\n")
    (SOURCE / "LATE_EVENT_ROSTER_STRUCTURE.json").write_text(json.dumps(structure, indent=2) + "\n")
    receipt.update({"source_reads_cumulative": 3, "later_read_limit_used": 1, "CPU_seconds": resource.getrusage(resource.RUSAGE_SELF).ru_utime + resource.getrusage(resource.RUSAGE_SELF).ru_stime, "max_RSS_KiB": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss})
    (REPORT / "LATE_SOURCE_RECEIPT.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"event": event, "roster_blocks": structure["roster_blocks"], "candidate_rows": len(structure["candidate_rows"]), "box_player_blocks": structure["player_box_blocks"], "receipt": receipt}, indent=2))


if __name__ == "__main__":
    main()
