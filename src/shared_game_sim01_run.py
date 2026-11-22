"""Admitted single scientific worker: closed S-P context -> retained game law.

Never reads the starter ZIP, cases, benchmarks, offered lines or target grades.
"""
from __future__ import annotations
import argparse,copy,hashlib,json,signal,time,traceback
from pathlib import Path
import numpy as np
from shared_game_sim01_budget import ROOT,D,LIMITS,LEDGER,footprint,save
from shared_game_sim01_inputs import load_context,utc,digest
from shared_game_sim01_fit import load_sources,fit_origin,restore_origin,build_team_prior,prior_to_record,team_to_record
from shared_game_sim01_condition import condition_game
from shared_game_sim01_kernel import sample_game,ExecutionPermit,COUNT_FIELDS,CHILD_FIELDS
from shared_game_sim01_retention import write_replay_bundle,reopen_replay_bundle

PRIVATE=ROOT/'private/shared-game-sim-01'
RAW=PRIVATE/'samples'
FREEZE=D/'FREEZE_A.json'
def verify_freeze():
 f=json.loads(FREEZE.read_text())
 for info in f['code']:
  p=ROOT/info['path']
  if hashlib.sha256(p.read_bytes()).hexdigest()!=info['SHA256']:raise ValueError('EXECUTABLE_FREEZE_MISMATCH:'+info['path'])
 return f
def storage_guard():
 ledger=json.loads(LEDGER.read_text());n=footprint();new=n-ledger['baseline_whole_C_bytes']
 if n>LIMITS['whole_C_bytes'] or new>LIMITS['peak_bytes']:raise RuntimeError('STORAGE_PEAK_SAFE_STOP')
 return dict(whole_C_bytes=n,new_simultaneous_bytes=new)
def game_params(store,prior,game,players):
 pp=[p for p in players if p['game_origin_key']==game['game_origin_key'] and p['identity_available']]
 teams=[];meta=[];anchors={};variances={}
 for team in (game['home'],game['away']):
  roster={p['gsis_id']:p['position'] for p in pp if p['team']==team}
  actors=[dict(gsis_id=a,position=pos) for a,pos in sorted(roster.items())]
  t,m=build_team_prior(store,prior,team,game['model_cutoff_utc'],actors)
  if m['latest_prior_available']>=min(utc(game['native_cutoff_utc']),utc(game['source_schedule_cutoff_utc'])):raise ValueError('DUAL_CLOCK_EARLIER_ADMISSION')
  teams.append(t);meta.append(m);variances[team]=m['process_variances'];anchors[team]={}
  for p in pp:
   if p['team']!=team:continue
   if p['gsis_id'] in anchors[team] and anchors[team][p['gsis_id']]!=p['provider_points']:raise ValueError('DUPLICATE_PLAYER_PROVIDER_CONFLICT')
   anchors[team][p['gsis_id']]=p['provider_points']
 conditioned,record=condition_game(tuple(teams),anchors,variances)
 record.update(component_source_metadata=meta,earlier_prior=prior_to_record(prior),
  native_game_id=game['native_game_id'],native_cutoff_utc=game['native_cutoff_utc'],
  archived_schedule_cutoff_utc=game['source_schedule_cutoff_utc'],effective_cutoff_utc=game['model_cutoff_utc'],
  source_clock_status='Both reconstructed schedule cutoffs; original issue/quote clocks unknown',
  query_identity_fingerprint=digest([dict(gsis_id=p['gsis_id'],team=p['team'],role=p['position'],missing=p['provider_missing']) for p in sorted(pp,key=lambda r:(r['team'],r['gsis_id']))]))
 return conditioned,record
def array_digest(arrays):
 h=hashlib.sha256()
 for k,a in sorted(arrays.items()):
  h.update(k.encode());h.update(a.dtype.str.encode());h.update(str(a.shape).encode());h.update(a.tobytes())
 return h.hexdigest()
def law_check(result):
 for ti in (0,1):
  p=f'team{ti}/';a=result.arrays
  if np.any(a[p+'pass_cmp']+a[p+'pass_int']>a[p+'pass_att']):raise ValueError('C_PLUS_INT_GT_A')
  if np.any(a[p+'rec']>a[p+'targets']):raise ValueError('REC_GT_TARGETS')
  if not np.array_equal(a[p+'rec'].sum(1),a[p+'pass_cmp'].sum(1)):raise ValueError('SHARED_CATCH_CONSERVATION')
  if not np.array_equal(a[p+'rush_att'].sum(1),a[p+'events'][:,2:].sum(1)):raise ValueError('SHARED_CARRY_CONSERVATION')
  if not np.array_equal(a[p+'events'].sum(1),a[p+'opportunities']):raise ValueError('SHARED_OPPORTUNITY_CONSERVATION')
 return 'PASS_RUNTIME_SUPPORT_CONSERVATION'
def generation(teams,prior,game,record,subcap=None):
 permit=ExecutionPermit('C-SHARED-GAME-SIM01-APPROVED-EXECUTION-v1',record['consumed_design_SHA256'],True,True,True)
 c=time.process_time()
 if subcap is not None:
  def stop(*_):raise RuntimeError('CANARY_GENERATION_6CPU_SAFE_STOP')
  old=signal.signal(signal.SIGPROF,stop);signal.setitimer(signal.ITIMER_PROF,subcap)
 try:result=sample_game(game['native_game_id'],game['model_cutoff_utc'],teams,prior.frailty_shape,permit=permit)
 finally:
  if subcap is not None:signal.setitimer(signal.ITIMER_PROF,0);signal.signal(signal.SIGPROF,old)
 return result,time.process_time()-c
def canary_or_full(stage):
 freeze=verify_freeze();storage_guard();games,players=load_context(PRIVATE)
 t=time.process_time();store=load_sources(ROOT);source_CPU=time.process_time()-t
 # Startup uses the same qualified2024/25 pool at all six origins; estimate once
 # and reuse. Per-game team/actor posteriors still update with eligible history.
 t=time.process_time()
 if stage=='canary' and not (PRIVATE/'frozen_startup_prior.json').exists():
  prior=fit_origin(store,games[0]['model_cutoff_utc']);save(PRIVATE/'frozen_startup_prior.json',prior_to_record(prior))
 else:prior=restore_origin(store,json.loads((PRIVATE/'frozen_startup_prior.json').read_text()))
 prior_CPU=time.process_time()-t
 source_receipt=D/('SOURCE_COMPONENT_EXECUTION_'+stage.upper()+'.json')
 if source_receipt.exists():source_receipt=D/('SOURCE_COMPONENT_EXECUTION_'+stage.upper()+'_'+str(len(list(D.glob('STOP_*.json')))+1)+'.json')
 save(source_receipt,dict(classification=store.classification,source_bodies=store.body_bindings,prior=prior_to_record(prior),source_CPU=source_CPU,prior_CPU=prior_CPU,source_state='READY_BOX_SCORE_RECONSTRUCTED',reuse='Same startup2024/25 prior reused across all origins; per-game earlier8 usage updates'))
 existing=json.loads((D/'GAME_EXECUTION_INDEX.json').read_text()) if (D/'GAME_EXECUTION_INDEX.json').exists() else []
 done={r['native_game_id'] for r in existing}
 # A numerical failure is unavailable for that original game, never retried or
 # erased. Other registered origins can be independently executable; all remain
 # in the full board. No grades or success-based week choice enter this rule.
 failed={p.name[len('STOP_'):-len('.json')] for p in D.glob('STOP_*.json')}
 done|=failed;RAW.mkdir(parents=True,exist_ok=True)
 todo=[g for g in games if g['native_game_id'] not in done]
 if stage=='canary':
  if existing:raise RuntimeError('CANARY_ALREADY_EXISTS_REUSE_DO_NOT_REPEAT')
 else:
  gate=json.loads((D/'CANARY_REMAINDER_GATE.json').read_text())
  if gate['decision']!='PASS':raise RuntimeError('FULL_REMAINDER_GATE_NOT_PASS')
 for game in todo:
  storage=storage_guard();t=time.process_time();w=time.monotonic()
  try:
   teams,record=game_params(store,prior,game,players);conditioning_CPU=time.process_time()-t
   r,gen_CPU=generation(teams,prior,game,record,6 if stage=='canary' else None)
   law_check(r);tio=time.process_time();path=RAW/(game['native_game_id']+'.zip')
   receipt=write_replay_bundle(path,r,teams,prior.frailty_shape,record)
   reopened=reopen_replay_bundle(path,expected_sha256=receipt['SHA256'])
   if array_digest(r.arrays)!=array_digest(reopened.arrays):raise ValueError('REOPENED_TRAJECTORIES_DIFFER')
   for k,m in reopened.dp_moments.items():
    if not np.array_equal(m['mean'],r.conditional_means[k].mean(axis=0)):raise ValueError('REOPENED_DP_MEAN_DIFFER')
    if not np.array_equal(m['conditional_mean_variance'],r.conditional_means[k].var(axis=0)):raise ValueError('REOPENED_DP_MIXING_VARIANCE_DIFFER')
   io_CPU=time.process_time()-tio
   row=dict(native_game_id=game['native_game_id'],source_game_origin_key=game['game_origin_key'],season=game['season'],week=game['week'],
    trajectories=10000,conditioning_CPU=conditioning_CPU,generation_CPU=gen_CPU,serialization_reopen_CPU=io_CPU,
    wall=time.monotonic()-w,body_bytes=path.stat().st_size,SHA256=receipt['SHA256'],
    arrays_SHA256=array_digest(r.arrays),input_design_SHA256=record['consumed_design_SHA256'],
    actor_count=sum(len(t.actor_ids) for t in teams),component_availability=r.metadata['teams'],
    D_P='Required sufficient moments AND fitted state reopened exactly',runtime_checks='PASS_SUPPORT_CONSERVATION_LOCAL_REOPEN',storage_before=storage)
   existing.append(row);save(D/'GAME_EXECUTION_INDEX.json',existing)
   print(json.dumps({k:row[k] for k in ('native_game_id','trajectories','generation_CPU','body_bytes')}),flush=True)
   del r,reopened
   if stage=='canary':break
  except BaseException as e:
   save(D/('STOP_'+game['native_game_id']+'.json'),dict(stage=stage,reason=str(e),type=type(e).__name__,fit_record=getattr(e,'record',None),CPU_since_game_start=time.process_time()-t,completed_games=len(existing),no_retry=True))
   if str(e)=='PROVIDER_CONDITIONING_FAILED;NO_RETRY':
    print('TECHNICAL_UNAVAILABLE_NO_RETRY',game['native_game_id'],flush=True)
    continue
   raise
 return existing
def mutation():
 verify_freeze();games,players=load_context(PRIVATE);game=games[0]
 rindex=json.loads((D/'GAME_EXECUTION_INDEX.json').read_text());row=rindex[0];kept=reopen_replay_bundle(RAW/(row['native_game_id']+'.zip'),expected_sha256=row['SHA256'])
 store=load_sources(ROOT);cut=utc(game['model_cutoff_utc']);pr=json.loads((PRIVATE/'frozen_startup_prior.json').read_text());prior=restore_origin(store,pr)
 t0,rec0=game_params(store,prior,game,players)
 altered=copy.deepcopy(store);mutated=0
 for g in altered.team_games.values():
  if g['kickoff']>=cut:
   for p in g['plays']:
    p['gain']=-999 if p['gain'] is not None else None
    if p['td'] is not None:p['td']=1-p['td']
    if p['event']==0:p['outcome']=(p['outcome']+1)%3
    mutated+=1
 prior1=restore_origin(altered,pr);t1,rec1=game_params(altered,prior1,game,players)
 if prior.design_SHA256!=prior1.design_SHA256 or rec0['consumed_design_SHA256']!=rec1['consumed_design_SHA256']:raise ValueError('PROHIBITED_OUTCOME_CONSUMED_DESIGN_CHANGED')
 if [team_to_record(t) for t in t0]!=[team_to_record(t) for t in t1]:raise ValueError('PROHIBITED_OUTCOME_FITTED_STATE_CHANGED')
 rs,cpu=generation(t1,prior1,game,rec1)
 if array_digest(rs.arrays)!=row['arrays_SHA256'] or array_digest(kept.arrays)!=row['arrays_SHA256']:raise ValueError('PROHIBITED_OUTCOME_PREDICTIONS_CHANGED')
 law_check(rs)
 save(D/'NFL_MUTATION_AND_CONSERVATION.json',dict(state='PASS',native_game_id=game['native_game_id'],mutated_prohibited_plays=mutated,held_fixed='Complete legitimate query/teammate context, actors, ordering, source row/denominator membership, cutoffs and seed',design='Identical actually consumed earlier design and fitted parameters',predictions='All retained10000trajectory primitive arrays exactly identical',scope='Separate C NFL runtime check; not B independent verification; no new evidence games',repeat_generation_CPU=cpu))
 print('NFL_FULL_CONTEXT_MUTATION_CONSERVATION_PASS',mutated)
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('stage',choices=['canary','full','mutation']);v=a.parse_args()
 mutation() if v.stage=='mutation' else canary_or_full(v.stage)
