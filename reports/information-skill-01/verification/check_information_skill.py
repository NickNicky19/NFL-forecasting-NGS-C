"""Independent deterministic arithmetic review of saved C information inputs.

This reads permitted C evidence only. It neither fits nor grades a model and
does not authenticate the source's unavailable original publication vintage.
"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import hashlib
import json
from pathlib import Path
import time
import warnings

import numpy as np
import pandas as pd


def read(path):
    wire = Path(path).read_bytes()
    return json.loads(gzip.decompress(wire) if str(path).endswith('.gz') else wire)


def canonical_hash(value):
    def clean(x):
        if isinstance(x, np.ndarray):
            return clean(x.tolist())
        if isinstance(x, (list, tuple)):
            return [clean(v) for v in x]
        if isinstance(x, (float, np.floating)):
            return float(x) if np.isfinite(x) else None
        if isinstance(x, (int, np.integer)):
            return int(x)
        if isinstance(x, dict):
            return {str(k): clean(v) for k, v in x.items()}
        return x
    return hashlib.sha256(json.dumps(clean(value), sort_keys=True, separators=(',', ':'),
                                      allow_nan=False).encode()).hexdigest()


def close(left, right):
    assert np.allclose(np.asarray(left, float), np.asarray(right, float),
                       rtol=0, atol=1e-12, equal_nan=True)


def verify(root):
    started = time.process_time()
    root = Path(root)
    out = root / 'reports/information-skill-01'
    folder = out / 'inputs'
    matrix_record = read(folder / 'FEATURE_MATRIX.json.gz')
    records = read(folder / 'FEATURE_RECORDS.json.gz')['records']
    adjusted = read(folder / 'OFFENSE_ADJUSTMENT_RECORDS.json.gz')['records']
    fixture = read(folder / 'NFL_MUTATION_CHECK.json')
    data = read(root / 'reports/targeted-accuracy-w1w9-01/M3/inputs/FEATURES_AND_MEMBER_FACTS.json.gz')
    matrix = np.asarray(matrix_record['matrix'], float)
    assert len(records) == len(data['rows']) == len(matrix)
    assert matrix.shape[1] == 6
    lookup = {(r['game_id'], r['player_id']): i for i, r in enumerate(data['rows'])}
    detailed = set(np.linspace(0, len(records) - 1, 64, dtype=int).tolist())
    detailed.update(lookup[(r['game_id'], r['player_id'])] for r in fixture['cases'])
    close([r['feature_values'] for r in records], matrix)
    for i, record in enumerate(records):
        native = data['rows'][i]
        assert (record['game_id'], record['player_id']) == (native['game_id'], native['player_id'])
        assert record['team'] == native['team'] and record['opponent_team'] == native['opponent_team']
        for source in record['own_games'] + record['opponent_games']:
            assert source['game_id'] != record['game_id']
            assert source['kickoff'] < record['information_cutoff_epoch']
            assert source['assumed_available'] < record['information_cutoff_epoch']
        assert len(record['own_games']) <= 8 and len(record['opponent_games']) <= 8
        if i not in detailed:
            continue
        n = np.asarray(record['own_targets_by_depth'], float)
        c = np.asarray(record['own_catches_by_depth'], float)
        league_mix = np.asarray(record['league_role_depth_mix_prior'], float)
        mix = (n + 20 * league_mix) / (n.sum() + 20)
        close(mix, record['predicted_depth_mix'])
        assert abs(mix.sum() - 1) < 1e-12 and np.all(mix >= 0)
        opp_n = np.asarray(record['opponent_role_targets_by_depth'], float)
        opp_r = np.asarray(record['opponent_role_raw_residual_by_depth'], float)
        pooled = np.asarray(record['opponent_all_role_depth_residual'], float)
        role_response = (opp_r + 20 * pooled) / (opp_n + 20)
        close(role_response, record['opponent_role_shrunk_residual_by_depth'])
        missing = record['substantive_state'] == 'UNAVAILABLE_HISTORY'
        value = np.nan if missing else float(mix @ role_response)
        age = ((record['information_cutoff_epoch'] - record['opponent_games'][-1]['kickoff']) / 86400
               if record['opponent_games'] else np.nan)
        expected = [n.sum(), opp_n.sum(), len(record['opponent_games']), age, float(missing), value]
        close(expected, matrix[i])
        close(record['feature_values'], matrix[i])
        baseline = (c + 20 * np.asarray(record['league_role_depth_catch_prior'], float)) / (n + 20)
        close(baseline, record['component_baseline_rate_by_depth'])
        close(np.clip(baseline + role_response, 0, 1), record['component_matchup_rate_by_depth'])
    residuals_checked = 0
    for record in adjusted:
        ln = np.asarray(record['offense_prior_league_targets'], float)
        lc = np.asarray(record['offense_prior_league_catches'], float)
        overall = lc.sum() / ln.sum() if ln.sum() else .5
        dn = ln.sum(axis=0)
        depth_rate = np.divide(lc.sum(axis=0), dn, out=np.full(5, overall), where=dn > 0)
        rate = np.divide(lc, ln, out=np.broadcast_to(depth_rate, (4, 5)).copy(), where=ln > 0)
        n = np.asarray(record['offense_prior_targets'], float)
        c = np.asarray(record['offense_prior_catches'], float)
        expected = (c + 20 * rate) / (n + 20)
        close(expected, record['expected_rate'])
        if 'target_catch_cells' in record:
            cells = np.asarray(record['target_catch_cells'], float)
            assert np.all(cells[:, :, 1] <= cells[:, :, 0])
            close(cells[:, :, 1] - cells[:, :, 0] * expected, record['residual'])
            residuals_checked += 1
        for prior in record['offense_prior_games']:
            assert prior['assumed_available'] < record['kickoff'] and prior['kickoff'] < record['kickoff']
    selected_adjusted = [adjusted[i] for i in np.linspace(0, len(adjusted) - 1, 6, dtype=int)]
    source_binding = read(folder / 'SOURCE_BINDINGS.json')
    roles = {(r['game_id'], r['player_id']): r['position'] for r in data['rows']}
    proof = []
    for source in source_binding['source_files']:
        path = root / source['path']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == source['SHA256']
        frame = pd.read_csv(path, usecols=['game_id', 'posteam', 'receiver_player_id', 'air_yards',
                                          'complete_pass', 'pass_attempt', 'sack', 'two_point_attempt',
                                          'play_deleted', 'play_type'])
        valid = frame[(frame.pass_attempt == 1) & (frame.sack != 1) &
                      (frame.two_point_attempt != 1) & (frame.play_deleted != 1) &
                      (frame.play_type != 'no_play')]
        for record in selected_adjusted:
            plays = valid[(valid.game_id == record['game_id']) & (valid.posteam == record['offense'])]
            if not len(plays):
                continue
            assert len(plays) == record['attempts']
            assert plays.complete_pass.isin([0, 1]).all()
            cells = np.zeros((4, 5, 2))
            for row in plays[plays.receiver_player_id.notna()].itertuples(index=False):
                role = roles.get((row.game_id, row.receiver_player_id))
                ri = {'WR': 0, 'TE': 1, 'RB': 2}.get(role, 3)
                a = row.air_yards
                di = 4 if not np.isfinite(a) else 0 if a < 0 else 1 if a < 10 else 2 if a < 20 else 3
                cells[ri, di, 0] += 1
                cells[ri, di, 1] += int(row.complete_pass == 1)
            close(cells[:, :, 1] - cells[:, :, 0] * np.asarray(record['expected_rate']), record['residual'])
            proof.append(dict(game_id=record['game_id'], offense=record['offense'],
                              valid_attempts=len(plays), targets=int(cells[:, :, 0].sum()),
                              catches=int(cells[:, :, 1].sum()),
                              source_SHA256=source['SHA256'], residual_reproduced=True))
    assert len(proof) == 6
    full = np.column_stack([np.asarray(data['X_by_target']['rec'], float), matrix])
    for case in fixture['cases']:
        i = lookup[(case['game_id'], case['player_id'])]
        cutoff = case['cutoff']
        prior = [j for j, r in enumerate(data['rows'])
                 if r.get('available') is not None and np.isfinite(r['available'])
                 and r['available'] < cutoff and r['game_id'] != case['game_id']
                 and r.get('values', {}).get('rec') is not None]
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', RuntimeWarning)
            medians = np.nanmedian(full[prior], axis=0)
        medians = np.where(np.isfinite(medians), medians, 0)
        row = full[i:i + 1]
        transformed = np.column_stack([np.where(np.isfinite(row), row, medians), ~np.isfinite(row)]).astype(float)
        assert case['full_query_context_rows'] == len(data['rows'])
        assert case['feature_equal'] and case['transformed_equal']
        assert canonical_hash(full[i]) == case['raw_full_feature_SHA256']
        assert canonical_hash(transformed) == case['transformed_full_input_SHA256']
    assert len(fixture['cases']) >= 4
    return dict(
        id='C-INFORMATION-SKILL-INDEPENDENT-FEATURE-REVIEW-v1',
        checked_UTC=dt.datetime.now(dt.timezone.utc).isoformat(), status='PASS',
        aligned_feature_records=len(records), detailed_independent_feature_formulas=len(detailed),
        earlier_offense_adjustments=len(adjusted), raw_PBP_residual_proof=proof,
        exact_residuals_with_numerators_denominators_checked=residuals_checked,
        independently_rebuilt_full_design_cases=len(fixture['cases']),
        own_and_opponent_history_admission='CHECKED_ALL_SAVED_RECORDS',
        scope='Independent formulas/count arithmetic and consumed design replay from retained NFL evidence; integrated full-context mutation reviewed and its equality hashes matched. No private peer rows, raw-PBP mutation rebuild, fit reproduction or original source-vintage authentication.',
        new_fits=0, new_grades=0, new_source_calls=0,
        CPU_seconds=time.process_time() - started,
    )


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[3])
    args = parser.parse_args()
    result = verify(args.root)
    path = args.root / 'reports/information-skill-01/verification/FEATURE_INDEPENDENT.json'
    with path.open('x') as handle:
        json.dump(result, handle, indent=2)
        handle.write('\n')
    print(json.dumps(result))
