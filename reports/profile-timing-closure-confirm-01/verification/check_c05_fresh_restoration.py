import pathlib,json,lzma,hashlib,base64,datetime,email.utils,math,time,resource
cpu=time.process_time();repo=pathlib.Path('/workspace/ngs-c');cache=pathlib.Path('/workspace/c05-fresh-restore');V=repo/'reports/profile-timing-closure-confirm-01/verification'
def read(p):return json.loads(lzma.decompress(p.read_bytes()) if p.suffix=='.xz' else p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dt(s):
 d=datetime.datetime.fromisoformat(s.replace('Z','+00:00'));assert d.tzinfo;return d
payload=read(cache/'FETCH_RESPONSES.json');assert payload['commit']=='5a2fec4457154b423ab631ea3c896c077ebe85b4' and payload['repository']=='NickNicky19/NFL-forecasting-NGS-C'
plan={r['path']:r for r in payload['plan']};assert len(plan)==len(payload['records'])==20
receipts=[];base64_bytes=0
for item in payload['records']:
 p=item['path'];assert p in plan and not pathlib.PurePosixPath(p).is_absolute() and '..' not in pathlib.PurePosixPath(p).parts
 assert item['encoding']=='base64';encoded=''.join(item['content'].split());b=base64.b64decode(encoded,validate=True);base64_bytes+=len(item['content'].encode())
 assert len(b)==plan[p]['bytes'] and hashlib.sha256(b).hexdigest()==plan[p]['SHA256']
 assert hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==item['sha']
 q=cache/p;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(b)
 receipts.append({'path':p,'bytes':len(b),'SHA256':hashlib.sha256(b).hexdigest(),'Git_blob_SHA1':item['sha'],'immutable_bytes_match':True,'started_UTC':item.get('started_UTC'),'completed_UTC':item.get('completed_UTC'),'clock_state':item.get('request_clock_state','ACTUAL_CONNECTOR_CALL_CLOCKS_RECORDED')})
P=cache/'prospective/runs/C-C05-NEDET-FIRST-01';R=read(P/'RUN.json');D=read(P/'INFERENCE_DRAFT.json');F=read(P/'FORECASTS.json.xz');DF=read(P/'inference_draft/FORECASTS_DRAFT.json.xz');S=read(P/'STATUS_SOURCE_MANIFEST.json');board=read(P/'CURRENT_BOARD.json.xz');C=read(P/'CLEAN_START_PROOF.json');N=read(P/'NATIVE_STATUS.json');IV=read(P/'INDEPENDENT_STATUS_VERIFICATION.json')
for rel,b in R['files'].items():assert sha(P/rel)==b['SHA256'] and (P/rel).stat().st_size==b['bytes']
for rel,b in D['files'].items():assert sha(P/'inference_draft'/rel)==b['SHA256']
assert sha(P/'INFERENCE_DRAFT.json')==sha(P/'inference_draft/DRAFT.json')
assert R['information_policy']=='FROZEN_FOOTBALL_SNAPSHOT_FIRST_PUBLICATION_SHADOW' and R['information_cutoff_UTC']=='2026-11-10T19:23:09.469852+00:00'
assert R['lineage']['football_source_cutoff_UTC']=='2026-11-10T18:55:28.982066+00:00' and R['eligibility_input_cutoff_UTC']=='2026-11-10T22:51:53.312826+00:00'
assert R['publication_state']=='AWAITING_GITHUB_SERVER_PROOF' # Original immutable state is preserved; qualification is an appended receipt.
assert R['new_fits']==0 and not R['primary_replacement'] and R['real_offers']==R['real_selections']==0
assert len(F)==len(DF)==69 and len({(r['player_id'],r['model_id']) for r in F})==69 and len({r['player_id'] for r in F})==23
assert len(board)==959 and sum(r['eligible_current_query'] for r in board)==23 and sum(r['available_all_models'] for r in board if r['eligible_current_query'])==23
prior=read(V/'C05_ACTUAL_INFERENCE_INDEPENDENT.json');assert sha(P/'inference_draft/FORECASTS_DRAFT.json.xz')==prior['forecasts_SHA256'] and sha(P/'INFERENCE_DRAFT.json')==prior['draft_SHA256']
lookup={(r['player_id'],r['model_id']):r for r in DF};allowed={'state','run_id','forecast_id','issued_UTC','generated_UTC','native_status_observed_UTC','event_version','event_state','native_event_source','expires_UTC','expiry_action','lead_seconds_at_issuance'}
for r in F:
 d=lookup[(r['player_id'],r['model_id'])];assert all(r[k]==v for k,v in d.items() if k not in allowed)
 assert all(r[k] is None for k in ['line','selected_side','probability_at_line','confidence','EV']) and not ({'actual','outcome','played','participated'}&r.keys())
 assert dt(r['inference_UTC'])<dt(C['created_UTC'])<dt(r['native_status_observed_UTC'])<dt(r['issued_UTC'])<dt(r['expires_UTC'])<dt(r['kickoff_UTC'])
 assert r['game_id']=='2026_10_NE_DET' and r['position'] in ['RB','WR','TE'] and r['team'] in ['NE','DET'] and all(math.isfinite(r[x]) and r[x]>=0 for x in ['mean','median','p05','p95'])
 law=r['law']
 if law.get('kind')=='POISSON':assert law['mu']==r['mean'] and law['mu']>=0
 else:assert law['alpha']==.05 and law['scale']==1 and all(v>=0 and int(v)==v for v in law['values']) and all(w>=0 and math.isfinite(w) for w in law['weights']) and abs(math.fsum(law['weights'])-1)<1e-12
source=cache/'sources/profile-timing-closure-confirm-01/forward';SI=read(source/'INPUT_MANIFEST.json');SS=read(source/'SOURCE_MANIFEST.json');RO=read(source/'roster_current_season.json');assert SS==S and sha(source/'SOURCE_MANIFEST.json')==IV['SOURCE_MANIFEST_SHA256'] and sha(source/'INPUT_MANIFEST.json')==R['source_input']['SHA256']
assert sha(source/'events.json')==S['events_binding']['SHA256'] and read(source/'events.json')==N==S['events']
assert len(RO)==959 and {r['player_id'] for r in F}=={r['gsis_id'] for r in RO if r['status']=='ACT' and r['team'] in ['NE','DET'] and r['position'] in ['RB','WR','TE']}
httpdate=email.utils.parsedate_to_datetime(S['status_source']['HTTP_Date']);issue=dt(R['issued_UTC']);assert S['status_source']['HTTP_status']==200 and S['status_source']['HTTP_Age'] is None and 0<=(issue-httpdate).total_seconds()<=1800
metadata=read(cache/'SERVER_METADATA_RESPONSES.json');assert len(metadata)==2
workflow=json.loads(metadata[0]['content']);jobs=json.loads(metadata[1]['content'])['jobs'];assert workflow['id']==42921995120 and workflow['head_sha']==payload['commit'] and workflow['status']=='completed' and workflow['conclusion']=='success'
checks=[j for j in jobs if j['name']=='checks'];assert len(checks)==1 and checks[0]['conclusion']=='success' and checks[0]['status']=='completed';J=checks[0]
step=[x for x in J['steps'] if x['name']=='Verify immutable prospective captures'];assert len(step)==1 and step[0]['conclusion']=='success'
server=read(repo/'prospective/receipts/C-C05-NEDET-FIRST-01-server.json');assert server['capture_commit']==payload['commit'] and server['run_manifest_SHA256']==sha(P/'RUN.json') and server['forecast_blob_SHA256']==sha(P/'FORECASTS.json.xz') and server['qualified_prospective'] and server['fresh_GitHub_bytes_verified']
assert dt(server['server_run_created_UTC'])==dt(workflow['created_at']) and dt(server['server_run_started_UTC'])==dt(workflow['run_started_at']) and dt(server['server_check_completed_UTC'])==dt(J['completed_at'])
assert issue<dt(workflow['created_at'])<=dt(J['completed_at'])<dt(R['first_kickoff_UTC'])-datetime.timedelta(seconds=300)
old=repo/'prospective/runs/C-C04-20261110-W10-FIRST-01';assert sha(old/'RUN.json')=='a951398153017f5dcf30a4b201821ca5bcc4798f9ae58ac36184012b402cb40d' and sha(old/'FORECASTS.json.xz')=='4334c6e93d41487011e3bedb9a0a0173e38ccfcf5c568b30efbd0b73995be362'
source_bytes=sum(len(x['content'].encode()) for x in metadata);total_bytes=sum(r['bytes'] for r in receipts)
out={'id':'C05-INDEPENDENT-FRESH-GITHUB-RESTORATION-v1','status':'PASS_NEW_C05_PACKET_FRESHLY_RESTORED_AND_SERVER_QUALIFIED;SERVED_CONSUMPTION_NOT_VERIFIED','checked_UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'repository':payload['repository'],'capture_commit':payload['commit'],'permitted_route':'GitHub connector immutable base64 file reads plus GitHub workflow/jobs GET metadata','remote_file_read_operations':20,'remote_workflow_metadata_read_operations':2,'total_remote_read_operations':22,'remote_read_cap':24,'restored_decoded_file_bytes':total_bytes,'returned_base64_content_bytes':base64_bytes,'workflow_JSON_content_bytes':source_bytes,'total_returned_content_bytes':base64_bytes+source_bytes,'content_byte_cap':1048576,'transport_accounting_limit':'Counts are connector read operations and returned content bytes. Connector-internal HTTP headers/envelopes are not exposed as raw transport bytes.','fresh_files':receipts,'restored_directory':'/workspace/c05-fresh-restore','runtime_rows_readback':69,'players':23,'basic_board':959,'complete_RUN_members':13,'complete_inference_draft_members':5,'RUN_SHA256':sha(P/'RUN.json'),'FORECASTS_SHA256':sha(P/'FORECASTS.json.xz'),'zero_actual_offers_or_selections':True,'inference_reproduction_reused':prior['id'],'reviewer_new_fits':0,'reviewer_extra_NFL_inference':0,'new_upstream_source_collection':0,'server_workflow_run':workflow['id'],'server_run_created_UTC':workflow['created_at'],'server_run_started_UTC':workflow['run_started_at'],'server_checks_completed_UTC':J['completed_at'],'immutable_capture_step_completed_UTC':step[0]['completed_at'],'server_receipt_SHA256':sha(repo/'prospective/receipts/C-C05-NEDET-FIRST-01-server.json'),'original_75_local_hashes_unchanged':True,'old_C04_recovery_scope':'Prior fresh restoration reused; no old model/source refetch and no fresh fit reproduction claimed.','source_clock_scope':'Real native response Date qualifies the current pregame gate; unknown Age remains unknown. Frozen football source/feature clocks remain 18:55/19:23, not a latest-input claim.','limitations':['No private A board, quote clock, or fitted-model access is conferred by public aggregate/readback verification.','This verifies public GitHub publication and recovery, not original-site use or served research-page rendering.','The deploy job on this research-branch workflow was skipped; passing checks are not a website deployment.','This is forecast-only first-publication shadow evidence, not line selection, predictive gain, grading, or primary-product release qualification.','Full raw upstream bodies were not re-collected; retained permitted projections and clock/provenance bindings were restored.'],'CPU_seconds':time.process_time()-cpu,'peak_RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024}
assert out['total_remote_read_operations']<=24 and out['total_returned_content_bytes']<=1048576 and out['CPU_seconds']<28 and out['peak_RSS_bytes']<=768*1024**2
(V/'C05_FRESH_GITHUB_RESTORATION.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items() if k!='fresh_files'},indent=2))
