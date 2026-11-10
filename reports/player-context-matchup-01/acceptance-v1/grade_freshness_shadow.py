"""Append-only numerical scoring of previously server-frozen query shadows.

Participation/actuals come from the existing qualified canonical grades; no new
label filling, line grading, forecasts, fits or retraining occurs here.
"""
import gzip,json,hashlib,math
from pathlib import Path
from datetime import datetime,timezone
import sys
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'src'))
from safe_models_v4 import law_load
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 shadow=ROOT/'prospective/shadows/AUDIT-D2-C-REC-W09-01';run=json.loads((shadow/'RUN.json').read_text());proof=json.loads((shadow/'SERVER_RECEIPT.json').read_text())
 assert sha(shadow/'ROWS.json.gz')==run['rows_SHA256']
 for item in proof['fresh_GitHub_bytes']:assert sha(shadow/item['path'])==item['SHA256']
 assert proof['server_completed_UTC']<run['first_kickoff_UTC']
 path=ROOT/'prospective/grades/C-NATIVE-GRADE-20261107-JAXBAL-01-C-FWD-v4-20261105-W09-JAXBAL-remainder.json';grades={r['forecast_id']:r for r in json.loads(path.read_text())['grades']};rows=[]
 for r in json.loads(gzip.decompress((shadow/'ROWS.json.gz').read_bytes())):
  grade=grades[r['forecast_id']];assert grade['category']=='rec';a=dict(forecast_id=r['forecast_id'],player_id=r['player_id'],state=grade['state'],actual=grade['actual'])
  if a['state']=='GRADED_PLAYED':
   y=a['actual'];a['observed_median_AE']=abs(r['original_observed_median']-y);a['proxy_median_AE']=abs(r['proxy_median']-y)
   a['observed_mean_SE']=(r['original_observed_mean']-y)**2;a['proxy_mean_SE']=(r['proxy_mean']-y)**2
   a['observed_CRPS']=law_load(r['observed_law']).crps(y);a['proxy_CRPS']=law_load(r['proxy_law']).crps(y)
  rows.append(a)
 known=[r for r in rows if r['state']=='GRADED_PLAYED'];metrics={key:sum(r[key] for r in known)/len(known) for key in known[0] if key.endswith(('_AE','_SE','_CRPS'))}
 d=dict(id='C-FROZEN-FRESHNESS-SHADOW-GRADE-v1',created_UTC=datetime.now(timezone.utc).isoformat(),shadow_rows=len(rows),graded=len(known),unknown=len(rows)-len(known),game_count=1,original_shadow_SHA256=sha(shadow/'ROWS.json.gz'),server_receipt_SHA256=sha(shadow/'SERVER_RECEIPT.json'),canonical_grade_SHA256=sha(path),metrics=metrics,rows=rows,qualified_offers=0,new_fits=0,originals_changed=0,interpretation='One originally pregame-frozen query-only comparison under same seven-day-trained model. Not aligned training/query information comparison, context finalist evaluation, or actual-line evidence; no primary release.')
 p=Path(__file__).with_name('FRESHNESS_SHADOW_GRADE.json');assert not p.exists();p.write_text(json.dumps(d,indent=2)+'\n');print(d['graded'],d['unknown'],metrics)
if __name__=='__main__':main()
