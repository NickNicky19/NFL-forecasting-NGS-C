"""One independent frozen-fit reproduction and Decimal/membership review.

No production action, source acquisition, threshold tuning or old record update.
Run only after the primary fit worker has completed.
"""
from __future__ import annotations

import datetime as dt
from collections import Counter, defaultdict
from decimal import Decimal
import gzip
import hashlib
import json
import math
from pathlib import Path
import time
import warnings

import numpy as np
from sklearn.ensemble import ExtraTreesRegressor
from threadpoolctl import threadpool_limits


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'reports/information-skill-01'


def read(path):
    b = Path(path).read_bytes()
    return json.loads(gzip.decompress(b) if str(path).endswith('.gz') else b)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def grade(row):
    side = row['selected_side']
    if side is None:
        return 'UNAVAILABLE_FORECAST'
    if side == 'ABSTAIN':
        return 'ABSTAIN'
    if row['appearance'] != 'PLAYED':
        return 'UNKNOWN_PARTICIPATION'
    if row['actual'] is None:
        return 'MISSING_ACTUAL'
    y, line = Decimal(str(row['actual'])), Decimal(str(row['line']))
    if y == line:
        return 'PUSH'
    return 'WIN' if (y > line) == (side == 'OVER') else 'LOSS'


def fit_review():
    state = read(OUT / 'FIT_LEDGER.json')
    assert not state['active'] and len(state['attempts']) == 36
    assert (OUT / 'RUN_COMPLETE.json').exists()
    model_path = OUT / 'models/W02/C1_VALUE.json.gz'
    saved = read(model_path)
    binding, expected = saved['binding'], saved['model']
    data_path = ROOT / 'reports/targeted-accuracy-w1w9-01/M3/inputs/FEATURES_AND_MEMBER_FACTS.json.gz'
    block_path = OUT / 'inputs/FEATURE_MATRIX.json.gz'
    data, block = read(data_path), read(block_path)
    rows = data['rows']
    x = np.column_stack([np.asarray(data['X_by_target']['rec'], float), np.asarray(block['matrix'], float)])
    assert x.shape == (len(rows), 38)
    assert binding['feature_names'] == data['feature_names']['rec'] + block['feature_names']
    assert binding['original_inputs_SHA256'] == sha(data_path)
    assert binding['information_matrix_SHA256'] == sha(block_path)
    cutoff = dt.datetime.fromisoformat(binding['fit_origin_UTC']).timestamp()
    train = [i for i, r in enumerate(rows) if not r['query_only'] and r['available'] is not None
             and r['available'] < cutoff and r['values']['rec'] is not None]
    query = data['query_indices_2026']['2']
    assert not ({rows[i]['game_id'] for i in train} & {rows[i]['game_id'] for i in query})
    y = np.asarray([rows[i]['values']['rec'] for i in train], float)
    xx = x[train]
    assert hashlib.sha256(np.nan_to_num(xx, nan=999999.).tobytes() + y.tobytes()).hexdigest() == binding['X_y_SHA256']
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', RuntimeWarning)
        imputation = np.nanmedian(xx, axis=0)
    imputation = np.where(np.isfinite(imputation), imputation, 0)
    assert np.array_equal(imputation, expected['imputation'])
    z = np.column_stack([np.where(np.isfinite(xx), xx, imputation), ~np.isfinite(xx)]).astype(np.float32)
    zq = np.column_stack([np.where(np.isfinite(x[query]), x[query], imputation), ~np.isfinite(x[query])]).astype(np.float32)
    fit_start = dict(id='C-INFORMATION-SKILL-INDEPENDENT-FIT-START-v1',
                     started_UTC=dt.datetime.now(dt.timezone.utc).isoformat(),
                     arm='C1_VALUE', origin='2026-W02', attempt=1,
                     parent_fit_attempts=len(state['attempts']), total_with_review=37,
                     model_SHA256=sha(model_path), training_rows=len(train),
                     settings='ExtraTrees32/depth8/minleaf30/maxfeatures1/bootstrapFalse/random1701/njobs1; no search',
                     input_fingerprint=binding['X_y_SHA256'])
    with (OUT / 'verification/FIT_START.json').open('x') as f:
        json.dump(fit_start, f, indent=2)
        f.write('\n')
    # Direct library construction, independent median/design preparation and
    # per-tree empirical masses; the parent's LeafModel fitter is not called.
    with threadpool_limits(limits=1):
        model = ExtraTreesRegressor(n_estimators=32, max_depth=8, min_samples_leaf=30,
                                    max_features=1., bootstrap=False, random_state=1701,
                                    n_jobs=1).fit(z, y)
        train_leaves, query_leaves = model.apply(z), model.apply(zq)
    assert len(expected['trees']) == 32
    for j, tree in enumerate(model.estimators_):
        old = expected['trees'][j]
        assert np.array_equal(tree.tree_.children_left, old['left'])
        assert np.array_equal(tree.tree_.children_right, old['right'])
        assert np.array_equal(tree.tree_.feature, old['feature'])
        assert np.array_equal(tree.tree_.threshold, old['threshold'])
        for node in np.unique(train_leaves[:, j]):
            values, counts = np.unique(y[train_leaves[:, j] == node], return_counts=True)
            assert [values.tolist(), counts.tolist()] == old['leaves'][str(node)]
    predictions = {(p['game_id'], p['player_id']): p
                   for p in read(OUT / 'PREDICTIONS.json.gz')
                   if p['arm'] == 'C1_VALUE' and p['week'] == 2}
    probe_indices = list(range(min(8, len(query))))
    for role in ['WR', 'TE']:
        found = next((i for i, j in enumerate(query) if rows[j]['position'] == role), None)
        if found is not None and found not in probe_indices:
            probe_indices.append(found)
    sparse = next((i for i, j in enumerate(query) if block['matrix'][j][0] == 0), None)
    if sparse is not None and sparse not in probe_indices:
        probe_indices.append(sparse)
    roles = np.asarray([rows[i]['position'] for i in train])
    checks = []
    for qi in probe_indices:
        row = rows[query[qi]]
        p = predictions[(row['game_id'], row['player_id'])]
        role_y = y[roles == row['position']]
        mean_role = max(.05, float(role_y.mean() if len(role_y) else y.mean()))
        q = mean_role / (1 + mean_role)
        leaf_values = [y[train_leaves[:, j] == query_leaves[qi, j]] for j in range(32)]
        mean = .95 * sum(float(v.mean()) for v in leaf_values) / 32 + .05 * q / (1 - q)
        assert abs(mean - p['mean']) < 1e-10
        for k in [-1, 0, 1, 3, 10, 30]:
            empirical = sum(float(np.mean(v <= k)) for v in leaf_values) / 32
            cdf = .95 * empirical + .05 * (0 if k < 0 else 1 - q ** (k + 1))
            law = p['law']
            stored_cdf = ((1 - law['alpha']) * sum(w for v, w in zip(law['values'], law['weights']) if v <= k)
                          + law['alpha'] * (0 if k < 0 else 1 - law['prior']['q'] ** (k + 1)))
            assert abs(cdf - stored_cdf) < 1e-10
        checks.append(dict(game_id=row['game_id'], player_id=row['player_id'], role=row['position'],
                           mean_reproduced=True, CDF_reproduced=True,
                           zero_own_target_support=block['matrix'][query[qi]][0] == 0))
    return dict(new_independent_fits=1, origin='2026-W02', arm='C1_VALUE',
                training_rows=len(train), exact_tree_structures_and_leaf_label_counts=32,
                model_SHA256=sha(model_path), probes=checks,
                tolerance=1e-10, native_constructor='Direct sklearn ExtraTreesRegressor; separate transformations and law arithmetic')


def result_review():
    rows = read(OUT / 'OFFER_ROWS.json.gz')
    groups = defaultdict(list)
    boards = defaultdict(list)
    for row in rows:
        assert grade(row) == row['status'], (row['offer_id'], row['arm'], row['product'])
        groups[(row['arm'], row['product'])].append(row)
        if row['product'] == 'LAW':
            boards[(row['arm'], row['week'])].append(row)
    all_views = read(OUT / 'scores/RESULTS.json.gz')['rows']
    for result in all_views:
        group = groups[(result['arm'], result['product'])]
        selected = group if result['week'] == 'ALL' else [r for r in group if r['week'] == result['week']]
        assert result['eligible'] == len(selected)
        for side in ['OVER', 'UNDER', 'COMBINED']:
            relevant = [r for r in selected if r['selected_side'] in ['OVER', 'UNDER']
                        and (side == 'COMBINED' or r['selected_side'] == side)]
            wins = sum(grade(r) == 'WIN' for r in relevant)
            losses = sum(grade(r) == 'LOSS' for r in relevant)
            target = result[side]
            assert target['selected'] == len(relevant) and target['decided'] == wins + losses
            assert target['wins'] == (wins if wins + losses else None)
            assert target['losses'] == (losses if wins + losses else None)
            assert target['rate'] == (wins / (wins + losses) if wins + losses else None)
    memberships = read(OUT / 'scores/SELECTED_MEMBERSHIP.json.gz')['rows']
    counts = Counter()
    for membership in memberships:
        board = boards[(membership['arm'], membership['week'])]
        pool = []
        for row in board:
            probabilities, side = row.get('probabilities'), row['selected_side']
            if probabilities is None or side not in ['OVER', 'UNDER']:
                continue
            if membership['side_scope'] != 'COMBINED' and side != membership['side_scope']:
                continue
            denominator = probabilities['over'] + probabilities['under']
            if denominator <= 0:
                continue
            confidence = probabilities[side.lower()] / denominator
            pool.append((confidence, row))
        pool.sort(key=lambda item: (-item[0], item[1]['game_id'], item[1]['player_id'], item[1]['offer_id']))
        policy = membership['policy']
        if policy.startswith('RAW_P_'):
            threshold = int(policy.removeprefix('RAW_P_')) / 100
            picked = [row for q, row in pool if q >= threshold]
        else:
            n = (math.ceil(int(policy.removeprefix('COVERAGE_')) / 100 * len(board))
                 if policy.startswith('COVERAGE_') else int(policy.removeprefix('TOP_')))
            picked = [row for _, row in pool[:n]]
        assert [r['offer_id'] for r in picked] == membership['selected_offer_ids']
        assert [r['selected_side'] for r in picked] == membership['selected_sides']
        counts[membership['arm']] += 1
    return dict(Decimal_row_grades_checked=len(rows), own_side_full_and_weekly_views_checked=len(all_views),
                frozen_membership_views_checked=len(memberships), memberships_by_arm=dict(counts),
                independent_rank_ties='Own chosen-side nonpush confidence descending, game/player/offer lexical; existing quotas/thresholds unchanged')


def main():
    started = time.process_time()
    fit = fit_review()
    with (OUT / 'verification/FIT_REPRODUCTION.json').open('x') as handle:
        json.dump(fit, handle, indent=2)
        handle.write('\n')
    result = result_review()
    receipt = dict(id='C-INFORMATION-SKILL-RESULT-INDEPENDENT-v1', status='PASS',
                   checked_UTC=dt.datetime.now(dt.timezone.utc).isoformat(),
                   fit_reproduction=fit, result_reproduction=result,
                   CPU_seconds=time.process_time() - started,
                   new_source_calls=0, new_original_selections=0, new_scored_NFL_weeks=0,
                   limits='C permitted local rows/model only; no A/B private-row, authentic original source/quote-time or production admission verification. Regrading reproduces frozen derived decisions, not new football observations.')
    with (OUT / 'verification/RESULT_INDEPENDENT.json').open('x') as handle:
        json.dump(receipt, handle, indent=2)
        handle.write('\n')
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
