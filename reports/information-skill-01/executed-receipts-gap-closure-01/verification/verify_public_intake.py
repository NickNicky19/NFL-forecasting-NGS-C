#!/usr/bin/env python3
"""Read retained public receipts only; print JSON; never fetch, fit or grade rows.

Run from any directory: python /path/to/verify_public_intake.py > result.json
The redirected result is separate from every immutable input. This verifies
aggregate arithmetic and bindings, not private identities, clocks or fit parity.
"""
import collections
import csv
import datetime
import gzip
import hashlib
import io
import json
import pathlib
import time
import zipfile


START = time.process_time()
BASE = pathlib.Path(__file__).resolve().parents[1]
checks = []


def check(name, condition, detail=None):
    checks.append({"check": name, "status": "PASS" if condition else "FAIL", "detail": detail})


def sha(data):
    return hashlib.sha256(data).hexdigest()


def blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def load(path):
    return json.loads((BASE / path).read_text())


def number(row, field):
    # Empty win/loss cells occur for empty decided groups. They remain empty
    # in retained evidence; zero is used solely in additive aggregate checks.
    return int(row[field]) if row.get(field, "") != "" else 0


def validate_triads(rows, label):
    n = 0
    for row in rows:
        for side in ("OVER", "UNDER", "COMBINED"):
            w, l, d = [number(row, f"{side}_{x}") for x in ("wins", "losses", "decided")]
            rate = row.get(f"{side}_rate", "")
            check(f"{label}/{n}/{side}", w + l == d and
                  ((rate == "" and d == 0) or (rate != "" and d > 0 and abs(float(rate) - w / d) < 1e-12)))
        for field in ("wins", "losses", "decided", "selected"):
            check(f"{label}/{n}/combined_{field}", number(row, "COMBINED_" + field) ==
                  number(row, "OVER_" + field) + number(row, "UNDER_" + field))
        n += 1
    return {"rows": n, "side_triads": n * 3}


def validate_week_sums(rows, cumulative, weeks, label):
    groups = collections.defaultdict(list)
    for row in rows:
        groups[(row["procedure"], row.get("policy", ""))].append(row)
    fields = [f"{side}_{field}" for side in ("OVER", "UNDER", "COMBINED")
              for field in ("wins", "losses", "decided", "selected")]
    for group, values in groups.items():
        totals = [r for r in values if r["week"] == cumulative]
        weekly = [r for r in values if r["week"] in weeks]
        check(f"{label}/{group}/exact_week_set", len(totals) == 1 and
              len(weekly) == len(weeks) and {r["week"] for r in weekly} == set(weeks))
        if len(totals) != 1:
            continue
        for field in fields:
            check(f"{label}/{group}/{field}", number(totals[0], field) == sum(number(r, field) for r in weekly))
    return {"procedure_policy_groups": len(groups), "additive_fields_per_group": len(fields)}


a = load("intake/A_RECEIPT.json")
b = load("intake/B_RECEIPT.json")
d = load("delivery/RECEIPT.json")
source_inputs = {}
report_bytes = gzip.decompress((BASE / "intake/A_FOLLOW_THROUGH_V1.md.gz").read_bytes())
zip_bytes = (BASE / "intake/A_SCIENTIFIC_TABLES_V1.zip").read_bytes()
for proof, data in zip(a["source_proofs"], (report_bytes, zip_bytes)):
    check("A/source_sha256/" + proof["kind"], sha(data) == proof["SHA256"])
    check("A/source_git_blob/" + proof["kind"], blob(data) == proof["Git_blob"])
    check("A/source_size/" + proof["kind"], len(data) == proof["bytes"])
    source_inputs[proof["kind"]] = {"sha256": sha(data), "bytes": len(data), "commit": proof["immutable_commit"]}

z = zipfile.ZipFile(io.BytesIO(zip_bytes))
expected = a["source_proofs"][1]["members"]
check("A/ZIP/exact_member_set", set(z.namelist()) == set(expected))
members = {}
tables = {}
for name in z.namelist():
    check("A/ZIP/flat_member/" + name, pathlib.PurePosixPath(name).name == name)
    data = z.read(name)
    rows = list(csv.DictReader(io.StringIO(data.decode()))) if name.endswith(".csv") else [json.loads(data)]
    check("A/ZIP/member_count/" + name, len(rows) == expected[name])
    members[name] = {"sha256": sha(data), "bytes": len(data), "rows_or_objects": len(rows)}
    tables[name] = rows

arithmetic = {}
for name in ("B_EARLY_OWN_WEEKLY.csv", "B_EARLY_SELECTED_OWN_WEEKLY.csv", "B_SKILL_W1_W9_BROAD.csv"):
    rows = tables[name]
    is_full = name == "B_SKILL_W1_W9_BROAD.csv"
    arithmetic[name] = validate_triads(rows, name)
    arithmetic[name].update(validate_week_sums(rows, "ALL_W1_W9" if is_full else "ALL_W1_W4",
                                             [str(i) for i in range(1, 10 if is_full else 5)], name))
early = [r for r in tables["B_EARLY_OWN_WEEKLY.csv"] if r["procedure"].startswith("B_SKILL::")]
broad = tables["B_SKILL_W1_W9_BROAD.csv"]
check("A/new_SKILL_exact_early_rows", len(early) == 60)
check("A/new_SKILL_exact_broad_rows", len(broad) == 120)
cumulative = {r["procedure"].split("::")[1] + "_" + r["procedure"].split("::")[2]: r
              for r in broad if r["week"] == "ALL_W1_W9"}
early_cumulative = {r["procedure"].split("::")[1] + "_" + r["procedure"].split("::")[2]: r
                    for r in early if r["week"] == "ALL_W1_W4"}
own = {}
for name, row in cumulative.items():
    own[name] = {"Over": [number(row, "OVER_wins"), number(row, "OVER_losses")],
                 "Under": [number(row, "UNDER_wins"), number(row, "UNDER_losses")],
                 "Combined": [number(row, "COMBINED_wins"), number(row, "COMBINED_losses")],
                 "decided": number(row, "COMBINED_decided"), "Brier": float(row["Brier"]),
                 "log_loss": float(row["three_state_log_loss"])}
    check("A/broad_226/" + name, number(row, "COMBINED_decided") == 226 and number(row, "unknown_selected") == 0)
change_early = number(early_cumulative["SKILL_R0_MEAN"], "COMBINED_wins") - number(early_cumulative["SKILL_C0_MEAN"], "COMBINED_wins")
change_full = own["SKILL_R0_MEAN"]["Combined"][0] - own["SKILL_C0_MEAN"]["Combined"][0]
check("A/R0_early_minus2_later_plus4_full_plus2", (change_early, change_full - change_early, change_full) == (-2, 4, 2))
check("A/separate_law_records", [own[f"SKILL_{x}_LAW"]["Combined"][0] for x in ("C0", "C1", "R0", "R1")] == [112, 112, 110, 111])
check("A/full_probability_deterioration_R0_R1", all(own[f"SKILL_{x}_LAW"][metric] > own["SKILL_C0_LAW"][metric]
      for x in ("R0", "R1") for metric in ("Brier", "log_loss")))
check("A/strong_controls_owner_reported", a["interpretation"]["full_strong_retained_B0_mean"] == 119 and
      a["interpretation"]["full_strong_retained_B2_median_law"] == 122)
selected = [r for r in tables["B_EARLY_SELECTED_OWN_WEEKLY.csv"] if r["policy"] == "COVERAGE_10"]
check("A/early_capacity10_four_aggregate_sets", len(selected) == 20)
selected_signatures = collections.defaultdict(list)
for row in selected:
    selected_signatures[row["procedure"]].append({k: row[k] for k in ("week", "OVER_decided", "UNDER_wins", "UNDER_losses", "UNDER_decided", "COMBINED_selected")})
signature_hashes = [sha(json.dumps(sorted(v, key=lambda r: r["week"]), sort_keys=True).encode()) for v in selected_signatures.values()]
check("A/early_capacity10_equal_public_aggregate_signatures", len(set(signature_hashes)) == 1)
for row in selected:
    if row["week"] == "ALL_W1_W4":
        check("A/early_capacity10_own6to1Under/" + row["procedure"], (number(row, "OVER_decided"), number(row, "UNDER_wins"), number(row, "UNDER_losses")) == (0, 6, 1))

m3 = a["M3_admission_and_budget"]
stop = tables["C_JOIN_STOP.json"][0]
check("A/M3_stop_before_grades", stop["state"] == "NO_NEW_C_GRADES" and m3["new_C_grades"] == 0 and not m3["repaired_fixture_PASS_received"])
check("A/M3_exact_142_required", stop["native_source_rows"] == stop["reference_rows"] == stop["common_source_rows"] == 142)
check("A/M3_budget_arithmetic", abs(1260 - m3["charged_CPU"] - m3["recorded_remaining_total_including_reserves"]) < 1e-9 and
      abs(m3["recorded_remaining_before_reserves"] - 63.665819985) < 1e-9 and m3["additional_CPU_granted_by_current_continuation"] == 0)

for proof in b["exact_public_artifacts"]:
    packed = (BASE / proof["path"]).read_bytes()
    data = gzip.decompress(packed)
    check("B/artifact_size/" + proof["path"], len(data) == proof["bytes"] and len(packed) == proof["gzip_bytes"])
    check("B/artifact_hash/" + proof["path"], sha(data) == proof["sha256"] and sha(packed) == proof["gzip_sha256"])
    if "git_blob_sha1" in proof:
        check("B/artifact_blob/" + proof["path"], blob(data) == proof["git_blob_sha1"])
for i, row in enumerate(b["own_side_cumulative"]):
    for side in ("Over", "Under", "Combined"):
        x = row[side]
        check(f"B/own/{i}/{side}", x["wins"] + x["losses"] == x["decided"] and
              (x["rate"] is None if x["decided"] == 0 else abs(x["rate"] - x["wins"] / x["decided"]) < 1e-12))
    check(f"B/combined/{i}", all(row["Combined"][k] == row["Over"][k] + row["Under"][k] for k in ("wins", "losses", "decided")))
check("B/exact24_aggregate_products", len(b["own_side_cumulative"]) == 24)
repro = b["reproduction"]
check("B/team_strict_failure_preserved", repro["new_opportunity_team"]["status"] == "FAILED" and
      repro["new_opportunity_team"]["maximum_CDF_discrepancy"] > repro["new_opportunity_team"]["frozen_CDF_tolerance"])
check("B/oldC1_failure_preserved", repro["old_C1"]["status"].startswith("FAILED"))
for artifact in d["durable_artifacts"]:
    data = (BASE / "delivery" / artifact["path"]).read_bytes()
    check("website/retained_artifact/" + artifact["path"], len(data) == artifact["bytes"] and sha(data) == artifact["sha256"])
meta = load("delivery/BASELINE_META.json")
run = load("delivery/BASELINE_RUN.json")
check("website/direct_metadata_model_and_time", meta["execution_model"]["model"] == d["consumer_state_owner_reported"]["current_model"] and
      meta["generated_at"] == d["baseline_capture"]["generated_at_utc"])
check("website/direct_run_state", run["id"] == d["baseline_capture"]["run"] and run["conclusion"] == "success" and
      run["head_sha"] == d["baseline_capture"]["source_commit"])
check("website/baseline581_zero_research_not_activation", d["baseline_capture"]["rows"] == 581 and d["baseline_capture"]["research_rows_admitted"] == 0 and
      d["actions_here"]["model_or_primary_activation"] == 0)
check("website/CountA_no_current_feed", not d["Count_A_latest_received_owner_report"]["readable_current_feed_received"] and
      not d["Count_A_latest_received_owner_report"]["consumer_admitted"])

failures = [x for x in checks if x["status"] != "PASS"]
out = {
    "id": "C-EXECUTED-RECEIPTS-PUBLIC-INTAKE-CHECK-01",
    "created_UTC": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "status": "PASS_SCOPED_PUBLIC_AGGREGATES" if not failures else "FAIL",
    "checks": len(checks), "failed_checks": failures,
    "sources": source_inputs, "ZIP_members": members, "arithmetic": arithmetic,
    "new_SKILL_early_rows": len(early), "new_SKILL_full_rows": len(broad), "new_SKILL_full_own_records": own,
    "R0_mean_win_change": {"early": change_early, "later": change_full - change_early, "full": change_full},
    "strong_controls": {"B0_mean": "119/226 owner-public report; not C private regrading", "B2_median_law": "122/226 owner-public report; not C private regrading"},
    "early_capacity10": {"public_aggregate_signatures_equal": True, "aggregate_signature_sha256": signature_hashes[0],
        "records_each": "7 UNDER, 6 wins 1 loss; weekly selected 1,2,2,2; 7/84 coverage",
        "membership_identity": "OWNER_REPORTED_A_INDEPENDENT_CHECK; no public case identities or membership fingerprints supplied; equal aggregate hashes do not prove private membership",
        "not_four_independent_discoveries": True, "nineweek_selector_qualified": False},
    "M3": {"admitted_scope": "A adapter omission before grading, not C negative model result", "published_stop": stop,
        "required": "Reuse admitted dual-clock mapping; preserve source21:25/canonical21:05 and canonicalT90, exact142 identity/fingerprint parity; no row drops/relaxed clocks/tolerance",
        "repaired_fixture_received_PASS": False, "budget": m3,
        "additional_allowance": "NONE; exact additional request amount absent in received public receipt"},
    "B_opportunity": {"scientific_commit": b["source"]["scientific_commit"], "delivery_commit": b["source"]["delivery_commit"],
        "own_side_aggregate_records": 24, "scope": b["actual_line_scope"], "handoff": b["historical_handoff"],
        "reproduction": repro, "proper_scores": b["proper_scores"],
        "early_join": "Distinct OPP_BASE/OPP_MEAN/OPP_JOINT/DIRECT_ATT W1-W4 not supplied by completed SKILL early84; own authorization/accounting required",
        "new_A_SKILL_independent_B_verification": "Not inferred from stale B pending status or C aggregate intake"},
    "personnel": {"A_depth_inspection": "COMPLETED_CURRENT_VINTAGE_ONLY", "historical_status": "SOURCE_BLOCKED_ARTIFACT_VINTAGE_IDENTITY_EVENT_EFFECTIVE_UNIVERSE",
        "interpretation": "GSIS missing/remappable while dt unchanged; rank is not health/participation/alignment; preserve separately qualified B QB depth diagnostics"},
    "website": {"baseline_rows": 581, "research_rows_admitted": 0, "direct_C_scope": "Immutable metadata bytes and run receipt only; no fresh full581/served-byte/browser/mobile execution",
        "served_scope": "Owner machine receipt received, not independently reenacted by C", "CountA_current_feed_received": False,
        "selector": d["closed_selector_status"], "activation": False},
    "C05": "Separate eligible-version/outcome task; no player outcomes or grades asserted by this public-intake check",
    "limits": ["Public aggregate arithmetic and exact retained-file bindings only; no protected raw offers, source-clock authentication, model loading or fit reproduction",
        "Count-weighted public records do not recreate private masks, calibration, bootstrap uncertainty, original issuance or full nine-week selector qualification",
        "No new source calls, fits, solver retries, grading worker, upload/auth tests, scheduler, production writes or primary activation"],
    "CPU_seconds_self": time.process_time() - START, "CPU_cap": 12,
    "measurement_limit": "This process CPU excludes interpreter startup, earlier bounded metadata reads and tool overhead; not complete session CPU certificate"
}
print(json.dumps(out, indent=2, sort_keys=True))
raise SystemExit(1 if failures else 0)
