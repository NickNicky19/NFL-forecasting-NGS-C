"""Frozen C information/relationship experiment using the adopted common grader.

This module performs no acquisition and never loads executable model objects.
The unchanged baseline is read from the already sealed M3 primitive outputs.
The only new field block is produced by ``information_skill_features_c01``.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
import resource
import signal
import time

import numpy as np
import pandas as pd
from scipy.stats import poisson
from threadpoolctl import threadpool_limits

import abc_championship_v2 as common
from context_experiment_c01 import pooled_fit, pooled_mu
from forward_budget_v4 import complete_C_roots, tree_bytes
from laws_v2 import LeafModel
from receiving_current_validation_c04 import PoissonCountLaw
from safe_models_v4 import export_forest, infer_forest, law_data, law_load
from targeted_data_m3 import clean, digest, read, sha
import targeted_scores_m3 as views


ROOT = Path(__file__).resolve().parents[1]
PARENT = Path('reports/targeted-accuracy-w1w9-01/M3')
DEFAULT_OUT = Path('reports/information-skill-01')
ARMS = ['C1_SUPPORT', 'C1_VALUE', 'R0_PARTIAL', 'R1_PARTIAL']
DECLARED_CONTRASTS = [
    ('C1_SUPPORT', 'LEAF', 'SUPPORT_AND_AVAILABILITY_EFFECT'),
    ('C1_VALUE', 'LEAF', 'TOTAL_INFORMATION_EFFECT_WITHIN_PARENT'),
    ('C1_VALUE', 'C1_SUPPORT', 'VALUES_BEYOND_SUPPORT_WITHIN_PARENT'),
    ('R1_PARTIAL', 'C1_VALUE', 'RELATIONSHIP_FAMILY_SAME_ENRICHED_INFORMATION'),
    ('R1_PARTIAL', 'R0_PARTIAL', 'VALUES_WITHIN_PARTIALLY_POOLED_FAMILY'),
    ('R0_PARTIAL', 'C1_SUPPORT', 'FAMILY_SAME_SUPPORT_INFORMATION'),
]


def resource_roots(root):
    """Retain prior workspace and temporary roots under the shared C cap."""
    candidates = complete_C_roots([root])
    prior = read(root / PARENT / 'RESOURCE_CLOSURE.json')
    candidates.extend(Path(item['path']) for item in prior['roots'])
    candidates.extend(Path('/tmp').glob('information-skill*'))
    candidates.extend(Path('/tmp').glob('info-skill*'))
    result = []
    for path in sorted(set(candidates), key=lambda value: (len(value.parts), str(value))):
        if path.exists() and not any(path.is_relative_to(parent) for parent in result):
            result.append(path)
    return result


def write(path, payload, *, replace=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(clean(payload), separators=(',', ':'), allow_nan=False) + '\n').encode()
    wire = gzip.compress(raw, mtime=0) if path.suffix == '.gz' else raw
    if path.exists() and not replace:
        assert path.read_bytes() == wire, 'FROZEN_OUTPUT_CHANGED:' + str(path)
    else:
        path.write_bytes(wire)
    return sha(path)


def _law_record(law):
    if isinstance(law, PoissonCountLaw):
        return {'kind': 'POISSON', 'mu': law.mean()}
    return law_data(law)


def _restore_law(record):
    if record.get('kind') == 'POISSON':
        return PoissonCountLaw(float(record['mu']))
    return law_load(record)


def _offer_view(offer, arm, product, law, prediction, procedure):
    probabilities = law.probability(offer['line'])
    assert all(math.isfinite(value) and value >= 0 for value in probabilities.values())
    assert abs(sum(probabilities.values()) - 1) <= 1e-10
    if product == 'LAW':
        difference = probabilities['over'] - probabilities['under']
        side = 'OVER' if difference > 1e-12 else 'UNDER' if difference < -1e-12 else 'ABSTAIN'
    else:
        point = prediction['mean' if product == 'MEAN' else 'median']
        side = 'OVER' if point > offer['line'] else 'UNDER' if point < offer['line'] else 'ABSTAIN'
    result = {k: v for k, v in offer.items() if k not in ['retained_methods', 'repeated_offer_ids']}
    result.update(
        arm=arm, product=product, method=arm + '_' + product,
        procedure=procedure + '::' + arm + '::' + product,
        selected_side=side, probabilities=probabilities,
        mean=prediction['mean'], median=prediction['median'],
        point=prediction['mean'] if product == 'MEAN' else prediction['median'] if product == 'MEDIAN' else None,
        point_type=product if product != 'LAW' else None,
        learned=True, fallback=False, model_binding=prediction['model_binding'],
        query_universe_tier=prediction['query_universe_tier'],
        component_fallback_flags=prediction['component_fallback_flags'])
    # The adapter retains the declared missing-state contract; the common
    # grader determines every supported exact-line outcome.
    result['status'] = ('ABSTAIN' if side == 'ABSTAIN' else
                        'UNKNOWN_PARTICIPATION' if offer['appearance'] != 'PLAYED' else
                        'MISSING_ACTUAL' if offer['actual'] is None else 'PENDING')
    result['status'] = common.status(result)
    if offer['actual'] is not None and offer['appearance'] == 'PLAYED':
        result['outcome_log_mass'] = law.logpmf(offer['actual'])
    return result


def _law_checks(laws):
    for law in laws:
        points = [-1, 0, 1, 5, 30, 300]
        cdf = [law.cdf(k) for k in points]
        assert np.isfinite(cdf).all() and np.all(np.diff(cdf) >= -1e-12)
        assert law.cdf(-1) == 0 and abs(law.cdf(10000) - 1) < 1e-10
        assert law.mean() >= 0 and math.isfinite(law.mean())
        for line in [0, .5, 3, 3.5]:
            p = law.probability(line)
            assert set(p) == {'under', 'push', 'over'}
            assert all(math.isfinite(v) and v >= 0 for v in p.values())
            assert abs(sum(p.values()) - 1) <= 1e-10
            assert abs(p['push'] - (law.pmf(int(line)) if float(line).is_integer() else 0)) <= 1e-10


def _declared_pairs(offer_rows, out):
    groups = defaultdict(list)
    for row in offer_rows:
        groups[(row['arm'], row['product'])].append(row)
    pairs = []
    for candidate, control, meaning in DECLARED_CONTRASTS:
        for product in ['MEAN', 'MEDIAN', 'LAW']:
            left, right = groups[(candidate, product)], groups[(control, product)]
            pairs.append(dict(category='rec', arm=candidate, product=product,
                              control_arm=control, control_product=product,
                              contrast=meaning, **views._paired(left, right)))
    for arm in ['LEAF', *ARMS]:
        for product in ['MEAN', 'MEDIAN', 'LAW']:
            for control, cproduct in [('CONTROL_P3_DIRECT', 'LAW'),
                                      ('CONTROL_EARLIER_PREVALENCE_V8', 'LAW'),
                                      ('CONTROL_RETAINED_P2_LAW', 'LAW'),
                                      ('CONTROL_ALWAYS_OVER', 'CONSTANT'),
                                      ('CONTROL_ALWAYS_UNDER', 'CONSTANT')]:
                if groups.get((control, cproduct)):
                    pairs.append(dict(category='rec', arm=arm, product=product,
                                      control_arm=control, control_product=cproduct,
                                      contrast='STRONG_RETAINED_SAME_CASE_REFERENCE',
                                      **views._paired(groups[(arm, product)], groups[(control, cproduct)])))
    write(out / 'scores/DECLARED_PAIRS.json.gz', {'rows': pairs,
          'grader': 'Existing targeted_scores_m3._paired and abc_championship_v2.status',
          'new_grader': False, 'exposed_development': True})


def _own_list_pairs(offer_rows, out):
    """Compare both frozen choosers, separately from same-selected-case sides."""
    memberships = read(out / 'scores/SELECTED_MEMBERSHIP.json.gz')['rows']
    by_policy = defaultdict(list)
    for row in memberships:
        by_policy[(row['arm'], row['side_scope'], row['policy'])].extend(row['selected_offer_ids'])
    boards = defaultdict(dict)
    for row in offer_rows:
        if row['product'] == 'LAW':
            boards[row['arm']][row['offer_id']] = row
    results = []
    for candidate, control, meaning in DECLARED_CONTRASTS:
        for side in ['COMBINED', 'OVER', 'UNDER']:
            policies = sorted({key[2] for key in by_policy if key[:2] == (candidate, side)})
            for policy in policies:
                left_ids = set(by_policy[(candidate, side, policy)])
                right_ids = set(by_policy[(control, side, policy)])
                left = [boards[candidate][key] for key in sorted(left_ids)]
                right = [boards[control][key] for key in sorted(right_ids)]
                same_case_control = [boards[control][key] for key in sorted(left_ids)
                                     if key in boards[control]]
                results.append(dict(
                    category='rec', candidate_arm=candidate, control_arm=control,
                    contrast=meaning, product='LAW', side_scope=side, policy=policy,
                    comparison='EACH_POLICY_OWN_SELECTED_LIST_WITH_SEPARATE_SAME_CASE_SIDES',
                    candidate_own_list=views._summary(left, [2, 3]),
                    control_own_list=views._summary(right, [2, 3]),
                    same_selected_case_direction=views._paired(left, same_case_control),
                    intersection=len(left_ids & right_ids),
                    candidate_only_members=len(left_ids - right_ids),
                    control_only_members=len(right_ids - left_ids),
                    original_pregame_selection=False))
    write(out / 'scores/OWN_LIST_COMPARISONS.json.gz', {'rows': results,
          'scope': 'Frozen retrospective weekly lists, not original issued picks; no new policy search.'})


def run(root=ROOT, out=DEFAULT_OUT, *, precharged_cpu=0.0):
    root = Path(root).resolve()
    out = Path(out)
    out = out if out.is_absolute() else root / out
    registration = out / 'REGISTRATION.json'
    reg = read(registration)
    assert reg['id'] == 'INFORMATION-SKILL-01-C-ROLE-DEPTH-ADJUSTED-v1'
    assert reg.get('execution_authorized') is True, 'REGISTRATION_NOT_AUTHORIZED'
    statefile = out / 'FIT_LEDGER.json'
    if statefile.exists():
        state = read(statefile)
        assert not state.get('active'), 'UNCLEAN_RUN_REQUIRES_SCOPED_RECOVERY'
        assert abs(state['precharged_CPU_seconds'] - precharged_cpu) < 1e-6
    else:
        state = dict(attempts=[], completed=[], failures=[], restored=[],
                     CPU_seconds=float(precharged_cpu), precharged_CPU_seconds=float(precharged_cpu))
    assert not (out / 'RUN_COMPLETE.json').exists(), 'COMPLETED_EXPERIMENT_FROZEN'
    cpu_mark = time.process_time()
    started = time.monotonic()
    state['active'] = True
    state['started_UTC'] = datetime.now(timezone.utc).isoformat()

    def checkpoint():
        nonlocal cpu_mark
        current = time.process_time()
        state['CPU_seconds'] += current - cpu_mark
        cpu_mark = current
        state['peak_RSS_bytes'] = max(state.get('peak_RSS_bytes', 0),
                                     resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024)
        state['new_public_bytes'] = tree_bytes(out)
        measured_roots = resource_roots(root)
        state['whole_C_bytes'] = sum(tree_bytes(path) for path in measured_roots)
        state['whole_C_roots'] = [str(path) for path in measured_roots]
        write(statefile, state, replace=True)
        assert state['CPU_seconds'] <= 400, 'INFORMATION_CPU_CAP_WITH_200_COMPLETION_RESERVE'
        assert state['peak_RSS_bytes'] <= 1288490188, 'INFORMATION_RSS_CAP'
        assert state['new_public_bytes'] <= 33554432, 'INFORMATION_PUBLIC_CAP'
        assert state['whole_C_bytes'] <= 2684354560, 'INFORMATION_WHOLE_C_CAP'
        assert time.monotonic() - started <= 2400, 'INFORMATION_WALL_CAP'

    def reserve(key):
        assert key not in state['attempts'], 'FROZEN_FIT_ATTEMPT_WITHOUT_RESTORATION:' + key
        assert len(state['attempts']) < 40, 'INFORMATION_FIT_CAP'
        state['attempts'].append(key)
        checkpoint()

    predictions, offered, origins, checks = [], [], [], []
    try:
        signal.signal(signal.SIGPROF, lambda *_: (_ for _ in ()).throw(RuntimeError('INFORMATION_CPU_TIMER')))
        signal.setitimer(signal.ITIMER_PROF, max(.01, 400 - state['CPU_seconds']))
        data_path = root / PARENT / 'inputs/FEATURES_AND_MEMBER_FACTS.json.gz'
        feature_path = out / 'inputs/FEATURE_MATRIX.json.gz'
        data, block = read(data_path), read(feature_path)
        rows = data['rows']
        x = np.asarray(data['X_by_target']['rec'], float)
        bx = np.asarray(block['matrix'], float)
        assert x.shape == (len(rows), 32) and bx.shape == (len(rows), 6)
        expected_order = digest([(r['game_id'], r['player_id']) for r in rows])
        assert block['identity_order_SHA256'] == expected_order, 'INFORMATION_QUERY_IDENTITY_ORDER'
        matrices = {'C1_SUPPORT': np.c_[x, bx[:, :5]], 'C1_VALUE': np.c_[x, bx],
                    'R0_PARTIAL': np.c_[x, bx[:, :5]], 'R1_PARTIAL': np.c_[x, bx]}
        names = {arm: data['feature_names']['rec'] + block['feature_names'][:5 if arm.endswith('SUPPORT') or arm == 'R0_PARTIAL' else 6]
                 for arm in ARMS}
        identities = np.asarray([[r['player_id'], r['team'], r['opponent_team']] for r in rows])
        offers = [r for r in read(root / PARENT / 'inputs/NATIVE_OFFERS.json.gz')['primary']
                  if r['category'] == 'rec']
        offer_map = {(r['game_id'], r['player_id']): r for r in offers}
        baseline = [dict(r, arm='LEAF') for r in read(root / PARENT / 'base-PREDICTIONS.json.gz')
                    if r['category'] == 'rec' and r['arm'] == 'M3-0']
        predictions.extend(baseline)
        base_offers = read(root / PARENT / 'base-OFFER_ROWS.json.gz')
        offered.extend(dict(r, arm='LEAF', method='LEAF_' + r['product'])
                       for r in base_offers if r['category'] == 'rec' and r['arm'] == 'M3-0')
        offered.extend(r for r in base_offers if r['category'] == 'rec' and r['arm'].startswith('CONTROL_'))
        # These compatible controls are present in the retained native rows,
        # although the old M3 report did not export them into its own views.
        # Preserve their exact probabilities, original sides and grades.
        for offer in offers:
            for name, arm in [('EARLIER_PREVALENCE_V8', 'CONTROL_EARLIER_PREVALENCE_V8'),
                              ('P2_LAW', 'CONTROL_RETAINED_P2_LAW')]:
                original = offer['retained_methods'].get(name)
                if original is None:
                    continue
                control = {key: value for key, value in offer.items()
                           if key not in ['retained_methods', 'repeated_offer_ids']}
                probabilities = {side: original.get('p_' + side) for side in ['under', 'push', 'over']}
                if any(value is None for value in probabilities.values()):
                    probabilities = None
                control.update(arm=arm, product='LAW', selected_side=original['selected_side'],
                               status=original['status'], probabilities=probabilities,
                               mean=None, median=None, point=None, point_type=None,
                               fallback=original.get('fallback'), learned=True,
                               method_version=original['method_version'],
                               original_forecast_id=original.get('forecast_id'))
                assert common.status(control) == control['status']
                offered.append(control)
        assert len(baseline) == 1975 and len(offers) == 295
        schedule = pd.read_csv(root / 'sources/category-decision-release-01/schedule.csv')
        schedule['kickoff'] = (pd.to_datetime(schedule.gameday + ' ' + schedule.gametime)
                               .dt.tz_localize('America/New_York').dt.tz_convert('UTC').astype('int64') / 1e9)
        checkpoint()

        for week in range(1, 10):
            cutoff = float(schedule.loc[(schedule.season == 2026) & (schedule.week == week), 'kickoff'].min())
            train = [i for i, row in enumerate(rows) if not row['query_only'] and
                     row['available'] is not None and row['available'] < cutoff and row['values']['rec'] is not None]
            query = data['query_indices_2026'][str(week)]
            assert not ({rows[i]['game_id'] for i in train} & {rows[i]['game_id'] for i in query})
            assert all(rows[i]['kickoff'] >= cutoff for i in query)
            target = np.asarray([rows[i]['values']['rec'] for i in train], float)
            assert np.isfinite(target).all() and np.all(target >= 0) and np.all(target == np.rint(target))
            roles = np.asarray([rows[i]['position'] for i in train])
            query_roles = np.asarray([rows[i]['position'] for i in query])
            members = [(rows[i]['game_id'], rows[i]['player_id']) for i in train]
            admission_mutated = [i for i, row in enumerate(rows) if not row['query_only'] and
                                 row['available'] is not None and row['available'] < cutoff and
                                 (999999 if row['available'] >= cutoff else row['values']['rec']) is not None]
            assert admission_mutated == train
            original_y = np.asarray([rows[i]['values']['rec'] for i in train], float)
            assert np.array_equal(original_y, target)

            for arm in ARMS:
                key = f'2026-W{week:02}-{arm}'
                path = out / 'models' / f'W{week:02}' / (arm + '.json.gz')
                train_x = matrices[arm][train]
                query_x = matrices[arm][query]
                binding = dict(
                    id=key, category='rec', arm=arm, training_rows=len(train),
                    membership_SHA256=digest(members),
                    X_y_SHA256=hashlib.sha256(np.nan_to_num(train_x, nan=999999.).tobytes() + target.tobytes()).hexdigest(),
                    feature_names=names[arm], original_inputs_SHA256=sha(data_path),
                    information_matrix_SHA256=sha(feature_path), registration_SHA256=sha(registration),
                    fit_code_SHA256=sha(Path(__file__)),
                    fit_origin_UTC=pd.Timestamp(cutoff, unit='s', tz='UTC').isoformat(),
                    latest_training_available=max(rows[i]['available'] for i in train))
                leaf = arm.startswith('C1_')
                if path.exists():
                    saved = read(path)
                    assert saved['binding'] == binding, 'ORIGIN_MODEL_RESTORATION_CONTRACT'
                    model = saved['model']
                    state['restored'].append(key)
                else:
                    reserve(key)
                    with threadpool_limits(limits=1):
                        if leaf:
                            fitted = LeafModel('count', 1).fit(train_x, target, roles)
                            model = export_forest(fitted)
                            native_probe = fitted.laws(query_x[:2], query_roles[:2])
                            safe_probe = infer_forest(model, query_x[:2], query_roles[:2])
                            assert all(abs(a.mean() - b.mean()) <= 1e-10 and
                                       max(abs(a.cdf(k) - b.cdf(k)) for k in [-1, 0, 1, 3, 10, 30]) <= 1e-10
                                       for a, b in zip(native_probe, safe_probe)), 'NATIVE_SAFE_LEAF_PARITY'
                        else:
                            model = pooled_fit(train_x, target, identities[train], True)
                    write(path, {'binding': binding, 'model': model})
                    state['completed'].append(key)
                    checkpoint()

                restored = read(path)['model']
                with threadpool_limits(limits=1):
                    if leaf:
                        laws = infer_forest(restored, query_x, query_roles)
                        singles = infer_forest(restored, query_x[:1], query_roles[:1])
                    else:
                        mu = pooled_mu(restored, query_x, identities[query])
                        assert np.isfinite(mu).all() and np.all(mu >= 0)
                        laws = [PoissonCountLaw(float(value)) for value in mu]
                        single = pooled_mu(restored, query_x[:1], identities[query[:1]])
                        singles = [PoissonCountLaw(float(single[0]))]
                assert abs(laws[0].mean() - singles[0].mean()) <= 1e-10
                assert abs(laws[0].cdf(3) - singles[0].cdf(3)) <= 1e-10
                _law_checks(laws[:2])
                model_binding = dict(path=str(path.relative_to(root)), SHA256=sha(path),
                                     output='DISCRETE_COUNT_LAW', complete_corrector='NONE')
                feature_use = None
                if leaf:
                    splits = [feature for tree in model['trees'] for feature in tree['feature'] if feature >= 0]
                    width = len(names[arm])
                    feature_use = {name: sum(feature == index or feature == index + width for feature in splits)
                                   for index, name in enumerate(names[arm]) if index >= 32}
                else:
                    feature_use = {name: dict(value_coefficient=model['coef'][index],
                                              missing_coefficient=model['coef'][index + len(names[arm])])
                                   for index, name in enumerate(names[arm]) if index >= 32}
                origin = dict(binding, model_binding=model_binding, query_rows=len(query),
                              source_policy='STRICT_KICKOFF_PLUS_7D_CURRENT_VINTAGE_RECONSTRUCTION',
                              learned_feature_use=feature_use,
                              convergence=model.get('converged') if not leaf else None,
                              restoration_batch_single_pass=True,
                              native_safe_fit_parity='CHECKED_FIRST_TWO_ROWS' if leaf else 'EXISTING_POOLED_PRIMITIVE_CONTRACT',
                              partial_pooling='L2 regularized player/team/opponent effects; unseen identity effect zero' if not leaf else None)
                origins.append(origin)
                for local_index, row_index in enumerate(query):
                    row = rows[row_index]
                    law = laws[local_index]
                    prediction = {key: row.get(key) for key in [
                        'game_id', 'player_id', 'position', 'team', 'opponent_team', 'season', 'week',
                        'query_only', 'native_offer_query', 'query_universe_tier']}
                    actual = row['values']['rec']
                    component_fallback = dict(
                        substantive_block_missing=bool(bx[row_index, 4]),
                        no_qualified_own_targets=bool(bx[row_index, 0] == 0),
                        no_qualified_opponent_role_targets=bool(bx[row_index, 1] == 0),
                        unseen_player=False, unseen_team=False, unseen_opponent=False,
                        interpretation='Component priors/missing-value handling within a learned complete forecast; not incumbent point fallback.')
                    if not leaf:
                        for column, field in enumerate(['unseen_player', 'unseen_team', 'unseen_opponent']):
                            component_fallback[field] = identities[row_index, column] not in model['categories'][column]
                    prediction.update(category='rec', arm=arm, actual=actual,
                                      mean=law.mean(), median=law.quantile(.5),
                                      variance=law.mean() if not leaf else None,
                                      learned=True, fallback=False, model_binding=model_binding,
                                      component_fallback_flags=component_fallback,
                                      feature_age_policy='STRICT_KICKOFF_PLUS_7D_CURRENT_VINTAGE_RECONSTRUCTION',
                                      law=_law_record(law))
                    if actual is not None:
                        prediction['outcome_log_mass'] = law.logpmf(actual)
                    predictions.append(prediction)
                    offer = offer_map.get((row['game_id'], row['player_id']))
                    if offer is not None:
                        for product in ['LAW', 'MEAN', 'MEDIAN']:
                            offered.append(_offer_view(offer, arm, product, law, prediction, reg['id']))
                write(out / 'checkpoints' / (key + '.json'), origin)
                checkpoint()
            checks.append(dict(week=week, training_admission_target_future_label_mutation='PASS',
                               training_membership_SHA256=digest(members),
                               scope='Exact same eligible earlier labels and design inputs; feature-layer full-context mutation is separate.'))
            print('INFORMATION_ORIGIN_COMPLETE', week, len(train), len(query),
                  round(state['CPU_seconds'], 3), flush=True)

        write(out / 'PREDICTIONS.json.gz', predictions)
        write(out / 'OFFER_ROWS.json.gz', offered)
        write(out / 'ORIGINS.json', origins)
        write(out / 'CHECKS.json', checks)
        score_receipt = views.summarize(offered, predictions, out / 'scores')
        write(out / 'SCORE_ADAPTER_RECEIPT.json', score_receipt)
        _declared_pairs(offered, out)
        _own_list_pairs(offered, out)
        checkpoint()
        complete = dict(id=reg['id'], status='EXECUTED_FROZEN_NATIVE_COMPARISON',
                        executed_UTC=datetime.now(timezone.utc).isoformat(),
                        actual_line_weeks=[2, 3], numerical_origins=list(range(1, 10)),
                        missing_actual_line_weeks=[1, 4, 5, 6, 7, 8, 9],
                        new_fit_attempts=len(state['attempts']), query_product_rows=len(predictions),
                        offer_product_rows=len(offered), primary_activation=False,
                        private_A_join_claim=False, retrospective_exposure=True,
                        recipe_SHA256=sha(registration), input_feature_SHA256=sha(feature_path))
        write(out / 'RUN_COMPLETE.json', complete)
    except Exception as error:
        state['failures'].append(dict(error=type(error).__name__ + ':' + str(error),
                                      UTC=datetime.now(timezone.utc).isoformat()))
        raise
    finally:
        signal.setitimer(signal.ITIMER_PROF, 0)
        state['active'] = False
        checkpoint()
    return state


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--out', type=Path, default=DEFAULT_OUT)
    parser.add_argument('--precharged-cpu', type=float, required=True)
    arguments = parser.parse_args()
    with threadpool_limits(limits=1):
        print(json.dumps(run(arguments.root, arguments.out, precharged_cpu=arguments.precharged_cpu), indent=2))
