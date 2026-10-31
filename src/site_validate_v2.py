"""Static contract checks; no new forecasting, acquisition or data refresh."""
import json,hashlib
from pathlib import Path
def validate(root):
 m=json.load(open(root/'data/manifest.json'));assert len(m['categories'])==12;assert not m['actionable_rankings'] and not m['live_offers_available']
 for e in m['files']:
  f=root/'data'/e['file'];assert hashlib.sha256(f.read_bytes()).hexdigest()==e['sha256'];rows=json.load(open(f));assert len(rows)==e['rows']
  for r in rows:
   assert r['target']==e['target'] and r['week']==e['week'] and r['history']==e['history'];assert len(r['grid'])==len(r['p_over'])
   assert all(0<=x<=1 for x in r['p_over']);assert all(a>=b-1e-10 for a,b in zip(r['p_over'],r['p_over'][1:]))
 assert all(r['state']=='NO_QUALIFIED_SIX_LEG_ENTRY' and r['six_of_six'] is None for r in json.load(open(root/'data/six-leg.json')))
 print('STATIC_SITE_CONTRACT_PASS',len(m['files']))
if __name__=='__main__':validate(Path('docs'))
