"""Bounded readback of C's research consumer; no forecast/source refresh."""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen

p = argparse.ArgumentParser()
p.add_argument('--commit', required=True)
args = p.parse_args()
root = Path(__file__).resolve().parents[3]
base = 'https://nicknicky19.github.io/NFL-forecasting-NGS-C/'
paths = ['build.json', 'championship.html', 'championship.js',
         'data/category-decisions-c06.json', 'data/championship-shared-c01.json']
rows, payloads = [], {}
for name in paths:
    with urlopen(Request(base + name + '?verified=' + args.commit,
                         headers={'User-Agent': 'C06-served-consumer-verifier',
                                  'Cache-Control': 'no-cache'}), timeout=30) as response:
        body = response.read(2_097_153)
        assert response.status == 200 and len(body) <= 2_097_152
        headers = {key.lower(): value for key, value in response.headers.items()}
    if name == 'build.json':
        build = json.loads(body)
        assert build['served_commit'] == args.commit
        for field, local_path in [
            ('category_decisions_c06_SHA256', 'data/category-decisions-c06.json'),
            ('championship_shared_C01_SHA256', 'data/championship-shared-c01.json'),
        ]:
            assert build[field] == hashlib.sha256((root / 'docs' / local_path).read_bytes()).hexdigest()
    else:
        assert body == (root / 'docs' / name).read_bytes(), name
    payloads[name] = body
    rows.append({'path': name, 'bytes': len(body), 'SHA256': hashlib.sha256(body).hexdigest(),
                 'HTTP_Date': headers.get('date'), 'HTTP_Age': headers.get('age'),
                 'exact_local_asset_parity': name != 'build.json',
                 'deployment_stamp_and_payload_bindings': name == 'build.json'})
data = json.loads(payloads['data/category-decisions-c06.json'])
packet = data['current_packet']
for category in ['pass_yd', 'rec_yd', 'rush_rec_yd']:
    row = next(r for r in data['categories'] if r['category'] == category)
    assert row['decision'] == 'SHADOW' and row['website_operational_decision'] == 'KEEP_INCUMBENT'
assert b'C research:' in payloads['championship.js'] and b'Original website:' in payloads['championship.js']
assert len(data['categories']) == 12 and len(packet['rows']) == 25
expected = {'pass_yd': (52, 89), 'pass_td': (49, 86), 'pass_cmp': (52, 88),
            'pass_att': (44, 87), 'pass_int': (50, 87), 'rush_yd': (165, 287),
            'rush_att': (146, 260), 'rec': (239, 412), 'rec_yd': (322, 593),
            'rush_rec_yd': (208, 386)}
for row in data['categories']:
    if row['category'] in expected:
        assert (row['COMBINED']['wins'], row['COMBINED']['decided']) == expected[row['category']]
        assert row['actual_weeks_by_season'] == {'2026': [1, 2, 3, 4, 5]}
    else:
        assert row['COMBINED'] is None and row['preferred_eligible_candidate'] is None
assert len({row['player_id'] for row in packet['rows']}) == 25
assert sum(row['direction_candidate_role_eligible'] for row in packet['rows']) == 18
assert {row['game_id'] for row in packet['rows']} == {'2026_10_WAS_NYG'}
assert all(row['line'] is None and row['selected_side'] is None for row in packet['rows'])
now = dt.datetime.now(dt.timezone.utc)
assert all(dt.datetime.fromisoformat(row['expires_UTC']) < now for row in packet['rows'])
report = {
    'id': 'FINAL-MILE-C-SERVED-BYTE-VERIFICATION-v1', 'checked_UTC': now.isoformat(),
    'URL': base + 'championship.html', 'served_asset_commit': args.commit,
    'files': rows, 'GETs': len(paths), 'response_bytes': sum(row['bytes'] for row in rows),
    'categories': 12, 'product_records': 48, 'retained_forecast_rows': 25,
    'WR_TE_candidate_scope': 18, 'RB_shadow': 7, 'games': 1,
    'real_offers': 0, 'real_selections': 0,
    'current_recommendation_use': 'EXPIRED; ORIGINAL FORECASTS RETAINED FOR GRADING',
    'C_research_site_deployed': True, 'original_website_changed': False,
    'primary_switch': False, 'new_fits': 0, 'new_inference': 0,
    'scope': 'Exact served C HTML/JS/source-bound twelve-category decision/retained legacy payloads and deployment stamp; direct browser checks separate. No original-site activation.'
}
assert report['response_bytes'] <= 4_194_304
(root / 'reports/category-decision-release-01/final-mile-v1/SERVED_VERIFICATION.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report))
