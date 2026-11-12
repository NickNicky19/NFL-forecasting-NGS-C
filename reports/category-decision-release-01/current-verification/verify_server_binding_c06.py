"""Independent appended server/snapshot qualification from retained responses."""
from pathlib import Path
import json,base64,gzip,lzma,hashlib,datetime,subprocess,ast,time,resource,sys
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent;CACHE=Path('/workspace/c06-fresh-restore');cpu=time.process_time()
def read(p):
 p=Path(p);b=p.read_bytes();return json.loads(lzma.decompress(b) if p.suffix=='.xz' else b)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dt(x):
 d=datetime.datetime.fromisoformat(x.replace('Z','+00:00'));assert d.tzinfo;return d
responses=read(CACHE/'SERVER_BINDING_RESPONSES.json');snapshot=responses['snapshot'];raw=base64.b64decode(''.join(snapshot['content'].split()),validate=True)
assert len(raw)==29775 and hashlib.sha256(raw).hexdigest()=='9abd61a443ac38e2a3cb4d59f0ee7d35569657eb33a629dd9d2ef34a94b6a4ea'
assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==snapshot['sha']
p=CACHE/'reports/category-decision-release-01/current/source-snapshots/prospective_v4_at_9994055.py';p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
assert raw==(ROOT/'reports/category-decision-release-01/current/source-snapshots/prospective_v4_at_9994055.py').read_bytes()
workflow=json.loads(responses['workflow']['content']);jobset=json.loads(responses['jobs']['content']);assert workflow['id']==43143050235 and workflow['head_sha']=='d1425e648ce14a99449873f5c8223fc423b5635e' and workflow['status']=='completed' and workflow['conclusion']=='success' and workflow['event']=='pull_request' and workflow['path']=='.github/workflows/c-checks-pages.yml'
jobs=jobset['jobs'];checks=[j for j in jobs if j['name']=='checks'];assert len(checks)==1 and checks[0]['conclusion']=='success' and checks[0]['status']=='completed';check=checks[0]
steps=[s for s in check['steps'] if s['name']=='Verify immutable prospective captures'];assert len(steps)==1 and steps[0]['conclusion']=='success'
receipt=read(ROOT/'reports/category-decision-release-01/CURRENT_PUBLICATION_RECEIPT.json');run=CACHE/'prospective/runs/C-C06-20261112-W10-CURRENT-P1-01';m=read(run/'RUN.json');rows=read(run/'FORECASTS.json.xz')
assert receipt['capture_commit']==workflow['head_sha'] and receipt['server_workflow_run']==workflow['id'] and receipt['qualified_prospective'] is True and receipt['not_client_commit_dates'] is True and receipt['fresh_GitHub_bytes_verified'] is True
assert receipt['run_manifest_SHA256']==sha(run/'RUN.json') and receipt['forecast_blob_SHA256']==sha(run/'FORECASTS.json.xz')
assert receipt['server_run_created_UTC']==workflow['created_at'] and receipt['server_run_started_UTC']==workflow['run_started_at'] and receipt['server_check_completed_UTC']==check['completed_at']
assert dt(m['issued_UTC'])<dt(workflow['created_at'])<=dt(workflow['run_started_at'])<=dt(check['completed_at'])
assert all(dt(check['completed_at'])<dt(r['expires_UTC']) and dt(check['completed_at'])+datetime.timedelta(seconds=300)<dt(r['kickoff_UTC']) for r in rows)
oldcode=subprocess.check_output(['git','show','e9b56a314acea2fbe958dc4415e8693c56516970:src/current_query_delivery_c06.py'],cwd=ROOT,text=True);newcode=(ROOT/'src/current_query_delivery_c06.py').read_text()
assert hashlib.sha256(oldcode.encode()).hexdigest()=='65d9823f42e6d1edb4b4ea9e884cc0f3052349cf09c1809e202c2516bbf5322b' and hashlib.sha256(newcode.encode()).hexdigest()=='bcfd657f541394db89111bd0bd1e8579ab1c91c43a0ae9dfb549750a40e697f1'
a,b=ast.parse(oldcode),ast.parse(newcode)
def normalize(tree,new):
 f=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='assess');names={'historical_source','historical_bytes','old_prospective'} if new else {'old_prospective'};removed=[];kept=[]
 for n in f.body:
  targets={t.id for t in n.targets if isinstance(t,ast.Name)} if isinstance(n,ast.Assign) else set()
  tagged=bool(targets&names) or (new and isinstance(n,ast.Assert) and any(isinstance(v,ast.Name) and v.id=='historical_bytes' for v in ast.walk(n.test)))
  if tagged:
   if not removed:kept.append(ast.Assign(targets=[ast.Name(id='old_prospective',ctx=ast.Store())],value=ast.Constant(value='EXACT_HASH_BOUND_HISTORICAL_UTF8_TEXT')))
   removed.append(n)
  else:kept.append(n)
 assert len(removed)==(4 if new else 1);f.body=kept;return ast.dump(tree,include_attributes=False)
assert normalize(a,False)==normalize(b,True),'PACKAGING_FIX_CHANGED_MORE_THAN_HISTORICAL_SOURCE_READ'
sys.path.insert(0,str(ROOT/'src'));import current_query_delivery_c06 as current
saved=read(ROOT/'reports/category-decision-release-01/current/P1_CURRENT_REUSE_ASSESSMENT.json');at=dt(m['issued_UTC']).timestamp()
with patch.object(current.subprocess,'check_output',side_effect=AssertionError('NO_HISTORICAL_GIT_COMMAND_ALLOWED')),patch.object(current,'pooled_mu',side_effect=AssertionError('NO_NFL_INFERENCE_ALLOWED')):
 assessment=current.assess(at=at)
assert assessment==saved['assessment']
prior=read(OUT/'PRIOR_CONTEXT_FRESH_RECOVERY.json');extra_snapshot=len(json.dumps({k:snapshot[k] for k in ['content','encoding','sha','display_url','display_title']},separators=(',',':'),ensure_ascii=False).encode());extra_metadata=sum(len(json.dumps({k:v for k,v in responses[x].items() if k not in ['started_UTC','completed_UTC']},separators=(',',':'),ensure_ascii=False).encode()) for x in ['workflow','jobs']);returned=prior['total_returned_structured_content_bytes']+extra_snapshot+extra_metadata;assert returned<3145728
(OUT/'SERVER_BINDING_METADATA.json.xz').write_bytes(lzma.compress(json.dumps({'workflow':workflow,'jobs':jobset},separators=(',',':')).encode()))
result=dict(id='C06-INDEPENDENT-APPENDED-SERVER-QUALIFICATION-v1',checked_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),status='PASS24FRESHFILES_PLUS_EXACT_SUCCESSFUL_SERVER_BINDING;ORIGINAL_SITE_USE_NOT_INFERRED',qualification_head=workflow['head_sha'],server_workflow_run=workflow['id'],server_run_URL=workflow['html_url'],server_created_UTC=workflow['created_at'],server_started_UTC=workflow['run_started_at'],server_checks_completed_UTC=check['completed_at'],immutable_capture_step_completed_UTC=steps[0]['completed_at'],server_qualified_before_snapshot_expiry=True,forecast_snapshot_expiry_UTC=min(r['expires_UTC'] for r in rows),actual_capture_execution_commit=m['code_commit'],actual_capture_adapter_SHA256=m['code_SHA256']['src/current_query_delivery_c06.py'],publication_validation_adapter_SHA256=hashlib.sha256(newcode.encode()).hexdigest(),historical_source_snapshot=dict(path=str(p.relative_to(CACHE)),bytes=len(raw),SHA256=hashlib.sha256(raw).hexdigest(),Git_blob_SHA1=snapshot['sha'],started_UTC=snapshot['started_UTC'],completed_UTC=snapshot['completed_UTC']),packaging_AST_difference_only_verified_historical_source_read=True,actual_assessment_unchanged_with_Git_and_inference_forbidden=True,prior23_recovery='PRIOR_CONTEXT_FRESH_RECOVERY.json',total_file_reads=24,workflow_metadata_reads=2,total_read_operations=26,restored_decoded_file_bytes=prior['total_decoded_restored_bytes']+len(raw),returned_structured_content_bytes=returned,returned_content_byte_cap=3145728,accounting_limit='Connector-returned content/operation accounting; hidden HTTP headers/envelopes are not exposed.',receipt_SHA256=sha(ROOT/'reports/category-decision-release-01/CURRENT_PUBLICATION_RECEIPT.json'),RUN_SHA256=sha(run/'RUN.json'),FORECASTS_SHA256=sha(run/'FORECASTS.json.xz'),model_and_forecast_bytes_changed=False,new_fits=0,extra_NFL_inference=0,new_upstream_source_collection=0,CPU_seconds=time.process_time()-cpu,peak_RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,limitations=['Original capture code65/e9 and later packaging-validation codebcfd/d142 are deliberately distinct; no re-issuance or forecast replacement.','Clean-checkout failures were packaging/recovery/source-text availability failures, not demonstrated NFL prediction defects; original failures retained by owner.','Server success is pregame persistence, not primary-product qualification or actual original-site activation.','Expiry stops new recommendation use; original supplementary snapshot remains later-gradeable and does not replace earlier75.','Served research consumer and original production consumption remain separate verification states.'])
(OUT/'SERVER_QUALIFICATION_INDEPENDENT.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
