"""Aligned availability sensitivity for retained C03 receiving procedures.

F0/F1 reuse the seven-day R1/R2 forecasts. F2/F3 preserve the learner, inputs,
cohorts and selection rules but refit with a one-day RECONSTRUCTION policy in
training-label admission, every historical feature prefix and query inference.
No old source/model is modified; no historical observation time is invented.
"""
from __future__ import annotations
import argparse, collections, copy, gzip, hashlib, json, lzma, math, resource, signal, time
from pathlib import Path
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
from sklearn.metrics import roc_auc_score
import receiving_increment_c03 as c03
from data_v2 import History, vector, DAY
from context_features_c01 import Context, Prefix
from receiving_defense_c03 import SUPPORT_NAMES
from receiving_profiles_c02 import BASE_NAMES
from laws_v2 import LeafModel
from safe_models_v4 import export_forest, infer_forest
from context_identity_view_c01 import corrected_rows
from context_sources_c01 import guard
import abc_championship_v2 as common

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/profile-closure-next-02/timing'
ART=ROOT/'artifacts/receiving-timing-c04'
REG=ROOT/'protocol/PROFILE_INCREMENT_CLOSURE_NEXT_02_C.json'
VERSION='C-RECEIVING-ALIGNED-TIMING-v1'
POLICY7='RECONSTRUCTED_KICKOFF_PLUS7D_STRICT_CURRENT_VINTAGE'
POLICY1='RECONSTRUCTED_KICKOFF_PLUS1D_STRICT_CURRENT_VINTAGE_NOT_OBSERVED_PUBLICATION'
ARMS=['F2','F3']
OLD={'F0':'R1','F1':'R2'}
CONTRASTS=[('F1','F0'),('F2','F0'),('F3','F2'),('F3','F1')]

def now(): return pd.Timestamp.now(tz='UTC').isoformat()
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):
 p=Path(path);b=p.read_bytes()
 return json.loads(lzma.decompress(b) if p.suffix=='.xz' else gzip.decompress(b) if p.suffix=='.gz' else b)
def clean(x): return c03.lookback.clean(x)
def write(path,obj):
 p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
 b=(json.dumps(clean(obj),separators=(',',':'),allow_nan=False)+'\n').encode()
 p.write_bytes(lzma.compress(b,preset=6) if p.suffix=='.xz' else b)
def fingerprint(x,y): return c03.fingerprint(x,y)
def finite(x):
 try:return x is not None and math.isfinite(float(x))
 except (TypeError,ValueError):return False

def retime_proxy_record(row,lag_days):
 """Retype ONLY an explicitly declared derived seven-day proxy, never a clock.

 The caller binds C03's raw reconstructed input. Explicitly unknown values and
 clocks inconsistent with that declared derivation are rejected, not filled.
 """
 if lag_days not in [1,7]:raise ValueError('UNREGISTERED_RECONSTRUCTION_LAG')
 if not finite(row.get('kickoff')):raise ValueError('UNKNOWN_GAME_TIME')
 if 'available' not in row or not finite(row['available']):raise ValueError('EXPLICIT_UNKNOWN_AVAILABILITY_NOT_RETIMED')
 if abs(float(row['available'])-(float(row['kickoff'])+7*DAY))>1e-6:raise ValueError('NOT_DECLARED_C03_SEVEN_DAY_PROXY')
 r=dict(row);r['available']=float(row['kickoff'])+lag_days*DAY
 return r

class AdmittedPrefix:
 """Admit first, then select most recent game times; strict boundary retained."""
 def __init__(self,rows,key):
  self.groups=collections.defaultdict(list)
  for r in rows:
   if not finite(r.get('available')) or not finite(r.get('kickoff')):raise ValueError('UNKNOWN_PREFIX_CLOCK')
   self.groups[r[key]].append(r)
  for rr in self.groups.values():rr.sort(key=lambda r:(r['kickoff'],r['game_id']))
 def before(self,key,cutoff,n=8):
  if not finite(cutoff):raise ValueError('FINITE_PREFIX_CUTOFF_REQUIRED')
  rr=[r for r in self.groups.get(key,[]) if r['available']<cutoff and r['kickoff']<cutoff]
  return rr[-n:]

class Capped:
 def __init__(self,history,cutoff):self.history,self.cutoff=history,float(cutoff)
 def before(self,key,cutoff,n=8):return self.history.before(key,min(float(cutoff),self.cutoff),n)

class OwnContext:
 """Expose own-player features only, so stale old residuals cannot be consumed."""
 def __init__(self,rows):self.players=AdmittedPrefix(rows,'player_id')
 def own(self,row,lookback=8,information_cutoff=None):
  if information_cutoff is None:return Context.own(self,row,lookback)
  shell=copy.copy(self);shell.players=Capped(self.players,information_cutoff)
  return Context.own(shell,row,lookback)

class TimedInputs:
 """Reusable as-of feature adapter for historical and legitimate future queries.

 Future rows need no outcome, participation or outcome-availability field. The
 parent live adapter must additionally validate actual source/event/roster clocks.
 """
 def __init__(self,pool,hist,teamhist,context,defense,lag_days):
  self.lag_days=lag_days;self.policy=POLICY7 if lag_days==7 else POLICY1
  self.pool=[retime_proxy_record(r,lag_days) for r in pool]
  pr=[retime_proxy_record(r,lag_days) for rr in hist.groups.values() for r in rr]
  tr=[retime_proxy_record(r,lag_days) for rr in teamhist.groups.values() for r in rr]
  self.hist=AdmittedPrefix(pr,'player_id');self.teamhist=AdmittedPrefix(tr,'team')
  self.own_context=OwnContext([retime_proxy_record(r,lag_days) for r in context.raw_player_games])
  self.defense=copy.copy(defense);self.defense.rows=[retime_proxy_record(r,lag_days) for r in defense.rows]
  self.defense.groups=collections.defaultdict(list)
  for r in self.defense.rows:self.defense.groups[r['defense']].append(r)
  self.defense._league_cache={}
 def support(self,row,information_cutoff=None):
  cut=float(row['kickoff']) if information_cutoff is None else min(float(row['kickoff']),float(information_cutoff))
  rs=self.defense.before(row['opponent_team'],cut,8)
  n=sum(float(r['cells'][:,:,0].sum()) for r in rs)
  return np.asarray([len(rs),n,(cut-rs[-1]['kickoff'])/DAY if rs else np.nan,float(not n)])
 def features(self,row,information_cutoff=None):
  if row.get('position') not in ['RB','WR','TE']:raise ValueError('UNSUPPORTED_RECEIVING_ROLE')
  if information_cutoff is not None and not finite(information_cutoff):raise ValueError('FINITE_INFORMATION_CUTOFF_REQUIRED')
  ph=self.hist if information_cutoff is None else Capped(self.hist,information_cutoff)
  th=self.teamhist if information_cutoff is None else Capped(self.teamhist,information_cutoff)
  base=np.asarray(vector(row,'rec',ph,th,'E0_OP'),float)
  own=self.own_context.own(row,8,information_cutoff);support=self.support(row,information_cutoff)
  return {'BASE':base,'SUPPORT':np.r_[base,own[:5],support],'PROFILE':np.r_[base,own[:5],support,own[5:]],'own':own,'defense_support':support}

def prepare():
 """One source reconstruction, no fits/network or writes to closed C03 reports."""
 pool,g,hist,th,context,defense,oldmats,names,bindings=c03.prepare()
 p7=TimedInputs(pool,hist,th,context,defense,7);p1=TimedInputs(pool,hist,th,context,defense,1)
 mat7={'F0':np.asarray([p7.features(r)['SUPPORT'] for r in pool]),'F1':np.asarray([p7.features(r)['PROFILE'] for r in pool])}
 mat1={'F2':np.asarray([p1.features(r)['SUPPORT'] for r in pool]),'F3':np.asarray([p1.features(r)['PROFILE'] for r in pool])}
 assert np.array_equal(mat7['F0'],oldmats['R1'],equal_nan=True),'SEVEN_DAY_SUPPORT_FEATURE_PARITY'
 assert np.array_equal(mat7['F1'],oldmats['R2'],equal_nan=True),'SEVEN_DAY_PROFILE_FEATURE_PARITY'
 names={k:names[v] for k,v in {'F0':'R1','F1':'R2','F2':'R1','F3':'R2'}.items()}
 proof=[]
 for year in [2025,2026]:
  for week in range(1,9):
   cut=float(g.loc[(g.season==year)&(g.week==week),'kickoff'].min());train=[i for i,r in enumerate(pool) if r['available']<cut and r['values']['rec'] is not None]
   y=np.asarray([pool[i]['values']['rec'] for i in train]);members=[(pool[i]['game_id'],pool[i]['player_id']) for i in train];mh=hashlib.sha256(json.dumps(members,separators=(',',':')).encode()).hexdigest()
   for arm,old in OLD.items():
    path=c03.ART/f'{year}-W{week:02}-{old}.json.xz';m=read(path)
    assert m['fingerprint']==fingerprint(mat7[arm][train],y) and m['membership_SHA256']==mh and m['feature_order']==names[arm],'SAVED_SEVEN_DAY_FIT_CONTRACT_MISMATCH'
    proof.append(dict(origin=f'{year}-W{week:02}',arm=arm,original_arm=old,path=str(path.relative_to(ROOT)),SHA256=sha(path),training_rows=len(train),fingerprint=m['fingerprint'],membership_SHA256=mh))
 bindings=dict(bindings,C03_source_commit='a9cb8ef61a294b73f558b3c5daad483094af80b2',C03_fit_driver_SHA256=sha(ROOT/'src/receiving_increment_c03.py'),new_timing_code_SHA256=sha(Path(__file__)),policy7=POLICY7,policy1=POLICY1,old_models_refitted=0,source_vintages_changed=False,defense_values_consumed=False)
 return pool,g,p7,p1,mat7,mat1,names,bindings,proof

def membership():
 path=ROOT/'reports/profile-increment-v2/COHORT_MEMBERSHIP.json.xz';rows=read(path)['rows']
 return {(r['game_id'],r['player_id']):dict(priority=r['profiling_priority'],workload_top20=r['top20_expected_targets'],reason=r['priority_reason'],reference_expected_targets=r['reference_expected_targets'],reference_cutoff=r['reference_cutoff']) for r in rows}

def query_for(case,schedule):
 g=schedule[case['game_id']]
 return dict(game_id=case['game_id'],player_id=case['player_id'],team=case['team'],opponent_team=case['opponent_team'],position=case['position'],season=2026,week=case['week'],home_team=g['home_team'],kickoff=g['kickoff'])

def diagnose(data):
 pool,g,p7,p1,mat7,mat1,names,bindings,proof=data
 schedule={r['game_id']:r for r in g.to_dict('records')};source=[r for r in corrected_rows() if r['method']=='E0'];rows=[]
 for c in sorted(source,key=lambda r:r['offer_id']):
  q=query_for(c,schedule);a=p7.hist.before(q['player_id'],q['kickoff'],8);b=p1.hist.before(q['player_id'],q['kickoff'],8)
  own7=p7.own_context.own(q,8);own1=p1.own_context.own(q,8)
  rows.append(dict(offer_id=c['offer_id'],game_id=c['game_id'],player_id=c['player_id'],position=c['position'],week=c['week'],outcome_state=c['status'],actual=c['actual'],latest7=a[-1]['game_id'] if a else None,latest1=b[-1]['game_id'] if b else None,game_age7_days=(q['kickoff']-a[-1]['kickoff'])/DAY if a else None,game_age1_days=(q['kickoff']-b[-1]['kickoff'])/DAY if b else None,own_qualified_games7=own7[0],own_qualified_games1=own1[0],own_targets7=own7[1],own_targets1=own1[1],assumed_available7=a[-1]['available'] if a else None,assumed_available1=b[-1]['available'] if b else None,source_observation_age='NOT_HISTORICALLY_AUTHENTICATED',no_actual_future_exposure_consumed=True))
 summaries=[]
 for label,roles in [('WR_TE',['WR','TE']),('RB',['RB']),('ALL_SUPPORTED',['RB','WR','TE'])]:
  for wk in ['ALL',2,3]:
   rr=[r for r in rows if r['position'] in roles and (wk=='ALL' or r['week']==wk)];age7=[r['game_age7_days'] for r in rr if r['game_age7_days'] is not None];age1=[r['game_age1_days'] for r in rr if r['game_age1_days'] is not None]
   summaries.append(dict(scope=label,week=wk,offers=len(rr),latest_prior_game_changes=sum(r['latest7']!=r['latest1'] for r in rr),old_empty_new_nonempty=sum(r['latest7'] is None and r['latest1'] is not None for r in rr),median_game_age7=float(np.median(age7)) if age7 else None,median_game_age1=float(np.median(age1)) if age1 else None,mean_qualified_own_games7=float(np.mean([r['own_qualified_games7'] for r in rr])) if rr else None,mean_qualified_own_games1=float(np.mean([r['own_qualified_games1'] for r in rr])) if rr else None))
 existing=read(ROOT/'reports/player-context-matchup-01/acceptance-v1/FRESHNESS_SHADOW_GRADE.json')
 report=dict(id=VERSION+'::DIAGNOSIS',created_UTC=now(),classification='MEASURED_INFORMATION_COVERAGE_WEAKNESS;NOT_VERIFIED_DEFECT_OR_MEASURED_CAUSAL_ACCURACY_PENALTY',prior_comparison=dict(id=existing['id'],graded=existing['graded'],unknown=existing['unknown'],games=existing['game_count'],interpretation=existing['interpretation'],equivalent_to_aligned_F0_F3=False),source_clock_tier='CURRENT_REVISED_HISTORICAL_RECONSTRUCTION;1DAY_IS_NOT_AN_OBSERVATION_CLOCK',summaries=summaries,workload_conversion='UNRESOLVED:directLeafdoesnotidentify a forecast-workload versusconversion error decomposition; no outcome-bias offset orcausal attribution.',role_teammate_changes='No qualified new current-role/teammate block added; native historical team filters remain unchanged.',broad_offered='Reuse C03 qualified broad/offered numeric distinction; timing contrast holds each original mask fixed.',old_defense_nonuse='Closed oldHGB diagnosis not reopened; C03 newLeafvalueswereused and their lossespreserved. No actualdefense values inthis contrast.',new_group_exposure='All role/week/history diagnostics are exposed development; no favorable subset orselector fitted.',new_fits=0)
 write(OUT/'DIAGNOSIS.json',report);write(OUT/'INFORMATION_AGE_ROWS.json.xz',rows);write(OUT/'SEVEN_DAY_REUSE_PARITY.json',dict(status='PASS',raw_query_rows=len(pool),F0_F1_matrices_exact=True,old_fit_contracts=proof,models_refitted=0));write(OUT/'INPUT_BINDINGS.json',bindings);write(OUT/'FEATURE_ORDER.json',names)
 return report

def old_numeric(year):return {(r['game_id'],r['player_id']):r for r in read(c03.ART/f'NUMERICAL_ROWS-{year}.json.xz')}

def rename_offer(old,arm,policy):
 q=dict(old);product=old['method'].split('_')[-1];q['source_procedure_id']=old['procedure'];q['method']=arm+'_'+product;q['procedure']=VERSION+'::'+arm+'::'+product;q['availability_policy']=policy;q['reused_saved_forecast']=True;return q

def bind_offer(template,arm,product,law,model_binding,support):
 q=c03.bind_offer(template,arm,product,law,model_binding,support);q['procedure']=VERSION+'::'+arm+'::'+product;q['availability_policy']=POLICY1;q['reused_saved_forecast']=False;return q

def actual_rows(p1,g,models,memberships):
 source=corrected_rows();cases=[r for r in source if r['method']=='E0'];schedule={r['game_id']:r for r in g.to_dict('records')};out=[]
 for c in cases:
  q=query_for(c,schedule);xx=p1.features(q)
  for arm,key in [('F2','SUPPORT'),('F3','PROFILE')]:
   model,path=models[c['week']][arm];law=infer_forest(model,xx[key][None,:],[q['position']])[0]
   mb=dict(path=str(path.relative_to(ROOT)),SHA256=sha(path),origin=f'2026-W{c["week"]:02}',policy=POLICY1,source=VERSION)
   support=dict(cohort=c03.cohorts(q,memberships),profile_covered=bool(np.isfinite(xx['own'][5])),any_imputed=bool((~np.isfinite(xx[key])).any()),hard_fallback=False)
   for product in ['MEAN','MEDIAN','LAW']:out.append(bind_offer(c,arm,product,law,mb,support))
 old=read(c03.ART/'ACTUAL_OFFER_ROWS.json.xz')
 for r in old:
  prefix=r['method'].split('_')[0]
  if prefix in ['R1','R2']:out.append(rename_offer(r,'F0' if prefix=='R1' else 'F1',POLICY7))
 controls=[dict(r,cohort=c03.cohorts(r,memberships)) for r in source if r['method'] in ['E0','P1','P2','RETAINED_EARLIER_PREVALENCE_V8','ALWAYS_OVER','ALWAYS_UNDER']]
 for r in old:
  if r['method'].startswith('R0_'):
   q=dict(r);q['source_procedure_id']=q['procedure'];q['method']='CONTROL_LEAF_'+r['method'].split('_')[-1];controls.append(q)
 return out,controls,cases

def paired(rows):
 out=[]
 for product in ['MEAN','MEDIAN','LAW']:
  pairs=[(a+'_'+product,b+'_'+product) for a,b in CONTRASTS]+[('F3_'+product,'P2'),('F3_'+product,'E0'),('F3_'+product,'RETAINED_EARLIER_PREVALENCE_V8')]
  for scope,roles in [('WR_TE',['WR','TE']),('RB',['RB']),('ALL_SUPPORTED',['RB','WR','TE'])]:
   for co in ['ALL','priority','workload_top20']:
    for a,b in pairs:
     aa={r['offer_id']:r for r in rows if r['method']==a and r['position'] in roles and (co=='ALL' or r['cohort'].get(co,False))};bb={r['offer_id']:r for r in rows if r['method']==b and r['position'] in roles and (co=='ALL' or r['cohort'].get(co,False))};ids=sorted(aa.keys()&bb.keys());ids=[i for i in ids if aa[i]['status'] in ['WIN','LOSS'] and bb[i]['status'] in ['WIN','LOSS']]
     if not ids:continue
     for i in ids:assert all(aa[i][k]==bb[i][k] for k in ['game_id','player_id','line','actual','appearance'])
     z=dict(scope=scope,cohort=co,product=product,candidate=a,control=b,decided=len(ids),candidate_wins=sum(aa[i]['status']=='WIN' for i in ids),control_wins=sum(bb[i]['status']=='WIN' for i in ids),disagreements=sum(aa[i]['selected_side']!=bb[i]['selected_side'] for i in ids));z['win_change']=z['candidate_wins']-z['control_wins'];z['change_pp']=100*z['win_change']/len(ids)
     for key in ['game_id','week']:
      groups=collections.defaultdict(lambda:np.zeros(2))
      for i in ids:groups[aa[i][key]]+=[int(aa[i]['status']=='WIN')-int(bb[i]['status']=='WIN'),1]
      blocks=np.asarray(list(groups.values()));rng=np.random.default_rng(661107);draw=blocks[rng.integers(len(blocks),size=(2000,len(blocks)))].sum(axis=1);z[key+'_sensitivity95_pp']=(100*np.quantile(draw[:,0]/draw[:,1],[.025,.975])).tolist();z[key+'_clusters']=len(blocks)
     bp=[i for i in ids if aa[i].get('Brier') is not None and bb[i].get('Brier') is not None];z['Brier_change']=float(np.mean([aa[i]['Brier']-bb[i]['Brier'] for i in bp])) if bp else None;out.append(z)
 return out

def reliability(rows):
 out=[]
 for method in sorted({r['method'] for r in rows if r.get('probabilities')}):
  for scope,roles in [('WR_TE',['WR','TE']),('RB',['RB']),('ALL_SUPPORTED',['RB','WR','TE'])]:
   for wk in ['ALL',2,3]:
    rr=[r for r in rows if r['method']==method and r['position'] in roles and (wk=='ALL' or r['week']==wk) and r['status'] in ['WIN','LOSS']];n=len(rr)
    if not n:continue
    p=np.asarray([r['probabilities']['over'] for r in rr]);truth=np.asarray([r['actual']>r['line'] for r in rr]);conf=np.asarray([r['probabilities'][r['selected_side'].lower()] for r in rr]);wins=np.asarray([r['status']=='WIN' for r in rr]);bins=[]
    edges=[.5,.6,.7,.8,.9,1.0000000001]
    for lo,hi in zip(edges,edges[1:]):
     mask=(conf>=lo)&(conf<hi);k=int(mask.sum());bins.append(dict(low=lo,high=min(1.,hi),n=k,predicted=float(conf[mask].mean()) if k else None,accuracy=float(wins[mask].mean()) if k else None,wins=int(wins[mask].sum()),gap=float((conf[mask]-wins[mask]).mean()) if k else None))
    out.append(dict(method=method,scope=scope,week=wk,decided=n,mean_predicted_over=float(p.mean()),actual_over_frequency=float(truth.mean()),mean_selected_confidence=float(conf.mean()),selected_accuracy=float(wins.mean()),expected_wins=float(conf.sum()),actual_wins=int(wins.sum()),Brier=float(np.mean([r['Brier'] for r in rr])),log_loss=float(np.mean([r['log_loss'] for r in rr])) if all(r.get('log_loss') is not None for r in rr) else None,Over_AUC=float(roc_auc_score(truth,p)) if len(set(truth))==2 else None,confidence_correctness_AUC=float(roc_auc_score(wins,conf)) if len(set(wins))==2 else None,fixed_selected_confidence_bins=bins,uncertainty='Descriptivefixedbins;32game/2weeklimitsandsharedoutcomes;notIIDconfidenceguarantee'))
 return out

def numeric_pairs(rows,year,*,offered=False):
 out=[]
 for scope,roles in [('WR_TE',['WR','TE']),('RB',['RB']),('ALL_SUPPORTED',['RB','WR','TE'])]:
  for co in ['ALL','priority','workload_top20']:
   for a,b in CONTRASTS:
    rr=[r for r in rows if r['position'] in roles and r['actual'] is not None and r.get(a) and r.get(b) and (co=='ALL' or r['cohort'].get(co,False))]
    if not rr:continue
    for metric,function in [('median_absolute_error',lambda r,m:abs(r[m]['median']-r['actual'])),('mean_absolute_error',lambda r,m:abs(r[m]['mean']-r['actual'])),('mean_squared_error',lambda r,m:(r[m]['mean']-r['actual'])**2)]:
     delta=[function(r,a)-function(r,b) for r in rr];z=dict(season=year,scope=scope,cohort=co,candidate=a,control=b,metric=metric,matched_known=len(rr),candidate_score=float(np.mean([function(r,a) for r in rr])),control_score=float(np.mean([function(r,b) for r in rr])),change=float(np.mean(delta)),offered_mask=offered)
     for key in ['game_id','week']:
      groups=collections.defaultdict(lambda:np.zeros(2))
      for r,d in zip(rr,delta):groups[r[key]]+=[d,1]
      blocks=np.asarray(list(groups.values()));rng=np.random.default_rng(661107);draw=blocks[rng.integers(len(blocks),size=(2000,len(blocks)))].sum(axis=1);z[key+'_sensitivity95']=np.quantile(draw[:,0]/draw[:,1],[.025,.975]).tolist();z[key+'_clusters']=len(blocks)
     out.append(z)
 return out

def run(year=2026,pilot=False,registration=REG):
 global REG
 REG=Path(registration);reg=read(REG);assert reg.get('execution_authorized') is True,'ROOT_AUTHORIZATION_REQUIRED'
 OUT.mkdir(parents=True,exist_ok=True);ART.mkdir(parents=True,exist_ok=True)
 runpath=OUT/f'RUN-{year}.json';assert not runpath.exists(),'COMPLETED_YEAR_FROZEN'
 ledgerpath=OUT/'FIT_LEDGER.json';ledger=read(ledgerpath) if ledgerpath.exists() else dict(id=VERSION,attempts=[],completed=[],failures=[],CPU_seconds=0)
 cpu=time.process_time();wall=time.monotonic();limit=reg.get('budget',{}).get('CPU_seconds',900)
 signal.signal(signal.SIGPROF,lambda *_:(_ for _ in ()).throw(RuntimeError('C04_CPU_CAP')));signal.setitimer(signal.ITIMER_PROF,max(.01,limit-ledger['CPU_seconds']))
 def checkpoint():
  nonlocal cpu
  t=time.process_time();ledger['CPU_seconds']+=t-cpu;cpu=t;ledger['peak_RSS_bytes']=max(ledger.get('peak_RSS_bytes',0),resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024);write(ledgerpath,ledger);guard()
  assert ledger['CPU_seconds']<=limit and ledger['peak_RSS_bytes']<=1288490188 and time.monotonic()-wall<1500
  from forward_budget_v4 import tree_bytes
  assert tree_bytes(ART)+tree_bytes(OUT.parent)<=reg.get('budget',{}).get('new_public_bytes_max',12582912),'C04_NEW_PUBLIC_CAP'
 def fit(origin,arm,x,y,roles,members,names):
  path=ART/f'{origin}-{arm}.json.xz';fp=fingerprint(x,y);mh=hashlib.sha256(json.dumps(members,separators=(',',':')).encode()).hexdigest()
  if path.exists():
   data=read(path);assert data['fingerprint']==fp and data['membership_SHA256']==mh and data['code_SHA256']==sha(Path(__file__)),'RECOVERED_FIT_BINDING_MISMATCH';return data['model'],path
  key=origin+'-'+arm;assert key not in ledger['attempts'],'PRIOR_ATTEMPT_WITHOUT_MODEL';assert len(ledger['attempts'])<32
  ledger['attempts'].append(key);checkpoint()
  with threadpool_limits(limits=1):m=LeafModel('count',1).fit(x,y,roles)
  primitive=export_forest(m);check=infer_forest(primitive,x[:2],roles[:2]);native=m.laws(x[:2],roles[:2]);assert max(abs(a.mean()-b.mean()) for a,b in zip(check,native))<1e-10
  write(path,dict(id=VERSION,origin=origin,arm=arm,model=primitive,policy=POLICY1,fingerprint=fp,membership_SHA256=mh,training_rows=len(y),code_SHA256=sha(Path(__file__)),registration_SHA256=sha(REG),feature_order=names))
  ledger['completed'].append(key);checkpoint();return primitive,path
 try:
  data=prepare();pool,g,p7,p1,mat7,mat1,names,bindings,proof=data;diagnose(data);checkpoint()
  memb=membership();old=old_numeric(year);rows=[];models={};origins=[];canaries=[]
  for week in ([1] if pilot else range(1,9)):
   origin=f'{year}-W{week:02}';cut=float(g.loc[(g.season==year)&(g.week==week),'kickoff'].min());tr=[i for i,r in enumerate(p1.pool) if r['available']<cut and r['values']['rec'] is not None];qr=[i for i,r in enumerate(pool) if r['season']==year and r['week']==week];y=np.asarray([pool[i]['values']['rec'] for i in tr]);roles=np.asarray([pool[i]['position'] for i in tr]);qroles=np.asarray([pool[i]['position'] for i in qr]);members=[(pool[i]['game_id'],pool[i]['player_id']) for i in tr]
   selected=['F2'] if pilot else ARMS;mm={a:fit(origin,a,mat1[a][tr],y,roles,members,names[a]) for a in selected};models[week]=mm;laws={a:infer_forest(m,mat1[a][qr],qroles) for a,(m,_) in mm.items()}
   for j,i in enumerate(qr):
    r=pool[i];saved=old[(r['game_id'],r['player_id'])];assert saved['actual']==r['values']['rec'];z={k:r[k] for k in ['game_id','player_id','position','team','opponent_team','season','week']};z.update(actual=r['values']['rec'],cohort=saved['cohort'])
    for a,b in OLD.items():z[a]=dict(saved[b],reused_saved_forecast=True,source_arm=b,availability_policy=POLICY7)
    for a,ll in laws.items():
     law=ll[j];z[a]=dict(mean=law.mean(),median=law.quantile(.5),p05=law.quantile(.05),p95=law.quantile(.95),hard_fallback=False,any_imputed=bool((~np.isfinite(mat1[a][i])).any()),profile_covered=bool(np.isfinite(p1.own_context.own(r,8)[5])),availability_policy=POLICY1)
    rows.append(z)
   for a,(m,path) in mm.items():
    j=next((j for j,i in enumerate(qr) if pool[i]['position'] in ['WR','TE']),0);i=qr[j];law=laws[a][j];canaries.append(dict(origin=origin,arm=a,game_id=pool[i]['game_id'],player_id=pool[i]['player_id'],position=pool[i]['position'],model=str(path.relative_to(ROOT)),model_SHA256=sha(path),feature_vector=clean(mat1[a][i]),expected_mean=law.mean(),expected_median=law.quantile(.5)))
   origins.append(dict(origin=origin,fit_cutoff_UTC=pd.Timestamp(cut,unit='s',tz='UTC').isoformat(),latest_training_available_UTC=pd.Timestamp(max(p1.pool[i]['available'] for i in tr),unit='s',tz='UTC').isoformat(),training_rows=len(tr),query_rows=len(qr),old_F0_F1_refits=0));checkpoint()
  if pilot:
   write(OUT/'PILOT.json',dict(origin=f'{year}-W01',arm='F2',model_bytes=sum(p.stat().st_size for _,p in models[1].values()),CPU_seconds=ledger['CPU_seconds'],RSS_bytes=ledger['peak_RSS_bytes'],fits=len(ledger['attempts']),comparative_scores_published=0));print('C04_PILOT_COMPLETE');return
  write(ART/f'NUMERICAL_ROWS-{year}.json.xz',rows);write(ART/f'CANARY_QUERIES-{year}.json.xz',canaries)
  scores=[]
  for co in ['ALL','priority','workload_top20']:scores+=c03.point_summary(rows,['F0','F1','F2','F3'],year=year,cohort=co)
  write(OUT/f'NUMERICAL_SCORES-{year}.json.xz',scores);write(OUT/f'NUMERICAL_PAIRED-{year}.json.xz',numeric_pairs(rows,year))
  if year==2026:
   offered,controls,cases=actual_rows(p1,g,models,memb);write(ART/'ACTUAL_OFFER_ROWS.json.xz',offered);write(OUT/'ACTUAL_LINE_SCORES.json.xz',c03.offer_summaries(offered+controls));write(OUT/'PAIRED_CHANGES.json.xz',paired(offered+controls));write(OUT/'RELIABILITY.json.xz',reliability(offered+controls))
   num=[]
   for c in cases:
    z={k:c[k] for k in ['game_id','player_id','position','week','actual']};z.update(season=2026,cohort=c03.cohorts(c,memb))
    for arm in ['F0','F1','F2','F3']:
     r=next(r for r in offered if r['method']==arm+'_LAW' and r['offer_id']==c['offer_id']);z[arm]=dict(mean=r['mean'],median=r['median'],hard_fallback=r['hard_fallback'],any_imputed=r.get('any_imputed'),profile_covered=r['profile_covered'])
    for arm in ['P1','P2']:
     r=next(r for r in controls if r['method']==arm and r['offer_id']==c['offer_id']);z['CONTROL_CONTEXT_'+arm]=dict(mean=r['mean'],median=r['median'],hard_fallback=r.get('fallback',False))
    num.append(z)
   ss=[]
   for co in ['ALL','priority','workload_top20']:ss+=c03.point_summary(num,['F0','F1','F2','F3','CONTROL_CONTEXT_P1','CONTROL_CONTEXT_P2'],year=2026,cohort=co,offered=True)
   # Support for old controls is unverified, never a fabricated complete zero.
   for r in ss:
    if r['method'].startswith('CONTROL_'):r['any_imputed_known']=None;r['profile_covered_known']=None
   write(OUT/'OFFERED_NUMERICAL_SCORES.json.xz',ss);write(OUT/'OFFERED_NUMERICAL_PAIRED.json.xz',numeric_pairs(num,2026,offered=True))
  write(OUT/f'RUN-{year}.json',dict(id=VERSION,created_UTC=now(),year=year,origins=origins,new_fits_for_year=16,old_forecasts_reused=True,registration_SHA256=sha(REG),code_SHA256=sha(Path(__file__)),source_bindings=bindings,profile_only_added_values='ExistingOWN_NAMES[5:] fixed8; no new defensevalues/currentroles',new_policy='One-dayreconstructedtiming sensitivity,notauthenticatedpublication',new_original_selections=0));checkpoint();print('C04_YEAR_COMPLETE',year,ledger['CPU_seconds'])
 except Exception as e:
  ledger['failures'].append(dict(UTC=now(),error=str(e),year=year,pilot=pilot));write(ledgerpath,ledger);raise
 finally:
  signal.setitimer(signal.ITIMER_PROF,0);ledger['CPU_seconds']+=time.process_time()-cpu;write(ledgerpath,ledger)

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--year',type=int,choices=[2025,2026],default=2026);parser.add_argument('--pilot',action='store_true');parser.add_argument('--prepare-only',action='store_true');parser.add_argument('--registration',type=Path,default=REG);args=parser.parse_args()
 if args.prepare_only:
  result=diagnose(prepare());print('C04_PREPARED_NO_FITS',result['summaries'][0])
 else:run(args.year,args.pilot,args.registration)
