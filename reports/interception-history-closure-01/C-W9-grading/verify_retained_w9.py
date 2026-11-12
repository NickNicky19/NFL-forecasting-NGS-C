"""Read-only verification/aggregation of existing W9 grades; never calls grader.

This adds a coverage-admission receipt, not a new NFL test or another evaluator.
Original law/prediction/source/grade files are read without unsafe model loading.
"""
from __future__ import annotations
import collections,csv,gzip,hashlib,io,json,math,resource,re,sys,time
from datetime import datetime,timezone
from decimal import Decimal,InvalidOperation
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'src'))
from prospective_v4 import validate_run,validate_receipt
OUT=Path(__file__).resolve().parent
PREFIXES=('C-FWD-v4-20261105-W09-JAXBAL-','C-FWD-v4-20261107-W09-CINATL-')
CATS=['pass_yd','pass_td','pass_cmp','pass_att','pass_int','rush_yd','rush_att','rec','rec_yd','rush_rec_yd','anytime_td','fpts']

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_bytes())
def stamp():return datetime.now(timezone.utc).isoformat()
def dump(p,obj):
 with Path(p).open('x') as f:json.dump(obj,f,indent=2,allow_nan=False);f.write('\n')
def integer(v):
 if v in [None,'']:return None
 try:
  x=Decimal(str(v))
  return int(x) if x.is_finite() and x==x.to_integral_value() else None
 except (ValueError,InvalidOperation):return None
def close(a,b):return math.isclose(a,b,rel_tol=1e-12,abs_tol=1e-10)

def run():
 started=stamp();cpu=time.process_time();wall=time.monotonic()
 reg=read(OUT/'REGISTRATION.json');runs=sorted(p for p in (ROOT/'prospective/runs').iterdir() if p.name.startswith(PREFIXES))
 assert len(runs)==4,'EXACT_FOUR_RETAINED_RUNS_REQUIRED'
 bindings=[];run_tables=[];category=collections.defaultdict(list);int_trace=[];allids=set();events=set()
 for folder in runs:
  m,rows=validate_run(folder);receipt_path=ROOT/'prospective/receipts'/(folder.name+'-server.json');receipt=read(receipt_path);validate_receipt(folder,receipt,m,rows)
  assert m['real_offers']==0 and m['real_selections']==0
  grades=sorted((ROOT/'prospective/grades').glob('*-'+folder.name+'.json'));assert len(grades)==1,'DO_NOT_CHOOSE_FAVORABLE_OR_DUPLICATE_GRADE_VERSION'
  gp=grades[0];g=read(gp);assert g['forecast_SHA256']==sha(folder/'forecasts.json.gz')
  outcome_path=ROOT/'prospective/outcomes'/g['outcome_version']/'OUTCOMES.json';packet=read(outcome_path)
  assert sha(outcome_path)==g['outcome_packet_SHA256'];assert packet['source_qualification']=='OFFICIAL_NUMERICAL_FACTS_VERIFIED'
  source_bindings=[]
  for evidence in packet['source_evidence']:
   p=(outcome_path.parent/evidence['path']).resolve();assert p.is_relative_to(outcome_path.parent.resolve()) and sha(p)==evidence['SHA256']
   source_bindings.append(dict(path=str(p.relative_to(ROOT)),SHA256=sha(p),source=evidence['source']))
  native=read(outcome_path.parent/'evidence/native_status.json');event=native['event'];source=native['source']
  assert event['state']=='post' and event['status_name']=='STATUS_FINAL' and event['completed'] is True
  assert event['espn_event_id']==event['competition_id'] and event['source_id']==source['id'] and event['observed_UTC']==source['observed_UTC']
  raw=gzip.decompress((outcome_path.parent/'evidence/player_facts.csv.gz').read_bytes()).decode()
  reader=csv.DictReader(io.StringIO(raw));assert 'passing_interceptions' in reader.fieldnames
  facts={};unjoined=[]
  for r in reader:
   if not re.fullmatch(r'00-\d{7}',r['player_id']):
    fields=[v for k,v in r.items() if k not in ['player_id','game_id','team','opponent_team','position','season','week','season_type']]
    assert all(integer(v)==0 for v in fields),'UNKNOWN_OR_NONZERO_UNIDENTIFIED_SOURCE_ROW'
    unjoined.append(dict(game_id=r['game_id'],team=r['team'],reason='NO_NATIVE_ID_EXPLICIT_ALL_ZERO_SOURCE_AGGREGATE_NOT_JOINED_TO_FORECAST'));continue
   k=(r['game_id'],r['player_id']);assert k not in facts;facts[k]=r
  lookup={(r['game_id'],r['player_id'],r['category']):r for r in packet['outcomes']};pred={r['forecast_id']:r for r in rows}
  assert set(pred)=={r['forecast_id'] for r in g['grades']};assert len(g['grades'])==len(rows)
  perrun=collections.defaultdict(list)
  for z in g['grades']:
   r=pred[z['forecast_id']];fid=r['forecast_id'];assert fid not in allids;allids.add(fid)
   a=lookup[(r['game_id'],r['player_id'],r['category'])]
   assert a['espn_event_id']==r['espn_event_id']==event['espn_event_id'] and a['event_status']=='FINAL'
   assert a['kickoff_UTC']==r['kickoff_UTC'] and event['kickoff_UTC']==r['kickoff_UTC']
   assert r['team'] in [event['home_team'],event['away_team']] and r['opponent_team'] in [event['home_team'],event['away_team']] and r['team']!=r['opponent_team']
   assert z['state'] in ['GRADED_PLAYED','UNKNOWN'],'NO_UNGRADED_CELLS_IN_RETAINED_SCOPE'
   if z['state']=='GRADED_PLAYED':
    assert a['appearance']=='PLAYED' and a['actual']==z['actual'] and math.isfinite(z['actual'])
    f=facts[(r['game_id'],r['player_id'])];assert f['team']==r['team'] and f['opponent_team']==r['opponent_team']
    assert a['participation_proof_fields'],'PARTICIPATION_REQUIRED_INDEPENDENT_OF_STAT_ZERO'
    if r['mean'] is not None:
     assert close(r['median']-z['actual'],z['median_error']) and close(abs(r['median']-z['actual']),z['absolute_error'])
     assert close((r['mean']-z['actual'])**2,z['mean_squared_error'])
    if r['category']=='rush_rec_yd':
     rush,rec=integer(f['rushing_yards']),integer(f['receiving_yards']);assert rush is not None and rec is not None and rush+rec==z['actual']
    if r['category']=='anytime_td':
     rush,rec=integer(f['rushing_tds']),integer(f['receiving_tds']);assert rush is not None and rec is not None and int(rush+rec>0)==z['actual']
   else:assert a['appearance']=='UNKNOWN' and a['actual'] is None and z['actual'] is None
   if r['category']=='pass_int':
    f=facts.get((r['game_id'],r['player_id']));raw_int=f.get('passing_interceptions') if f else None
    actual=integer(raw_int)
    if z['state']=='GRADED_PLAYED':assert actual is not None and actual>=0 and actual==z['actual']
    else:assert not f or a['unavailable_reasons'],'MISSING_ROW_IS_NOT_ZERO'
    int_trace.append(dict(run_id=folder.name,game_id=r['game_id'],player_id=r['player_id'],name=r['name'],
       state=z['state'],actual=z['actual'],raw_stat_row_present=f is not None,passing_interceptions_raw=raw_int,
       explicit_reported_zero=raw_int not in [None,''] and actual==0,participation_proof_fields=a['participation_proof_fields'],
       unavailable_reasons=a['unavailable_reasons'],forecast_id=fid,forecast_mean=r['mean'],forecast_median=r['median'],
       source_player_facts_SHA256=sha(outcome_path.parent/'evidence/player_facts.csv.gz')))
   category[r['category']].append((r,z));perrun[r['category']].append((r,z));events.add(r['game_id'])
  bindings.append(dict(run_id=folder.name,run_manifest=dict(path=str((folder/'RUN.json').relative_to(ROOT)),SHA256=sha(folder/'RUN.json')),
      forecasts=dict(path=str((folder/'forecasts.json.gz').relative_to(ROOT)),SHA256=sha(folder/'forecasts.json.gz')),
      server_receipt=dict(path=str(receipt_path.relative_to(ROOT)),SHA256=sha(receipt_path),persistence_UTC=receipt['server_check_completed_UTC'],capture_commit=receipt['capture_commit']),
      grade=dict(path=str(gp.relative_to(ROOT)),SHA256=sha(gp),created_UTC=g['created_UTC']),
      outcomes=dict(path=str(outcome_path.relative_to(ROOT)),SHA256=sha(outcome_path),version=packet['version']),source_evidence=source_bindings,
      source_native_status_observed_UTC=event['observed_UTC'],unjoined_source_rows=unjoined,method_identity=read(folder/'model_manifest.json')))
  for cat,rr in perrun.items():run_tables.append(summarize(cat,rr,folder.name))
 result=[summarize(cat,category[cat],'ALL_FOUR_RETAINED_RUNS') for cat in CATS]
 assert sum(r['eligible_forecasts'] for r in result)==382 and sum(r['graded_played'] for r in result)==226 and sum(r['unknown'] for r in result)==156
 cpu=time.process_time()-cpu;rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
 assert cpu<=reg['budget']['CPU_seconds_max'] and rss<=reg['budget']['RSS_bytes_max']
 receipt=dict(id=reg['id'],started_UTC=started,completed_UTC=stamp(),status='REUSED_EXISTING_QUALIFIED_GRADES_NO_NEW_TEST',
   verified_HEAD=reg['base_commit'],executing_verifier_SHA256=sha(Path(__file__)),original_grader_SHA256=sha(ROOT/'src/prospective_v4.py'),
   new_source_reads=0,new_fits=0,new_inference=0,new_grade_calls=0,new_NFL_games=0,new_actual_offer_weeks=0,
   newly_admitted_existing_scope=dict(season=2026,week=9,games=sorted(events),forecast_rows=382,graded_played=226,unknown=156,pending=0),
   evidence_tier='ORIGINAL_GITHUB_PERSISTED_PREGAME_FORECAST_ONLY;NO_QUALIFIED_ACTUAL_OFFERS',
   actual_offer_O_U_combined='N/A_NO_FROZEN_ACTUAL_LINES',venue_settlement='UNVERIFIED_NOT_BETTING_RETURNS',
   interceptions=dict(eligible=12,graded=4,explicit_reported_zero=sum(r['explicit_reported_zero'] for r in int_trace),unknown=8,
     unknown_to_zero_changes=0,scope='C_NATIVE_W9_ONLY;NO_CLAIM_ABOUT_ORIGINAL_WEBSITE46'),
   CPU_seconds=cpu,wall_seconds=time.monotonic()-wall,peak_RSS_bytes=rss,bindings=bindings)
 dump(OUT/'REUSE_RECEIPT.json',receipt);dump(OUT/'CATEGORY_NUMERICAL.json',dict(rows=result,exact_run_rows=run_tables));dump(OUT/'PASS_INT_SOURCE_TRACE.json',int_trace)
 print(json.dumps({k:v for k,v in receipt.items() if k not in ['bindings']},indent=2));return result

def summarize(cat,rr,run):
 kk=[(p,g) for p,g in rr if g['state']=='GRADED_PLAYED'];numeric=[(p,g) for p,g in kk if p['mean'] is not None]
 out=dict(run_id=run,category='nick-chart-ppr-v1' if cat=='fpts' else cat,eligible_forecasts=len(rr),graded_played=len(kk),unknown=sum(g['state']=='UNKNOWN' for _,g in rr),
   observed_zero=sum(g['actual']==0 for _,g in kk),pending=0,actual_scored_weeks=sorted({(p['season'],p['week']) for p,_ in kk}),
   games=len({p['game_id'] for p,_ in kk}),player_games=len({(p['game_id'],p['player_id']) for p,_ in kk}),
   actual_offer_over=None,actual_offer_under=None,actual_offer_combined=None,actual_offer_reason='NO_QUALIFIED_RETAINED_LINE',
   fallback_outputs=sum(p.get('model_fallback',False) for p,_ in rr),method_family='C-FORWARD-P2-v4/retained_Leaf32_8_30_seed1701',
   exact_method_ids=sorted({p['model_id'] for p,_ in rr}),numerical_point_output='EXPECTED_MEAN_AND_LOWER_MEDIAN' if numeric else 'TYPED_EVENT_PROBABILITY_ONLY',
   scoring_contracts=sorted({p['scoring_contract_id'] for p,_ in rr}),role_scope=sorted({p['position'] for p,_ in rr}),
   median_MAE=sum(g['absolute_error'] for _,g in numeric)/len(numeric) if numeric else None,
   mean_MAE=sum(abs(p['mean']-g['actual']) for p,g in numeric)/len(numeric) if numeric else None,
   mean_MSE=sum(g['mean_squared_error'] for _,g in numeric)/len(numeric) if numeric else None,
   mean_bias=sum(p['mean']-g['actual'] for p,g in numeric)/len(numeric) if numeric else None,
   mean_CRPS=sum(g['CRPS'] for _,g in kk)/len(kk) if kk else None)
 if cat=='anytime_td' and kk:out['binary_Brier']=sum((p['event_probability']-g['actual'])**2 for p,g in kk)/len(kk)
 return out

if __name__=='__main__':run()
