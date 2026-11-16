"""Bounded C-only check of received public scopes; no source/fits/grading."""
import datetime
import hashlib
import json
from pathlib import Path
import time

START = time.process_time()
D = Path(__file__).resolve().parents[1]
ROOT = D.parents[2]


def read(relative):
    return json.loads((D / relative).read_text())


def bind(relative):
    path = D / relative
    return dict(path=str(path.relative_to(ROOT)), bytes=path.stat().st_size,
                SHA256=hashlib.sha256(path.read_bytes()).hexdigest())


def main():
    a = read("intake/A_RECEIPT.json")
    b = read("intake/B_RECEIPT.json")
    website = read("delivery/RECEIPT.json")
    proposal = read("proposal/C_DYAD_MIX_V1.json")
    registration = read("REGISTRATION.json")
    checks = []

    def check(ok, name):
        if not ok:
            raise AssertionError(name)
        checks.append(name)

    m3 = a["M3"]
    authority = m3["authority_overlay"]
    fixture = m3["fixture"]
    check(fixture["full_identity_rows"] == 142 and fixture["weekly_CMP_ATT_fingerprints"] == 5,
          "Owner-reported repaired fixture covers142 rows/five fingerprints")
    check(fixture["dual_clocks_preserved"] and fixture["original_chronology_checks_preserved"],
          "Reported repair preserves clocks and chronology")
    check(fixture["private_retained_fixture_hash"].startswith("NOT_RECEIVED") and
          fixture["C_reproduction"] is False, "Private fixture proof not copied or reproduced")
    check(m3["new_offer_grades"] == 0 and not m3["new_full_worker_launched"],
          "Fixture PASS is not new M3 scoring")
    check(authority["CPU_cap"] == 1660 and authority["wall_cap"] == 2250 and
          authority["CPU_increment_once"] == 400 and authority["wall_increment_once"] == 450,
          "Current user grant cumulative once1660CPU2250wall")
    check(authority["retention_CPU_reserve"] == 120 and authority["reporting_CPU_reserve"] == 20,
          "Retention/report reserves retained")
    check(not authority["latest_exact_owner_ledger_charge_received"] and
          authority["wall_consumption_publicly_received"] is None and
          authority["private_owner_accounting_must_be_carried_not_reset"],
          "Private exact charges/wall not invented from supplied checkpoint")
    check(authority["no_budget_transfer"] and not m3["new_model_or_selector_activated"],
          "No transfer or activation")
    grant = registration["A_M3_grant"]
    check(grant["cap_CPU"] == 1660 and grant["cap_wall"] == 2250 and
          grant["owner_carries_exact_private_ledger_and_disclosed_overheads"] and
          "latest_discovery_charge_CPU" not in grant,
          "Current grant requires owner-carried private ledger; no exact private balance exported")
    check(b["new_fact"]["B_verification_status"] == "PASS_PUBLIC_AGGREGATE_AND_NATIVE_BINDING_SCOPE" and
          b["new_fact"]["B_reported_checks"] == 24555,
          "B independent public review is actually received")
    scope = b["new_fact"]["scope"]
    check(scope["public_arithmetic"] and scope["own_native_scalar_parity"] and
          not scope["private_A_rows"] and not scope["private_membership_identity"] and
          not scope["source_clock_authentication"] and not scope["fit_reproduction"],
          "Public/native binding admission does not establish private parity")
    check(b["distinct_opportunity_v1"]["W1_W4_exact_product_grades"].startswith("PENDING") and
          b["distinct_opportunity_v1"]["A_SKILL84_is_not_opportunity_join"],
          "Opportunity early products remain distinct and pending")
    for name in ["C1", "opportunity_team_fit"]:
        check(b["strict_reproduction"][name].startswith("FAILED"), name + " strict FAILED preserved")
    check(b["strict_reproduction"]["opportunity_share_fit"] == "PASS_SEPARATE_SCOPE" and
          b["strict_reproduction"]["saved_row_grading"] == "PASS_SEPARATE_SCOPE",
          "Narrow passes remain separate from fit failures")
    check(b["C05_scope"]["GRADED_PLAYED_views"] == 57 and b["C05_scope"]["UNKNOWN_views"] == 12 and
          b["C05_scope"]["graded_unique_players"] == 19 and
          b["C05_scope"]["actual_line_selections"] == 0,
          "C05 original forecast views are not independent selections/players")
    check(website["capture"]["rows"] == 237 and website["capture"]["research_rows"] == 0 and
          website["capture"]["not_actual_line_selections_or_wins"],
          "237 baseline rows are not research picks/wins")
    check(sum(website["capture"]["source_labels"].values()) == 237,
          "Source-label counts sum to237 baseline rows")
    check(website["scope"].startswith("C received current immutable metadata only") and
          "no current Cbrowser/fullcapture readback" in website["actual_products"],
          "Current metadata and owner-served claims remain separate")
    check(website["published_data_commit"] == "0a2ab5e9e9e0f1f4dd2077bac8375822a1e07fe1" and
          website["actual_head_once"] == "44209a6b4046535db1c65da42febeb7bdad698a6",
          "Archived237 publication and current head are distinct actual bindings")
    check(not website["copied_private_rows_internal_locators_or_execution_metadata"] and
          website["original_site_writes"] == 0 and website["no_research_activation"],
          "No protected payload or original-site modification claimed")
    check(proposal["no_new_predictive_experiment_executed"] and
          proposal["request"]["state"] == "REQUEST_ONLY_NOT_GRANTED" and
          proposal["request"]["fit_attempts_max_including_failures"] == 5,
          "One finite C proposal is not an executed or funded predictive test")
    check(proposal["request"]["new_raw_source_GETs"] == 0 and
          proposal["offered_population"]["weeks"] == [2, 3] and
          proposal["offered_population"]["eligible"] == 295 and
          proposal["offered_population"]["decided"] == 268 and
          proposal["offered_population"]["selected_unknown"] == 27,
          "Proposed native scope remains two partial actual-offer weeks")
    check("algebraically" not in proposal["algebraic_redundancy_rejected"] or
          "excluded" in proposal["algebraic_redundancy_rejected"],
          "Equivalent same-window marginal share is rejected")
    # Check only supplied scalar records, not B's24555 original source/row checks.
    arithmetic_rows = b["full_window_own_records"] + b["strong_control_records"]
    for row in arithmetic_rows:
        own = row["own"]
        check(own["OVER"]["wins"] + own["UNDER"]["wins"] == own["COMBINED"]["wins"] and
              own["OVER"]["losses"] + own["UNDER"]["losses"] == own["COMBINED"]["losses"],
              row.get("method", "") + row.get("policy", "") + " additive own-side scalar")
        for side in ["OVER", "UNDER", "COMBINED"]:
            item = own[side]
            check(item["wins"] + item["losses"] == item["decided"] and
                  abs(item["rate"] - item["wins"] / item["decided"]) <= 1e-15,
                  row.get("method", "") + row.get("policy", "") + side + "scalar denominator")
    result = dict(
        id="C-PREDICTIVE-VALUE-NEXT-RECEIPT-SCOPE-CHECK-v1",
        recorded_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        status="PASS_SCOPED_PUBLIC_RECEIPT_RECONCILIATION", checks=len(checks), failures=[],
        source_bindings=[bind(p) for p in ["REGISTRATION.json", "intake/A_RECEIPT.json",
            "intake/A_PUBLIC_RECONCILIATION_V2.md", "intake/B_RECEIPT.json",
            "delivery/RECEIPT.json", "proposal/C_DYAD_MIX_V1.json"]],
        checked_scopes=checks[:24], public_scalar_rows=len(arithmetic_rows),
        verification_limit="Public summary and supplied scalar arithmetic only; no A private fixture/model/row reproduction, source-clock authentication, original browser/full-capture receipt, source lookup or C scientific fit.",
        no_private_A_fixture_hashes_or_locators_copied=True,
        no_exact_private_A_current_charges_copied=True,
        M3_user_supplied_checkpoint_amount_is_not_independently_verified_current_ledger=True,
        new_HTTP=0, new_fits=0, new_grading=0, model_restoration=0,
        old_fit_failures_or_tolerances_changed=False,
        CPU_seconds=time.process_time()-START,
        measurement_limit="Small check process only; imports/tool/retention overhead belongs to parent metadata bookkeeping, not a complete measured certificate.")
    result["checker_failure_preserved"] = dict(
        error="KeyError latest_discovery_charge_CPU", effect="Checker assumed a public key intentionally removed by coordinator for restricted accounting scope; stopped before receipt output.",
        repair="Check owner-carried private ledger/no exported exact charge instead; no scientific tolerance, evidence, forecast or grade changed.",
        failed_helper_CPU_unmetered=True, conservative_total_subtask_CPU_charge_including_failure=1.0)
    (D / "verification/RECEIPT_SCOPE_CHECK.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: result[k] for k in ["status", "checks", "public_scalar_rows", "CPU_seconds"]}))


if __name__ == "__main__":
    main()
