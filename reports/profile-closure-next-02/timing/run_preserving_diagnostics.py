"""Version derivative preparation receipts before an authorized C04 year run.

The original timing/model driver remains frozen at its pilot SHA. This wrapper
adds no fit and uses the very same preparation already needed by that run.
"""
import argparse
import gzip
import hashlib
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'src'))
import receiving_timing_c04 as d

# The pilot passed this route explicitly. Preserve the frozen scientific driver
# and repair only this supported operational entry point.
REGISTRATION = ROOT / 'protocol/PROFILE_CLOSURE_NEXT_02_C.json'


def preserve_receipts(year):
    records = []
    for name in ['DIAGNOSIS.json', 'INPUT_BINDINGS.json', 'SEVEN_DAY_REUSE_PARITY.json', 'FEATURE_ORDER.json', 'FIT_LEDGER.json', 'PILOT.json']:
        source = d.OUT / name
        if not source.exists():
            continue
        body = source.read_bytes()
        digest = hashlib.sha256(body).hexdigest()
        target = d.OUT / 'snapshots' / (name + '.' + digest[:16] + '.gz')
        target.parent.mkdir(exist_ok=True)
        packed = gzip.compress(body, mtime=0)
        if target.exists():
            assert target.read_bytes() == packed
        else:
            target.write_bytes(packed)
        records.append(dict(path=str(source.relative_to(ROOT)), SHA256=digest, snapshot=str(target.relative_to(ROOT))))
    d.write(d.OUT / f'PRE-RUN-{year}-RECEIPTS.json', dict(created_UTC=d.now(), year=year, retained=records))


def aligned_membership(data):
    pool, games, p7, p1, matrix7, matrix1, names, bindings, proof = data
    result = []
    for year in [2025, 2026]:
        for week in range(1, 9):
            cutoff = float(games.loc[(games.season == year) & (games.week == week), 'kickoff'].min())
            a = {i for i, r in enumerate(p7.pool) if r['available'] < cutoff and r['values']['rec'] is not None}
            b = {i for i, r in enumerate(p1.pool) if r['available'] < cutoff and r['values']['rec'] is not None}
            assert a <= b
            common = sorted(a & b)
            query = [i for i, r in enumerate(pool) if r['season'] == year and r['week'] == week]
            row = dict(season=year, week=week, original_training_rows=len(a), alternative_training_rows=len(b), additionally_admitted_labels=len(b-a), query_rows=len(query))
            for old, new in [('F0', 'F2'), ('F1', 'F3')]:
                left, right = matrix7[old], matrix1[new]
                def changed(indices):
                    return int((~np.all((left[indices] == right[indices]) | (np.isnan(left[indices]) & np.isnan(right[indices])), axis=1)).sum())
                row[new + '_common_training_feature_rows_changed'] = changed(common)
                row[new + '_query_feature_rows_changed'] = changed(query)
            result.append(row)
    d.write(d.OUT / 'ALIGNED_ORIGIN_CONTRACT_CHANGES.json', dict(
        created_UTC=d.now(), rows=result,
        interpretation='Same algorithm and declared policies; information changes may affect admitted training labels, historical training features and query features. A first-week query with unchanged own history can still change because its fitted training features change.',
        observation_clocks_authenticated=False, new_fits=0,
    ))


def main(year, registration):
    preserve_receipts(year)
    original = d.prepare
    def observed_prepare():
        data = original()
        aligned_membership(data)
        return data
    d.prepare = observed_prepare
    d.run(year=year, registration=registration)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--year', type=int, choices=[2025, 2026], required=True)
    parser.add_argument('--registration', type=Path, default=REGISTRATION)
    args = parser.parse_args()
    main(args.year, args.registration)
