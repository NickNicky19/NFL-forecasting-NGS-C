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


def retain_fixed_independent_fit(data):
    """One prechosen 2025W01 F3 design, not an additional improvement fit.

    Plain JSON arrays with explicit NumPy dtype/shape restore NaNs as NaNs and
    integer/float targets exactly. No executable serialization is accepted.
    """
    pool, games, p7, p1, matrix7, matrix1, names, bindings, proof = data
    year, week, arm = 2025, 1, 'F3'
    cutoff = float(games.loc[(games.season == year) & (games.week == week), 'kickoff'].min())
    train = [i for i, r in enumerate(p1.pool) if r['available'] < cutoff and r['values']['rec'] is not None]
    x = matrix1[arm][train]
    y = np.asarray([pool[i]['values']['rec'] for i in train])
    roles = np.asarray([pool[i]['position'] for i in train])
    members = [(pool[i]['game_id'], pool[i]['player_id']) for i in train]
    query = [i for i, r in enumerate(pool) if r['season'] == year and r['week'] == week]
    sample = []
    for role in ['RB', 'WR', 'TE']:
        i = next(i for i in query if pool[i]['position'] == role)
        sample.append(dict(game_id=pool[i]['game_id'], player_id=pool[i]['player_id'], role=role, features=matrix1[arm][i]))
    dataset = dict(
        id='C04-INDEPENDENT-FRESH-FIT-DESIGN-v1', origin='2025-W01', arm=arm,
        chosen_before_2025_comparative_scores=True,
        choice='Fixed earliest 2025 origin F3; root selected before any 2025 scores',
        created_UTC=d.now(), policy=d.POLICY1,
        core_code_SHA256=d.sha(ROOT / 'src/receiving_timing_c04.py'),
        wrapper_code_SHA256=d.sha(Path(__file__)),
        registration=dict(path=str(d.REG.resolve().relative_to(ROOT)), SHA256=d.sha(d.REG)),
        feature_order=names[arm], input_bindings=bindings,
        fit_cutoff=cutoff, membership=members,
        membership_SHA256=hashlib.sha256(__import__('json').dumps(members, separators=(',', ':')).encode()).hexdigest(),
        fingerprint=d.fingerprint(x, y),
        X=dict(dtype=x.dtype.str, shape=list(x.shape), values=x),
        y=dict(dtype=y.dtype.str, shape=list(y.shape), values=y),
        roles=dict(dtype=roles.dtype.str, shape=list(roles.shape), values=roles),
        query_sample=sample, new_fits=0,
        verification_scope='Exact saved design reproduction; not an independent raw-source reconstruction',
    )
    path = d.ART / 'FIT_REPRODUCTION_DATASET-2025-W01-F3.json.xz'
    assert not path.exists(), 'INDEPENDENT_DESIGN_ALREADY_RETAINED'
    d.write(path, dataset)
    d.write(d.OUT / 'INDEPENDENT_FIT_DESIGN_RECEIPT.json', dict(
        id=dataset['id'], created_UTC=d.now(), path=str(path.relative_to(ROOT)),
        SHA256=d.sha(path), public_bytes=path.stat().st_size,
        fingerprint=dataset['fingerprint'], membership_SHA256=dataset['membership_SHA256'],
        rows=len(train), features=x.shape[1], model_fits=0,
        separate_verifier_fit='Not yet executed; only its prechosen exact design retained',
    ))


def main(year, registration):
    preserve_receipts(year)
    original = d.prepare
    def observed_prepare():
        data = original()
        aligned_membership(data)
        if year == 2025:
            retain_fixed_independent_fit(data)
        return data
    d.prepare = observed_prepare
    d.run(year=year, registration=registration)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--year', type=int, choices=[2025, 2026], required=True)
    parser.add_argument('--registration', type=Path, default=REGISTRATION)
    args = parser.parse_args()
    main(args.year, args.registration)
