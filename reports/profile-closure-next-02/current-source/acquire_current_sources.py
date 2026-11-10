"""Bounded manual C04 factual-source qualification, with recoverable projections.

No full raw payload, target-game outcomes, sportsbook feed or collector is saved.
"""
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
import argparse,json,hashlib,datetime,gzip,io,re,lzma,csv,sys,zipfile,math
from email.utils import parsedate_to_datetime
import pandas as pd
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'src'))
from forward_sources_v4 import team,records,kickoff_frame,native,scoreboard_projection,quarantine_stat_orphans
from context_sources_c01 import COLS,guard
REPORT=ROOT/'reports/profile-closure-next-02/current-source';OUT=ROOT/'sources/profile-closure-next-02'
LIMIT=8;TOTAL=33554432;PER=12582912

def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def sha(b):return hashlib.sha256(b).hexdigest()
def write(p,d):p.write_text(json.dumps(d,indent=2,allow_nan=False)+'\n')
def get(key,url):
 ledger_path=REPORT/'REQUESTS.json';ledger=json.loads(ledger_path.read_text()) if ledger_path.exists() else []
 assert len(ledger)<scope_limit(),'CURRENT_SOURCE_REQUEST_CAP'
 assert not any(r['id']==key and r.get('status')==200 for r in ledger),'COMPLETED_SOURCE_FETCH_FROZEN'
 remaining=TOTAL-sum(x.get('bytes',0) for x in ledger);read_bound=min(PER,remaining);assert read_bound>0,'CURRENT_SOURCE_TOTAL_RESPONSE_CAP'
 r=dict(id=key,url=url,started_UTC=now(),state='ATTEMPTING',maximum_body_bytes_this_request=read_bound);ledger.append(r);write(ledger_path,ledger)
 try:
  with urlopen(Request(url,headers={'User-Agent':'Session-C-manual-C04-source-qualification','Cache-Control':'no-cache','Accept-Encoding':'identity'}),timeout=45) as response:
   body=response.read(read_bound);headers={k.lower():v for k,v in response.headers.items()}
   r.update(status=response.status,bytes=len(body),SHA256=sha(body),observed_UTC=now(),HTTP_Date=headers.get('date'),HTTP_Age=headers.get('age'),HTTP_Last_Modified=headers.get('last-modified'),ETag=headers.get('etag'),state='RECEIVED')
  write(ledger_path,ledger);assert len(body)<read_bound,'CURRENT_SOURCE_AT_READ_BOUND_OR_TRUNCATED';assert sum(x.get('bytes',0) for x in ledger)<=TOTAL,'CURRENT_SOURCE_TOTAL_RESPONSE_CAP'
  return body,r
 except Exception as e:
  r.update(state='FAILED',error=type(e).__name__+':'+str(e),observed_UTC=now(),HTTP_error_status=getattr(e,'code',None),error_body_bytes='NOT_READ');write(ledger_path,ledger);raise

def strip_html(body):
 s=body.decode(errors='replace');s=re.sub(r'<script\b.*?</script>|<style\b.*?</style>',' ',s,flags=re.I|re.S);s=re.sub(r'<[^>]+>',' ',s);return re.sub(r'\s+',' ',s)

def roster():
 assert not (REPORT/'ROSTER_QUALIFICATION.json').exists(),'COMPLETED_ROSTER_QUALIFICATION_FROZEN'
 b,doc=get('CURRENT_ROSTER_DEFINITION','https://nflreadr.nflverse.com/reference/load_rosters.html');s=strip_html(b)
 snippets=[]
 for word in ['current','roster','week','status','season','nflverse','daily']:
  for m in list(re.finditer(re.escape(word),s,re.I))[:5]:snippets.append(s[max(0,m.start()-90):m.start()+360])
 write(REPORT/'CURRENT_ROSTER_DOCUMENTATION.json',dict(source=doc,excerpts=snippets,notes='Definition documentation is not observation of future event participation. Existing data-schedule documentation retained separately states roster daily7AMUTC.'))
 b,source=get('CURRENT_SEASON_ROSTER','https://github.com/nflverse/nflverse-data/releases/download/rosters/roster_2026.csv')
 frame=pd.read_csv(io.BytesIO(b),low_memory=False);columns=frame.columns.tolist()
 needed=['season','team','position','gsis_id','full_name','status'];missing=[c for c in needed if c not in frame]
 if missing:
  write(REPORT/'ROSTER_QUALIFICATION.json',dict(status='SOURCE_BLOCKED',source=source,columns=columns,missing=missing,reason='Required current-roster identity/status fields absent; no guesses or week fabrication.'));return
 frame=frame[frame.season==2026].copy();frame['team']=frame.team.map(team);used=frame[frame.position.isin(['QB','RB','WR','TE'])][needed].copy()
 metadata={'source_contract':'NFLVERSE_SEASON_ROSTER_SNAPSHOT_CURRENT_VINTAGE','source_observed_UTC':source['observed_UTC'],'provider_last_modified_UTC':source['HTTP_Last_Modified'],'original_effective_datetime':'NOT_IN_SOURCE_ROWS;current snapshot meaning assessed separately','week':None,'original_source_has_week':'week' in columns}
 if 'week' in frame:metadata['source_week_values']=sorted(frame.week.dropna().unique().tolist())
 # No gameday healthy/starter inference, and nonACT records remain basic coverage.
 outrows=records(used);(OUT/'roster_current_season.json').write_text(json.dumps(outrows,separators=(',',':'))+'\n')
 counts=used.groupby(['position','status'],dropna=False).size().to_dict();by_status={str(k):int(v) for k,v in counts.items()}
 duplicate=used.gsis_id.notna() & used.duplicated(['gsis_id'],keep=False)
 disposition=dict(id='C04-CURRENT-SEASON-ROSTER-QUALIFICATION-v1',source=source,documentation=doc,metadata=metadata,columns=columns,rows=len(used),all_roles_basic_counts=by_status,duplicate_native_rows=int(duplicate.sum()),duplicate_native_examples=records(used[duplicate][needed].head(12)),status='AWAITING_SEMANTIC_REVIEW',reason='Season/current roster has no declared event-week; never relabel asWeek10. Retain actual source clocks; parent reviews current roster snapshot semantics before forecast admission.',rights='ExistingqualifiedNFLverseordinary factualrosterprojection/CCBY4; noFTN/NGS/odds/privatefields',projection=dict(path=str((OUT/'roster_current_season.json').relative_to(ROOT)),bytes=(OUT/'roster_current_season.json').stat().st_size,SHA256=sha((OUT/'roster_current_season.json').read_bytes())),not_claimed=['Expectedstarter','Confirmedfutureparticipation','Healthy','Authenticatedhistoricalavailability'])
 write(REPORT/'ROSTER_QUALIFICATION.json',disposition);guard();print(json.dumps({k:disposition[k] for k in ['rows','duplicate_native_rows','status']},separators=(',',':')))

# The original failed roster/range builds above are preserved as gzip members.
# New stages below recover retained inputs before any dependent network step.
def scope_limit():
 finality=REPORT.parent/'CURRENT_FINALITY_AMENDMENT.json'
 if finality.exists():
  x=json.loads(finality.read_text());assert x['attempts_already_consumed']==8 and x['total_attempts_max']==11 and x['total_bytes_max_unchanged']==TOTAL
  return 11
 amendment=REPORT.parent/'CURRENT_SOURCE_SCOPE_AMENDMENT.json'
 if amendment.exists():
  x=json.loads(amendment.read_text());assert x['original_GET_cap']==8 and x['new_total_GET_cap']==10 and x['response_byte_cap_unchanged']==TOTAL
  return 10
 return 8

def source_rows():return json.loads((REPORT/'REQUESTS.json').read_text())

def status_http_clock(meta):
 """Receipt time alone does not establish current native status freshness."""
 observed=datetime.datetime.fromisoformat(meta['observed_UTC'])
 assert observed.tzinfo is not None,'STATUS_OBSERVATION_TIMEZONE_UNKNOWN'
 age_raw=meta.get('HTTP_Age');date_raw=meta.get('HTTP_Date');age=None;date=None;date_age=None
 if age_raw not in (None,''):
  try:age=float(age_raw)
  except (TypeError,ValueError):raise AssertionError('STATUS_HTTP_AGE_INVALID')
  assert math.isfinite(age) and 0<=age<=1800,'STATUS_HTTP_AGE_INVALID_OR_STALE'
 if date_raw not in (None,''):
  try:date=parsedate_to_datetime(date_raw)
  except (TypeError,ValueError,OverflowError):raise AssertionError('STATUS_HTTP_DATE_INVALID')
  assert date.tzinfo is not None,'STATUS_HTTP_DATE_TIMEZONE_UNKNOWN'
  date_age=(observed-date).total_seconds()
  assert -5<=date_age<=1800,'STATUS_HTTP_DATE_STALE_OR_FUTURE'
 assert age is not None or date is not None,'STATUS_HTTP_RESPONSE_AGE_UNKNOWN'
 return {'state':'HTTP_RESPONSE_CLOCK_QUALIFIED','max_age_seconds':1800,'future_Date_clock_skew_tolerance_seconds':5,'HTTP_Age_seconds':age,'HTTP_Date_UTC':date.astimezone(datetime.timezone.utc).isoformat() if date else None,'HTTP_Date_age_seconds_at_observation':date_age,'observed_UTC':meta['observed_UTC'],'source_id':meta['id'],'response_raw_SHA256':meta['SHA256'],'HTTP_Age_raw':age_raw,'HTTP_Date_raw':date_raw,'original_event_publication_clock':'NOT_AUTHENTICATED_BY_HTTP_RESPONSE_CLOCK'}

def candidate_schedule():
 g=kickoff_frame(pd.read_csv(OUT/'schedule.csv',low_memory=False));cut=pd.Timestamp.now(tz='UTC').timestamp()
 future=g[(g.season==2026)&(g.game_type=='REG')&(g.week==10)&(g.kickoff>cut+300)].sort_values(['kickoff','game_id'])
 return g,future

def prepare_inputs():
 assert (REPORT/'ROSTER_QUALIFICATION.json').exists(),'ROSTER_QUALIFICATION_FIRST'
 assert not (OUT/'MODEL_INPUT_MANIFEST.json').exists(),'COMPLETED_CURRENT_INPUTS_FROZEN'
 b,sm=get('SCHEDULE_RECOVERY_CURRENT','https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv')
 g=kickoff_frame(pd.read_csv(io.BytesIO(b),low_memory=False));g=g[(g.season==2026)&(g.game_type=='REG')].copy()
 for key in ['home_team','away_team']:g[key]=g[key].map(team)
 cols=['game_id','season','week','game_type','gameday','gametime','home_team','away_team','home_score','away_score','espn']
 # Persist immediately, before status/stats/PBP can fail. Include native event IDs.
 g[cols].to_csv(OUT/'schedule.csv',index=False)
 future=g[(g.week==10)&(g.kickoff>pd.Timestamp.now(tz='UTC').timestamp()+300)].sort_values(['kickoff','game_id']);assert len(future),'NO_UPCOMING_WEEK10_SCHEDULE'
 proposal=records(future[['game_id','season','week','gameday','gametime','home_team','away_team','espn','kickoff']])
 write(OUT/'candidate_schedule.json',{'status':'SCHEDULE_CANDIDATES_ONLY_NATIVE_STATUS_NOT_YET_VERIFIED','created_UTC':now(),'games':proposal})
 b,tm=get('CURRENT_PLAYER_STATS','https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_2026.csv.gz')
 df=pd.read_csv(io.BytesIO(b),compression='gzip',low_memory=False);df=df[(df.season==2026)&(df.season_type=='REG')].copy();df,orphans=quarantine_stat_orphans(df)
 for name in ['team','opponent_team']:df[name]=df[name].map(team)
 with zipfile.ZipFile(ROOT/'artifacts/basic-football-facts-v2.1.zip') as z:cols=pd.read_csv(io.BytesIO(z.read('facts.csv.gz')),compression='gzip',nrows=0).columns.tolist()
 assert set(cols)<=set(df),'MISSING_FACT_SCHEMA';assert not df.duplicated(['game_id','player_id']).any(),'DUPLICATE_NATIVE_PLAYER_EVENT';assert not df.game_id.isin(future.game_id).any(),'FUTURE_TARGET_STATS_NOT_EXPECTED'
 df[cols].to_csv(OUT/'current_facts_2026.csv.gz',index=False,compression={'method':'gzip','mtime':0})
 write(REPORT/'CURRENT_FACT_PROJECTION.json',{'source':tm,'rows':len(df),'used_columns':cols,'quarantined_stat_orphans':orphans,'unknown_fields_not_zero_filled':True})
 b,pm=get('CURRENT_PBP','https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_2026.csv.gz')
 buf=io.StringIO();writer=csv.DictWriter(buf,fieldnames=COLS,lineterminator='\n');writer.writeheader();seen=set();count=0;games=set();missing={k:0 for k in COLS}
 with gzip.open(io.BytesIO(b),'rt') as f:
  rows=csv.DictReader(f);assert set(COLS)<=set(rows.fieldnames),'PBP_43_FIELD_SCHEMA_MISSING'
  for row in rows:
   if row['season_type']!='REG' or not any(row[c]=='1' for c in ['pass_attempt','rush_attempt','qb_dropback']):continue
   assert row['season']=='2026';key=(row['game_id'],row['play_id']);assert key not in seen,'DUPLICATE_PBP_PLAY';seen.add(key)
   used={k:row[k] for k in COLS};used['posteam']=team(used['posteam']) if used['posteam'] else '';used['defteam']=team(used['defteam']) if used['defteam'] else '';writer.writerow(used);count+=1;games.add(row['game_id'])
   for k,v in used.items():missing[k]+=v==''
 p=OUT/'pbp_facts_2026.csv.xz';p.write_bytes(lzma.compress(buf.getvalue().encode(),preset=6));assert not games.intersection(set(future.game_id)),'FUTURE_TARGET_PLAY_NOT_EXPECTED'
 write(REPORT/'CURRENT_PBP_PROJECTION.json',{'source':pm,'rows':count,'games':len(games),'used_columns':COLS,'missing':missing,'role':'Ordinary factualcontextprojection, notNGS/charting/alignment/routes','unknown_fields_not_zero_filled':True})
 files=[]
 for name in ['roster_current_season.json','schedule.csv','candidate_schedule.json','current_facts_2026.csv.gz','pbp_facts_2026.csv.xz']:
  p=OUT/name;files.append(dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,SHA256=sha(p.read_bytes())))
 snapshot={'id':'C04-CURRENT-MODEL-INPUTS-v1','actual_input_cutoff_UTC':now(),'roster_contract':'NFLVERSE_CURRENT_KNOWN_SEASON_ROSTER_SNAPSHOT-v1','roster_week':None,'roster_definition_note':'Projectiondoesnotuseafuturegameweek;originalfullheaderpresenceunrecordedafterpreserveddiagnosticfailure','source_observed':{r['id']:r.get('observed_UTC') for r in source_rows() if r.get('status')==200},'sources':source_rows(),'files':files,'target_season':2026,'target_week':10,'tentative_future_games':len(future),'native_event_admission':'PENDING_RESERVED_FINAL_STATUS_GET_AT_ISSUANCE','future_target_outcomes_absent':True,'source_history_vintage':'Currentrevisedhistoricalfacts,notauthenticatedoriginalavailability','roster_qualification':'reports/profile-closure-next-02/current-source/ROSTER_QUALIFICATION.json','fits_or_forecasts_issued':0,'rights':'Existingapprovedordinarynflverse factualprojectionandminimalnativeeventfacts;noodds/privateNGS/FTN/descriptions','failed_schedule_attempt_preserved':'reports/profile-closure-next-02/current-source/FOOTBALL_STAGE_FAILURE.json'}
 write(OUT/'MODEL_INPUT_MANIFEST.json',snapshot)
 (OUT/'ATTRIBUTION.md').write_text('Ordinary roster/player/play facts: nflverse/nflverse-data, CC BY 4.0, https://creativecommons.org/licenses/by/4.0/; schedule: nflverse/nfldata. C projects only needed ordinary factual fields, canonicalizes existing team aliases, and derives profiles/timing sensitivity. Native event status is from the public ESPN scoreboard. Current source observations are recorded; historical versions/individual roster transaction clocks are not backdated. No FTN/NGS tracking, sportsbook data, descriptions or provider presentation is retained.\n')
 guard();print('CURRENT_MODEL_INPUTS_READY',len(future),len(df),count,snapshot['actual_input_cutoff_UTC'])

def completion_proof():
 assert (OUT/'MODEL_INPUT_MANIFEST.json').exists(),'MODEL_INPUTS_REQUIRED'
 assert not (OUT/'MODEL_INPUT_MANIFEST_V2.json').exists(),'COMPLETION_INPUT_V2_ALREADY_FROZEN'
 with zipfile.ZipFile(ROOT/'artifacts/basic-football-facts-v2.1.zip') as z:old=pd.read_csv(io.BytesIO(z.read('schedule.csv')),low_memory=False)
 current=pd.read_csv(OUT/'schedule.csv',low_memory=False);g=pd.concat([old[old.season!=2026],current],ignore_index=True);g=kickoff_frame(g[(g.game_type=='REG')&g.season.between(2022,2026)])
 for key in ['home_team','away_team']:g[key]=g[key].map(team)
 assert not g.game_id.duplicated().any(),'DUPLICATE_FINALITY_SCHEDULE_ID'
 events=[];source=None;clock=None;failure=None
 try:
  b,source=get('CURRENT_NATIVE_WEEK9_FINALITY','https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates=20261105-20261111&seasontype=2&week=9&year=2026&limit=100')
  clock=status_http_clock(source);events=scoreboard_projection(json.loads(b),source['id'],source['observed_UTC'])
  assert len(events)==len({e['espn_event_id'] for e in events}),'DUPLICATE_NATIVE_FINALITY_EVENT'
 except Exception as error:failure=type(error).__name__+':'+str(error)
 cutoff=now();cut=pd.Timestamp(cutoff).timestamp();final=g[(g.kickoff<cut)&g.home_score.notna()&g.away_score.notna()].copy();older=final[final.kickoff<=cut-7*86400];recent=final[final.kickoff>cut-7*86400]
 native_map={e['espn_event_id']:e for e in events};native_schedule={native(r['espn']):r['game_id'] for r in current.to_dict('records') if native(r.get('espn'))}
 for e in events:e['game_id']=native_schedule.get(e['espn_event_id'])
 retained=[]
 for run in ['C-NATIVE-GRADE-20261110-CINATL-01','C-NATIVE-GRADE-20261107-JAXBAL-01']:
  p=ROOT/'prospective/outcomes'/run/'evidence/native_status.json';item=json.loads(p.read_text());rsource=item['source'];mapped=dict(rsource,id=rsource['id'],status=rsource['HTTP_status'],SHA256=rsource['raw_SHA256']);rclock=status_http_clock(mapped)
  retained.append({'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'SHA256':sha(p.read_bytes()),'event':item['event'],'status_source':rsource,'HTTP_response_clock_at_original_observation':rclock})
 fallback_events={r['event']['espn_event_id']:r['event'] for r in retained};admitted=[];held=[];matches=[]
 for r in recent.to_dict('records'):
  eid=native(r.get('espn'));e=native_map.get(eid);origin='CURRENT_WEEK9_NATIVE_RESPONSE'
  if e is None:e=fallback_events.get(eid);origin='RETAINED_PREVIOUSLY_QUALIFIED_NATIVE_FINAL'
  valid=e is not None and e['season']==int(r['season']) and e['season_type']==2 and e['week']==int(r['week']) and e['state']=='post' and e['status_name']=='STATUS_FINAL' and e['completed'] is True and e['kickoff']<cut and abs(e['kickoff']-r['kickoff'])<1 and e['home_team']==r['home_team'] and e['away_team']==r['away_team'] and pd.Timestamp(e['observed_UTC']).timestamp()<=cut
  item={'game_id':r['game_id'],'espn_event_id':eid,'season':int(r['season']),'week':int(r['week']),'home_team':r['home_team'],'away_team':r['away_team'],'kickoff':r['kickoff'],'kickoff_UTC':pd.Timestamp(r['kickoff'],unit='s',tz='UTC').isoformat(),'rule':origin if valid else 'HELD_NO_MATCHED_EXPLICIT_NATIVE_FINAL'}
  if valid:admitted.append(r['game_id']);item['native_event']=e
  else:held.append(r['game_id'])
  matches.append(item)
 completed=sorted(set(older.game_id)|set(admitted));proof={'id':'C04-COMPLETED-GAME-PROOF-v1','actual_information_cutoff_UTC':cutoff,'events':events,'status_source':source,'status_HTTP_response_clock':clock,'status_execution_code_SHA256':sha(Path(__file__).read_bytes()),'native_request_failure':failure,'older_final_game_ids':sorted(older.game_id),'older_final_rule':'Officialsourcefinalscoreswithkickoffatleast7daysbeforeinformationcutoff;baselinearchivebefore2026+current2026schedule','older_schedule_sources':[{'path':'artifacts/basic-football-facts-v2.1.zip','SHA256':sha((ROOT/'artifacts/basic-football-facts-v2.1.zip').read_bytes())},{'path':str((OUT/'schedule.csv').relative_to(ROOT)),'SHA256':sha((OUT/'schedule.csv').read_bytes())}],'recent_native_final_game_ids':sorted(admitted),'held_recent_game_ids':sorted(held),'completed_game_ids':completed,'game_match_records':matches,'retained_native_final_proofs':retained,'not_claimed':'NativeFINALproofisnotoriginalhistoricalstatisticpublicationclock;predictorfilesstay18:55vintage. Nofootballline,forecastorfitissued.'}
 pp=OUT/'completed_game_proof.json';write(pp,proof)
 previous=(OUT/'MODEL_INPUT_MANIFEST.json').read_bytes();manifest=json.loads(previous);manifest.update(id='C04-CURRENT-MODEL-INPUTS-v2',actual_input_cutoff_UTC=cutoff,football_predictor_cutoff_UTC=json.loads(previous)['actual_input_cutoff_UTC'],preceding_input_manifest={'path':str((OUT/'MODEL_INPUT_MANIFEST.json').relative_to(ROOT)),'bytes':len(previous),'SHA256':sha(previous),'input_cutoff_UTC':json.loads(previous)['actual_input_cutoff_UTC']},finality_proof={'path':str(pp.relative_to(ROOT)),'bytes':pp.stat().st_size,'SHA256':sha(pp.read_bytes())},completed_game_ids=completed,held_recent_game_ids=sorted(held),native_completion_qualification='EXPLICIT_MATCHED_FINAL_OR_RETAINED_OLDER_FINAL_SCORES_NOT_UNQUALIFIED_STAT_APPEARANCE')
 manifest['sources']=source_rows();manifest['source_observed']={r['id']:r.get('observed_UTC') for r in source_rows() if r.get('status')==200};write(OUT/'MODEL_INPUT_MANIFEST_V2.json',manifest)
 guard();print('CURRENT_FINALITY_READY',len(completed),'older',len(older),'recent_native',len(admitted),'held',len(held),'cutoff',cutoff,'request_failure',failure)

def refresh_status():
 assert (OUT/'MODEL_INPUT_MANIFEST_V2.json').exists(),'FINALITY_QUALIFIED_MODEL_INPUT_V2_REQUIRED'
 assert not (OUT/'SOURCE_MANIFEST.json').exists(),'FINAL_SOURCE_MANIFEST_ALREADY_FROZEN'
 route=REPORT.parent/'CURRENT_STATUS_ROUTE_AMENDMENT.json';amendment=json.loads(route.read_text())
 assert amendment['next_reserved_attempt']==10 and amendment['total_GET_max_unchanged']==11 and amendment['source_bytes_max_unchanged']==TOTAL,'FINAL_STATUS_ROUTE_NOT_REGISTERED'
 url=amendment['url'];assert url=='https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates=20261112&limit=100','UNREGISTERED_NATIVE_STATUS_ROUTE'
 g,future=candidate_schedule();assert len(future),'NO_CURRENT_FUTURE_CANDIDATES'
 b,em=get('CURRENT_NATIVE_STATUS_FIRST_EVENT_20261112',url)
 clock=status_http_clock(em)
 observed=scoreboard_projection(json.loads(b),em['id'],em['observed_UTC']);assert len(observed)==len({e['espn_event_id'] for e in observed}),'DUPLICATE_NATIVE_STATUS_EVENT';eventmap={e['espn_event_id']:e for e in observed}
 # No automatic retry, range request or substitution of favorable older status.
 accepted=[];excluded=[];cut=pd.Timestamp.now(tz='UTC').timestamp()
 for r in future.to_dict('records'):
  e=eventmap.get(native(r['espn']))
  if not e:excluded.append(dict(game_id=r['game_id'],reason='NO_NATIVE_EVENT_IN_FINAL_SNAPSHOT'));continue
  valid=e['season']==2026 and e['season_type']==2 and e['week']==10 and e['state']=='pre' and e['status_name']=='STATUS_SCHEDULED' and e['completed'] is False and e['kickoff']>cut and abs(e['kickoff']-r['kickoff'])<1 and e['home_team']==team(r['home_team']) and e['away_team']==team(r['away_team'])
  if not valid:excluded.append(dict(game_id=r['game_id'],reason='CURRENT_NATIVE_ID_KICKOFF_TEAM_WEEK_STATUS_MISMATCH_OR_STARTED'));continue
  e=dict(e,game_id=r['game_id']);e['event_version']=sha(json.dumps({k:e[k] for k in ['game_id','espn_event_id','kickoff_UTC','state']},sort_keys=True).encode());accepted.append(e)
 assert accepted,'NO_NATIVE_VERIFIED_UPCOMING_EVENT'
 write(OUT/'events.json',accepted)
 event_bytes=(OUT/'events.json').read_bytes()
 assert all(e['source_id']==em['id'] and e['observed_UTC']==em['observed_UTC'] for e in accepted),'EVENT_RESPONSE_BINDING_MISMATCH'
 prior=(OUT/'MODEL_INPUT_MANIFEST_V2.json').read_bytes();roster=json.loads((REPORT/'ROSTER_QUALIFICATION.json').read_text());manifest={'id':'C04-CURRENT-SOURCE-ADMISSION-v1','actual_status_observed_UTC':em['observed_UTC'],'actual_admission_UTC':now(),'model_inputs':{'path':str((OUT/'MODEL_INPUT_MANIFEST_V2.json').relative_to(ROOT)),'SHA256':sha(prior),'input_cutoff_UTC':json.loads(prior)['actual_input_cutoff_UTC']},'events':accepted,'event':accepted[0],'target_season':2026,'target_week':10,'roster_source_week':None,'roster_contract':roster['source_contract'],'roster_qualification':{'path':str((REPORT/'ROSTER_QUALIFICATION.json').relative_to(ROOT)),'SHA256':sha((REPORT/'ROSTER_QUALIFICATION.json').read_bytes())},'scheduled_candidate_games':len(future),'verified_future_games':len(accepted),'excluded_events':excluded,'sources':source_rows(),'source_observed':{r['id']:r.get('observed_UTC') for r in source_rows() if r.get('status')==200},'forecasts_or_selections_issued':0,'scope':'Currentknownrosterqueryadmission,conditionalonappearance;nostarter/healthy/futuregamedayguarantee','final_status_age_rule':'Actualissuanceadaptermustcheckstatusage<=1800secondsandkickoffstillfuture;thisfileisnotpermanentavailability','current_offers':0,'status_execution_code_SHA256':sha(Path(__file__).read_bytes()),'current_source_transform_binding':'reports/profile-closure-next-02/current-source/SOURCE_TRANSFORM_BINDING.json','source_rights':'Existingordinarynflverse facts/CCBY4 andminimalnativeeventfacts;nooffercollection'}
 manifest['events_binding']={'path':str((OUT/'events.json').relative_to(ROOT)),'bytes':len(event_bytes),'SHA256':sha(event_bytes),'rows':len(accepted),'source_id':em['id'],'observed_UTC':em['observed_UTC'],'status_response_raw_SHA256':em['SHA256']}
 manifest['status_source']=em
 manifest['status_HTTP_response_clock']=clock
 manifest['source_route_amendment']={'path':str(route.relative_to(ROOT)),'SHA256':sha(route.read_bytes())}
 manifest['football_predictor_cutoff_UTC']=json.loads(prior)['football_predictor_cutoff_UTC']
 manifest['status_clock_repair_record']='reports/profile-closure-next-02/current-source/STATUS_HTTP_AGE_REPAIR.json'
 write(OUT/'SOURCE_MANIFEST.json',manifest);guard();print('CURRENT_NATIVE_STATUS_READY',len(accepted),'of',len(future),em['observed_UTC'])

if __name__=='__main__':
 REPORT.mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
 p=argparse.ArgumentParser();p.add_argument('--stage',choices=['roster','prepare_inputs','completion_proof','refresh_status'],required=True);a=p.parse_args()
 {'roster':roster,'prepare_inputs':prepare_inputs,'completion_proof':completion_proof,'refresh_status':refresh_status}[a.stage]()
