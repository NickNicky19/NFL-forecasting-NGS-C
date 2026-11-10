"""No-fit offered-player numerical paired comparisons, including strong controls."""
import collections,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(Path(__file__).resolve().parent))
import receiving_increment_c03 as d
from qualified_metric_view import offered_numeric_rows
from summarize_increment import ci
rows=offered_numeric_rows();out=[]
for scope,roles in [('WR_TE',['WR','TE']),('RB',['RB']),('ALL_SUPPORTED',['RB','WR','TE'])]:
 for co in ['ALL','priority','workload_top20']:
  for a,b in [('R1','R0'),('R2','R0'),('R2','R1'),('R3','R2'),('R3','R0'),('R2','CONTROL_CONTEXT_P1'),('R2','CONTROL_CONTEXT_P2'),('R3','CONTROL_CONTEXT_P2')]:
   rr=[r for r in rows if r['position'] in roles and (co=='ALL' or r['cohort'].get(co,False)) and r.get(a) and r.get(b) and r['actual'] is not None]
   for metric in ['median_absolute_error','mean_absolute_error','mean_squared_error']:
    def error(r,m):
     e=r[m]['median' if metric.startswith('median') else 'mean']-r['actual'];return e*e if metric.endswith('squared_error') else abs(e)
    delta=[error(r,a)-error(r,b) for r in rr]
    out.append(dict(scope=scope,cohort=co,candidate=a,control=b,metric=metric,matched_known=len(rr),candidate_score=float(np.mean([error(r,a) for r in rr])) if rr else None,control_score=float(np.mean([error(r,b) for r in rr])) if rr else None,change=float(np.mean(delta)) if delta else None,uncertainty=ci(rr,delta),evidence_tier='Qualifiedexactofferedplayermask;timingunverifiedactualquotes;exposedreconstruction',actual_weeks=sorted({r['week'] for r in rr})))
d.write(d.OUT/'OFFERED_NUMERICAL_PAIRED_CHANGES.json.xz',out)
print('OFFERED_NUMERIC_PAIRS',len(out))
