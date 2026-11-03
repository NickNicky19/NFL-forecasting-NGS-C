"""Fixed-procedure suite totals; never stitch category winners or pool years twice."""
import json,hashlib
from pathlib import Path
r=Path(__file__).resolve().parents[1]/'reports/abc-championship';q=json.loads((r/'COMMON_CORE-v2-C-1.json').read_bytes())['scores'];out=[]
for m in sorted({x['method'] for x in q}):
 rr=[x for x in q if x['method']==m];s={}
 for side in ['OVER','UNDER','COMBINED']:
  w=sum(x[side]['wins'] or 0 for x in rr);l=sum(x[side]['losses'] or 0 for x in rr);s[side]=dict(wins=w,losses=l,decided=w+l,rate=w/(w+l) if w+l else None)
 out.append(dict(procedure=m,period_id='E1',requested_weeks=list(range(1,9)),actual_weeks=[2,3],season=2026,categories=[x['category'] for x in rr],scope='PARTIAL_FOUR_MARKETS_C_ONLY_COMMON_CORE',own_record=s,opportunity_weighted_rate=s['COMBINED']['rate'],category_balanced_rate=sum(x['COMBINED']['rate'] for x in rr)/len(rr),season_balanced='N/A_requested_multiseason_set_not_supported',rule='One fixed existing procedure acrosssupportedcategories;NOT hindsightbestrouter;noE5/E6poolofduplicateviews'))
p=r/'SUITE_SUMMARIES.json';p.write_text(json.dumps(out,indent=2)+'\n');j=json.loads((r/'CURRENT_PROTOCOL.json').read_bytes());j['suite_summaries']=dict(path='reports/abc-championship/SUITE_SUMMARIES.json',SHA256=hashlib.sha256(p.read_bytes()).hexdigest());code=Path(__file__);j['suite_code']=dict(path='src/'+code.name,SHA256=hashlib.sha256(code.read_bytes()).hexdigest());(r/'CURRENT_PROTOCOL.json').write_text(json.dumps(j,indent=2)+'\n')
