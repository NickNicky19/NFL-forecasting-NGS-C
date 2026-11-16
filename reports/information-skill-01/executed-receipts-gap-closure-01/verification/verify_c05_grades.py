#!/usr/bin/env python3
"""Independently check retained C05 facts/grades; no project grader or model imports.

Print JSON only. Uses original saved laws and minimum factual projections,
not raw provider responses. No HTTP, fitting, inference, source mutation or
offer reconstruction. CRPS is recomputed as an integer-CDF squared sum.
"""
import collections
import csv
import datetime
import decimal
import gzip
import hashlib
import io
import json
import lzma
import math
import pathlib
import time

START = time.process_time()
BASE = pathlib.Path(__file__).resolve().parents[1]
ROOT = BASE.parents[2]
RESUME = BASE / "C05-outcomes/resume-01"
checks = []


def check(label, condition):
    checks.append({"check": label, "PASS": bool(condition)})


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def integer(value, signed=False):
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        number = decimal.Decimal(str(value))
        if not number.is_finite() or number != number.to_integral_value() or (number < 0 and not signed):
            return None
        return int(number)
    except decimal.InvalidOperation:
        return None


def crps(law, actual):
    """Discrete CRPS=sum_k(F(k)-1{k>=y})**2, not common grader formula."""
    if law.get("kind") == "POISSON":
        mu = law["mu"]
        # All saved means are small. 512 bounds the numerical tail far below
        # 1e-14; recurrence uses no scipy or project law implementation.
        check("poisson_mean_in_bounded_integration_range", 0 <= mu < 40)
        mass, cdf, value = math.exp(-mu), 0.0, 0.0
        for k in range(513):
            if k:
                mass *= mu / k
            cdf += mass
            value += (cdf - int(k >= actual)) ** 2
        # Chernoff bound on first omitted survival; for these means this
        # underflows below machine precision. No test-score-selected cutoff.
        log_bound = -mu + 514 * (1 + math.log(mu / 514)) if mu else -math.inf
        check("poisson_omitted_survival_bound", log_bound < math.log(1e-14))
        return value
    check("saved_count_law_support", law["prior"]["kind"] == "count" and law["scale"] == 1)
    values, weights, q, alpha = law["values"], law["weights"], law["prior"]["q"], law["alpha"]
    check("saved_mass_and_prior_support", all(v >= 0 and int(v) == v for v in values) and
          all(w >= 0 and math.isfinite(w) for w in weights) and abs(sum(weights) - 1) < 1e-12 and 0 <= q < 1 and 0 <= alpha <= 1)
    stop = max(max(values, default=0), actual)
    result = sum(((1 - alpha) * sum(w for v, w in zip(values, weights) if v <= k) +
                  alpha * (1 - q ** (k + 1)) - int(k >= actual)) ** 2 for k in range(stop + 1))
    # Exact geometric-prior squared-survival tail after last empirical atom.
    return result + alpha ** 2 * q ** (2 * (stop + 2)) / (1 - q ** 2)


status = json.loads((RESUME / "SOURCE_STATUS.json").read_text())
resource = json.loads((RESUME / "PROCESS_RESOURCE.json").read_text())
packet_path = ROOT / status["outcome_packet"]["path"]
grade_path = ROOT / status["grade"]["path"]
packet, grades_packet = [json.loads(p.read_text()) for p in (packet_path, grade_path)]
forecasts = json.loads(lzma.decompress((ROOT / "prospective/runs/C-C05-NEDET-FIRST-01/FORECASTS.json.xz").read_bytes()))
outdir = packet_path.parent
for relative, expected in status["original_packet_hashes"].items():
    check("original_packet_hash/" + relative, digest(ROOT / relative) == expected)
check("outcome_packet_binding", digest(packet_path) == status["outcome_packet"]["SHA256"])
check("grade_binding", digest(grade_path) == status["grade"]["SHA256"])
for evidence in packet["source_evidence"]:
    check("factual_projection_hash/" + evidence["path"], digest(outdir / evidence["path"]) == evidence["SHA256"])
facts = list(csv.DictReader(io.StringIO(gzip.decompress((outdir / "evidence/player_facts.csv.gz").read_bytes()).decode())))
check("facts_exact_identity_unique", len(facts) == 72 and len({(f["game_id"], f["player_id"]) for f in facts}) == 72)
factmap = {(f["game_id"], f["player_id"]): f for f in facts}
outcomes = {(o["game_id"], o["player_id"], o["category"]): o for o in packet["outcomes"]}
grades = {g["forecast_id"]: g for g in grades_packet["grades"]}
physical = ["attempts", "carries", "targets", "receptions", "sacks_suffered", "passing_tds", "rushing_tds", "receiving_tds", "passing_2pt_conversions", "rushing_2pt_conversions", "receiving_2pt_conversions", "kickoff_returns", "punt_returns", "special_teams_tds"]
signed = ["passing_yards", "rushing_yards", "receiving_yards"]
by_model, absent, no_positive_proof, explicit_zeros, max_crps_error = collections.defaultdict(list), set(), set(), set(), 0.0
for row in forecasts:
    key = (row["game_id"], row["player_id"], row["category"])
    out, grade = outcomes[key], grades[row["forecast_id"]]
    check("forecast_only_contract", row["line"] is None and row["selected_side"] is None and row["category"] == "rec")
    check("grade_identity", all(grade[k] == row[k] for k in ("forecast_id", "game_id", "player_id", "category")))
    fact = factmap.get(key[:2])
    if fact is None:
        absent.add(row["player_id"])
        check("absent_preserved_UNKNOWN", out["appearance"] == grade["state"] == "UNKNOWN" and out["actual"] is None and grade["actual"] is None and out["unavailable_reasons"] == ["MISSING_STAT_ROW_NOT_ZERO_OR_DNP"])
        by_model[row["model_id"]].append(None)
        continue
    check("qualified_fact_event_team", fact["game_id"] == "2026_10_NE_DET" and fact["season"] == "2026" and fact["week"] == "10" and fact["season_type"] == "REG" and fact["team"] == row["team"] and fact["opponent_team"] == row["opponent_team"])
    proof = [k for k in physical if integer(fact.get(k)) is not None and integer(fact[k]) > 0]
    proof += [k for k in signed if integer(fact.get(k), True) not in (None, 0)]
    if not proof:
        no_positive_proof.add(row["player_id"])
        check("present_no_participation_proof_preserved_UNKNOWN", out["appearance"] == grade["state"] == "UNKNOWN" and
              out["actual"] is None and grade["actual"] is None and out["unavailable_reasons"] == ["PARTICIPATION_UNRESOLVED_NOT_DNP"])
        by_model[row["model_id"]].append(None)
        continue
    actual = integer(fact.get("receptions"))
    check("independent_participation_and_explicit_rec", bool(proof) and out["appearance"] == "PLAYED" and actual is not None and out["actual"] == grade["actual"] == actual and
          set(out["participation_proof_fields"]) == set(proof) and len(out["participation_proof_fields"]) == len(proof) and grade["state"] == "GRADED_PLAYED")
    if actual == 0:
        explicit_zeros.add(row["player_id"])
    score = crps(row["law"], actual)
    max_crps_error = max(max_crps_error, abs(score - grade["CRPS"]))
    check("independent_crps", abs(score - grade["CRPS"]) < 1e-12)
    check("independent_point_errors", abs(grade["median_error"] - (row["median"] - actual)) < 1e-12 and abs(grade["mean_squared_error"] - (row["mean"] - actual) ** 2) < 1e-12)
    by_model[row["model_id"]].append((row["mean"] - actual, row["median"] - actual, score))
metrics = []
for model, records in sorted(by_model.items()):
    values = [r for r in records if r is not None]
    n = len(values)
    metric = {"model_id": model, "eligible": len(records), "scored": n, "UNKNOWN": len(records) - n,
              "mean_MAE": sum(abs(r[0]) for r in values) / n, "mean_MSE": sum(r[0] ** 2 for r in values) / n,
              "mean_bias": sum(r[0] for r in values) / n, "median_MAE": sum(abs(r[1]) for r in values) / n,
              "CRPS": sum(r[2] for r in values) / n}
    reported = next(r for r in status["metrics"] if r["model_id"] == model)
    check("own_metric_reproduction/" + model, all(abs(metric[k] - reported[k]) < 1e-12 for k in ("mean_MAE", "mean_MSE", "mean_bias", "median_MAE", "CRPS")))
    metrics.append(metric)
check("exact69_23players_19qualified_4unknown", len(forecasts) == len(grades) == 69 and len(outcomes) == 23 and
      len(absent) == 3 and len(no_positive_proof) == 1 and all(m["scored"] == 19 and m["UNKNOWN"] == 4 for m in metrics))
check("exact_source_consumption", len(status["source_manifest"]) == 3 and sum(s["bytes_received"] for s in status["source_manifest"]) == 3053465 and status["resources"]["version_HEAD_attempts"] == 1 and status["resources"]["new_GETs"] == 2)
stats_source = status["source_manifest"][2]
check("eligible_stats_version_exact_HEAD", stats_source["HTTP_ETag"] == status["version_gate"]["HTTP_ETag"] and stats_source["HTTP_Last_Modified"] == status["version_gate"]["HTTP_Last_Modified"] and stats_source["eligible_new_version_vs_prior"] and stats_source["HTTP_ETag"] != status["version_gate"]["previous_source_version"]["HTTP_ETag"])
check("charged_CPU_carried_and_below_cap", abs(resource["total_charged_CPU_seconds"] - (resource["prior_charged_CPU_seconds"] + resource["full_child_CPU_seconds"] + resource["wrapper_CPU_seconds"] + resource["conservative_preparation_CPU"])) < 1e-12 and resource["total_charged_CPU_seconds"] == 15.94627805 < 30)
failed = [c for c in checks if not c["PASS"]]
result = {"id": "C05-INDEPENDENT-FACTS-AND-GRADES-CHECK-01", "created_UTC": datetime.datetime.now(datetime.timezone.utc).isoformat(),
          "state": "PASS_SCOPED_INDEPENDENT_GRADING" if not failed else "FAIL", "checks": len(checks), "failures": failed,
          "metrics": metrics, "max_absolute_CRPS_discrepancy": max_crps_error, "numeric_tolerance": 1e-12,
          "explicit_zero_reception_players": sorted(explicit_zeros), "absent_UNKNOWN_player_ids": sorted(absent),
          "present_but_no_participation_proof_UNKNOWN_player_ids": sorted(no_positive_proof),
          "scored_forecast_rows": 57, "UNKNOWN_forecast_rows": 12,
          "source_consumption": {"HEAD": 1, "GET": 3, "bytes": 3053465, "new_resume_GET": 2},
          "owner_operation_charged_CPU_before_independent_check": resource["total_charged_CPU_seconds"],
          "CPU_seconds_self": time.process_time() - START, "independent_check_CPU_cap": 5,
          "method": "Independent decimal validity/positive-stat participation and explicit receptions; saved-law CDF squared-sum CRPS (exact geometric tail; bounded Poisson recurrence), original point-error arithmetic. No common grade_run/law or model imports.",
          "initial_checker_failure_preserved": "First independent checker assumed all four UNKNOWN players absent and raised KeyError at missing CRPS for present all-zero Tay Martin; corrected checker distinguishes3absent+1present_no_proof. No outcome/grader/source changed. Initial failed check CPU unmetered; carry conservative0.1s plus bounded inspections, not complete total certificate.",
          "second_checker_failure_preserved": "C05_GRADE_CHECK_V1_FAILED_ORDER_ASSUMPTION.json retains12checks failing only because independent checker imposed ordered SIGNED proof fields on original set-valued field order. Exact proof sets/lengths are checked; no numeric tolerance or outcome qualification changed. That complete check CPU0.011319978 retained separately.",
          "limits": ["Checks retained minimum permitted facts/provenance only; raw memory-only response is not recovered, no new external source authentication or provider completeness assumption.", "One final game, conditional-on-appearance numerical forecast evidence; no offers, O/U decisions, DNP inference, model superiority or release qualification.", "Original expiry stops recommendation use but preserves frozen issuance and later grading.", "Process CPU excludes interpreter startup, bounded preceding read-only inspection and tool overhead; parent must carry any separate conservative verification allowance."]}
print(json.dumps(result, indent=2, sort_keys=True))
raise SystemExit(1 if failed else 0)
