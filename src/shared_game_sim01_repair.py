"""One approved numerical repair namespace; old attempts/freezes are immutable.

Only the controlled worker may fit or generate. No work occurs on import.
"""
from __future__ import annotations
import argparse,copy,datetime,hashlib,json,os,resource,subprocess,sys,time
from pathlib import Path
from shared_game_sim01_budget import ROOT,footprint

OLD=ROOT/'reports/shared-game-sim-01/execution-v1'
CARRY=ROOT/'reports/shared-game-sim-01/follow-through-v1/LEDGER_CARRY_V1.json'
D=ROOT/'reports/shared-game-sim-01/numerical-repair-v1'
LEDGER=D/'LEDGER.json'
PRIVATE=ROOT/'private/shared-game-sim-01'
RAW=PRIVATE/'samples'
LAUNCH='2026-11-22T18:05:20.108935+00:00'
DEADLINE='2026-11-23T00:05:20.108935+00:00'
GAME='2026_04_DET_CAR'
LIMITS=dict(CPU_seconds=1800.,controlled_wall_seconds=7200.,elapsed_seconds=21600.,
 canary_CPU_seconds=180.,completion_CPU_reserve=380.,RSS_bytes=1288490188,
 retained_bytes=536870912,peak_bytes=805306368,whole_C_bytes=2684354560,
 source_recovery_reads=8,output_readbacks=20,new_stages=152,new_iterations=76000,
 new_evaluations=152000,new_games=74,generation_calls=75)
def now():return datetime.datetime.now(datetime.timezone.utc)
def save(p,x):
 p.parent.mkdir(parents=True,exist_ok=True);q=p.with_suffix(p.suffix+'.tmp')
 with q.open('w') as f:
  json.dump(x,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
 os.replace(q,p)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def binding(p):return dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,SHA256=sha(p))
def initialize():
 if LEDGER.exists():return json.loads(LEDGER.read_text())
 old=json.loads(CARRY.read_text());original=json.loads((OLD/'LEDGER.json').read_text())
 # User explicitly carries the recorded decimal once, not a new allocation.
 x=dict(id='C-SIM01-NUMERICAL-REPAIR-v1',limits=LIMITS,
  approval_commit='0f5859c661c0404b02f0914826cf560f1754ed24',approval='User expressly approves pinned request once;PR65 remains draft',
  charged_CPU_seconds=max(260.154994406,old['CPU_seconds']),
  charged_controlled_wall_seconds=old['controlled_wall_seconds'],
  canary_CPU_seconds=59.093234438,source_recovery_reads=0,output_readbacks=8,
  baseline_whole_C_bytes=original['baseline_whole_C_bytes'],
  first_scientific_launch_UTC=LAUNCH,deadline_UTC=DEADLINE,
  counters=dict(stages=0,iterations=0,evaluations=0,game_attempts=0,generations=0),
  events=[dict(stage='Carry all original task charges ONCE',CPU_seconds=max(260.154994406,old['CPU_seconds']),controlled_wall_seconds=old['controlled_wall_seconds'],source=binding(CARRY))],
  metering='Selected single-worker/controller process CPU plus disclosed conservative preparation. Original missing vectors, unmetered overhead and elapsed overrun preserved; no full CPU certificate.')
 save(LEDGER,x);return x
def charge(stage,cpu,wall=0.,*,canary=False,details=None):
 x=initialize();x['charged_CPU_seconds']+=cpu;x['charged_controlled_wall_seconds']+=wall
 if canary:x['canary_CPU_seconds']+=cpu
 x['events'].append(dict(stage=stage,CPU_seconds=cpu,controlled_wall_seconds=wall,canary=canary,UTC=now().isoformat(),details=details));save(LEDGER,x);return x
def deadline_guard():
 if now()>=datetime.datetime.fromisoformat(DEADLINE):raise RuntimeError('ORIGINAL_LAUNCH_FIXED_DEADLINE_EXPIRED_NO_RESTART')
def storage():
 x=initialize();whole=footprint();new=whole-x['baseline_whole_C_bytes']
 if whole>LIMITS['whole_C_bytes'] or new>LIMITS['peak_bytes']:raise RuntimeError('STORAGE_GUARD')
 if new>LIMITS['retained_bytes']:raise RuntimeError('RETAINED_STORAGE_GUARD')
 return dict(current_whole_bytes=whole,current_new_bytes=new,baseline_whole_C_bytes=x['baseline_whole_C_bytes'],duplication_multiplier=3)
def controlled(stage,command,cap,*,canary=False,completion=False):
 deadline_guard();x=initialize()
 allowed=min(cap,LIMITS['CPU_seconds']-x['charged_CPU_seconds']-(0 if completion else 380))
 if canary:allowed=min(allowed,180-x['canary_CPU_seconds'])
 if allowed<=1:raise RuntimeError('CPU_RESERVE_OR_CANARY_EXHAUSTED')
 wall_left=7200-x['charged_controlled_wall_seconds']
 if wall_left<=1:raise RuntimeError('CONTROLLED_WALL_EXHAUSTED')
 env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',
 NUMEXPR_NUM_THREADS='1',VECLIB_MAXIMUM_THREADS='1',PYTHONHASHSEED='0')
 c=time.process_time();w=time.monotonic();usage=resource.getrusage(resource.RUSAGE_CHILDREN)
 p=subprocess.Popen(command,cwd=ROOT,env=env);reason=None;peak=threads=0
 try:
  while p.poll() is None:
   try:
    s=Path(f'/proc/{p.pid}/stat').read_text().split();cpu=sum(int(s[k]) for k in (13,14,15,16))/os.sysconf('SC_CLK_TCK')
    rss=int(s[23])*os.sysconf('SC_PAGE_SIZE');peak=max(peak,rss);threads=max(threads,len(list(Path(f'/proc/{p.pid}/task').iterdir())))
   except (FileNotFoundError,ProcessLookupError):continue
   if cpu+time.process_time()-c>=allowed-.5:reason='CPU_HARD_SAFE_STOP'
   elif time.monotonic()-w>=wall_left-.5 or now()>=datetime.datetime.fromisoformat(DEADLINE):reason='WALL_HARD_SAFE_STOP'
   elif rss>LIMITS['RSS_bytes']:reason='RSS_HARD_SAFE_STOP'
   elif threads>1:reason='THREAD_HARD_SAFE_STOP'
   if reason:p.terminate();break
   time.sleep(.05)
  try:p.wait(timeout=2)
  except subprocess.TimeoutExpired:p.kill();p.wait()
 finally:
  u=resource.getrusage(resource.RUSAGE_CHILDREN)
  cpu=time.process_time()-c+u.ru_utime-usage.ru_utime+u.ru_stime-usage.ru_stime
  wall=time.monotonic()-w
  charge(stage,cpu,wall,canary=canary,details=dict(returncode=p.returncode,safe_stop=reason,peak_RSS_bytes=peak,threads=threads,command_SHA256=hashlib.sha256(json.dumps(command).encode()).hexdigest(),interruption_scope='Last durable counter/checkpoint retained; any postcheckpoint in-flight tail remains unknown'))
 if reason or p.returncode:
  if not (D/'PACKAGE_STOP.json').exists():
   save(D/'PACKAGE_STOP.json',dict(state='STOP_FIRST_NEW_WORKER_FAILURE',stage=stage,
    reason=reason or 'WORKER_NONZERO',returncode=p.returncode,completed_game_sets=len(index()),
    uncertainty='Interrupt stage/vector/in-memory tail beyond durable last checkpoint unobserved; no retry'))
  raise SystemExit(reason or p.returncode)
 return dict(CPU_seconds=cpu,wall_seconds=wall,peak_RSS_bytes=peak,threads=threads)
def freeze_check():
 f=json.loads((D/'FREEZE_A.json').read_text())
 for r in f['code']+f['required_public_bodies']:
  p=ROOT/r['path']
  if p.stat().st_size!=r['bytes'] or sha(p)!=r['SHA256']:raise ValueError('AMENDED_FREEZE_BODY_MISMATCH:'+r['path'])
 from shared_game_sim01_run import verify_private_inputs
 verify_private_inputs(f)
 pr=f['startup_prior'];p=PRIVATE/pr['private_role']
 if p.stat().st_size!=pr['bytes'] or sha(p)!=pr['SHA256']:raise ValueError('STARTUP_PRIOR_BODY_MISMATCH')
 return f
class Attempt:
 def __init__(self,game,phase):
  self.game=game;self.phase=phase;gid=game['native_game_id']
  if any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_' for c in gid):raise ValueError('BAD_GAME_ID')
  self.path=D/'attempts'/(phase+'__'+gid+'.json')
  if self.path.exists():raise RuntimeError('REPAIR_ATTEMPT_ALREADY_EXISTS_NO_RETRY')
  old=[binding(p) for p in [OLD/('STOP_'+gid+'.json'),OLD/('ATTEMPT_'+gid+'.json')] if p.exists()]
  self.value=dict(native_game_id=gid,phase=phase,original_records=old,events=[],
   stage_records={},stage_starts={},stage_checkpoints={},current_stage=None)
  if phase in ('canary','full'):
   x=initialize()
   if x['counters']['game_attempts']>=74:raise RuntimeError('GAME_ATTEMPT_LIMIT')
   x['counters']['game_attempts']+=1;save(LEDGER,x)
  self.progress('STARTED_BEFORE_NUMERICAL_WORK',input_game=dict(game),original_records=old)
 def progress(self,state,**fields):
  self.value['events'].append(dict(state=state,UTC=now().isoformat(),**fields));save(self.path,self.value)
 def __call__(self,event):
  x=initialize();kind=event['event'];key=event.get('stage','UNKNOWN')
  if kind=='STAGE_STARTED':
   if x['counters']['stages']>=152:raise RuntimeError('AGGREGATE_STAGE_LIMIT')
   x['counters']['stages']+=1;self.value['current_stage']=key
  elif kind=='BEFORE_OBJECTIVE':
   if x['counters']['evaluations']>=152000:raise RuntimeError('AGGREGATE_EVALUATION_LIMIT')
   x['counters']['evaluations']+=1
  elif kind=='ACCEPTED_ITERATION':
   if x['counters']['iterations']>=76000:raise RuntimeError('AGGREGATE_ITERATION_LIMIT')
   x['counters']['iterations']+=1
  save(LEDGER,x) # Count reservations before computation, including failed calls.
  if kind in ('STAGE_STARTED','CHECKPOINT','TERMINATED','EXCEPTION'):
   if kind=='STAGE_STARTED':
    self.value['stage_starts'][key]=event
   elif kind=='CHECKPOINT':
    self.value['stage_checkpoints'].setdefault(key,[]).append(event)
   self.value['stage_records'][key]=event
   self.progress(kind,stage=key,counters=dict(x['counters']))
 def fail(self,e):
  self.value['failure']=dict(type=type(e).__name__,reason=str(e),optimizer_record=getattr(e,'record',None),no_retry=True)
  self.progress('FAILED_STOP_PACKAGE')
  save(D/'PACKAGE_STOP.json',dict(state='STOP_FIRST_NEW_FAILURE',native_game_id=self.game['native_game_id'],phase=self.phase,reason=str(e),attempt=binding(self.path),completed_game_sets=len(index()),unknown_tail='Any interrupt after last checkpoint unobserved; no invented state or retry'))
def index():return json.loads((D/'GAME_EXECUTION_INDEX.json').read_text()) if (D/'GAME_EXECUTION_INDEX.json').exists() else []
def generate(teams,prior,game,record,*,canary=False):
 import shared_game_sim01_run as rw
 x=initialize()
 if x['counters']['generations']>=75:raise RuntimeError('GENERATION_INVOCATION_LIMIT')
 x['counters']['generations']+=1;save(LEDGER,x)
 return rw.generation(teams,prior,game,record,6 if canary else None)
def worker(stage):
 deadline_guard();f=freeze_check();storage()
 if (D/'PACKAGE_STOP.json').exists():raise RuntimeError('REPAIR_PACKAGE_ALREADY_STOPPED_NO_RESTART')
 import shared_game_sim01_run as rw
 from shared_game_sim01_inputs import load_context
 from shared_game_sim01_fit import load_sources,restore_origin
 from shared_game_sim01_retention import write_replay_bundle,reopen_replay_bundle
 games,players=load_context(PRIVATE)
 if len(games)!=74 or len({g['native_game_id'] for g in games})!=74:raise ValueError('FROZEN_FULL_GAME_UNIVERSE')
 t=time.process_time();store=load_sources(ROOT);pr=json.loads((PRIVATE/'frozen_startup_prior.json').read_text());prior=restore_origin(store,pr);restore_CPU=time.process_time()-t
 source=[dict(x) for x in store.body_bindings]
 expected=json.loads((OLD/'SOURCE_COMPONENT_EXECUTION_CANARY.json').read_text())['source_bodies']
 if source!=expected:raise ValueError('EXACT_RETAINED_SOURCE_BINDINGS_DIFFER')
 save(D/('SOURCE_REOPEN_'+stage+'.json'),dict(source_bodies=source,prior_design_SHA256=prior.design_SHA256,source_restore_CPU=restore_CPU,prior_reused=True))
 if stage=='canary':
  if index():raise RuntimeError('CANARY_ALREADY_COMPLETED_REUSE')
  selected=[g for g in games if g['native_game_id']==GAME]
  if len(selected)!=1:raise ValueError('DECLARED_CANARY_NOT_UNIQUE')
 elif stage=='full':
  gate=json.loads((D/'FULL_REMAINDER_GATE.json').read_text())
  if gate['decision']!='PASS':raise RuntimeError('FULL_REMAINDER_NOT_ADMITTED')
  done={r['native_game_id'] for r in index()};selected=[g for g in games if g['native_game_id'] not in done]
  if len(selected)!=73:raise ValueError('REGISTERED_REMAINDER_NOT_EXACTLY73')
 else:raise ValueError('UNKNOWN_WORKER_STAGE')
 for game in selected:
  deadline_guard();st=storage();attempt=Attempt(game,stage);t=time.process_time();w=time.monotonic()
  try:
   attempt.progress('INPUTS_BOUND',private_inputs=f['actual_private_inputs_reopened'],source_bodies=source,prior_SHA256=f['startup_prior']['SHA256'])
   teams,record=rw.game_params(store,prior,game,players,execution=attempt);fit_CPU=time.process_time()-t
   record['replay_input_bindings']=dict(private_inputs=f['actual_private_inputs_reopened'],source_bodies=source)
   attempt.progress('CONDITIONED_BEFORE_GENERATION',design_SHA256=record['consumed_design_SHA256'])
   r,gen_CPU=generate(teams,prior,game,record,canary=stage=='canary');rw.law_check(r);io=time.process_time()
   path=RAW/(game['native_game_id']+'.zip');receipt=write_replay_bundle(path,r,teams,prior.frailty_shape,record)
   kept=reopen_replay_bundle(path,receipt['SHA256'])
   storage() # Count the actual retained raw/state bytes before admission.
   if rw.array_digest(r.arrays)!=rw.array_digest(kept.arrays):raise ValueError('REOPENED_SP_ARRAYS_DIFFER')
   import numpy as np
   for key,v in kept.dp_moments.items():
    if not np.array_equal(v['mean'],r.conditional_means[key].mean(axis=0)):raise ValueError('REOPENED_DP_MEAN_DIFFER')
    if not np.array_equal(v['conditional_mean_variance'],r.conditional_means[key].var(axis=0)):raise ValueError('REOPENED_DP_MIX_VARIANCE_DIFFER')
   if [rw.team_to_record(x) for x in teams]!=[rw.team_to_record(x) for x in kept.teams]:raise ValueError('REOPENED_FITTED_STATE_DIFFER')
   row=dict(native_game_id=game['native_game_id'],source_game_origin_key=game['game_origin_key'],season=game['season'],week=game['week'],trajectories=10000,conditioning_CPU=fit_CPU,generation_CPU=gen_CPU,serialization_reopen_CPU=time.process_time()-io,source_restore_CPU=restore_CPU,wall=time.monotonic()-w,body_bytes=path.stat().st_size,uncompressed_member_bytes=receipt['uncompressed_member_bytes'],SHA256=receipt['SHA256'],arrays_SHA256=rw.array_digest(r.arrays),input_design_SHA256=record['consumed_design_SHA256'],actor_count=sum(len(t.actor_ids) for t in teams),local_reopened=True,DP_reopened=True,remote_reopened=False,storage_before=st,attempt=binding(attempt.path))
   rows=index();rows.append(row);save(D/'GAME_EXECUTION_INDEX.json',rows)
   attempt.progress('SP_DP_AND_FITTED_STATE_LOCAL_REOPEN_PASS',raw_bundle_SHA256=row['SHA256'])
   print(json.dumps(dict(state='RETAINED_GAME_LOCAL',game=row['native_game_id'],trajectories=10000,conditioning_CPU=fit_CPU,generation_CPU=gen_CPU,bytes=row['body_bytes'])),flush=True)
   del r,kept
  except BaseException as e:
   attempt.fail(e);raise # Both canary AND full worker stop on first failure.
 return index()
def mutation():
 deadline_guard();f=freeze_check()
 if (D/'PACKAGE_STOP.json').exists():raise RuntimeError('PACKAGE_STOPPED')
 import shared_game_sim01_run as rw
 from shared_game_sim01_inputs import load_context,utc
 from shared_game_sim01_fit import load_sources,restore_origin,team_to_record
 from shared_game_sim01_retention import reopen_replay_bundle
 rows=index()
 if not rows:raise RuntimeError('NO_RETAINED_ARTIFACT')
 row=rows[0];kept=reopen_replay_bundle(RAW/(row['native_game_id']+'.zip'),row['SHA256'])
 if rw.array_digest(kept.arrays)!=row['arrays_SHA256']:raise ValueError('RETAINED_MUTATION_ARRAY_HASH_MISMATCH')
 games,players=load_context(PRIVATE);store=load_sources(ROOT)
 game=rw.retained_mutation_game(games,row,kept,f,store.body_bindings)
 pr=json.loads((PRIVATE/'frozen_startup_prior.json').read_text());prior=rw.restore_retained_prior(store,pr,kept)
 a=Attempt(game,'reproduction_baseline')
 try:
  t0,rec0=rw.game_params(store,prior,game,players,execution=a)
  if rec0['consumed_design_SHA256']!=row['input_design_SHA256'] or rec0['query_identity_fingerprint']!=kept.fit_record['query_identity_fingerprint']:raise ValueError('BASELINE_DESIGN_OR_QUERY_DIFFER')
  if [team_to_record(t) for t in t0]!=[team_to_record(t) for t in kept.teams]:raise ValueError('BASELINE_FITTED_STATE_DIFFER')
  a.progress('REPRODUCTION_PASS')
 except BaseException as e:a.fail(e);raise
 altered=copy.deepcopy(store);count=0;cut=utc(game['model_cutoff_utc'])
 for g in altered.team_games.values():
  if g['kickoff']>=cut:
   for p in g['plays']:
    p['gain']=-999 if p['gain'] is not None else None
    if p['td'] is not None:p['td']=1-p['td']
    if p['event']==0:p['outcome']=(p['outcome']+1)%3
    count+=1
 b=Attempt(game,'mutation_prohibited_future')
 try:
  prior1=restore_origin(altered,pr);t1,rec1=rw.game_params(altered,prior1,game,players,execution=b)
  if rec0['consumed_design_SHA256']!=rec1['consumed_design_SHA256'] or [team_to_record(t) for t in t0]!=[team_to_record(t) for t in t1]:raise ValueError('PROHIBITED_OUTCOME_CHANGED_DESIGN_STATE')
  r,cpu=generate(t1,prior1,game,rec1)
  if rw.array_digest(r.arrays)!=row['arrays_SHA256'] or rw.array_digest(kept.arrays)!=row['arrays_SHA256']:raise ValueError('PROHIBITED_OUTCOME_CHANGED_TRAJECTORIES')
  rw.law_check(r);b.progress('NFL_MUTATION_CONSERVATION_PASS')
  save(D/'NFL_MUTATION_REPRODUCTION.json',dict(state='PASS',native_game_id=game['native_game_id'],source_input_hashes_verified=True,complete_context_held=True,mutated_prohibited_plays=count,repeat_generation_CPU=cpu,scope='C scoped runtime check, not independent B fit reproduction'))
 except BaseException as e:b.fail(e);raise
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['canary','full','mutation']);ap.add_argument('--worker',action='store_true');args=ap.parse_args()
 if args.worker:mutation() if args.stage=='mutation' else worker(args.stage)
 else:
  # Included canary reserve for mandatory raw-shard publication/restoration;
  # it is not additional CPU or a change to the approved180 cumulative ceiling.
  x=initialize();cap=180-x['canary_CPU_seconds']-12 if args.stage=='canary' else (160 if args.stage=='mutation' else LIMITS['CPU_seconds']-x['charged_CPU_seconds']-380)
  print(json.dumps(controlled('repair_'+args.stage,[sys.executable,str(Path(__file__).resolve()),args.stage,'--worker'],cap,canary=args.stage=='canary',completion=args.stage=='mutation')))
