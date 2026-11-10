"""C receiving Leaf information increment, registered finite v2 package.

R0 saved complete procedure; R1 support; R2 player values; R3 receiving-defense
values. No closed HGB/Poisson fit is repeated, no unsafe artifact is loaded.
"""
from __future__ import annotations
import argparse,collections,gzip,hashlib,json,lzma,math,resource,signal,time,zipfile
from pathlib import Path
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
import receiving_lookback_c02 as lookback
from context_sources_c01 import guard,pbp_path
from context_features_c01 import OWN_NAMES
from context_identity_view_c01 import corrected_rows
from data_v2 import vector
from laws_v2 import LeafModel
from safe_models_v4 import export_forest,infer_forest,law_data
import abc_championship_v2 as common
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/profile-increment-v2/experiment'
ART=ROOT/'artifacts/profile-increment-v2'
REG=ROOT/'protocol/PROFILE_INCREMENT_TO_RELEASE_01_C_V2.json'
VERSION='C-RECEIVING-PROFILE-INCREMENT-v2'
ARMS=['R1','R2','R3']

def now():return pd.Timestamp.now(tz='UTC').isoformat()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
 p=Path(p);b=p.read_bytes()
 return json.loads(lzma.decompress(b) if p.suffix=='.xz' else gzip.decompress(b) if p.suffix=='.gz' else b)
def write(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 b=(json.dumps(lookback.clean(x),separators=(',',':'),allow_nan=False)+'\n').encode()
 if p.suffix=='.xz':b=lzma.compress(b,preset=6)
 elif p.suffix=='.gz':b=gzip.compress(b,mtime=0)
 p.write_bytes(b)
def fingerprint(x,y):return hashlib.sha256(np.nan_to_num(x,nan=999999.).tobytes()+y.tobytes()).hexdigest()

def prepare():
 # Reuse the already-verified builder without rewriting its frozen reports.
 saved=lookback.write;captured={}
 try:
  lookback.write=lambda p,x:captured.setdefault(str(p.relative_to(ROOT)),lookback.clean(x))
  pool,g,hist,th,context,old=lookback.prep()
 finally:lookback.write=saved
 from receiving_defense_c03 import ReceivingDefense,SUPPORT_NAMES,VALUE_NAMES
 frames=[pd.read_csv(lookback.SOURCE24,low_memory=False)]+[pd.read_csv(pbp_path(y),low_memory=False) for y in [2025,2026]]
 # Pool includes all supported role rows; QB/other facts are used by Context's
 # official completeness checks and the unallocated bucket, never redistributed.
 defense=ReceivingDefense(frames,pd.DataFrame(pool),g,context=context,
  source_bindings={'2024':sha(lookback.SOURCE24),'2025':sha(pbp_path(2025)),'2026':sha(pbp_path(2026))})
 ds=np.array([defense.vector(r) for r in pool],float)
 own=np.array([context.own(r,8) for r in pool]);base=old['ordinary']
 mats={'R0':base,'R1':np.c_[base,own[:,:5],ds[:,:len(SUPPORT_NAMES)]],
       'R2':np.c_[base,own[:,:5],ds[:,:len(SUPPORT_NAMES)],own[:,5:]],
       'R3':np.c_[base,own[:,:5],ds[:,:len(SUPPORT_NAMES)],own[:,5:],ds[:,len(SUPPORT_NAMES):]]}
 from receiving_profiles_c02 import BASE_NAMES
 names={'R0':BASE_NAMES,'R1':BASE_NAMES+OWN_NAMES[:5]+SUPPORT_NAMES,
        'R2':BASE_NAMES+OWN_NAMES[:5]+SUPPORT_NAMES+OWN_NAMES[5:],
        'R3':BASE_NAMES+OWN_NAMES[:5]+SUPPORT_NAMES+OWN_NAMES[5:]+VALUE_NAMES}
 assert all(len(names[k])==v.shape[1] for k,v in mats.items())
 bindings={'underlying_builder_reports_checked_not_rewritten':captured,
  'defense_code_SHA256':sha(ROOT/'src/receiving_defense_c03.py'),
  'old_leaf':{'archive':'artifacts/all12-rec-v2.1.zip','SHA256':sha(ROOT/'artifacts/all12-rec-v2.1.zip')},
  'information_policy':'CURRENT_REVISED_KICKOFF_PLUS7D_STRICT_RECONSTRUCTION;NOT_AUTHENTICATED_VINTAGES',
  'ordinary_source_rows_conditioned_history':True,'source_2024':sha(lookback.SOURCE24),
  'source_2025':sha(pbp_path(2025)),'source_2026':sha(pbp_path(2026))}
 return pool,g,hist,th,context,defense,mats,names,bindings

def cohorts(row,membership):
 return membership.get((row['game_id'],row['player_id']),{'priority':False,'workload_top20':False,'reason':'NOT_IN_DECLARED_COHORT'})
def freeze_cohorts(pool,g,hist):
 from receiving_priority_c03 import memberships
 schedule={r['game_id']:r for r in g.to_dict('records')}
 query={ (r['game_id'],r['player_id']):{k:r[k] for k in ['game_id','player_id','team','opponent_team','position','season','week','kickoff','home_team']} for r in pool if r['season'] in [2025,2026] and r['week']<=8 }
 for c in [r for r in corrected_rows() if r['method']=='E0']:
  k=(c['game_id'],c['player_id']);gg=schedule[c['game_id']]
  if k not in query:query[k]=dict(game_id=c['game_id'],player_id=c['player_id'],team=c['team'],opponent_team=c['opponent_team'],position=c['position'],season=2026,week=c['week'],kickoff=gg['kickoff'],home_team=gg['home_team'])
  query[k]['qualified_offer']=True
 raw=memberships(list(query.values()),hist,g)
 result={}
 for r in raw:
  k=(r['game_id'],r['player_id']);result[k]=dict(priority=bool(r['profiling_priority']),workload_top20=bool(r['top20_expected_targets']),reason=r['priority_reason'],reference_expected_targets=r.get('reference_expected_targets'),reference_cutoff=r.get('reference_cutoff'))
 path=OUT.parent/'COHORT_MEMBERSHIP.json.xz';obj=dict(policy='receiving_priority_c03.py:memberships',code_SHA256=sha(ROOT/'src/receiving_priority_c03.py'),rows=raw,eligible_statrow_history_limitation=True)
 if path.exists():assert read(path)==lookback.clean(obj),'FROZEN_COHORT_CHANGED'
 else:write(path,obj)
 return result,{'path':str(path.relative_to(ROOT)),'SHA256':sha(path)}

def point_summary(rows,methods,*,year,cohort='ALL',offered=False):
 result=[]
 for scope,roles in [('WR_TE',['WR','TE']),('RB',['RB']),('ALL_SUPPORTED',['RB','WR','TE'])]:
  for wk in ['ALL']+list(range(1,9)):
   rr=[r for r in rows if r['position'] in roles and r.get('season',2026)==year and (wk=='ALL' or r['week']==wk) and (cohort=='ALL' or r['cohort'].get(cohort,False))]
   for method in methods:
    aa=[r for r in rr if r.get(method) is not None];kk=[r for r in aa if r['actual'] is not None]
    z=dict(season=year,scope=scope,cohort=cohort,week=wk,method=method,eligible=len(rr),available=len(aa),known=len(kk),unknown=len(aa)-len(kk),unavailable=len(rr)-len(aa),games=len({r['game_id'] for r in kk}),player_games=len({(r['game_id'],r['player_id']) for r in kk}),actual_weeks=sorted({r['week'] for r in kk}),source_row_conditioned=not offered,offered_player_mask=offered)
    if kk:
     e=np.array([r[method]['mean']-r['actual'] for r in kk]);m=np.array([r[method]['median']-r['actual'] for r in kk]);player=collections.defaultdict(list)
     for r in kk:player[r['player_id']].append(abs(r[method]['median']-r['actual']))
     z.update(mean_MAE=float(abs(e).mean()),median_MAE=float(abs(m).mean()),mean_MSE=float((e*e).mean()),mean_RMSE=float(np.sqrt((e*e).mean())),mean_bias=float(e.mean()),median_bias=float(m.mean()),absolute_error_p90=float(np.quantile(abs(e),.9)),equal_player_median_MAE=float(np.mean([np.mean(v) for v in player.values()])),hard_fallback=sum(r[method].get('hard_fallback',False) for r in kk),profile_covered_known=sum(r[method].get('profile_covered',False) for r in kk),any_imputed_known=sum(r[method].get('any_imputed',False) for r in kk))
    result.append(z)
 return result

def bind_offer(template,arm,product,law,model_binding,support):
 q=dict(template)
 for k in ['Brier','log_loss','infinite_log_loss','point','point_type','probabilities']:q.pop(k,None)
 mu,median=law.mean(),law.quantile(.5);p=law.probability(q['line'])
 point=mu if product=='MEAN' else median if product=='MEDIAN' else None
 side=('OVER' if p['over']>p['under'] else 'UNDER' if p['under']>p['over'] else 'ABSTAIN') if product=='LAW' else ('OVER' if point>q['line'] else 'UNDER' if point<q['line'] else 'ABSTAIN')
 state='ABSTAIN' if side=='ABSTAIN' else 'UNKNOWN_PARTICIPATION' if q['appearance']!='PLAYED' else 'MISSING_ACTUAL' if q['actual'] is None else 'PUSH' if q['actual']==q['line'] else 'WIN' if (q['actual']>q['line'])==(side=='OVER') else 'LOSS'
 q.update(method=arm+'_'+product,procedure=VERSION+'::'+arm+'::'+product,mean=mu,median=median,point=point,point_type=None if product=='LAW' else product.lower(),probabilities=p if product=='LAW' else None,selected_side=side,status=state,model_binding=model_binding,fallback=False,**support)
 if product=='LAW' and state in ['WIN','LOSS','PUSH']:
  y,l=q['actual'],q['line'];truth={'under':int(y<l),'push':int(y==l),'over':int(y>l)};prob=sum(p[k]*truth[k] for k in p)
  q.update(Brier=.5*sum((p[k]-truth[k])**2 for k in p),log_loss=-math.log(prob) if prob else None,infinite_log_loss=prob==0)
 assert common.status(q)==state
 return q

def baseline_points(year=2026):
 if year==2026:
  data=read(ROOT/'reports/player-context-matchup-01/completion-decision-v1/intake/C_RETAINED_LEAF_POINTS_W1_W7.json.gz')
  return {(r['game_id'],r['player_id']):r for r in data['rows']}
 rows=[];proof=[];archive=ROOT/'artifacts/robustness-rec-v3.zip'
 with zipfile.ZipFile(archive) as z:
  for week in range(1,9):
   pre=f'raw/rec/W{week:02}/';done=json.loads(z.read(pre+'DONE.json'));body=z.read(pre+'rows.json.gz');rr=json.loads(gzip.decompress(body))
   assert done['season']==2025 and done['week']==week and done['family']=='P2_LEAF' and done['arm']=='E0_OP' and done['history']=='H-MULTI'
   assert done['source_sha256']['facts.csv.gz']==sha(lookback.INPUTS/'facts.csv.gz')
   for r in rr:assert r['season']==2025 and r['week']==week and r['family']=='P2_LEAF' and r['arm']=='E0_OP'
   proof.append(dict(week=week,source_member=pre+'rows.json.gz',row_SHA256=hashlib.sha256(body).hexdigest(),training_rows=done['training_rows'],membership_SHA256=done['training_membership_sha256'],origin_UTC=done['origin_UTC'],latest_training_available=done['latest_training_available']))
   rows+=rr
 write(OUT/'SAVED_2025_R0_BINDINGS.json',dict(archive=str(archive.relative_to(ROOT)),SHA256=sha(archive),slots=proof,unsafe_loaded=False,new_fits=0))
 return {(r['game_id'],r['player_id']):r for r in rows}

def run(year=2026,pilot=False):
 assert REG.exists(),'REGISTRATION_REQUIRED'
 registration=read(REG)
 assert registration.get('execution_authorized',False),'ROOT_EXECUTION_AUTHORIZATION_REQUIRED'
 OUT.mkdir(parents=True,exist_ok=True);ART.mkdir(parents=True,exist_ok=True)
 runpath=OUT/f'RUN-{year}.json';assert not runpath.exists(),'COMPLETED_YEAR_RUN_FROZEN'
 if year==2025:assert (OUT/'RUN-2026.json').exists() and registration.get('historical_expansion_authorized',False),'2025_EXPANSION_NOT_YET_AUTHORIZED'
 ledgerpath=OUT/'FIT_LEDGER.json';ledger=read(ledgerpath) if ledgerpath.exists() else dict(id=VERSION,attempts=[],completed=[],failures=[],CPU_seconds=0)
 cpu=time.process_time();wall=time.monotonic();max_cpu=registration.get('budget',{}).get('CPU_seconds',900)
 signal.signal(signal.SIGPROF,lambda *_:(_ for _ in ()).throw(RuntimeError('C03_CPU_CAP')));signal.setitimer(signal.ITIMER_PROF,max(.01,max_cpu-ledger['CPU_seconds']))
 def checkpoint():
  nonlocal cpu
  c=time.process_time();ledger['CPU_seconds']+=c-cpu;cpu=c;ledger['peak_RSS_bytes']=max(ledger.get('peak_RSS_bytes',0),resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024);write(ledgerpath,ledger);guard()
  assert ledger['CPU_seconds']<=max_cpu and ledger['peak_RSS_bytes']<=1288490188
  assert time.monotonic()-wall<1500
  from forward_budget_v4 import tree_bytes
  assert tree_bytes(ART)+tree_bytes(OUT.parent)<=registration.get('budget',{}).get('new_public_bytes_max',16777216),'C03_NEW_PUBLIC_CAP'
 def fitted(origin,arm,xx,yy,roles,members):
  dest=ART/f'{origin}-{arm}.json.xz';fp=fingerprint(xx,yy);mh=hashlib.sha256(json.dumps(members,separators=(',',':')).encode()).hexdigest()
  if dest.exists():
   d=read(dest);assert d['fingerprint']==fp and d['membership_SHA256']==mh and d['code_SHA256']==sha(Path(__file__)),'RECOVERED_FIT_BINDING_MISMATCH';return d['model'],dest
  key=origin+'-'+arm;assert key not in ledger['attempts'],'PRIOR_ATTEMPT_WITHOUT_RECOVERABLE_SAVED_MODEL';assert len(ledger['attempts'])<48
  ledger['attempts'].append(key);checkpoint()
  with threadpool_limits(limits=1):m=LeafModel('count',1).fit(xx,yy,roles)
  primitive=export_forest(m);parity=infer_forest(primitive,xx[:2],roles[:2]);native=m.laws(xx[:2],roles[:2]);assert max(abs(a.mean()-b.mean()) for a,b in zip(parity,native))<1e-10
  write(dest,dict(id=VERSION,origin=origin,arm=arm,model=primitive,fingerprint=fp,membership_SHA256=mh,training_rows=len(yy),code_SHA256=sha(Path(__file__)),registration_SHA256=sha(REG),feature_order=names[arm],defense_code_SHA256=bindings['defense_code_SHA256']))
  ledger['completed'].append(key);checkpoint();return primitive,dest
 try:
  pool,g,hist,th,context,defense,mats,names,bindings=prepare();checkpoint()
  membership,cohort_binding=freeze_cohorts(pool,g,hist);bindings['cohort']=cohort_binding
  write(OUT/'INPUT_BINDINGS.json',bindings);write(OUT/'FEATURE_ORDER.json',names)
  index={(r['game_id'],r['player_id']):i for i,r in enumerate(pool)};saved=baseline_points(year);rows=[];origins=[];models={};canaries=[]
  weeks=[1] if pilot else list(range(1,9))
  for week in weeks:
   origin=f'{year}-W{week:02}';cut=float(g.loc[(g.season==year)&(g.week==week),'kickoff'].min());tr=[i for i,r in enumerate(pool) if r['available']<cut and r['values']['rec'] is not None];qr=[i for i,r in enumerate(pool) if r['season']==year and r['week']==week]
   yy=np.array([pool[i]['values']['rec'] for i in tr]);roles=np.array([pool[i]['position'] for i in tr]);qroles=np.array([pool[i]['position'] for i in qr]);members=[(pool[i]['game_id'],pool[i]['player_id']) for i in tr]
   mm={}
   for arm in (['R1'] if pilot else ARMS):mm[arm]=fitted(origin,arm,mats[arm][tr],yy,roles,members)
   if year==2026 and week==8:
    p=ROOT/'artifacts/player-context-matchup-01/completion-decision-v1/lookback/2026-W08-retainedLeafExtension.json.gz';d=read(p);assert d['fingerprint']==fingerprint(mats['R0'][tr],yy);mm['R0']=(d['model'],p)
   laws={arm:infer_forest(model,mats[arm][qr],qroles) for arm,(model,_) in mm.items()};models[week]=mm
   usage=[]
   for arm,(model,path) in mm.items():
    cnt=collections.Counter(v for t in model['trees'] for v in t['feature'] if v>=0);n=len(names[arm]);usage.append(dict(origin=origin,arm=arm,model=str(path.relative_to(ROOT)),value_splits={names[arm][i]:cnt[i] for i in range(n) if cnt[i]},missing_indicator_splits={names[arm][i]:cnt[n+i] for i in range(n) if cnt[n+i]}))
   write(OUT/f'FEATURE_USAGE-{origin}.json',usage)
   for j,i in enumerate(qr):
    r=pool[i];z=dict(game_id=r['game_id'],player_id=r['player_id'],position=r['position'],team=r['team'],opponent_team=r['opponent_team'],season=year,week=week,actual=r['values']['rec'],cohort=cohorts(r,membership))
    for arm,ll in laws.items():
     law=ll[j];x=mats[arm][i];z[arm]=dict(mean=law.mean(),median=law.quantile(.5),p05=law.quantile(.05),p95=law.quantile(.95),hard_fallback=False,any_imputed=bool((~np.isfinite(x)).any()),profile_covered=bool(np.isfinite(context.own(r,8)[5])) if arm!='R0' else False)
    if 'R0' not in z:
     old=saved.get((r['game_id'],r['player_id']));
     if year==2025 and old is not None:assert np.array_equal(np.asarray([np.nan if v is None else v for v in old['features']]),mats['R0'][i],equal_nan=True),'SAVED_2025_R0_FEATURE_SEMANTICS_DIFFER'
     z['R0']=dict(mean=old['mean'],median=old['median'],hard_fallback=old['fallback'],profile_covered=False) if old else None
    rows.append(z)
   for arm,(model,path) in mm.items():
    if qr:
     j=next((j for j,i in enumerate(qr) if pool[i]['position'] in ['WR','TE']),0);i=qr[j];law=laws[arm][j]
     canaries.append(dict(origin=origin,arm=arm,game_id=pool[i]['game_id'],player_id=pool[i]['player_id'],position=pool[i]['position'],model=str(path.relative_to(ROOT)),model_SHA256=sha(path),feature_vector=lookback.clean(mats[arm][i]),expected_mean=law.mean(),expected_median=law.quantile(.5)))
   origins.append(dict(origin=origin,fit_cutoff_UTC=pd.Timestamp(cut,unit='s',tz='UTC').isoformat(),latest_training_available_UTC=pd.Timestamp(max(pool[i]['available'] for i in tr),unit='s',tz='UTC').isoformat(),training_rows=len(tr),query_rows=len(qr),old_R0_refits=0));checkpoint()
  if pilot:
   write(OUT/'PILOT.json',dict(origin=f'{year}-W01',arm='R1',new_model_bytes=sum(p.stat().st_size for _,p in models[1].values()),CPU_seconds=ledger['CPU_seconds'],RSS_bytes=ledger['peak_RSS_bytes'],fits=len(ledger['attempts']),scored_rows_published=0,decision='Awaitrootfinitepackagecontinuation'))
   print('C03_PILOT_COMPLETE',ledger['CPU_seconds']);return
  write(ART/f'NUMERICAL_ROWS-{year}.json.xz',rows);write(ART/f'CANARY_QUERIES-{year}.json.xz',canaries)
  scores=[]
  for co in ['ALL','priority','workload_top20']:scores+=point_summary(rows,['R0']+ARMS,year=year,cohort=co)
  write(OUT/f'NUMERICAL_SCORES-{year}.json.xz',scores)
  offered=[]
  if year==2026:
   source=corrected_rows();cases=[r for r in source if r['method']=='E0'];sched={r['game_id']:r for r in g.to_dict('records')}
   for c in cases:
    gg=sched[c['game_id']];q=dict(game_id=c['game_id'],player_id=c['player_id'],team=c['team'],opponent_team=c['opponent_team'],position=c['position'],season=year,week=c['week'],home_team=gg['home_team'],kickoff=gg['kickoff']);b=np.asarray(vector(q,'rec',hist,th,'E0_OP'));o=context.own(q,8);dv=defense.vector(q)
    xx={'R1':np.r_[b,o[:5],dv[:4]],'R2':np.r_[b,o[:5],dv[:4],o[5:]],'R3':np.r_[b,o[:5],dv[:4],o[5:],dv[4:]]}
    for arm in ARMS:
     model,path=models[c['week']][arm];law=infer_forest(model,xx[arm][None,:],[c['position']])[0];binding=dict(path=str(path.relative_to(ROOT)),SHA256=sha(path),origin=f'{year}-W{c["week"]:02}',source=VERSION)
     support=dict(cohort=cohorts(q,membership),profile_covered=bool(np.isfinite(o[5])),any_imputed=bool((~np.isfinite(xx[arm])).any()),hard_fallback=False)
     for product in ['MEAN','MEDIAN','LAW']:offered.append(bind_offer(c,arm,product,law,binding,support))
   # Exact saved R0 outputs only. The unsafe legacy models are never loaded;
   # unprovided native rows remain genuinely unavailable instead of refitted.
   for oldmethod,product in [('RETAINED_P1_MEAN','MEAN'),('RETAINED_P1_MEDIAN','MEDIAN'),('RETAINED_P2_LAW','LAW')]:
    for old in source:
     if old['method']!=oldmethod:continue
     r=dict(old,method='R0_'+product,procedure=VERSION+'::R0_SAVED::'+product,point_type=product.lower() if product!='LAW' else None,cohort=cohorts(old,membership),model_binding={'source':'EXACT_RETAINED_OUTPUT;NO_UNSAFE_LOAD_OR_EQUIVALENT_REFIT'},profile_covered=False,any_imputed=None,hard_fallback=old.get('fallback',False))
     if product!='LAW':
      for k in ['Brier','log_loss','infinite_log_loss']:r.pop(k,None)
      r['probabilities']=None
     offered.append(r)
   controls=[dict(r,cohort=cohorts(r,membership)) for r in source if r['method'] in ['E0','P1','P2','RETAINED_EARLIER_PREVALENCE_V8','ALWAYS_OVER','ALWAYS_UNDER']]
   write(ART/'ACTUAL_OFFER_ROWS.json.xz',offered);write(OUT/'ACTUAL_LINE_SCORES.json.xz',offer_summaries(offered+controls))
   write(OUT/'PAIRED_CHANGES.json',paired_changes(offered+controls))
   # Numerical errors on precisely the offered-player cases, no broad transfer.
   offnum=[]
   for c in cases:
    r=dict(game_id=c['game_id'],player_id=c['player_id'],position=c['position'],season=2026,week=c['week'],actual=c['actual'],cohort=cohorts(c,membership))
    for arm in ['R0']+ARMS:
     rr=next(x for x in offered if x['offer_id']==c['offer_id'] and x['method']==arm+'_LAW');r[arm]=dict(mean=rr['mean'],median=rr['median'],hard_fallback=rr.get('hard_fallback',False),profile_covered=rr.get('profile_covered',False),any_imputed=rr.get('any_imputed',False)) if rr.get('mean') is not None else None
    offnum.append(r)
   out=[]
   for co in ['ALL','priority','workload_top20']:out+=point_summary(offnum,['R0']+ARMS,year=2026,cohort=co,offered=True)
   write(OUT/'OFFERED_NUMERICAL_SCORES.json.xz',out)
  checkpoint();write(runpath,dict(id=VERSION,created_UTC=now(),year=year,origins=origins,fit_attempts_cumulative=len(ledger['attempts']),CPU_seconds_cumulative=ledger['CPU_seconds'],peak_RSS_bytes=ledger['peak_RSS_bytes'],code_SHA256=sha(Path(__file__)),registration_SHA256=sha(REG),numerical_rows=len(rows),actual_offer_weeks=[2,3] if year==2026 else [],actual_offer_method_rows=len(offered),old_R0_equivalent_fits_repeated=0,new_primary_release=False,source_vintage='EXPOSED_CURRENT_REVISED_RECONSTRUCTION'))
  print('C03_COMPLETE',year,len(ledger['attempts']),ledger['CPU_seconds'])
 except Exception as e:
  ledger['failures'].append(dict(at=now(),error=repr(e)));write(ledgerpath,ledger);raise
 finally:
  signal.setitimer(signal.ITIMER_PROF,0);ledger['CPU_seconds']+=time.process_time()-cpu;write(ledgerpath,ledger)

def offer_summaries(rows):
 out=[]
 for scope,roles in [('WR_TE',['WR','TE']),('RB',['RB']),('ALL_SUPPORTED',['RB','WR','TE'])]:
  for co in ['ALL','priority','workload_top20']:
   for wk in ['ALL',2,3]:
    for method in sorted({r['method'] for r in rows}):
     rr=[r for r in rows if r['method']==method and r['position'] in roles and (wk=='ALL' or r['week']==wk) and (co=='ALL' or r['cohort'].get(co,False))];bp=[r for r in rr if r['status'] in ['WIN','LOSS','PUSH'] and r.get('probabilities') and r.get('Brier') is not None]
     out.append(dict(scope=scope,cohort=co,week=wk,method=method,**common.summary(rr),Brier=float(np.mean([r['Brier'] for r in bp])) if bp else None,log_loss=float(np.mean([r['log_loss'] for r in bp])) if bp and all(r.get('log_loss') is not None for r in bp) else None,profile_covered=sum(r.get('profile_covered',False) for r in rr),hard_fallback=sum(bool(r.get('hard_fallback',r.get('fallback',False))) for r in rr),evidence_tier='TIMING_UNVERIFIED_LAST_RECORDED_ACTUAL_LINES;EXPOSED_RECONSTRUCTION'))
 return out

def paired_changes(rows):
 result=[]
 pairs=[('R2_LAW','R0_LAW'),('R2_LAW','R1_LAW'),('R3_LAW','R2_LAW'),('R1_LAW','R0_LAW'),('R3_LAW','P2'),('R3_LAW','E0'),('R3_LAW','RETAINED_EARLIER_PREVALENCE_V8')]
 for scope,roles in [('WR_TE',['WR','TE']),('ALL_SUPPORTED',['RB','WR','TE'])]:
  for co in ['ALL','priority','workload_top20']:
   for a,b in pairs:
    aa={r['offer_id']:r for r in rows if r['method']==a and r['position'] in roles and (co=='ALL' or r['cohort'].get(co,False))};bb={r['offer_id']:r for r in rows if r['method']==b and r['position'] in roles and (co=='ALL' or r['cohort'].get(co,False))};ids=sorted(aa.keys()&bb.keys());ids=[i for i in ids if aa[i]['status'] in ['WIN','LOSS'] and bb[i]['status'] in ['WIN','LOSS']]
    if not ids:result.append(dict(scope=scope,cohort=co,candidate=a,control=b,decided=0));continue
    for i in ids:assert all(aa[i][k]==bb[i][k] for k in ['game_id','player_id','line','actual','appearance'])
    z=dict(scope=scope,cohort=co,candidate=a,control=b,decided=len(ids),candidate_wins=sum(aa[i]['status']=='WIN' for i in ids),control_wins=sum(bb[i]['status']=='WIN' for i in ids),disagreements=sum(aa[i]['selected_side']!=bb[i]['selected_side'] for i in ids))
    z['win_change']=z['candidate_wins']-z['control_wins'];z['change_pp']=100*z['win_change']/len(ids)
    for key in ['game_id','week']:
     groups=collections.defaultdict(lambda:np.zeros(2))
     for i in ids:groups[aa[i][key]]+=[int(aa[i]['status']=='WIN')-int(bb[i]['status']=='WIN'),1]
     ar=np.array(list(groups.values()));rng=np.random.default_rng(661107);draw=ar[rng.integers(len(ar),size=(2000,len(ar)))].sum(axis=1);z[key+'_sensitivity95_pp']=(100*np.quantile(draw[:,0]/draw[:,1],[.025,.975])).tolist();z[key+'_clusters']=len(ar)
    both=[i for i in ids if aa[i].get('Brier') is not None and bb[i].get('Brier') is not None];z['Brier_change']=float(np.mean([aa[i]['Brier']-bb[i]['Brier'] for i in both])) if both else None;result.append(z)
 return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--year',type=int,choices=[2025,2026],default=2026);p.add_argument('--pilot',action='store_true');a=p.parse_args();run(a.year,a.pilot)
