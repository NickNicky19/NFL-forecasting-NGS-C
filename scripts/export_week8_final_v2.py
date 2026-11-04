"""Rebuild the expanded CSV from saved grades; no source calls or model refits."""
import csv
import gzip
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'reports/abc-championship/continuation-v2'


def build():
    summary = json.loads((BASE/'C_WEEK8_FINAL_FORECAST_GRADES.json').read_text())
    rows = list(csv.DictReader(gzip.open(ROOT/'reports/week8-v9/GRADED_FORECAST_ROWS.csv.gz','rt')))
    packet = json.loads((ROOT/summary['outcome_packet']).read_text())
    observations = {(r['game_id'],r['player_id'],r['category']):r['observed_UTC'] for r in packet['outcomes']}
    grades = {}
    for artifact in summary['grade_files']:
        grades.update({r['forecast_id']:r for r in json.loads((ROOT/artifact['path']).read_text())['grades']})
    for row in rows:
        grade = grades[row['forecast_id']]
        for key in ['state','actual','absolute_error','median_error','mean_squared_error','CRPS','NLL']:
            row[key] = '' if grade.get(key) is None else str(grade[key])
        row['outcome_observed_UTC'] = observations[(row['game_id'],row['player_id'],row['category'])]
        row['grade_version'] = summary['id']
    stream = io.StringIO()
    writer = csv.DictWriter(stream, list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return gzip.compress(stream.getvalue().encode(),mtime=0)


if __name__ == '__main__':
    assert build() == (BASE/'C_WEEK8_FINAL_GRADED_FORECAST_ROWS.csv.gz').read_bytes()
    print('SAVED_FINAL_CSV_REPRODUCED', 2513)
