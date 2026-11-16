"""Append the received evidence to C's existing discovery/coordination records.

This performs no source request, model fitting, inference or grading.
Run after the bounded outcome operation and ledger append are complete.
"""
from pathlib import Path
import datetime
import hashlib
import json
import time

START = time.process_time()
ROOT = Path(__file__).resolve().parents[3]
D = Path(__file__).resolve().parent
COMMON = ROOT / "reports/abc-championship"


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def binding(path):
    path = Path(path)
    return dict(path=str(path.relative_to(ROOT)), bytes=path.stat().st_size,
                SHA256=hashlib.sha256(path.read_bytes()).hexdigest())


def main():
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    a = read(D / "intake/A_RECEIPT.json")
    b = read(D / "intake/B_RECEIPT.json")
    m3 = a["M3_admission_and_budget"]
    outcome = read(D / "C05-outcomes/resume-01/SOURCE_STATUS.json")
    admission = dict(
        id="C-EXECUTED-RECEIPTS-GAP-CLOSURE-ADMISSION-v1", recorded_UTC=now,
        coordinator="C", source_receipts={
            "A": binding(D / "intake/A_RECEIPT.json"),
            "B": binding(D / "intake/B_RECEIPT.json"),
            "website": binding(D / "delivery/RECEIPT.json"),
            "CountA_auth_coordination": binding(D / "intake/A_AUTH_COORDINATION.json")},
        A_actual_head=a["actual_head"], B_source=b["source"],
        A_SKILL=dict(early_weeks=[1, 2, 3, 4], early_offers=84,
                     full_weeks=list(range(1, 10)), full_decided=226,
                     receipt_scope="Owner-local public aggregates and immutable bindings; no C access to protected rows or source vintages.",
                     decision="NO_PREFERRED_REPLACEMENT;EXPOSED_TIMING_UNVERIFIED_ACTUAL_LINE_DIAGNOSTIC",
                     new_NFL_games=0, B_independent_new_join_review_received=False,
                     early_capacity10_same_seven_under_membership="OWNER_REPORTED;C verified aggregate signatures, not private IDs",
                     full_nine_week_selector_qualification=False),
        B_opportunity=dict(actual_offer_weeks=[5, 6, 7, 8, 9], offers_per_target=142,
                           missing_early_offer_weeks=[1, 2, 3, 4],
                           products=["OPP_BASE", "OPP_MEAN", "OPP_JOINT", "DIRECT_ATT"],
                           decision="CLOSE_RECIPE_NO_GAIN_EXACT_JOINT_RECIPE",
                           scope="Public arithmetic and typed handoff; not independent model restoration or private-row parity"),
        frozen_C_M3=m3,
        reproduction=dict(C1_strict="FAILED;independent full vector not retained",
                          opportunity_team_fit="FAILED_AT_FROZEN_TOLERANCE",
                          opportunity_share_fit="PASS_SEPARATE_SCOPE",
                          saved_row_grading="PASS_SEPARATE_SCOPE",
                          retries=0, relaxed_tolerances=0,
                          causal_forecast_loss_impact="NOT_ESTABLISHED"),
        personnel=dict(A_retained_depth_inspection="COMPLETED_OWNER_RECEIPT_ADMITTED",
                       authenticated_historical_personnel="SOURCE_BLOCKED",
                       missing_gates=["artifact vintage and revisions", "origin-qualified identity", "complete event-effective roster/status"],
                       current_vintage_depth_diagnostics="PRESERVED_WITH_EXISTING_LIMITS",
                       new_source_search=0),
        C05=dict(source_status=binding(D / "C05-outcomes/resume-01/SOURCE_STATUS.json"),
                 status=outcome["status"], outcome_packet=outcome["outcome_packet"],
                 independent_grade_check=binding(D / "verification/C05_GRADE_CHECK.json"),
                 resource=binding(D / "C05-outcomes/FINAL_RESOURCE.json"),
                 grade=outcome["grade"], original_forecast_rows=69,
                 actual_offers=0, new_original_picks=0,
                 verification="Original forecasts/issue clocks unchanged; prior failed logger retained; reused native proof retains old observation clock"),
        website=dict(baseline_capture_rows=581, new_research_admitted_rows=0,
                     C_direct_current_served_browser_check=False,
                     scope="C retrieved immutable metadata and scheduled run; owner-reported served checks remain scoped"),
        public_independent_check=binding(D / "verification/PUBLIC_INTAKE_CHECK.json"),
        no_new_model_fits=True, no_new_research_forecasts=True,
        new_primary_activation=False, old_records_preserved=True)
    write(D / "ADMISSION.json", admission)
    coverage = binding(ROOT / "reports/category-decision-release-01/W1_W9_AND_HISTORY_COVERAGE_V9.csv.gz")
    checkpoint = dict(
        id="INFORMATION-SKILL-01-EXECUTED-RECEIPTS-GAP-CLOSURE-C-v1",
        stage="ACTUAL_A_SKILL_EARLY_AND_B_OPPORTUNITY_ADMITTED;A_M3_ADAPTER_BUDGET_STOP;NO_PRIMARY_PROMOTION",
        recorded_UTC=now, report=binding(D / "README.md"),
        registration=binding(D / "REGISTRATION.json"), admission=binding(D / "ADMISSION.json"),
        queue=binding(D / "FINITE_QUEUE.json"), coverage_ledger=coverage,
        coverage_append=binding(D / "LEDGER_APPEND_RECEIPT.json"),
        A_SKILL_actual_offer_weeks=list(range(1, 10)), A_SKILL_full_decided=226,
        B_opportunity_actual_offer_weeks=[5, 6, 7, 8, 9],
        A_M3_accounting=m3, personnel="A_INSPECTION_COMPLETED;AUTHENTICATED_HISTORY_SOURCE_BLOCKED",
        reproduction="C1_STRICT_FAILED;OPPORTUNITY_TEAM_FIT_FAILED;OTHER_CHECKS_SEPARATELY_SCOPED",
        C05=admission["C05"], baseline_capture_not_research=581,
        current_CountA_feed_received=False, primary_activation=False,
        independent_public_check=admission["public_independent_check"])
    # Preserve former checkpoints as historical records, while making current status explicit.
    for name in ["CURRENT_PROTOCOL.json", "EXPORT_INDEX.json"]:
        path = COMMON / name
        obj = read(path)
        obj["executed_receipts_gap_closure_01"] = checkpoint
        obj["information_skill_follow_through_01"]["superseded_forward_by"] = binding(D / "ADMISSION.json")
        obj["information_skill_follow_through_01"]["current_status"] = checkpoint["stage"]
        obj["information_skill_follow_through_01"]["original_fields_are_historical_snapshot"] = True
        obj["information_skill_follow_through_01"]["current_A_M3_accounting"] = m3
        obj["information_skill_01"]["current_status"] = "SKILL_FULL_W1_W9_RECEIVED;NEW_OPPORTUNITY_DISTINCT;C_RECIPES_CLOSED"
        obj["category_decision_release_01"]["coverage_matrix"] = coverage
        obj["category_decision_release_01"]["latest_received_delivery"] = binding(D / "delivery/RECEIPT.json")
        write(path, obj)
    tasks = read(COMMON / "TASK_LEDGER.json")
    updates = {
        "A_FROZEN_C_M3_OWNER_LOCAL_JOIN": dict(
            state="STOPPED_BEFORE_GRADING_ADAPTER_OMISSION;NO_SAFE_FULL_WORKER_HEADROOM",
            artifact=str((D / "intake/A_RECEIPT.json").relative_to(ROOT)),
            next_action="A reviews scoped existing dual-clock repair and smallest existing fixture for full142 parity. Carry actual charges. If complete execution cannot safely fit, publish one quantified completion request with stages, reusable checkpoints and reserves; no new grant.",
            budget=m3),
        "A_B_INFORMATION_SKILL_EARLY_JOIN": dict(
            state="EXECUTED_84_EARLY_OFFERS;SOURCE_BOUND_226_W1_W9_RECEIVED",
            artifact=str((D / "intake/A_RECEIPT.json").relative_to(ROOT)),
            next_action="B independently checks permitted new SKILL outputs; C public aggregate admission complete. Do not repeat the join or substitute opportunity-v1 products."),
        "B_NEXT_DISTINCT_QB_OPPORTUNITY_HYPOTHESIS": dict(
            state="OPPORTUNITY_V1_EXECUTED_W5_W9;EXACT_JOINT_RECIPE_CLOSED_NO_GAIN",
            artifact=str((D / "intake/B_RECEIPT.json").relative_to(ROOT)),
            next_action="Preserve losses and failed team fit; early opportunity grades require exact typed handoff and separate A-owned allocation. No refit, retune or C-M3 budget transfer."),
        "C05_NEDET_FROZEN_GRADING": dict(
            state=outcome["status"], artifact=str((D / "C05-outcomes/resume-01/SOURCE_STATUS.json").relative_to(ROOT)),
            next_action="Retain append-only outcomes/grades and unknowns; no new offers, backdated picks or repeated source polling." if outcome["grade"] else outcome["remaining"]),
        "C_INFORMATION_SKILL_FOLLOW_THROUGH_01": dict(
            state="A_SKILL_EARLY_AND_B_OPPORTUNITY_RECEIVED;C05_QUALIFIED_FORECAST_ONLY_GRADES_APPENDED",
            artifact=str((D / "ADMISSION.json").relative_to(ROOT)),
            next_action="Preserve original follow-through as historical snapshot; use actual current receipt and task-specific accounting. No new model or primary activation."),
    }
    for task in tasks:
        if task.get("task_id") in updates:
            task["prior_state_preserved_in_git"] = True
            task.update(updates[task["task_id"]])
    new_task = dict(task_id="C_EXECUTED_RECEIPTS_GAP_CLOSURE_01", owner="C",
                    state="EXECUTED_SCOPED_ADMISSION_AND_OUTCOME_CHECK;PUBLICATION_IN_PROGRESS",
                    artifact=str((D / "ADMISSION.json").relative_to(ROOT)),
                    next_action="Complete normal C publication and immutable readback; no peer implementation or new primary product.")
    existing = next((t for t in tasks if t.get("task_id") == new_task["task_id"]), None)
    if existing is None:
        tasks.append(new_task)
    else:
        existing.update(new_task)
    write(COMMON / "TASK_LEDGER.json", tasks)
    ledger = read(COMMON / "ADMISSION_LEDGER.json")
    ledger["executed_receipts_gap_closure_01"] = checkpoint
    ledger["information_skill_follow_through_01"]["superseded_forward_by"] = binding(D / "ADMISSION.json")
    write(COMMON / "ADMISSION_LEDGER.json", ledger)
    write(D / "DISCOVERY_UPDATE.json", dict(recorded_UTC=now, metadata_only=True,
          touched=[str((COMMON / n).relative_to(ROOT)) for n in
                   ["CURRENT_PROTOCOL.json", "EXPORT_INDEX.json", "TASK_LEDGER.json", "ADMISSION_LEDGER.json"]],
          CPU_seconds=time.process_time()-START, old_sealed_evidence_not_modified=True))


if __name__ == "__main__":
    main()
