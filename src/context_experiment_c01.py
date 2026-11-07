"""Finite C-owned target-context and personalization comparison.

Saved primitive models only. Football outcome training is separated from exact
offered thresholds and later labels; original C forecasts are never rewritten.
"""
import argparse,gzip,hashlib,json,math,resource,signal,time,warnings
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import sparse
from scipy.stats import poisson
from sklearn.linear_model import PoissonRegressor
from sklearn.preprocessing import OneHotEncoder
from threadpoolctl import threadpool_limits
from data_v2 import load,History,vector
from laws_v2 import ThresholdModel,Law,Prior,medians,design
from reliability_v8 import hgb_export,hgb_cdf
from contracts_v2 import thresholds_for_line
from context_features_c01 import Context,OWN_NAMES,OPP_NAMES,INTER_NAMES
from context_sources_c01 import guard
import abc_championship_v2 as common

ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'artifacts/player-context-matchup-01';OUT=ROOT/'reports/player-context-matchup-01'
def now():return datetime.now(timezone.utc).isoformat()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple,np.ndarray)):return [clean(v) for v in x]
 if isinstance(x,(np.integer,)):return int(x)
 if isinstance(x,(float,np.floating)):return float(x) if math.isfinite(x) else None
 if isinstance(x,np.bool_):return bool(x)
 return x
def write(p,x):
 p.parent.mkdir(parents=True,exist_ok=True);b=(json.dumps(clean(x),separators=(',',':'),allow_nan=False)+'\n').encode();p.write_bytes(gzip.compress(b,mtime=0) if p.suffix=='.gz' else b)
def read(p):
 b=Path(p).read_bytes();return json.loads(gzip.decompress(b) if str(p).endswith('.gz') else b)
def fingerprint(x,y):return hashlib.sha256(np.nan_to_num(x,nan=999999.).tobytes()+y.tobytes()).hexdigest()
def hgb_probs(model,f,line):
 u,o,_=thresholds_for_line(line,1);p=hgb_cdf(model,f,[u,o]);p=[0. if k<0 else v for k,v in zip([u,o],p)]
 return dict(under=p[0],push=max(0.,p[1]-p[0]),over=1-p[1])
def count_probs(mu,line):
 u,o,_=thresholds_for_line(line,1);a=float(poisson.cdf(u,mu));b=float(poisson.cdf(o,mu));return dict(under=a,push=max(0.,b-a),over=float(poisson.sf(o,mu)))
def empirical_law(ys,prior):
 v,c=np.unique(np.asarray(ys,int),return_counts=True);return Law(v,c,prior,alpha=.05)
def setup(inputs):
 t=time.process_time();d,g,teams=load(inputs)
 # Preserve the exact W1-W7 source prefix; append only independently retained
 # W8 facts from the genuine W9 source capture, never replace earlier labels.
 later=ROOT/'prospective/runs/C-FWD-v4-20261105-W09-JAXBAL-remainder/sources'
 dd,gg,tt=load(later)
 extra=dd[(dd.season==2026)&(dd.week==8)].copy()
 assert not d[(d.season==2026)&(d.week==8)].shape[0]
 d=pd.concat([d,extra],ignore_index=True);teams=pd.concat([teams,tt[(tt.season==2026)&(tt.week==8)]],ignore_index=True)
 g=pd.concat([g[~((g.season==2026)&(g.week==8))],gg[(gg.season==2026)&(gg.week==8)]],ignore_index=True)
 write(OUT/'FOOTBALL_INPUT_BINDINGS.json',dict(original_facts_SHA256=sha(inputs/'facts.csv.gz'),original_schedule_SHA256=sha(inputs/'schedule.csv'),append_W8_source=str(later.relative_to(ROOT)),append_source_manifest_SHA256=sha(later/'SOURCE_MANIFEST.json'),appended_rows=len(extra),old_rows_replaced=0))
 frames=[pd.read_csv(ROOT/f'sources/player-context-matchup-01/pbp_facts_{year}.csv.gz',low_memory=False) for year in [2025,2026]]
 context=Context(frames,d,g)
 hist,thist=History(d[d.season>=2022],'player_id'),History(teams[teams.season>=2022],'team')
 fields=['game_id','player_id','team','opponent_team','position','season','week','home_team','kickoff','available','values','played']
 pool=d.loc[d.position.isin(['RB','WR','TE']),fields].to_dict('records')
 base=np.asarray([vector(r,'rec',hist,thist,'E0_OP') for r in pool])
 groups=[context.features(r) for r in pool];own=np.asarray([v[0] for v in groups]);opp=np.asarray([v[1] for v in groups]);inter=np.asarray([v[2] for v in groups])
 matrices={'E0':base,'E1':np.column_stack([base,own]),'E2':np.column_stack([base,own,opp]),'E3':np.column_stack([base,own,opp,inter])}
 write(OUT/'DENOMINATOR_AUDIT.json',dict(team_games=context.quality,player_context_games=len(context.raw_player_games),targeted_player_reception_matches=sum(r['receptions_match'] for r in context.raw_player_games),source_mismatch_policy='Keep forecast/label membership; unmatched context missing or explicitly flagged, never replace source counts',preprocessing_CPU_seconds=time.process_time()-t))
 write(OUT/'INPUT_SCHEMA.json',dict(id='C-TARGET-CONTEXT-v1',base='Exact32 retained E0_OP input order',own=dict(zip(OWN_NAMES,['Earlier player target/context proxy']*len(OWN_NAMES))),opponent=dict(zip(OPP_NAMES,['Earlier offense-adjusted opponent response']*len(OPP_NAMES))),interactions=INTER_NAMES,units='Counts; days; yards; unitless denominator-bound rates; no receiver alignment/routes',historical_availability='Declared kickoff+7day current-vintage reconstruction; not observed historical clocks',no_future_actual_required=True))
 return pool,g,hist,matrices
def pooled_fit(x,y,identities,partial):
 m=medians(x);z=design(x,m);center=z.mean(axis=0);scale=np.maximum(z.std(axis=0),1.);z=(z-center)/scale
 encoder=None
 if partial:
  encoder=OneHotEncoder(handle_unknown='ignore',sparse_output=True,dtype=float);cat=encoder.fit_transform(identities);xx=sparse.hstack([sparse.csr_matrix(z),cat],format='csr')
 else:xx=z
 fitted=PoissonRegressor(alpha=.1,max_iter=120,tol=1e-7).fit(xx,y)
 return dict(type='L2_POOLED_POISSON',partial=partial,impute=m.tolist(),center=center.tolist(),scale=scale.tolist(),coef=fitted.coef_.tolist(),intercept=float(fitted.intercept_),categories=[v.tolist() for v in encoder.categories_] if encoder else [],iterations=int(fitted.n_iter_),converged=fitted.n_iter_<120,alpha=.1)
def pooled_mu(model,x,ids):
 z=(design(x,np.asarray(model['impute']))-model['center'])/model['scale'];coef=np.asarray(model['coef']);eta=z@coef[:z.shape[1]]+model['intercept'];offset=z.shape[1]
 for col,values in enumerate(model['categories']):
  mapping={v:i for i,v in enumerate(values)}
  for j,row in enumerate(ids):
   i=mapping.get(row[col]);eta[j]+=coef[offset+i] if i is not None else 0.
  offset+=len(values)
 assert np.all(np.isfinite(eta)) and np.max(eta)<700
 return np.exp(eta)
def run(inputs):
 assert not (OUT/'RUN.json').exists(),'COMPLETED_RUN_FROZEN'
 ART.mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
 ledgerpath=OUT/'FIT_LEDGER.json';ledger=read(ledgerpath) if ledgerpath.exists() else dict(HGB_attempts=0,count_attempts=0,CPU_seconds=20.14275997,failures=[],completed=[])
 cpu=time.process_time();wall=time.monotonic();signal.signal(signal.SIGPROF,lambda *_:(_ for _ in ()).throw(RuntimeError('CPU_CAP')));signal.setitimer(signal.ITIMER_PROF,max(.1,900-ledger['CPU_seconds']))
 predictions=[];numerical=[];features=[];models={};receipts=[]
 try:
  guard();pool,g,hist,mats=setup(inputs);keys={(r['game_id'],r['player_id']):i for i,r in enumerate(pool)}
  cases=read(ROOT/'artifacts/predictive-C01/APPROVED_OFFER_CASES.json.gz')['cases'];refs=read(ROOT/'artifacts/predictive-C01/REUSED_REFERENCE.json.gz')
  grids=[0,1,2,3,4,5,7];origins=[(2025,w) for w in range(1,9)]+[(2026,w) for w in range(1,9)]
  for season,week in origins:
   oid=f'{season}-W{week:02}';cut=float(g.loc[(g.season==season)&(g.week==week),'kickoff'].min())
   train=[i for i,r in enumerate(pool) if r['season']>=2022 and r['available']<cut and r['values']['rec'] is not None]
   query=[i for i,r in enumerate(pool) if r['season']==season and r['week']==week]
   y=np.asarray([pool[i]['values']['rec'] for i in train]);membership=[dict(game_id=pool[i]['game_id'],player_id=pool[i]['player_id']) for i in train];membership_hash=hashlib.sha256(json.dumps(membership,separators=(',',':')).encode()).hexdigest()
   arm_models={}
   for arm in ['E1','E2','E3']:
    path=ART/f'{oid}-{arm}.json.gz';x=mats[arm][train];fp=fingerprint(x,y)
    if path.exists():
     p=read(path);assert p['training_fingerprint']==fp and p['membership_SHA256']==membership_hash;model=p['model']
    else:
     assert ledger['HGB_attempts']<48;ledger['HGB_attempts']+=1;write(ledgerpath,ledger);guard()
     with threadpool_limits(limits=1):fitted=ThresholdModel('MONOTONE_HGB',False,grids).fit(x,y)
     model=hgb_export(fitted);sample=mats[arm][query[:8]]
     assert np.allclose(fitted.cdfs(sample,grids),np.asarray([hgb_cdf(model,f,grids) for f in sample]),rtol=0,atol=1e-12)
     write(path,dict(model=model,training_fingerprint=fp,membership_SHA256=membership_hash,training_rows=len(train),fit_cutoff_UTC=pd.Timestamp(cut,unit='s',tz='UTC').isoformat(),protocol_SHA256=sha(ROOT/'protocol/PLAYER_CONTEXT_MATCHUP_01_C_V1.json'),fit_code_SHA256=sha(__file__)))
    arm_models[arm]=model;models[str(path.relative_to(ROOT))]=sha(path)
   pmodels={};mus={};ids=np.asarray([[r['player_id'],r['team'],r['opponent_team']] for r in pool])
   if season==2026:
    for label,partial in [('P1',False),('P2',True)]:
     path=ART/f'{oid}-{label}.json.gz';x=mats['E2'][train];fp=fingerprint(x,y)
     if path.exists():
      p=read(path);assert p['training_fingerprint']==fp and p['membership_SHA256']==membership_hash;model=p['model']
     else:
      assert ledger['count_attempts']<16;ledger['count_attempts']+=1;write(ledgerpath,ledger)
      with threadpool_limits(limits=1):model=pooled_fit(x,y,ids[train],partial)
      write(path,dict(model=model,training_fingerprint=fp,membership_SHA256=membership_hash,fit_cutoff_UTC=pd.Timestamp(cut,unit='s',tz='UTC').isoformat(),protocol_SHA256=sha(ROOT/'protocol/PLAYER_CONTEXT_MATCHUP_01_C_V1.json')))
     pmodels[label]=model;mus[label]=dict(zip(query,pooled_mu(model,mats['E2'][query],ids[query])));models[str(path.relative_to(ROOT))]=sha(path)
   # Count laws are complete distributions; classifiers are not numerical models.
   prior=Prior(y,'count')
   for i in query:
    r=pool[i];past=[h['values']['rec'] for h in hist.before(r['player_id'],r['kickoff'],8) if h['values']['rec'] is not None]
    ownlaw=empirical_law(past,prior) if len(past)>=8 else None
    if season==2026:
     for label in ['P1','P2','P3']:
      mu=mus[label][i] if label in mus else ownlaw.mean() if ownlaw else mus['P1'][i]
      med=float(poisson.ppf(.5,mu)) if label!='P3' or ownlaw is None else ownlaw.quantile(.5)
      actual=r['values']['rec'];numerical.append(dict(origin=oid,procedure=label,game_id=r['game_id'],player_id=r['player_id'],position=r['position'],mean=mu,median=med,actual=actual,known=actual is not None,fallback=label=='P3' and ownlaw is None,player_history_support=len(past)))
    features.append(dict(origin=oid,game_id=r['game_id'],player_id=r['player_id'],team=r['team'],opponent=r['opponent_team'],position=r['position'],kickoff_UTC=pd.Timestamp(r['kickoff'],unit='s',tz='UTC').isoformat(),own=mats['E1'][i][32:].tolist(),opponent_values=mats['E2'][i][-6:].tolist(),predicted_mix_interactions=mats['E3'][i][-2:].tolist()))
   # Actual offers are never rounded/interpolated to a training grid.
   offered=[c for c in cases if c['season']==season and c['week']==week]
   for case in offered:
    i=keys.get((case['game_id'],case['player_id']));base=dict(case);base.pop('retained_methods',None)
    for method in ['E0','E1','E2','E3','P1','P2','P3']:
     p=None;fallback=False;mean=median=None
     if i is not None:
      r=pool[i]
      if method=='E0':
       original=refs['references'].get('rec|'+r['game_id']+'|'+r['player_id'])
       assert original and np.allclose(mats['E0'][i],np.asarray(original['saved']['features'],float),rtol=0,atol=1e-10,equal_nan=True),'RETAINED_CONTROL_FEATURE_MISMATCH'
       model=refs['direct_models'][f'C-ALL12-LAW-THRESHOLD-v2.1-rec-H-MULTI-P3_HGB-E0_OP-W{week:02}'];p=hgb_probs(model,mats['E0'][i],case['line'])
      elif method.startswith('E'):p=hgb_probs(arm_models[method],mats[method][i],case['line'])
      else:
       past=[h['values']['rec'] for h in hist.before(r['player_id'],r['kickoff'],8) if h['values']['rec'] is not None];law=empirical_law(past,prior) if len(past)>=8 else None
       fallback=method=='P3' and law is None
       if method=='P3' and law is not None:p=law.probability(case['line']);mean=law.mean();median=law.quantile(.5)
       else:
        mean=mus['P1' if method=='P3' else method][i];median=float(poisson.ppf(.5,mean));p=count_probs(mean,case['line'])
     side=None if p is None else 'OVER' if p['over']>p['under'] else 'UNDER' if p['under']>p['over'] else 'ABSTAIN'
     row=dict(base,procedure='C::PLAYER-CONTEXT-MATCHUP-01::'+method,method=method,selected_side=side,probabilities=p,fallback=fallback,mean=mean,median=median,status='UNAVAILABLE_FORECAST' if side is None else 'ABSTAIN' if side=='ABSTAIN' else 'UNKNOWN_PARTICIPATION' if case['appearance']!='PLAYED' else 'MISSING_ACTUAL' if case['actual'] is None else 'PUSH' if case['actual']==case['line'] else 'WIN' if (case['actual']>case['line'])==(side=='OVER') else 'LOSS',comparator='OVER_UNDER',evidence_tier='TIMING_UNVERIFIED_ACTUAL_LINE_RECONSTRUCTION',settlement='UNVERIFIED')
     if p:
      assert min(p.values())>=-1e-12 and abs(sum(p.values())-1)<1e-10
      if case['actual'] is not None:
       yv=case['actual'];truth=dict(under=int(yv<case['line']),push=int(yv==case['line']),over=int(yv>case['line']));row['Brier']=.5*sum((p[k]-truth[k])**2 for k in truth);prob=sum(p[k]*truth[k] for k in truth);row['log_loss']=-math.log(prob) if prob else None;row['infinite_log_loss']=prob==0
     assert common.status(row)==row['status'];predictions.append(row)
   receipts.append(dict(origin=oid,fit_cutoff_UTC=pd.Timestamp(cut,unit='s',tz='UTC').isoformat(),training_rows=len(train),membership_SHA256=membership_hash,query_rows=len(query),latest_training_available=max(pool[i]['available'] for i in train),HGB_arms=['E1','E2','E3'],personalization_arms=list(pmodels)))
   if oid not in ledger['completed']:ledger['completed'].append(oid)
   write(ledgerpath,ledger);guard();assert resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024<=1288490188,'RSS_CAP';assert time.monotonic()-wall<=1500,'WALL_CAP'
  write(ART/'EXACT_OFFER_ROWS.json.gz',predictions);write(ART/'NUMERICAL_ROWS.json.gz',numerical);write(ART/'FEATURE_EXPORT.json.gz',features)
  write(OUT/'RUN.json',dict(id='PLAYER-CONTEXT-MATCHUP-01-C-v1',created_UTC=now(),origins=receipts,models=models,new_HGB_fits=ledger['HGB_attempts'],new_count_fits=ledger['count_attempts'],CPU_seconds=ledger['CPU_seconds']+time.process_time()-cpu,wall_seconds=time.monotonic()-wall,peak_RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,actual_offer_method_rows=len(predictions),numerical_method_rows=len(numerical),query_rows=len(features),old_forecasts_changed=0,new_paper_picks=0,source_tier='CURRENT_REVISED_7DAY_RECONSTRUCTION',five_week='Numerical/tested-origin support must be counted per product; actual lines remain two weeks',ninety_percent='TARGET_NOT_ESTABLISHED'))
  print(read(OUT/'RUN.json'))
 except Exception as e:
  ledger['failures'].append(dict(created_UTC=now(),error=str(e)));raise
 finally:
  signal.setitimer(signal.ITIMER_PROF,0);ledger['CPU_seconds']+=time.process_time()-cpu;write(ledgerpath,ledger)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--inputs',type=Path,required=True);a=p.parse_args();run(a.inputs)
