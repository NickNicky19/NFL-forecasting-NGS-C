"""Manual C04 forecast-only capture; no acquisition, scheduler or implicit fits.

Prepare is metadata-only. Draft fits require a separate root authorization and
committed code. Issue consumes the draft after a separately refreshed native
event gate. Football-input time, inference time, issue time and later GitHub
persistence remain different clocks. Safe primitive JSON models only.
"""
from __future__ import annotations
import argparse, collections, copy, gzip, hashlib, io, json, lzma, re
import resource, signal, subprocess, time, zipfile, platform
from importlib.metadata import version
from email.utils import parsedate_to_datetime
from pathlib import Path
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'sources/profile-closure-next-02'
REG=ROOT/'protocol/PROFILE_CLOSURE_NEXT_02_C.json'
STATUS_CODE_PATH=ROOT/'reports/profile-closure-next-02/current-source/acquire_current_sources.py'
FINALITY_CODE_BINDING=ROOT/'reports/profile-closure-next-02/current-source/FINALITY_EXECUTION_BINDING.json'
ROSTER_CONTRACT='NFLVERSE_CURRENT_KNOWN_SEASON_ROSTER_SNAPSHOT-v1'
MODELS=['C_V4_RETAINED_REFERENCE_OBSERVED','C_V11_P1_E2_POOLED_7D','C04_F3_PROFILE_1D_SHADOW']
CODE=['receiving_current_capture_c04.py','receiving_timing_c04.py','prospective_v4.py',
      'data_v2.py','contracts_v2.py','laws_v2.py','safe_models_v4.py',
      'context_features_c01.py','context_experiment_c01.py','receiving_defense_c03.py',
      'receiving_profiles_c02.py','forward_sources_v4.py','context_sources_c01.py','forward_budget_v4.py']

def now(): return pd.Timestamp.now(tz='UTC').isoformat()
def timestamp(value):
    t=pd.Timestamp(value)
    if t.tzinfo is None: raise ValueError('TIMEZONE_AWARE_CLOCK_REQUIRED')
    return t.timestamp()
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def clean(x):
    if isinstance(x,dict): return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple,np.ndarray)): return [clean(v) for v in x]
    if isinstance(x,(bool,np.bool_)): return bool(x)
    if isinstance(x,(int,np.integer)): return int(x)
    if isinstance(x,(float,np.floating)): return float(x) if np.isfinite(x) else None
    return x
def read(path):
    p=Path(path);b=p.read_bytes()
    return json.loads(lzma.decompress(b) if p.suffix=='.xz' else gzip.decompress(b) if p.suffix=='.gz' else b)
def write(path,obj,*,exclusive=False):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    b=(json.dumps(clean(obj),separators=(',',':'),allow_nan=False)+'\n').encode()
    if p.suffix=='.xz': b=lzma.compress(b,preset=6)
    with p.open('xb' if exclusive else 'wb') as f: f.write(b)
def git(*args): return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()
def extra_code_paths():
    paths=[STATUS_CODE_PATH]
    if FINALITY_CODE_BINDING.exists(): paths += [FINALITY_CODE_BINDING,ROOT/read(FINALITY_CODE_BINDING)['execution_code']['path']]
    return paths
def code_bindings(): return {**{f:sha(ROOT/'src'/f) for f in CODE},**{str(p.relative_to(ROOT)):sha(p) for p in extra_code_paths()}}
def committed_bindings():
    for p in [*(ROOT/'src'/f for f in CODE),REG,*extra_code_paths()]:
        rel=p.relative_to(ROOT).as_posix()
        committed=subprocess.check_output(['git','show','HEAD:'+rel],cwd=ROOT)
        if hashlib.sha256(committed).hexdigest()!=sha(p): raise RuntimeError('UNCOMMITTED_CODE_OR_POLICY:'+rel)
    return dict(code_commit=git('rev-parse','HEAD'),code_SHA256=code_bindings(),registration_SHA256=sha(REG))
def record_clean_start(path):
    if git('status','--porcelain'): raise RuntimeError('COMMIT_POLICY_AND_CODE_BEFORE_ISSUANCE')
    p=Path(path).resolve()
    if p.is_relative_to(ROOT): raise ValueError('CLEAN_PROOF_MUST_BE_OUTSIDE_REPOSITORY')
    proof=dict(created_UTC=now(),git_status='',**committed_bindings())
    write(p,proof,exclusive=True);return proof

def input_manifest_path(source):
    p=Path(source)/'MODEL_INPUT_MANIFEST_V2.json'
    return p if p.exists() else Path(source)/'MODEL_INPUT_MANIFEST.json'

def validate_inputs(source=SOURCE,at=None):
    source=Path(source);m=read(input_manifest_path(source))
    at=timestamp(now()) if at is None else float(at)
    cutoff=timestamp(m['actual_input_cutoff_UTC'])
    if cutoff>at: raise ValueError('INPUT_CUTOFF_FROM_FUTURE')
    if m['roster_contract']!=ROSTER_CONTRACT or m['roster_week'] is not None: raise ValueError('WRONG_ROSTER_CONTRACT')
    for f in m['files']:
        p=ROOT/f['path']
        if p.stat().st_size!=f['bytes'] or sha(p)!=f['SHA256']: raise ValueError('SOURCE_BYTES_CHANGED:'+f['path'])
    for observed in m['source_observed'].values():
        if timestamp(observed)>cutoff: raise ValueError('SOURCE_OBSERVED_AFTER_FEATURE_CUTOFF')
    r=next(x for x in m['sources'] if x['id']=='CURRENT_SEASON_ROSTER')
    published=parsedate_to_datetime(r['HTTP_Last_Modified']).timestamp()
    if not 0<=at-published<=36*3600: raise ValueError('CURRENT_ROSTER_STALE_OR_FUTURE')
    if timestamp(r['observed_UTC'])>at: raise ValueError('ROSTER_OBSERVATION_FROM_FUTURE')
    if 'preceding_input_manifest' in m:
        previous=m['preceding_input_manifest'];p=ROOT/previous['path']
        if sha(p)!=previous['SHA256']: raise ValueError('PRECEDING_INPUT_BYTES_CHANGED')
        old=read(p)
        if old['files']!=m['files'] or old['actual_input_cutoff_UTC']!=m['football_predictor_cutoff_UTC']: raise ValueError('PREDICTOR_SNAPSHOT_CHANGED_WHILE_QUALIFYING_FINALITY')
        proof=m['finality_proof'];p=ROOT/proof['path']
        if sha(p)!=proof['SHA256'] or p.stat().st_size!=proof['bytes']: raise ValueError('FINALITY_PROOF_BYTES_CHANGED')
    return m

def query_universe(roster,games,season):
    """Preserve all basic records; future queries require no target stat row."""
    from forward_sources_v4 import team, native
    seen=collections.Counter(str(r.get('gsis_id')) for r in roster if re.fullmatch(r'00-\d{7}',str(r.get('gsis_id'))))
    basic=[];queries=[]
    for i,r in enumerate(roster):
        pid=r.get('gsis_id');role=r.get('position');tm=team(r.get('team'))
        events=[g for g in games if tm in [team(g['home_team']),team(g['away_team'])]]
        reason=('INVALID_NATIVE_PLAYER_ID' if not re.fullmatch(r'00-\d{7}',str(pid)) else
                'DUPLICATE_NATIVE_PLAYER_ID' if seen[pid]!=1 else
                'ROSTER_SEASON_MISMATCH' if r.get('season')!=season else
                'UNSUPPORTED_ROLE' if role not in ['QB','RB','WR','TE'] else
                'B_OWNED_QB_BASIC_ONLY' if role=='QB' else
                'CURRENT_ROSTER_'+str(r.get('status')) if r.get('status')!='ACT' else
                'NO_CANDIDATE_SCHEDULE_EVENT' if not events else 'DRAFT_CANDIDATE_PENDING_NATIVE_EVENT')
        base=dict(basic_id=i,player_id=pid,name=r.get('full_name'),position=role,team=tm,
                  roster_season=r.get('season'),roster_week=None,roster_status=r.get('status'),
                  individual_transaction_effective_UTC=None,individual_clock_state='UNKNOWN_NOT_FILLED_FROM_HTTP_CLOCK',
                  starter_state='UNKNOWN_NOT_INFERRED',injury_state='UNKNOWN_NO_QUALIFIED_INJURY_FEED',
                  candidate_game_ids=[g['game_id'] for g in events],state=reason)
        basic.append(base)
        if reason!='DRAFT_CANDIDATE_PENDING_NATIVE_EVENT': continue
        for g in events:
            queries.append(dict(base,game_id=g['game_id'],season=int(g['season']),week=int(g['week']),
                         opponent_team=team(g['away_team']) if tm==team(g['home_team']) else team(g['home_team']),
                         home_team=team(g['home_team']),away_team=team(g['away_team']),
                         espn_event_id=native(g['espn']),kickoff=float(g['kickoff']),
                         kickoff_UTC=pd.Timestamp(g['kickoff'],unit='s',tz='UTC').isoformat()))
    if len({(r['game_id'],r['player_id']) for r in queries})!=len(queries): raise ValueError('DUPLICATE_FUTURE_QUERY')
    return basic,queries

def qualified_events(candidates,events,at,*,after=None):
    from forward_sources_v4 import match_event
    byid=collections.defaultdict(list)
    for e in events: byid[str(e['espn_event_id'])].append(e)
    accepted={};rejected=[]
    for g in candidates:
        matches=byid.get(str(g['espn']),[]);reason=None
        if len(matches)!=1: reason='NATIVE_EVENT_MISSING_OR_DUPLICATED'
        else:
            e=matches[0]
            try:
                observed=timestamp(e['observed_UTC'])
                if not 0<=at-observed<=1800: reason='NATIVE_STATUS_STALE_OR_FUTURE'
                elif after is not None and observed<after: reason='STATUS_PRECEDES_CLEAN_START'
                elif str(e.get('competition_id'))!=str(e['espn_event_id']): reason='NATIVE_COMPETITION_EVENT_ID_CONFLICT'
                elif not match_event(g,e,at) or e['kickoff']<=at+300: reason='STARTED_COMPLETED_CHANGED_OR_TOO_CLOSE'
                elif e.get('game_id',g['game_id'])!=g['game_id']: reason='CANONICAL_GAME_ID_MISMATCH'
            except (AssertionError,KeyError,ValueError,TypeError): reason='NATIVE_EVENT_CONTRACT_MISMATCH'
            if reason is None: accepted[g['game_id']]=e
        if reason: rejected.append(dict(game_id=g['game_id'],reason=reason))
    return accepted,rejected

def independent_response_clock(source,at):
    """Separate calculation from the source collector's claimed qualification.

    A freshly recorded local receipt cannot revive a two-hour cached response.
    Check each supplied clock; an unknown clock is never interpreted as zero.
    """
    observed=timestamp(source['observed_UTC']);elapsed=float(at)-observed
    if not 0<=elapsed<=1800: raise ValueError('STATUS_RECEIPT_STALE_OR_FUTURE')
    raw_age=source.get('HTTP_Age');raw_date=source.get('HTTP_Date');age=None;date=None;date_age=None
    if raw_age not in [None,'']:
        try: age=float(raw_age)
        except (ValueError,TypeError): raise ValueError('STATUS_HTTP_AGE_MALFORMED')
        if not np.isfinite(age) or not 0<=age<=1800 or age+elapsed>1800: raise ValueError('STATUS_HTTP_AGE_STALE_INVALID_OR_EXPIRED')
    if raw_date not in [None,'']:
        try:
            parsed=parsedate_to_datetime(raw_date)
            if parsed.tzinfo is None: raise ValueError('TIMEZONE_UNKNOWN')
            date=parsed.timestamp();date_age=observed-date
        except (ValueError,TypeError,OverflowError): raise ValueError('STATUS_HTTP_DATE_MALFORMED')
        if not -5<=date_age<=1800 or not -5<=float(at)-date<=1800: raise ValueError('STATUS_HTTP_DATE_STALE_FUTURE_OR_EXPIRED')
    if age is None and date is None: raise ValueError('STATUS_HTTP_AGE_AND_DATE_UNKNOWN')
    return dict(HTTP_Age_seconds=age,HTTP_Date_UTC=pd.Timestamp(date,unit='s',tz='UTC').isoformat() if date is not None else None,
                HTTP_Date_age_seconds_at_observation=date_age,observed_UTC=source['observed_UTC'],source_id=source['id'],
                response_raw_SHA256=source['SHA256'],HTTP_Age_raw=raw_age,HTTP_Date_raw=raw_date,
                effective_HTTP_Age_seconds_at_issuance=age+elapsed if age is not None else None,
                HTTP_Date_age_seconds_at_issuance=float(at)-date if date is not None else None)

def same_clock_value(a,b):
    # Unix float subtraction and datetime timedeltas differ below a microsecond.
    if isinstance(a,(float,int)) and isinstance(b,(float,int)):
        return bool(np.isfinite(a) and np.isfinite(b) and abs(a-b)<=1e-6)
    return a==b

def validate_status_snapshot(events_path,at,*,input_manifest_SHA256,after=None):
    """Verify recoverable derivative provenance as well as native event facts."""
    p=Path(events_path);manifest=read(p.parent/'SOURCE_MANIFEST.json');events=read(p)
    if not isinstance(events,list): raise ValueError('STATUS_EVENTS_MUST_BE_BOUND_LIST')
    binding=manifest['events_binding'];source=manifest['status_source'];claimed=manifest['status_HTTP_response_clock']
    if source.get('status')!=200 or source.get('state')!='RECEIVED': raise ValueError('STATUS_RESPONSE_NOT_RECEIVED_200')
    expected=dict(path=p.resolve().relative_to(ROOT.resolve()).as_posix(),bytes=p.stat().st_size,SHA256=sha(p),rows=len(events),
                  source_id=source['id'],observed_UTC=source['observed_UTC'],status_response_raw_SHA256=source['SHA256'])
    if binding!=expected: raise ValueError('STATUS_EVENT_BYTES_OR_SOURCE_BINDING_MISMATCH')
    if manifest['model_inputs']['SHA256']!=input_manifest_SHA256: raise ValueError('STATUS_MODEL_INPUT_MANIFEST_MISMATCH')
    if manifest['actual_status_observed_UTC']!=source['observed_UTC']: raise ValueError('STATUS_MANIFEST_OBSERVATION_MISMATCH')
    if manifest['status_execution_code_SHA256']!=sha(STATUS_CODE_PATH): raise ValueError('STATUS_EXECUTING_COLLECTOR_CODE_MISMATCH')
    if not re.fullmatch('[0-9a-f]{64}',source['SHA256']): raise ValueError('STATUS_RAW_HASH_INVALID')
    if after is not None and timestamp(source['observed_UTC'])<after: raise ValueError('STATUS_PRECEDES_CLEAN_START')
    actual=independent_response_clock(source,at)
    for key in ['HTTP_Age_seconds','HTTP_Date_UTC','HTTP_Date_age_seconds_at_observation','observed_UTC','source_id','response_raw_SHA256','HTTP_Age_raw','HTTP_Date_raw']:
        if not same_clock_value(actual[key],claimed.get(key)): raise ValueError('STATUS_CLAIMED_CLOCK_MISMATCH:'+key)
    if claimed.get('state')!='HTTP_RESPONSE_CLOCK_QUALIFIED' or claimed.get('max_age_seconds')!=1800 or claimed.get('future_Date_clock_skew_tolerance_seconds')!=5: raise ValueError('STATUS_CLAIMED_CLOCK_POLICY_MISMATCH')
    for e in events:
        if e.get('source_id')!=source['id'] or e.get('observed_UTC')!=source['observed_UTC']: raise ValueError('STATUS_EVENT_OBSERVATION_OR_SOURCE_MISMATCH')
    return events,dict(state='INDEPENDENT_ISSUER_HTTP_AND_DERIVATIVE_BINDINGS_PASS',**actual,events_binding=expected,
                       status_execution_code_SHA256=manifest['status_execution_code_SHA256'],SOURCE_MANIFEST_SHA256=sha(p.parent/'SOURCE_MANIFEST.json'))

def qualified_completed_games(schedule,manifest,proof,cutoff):
    """Retain v4 recent FINAL gate; never infer completion from recent scores alone."""
    from forward_sources_v4 import native,team
    if timestamp(proof['actual_information_cutoff_UTC'])!=cutoff or timestamp(manifest['actual_input_cutoff_UTC'])!=cutoff: raise ValueError('FINALITY_CUTOFF_MISMATCH')
    source=proof['status_source'];claimed=proof['status_HTTP_response_clock']
    if proof['status_execution_code_SHA256']!=sha(STATUS_CODE_PATH):
        if not FINALITY_CODE_BINDING.exists(): raise ValueError('FINALITY_CODE_MISMATCH')
        binding=read(FINALITY_CODE_BINDING);saved=binding['execution_code'];p=ROOT/saved['path']
        if sha(p)!=saved['SHA256'] or p.stat().st_size!=saved['bytes'] or hashlib.sha256(gzip.decompress(p.read_bytes())).hexdigest()!=saved['decoded_SHA256'] or saved['decoded_SHA256']!=proof['status_execution_code_SHA256']: raise ValueError('RETAINED_FINALITY_EXECUTION_CODE_MISMATCH')
        for key,obj in [('model_input_manifest_v2',manifest),('finality_proof',proof)]:
            b=binding[key];p=ROOT/b['path']
            if sha(p)!=b['SHA256'] or read(p)!=obj: raise ValueError('FINALITY_EXECUTION_SOURCE_BINDING_MISMATCH')
    if source is None:
        if proof['events'] or claimed is not None or not proof.get('native_request_failure'): raise ValueError('UNBOUND_FRESH_FINALITY_EVENTS')
        actual=dict(state='NO_NEW_NATIVE_FINALS;FAILED_REQUEST_RETAINED;ONLY_BOUND_OLD_FINALS_USABLE')
    else:
        actual=independent_response_clock(source,cutoff)
        for key in ['HTTP_Age_seconds','HTTP_Date_UTC','HTTP_Date_age_seconds_at_observation','observed_UTC','source_id','response_raw_SHA256','HTTP_Age_raw','HTTP_Date_raw']:
            if not same_clock_value(actual[key],claimed.get(key)): raise ValueError('FINALITY_SOURCE_CLOCK_BINDING_MISMATCH:'+key)
        if source.get('status')!=200 or source.get('state')!='RECEIVED': raise ValueError('FINALITY_SOURCE_NOT_RECEIVED_200')
    byid=collections.defaultdict(list)
    for e in proof['events']:
        if e.get('source_id')!=source['id'] or e.get('observed_UTC')!=source['observed_UTC']: raise ValueError('FINALITY_EVENT_SOURCE_OR_CLOCK_MISMATCH')
        byid[str(e['espn_event_id'])].append(e)
    retained=[]
    for r in proof.get('retained_native_final_proofs',[]):
        p=ROOT/r['path']
        if p.stat().st_size!=r['bytes'] or sha(p)!=r['SHA256']: raise ValueError('RETAINED_FINALITY_BYTES_CHANGED')
        old=read(p)
        if old['event']!=r['event'] or old['source']!=r['status_source']: raise ValueError('RETAINED_FINALITY_EVENT_SOURCE_MISMATCH')
        s=old['source'];e=old['event'];t=timestamp(s['observed_UTC'])
        if not t<=cutoff or s.get('HTTP_status')!=200 or e['source_id']!=s['id'] or e['observed_UTC']!=s['observed_UTC']: raise ValueError('RETAINED_FINALITY_CLOCK_OR_SOURCE_INVALID')
        normalized=dict(s,SHA256=s['raw_SHA256'])
        oldclock=independent_response_clock(normalized,t)
        for key in ['HTTP_Age_seconds','HTTP_Date_UTC','HTTP_Date_age_seconds_at_observation','observed_UTC','source_id','response_raw_SHA256','HTTP_Age_raw','HTTP_Date_raw']:
            if not same_clock_value(oldclock[key],r['HTTP_response_clock_at_original_observation'].get(key)): raise ValueError('RETAINED_FINALITY_HTTP_CLOCK_BINDING_MISMATCH')
        # Prior FINAL remains evidence; never override a present current response.
        if str(e['espn_event_id']) not in byid: byid[str(e['espn_event_id'])].append(e)
        retained.append(dict(path=r['path'],SHA256=r['SHA256'],original_observed_UTC=s['observed_UTC'],native_event_id=e['espn_event_id']))
    for s in proof.get('older_schedule_sources',[]):
        if sha(ROOT/s['path'])!=s['SHA256']: raise ValueError('RETAINED_OFFICIAL_SCHEDULE_BYTES_CHANGED')
    older=set();recent=set();held=set();current=int(manifest['target_season'])
    for g in schedule.to_dict('records'):
        if not (g['kickoff']<cutoff and pd.notna(g['home_score']) and pd.notna(g['away_score'])): continue
        if g['kickoff']<=cutoff-7*86400:
            older.add(g['game_id']);continue
        ee=byid.get(native(g.get('espn')),[])
        valid=False
        if len(ee)==1:
            e=ee[0]
            valid=(e.get('state')=='post' and e.get('completed') is True and e.get('status_name')=='STATUS_FINAL'
                and str(e.get('competition_id'))==str(e['espn_event_id'])
                and abs(float(e['kickoff'])-float(g['kickoff']))<1
                and team(e['home_team'])==team(g['home_team']) and team(e['away_team'])==team(g['away_team'])
                and int(e['season'])==int(g['season']) and int(e['week'])==int(g['week']) and int(e['season_type'])==2
                and e.get('game_id',g['game_id'])==g['game_id'])
        (recent if valid else held).add(g['game_id'])
    current_ids=set(schedule.loc[schedule.season==current,'game_id'])
    expected=older|recent
    if set(manifest['completed_game_ids'])!=expected or set(proof['completed_game_ids'])!=expected: raise ValueError('QUALIFIED_COMPLETED_MEMBERSHIP_MISMATCH')
    for key,values in [('older_final_game_ids',older),('recent_native_final_game_ids',recent),('held_recent_game_ids',held)]:
        if set(proof[key])!=values: raise ValueError('FINALITY_RULE_PARTITION_MISMATCH:'+key)
    return older|recent,dict(current_older_final_games=sorted(older&current_ids),current_recent_native_final_games=sorted(recent&current_ids),
                            held_recent_games=sorted(held),qualification='RETAINED_V4_SEVENDAY_OFFICIAL_FINAL_PLUS_EXACT_NATIVE_RECENT_FINAL',
                            actual_native_source_observed_UTC=source['observed_UTC'] if source else None,independent_clock=actual,
                            retained_finality_receipts=retained,retained_finality_clocks_not_relabeled=True)

def prepare(source=SOURCE,output=None):
    m=validate_inputs(source);games=read(Path(source)/'candidate_schedule.json')['games']
    basic,queries=query_universe(read(Path(source)/'roster_current_season.json'),games,m['target_season'])
    result=dict(schema='C04-CURRENT-PREPARE-v1',created_UTC=now(),source_manifest_SHA256=sha(input_manifest_path(source)),
                input_cutoff_UTC=m['actual_input_cutoff_UTC'],roster_contract=ROSTER_CONTRACT,basic_rows=len(basic),
                candidate_queries=len(queries),candidate_games=len(games),model_names=MODELS,
                state='METADATA_ONLY_NO_FIT_NO_FORECAST_NO_NATIVE_STATUS_ADMISSION',fits=0,issued_rows=0,
                basic_states=dict(collections.Counter(r['state'] for r in basic)),roster_week=None)
    if output: write(output,result,exclusive=True)
    return result

class FrameFiles:
    def __init__(self,facts,schedule): self.frames={'facts.csv.gz':facts,'schedule.csv':schedule}
    def __truediv__(self,name): return io.StringIO(self.frames[name].to_csv(index=False))

def football_inputs(source):
    """All-position totals are computed before the retained role filter."""
    from data_v2 import load
    archive=ROOT/'artifacts/basic-football-facts-v2.1.zip'
    with zipfile.ZipFile(archive) as z:
        old=pd.read_csv(io.BytesIO(z.read('facts.csv.gz')),compression='gzip',low_memory=False)
        schedule=pd.read_csv(io.BytesIO(z.read('schedule.csv')),low_memory=False)
    facts=pd.concat([old[old.season.between(2022,2025)],pd.read_csv(Path(source)/'current_facts_2026.csv.gz',low_memory=False)],ignore_index=True)
    schedule=pd.concat([schedule[schedule.season.between(2022,2025)],pd.read_csv(Path(source)/'schedule.csv')],ignore_index=True)
    if facts.duplicated(['game_id','player_id']).any() or schedule.duplicated('game_id').any(): raise ValueError('DUPLICATE_INPUT_IDENTITY_VERSION')
    counts={}
    for key,f in facts.groupby(['game_id','team'],sort=False):
        a=f[['attempts','completions','targets']].to_numpy(float)
        counts[key]=dict(zip(['attempts','completions','targets'],a.sum(axis=0)))
        counts[key]['complete']=bool(np.isfinite(a).all() and (a>=0).all() and (a==np.floor(a)).all())
    d,g,t=load(FrameFiles(facts,schedule))
    return d,g,t,counts,dict(archive=str(archive.relative_to(ROOT)),SHA256=sha(archive),raw_all_position_rows=len(facts),all_position_team_games=len(counts))

def capped_context(context,cutoff):
    from receiving_timing_c04 import Capped
    shell=copy.copy(context)
    for field in ['players','teams','league','defenses']: setattr(shell,field,Capped(getattr(context,field),cutoff))
    return shell

def current_matrices(source,queries,cutoff):
    from data_v2 import History,vector
    from prospective_v4 import ObservedHistory,qualified_training_frame,held_ungraded_games
    from context_features_c01 import Context,OWN_NAMES,OPP_NAMES
    from receiving_profiles_c02 import BASE_NAMES
    from receiving_defense_c03 import ReceivingDefense,SUPPORT_NAMES
    from receiving_timing_c04 import TimedInputs,Capped
    from context_sources_c01 import pbp_path
    d,g,teams,counts,binding=football_inputs(source)
    source_manifest=read(input_manifest_path(source))
    if 'finality_proof' not in source_manifest: raise RuntimeError('RECENT_GAME_FINALITY_PROOF_REQUIRED_BEFORE_FITS')
    p=ROOT/source_manifest['finality_proof']['path'];proof=read(p)
    if sha(p)!=source_manifest['finality_proof']['SHA256']: raise ValueError('FINALITY_PROOF_BYTES_CHANGED')
    completed,finality=qualified_completed_games(g,source_manifest,proof,cutoff)
    binding.update(finality_proof=source_manifest['finality_proof'],independent_finality=finality)
    held=held_ungraded_games(completed,ROOT/'prospective');completed-=set(held)
    d=qualified_training_frame(d,completed,cutoff);teams=teams[teams.game_id.isin(completed)&(teams.kickoff<cutoff)].copy()
    hist,th=History(d,'player_id'),History(teams,'team')
    observed,ot=ObservedHistory(d,'player_id',cutoff),ObservedHistory(teams,'team',cutoff)
    pool=d[d.position.isin(['RB','WR','TE'])].to_dict('records')
    ordinary=[r for r in pool if r['values']['rec'] is not None]
    f25=pbp_path(2025);f24=ROOT/'sources/player-context-matchup-01/completion-decision-v1/pbp_facts_2024.csv.xz';f26=Path(source)/'pbp_facts_2026.csv.xz'
    frames=[pd.read_csv(p,low_memory=False) for p in [f24,f25,f26]]
    # Same completed/held universe in every procedure, including context priors.
    frames=[f[f.game_id.isin(completed)].copy() for f in frames]
    ctx=Context(frames,d,g,strict=True,all_position_counts=counts)
    oldctx=Context(frames[1:],d,g,strict=True,all_position_counts=counts)
    defense=ReceivingDefense(frames,d,g,context=ctx)
    timed=TimedInputs(pool,hist,th,ctx,defense,1)
    one=[r for r in timed.pool if r['available']<cutoff and r['values']['rec'] is not None]
    seven=[r for r in pool if r['available']<cutoff and r['values']['rec'] is not None]
    oldcurrent=capped_context(oldctx,cutoff)
    def p1(r,q=False):
        ph,tt=(Capped(hist,cutoff),Capped(th,cutoff)) if q else (hist,th)
        own,opp,_=(oldcurrent if q else oldctx).features(r)
        return np.r_[vector(r,'rec',ph,tt,'E0_OP'),own,opp]
    specs={MODELS[0]:dict(pool=ordinary,x=[vector(r,'rec',hist,th,'E0_OP') for r in ordinary],qx=[vector(q,'rec',observed,ot,'E0_OP') for q in queries],fields=BASE_NAMES,
              policy='UNCHANGED_V4_MIXED_HISTORICAL_FEATURE_KICKOFF_PLUS7D_WITH_SOURCE_COMPLETED_LABELS_AND_OBSERVED_CURRENT_QUERY',family='LEAF'),
           MODELS[1]:dict(pool=seven,x=[p1(r) for r in seven],qx=[p1(q,True) for q in queries],fields=BASE_NAMES+OWN_NAMES+OPP_NAMES,
              policy='ALL_LABEL_FEATURE_QUERY_KICKOFF_PLUS7D_STRICT_RECONSTRUCTION;CONTEXT2025_2026_ONLY',family='POISSON'),
           MODELS[2]:dict(pool=one,x=[timed.features(r)['PROFILE'] for r in one],qx=[timed.features(q,information_cutoff=cutoff)['PROFILE'] for q in queries],fields=BASE_NAMES+OWN_NAMES[:5]+SUPPORT_NAMES+OWN_NAMES[5:],
              policy='ALIGNED_ALL_LABEL_FEATURE_QUERY_KICKOFF_PLUS1D_STRICT_CURRENT_VINTAGE_RECONSTRUCTION_NOT_OBSERVED_PUBLICATION',family='LEAF')}
    for s in specs.values():
        s['x']=np.asarray(s['x'],float);s['qx']=np.asarray(s['qx'],float)
        if s['x'].shape[1]!=len(s['fields']) or s['qx'].shape[1]!=len(s['fields']): raise ValueError('FEATURE_ORDER_LENGTH')
    for name,ph in [(MODELS[0],observed),(MODELS[1],hist),(MODELS[2],timed.hist)]:
        specs[name]['query_history']=[]
        for q in queries:
            rr=ph.before(q['player_id'],cutoff,8)
            specs[name]['query_history'].append(dict(admitted_prior_games=[dict(game_id=r['game_id'],team=r['team'],kickoff=r['kickoff'],available=r['available'],known_receptions=r['values']['rec'] is not None) for r in rr],
                latest_admitted_game=rr[-1]['game_id'] if rr else None,
                latest_game_age_at_feature_cutoff_days=(cutoff-rr[-1]['kickoff'])/86400 if rr else None,
                age_semantics='ACTUAL_FEATURE_CUTOFF_MINUS_GAME_TIME;VECTOR_LAG_AGES_USE_FUTURE_KICKOFF_REST'))
    binding.update(held_ungraded_own_completed_games=held,completed_game_ids=sorted(completed),context_sources={str(p.relative_to(ROOT)):sha(p) for p in [f24,f25,f26]},
                   label_source_vintage='CURRENT_REVISED_HISTORY;NOT_ORIGINAL_AVAILABILITY',counts_before_role_filter=True)
    return specs,binding

def fit_draft(source,draft):
    registration=read(REG);capture=registration['current_capture']
    if not capture.get('execution_authorized') or capture.get('future_fits_max')!=3: raise RuntimeError('CURRENT_THREE_FIT_ROOT_AUTHORIZATION_REQUIRED')
    budget=capture['budget'];bind=committed_bindings()
    if git('status','--porcelain'): raise RuntimeError('COMMIT_POLICY_AND_CODE_BEFORE_CURRENT_DRAFT')
    draft=Path(draft).resolve()
    if draft.is_relative_to(ROOT): raise ValueError('DRAFT_CACHE_MUST_BE_OUTSIDE_REPOSITORY')
    if draft.exists(): raise FileExistsError('IMMUTABLE_DRAFT_ATTEMPT_ALREADY_EXISTS')
    m=validate_inputs(source);cutoff=timestamp(m['actual_input_cutoff_UTC'])
    if 'finality_proof' not in m: raise RuntimeError('RECENT_GAME_FINALITY_PROOF_REQUIRED_BEFORE_FITS')
    games=read(Path(source)/'candidate_schedule.json')['games'];basic,queries=query_universe(read(Path(source)/'roster_current_season.json'),games,m['target_season'])
    draft.mkdir(parents=True);started=now();cpu=time.process_time();wall=time.monotonic()
    ledger=dict(created_UTC=started,state='DRAFT_NOT_ISSUED',attempts=[],completed=[],failures=[],new_fits=0,**bind)
    write(draft/'FIT_LEDGER.json',ledger,exclusive=True)
    def check():
        from context_sources_c01 import guard
        from forward_budget_v4 import tree_bytes
        if guard()+tree_bytes(draft)>2684354560: raise RuntimeError('WHOLE_C_PLUS_EXTERNAL_DRAFT_CAP')
        if time.process_time()-cpu>budget['CPU_seconds'] or time.monotonic()-wall>budget['process_wall_seconds']: raise RuntimeError('CURRENT_CAPTURE_TIME_CAP')
        if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024>budget['RSS_bytes']: raise RuntimeError('CURRENT_CAPTURE_RSS_CAP')
        if sum(p.stat().st_size for p in draft.rglob('*') if p.is_file())>budget['draft_bytes_max']: raise RuntimeError('CURRENT_DRAFT_BYTE_CAP')
    old_handler=signal.getsignal(signal.SIGPROF)
    def timeout(*_): raise RuntimeError('CURRENT_CAPTURE_CPU_CAP')
    signal.signal(signal.SIGPROF,timeout);signal.setitimer(signal.ITIMER_PROF,budget['CPU_seconds'])
    try:
        specs,binding=current_matrices(source,queries,cutoff);check();rows=[];metas=[]
        from laws_v2 import LeafModel
        from safe_models_v4 import export_forest,infer_forest,law_data
        from context_experiment_c01 import pooled_fit,pooled_mu,fingerprint
        from scipy.stats import poisson
        for name in MODELS:
            s=specs[name];y=np.asarray([r['values']['rec'] for r in s['pool']],float);roles=[r['position'] for r in s['pool']]
            if len(y)<60: raise RuntimeError('INSUFFICIENT_QUALIFIED_TRAINING')
            ledger['attempts'].append(dict(model=name,started_UTC=now(),training_rows=len(y),fingerprint=fingerprint(s['x'],y)))
            write(draft/'FIT_LEDGER.json',ledger);check()
            with threadpool_limits(limits=1):
                if s['family']=='LEAF':
                    fitted=LeafModel('count',1).fit(s['x'],y,np.asarray(roles));model=export_forest(fitted)
                    laws=infer_forest(model,s['qx'],[q['position'] for q in queries]);expected=fitted.laws(s['qx'],[q['position'] for q in queries])
                    for a,b in zip(laws,expected):
                        if law_data(a)!=law_data(b): raise ValueError('SAFE_EXPORT_PARITY_FAILED')
                    predictions=[dict(mean=l.mean(),median=l.quantile(.5),p05=l.quantile(.05),p95=l.quantile(.95),law=law_data(l)) for l in laws]
                else:
                    model=pooled_fit(s['x'],y,None,False);mu=pooled_mu(model,s['qx'],None)
                    predictions=[dict(mean=float(v),median=float(poisson.ppf(.5,v)),p05=float(poisson.ppf(.05,v)),p95=float(poisson.ppf(.95,v)),law=dict(kind='POISSON',mu=float(v),assumption='REGISTERED_POISSON_OUTCOME_LAW_CONDITIONAL_ON_APPEARANCE')) for v in mu]
            ledger['new_fits']+=1
            meta=dict(model_id=name,family=s['family'],model=model,feature_order=s['fields'],feature_policy=s['policy'],training_rows=len(y),
                      training_membership=[dict(game_id=r['game_id'],player_id=r['player_id'],kickoff=r['kickoff'],available=r['available']) for r in s['pool']],
                      training_feature_rows=clean(s['x']),training_labels=y.tolist(),training_roles=roles,fingerprint=fingerprint(s['x'],y),
                      latest_training_game_UTC=pd.Timestamp(max(r['kickoff'] for r in s['pool']),unit='s',tz='UTC').isoformat(),
                      fit_information_cutoff_UTC=m['actual_input_cutoff_UTC'],fit_completed_UTC=now(),safe_export_parity_queries=len(queries) if s['family']=='LEAF' else None)
            p=draft/'models'/f'{name}.json.xz';write(p,meta,exclusive=True);modelhash=sha(p)
            metas.append(dict(model_id=name,path='models/'+p.name,SHA256=modelhash,feature_count=len(s['fields']),family=s['family'],feature_policy=s['policy'],training_rows=len(y)))
            history_index=3
            for q,x,pred,history in zip(queries,s['qx'],predictions,s['query_history']):
                rows.append(dict(q,model_id=name,model_SHA256=modelhash,category='rec',**pred,
                    product_type='DISCRETE_OUTCOME_LAW_WITH_MEAN_MEDIAN',point_types=['EXPECTED_MEAN','LOWER_MEDIAN'],**history,
                    features=clean(x),feature_order=s['fields'],feature_policy=s['policy'],history_support=int(x[history_index]),
                    any_imputed=bool(not np.isfinite(x).all()),profile_missing=bool(x[36]) if len(x)>=58 else None,
                    prior_provenance='EARLIER_TRAINING_ONLY_ROLE_GEOMETRIC_05' if s['family']=='LEAF' else 'L2_POOLED_POISSON_WITH_TRAINING_ONLY_IMPUTATION',
                    hard_incumbent_fallback=False,sparse_history=int(x[3])<3,appearance_conditioning='CONDITIONAL_ON_APPEARANCE_NOT_HEALTH_OR_STARTER_PROBABILITY',
                    inference_UTC=now(),information_cutoff_UTC=m['actual_input_cutoff_UTC'],
                    state='DRAFT_NOT_ADMITTED_NOT_ISSUED',line=None,selected_side=None,probability_at_line=None,
                    offer_state='NO_SOURCE_QUALIFIED_CURRENT_OPEN_OFFER',confidence=None,EV=None))
            ledger['completed'].append(name);write(draft/'FIT_LEDGER.json',ledger);check()
        write(draft/'DRAFT_FORECASTS.json.xz',rows,exclusive=True);write(draft/'BASIC_UNIVERSE.json.xz',basic,exclusive=True)
        write(draft/'MODEL_INPUT_MANIFEST.json',m,exclusive=True)
        manifest=dict(schema='C04-CURRENT-DRAFT-v1',created_UTC=now(),draft_started_UTC=started,state='DRAFT_NOT_ISSUED',
                      **bind,input_manifest_SHA256=sha(input_manifest_path(source)),input_source_manifest_path=str(input_manifest_path(source).relative_to(ROOT)),input_cutoff_UTC=m['actual_input_cutoff_UTC'],
                      source_bindings=binding,models=metas,basic_rows=len(basic),query_rows=len(queries),forecast_rows=len(rows),
                      new_fits=ledger['new_fits'],CPU_seconds=time.process_time()-cpu,wall_seconds=time.monotonic()-wall,
                      peak_RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,candidate_games=games,
                      environment=dict(python=platform.python_version(),packages={p:version(p) for p in ['numpy','pandas','scipy','scikit-learn','threadpoolctl']}))
        manifest['files']={p.relative_to(draft).as_posix():dict(SHA256=sha(p),bytes=p.stat().st_size) for p in draft.rglob('*') if p.is_file()}
        write(draft/'DRAFT.json',manifest,exclusive=True);check();return manifest
    except Exception as e:
        ledger['failures'].append(dict(created_UTC=now(),error=repr(e)));write(draft/'FIT_LEDGER.json',ledger);raise
    finally:
        signal.setitimer(signal.ITIMER_PROF,0);signal.signal(signal.SIGPROF,old_handler)

def issue(draft,events_path,output,run_id,proof_path,status_generated_paths=()):
    draft,output=Path(draft),Path(output)
    if output.exists(): raise FileExistsError('IMMUTABLE_RUN_ALREADY_EXISTS')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+',run_id): raise ValueError('INVALID_RUN_ID')
    bind=committed_bindings();proof=read(proof_path);issued=now();at=timestamp(issued)
    if proof.get('git_status')!='' or any(proof.get(k)!=v for k,v in bind.items()) or not 0<=at-timestamp(proof['created_UTC'])<=1800: raise ValueError('CLEAN_START_PROOF_INVALID')
    allowed=set(status_generated_paths)
    for p in allowed:
        if not (p.startswith('sources/profile-closure-next-02/') or p.startswith('reports/profile-closure-next-02/current-source/')) or p.endswith('.py'): raise ValueError('INVALID_STATUS_GENERATED_ALLOWLIST')
    # New status/source receipts are expected only after the whole-tree clean gate.
    dirty=subprocess.check_output(['git','status','--porcelain','--untracked-files=all'],cwd=ROOT,text=True).splitlines()
    if any(line[3:] not in allowed for line in dirty): raise RuntimeError('UNEXPECTED_CHANGE_AFTER_CLEAN_START')
    m=read(draft/'DRAFT.json')
    if any(m[k]!=bind[k] for k in bind): raise ValueError('DRAFT_CODE_OR_POLICY_CHANGED')
    for name,f in m['files'].items():
        if sha(draft/name)!=f['SHA256'] or (draft/name).stat().st_size!=f['bytes']: raise ValueError('DRAFT_BYTES_CHANGED')
    source_manifest=read(draft/'MODEL_INPUT_MANIFEST.json');validate_inputs(SOURCE,at)
    if sha(input_manifest_path(SOURCE))!=m['input_manifest_SHA256']: raise ValueError('FEATURE_SOURCE_CHANGED')
    events,status_verification=validate_status_snapshot(events_path,at,input_manifest_SHA256=m['input_manifest_SHA256'],after=timestamp(proof['created_UTC']))
    accepted,rejected=qualified_events(m['candidate_games'],events,at,after=timestamp(proof['created_UTC']))
    if not accepted: raise ValueError('NO_NATIVE_VERIFIED_FUTURE_EVENTS')
    roster_source=next(s for s in source_manifest['sources'] if s['id']=='CURRENT_SEASON_ROSTER')
    roster_expiry=parsedate_to_datetime(roster_source['HTTP_Last_Modified']).timestamp()+36*3600
    rows=[]
    for r in read(draft/'DRAFT_FORECASTS.json.xz'):
        if r['game_id'] not in accepted: continue
        e=accepted[r['game_id']];r=dict(r);r.update(run_id=run_id,state='ISSUED_SHADOW_FORECAST_ONLY_AWAITING_GITHUB_PERSISTENCE',
            issued_UTC=issued,generated_UTC=issued,native_status_observed_UTC=e['observed_UTC'],event_version=e.get('event_version'),
            event_state=e['state'],native_event_source=e['source_id'],lead_seconds_at_issuance=r['kickoff']-at,
            expires_UTC=pd.Timestamp(min(roster_expiry,r['kickoff']-300),unit='s',tz='UTC').isoformat(),
            expiry_action='NO_LONGER_FRESH_FOR_CURRENT_DISPLAY;RETAIN_ORIGINAL_SNAPSHOT_FOR_SUBSEQUENT_GRADING',
            forecast_id=hashlib.sha256((run_id+'|'+r['model_id']+'|'+r['game_id']+'|'+r['player_id']+'|rec').encode()).hexdigest()[:24])
        rows.append(r)
    if not rows: raise ValueError('NO_ELIGIBLE_ISSUABLE_FORECASTS')
    output.mkdir(parents=True);write(output/'FORECASTS.json.xz',rows,exclusive=True)
    basic=read(draft/'BASIC_UNIVERSE.json.xz')
    for b in basic:
        b['native_verified_candidate_games']=[g for g in b['candidate_game_ids'] if g in accepted]
        if b['state']=='DRAFT_CANDIDATE_PENDING_NATIVE_EVENT': b['state']='ISSUED_CONDITIONAL_FORECAST_CANDIDATE' if b['native_verified_candidate_games'] else 'NATIVE_EVENT_NOT_ADMITTED'
    write(output/'BASIC_UNIVERSE.json.xz',basic,exclusive=True);write(output/'EVENT_ADMISSION.json',dict(issued_UTC=issued,accepted=accepted,rejected=rejected),exclusive=True)
    write(output/'CLEAN_START_PROOF.json',proof,exclusive=True)
    write(output/'INDEPENDENT_STATUS_VERIFICATION.json',status_verification,exclusive=True)
    # Keep exact recoverable primitive models/training evidence and original draft clocks.
    for p in draft.rglob('*'):
        if p.is_file() and p.name not in ['DRAFT_FORECASTS.json.xz','BASIC_UNIVERSE.json.xz']:
            target=output/'draft'/p.relative_to(draft);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(p.read_bytes())
    status=Path(events_path);write(output/'NATIVE_STATUS.json',events,exclusive=True)
    if (status.parent/'SOURCE_MANIFEST.json').exists(): write(output/'STATUS_SOURCE_MANIFEST.json',read(status.parent/'SOURCE_MANIFEST.json'),exclusive=True)
    manifest=dict(schema='C04-CURRENT-FORECAST-ONLY-RUN-v1',run_id=run_id,created_UTC=issued,issued_UTC=issued,**bind,
        information_cutoff_UTC=m['input_cutoff_UTC'],draft_created_UTC=m['created_UTC'],source_input_manifest_SHA256=m['input_manifest_SHA256'],
        roster_contract=ROSTER_CONTRACT,roster_week=None,individual_transaction_effective_UTC=None,
        basic_rows=len(basic),forecast_rows=len(rows),unique_players=len({r['player_id'] for r in rows}),games=sorted(accepted),models=m['models'],
        first_kickoff_UTC=min(r['kickoff_UTC'] for r in rows),real_offers=0,real_selections=0,new_fits=m['new_fits'],
        primary_replacement=False,predictive_improvement_demonstrated=False,original_website_incumbent=False,
        primary_scoring_snapshot='FIRST_VALID_MANUAL_BATCH_PER_MODEL;NO_FAVORABLE_REFRESH_SELECTION',
        publication_state='AWAITING_GITHUB_SERVER_PROOF',consumer_state='NOT_YET_VERIFIED',
        limitations=['CURRENT_KNOWN_SEASON_ROSTER_NOT_FUTURE_GAMEDAY_MEMBERSHIP','CONDITIONAL_ON_APPEARANCE',
                     'FOOTBALL_SOURCE18_55_CUTOFF_DISTINCT_FROM_LATER_NATIVE_ELIGIBILITY_CLOCK',
                     'CURRENT_PROCEDURE_COMPARISON_NOT_CAUSAL_TIMING_ISOLATION','NO_AUTHENTICATED_CURRENT_PROP_OFFERS',
                     'POISSON_AND_LEAF_LAWS_ARE_MODEL_ASSUMPTIONS_NOT_VALIDATED_CONFIDENCE'])
    manifest['files']={p.relative_to(output).as_posix():dict(SHA256=sha(p),bytes=p.stat().st_size) for p in output.rglob('*') if p.is_file()}
    if sum(f['bytes'] for f in manifest['files'].values())>read(REG)['current_capture']['budget']['new_public_bytes_max']: raise RuntimeError('PUBLIC_RUN_BYTE_CAP_NO_PUBLICATION')
    write(output/'RUN.json',manifest,exclusive=True);return manifest

if __name__=='__main__':
    p=argparse.ArgumentParser();s=p.add_subparsers(dest='command',required=True)
    a=s.add_parser('prepare');a.add_argument('--source',type=Path,default=SOURCE);a.add_argument('--output',type=Path)
    a=s.add_parser('fit-draft');a.add_argument('--source',type=Path,default=SOURCE);a.add_argument('--draft',type=Path,required=True)
    a=s.add_parser('clean-start');a.add_argument('--output',type=Path,required=True)
    a=s.add_parser('issue');a.add_argument('--draft',type=Path,required=True);a.add_argument('--events',type=Path,required=True);a.add_argument('--output',type=Path,required=True);a.add_argument('--run-id',required=True);a.add_argument('--proof',type=Path,required=True);a.add_argument('--status-generated-path',action='append',default=[])
    a=p.parse_args()
    if a.command=='prepare': result=prepare(a.source,a.output)
    elif a.command=='fit-draft': result=fit_draft(a.source,a.draft)
    elif a.command=='clean-start': result=record_clean_start(a.output)
    else: result=issue(a.draft,a.events,a.output,a.run_id,a.proof,a.status_generated_path)
    print(json.dumps({k:v for k,v in result.items() if k not in ['files','source_bindings','candidate_games','code_SHA256','models']},indent=2))
