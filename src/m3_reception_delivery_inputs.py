"""Current WR/TE queries and the unchanged weekly M3 Leaf training basis."""
import collections
import csv
import gzip
import io
import json
import zipfile
from datetime import timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path

import numpy as np
import pandas as pd

from data_v2 import History, load as load_facts, vector
from forward_sources_v4 import kickoff_frame, quarantine_stat_orphans, team
from m3_reception_delivery_window import END, EVENT, EXPIRY, GAME, REPORT, ROOT, instant, load, require, sha
from receiving_current_capture_c04 import query_universe
from targeted_data_m3 import digest, feature_names


def numeric_features(row):
    return [float(value) if np.isfinite(value) else None for value in row]


def validated_sources(work, records):
    for name in ("schedule", "roster", "weekly"):
        rec = records[name]
        raw = (work / (name + ".source")).read_bytes()
        require(rec["state"] == "OBTAINED" and len(raw) == rec["bytes"] and sha(raw) == rec["sha256"],
                "Source binding " + name)
    roster_record = records["roster"]
    published = parsedate_to_datetime(roster_record["headers"]["Last-Modified"])
    require(published.tzinfo is not None and published <= instant(roster_record["observed_UTC"]), "Roster publication clock")
    require(published + timedelta(hours=36) >= instant(EXPIRY), "Roster expires before registered cohort")
    with gzip.open(work / "weekly.source", "rb") as f:
        weekly = f.read(33554433)
    require(len(weekly) <= 33554432, "Decoded source cap")
    return pd.read_csv(io.BytesIO(weekly), low_memory=False), published.isoformat()


def calendar_for_game(work, cutoff):
    games = kickoff_frame(pd.read_csv(work / "schedule.source", low_memory=False))
    games = games[(games.season == 2026) & (games.game_type == "REG")]
    require(games.game_id.is_unique, "Duplicate scheduled game")
    game = games.loc[games.game_id == GAME].to_dict("records")
    require(len(game) == 1, "Event missing from calendar")
    g = game[0]
    require(g["away_team"] == "DEN" and g["home_team"] == "PIT" and int(g["espn"]) == int(EVENT) and
            g["week"] == 12 and g["kickoff"] == instant(END).timestamp(), "Event identity or schedule changed")
    weekly = games.loc[games.week == 12, "kickoff"].min()
    require(weekly == instant("2026-11-26T01:00:00Z").timestamp(), "Weekly origin changed")
    def eligible(at):
        before = games[games.kickoff + 7 * 86400 < at]
        require(before[["away_score", "home_score"]].notna().all().all(), "An eligible prior lacks finality")
        return set(before.game_id)
    train, query = eligible(weekly), eligible(g["kickoff"])
    require(eligible(cutoff) == query and not ({GAME} & (train | query)), "Seven-day query basis differs")
    return games, g, weekly, train, query


def current_players(work, game):
    with (work / "roster.source").open() as f:
        roster = list(csv.DictReader(f))
    for r in roster:
        r["season"] = int(r["season"])
    board, potential = query_universe(roster, [game], 2026)
    ours = [r for r in board if r["position"] in ("WR", "TE") and r["team"] in ("DEN", "PIT")]
    candidates = [r for r in potential if r["position"] in ("WR", "TE")]
    ids = {r["gsis_id"]: r for r in roster if r.get("gsis_id")}
    player_ids = {q["player_id"] for q in candidates}
    counts = {k: collections.Counter(ids[pid][k] for pid in player_ids) for k in ("sleeper_id", "espn_id")}
    rejected = {str(r["basic_id"]): r["state"] for r in ours if r["state"] != "DRAFT_CANDIDATE_PENDING_NATIVE_EVENT"}
    result = []
    for q in candidates:
        r = ids[q["player_id"]]
        if any(not str(r.get(k) or "").isdigit() or counts[k][r[k]] != 1 for k in counts):
            rejected[str(q["basic_id"])] = "MISSING_OR_AMBIGUOUS_IDENTITY"
            continue
        result.append(dict(q, sleeper_id=r["sleeper_id"], espn_player_id=r["espn_id"]))
    require(len(ours) == len(result) + len(rejected) and result, "No supported identity or incomplete query accounting")
    return result, dict(roster_rows=len(ours), supported=len(result), unavailable=len(rejected),
                        exclusions=dict(collections.Counter(rejected.values())))


def input_design(work, previous_work, account):
    records = account["source"]
    stats, pub = validated_sources(work, records)
    spec = load(REPORT / "REC_MEAN_CURRENT_DELIVERY_REQUEST_V1.json")
    for b in [*spec["inputs"]["retained_prefix"], *spec["recipe"]["code"].values(), spec["recipe"]["historical_example_binding"]]:
        data = (ROOT / b["path"]).read_bytes()
        require(len(data) == b["bytes"] and sha(data) == b["SHA256"], "Changed retained input or executable")
    cutoff = max(instant(records[k]["observed_UTC"]) for k in ("roster", "schedule", "weekly"))
    games, game, weekly, train_games, query_games = calendar_for_game(work, cutoff.timestamp())
    queries, coverage = current_players(work, game)
    facts = stats[(stats.season == 2026) & (stats.season_type == "REG") & stats.game_id.isin(query_games)]
    facts, orphans = quarantine_stat_orphans(facts)
    require(set(facts.game_id) == query_games and not facts.duplicated(["game_id", "player_id"]).any(), "Missing/duplicate earlier facts")
    facts = facts.copy()
    for col in ("team", "opponent_team"):
        facts[col] = facts[col].map(team)
    with zipfile.ZipFile(ROOT / spec["inputs"]["retained_prefix"][0]["path"]) as z:
        base = pd.read_csv(io.BytesIO(z.read("facts.csv.gz")), compression="gzip", low_memory=False)
        sched0 = pd.read_csv(io.BytesIO(z.read("schedule.csv")))
    old_source = ROOT / "sources/category-decision-release-01"
    prior = load(REPORT / "REC_MEAN_NEXT_WINDOW_AMENDMENT_V1.json")["reusable_inputs"]["reopened_source_bodies"]
    for name in ("current_facts_2026.csv.gz", "schedule.csv"):
        body = (old_source / name).read_bytes()
        check = prior["W8_W9_" + name]
        require(len(body) == check["bytes"] and sha(body) == check["sha256"], "Changed fixed W8/W9 " + name)
    extra = pd.read_csv(old_source / "current_facts_2026.csv.gz", low_memory=False)
    extra = extra[(extra.season == 2026) & extra.week.isin([8, 9]) & (extra.season_type == "REG")]
    sched1 = pd.read_csv(old_source / "schedule.csv")
    sched1 = sched1[(sched1.season == 2026) & sched1.week.isin([8, 9]) & (sched1.game_type == "REG")]
    new = facts[facts.week > 9]
    data = pd.concat([base, extra[base.columns], new[base.columns]], ignore_index=True)
    schedule = pd.concat([sched0, sched1[sched0.columns], games.loc[games.game_id.isin(new.game_id), sched0.columns]], ignore_index=True)
    require(schedule.game_id.is_unique and not data.duplicated(["game_id", "player_id"]).any() and
            data.game_id.isin(schedule.game_id).all(), "Overlapping or unmatched immutable prefix")
    class MemoryInputs:
        def __truediv__(self, name):
            return io.StringIO({"facts.csv.gz": data, "schedule.csv": schedule}[name].to_csv(index=False))
    parsed, _, teams = load_facts(MemoryInputs())
    parsed = parsed[(parsed.season >= 2022) & (parsed.season_type == "REG")]
    added = parsed[(parsed.season == 2026) & (parsed.week > 9) & parsed.game_id.isin(train_games) &
                   parsed.position.isin(["RB", "WR", "TE"])]
    players = {r["player_id"] for r in queries} | set(added.player_id)
    history = History(parsed[parsed.player_id.isin(players)], "player_id")
    team_history = History(teams[teams.season >= 2022], "team")
    order = feature_names("rec")
    require(order == spec["recipe"]["ordered_feature_names"], "Feature order changed")
    query_rows = []
    for q in queries:
        recent = history.before(q["player_id"], q["kickoff"])
        recent_team = team_history.before(q["team"], q["kickoff"], 3)
        require(all(r["available"] < cutoff.timestamp() for r in recent + recent_team), "Future query input")
        query_rows.append(dict(player_id=q["player_id"], sleeper_id=q["sleeper_id"], espn_player_id=q["espn_player_id"],
                               position=q["position"], team=q["team"], opponent_team=q["opponent_team"],
                               features=numeric_features(vector(q, "rec", history, team_history, "E0_OP")),
                               last_prior_game=recent[-1]["game_id"] if recent else None,
                               last_team_game=recent_team[-1]["game_id"] if recent_team else None))

    with gzip.open(ROOT / spec["inputs"]["retained_prefix"][1]["path"]) as f:
        frozen = json.load(f)
    indices = [n for n, r in enumerate(frozen["rows"]) if not r["query_only"] and r["available"] is not None
               and r["available"] < weekly and r["values"]["rec"] is not None]
    prefix = [frozen["rows"][n] for n in indices]
    extension = [r for r in added.to_dict("records") if r["values"]["rec"] is not None]
    rows = prefix + extension
    ids = [(r["game_id"], r["player_id"]) for r in rows]
    require(len(set(ids)) == len(ids) and all(r["available"] < weekly and r["game_id"] != GAME for r in rows),
            "Invalid weekly training membership")
    y = np.asarray([r["values"]["rec"] for r in rows], dtype=np.float64)
    roles = np.asarray([r["position"] for r in rows], dtype="U2")
    features = [frozen["X_by_target"]["rec"][n] for n in indices]
    features.extend(vector(r, "rec", history, team_history, "E0_OP") for r in extension)
    X = np.asarray(features, dtype=np.float64)
    require(X.shape == (len(rows), 32) and np.isfinite(y).all(), "Invalid training design")
    hashes = dict(feature_order_sha256=digest(order), training_member_sha256=digest(ids), role_sequence_sha256=digest(roles.tolist()),
                  retained_recipe_X_y_sha256=sha(np.nan_to_num(X, nan=999999.).tobytes() + y.tobytes()),
                  training_NaN_mask_sha256=sha(np.isnan(X).tobytes()))
    old = load(REPORT / "REC_MEAN_CURRENT_EXECUTION_V1.json")["input_design"]
    matched = all(old[k] == value for k, value in hashes.items())
    if matched:
        path = Path(previous_work) / "design.npz"
        require(sha(path.read_bytes()) == old["private_working_design_sha256"], "Retained W12 design changed")
        with np.load(path, allow_pickle=False) as arrays:
            np.testing.assert_array_equal(X, arrays["X"])
            np.testing.assert_array_equal(y, arrays["y"])
            np.testing.assert_array_equal(roles, arrays["roles"])
            X, y, roles = arrays["X"], arrays["y"], arrays["roles"]
    summary = dict(**hashes, actual_rows=len(rows), eligible_training_2026_games=len(train_games),
                   eligible_query_2026_games=len(query_games), retained_design_reused=matched,
                   latest_training_available_UTC=pd.Timestamp(max(r["available"] for r in rows), unit="s", tz="UTC").isoformat(),
                   information_cutoff_UTC=cutoff.isoformat(), roster_publication_UTC=pub,
                   fit_cutoff_UTC=pd.Timestamp(weekly, unit="s", tz="UTC").isoformat(),
                   quarantined_orphans=len(orphans), coverage=coverage)
    return (X, y, roles), query_rows, summary
