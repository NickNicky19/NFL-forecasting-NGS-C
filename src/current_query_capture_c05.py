"""Fitless C05 first publication from bound C04 models/frozen football inputs.

Current roster/event evidence gates eligibility; it does not refresh football
features. Every actual inference, issue and server clock is recorded separately.
No fitting, collection, selection, price or production switch is performed here.
"""
from __future__ import annotations
import argparse,collections,hashlib,json,lzma,math,platform,re,resource,subprocess,time
from importlib.metadata import version
from pathlib import Path
from email.utils import parsedate_to_datetime
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
from safe_models_v4 import infer_forest,law_data
from context_experiment_c01 import pooled_mu
from receiving_current_validation_c04 import load_capture_law,bound_files,close,aware
from receiving_current_capture_c04 import independent_response_clock,same_clock_value,qualified_events

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'sources/profile-timing-closure-confirm-01/forward'
REG=ROOT/'protocol/PROFILE_TIMING_CLOSURE_CONFIRM_01_C.json'
ORIGINAL=ROOT/'prospective/runs/C-C04-20261110-W10-FIRST-01'
COLLECTOR=ROOT/'reports/profile-timing-closure-confirm-01/forward-source/acquire_forward_sources_c05.py'
SCHEMA='C05-FROZEN-FOOTBALL-CURRENT-QUERY-RUN-v1'
RECEIPT_SCHEMA='C05-SERVER-PREGAME-RECEIPT-v1'
POLICY='FROZEN_FOOTBALL_SNAPSHOT_FIRST_PUBLICATION_SHADOW'
TARGET='2026_10_NE_DET'
MODEL_IDS=['C_V4_RETAINED_REFERENCE_OBSERVED','C_V11_P1_E2_POOLED_7D','C04_F3_PROFILE_1D_SHADOW']
CODE=['src/current_query_capture_c05.py','src/prospective_v4.py','src/receiving_current_validation_c04.py','src/receiving_current_capture_c04.py','src/safe_models_v4.py','src/context_experiment_c01.py','src/laws_v2.py']

def now():return pd.Timestamp.now(tz='UTC').isoformat()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
 p=Path(p);b=p.read_bytes();return json.loads(lzma.decompress(b) if p.suffix=='.xz' else b)
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple,np.ndarray)):return [clean(v) for v in x]
 if isinstance(x,(bool,np.bool_)):return bool(x)
 if isinstance(x,(int,np.integer)):return int(x)
 if isinstance(x,(float,np.floating)):return float(x) if np.isfinite(x) else None
 return x
def write(p,obj,exclusive=False):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);b=(json.dumps(clean(obj),separators=(',',':'),allow_nan=False)+'\n').encode()
 if p.suffix=='.xz':b=lzma.compress(b,preset=6)
 with p.open('xb' if exclusive else 'wb') as f:f.write(b)
def binding(p):
 p=Path(p);return dict(path=p.resolve().relative_to(ROOT).as_posix(),bytes=p.stat().st_size,SHA256=sha(p))
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()
def code_bindings():return {name:sha(ROOT/name) for name in [*CODE,str(COLLECTOR.relative_to(ROOT))]}
def committed_bindings():
 for rel in [*CODE,str(COLLECTOR.relative_to(ROOT)),str(REG.relative_to(ROOT))]:
  assert hashlib.sha256(subprocess.check_output(['git','show','HEAD:'+rel],cwd=ROOT)).hexdigest()==sha(ROOT/rel),'C05_UNCOMMITTED_CODE_OR_POLICY:'+rel
 return dict(code_commit=git('rev-parse','HEAD'),code_SHA256=code_bindings(),registration_SHA256=sha(REG))
def clean_start(output):
 assert not git('status','--porcelain'),'C05_WHOLE_TREE_MUST_BE_CLEAN'
 p=Path(output).resolve();assert not p.is_relative_to(ROOT),'C05_PROOF_MUST_BE_OUTSIDE_GIT'
 r=dict(created_UTC=now(),git_status='',**committed_bindings());write(p,r,True);return r

def lineage():
 """Restore immutable original bytes without re-fitting or loading executable models."""
 m=read(ORIGINAL/'RUN.json');bound_files(ORIGINAL,m['files'])
 app=read(ORIGINAL/'RECOVERY_COMPLETENESS_APPENDIX.json');assert app['parent_RUN_SHA256']==sha(ORIGINAL/'RUN.json')
 bound_files(ORIGINAL,{x['path']:x for x in app['added_files']})
 d=read(ORIGINAL/'draft/DRAFT.json');bound_files(ORIGINAL/'draft',d['files'])
 assert m['code_commit']==d['code_commit'] and m['source_input_manifest_SHA256']==d['input_manifest_SHA256']
 specs={s['model_id']:s for s in d['models']};assert set(specs)==set(MODEL_IDS)
 for s in specs.values():assert sha(ORIGINAL/'draft'/s['path'])==s['SHA256'],'C05_MODEL_LINEAGE_CHANGED'
 games=sorted([g for g in d['candidate_games'] if g['game_id'] not in m['games']],key=lambda g:(g['kickoff'],g['game_id']))
 assert games and games[0]['game_id']==TARGET,'C05_PREDECLARED_EVENT_ORDER_CHANGED'
 rows=read(ORIGINAL/'draft/DRAFT_FORECASTS.json.xz')
 return m,d,specs,rows,dict(original_run=binding(ORIGINAL/'RUN.json'),original_draft=binding(ORIGINAL/'draft/DRAFT.json'),original_prepared_rows=binding(ORIGINAL/'draft/DRAFT_FORECASTS.json.xz'),original_feature_input=binding(ORIGINAL/'draft/MODEL_INPUT_MANIFEST.json'),model_producer_commit=d['code_commit'],model_producer_code_SHA256=d['code_SHA256'],model_feature_cutoff_UTC=d['input_cutoff_UTC'],football_source_cutoff_UTC='2026-11-10T18:55:28.982066+00:00',models=[dict(s,path=str((ORIGINAL/'draft'/s['path']).relative_to(ROOT))) for s in specs.values()],target_event=games[0])

def source_inputs(source=SOURCE,at=None):
 source=Path(source);m=read(source/'INPUT_MANIFEST.json');at=aware(now()).timestamp() if at is None else float(at)
 # Field names are explicit in the source owner's retained contract.
 roster=m['roster_projection'];p=ROOT/roster['path'];assert p.resolve().is_relative_to(ROOT)
 assert sha(p)==roster['SHA256'] and p.stat().st_size==roster['bytes'],'C05_ROSTER_BYTES_CHANGED'
 s=m['roster_source'];assert s.get('HTTP_status')==200 and s.get('state')=='RECEIVED'
 published=parsedate_to_datetime(s['HTTP_Last_Modified']).timestamp();observed=aware(s['observed_UTC']).timestamp()
 assert 0<=at-published<=36*3600 and observed<=at,'C05_ROSTER_STALE_OR_FUTURE'
 assert m['roster_contract']=='NFLVERSE_CURRENT_KNOWN_SEASON_ROSTER_SNAPSHOT-v1' and m.get('roster_week') is None
 assert m['candidate_game']['game_id']==TARGET
 assert aware(m['actual_eligibility_cutoff_UTC']).timestamp()<=at and observed<=aware(m['actual_eligibility_cutoff_UTC']).timestamp()
 return m,read(p)

def current_board(roster,game,prepared):
 """Build current eligibility without appearances/target labels; retain every basic row."""
 ids=collections.Counter(r.get('gsis_id') for r in roster if re.fullmatch(r'00-\d{7}',str(r.get('gsis_id'))))
 frozen={(r['model_id'],r['game_id'],r['player_id']):r for r in prepared};assert len(frozen)==len(prepared)
 board=[];selected=[]
 for i,r in enumerate(roster):
  pid=r.get('gsis_id');team=r.get('team');role=r.get('position');status=r.get('status');in_event=team in [game['home_team'],game['away_team']]
  reason=('INVALID_NATIVE_PLAYER_ID' if not re.fullmatch(r'00-\d{7}',str(pid)) else 'DUPLICATE_NATIVE_PLAYER_ID' if ids[pid]!=1 else 'ROSTER_SEASON_MISMATCH' if r.get('season')!=2026 else 'NOT_SELECTED_EVENT_TEAM' if not in_event else 'B_OWNED_QB_BASIC_ONLY' if role=='QB' else 'UNSUPPORTED_ROLE' if role not in ['RB','WR','TE'] else 'CURRENT_ROSTER_'+str(status) if status!='ACT' else None)
  eligible=reason is None;missing=[]
  if eligible:
   for model in MODEL_IDS:
    old=frozen.get((model,game['game_id'],pid))
    if old is None:missing.append(model+':NO_BOUND_FROZEN_FEATURES')
    elif old['team']!=team or old['position']!=role or old['opponent_team']!=(game['away_team'] if team==game['home_team'] else game['home_team']) or old['kickoff']!=game['kickoff']:missing.append(model+':CURRENT_ID_TEAM_ROLE_OR_EVENT_MISMATCH')
   reason='FROZEN_FEATURE_UNAVAILABLE' if missing else 'AVAILABLE_ALL_THREE_BOUND_MODELS'
  b=dict(basic_id=i,player_id=pid,name=r.get('full_name'),team=team,position=role,roster_status=status,roster_season=r.get('season'),roster_week=None,game_id=game['game_id'] if in_event else None,eligible_current_query=eligible,available_all_models=reason=='AVAILABLE_ALL_THREE_BOUND_MODELS',reason=reason,model_unavailability=missing,starter_state='UNKNOWN_NOT_INFERRED',injury_state='UNKNOWN_NO_QUALIFIED_INJURY_FEED',individual_transaction_effective_UTC=None)
  board.append(b)
  if b['available_all_models']:selected.extend(frozen[(model,game['game_id'],pid)] for model in MODEL_IDS)
 return board,selected

def infer_rows(selected,specs,executed_UTC=None):
 """Pure safe-model inference against the exact bound frozen input vectors."""
 from scipy.stats import poisson
 out=[];maxdelta=0.
 for name in MODEL_IDS:
  old=sorted([r for r in selected if r['model_id']==name],key=lambda r:(r['game_id'],r['player_id']))
  if not old:continue
  meta=read(ORIGINAL/'draft'/specs[name]['path']);assert meta['feature_order']==old[0]['feature_order']
  assert all(r['feature_order']==meta['feature_order'] and r['model_SHA256']==specs[name]['SHA256'] for r in old)
  x=np.asarray([r['features'] for r in old],float)
  with threadpool_limits(limits=1):
   if meta['family']=='LEAF':
    laws=infer_forest(meta['model'],x,[r['position'] for r in old]);pred=[dict(mean=l.mean(),median=l.quantile(.5),p05=l.quantile(.05),p95=l.quantile(.95),law=law_data(l)) for l in laws]
   else:
    assert meta['family']=='POISSON';mu=pooled_mu(meta['model'],x,None);pred=[dict(mean=float(v),median=float(poisson.ppf(.5,v)),p05=float(poisson.ppf(.05,v)),p95=float(poisson.ppf(.95,v)),law=dict(kind='POISSON',mu=float(v),assumption='REGISTERED_POISSON_OUTCOME_LAW_CONDITIONAL_ON_APPEARANCE')) for v in mu]
  at=executed_UTC or now()
  for r,v in zip(old,pred):
   maxdelta=max(maxdelta,abs(v['mean']-r['mean']));assert close(v['mean'],r['mean']) and all(v[k]==r[k] for k in ['median','p05','p95']),'C05_FROZEN_MODEL_PARITY_FAILED'
   z=dict(r);z.update(v,original_prepared_inference_UTC=r['inference_UTC'],inference_UTC=at,information_policy=POLICY,state='NEW_INFERENCE_NOT_ISSUED',model_producer_commit='9994055c8dd666be4564e066579856091cb4011e',line=None,selected_side=None,probability_at_line=None,confidence=None,EV=None)
   out.append(z)
 return out,maxdelta

def prepare(source=SOURCE):
 _,d,specs,old,lin=lineage();m,roster=source_inputs(source);assert m['candidate_game']==lin['target_event'],'C05_EVENT_CONTRACT_CHANGED'
 board,selected=current_board(roster,lin['target_event'],old)
 return dict(schema='C05-METADATA-PREPARE-v1',created_UTC=now(),basic_rows=len(board),eligible=sum(b['eligible_current_query'] for b in board),available_players=sum(b['available_all_models'] for b in board),unavailable_players=sum(b['eligible_current_query'] and not b['available_all_models'] for b in board),forecast_rows=len(selected),new_fits=0,information_policy=POLICY,information_cutoff_UTC=d['input_cutoff_UTC'],current_eligibility_cutoff_UTC=m['actual_eligibility_cutoff_UTC'],target_event=lin['target_event'],source_INPUT_SHA256=sha(Path(source)/'INPUT_MANIFEST.json'))

def task_guard(extra=()):
 from forward_budget_v4 import complete_C_roots,tree_bytes
 roots=complete_C_roots([ROOT,*Path('/workspace').glob('c0[45]*'),*extra]);total=sum(tree_bytes(p) for p in roots)
 assert total<=read(REG)['whole_C_bytes_cap_unchanged'],'C05_WHOLE_C_BYTE_CAP'
 return total

def infer_draft(output,source=SOURCE):
 reg=read(REG);scope=reg['forward_capture'];assert scope['new_fits_max']==0 and scope.get('new_capture_execution_authorized') is True,'C05_ROOT_AUTHORIZATION_REQUIRED'
 bind=committed_bindings();assert not git('status','--porcelain'),'C05_WHOLE_TREE_MUST_BE_CLEAN'
 p=Path(output).resolve();assert not p.is_relative_to(ROOT) and not p.exists(),'C05_IMMUTABLE_EXTERNAL_DRAFT_REQUIRED'
 p.mkdir();started=now();cpu=time.process_time();wall=time.monotonic();attempt=dict(started_UTC=started,state='INFERENCE_ATTEMPT_NO_FIT',new_fits=0,**bind);write(p/'ATTEMPT.json',attempt,True)
 try:
  task_guard([p]);_,d,specs,old,lin=lineage();source_m,roster=source_inputs(source);assert source_m['candidate_game']==lin['target_event']
  board,selected=current_board(roster,lin['target_event'],old);assert selected,'C05_NO_SUPPORTED_CURRENT_QUERY'
  rows,delta=infer_rows(selected,specs)
  for r in rows:r.update(eligibility_information_cutoff_UTC=source_m['actual_eligibility_cutoff_UTC'],current_roster_observed_UTC=source_m['roster_source']['observed_UTC'])
  write(p/'FORECASTS_DRAFT.json.xz',rows,True);write(p/'CURRENT_BOARD.json.xz',board,True);write(p/'INPUT_MANIFEST.json',source_m,True)
  manifest=dict(schema='C05-INFERENCE-DRAFT-v1',created_UTC=now(),started_UTC=started,**bind,source_input=binding(Path(source)/'INPUT_MANIFEST.json'),lineage=lin,target_event=lin['target_event'],information_policy=POLICY,information_cutoff_UTC=d['input_cutoff_UTC'],eligibility_input_cutoff_UTC=source_m['actual_eligibility_cutoff_UTC'],forecast_rows=len(rows),basic_rows=len(board),current_eligible_players=sum(b['eligible_current_query'] for b in board),available_players=sum(b['available_all_models'] for b in board),unavailable_players=sum(b['eligible_current_query'] and not b['available_all_models'] for b in board),new_fits=0,new_inference_rows=len(rows),maximum_point_delta_from_prepared=delta,CPU_seconds=time.process_time()-cpu,wall_seconds=time.monotonic()-wall,peak_RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,environment=dict(python=platform.python_version(),packages={n:version(n) for n in ['numpy','pandas','scipy','scikit-learn','threadpoolctl']}))
  budget=scope['budget'];assert manifest['CPU_seconds']<=budget['CPU_seconds'] and manifest['peak_RSS_bytes']<=budget['RSS_bytes'],'C05_INFERENCE_RESOURCE_CAP'
  attempt.update(state='INFERENCE_COMPLETE_NO_FIT',completed_UTC=now(),CPU_seconds=time.process_time()-cpu);write(p/'ATTEMPT.json',attempt)
  manifest['files']={x.name:dict(bytes=x.stat().st_size,SHA256=sha(x)) for x in p.iterdir()};write(p/'DRAFT.json',manifest,True);task_guard([p]);assert sum(x.stat().st_size for x in p.rglob('*') if x.is_file())<=reg['temporary_bytes_max'],'C05_DRAFT_BYTE_CAP';return manifest
 except Exception as e:
  write(p/'FAILURE.json',dict(at_UTC=now(),error=repr(e),CPU_seconds=time.process_time()-cpu,new_fits=0,attempt_preserved=True),True);raise

def event_version(event):
 return hashlib.sha256(json.dumps({k:event[k] for k in ['game_id','espn_event_id','kickoff_UTC','state']},sort_keys=True).encode()).hexdigest()

def validate_status(source,at,input_sha,after=None):
 source=Path(source);m=read(source/'SOURCE_MANIFEST.json');events=read(source/'events.json');s=m['status_source'];claim=m['status_HTTP_response_clock']
 assert s['state']=='RECEIVED' and s['HTTP_status']==200 and m['model_inputs']['SHA256']==input_sha
 b=dict(path=str((source/'events.json').resolve().relative_to(ROOT)),bytes=(source/'events.json').stat().st_size,SHA256=sha(source/'events.json'),rows=len(events),source_id=s['id'],observed_UTC=s['observed_UTC'],status_response_raw_SHA256=s['SHA256']);assert b==m['events_binding'],'C05_STATUS_BYTE_BINDING'
 assert m['status_execution_code_path']==str(COLLECTOR.relative_to(ROOT)) and m['status_execution_code_SHA256']==sha(COLLECTOR),'C05_STATUS_COLLECTOR_BINDING'
 clock=independent_response_clock(s,at)
 for k in ['HTTP_Age_seconds','HTTP_Date_UTC','HTTP_Date_age_seconds_at_observation','observed_UTC','source_id','response_raw_SHA256','HTTP_Age_raw','HTTP_Date_raw']:assert same_clock_value(clock[k],claim.get(k)),'C05_STATUS_CLOCK_CLAIM:'+k
 assert claim.get('state')=='HTTP_RESPONSE_CLOCK_QUALIFIED' and claim.get('max_age_seconds')==1800 and claim.get('future_Date_clock_skew_tolerance_seconds')==5,'C05_STATUS_CLOCK_POLICY'
 assert after is None or aware(s['observed_UTC']).timestamp()>=after,'C05_STATUS_PRECEDES_CLEAN_GATE'
 assert all(e['source_id']==s['id'] and e['observed_UTC']==s['observed_UTC'] for e in events)
 return m,events,dict(**clock,SOURCE_MANIFEST_SHA256=sha(source/'SOURCE_MANIFEST.json'),events_binding=b)

def issue(draft,output,proof_path,source=SOURCE,run_id='C-C05-NEDET-FIRST-01',allowed_paths=()):
 draft=Path(draft);output=Path(output);source=Path(source);assert not output.exists(),'C05_IMMUTABLE_RUN_EXISTS';assert re.fullmatch(r'[A-Za-z0-9_.-]+',run_id)
 bind=committed_bindings();proof=read(proof_path);at_s=now();at=aware(at_s).timestamp();assert proof['git_status']=='' and all(proof[k]==v for k,v in bind.items()) and 0<=at-aware(proof['created_UTC']).timestamp()<=1800,'C05_CLEAN_PROOF_INVALID'
 allowed=set(allowed_paths)
 assert all((p.startswith('sources/profile-timing-closure-confirm-01/') or p.startswith('reports/profile-timing-closure-confirm-01/forward-source/')) and not p.endswith('.py') for p in allowed),'C05_DIRTY_ALLOWLIST_INVALID'
 dirty=subprocess.check_output(['git','status','--porcelain','--untracked-files=all'],cwd=ROOT,text=True).splitlines();assert all(r[3:] in allowed for r in dirty),'C05_UNEXPECTED_DIRTY_PATH'
 d=read(draft/'DRAFT.json');bound_files(draft,d['files']);assert all(d[k]==v for k,v in bind.items()),'C05_DRAFT_EXECUTOR_CHANGED';assert sha(ROOT/d['source_input']['path'])==d['source_input']['SHA256'],'C05_INPUT_SOURCE_CHANGED'
 source_inputs(source,at);m,events,status=validate_status(source,at,d['source_input']['SHA256'],aware(proof['created_UTC']).timestamp());accepted,rejected=qualified_events([d['target_event']],events,at,after=aware(proof['created_UTC']).timestamp());assert list(accepted)==[TARGET],'C05_NATIVE_EVENT_NOT_ELIGIBLE'
 event=accepted[TARGET];roster=read(draft/'INPUT_MANIFEST.json')['roster_source'];expiry=min(parsedate_to_datetime(roster['HTTP_Last_Modified']).timestamp()+36*3600,d['target_event']['kickoff']-300)
 rows=read(draft/'FORECASTS_DRAFT.json.xz')
 for r in rows:
  r.update(run_id=run_id,forecast_id=hashlib.sha256((run_id+'|'+r['model_id']+'|'+r['game_id']+'|'+r['player_id']+'|rec').encode()).hexdigest()[:24],state='ISSUED_FROZEN_FOOTBALL_SHADOW_AWAITING_GITHUB_PROOF',issued_UTC=at_s,generated_UTC=at_s,native_status_observed_UTC=event['observed_UTC'],event_version=event_version(event),event_state=event['state'],native_event_source=event['source_id'],expires_UTC=pd.Timestamp(expiry,unit='s',tz='UTC').isoformat(),expiry_action='EXPIRE_CURRENT_USE_NOT_ORIGINAL_GRADING_SNAPSHOT',lead_seconds_at_issuance=r['kickoff']-at)
 output.mkdir(parents=True);write(output/'FORECASTS.json.xz',rows,True);write(output/'CURRENT_BOARD.json.xz',read(draft/'CURRENT_BOARD.json.xz'),True);write(output/'INFERENCE_DRAFT.json',d,True);write(output/'CLEAN_START_PROOF.json',proof,True);write(output/'INPUT_MANIFEST.json',read(draft/'INPUT_MANIFEST.json'),True);write(output/'STATUS_SOURCE_MANIFEST.json',m,True);write(output/'NATIVE_STATUS.json',events,True);write(output/'INDEPENDENT_STATUS_VERIFICATION.json',status,True)
 for p in draft.iterdir():
  if p.is_file():
   target=output/'inference_draft'/p.name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(p.read_bytes())
 manifest=dict(schema=SCHEMA,run_id=run_id,created_UTC=at_s,issued_UTC=at_s,**bind,lineage=d['lineage'],source_input=d['source_input'],source_status_path=str((source/'SOURCE_MANIFEST.json').relative_to(ROOT)),information_policy=POLICY,information_cutoff_UTC=d['information_cutoff_UTC'],eligibility_input_cutoff_UTC=d['eligibility_input_cutoff_UTC'],forecast_rows=len(rows),unique_players=len({r['player_id'] for r in rows}),games=[TARGET],first_kickoff_UTC=min(r['kickoff_UTC'] for r in rows),new_fits=0,new_inference_rows=len(rows),real_offers=0,real_selections=0,primary_replacement=False,original_website_incumbent=False,current_eligible_players=d['current_eligible_players'],available_players=d['available_players'],unavailable_players=d['unavailable_players'],publication_state='AWAITING_GITHUB_SERVER_PROOF',conditioning='Conditionalonappearance;currentknownrosterisnotstarterhealthorgamedaymembership')
 manifest['files']={p.relative_to(output).as_posix():dict(bytes=p.stat().st_size,SHA256=sha(p)) for p in output.rglob('*') if p.is_file()};assert sum(x['bytes'] for x in manifest['files'].values())<=read(REG)['forward_capture']['budget']['new_public_bytes_max'],'C05_PUBLIC_BYTE_CAP';write(output/'RUN.json',manifest,True);task_guard([draft]);assert sum(p.stat().st_size for p in output.rglob('*') if p.is_file())<=read(REG)['forward_capture']['budget']['new_public_bytes_max'],'C05_PUBLIC_TOTAL_BYTE_CAP';return manifest

def same_law(a,b):
 if a.get('kind')=='POISSON' or b.get('kind')=='POISSON':return a.get('kind')==b.get('kind')=='POISSON' and close(a['mu'],b['mu'])
 return a['prior']==b['prior'] and a['scale']==b['scale'] and a['alpha']==b['alpha'] and a['values']==b['values'] and np.allclose(a['weights'],b['weights'],rtol=1e-12,atol=1e-12)

def validate_run(run,check_clock=False):
 run=Path(run);m=read(run/'RUN.json');assert m['schema']==SCHEMA and m['information_policy']==POLICY;bound_files(run,m['files']);assert m['new_fits']==m['real_offers']==m['real_selections']==0 and m['primary_replacement'] is False
 original,d,specs,prepared,lin=lineage();assert m['lineage']==lin,'C05_ORIGINAL_LINEAGE_CHANGED'
 draft=read(run/'INFERENCE_DRAFT.json');assert draft==read(run/'inference_draft/DRAFT.json'),'C05_DRAFT_METADATA_CHANGED';bound_files(run/'inference_draft',draft['files']);assert all(m[k]==draft[k] for k in ['code_commit','code_SHA256','registration_SHA256','information_cutoff_UTC','eligibility_input_cutoff_UTC','source_input','lineage'])
 at=aware(m['issued_UTC']).timestamp();proof=read(run/'CLEAN_START_PROOF.json');assert proof['git_status']=='' and all(m[k]==proof[k] for k in ['code_commit','code_SHA256','registration_SHA256']);assert 0<=at-aware(proof['created_UTC']).timestamp()<=1800
 source=(ROOT/Path(m['source_status_path']).parent).resolve();assert source.is_relative_to(ROOT.resolve()),'C05_SOURCE_PATH_ESCAPE';inp,roster=source_inputs(source,at);assert read(run/'INPUT_MANIFEST.json')==inp and sha(source/'INPUT_MANIFEST.json')==m['source_input']['SHA256']
 sm,events,status=validate_status(source,at,m['source_input']['SHA256'],aware(proof['created_UTC']).timestamp());assert sm==read(run/'STATUS_SOURCE_MANIFEST.json') and events==read(run/'NATIVE_STATUS.json') and status==read(run/'INDEPENDENT_STATUS_VERIFICATION.json')
 accepted,_=qualified_events([lin['target_event']],events,at,after=aware(proof['created_UTC']).timestamp());assert list(accepted)==m['games']==[TARGET]
 board,selected=current_board(roster,lin['target_event'],prepared);assert board==read(run/'CURRENT_BOARD.json.xz')
 rows=read(run/'FORECASTS.json.xz');assert len(rows)==len(selected)==m['forecast_rows'] and len({r['forecast_id'] for r in rows})==len(rows)
 assert len({r['player_id'] for r in rows})==m['available_players']==m['unique_players']
 assert sum(b['eligible_current_query'] for b in board)==m['current_eligible_players'] and sum(b['eligible_current_query'] and not b['available_all_models'] for b in board)==m['unavailable_players']
 originals={(r['model_id'],r['game_id'],r['player_id']):r for r in selected};fresh={(r['model_id'],r['game_id'],r['player_id']):r for r in read(run/'inference_draft/FORECASTS_DRAFT.json.xz')}
 assert set(fresh)==set(originals),'C05_INFERENCE_QUERY_MASK_CHANGED'
 for r in rows:
  q=fresh[(r['model_id'],r['game_id'],r['player_id'])];assert all(r.get(k)==v for k,v in q.items() if k!='state'),'C05_INFERENCE_BYTES_CHANGED_BEFORE_ISSUE'
  old=originals[(r['model_id'],r['game_id'],r['player_id'])];assert r['category']=='rec' and r['information_policy']==POLICY
  assert all(r[k] is None for k in ['line','selected_side','probability_at_line','confidence','EV']) and not any(k in r for k in ['actual','played','values','realized_starter'])
  assert all(r.get(k)==v for k,v in old.items() if k not in ['state','inference_UTC','mean','median','p05','p95','law']),'C05_PREPARED_FEATURE_OR_METADATA_CHANGED'
  assert r['features']==old['features'] and r['feature_order']==old['feature_order'] and r['model_SHA256']==old['model_SHA256'] and r['information_cutoff_UTC']==lin['model_feature_cutoff_UTC']
  assert r['original_prepared_inference_UTC']==old['inference_UTC'] and aware(r['information_cutoff_UTC'])<=aware(r['original_prepared_inference_UTC'])<aware(r['inference_UTC'])<aware(m['issued_UTC'])<aware(r['expires_UTC'])<=aware(r['kickoff_UTC'])
  assert aware(r['eligibility_information_cutoff_UTC'])<=aware(r['inference_UTC']) and r['native_status_observed_UTC']==accepted[TARGET]['observed_UTC']
  law=load_capture_law(r['law']);assert close(r['mean'],law.mean()) and all(r[k]==law.quantile(p) for k,p in [('median',.5),('p05',.05),('p95',.95)])
  assert close(r['mean'],old['mean']) and all(r[k]==old[k] for k in ['median','p05','p95'])
  assert r['event_version']==event_version(accepted[TARGET]) and all(math.isfinite(r[k]) and r[k]>=0 for k in ['mean','median','p05','p95'])
 # Re-infer every saved vector from the bound original safe models, no fit.
 reinferred,_=infer_rows(selected,specs,executed_UTC=rows[0]['inference_UTC']);new={(r['model_id'],r['player_id']):r for r in reinferred}
 assert all(close(r['mean'],new[(r['model_id'],r['player_id'])]['mean']) and r['median']==new[(r['model_id'],r['player_id'])]['median'] and same_law(r['law'],new[(r['model_id'],r['player_id'])]['law']) for r in rows),'C05_SAFE_RESTORATION_FAILED'
 if check_clock:assert pd.Timestamp.now(tz='UTC')+pd.Timedelta(seconds=300)<min(aware(r['kickoff_UTC']) for r in rows),'CAPTURE_SERVER_CHECK_TOO_LATE'
 return m,[dict(r,policy_id='C05::'+r['model_id'],scoring_contract_id='official-player-fullgame-OT-v1') for r in rows]

def validate_receipt(run,receipt,m,rows):
 assert receipt['schema']==RECEIPT_SCHEMA and receipt['qualified_prospective'] is True and receipt['run_id']==m['run_id']
 assert receipt['forecast_blob_SHA256']==sha(Path(run)/'FORECASTS.json.xz') and receipt['run_manifest_SHA256']==sha(Path(run)/'RUN.json')
 assert receipt['fresh_GitHub_bytes_verified'] is True and receipt['not_client_commit_dates'] is True
 created=aware(receipt['server_run_created_UTC']);started=aware(receipt['server_run_started_UTC']);done=aware(receipt['server_check_completed_UTC']);assert created<=started<=done and aware(m['issued_UTC'])<=done
 assert all(done+pd.Timedelta(seconds=300)<aware(r['kickoff_UTC']) for r in rows),'LATE_GITHUB_PERSISTENCE';return done

if __name__=='__main__':
 p=argparse.ArgumentParser();s=p.add_subparsers(dest='command',required=True)
 a=s.add_parser('prepare');a.add_argument('--source',type=Path,default=SOURCE)
 a=s.add_parser('infer-draft');a.add_argument('--source',type=Path,default=SOURCE);a.add_argument('--output',type=Path,required=True)
 a=s.add_parser('clean-start');a.add_argument('--output',type=Path,required=True)
 a=s.add_parser('issue');a.add_argument('--draft',type=Path,required=True);a.add_argument('--source',type=Path,default=SOURCE);a.add_argument('--output',type=Path,required=True);a.add_argument('--proof',type=Path,required=True);a.add_argument('--run-id',required=True);a.add_argument('--status-generated-path',action='append',default=[])
 a=p.parse_args();r=prepare(a.source) if a.command=='prepare' else infer_draft(a.output,a.source) if a.command=='infer-draft' else clean_start(a.output) if a.command=='clean-start' else issue(a.draft,a.output,a.proof,a.source,a.run_id,a.status_generated_path)
 print(json.dumps({k:v for k,v in r.items() if k not in ['files','code_SHA256','lineage']},indent=2))
