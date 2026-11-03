"""All predeclared strong simple-control pairs, on each exact common decided mask."""
from collections import defaultdict
import abc_championship_v2 as c
import actual_accuracy_v6 as a
rows,_=a.load_records();by=defaultdict(dict)
for r in rows:
 if r['venue']=='pinnacle' and r['season']==2026 and 1<=r['week']<=8:by[r['offer_id']][r['method_id']]=r
results=[]
for target in a.CATEGORIES:
 for method in sorted({r['method_id'] for r in rows}-{'ALWAYS_OVER','ALWAYS_UNDER','EARLIER_PREVALENCE_V8'}):
  matches=[]
  for control in ['ALWAYS_OVER','ALWAYS_UNDER','EARLIER_PREVALENCE_V8']:
   rr=[(g[method],g[control]) for g in by.values() if method in g and control in g and g[method]['category']==target and all(c.status(g[m]) in ['WIN','LOSS'] for m in [method,control])]
   if not rr:continue
   for x,y in rr:assert a.offer_case(x)==a.offer_case(y) and x['actual']==y['actual'] and x['decision_UTC']==y['decision_UTC'] and x['position']==y['position'] and x['scoring_contract_id']==y['scoring_contract_id']
   w=sum(c.status(x)=='WIN' for x,y in rr);b=sum(c.status(y)=='WIN' for x,y in rr);matches.append(dict(category=target,method=method,control=control,common_decided=len(rr),candidate_wins=w,control_wins=b,paired_win_change=w-b,opportunity_ids=[x['offer_id'] for x,y in rr]))
  for r in matches:r['highest_observed_control_on_own_common_mask']=r['control_wins']/r['common_decided']==max(q['control_wins']/q['common_decided'] for q in matches)
  results+=matches
c.write('STRONG_CONTROL_PAIRS.json',dict(scope='EXPOSED_C_ONLY_PARTIAL_E1;controls selected for reporting not operationalrouting',pairs=results,new_fits=0))
print('STRONG_CONTROL_PAIRS',len(results))
