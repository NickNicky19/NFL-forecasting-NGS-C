"""Independent offline C04 repaired native-source/issuance boundary checks."""
import copy,hashlib,importlib.util,json,resource,sys,tempfile,time
from pathlib import Path
START=time.process_time();ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'src'))
import receiving_current_capture_c04 as c
source=ROOT/'reports/profile-closure-next-02/current-source/acquire_current_sources.py'
spec=importlib.util.spec_from_file_location('independent_status_source',source);collector=importlib.util.module_from_spec(spec);spec.loader.exec_module(collector)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
at=c.timestamp('2026-11-10T20:00:00+00:00')
base=dict(id='SOFTWARE_FIXTURE_NOT_NFL',state='RECEIVED',status=200,SHA256='0'*64,observed_UTC='2026-11-10T20:00:00+00:00',HTTP_Age='0',HTTP_Date='Tue, 10 Nov 2026 20:00:00 GMT')
clockcases=[('fresh',{},True),('age1800',{'HTTP_Age':'1800'},True),('age1801',{'HTTP_Age':'1801'},False),('negative',{'HTTP_Age':'-1'},False),('nan',{'HTTP_Age':'nan'},False),('inf',{'HTTP_Age':'inf'},False),('bad_age',{'HTTP_Age':'unknown'},False),('old_date',{'HTTP_Date':'Tue, 10 Nov 2026 18:00:00 GMT'},False),('future_date',{'HTTP_Date':'Tue, 10 Nov 2026 20:00:06 GMT'},False),('both_unknown',{'HTTP_Age':None,'HTTP_Date':None},False),('date_only',{'HTTP_Age':None},True),('age_only',{'HTTP_Date':None},True)]
for name,changes,want in clockcases:
 meta=dict(base,**changes)
 try:collector.status_http_clock(meta);accepted=True
 except (ValueError,AssertionError,TypeError):accepted=False
 assert accepted==want,name
 try:c.independent_response_clock(meta,at);accepted=True
 except (ValueError,AssertionError,TypeError):accepted=False
 assert accepted==want,('issuer',name)
elapsed_cases=0
for meta,elapsed,want in [(dict(base,HTTP_Age='1700'),100,True),(dict(base,HTTP_Age='1700'),101,False),(dict(base,HTTP_Age=None,HTTP_Date='Tue, 10 Nov 2026 19:33:20 GMT'),200,True),(dict(base,HTTP_Age=None,HTTP_Date='Tue, 10 Nov 2026 19:33:20 GMT'),201,False),(base,-1,False)]:
 try:c.independent_response_clock(meta,at+elapsed);accepted=True
 except ValueError:accepted=False
 assert accepted==want,('effective_age',elapsed,want);elapsed_cases+=1
with tempfile.TemporaryDirectory(prefix='.status-software-',dir=OUT)as tmp:
 p=Path(tmp)/'events.json';m=Path(tmp)/'SOURCE_MANIFEST.json'
 events=[dict(source_id=base['id'],observed_UTC=base['observed_UTC'])]
 p.write_text(json.dumps(events,separators=(',',':'))+'\n')
 manifest=dict(events_binding=dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,SHA256=sha(p),rows=1,source_id=base['id'],observed_UTC=base['observed_UTC'],status_response_raw_SHA256=base['SHA256']),status_source=base,status_HTTP_response_clock=collector.status_http_clock(base),model_inputs=dict(SHA256='1'*64),actual_status_observed_UTC=base['observed_UTC'],status_execution_code_SHA256=sha(source))
 def check(mm=manifest,ee=events,want=True,after=at-1):
  p.write_text(json.dumps(ee,separators=(',',':'))+'\n');m.write_text(json.dumps(mm,separators=(',',':'))+'\n')
  try:c.validate_status_snapshot(p,at,input_manifest_SHA256='1'*64,after=after);accepted=True
  except (ValueError,KeyError,TypeError,AssertionError):accepted=False
  assert accepted==want
 check();mutations=[]
 for key,changes in [('binding',lambda q:q['events_binding'].update(SHA256='2'*64)),('rawhash',lambda q:q['status_source'].update(SHA256='bad')),('source_state',lambda q:q['status_source'].update(state='FAILED')),('model_inputs',lambda q:q['model_inputs'].update(SHA256='2'*64)),('observed',lambda q:q.update(actual_status_observed_UTC='2026-11-10T20:00:01+00:00')),('collector_hash',lambda q:q.update(status_execution_code_SHA256='2'*64)),('clock_claim',lambda q:q['status_HTTP_response_clock'].update(HTTP_Age_seconds=100)),('cached_stale',lambda q:q['status_source'].update(HTTP_Age='7200'))]:
  q=copy.deepcopy(manifest);changes(q);check(q,want=False);mutations.append(key)
 check(ee=[dict(events[0],extra='changedbytes')],want=False);mutations.append('event_bytes')
 check(after=at+1,want=False);mutations.append('before_clean_start')
 # Even a self-consistent updated derivative hash cannot replace source identity.
 ee=[dict(events[0],source_id='OTHER_SOURCE')];q=copy.deepcopy(manifest);p.write_text(json.dumps(ee,separators=(',',':'))+'\n');q['events_binding'].update(SHA256=sha(p),bytes=p.stat().st_size);check(q,ee,want=False);mutations.append('event_source_after_hash_update')
receipt=dict(id='C04-INDEPENDENT-STATUS-GATE-v1',status='PASS_OFFLINE_REPAIR_BEFORE_ISSUANCE',collector_code_SHA256=sha(source),capture_code_SHA256=sha(ROOT/'src/receiving_current_capture_c04.py'),response_clock_cases=len(clockcases),independent_issuer_rechecks=len(clockcases),effective_age_at_issuance_cases=elapsed_cases,snapshot_binding_rejections=mutations,snapshot_valid_fixture=True,unknown_Age_not_imputed=True,combined_Age_plus_elapsed_and_Date_at_issuance_enforced=True,events_file_rawhash_source_observation_collector_and_input_manifest_bound=True,prior_path='Unexecutedpre-GETstatuspathwithcache-agegap preserved byproducer;no NFL forecast contaminated',actual_status_requests=0,current_fits=0,NFL_forecasts=0,limits='Synthetic boundary proof only. Actual final native response,draft/model inference,immutable issuance andGitHub/server proof remain separate later checks.',CPU_seconds=time.process_time()-START,peak_RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024)
(OUT/'STATUS_GATE_REVIEW.json').write_text(json.dumps(receipt,separators=(',',':'))+'\n');print(json.dumps(receipt,separators=(',',':')))
