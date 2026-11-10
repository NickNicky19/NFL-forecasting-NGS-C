"""Zero-fit qualified controls and point-only handoff after the frozen C04 run.

No actuals, lines, probabilities, selected sides, participation or grades enter
the handoff. A owns any permitted actual-offer join and its independent receipt.
"""
import time
CPU_START = time.process_time()
WALL_START = time.monotonic()
import hashlib
import importlib.util
import json
import resource
import signal
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'src'))
import pandas as pd
import receiving_timing_c04 as d


def bound(path):
    return dict(path=str(path.relative_to(ROOT)), SHA256=d.sha(path))


def safe_schedule():
    """Read the same two saved schedules, without another source reconstruction."""
    original = d.c03.lookback.INPUTS / 'schedule.csv'
    late = ROOT / 'prospective/runs/C-FWD-v4-20261105-W09-JAXBAL-remainder/sources/schedule.csv'
    bindings = d.read(d.OUT / 'INPUT_BINDINGS.json')
    expected = bindings['underlying_builder_reports_checked_not_rewritten']['reports/player-context-matchup-01/completion-decision-v1/lookback/INPUT_BINDINGS.json']['schedule_sha']
    assert d.sha(original) == expected, 'HANDOFF_SCHEDULE_VERSION_MISMATCH'
    a, b = pd.read_csv(original), pd.read_csv(late)
    a = pd.concat([a[~((a.season == 2026) & (a.week == 8))], b[(b.season == 2026) & (b.week == 8)]], ignore_index=True)
    a['kickoff_UTC'] = pd.to_datetime(a.gameday + ' ' + a.gametime).dt.tz_localize('America/New_York').dt.tz_convert('UTC')
    assert not a.game_id.duplicated().any()
    return {r['game_id']: r['kickoff_UTC'].isoformat() for r in a.to_dict('records')}, [dict(source_role='ORIGINAL_SCHEDULE', SHA256=d.sha(original)), bound(late)]


def point_handoff():
    schedule, schedule_bindings = safe_schedule()
    manifest = dict(
        id='C04-POINT-ONLY-OWNER-LOCAL-HANDOFF-v1', created_UTC=d.now(),
        category='rec', statistic='FULL_GAME_OVERTIME_OFFICIAL_RECEPTIONS',
        recipient_execution_owner='A:permitted_owner_local_offer_join',
        recipient_receipt='NOT_VERIFIED', common_admission='NOT_IMPLIED_BY_EXPORT',
        historical_tier='CURRENT_REVISED_TIMING_RECONSTRUCTION;EXPOSED_DEVELOPMENT;NOT_ORIGINAL_ISSUANCE',
        query_universe='Existing_C03_RB_WR_TE_stat_row_conditioned_historical_queries;not_authenticated_pregame_roster',
        query_horizon='Per_game_kickoff_reconstruction;weekly_fit_at_earliest_scheduled_game',
        forecast_issue_clock='NONE:historical_reconstruction_export_creation_is_not_pregame_issuance',
        supplied=['canonical_identity', 'historical_team_role', 'query_cutoff', 'saved_unrounded_mean', 'saved_lower_median', 'immutable_model_reference'],
        not_supplied=['actual', 'line', 'price', 'selected_side', 'participation', 'probability', 'EV', 'grade', 'Top_Picks'],
        decision_rule='Receiver_must_bind_its_exact_offer_contract;point>line_OVER;point<line_UNDER;point==line_ABSTAIN',
        model_source=bound(ROOT / 'src/receiving_timing_c04.py'),
        code_dependencies=[bound(ROOT / 'src' / f) for f in [
            'receiving_increment_c03.py', 'data_v2.py', 'context_features_c01.py',
            'receiving_defense_c03.py', 'laws_v2.py', 'safe_models_v4.py',
        ]],
        input_bindings=bound(d.OUT / 'INPUT_BINDINGS.json'),
        feature_order=bound(d.OUT / 'FEATURE_ORDER.json'),
        schedule_bindings=schedule_bindings,
        numerical_evidence='2025_and_2026_W1_W8_separately;not_evidence_of_actual_offers',
        actual_line_evidence='C_native_Pinnacle_W2_W3_separate;new_A_join_not_executed_by_C',
        new_fits=0, new_inference=0, future_queries_issued=0,
        source_predictions=[], origins={}, procedures={},
    )
    for arm in ['F0', 'F1', 'F2', 'F3']:
        for product in ['MEAN', 'MEDIAN']:
            procedure = d.VERSION + '::' + arm + '::' + product
            manifest['procedures'][procedure] = dict(
                category='rec', arm=arm, output_type=product.lower(),
                original_C03_arm=d.OLD.get(arm),
                original_procedure_id=(d.c03.VERSION + '::' + d.OLD[arm] + '::' + product) if arm in d.OLD else None,
                availability_policy=d.POLICY7 if arm in d.OLD else d.POLICY1,
                aliases_are_not_new_learner_families=True,
            )
            descriptor = manifest['procedures'][procedure]
            descriptor['recipe_descriptor_SHA256'] = hashlib.sha256(json.dumps(descriptor, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    rows = []
    for year in [2025, 2026]:
        path = d.ART / f'NUMERICAL_ROWS-{year}.json.xz'
        run = d.read(d.OUT / f'RUN-{year}.json')
        origins = {r['origin']: r for r in run['origins']}
        source = d.read(path)
        manifest['source_predictions'].append(dict(**bound(path), season=year, rows=len(source), actual_weeks=sorted({r['week'] for r in source})))
        for week in range(1, 9):
            origin = f'{year}-W{week:02}'
            for arm in ['F0', 'F1', 'F2', 'F3']:
                old = d.OLD.get(arm)
                model_path = (d.c03.ART / f'{origin}-{old}.json.xz') if old else (d.ART / f'{origin}-{arm}.json.xz')
                model = d.read(model_path)
                key = origin + '-' + arm
                manifest['origins'][key] = dict(
                    **bound(model_path), arm=arm, original_C03_arm=old,
                    model_fit_cutoff_UTC=origins[origin]['fit_cutoff_UTC'],
                    source_code_SHA256=model['code_SHA256'],
                    source_registration_SHA256=model['registration_SHA256'],
                    fingerprint=model['fingerprint'], membership_SHA256=model['membership_SHA256'],
                    training_rows=model['training_rows'],
                    feature_order_SHA256=hashlib.sha256(json.dumps(model['feature_order'], separators=(',', ':')).encode()).hexdigest(),
                    availability_policy=d.POLICY7 if old else d.POLICY1,
                    reused_original_fit=bool(old),
                )
        for source_row in source:
            row = {k: source_row[k] for k in ['game_id', 'player_id', 'position', 'team', 'opponent_team', 'season', 'week']}
            row.update(query_cutoff_UTC=schedule[row['game_id']], category='rec', forecasts={})
            for arm in ['F0', 'F1', 'F2', 'F3']:
                saved = source_row[arm]
                assert d.finite(saved['mean']) and d.finite(saved['median'])
                row['forecasts'][arm] = dict(
                    mean=saved['mean'], median=saved['median'],
                    mean_procedure_id=d.VERSION + '::' + arm + '::MEAN',
                    median_procedure_id=d.VERSION + '::' + arm + '::MEDIAN',
                    origin_ref=f'{year}-W{row["week"]:02}-{arm}',
                )
            rows.append(row)
    rows.sort(key=lambda r: (r['season'], r['week'], r['game_id'], r['player_id']))
    assert len({(r['season'], r['game_id'], r['player_id']) for r in rows}) == len(rows)
    # A structural whitelist is stronger than deleting target fields after copy.
    assert all(set(r) == {'game_id', 'player_id', 'position', 'team', 'opponent_team', 'season', 'week', 'query_cutoff_UTC', 'category', 'forecasts'} for r in rows)
    target = d.OUT / 'POINT_HANDOFF.json.xz'
    d.write(target, dict(id=manifest['id'], rows=rows))
    manifest['export'] = dict(**bound(target), query_rows=len(rows), arm_query_records=4*len(rows), typed_point_values=8*len(rows), public_bytes=target.stat().st_size)
    d.write(d.OUT / 'POINT_HANDOFF_MANIFEST.json', manifest)
    return manifest['export']


def main():
    signal.signal(signal.SIGPROF, lambda *_: (_ for _ in ()).throw(RuntimeError('C04_POSTSCORE_CPU_CAP')))
    signal.setitimer(signal.ITIMER_PROF, max(.01, 30-(time.process_time()-CPU_START)))
    try:
        path = Path(__file__).with_name('qualified_control_view.py')
        spec = importlib.util.spec_from_file_location('qualified_c04_controls', path)
        controls = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(controls)
        for year in [2026, 2025]:
            controls.main(year)
        exported = point_handoff()
        d.write(d.OUT / 'POSTSCORE_RESOURCE.json', dict(
            id='C04-POSTSCORE-PACKAGE-v1', created_UTC=d.now(),
            CPU_seconds=time.process_time()-CPU_START, wall_seconds=time.monotonic()-WALL_START,
            RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
            new_fits=0, new_inference=0, source_requests=0,
            point_handoff=exported, code_SHA256=d.sha(Path(__file__)),
        ))
        print('C04_POSTSCORE_PACKAGE_COMPLETE', exported)
    finally:
        signal.setitimer(signal.ITIMER_PROF, 0)


if __name__ == '__main__':
    main()
