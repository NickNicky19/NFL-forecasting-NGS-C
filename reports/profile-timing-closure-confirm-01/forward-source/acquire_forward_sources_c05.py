"""Four-request manual C05 eligibility/version snapshot; never fits or issues.

Full source bodies remain memory-only. Only permitted identity/status facts and
HTTP metadata are retained. Native status is deliberately a separate final stage.
"""
from pathlib import Path
from urllib.request import Request,build_opener,HTTPRedirectHandler
from urllib.error import HTTPError
from urllib.parse import urlsplit
from email.utils import parsedate_to_datetime
import argparse,csv,datetime,hashlib,importlib.util,io,json,math,re,sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'src'))
from forward_sources_v4 import team,native,scoreboard_projection,match_event
from context_sources_c01 import guard
REPORT=ROOT/'reports/profile-timing-closure-confirm-01/forward-source'
OUT=ROOT/'sources/profile-timing-closure-confirm-01/forward'
REG=ROOT/'protocol/PROFILE_TIMING_CLOSURE_CONFIRM_01_C.json'
OLD=ROOT/'sources/profile-closure-next-02/MODEL_INPUT_MANIFEST_V2.json'
SCHEDULE=ROOT/'sources/profile-closure-next-02/candidate_schedule.json'
CLOCK_CODE=ROOT/'reports/profile-closure-next-02/current-source/acquire_current_sources.py'
SELECTED_HEADERS={'date','age','last-modified','etag','content-type','content-length','cache-control'}

def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def sha(b):return hashlib.sha256(b).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def write(p,obj):
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n')
def binding(p):return {'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'SHA256':sha(p.read_bytes())}
class PreserveHEAD(HTTPRedirectHandler):
 def redirect_request(self,req,fp,code,msg,headers,newurl):
  redirected=super().redirect_request(req,fp,code,msg,headers,newurl)
  if redirected is not None and req.get_method()=='HEAD':redirected.method='HEAD'
  return redirected
OPENER=build_opener(PreserveHEAD())

def request(source_id,url,method='GET'):
 reg=read(REG)['forward_capture'];lp=REPORT/'REQUESTS.json';ledger=read(lp) if lp.exists() else []
 assert len(ledger)<reg['source_requests_max'],'C05_SOURCE_REQUEST_CAP'
 assert source_id not in {r['id'] for r in ledger},'SOURCE_ATTEMPT_ALREADY_RETAINED_NO_IMPLICIT_RETRY'
 remaining=reg['source_body_bytes_max']-sum(r.get('body_bytes_read',0) for r in ledger)
 cap=min(reg['single_body_bytes_max'],remaining);assert cap>0
 meta={'id':source_id,'url':url,'method':method,'started_UTC':now(),'state':'ATTEMPTING','body_read_bound':0 if method=='HEAD' else cap}
 ledger.append(meta);write(lp,ledger)
 try:
  with OPENER.open(Request(url,method=method,headers={'User-Agent':'C05-bounded-current-eligibility'}),timeout=30) as response:
   header_pairs=[(k,v) for k,v in response.headers.items() if k.lower() in SELECTED_HEADERS]
   lower={k.lower():v for k,v in header_pairs};body=b'' if method=='HEAD' else response.read(cap)
   meta.update(state='RECEIVED',HTTP_status=response.status,observed_UTC=now(),body_bytes_read=len(body),
               SHA256=sha(body) if method=='GET' else None,HTTP_headers_original_case=header_pairs,
               HTTP_Date=lower.get('date'),HTTP_Age=lower.get('age'),HTTP_Last_Modified=lower.get('last-modified'),
               ETag=lower.get('etag'),Content_Type=lower.get('content-type'),Content_Length=lower.get('content-length'),
               response_final_host=urlsplit(response.geturl()).hostname)
   assert response.status==200,'SOURCE_HTTP_NOT_200'
   assert method=='HEAD' or len(body)<cap,'SOURCE_BODY_AT_BOUND_POSSIBLY_TRUNCATED'
  write(lp,ledger);return body,meta
 except Exception as error:
  meta.update(state='FAILED',observed_UTC=now(),error_type=type(error).__name__,error=str(error),body_bytes_read=meta.get('body_bytes_read',0))
  if isinstance(error,HTTPError):meta['HTTP_error_status']=error.code;meta['error_body_bytes']='NOT_READ'
  write(lp,ledger);raise

def source_rows():return read(REPORT/'REQUESTS.json')
def status_clock(meta):
 spec=importlib.util.spec_from_file_location('retained_c04_clock',CLOCK_CODE);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 return m.status_http_clock(meta)
def validate_roster_publisher(meta,at):
 assert meta.get('HTTP_Last_Modified'),'CURRENT_ROSTER_PUBLISHER_CLOCK_UNKNOWN'
 published=parsedate_to_datetime(meta['HTTP_Last_Modified']);assert published.tzinfo is not None
 elapsed=(at-published).total_seconds();assert 0<=elapsed<=36*3600,'CURRENT_ROSTER_PUBLISHER_STALE_OR_FUTURE'
 return published.astimezone(datetime.timezone.utc).isoformat(),elapsed

def prepare():
 assert not (OUT/'INPUT_MANIFEST.json').exists(),'C05_INPUT_MANIFEST_FROZEN'
 reg=read(REG)['forward_capture'];old=read(OLD);old_sources={x['id']:x for x in old['sources']}
 candidate=next(g for g in read(SCHEDULE)['games'] if g['game_id']==reg['target_game'])
 assert native(candidate['espn'])==reg['native_event']
 assert datetime.datetime.fromisoformat(reg['target_kickoff_UTC'].replace('Z','+00:00')).timestamp()==candidate['kickoff']
 body,roster_meta=request('C05_CURRENT_SEASON_ROSTER',old_sources['CURRENT_SEASON_ROSTER']['url'])
 reader=csv.DictReader(io.StringIO(body.decode('utf-8-sig')));header=list(reader.fieldnames or [])
 fields=['season','team','position','gsis_id','full_name','status'];assert set(fields)<=set(header),'ROSTER_SCHEMA_UNQUALIFIED'
 roster=[]
 for row in reader:
  if row['position'] not in ['QB','RB','WR','TE']:continue
  item={k:(row[k] if row[k]!='' else None) for k in fields};item['season']=int(item['season']);roster.append(item)
 write(OUT/'roster_current_season.json',roster)
 published,age=validate_roster_publisher(roster_meta,datetime.datetime.now(datetime.timezone.utc))
 versions=[]
 for old_id,new_id in [('CURRENT_PLAYER_STATS','C05_STATS_VERSION_HEAD'),('CURRENT_PBP','C05_PBP_VERSION_HEAD')]:
  previous=old_sources[old_id];_,meta=request(new_id,previous['url'],'HEAD')
  before=previous.get('ETag');after=meta.get('ETag');strong=lambda v:isinstance(v,str) and v.startswith('"') and v.endswith('"') and not v.startswith('W/')
  equal=strong(before) and strong(after) and before==after
  versions.append(dict(source_id=old_id,old_ETag=before,current_ETag=after,strong_ETag_match=equal,
       version_state='STRONG_ETAG_MATCH_NO_BODY_REFETCH' if equal else 'CHANGED_OR_UNKNOWN_NO_LATEST_INPUT_CLAIM',
       old_body_SHA256=previous['SHA256'],current_body_SHA256=None,body_not_downloaded=True,HEAD=meta))
 cutoff=now();valid_ids={r['gsis_id'] for r in roster if isinstance(r['gsis_id'],str) and re.fullmatch(r'00-\d{7}',r['gsis_id'])}
 counts={pid:sum(r['gsis_id']==pid for r in roster) for pid in valid_ids}
 slate=[r for r in roster if team(r['team']) in ['NE','DET']]
 eligible=[r for r in slate if r['season']==2026 and r['position'] in ['RB','WR','TE'] and r['status']=='ACT' and r['gsis_id'] in valid_ids and counts[r['gsis_id']]==1]
 manifest={'id':'C05-CURRENT-ELIGIBILITY-INPUTS-v1','created_UTC':cutoff,'actual_eligibility_cutoff_UTC':cutoff,
   'roster_contract':'NFLVERSE_CURRENT_KNOWN_SEASON_ROSTER_SNAPSHOT-v1','roster_week':None,'raw_roster_has_week_column':'week' in header,
   'roster_projection':binding(OUT/'roster_current_season.json'),'sources':source_rows(),'roster_source':roster_meta,
   'roster_published_UTC':published,'roster_publisher_age_seconds_at_qualification':age,
   'basic_roster_records':len(roster),'target_basic_roster_records':len(slate),'target_ACT_receiving_candidates':len(eligible),
   'target_role_counts':{r:sum(x['position']==r for x in eligible) for r in ['RB','WR','TE']},
   'candidate_game':candidate,'target_game':reg['target_game'],'original_model_input_manifest':binding(OLD),
   'original_candidate_schedule':binding(SCHEDULE),'football_version_checks':versions,
   'all_football_HEAD_versions_match':all(x['strong_ETag_match'] for x in versions),
   'forecast_information_policy':reg['information_policy'],'football_source_cutoff_UTC':old['football_predictor_cutoff_UTC'],
   'model_feature_cutoff_UTC':old['actual_input_cutoff_UTC'],'individual_transaction_effective_UTC':None,
   'health_and_starter_state':'UNKNOWN_NOT_INFERRED_FROM_ACT_STATUS','model_fits':0,'forecast_rows_issued':0,
   'current_offers':0,'source_execution_code':binding(Path(__file__)),'clock_helper':binding(CLOCK_CODE),
   'scope':'Currentknownseasonrosterandversionmetadataonly;notfuturegamedayparticipation. No current football body downloaded or backdated.'}
 write(OUT/'INPUT_MANIFEST.json',manifest);guard();projection_check()
 write(REPORT/'PREPARE_READINESS.json',dict(id='C05-SOURCE-PREPARE-READINESS-v1',created_UTC=now(),input_manifest=binding(OUT/'INPUT_MANIFEST.json'),
   basic=len(roster),target_basic=len(slate),eligible_receiving=len(eligible),native_event_state='DEFERRED_FINAL_ROOT_GO_REQUIRED',
   football_source_version_state='MATCHED_METADATA_ONLY' if manifest['all_football_HEAD_versions_match'] else 'CHANGED_OR_UNKNOWN_KEEP_EXPLICIT_OLDER_CUTOFF',
   requests_consumed=len(source_rows()),new_fits=0,new_forecasts=0))
 print('C05_PRESTATUS_READY',len(roster),len(slate),len(eligible),manifest['all_football_HEAD_versions_match'])

def projection_check():
 cap=read(REG)['forward_capture']['source_projection_bytes_max']
 assert sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file())<=cap,'C05_SOURCE_PROJECTION_CAP'

def native_status():
 assert (OUT/'INPUT_MANIFEST.json').exists(),'PRESTATUS_INPUTS_REQUIRED'
 assert not (OUT/'SOURCE_MANIFEST.json').exists(),'C05_NATIVE_SOURCE_ALREADY_FROZEN'
 inputs=read(OUT/'INPUT_MANIFEST.json');candidate=inputs['candidate_game'];validate_roster_publisher(inputs['roster_source'],datetime.datetime.now(datetime.timezone.utc))
 body,meta=request('C05_NATIVE_SUNDAY_20261115','https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates=20261115&limit=100')
 clock=status_clock(meta);events=scoreboard_projection(json.loads(body),meta['id'],meta['observed_UTC'])
 assert len(events)==len({e['espn_event_id'] for e in events}),'DUPLICATE_NATIVE_EVENT_ID'
 write(OUT/'native_events_all.json',events)
 target=[e for e in events if e['espn_event_id']==native(candidate['espn'])];assert len(target)==1,'TARGET_NATIVE_EVENT_MISSING_OR_DUPLICATE'
 event=target[0];assert match_event(candidate,event,datetime.datetime.now(datetime.timezone.utc).timestamp()),'TARGET_NATIVE_EVENT_NOT_MATCHED_FUTURE'
 event=dict(event,game_id=candidate['game_id']);write(OUT/'events.json',[event])
 manifest={'id':'C05-CURRENT-FORWARD-SOURCE-v1','created_UTC':now(),'INPUT_MANIFEST':binding(OUT/'INPUT_MANIFEST.json'),
  'model_inputs':dict(binding(OUT/'INPUT_MANIFEST.json'),input_cutoff_UTC=inputs['actual_eligibility_cutoff_UTC']),
  'events_binding':dict(binding(OUT/'events.json'),rows=1,source_id=meta['id'],observed_UTC=meta['observed_UTC'],status_response_raw_SHA256=meta['SHA256']),
  'events':[event],'status_source':meta,'status_HTTP_response_clock':clock,'status_execution_code_path':str(Path(__file__).relative_to(ROOT)),
  'status_execution_code_SHA256':sha(Path(__file__).read_bytes()),'roster_contract':inputs['roster_contract'],'roster_week':None,
  'sources':source_rows(),'current_offers':0,'forecast_or_selection_issuance':0,
  'source_semantics':'Native current pregame eligibility plus current-known season roster; no latest-football model update or healthy/starter claim.'}
 write(OUT/'SOURCE_MANIFEST.json',manifest);guard();projection_check()
 write(REPORT/'FINAL_NATIVE_READINESS.json',dict(id='C05-FINAL-NATIVE-READINESS-v1',created_UTC=now(),source_manifest=binding(OUT/'SOURCE_MANIFEST.json'),
  game_id=candidate['game_id'],native_event=event['espn_event_id'],kickoff_UTC=event['kickoff_UTC'],native_observed_UTC=event['observed_UTC'],
  HTTP_response_clock=clock,requests_consumed=len(source_rows()),new_fits=0,new_forecasts=0))
 print('C05_NATIVE_READY',candidate['game_id'],event['observed_UTC'])

if __name__=='__main__':
 REPORT.mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
 p=argparse.ArgumentParser();p.add_argument('--stage',choices=['prepare','native-status'],required=True);a=p.parse_args()
 (prepare if a.stage=='prepare' else native_status)()
