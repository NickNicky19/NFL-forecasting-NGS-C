"""Finite earlier-chosen receiving-context window comparison, C-owned.

New2024warmstart, exact4/8/16 own-context windows; team/opponent windows fixed8.
No completed HGB experiment or old forecast/model is overwritten or refitted.
"""
import argparse,collections,gzip,hashlib,json,math,resource,signal,time,zipfile
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import poisson
from threadpoolctl import threadpool_limits
from data_v2 import load,History,vector
from context_features_c01 import Context,OWN_NAMES,OPP_NAMES
from context_sources_c01 import pbp_path,guard
from context_experiment_c01 import pooled_fit,pooled_mu,fingerprint,count_probs
from context_identity_view_c01 import corrected_rows
from laws_v2 import LeafModel
from safe_models_v4 import export_forest,infer_forest,law_data
import abc_championship_v2 as common
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'reports/player-context-matchup-01/completion-decision-v1'
OUT=BASE/'lookback';ART=ROOT/'artifacts/player-context-matchup-01/completion-decision-v1/lookback'
SOURCE24=ROOT/'sources/player-context-matchup-01/completion-decision-v1/pbp_facts_2024.csv.xz'
INPUTS=Path('/workspace/c-v2/corrected-inputs')
def now():return pd.Timestamp.now(tz='UTC').isoformat()
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple,np.ndarray)):return [clean(v) for v in x]
 if isinstance(x,(np.integer,)):return int(x)
 if isinstance(x,(np.bool_,)):return bool(x)
 if isinstance(x,(float,np.floating)):return float(x) if math.isfinite(x) else None
 return x
def write(p,x):
 p.parent.mkdir(parents=True,exist_ok=True);b=(json.dumps(clean(x),separators=(',',':'),allow_nan=False)+'\n').encode();p.write_bytes(gzip.compress(b,mtime=0) if p.suffix=='.gz' else b)
def read(p):
 b=p.read_bytes();return json.loads(gzip.decompress(b) if str(p).endswith('.gz') else b)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def prep():
 assert SOURCE24.exists(),'QUALIFIED_2024_CONTEXT_SOURCE_REQUIRED'
 d,g,teams=load(INPUTS);late=ROOT/'prospective/runs/C-FWD-v4-20261105-W09-JAXBAL-remainder/sources';dd,gg,tt=load(late)
 d=pd.concat([d,dd[(dd.season==2026)&(dd.week==8)]],ignore_index=True);teams=pd.concat([teams,tt[(tt.season==2026)&(tt.week==8)]],ignore_index=True);g=pd.concat([g[~((g.season==2026)&(g.week==8))],gg[(gg.season==2026)&(gg.week==8)]],ignore_index=True)
 cols=['game_id','team','season','week','attempts','completions','targets'];old=pd.read_csv(INPUTS/'facts.csv.gz',usecols=cols);new=pd.read_csv(late/'facts.csv.gz',usecols=cols);allrows=pd.concat([old,new[(new.season==2026)&(new.week==8)]]);counts={}
 for (game,team),f in allrows.groupby(['game_id','team'],sort=False):
  a=f[['attempts','completions','targets']].to_numpy(float);counts[(game,team)]=dict(zip(['attempts','completions','targets'],a.sum(axis=0)));counts[(game,team)]['complete']=bool(np.isfinite(a).all() and (a>=0).all() and np.equal(a,np.floor(a)).all())
 frames=[pd.read_csv(SOURCE24,low_memory=False)]+[pd.read_csv(pbp_path(y),low_memory=False) for y in [2025,2026]]
 context=Context(frames,d,g,strict=True,all_position_counts=counts);hist=History(d[d.season>=2022],'player_id');th=History(teams[teams.season>=2022],'team')
 pool=d[d.position.isin(['RB','WR','TE'])].to_dict('records');base=np.asarray([vector(r,'rec',hist,th,'E0_OP') for r in pool]);own={w:np.asarray([context.own(r,w) for r in pool]) for w in [4,8,16]};opp=np.asarray([context.features(r)[1] for r in pool]);mats={'ordinary':base,**{str(w):np.c_[base,own[w],opp] for w in [4,8,16]}}
 # Genuinely available history: report differing windows, not fictitious8/16ties.
 distinct=[]
 for year in [2025,2026]:
  for week in range(1,9):
   ix=[i for i,r in enumerate(pool) if r['season']==year and r['week']==week and r['position'] in ['WR','TE']]
   distinct.append(dict(season=year,week=week,rows=len(ix),own4_vs8_different=sum(not np.array_equal(own[4][i],own[8][i],equal_nan=True) for i in ix),own8_vs16_different=sum(not np.array_equal(own[8][i],own[16][i],equal_nan=True) for i in ix),max_qualified_context_games16=max((own[16][i][0] for i in ix),default=0)))
 write(OUT/'INPUT_BINDINGS.json',dict(facts_sha=sha(INPUTS/'facts.csv.gz'),schedule_sha=sha(INPUTS/'schedule.csv'),source24_sha=sha(SOURCE24),source25_sha=sha(pbp_path(2025)),source26_sha=sha(pbp_path(2026)),append_W8_source=sha(late/'SOURCE_MANIFEST.json'),context_source='2024-2026PBP;ordinaryhistory2022expanding;strict7daycurrentvintage',own_windows=[4,8,16],fixed_team_opponent_window=8,old_scientific_outputs_changed=0));write(OUT/'WINDOW_DISTINCTNESS.json',distinct)
 return pool,g,hist,th,context,mats

def numeric_summary(rows,methods,mask=None):
 out=[]
 for scope,roles in [('WR_TE',['WR','TE']),('ALL_SUPPORTED',['RB','WR','TE']),('RB',['RB'])]:
  for period in ['ALL']+list(range(1,9)):
   rr=[r for r in rows if r['position'] in roles and (period=='ALL' or r['week']==period) and (mask is None or (r['game_id'],r['player_id']) in mask)]
   for method in methods:
    available=[r for r in rr if r.get(method) is not None];known=[r for r in available if r['actual'] is not None]
    z=dict(scope=scope,week=period,method=method,eligible=len(rr),available=len(available),known=len(known),unknown=len(available)-len(known),unavailable=len(rr)-len(available),games=len({r['game_id'] for r in known}),actual_weeks=sorted({r['week'] for r in known}),fallback_known=sum(r.get('fallback',{}).get(method,False) for r in known))
    if known:
     mean=np.asarray([r[method]['mean']-r['actual'] for r in known]);med=np.asarray([r[method]['median']-r['actual'] for r in known]);per=collections.defaultdict(list)
     for r in known:per[r['player_id']].append(abs(r[method]['median']-r['actual']))
     z.update(median_MAE=float(np.mean(abs(med))),mean_MAE=float(np.mean(abs(mean))),mean_RMSE=float(np.sqrt(np.mean(mean**2))),mean_bias=float(np.mean(mean)),equal_player_median_MAE=float(np.mean([np.mean(v) for v in per.values()])))
    out.append(z)
 return out

def run(pilot=False):
 assert not (OUT/'RUN.json').exists(),'COMPLETED_LOOKBACK_RUN_FROZEN';OUT.mkdir(parents=True,exist_ok=True);ART.mkdir(parents=True,exist_ok=True)
 ledgerpath=OUT/'FIT_LEDGER.json';ledger=read(ledgerpath) if ledgerpath.exists() else dict(count_attempts=[],Leaf_attempts=[],completed=[],failures=[],CPU_seconds=0)
 cpu=time.process_time();wall=time.monotonic();signal.signal(signal.SIGPROF,lambda *_:(_ for _ in ()).throw(RuntimeError('LOOKBACK_CPU_CAP')));signal.setitimer(signal.ITIMER_PROF,max(.01,900-ledger['CPU_seconds']))
 def checkpoint():
  nonlocal cpu
  current=time.process_time();ledger['CPU_seconds']+=current-cpu;cpu=current;write(ledgerpath,ledger);guard();assert ledger['CPU_seconds']<900;assert resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024<=1288490188
  assert time.monotonic()-wall<1500
 def fit_model(origin,arm,train,y,membership,mats):
  path=ART/f'{origin}-{arm}.json.gz';x=mats[arm][train];fp=fingerprint(x,y);mh=hashlib.sha256(json.dumps(membership,separators=(',',':')).encode()).hexdigest()
  if path.exists():
   item=read(path);assert item['fingerprint']==fp and item['membership_SHA256']==mh;return item['model']
  assert len(ledger['count_attempts'])<48;key=origin+'-'+arm;assert key not in ledger['count_attempts'],'PREVIOUS_ATTEMPT_NOT_RECOVERABLE';ledger['count_attempts'].append(key);checkpoint()
  with threadpool_limits(limits=1):model=pooled_fit(x,y,None,False)
  write(path,dict(model=model,origin=origin,arm=arm,fingerprint=fp,membership_SHA256=mh,rows=len(y),code_SHA256=sha(Path(__file__)),protocol_SHA256=sha(ROOT/'protocol/PLAYER_CONTEXT_COMPLETION_DECISION_01_C.json')));checkpoint();return model
 try:
  pool,g,hist,th,context,mats=prep();checkpoint();index={(r['game_id'],r['player_id']):i for i,r in enumerate(pool)}
  def origin(year,week):
   cut=float(g.loc[(g.season==year)&(g.week==week),'kickoff'].min());train=[i for i,r in enumerate(pool) if r['available']<cut and r['values']['rec'] is not None];query=[i for i,r in enumerate(pool) if r['season']==year and r['week']==week];y=np.array([pool[i]['values']['rec'] for i in train]);membership=[(pool[i]['game_id'],pool[i]['player_id']) for i in train];return cut,train,query,y,membership
  if pilot:
   assert not (OUT/'PILOT.json').exists(),'PILOT_ALREADY_COMPLETED'
   cut,train,query,y,membership=origin(2025,1);model=fit_model('2025-W01','4',train,y,membership,mats);checkpoint()
   write(OUT/'PILOT.json',dict(origin='2025-W01',window=4,training_rows=len(train),query_rows=len(query),CPU_seconds=ledger['CPU_seconds'],wall_seconds=time.monotonic()-wall,peak_RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,model_bytes=(ART/'2025-W01-4.json.gz').stat().st_size,scored_outcomes=0,decision='Finite remaining run fitswithinregisteredbudget;source2024windowdifferences separatelyquantified'))
   print('LOOKBACK_PILOT',read(OUT/'PILOT.json'));return
  val=[];origin_records=[]
  for week in range(1,9):
   oid=f'2025-W{week:02}';cut,train,query,y,membership=origin(2025,week);means={}
   for window in [4,8,16]:
    model=fit_model(oid,str(window),train,y,membership,mats);means[window]=pooled_mu(model,mats[str(window)][query],None)
   for j,i in enumerate(query):
    r=pool[i];val.append(dict(game_id=r['game_id'],player_id=r['player_id'],position=r['position'],week=week,actual=r['values']['rec'],**{str(w):dict(mean=float(means[w][j]),median=float(poisson.ppf(.5,means[w][j]))) for w in [4,8,16]}))
   origin_records.append(dict(origin=oid,cutoff=cut,latest_training_available=max(pool[i]['available'] for i in train),training_rows=len(train),query_rows=len(query)));checkpoint()
  scores=numeric_summary(val,['4','8','16']);aggregates=[r for r in scores if r['scope']=='WR_TE' and r['week']=='ALL'];ranks=sorted(aggregates,key=lambda r:(round(r['median_MAE'],12),{8:0,4:1,16:2}[int(r['method'])]));chosen=int(ranks[0]['method'])
  write(ART/'VALIDATION_PREDICTIONS.json.gz',val);write(OUT/'VALIDATION_SCORES.json',scores)
  selection=dict(created_UTC=now(),period='2025W1-W8 rolling-origin, exposeddevelopment',objective='WRTEfullgame lower-medianMAE on all knownqueryrows;noofferedlineobjectiveavailable',selected_own_appearances=chosen,team_opponent_window=8,ranked=aggregates,tie_rule='1e-12prefer8then4then16',frozen_before_2026_evaluation=True)
  if (OUT/'SELECTION.json').exists():assert read(OUT/'SELECTION.json')['selected_own_appearances']==chosen
  else:write(OUT/'SELECTION.json',selection)
  checkpoint();models={};numerical=[]
  # Retained strongLeafpoint rows are read, never deserialized pickle.
  leaf={ (r['game_id'],r['player_id']):r for r in read(BASE/'intake/C_RETAINED_LEAF_POINTS_W1_W7.json.gz')['rows'] }
  for week in range(1,9):
   oid=f'2026-W{week:02}';cut,train,query,y,membership=origin(2026,week);arms=['ordinary','8']+([str(chosen)] if chosen!=8 else []);mm={arm:fit_model(oid,arm,train,y,membership,mats) for arm in arms};models[week]=mm
   predictions={arm:pooled_mu(model,mats[arm][query],None) for arm,model in mm.items()}
   leaf_laws=None
   if week==8:
    path=ART/'2026-W08-retainedLeafExtension.json.gz';fp=fingerprint(mats['ordinary'][train],y);roles=np.array([pool[i]['position'] for i in train]);qr=np.array([pool[i]['position'] for i in query])
    if path.exists():item=read(path);assert item['fingerprint']==fp;leaf_laws=infer_forest(item['model'],mats['ordinary'][query],qr)
    else:
     assert len(ledger['Leaf_attempts'])<1;ledger['Leaf_attempts'].append(oid);checkpoint()
     with threadpool_limits(limits=1):lm=LeafModel('count',1).fit(mats['ordinary'][train],y,roles)
     data=export_forest(lm);leaf_laws=lm.laws(mats['ordinary'][query],qr);replay=infer_forest(data,mats['ordinary'][query[:3]],qr[:3]);assert all(abs(a.mean()-b.mean())<1e-10 for a,b in zip(leaf_laws[:3],replay));write(path,dict(model=data,fingerprint=fp,rows=len(y),origin=oid,method='UNCHANGED32TREE/E0_OP/H-MULTI'))
   for j,i in enumerate(query):
    r=pool[i];a=dict(game_id=r['game_id'],player_id=r['player_id'],position=r['position'],week=week,actual=r['values']['rec'])
    for label,arm in [('ORDINARY','ordinary'),('CONTEXT8','8'),('CHOSEN',str(chosen))]:mu=float(predictions[arm][j]);a[label]=dict(mean=mu,median=float(poisson.ppf(.5,mu)))
    l=leaf.get((r['game_id'],r['player_id']))
    if l:
     a['LEAF']=dict(mean=l['mean'],median=l['median'])
    elif leaf_laws is not None:a['LEAF']=dict(mean=leaf_laws[j].mean(),median=leaf_laws[j].quantile(.5))
    numerical.append(a)
   origin_records.append(dict(origin=oid,cutoff=cut,latest_training_available=max(pool[i]['available'] for i in train),training_rows=len(train),query_rows=len(query)));checkpoint()
  write(ART/'EVALUATION_PREDICTIONS.json.gz',numerical);write(OUT/'NUMERICAL_SCORES.json.gz',numeric_summary(numerical,['ORDINARY','CONTEXT8','CHOSEN','LEAF']))
  cases=[r for r in corrected_rows() if r['method']=='E0'];casepred=[];feature_rows=[]
  sched={r['game_id']:r for r in g.to_dict('records')}
  # Queries come from native offer identity, never target actual requirements.
  for c in cases:
   gg=sched[c['game_id']];q=dict(game_id=c['game_id'],player_id=c['player_id'],team=c['team'],opponent_team=c['opponent_team'],position=c['position'],season=2026,week=c['week'],home_team=gg['home_team'],kickoff=gg['kickoff']);base=np.array(vector(q,'rec',hist,th,'E0_OP'));_,op,_=context.features(q)
   xx={'ordinary':base,**{str(w):np.r_[base,context.own(q,w),op] for w in set([8,chosen])}}
   for method,arm in [('ORDINARY','ordinary'),('CONTEXT8','8'),('CHOSEN',str(chosen))]:
    model=models[c['week']][arm];mu=float(pooled_mu(model,xx[arm][None,:],None)[0]);p=count_probs(mu,c['line']);med=float(poisson.ppf(.5,mu))
    for product in ['LAW','MEAN','MEDIAN']:
     point=mu if product=='MEAN' else med if product=='MEDIAN' else None;side='OVER' if p['over']>p['under'] else 'UNDER' if p['under']>p['over'] else 'ABSTAIN'
     if product!='LAW':side='OVER' if point>c['line'] else 'UNDER' if point<c['line'] else 'ABSTAIN'
     r=dict(c,method=method+'_'+product,procedure='C::RECEIVING-LOOKBACK-C02::'+method+'::'+product,mean=mu,median=med,point=point,point_type=None if product=='LAW' else product.lower(),selected_side=side,probabilities=p if product=='LAW' else None,status='ABSTAIN' if side=='ABSTAIN' else 'UNKNOWN_PARTICIPATION' if c['appearance']!='PLAYED' else 'MISSING_ACTUAL' if c['actual'] is None else 'PUSH' if c['actual']==c['line'] else 'WIN' if (c['actual']>c['line'])==(side=='OVER') else 'LOSS',fallback=False,window=chosen if method=='CHOSEN' else 8 if method=='CONTEXT8' else None)
     if product=='LAW' and c['actual'] is not None:
      truth=dict(under=int(c['actual']<c['line']),push=int(c['actual']==c['line']),over=int(c['actual']>c['line']));r['Brier']=.5*sum((p[k]-truth[k])**2 for k in p)
     assert common.status(r)==r['status'];casepred.append(r)
   feature_rows.append(dict(offer_id=c['offer_id'],game_id=c['game_id'],player_id=c['player_id'],position=c['position'],week=c['week'],actual=c['actual'],ORDINARY=next(r for r in casepred[-9:] if r['method']=='ORDINARY_LAW'),CONTEXT8=next(r for r in casepred[-9:] if r['method']=='CONTEXT8_LAW'),CHOSEN=next(r for r in casepred[-9:] if r['method']=='CHOSEN_LAW')))
  write(ART/'ACTUAL_OFFER_ROWS.json.gz',casepred)
  # Retained compatible actual-line controls stay on exactly matching offers.
  retained=[r for r in corrected_rows() if r['method'] in ['E0','RETAINED_P1_MEAN','RETAINED_P1_MEDIAN','RETAINED_P2_LAW','RETAINED_EARLIER_PREVALENCE_V8','ALWAYS_OVER','ALWAYS_UNDER']]
  scores=[]
  for scope,roles in [('WR_TE',['WR','TE']),('ALL_SUPPORTED',['RB','WR','TE']),('RB',['RB'])]:
   for week in ['ALL',2,3]:
    for method in sorted({r['method'] for r in casepred+retained}):
     rr=[r for r in casepred+retained if r['method']==method and r['position'] in roles and (week=='ALL' or r['week']==week)];z=common.summary(rr);known=[r for r in rr if r['status'] in ['WIN','LOSS']];bp=[r for r in known if r.get('probabilities') and 'Brier' in r];scores.append(dict(scope=scope,week=week,method=method,**z,Brier=sum(r['Brier'] for r in bp)/len(bp) if bp else None,evidence_tier='TIMING_UNVERIFIED_LAST_RECORDED_ACTUAL_LINES',actual_weeks=[2,3] if week=='ALL' else [week]))
  write(OUT/'ACTUAL_LINE_SCORES.json.gz',scores)
  # Numerical exact offered mask, separate from the broader source-row population.
  offnum=[]
  for c in cases:
   rr=[r for r in casepred if r['offer_id']==c['offer_id'] and r['method'].endswith('_LAW')];a=dict(game_id=c['game_id'],player_id=c['player_id'],position=c['position'],week=c['week'],actual=c['actual'])
   for r in rr:a[r['method'].removesuffix('_LAW')]=dict(mean=r['mean'],median=r['median'])
   l=leaf.get((c['game_id'],c['player_id']))
   if l:a['LEAF']=dict(mean=l['mean'],median=l['median'])
   offnum.append(a)
  write(OUT/'OFFERED_NUMERICAL_SCORES.json.gz',numeric_summary(offnum,['ORDINARY','CONTEXT8','CHOSEN','LEAF']))
  pairs=[]
  for scope,roles in [('WR_TE',['WR','TE']),('ALL_SUPPORTED',['RB','WR','TE'])]:
   for cand,control in [('CHOSEN_LAW','CONTEXT8_LAW'),('CHOSEN_LAW','ORDINARY_LAW'),('CONTEXT8_LAW','ORDINARY_LAW'),('CHOSEN_LAW','E0'),('CHOSEN_LAW','RETAINED_P2_LAW'),('CHOSEN_LAW','RETAINED_EARLIER_PREVALENCE_V8')]:
    aa={r['offer_id']:r for r in casepred+retained if r['method']==cand and r['position'] in roles};bb={r['offer_id']:r for r in casepred+retained if r['method']==control and r['position'] in roles};ids=sorted(aa.keys()&bb.keys());ids=[i for i in ids if aa[i]['status'] in ['WIN','LOSS'] and bb[i]['status'] in ['WIN','LOSS']];by=collections.defaultdict(lambda:np.zeros(2))
    for i in ids:by[aa[i]['game_id']]+=[int(aa[i]['status']=='WIN')-int(bb[i]['status']=='WIN'),1]
    ar=np.array(list(by.values()));rng=np.random.default_rng(661107);b=ar[rng.integers(len(ar),size=(2000,len(ar)))].sum(axis=1);ci=np.quantile(b[:,0]/b[:,1],[.025,.975])*100;w=sum(aa[i]['status']=='WIN' for i in ids);v=sum(bb[i]['status']=='WIN' for i in ids)
    pairs.append(dict(scope=scope,candidate=cand,control=control,decided=len(ids),candidate_wins=w,control_wins=v,difference_wins=w-v,difference_pp=100*(w-v)/len(ids),sensitivity95_pp=ci.tolist()))
  write(OUT/'PAIRED_CHANGES.json',pairs);checkpoint()
  write(OUT/'RUN.json',dict(id='C-RECEIVING-LOOKBACK-C02',created_UTC=now(),selected_window=chosen,count_fit_attempts=len(ledger['count_attempts']),Leaf_fit_attempts=len(ledger['Leaf_attempts']),HGBfits=0,CPU_seconds=ledger['CPU_seconds'],wall_seconds=time.monotonic()-wall,peak_RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,origins=origin_records,actual_offer_weeks=[2,3],actual_offers=len(cases),old_models_or_forecasts_changed=0,new_primary_release=False,selection_before_evaluation=True))
  print('LOOKBACK_COMPLETE',chosen,len(ledger['count_attempts']),ledger['CPU_seconds'])
 except Exception as error:
  ledger['failures'].append(dict(at=now(),error=str(error)));write(ledgerpath,ledger);raise
 finally:
  signal.setitimer(signal.ITIMER_PROF,0);ledger['CPU_seconds']+=time.process_time()-cpu;write(ledgerpath,ledger)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--pilot',action='store_true');a=p.parse_args();run(a.pilot)
