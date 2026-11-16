"""Append new original-forecast grades and baseline-only capture to V9.

The 890-row peer intake append is preserved byte-for-byte as a decoded prefix.
No O/U record, fit, offer or original forecast is created by this adapter.
"""
import csv
import datetime
import gzip
import hashlib
import io
import json
from pathlib import Path
import time

START = time.process_time()
ROOT = Path(__file__).resolve().parents[3]
D = Path(__file__).resolve().parent
TARGET = ROOT / "reports/category-decision-release-01/W1_W9_AND_HISTORY_COVERAGE_V9.csv.gz"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    old_receipt = D / "LEDGER_APPEND_RECEIPT.json"
    core = json.loads(old_receipt.read_text())
    assert core["total_rows"] == 37447
    data = gzip.decompress(TARGET.read_bytes())
    assert sha(data) == core["decoded_SHA256"] and sha(TARGET.read_bytes()) == core["SHA256"]
    core_copy = D / "V9_CORE_APPEND_RECEIPT.json"
    assert not core_copy.exists()
    core_copy.write_bytes(old_receipt.read_bytes())
    fields = next(csv.reader(io.StringIO(data.decode())))
    receipt = json.loads((D / "C05-outcomes/resume-01/COMPLETION_RECEIPT.json").read_text())
    source = "prospective/grades/C-NATIVE-GRADE-20261116-NEDET-01-C-C05-NEDET-FIRST-01.json"
    rows = []
    for metric in receipt["metrics"]:
        row = dict.fromkeys(fields, "")
        row.update(owner="C", category="rec", procedure_id=metric["model_id"],
            product="ORIGINAL_FORECAST_ONLY_NUMERICAL_AND_LAW_GRADE",
            history="Original Nov10 frozen feature/issue/model/receipt bindings unchanged",
            role_scope="ORIGINAL_23_PLAYERS;THREE_FROZEN_VIEWS",
            source_panel="C-C05-NEDET-FIRST-01", season=2026, week=10,
            status="GRADED_PLAYED_WITH_EXPLICIT_UNKNOWN_OUTCOMES",
            eligible=23, available=23, scored=19, unknown=4, games=1, player_games=23,
            evidence_tier="ORIGINAL_SERVER_QUALIFIED_FORECAST_ONLY;POSTGAME_QUALIFIED_PLAYER_FACTS",
            source_artifacts=json.dumps([source, str((D / "C05-outcomes/resume-01/COMPLETION_RECEIPT.json").relative_to(ROOT))]),
            verification_limit="19 observed players across three views are not57 independent events. Zero offers, no O/U, participation unknown is not DNP or zero. One game is not five-week qualification.",
            source_evidence_class="ORIGINAL_PREGAME_FORECAST_WITH_LATER_QUALIFIED_OUTCOME",
            new_procedure_coverage_not_new_games="True",
            required_next_owner_action="Preserve append-only grades and unresolved outcomes; any later resolution requires genuinely new qualified facts through existing bounded route.",
            row_kind="C05_ORIGINAL_FORECAST_ONLY_QUALIFIED_GRADE",
            grading_version=receipt["outcome_version"],
            issuance_state="ORIGINAL_NOV10_ISSUANCE_PRESERVED;NO_NEW_SELECTION",
            additional_metrics=json.dumps(dict(metric, actual_offers=0, original_forecasts_changed=0,
                                               played_zero_players=5,
                                               unknown_missing_stat_rows=3,
                                               unknown_participation_unresolved=1), sort_keys=True))
        rows.append(row)
    row = dict.fromkeys(fields, "")
    row.update(owner="Original website", category="ALL12", procedure_id="CURRENT_BASELINE/reference_point",
        product="BASELINE_CAPTURE_METADATA_ONLY", source_panel="OWNER_COMMENT_6901141462",
        season=2026, week="CURRENT_CAPTURE",
        status="581_BASELINE_ROWS_CAPTURED;ZERO_RESEARCH_ROWS_ADMITTED",
        available=581, evidence_tier="C_IMMUTABLE_META_AND_SCHEDULED_RUN_READBACK;SERVED_VALUES_OWNER_REPORTED",
        source_artifacts=json.dumps([str((D / "delivery/RECEIPT.json").relative_to(ROOT))]),
        verification_limit="581 forecasts are not actual-line selected decisions or research activation. C fetched meta and run, not full rows or a current browser.",
        required_next_owner_action="Original owner retains existing consumer/admission and qualified capture jobs; CountA requires fresh authorized producer feed and separate consumer admission.",
        row_kind="BASELINE_CAPTURE_NOT_RESEARCH_ACTIVATION", issuance_state="BASELINE_ONLY_CAPTURE",
        additional_metrics=json.dumps(dict(research_admitted=0, scheduled_run="43753723588",
                                          data_commit="0e37e02fecb88dc8835c4c3d694958a61ba174af"), sort_keys=True))
    rows.append(row)
    for row in rows:
        key = {k: v for k, v in row.items() if k not in ["row_id", "coverage_entry_id"]}
        row["row_id"] = row["coverage_entry_id"] = sha(json.dumps(key, sort_keys=True).encode())
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writerows(rows)
    result = data + stream.getvalue().encode()
    assert result[:len(data)] == data
    TARGET.write_bytes(gzip.compress(result, compresslevel=9, mtime=0))
    # gzip.compress adds no filename; fixed mtime reproduces the final wire bytes.
    final = dict(core)
    final.update(recorded_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        core_intermediate_receipt=str(core_copy.relative_to(ROOT)),
        core_intermediate_decoded_SHA256=sha(data), core_intermediate_decoded_prefix_preserved=True,
        target=str(TARGET.relative_to(ROOT)), SHA256=sha(TARGET.read_bytes()),
        bytes=TARGET.stat().st_size, decoded_bytes=len(result), decoded_SHA256=sha(result),
        added_rows=894, total_rows=37451,
        outcome_status_rows=3, baseline_capture_status_rows=1,
        final_append_script=str(Path(__file__).relative_to(ROOT)),
        final_append_CPU_seconds=time.process_time()-START,
        C05_and_website_additions="Three original forecast-only numerical/law grade rows and one baseline-only metadata row; no new O/U denominator.")
    final["new_row_kind_counts"] = dict(core["new_row_kind_counts"],
        C05_ORIGINAL_FORECAST_ONLY_QUALIFIED_GRADE=3,
        BASELINE_CAPTURE_NOT_RESEARCH_ACTIVATION=1)
    old_receipt.write_text(json.dumps(final, indent=2) + "\n")
    print(json.dumps({k: final[k] for k in ["total_rows", "added_rows", "SHA256", "final_append_CPU_seconds"]}))


if __name__ == "__main__":
    main()
