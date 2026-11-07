"""Zero-refit later scoring of retained historical threshold predictions.

Synthetic diagnostic probabilities are never sportsbook lines or hit rates.
"""
import hashlib,json,math,resource,signal,time
from pathlib import Path
from collections import defaultdict
import numpy as np
import pandas as pd
import context_experiment_c01 as e
from reliability_v8 import hgb_cdf
def run(inputs):
 out=e.BASE_OUT/'validation-replay-v1';art=e.BASE_ART/'validation-replay-v1'
 assert not (out/'RUN.json').exists(),'COMPLETED_VALIDATION_REPLAY_FROZEN'
 started=time.process_time();signal.signal(signal.SIGPROF,lambda *_:(_ for _ in ()).throw(RuntimeError('VALIDATION_REPLAY_CPU_CAP')));signal.setitimer(signal.ITIMER_PROF,90)
 e.OUT=out;e.STRICT=True;pool,g,hist,mats=e.setup(inputs);index={(r['game_id'],r['player_id']):i for i,r in enumerate(pool)};features=e.read(e.BASE_ART/'v1.1/FEATURE_EXPORT.json.gz');run=e.read(e.BASE_OUT/'v1.1/RUN.json');models={}
 for path,h in run['models'].items():
  if Path(path).stem.split('-')[-1].startswith('P'):continue
  p=e.ROOT/path;assert e.sha(p)==h;models[p.name]=e.read(p)['model']
 grids=[0,1,2,3,4,5,7];pred=[]
 for f in features:
  i=index[(f['game_id'],f['player_id'])];r=pool[i];y=r['values']['rec'];arms={}
  for arm in ['E1','E2','E3']:
   model=models[f"{f['origin']}-{arm}.json.gz"];cdf=hgb_cdf(model,mats[arm][i],grids);assert all(b-a>=-1e-12 for a,b in zip(cdf,cdf[1:]));arms[arm]=cdf
  pred.append(dict(origin=f['origin'],game_id=r['game_id'],player_id=r['player_id'],position=r['position'],actual=y,cdfs=arms))
 groups=[]
 for season in [2025,2026]:
  for week in ['ALL']+list(range(1,9)):
   for scope,positions in [('WR_TE',['WR','TE']),('ALL_SUPPORTED',['RB','WR','TE'])]:
    selected=[r for r in pred if r['origin'].startswith(str(season)) and (week=='ALL' or r['origin'].endswith(f'W{week:02}')) and r['position'] in positions];known=[r for r in selected if r['actual'] is not None]
    for arm in ['E1','E2','E3']:
     scores=[];logs=[]
     for r in known:
      truth=(r['actual']<=np.asarray(grids)).astype(float);p=np.asarray(r['cdfs'][arm]);scores.append(float(np.mean((p-truth)**2)));probs=np.where(truth==1,p,1-p);logs.append(float(-np.log(probs).mean()))
     groups.append(dict(season=season,week=week,scope=scope,arm=arm,query_rows=len(selected),known_rows=len(known),unknown_rows=len(selected)-len(known),scored_distinct_weeks=len({r['origin'] for r in known}),mean_Brier=float(np.mean(scores)) if scores else None,mean_log_loss=float(np.mean(logs)) if logs else None,neutral_Brier=.25,thresholds_integer_CDF=grids,evaluation='SYNTHETIC_THRESHOLD_DIAGNOSTIC_NOT_ACTUAL_PROP_ACCURACY',five_week_actual_line=False))
 e.write(art/'PREDICTIONS.json.gz',pred);e.write(out/'SCORES.json.gz',groups);e.write(out/'RUN.json',dict(id='C-CONTEXT-VALIDATION-REPLAY-v1',created_UTC=e.now(),new_fits=0,query_rows=len(pred),NFL_player_games=len(pred),binary_threshold_views_not_independent_games=len(pred)*len(grids)*3,CPU_seconds=time.process_time()-started,peak_RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,source_model_run_SHA256=e.sha(e.BASE_OUT/'v1.1/RUN.json'),evidence='CURRENT_REVISED_7DAY_RECONSTRUCTION;ALL_EXPOSED_DEVELOPMENT;SYNTHETIC_ONLY'))
 signal.setitimer(signal.ITIMER_PROF,0);print(e.read(out/'RUN.json'))
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--inputs',type=Path,required=True);a=p.parse_args();run(a.inputs)
