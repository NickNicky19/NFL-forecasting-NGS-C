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
root = Path(__file__).resolve().parents[2]
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
        headers = dict(response.headers)
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
                 'HTTP_Date': headers.get('Date'), 'HTTP_Age': headers.get('Age'),
                 'exact_local_asset_parity': name != 'build.json',
                 'deployment_stamp_and_payload_bindings': name == 'build.json'})
data = json.loads(payloads['data/category-decisions-c06.json'])
packet = data['current_packet']
assert len(data['categories']) == 12 and len(packet['rows']) == 25
assert len({row['player_id'] for row in packet['rows']}) == 25
assert sum(row['direction_candidate_role_eligible'] for row in packet['rows']) == 18
assert {row['game_id'] for row in packet['rows']} == {'2026_10_WAS_NYG'}
assert all(row['line'] is None and row['selected_side'] is None for row in packet['rows'])
now = dt.datetime.now(dt.timezone.utc)
assert all(dt.datetime.fromisoformat(row['expires_UTC']) < now for row in packet['rows'])
report = {
    'id': 'C06-SERVED-BYTE-VERIFICATION-v1', 'checked_UTC': now.isoformat(),
    'URL': base + 'championship.html', 'served_asset_commit': args.commit,
    'files': rows, 'GETs': len(paths), 'response_bytes': sum(row['bytes'] for row in rows),
    'categories': 12, 'product_records': 48, 'retained_forecast_rows': 25,
    'WR_TE_candidate_scope': 18, 'RB_shadow': 7, 'games': 1,
    'real_offers': 0, 'real_selections': 0,
    'current_recommendation_use': 'EXPIRED; ORIGINAL FORECASTS RETAINED FOR GRADING',
    'C_research_site_deployed': True, 'original_website_changed': False,
    'primary_switch': False, 'new_fits': 0, 'new_inference': 0,
    'scope': 'Exact served C HTML/JS/current/legacy payload bytes and deployment stamp; direct browser checks recorded separately.'
}
assert report['response_bytes'] <= 4_194_304
(root / 'reports/category-decision-release-01/SERVED_VERIFICATION.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report))
