"""Descriptive paired intervals for the displayed, research-exposed leaders."""
import json,gzip,argparse
from pathlib import Path
import numpy as np,pandas as pd
from contracts_v2 import CATEGORIES
def intervals(p):
 result={}
 for key in ['game_id','week']:
  g=p.groupby(key).delta.agg(['sum','count']);rng=np.random.default_rng(1701);i=rng.integers(0,len(g),(500,len(g)));v=g['sum'].to_numpy()[i].sum(axis=1)/g['count'].to_numpy()[i].sum(axis=1);result[key+'_ci95']=list(map(float,np.quantile(v,[.025,.975])))
 return result
def run(root,report):
 leaders=pd.read_csv(report/'LEADERS.csv');rows=[]
 for p in root.glob('*/rows.json.gz'):rows+=json.loads(gzip.decompress(p.read_bytes()))
 d=pd.DataFrame(rows);result=[]
 for leader in leaders.itertuples():
  t=leader.target;pool=d[d.target==t]
  if leader.horizon=='RB':pool=pool[pool.position=='RB']
  elif leader.horizon=='PRIMARY':pool=pool[pool.position.isin(CATEGORIES[t][4])]
  base=pool[(pool.family=='P2_LEAF')&(pool.history=='H-MULTI')&(pool.arm=='E0_BASE')]
  for objective,method in [('probability',leader.probability_method),('numerical',leader.numerical_method)]:
   if objective=='numerical' and t=='anytime_td':continue
   f,h,a=method.split('/');candidate=pool[(pool.family==f)&(pool.history==h)&(pool.arm==a)];p=candidate.merge(base,on=['game_id','player_id','week'],suffixes=('_a','_b'),validate='one_to_one');assert len(p)==len(base);assert np.array_equal(p.actual_a.fillna(-9999),p.actual_b.fillna(-9999));p=p[p.actual_a.notna()].copy()
   p['delta']=p.grid_brier_a-p.grid_brier_b if objective=='probability' else (p.median_a-p.actual_a).abs()-(p.median_b-p.actual_b).abs()
   result.append(dict(target=t,horizon=leader.horizon,objective=objective,candidate=method,control='P2_LEAF/H-MULTI/E0_BASE',n=len(p),delta=float(p.delta.mean()),research_exposed_selected_pair=True,**intervals(p)))
 (report/'PRIMARY_PAIRED.json').write_text(json.dumps(result,indent=2));print('PRIMARY_PAIRS',len(result))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args();run(a.run,a.report)
