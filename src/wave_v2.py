"""Finite, resumable twelve-category non-NGS distribution/threshold experiment."""
import argparse,gzip,hashlib,json,math,pickle,resource,time,sys
from pathlib import Path
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
from contracts_v2 import CATEGORIES,CHART
from data_v2 import load,History,vector,admitted_roles
from laws_v2 import LeafModel,ThresholdModel,Prior,Law

VERSION='C-ALL12-LAW-THRESHOLD-v2.1'
HISTORIES={'H-CURRENT':2026,'H-RECENT':2025,'H-MULTI':2022}
GRIDS={
 'pass_yd':[99.5,149.5,199.5,249.5,299.5,349.5],
 'pass_td':[.5,1.5,2.5,3.5], 'pass_cmp':[9.5,14.5,19.5,24.5,29.5],
 'pass_att':[14.5,19.5,24.5,29.5,34.5,39.5], 'pass_int':[.5,1.5,2.5],
 'rush_yd':[-.5,9.5,24.5,49.5,74.5,99.5], 'rush_att':[.5,4.5,9.5,14.5,19.5,24.5],
 'rec':[.5,1.5,2.5,3.5,4.5,5.5,7.5], 'rec_yd':[-.5,9.5,24.5,49.5,74.5,99.5],
 'rush_rec_yd':[-.5,19.5,39.5,59.5,79.5,99.5,129.5],
 'fpts':[.01,5.01,10.01,15.01,20.01,25.01,30.01], 'anytime_td':[.5]}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(v):
 if isinstance(v,dict):return {str(k):clean(x) for k,x in v.items()}
 if isinstance(v,(list,tuple)):return [clean(x) for x in v]
 if isinstance(v,(np.integer,)):return int(v)
 if isinstance(v,(np.floating,float)):
  if math.isnan(v):return None
  if math.isinf(v):return 'Infinity' if v>0 else '-Infinity'
  return float(v)
 return v
def write(p,x):
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(clean(x),f,allow_nan=False,separators=(',',':'))
def eligible(r,t):return r['position'] in admitted_roles(t)
def run(inputs,out,public,pilot=False,artifact_cap=134217728):
 start=time.monotonic();cpu=time.process_time();out.mkdir(parents=True,exist_ok=True);public.mkdir(parents=True,exist_ok=True)
 launch_code={name:sha(Path(__file__).with_name(name)) for name in ['wave_v2.py','laws_v2.py','data_v2.py','contracts_v2.py']}
 d,g,teams=load(inputs);records=d.to_dict('records');index={id(r):i for i,r in enumerate(records)}
 latest=[];fits=0;rows=0;attempts=0;cache={};all_receipts=[]
 configs=[]
 for h in HISTORIES:
  configs += [(h,'P2_LEAF','E0_BASE'),(h,'P2_LEAF','E0_OP'),(h,'P3_LOGIT','E0_OP'),(h,'P3_HGB','E0_OP')]
 configs += [('H-MULTI','P2_LEAF','E0_ENV'),('H-MULTI','P2_LEAF','E0_DEF')]
 if pilot:configs=[('H-MULTI','P2_LEAF','E0_BASE'),('H-MULTI','P3_LOGIT','E0_OP'),('H-MULTI','P3_HGB','E0_OP')]
 source={p.name:sha(p) for p in inputs.iterdir() if p.is_file()}
 for target in (['pass_cmp'] if pilot else CATEGORIES):
  kind,scale=CATEGORIES[target][2:4];grid=np.asarray(GRIDS[target]);grid_floor=np.floor(grid*scale).astype(int)
  pool=[r for r in records if eligible(r,target)]
  for history,family,arm in configs:
   check_version=VERSION+'-fantasy-lattice-v1' if target=='fpts' else VERSION
   if all((out/f'{check_version}-{target}-{history}-{family}-{arm}-W{w:02}'/'DONE.json').exists() for w in ([1] if pilot else range(1,8))):continue
   floor=HISTORIES[history];hist=History(d[d.season>=floor],'player_id');th=History(teams[teams.season>=floor],'team')
   x=np.asarray([vector(r,target,hist,th,arm) for r in pool],dtype=float)
   for week in ([1] if pilot else range(1,8)):
    slot_version=VERSION+'-fantasy-lattice-v1' if target=='fpts' else VERSION
    slot=f'{slot_version}-{target}-{history}-{family}-{arm}-W{week:02}';dest=out/slot
    if (dest/'DONE.json').exists():continue
    dest.mkdir(parents=True,exist_ok=True)
    origin=float(g.loc[(g.season==2026)&(g.week==week),'kickoff'].min())
    ti=[i for i,r in enumerate(pool) if r['season']>=floor and r['available']<origin and r['values'][target] is not None]
    qi=[i for i,r in enumerate(pool) if r['season']==2026 and r['week']==week]
    tx=x[ti];qx=x[qi];train=[pool[i] for i in ti];query=[pool[i] for i in qi];y=np.asarray([r['values'][target]*scale for r in train],dtype=float);roles=np.asarray([r['position'] for r in train]);qr=np.asarray([r['position'] for r in query])
    if target=='fpts':y=np.rint(y)
    minimum=60;learned=len(ti)>=minimum and (kind!='event' or len(np.unique(y))==2)
    # P3 single class in synthetic labels can occur; use explicit earlier prevalence fallback.
    if family!='P2_LEAF' and kind!='event':learned=learned and len(np.unique((np.repeat(y,len(grid_floor))<=np.tile(grid_floor,len(y))).astype(int)))==2
    prior={p:Prior(y[roles==p],kind) for p in set(roles)};global_prior=Prior(y,kind)
    attempt=dict(slot=slot,started_UTC=pd.Timestamp.now(tz='UTC').isoformat(),origin_UTC=pd.Timestamp(origin,unit='s',tz='UTC').isoformat(),training_rows=len(ti),history=history,feature_floor=floor,latest_training_available=max([r['available'] for r in train],default=None),training_membership_sha256=hashlib.sha256('\n'.join(r['game_id']+':'+r['player_id'] for r in train).encode()).hexdigest(),family=family,information_arm=arm,learned=learned,source_sha256=source)
    attempt['launch_code_sha256']=launch_code;attempt['score_version']='ANALYTIC_LOGPMF_V1'
    if (dest/'ATTEMPT.json').exists():
     old=json.load(open(dest/'ATTEMPT.json'))
     if old['training_membership_sha256']!=attempt['training_membership_sha256']:raise ValueError('partial slot training changed')
    else:write(dest/'ATTEMPT.json',attempt)
    attempts+=1;restored_partial=(dest/'model.pkl.gz').exists()
    if restored_partial:
     with gzip.open(dest/'model.pkl.gz','rb') as f:model=pickle.load(f)['model']
    elif learned:
     if fits>=1176:raise RuntimeError('FIT_CAP')
     with threadpool_limits(limits=1):
      model=LeafModel(kind,scale).fit(tx,y,roles) if family=='P2_LEAF' else ThresholdModel('MONOTONE_HGB' if family=='P3_HGB' else 'LOGIT',kind=='event',grid_floor).fit(tx,y)
     fits+=1
    else:model=None
    if not restored_partial:
     with gzip.open(dest/'model.pkl.gz','wb',compresslevel=5) as f:pickle.dump(dict(model=model,prior=prior,global_prior=global_prior,kind=kind,scale=scale,grid_floor=grid_floor,attempt=attempt),f,protocol=5)
    with threadpool_limits(limits=1):
     if family=='P2_LEAF':laws=model.laws(qx,qr) if model else [Law([],[],prior.get(role,global_prior),scale) for role in qr]
     else:
      if model:cp=model.cdfs(qx,grid_floor)
      else:cp=np.asarray([[prior.get(role,global_prior).event] if kind=='event' else [prior.get(role,global_prior).cdf(k) if len(y) else .5 for k in grid_floor] for role in qr])
    packet=[]
    for j,(r,fv) in enumerate(zip(query,qx)):
     actual=r['values'][target];p=dict(version=slot_version,slot=slot,target=target,history=history,family=family,arm=arm,game_id=r['game_id'],player_id=r['player_id'],name=r['player_display_name'],position=r['position'],team=r['team'],opponent=r['opponent_team'],season=2026,week=week,kickoff_UTC=pd.Timestamp(r['kickoff'],unit='s',tz='UTC').isoformat(),as_of_UTC=pd.Timestamp(r['kickoff'],unit='s',tz='UTC').isoformat(),information_tier='CURRENT_REVISED_7DAY_RECONSTRUCTION',generated_UTC=pd.Timestamp.now(tz='UTC').isoformat(),scoring_contract_id=CHART if target=='fpts' else 'rush-or-rec-at-least-one-v1' if kind=='event' else 'official-player-fullgame-OT-v1',actual=actual,appearance='PLAYED' if r['played'] else 'UNKNOWN',chart_state=r['chart_state'] if target=='fpts' else None,features=[float(v) if np.isfinite(v) else None for v in fv],fallback=not learned,grid=list(map(float,grid)))
     ref=prior.get(r['position'],global_prior)
     if family=='P2_LEAF':
      law=laws[j];p.update(mean=law.mean(),median=law.quantile(.5),p05=law.quantile(.05),p95=law.quantile(.95),product_type='EVENT_PROBABILITY' if kind=='event' else 'DISCRETE_OUTCOME_LAW')
      po=[law.probability(line)['over'] for line in grid];p['p_over']=po
      if actual is not None:
       p['crps']=law.crps(actual);p['nll']=-law.logpmf(int(round(actual*scale)))
     else:
      po=[float(cp[j,0])] if kind=='event' else list(map(float,1-cp[j]));p.update(mean=None,median=None,p05=None,p95=None,product_type='DIRECT_EVENT_PROBABILITY' if kind=='event' else 'DIRECT_THRESHOLD_PROBABILITY',p_over=po,crps=None,nll=None)
     # Fixed diagnostic grid is off-lattice: no pushes by construction, not sportsbook offers.
     p['p_push']=[0.]*len(grid);p['reference_over']=[ref.event] if kind=='event' else [1-ref.cdf(k) for k in grid_floor]
     if actual is not None:
      truth=(actual>grid).astype(float);p['grid_brier']=float(np.mean((np.asarray(po)-truth)**2));p['grid_logloss']=float(np.mean([-math.log(v if y0 else 1-v) if (v if y0 else 1-v)>0 else float('inf') for v,y0 in zip(po,truth)]));p['reference_brier']=float(np.mean((np.asarray(p['reference_over'])-truth)**2))
     packet.append(clean(p))
    if (dest/'rows.json.gz').exists():(dest/'rows.json.gz').rename(dest/'rows-before-completion.json.gz')
    with gzip.open(dest/'rows.json.gz','wt',compresslevel=5) as f:json.dump(packet,f,separators=(',',':'),allow_nan=False)
    rows+=len(packet);receipt=attempt|dict(completed_UTC=pd.Timestamp.now(tz='UTC').isoformat(),rows=len(packet),model_sha256=sha(dest/'model.pkl.gz'),row_sha256=sha(dest/'rows.json.gz'),raw_features=int(x.shape[1]),cpu_seconds_since_start=time.process_time()-cpu)
    write(dest/'DONE.json',receipt);all_receipts.append(receipt);print(slot,len(query),len(ti),'FIT' if learned else 'FALLBACK',flush=True)
    if time.process_time()-cpu>1800 or time.monotonic()-start>2400:raise RuntimeError('TIME_BUDGET')
    if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024>2147483648:raise RuntimeError('RSS_BUDGET')
    if sum(p.stat().st_size for p in out.rglob('*') if p.is_file())>artifact_cap:raise RuntimeError('ARTIFACT_BUDGET')
 write(public/('PILOT_RECEIPT.json' if pilot else 'RUN_RECEIPT.json'),dict(version=VERSION,pilot=pilot,new_attempts=attempts,new_fits=fits,new_forecast_views=rows,wall_seconds=time.monotonic()-start,cpu_seconds=time.process_time()-cpu,peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,launch_code_sha256=launch_code,artifacts_bytes=sum(p.stat().st_size for p in out.rglob('*') if p.is_file()),source_sha256=source,all_slots=len(list(out.glob('*/DONE.json')))))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--inputs',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--public',type=Path,required=True);p.add_argument('--pilot',action='store_true');p.add_argument('--artifact-cap',type=int,default=134217728);a=p.parse_args();run(a.inputs,a.out,a.public,a.pilot,a.artifact_cap)
