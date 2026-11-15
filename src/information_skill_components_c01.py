"""Conditional component diagnostics for the frozen C information experiment.

No fitting, source acquisition, offered-line grading or policy selection occurs
here.  Outcomes supply scoring weights and labels only.  The final reception
models never consume these postgame component labels.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
import resource
import time


ROOT = Path(__file__).resolve().parents[1]
OUT = Path('reports/information-skill-01')
PARENT = Path('reports/targeted-accuracy-w1w9-01/M3')
DEPTHS = ['behind_LOS', '0_9', '10_19', '20plus', 'UNKNOWN']


def read(path):
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == '.gz' else raw)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finite(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def binary_state():
    return dict(targets=0, catches=0, incomplete_targets=0,
                brier_sum=0.0, catch_brier_sum=0.0, incomplete_brier_sum=0.0,
                finite_nll_sum=0.0, catch_finite_nll_sum=0.0,
                incomplete_finite_nll_sum=0.0, zero_probability_outcomes=0)


def add_binary(state, targets, catches, probability):
    assert targets >= catches >= 0
    assert finite(probability) and 0 <= probability <= 1
    failed = targets - catches
    state['targets'] += targets
    state['catches'] += catches
    state['incomplete_targets'] += failed
    success_brier = catches * (1 - probability) ** 2
    failed_brier = failed * probability ** 2
    state['catch_brier_sum'] += success_brier
    state['incomplete_brier_sum'] += failed_brier
    state['brier_sum'] += success_brier + failed_brier
    if catches:
        if probability == 0:
            state['zero_probability_outcomes'] += catches
        else:
            term = -catches * math.log(probability)
            state['catch_finite_nll_sum'] += term
            state['finite_nll_sum'] += term
    if failed:
        if probability == 1:
            state['zero_probability_outcomes'] += failed
        else:
            term = -failed * math.log1p(-probability)
            state['incomplete_finite_nll_sum'] += term
            state['finite_nll_sum'] += term


def finish_binary(state):
    n = state['targets']
    infinite = state['zero_probability_outcomes'] > 0
    return dict(state, brier=state['brier_sum'] / n if n else None,
                log_loss=state['finite_nll_sum'] / n if n and not infinite else None,
                log_loss_state='INFINITE' if infinite else 'DEFINED' if n else 'UNDEFINED_NO_TARGETS',
                observed_catch_rate=state['catches'] / n if n else None)


def multi_state():
    return dict(targets=0, brier_sum=0.0, finite_nll_sum=0.0,
                zero_probability_outcomes=0,
                observed_depth_targets=[0] * 5,
                expected_depth_targets=[0.0] * 5,
                nonzero_target_player_games=0, player_game_mix_L1_sum=0.0)


def add_multinomial(state, counts, probabilities):
    n = sum(counts)
    assert all(finite(p) and 0 <= p <= 1 for p in probabilities)
    assert abs(sum(probabilities) - 1) <= 1e-12
    state['targets'] += n
    sum_square = sum(p * p for p in probabilities)
    state['brier_sum'] += sum(c * (1 - 2 * p + sum_square)
                              for c, p in zip(counts, probabilities))
    for i, (c, p) in enumerate(zip(counts, probabilities)):
        state['observed_depth_targets'][i] += c
        state['expected_depth_targets'][i] += n * p
        if c:
            if p == 0:
                state['zero_probability_outcomes'] += c
            else:
                state['finite_nll_sum'] -= c * math.log(p)
    if n:
        state['nonzero_target_player_games'] += 1
        state['player_game_mix_L1_sum'] += sum(abs(c / n - p)
                                              for c, p in zip(counts, probabilities))


def finish_multinomial(state):
    n = state['targets']
    games = state['nonzero_target_player_games']
    infinite = state['zero_probability_outcomes'] > 0
    return dict(state, categorical_Brier=state['brier_sum'] / n if n else None,
                categorical_log_loss=state['finite_nll_sum'] / n if n and not infinite else None,
                log_loss_state='INFINITE' if infinite else 'DEFINED' if n else 'UNDEFINED_NO_TARGETS',
                mean_player_game_depth_mix_L1=state['player_game_mix_L1_sum'] / games if games else None)


def period(game_id):
    parts = game_id.split('_')
    return int(parts[0]), int(parts[1])


def summary(records, labels):
    counts = Counter()
    games, players, supported_games = set(), set(), set()
    own_support, role_support, ages = [], [], []
    states = Counter()
    mixture = multi_state()
    forecast = {'BASELINE': binary_state(), 'MATCHUP': binary_state()}
    depth = {name: {'BASELINE': binary_state(), 'MATCHUP': binary_state()}
             for name in DEPTHS}
    for record in records:
        key = (record['game_id'], record['player_id'])
        counts['eligible_player_games'] += 1
        games.add(record['game_id'])
        players.add(record['player_id'])
        states[record['substantive_state']] += 1
        if record['own_mix_fallback'] == 'ROLE_DEPTH_PRIOR':
            counts['player_depth_prior_only'] += 1
        if record['defense_role_fallback'] == 'POOLED_DEPTH_RESIDUAL':
            counts['defense_role_prior_only'] += 1
        support = record['feature_values']
        own_support.append(support[0])
        role_support.append(support[1])
        if finite(support[3]):
            ages.append(support[3])
        counts['clipped_component_probability_cells'] += record['component_probability_clipped_cells']
        label = labels.get(key)
        if label is None:
            counts['component_label_unavailable'] += 1
            continue
        assert label['label_only_never_predictor']
        n = label['observed_target_depth_n']
        c = label['observed_catch_depth_c']
        assert len(n) == len(c) == 5
        assert all(finite(a) and a >= 0 and float(a).is_integer() for a in n + c)
        n, c = [int(a) for a in n], [int(a) for a in c]
        assert all(a >= b for a, b in zip(n, c))
        assert sum(n) == label['observed_targets'] and sum(c) == label['observed_catches']
        counts['qualified_label_player_games'] += 1
        counts['qualified_label_targets'] += sum(n)
        counts['qualified_label_catches'] += sum(c)
        if not sum(n):
            counts['known_zero_target_player_games'] += 1
        p0 = record['component_baseline_catch_probability']
        p1 = record['component_matchup_catch_probability']
        if not finite(p0) or not finite(p1):
            counts['unavailable_component_forecast_player_games'] += 1
            counts['unavailable_component_forecast_targets'] += sum(n)
            continue
        counts['matched_component_player_games'] += 1
        counts['matched_component_targets'] += sum(n)
        counts['matched_component_catches'] += sum(c)
        supported_games.add(record['game_id'])
        if not sum(n):
            counts['matched_zero_target_undefined_rate_player_games'] += 1
        add_multinomial(mixture, n, record['predicted_depth_mix'])
        add_binary(forecast['BASELINE'], sum(n), sum(c), p0)
        add_binary(forecast['MATCHUP'], sum(n), sum(c), p1)
        for i, name in enumerate(DEPTHS):
            add_binary(depth[name]['BASELINE'], n[i], c[i], record['component_baseline_rate_by_depth'][i])
            add_binary(depth[name]['MATCHUP'], n[i], c[i], record['component_matchup_rate_by_depth'][i])
    predicted = {name: finish_binary(state) for name, state in forecast.items()}
    d0, d1 = predicted['BASELINE'], predicted['MATCHUP']
    return dict(
        counts=dict(counts), games=len(games), unique_players=len(players),
        supported_component_games=len(supported_games),
        substantive_states=dict(states),
        source_support=dict(
            player_prior_targets8_min=min(own_support) if own_support else None,
            player_prior_targets8_mean=sum(own_support) / len(own_support) if own_support else None,
            opponent_role_prior_targets8_min=min(role_support) if role_support else None,
            opponent_role_prior_targets8_mean=sum(role_support) / len(role_support) if role_support else None,
            opponent_age_days_min=min(ages) if ages else None,
            opponent_age_days_max=max(ages) if ages else None,
            fixed_prior_targets=20,
            uncertainty_scope='Support counts and fixed shrinkage, not posterior/independent-trial confidence intervals'),
        forecast_mix_expected_conversion=predicted,
        MATCHUP_minus_BASELINE=dict(
            Brier=d1['brier'] - d0['brier'] if d0['brier'] is not None and d1['brier'] is not None else None,
            log_loss=d1['log_loss'] - d0['log_loss'] if d0['log_loss'] is not None and d1['log_loss'] is not None else None),
        depth_conditional_conversion={name: {arm: finish_binary(state) for arm, state in arms.items()}
                                      for name, arms in depth.items()},
        predicted_target_depth_mix=finish_multinomial(mixture))


def run(root=ROOT, out=OUT):
    root = Path(root).resolve()
    out = out if out.is_absolute() else root / out
    output = out / 'COMPONENT_RESULTS.json'
    resource_output = out / 'COMPONENT_RESOURCE.json'
    assert not output.exists() and not resource_output.exists(), 'COMPONENT_RESULTS_ALREADY_FROZEN'
    started = time.monotonic()
    input_paths = [out / 'inputs/FEATURE_RECORDS.json.gz', out / 'inputs/COMPONENT_LABELS.json.gz',
                   root / PARENT / 'inputs/NATIVE_OFFERS.json.gz']
    records = read(input_paths[0])['records']
    label_rows = read(input_paths[1])['records']
    labels = {(r['game_id'], r['player_id']): r for r in label_rows}
    assert len(labels) == len(label_rows)
    keys = [(r['game_id'], r['player_id']) for r in records]
    assert len(keys) == len(set(keys))
    offers = [r for r in read(input_paths[2])['primary'] if r['category'] == 'rec']
    offer_ids = {(r['game_id'], r['player_id']) for r in offers}
    assert len(offer_ids) == len(offers) == 295
    assert offer_ids <= set(keys)
    panels = {
        'ROLE_APPROPRIATE_RB_WR_TE_STAT_ROW_CONDITIONED': [r for r in records if r['position'] in ['RB', 'WR', 'TE']],
        'WR_TE_STAT_ROW_CONDITIONED_PLUS_NATIVE_QUERY_ADDITIONS': [r for r in records if r['position'] in ['WR', 'TE']],
        'FIXED_NATIVE_RECEPTION_OFFER_PLAYERS': [r for r in records if (r['game_id'], r['player_id']) in offer_ids],
    }
    results = []
    for panel, candidates in panels.items():
        for season, requested in [(2025, list(range(1, 19))), (2026, list(range(1, 10)))]:
            rr = [r for r in candidates if period(r['game_id'])[0] == season]
            if not rr and panel == 'FIXED_NATIVE_RECEPTION_OFFER_PLAYERS' and season == 2025:
                continue
            actual_weeks = sorted({period(r['game_id'])[1] for r in rr
                                   if (r['game_id'], r['player_id']) in labels})
            for week in ['ALL', *requested]:
                subset = rr if week == 'ALL' else [r for r in rr if period(r['game_id'])[1] == week]
                results.append(dict(panel=panel, season=season, week=week,
                                    actual_component_label_weeks=actual_weeks if week == 'ALL' else ([week] if week in actual_weeks else []),
                                    **summary(subset, labels)))
            if season == 2025:
                early = [r for r in rr if period(r['game_id'])[1] <= 9]
                results.append(dict(panel=panel, season=season, week='EARLY_W1_W9',
                                    actual_component_label_weeks=[w for w in actual_weeks if w <= 9],
                                    **summary(early, labels)))
    result = dict(
        id='C-INFORMATION-SKILL-COMPONENT-DIAGNOSTICS-v1',
        recorded_UTC=datetime.now(timezone.utc).isoformat(),
        registration_SHA256=sha(out / 'REGISTRATION.json'),
        sources=[dict(path=str(path.relative_to(root)), bytes=path.stat().st_size, SHA256=sha(path)) for path in input_paths],
        target='rec', new_fits=0, new_source_requests=0, new_actual_offer_grades=0,
        outcome_contract='Postgame qualified target/catch counts used only for diagnostic labels and proper-score weights. Explicit zero targets remain undefined-rate cases; missing labels never become zero.',
        probability_contract='Prior-only player depth mixture and baseline/adjusted catch probabilities are frozen inputs. Exact zero probabilities retain infinite NLL outcomes; no epsilon replacement. Per-depth actual exposure is a conditional scoring diagnostic, not pregame inference.',
        formulas=dict(binary_Brier='[c*(1-p)^2+(n-c)*p^2]/n',
                      binary_log_loss='[-c*log(p)-(n-c)*log(1-p)]/n',
                      multinomial_Brier='sum_d n_d*(1-2*p_d+sum_j p_j^2)/sum_d n_d',
                      multinomial_log_loss='-sum_d n_d*log(p_d)/sum_d n_d',
                      aggregation='Numerator totals / target denominator totals, never average of rounded rates'),
        limits=['Conditional-on-target quality diagnostics do not forecast target volume or establish final prop improvement.',
                'Depth mixture is a shrunk expectation, not full joint uncertainty integration or alignment/routes.',
                'Current-vintage strict kickoff+7d reconstruction does not authenticate historical publication.',
                '2026 frozen PBP supplies W1-W8 only; W9 feature queries do not manufacture W9 component labels.',
                'Repeated targets are dependent within players/games/weeks; these descriptive proper scores provide no IID accuracy guarantee.'],
        rows=results)
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    usage = resource.getrusage(resource.RUSAGE_SELF)
    charge = dict(status='PASS', CPU_seconds_full_process=usage.ru_utime + usage.ru_stime,
                  conservative_initial_schema_read_CPU_charge=2.0,
                  total_component_CPU_charge=usage.ru_utime + usage.ru_stime + 2.0,
                  wall_seconds= time.monotonic() - started, RSS_bytes=usage.ru_maxrss * 1024,
                  max_total_component_CPU_seconds=10,
                  new_fits=0, new_source_requests=0, new_actual_offer_grades=0,
                  result_SHA256=sha(output), result_bytes=output.stat().st_size,
                  measurement_scope='Full calculation-process CPU plus conservative initial-schema read charge; final tiny resource receipt serialization is bookkeeping overhead.')
    assert charge['total_component_CPU_charge'] <= 10, 'COMPONENT_CPU_CAP'
    resource_output.write_text(json.dumps(charge, indent=2) + '\n')
    return charge


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--out', type=Path, default=OUT)
    args = parser.parse_args()
    print(json.dumps(run(args.root, args.out), indent=2))
