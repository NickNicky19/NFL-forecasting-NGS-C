"""Fresh C GitHub byte recovery and separate aggregate/grade arithmetic checks."""
import argparse
import csv
import gzip
import hashlib
import io
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
BASE = 'reports/abc-championship/continuation-v2/'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--commit',required=True)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--receipt',required=True,type=Path)
    args = parser.parse_args()
    assert not args.output.exists()
    args.output.mkdir(parents=True)
    files = [
        'reports/abc-championship/CURRENT_PROTOCOL.json',
        BASE+'A_W1_W7_ARCHIVED_SCORES.json.gz',
        BASE+'B_OWNER_LOCAL_SCORES.json.gz',
        BASE+'A_C_OWNER_LOCAL_SCORES.json',
        BASE+'C_WEEK8_FINAL_FORECAST_GRADES.json',
        BASE+'C_WEEK8_FINAL_GRADED_FORECAST_ROWS.csv.gz',
        'docs/data/championship-period-v2.json',
    ]
    summary = json.loads((ROOT/BASE/'C_WEEK8_FINAL_FORECAST_GRADES.json').read_text())
    files += [summary['outcome_packet']]+[r['path'] for r in summary['grade_files']]
    files += [str(Path(summary['outcome_packet']).parent/'evidence/MONDAY_FACTS.csv')]
    assert len(files) <= 12
    data, receipts, retained = {}, [], 0
    for path in files:
        url = 'https://raw.githubusercontent.com/NickNicky19/NFL-forecasting-NGS-C/'+args.commit+'/'+path
        with urlopen(Request(url,headers={'Cache-Control':'no-cache','Accept-Encoding':'identity'}),timeout=30) as response:
            b = response.read(4*1024*1024+1)
            server_date = response.headers.get('Date')
        assert len(b) <= 4*1024*1024 and b == (ROOT/path).read_bytes(), ('RESTORE_BYTES',path)
        keep = path.endswith('.csv.gz') or path.endswith('SCORES.json.gz') or path.startswith('docs/')
        if keep:
            retained += len(b)
            assert retained <= 786432
            dest = args.output/path
            dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes(b)
        receipts.append(dict(path=path,commit=args.commit,bytes=len(b),SHA256=hashlib.sha256(b).hexdigest(),server_HTTP_date=server_date,retained_copy=keep))
        data[path] = b
    a = json.loads(gzip.decompress(data[BASE+'A_W1_W7_ARCHIVED_SCORES.json.gz']))
    for r in a:
        assert sum(int(w['correct']) for w in r['week_rows']) == r['COMBINED']['wins']
        assert sum(int(w['decided']) for w in r['week_rows']) == r['COMBINED']['decided']
        assert r['selected'] == r['COMBINED']['decided']+r['unresolved']+r['pushes']+r['DNP']
    b = json.loads(gzip.decompress(data[BASE+'B_OWNER_LOCAL_SCORES.json.gz']))
    original = [r for r in b if r['strategy']=='original' and r['horizon_id']=='B_LOCAL_W8_FIXED_ORIGINAL_SOURCE_FINAL_LABELS_V2']
    assert sum(r['COMBINED']['wins'] or 0 for r in original) == 205
    assert sum((r['OVER']['losses'] or 0)+(r['UNDER']['wins'] or 0) for r in original) == 224
    rows = list(csv.DictReader(io.StringIO(gzip.decompress(data[BASE+'C_WEEK8_FINAL_GRADED_FORECAST_ROWS.csv.gz']).decode())))
    counts = dict(Counter(r['state'] for r in rows))
    assert counts == {'GRADED_PLAYED':1532,'UNKNOWN':981}
    for r in rows:
        if r['state']=='GRADED_PLAYED' and r['median']:
            assert abs(abs(float(r['median'])-float(r['actual']))-float(r['absolute_error'])) < 1e-10
    packet = json.loads(data[summary['outcome_packet']])
    for artifact in summary['grade_files']:
        assert hashlib.sha256(data[artifact['path']]).hexdigest() == artifact['SHA256']
    assert hashlib.sha256(data[summary['outcome_packet']]).hexdigest() == summary['outcome_SHA256']
    result = dict(id='ABC-C-PERIOD-GITHUB-RESTORATION-v2-1',verified_UTC=datetime.now(timezone.utc).isoformat(),commit=args.commit,files=receipts,all_bytes_fresh_and_equal=True,retained_bytes=retained,downloaded_bytes=sum(r['bytes'] for r in receipts),A_weekly_cumulative_reconciliations=len(a),B_complete_triads=len(b),original_control='205/415 vs224/415',C_states=counts,C_forecast_rows=len(rows),new_fits=0,new_inference=0,untrusted_models_loaded=False,original_pregame_claim_created=False,limits='Fresh public aggregate recovery and arithmetic; not A/B raw identity/quote/mask verification or Session A/B acknowledgement')
    args.receipt.write_text(json.dumps(result,indent=2)+'\n')
    print('FRESH_GITHUB_PERIOD_RESTORED',len(receipts),retained,counts)


if __name__=='__main__':
    main()
