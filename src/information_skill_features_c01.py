"""Prior-only receiver-role/depth matchup information for INFORMATION-SKILL-01.

This module acquires nothing and fits or scores no model.  Its new relationship
is role-specific, offense-adjusted defensive conversion by target depth.  Target
depth is not receiver alignment, and this is not a personnel model.  The frozen
sources retain their current-vintage kickoff-plus-seven-day reconstruction.
"""

from __future__ import annotations

import bisect
import copy
import gzip
import json
import math
import resource
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from context_features_c01 import Context
from data_v2 import DAY
from receiving_defense_c03 import DEPTH, ROLES, ReceivingDefense
from targeted_context_m3 import (
    EXPECTED_SOURCE_HASHES,
    REQUIRED_PBP,
    SOURCE_FILES,
    _all_position_counts,
)
from targeted_data_m3 import _ordinary, clean, digest, sha

VERSION = "C-INFORMATION-SKILL-ROLE-DEPTH-v1"
FEATURE_NAMES = [
    "prior_player_targets8",
    "prior_opponent_role_targets8",
    "prior_opponent_games8",
    "prior_opponent_age_days",
    "substantive_missing",
    "forecast_depth_mix_x_role_depth_offense_adjusted_catch_residual",
]
LOOKBACK = 8
PRIOR_TARGETS = 20.0
GLOBAL_RESIDUAL_TARGETS = 40.0
CPU_CAP_SECONDS = 65.0
RSS_CAP_BYTES = 1288490188
OUTPUT_CAP_BYTES = 8 * 1024 * 1024


def _checkpoint(start):
    if time.process_time() - start > CPU_CAP_SECONDS:
        raise RuntimeError("INFORMATION_FEATURE_CPU_CAP")
    if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024 > RSS_CAP_BYTES:
        raise RuntimeError("INFORMATION_FEATURE_RSS_CAP")


def _finite(value):
    return value is not None and math.isfinite(float(value))


def _time(value):
    if not _finite(value):
        raise ValueError("EXPLICIT_UNKNOWN_OR_NONFINITE_CLOCK")
    return float(value)


def _cutoff(row):
    kickoff = _time(row["kickoff"])
    if "information_cutoff_epoch" in row:
        return min(kickoff, _time(row["information_cutoff_epoch"]))
    return kickoff


def _sum(records, field, shape):
    return sum((record[field] for record in records), np.zeros(shape))


def _recent(records, cutoff):
    """Admission first; game-time ordering second; last eight surviving games."""
    admitted = [record for record in records
                if _time(record["available"]) < cutoff
                and _time(record["kickoff"]) < cutoff]
    return sorted(admitted, key=lambda r: (r["kickoff"], r["game_id"]))[-LOOKBACK:]


def _games(records):
    return [dict(game_id=record["game_id"], kickoff=record["kickoff"],
                 assumed_available=record["available"]) for record in records]


class RoleDepthInformation:
    """A deterministic conditional relationship, with no target-outcome access."""

    def __init__(self, context, defense, *, held_completion_games=()):
        self.context = context
        self.defense = defense
        held = set(held_completion_games)
        self.held_completion_games = tuple(sorted(held))
        self.rows = [row for row in defense.rows
                     if (row["game_id"], row["offense"]) not in held]
        self.rows.sort(key=lambda r: (r["available"], r["kickoff"],
                                     r["game_id"], r["offense"]))
        self.available_times = [row["available"] for row in self.rows]
        if any(not _finite(t) for t in self.available_times):
            raise ValueError("EXPLICIT_UNKNOWN_DEFENSE_CLOCK")
        cumulative = np.zeros((len(self.rows) + 1, 4, 5, 2))
        for i, row in enumerate(self.rows):
            cell = np.asarray(row["cells"], float)[:, :, :2]
            if (not np.isfinite(cell).all() or (cell < 0).any()
                    or not np.equal(cell, np.floor(cell)).all()
                    or (cell[:, :, 1] > cell[:, :, 0]).any()):
                raise ValueError("INVALID_ROLE_DEPTH_COUNT_SUPPORT")
            cumulative[i + 1] = cumulative[i] + cell
        self.cumulative = cumulative
        self.league_cache = {}
        self.by_offense = defaultdict(list)
        for row in self.rows:
            self.by_offense[row["offense"]].append(row)
        admitted_keys = {(row["game_id"], row["offense"]) for row in self.rows}
        self.own_groups = defaultdict(list)
        for row in context.raw_player_games:
            if (row["team_complete"] and row["receptions_match"]
                    and (row["game_id"], row["team"]) in admitted_keys):
                self.own_groups[(row["player_id"], row["team"])].append(row)
        self.adjusted_groups = defaultdict(list)
        self.adjusted_rows = []
        for row in self.rows:
            cutoff = row["kickoff"]
            league, _, _ = self.league(cutoff)
            league_rate, _, _ = self.priors(league)
            earlier = _recent(self.by_offense[row["offense"]], cutoff)
            cells = _sum(earlier, "cells", (4, 5, 6))
            expected = (cells[:, :, 1] + PRIOR_TARGETS * league_rate) / (
                cells[:, :, 0] + PRIOR_TARGETS)
            residual = row["cells"][:, :, 1] - row["cells"][:, :, 0] * expected
            adjusted = dict(
                row, expected_rate=expected, residual=residual,
                offense_prior_games=_games(earlier),
                offense_prior_targets=cells[:, :, 0],
                offense_prior_catches=cells[:, :, 1],
                offense_prior_league_targets=league[:, :, 0],
                offense_prior_league_catches=league[:, :, 1],
            )
            self.adjusted_rows.append(adjusted)
            self.adjusted_groups[row["defense"]].append(adjusted)
        self.cache = {}

    def league(self, cutoff):
        if cutoff in self.league_cache:
            return self.league_cache[cutoff]
        end = bisect.bisect_left(self.available_times, cutoff)
        admitted = self.rows[:end]
        # Every admitted row has an explicit outcome clock after its game.
        if any(row["kickoff"] >= cutoff for row in admitted):
            raise ValueError("ADMITTED_FUTURE_GAME")
        latest = max(admitted, key=lambda r: (r["kickoff"], r["game_id"]),
                     default=None)
        result = self.cumulative[end], end, latest
        self.league_cache[cutoff] = result
        return result

    @staticmethod
    def priors(league):
        counts, catches = league[:, :, 0], league[:, :, 1]
        total = float(counts.sum())
        overall = float(catches.sum() / total) if total else 0.5
        depth_counts = counts.sum(axis=0)
        depth_rate = np.divide(catches.sum(axis=0), depth_counts,
                               out=np.full(5, overall), where=depth_counts > 0)
        rate = np.divide(catches, counts, out=np.broadcast_to(depth_rate, (4, 5)).copy(),
                         where=counts > 0)
        league_mix = depth_counts / total if total else np.full(5, 0.2)
        role_counts = counts.sum(axis=1)
        mix = np.divide(counts, role_counts[:, None],
                        out=np.broadcast_to(league_mix, (4, 5)).copy(),
                        where=role_counts[:, None] > 0)
        return rate, mix, total

    def record(self, row):
        cutoff = _cutoff(row)
        key = (row["game_id"], row["player_id"], row["team"],
               row["opponent_team"], row["position"], cutoff)
        if key in self.cache:
            return self.cache[key]
        role = row["position"]
        ri = ROLES.index(role) if role in ROLES[:3] else 3
        league, league_games, latest_league = self.league(cutoff)
        league_rate, league_mix, league_targets = self.priors(league)
        own = _recent(self.own_groups.get((row["player_id"], row["team"]), []), cutoff)
        opponents = _recent(self.adjusted_groups.get(row["opponent_team"], []), cutoff)
        own_n = _sum(own, "depth_n", (5,))
        own_c = _sum(own, "depth_c", (5,))
        mix = (own_n + PRIOR_TARGETS * league_mix[ri]) / (own_n.sum() + PRIOR_TARGETS)
        opponent_cells = _sum(opponents, "cells", (4, 5, 6))
        residual = _sum(opponents, "residual", (4, 5))
        global_depth = residual.sum(axis=0) / (
            opponent_cells[:, :, 0].sum(axis=0) + GLOBAL_RESIDUAL_TARGETS)
        role_residual = (residual[ri] + PRIOR_TARGETS * global_depth) / (
            opponent_cells[ri, :, 0] + PRIOR_TARGETS)
        missing = not opponents or not league_targets or role not in ROLES[:3]
        substantive = float(mix @ role_residual) if not missing else np.nan
        raw_rate = (own_c + PRIOR_TARGETS * league_rate[ri]) / (own_n + PRIOR_TARGETS)
        adjusted_raw_rate = raw_rate + role_residual
        adjusted_rate = np.clip(adjusted_raw_rate, 0.0, 1.0)
        raw_component = float(mix @ raw_rate) if league_targets else None
        adjusted_component = float(mix @ adjusted_rate) if not missing else None
        latest = latest_league
        consumed = own + opponents + ([latest_league] if latest_league else [])
        if consumed:
            latest = max(consumed, key=lambda r: (r["kickoff"], r["game_id"]))
        vector = np.asarray([
            float(own_n.sum()), float(opponent_cells[ri, :, 0].sum()),
            float(len(opponents)),
            (cutoff - opponents[-1]["kickoff"]) / DAY if opponents else np.nan,
            float(missing), substantive,
        ])
        record = dict(
            game_id=row["game_id"], player_id=row["player_id"], team=row["team"],
            opponent_team=row["opponent_team"], position=role,
            information_cutoff_epoch=cutoff, feature_values=vector,
            source_tier="CURRENT_VINTAGE_SEVEN_DAY_RECONSTRUCTION",
            definition="Predicted target-depth mix times role/depth offense-adjusted defense conversion residual; not alignment/personnel",
            depth_bins=DEPTH, predicted_depth_mix=mix,
            own_targets_by_depth=own_n, own_catches_by_depth=own_c,
            own_games=_games(own), opponent_games=_games(opponents),
            opponent_role_targets_by_depth=opponent_cells[ri, :, 0],
            opponent_role_catches_by_depth=opponent_cells[ri, :, 1],
            opponent_role_raw_residual_by_depth=residual[ri],
            opponent_all_role_depth_residual=global_depth,
            opponent_role_shrunk_residual_by_depth=role_residual,
            league_role_targets_by_depth=league[ri, :, 0],
            league_role_catches_by_depth=league[ri, :, 1],
            league_role_depth_catch_prior=league_rate[ri],
            league_role_depth_mix_prior=league_mix[ri], eligible_league_team_games=league_games,
            component_baseline_catch_probability=raw_component,
            component_matchup_catch_probability=adjusted_component,
            component_baseline_rate_by_depth=raw_rate,
            component_matchup_raw_rate_by_depth=adjusted_raw_rate,
            component_matchup_rate_by_depth=adjusted_rate,
            component_probability_clipped_cells=int(np.count_nonzero(adjusted_raw_rate != adjusted_rate)),
            latest_consumed_game_id=latest["game_id"] if latest else None,
            latest_consumed_game_epoch=latest["kickoff"] if latest else None,
            latest_assumed_available_epoch=max(
                [r["available"] for r in consumed]
                + ([self.available_times[league_games - 1]] if league_games else []),
                default=None),
            own_mix_fallback="ROLE_DEPTH_PRIOR" if not own_n.sum() else "SHRUNK_PLAYER_DEPTH_HISTORY",
            defense_role_fallback="POOLED_DEPTH_RESIDUAL" if not opponent_cells[ri, :, 0].sum() else "SHRUNK_ROLE_DEPTH_RESIDUAL",
            startup_prior="Neutral .5 conversion/uniform depth only at empty league startup; substantive feature missing and component predictions unavailable there",
            substantive_state="UNAVAILABLE_HISTORY" if missing else "SUPPORTED_PRIOR_ONLY" if not own_n.sum() else "SUPPORTED_PLAYER_HISTORY",
        )
        if not np.isclose(mix.sum(), 1.0, rtol=0, atol=1e-12) or (mix < 0).any():
            raise ValueError("INVALID_PREDICTED_DEPTH_MIX")
        if any(r["available"] >= cutoff or r["kickoff"] >= cutoff for r in consumed):
            raise ValueError("INELIGIBLE_CONSUMED_HISTORY")
        self.cache[key] = record
        return record

    def vector(self, row):
        return np.asarray(self.record(row)["feature_values"], float)


def nfl_mutation_check(engine, data, matrix):
    """Retained NFL aggregated-outcome test with the full fixed query context.

    Only prohibited catch outcomes change.  Target counts, identities, roles,
    clocks, ordering, support qualification and the entire source/query universe
    remain fixed.  This is not raw-PBP reconstruction or vintage authentication.
    """
    from laws_v2 import design, medians

    rows = data["rows"]
    fixed = []
    predicates = [
        lambda i, r: r["season"] == 2026 and r["week"] == 2 and r["position"] == "WR",
        lambda i, r: r["season"] == 2026 and r["week"] == 2 and r["position"] == "TE",
        lambda i, r: r["season"] == 2026 and r["week"] == 9 and r["position"] == "WR",
        lambda i, r: r["season"] == 2026 and r["week"] == 9 and r["position"] == "TE",
        lambda i, r: r["season"] == 2026 and matrix[i, 0] == 0 and matrix[i, 4] == 0,
        lambda i, r: r["season"] == 2026 and bool(r.get("query_only")),
    ]
    for predicate in predicates:
        found = next((i for i, r in enumerate(rows) if predicate(i, r)), None)
        if found is not None and found not in fixed:
            fixed.append(found)
    base = np.asarray(data["X_by_target"]["rec"], float)
    full = np.column_stack([base, matrix])
    checks = []
    for i in fixed:
        row = rows[i]
        cutoff = _cutoff(row)
        changed_defense = copy.copy(engine.defense)
        changed_defense.rows = []
        changed_games = 0
        for record in engine.defense.rows:
            changed = dict(record)
            if record["available"] >= cutoff or record["kickoff"] >= cutoff:
                cells = np.asarray(record["cells"], float).copy()
                cells[:, :, 1] = cells[:, :, 0] - cells[:, :, 1]
                changed["cells"] = cells
                changed_games += 1
            changed_defense.rows.append(changed)
        changed_context = copy.copy(engine.context)
        changed_context.raw_player_games = []
        for record in engine.context.raw_player_games:
            changed = dict(record)
            if record["available"] >= cutoff or record["kickoff"] >= cutoff:
                changed["depth_c"] = record["depth_n"] - record["depth_c"]
                changed["completions"] = record["targets"] - record["completions"]
            changed_context.raw_player_games.append(changed)
        changed = RoleDepthInformation(
            changed_context, changed_defense,
            held_completion_games=engine.held_completion_games,
        )
        altered = changed.vector(row)
        if not np.array_equal(altered, matrix[i], equal_nan=True):
            raise AssertionError("NFL_FUTURE_OUTCOMES_CHANGED_INFORMATION_FEATURES")
        prior_indices = [j for j, r in enumerate(rows)
                         if _finite(r.get("available")) and r["available"] < cutoff
                         and r["game_id"] != row["game_id"]
                         and _finite(r.get("values", {}).get("rec"))]
        if not prior_indices:
            raise AssertionError("NO_EARLIER_TRAINING_INPUT_FOR_NFL_FIXTURE")
        imputation = medians(full[prior_indices])
        original_design = design(full[i:i + 1], imputation)
        altered_full = np.column_stack([base[i:i + 1], altered[None, :]])
        altered_design = design(altered_full, imputation)
        if not np.array_equal(original_design, altered_design):
            raise AssertionError("NFL_FUTURE_OUTCOMES_CHANGED_TRANSFORMED_INPUTS")
        checks.append(dict(
            game_id=row["game_id"], player_id=row["player_id"], role=row["position"],
            cutoff=cutoff, full_query_context_rows=len(rows),
            unchanged_source_team_games=len(engine.defense.rows),
            mutated_prohibited_team_games=changed_games,
            earlier_training_rows_for_fixed_imputation=len(prior_indices),
            raw_full_feature_SHA256=digest(full[i]),
            transformed_full_input_SHA256=digest(original_design),
            feature_equal=True, transformed_equal=True,
            held_identities_clocks_target_denominators_order_and_support_fixed=True,
        ))
    return dict(
        scope="Retained NFL aggregated catch-outcome mutation with full source and query universe, fixed denominators and pregame inputs; not raw-PBP rebuild or historical vintage authentication",
        cases=checks, no_synthetic_games=True, no_fits=True,
    )


def prepare_information_block(root, data, out):
    """Build append-only feature evidence aligned exactly to ``data['rows']``."""
    start = time.process_time()
    root, out = Path(root).resolve(), Path(out).resolve()
    frames, source_records, incomplete_completion_games = [], [], set()
    for name, expected in zip(SOURCE_FILES, EXPECTED_SOURCE_HASHES):
        path = root / name
        if sha(path) != expected:
            raise ValueError("RETAINED_INFORMATION_SOURCE_CHANGED")
        frame = pd.read_csv(path, usecols=REQUIRED_PBP, low_memory=False)
        if frame.duplicated(["game_id", "play_id"]).any():
            raise ValueError("DUPLICATE_PLAY_VERSION")
        valid = frame[(frame.pass_attempt == 1) & (frame.sack != 1)
                      & (frame.two_point_attempt != 1) & (frame.play_deleted != 1)
                      & (frame.play_type != "no_play")]
        for (game, team), plays in valid.groupby(["game_id", "posteam"], sort=False):
            if not plays.complete_pass.isin([0, 1]).all():
                incomplete_completion_games.add((game, team))
        frames.append(frame)
        source_records.append(dict(path=name, SHA256=expected, bytes=path.stat().st_size,
                                   games=frame.game_id.nunique(), plays=len(frame)))
    ordinary, schedule, _, rebuild = _ordinary(root)
    counts = _all_position_counts(root)
    context = Context(frames, ordinary, schedule, strict=True, all_position_counts=counts)
    defense = ReceivingDefense(frames, ordinary, schedule, context=context,
                               all_position_counts=counts)
    engine = RoleDepthInformation(context, defense,
                                  held_completion_games=incomplete_completion_games)
    _checkpoint(start)
    records = []
    for i, row in enumerate(data["rows"]):
        records.append(engine.record(row))
        if i % 500 == 0:
            _checkpoint(start)
    matrix = np.asarray([r["feature_values"] for r in records], float)
    if matrix.shape != (len(data["rows"]), len(FEATURE_NAMES)):
        raise ValueError("INFORMATION_MATRIX_ALIGNMENT")
    quality_counts = Counter(bool(r["qualified"]) for r in context.quality)
    binding = dict(
        id=VERSION, code_SHA256=sha(Path(__file__)),
        context_code_SHA256=sha(root / "src/context_features_c01.py"),
        defense_code_SHA256=sha(root / "src/receiving_defense_c03.py"),
        source_files=source_records, ordinary_source_rebuild=rebuild,
        ordinary_source_bindings=json.loads((root / "reports/targeted-accuracy-w1w9-01/M3/inputs/SOURCE_BINDINGS.json").read_text())["sources"],
        source_clock_contract=dict(
            original_publication_time=None, authenticated_original_observation_time=None,
            source_revision_vintage="Frozen retained current-vintage files with exact SHA256; original per-play revision clocks unavailable",
            known_observation_reference="reports/player-context-matchup-01/SOURCE_METADATA_INDEX.json and retained SOURCE_METADATA.zip; parent source qualification binds actual observed receipt clocks without backdating",
            feature_availability="Reconstructed kickoff+7d only; neither a publication timestamp nor proof of earlier file availability",
        ),
        feature_names=FEATURE_NAMES, lookback=LOOKBACK, prior_targets=PRIOR_TARGETS,
        global_residual_targets=GLOBAL_RESIDUAL_TARGETS,
        cutoff_policy="Explicit finite availability strictly less than cutoff, then game-time ordering; current-vintage kickoff+7d source assumption retained; no authenticated historical publication claim",
        target_population="Existing immutable M3 role-appropriate training/conditional reconstructed query universe; qualified offer queries remain separate",
        qualified_team_games=quality_counts[True], held_by_original_totals=quality_counts[False],
        held_by_nonbinary_or_missing_completion_flags=[list(k) for k in sorted(incomplete_completion_games)],
        admitted_team_games=len(engine.rows), prior_adjusted_games=len(engine.adjusted_rows),
        identity_order_SHA256=digest([[r["game_id"], r["player_id"]] for r in data["rows"]]),
        matrix_SHA256=digest(matrix), target_outcomes_used_as_query_predictors=False,
        source_terms="Ordinary factual PBP attribution/retention from existing C01/C03 source bindings; no new FTN or protected offer export",
        output_semantics="Five support indicators plus one role-depth matchup scalar; component rates are diagnostics, not a new count law or per-pick confidence",
        new_fits=0, new_source_requests=0, new_offer_grades=0,
    )
    mutation = nfl_mutation_check(engine, data, matrix)
    _checkpoint(start)
    labels_by_key = {}
    admitted_keys = {(r["game_id"], r["offense"]) for r in engine.rows}
    for record in context.raw_player_games:
        if (record["team_complete"] and record["receptions_match"]
                and (record["game_id"], record["team"]) in admitted_keys):
            key = record["game_id"], record["player_id"]
            if key in labels_by_key:
                raise ValueError("DUPLICATE_COMPONENT_LABEL_IDENTITY")
            labels_by_key[key] = dict(
                game_id=record["game_id"], player_id=record["player_id"],
                team=record["team"], role=record["role"],
                observed_target_depth_n=record["depth_n"],
                observed_catch_depth_c=record["depth_c"],
                observed_targets=record["targets"], observed_catches=record["completions"],
                label_assumed_available=record["available"],
                label_only_never_predictor=True,
            )
    adjusted = [{k: v for k, v in row.items() if k != "cells"}
                for row in engine.adjusted_rows]
    payloads = {
        "FEATURE_MATRIX.json.gz": dict(schema=VERSION, feature_names=FEATURE_NAMES,
                                       matrix=matrix, identity_order_SHA256=binding["identity_order_SHA256"]),
        "FEATURE_RECORDS.json.gz": dict(schema=VERSION, records=records),
        "OFFENSE_ADJUSTMENT_RECORDS.json.gz": dict(schema=VERSION, records=adjusted),
        "COMPONENT_LABELS.json.gz": dict(
            schema=VERSION, label_contract="Postgame component diagnostics only; separate from all model features",
            records=list(labels_by_key.values())),
    }
    encoded = {name: gzip.compress((json.dumps(clean(value), separators=(",", ":"),
                                                allow_nan=False) + "\n").encode(), mtime=0)
               for name, value in payloads.items()}
    _checkpoint(start)
    binding["CPU_seconds"] = time.process_time() - start
    binding["RSS_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    encoded["SOURCE_BINDINGS.json"] = (json.dumps(clean(binding), indent=2,
                                                  allow_nan=False) + "\n").encode()
    encoded["NFL_MUTATION_CHECK.json"] = (json.dumps(clean(mutation), indent=2,
                                                     allow_nan=False) + "\n").encode()
    if sum(map(len, encoded.values())) > OUTPUT_CAP_BYTES:
        raise RuntimeError("INFORMATION_FEATURE_OUTPUT_CAP")
    out.mkdir(parents=True, exist_ok=True)
    for name, value in encoded.items():
        with (out / name).open("xb") as handle:
            handle.write(value)
    return dict(matrix=matrix, feature_names=FEATURE_NAMES, records=records,
                sourcebindings=binding, engine=engine,
                saved_evidence_bytes=sum(map(len, encoded.values())))
