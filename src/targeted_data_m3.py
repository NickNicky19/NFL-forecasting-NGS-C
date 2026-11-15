"""Deterministic retained-input preparation for the bounded C M3 comparison.

No acquisition, model fit, grading or source-clock inference occurs here.  The
ordinary source prefix and existing E0_OP feature semantics remain unchanged.
Historical statistical-row queries are explicitly reconstructed; the separately
qualified native offer identities also admit a query without a statistical row.
"""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import math
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from data_v2 import DAY, History, load, vector

TARGETS = ("rec", "rec_yd")
TRAIN_ROLES = ("RB", "WR", "TE")
QUERY_ROLES = ("WR", "TE")
BASE_SOURCE_COMMIT = "1bd6d071e2083ae060e601da0ac8c281296babc5"
BOOK_ORDER = {"pinnacle": 0, "draftkings": 1, "fanduel": 2}
OUTPUT_CAP_BYTES = 8 * 1024 * 1024
SOURCE_PATHS = (
    "artifacts/basic-football-facts-v2.1.zip",
    "sources/category-decision-release-01/current_facts_2026.csv.gz",
    "sources/category-decision-release-01/schedule.csv",
    "sources/category-decision-release-01/MODEL_INPUT_MANIFEST.json",
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def clean(value):
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [clean(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (float, np.floating)):
        return float(value) if math.isfinite(value) else None
    return value


def read(path):
    path = Path(path)
    data = path.read_bytes()
    return json.loads(gzip.decompress(data) if path.suffix == ".gz" else data)


def digest(value):
    return hashlib.sha256(
        json.dumps(clean(value), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def feature_names(target):
    names = [f"{target}_mean_last3", f"{target}_known_last3",
             f"{target}_mean_last8", f"{target}_known_last8"]
    names += [f"{target}_lag{i}_{s}" for i in range(1, 5)
              for s in ["value", "age_days", "missing"]]
    names += ["role_QB", "role_RB", "role_WR", "role_TE"]
    names += [f"player_{s}_{k}" for s in ["attempts", "carries", "targets"]
              for k in ["mean_last3", "rows_last3", "last"]]
    names += ["team_attempts_mean3", "team_carries_mean3", "team_sacks_mean3"]
    assert len(names) == 32
    return names


def _immutable_sources(root):
    previous = read(root / "reports/w1w9-comparison-closure-01/C-panels/"
                           "cmp-origin-extension/SOURCE_REBUILD_BINDINGS.json")
    expected = {r["path"]: r for r in previous["sources"]}
    bindings = []
    for name in SOURCE_PATHS:
        item = expected[name]
        assert item["immutable_commit"] == BASE_SOURCE_COMMIT
        path = root / name
        assert path.stat().st_size == item["bytes"] and sha(path) == item["SHA256"], name
        bindings.append(dict(item))
    return bindings


def _ordinary(root):
    with zipfile.ZipFile(root / SOURCE_PATHS[0]) as archive:
        original = pd.read_csv(io.BytesIO(archive.read("facts.csv.gz")),
                               compression="gzip", low_memory=False)
        original_schedule = pd.read_csv(io.BytesIO(archive.read("schedule.csv")))
    current = pd.read_csv(root / SOURCE_PATHS[1], low_memory=False)
    current_schedule = pd.read_csv(root / SOURCE_PATHS[2])
    assert list(original.columns) == list(current.columns)
    extra = current[(current.season == 2026) & current.week.isin([8, 9]) &
                    (current.season_type == "REG")].copy()
    extra_schedule = current_schedule[(current_schedule.season == 2026) &
                                     current_schedule.week.isin([8, 9]) &
                                     (current_schedule.game_type == "REG")].copy()
    assert not extra.game_id.isin(original.game_id).any()
    assert not extra_schedule.game_id.isin(original_schedule.game_id).any()
    assert not extra[["game_id", "player_id"]].duplicated().any()
    assert extra.game_id.isin(extra_schedule.game_id).all()
    assert extra_schedule[["home_score", "away_score"]].notna().all().all()
    facts = pd.concat([original, extra], ignore_index=True)
    schedule = pd.concat([original_schedule,
                          extra_schedule[list(original_schedule.columns)]], ignore_index=True)
    # Raw original records and order are preserved, including explicit nulls.
    pd.testing.assert_frame_equal(facts.iloc[:len(original)].reset_index(drop=True), original)
    pd.testing.assert_frame_equal(schedule.iloc[:len(original_schedule)].reset_index(drop=True),
                                  original_schedule)

    class MemoryInputs:
        def __truediv__(self, name):
            if name == "facts.csv.gz":
                return io.StringIO(facts.to_csv(index=False))
            if name == "schedule.csv":
                return io.StringIO(schedule.to_csv(index=False))
            raise ValueError(name)

    d, g, teams = load(MemoryInputs())
    return d, g, teams, {
        "original_rows": len(original), "appended_rows": len(extra),
        "original_schedule_rows": len(original_schedule),
        "appended_schedule_rows": len(extra_schedule),
        "original_prefix_preserved": True,
        "appended_season_weeks": [[2026, 8], [2026, 9]],
        "appended_source_rows_SHA256": digest(extra.to_dict("records")),
    }


def _native_offers(root, schedule):
    # This reads the accepted corrected ledger, not a new collector or grader.
    import actual_accuracy_v6 as accuracy
    from context_identity_view_c01 import corrected_rows

    records, receipts = accuracy.load_records()
    identity_path = root / "sources/propline-v7/historical_identity_crosswalk.json.gz"
    extra_identity_path = root / "artifacts/reliability-v8/IDENTITY_CROSSWALK.json.gz"
    crosswalk = read(identity_path) + [dict(r, season=2026) for r in read(extra_identity_path)]
    identities = {}
    for r in crosswalk:
        key = (int(r["season"]), int(r["week"]), r["player_id"])
        value = (r["team"], r["position"])
        assert key not in identities or identities[key] == value, "AMBIGUOUS_NATIVE_IDENTITY"
        identities[key] = value
    corrected = {}
    for r in corrected_rows():
        key = (r["game_id"], r["player_id"])
        value = (r["team"], r["position"])
        assert key not in corrected or corrected[key] == value
        corrected[key] = value
    games = {r["game_id"]: r for r in schedule.to_dict("records")}
    offers = {}
    method_fields = ["method_version", "selected_side", "status", "point", "point_type",
                     "p_under", "p_push", "p_over", "fallback", "forecast_id", "graded_UTC"]
    fields = ["record_kind", "offer_id", "game_id", "player_id", "player_name", "category",
              "season", "week", "position", "espn_event_id", "role_evidence_reference",
              "scoring_contract_id", "scoring_snapshot_id", "evidence_tier", "decision_horizon",
              "venue", "product", "line_tier", "period", "line", "comparator", "offered_sides",
              "actual", "appearance", "decision_UTC", "kickoff_UTC", "graded_UTC",
              "outcome_evidence_reference", "source_offer_evidence_reference",
              "source_snapshot_clocks", "source_event_commence_UTC"]
    for r in records:
        if (r["category"] not in TARGETS or r["position"] not in QUERY_ROLES or
                r["season"] != 2026 or not 1 <= r["week"] <= 9 or
                r["policy_id"] != "ALL_ELIGIBLE_OFFERS"):
            continue
        assert r["comparator"] == "STRICT_OVER_UNDER"
        assert r["period"] == "FULL_GAME_INCLUDING_OT"
        assert r["scoring_contract_id"] == "official-player-fullgame-OT-v1"
        identity = identities.get((r["season"], r["week"], r["player_id"]))
        if identity is None:
            identity = corrected.get((r["game_id"], r["player_id"]))
        assert identity is not None, "NATIVE_OFFER_IDENTITY_UNAVAILABLE"
        team, role = identity
        assert role == r["position"], "OFFER_ROLE_CONFLICT"
        game = games[r["game_id"]]
        assert team in [game["home_team"], game["away_team"]]
        if r.get("team") is not None:
            assert r["team"] == team
        projected = {k: r.get(k) for k in fields}
        projected.update(team=team, opponent_team=game["away_team"] if team == game["home_team"]
                         else game["home_team"],
                         identity_source="RETAINED_WEEKLY_NATIVE_ROSTER_CROSSWALK_OR_CORRECTED_IDENTITY",
                         authentic_pregame_role=False,
                         quote_clock_qualification="UNVERIFIED_RETAINED_LINE_DIAGNOSTIC",
                         main_alternate_qualification="UNKNOWN_NOT_ASSUMED_MAIN")
        key = r["offer_id"]
        if key in offers:
            # The same accepted outcome was graded separately for each method.
            # Keep those clocks per method; they are not quote/version clocks.
            invariant = [k for k in projected if k != "graded_UTC"]
            assert {k: offers[key][k] for k in invariant} == {
                k: projected[k] for k in invariant}, "OFFER_VERSION_CONFLICT"
            clocks = [v for v in [offers[key].get("graded_UTC"), projected.get("graded_UTC")]
                      if v is not None]
            offers[key]["graded_UTC"] = min(clocks) if clocks else None
        else:
            offers[key] = projected | {"retained_methods": {}}
        offers[key]["retained_methods"][r["method_id"]] = {k: r.get(k) for k in method_fields}
    repeated = sorted(offers.values(), key=lambda r: (r["season"], r["week"], r["game_id"],
                        r["player_id"], r["category"], BOOK_ORDER.get(r["venue"], 99), r["offer_id"]))
    grouped = defaultdict(list)
    for r in repeated:
        grouped[(r["game_id"], r["player_id"], r["category"])].append(r)
    primary = []
    for _, candidates in sorted(grouped.items()):
        chosen = min(candidates, key=lambda r: (BOOK_ORDER.get(r["venue"], 99), r["venue"],
                                               r["offer_id"]))
        primary.append(dict(chosen, source_selection_policy="M3_FIXED_PINNACLE_DK_FD_THEN_OFFER_ID",
                            repeated_offer_ids=[r["offer_id"] for r in candidates]))
    return primary, repeated, receipts, {
        "identity_crosswalk_path": str(identity_path.relative_to(root)),
        "identity_crosswalk_SHA256": sha(identity_path),
        "additional_book_identity_crosswalk_path": str(extra_identity_path.relative_to(root)),
        "additional_book_identity_crosswalk_SHA256": sha(extra_identity_path),
        "policy": "For each player/game/target choose Pinnacle, then DraftKings, then FanDuel; "
                  "then lexicographic original offer_id. No outcome/model-dependent quote selection.",
        "dedup_key": ["game_id", "player_id", "category"],
        "primary_opportunities": len(primary), "retained_repeated_book_opportunities": len(repeated),
        "offer_weeks": sorted({r["week"] for r in primary}),
        "source_clock_main_alternate_holds_retained": True,
    }


def prepare(root, out):
    """Return primitive rows, arrays and native offers; save <=8MiB new evidence.

    Returned ``rows`` preserve full role-appropriate ordinary training history.
    WR/TE query membership is indicated separately from RB/WR/TE training scope.
    A missing-stat native query never acquires a target label from participation.
    """
    root, out = Path(root).resolve(), Path(out).resolve()
    bindings = _immutable_sources(root)
    d, schedule, teams, rebuild = _ordinary(root)
    hist = History(d[d.season >= 2022], "player_id")
    teamhist = History(teams[teams.season >= 2022], "team")
    mask = (d.season >= 2022) & d.position.isin(TRAIN_ROLES)
    if "season_type" in d:
        mask &= d.season_type == "REG"
    pool = d.loc[mask].to_dict("records")
    for r in pool:
        r["query_only"] = False
        r["query_universe_tier"] = "STAT_ROW_CONDITIONED_RECONSTRUCTION_NOT_PREGAME_ROSTER"
    native, repeated, receipts, source_policy = _native_offers(root, schedule)
    index = {(r["game_id"], r["player_id"]): i for i, r in enumerate(pool)}
    assert len(index) == len(pool)
    games = {r["game_id"]: r for r in schedule.to_dict("records")}
    added = []
    for offer in native:
        key = (offer["game_id"], offer["player_id"])
        if key in index:
            r = pool[index[key]]
            assert r["team"] == offer["team"] and r["position"] == offer["position"]
            r["native_offer_query"] = True
            continue
        game = games[offer["game_id"]]
        r = dict(game_id=offer["game_id"], player_id=offer["player_id"],
                 player_display_name=offer.get("player_name"), team=offer["team"],
                 opponent_team=offer["opponent_team"], position=offer["position"],
                 season=offer["season"], week=offer["week"], home_team=game["home_team"],
                 kickoff=float(game["kickoff"]), available=None, values={t: None for t in TARGETS},
                 played=False, game_final=None, query_only=True, native_offer_query=True,
                 query_universe_tier="RETAINED_NATIVE_OFFER_IDENTITY_WITHOUT_STAT_ROW;NOT_AUTHENTICATED_PREGAME_ROSTER")
        index[key] = len(pool)
        pool.append(r)
        added.append({"game_id": key[0], "player_id": key[1], "team": r["team"],
                      "position": r["position"], "all_target_labels_unknown": True})
    names = {t: feature_names(t) for t in TARGETS}
    matrices = {t: np.asarray([vector(r, t, hist, teamhist, "E0_OP") for r in pool], float)
                for t in TARGETS}
    assert all(x.shape == (len(pool), 32) for x in matrices.values())
    bank_path = root / "artifacts/reliability-v8/REFERENCE_BANK.json.gz"
    bank = read(bank_path)
    trace = []
    for key, reference in bank["references"].items():
        t = key.split("|", 1)[0]
        if t not in TARGETS:
            continue
        saved = reference["saved"]
        identity = (saved["game_id"], saved["player_id"])
        if identity not in index:
            continue
        i = index[identity]
        expected = np.array([np.nan if v is None else v for v in saved["features"]], float)
        assert np.array_equal(matrices[t][i], expected, equal_nan=True), "FROZEN_NATIVE_FEATURE_MISMATCH"
        assert pd.Timestamp(reference["fit_origin_UTC"]).timestamp() <= pool[i]["kickoff"]
        trace.append({"target": t, "game_id": identity[0], "player_id": identity[1],
                      "features_equal": True, "feature_SHA256": digest(matrices[t][i]),
                      "origin_UTC": reference["fit_origin_UTC"]})
    assert all(any(q["target"] == t for q in trace) for t in TARGETS)
    query_masks = {str(w): [i for i, r in enumerate(pool) if r["season"] == 2026 and
                           r["week"] == w and r["position"] in QUERY_ROLES]
                   for w in range(1, 10)}
    fields = ["game_id", "player_id", "player_display_name", "team", "opponent_team", "position",
              "season", "week", "home_team", "kickoff", "available", "played", "query_only",
              "native_offer_query", "query_universe_tier"]
    member_facts = [{k: r.get(k) for k in fields} | {"values": {t: r["values"][t] for t in TARGETS}}
                    for r in pool]
    sourcebindings = {
        "id": "C-M3-RETAINED-DATA-v1", "sources": bindings, "rebuild": rebuild,
        "code_SHA256": sha(Path(__file__)),
        "core_code": {p: sha(root / "src" / p) for p in ["data_v2.py", "contracts_v2.py"]},
        "history": "H-MULTI expanding2022+; kickoff+7days strictly before each query/origin; "
                   "current-vintage chronological reconstruction, not authenticated historical publication",
        "source_policy": source_policy, "accepted_offer_dataset_receipts": receipts,
        "native_query_additions": added, "native_reference_bank_SHA256": sha(bank_path),
        "native_feature_trace": trace,
        "training_roles": list(TRAIN_ROLES), "primary_query_roles": list(QUERY_ROLES),
        "query_count_by_week": {w: len(v) for w, v in query_masks.items()},
        "M3_2_block": {"status": "NOT_PREPARED_IN_THIS_ADAPTER",
                       "dependency": "A matched earlier-only own/opponent context matrix for every "
                       "training and query row, with denominator/source qualification. Existing C01 "
                       "context vectors cannot silently be attached to unmatched older rows. "
                       "M3-1 execution does not wait for this block.",
                       "existing_builder": "src/context_features_c01.py:Context"},
        "new_model_fits": 0, "new_actual_offer_grades": 0, "new_source_requests": 0,
        "population_limitation": "Stat-row-conditioned historical queries plus native offer identities; "
                                 "not an authenticated pregame league roster universe",
        "known_zero_and_unknown": "Retained qualified target labels only. Missing statistical rows "
                                  "remain null; no participation-to-zero imputation.",
    }
    payloads = {
        "FEATURES_AND_MEMBER_FACTS.json.gz": {
            "schema": "C-M3-PRIMITIVE-FEATURES-v1", "rows": member_facts,
            "X_by_target": matrices, "feature_names": names, "query_indices_2026": query_masks,
        },
        "NATIVE_OFFERS.json.gz": {"primary": native, "repeated_book_views": repeated,
                                   "source_selection": source_policy},
        "SOURCE_BINDINGS.json": sourcebindings,
    }
    encoded = {}
    for filename, value in payloads.items():
        b = (json.dumps(clean(value), separators=(",", ":"), allow_nan=False) + "\n").encode()
        encoded[filename] = gzip.compress(b, mtime=0) if filename.endswith(".gz") else b
    assert sum(map(len, encoded.values())) <= OUTPUT_CAP_BYTES, "M3_PREPARATION_OUTPUT_CAP"
    out.mkdir(parents=True, exist_ok=True)
    for filename, data in encoded.items():
        path = out / filename
        if path.exists():
            assert path.read_bytes() == data, "PREPARED_INPUT_BYTES_FROZEN_DO_NOT_OVERWRITE"
        else:
            with path.open("xb") as handle:
                handle.write(data)
    return {"rows": pool, "schedule": schedule, "X_by_target": matrices,
            "feature_names": names, "nativeoffers": native, "repeated_book_offers": repeated,
            "sourcebindings": sourcebindings, "query_indices": query_masks,
            "history": hist, "team_history": teamhist,
            "saved_evidence_bytes": sum(map(len, encoded.values()))}
