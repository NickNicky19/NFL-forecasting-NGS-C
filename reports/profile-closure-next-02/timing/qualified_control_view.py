"""Append-only, zero-fit strong-control views for C04 numerical results.

Recover R0's exact saved typed points/support from the already qualified C03
view. Do not alter forecasts, source rows, actual-line directions or grades.
"""
import argparse
import collections
import importlib.util
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'src'))
import receiving_timing_c04 as d

OLD_VIEW = ROOT / 'reports/profile-increment-v2/experiment/qualified_metric_view.py'
spec = importlib.util.spec_from_file_location('c03_qualified_control_view', OLD_VIEW)
old_view = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old_view)


def identity(row):
    return row['game_id'], row['player_id']


def attach_broad(rows, year):
    prior = {identity(r): r for r in old_view.numerical_rows(year)}
    assert len(prior) == len(rows)
    out = []
    for row in rows:
        old = prior[identity(row)]
        assert all(row[k] == old[k] for k in ['position', 'season', 'week', 'actual', 'cohort'])
        out.append(dict(row, CONTROL_LEAF=old.get('R0')))
    return out


def attach_offered(rows):
    old_rows = old_view.offered_numeric_rows()
    prior = {identity(r): r for r in old_rows}
    # One frozen primary quote per player/game; never collapse alternate offers.
    assert len(prior) == len(old_rows)
    by_offer = collections.defaultdict(dict)
    for r in rows:
        if r['method'].endswith('_LAW'):
            assert r['method'] not in by_offer[r['offer_id']]
            by_offer[r['offer_id']][r['method']] = r
    out = []
    for offered in by_offer.values():
        source = offered['F0_LAW']
        old = prior[identity(source)]
        assert all(source[k] == old[k] for k in ['position', 'week', 'actual', 'cohort'])
        r = {k: source[k] for k in ['game_id', 'player_id', 'position', 'week', 'actual', 'cohort']}
        r['season'] = 2026
        for arm in ['F0', 'F1', 'F2', 'F3']:
            x = offered[arm + '_LAW']
            assert all(x[k] == source[k] for k in ['game_id', 'player_id', 'line', 'actual', 'appearance'])
            r[arm] = {k: x[k] for k in ['mean', 'median', 'hard_fallback', 'any_imputed', 'profile_covered']}
        r['CONTROL_LEAF'] = old.get('R0')
        for method in ['P1', 'P2']:
            r['CONTROL_CONTEXT_' + method] = old['CONTROL_CONTEXT_' + method]
        out.append(r)
    assert len(out) == len(old_rows)
    return out


def summaries(rows, methods, year, offered=False):
    out = []
    for cohort in ['ALL', 'priority', 'workload_top20']:
        out += d.c03.point_summary(rows, methods, year=year, cohort=cohort, offered=offered)
    for r in out:
        if r['method'].startswith('CONTROL_CONTEXT_'):
            # These old controls have typed points, not an inspected imputation
            # contract. Unknown support must never become apparent zero use.
            r['any_imputed_known'] = None
            r['profile_covered_known'] = None
            r['support_state'] = 'EXACT_RETAINED_POINTS;INPUT_SUPPORT_NOT_RECONSTRUCTED'
    return out


def control_pairs(rows, year, offered=False):
    """Use the existing C04 metric/cluster calculation, with explicit controls.

    This changes only a process-local requested pair list. No scorer, forecast,
    model, fit configuration, or saved driver bytes are changed.
    """
    saved = d.CONTRASTS
    controls = ['CONTROL_LEAF'] + (['CONTROL_CONTEXT_P1', 'CONTROL_CONTEXT_P2'] if offered else [])
    try:
        d.CONTRASTS = [(a, b) for a in ['F0', 'F1', 'F2', 'F3'] for b in controls]
        return d.numeric_pairs(rows, year, offered=offered)
    finally:
        d.CONTRASTS = saved


def main(year):
    source = d.ART / f'NUMERICAL_ROWS-{year}.json.xz'
    rows = attach_broad(d.read(source), year)
    d.write(d.OUT / f'QUALIFIED_NUMERICAL_SCORES-{year}.json.xz', summaries(rows, ['F0', 'F1', 'F2', 'F3', 'CONTROL_LEAF'], year))
    d.write(d.OUT / f'NUMERICAL_STRONG_CONTROL_PAIRED-{year}.json.xz', control_pairs(rows, year))
    bindings = dict(
        id='C04-QUALIFIED-NUMERICAL-CONTROL-VIEW-v1',
        source=dict(path=str(source.relative_to(ROOT)), SHA256=d.sha(source)),
        original_control_view=dict(path=str(OLD_VIEW.relative_to(ROOT)), SHA256=d.sha(OLD_VIEW)),
        view_code_SHA256=d.sha(Path(__file__)),
        control_name='CONTROL_LEAF=C03_R0;exact_safe_saved_points_and_qualified_support',
        new_fits=0, new_inference=0, point_probability_side_grade_changes=0,
        immutable_raw_rows_preserved=True,
    )
    if year == 2026:
        actual = d.ART / 'ACTUAL_OFFER_ROWS.json.xz'
        offered = attach_offered(d.read(actual))
        methods = ['F0', 'F1', 'F2', 'F3', 'CONTROL_LEAF', 'CONTROL_CONTEXT_P1', 'CONTROL_CONTEXT_P2']
        d.write(d.OUT / 'QUALIFIED_OFFERED_NUMERICAL_SCORES.json.xz', summaries(offered, methods, 2026, offered=True))
        d.write(d.OUT / 'OFFERED_STRONG_CONTROL_PAIRED.json.xz', control_pairs(offered, 2026, offered=True))
        bindings['actual_rows'] = dict(path=str(actual.relative_to(ROOT)), SHA256=d.sha(actual))
    d.write(d.OUT / f'QUALIFIED_CONTROL_VIEW-{year}.json', bindings)
    print('C04_QUALIFIED_CONTROL_VIEW', year)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--year', type=int, choices=[2025, 2026], required=True)
    main(parser.parse_args().year)
