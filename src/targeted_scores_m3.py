"""Bounded M3 result views using the adopted common grader and summaries.

This adapter does not fit, calibrate, acquire data, create offers, or alter an
original side/outcome.  Selected-policy views are frozen retrospective weekly
comparison lists, not claims that all weekly inputs existed before one cutoff.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
import gzip
import hashlib
import json
import math

import numpy as np

import abc_championship_v2 as common

SCHEMA = 'C-M3-RESULT-VIEWS-v1.1'
REQUESTED_WEEKS = list(range(1, 10))
RELIABILITY_EDGES = [.5, .6, .7, .75, .8, .9, 1.]
RAW_THRESHOLDS = [.75, .80, .90]
FRACTIONS = [1., .5, .25, .1]
TOP_K = [6, 10, 20]
SEED = 1703
REPLICATES = 500
UNKNOWN_STATES = {'UNKNOWN_PARTICIPATION', 'MISSING_ACTUAL', 'PENDING'}
DECIDED = {'WIN', 'LOSS'}


def clean(value):
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [clean(v) for v in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, (float, np.floating)):
        return float(value) if math.isfinite(value) else None
    return value


def _write(path, payload):
    path = Path(path)
    data = (json.dumps(clean(payload), separators=(',', ':'), allow_nan=False) + '\n').encode()
    wire = gzip.compress(data, mtime=0) if path.suffix == '.gz' else data
    if path.exists():
        if path.read_bytes() != wire:
            raise AssertionError('M3_RESULT_ALREADY_FROZEN:' + str(path))
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as handle:
            handle.write(wire)
    return dict(path=str(path), bytes=len(wire), SHA256=hashlib.sha256(wire).hexdigest())


def _category(row):
    return row.get('category', row.get('target'))


def _key(row):
    return (_category(row), row['game_id'], row['player_id'])


def _method(row):
    return (row['arm'], row.get('product', 'LAW'))


def _finite(value):
    return (isinstance(value, (float, int, np.floating, np.integer)) and
            not isinstance(value, (bool, np.bool_)) and math.isfinite(float(value)))


def _probs(row):
    p = row.get('probabilities')
    if p is None and all(row.get('p_' + x) is not None for x in ['under', 'push', 'over']):
        p = {x: row['p_' + x] for x in ['under', 'push', 'over']}
    if p is None:
        return None
    if set(p) != {'under', 'push', 'over'}:
        raise AssertionError('M3_PROBABILITY_SCHEMA')
    if any(not _finite(v) or v < 0 for v in p.values()) or abs(sum(p.values()) - 1) > 1e-10:
        raise AssertionError('M3_INVALID_PROBABILITY')
    return {k: float(v) for k, v in p.items()}


def _confidence(row):
    side = row.get('selected_side')
    p = _probs(row)
    if side not in ['OVER', 'UNDER'] or p is None:
        return None
    denominator = p['over'] + p['under']
    if denominator <= 0:
        return None
    return p[side.lower()] / denominator


def _outcome(row):
    if row.get('appearance') != 'PLAYED' or not _finite(row.get('actual')):
        return None
    y, line = row['actual'], row['line']
    return 'under' if y < line else 'over' if y > line else 'push'


def _target_status(wins, losses):
    n = wins + losses
    return {str(q): dict(
        MODEL_CONFIDENCE='SEPARATE_FROM_OBSERVED_ACCURACY',
        OBSERVED_HIT_RATE=(wins / n if n else None),
        observed_target_met=(wins / n >= q if n else None),
        observed_status=('OBSERVED_ON_THIS_SAMPLE' if n and wins / n >= q else
                         'TARGET_NOT_ESTABLISHED'),
        SUPPORTED_ACCURACY_CLAIM='TARGET_NOT_ESTABLISHED',
        support_reason='Exposed retrospective development; limited dependent clusters and repeated '
                       'comparisons; no prespecified simultaneous guarantee of this lower accuracy bound.')
        for q in RAW_THRESHOLDS}


def _probability_quality(rows):
    known = []
    conditional = []
    impossible = 0
    for row in rows:
        p = _probs(row)
        truth = _outcome(row)
        if p is None or truth is None:
            continue
        brier = .5 * sum((p[x] - int(x == truth)) ** 2 for x in p)
        if p[truth] > 0:
            nll = -math.log(p[truth])
        else:
            nll = None
            impossible += 1
        known.append((brier, nll))
        confidence = _confidence(row)
        if row['status'] in DECIDED and confidence is not None:
            conditional.append((confidence, int(row['status'] == 'WIN')))
    reliability = []
    for j, (lo, hi) in enumerate(zip(RELIABILITY_EDGES[:-1], RELIABILITY_EDGES[1:])):
        q = [(p, y) for p, y in conditional if lo <= p and
             (p <= hi if j == len(RELIABILITY_EDGES) - 2 else p < hi)]
        reliability.append(dict(low_inclusive=lo, high=hi,
            high_inclusive=j == len(RELIABILITY_EDGES) - 2,
            decided=len(q), mean_model_confidence=float(np.mean([p for p, _ in q])) if q else None,
            wins=sum(y for _, y in q), observed_accuracy=float(np.mean([y for _, y in q])) if q else None))
    # Confidence can be <.5 for a point-based side; keep its support explicit.
    below = [(p, y) for p, y in conditional if p < .5]
    return dict(probability_scored=len(known),
        Brier_half_multiclass=float(np.mean([x[0] for x in known])) if known else None,
        log_loss=(float(np.mean([x[1] for x in known])) if known and not impossible else None),
        infinite_log_loss_count=impossible,
        finite_log_loss_only_mean=(float(np.mean([x[1] for x in known if x[1] is not None]))
                                  if any(x[1] is not None for x in known) else None),
        log_loss_caution='Any impossible observed event makes the complete mean log loss infinite; '
                         'the finite-only mean is a separate diagnostic, not a replacement.',
        reliability_conditioning='Chosen-side probability conditional on a nonpush decision; '
                                 'observed reliability uses WIN/LOSS only.',
        reliability=reliability,
        below_half_confidence_decided=len(below),
        confidence_ordering='Fixed bins, no score-based cutoff search')


def _summary(rows, evaluated_weeks=None):
    for row in rows:
        if common.status(row) != row['status']:
            raise AssertionError('M3_COMMON_GRADER_MISMATCH:' + str(row.get('offer_id')))
    result = common.summary(rows)
    states = Counter(row['status'] for row in rows)
    selected = [r for r in rows if r.get('selected_side') in ['OVER', 'UNDER']]
    decided = [r for r in selected if r['status'] in DECIDED]
    unknown = [r for r in selected if r['status'] in UNKNOWN_STATES]
    wins = sum(r['status'] == 'WIN' for r in decided)
    losses = len(decided) - wins
    n = len(decided)
    result.update(
        unknown=len(unknown), unknown_states={k: states[k] for k in sorted(UNKNOWN_STATES)},
        pushes=states['PUSH'], voids=states['VOID'], DNP=states['DNP'],
        unique_players=len({r['player_id'] for r in rows}),
        unique_decided_selections=len({_key(r) for r in decided}),
        learned_selected=sum(bool(r.get('learned', not r.get('fallback', False))) for r in selected),
        fallback_selected=sum(r.get('fallback') is True for r in selected),
        fallback_attribution_unknown_selected=sum(r.get('fallback') is None for r in selected),
        fallback_fraction=(sum(r.get('fallback') is True for r in selected) / len(selected)
                           if selected else None),
        evaluated_weeks=sorted(evaluated_weeks if evaluated_weeks is not None else
                               {r['week'] for r in rows}),
        selected_weeks=sorted({r['week'] for r in selected}),
        decided_weeks=sorted({r['week'] for r in decided}),
        zero_selection_weeks=sorted(set(evaluated_weeks or [r['week'] for r in rows]) -
                                    {r['week'] for r in selected}),
        picks_per_week={str(w): sum(r['week'] == w for r in selected)
                        for w in sorted(evaluated_weeks or {r['week'] for r in rows})},
        selected_unknown_sensitivity=dict(
            unresolved_selected=len(unknown),
            lower_accuracy_if_all_unknown_lose=(wins / (n + len(unknown)) if n + len(unknown) else None),
            upper_accuracy_if_all_unknown_win=((wins + len(unknown)) / (n + len(unknown))
                                              if n + len(unknown) else None),
            interpretation='Sensitivity only; no unknown is assigned an actual grade.'),
        unique_decided_progress={str(k): dict(observed=len({_key(r) for r in decided}),
                                             remaining=max(0, k-len({_key(r) for r in decided})))
                                 for k in [50, 100, 200]},
        target_status=_target_status(wins, losses),
        probability_quality=_probability_quality(rows),
    )
    for side in ['OVER', 'UNDER', 'COMBINED']:
        rr = selected if side == 'COMBINED' else [r for r in selected if r['selected_side'] == side]
        dec = [r for r in rr if r['status'] in DECIDED]
        w = sum(r['status'] == 'WIN' for r in dec)
        u = sum(r['status'] in UNKNOWN_STATES for r in rr)
        side_weeks = sorted({r['week'] for r in rr})
        evaluated = sorted(evaluated_weeks if evaluated_weeks is not None else
                           {r['week'] for r in rows})
        result[side]['target_status'] = _target_status(w, len(dec)-w)
        result[side].update(unknown=u, games=len({r['game_id'] for r in rr}),
            unique_players=len({r['player_id'] for r in rr}),
            unique_decided_selections=len({_key(r) for r in dec}),
            uncertainty=common.a.interval(rr),
            selected_weeks=side_weeks,
            decided_weeks=sorted({r['week'] for r in dec}),
            zero_selection_weeks=sorted(set(evaluated)-set(side_weeks)),
            picks_per_week={str(k): sum(r['week'] == k for r in rr) for k in evaluated},
            fallback_selected=sum(r.get('fallback') is True for r in rr),
            fallback_fraction=(sum(r.get('fallback') is True for r in rr)/len(rr) if rr else None),
            unknown_sensitivity=dict(unresolved_selected=u,
                lower_accuracy_if_all_unknown_lose=w/(len(dec)+u) if len(dec)+u else None,
                upper_accuracy_if_all_unknown_win=(w+u)/(len(dec)+u) if len(dec)+u else None),
            probability_quality=_probability_quality(rr))
    return result


def _paired(candidate, control):
    ca = {_key(r): r for r in candidate}
    co = {_key(r): r for r in control}
    pairs = []
    for k in sorted(ca.keys() & co.keys()):
        x, y = ca[k], co[k]
        for f in ['line', 'game_id', 'player_id', 'category', 'appearance', 'actual', 'offer_id']:
            if x.get(f) != y.get(f):
                raise AssertionError('M3_PAIR_CONTRACT_MISMATCH:' + f)
        pairs.append((x, y))
    decided = [(x, y) for x, y in pairs if x['status'] in DECIDED and y['status'] in DECIDED]
    cw = sum(x['status'] == 'WIN' for x, _ in decided)
    rw = sum(y['status'] == 'WIN' for _, y in decided)
    by = defaultdict(lambda: [0, 0])
    for x, y in decided:
        z = by[(x['season'], x['week'])]
        z[0] += int(x['status'] == 'WIN') - int(y['status'] == 'WIN')
        z[1] += 1
    interval = dict(kind='N/A_NO_COMMON_DECIDED', low=None, high=None, week_clusters=0)
    if by:
        a = np.asarray(list(by.values()), dtype=float)
        rng = np.random.default_rng(SEED)
        sample = a[rng.integers(len(a), size=(REPLICATES, len(a)))].sum(axis=1)
        diffs = sample[:, 0] / sample[:, 1]
        lo, hi = np.quantile(diffs, [.025, .975])
        interval = dict(kind='PAIRED_WHOLE_WEEK_SENSITIVITY_500_SEED1703',
            low=float(lo), high=float(hi), week_clusters=len(a),
            small_cluster_caution=len(a) < 20,
            scope='Descriptive dependent-week resampling, not an independent or multiple-search guarantee')
    return dict(matched_offers=len(pairs), common_decided=len(decided), candidate_wins=cw,
        control_wins=rw, win_difference=cw-rw,
        rate_difference=(cw-rw)/len(decided) if decided else None,
        disagreements=sum(x['selected_side'] != y['selected_side'] for x, y in decided),
        candidate_only_wins=sum(x['status'] == 'WIN' and y['status'] == 'LOSS' for x, y in decided),
        control_only_wins=sum(x['status'] == 'LOSS' and y['status'] == 'WIN' for x, y in decided),
        uncertainty=interval,
        common_mask_candidate=_summary([x for x, _ in pairs]),
        common_mask_control=_summary([y for _, y in pairs]))


def _numeric(rows):
    result = {}
    for field in ['mean', 'median']:
        known = [r for r in rows if _finite(r.get(field)) and _finite(r.get('actual'))]
        errors = np.asarray([r[field] - r['actual'] for r in known], dtype=float)
        result[field] = dict(eligible=len(rows), available=sum(_finite(r.get(field)) for r in rows),
            known=len(known), unknown=sum(_finite(r.get(field)) and not _finite(r.get('actual'))
                                         for r in rows),
            MAE=float(np.mean(abs(errors))) if len(errors) else None,
            MSE=float(np.mean(errors**2)) if len(errors) else None,
            bias=float(np.mean(errors)) if len(errors) else None,
            absolute_error_p90=float(np.quantile(abs(errors), .9)) if len(errors) else None,
            absolute_error_p95=float(np.quantile(abs(errors), .95)) if len(errors) else None,
            games=len({r['game_id'] for r in known}),
            unique_players=len({r['player_id'] for r in known}),
            weeks=sorted({r['week'] for r in known}))
    return result


def _baseline_arm(arms):
    for a in ['M3-0', 'M3_0', 'M30', 'LEAF']:
        if a in arms:
            return a
    return None


def _constant_arm(arm):
    """Resolve the engine's explicit constant aliases without changing sides."""
    return arm in {'ALWAYS_OVER', 'ALWAYS_UNDER',
                   'CONTROL_ALWAYS_OVER', 'CONTROL_ALWAYS_UNDER'}


def _constant_key(key):
    return _constant_arm(key[1]) and key[2] in {'LAW', 'DIRECTION', 'CONSTANT'}


def _pair_controls(key, keys, baseline):
    """Declared contrasts and retained references, all with typed outputs."""
    category, arm, product = key
    controls = defaultdict(list)

    def add(control_arm, control_product, reason):
        control = (category, control_arm, control_product)
        if control in keys and control != key:
            controls[control].append(reason)

    if baseline and arm != baseline:
        add(baseline, product, 'UNCHANGED_BASELINE_SAME_OUTPUT')
    if arm == 'M3-0+BLOCK':
        add('M3-0', product, 'INFORMATION_EFFECT_WITHIN_LEAF')
    if arm == 'M3-2':
        add('M3-1', product, 'INFORMATION_EFFECT_WITHIN_BOOSTER')
        add('M3-0+BLOCK', product, 'SAME_INFORMATION_LAW_FAMILY_EFFECT')
    if arm == 'M3-1':
        add('M3-0', product, 'SAME_INFORMATION_LAW_FAMILY_EFFECT')
    add('SANITY', product, 'EARLIER_FIT_SANITY_REFERENCE_SAME_OUTPUT')
    add('CONTROL_P3_DIRECT', 'LAW', 'STRONG_RETAINED_DIRECT_REFERENCE')
    if product in {'MEAN', 'MEDIAN'}:
        add('CONTROL_P1_' + product, product, 'RETAINED_POINT_REFERENCE_SAME_OUTPUT')
    for other in keys:
        if _constant_key(other) and other != key:
            controls[other].append('CONSTANT_SIDE_REFERENCE')
    return controls


def _selected_control_keys(category, groups, baseline):
    """References evaluated on the candidate's exact selected opportunities."""
    law_references = {baseline, 'M3-0+BLOCK', 'M3-1', 'SANITY', 'CONTROL_P3_DIRECT'}
    return [key for key in sorted(groups) if key[0] == category and
            (_constant_key(key) or (key[1] in law_references and key[2] == 'LAW'))]


def summarize(offer_rows, prediction_rows, out):
    """Freeze broad, paired, selective and numerical views of provided rows.

    ``offer_rows`` is one row per (category,arm,product,player/game/target).
    ``prediction_rows`` is one row per (category,arm,player/game) with typed
    mean/median, actual and the same identity/week fields.  This function never
    supplies a missing forecast, outcome, quote, probability or calibration.
    """
    out = Path(out)
    offer_rows = [dict(r, category=_category(r)) for r in offer_rows]
    prediction_rows = [dict(r, category=_category(r)) for r in prediction_rows]
    if any(r['category'] not in ['rec', 'rec_yd'] for r in offer_rows + prediction_rows):
        raise AssertionError('M3_TARGET_SCOPE')
    seen = set()
    groups = defaultdict(list)
    for row in offer_rows:
        ident = (*_key(row), *_method(row))
        if ident in seen:
            raise AssertionError('M3_DUPLICATED_PRIMARY_PLAYER_GAME_TARGET')
        seen.add(ident)
        if row.get('selected_side') is None and row['status'] != 'UNAVAILABLE_FORECAST':
            raise AssertionError('M3_UNAVAILABLE_NOT_ABSTENTION')
        if common.status(row) != row['status']:
            raise AssertionError('M3_COMMON_GRADER_MISMATCH')
        _probs(row)
        groups[(row['category'], *_method(row))].append(row)
    categories = sorted({r['category'] for r in offer_rows})
    result = []
    for (category, arm, product), rows in sorted(groups.items()):
        weeks = sorted({r['week'] for r in rows})
        for week in ['ALL', *REQUESTED_WEEKS]:
            rr = rows if week == 'ALL' else [r for r in rows if r['week'] == week]
            result.append(dict(category=category, arm=arm, product=product, week=week,
                coverage_status='PARTIAL_NATIVE_ACTUAL_LINES' if weeks != REQUESTED_WEEKS else
                                'W1W9_NAMED_PANEL;WITHIN_WEEK_COVERAGE_SEPARATE',
                requested_weeks=REQUESTED_WEEKS,
                missing_real_offer_weeks=sorted(set(REQUESTED_WEEKS)-set(weeks)),
                evidence_tier='TIMING_UNVERIFIED_ACTUAL_LINE_DIAGNOSTIC',
                research_exposure='PREVIOUSLY_INSPECTED_DEVELOPMENT',
                **_summary(rr, weeks if week == 'ALL' else ([week] if rr else []))))

    pairs = []
    for category in categories:
        keys = sorted(k for k in groups if k[0] == category)
        baseline = _baseline_arm({k[1] for k in keys})
        for key in keys:
            arm, product = key[1:]
            controls = _pair_controls(key, keys, baseline)
            for control, reasons in controls.items():
                pairs.append(dict(category=category, arm=arm, product=product,
                    control_arm=control[1], control_product=control[2],
                    comparison='SAME_CASE_OWN_SIDE_COMPLETE_PROCEDURES',
                    contrast_reasons=sorted(set(reasons)),
                    **_paired(groups[key], groups[control])))

    selective = []
    memberships = []
    for (category, arm, product), rows in sorted(groups.items()):
        if product != 'LAW' or not any(_probs(r) is not None for r in rows):
            continue
        weeks = sorted({r['week'] for r in rows})
        for side in ['COMBINED', 'OVER', 'UNDER']:
            policies = [('COVERAGE_%d' % int(f*100), 'FRACTION', f) for f in FRACTIONS]
            policies += [('TOP_%d' % k, 'TOPK', k) for k in TOP_K]
            policies += [('RAW_P_%d' % int(q*100), 'THRESHOLD', q) for q in RAW_THRESHOLDS]
            for policy, kind, parameter in policies:
                selected = []
                eligible_by_week = {}
                for week in weeks:
                    weekly = [r for r in rows if r['week'] == week]
                    eligible_by_week[str(week)] = len(weekly)
                    pool = [r for r in weekly if _confidence(r) is not None and
                            (side == 'COMBINED' or r['selected_side'] == side)]
                    pool.sort(key=lambda r: (-_confidence(r), r['game_id'], r['player_id'], r['offer_id']))
                    if kind == 'THRESHOLD':
                        pick = [r for r in pool if _confidence(r) >= parameter]
                    else:
                        n = int(math.ceil(parameter*len(weekly))) if kind == 'FRACTION' else int(parameter)
                        pick = pool[:min(n, len(pool))]
                    selected.extend(pick)
                ids = {_key(r) for r in selected}
                controls = []
                baseline = _baseline_arm({k[1] for k in groups if k[0] == category})
                for control_key in _selected_control_keys(category, groups, baseline):
                    control_rows = [r for r in groups[control_key] if _key(r) in ids]
                    controls.append(dict(arm=control_key[1], product=control_key[2],
                        comparison='CANDIDATE_SELECTED_CASES_CONTROL_OWN_SIDES',
                        **_paired(selected, control_rows)))
                s = _summary(selected, weeks)
                s['eligible'] = len(rows)
                s['coverage'] = len(selected)/len(rows) if rows else None
                weekly_results = []
                for w in weeks:
                    weekly_board = [r for r in rows if r['week'] == w]
                    weekly_selected = [r for r in selected if r['week'] == w]
                    weekly_summary = _summary(weekly_selected, [w])
                    weekly_summary['eligible'] = len(weekly_board)
                    weekly_summary['coverage'] = (len(weekly_selected)/len(weekly_board)
                                                   if weekly_board else None)
                    weekly_results.append(dict(week=w,
                        forecast_unavailable_on_board=sum(r['selected_side'] is None
                                                          for r in weekly_board),
                        intentional_abstentions_on_board=sum(r['selected_side'] == 'ABSTAIN'
                                                             for r in weekly_board),
                        board_status_counts=dict(Counter(r['status'] for r in weekly_board)),
                        **weekly_summary))
                    memberships.append(dict(category=category, arm=arm, product=product,
                        side_scope=side, policy=policy, week=w,
                        eligible_board=eligible_by_week[str(w)],
                        selected_offer_ids=[r['offer_id'] for r in selected if r['week'] == w],
                        selected_sides=[r['selected_side'] for r in selected if r['week'] == w]))
                selective.append(dict(category=category, arm=arm, product=product, side_scope=side,
                    policy=policy, calibration='RAW_UNCALIBRATED_PROBABILITY',
                    requested_weeks=REQUESTED_WEEKS,
                    missing_real_offer_weeks=sorted(set(REQUESTED_WEEKS)-set(weeks)),
                    decision_batch='RETROSPECTIVE_FULL_WEEK;NOT_AUTHENTICATED_PREGAME_LIST',
                    ranking='Own-side P(correct|notpush) descending; game/player/offer lexical ties',
                    controls_same_selected_cases=controls, weekly_results=weekly_results, **s))
            selective.append(dict(category=category, arm=arm, product=product, side_scope=side,
                policy='CALIBRATED_P75_P80_P90', status='BLOCKED',
                dependency='No earlier qualified actual-offer calibration panel supplied; '
                           'do not calibrate or select thresholds on exposed target weeks.',
                eligible=len(rows), selected=None, accuracy=None))

    pred_groups = defaultdict(list)
    pred_seen = set()
    for r in prediction_rows:
        ident = (*_key(r), r['arm'])
        if ident in pred_seen:
            raise AssertionError('M3_DUPLICATED_NUMERICAL_QUERY')
        pred_seen.add(ident)
        pred_groups[(r['category'], r['arm'])].append(r)
    numerical = []
    for (category, arm), rows in sorted(pred_groups.items()):
        offered = {}
        for (c, a, _), rr in groups.items():
            if c == category and a == arm:
                for r in rr:
                    old = offered.get(_key(r))
                    if old is not None:
                        for field in ['mean', 'median', 'actual']:
                            if old.get(field) != r.get(field):
                                raise AssertionError('M3_TYPED_NUMERICAL_VIEW_MISMATCH')
                    offered[_key(r)] = r
        for week in ['ALL', *REQUESTED_WEEKS]:
            rr = rows if week == 'ALL' else [r for r in rows if r['week'] == week]
            oo = list(offered.values()) if week == 'ALL' else [r for r in offered.values() if r['week'] == week]
            numerical.append(dict(category=category, arm=arm, week=week,
                broad_query_universe='STAT_ROW_CONDITIONED_PLUS_NATIVE_OFFER_ADDITIONS;NOT_PREGAME_ROSTER',
                broad=_numeric(rr), identical_offered_player_rows=_numeric(oo)))

    meta = dict(schema=SCHEMA, origin_session='C', requested_season=2026,
        requested_weeks=REQUESTED_WEEKS,
        common_grader='src/abc_championship_v2.py:status/summary',
        raw_probability_quality='Half-multiclass O/U/push Brier and full event NLL; no point-to-confidence inference',
        calibration='NO_TARGET_WEEK_FITTING;CALIBRATED_THRESHOLD_CELLS_BLOCKED',
        retrospective_exposure=True, production_activation=False,
        repeated_book_views='Excluded from primary unique-selection denominator; retained by input adapter')
    files = [
        _write(out/'RESULTS.json.gz', dict(meta, rows=result)),
        _write(out/'SELECTIVE.json.gz', dict(meta, rows=selective)),
        _write(out/'PAIRS.json.gz', dict(meta, rows=pairs)),
        _write(out/'NUMERICAL.json.gz', dict(meta, rows=numerical)),
        _write(out/'SELECTED_MEMBERSHIP.json.gz', dict(meta, rows=memberships)),
    ]
    return dict(schema=SCHEMA, files=files, broad_views=len(result),
                selective_views=len(selective), paired_views=len(pairs), numerical_views=len(numerical),
                new_fits=0, source_requests=0, private_row_parity_claim=False)


def fixtures():
    """Tiny non-NFL arithmetic fixture, never included in an NFL report."""
    base = dict(category='rec', arm='M3-0', product='LAW', season=2026,
                week=2, appearance='PLAYED', comparator='STRICT_OVER_UNDER',
                fallback=False, learned=True, line=3.5, mean=4., median=4.,
                probabilities=dict(under=.2, push=0., over=.8))
    rows = []
    for i, y in enumerate([4, 2]):
        r = base | dict(game_id='FIXTURE_GAME_%d' % i, player_id='FIXTURE_PLAYER_%d' % i,
                        offer_id='FIXTURE_%d' % i, actual=y, selected_side='OVER',
                        status='WIN' if y == 4 else 'LOSS')
        rows.append(r)
    s = _summary(rows, [2, 3])
    assert s['COMBINED']['wins'] == 1 and s['COMBINED']['losses'] == 1
    assert s['zero_selection_weeks'] == [3]
    assert s['target_status']['0.9']['observed_target_met'] is False
    assert abs(s['probability_quality']['Brier_half_multiclass'] - .34) < 1e-12
    p = _paired(rows, rows)
    assert p['win_difference'] == 0 and p['disagreements'] == 0
    assert p['uncertainty']['low'] == p['uncertainty']['high'] == 0
    assert _summary([], [2, 3])['COMBINED']['rate'] is None
    return dict(status='PASS', scope='NON_NFL_ARITHMETIC_ONLY', new_fits=0)


def repair_regression_fixtures(before_source=None):
    """Independent expected arithmetic for reporting-only repair, outside NFL.

    Fixture identities, outcomes and sides are hand declared.  The known
    selected-list delta is +1 versus the baseline/Under control, and zero versus
    Always-Over.  No fit, NFL row or published result is consumed or changed.
    """
    import tempfile
    base = dict(category='rec', season=2026, week=2, appearance='PLAYED',
                comparator='STRICT_OVER_UNDER', fallback=False, learned=True,
                line=3.5)
    sides = {
        'M3-0': ['UNDER', 'UNDER'],
        'M3-1': ['OVER', 'OVER'],
        'M3-0+BLOCK': ['OVER', 'UNDER'],
        'M3-2': ['OVER', 'OVER'],
        'SANITY': ['UNDER', 'UNDER'],
        'CONTROL_P3_DIRECT': ['UNDER', 'UNDER'],
        'CONTROL_ALWAYS_OVER': ['OVER', 'OVER'],
        'CONTROL_ALWAYS_UNDER': ['UNDER', 'UNDER'],
    }
    rows, predictions = [], []
    for arm, decisions in sides.items():
        products = (['CONSTANT'] if _constant_arm(arm) else
                    ['LAW'] if arm == 'CONTROL_P3_DIRECT' else ['LAW', 'MEAN', 'MEDIAN'])
        for i, (actual, side) in enumerate(zip([4, 2], decisions)):
            correct = (actual > 3.5) == (side == 'OVER')
            confidence = [.9, .6][i] if side == 'OVER' else [.8, .7][i]
            p = ({'over': confidence if side == 'OVER' else 1-confidence,
                  'under': confidence if side == 'UNDER' else 1-confidence, 'push': 0.}
                 if not _constant_arm(arm) else None)
            row = dict(base, arm=arm, game_id='FIXTURE_GAME_%d' % i,
                player_id='FIXTURE_PLAYER_%d' % i, offer_id='FIXTURE_OFFER_%d' % i,
                actual=actual, selected_side=side, status='WIN' if correct else 'LOSS',
                probabilities=p, mean=4. if side == 'OVER' else 3.,
                median=4. if side == 'OVER' else 3.)
            rows.extend(dict(row, product=product) for product in products)
            if not arm.startswith('CONTROL_'):
                # Deliberate missing stat-row label: the qualified offer labels
                # must still support offered-player numerical measurement.
                predictions.append({k: row[k] for k in ['category', 'arm', 'season', 'week',
                    'game_id', 'player_id', 'mean', 'median']} |
                    dict(actual=None, query_only=True))
    def read(p):
        return json.loads(gzip.decompress(Path(p).read_bytes()))
    with tempfile.TemporaryDirectory(prefix='m3-score-repair-fixture-') as directory:
        directory = Path(directory)
        summarize(rows, predictions, directory/'after')
        selective = read(directory/'after/SELECTIVE.json.gz')['rows']
        q = next(r for r in selective if r['arm'] == 'M3-2' and
                 r['side_scope'] == 'COMBINED' and r['policy'] == 'COVERAGE_50')
        assert q['COMBINED']['selected'] == q['COMBINED']['decided'] == 1
        assert q['COMBINED']['wins'] == 1
        controls = {r['arm']: r for r in q['controls_same_selected_cases']}
        assert controls['M3-0']['matched_offers'] == 1
        assert controls['M3-0']['candidate_wins'] == 1
        assert controls['M3-0']['control_wins'] == 0
        assert controls['M3-0']['win_difference'] == 1
        assert controls['CONTROL_ALWAYS_UNDER']['win_difference'] == 1
        assert controls['CONTROL_ALWAYS_OVER']['win_difference'] == 0
        assert controls['CONTROL_ALWAYS_OVER']['matched_offers'] == 1
        assert controls['CONTROL_P3_DIRECT']['matched_offers'] == 1
        assert controls['SANITY']['matched_offers'] == 1
        weekly = q['weekly_results']
        assert len(weekly) == 1 and weekly[0]['week'] == 2
        assert weekly[0]['eligible'] == 2 and weekly[0]['coverage'] == .5
        assert weekly[0]['COMBINED']['wins'] == 1
        empty = next(r for r in selective if r['arm'] == 'M3-0' and
                     r['side_scope'] == 'OVER' and r['policy'] == 'COVERAGE_100')
        assert empty['weekly_results'][0]['COMBINED']['selected'] == 0
        assert empty['weekly_results'][0]['COMBINED']['rate'] is None
        assert empty['weekly_results'][0]['eligible'] == 2
        paired = read(directory/'after/PAIRS.json.gz')['rows']
        edges = {(r['arm'], r['product'], r['control_arm'], r['control_product']): r
                 for r in paired}
        for product in ['LAW', 'MEAN', 'MEDIAN']:
            assert edges[('M3-2', product, 'M3-1', product)]['win_difference'] == 0
            assert edges[('M3-0+BLOCK', product, 'M3-0', product)]['win_difference'] == 1
            assert edges[('M3-2', product, 'M3-0+BLOCK', product)]['win_difference'] == -1
            assert ('M3-2', product, 'SANITY', product) in edges
            assert ('M3-2', product, 'CONTROL_P3_DIRECT', 'LAW') in edges
        numeric = read(directory/'after/NUMERICAL.json.gz')['rows']
        numeric = next(r for r in numeric if r['arm'] == 'M3-2' and r['week'] == 'ALL')
        assert numeric['broad']['mean']['known'] == 0
        assert numeric['identical_offered_player_rows']['mean']['known'] == 2
        assert numeric['identical_offered_player_rows']['mean']['MAE'] == 1.
        before_checked = False
        if before_source is not None:
            expected = '4c2ca3f8cd6176ec47ae8eebd0e82cc51e2dea5ee325aa6ea1193d1aea6e8a9a'
            assert hashlib.sha256(before_source.encode()).hexdigest() == expected
            namespace = {'__name__': 'm3_before_repair_synthetic_only'}
            exec(compile(before_source, '<hash_verified_m3_before_source>', 'exec'), namespace)
            namespace['summarize'](rows, predictions, directory/'before')
            for file in ['RESULTS.json.gz', 'SELECTED_MEMBERSHIP.json.gz', 'NUMERICAL.json.gz']:
                assert read(directory/'before'/file)['rows'] == read(directory/'after'/file)['rows'], file
            old_selected = read(directory/'before/SELECTIVE.json.gz')['rows']
            old_q = next(r for r in old_selected if r['arm'] == 'M3-2' and
                         r['side_scope'] == 'COMBINED' and r['policy'] == 'COVERAGE_50')
            assert all(r['matched_offers'] == 0 for r in old_q['controls_same_selected_cases'])
            assert not any(_constant_arm(r['arm']) for r in old_q['controls_same_selected_cases'])
            old_pairs = read(directory/'before/PAIRS.json.gz')['rows']
            assert not any(r['arm'] == 'M3-2' and r['control_arm'] == 'M3-1' for r in old_pairs)
            before_checked = True
    return dict(status='PASS', scope='HAND_DECLARED_NON_NFL_REPORTING_REGRESSION',
        no_NFL_scoring=True, no_fits=True,
        selected_candidate_decided=1, expected_selected_control_matches=1,
        expected_delta_vs_baseline=1, expected_delta_vs_always_under=1,
        expected_delta_vs_always_over=0,
        declared_same_output_contrasts=['M3-2 minus M3-1', 'M3-0+BLOCK minus M3-0',
                                        'M3-2 minus M3-0+BLOCK'],
        offered_numeric_uses_qualified_offer_actuals=True,
        native_query_null_does_not_erase_qualified_offer_actual=True,
        weekly_zero_selection_explicit_NA=True,
        before_after_broad_result_rows_identical=before_checked,
        before_after_selected_membership_identical=before_checked,
        before_after_numerical_result_rows_identical=before_checked,
        before_source_reproduces_empty_selected_controls=before_checked)
