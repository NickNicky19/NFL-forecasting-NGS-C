"""A compact, reused C01 context block for the separately registered M3-2 arm.

This module acquires nothing and fits/scores no model.  It preserves the
existing strict C01 raw-to-context definition and seven-day reconstructed
availability policy.  The information is not new; its controlled combination
with a new conditional-distribution family is the new tested mechanism.
"""
from __future__ import annotations

import copy
import gzip
import hashlib
import io
import json
import resource
import time
import zipfile
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

from context_features_c01 import Context, OWN_NAMES, OPP_NAMES
from targeted_data_m3 import _ordinary, clean, digest, read, sha

OWN_INDEX = [0, 1, 2, 3, 4, 8, 12, 13, 14, 15, 16]
FEATURE_NAMES = [OWN_NAMES[i] for i in OWN_INDEX] + list(OPP_NAMES)
REQUIRED_PBP = ["game_id", "play_id", "posteam", "pass_attempt", "sack",
                "two_point_attempt", "play_deleted", "play_type", "receiver_player_id",
                "air_yards", "down", "complete_pass", "yards_after_catch", "ydstogo",
                "yardline_100"]
SOURCE_FILES = [
    "sources/player-context-matchup-01/completion-decision-v1/pbp_facts_2024.csv.xz",
    "sources/player-context-matchup-01/pbp_facts_2025.csv.gz",
    "sources/player-context-matchup-01/pbp_facts_2026.csv.gz",
]
EXPECTED_SOURCE_HASHES = [
    "2e4ce6ad4f0a11bee49c1ecfc4f895e39de0a42566f230b57e00d555afca3a7b",
    "27828cc322333bd67602aea6df6a032cfb6c74cee34737bbe8b20fe02590dc8f",
    "36b6f89ea3a17de230d27a3b93c50294cf8febd9d0fd665b14c0eb979fc82e4e",
]
CPU_CAP = 90
RSS_CAP = 1288490188
OUTPUT_CAP = 3 * 1024 * 1024


def _checkpoint(start):
    assert time.process_time() - start <= CPU_CAP, "M3_CONTEXT_CPU_CAP"
    assert resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024 <= RSS_CAP, "M3_CONTEXT_RSS_CAP"


def _all_position_counts(root):
    fields = ["game_id", "team", "season", "week", "attempts", "completions", "targets"]
    with zipfile.ZipFile(root / "artifacts/basic-football-facts-v2.1.zip") as archive:
        original = pd.read_csv(io.BytesIO(archive.read("facts.csv.gz")),
                               compression="gzip", usecols=fields, low_memory=False)
    current = pd.read_csv(root / "sources/category-decision-release-01/current_facts_2026.csv.gz",
                          usecols=fields + ["season_type"], low_memory=False)
    extra = current[(current.season == 2026) & current.week.isin([8, 9]) &
                    (current.season_type == "REG")][fields]
    assert not extra.game_id.isin(original.game_id).any()
    rows = pd.concat([original, extra], ignore_index=True)
    counts = {}
    for (game, team), frame in rows.groupby(["game_id", "team"], sort=False):
        values = frame[["attempts", "completions", "targets"]].to_numpy(float)
        complete = bool(np.isfinite(values).all() and (values >= 0).all() and
                        np.equal(values, np.floor(values)).all())
        # Ordinary np.sum preserves unknowns as NaN.  No skipna/sparse-zero rule
        # or participation inference establishes an otherwise missing statistic.
        totals = values.sum(axis=0)
        counts[(game, team)] = dict(zip(["attempts", "completions", "targets"], totals))
        counts[(game, team)]["complete"] = complete
    return counts


def block_vector(context, row):
    own, opponent, _ = context.features(row)
    result = np.r_[own[OWN_INDEX], opponent]
    assert result.shape == (17,)
    return result


def _prefix_mutation_check(context, rows, matrix):
    """Scoped context-layer check; this does not authenticate source vintages."""
    # Fixed deterministic cases cover empty history, qualified history, known
    # zero target support and both roles/late origins without inspecting scores.
    fixed = []
    predicates = [
        lambda i, r: r["season"] == 2022,
        lambda i, r: r["season"] == 2025 and r["position"] == "WR",
        lambda i, r: r["season"] == 2025 and r["position"] == "TE",
        lambda i, r: r["season"] == 2026 and r["week"] == 2 and r["position"] == "WR",
        lambda i, r: r["season"] == 2026 and r["week"] == 8 and r["position"] == "TE",
        lambda i, r: r["season"] == 2026 and r["week"] == 9 and r["position"] == "WR",
        lambda i, r: matrix[i, 0] > 0 and matrix[i, 1] == 0,
        lambda i, r: bool(r.get("query_only")),
    ]
    for predicate in predicates:
        found = next((i for i, r in enumerate(rows) if predicate(i, r)), None)
        if found is not None and found not in fixed:
            fixed.append(found)
    checks = []
    for i in fixed:
        row = rows[i]
        cutoff = row["kickoff"]
        changed = copy.copy(context)
        for name in ["players", "teams", "defenses", "league"]:
            original = getattr(context, name)
            prefix = copy.copy(original)
            prefix.groups = {}
            prefix.times = {}
            for key, values in original.groups.items():
                altered = []
                for record in values:
                    value = dict(record)
                    if value["available"] >= cutoff:
                        for field in ["targets", "completions", "attempts", "air_sum", "air_n",
                                      "wrte_targets", "role_residual"]:
                            if field in value:
                                value[field] = 999999
                        for field in ["depth_n", "depth_c", "depth_residual", "down_n", "down_c",
                                      "down_residual"]:
                            if field in value:
                                value[field] = np.full(5, 999999.)
                    altered.append(value)
                if altered:
                    future = dict(altered[-1])
                    future["kickoff"] = max(cutoff, altered[-1]["kickoff"]) + 30 * 86400
                    future["available"] = future["kickoff"] + 7 * 86400
                    future["game_id"] = "SYNTHETIC_FUTURE_CONTEXT_ONLY_NOT_NFL_EVIDENCE"
                    altered.append(future)
                prefix.groups[key] = altered
                prefix.times[key] = [v["available"] for v in altered]
                assert prefix.times[key] == sorted(prefix.times[key])
            setattr(changed, name, prefix)
        reconstructed = block_vector(changed, row)
        assert np.array_equal(reconstructed, matrix[i], equal_nan=True), "FUTURE_CONTEXT_MUTATION_CHANGED_FEATURES"
        checks.append(dict(index=i, game_id=row["game_id"], player_id=row["player_id"],
                           position=row["position"], source_cutoff_epoch=cutoff, features_unchanged=True,
                           mutation_scope="TARGET_AND_LATER_DERIVED_CONTEXT_VALUES_PLUS_FUTURE_RECORD"))
    return {"scope": "Derived context prefix invariance; not an independent raw-PBP reconstruction "
                     "or proof of original publication time", "cases": checks,
            "future_mutations_changed_features": False}


def prepare_block(root, data, out):
    start = time.process_time()
    root, out = Path(root).resolve(), Path(out).resolve()
    _checkpoint(start)
    sources = []
    frames = []
    for path, expected in zip(SOURCE_FILES, EXPECTED_SOURCE_HASHES):
        source = root / path
        assert sha(source) == expected, "RETAINED_CONTEXT_SOURCE_CHANGED"
        frame = pd.read_csv(source, usecols=REQUIRED_PBP, low_memory=False)
        assert not frame[["game_id", "play_id"]].duplicated().any()
        frames.append(frame)
        sources.append(dict(path=path, SHA256=expected, bytes=source.stat().st_size,
                            games=frame.game_id.nunique(), plays=len(frame), columns=REQUIRED_PBP))
    d, schedule, teams, rebuild = _ordinary(root)
    counts = _all_position_counts(root)
    context = Context(frames, d, schedule, strict=True, all_position_counts=counts)
    del frames
    _checkpoint(start)
    rows = data["rows"]
    matrix = np.asarray([block_vector(context, row) for row in rows], float)
    assert matrix.shape == (len(rows), len(FEATURE_NAMES))
    _checkpoint(start)
    quality_counts = Counter(bool(r["qualified"]) for r in context.quality)
    support = {str(year): dict(rows=sum(r["season"] == year for r in rows),
                              own_supported=sum(r["season"] == year and matrix[i, 4] == 0
                                                for i, r in enumerate(rows)),
                              opponent_supported=sum(r["season"] == year and matrix[i, 14] == 0
                                                     for i, r in enumerate(rows)))
               for year in range(2022, 2027)}
    # All 2022/2023 queries precede available PBP, so substantive values remain
    # explicitly missing. Known zero support counts/flags are genuine metadata.
    early = [i for i, r in enumerate(rows) if r["season"] in [2022, 2023]]
    assert np.isnan(matrix[np.ix_(early, [5, 6, 7, 8, 9, 10, 15, 16])]).all()
    mutation = _prefix_mutation_check(context, rows, matrix)
    _checkpoint(start)
    binding = {
        "id": "C-M3-C01-COMPACT-CONTEXT-v1", "code_SHA256": sha(Path(__file__)),
        "reused_Context_code_SHA256": sha(root / "src/context_features_c01.py"),
        "source_files": sources, "ordinary_source_rebuild": rebuild,
        "ordinary_source_bindings": data["sourcebindings"]["sources"],
        "existing_equivalent_information": "C01/C02 own target-depth and offense-adjusted opponent "
                                           "residual summaries; no claim of new source information",
        "changed_test": "Same compact block supplied to unchanged Leaf and new M3 distributional "
                        "booster; fixed eight-game definition; no lag/window/model search",
        "feature_names": FEATURE_NAMES, "OWN_NAMES_indices": OWN_INDEX,
        "population": "Aligned exactly to M3 retained RB/WR/TE training and WR/TE/native-offer query rows",
        "lookback": 8,
        "cutoff_policy": "Strict earlier kickoff+7day reconstructed availability; current-vintage "
                         "ordinary/PBP source; not authenticated historical publication",
        "own_denominator": "Qualified earlier targeted passes for the player on the historical team; "
                           "mean air yards uses known-air target count, depth shares use all targets "
                           "including an explicit unknown-depth bin. These are not routes/alignment.",
        "opponent_equations": {
            "offense_depth_rate_g_d": "(sum earlier-eight-offense completions_d +20*earlier_league_rate_d) / "
                                       "(sum earlier-eight-offense targets_d+20)",
            "completion_residual_g_d": "completed_g_d-targets_g_d*offense_depth_rate_g_d",
            "opponent_completion_feature": "sum residuals over depth and earlier-eight eligible defense "
                                            "games / (earlier defense target count+40)",
            "offense_WRTE_target_rate_g": "(earlier-eight-offense WRTE targets+40*earlier league WRTE "
                                         "targets per attempt)/(earlier-eight-offense attempts+40)",
            "opponent_WRTE_feature": "sum(WRTE_targets_g-attempts_g*offense_WRTE_target_rate_g) / "
                                     "(earlier-eight-defense attempts+80)",
        },
        "qualification": "Official all-position attempts/completions/targets must be finite integer "
                         "complete and exactly reconcile with PBP valid-attempt counts. Sacks, "
                         "two-point, deleted/no-play excluded. Unallocated target IDs are retained "
                         "in official attempt reconciliation, not assigned to a receiver.",
        "team_games_qualified": quality_counts[True], "team_games_held": quality_counts[False],
        "all_position_count_cells": len(counts),
        "all_position_complete_cells": sum(v["complete"] for v in counts.values()),
        "support_by_season": support,
        "missingness": "2022/2023 lack this PBP panel: support zero/missing flags, substantive values "
                       "NaN. Known-zero-target contexts retain counts but undefined target-quality/"
                       "depth ratios stay missing under the existing C01 representation.",
        "identity_order_SHA256": digest([[r["game_id"], r["player_id"]] for r in rows]),
        "matrix_SHA256": digest(matrix), "future_context_mutation_check": mutation,
        "new_model_fits": 0, "new_source_requests": 0, "new_offer_grades": 0,
        "CPU_seconds": time.process_time() - start,
        "RSS_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
    }
    payloads = {
        "COMPACT_CONTEXT_MATRIX.json.gz": gzip.compress((json.dumps(clean({
            "schema": binding["id"], "feature_names": FEATURE_NAMES, "matrix": matrix,
            "identity_order_SHA256": binding["identity_order_SHA256"]}),
            separators=(",", ":"), allow_nan=False) + "\n").encode(), mtime=0),
        "CONTEXT_BINDINGS.json": (json.dumps(clean(binding), separators=(",", ":"),
                                             allow_nan=False) + "\n").encode(),
    }
    assert sum(map(len, payloads.values())) <= OUTPUT_CAP, "M3_CONTEXT_OUTPUT_CAP"
    out.mkdir(parents=True, exist_ok=True)
    for name, value in payloads.items():
        path = out / name
        # Resource counters vary across reruns, so source/feature execution
        # receipts are append-only: the caller must use a new output directory.
        with path.open("xb") as handle:
            handle.write(value)
    return {"matrix": matrix, "feature_names": FEATURE_NAMES, "sourcebindings": binding,
            "context": context, "saved_evidence_bytes": sum(map(len, payloads.values()))}
