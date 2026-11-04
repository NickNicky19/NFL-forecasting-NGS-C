"""Render admitted public aggregate panels; never grade unseen restricted offers."""
import csv
import gzip
import io
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from abc_championship_v2 import ROOT
from contracts_v2 import CATEGORIES

OUT = ROOT / 'reports/abc-championship/continuation-v2'


def read(name):
    data = (OUT / name).read_bytes()
    return json.loads(gzip.decompress(data) if name.endswith('.gz') else data)


def write(name, obj):
    (OUT / name).write_text(json.dumps(obj, indent=2, allow_nan=False) + '\n')


def record(q):
    if not q['decided']:
        return 'N/A — no decided selections'
    return f"{q['wins']}-{q['losses']}/{q['decided']}/{100*q['rate']:.2f}%"


def uncertainty(row):
    """Resample whole weeks, retaining all selected outcomes in that week."""
    weeks = row['week_rows']
    weights = np.random.default_rng(1703).multinomial(7, [1/7]*7, size=500)
    result = {}
    for side in ['over', 'under', 'combined']:
        if side == 'combined':
            wins = np.array([int(w['correct']) for w in weeks])
            decided = np.array([int(w['decided']) for w in weeks])
        else:
            wins = np.array([int(w[side+'_wins']) for w in weeks])
            decided = np.array([int(w[side+'_decided']) for w in weeks])
        den = weights @ decided
        samples = (weights @ wins)[den > 0] / den[den > 0]
        result[side.upper()] = np.quantile(samples, [.025, .975]).tolist() if len(samples) else None
    return dict(procedure_id=row['procedure_id'], intervals=result, clusters=7,
                resamples=500, seed=1703, scope='Whole-week descriptive bootstrap; exposed maxima/multiplicity not adjusted; few clusters; not a future guarantee')


def build():
    a = read('A_W1_W7_ARCHIVED_SCORES.json.gz')
    controls = {x['procedure_id']: x for x in read('A_W1_W7_OWN_MASK_CONSTANT_CONTROLS.json')}
    intervals = {x['procedure_id']: uncertainty(x) for x in a}
    write('A_WEEK_CLUSTER_UNCERTAINTY.json', list(intervals.values()))
    leaders = read('A_W1_W7_RAW_LEADERS.json')
    headline = []
    for category in CATEGORIES:
        matches = [r for r in leaders if r['category'] == category and r['side'] == 'COMBINED']
        if not matches:
            headline.append(dict(category=category, state='NOT_ESTABLISHED', reason='No qualified actual offer/export for this event/scoring contract', actual_weeks=[], OVER=None, UNDER=None, COMBINED=None))
            continue
        ties = matches[0]['ties']
        row = next(x for x in a if x['procedure_id'] == ties[0]['procedure_id'])
        z = {k: v for k, v in row.items() if k != 'week_rows'}
        z['tied_complete_procedures'] = [r['procedure_id'] for r in ties]
        z['matched_control'] = controls[row['procedure_id']]
        z['uncertainty'] = intervals[row['procedure_id']]
        o, u = row['OVER'], row['UNDER']
        z['higher_observed_side'] = ('TIE' if o['rate'] == u['rate'] else 'OVER' if o['rate'] > u['rate'] else 'UNDER') if o['decided'] and u['decided'] else 'NOT_COMPARABLE_EMPTY_SIDE'
        z['side_difference_percentage_points'] = abs(100*(o['rate']-u['rate'])) if o['decided'] and u['decided'] else None
        z['operational_recommendation'] = 'NO_PROMOTION; observed historical procedure, not earlier-selected live winner'
        headline.append(z)
    write('HEADLINE_A_W1_W7.json', headline)
    fields = ['category','procedure_id','method','product','eligible','selected','decided','wins','losses','OVER','UNDER','COMBINED','games','best_constant_wins','difference_wins']
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fields, lineterminator="\n")
    writer.writeheader()
    for x in headline:
        if not x['COMBINED']:
            writer.writerow(dict(category=x['category'], procedure_id=x['reason']))
            continue
        writer.writerow(dict(category=x['category'], procedure_id=x['procedure_id'], method=x['method'], product=x['product'], eligible=x['eligible'], selected=x['selected'], **{k:x['COMBINED'][k] for k in ['decided','wins','losses']}, **{s:record(x[s]) for s in ['OVER','UNDER','COMBINED']}, games=x['games'], best_constant_wins=max(x['matched_control']['always_Over_wins'],x['matched_control']['always_Under_wins']), difference_wins=x['matched_control']['change_vs_best_constant']))
    (OUT/'HEADLINE_A_W1_W7.csv').write_text(buf.getvalue())
    # Per-week raw maxima: preserve every method's selected sample and ties.
    weekly = []
    for week in range(1,8):
        for category in sorted({x['category'] for x in a}):
            for side in ['over','under','combined']:
                candidates = []
                for row in a:
                    if row['category'] != category:
                        continue
                    w = row['week_rows'][week-1]
                    n = int(w['decided'] if side == 'combined' else w[side+'_decided'])
                    wins = int(w['correct'] if side == 'combined' else w[side+'_wins'])
                    if n:
                        candidates.append(dict(procedure_id=row['procedure_id'], wins=wins, losses=n-wins, decided=n, rate=wins/n))
                best = max((r['rate'] for r in candidates), default=None)
                weekly.append(dict(week=week,category=category,side=side.upper(),raw_observed_ties=[r for r in candidates if r['rate']==best], scope='Exposed raw maxima; not chronological selector or supported champion'))
    write('A_WEEKLY_RAW_LEADERS.json', weekly)
    # B maxima stay within source, horizon, population/cohort, history and policy.
    grouped = defaultdict(list)
    for row in read('B_OWNER_LOCAL_SCORES.json.gz'):
        key = tuple(json.dumps(row.get(k),sort_keys=True) for k in ['source','evaluation_weeks','target','history_regime','horizon_id','cohort_id','decision_rule'])
        grouped[key].append(row)
    b_leaders = []
    for key, rows in grouped.items():
        for side in ['OVER','UNDER','COMBINED']:
            valid = [r for r in rows if r[side]['decided']]
            best = max((r[side]['rate'] for r in valid),default=None)
            b_leaders.append(dict(stratum=list(key),side=side,raw_observed_ties=[{k:r[k] for k in ['procedure_id','method_id','strategy','product_id','target','history_regime',side,'eligible','selected','games','membership_SHA256','uncertainty']} for r in valid if r[side]['rate']==best],scope='Owner-local aggregate descriptive only; same counts/horizon do not prove equal masks; no paired superiority or promotion'))
    data=(json.dumps(b_leaders,separators=(',',':'))+'\n').encode()
    (OUT/'B_SOURCE_STRATIFIED_RAW_LEADERS.json.gz').write_bytes(gzip.compress(data,mtime=0))
    print('PERIOD_REPORT_EXECUTED', len(headline), len(weekly), len(b_leaders))


if __name__ == '__main__':
    build()
