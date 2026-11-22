"""Lossless SIM forecast/state retention and sufficient D-P moment records.

No sampling, inference, source reads or writes happen on import.  Only the
admitted caller may invoke these functions.  Conditional 10,000-by-actor float
matrices are reduced with the registered ddof=0 moment operation, not retained.
The resulting float64 vectors exactly suffice for the registered D-P calls.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import io
import json
import math
from pathlib import Path
import zipfile

import numpy as np

from shared_game_sim01_kernel import (
    CHILD_FIELDS, COUNT_FIELDS, TRAJECTORIES, GameSamples, GainTupleLaw,
    TeamParameters, _team_check,
)

FORMAT = "SHARED-GAME-SIM01-REPLAY-v1"


@dataclass
class RetainedGame:
    arrays: dict[str, np.ndarray]
    metadata: dict
    dp_moments: dict[str, dict[str, np.ndarray]]
    teams: tuple[TeamParameters, TeamParameters]
    frailty_shape: float | None
    fit_record: dict
    receipt: dict


def _json_bytes(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       allow_nan=False) + "\n").encode("utf-8")


def _numeric(value):
    a = np.asarray(value)
    if a.dtype.kind not in "biuf" or not np.isfinite(a).all():
        raise ValueError("NONFINITE_OR_NONPRIMITIVE_REPLAY_ARRAY")
    return a


def _npy(value):
    a = _numeric(value)
    b = io.BytesIO()
    np.lib.format.write_array(b, a, allow_pickle=False)
    return b.getvalue(), a


def _law_dict(law):
    if law is None:
        return None
    law = law.checked()
    return dict(gains=law.gains.tolist(), touchdowns=law.touchdowns.tolist(),
                weights=law.weights.tolist())


def _team_dict(t):
    _team_check(t)
    out = dict(team_id=t.team_id, actor_ids=list(t.actor_ids),
               other_index=t.other_index, qb_indices=list(t.qb_indices),
               target_indices=list(t.target_indices), rusher_indices=list(t.rusher_indices),
               opportunity_mean=t.opportunity_mean)
    for key in ("event_alpha", "qb_alpha", "target_alpha", "conversion_alpha", "rusher_alpha"):
        out[key] = _numeric(getattr(t, key)).tolist()
    out["catch_laws"] = (None if t.catch_laws is None else
                         [[_law_dict(law) for law in row] for row in t.catch_laws])
    for key in ("designed_laws", "scramble_laws", "kneel_laws"):
        laws = getattr(t, key)
        out[key] = None if laws is None else [_law_dict(law) for law in laws]
    return out


def _law_from(d):
    if d is None:
        return None
    if set(d) != {"gains", "touchdowns", "weights"}:
        raise ValueError("UNKNOWN_GAIN_STATE_FIELDS")
    return GainTupleLaw(np.asarray(d["gains"], dtype=np.int64),
                        np.asarray(d["touchdowns"], dtype=np.int64),
                        np.asarray(d["weights"], dtype=float)).checked()


def _team_from(d):
    d = dict(d)
    d["catch_laws"] = (None if d["catch_laws"] is None else
                       tuple(tuple(_law_from(x) for x in row) for row in d["catch_laws"]))
    for key in ("designed_laws", "scramble_laws", "kneel_laws"):
        d[key] = None if d[key] is None else tuple(_law_from(x) for x in d[key])
    t = TeamParameters(**d)
    _team_check(t)
    return t


def _column_count(metadata, key):
    prefix, field = key.split("/", 1)
    t = metadata["teams"][prefix + "/"]
    k = len(t["actor_ids"])
    if field in COUNT_FIELDS:
        return k
    if field in CHILD_FIELDS:
        return len(t["child_columns"][field])
    if field == "rush_rec_yd":
        return len(t["rush_rec_yd_columns"])
    raise ValueError("UNREGISTERED_DP_FIELD:" + key)


def _metadata_check(metadata):
    if metadata.get("trajectories") != TRAJECTORIES:
        raise ValueError("REPLAY_TRAJECTORY_COUNT")
    if set(metadata.get("teams", {})) != {"team0/", "team1/"}:
        raise ValueError("REPLAY_TEAM_MANIFEST")
    for t in metadata["teams"].values():
        k = len(t["actor_ids"])
        if len(set(t["actor_ids"])) != k or not 0 <= t["other_index"] < k:
            raise ValueError("REPLAY_ACTOR_MANIFEST")
        for field in CHILD_FIELDS:
            good = t["child_columns"][field]
            bad = t["unavailable_child_columns"][field]
            if len(good) != len(set(good)) or len(bad) != len(set(bad)):
                raise ValueError("DUPLICATE_CHILD_COLUMN")
            if set(good) & set(bad) or set(good) | set(bad) != set(range(k)):
                raise ValueError("MISSINGNESS_COLUMN_PARTITION")
        for cols in (t["rush_rec_yd_columns"], t["anytime_td_columns"]):
            if len(set(cols)) != len(cols) or not set(cols).issubset(range(k)):
                raise ValueError("DERIVED_COLUMN_MANIFEST")


def sufficient_dp_moments(result: GameSamples):
    """Exact sufficient aggregates for marginal_moments and registered D-P laws."""
    _metadata_check(result.metadata)
    if set(result.conditional_means) != set(result.conditional_variances):
        raise ValueError("DP_CONDITIONAL_KEYS_MISMATCH")
    expected_keys = {f"team{ti}/{field}" for ti in range(2)
                     for field in (*COUNT_FIELDS, *CHILD_FIELDS, "rush_rec_yd")}
    if set(result.conditional_means) != expected_keys:
        raise ValueError("DP_REQUIRED_MOMENTS_MISSING_OR_UNREGISTERED")
    out = {}
    for key, raw_m in result.conditional_means.items():
        m = _numeric(raw_m).astype(float, copy=False)
        v = _numeric(result.conditional_variances[key]).astype(float, copy=False)
        expected = (TRAJECTORIES, _column_count(result.metadata, key))
        if m.shape != expected or v.shape != expected or np.any(v < 0):
            raise ValueError("DP_CONDITIONAL_SHAPE_SUPPORT:" + key)
        mean = np.mean(m, axis=0)
        within = np.mean(v, axis=0)
        between = np.var(m, axis=0, ddof=0)
        out[key] = dict(mean=mean, conditional_variance_mean=within,
                        conditional_mean_variance=between,
                        total_variance=within + between)
    return out


def write_replay_bundle(path: Path, result: GameSamples,
                        teams: tuple[TeamParameters, TeamParameters],
                        frailty_shape: float | None, fit_record: dict):
    """Create one immutable primitive bundle; caller accounts bytes and costs.

    All S-P arrays, aggregate D-P moments, full fitted primitive state and
    original game/actor/input/seed metadata are included.  Never overwrites.
    """
    path = Path(path)
    if path.exists():
        raise FileExistsError("IMMUTABLE_REPLAY_PATH_ALREADY_EXISTS")
    if len(teams) != 2 or not isinstance(fit_record, dict):
        raise ValueError("REPLAY_FITTED_STATE_SHAPE")
    if frailty_shape is not None and (not math.isfinite(frailty_shape) or frailty_shape <= 0):
        raise ValueError("REPLAY_FRAILTY_SUPPORT")
    _metadata_check(result.metadata)
    state = dict(teams=[_team_dict(t) for t in teams], frailty_shape=frailty_shape,
                 fit_record=fit_record)
    state_bytes = _json_bytes(state)
    dp = sufficient_dp_moments(result)
    members = {}
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        def put(name, body, **description):
            if name in members or name.startswith("/") or ".." in name.split("/"):
                raise ValueError("UNSAFE_OR_DUPLICATE_REPLAY_MEMBER")
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, body)
            members[name] = dict(bytes=len(body), SHA256=hashlib.sha256(body).hexdigest(),
                                 **description)
        for key, raw in sorted(result.arrays.items()):
            body, a = _npy(raw)
            if a.shape[0] != TRAJECTORIES:
                raise ValueError("SAMPLE_ROWS_NOT_REGISTERED")
            put("samples/" + key + ".npy", body, shape=list(a.shape), dtype=a.dtype.str)
        for key, fields in sorted(dp.items()):
            for statistic, raw in sorted(fields.items()):
                body, a = _npy(raw)
                put("dp/" + key + "/" + statistic + ".npy", body,
                    shape=list(a.shape), dtype=a.dtype.str)
        put("fitted_state.json", state_bytes)
        put("game_metadata.json", _json_bytes(result.metadata))
        manifest = dict(format=FORMAT, members=members, trajectories=TRAJECTORIES,
                        dp_rule="ddof=0; count mixing=conditional_mean_variance; signed variance=total_variance",
                        conditional_float_matrices_retained=False,
                        state_allows_explicit_replay=True)
        info = zipfile.ZipInfo("manifest.json", date_time=(1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        z.writestr(info, _json_bytes(manifest))
    return dict(path=str(path), bytes=path.stat().st_size,
                SHA256=hashlib.sha256(path.read_bytes()).hexdigest(),
                uncompressed_member_bytes=sum(x["bytes"] for x in members.values()),
                members=len(members) + 1)


def reopen_replay_bundle(path: Path, expected_sha256: str | None = None,
                         max_uncompressed_bytes: int = 805306368) -> RetainedGame:
    """Independently reopen actual records; no simulation or unsafe unpickling."""
    path = Path(path)
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if expected_sha256 is not None and actual != expected_sha256:
        raise ValueError("REPLAY_BODY_HASH_MISMATCH")
    arrays, dp = {}, {}
    with zipfile.ZipFile(path) as z:
        infos = z.infolist()
        names = [i.filename for i in infos]
        if (len(names) != len(set(names)) or len(names) > 8192 or
                any(n.startswith("/") or ".." in n.split("/") for n in names) or
                any(i.flag_bits & 1 or (i.external_attr >> 16) & 0o170000 == 0o120000 for i in infos) or
                sum(i.file_size for i in infos) > max_uncompressed_bytes):
            raise ValueError("UNSAFE_OR_OVERSIZE_REPLAY_ZIP")
        manifest = json.loads(z.read("manifest.json"))
        if manifest.get("format") != FORMAT or manifest.get("trajectories") != TRAJECTORIES:
            raise ValueError("UNSUPPORTED_REPLAY_FORMAT")
        if set(names) != set(manifest["members"]) | {"manifest.json"}:
            raise ValueError("REPLAY_MEMBER_MANIFEST_MISMATCH")
        bodies = {}
        for name, desc in manifest["members"].items():
            body = z.read(name)
            if len(body) != desc["bytes"] or hashlib.sha256(body).hexdigest() != desc["SHA256"]:
                raise ValueError("REPLAY_MEMBER_HASH_MISMATCH:" + name)
            if name.endswith(".npy"):
                a = np.lib.format.read_array(io.BytesIO(body), allow_pickle=False)
                _numeric(a)
                if list(a.shape) != desc["shape"] or a.dtype.str != desc["dtype"]:
                    raise ValueError("REPLAY_ARRAY_SCHEMA_MISMATCH:" + name)
                if name.startswith("samples/"):
                    if not a.ndim or a.shape[0] != TRAJECTORIES:
                        raise ValueError("REPLAY_SAMPLE_ROW_COUNT")
                    arrays[name[len("samples/"):-4]] = a
                elif name.startswith("dp/"):
                    key, statistic = name[len("dp/"):-4].rsplit("/", 1)
                    dp.setdefault(key, {})[statistic] = a
                else:
                    raise ValueError("UNEXPECTED_NUMERIC_REPLAY_MEMBER")
            elif name in {"fitted_state.json", "game_metadata.json"}:
                bodies[name] = json.loads(body)
            else:
                raise ValueError("UNEXPECTED_REPLAY_MEMBER:" + name)
    metadata = bodies["game_metadata.json"]
    _metadata_check(metadata)
    expected_keys = {f"team{ti}/{field}" for ti in range(2)
                     for field in (*COUNT_FIELDS, *CHILD_FIELDS, "rush_rec_yd")}
    if set(dp) != expected_keys:
        raise ValueError("REOPENED_DP_REQUIRED_MOMENTS_MISSING")
    state = bodies["fitted_state.json"]
    if len(state["teams"]) != 2:
        raise ValueError("REPLAY_FITTED_TEAM_COUNT")
    teams = tuple(_team_from(t) for t in state["teams"])
    for ti, team in enumerate(teams):
        if (team.team_id != metadata["teams"][f"team{ti}/"]["team_id"] or
                team.actor_ids != tuple(metadata["teams"][f"team{ti}/"]["actor_ids"])):
            raise ValueError("REPLAY_FITTED_SAMPLE_IDENTITY_MISMATCH")
    for key, fields in dp.items():
        if set(fields) != {"mean", "conditional_variance_mean", "conditional_mean_variance", "total_variance"}:
            raise ValueError("DP_SUFFICIENT_FIELDS_MISMATCH")
        expected = (_column_count(metadata, key),)
        if key not in arrays or arrays[key].shape != (TRAJECTORIES, expected[0]):
            raise ValueError("DP_SAMPLE_COLUMN_ALIGNMENT")
        if any(a.shape != expected for a in fields.values()):
            raise ValueError("DP_AGGREGATE_COLUMN_SHAPE")
        if any(np.any(fields[n] < 0) for n in fields if n != "mean"):
            raise ValueError("DP_NEGATIVE_VARIANCE")
        if not np.array_equal(fields["total_variance"], fields["conditional_variance_mean"] + fields["conditional_mean_variance"]):
            raise ValueError("DP_TOTAL_VARIANCE_IDENTITY")
    receipt = dict(path=str(path), bytes=path.stat().st_size, SHA256=actual,
                   members=len(manifest["members"]) + 1,
                   reopened="ALL_MEMBER_HASHES_SCHEMA_STATE_AND_DP_MOMENTS_CHECKED")
    return RetainedGame(arrays, metadata, dp, teams, state["frailty_shape"],
                        state["fit_record"], receipt)
