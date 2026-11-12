"""One authorized current-input analysis pass; no fit, inference or issuance.

Reuses the retained method-preserving HTTP opener, roster clock contract and team
normalization. Only this new report directory is written; old snapshots are read.
"""
from pathlib import Path
from urllib.request import Request
from urllib.parse import urlsplit
from urllib.error import HTTPError
import csv,datetime,hashlib,importlib.util,io,json,re
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
HELPER=ROOT/'reports/profile-timing-closure-confirm-01/forward-source/acquire_forward_sources_c05.py'
spec=importlib.util.spec_from_file_location('retained_source_helpers',HELPER)
h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)

def read(p):return json.loads(Path(p).read_text())
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def sha(b):return hashlib.sha256(b).hexdigest()
def write(p,obj):p.write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n')
def bind(p):return {'path':p.relative_to(ROOT).as_posix(),'bytes':p.stat().st_size,'SHA256':sha(p.read_bytes())}
def request(sid,url,method):
 p=OUT/'SOURCE_REQUESTS.json';ledger=read(p) if p.exists() else []
 assert len(ledger)<3 and sid not in {x['id'] for x in ledger},'ANALYSIS_REQUEST_CAP_OR_DUPLICATE'
 assert read(ROOT/'reports/category-decision-release-01/CURRENT_SOURCE_ANALYSIS_GO.json')['requests_authorized_now']==3
 remaining=8388608-sum(x.get('body_bytes_read',0) for x in ledger);cap=min(3145728,remaining);assert cap>0
 m={'id':sid,'url':url,'method':method,'started_UTC':now(),'state':'ATTEMPTING','body_read_bound':0 if method=='HEAD' else cap}
 ledger.append(m);write(p,ledger)
 try:
  with h.OPENER.open(Request(url,method=method,headers={'User-Agent':'C-category-current-source-analysis'}),timeout=30) as response:
   pairs=[(k,v) for k,v in response.headers.items() if k.lower() in h.SELECTED_HEADERS];lower={k.lower():v for k,v in pairs}
   body=b'' if method=='HEAD' else response.read(cap)
   m.update(state='RECEIVED',HTTP_status=response.status,observed_UTC=now(),body_bytes_read=len(body),SHA256=sha(body) if method=='GET' else None,HTTP_headers_original_case=pairs,HTTP_Date=lower.get('date'),HTTP_Age=lower.get('age'),HTTP_Last_Modified=lower.get('last-modified'),ETag=lower.get('etag'),Content_Length=lower.get('content-length'),Content_Type=lower.get('content-type'),response_final_host=urlsplit(response.geturl()).hostname)
   assert response.status==200 and (method=='HEAD' or len(body)<cap),'HTTP_STATUS_OR_BODY_BOUND'
  write(p,ledger);return body,m
 except Exception as e:
  m.update(state='FAILED',observed_UTC=now(),error_type=type(e).__name__,error=str(e),body_bytes_read=m.get('body_bytes_read',0))
  if isinstance(e,HTTPError):m['HTTP_error_status']=e.code;m['error_body_bytes']='NOT_READ'
  write(p,ledger);raise

def run():
 assert not (OUT/'SOURCE_ANALYSIS.json').exists(),'IMMUTABLE_ANALYSIS_EXISTS'
 prior=read(ROOT/'sources/profile-closure-next-02/MODEL_INPUT_MANIFEST_V2.json');sources={x['id']:x for x in prior['sources']}
 body,rm=request('CATEGORY_CURRENT_ROSTER',sources['CURRENT_SEASON_ROSTER']['url'],'GET')
 reader=csv.DictReader(io.StringIO(body.decode('utf-8-sig')));header=list(reader.fieldnames or []);fields=['season','team','position','gsis_id','full_name','status'];assert set(fields)<=set(header),'ROSTER_REQUIRED_FIELDS'
 roster=[]
 for row in reader:
  if row['position'] not in ['QB','RB','WR','TE']:continue
  z={k:row[k] if row[k]!='' else None for k in fields};z['season']=int(z['season']);roster.append(z)
 write(OUT/'roster_current_season.json',roster)
 publisher_error=None
 try:published,pub_age=h.validate_roster_publisher(rm,datetime.datetime.now(datetime.timezone.utc));publisher_state='PASS_36H_SOURCE_PUBLISHER_BOUND'
 except Exception as e:published=pub_age=None;publisher_state='FAILED';publisher_error=repr(e)
 checks=[]
 for key,sid in [('CURRENT_PLAYER_STATS','CATEGORY_STATS_VERSION_HEAD'),('CURRENT_PBP','CATEGORY_PBP_VERSION_HEAD')]:
  old=sources[key];_,meta=request(sid,old['url'],'HEAD');before=old.get('ETag');after=meta.get('ETag');strong=lambda v:isinstance(v,str) and v.startswith('"') and v.endswith('"') and not v.startswith('W/')
  equal=strong(before) and strong(after) and before==after
  checks.append({'source_id':key,'old_ETag':before,'current_ETag':after,'strong_ETag_match':equal,'old_body_SHA256':old['SHA256'],'new_body_SHA256':None,'body_not_downloaded':True,'old_body_bytes':old['bytes'],'current_Content_Length':meta['Content_Length'],'HEAD':meta})
 valid={r['gsis_id'] for r in roster if re.fullmatch(r'00-\d{7}',str(r['gsis_id']))};counts={pid:sum(r['gsis_id']==pid for r in roster) for pid in valid}
 target=[r for r in roster if h.team(r['team']) in ['WAS','NYG']]
 eligible=[r for r in target if r['season']==2026 and r['position'] in ['RB','WR','TE'] and r['status']=='ACT' and r['gsis_id'] in valid and counts[r['gsis_id']]==1]
 oldroster=read(ROOT/'sources/profile-closure-next-02/roster_current_season.json');oldtarget=[r for r in oldroster if h.team(r['team']) in ['WAS','NYG']]
 oldkeys={(r['gsis_id'],r['team'],r['position'],r['status']) for r in oldtarget};newkeys={(r['gsis_id'],r['team'],r['position'],r['status']) for r in target}
 out={'id':'CATEGORY-CURRENT-SOURCE-ANALYSIS-v1','created_UTC':now(),'requests_consumed':3,'reserved_final_native_requests_remaining':1,'new_fits':0,'new_inference_rows':0,'new_issues':0,'roster':{'projection':bind(OUT/'roster_current_season.json'),'raw_headers':header,'raw_has_week_column':'week' in header,'contract':'NFLVERSE_CURRENT_KNOWN_SEASON_ROSTER_SNAPSHOT-v1','basic_records':len(roster),'target_basic_records':len(target),'target_ACT_receiving_candidates':len(eligible),'target_ACT_WR_TE_candidates':sum(r['position'] in ['WR','TE'] for r in eligible),'target_role_counts':{role:sum(r['position']==role for r in eligible) for role in ['RB','WR','TE']},'publisher_state':publisher_state,'publisher_error':publisher_error,'published_UTC':published,'publisher_age_seconds':pub_age,'source':rm,'team_role_status_rows_added':[list(x) for x in sorted(newkeys-oldkeys)],'team_role_status_rows_removed':[list(x) for x in sorted(oldkeys-newkeys)],'individual_transaction_effective_UTC':None,'starter_health_participation':'UNKNOWN_NOT_INFERRED_FROM_ACT'},'football_version_checks':checks,'all_football_HEAD_versions_match':all(x['strong_ETag_match'] for x in checks),'old_football_source_cutoff_UTC':prior['football_predictor_cutoff_UTC'],'old_feature_cutoff_UTC':prior['actual_input_cutoff_UTC'],'source_execution_code':bind(Path(__file__)),'retained_helper':bind(HELPER),'scope':'Analysis only: no target outcome, native status, model fit, inference, current offer or issuance. Strong metadata match cannot backdate a source or refresh original model feature clock.'}
 write(OUT/'SOURCE_ANALYSIS.json',out)
 write(OUT/'SOURCE_RESOURCE.json',{'requests':3,'body_bytes':sum(x.get('body_bytes_read',0) for x in read(OUT/'SOURCE_REQUESTS.json')),'upstream_request_cap':4,'analysis_requests_authorized':3,'native_final_request_deferred':True,'new_fits':0,'new_forecasts':0})
 print(json.dumps({'roster_basic':len(roster),'target_basic':len(target),'eligible':len(eligible),'publisher_state':publisher_state,'same_football_versions':out['all_football_HEAD_versions_match'],'version_checks':[{k:x[k] for k in ['source_id','strong_ETag_match','current_Content_Length']} for x in checks]}))
if __name__=='__main__':run()
