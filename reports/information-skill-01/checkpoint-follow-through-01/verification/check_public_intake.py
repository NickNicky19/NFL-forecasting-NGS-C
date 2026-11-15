"""Independent public-receipt arithmetic/binding check; no grading or fits."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
import gzip
import hashlib
import json
from pathlib import Path
import re
import resource
import time

ROOT = Path(__file__).resolve().parents[4]
PACKAGE = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(Path(path).read_text())


def digest(data):
    return hashlib.sha256(data).hexdigest()


def git_blob(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def count(value, decided):
    # A source's empty group retains N/A. Zero is used only to sum no decisions.
    if decided == 0 and value is None:
        return 0
    assert isinstance(value, int) and value >= 0
    return value


def source_body(proof):
    path = ROOT / proof["local_lossless_gzip"]
    wire = path.read_bytes()
    assert len(wire) == proof["gzip_bytes"]
    assert digest(wire) == proof["gzip_SHA256"]
    body = gzip.decompress(wire)
    assert len(body) == proof["bytes"]
    assert digest(body) == proof["SHA256"]
    assert git_blob(body) == proof["Git_blob"]
    assert proof["immutable_commit"] in proof["url"]
    return body


def run():
    started = time.process_time()
    a = read(PACKAGE / "intake/A_RECEIPT.json")
    b = read(PACKAGE / "intake/B_RECEIPT.json")
    checks = []

    for receipt, cap_key in [(a, "requests_cap"), (b, "request_cap")]:
        assert receipt["requests_used"] <= receipt[cap_key]
        assert receipt["new_C_fits"] == receipt["new_C_grades"] == 0
    ax = a["exact_report"]
    awire = (ROOT / ax["compressed_path"]).read_bytes()
    abody = gzip.decompress(awire)
    assert len(awire) == ax["compressed_bytes"] and digest(awire) == ax["compressed_SHA256"]
    assert len(abody) == ax["decoded_bytes"] and digest(abody) == ax["decoded_SHA256"]
    assert git_blob(abody) == ax["git_blob"]
    text = abody.decode()
    assert "before launching the scoring worker" in text
    assert "830.968258" in text
    table_rows = [r for r in text.splitlines() if r.startswith("| M1 ") or r.startswith("| M2 ")]
    table_rows = [r for r in table_rows if len(r.split("|")) >= 7 and re.search(r"\d+[–-]\d+", r)]
    assert len(table_rows) == 8
    published = a["public_arithmetic"]["checked_own_side_triads"]
    assert len(published) == 8
    for row, admitted in zip(table_rows, published):
        cells = [v.strip() for v in row.strip("|").split("|")]
        pairs = [tuple(map(int, re.match(r"(\d+)[–-](\d+)", c).groups())) for c in cells[1:4]]
        assert pairs[2] == (pairs[0][0] + pairs[1][0], pairs[0][1] + pairs[1][1])
        assert list(pairs[0]) == admitted["over"]
        assert list(pairs[1]) == admitted["under"]
        assert list(pairs[2]) == admitted["combined"]
        n, rate = re.search(r"/\s*(\d+)\s*/\s*([\d.]+)%", cells[3]).groups()
        assert int(n) == sum(pairs[2]) == admitted["decided"]
        assert abs(Decimal(rate) - Decimal(100) * pairs[2][0] / int(n)) <= Decimal("0.0051")
    spent = Decimal(str(a["findings"]["recorded_C_join_CPU"]))
    cap = Decimal(900) + Decimal(360)
    assert cap == Decimal(1260) == Decimal(a["findings"]["new_user_cap"])
    headroom = cap - spent
    reserves = Decimal(a["findings"]["reserves"]["retention_CPU"]) + Decimal(a["findings"]["reserves"]["reporting_CPU"])
    assert headroom == Decimal("429.031742")
    assert headroom - reserves == Decimal("289.031742")
    assert Decimal(str(a["findings"]["recorded_new_headroom_arithmetic"])) == headroom
    assert Decimal(str(a["findings"]["recorded_before_reserves_ceiling"])) == headroom - reserves
    assert "not a complete measured total" in a["findings"]["metering_limit"]
    checks.append(dict(
        name="A_ACTUAL_BODY_AND_OLD_AGGREGATES_AND_SINGLE_EXTENSION",
        status="PASS", Git_blob=ax["git_blob"], old_grade_triads=8,
        new_M3_worker_grades=0, recorded_spent=str(spent),
        cumulative_cap=str(cap), headroom_including_reserves=str(headroom),
        worker_ceiling_before_reserves=str(headroom-reserves),
        scope="Public receipt/budget arithmetic; not private row, source clock or model parity.",
    ))

    proofs = {proof["kind"]: proof for proof in b["source_proofs"]}
    bodies = {kind: source_body(proof) for kind, proof in proofs.items()}
    assert set(bodies) == {"report", "handoff", "reproduction", "final"}
    final = json.loads(bodies["final"])
    records = final["independent_native_grading"]["receipt"]["aggregate_records"]
    assert records == b["own_records"] and len(records) == 72
    grouped = defaultdict(list)
    for record in records:
        over, under, combined = [record[s] for s in ["OVER", "UNDER", "COMBINED"]]
        for group in [over, under, combined]:
            n = group["decided"]
            wins, losses = count(group["wins"], n), count(group["losses"], n)
            assert wins + losses == n
            if n:
                assert abs(Decimal(str(group["rate"])) - Decimal(wins)/n) <= Decimal("1e-15")
            else:
                assert group["rate"] is None
            assert group["selected"] >= n
        assert combined["decided"] == over["decided"] + under["decided"]
        assert combined["wins"] == count(over["wins"], over["decided"]) + count(under["wins"], under["decided"])
        assert combined["losses"] == count(over["losses"], over["decided"]) + count(under["losses"], under["decided"])
        assert record["eligible"] == record["available"] == combined["decided"]
        assert record["unknown"] == record["abstentions"] == record["pushes"] == 0
        grouped[(record["method"], record["policy"])].append(record)
    assert len(grouped) == 12
    all_rows = {}
    for key, group in grouped.items():
        overall = next(r for r in group if r["window"] == "ALL")
        weeks = [r for r in group if r["window"] != "ALL"]
        assert sorted(int(r["window"]) for r in weeks) == [5, 6, 7, 8, 9]
        assert [r["eligible"] for r in sorted(weeks, key=lambda r:int(r["window"]))] == [28,28,28,28,30]
        for side in ["OVER", "UNDER", "COMBINED"]:
            for metric in ["wins", "losses", "decided", "selected"]:
                assert sum(count(r[side][metric],r[side]["decided"]) for r in weeks) == overall[side][metric]
        assert sum(r["eligible"] for r in weeks) == overall["eligible"] == 142
        all_rows[key] = overall
    for method in ["SKILL_C0","SKILL_C1","SKILL_R0","SKILL_R1"]:
        assert all_rows[(method,"LAW")]["COMBINED"]["wins"] == 70
        assert all_rows[(method,"MEAN")]["COMBINED"]["wins"] == (68 if method.startswith("SKILL_C") else 72)
    assert b["controls"]["B0_mean"]["wins"] == 76
    assert b["controls"]["B2_law"]["wins"] == 75
    assert b["coverage"]["actual_line_2026_weeks"] == [5,6,7,8,9]
    assert "NOT_THE_COMPLETED_OLD_M2_JOIN" in b["new_early_information_product_join"]["state_in_retrieved_B_receipt"]
    checks.append(dict(
        name="B_EXACT_PUBLIC_BODIES_AND_NATIVE_OWN_COUNTS", status="PASS",
        source_files=len(bodies), own_side_records=72, week_sum_products=12,
        actual_line_weeks=[5,6,7,8,9], decided=142,
        new_early_information_grades="NOT_ESTABLISHED_IN_RECEIVED_SCOPE",
        scope="Exact received public aggregate rows and arithmetic; not independent raw grading/membership.",
    ))

    fit = json.loads(bodies["reproduction"])
    assert fit["status"] == "FAILED_PRESERVED_NO_AUTOMATIC_RETRY"
    assert fit["all_fit_comparisons_passed"] is False and fit["all_passed"] is False
    attempts = {r["slot"].rsplit("-",1)[-1]:r for r in fit["attempts"]}
    tolerances = fit["tolerances"]
    c1 = attempts["C1"]["comparison"]
    assert c1["tolerance_pass"] is False
    assert c1["coefficient_max_absolute_difference"] > tolerances["coefficient_absolute"]
    assert c1["query_probability_max_absolute_difference"] > tolerances["prediction_absolute"]
    assert c1["objective_difference"] > tolerances["objective_absolute"]
    assert attempts["C1"]["success"] is True  # Optimizer success is not reproduction PASS.
    for method in ["R0","R1"]:
        assert attempts[method]["comparison"]["tolerance_pass"] is True
    diagnosis = fit["postfit_no_optimizer_diagnosis"]
    assert diagnosis["full_design_max_difference"] == 0
    assert diagnosis["membership_equal"] and diagnosis["labels_equal"] and diagnosis["penalty_exact_equality"]
    assert diagnosis["optimizer_calls"] == 0
    assert all(row["objective_difference"] == 0 and row["gradient_max_difference"] < 1e-9 for row in diagnosis["objective_probes"])
    assert "not persisted" in diagnosis["independent_full_beta_retention_limitation"]
    assert "plausible" in diagnosis["verdict"] and "not proved" in diagnosis["verdict"]
    assert fit["saved_law_checks"]["all_passed"] is True
    assert b["strict_reproduction"]["status"] == fit["status"]
    assert b["strict_reproduction"]["C1"] == c1
    checks.append(dict(
        name="B_STRICT_FIT_STATUS_AND_CHECKED_SCOPE", status="PASS_STATUS_PRESERVATION",
        C1_reproduction="FAILED", C1_coefficient_delta=c1["coefficient_max_absolute_difference"],
        C1_probability_delta=c1["query_probability_max_absolute_difference"],
        original_tolerances=tolerances, independent_full_C1_beta="NOT_RETAINED",
        numerical_termination="PLAUSIBLE_NOT_PROVED", mixers="PASS_REPORTED_COMPARISONS",
        saved_laws_and_integer_arithmetic="PASS_SEPARATE_SCOPE",
        additional_optimizer_calls=0, downstream_C1_parity="NOT_ESTABLISHED",
    ))
    source_path = PACKAGE / "PERSONNEL_SOURCE_DISPOSITION.json"
    source_review = dict(state="NOT_YET_PRESENT_AT_THIS_CHECK;NO_SOURCE_VERIFICATION_CLAIM")
    if source_path.exists():
        source_review = dict(state="FILE_RECEIVED_FOR_SEPARATE_SCOPE_REVIEW", file=str(source_path.relative_to(ROOT)),
                             SHA256=digest(source_path.read_bytes()))
    return dict(
        id="C-INFORMATION-SKILL-FOLLOWTHROUGH-PUBLIC-INTAKE-CHECK-v1",
        checked_UTC=datetime.now(timezone.utc).isoformat(),
        status="PASS_PUBLIC_ARITHMETIC_BINDINGS_AND_FAILURE_PRESERVATION",
        checks=checks, personnel_source=source_review,
        source_receipts=[dict(path=str((PACKAGE/"intake"/f).relative_to(ROOT)),
                              SHA256=digest((PACKAGE/"intake"/f).read_bytes()))
                         for f in ["A_RECEIPT.json","B_RECEIPT.json"]],
        scope="Independent C public arithmetic/binding/status review only. No private rows, source vintages, model restoration or fit reproduction newly inspected.",
        resources=dict(CPU_seconds=time.process_time()-started,
                       RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
                       new_fits=0,new_inference=0,new_grades=0,new_source_calls=0),
    )


if __name__ == "__main__":
    result = run()
    destination = PACKAGE / "verification/PUBLIC_INTAKE_CHECK.json"
    assert not destination.exists(), "VERIFICATION_RECEIPT_ALREADY_EXISTS"
    destination.write_text(json.dumps(result,indent=2)+"\n")
    print(result["status"], result["resources"])
