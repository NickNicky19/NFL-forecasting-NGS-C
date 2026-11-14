"""Independent public-summary arithmetic; no private-row, source-clock or fit parity."""
import gzip
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    with gzip.open(ROOT / 'FTN_COMPLETION_W1_W4_RESULTS_PERMITTED_PROJECTION.json.gz', 'rt') as handle:
        data = json.load(handle)
    for row in data['summaries']:
        for side in ('OVER', 'UNDER', 'COMBINED'):
            value = row[side]
            wins, losses, decided = value['wins'] or 0, value['losses'] or 0, value['decided']
            assert wins + losses == decided
            assert value['rate'] is None if decided == 0 else math.isclose(value['rate'], wins / decided, abs_tol=1e-12)
        for field in ('wins', 'losses', 'decided', 'selected'):
            assert sum(row[side][field] or 0 for side in ('OVER', 'UNDER')) == (row['COMBINED'][field] or 0)
        if row['week_view'] != 'ALL':
            continue
        weeks = [item for item in data['summaries'] if item['candidate_id'] == row['candidate_id'] and item['view'] == row['view'] and item['week_view'] != 'ALL']
        for side in ('OVER', 'UNDER', 'COMBINED'):
            for field in ('wins', 'losses', 'decided', 'selected'):
                assert sum(item[side][field] or 0 for item in weeks) == (row[side][field] or 0)
        for field in ('eligible', 'unavailable', 'abstentions', 'games', 'player_games'):
            assert sum(item[field] for item in weeks) == row[field]
        count = row['numerical']['scored']
        if count:
            for metric in ('MAE', 'MSE', 'bias'):
                weighted = sum(item['numerical'][metric] * item['numerical']['scored'] for item in weeks if item['numerical']['scored']) / count
                assert math.isclose(weighted, row['numerical'][metric], abs_tol=1e-12)
        events = row['probability']['events']
        if events:
            weighted = sum(item['probability']['Brier'] * item['probability']['events'] for item in weeks if item['probability']['events']) / events
            assert math.isclose(weighted, row['probability']['Brier'], abs_tol=1e-12)
    for pair in data['paired']:
        if pair['common_decided']:
            assert math.isclose(pair['accuracy_change'], (pair['left_wins'] - pair['right_wins']) / pair['common_decided'], abs_tol=1e-12)
        assert abs((pair.get('left_wins') or 0) - (pair.get('right_wins') or 0)) <= pair['side_disagreements']
    print(json.dumps({'status': 'PASS_PUBLIC_AGGREGATE_ARITHMETIC', 'triads': len(data['summaries']), 'paired_contrasts': len(data['paired']), 'fits': 0}))


if __name__ == '__main__':
    main()
