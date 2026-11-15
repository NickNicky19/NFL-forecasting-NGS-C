"""Independent event-score/reliability arithmetic for frozen C rows only."""
from collections import defaultdict
from decimal import Decimal
import datetime
import gzip
import json
import math
from pathlib import Path
import time


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'reports/information-skill-01'


def read(path):
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == '.gz' else raw)


def main():
    start = time.process_time()
    rows = read(OUT / 'OFFER_ROWS.json.gz')
    groups = defaultdict(list)
    for row in rows:
        groups[(row['arm'], row['product'])].append(row)
    results = read(OUT / 'scores/RESULTS.json.gz')['rows']
    brier_checks = reliability_checks = 0
    for result in results:
        group = groups[(result['arm'], result['product'])]
        group = group if result['week'] == 'ALL' else [r for r in group if r['week'] == result['week']]
        pairs, log_losses, confidence = [], [], []
        impossible = 0
        for row in group:
            p = row.get('probabilities')
            if p is None or row['appearance'] != 'PLAYED' or row['actual'] is None:
                continue
            assert set(p) == {'over', 'under', 'push'}
            assert all(math.isfinite(v) and v >= 0 for v in p.values())
            assert abs(sum(p.values()) - 1) < 1e-10
            y, line = Decimal(str(row['actual'])), Decimal(str(row['line']))
            truth = 'over' if y > line else 'under' if y < line else 'push'
            pairs.append(.5 * sum((p[s] - (1 if s == truth else 0)) ** 2 for s in p))
            if p[truth] > 0:
                log_losses.append(-math.log(p[truth]))
            else:
                impossible += 1
            side = row['selected_side']
            total = p['over'] + p['under']
            if side in ['OVER', 'UNDER'] and row['status'] in ['WIN', 'LOSS'] and total > 0:
                confidence.append((p[side.lower()] / total, int(row['status'] == 'WIN')))
        actual = result['probability_quality']
        assert actual['probability_scored'] == len(pairs)
        assert actual['infinite_log_loss_count'] == impossible
        brier = sum(pairs) / len(pairs) if pairs else None
        nll = sum(log_losses) / len(log_losses) if log_losses and not impossible else None
        for measured, stored in [(brier, actual['Brier_half_multiclass']), (nll, actual['log_loss'])]:
            assert measured is None and stored is None or measured is not None and stored is not None and abs(measured - stored) < 1e-12
        brier_checks += 1
        for bucket in actual['reliability']:
            sample = [(p, y) for p, y in confidence if p >= bucket['low_inclusive']
                      and (p <= bucket['high'] if bucket['high_inclusive'] else p < bucket['high'])]
            assert bucket['decided'] == len(sample)
            assert bucket['wins'] == sum(y for _, y in sample)
            if sample:
                assert abs(bucket['mean_model_confidence'] - sum(p for p, _ in sample) / len(sample)) < 1e-12
                assert abs(bucket['observed_accuracy'] - sum(y for _, y in sample) / len(sample)) < 1e-12
            else:
                assert bucket['mean_model_confidence'] is None and bucket['observed_accuracy'] is None
            reliability_checks += 1
    receipt = dict(id='C-INFORMATION-SKILL-INDEPENDENT-PROBABILITY-v1', status='PASS',
                   checked_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   full_and_weekly_Brier_logloss_views_checked=brier_checks,
                   fixed_reliability_bins_checked=reliability_checks,
                   tolerance=1e-12, CPU_seconds=time.process_time() - start,
                   new_fits=0, new_original_selections=0, new_scored_NFL_weeks=0,
                   scope='Independent event/probability and fixed-bin arithmetic from frozen C offer rows; not authentication of source clocks, calibration, untouched accuracy or production admission.')
    with (OUT / 'verification/PROBABILITY_INDEPENDENT.json').open('x') as handle:
        json.dump(receipt, handle, indent=2)
        handle.write('\n')
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
