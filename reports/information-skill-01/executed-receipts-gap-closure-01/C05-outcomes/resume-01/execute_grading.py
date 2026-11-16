"""Append-only outcome qualification for the original frozen C05 NE--DET packet.

No model fitting, new forecast issuance, offered line, selection, or source
polling is performed.  Raw responses remain memory-only; only the existing
permitted factual projections and actual observation clocks are retained.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import gzip
import hashlib
import io
import json
import math
import resource
import signal
import sys
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from email.utils import parsedate_to_datetime

ENTRY_CPU = time.process_time()
ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd

from contracts_v2 import SIGNED, integer, target
from data_v2 import PHYSICAL
from forward_budget_v4 import complete_C_roots, tree_bytes
from forward_sources_v4 import kickoff_frame, scoreboard_projection, stamp, team, write
from prospective_v4 import grade_run, validate_receipt, validate_run

REPORT = Path(__file__).resolve().parent
BASE_REPORT = REPORT.parent
VERSION = "C-NATIVE-GRADE-20261116-NEDET-01"
RUN_ID = "C-C05-NEDET-FIRST-01"
GAME_ID = "2026_10_NE_DET"
EVENT_ID = "401873053"
KICKOFF = "2026-11-15T14:30:00+00:00"
OUT = ROOT / "prospective/outcomes" / VERSION
GRADE = ROOT / "prospective/grades" / (VERSION + "-" + RUN_ID + ".json")
SOURCE_URLS = [
    ("native_status", "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates=20261115&limit=100"),
    ("schedule", "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"),
    ("stats", "https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_2026.csv.gz"),
]
MAX_BODY = 5 * 1024 * 1024
CPU_CAP = 20
RSS_CAP = 1288490188
MAX_PUBLIC = 2 * 1024 * 1024
GLOBAL_CAP = 2684354560


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_bytes())


def boundary(condition, message):
    if not condition:
        raise RuntimeError(message)


def eligible_version(current, previous):
    """Only known changed ETag or strictly later Last-Modified qualifies."""
    ce, pe = current.get("HTTP_ETag"), previous.get("HTTP_ETag")
    if ce and pe and ce != pe:
        return True, "CHANGED_KNOWN_ETAG"
    cm, pm = current.get("HTTP_Last_Modified"), previous.get("HTTP_Last_Modified")
    if cm and pm:
        try:
            if parsedate_to_datetime(cm) > parsedate_to_datetime(pm):
                return True, "LATER_KNOWN_LAST_MODIFIED"
        except (TypeError, ValueError, OverflowError):
            pass
    return False, "SAME_OR_UNKNOWN_SOURCE_VERSION"


def main():
    started = time.monotonic()
    boundary(not OUT.exists() and not GRADE.exists(), "GRADE_VERSION_ALREADY_EXISTS")
    boundary(not (REPORT / "SOURCE_STATUS.json").exists(), "SOURCE_ATTEMPT_ALREADY_RECORDED")
    registration = read(BASE_REPORT / "REGISTRATION.json")
    boundary(registration["event_id"] == EVENT_ID and registration["game_id"] == GAME_ID,
             "REGISTRATION_EVENT_MISMATCH")
    prior_stop = read(BASE_REPORT / "SOURCE_STATUS.json")
    boundary(prior_stop["stage"] == "NATIVE_FINAL_STATUS" and
             prior_stop["reason"].startswith("FileExistsError:"), "UNEXPECTED_PRIOR_STOP")
    boundary(len(prior_stop["source_manifest"]) == 1 and
             prior_stop["source_manifest"][0]["id"] == "native_status" and
             prior_stop["source_manifest"][0]["HTTP_status"] == 200 and
             prior_stop["source_manifest"][0]["bytes_received"] == 208679 and
             prior_stop["observed_native_event"] is None and
             prior_stop["outcome_packet"] is None and prior_stop["grade"] is None,
             "PRIOR_CONSUMPTION_OR_STOP_CONFLICT")
    manifest = [dict(prior_stop["source_manifest"][0],
                     use="CONSUMED_NOT_USED;BODY_UNPROJECTED_BEFORE_LOGGING_FAILURE")]
    reused_native_binding = None
    original_hashes = {}
    status = "STOPPED"
    stage = "ORIGINAL_PACKET_VALIDATION"
    reason = None
    rows = []
    state = None
    metrics = []
    qualified_outcome_packet = None
    grade_binding = None
    version_gate = None
    stats_presence = None

    def checkpoint():
        boundary(time.process_time() - ENTRY_CPU < CPU_CAP, "C05_GRADING_CPU_CAP")
        boundary(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024 <= RSS_CAP,
                 "C05_GRADING_RSS_CAP")
        old_roots = read(ROOT / "reports/information-skill-01/FIT_LEDGER.json")["whole_C_roots"]
        roots = complete_C_roots([ROOT] + [Path(p) for p in old_roots]
                                 + list(Path("/tmp").glob("gap-c05*")))
        boundary(sum(tree_bytes(p) for p in roots) <= GLOBAL_CAP, "WHOLE_C_CAP")
        boundary(tree_bytes(BASE_REPORT) + tree_bytes(OUT) +
                 (GRADE.stat().st_size if GRADE.exists() else 0) <= MAX_PUBLIC,
                 "C05_GRADING_PUBLIC_CAP")

    def fetch(key, url):
        boundary(len(manifest) < len(SOURCE_URLS), "SOURCE_REQUEST_CAP")
        boundary((key, url) == SOURCE_URLS[len(manifest)], "SOURCE_ROUTE_OR_ORDER_CHANGED")
        remaining = MAX_BODY - sum(item["bytes_received"] for item in manifest)
        boundary(remaining > 0, "SOURCE_BODY_CAP")
        item = dict(id=key, url=url, started_UTC=stamp(), observed_UTC=None,
                    HTTP_status=None, bytes_received=0, raw_SHA256=None,
                    raw_retention="Memory-only; minimum permitted factual projections only")
        manifest.append(item)  # Failed attempts count; there is no retry loop.
        write(REPORT / ("SOURCE_ATTEMPT_%02d_STARTED.json" % len(manifest)), dict(
            recorded_UTC=stamp(), attempt=dict(item),
            scope="Immutable started checkpoint; prior consumed request is carried forward."))
        try:
            request = Request(url, headers={
                "User-Agent": "Session-C-existing-frozen-outcome-grading",
                "Accept-Encoding": "identity", "Cache-Control": "no-cache"})
            with urlopen(request, timeout=35) as response:
                item.update(HTTP_status=response.status,
                            HTTP_Date=response.headers.get("Date"),
                            HTTP_Age=response.headers.get("Age"),
                            HTTP_Last_Modified=response.headers.get("Last-Modified"),
                            HTTP_ETag=response.headers.get("ETag"))
                declared = response.headers.get("Content-Length")
                if declared is not None:
                    boundary(int(declared) < remaining, "DECLARED_SOURCE_BODY_CAP")
                body = response.read(remaining)
                item.update(observed_UTC=stamp(), bytes_received=len(body),
                            raw_SHA256=hashlib.sha256(body).hexdigest())
                boundary(len(body) < remaining, "SOURCE_BODY_BOUNDARY_NO_COMPLETENESS_PROOF")
                boundary(response.status == 200, "SOURCE_HTTP_NOT_200")
        except HTTPError as error:
            item.update(observed_UTC=stamp(), HTTP_status=error.code,
                        HTTP_Date=error.headers.get("Date"),
                        HTTP_Age=error.headers.get("Age"),
                        HTTP_Last_Modified=error.headers.get("Last-Modified"),
                        error="HTTPError: " + str(error.code),
                        failed_body_bytes="Not read; no retry or access workaround")
            raise RuntimeError("SOURCE_HTTP_" + str(error.code)) from None
        except Exception as error:
            item.setdefault("error", type(error).__name__ + ": " + str(error))
            item["observed_UTC"] = item["observed_UTC"] or stamp()
            raise
        finally:
            write(REPORT / ("SOURCE_ATTEMPT_%02d_COMPLETED.json" % len(manifest)), dict(
                recorded_UTC=stamp(), attempt=dict(item),
                scope="Immutable completed checkpoint, including failed attempt; no retry."))
        checkpoint()
        return body, item

    previous_handler = signal.signal(
        signal.SIGPROF, lambda *_: (_ for _ in ()).throw(RuntimeError("C05_GRADING_CPU_TIMER")))
    signal.setitimer(signal.ITIMER_PROF, max(.01, CPU_CAP - (time.process_time() - ENTRY_CPU)))
    try:
        folder = ROOT / "prospective/runs" / RUN_ID
        receipt = ROOT / "prospective/receipts" / (RUN_ID + "-server.json")
        for path in [folder / "RUN.json", folder / "FORECASTS.json.xz", receipt]:
            original_hashes[str(path.relative_to(ROOT))] = sha(path)
        model_metadata, rows = validate_run(folder)
        validate_receipt(folder, read(receipt), model_metadata, rows)
        boundary(len(rows) == 69 and len({r["player_id"] for r in rows}) == 23,
                 "ORIGINAL_FORECAST_POPULATION_CHANGED")
        boundary(len({r["model_id"] for r in rows}) == 3, "MODEL_VIEW_COUNT_CHANGED")
        boundary(all(r["espn_event_id"] == EVENT_ID and r["game_id"] == GAME_ID and
                     r["category"] == "rec" and pd.Timestamp(r["kickoff_UTC"]) == pd.Timestamp(KICKOFF)
                     and r["line"] is None and r["selected_side"] is None for r in rows),
                 "ORIGINAL_EVENT_OR_OFFER_CONTRACT_CHANGED")
        checkpoint()

        stage = "REUSE_QUALIFIED_NATIVE_AND_VERSION_GATE"
        old_attempt = ROOT / registration["old_attempt"]
        boundary(sha(old_attempt) == "23d3dddf9da5651edcd3f60cbab9d38bcbbcd9bea7c67a4aeb9449ce89762b98",
                 "REUSED_NATIVE_BINDING_CHANGED")
        old_qualified = read(old_attempt)
        previous_stats = next(r for r in old_qualified["source_manifest"] if r["id"] == "stats")
        boundary(previous_stats["url"] == SOURCE_URLS[2][1], "VERSION_SOURCE_ROUTE_CHANGED")
        boundary(sha(BASE_REPORT / "VERSION_GATE.json") ==
                 "0f30456c910a3ee577969aee37bfb2f783818d72e7e5796f83a28e4636dd554c",
                 "PRIOR_ELIGIBLE_HEAD_BINDING_CHANGED")
        version_gate = read(BASE_REPORT / "VERSION_GATE.json")
        boundary(version_gate["eligible"] and version_gate["HTTP_status"] == 200 and
                 version_gate["url"] == SOURCE_URLS[2][1], "PRIOR_HEAD_NOT_ELIGIBLE")
        eligible, why = eligible_version(version_gate, previous_stats)
        boundary(eligible, "NO_ELIGIBLE_NEW_SOURCE_VERSION")
        state = dict(old_qualified["observed_native_event"])
        native_source = dict(next(x for x in old_qualified["source_manifest"] if x["id"] == "native_status"))
        reused_native_binding = dict(
            path=str(old_attempt.relative_to(ROOT)), SHA256=sha(old_attempt),
            projection_field="observed_native_event", source_field="source_manifest[native_status]",
            original_observed_UTC=native_source["observed_UTC"],
            retained_commit="d4b42faa897b2ab75067f2a4e078dc3e521a404e",
            note="Reused qualified FINAL projection at original observation clock; newer consumed native GET body was unprojected and is not used.")
        boundary(state["espn_event_id"] == EVENT_ID and
                 state["competition_id"] == EVENT_ID and state["competition_state_agreement"] and
                 state["season"] == 2026 and state["season_type"] == 2 and state["week"] == 10,
                 "REUSED_NATIVE_SEASON_WEEK_EVENT_CONFLICT")
        boundary(state["home_team"] == "DET" and state["away_team"] == "NE" and
                 pd.Timestamp(state["kickoff_UTC"]) == pd.Timestamp(KICKOFF),
                 "REUSED_NATIVE_TEAM_OR_KICKOFF_CONFLICT")
        boundary(state["state"] == "post" and state["completed"] and
                 state["status_name"] == "STATUS_FINAL" and native_source["HTTP_status"] == 200 and
                 state["observed_UTC"] == native_source["observed_UTC"],
                 "REUSED_NATIVE_FINAL_NOT_QUALIFIED")
        native_scores = {"home": integer(state["home_score"]), "away": integer(state["away_score"])}
        boundary(native_scores == {"home":35,"away":10}, "REUSED_NATIVE_SCORE_CONFLICT")
        write(REPORT / "REUSED_QUALIFIED_NATIVE.json", dict(
            event=state, source=native_source, binding=reused_native_binding,
            source_clock_rewritten=False, new_HEAD=0, new_native_GET=0))
        checkpoint()

        stage = "SCHEDULE_FINAL_RECONCILIATION"
        body, schedule_source = fetch(*SOURCE_URLS[1])
        schedule = kickoff_frame(pd.read_csv(io.BytesIO(body), low_memory=False))
        schedule = schedule[schedule.game_id == GAME_ID].copy()
        boundary(len(schedule) == 1, "EXACT_SCHEDULE_GAME_NOT_AVAILABLE")
        game = schedule.iloc[0]
        boundary(int(game.season) == 2026 and int(game.week) == 10 and game.game_type == "REG",
                 "SCHEDULE_SEASON_WEEK_CONFLICT")
        boundary(abs(game.kickoff - state["kickoff"]) < 1 and
                 team(game.home_team) == "DET" and team(game.away_team) == "NE",
                 "SCHEDULE_NATIVE_IDENTITY_OR_TIME_CONFLICT")
        boundary(integer(game.home_score) == native_scores["home"] and
                 integer(game.away_score) == native_scores["away"], "SCHEDULE_NATIVE_SCORE_CONFLICT")
        del body

        stage = "QUALIFIED_ORDINARY_PLAYER_FACTS"
        body, player_source = fetch(*SOURCE_URLS[2])
        body_eligible, body_reason = eligible_version(player_source, previous_stats)
        player_source.update(eligible_new_version_vs_prior=body_eligible, eligibility_reason=body_reason)
        boundary(body_eligible, "BODY_VERSION_NOT_ELIGIBLE_AGAINST_PRIOR")
        boundary(player_source.get("HTTP_ETag") == version_gate.get("HTTP_ETag") and
                 player_source.get("HTTP_Last_Modified") == version_gate.get("HTTP_Last_Modified") and
                 bool(player_source.get("HTTP_ETag")), "STATS_VERSION_DOES_NOT_MATCH_ELIGIBLE_HEAD")
        full = pd.read_csv(io.BytesIO(body), compression="gzip", low_memory=False)
        required = {"game_id", "season", "week", "season_type"}
        boundary(required <= set(full), "ORDINARY_FACT_IDENTITY_SCHEMA_MISSING")
        frame = full[(full.game_id == GAME_ID) & (full.season == 2026) &
                     (full.week == 10) & (full.season_type == "REG")].copy()
        stats_presence = dict(
            expected_game_id=GAME_ID, expected_season=2026, expected_week=10,
            expected_season_type="REG", source_total_rows=len(full),
            exact_game_id_rows_before_contract_filter=int((full.game_id == GAME_ID).sum()),
            exact_qualified_contract_rows=len(frame),
            source_version={k: player_source.get(k) for k in
                            ["raw_SHA256", "HTTP_ETag", "HTTP_Last_Modified", "observed_UTC"]},
            source_schema_identity_columns={k: k in full.columns for k in
                                            ["game_id", "player_id", "team", "opponent_team", "season", "week", "season_type", "receptions"]})
        write(REPORT / "STATS_PRESENCE.json", stats_presence)
        boundary(len(frame) > 0, "FINAL_PLAYER_FACT_ROWS_NOT_YET_AVAILABLE")
        columns = list(dict.fromkeys([
            "player_id", "game_id", "team", "opponent_team", "position",
            "season", "week", "season_type"] + PHYSICAL + list(SIGNED) + ["receptions"]))
        boundary(set(columns) <= set(frame), "ORDINARY_FACT_COMPONENT_SCHEMA_MISSING")
        frame = frame[columns]
        boundary(not frame.duplicated(["game_id", "player_id"]).any(),
                 "DUPLICATE_PLAYER_GAME_FACTS")
        frame["team"] = frame.team.map(team)
        frame["opponent_team"] = frame.opponent_team.map(team)
        facts = {(r["game_id"], r["player_id"]): r for r in
                 frame.astype(object).where(pd.notna(frame), None).to_dict("records")}
        del body, full

        unique = {}
        for row in rows:
            key = (row["game_id"], row["player_id"], row["category"])
            previous = unique.get(key)
            boundary(previous is None or all(previous[k] == row[k] for k in
                     ["team", "opponent_team", "scoring_contract_id"]), "MODEL_VIEW_IDENTITY_CONFLICT")
            unique.setdefault(key, row)
        boundary(len(unique) == 23, "OUTCOME_UNIVERSE_CHANGED")
        outcomes = []
        for key, row in sorted(unique.items()):
            fact = facts.get(key[:2])
            appearance, actual, reasons, proof = "UNKNOWN", None, [], []
            if fact is None:
                reasons.append("MISSING_STAT_ROW_NOT_ZERO_OR_DNP")
            elif fact["team"] != row["team"] or fact["opponent_team"] != row["opponent_team"]:
                reasons.append("PLAYER_TEAM_EVENT_CONFLICT")
            else:
                proof = [c for c in PHYSICAL if integer(fact.get(c)) is not None and integer(fact[c]) > 0]
                proof += [c for c in SIGNED if integer(fact.get(c), True) not in [None, 0]]
                if proof:
                    appearance = "PLAYED"
                    actual = target(fact, row["category"], True)
                else:
                    reasons.append("PARTICIPATION_UNRESOLVED_NOT_DNP")
                if appearance == "PLAYED" and actual is None:
                    reasons.append("MISSING_REQUIRED_STAT_COMPONENT")
            outcomes.append(dict(game_id=row["game_id"], player_id=row["player_id"],
                category=row["category"], espn_event_id=EVENT_ID,
                kickoff_UTC=row["kickoff_UTC"], scoring_contract_id=row["scoring_contract_id"],
                event_status="FINAL", observed_UTC=player_source["observed_UTC"],
                appearance=appearance, actual=actual, participation_proof_fields=proof,
                unavailable_reasons=reasons))

        stage = "DURABLE_OUTCOME_AND_UNCHANGED_GRADER"
        (OUT / "evidence").mkdir(parents=True)
        write(OUT / "evidence/native_status.json", dict(
            event=state, source=native_source, reused_native_binding=reused_native_binding))
        facts_bytes = frame.to_csv(index=False, lineterminator="\n").encode()
        (OUT / "evidence/player_facts.csv.gz").write_bytes(gzip.compress(facts_bytes, mtime=0))
        schedule[["game_id", "season", "week", "game_type", "gameday", "gametime",
                  "home_team", "away_team", "home_score", "away_score"]].to_csv(
                      OUT / "evidence/schedule.csv", index=False, lineterminator="\n")
        write(OUT / "evidence/SOURCE_MANIFEST.json", dict(
            created_UTC=stamp(), sources_used=[native_source,schedule_source,player_source],
            current_operation_consumed_requests=manifest,
            reused_native_binding=reused_native_binding,
            eligible_version_HEAD=version_gate, qualified_player_rows=len(frame),
            rights="Existing qualified ordinary numerical facts: nflverse CC BY4; minimal native status facts; no provider presentation, odds, EPA or charting"))
        (OUT / "evidence/ATTRIBUTION.md").write_text(
            "Ordinary NFL numerical facts: nflverse/nflverse-data (CC BY 4.0). "
            "Schedule: nflverse/nfldata. Minimal final-status facts: ESPN public scoreboard. "
            "Raw responses are not retained. This is postgame outcome observation, not an "
            "historical pregame publication clock. Missing statistics are not filled from "
            "participation. No actual offered lines, direction picks or venue settlements "
            "are inferred.\n")
        evidence = [dict(path=str(p.relative_to(OUT)), SHA256=sha(p), source="QUALIFIED_ORDINARY_FACTS")
                    for p in sorted((OUT / "evidence").iterdir())]
        write(OUT / "OUTCOMES.json", dict(
            schema="C-OUTCOMES-v4", version=VERSION, created_UTC=stamp(),
            source_qualification="OFFICIAL_NUMERICAL_FACTS_VERIFIED",
            source_evidence=evidence, outcomes=outcomes))
        qualified_outcome_packet = dict(path=str((OUT / "OUTCOMES.json").relative_to(ROOT)),
                                        SHA256=sha(OUT / "OUTCOMES.json"))
        write(REPORT / "QUALIFIED_OUTCOME_CHECKPOINT.json", dict(
            outcome_packet=qualified_outcome_packet, original_packet_hashes=original_hashes,
            outcome_states=dict(Counter(r["appearance"] for r in outcomes)),
            outcome_rows=len(outcomes), created_UTC=stamp()))
        grades = grade_run(folder, receipt, OUT / "OUTCOMES.json", GRADE)
        boundary(len(grades) == 69, "FROZEN_FORECAST_GRADE_COUNT_CHANGED")
        lookup = {r["forecast_id"]: r for r in rows}
        for model in sorted({r["model_id"] for r in rows}):
            selected = [g for g in grades if lookup[g["forecast_id"]]["model_id"] == model]
            scored = [g for g in selected if g["state"] == "GRADED_PLAYED"]
            errors = [lookup[g["forecast_id"]]["mean"] - g["actual"] for g in scored]
            medians = [lookup[g["forecast_id"]]["median"] - g["actual"] for g in scored]
            metrics.append(dict(
                model_id=model, eligible=len(selected), scored=len(scored),
                states=dict(Counter(g["state"] for g in selected)),
                mean_MAE=sum(abs(x) for x in errors) / len(errors) if errors else None,
                mean_MSE=sum(x*x for x in errors) / len(errors) if errors else None,
                mean_bias=sum(errors) / len(errors) if errors else None,
                median_MAE=sum(abs(x) for x in medians) / len(medians) if medians else None,
                CRPS=sum(g["CRPS"] for g in scored) / len(scored) if scored else None,
                forecast_only=True, actual_offers=0, OU_direction=None))
        grade_binding = dict(path=str(GRADE.relative_to(ROOT)), SHA256=sha(GRADE),
                             rows=len(grades), states=dict(Counter(g["state"] for g in grades)))
        write(OUT / "RUN.json", dict(version=VERSION, created_UTC=stamp(), event=state,
              original_forecast_rows=len(rows), unique_outcome_rows=len(outcomes),
              grade=grade_binding, original_forecasts_changed=0,
              new_fits=0, new_offers=0, new_original_selected_sides=0))
        checkpoint()
        status, stage = "GRADED_QUALIFIED_FROZEN_FORECAST_ONLY", "COMPLETE"
    except Exception as error:
        reason = type(error).__name__ + ": " + str(error)
    finally:
        signal.setitimer(signal.ITIMER_PROF, 0)
        signal.signal(signal.SIGPROF, previous_handler)
        unchanged = all(sha(ROOT / p) == h for p, h in original_hashes.items())
        boundary(unchanged, "ORIGINAL_PACKET_BYTES_CHANGED")
        resource_receipt = dict(
            full_process_CPU_seconds=time.process_time(), CPU_seconds_from_entry=time.process_time()-ENTRY_CPU,
            wall_seconds=time.monotonic()-started,
            RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
            source_attempts=len(manifest), version_HEAD_attempts=1,
            new_GETs=len(manifest)-1, new_HEADs=0, reused_native_FINAL=True,
            response_bytes=sum(x["bytes_received"] for x in manifest),
            code_SHA256=sha(Path(__file__)),
            original_packet_unchanged=unchanged and len(original_hashes) == 3,
            new_fits=0, new_forecast_generation=0, new_original_picks=0,
            verification_note="Existing validate_run restores prior safe-model predictions as verification only.")
        result = dict(
            id=VERSION, recorded_UTC=stamp(), status=status, stage=stage, reason=reason,
            registration_SHA256=sha(BASE_REPORT / "REGISTRATION.json"),
            resume_registration_SHA256=sha(REPORT / "REGISTRATION.json"),
            prior_stop_binding=dict(path=str((BASE_REPORT / "SOURCE_STATUS.json").relative_to(ROOT)),
                                    SHA256=sha(BASE_REPORT / "SOURCE_STATUS.json")),
            reused_native_binding=reused_native_binding,
            original_packet_hashes=original_hashes, source_manifest=manifest,
            version_gate=version_gate, stats_presence=stats_presence,
            observed_native_event=state, outcome_packet=qualified_outcome_packet,
            grade=grade_binding, metrics=metrics, resources=resource_receipt,
            current_offer_or_capture_claim=False, primary_activation=False,
            no_retry=True, original_pregame_forecast_lineage_preserved=True,
            remaining=None if status.startswith("GRADED_") else
            "See exact stopped stage/version/presence gate. No repeated polling, missing-stat zero fill, or calendar-only finality inference.")
        write(REPORT / "SOURCE_STATUS.json", result)
        print(json.dumps(result, indent=2))
    return 0 if status.startswith("GRADED_") else 2


if __name__ == "__main__":
    raise SystemExit(main())
