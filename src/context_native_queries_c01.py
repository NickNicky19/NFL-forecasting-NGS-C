"""Append source-qualified missing-stat queries without labels or new fits."""
import hashlib,json,math,time
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import poisson
import context_experiment_c01 as e
from context_features_c01 import Context
from data_v2 import vector
from laws_v2 import Prior
from contracts_v2 import grade

def run(inputs):
 out=e.BASE_OUT/'native-query-extension-v1';art=e.BASE_ART/'native-query-extension-v1'
 assert not (out/'RUN.json').exists(),'FROZEN_NATIVE_QUERY_EXTENSION'
 started=time.process_time();e.STRICT=True
 # This invokes no estimator fit. Rebuild exact qualified prefix inputs.
 e.OUT=out;pool,g,hist,mats=e.setup(inputs)
 from data_v2 import load,History
 d,oldg,teams=load(inputs);later=e.ROOT/'prospective/runs/C-FWD-v4-20261105-W09-JAXBAL-remainder/sources';dd,gg,tt=load(later)
 d=pd.concat([d,dd[(dd.season==2026)&(dd.week==8)]],ignore_index=True);teams=pd.concat([teams,tt[(tt.season==2026)&(tt.week==8)]],ignore_index=True)
 cols=['game_id','team','season','week','attempts','completions','targets'];old=pd.read_csv(inputs/'facts.csv.gz',usecols=cols);new=pd.read_csv(later/'facts.csv.gz',usecols=cols);new=new[(new.season==2026)&(new.week==8)];counts={}
 for (game,team),f in pd.concat([old,new]).groupby(['game_id','team'],sort=False):
  x=f[['attempts','completions','targets']].to_numpy(float);counts[(game,team)]=dict(zip(['attempts','completions','targets'],x.sum(axis=0)));counts[(game,team)]['complete']=bool(np.isfinite(x).all() and (x>=0).all() and np.equal(x,np.floor(x)).all())
 from context_sources_c01 import pbp_path
 frames=[pd.read_csv(pbp_path(year),low_memory=False) for year in [2025,2026]];context=Context(frames,d,g,strict=True,all_position_counts=counts);thist=History(teams,'team')
 cases=e.read(e.ROOT/'artifacts/predictive-C01/APPROVED_OFFER_CASES.json.gz')['cases'];original=e.read(e.BASE_ART/'v1.1/EXACT_OFFER_ROWS.json.gz');held={r['offer_id'] for r in original if r['selected_side'] is None};assert len(held)==22
 crosspath=e.ROOT/'sources/propline-v7/historical_identity_crosswalk.json.gz';cross=e.read(crosspath);events=e.read(e.ROOT/'sources/propline-v7/event_native_schedule.json.gz');proofs=[];newrows=[];feature_export=[]
 refs=e.read(e.ROOT/'artifacts/predictive-C01/REUSED_REFERENCE.json.gz');run=e.read(e.BASE_OUT/'v1.1/RUN.json')
 def model(oid,arm):
  paths=[p for p in run['models'] if Path(p).name==f'{oid}-{arm}.json.gz'];assert len(paths)==1
  p=e.ROOT/paths[0];assert e.sha(p)==run['models'][paths[0]];return e.read(p)['model']
 schedule={r['game_id']:r for r in g.to_dict('records')}
 for case in cases:
  if case['offer_id'] not in held:continue
  ids=[x for x in cross if x['season']==case['season'] and x['week']==case['week'] and x['player_id']==case['player_id']]
  assert len(ids)==1,'NATIVE_HISTORICAL_ROSTER_MAPPING_NOT_UNIQUE';identity=ids[0];gg=schedule[case['game_id']];assert identity['team'] in [gg['home_team'],gg['away_team']]
  # The missing native team is precisely the old hold. Resolve from the
  # pre-existing source roster projection, never from final box-score presence.
  assert case['team'] is None or case['team']==identity['team'],'CONFLICTING_NATIVE_TEAM'
  case=dict(case,team=identity['team'],position=identity['position'])
  q=dict(game_id=case['game_id'],player_id=case['player_id'],team=case['team'],opponent_team=gg['away_team'] if case['team']==gg['home_team'] else gg['home_team'],position=case['position'],season=2026,week=case['week'],home_team=gg['home_team'],kickoff=gg['kickoff'],available=None,values={'rec':None},played=False)
  base=np.asarray(vector(q,'rec',hist,thist,'E0_OP'));own,opp,inter=context.features(q);x={'E0':base,'E1':np.r_[base,own],'E2':np.r_[base,own,opp],'E3':np.r_[base,own,opp,inter]};oid=f"2026-W{case['week']:02}";past=[h['values']['rec'] for h in hist.before(q['player_id'],q['kickoff'],100000) if h['values']['rec'] is not None][-8:];law=e.empirical_law(past,Prior(past,'count')) if len(past)>=8 else None;idsnow=np.asarray([[q['player_id'],q['team'],q['opponent_team']]])
  for arm in ['E0','E1','E2','E3','P1','P2','P3']:
   mean=median=None;fallback=arm=='P3' and law is None
   if arm=='E0':p=e.hgb_probs(refs['direct_models'][f"C-ALL12-LAW-THRESHOLD-v2.1-rec-H-MULTI-P3_HGB-E0_OP-W{case['week']:02}"],base,case['line'])
   elif arm.startswith('E'):p=e.hgb_probs(model(oid,arm),x[arm],case['line'])
   elif arm=='P3' and law is not None:p=law.probability(case['line']);mean=law.mean();median=law.quantile(.5)
   else:mean=float(e.pooled_mu(model(oid,'P1' if arm=='P3' else arm),x['E2'][None,:],idsnow)[0]);median=float(poisson.ppf(.5,mean));p=e.count_probs(mean,case['line'])
   side='OVER' if p['over']>p['under'] else 'UNDER' if p['under']>p['over'] else 'ABSTAIN';template=next(r for r in original if r['offer_id']==case['offer_id'] and r['method']==arm)
   row=dict(template,team=case['team'],position=case['position'],selected_side=side,probabilities=p,mean=mean,median=median,fallback=fallback,status='ABSTAIN' if side=='ABSTAIN' else 'UNKNOWN_PARTICIPATION' if case['appearance']!='PLAYED' else grade(case['actual'],case['line'],side),query_status='NEW_SOURCE_QUALIFIED_QUERY_RECONSTRUCTION;NOT_ORIGINAL_SAVED_ISSUANCE',native_query_extension='v1',source_crosswalk_SHA256=e.sha(crosspath))
   if case['actual'] is not None:
    y=case['actual'];truth=dict(under=int(y<case['line']),push=int(y==case['line']),over=int(y>case['line']));row['Brier']=.5*sum((p[k]-truth[k])**2 for k in truth);prob=sum(p[k]*truth[k] for k in truth);row['log_loss']=-math.log(prob) if prob else None;row['infinite_log_loss']=prob==0
   assert e.common.status(row)==row['status'];newrows.append(row)
  proofs.append(dict(offer_id=case['offer_id'],game_id=case['game_id'],roster_identity=identity,event_teams=[gg['home_team'],gg['away_team']],source_commit='68f0a07ff8cc7a1907eb959a999189bfc0c25f06',input_values_required=False))
  feature_export.append(dict(offer_id=case['offer_id'],game_id=q['game_id'],player_id=q['player_id'],base=base,own=own,opponent=opp,interactions=inter,cutoff=q['kickoff']))
 full=[r for r in original if r['offer_id'] not in held]+newrows;assert len(full)==len(original)
 e.write(art/'NEW_QUERY_ROWS.json.gz',newrows);e.write(art/'FULL_OFFER_ROWS.json.gz',full);e.write(art/'FEATURES.json.gz',feature_export);e.write(out/'ADMISSION.json',dict(crosswalk_path=str(crosspath.relative_to(e.ROOT)),crosswalk_SHA256=e.sha(crosspath),source_events_SHA256=e.sha(e.ROOT/'sources/propline-v7/event_native_schedule.json.gz'),proofs=proofs,old_22_holds_preserved=True,qualified_clock='Retrospective native-week projection;not authenticated C pregame issuance',raw_roster_recovery='Original rosterSHA retained in projected rows;entire raw roster not newly restored'))
 e.write(out/'RUN.json',dict(id='C-CONTEXT-NATIVE-QUERY-EXTENSION-v1',created_UTC=e.now(),new_fits=0,queries=len(proofs),method_views=len(newrows),CPU_seconds=time.process_time()-started,unchanged_original_available_rows=len(original)-len(newrows),old_mask_view_preserved=True,no_extra_source_collection=True))
 print(e.read(out/'RUN.json'))
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--inputs',type=Path,required=True);a=p.parse_args();run(a.inputs)
