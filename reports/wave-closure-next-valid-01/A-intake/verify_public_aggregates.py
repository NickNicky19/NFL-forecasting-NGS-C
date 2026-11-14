"""Recheck permitted aggregate calculations; does not establish raw-row or fit parity."""
import gzip
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load(name):
    with gzip.open(ROOT / name, 'rt') as handle:
        return json.load(handle)


def triad(summary):
    for side in ('OVER', 'UNDER', 'COMBINED'):
        row = summary[side]
        wins, losses, decided = row['wins'] or 0, row['losses'] or 0, row['decided']
        assert wins + losses == decided
        assert row['rate'] is None if not decided else math.isclose(row['rate'], wins / decided, abs_tol=1e-12)
    for field in ('wins', 'losses', 'decided', 'selected'):
        assert sum(summary[side][field] or 0 for side in ('OVER', 'UNDER')) == (summary['COMBINED'][field] or 0)


def main():
    result = load('RUSH2023_HISTORICAL_RESULTS_V1_PERMITTED_PROJECTION.json.gz')
    raw = load('RUSH2023_RAW_F_CONTROL_APPENDIX_V1_PERMITTED_PROJECTION.json.gz')
    checked = 0
    for record in result['records']:
        triad(record['summary'])
        checked += 1
        for week in record.get('weekly', []):
            triad(week['summary'])
            checked += 1
        if record.get('weekly'):
            for side in ('OVER', 'UNDER', 'COMBINED'):
                for field in ('wins', 'losses', 'decided', 'selected'):
                    assert sum(week['summary'][side][field] or 0 for week in record['weekly']) == (record['summary'][side][field] or 0)
    for panel in raw['panels']:
        for field in ('raw_F_own_Top6', 'raw_F_own_full_board'):
            triad(panel[field])
            checked += 1
        candidate = next(record for record in result['records'] if record['period'] == panel['period'] and record['product'] == 'BACKFIELD_CDF_P2_FULL_BOARD')
        assert candidate['summary']['COMBINED']['wins'] - panel['raw_F_own_full_board']['COMBINED']['wins'] == panel['candidate_minus_raw_F_wins']
    normalized = load('NORMALIZED_HISTORICAL_CONTROL_ROWS.json.gz')
    assert len(normalized) == checked == 87
    for row in normalized:
        triad(row)
        assert row['unselected'] >= 0
    assert sum(week['eligible'] for week in result['offer_coverage_before_labels']['by_week']) == 560
    print(json.dumps({'status': 'PASS_PUBLIC_AGGREGATE_ARITHMETIC_ONLY', 'triads': checked, 'NFL_fits': 0}))


if __name__ == '__main__':
    main()
