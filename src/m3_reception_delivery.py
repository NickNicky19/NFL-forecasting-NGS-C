"""Manually produce the exact M3-0 reception mean and its two-step persistence proof."""
import gzip
import json
import lzma
import math
import re
from datetime import timedelta
from pathlib import Path

from m3_reception_delivery_window import (
    CONDITION, CONDITION_SHA, END, EVENT, EXPIRY, GAME, ISSUE_DEADLINE, PRODUCT, REPORT,
    ROOT, RUN, canonical, exclusive, instant, load, require, sha, stamp, utc,
)

FOLDER = ROOT / "prospective/runs" / RUN
SERVER = ROOT / "prospective/receipts" / (RUN + "-server.json")
FAMILY = PRODUCT.rsplit("::", 1)[0]
ROLES = ["WR", "TE"]
TARGET = {"season": 2026, "week": 12, "game_id": GAME, "native_event_id": EVENT,
          "away_team": "DEN", "home_team": "PIT", "kickoff_UTC": END}


def write_json(path, data):
    exclusive(path, canonical(data) + b"\n")


def bind(path):
    raw = path.read_bytes()
    return dict(path=path.relative_to(ROOT).as_posix(), bytes=len(raw), SHA256=sha(raw))


def fingerprint(value):
    return sha(canonical(value))


def recent_source_evidence(source):
    return {name: {k: body[k] for k in ("url", "bytes", "sha256", "observed_UTC", "headers")}
            for name, body in source.items() if name in ("schedule", "roster", "weekly")}


def check_storage(window, previous_work):
    from forward_budget_v4 import complete_C_roots, tree_bytes
    limits = window.amendment["C_limits"]["storage"]
    wt = load(ROOT / "reports/wave-closure-next-valid-01/RESOURCE_CLOSURE.json")
    roots = complete_C_roots([ROOT, window.work, previous_work, *Path("/workspace").glob("c0[456]*"),
                              *(r["path"] for r in wt["whole_C_roots"])])
    whole = sum(tree_bytes(p) for p in roots if p.exists())
    require(whole + limits["next_incremental_peak_max"] <= limits["whole_C_bytes"], "Insufficient whole-C working space")
    new = tree_bytes(window.work) + (tree_bytes(FOLDER) if FOLDER.exists() else 0)
    require(new <= limits["next_incremental_peak_max"], "Incremental working footprint")
    require(limits["reopened_working_bytes_after_publication"] + limits["previous_distinct_published_blob_version_bytes"] +
            limits["next_incremental_peak_max"] <= limits["simultaneous_new_bytes_including_retention"], "Peak storage")
    return {"whole_C_bytes": whole, "working_bytes": new}


def draft(window, previous_work):
    window.check(150, "2026-11-27T19:10:00Z", 190)
    check_storage(window, previous_work)
    from threadpoolctl import threadpool_limits
    import numpy as np
    from laws_v2 import LeafModel
    from safe_models_v4 import export_forest, infer_forest, validate_training_model
    from m3_reception_delivery_inputs import input_design
    from receiving_increment_query_c03 import _load_bytes
    from receiving_current_validation_c04 import close
    from targeted_data_m3 import feature_names
    spec = load(REPORT / "REC_MEAN_CURRENT_DELIVERY_REQUEST_V1.json")
    require(not window.state()["fit_attempts"] and not FOLDER.exists(), "Earlier draft or fit exists")
    with threadpool_limits(limits=1):
        (X, y, roles), query, summary = input_design(window.work, previous_work, window.state())
        feature_finished = stamp()
        window.claim_fit()
        fit_started = stamp()
        model = LeafModel("count", 1).fit(X, y, roles)
        fit_finished = stamp()
        safe = export_forest(model)
        model_bytes = gzip.compress(canonical(safe), mtime=0)
        private_model = window.work / "CURRENT_MODEL.json.gz"
        exclusive(private_model, model_bytes)
        reopened = _load_bytes(private_model.read_bytes())
        require(canonical(safe) == canonical(reopened), "Model did not reopen exactly")
        validate_training_model(reopened, X, y, roles)
        lookup = np.asarray([[np.nan if value is None else value for value in q["features"]] for q in query])
        positions = [q["position"] for q in query]
        native = model.laws(lookup, positions)
        restored = infer_forest(reopened, lookup, positions)
        require(all(close(a.mean(), b.mean()) for a, b in zip(native, restored)) and len(native) == len(restored) == len(query),
                "Native and reopened query means differ")
    summary["native_reopen_mean_max_absolute_difference"] = max(abs(a.mean() - b.mean()) for a, b in zip(native, restored))
    window.check(30, "2026-11-27T19:10:00Z")
    account = window.state()
    account["fit_attempts"][0].update(state="FITTED_AND_SAFELY_REOPENED", started_UTC=fit_started,
                                      completed_UTC=fit_finished, model_SHA256=sha(model_bytes))
    window.put(account)
    FOLDER.mkdir(parents=True, exist_ok=False)
    # One event's permitted derived inputs. Private source bodies and training rows stay off the public route.
    source_evidence = recent_source_evidence(account["source"])
    order = feature_names("rec")
    bridge = [{k: q[k] for k in ("player_id", "sleeper_id", "espn_player_id", "team", "opponent_team", "position")}
              for q in query]
    projection = dict(event=TARGET, product=PRODUCT, feature_order=order, rows=query)
    model_path = FOLDER / "CURRENT_MODEL.json.gz"
    query_path = FOLDER / "QUERY_PROJECTION.json"
    exclusive(model_path, model_bytes)
    write_json(query_path, projection)
    base_policy = {"recipe": spec["recipe"]["code"], "family": FAMILY, "order": order,
                   "update": "H-MULTI/E0_OP32/weekly_first_kickoff/strict_7d", "conditional_on": CONDITION}
    point_profile = {"family": FAMILY, "product": PRODUCT, "functional": "unrounded Law.mean()",
                     "corrector": "NO_EXTRA_CORRECTOR", "conditioning_contract_sha256": CONDITION_SHA}
    source_contract = {"target": "rec", "history": base_policy["update"], "event_role": ROLES,
                       "sources": [rec["url"] for rec in source_evidence.values()],
                       "conditioning_contract_sha256": CONDITION_SHA}
    receipt = {"event": TARGET, "observations": source_evidence, "cutoff_UTC": summary["information_cutoff_UTC"]}
    features = {"completed_UTC": feature_finished, "order_SHA256": fingerprint(order),
                "query_SHA256": fingerprint(projection), "identity_SHA256": fingerprint(bridge),
                "source_SHA256": fingerprint(receipt)}
    artifact = {"model": bind(model_path), "procedure_sha256": fingerprint(base_policy), "training": summary,
                "fit_started_UTC": fit_started, "fit_completed_UTC": fit_finished}
    model_version = fingerprint(artifact)
    fields = dict(target="rec", model_version=model_version, procedure_version=fingerprint(base_policy),
                  point_profile_sha256=fingerprint(point_profile), source_policy_sha256=fingerprint(spec["inputs"]["admission"]),
                  source_contract_sha256=fingerprint(source_contract), public_roles=ROLES)
    entry = dict(fields, scoring_target="rec", method_id=PRODUCT, base_learner_id="P2_LEAF",
                 artifact_sha256=model_version, model_bytes_sha256=sha(model_bytes), base_procedure_version=fingerprint(base_policy),
                 forecast_product="point_mean", prediction_functional="expected_mean", original_contract_version="C-M3-v1.1",
                 conditional_on=CONDITION, conditioning_contract_sha256=CONDITION_SHA)
    source = dict(fields, identity_bridge_sha256=fingerprint(bridge), source_receipt_sha256=fingerprint(receipt),
                  feature_capture_receipt_sha256=fingerprint(features), feature_binding_sha256=fingerprint({"order": order, "rows": query}),
                  query_projection_sha256=fingerprint(projection), query_source_sha256=fingerprint({"event": TARGET, "ids": bridge}),
                  information_cutoff_utc=summary["information_cutoff_UTC"], feature_capture_completed_at=feature_finished,
                  conditional_on=CONDITION, conditioning_contract_sha256=CONDITION_SHA, expires_at=EXPIRY)
    manifest = dict(state="ACTUAL_MODEL_AND_QUERY_PENDING_OWNER_ADMISSION", run=RUN, product=PRODUCT,
                    event=TARGET, model=bind(model_path), query=bind(query_path), model_artifact=artifact,
                    procedure=base_policy, point_profile=point_profile, source_contract=source_contract,
                    source_evidence=receipt, feature_capture=features, identity_bridge=bridge,
                    source_record_proposal=source, catalog_entry_proposal=entry, issued_at=None, prior_fit_reused=False)
    write_json(FOLDER / "INPUT_MANIFEST.json", manifest)
    return manifest


def verify_owner_admission(window, registry_body, catalog_body, verifier_receipt):
    """C checks the results of the real website owner's verifiers. C cannot issue capabilities."""
    window.check(30, "2026-11-27T19:28:00Z")
    m = load(FOLDER / "INPUT_MANIFEST.json")
    registry, catalog = json.loads(registry_body), json.loads(catalog_body)
    require(registry["schema_version"] == "stat-point-mae-source-registry-v2-expiring-v1" and
            catalog["schema_version"] == "stat-point-mae-public-catalog-v2-expiring-v1", "Wrong website wire")
    require(m["source_record_proposal"] in registry["records"] and m["catalog_entry_proposal"] in catalog["entries"],
            "Website did not bind the actual model/source/query")
    for doc in (registry, catalog):
        require(instant(m["source_record_proposal"]["feature_capture_completed_at"]) <= instant(doc["registered_at"]) <= utc(),
                "Missing genuine preissue registration time")
        require(re.fullmatch("[a-f0-9]{64}", doc["owner_admission_receipt_sha256"]), "Owner admission commitment missing")
    require(verifier_receipt["repository"] == "NickNicky19/nicks-expert-nfl-picks" and
            verifier_receipt["locator"].startswith("https://github.com/NickNicky19/nicks-expert-nfl-picks/"), "Original website owner required")
    wire = (window.work / "website_preissue.http").read_bytes()
    require(sha(wire) == verifier_receipt["owner_wire_sha256"], "Actual owner receipt required")
    response = load(window.work / "website_preissue-body.json")
    comments = response if isinstance(response, list) else [response]
    matches = [r for r in comments if r.get("html_url") == verifier_receipt["locator"] and
               r.get("author_association") in ("OWNER", "MEMBER", "COLLABORATOR")]
    require(len(matches) == 1 and verifier_receipt["owner_statement"].strip() and
            verifier_receipt["owner_statement"] in matches[0]["body"], "Website-owner registration attestation missing")
    require(verifier_receipt["model_bytes_sha256"] == m["model"]["SHA256"] and
            verifier_receipt["query_sha256"] == m["query"]["SHA256"], "Owner reviewed different bytes")
    document = dict(registry_sha256=fingerprint(registry), catalog_sha256=fingerprint(catalog),
                    registry_registered_at=registry["registered_at"], catalog_registered_at=catalog["registered_at"],
                    review=verifier_receipt, verified_UTC=stamp())
    write_json(window.work / "PREISSUE_ADMISSION.json", document)
    return document


def issue(window):
    window.check(30, "2026-11-27T19:34:00Z")
    import numpy as np
    from forward_sources_v4 import scoreboard_projection
    from receiving_current_capture_c04 import independent_response_clock, qualified_events
    from receiving_increment_query_c03 import _load_bytes
    from safe_models_v4 import infer_forest
    m = load(FOLDER / "INPUT_MANIFEST.json")
    admission = load(window.work / "PREISSUE_ADMISSION.json")
    n = window.state()["source"]["native"]
    raw = (window.work / "native.source").read_bytes()
    require(n["state"] == "OBTAINED" and sha(raw) == n["sha256"] and n["url"] == window.amendment["C_limits"]["sources"]["native_URL"],
            "Native body binding")
    source = {"id": RUN, "SHA256": sha(raw), "observed_UTC": n["observed_UTC"],
              "HTTP_Date": n["headers"]["Date"], "HTTP_Age": n["headers"]["Age"]}
    at = utc().timestamp()
    independent_response_clock(source, at)
    observed = scoreboard_projection(json.loads(raw), RUN, n["observed_UTC"])
    game = dict(espn=EVENT, game_id=GAME, away_team="DEN", home_team="PIT", season=2026, week=12,
                kickoff=instant(END).timestamp())
    accepted, _ = qualified_events([game], observed, at, after=instant(admission["verified_UTC"]).timestamp())
    require(set(accepted) == {GAME}, "Native event qualification failed")
    native = dict(accepted[GAME], game_id=GAME)
    expiry = min(instant(m["model_artifact"]["training"]["roster_publication_UTC"]) + timedelta(hours=36),
                 instant(n["observed_UTC"]) + timedelta(minutes=30), instant(END) - timedelta(minutes=5))
    require(expiry == instant(EXPIRY), "Actual producer expiry differs from cohort bound")
    query_bytes = (FOLDER / "QUERY_PROJECTION.json").read_bytes()
    model = (FOLDER / "CURRENT_MODEL.json.gz").read_bytes()
    require(sha(query_bytes) == m["query"]["SHA256"] and sha(model) == m["model"]["SHA256"], "Changed admitted bytes")
    queries = json.loads(query_bytes)["rows"]
    inferred = stamp()
    laws = infer_forest(_load_bytes(model), np.asarray([[np.nan if x is None else x for x in q["features"]] for q in queries]),
                        [q["position"] for q in queries])
    issued = stamp()
    require(instant(issued) < instant(ISSUE_DEADLINE) and len(laws) == len(queries), "Timing or incomplete inference")
    originals = []
    for q, law in zip(queries, laws):
        value = float(law.mean())
        require(math.isfinite(value) and value >= 0, "Invalid count mean")
        originals.append(dict(forecast_id=sha(canonical([RUN, GAME, q["player_id"], PRODUCT]))[:24],
                              product=PRODUCT, game_id=GAME, player_id=q["player_id"], position=q["position"],
                              team=q["team"], opponent_team=q["opponent_team"], sleeper_id=q["sleeper_id"],
                              expected_mean=value, selected_projection=value, prior_mixture=float(law.a),
                              attribution="PRIOR_ONLY" if law.a == 1 else "LEARNED_LEAF_WITH_EXPLICIT_PRIOR_TAIL",
                              inference_UTC=inferred, issued_UTC=issued, expires_UTC=EXPIRY))
    path = FOLDER / "FORECASTS.json.xz"
    exclusive(path, lzma.compress(canonical(originals), preset=3))
    require(json.loads(lzma.decompress(path.read_bytes())) == originals, "Original capture restoration")
    run = dict(run=RUN, event=TARGET, product=PRODUCT, state="ISSUED_AWAITING_GITHUB_PROOF", issued_UTC=issued,
               originals=bind(path), inputs=bind(FOLDER / "INPUT_MANIFEST.json"), registry=admission,
               native_status=native, native_source=source, actual_expiry_UTC=EXPIRY,
               coverage=m["model_artifact"]["training"]["coverage"], native=sum(r["prior_mixture"] < 1 for r in originals),
               prior_only=sum(r["prior_mixture"] == 1 for r in originals))
    write_json(FOLDER / "RUN.json", run)
    return run


def server_proof(window, run_metadata, capture_commit, original_readback):
    from m3_reception_delivery_io import BRANCH, REPO, git
    window.check(completion=True, before=ISSUE_DEADLINE)
    run = load(FOLDER / "RUN.json")
    require(sha(original_readback) == run["originals"]["SHA256"] and
            len(original_readback) == run["originals"]["bytes"], "Original readback mismatch")
    require(re.fullmatch("[0-9a-f]{40}", capture_commit) and
            git("show", capture_commit + ":" + str((FOLDER / "RUN.json").relative_to(ROOT))).encode() ==
            canonical(run), "Wrong capture commit")
    evidence = run_metadata
    require(evidence["repository"]["full_name"] == REPO and evidence["head_branch"] == BRANCH and
            evidence["path"].split("@")[0] == ".github/workflows/c-checks-pages.yml" and evidence["event"] == "pull_request" and
            evidence["status"] == "completed" and evidence["conclusion"] == "success", "Normal completed C PR check required")
    prs = evidence.get("pull_requests", [])
    correct_pr = any(pr["number"] == 65 and pr["head"]["sha"] == capture_commit for pr in prs)
    require(correct_pr or evidence["head_sha"] == capture_commit and not prs,
            "Run belongs to another revision")
    created, started, complete = (instant(evidence[k]) for k in ("created_at", "run_started_at", "updated_at"))
    require(instant(run["issued_UTC"]) <= complete and created <= started <= complete <= utc() < instant(ISSUE_DEADLINE),
            "Original persistence was not proved inside deadline")
    proof = dict(run=RUN, capture_commit=capture_commit, original_SHA256=sha(original_readback), original_bytes=len(original_readback),
                 workflow_run_id=evidence["id"], workflow_run_url=evidence["html_url"], created_UTC=evidence["created_at"],
                 started_UTC=evidence["run_started_at"], completed_UTC=evidence["updated_at"], actual_original_readback_UTC=stamp())
    write_json(SERVER, proof)
    return proof


def envelope(window):
    from current_query_delivery_c06 import m3_current_query_fingerprint, m3_leaf_current_records
    from receiving_increment_query_c03 import _load_bytes
    m, run, proof = (load(p) for p in (FOLDER / "INPUT_MANIFEST.json", FOLDER / "RUN.json", SERVER))
    original_bytes = (FOLDER / "FORECASTS.json.xz").read_bytes()
    require(sha(original_bytes) == proof["original_SHA256"], "Original changed after server proof")
    rows = json.loads(lzma.decompress(original_bytes))
    q = load(FOLDER / "QUERY_PROJECTION.json")
    require(len(q["rows"]) == len(rows), "Incomplete typed population")
    model_bytes = (FOLDER / "CURRENT_MODEL.json.gz").read_bytes()
    imputation = fingerprint(_load_bytes(model_bytes)["imputation"])
    training = m["model_artifact"]["training"]
    source = m["source_record_proposal"]
    out = []
    for original, x in zip(rows, q["rows"]):
        require(original["player_id"] == x["player_id"], "Query ordering changed")
        row = dict(original, category="rec", procedure_id=FAMILY, native_event_id=EVENT, feature_order=q["feature_order"],
                   features=x["features"], source_contract_SHA256=source["source_contract_sha256"],
                   query_admission_SHA256=run["registry"]["registry_sha256"],
                   information_cutoff_UTC=source["information_cutoff_utc"], source_observed_UTC=source["information_cutoff_utc"],
                   persisted_UTC=proof["completed_UTC"], kickoff_UTC=END)
        basis = dict(procedure_id=FAMILY, feature_order=q["feature_order"], model_SHA256=m["model"]["SHA256"],
                     source_contract_SHA256=row["source_contract_SHA256"], query_admission_SHA256=row["query_admission_SHA256"],
                     query_row_SHA256=m3_current_query_fingerprint(row), persistence_receipt_SHA256=bind(SERVER)["SHA256"],
                     fit_cutoff_UTC=training["fit_cutoff_UTC"], latest_training_available_UTC=training["latest_training_available_UTC"],
                     model_origin="2026-W12", target_game_exclusion_verified=True, query_role_membership_verified=True,
                     preprocessing="M3_E0_OP32_TRAINING_MEDIAN_PLUS_MISSING_MASK", corrector="NO_EXTRA_CORRECTOR",
                     imputation_SHA256=imputation)
        typed = m3_leaf_current_records(row, basis, model_bytes, stamp(), current_event=run["native_status"])
        selected = [item for item in typed if item["product_id"] == PRODUCT]
        require(len(selected) == 1 and selected[0]["available"] and selected[0]["point"] == original["expected_mean"] and
                selected[0]["prior_mixture_mass"] == original["prior_mixture"], "Original and typed mean differ")
        out.append(dict(original, query_fingerprint=basis["query_row_SHA256"], conditional_on=CONDITION,
                        conditioning_contract_sha256=CONDITION_SHA, forecast_product="point_mean", prediction_functional="expected_mean",
                        expected_mean_kind="full_law_expected_mean", label="Appearance-conditioned mean", mean_eligible=True,
                        functional_proof=None, fallback=original["attribution"] == "PRIOR_ONLY"))
    window.check(completion=True, before="2026-11-27T19:44:00Z")
    packet = dict(schema="C-M3-0-MANUAL-RECEPTION-MEAN-ENVELOPE-v1", run=RUN, event=TARGET, product=PRODUCT,
                  model=m["model"], query=m["query"], source=source, catalog_entry=m["catalog_entry_proposal"],
                  actual_website_admission=run["registry"], originals=run["originals"], server=proof, server_receipt=bind(SERVER),
                  coverage=run["coverage"], native=run["native"], prior_only=run["prior_only"], expires_at=EXPIRY,
                  issued_at=run["issued_UTC"], issue_deadline_utc=ISSUE_DEADLINE, prepared_UTC=stamp(), rows=out)
    write_json(FOLDER / "REC_MEAN_ENVELOPE.json", packet)
    return packet
