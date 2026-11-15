"""Read-only check of an executed outcome-source checkpoint; never fetch/grade."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import resource
import time

ROOT = Path(__file__).resolve().parents[4]
PACKAGE = Path(__file__).resolve().parents[1]
DIRECTORY = PACKAGE / "C05-grading"


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_manifest(path):
    data = read(path)
    members = data["files"]
    for member in members:
        p = ROOT / member["path"]
        assert sha(p) == member["SHA256"]
        if "bytes" in member:
            assert p.stat().st_size == member["bytes"]
    return len(members)


def run():
    start = time.process_time()
    registration = read(DIRECTORY / "REGISTRATION.json")
    checkpoint = read(DIRECTORY / "SOURCE_STATUS.json")
    process = read(DIRECTORY / "PROCESS_RESOURCE.json")
    stop = read(DIRECTORY / "EXACT_STOP.json")
    source_code = (DIRECTORY / "execute_grading.py").read_text()
    assert sha(DIRECTORY / "execute_grading.py") == checkpoint["resources"]["code_SHA256"]
    assert sha(DIRECTORY / "REGISTRATION.json") == checkpoint["registration_SHA256"]
    for name in ["checkpoint", "full_process_resource"]:
        bound = stop[name]
        path = ROOT / bound["path"]
        assert path.stat().st_size == bound["bytes"] and sha(path) == bound["SHA256"]
    old_hashes = checkpoint["original_packet_hashes"]
    assert len(old_hashes) == 3 and all(sha(ROOT/path) == expected for path, expected in old_hashes.items())
    assert checkpoint["status"] == "STOPPED"
    assert checkpoint["stage"] == "QUALIFIED_ORDINARY_PLAYER_FACTS"
    assert checkpoint["reason"] == "RuntimeError: FINAL_PLAYER_FACT_ROWS_NOT_YET_AVAILABLE"
    # Inspect the executed path, not its raw source bodies, which were not retained.
    assert source_code.count('"FINAL_PLAYER_FACT_ROWS_NOT_YET_AVAILABLE"') == 1
    assert 'boundary(len(frame) > 0, "FINAL_PLAYER_FACT_ROWS_NOT_YET_AVAILABLE")' in source_code
    prior_guard = source_code.index('"SCHEDULE_NATIVE_SCORE_CONFLICT"')
    stop_guard = source_code.index('"FINAL_PLAYER_FACT_ROWS_NOT_YET_AVAILABLE"')
    outcome_write = source_code.index('write(OUT / "OUTCOMES.json"')
    assert prior_guard < stop_guard < outcome_write
    assert 'integer(game.home_score) == native_scores["home"]' in source_code
    assert 'integer(game.away_score) == native_scores["away"]' in source_code
    assert 'full.game_id == GAME_ID' in source_code and 'full.season_type == "REG"' in source_code
    event = checkpoint["observed_native_event"]
    assert event["espn_event_id"] == event["competition_id"] == registration["event_id"] == "401873053"
    assert event["competition_state_agreement"] is True
    assert event["season"] == 2026 and event["season_type"] == 2 and event["week"] == 10
    assert event["home_team"] == "DET" and event["away_team"] == "NE"
    assert event["home_score"] == 35 and event["away_score"] == 10
    assert event["state"] == "post" and event["completed"] is True and event["status_name"] == "STATUS_FINAL"
    assert datetime.fromisoformat(event["kickoff_UTC"]) == datetime.fromisoformat(registration["retained_kickoff_UTC"])
    manifest = checkpoint["source_manifest"]
    assert [row["id"] for row in manifest] == ["native_status", "schedule", "stats"]
    assert all(row["HTTP_status"] == 200 and row["raw_retention"].startswith("Memory-only") for row in manifest)
    for row in manifest:
        assert len(row["raw_SHA256"]) == 64 and all(c in "0123456789abcdef" for c in row["raw_SHA256"])
        a, b = [datetime.fromisoformat(row[key]) for key in ["started_UTC", "observed_UTC"]]
        assert a.tzinfo is not None and b.tzinfo is not None and a <= b
    cap = registration["budget"]
    assert len(manifest) == checkpoint["resources"]["source_attempts"] == process["source_requests_cap"] == 3
    total_bytes = sum(row["bytes_received"] for row in manifest)
    assert total_bytes == checkpoint["resources"]["response_bytes"] == stop["actual_execution"]["source_bytes"] == 2972271
    assert total_bytes <= cap["source_response_bytes_cumulative_max"] == process["source_bytes_cap"] == 5242880
    assert process["full_child_CPU_seconds"] <= cap["CPU_seconds_max"] == 30
    assert process["child_peak_RSS_bytes"] <= cap["RSS_bytes_max"]
    assert process["returncode"] == 2
    assert checkpoint["outcome_packet"] is None and checkpoint["grade"] is None and checkpoint["metrics"] == []
    version = registration["new_grade_version"]
    outcome = ROOT / "prospective/outcomes" / version
    grade = ROOT / "prospective/grades" / (version + "-C-C05-NEDET-FIRST-01.json")
    assert not outcome.exists() and not grade.exists()
    assert checkpoint["resources"]["new_fits"] == checkpoint["resources"]["new_forecast_generation"] == checkpoint["resources"]["new_original_picks"] == 0
    assert process["new_fits"] == process["new_forecasts"] == process["new_original_selected_sides"] == 0
    assert checkpoint["resources"]["original_packet_unchanged"] is True
    assert stop["state"] == "FINALITY_QUALIFIED;ORDINARY_PLAYER_FACTS_NOT_AVAILABLE_IN_OBSERVED_VERSION"
    assert stop["actual_execution"]["remaining_source_attempts_this_registration"] == 0
    assert stop["actual_execution"]["new_outcome_packet"] is False and stop["actual_execution"]["new_grade"] is False
    old_c57 = verify_manifest(ROOT / "reports/information-skill-01/MANIFEST.json")
    old_m3 = verify_manifest(ROOT / "reports/targeted-accuracy-w1w9-01/M3/MANIFEST.json")
    assert old_c57 == 123 and old_m3 == 379
    return dict(
        id="C-FOLLOWTHROUGH-C05-CHECKPOINT-INDEPENDENT-v1",
        checked_UTC=datetime.now(timezone.utc).isoformat(),
        status="PASS_EXECUTED_CHECKPOINT_BINDINGS_AND_EXACT_STOP_SCOPE",
        original_C05_hashes_unchanged=old_hashes,
        C57_sealed_members_unchanged=old_c57, older_M3_sealed_members_unchanged=old_m3,
        event=dict(id=event["espn_event_id"],game=registration["game_id"],home="DET",away="NE",
                   home_score=35,away_score=10,kickoff_UTC=event["kickoff_UTC"],state="FINAL"),
        source_attempts=3,response_bytes=total_bytes,full_child_CPU_seconds=process["full_child_CPU_seconds"],
        player_fact_exact_filter_rows=0,
        player_fact_zero_count_verification_scope="Code's unique executed len(frame)>0 boundary and preserved stop reason establish the worker's zero-row observation; no independent raw-body reparse.",
        finality_verification_scope="Observed normalized native event and executed schedule equality guards; no raw native/schedule bytes retained or newly retrieved.",
        raw_body_SHA256_scope="Source worker reported hashes/lengths; checked metadata format and cross-receipt consistency, not recomputed hashes of unretained raw bodies.",
        original_SOURCE_STATUS_remaining_text="Generic finality-plus-facts fallback is historical execution text; EXACT_STOP supersedes it: finality qualified, only exact-game ordinary player facts remain missing.",
        grade_created=False,new_forecasts=0,new_original_picks=0,
        no_retry_or_source_requery=True, B_C1_reproduction="UNCHANGED_FAILED;unrelated to this checkpoint",
        resources=dict(CPU_seconds=time.process_time()-start,
                       RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
                       independent_new_source_requests=0,new_fits=0,new_grades=0,new_inference=0),
    )


if __name__ == "__main__":
    result = run()
    destination = PACKAGE / "verification/C05_CHECKPOINT_CHECK.json"
    assert not destination.exists()
    destination.write_text(json.dumps(result,indent=2)+"\n")
    print(result["status"], result["resources"])
