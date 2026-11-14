"""No-fit independent raw-mutation and numeric restoration check for two origins."""
import gzip,hashlib,json,sys
from pathlib import Path
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from extend_completion_origins import prepare,finite,OUT,sha
from data_v2 import History,vector
from safe_models_v4 import load,infer_forest

def main():
 d,g,teams,pool,x,earlier,raw,schedule=prepare();checks=[]
 for week in [8,9]:
  done=json.loads((OUT/f'W{week:02d}/DONE.json').read_bytes());origin=pd.Timestamp(done['origin_UTC']).timestamp()
  ti=[i for i,r in enumerate(pool) if r['season']>=2022 and r['available']<origin and r['values']['pass_cmp'] is not None]
  qi=[i for i,r in enumerate(pool) if r['season']==2026 and r['week']==week]
  changed=d.copy(deep=True);changed['values']=changed['values'].map(dict)
  target=(changed.season==2026)&(changed.week>=week)
  for i in changed.index[target]:changed.at[i,'values']['pass_cmp']=99999
  for c in ['attempts','carries','targets']:changed.loc[target,c]=99999
  # Explicit synthetic future row is a leakage fixture, not NFL evidence.
  future=changed.loc[changed.index[target][0]].copy();future['game_id']='SYNTHETIC_FUTURE_ONLY';future['kickoff']=float(changed.kickoff.max())+30*86400;future['available']=future['kickoff']+7*86400;future['week']=99
  changed=pd.concat([changed,pd.DataFrame([future])],ignore_index=True)
  ct=teams.copy(deep=True);tm=(ct.season==2026)&(ct.week>=week)
  for c in ['attempts','carries','sacks_suffered']:ct.loc[tm,c]=99999
  ft=ct.loc[ct.index[tm][0]].copy();ft['game_id']='SYNTHETIC_FUTURE_ONLY';ft['kickoff']=future['kickoff'];ft['available']=future['available'];ft['week']=99
  ct=pd.concat([ct,pd.DataFrame([ft])],ignore_index=True)
  h=History(changed[changed.season>=2022],'player_id');th=History(ct[ct.season>=2022],'team')
  bykey={(r['game_id'],r['player_id']):r for r in changed[changed.position=='QB'].to_dict('records')}
  mutated_x=[]
  for i in ti+qi:
   r=bykey[pool[i]['game_id'],pool[i]['player_id']]
   v=vector(r,'pass_cmp',h,th,'E0_ENV');assert finite(v)==finite(x[i]);mutated_x.append(v)
  for i in ti:assert bykey[pool[i]['game_id'],pool[i]['player_id']]['values']['pass_cmp']==pool[i]['values']['pass_cmp']
  model=load(OUT/f'W{week:02d}/MODEL.json.gz',done['model_SHA256'])
  laws=infer_forest(model,np.asarray(mutated_x[len(ti):],float),np.asarray(['QB']*len(qi)))
  points=json.loads(gzip.decompress((OUT/f'W{week:02d}/POINTS.json.gz').read_bytes()))
  assert len(points)==len(laws)
  for p,l in zip(points,laws):assert abs(p['mean']-l.mean())<1e-12 and p['median']==l.quantile(.5)
  checks.append({'week':week,'training_rows':len(ti),'query_rows':len(qi),'target_query_own_outcomes_and_realized_exposures_mutated':True,'target_and_future_history_mutated':True,'synthetic_future_rows_appended':2,'training_X_Y_and_query_X_unchanged':True,'numeric_restored_predictions_unchanged':True,'new_fits':0})
 receipt={'id':'C-CMP-EXTENSION-INDEPENDENT-MUTATION-v1','status':'PASS','checks':checks,'scope':'Direct unchanged core features on mutated raw target/future rows, including query rows themselves; immutable safe numeric model restoration. No newfit/sourcecall/offergrade. Synthetic rows are separate fixtures, not NFL observations.'}
 path=OUT/'INDEPENDENT_MUTATION_CHECK.json'
 with path.open('x') as f:json.dump(receipt,f,indent=2);f.write('\n')
 print(json.dumps(receipt))
if __name__=='__main__':main()
