"""Verify retained source bindings and scope labels without acquisition."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import resource
import time
import zipfile

ROOT = Path(__file__).resolve().parents[4]
PACKAGE = Path(__file__).resolve().parents[1]


def run():
    start = time.process_time()
    source = PACKAGE / "PERSONNEL_SOURCE_DISPOSITION.json"
    data = json.loads(source.read_text())
    assert data["new_source_reads"] == data["new_fits"] == data["new_offer_grades"] == 0
    bindings = []

    def visit(value):
        if isinstance(value, dict):
            if (value.get("repository") == "NickNicky19/NFL-forecasting-NGS-C"
                    and all(k in value for k in ["path", "bytes", "SHA256"])):
                path = ROOT / value["path"]
                raw = path.read_bytes()
                assert len(raw) == value["bytes"] and hashlib.sha256(raw).hexdigest() == value["SHA256"]
                assert value["immutable_commit"] in value["URL"]
                bindings.append(value["path"])
            for item in value.values():
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(data)
    doc = data["previous_C_depth_documentation"]
    with zipfile.ZipFile(ROOT / doc["archive"]["path"]) as archive:
        raw = archive.read(doc["member"])
    assert len(raw) == doc["member_bytes"]
    assert hashlib.sha256(raw).hexdigest() == doc["member_SHA256"]
    prior = data["prior_depth_history"]
    assert "ALREADY_OBTAINED_AND_TESTED_BY_B" in prior["state"]
    assert "CURRENT_VINTAGE" in prior["state"] and "NOT_AUTHENTICATED" in prior["state"]
    assert "did not fetch their raw bytes" in prior["received_scope"]
    assert "load time" in prior["owner_reported_definition"]
    assert "not injury clearance" in prior["meaning_limits"][0]
    assert "CLOSED_AT_EXACT_MISSING_ARCHIVE" in data["historical_personnel_search"]["state"]
    assert len(data["historical_personnel_search"]["exact_missing_gates"]) == 2
    roster = data["qualified_frozen_observations"]["official_roster_route"]
    assert roster["all_displayed_rows"] == 164
    assert roster["skill_rows"] == 48 and roster["resolved_skill_ids"] == 47 and roster["unresolved_skill_ids"] == 1
    kickoff = datetime.fromisoformat(roster["retained_kickoff_UTC"])
    assert kickoff.tzinfo is not None and kickoff < datetime.now(timezone.utc)
    assert "NOT_FRESH" in roster["state"]
    packet = data["C05_frozen_NEDET_status"]
    assert packet["original_forecasts"] == 69 and packet["unique_players"] == 23
    assert packet["real_offers"] == packet["real_selected_sides"] == 0
    assert "NO_LOCAL_QUALIFIED_NEDET_FINAL_OUTCOME_PACKET" in packet["current_status"]
    assert "grade_run" in packet["exact_next_operation"]["permissible_action"]
    assert "Do not rerun or silently retarget" in packet["exact_next_operation"]["do_not_reuse_fixed_wrong_event_adapter"]
    assert data["prospective_source_next_route"]["executor"].startswith("C existing")
    return dict(
        id="C-FOLLOWTHROUGH-PERSONNEL-SCOPE-CHECK-v1",
        checked_UTC=datetime.now(timezone.utc).isoformat(), status="PASS_RETAINED_BINDINGS_AND_SCOPE",
        source_file=str(source.relative_to(ROOT)),
        source_SHA256=hashlib.sha256(source.read_bytes()).hexdigest(),
        checked_C_binding_count=len(bindings), checked_C_paths=sorted(bindings),
        exact_archived_document_member=True,
        prior_B_depth_history="OWNER_REPORTED_CURRENT_VINTAGE_ALREADY_TESTED;RAW_HISTORY_NOT_NEWLY_INSPECTED_BY_C",
        historical_personnel="SOURCE_BLOCKED_ARCHIVED_AVAILABILITY_AND_COMPLETE_EVENT_UNIVERSE",
        current_roster="FROZEN_OBSERVED_164_ROWS;PAST_RETAINED_EVENT_CUTOFF;NOT_HEALTH_OR_STARTS",
        C05="69_ORIGINAL_FORECAST_ONLY_ROWS_PRESERVED;FINAL_EVIDENCE_MISSING_IN_CHECKED_LOCAL_SCOPE",
        scope="Local retained-byte and classification review, not new provider/source-clock validation or outcome collection.",
        resources=dict(CPU_seconds=time.process_time()-start, RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
                       new_network=0,new_fits=0,new_grades=0),
    )


if __name__ == "__main__":
    result = run()
    path = PACKAGE / "verification/PERSONNEL_SCOPE_CHECK.json"
    assert not path.exists()
    path.write_text(json.dumps(result,indent=2)+"\n")
    print(result["status"], result["checked_C_binding_count"], result["resources"])
