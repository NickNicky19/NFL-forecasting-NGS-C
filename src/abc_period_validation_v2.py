"""Validate published bindings and canonical-to-site parity without any NFL fits."""
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    b = (ROOT / path).read_bytes()
    return json.loads(gzip.decompress(b) if str(path).endswith('.gz') else b)


def validate():
    pointer = load('reports/abc-championship/CURRENT_PROTOCOL.json')
    checked = []

    def walk(x):
        if isinstance(x, dict):
            if 'path' in x and 'SHA256' in x:
                p = ROOT / x['path']
                assert p.is_file(), ('MISSING_BOUND_FILE', x['path'])
                assert hashlib.sha256(p.read_bytes()).hexdigest() == x['SHA256'], ('BOUND_HASH_MISMATCH', x['path'])
                checked.append(x['path'])
            for value in x.values():
                walk(value)
        elif isinstance(x, list):
            for value in x:
                walk(value)

    walk(pointer)
    site = load('docs/data/championship-period-v2.json')
    base = 'reports/abc-championship/continuation-v2/'
    assert site['A_headline'] == load(base+'HEADLINE_A_W1_W7.json')
    b = load(base+'B_OWNER_LOCAL_SCORES.json.gz')
    assert site['B_original'] == [r for r in b if r['strategy']=='original' and r['horizon_id']=='B_LOCAL_W8_FIXED_ORIGINAL_SOURCE_FINAL_LABELS_V2']
    assert site['C_forecast_only'] == load(base+'C_WEEK8_FINAL_FORECAST_GRADES.json')
    assert hashlib.sha256((ROOT/'docs/data/championship-period-v2.json').read_bytes()).hexdigest() == load('docs/build.json')['championship_SHA256']
    assert len(site['A_headline']) == 12 and not site['A_B_current_common_acknowledgement']
    print('PERIOD_BOUND_FILES_AND_SERVED_PROJECTION_VALID', len(checked))


if __name__ == '__main__':
    validate()
