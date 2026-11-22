"""SIM comparison view over the retained common grader; no work on import.

Canonical case/outcome records remain private.  This module is a reporting and
matched-mask adapter, not another outcome source, grader or championship.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from decimal import Decimal
import math

import numpy as np

from contracts_v2 import grade
from abc_championship_v2 import summary as common_summary

SEED = 661107
BOOTSTRAP_DRAWS = 2000
FRACTIONS = (0.50, 0.25, 0.10)


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _probabilities(value):
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != {'under', 'push', 'over'}:
        raise ValueError('PROBABILITY_EVENT_ORIENTATION')
    p = [value[x] for x in ('under', 'push', 'over')]
    if (not all(_finite(x) and x >= 0 for x in p)
            or abs(sum(p)-1.) > 1e-12):
        raise ValueError('INVALID_RETAINED_PROBABILITIES;NO_CLIPPING')
    return dict(zip(('under', 'push', 'over'), map(float, p)))


def build_raw_grades(cases, outcomes, predictions):
    """Return one private row per method/applicable full-frame case.

    No absent statistic becomes zero.  Known statistics reuse the website's
    inherited eligibility gate; this is not a fresh participation audit.
    """
    case_map = {r['case_id']: r for r in cases}
    outcome_map = {r['case_id']: r for r in outcomes}
    if len(case_map) != len(cases) or len(outcome_map) != len(outcomes):
        raise ValueError('DUPLICATE_CANONICAL_CASE_OR_OUTCOME')
    if set(case_map) != set(outcome_map):
        raise ValueError('FULL_FRAME_OUTCOME_MEMBERSHIP')
    raw = []
    for method, supplied in predictions.items():
        byid = {r['case_id']: r for r in supplied}
        if len(byid) != len(supplied) or not set(byid) <= set(case_map):
            raise ValueError('DUPLICATE_OR_FOREIGN_FORECAST_CASE')
        categories = {r.get('category', case_map[r['case_id']]['identity']['category'])
                      for r in supplied}
        if not categories:
            categories = {r['identity']['category'] for r in cases}
        for cid, case in case_map.items():
            identity = case['identity']; category = identity['category']
            if category not in categories:
                continue
            pred = byid.get(cid, {})
            if {'actual', 'outcome', 'grade', 'correct'} & set(pred):
                raise ValueError('TARGET_FIELD_IN_FROZEN_PREDICTION')
            if pred.get('category', category) != category:
                raise ValueError('FORECAST_TARGET_MISMATCH')
            y = outcome_map[cid]['actual']
            if y is not None and not _finite(y):
                raise ValueError('INVALID_CANONICAL_ACTUAL')
            available = bool(pred.get('available', False))
            side = pred.get('selected_side') if available else None
            if side not in ('OVER', 'UNDER', 'ABSTAIN', None):
                raise ValueError('UNSUPPORTED_NUMERICAL_OFFER_SIDE')
            point = pred.get('point')
            if point is not None and not _finite(point):
                raise ValueError('NONFINITE_TYPED_POINT')
            probabilities = _probabilities(pred.get('probabilities')) if available else None
            status = ('UNAVAILABLE_FORECAST' if not available else
                      grade(y, identity['line'], side,
                            'PLAYED' if y is not None else 'MISSING_ACTUAL'))
            raw.append(dict(
                case_id=cid, method=method, category=category,
                season=int(identity['season']), week=int(identity['week']),
                game_id=identity['game_id'], player_id=identity['player_id'],
                player_game_key=case['player_game_key'],
                game_origin_key=case['game_origin_key'],
                canonical_case_key=case['canonical_case_key'],
                venue=identity['venue'], line=identity['line'],
                line_classification=case.get('line_classification', 'UNCLASSIFIED'),
                position=identity['position'], actual=y,
                outcome_version=outcome_map[cid]['outcome_version'],
                appearance='PLAYED' if y is not None else 'UNKNOWN',
                appearance_contract='REUSED_CANONICAL_STATISTICAL_ELIGIBILITY_NOT_REAUDITED',
                comparator='STRICT_CROSSING', selected_side=side, status=status,
                available=available, unavailable_reason=pred.get('unavailable_reason'),
                point=point if available else None, probabilities=probabilities,
                native=pred.get('native'), fallback=bool(pred.get('fallback', False)),
                source_binding=pred.get('source_binding'),
                correctness_hold=pred.get('correctness_hold')))
    return raw


def _numeric(rows):
    errors = [r['point']-r['actual'] for r in rows
              if r['available'] and r['point'] is not None and r['actual'] is not None]
    return dict(n=len(errors), MAE=float(np.mean(np.abs(errors))) if errors else None,
                bias=float(np.mean(errors)) if errors else None,
                RMSE=float(np.sqrt(np.mean(np.square(errors)))) if errors else None)


def _probability(rows):
    scores = []; logs = []; zero = 0
    reliability = defaultdict(lambda: [0, 0, 0.])
    for r in rows:
        p = r['probabilities']; y = r['actual']
        if not r['available'] or p is None or y is None:
            continue
        a, line = Decimal(str(y)), Decimal(str(r['line']))
        event = 'under' if a < line else ('over' if a > line else 'push')
        scores.append(.5*sum((p[k]-float(k == event))**2 for k in p))
        if p[event] == 0:
            zero += 1
        else:
            logs.append(-math.log(p[event]))
        if r['status'] in ('WIN', 'LOSS'):
            nonpush = p['under']+p['over']
            confidence = p[r['selected_side'].lower()]/nonpush if nonpush else None
            if confidence is not None:
                # Descriptive reliability bins, never a selection search.
                lower = min(9, int(confidence*10))
                b = reliability[lower]; b[0] += 1
                b[1] += r['status'] == 'WIN'; b[2] += confidence
    n = len(scores)
    return dict(n=n, half_multiclass_Brier=float(np.mean(scores)) if n else None,
                raw_log_loss='Infinity' if zero else (float(np.mean(logs)) if logs else None),
                zero_probability_actual_events=zero,
                calibration='RAW_UNCALIBRATED_UNLESS_ORIGIN_PROCEDURE_EXPLICITLY_CALIBRATED',
                reliability=[dict(lower=k/10, upper=(k+1)/10, decided=v[0],
                                  wins=v[1], stated_mean=v[2]/v[0],
                                  observed_rate=v[1]/v[0])
                             for k, v in sorted(reliability.items())])


def _summarize(rows):
    result = common_summary(rows)
    result.update(available=sum(r['available'] for r in rows),
                  unavailable=sum(not r['available'] for r in rows),
                  unknown_outcomes=sum(r['actual'] is None for r in rows),
                  selected_unknown=sum(r['actual'] is None and r['selected_side'] in ('OVER', 'UNDER') for r in rows),
                  native=sum(r['available'] and r['native'] is True for r in rows),
                  fallback=sum(r['available'] and r['fallback'] for r in rows),
                  attribution_unknown=sum(r['available'] and r['native'] is None and not r['fallback'] for r in rows),
                  pushes=sum(r['status'] == 'PUSH' for r in rows),
                  voids=sum(r['status'] == 'VOID' for r in rows),
                  numerical=_numeric(rows), probability=_probability(rows))
    result['uncertainty']['scope'] = 'DESCRIPTIVE_EXPOSED_HISTORY;LIMITED_CLUSTERS_AND_MULTIPLE_COMPARISONS'
    return result


def _block_interval(pairs, cluster):
    grouped = defaultdict(lambda: [0., 0.])
    for a, b in pairs:
        key = a['game_id'] if cluster == 'game' else (a['season'], a['week'])
        grouped[key][0] += float(a['status'] == 'WIN')-float(b['status'] == 'WIN')
        grouped[key][1] += 1
    if not grouped:
        return dict(kind='N/A_NO_COMMON_DECIDED', clusters=0, low=None, high=None)
    values = np.asarray(list(grouped.values()), dtype=float)
    if len(values) < 2:
        return dict(kind='INCONCLUSIVE_ONE_CLUSTER', clusters=len(values), low=None, high=None)
    rng = np.random.default_rng(SEED)
    draws = values[rng.integers(len(values), size=(BOOTSTRAP_DRAWS, len(values)))].sum(axis=1)
    rates = draws[:, 0]/draws[:, 1]
    lo, hi = np.quantile(rates, [.025, .975])
    return dict(kind=cluster.upper()+'_BLOCK_BOOTSTRAP95_DESCRIPTIVE',
                clusters=len(values), draws=BOOTSTRAP_DRAWS, seed=SEED,
                low=float(lo), high=float(hi), limited_clusters=len(values) < 20,
                multiplicity='UNADJUSTED_EXPOSED_DESCRIPTIVE;NOT_CONFIRMATORY_SUPERIORITY')


def _pair(primary, control):
    byid = {r['case_id']: r for r in control}
    matched = [(r, byid[r['case_id']]) for r in primary if r['case_id'] in byid]
    for a, b in matched:
        if (a['canonical_case_key'], a['outcome_version'], a['actual']) != (
                b['canonical_case_key'], b['outcome_version'], b['actual']):
            raise ValueError('PAIR_CASE_OUTCOME_CONTRACT_MISMATCH')
    dec = [(a, b) for a, b in matched
           if a['status'] in ('WIN', 'LOSS') and b['status'] in ('WIN', 'LOSS')]
    n = len(dec); aw = sum(a['status'] == 'WIN' for a, b in dec)
    bw = sum(b['status'] == 'WIN' for a, b in dec)
    return dict(matched_cases=len(matched), common_decided=n, primary_wins=aw,
                control_wins=bw, win_difference=aw-bw,
                paired_rate_difference=(aw-bw)/n if n else None,
                disagreements=sum(a['selected_side'] != b['selected_side'] for a, b in dec),
                primary_only_wins=sum(a['status'] == 'WIN' and b['status'] == 'LOSS' for a, b in dec),
                control_only_wins=sum(a['status'] == 'LOSS' and b['status'] == 'WIN' for a, b in dec),
                game_uncertainty=_block_interval(dec, 'game'),
                week_sensitivity=_block_interval(dec, 'week'))


def _rank(rows):
    valid = [r for r in rows if r['available'] and r['selected_side'] in ('OVER', 'UNDER')]
    def score(r):
        p = r['probabilities']
        if p is not None:
            return p[r['selected_side'].lower()]/(p['under']+p['over']) if p['under']+p['over'] else -1.
        return abs(r['point']-r['line']) if r['point'] is not None else -1.
    return sorted(valid, key=lambda r: (-score(r), r['case_id']))


def evaluate(cases, outcomes, predictions, *, primary_method='S-P::LAW', raw_grades=None):
    """Aggregate already-frozen forecasts; raw output/lists require private retention.

    The caller may first persist build_raw_grades(...) and pass those same rows
    here, satisfying raw-grade-before-summary order without duplicate grading.
    """
    raw = build_raw_grades(cases, outcomes, predictions) if raw_grades is None else raw_grades
    groups = defaultdict(list)
    for r in raw:
        groups[(r['method'], r['category'])].append(r)
    scores = []
    for (method, category), rows in sorted(groups.items()):
        for week in [None]+sorted({r['week'] for r in rows}):
            rr = rows if week is None else [r for r in rows if r['week'] == week]
            scores.append(dict(method=method, category=category, week='ALL' if week is None else week,
                               **_summarize(rr)))
    paired = []
    for (method, category), rows in sorted(groups.items()):
        if method == primary_method or (primary_method, category) not in groups:
            continue
        for week in [None]+sorted({r['week'] for r in rows}):
            pp = groups[primary_method, category]
            a = pp if week is None else [r for r in pp if r['week'] == week]
            b = rows if week is None else [r for r in rows if r['week'] == week]
            paired.append(dict(primary=primary_method, control=method, category=category,
                               week='ALL' if week is None else week, **_pair(a, b)))
    batches = defaultdict(list)
    for r in raw:
        batches[r['method'], r['category'], r['game_origin_key']].append(r)
    lists = {}; own_selections = []
    for fraction in FRACTIONS:
        for (method, category), rows in sorted(groups.items()):
            selected = []; volumes = []
            for (m, c, origin), batch in sorted(batches.items()):
                if (m, c) != (method, category):
                    continue
                cap = math.floor(fraction*len(batch)); picked = _rank(batch)[:cap]
                lists[fraction, method, category, origin] = picked; selected += picked
                volumes.append(dict(origin=origin, week=batch[0]['week'], eligible=len(batch),
                                    capacity=cap, selected=len(picked),
                                    unknown=sum(r['actual'] is None for r in picked)))
            own_selections.append(dict(method=method, category=category, fraction=fraction,
                policy='CATEGORY_GAME_ORIGIN_CAP_STABLE_CASE_ID',
                ranking='NONPUSH_SIDE_PROBABILITY' if any(r['probabilities'] is not None for r in rows) else 'POINT_GAP_DIAGNOSTIC_NOT_PROBABILITY_OR_TOPPICKS',
                eligible_board=len(rows), achieved_coverage=len(selected)/len(rows) if rows else None,
                own_selected_summary=_summarize(selected),
                case_ids=[r['case_id'] for r in selected], batches=volumes,
                zero_selection_batches=sum(v['selected'] == 0 for v in volumes),
                zero_selection_weeks=sorted(w for w in {r['week'] for r in rows}
                                            if not any(r['week'] == w for r in selected))))
    selection_pairs = []
    for fraction in FRACTIONS:
        for (method, category), rows in sorted(groups.items()):
            if method == primary_method or (primary_method, category) not in groups:
                continue
            primary_own=[]; control_own=[]; primary_selected=[]; control_same=[]
            for (m, c, origin), batch in sorted(batches.items()):
                if (m, c) != (method, category):continue
                a=lists.get((fraction,primary_method,category,origin),[])
                b=lists.get((fraction,method,category,origin),[])
                k=min(len(a),len(b));primary_own+=a[:k];control_own+=b[:k]
                byid={r['case_id']:r for r in batch}
                primary_selected += [r for r in a if r['case_id'] in byid]
                control_same += [byid[r['case_id']] for r in a if r['case_id'] in byid]
            selection_pairs.append(dict(primary=primary_method,control=method,category=category,
                fraction=fraction, matched_capacity_primary_own=_summarize(primary_own),
                matched_capacity_control_own=_summarize(control_own),
                matched_capacity_list_overlap=len({r['case_id'] for r in primary_own}&{r['case_id'] for r in control_own}),
                same_primary_selected_cases=_pair(primary_selected,control_same),
                scope='Own lists test selection; same-selected cases test directions only. No Top Picks/ticket claim.'))
    return dict(schema='SHARED-GAME-SIM01-COMMON-GRADE-VIEW-v1',
        scope='CONDITIONAL_RECONSTRUCTED_EXPOSED_STATISTICAL_COMPARISON;NOT_VENUE_SETTLEMENT',
        primary=primary_method, raw_grades=raw, scores=scores, paired=paired,
        own_selection_policies=own_selections, selection_pairs=selection_pairs,
        raw_and_lists_retention='PRIVATE_CANONICAL_CASES;PUBLIC_AGGREGATE_PROJECTION_REQUIRES_REVIEW',
        numerical_probability_direction_selection='Separate products; no automatic primary admission',
        actual_weeks=sorted({(r['season'],r['week']) for r in raw}),
        full_case_count=len(cases), full_unknown_outcomes=sum(r['actual'] is None for r in outcomes))


def saved_control_pairs(raw_grades, selection_policies):
    """Named companion diagnostics; primary simulator contrast stays unchanged."""
    groups = defaultdict(list)
    for r in raw_grades:groups[r['method'],r['category']].append(r)
    comparisons=[];selected_pairs=[]
    lists={(x['method'],x['category'],x['fraction']):x['case_ids'] for x in selection_policies}
    for (method,category),rows in sorted(groups.items()):
        if not method.startswith('C-') and not method.startswith('C::'):continue
        for control in ('W0','W1','ALWAYS_OVER','ALWAYS_UNDER'):
            reference=groups.get((control,category),[])
            for week in [None]+sorted({r['week'] for r in rows}):
                a=rows if week is None else [r for r in rows if r['week']==week]
                b=reference if week is None else [r for r in reference if r['week']==week]
                comparisons.append(dict(candidate=method,control=control,category=category,week='ALL' if week is None else week,**_pair(a,b)))
            if control not in ('W0','W1'):continue
            ra={r['case_id']:r for r in rows};rb={r['case_id']:r for r in reference}
            for fraction in FRACTIONS:
                own=[ra[k] for k in lists.get((method,category,fraction),[])];ref=[rb[k] for k in lists.get((control,category,fraction),[])]
                aa=[];bb=[]
                for origin in sorted({r['game_origin_key'] for r in rows}):
                    a=[r for r in own if r['game_origin_key']==origin];b=[r for r in ref if r['game_origin_key']==origin];n=min(len(a),len(b));aa+=a[:n];bb+=b[:n]
                selected_pairs.append(dict(candidate=method,control=control,category=category,fraction=fraction,candidate_own_matched_capacity=_summarize(aa),control_own_matched_capacity=_summarize(bb),same_candidate_selected_directions=_pair(own,[rb[r['case_id']] for r in own]),scope='Companion diagnostic; own lists versus same-selected cases are distinct; point-gap lists not probability or TopPicks'))
    return dict(paired=comparisons,selection_pairs=selected_pairs)
