"""Read-only retained-evidence feasibility; no author predictors/grader imported.

Run from the C repository root. The only write is EVALUATION_FEASIBILITY.json
beside this script. Saved statuses are inventoried, never recomputed.
"""
from pathlib import Path
from collections import Counter
import csv
import gzip
import hashlib
import io
import json
import resource
import sys
import time
import zipfile
from datetime import datetime, timezone


ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent


def read(relative):
    p = ROOT / relative
    b = p.read_bytes()
    return json.loads(gzip.decompress(b) if p.suffix == ".gz" else b)


def sha(relative):
    return hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def run():
    started = time.process_time()
    bindings = {}
    def bind(p):
        bindings[p] = {"path": p, "bytes": (ROOT / p).stat().st_size, "SHA256": sha(p)}
        return read(p)
    run_path = "reports/player-context-matchup-01/v1.1/RUN.json"
    runs = bind(run_path)
    native_path = "artifacts/player-context-matchup-01/native-query-extension-v1/FULL_OFFER_ROWS.json.gz"
    native = bind(native_path)
    canonical_path = "artifacts/player-context-matchup-01/CANONICAL_REPORT_ROWS.json.gz"
    canonical = bind(canonical_path)
    scores_path = "reports/player-context-matchup-01/ACTUAL_LINE_SCORES.json.gz"
    scores = bind(scores_path)
    cases_path = "artifacts/predictive-C01/APPROVED_OFFER_CASES.json.gz"
    cases = bind(cases_path)
    numerical = bind("artifacts/player-context-matchup-01/v1.1/NUMERICAL_ROWS.json.gz")
    exported = bind("artifacts/player-context-matchup-01/v1.1/FEATURE_EXPORT.json.gz")
    bind("reports/player-context-matchup-01/v1.1/FOOTBALL_INPUT_BINDINGS.json")
    fit_repro = bind("reports/player-context-matchup-01/acceptance-v1/FIT_REPRODUCTION_FINAL.json")
    for p in ["src/context_experiment_c01.py", "src/context_features_c01.py", "src/data_v2.py",
              "src/context_native_queries_c01.py", "src/context_report_c01.py",
              "protocol/PLAYER_CONTEXT_MATCHUP_01_C_V1_1.json"]:
        bindings[p] = {"path": p, "bytes": (ROOT / p).stat().st_size, "SHA256": sha(p)}
    protocol = bind("reports/abc-championship/CURRENT_PROTOCOL.json")
    for key in ["protocol", "scorer", "population_offers_outcomes"]:
        b = protocol[key]
        assert sha(b["path"]) == b["SHA256"]
        bindings[b["path"]] = b
    rows = [r for r in canonical if r["method"] == "P1_MEAN_DIRECTION" and r["position"] in ["WR", "TE"]]
    assert len(rows) == len({r["offer_id"] for r in rows}) == 278
    fields = ["offer_id", "game_id", "player_id", "category", "position", "line", "week", "season",
              "actual", "appearance", "venue", "scoring_contract_id", "line_tier", "decision_UTC"]
    contract = sorted([{k: r[k] for k in fields} for r in rows], key=lambda r: r["offer_id"])
    common = {}
    for method in ["E0", "P1_MEAN_DIRECTION", "P1_MEDIAN_DIRECTION", "P1", "P2"]:
        rr = [r for r in canonical if r["method"] == method and r["position"] in ["WR", "TE"]]
        observed = sorted([{k: r[k] for k in fields} for r in rr], key=lambda r: r["offer_id"])
        assert observed == contract
        common[method] = {"eligible": len(rr), "available": sum(r["selected_side"] is not None for r in rr),
                          "saved_status_counts": dict(Counter(r["status"] for r in rr)),
                          "contract_SHA256": digest(observed)}
    decided_ids = sorted(r["offer_id"] for r in rows if r["status"] in ["WIN", "LOSS"])
    assert len(decided_ids) == 255
    baseline_scores = {}
    for method in ["E0", "P1_MEAN_DIRECTION", "P1_MEDIAN_DIRECTION", "P1", "P2", "ALWAYS_OVER", "ALWAYS_UNDER", "RETAINED_EARLIER_PREVALENCE_V8"]:
        ss = [r for r in scores if r["method"] == method and r["scope"] == "WR_TE" and r["week"] == "ALL"]
        assert len(ss) == 1
        x = ss[0]
        # Independent integer reconciliation of already-saved grades, not a
        # new label/side/grader execution.
        rr = [r for r in canonical if r["method"] == method and r["position"] in ["WR", "TE"]]
        for side in ["OVER", "UNDER"]:
            sr = [r for r in rr if r["selected_side"] == side]
            nw = sum(r["status"] == "WIN" for r in sr)
            nl = sum(r["status"] == "LOSS" for r in sr)
            expected = x[side]
            assert len(sr) == expected["selected"] and nw + nl == expected["decided"]
            assert (nw == expected["wins"] and nl == expected["losses"]) if nw + nl else expected["rate"] is None
        assert x["OVER"]["decided"] + x["UNDER"]["decided"] == x["COMBINED"]["decided"]
        baseline_scores[method] = {k: x[k] for k in ["OVER", "UNDER", "COMBINED", "eligible", "unavailable", "states", "games", "mean_Brier", "mean_log_loss"]}
    models = []
    for p, expected in runs["models"].items():
        if not p.endswith("-P1.json.gz"):
            continue
        assert sha(p) == expected
        m = bind(p)
        assert m["model"]["type"] == "L2_POOLED_POISSON" and not m["model"]["partial"]
        assert len(m["model"]["impute"]) == 60 and len(m["model"]["coef"]) == 120
        origin = Path(p).name[:8]
        meta = next(x for x in runs["origins"] if x["origin"] == origin)
        models.append({"origin": origin, "path": p, "SHA256": expected,
                       "fit_cutoff_UTC": m["fit_cutoff_UTC"], "membership_SHA256": m["membership_SHA256"],
                       "training_fingerprint": m["training_fingerprint"], "training_rows": meta["training_rows"],
                       "query_rows": meta["query_rows"], "alpha": m["model"]["alpha"],
                       "iterations": m["model"]["iterations"], "converged": m["model"]["converged"]})
    assert len(models) == 8 and {x["origin"][:4] for x in models} == {"2026"}
    p1 = [r for r in numerical if r["procedure"] == "P1"]
    annual = bind("reports/category-decision-release-01/follow-through-v1/peer-intake/OWNER_DECISION_ROWS.json")
    a_rec = next(r for r in annual["rows"] if r["category"] == "rec")
    assert a_rec["own_sides"]["COMBINED"]["decided"] == 579
    annual_common = bind("reports/category-decision-release-01/CATEGORY_PRODUCT_DECISIONS.json")
    c_rec = next(r for r in annual_common["categories"] if r["category"] == "rec")
    assert c_rec["COMBINED"]["wins"] == 239 and c_rec["COMBINED"]["decided"] == 412
    with zipfile.ZipFile(ROOT / "artifacts/basic-football-facts-v2.1.zip") as z:
        raw = gzip.decompress(z.read("facts.csv.gz"))
        ordinary_years = dict(Counter(r["season"] for r in csv.DictReader(io.StringIO(raw.decode()))))
    source_report = "reports/next-generation-information-01/feasibility/personnel-source/ACTUAL_COVERAGE.json"
    source = bind(source_report) if (ROOT / source_report).exists() else None
    report = {
        "id": "C-NEXTINFO-EVALUATION-FEASIBILITY-v1", "checked_UTC": datetime.now(timezone.utc).isoformat(),
        "status": "EVALUATION_READY_PERSONNEL_SOURCE_BLOCKED_NO_NEW_FIT",
        "scope": "Standard-library read/hash/inventory of retained evidence. No predictors, author graders, fits, raw transfer, source collection or new NFL scoring.",
        "native_panel": {"period": "2026 W2-W3", "venue": "Pinnacle", "raw_offers": len([r for r in native if r["method"] == "P1"]),
                         "WR_TE_eligible": len(rows), "WR_TE_decided": len(decided_ids), "WR_TE_unknown": 23,
                         "games": len({r["game_id"] for r in rows}), "common_contract_SHA256": digest(contract),
                         "decided_offer_ids_SHA256": digest(decided_ids), "hash_contract_fields": fields,
                         "weekly": {str(w): {"eligible": sum(r["week"] == w for r in rows), "saved_states": dict(Counter(r["status"] for r in rows if r["week"] == w))} for w in [2, 3]},
                         "contracts": common, "saved_baseline_scores": baseline_scores,
                         "own_side_arithmetic": "Independently counted selected sides and saved WIN/LOSS flags for every retained listed control; no new grading or outcome mutation.",
                         "evidence_tier": "TIMING_UNVERIFIED_LAST_RECORDED_ACTUAL_LINE;CURRENT_REVISED_7DAY_RECONSTRUCTION;EXPOSED_DEVELOPMENT",
                         "line_tier": "UNVERIFIED_MAIN_ALTERNATE; no main-line-only assertion", "original_issuance_or_venue_settlement": False,
                         "source": cases["source"], "team_identity": "Some ordinary case team fields are null; existing native-query extension uses the retained native-week roster crosswalk, never target-game stat presence. Do not silently fill from current roster."},
        "annual_A_owner_local_panel": {"eligible_WR_TE": 469, "selected": 421, "decided": 412, "unavailable": 48, "selected_unknown": 9,
                                       "C_P1_mean": [239, 412], "strong_A_Leaf_mean_same_mask": [238, 412],
                                       "actual_weeks": [1, 2, 3, 4, 5], "row_access": "NOT_IN_C; public aggregate admission only; A executes joins via existing route",
                                       "do_not_substitute": "Old733/667 W1-W7 and A328/579 broader median are separate panels; no raw/clock parity or new-recipe inheritance."},
        "retained_P1": {"exact_product": "C::PLAYER-CONTEXT-MATCHUP-01::v1.1::P1::mean", "native_mean_method": "P1_MEAN_DIRECTION",
                        "models": models, "2025_P1_origin_models": "NOT_PRESENT_IN_RETAINED_RUN;2025 origins have only E1/E2/E3 HGB",
                        "training_years": "Ordinary outcome/history from2022; eligible labels and per-example features strict kickoff+7days. Context PBP loaded only2025/2026; older context is missing, not historical zero.",
                        "ordinary_archive_rows_by_season": ordinary_years,
                        "feature_contract": "32 E0_OP ordinary fields +22 own target/depth/down +6 opponent values =60; train-only median+missing design120, scale floor1, alpha0.1 Poisson log-link, max120/tol1e-7. No player identity coefficient in pooledP1.",
                        "population": "Training/query RB/WR/TE stat-row-conditioned reconstruction plus separately qualified22 native missing-stat queries. Not a complete historical pregame teammate universe.",
                        "numerical_population": {"query_rows": len(p1), "known": sum(r["known"] for r in p1), "unknown": sum(not r["known"] for r in p1), "origins": dict(Counter(r["origin"] for r in p1))},
                        "not_an_upstream_target_engine": "P1 directly predicts reception count; its mean is neither target share nor forecast team target count. Marginal means do not establish coherent allocation.",
                        "separate_products": "Native mean148/255; law/median149/255; partial law150/255. Annual mean239/412 cannot be copied onto native255 or probability/selection products."},
        "reuse": {"fresh_fit": "Prior acceptance independently reproduced P1 W1 exactly (0.278706CPU s,19605rows,86iterations); no repeat needed for unchanged control.",
                  "full_prior_fit_receipt": "reports/player-context-matchup-01/acceptance-v1/FIT_REPRODUCTION_FINAL.json", "environment": fit_repro["environment"],
                  "existing_native_extension": "22 historical identity-qualified missing-stat queries;0newfits,60.659497CPU s; do not repeat source acquisition or alias recovery.",
                  "source_grader_repairs": "Reuse accepted C strict identities/presence/coherence/native extension and common scorer. New status clocks/role-universe qualification is a new input contract, not another audit of passed paths."},
        "source_gate": {"status": "SOURCE_BLOCKED", "owner": "receiving_personnel_source / C source coordinator",
                        "evidence": source,
                        "blocker": "2026 injury asset has no per-row report_date/date_modified/availability clock and only reported-injury subset, not all healthy/active teammates. Retained snapshots demonstrate later designation changes. Historical pregame designations and full teammate denominator cannot be recovered from later snapshot/stat appearances.",
                        "do_not_do": "Do not attach latest injury rows to historical games, assume absent means healthy, infer inactive from no stats, invent injury penalties or call a source-vintage gap a runtime failure.",
                        "independent_next_action": "Preserve prospective observations with real clocks, event-effective roster/status unknowns and existing source owner; no duplicate collector. Existing numerical/direction delivery remains independent."},
        "resources": {"feasibility_CPU_seconds": time.process_time() - started, "feasibility_peak_RSS_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
                      "maximum_CPU_seconds": 90, "maximum_RSS_bytes": 1073741824, "maximum_new_retention_bytes": 1048576,
                      "network": 0, "new_fits": 0, "new_inference": 0, "new_NFL_scoring": 0},
        "bindings": list(bindings.values())}
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / "EVALUATION_FEASIBILITY.json"
    p.write_text(json.dumps(report, indent=2) + "\n")
    assert sum(x.stat().st_size for x in OUT.iterdir() if x.is_file()) < 1048576
    print(json.dumps({"status": report["status"], "report": str(p.relative_to(ROOT)), "bytes": p.stat().st_size,
                      "SHA256": hashlib.sha256(p.read_bytes()).hexdigest(), "resources": report["resources"]}))


if __name__ == "__main__":
    run()
