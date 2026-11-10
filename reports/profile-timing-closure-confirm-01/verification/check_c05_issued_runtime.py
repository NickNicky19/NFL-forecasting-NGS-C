import pathlib,json,lzma,hashlib,datetime,email.utils,math,time,resource
cpu=time.process_time();root=pathlib.Path('/workspace/ngs-c');P=root/'prospective/runs/C-C05-NEDET-FIRST-01';V=root/'reports/profile-timing-closure-confirm-01/verification'
def load(p):return json.loads(lzma.decompress(p.read_bytes()) if p.suffix=='.xz' else p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dt(x):
 d=datetime.datetime.fromisoformat(x);assert d.tzinfo;return d
R=load(P/'RUN.json');D=load(P/'INFERENCE_DRAFT.json');F=load(P/'FORECASTS.json.xz');DF=load(P/'inference_draft/FORECASTS_DRAFT.json.xz');N=load(P/'NATIVE_STATUS.json');S=load(P/'STATUS_SOURCE_MANIFEST.json');C=load(P/'CLEAN_START_PROOF.json');IV=load(P/'INDEPENDENT_STATUS_VERIFICATION.json');A=load(pathlib.Path('/workspace/c05-actual-inference-independent.json'))
assert R['schema']=='C05-FROZEN-FOOTBALL-CURRENT-QUERY-RUN-v1' and R['code_commit']==D['code_commit']==A['code_commit']=='0e1768af6134a66fc71d6eaec3f92ef5a10693bb'
assert R['publication_state']=='AWAITING_GITHUB_SERVER_PROOF' and R['real_offers']==R['real_selections']==0 and not R['primary_replacement'] and not R['original_website_incumbent']
for rel,b in R['files'].items():assert sha(P/rel)==b['SHA256'] and (P/rel).stat().st_size==b['bytes']
assert sha(P/'INFERENCE_DRAFT.json')==sha(P/'inference_draft/DRAFT.json')==A['draft_SHA256']
assert sha(P/'inference_draft/FORECASTS_DRAFT.json.xz')==A['forecasts_SHA256']
assert set(p.name for p in (P/'inference_draft').iterdir())==set(D['files'])|{'DRAFT.json'}
for rel,b in D['files'].items():assert sha(P/'inference_draft'/rel)==b['SHA256'] and (P/'inference_draft'/rel).stat().st_size==b['bytes']
assert R['registration_SHA256']==C['registration_SHA256']==D['registration_SHA256'] and C['git_status']==''
for rel,h in R['code_SHA256'].items():assert sha(root/rel)==h==C['code_SHA256'][rel]==D['code_SHA256'][rel]
assert R['information_policy']=='FROZEN_FOOTBALL_SNAPSHOT_FIRST_PUBLICATION_SHADOW' and R['information_cutoff_UTC']==D['information_cutoff_UTC']=='2026-11-10T19:23:09.469852+00:00'
assert R['eligibility_input_cutoff_UTC']==D['eligibility_input_cutoff_UTC']=='2026-11-10T22:51:53.312826+00:00'
assert R['lineage']==D['lineage'];assert R['lineage']['football_source_cutoff_UTC']=='2026-11-10T18:55:28.982066+00:00'
sourceactual=root/R['source_status_path'];assert sha(sourceactual)==IV['SOURCE_MANIFEST_SHA256'] and load(sourceactual)==S
source_input=root/R['source_input']['path'];assert sha(source_input)==R['source_input']['SHA256']
B=S['events_binding'];assert sha(root/B['path'])==B['SHA256'] and (root/B['path']).stat().st_size==B['bytes'];assert load(root/B['path'])==N==S['events']
assert len(N)==1;n=N[0];assert n['game_id']=='2026_10_NE_DET' and str(n['espn_event_id'])==str(n['competition_id'])=='401873053'
assert n['home_team']=='DET' and n['away_team']=='NE' and n['week']==10 and n['season']==2026 and n['season_type']==2
assert n['competition_state_agreement'] and n['state']=='pre' and n['status_name']=='STATUS_SCHEDULED' and not n['completed']
assert n['kickoff']==dt(n['kickoff_UTC']).timestamp()==dt('2026-11-15T14:30:00+00:00').timestamp()
issue=dt(R['issued_UTC']);observed=dt(n['observed_UTC']);clean=dt(C['created_UTC']);assert dt(D['created_UTC'])<clean<observed<issue<dt(n['kickoff_UTC'])-datetime.timedelta(seconds=300)
assert (issue-clean).total_seconds()<1800 and issue==dt(R['created_UTC'])
st=S['status_source'];assert st['HTTP_status']==200 and st['state']=='RECEIVED' and st['method']=='GET'
assert st['observed_UTC']==n['observed_UTC']==B['observed_UTC'] and st['SHA256']==B['status_response_raw_SHA256'] and st['id']==B['source_id']==n['source_id']
assert st['response_final_host']=='site.api.espn.com' and S['status_execution_code_SHA256']==sha(root/S['status_execution_code_path'])
age=st['HTTP_Age'];assert age is None # Preserve unknown Age; do not coerce it to zero.
httpdate=email.utils.parsedate_to_datetime(st['HTTP_Date']);date_age_at_observation=(observed-httpdate).total_seconds();date_age_at_issue=(issue-httpdate).total_seconds();assert -5<=date_age_at_issue<=1800
assert math.isclose(date_age_at_observation,S['status_HTTP_response_clock']['HTTP_Date_age_seconds_at_observation'],abs_tol=1e-6)
assert math.isclose(date_age_at_issue,IV['HTTP_Date_age_seconds_at_issuance'],abs_tol=1e-6)
assert IV['HTTP_Age_seconds'] is None and IV['effective_HTTP_Age_seconds_at_issuance'] is None
roster=[x for x in S['sources'] if x['id']=='C05_CURRENT_SEASON_ROSTER'][0];published=email.utils.parsedate_to_datetime(roster['HTTP_Last_Modified']);assert 0<=(issue-published).total_seconds()<36*3600
assert len(F)==len(DF)==69 and len({(r['model_id'],r['player_id']) for r in F})==69
lookup={(r['model_id'],r['player_id']):r for r in DF};allowed={'state','run_id','forecast_id','issued_UTC','generated_UTC','native_status_observed_UTC','event_version','event_state','native_event_source','expires_UTC','expiry_action','lead_seconds_at_issuance'}
forecast_ids=set();expiries=[]
for r in F:
 d=lookup[(r['model_id'],r['player_id'])];assert all(r[k]==v for k,v in d.items() if k not in allowed)
 assert set(r)-set(d)<=allowed and r['run_id']==R['run_id'] and r['forecast_id'] not in forecast_ids;forecast_ids.add(r['forecast_id'])
 assert r['state']=='ISSUED_FROZEN_FOOTBALL_SHADOW_AWAITING_GITHUB_PROOF' and r['issued_UTC']==R['issued_UTC']==r['generated_UTC']
 assert r['native_status_observed_UTC']==n['observed_UTC'] and r['event_state']=='pre' and r['native_event_source']==st['id']
 assert dt(r['inference_UTC'])<clean<issue<dt(r['expires_UTC'])<=dt(n['kickoff_UTC'])-datetime.timedelta(seconds=300)
 assert dt(r['expires_UTC'])==min(published+datetime.timedelta(hours=36),dt(n['kickoff_UTC'])-datetime.timedelta(seconds=300))
 assert math.isclose(r['lead_seconds_at_issuance'],n['kickoff']-issue.timestamp(),abs_tol=1e-6)
 assert all(r[k] is None for k in ['line','selected_side','probability_at_line','confidence','EV']);expiries.append(r['expires_UTC'])
assert len({r['player_id'] for r in F})==23 and {r['model_id'] for r in F}=={x['model_id'] for x in R['lineage']['models']}
for ref in R['lineage']['models']:assert sha(root/ref['path'])==ref['SHA256']
old=root/'prospective/runs/C-C04-20261110-W10-FIRST-01';assert sha(old/'RUN.json')=='a951398153017f5dcf30a4b201821ca5bcc4798f9ae58ac36184012b402cb40d' and sha(old/'FORECASTS.json.xz')=='4334c6e93d41487011e3bedb9a0a0173e38ccfcf5c568b30efbd0b73995be362'
for rel,b in load(old/'RUN.json')['files'].items():assert sha(old/rel)==b['SHA256']
assert len(load(old/'FORECASTS.json.xz'))==75
out={'id':'C05-INDEPENDENT-ISSUED-RUNTIME-v1','status':'PASS_LOCAL_ISSUED_PACKET_AND_COMPLETE_RECOVERY;PUBLICATION_PENDING','checked_UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'run_id':R['run_id'],'RUN_SHA256':sha(P/'RUN.json'),'FORECASTS_SHA256':sha(P/'FORECASTS.json.xz'),'run_bound_files':len(R['files']),'recoverable_inference_draft_members':len(D['files'])+1,'issued_forecasts':69,'unique_players':23,'current_basic_records':959,'new_fits':0,'reviewer_new_GETs':0,'actual_inference_receipt':'C05_ACTUAL_INFERENCE_INDEPENDENT.json','actual_inference_receipt_SHA256':sha(pathlib.Path('/workspace/c05-actual-inference-independent.json')),'code_commit':R['code_commit'],'football_source_cutoff_UTC':R['lineage']['football_source_cutoff_UTC'],'feature_cutoff_UTC':R['information_cutoff_UTC'],'current_eligibility_cutoff_UTC':R['eligibility_input_cutoff_UTC'],'clean_start_UTC':C['created_UTC'],'native_GET_observed_UTC':n['observed_UTC'],'HTTP_Date_age_seconds_at_observation':date_age_at_observation,'HTTP_Date_age_seconds_at_issuance':date_age_at_issue,'HTTP_Age_seconds':None,'HTTP_Age_state':'UNKNOWN_PRESERVED; independent Date age qualifies this response','issued_UTC':R['issued_UTC'],'expiry_UTC':sorted(set(expiries)),'local_RUN_file_mtime_UTC':datetime.datetime.fromtimestamp((P/'RUN.json').stat().st_mtime,datetime.timezone.utc).isoformat(),'zero_real_offers_or_selections':True,'no_primary_replacement':True,'original_75_unchanged':True,'verdict_scope':['All RUN member bytes/hashes and all five inference-draft members independently read back.','Issued rows preserve independently reconstructed model outputs, features, inference clocks, and frozen-football claims.','Latest native response bound by source projection, code, raw response hash, identity, pregame state, Date clock, and clean-start gate.','Roster publisher freshness and expiry checked separately; current roster is not a starter, health, or gameday guarantee.'],'limitations':['Raw provider response body is represented by the retained permitted event projection and response hash; the reviewer did not perform a new GET or independently reinterpret the full raw body.','No GitHub server-time publication receipt or served consumer proof exists in this review yet.','Forecast-only shadow evidence: no actual offers, selections, grades, or five-week release qualification are created.'],'CPU_seconds':time.process_time()-cpu,'peak_RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024}
assert out['CPU_seconds']<28 and out['peak_RSS_bytes']<768*1024**2
V.mkdir(exist_ok=True);(V/'C05_ISSUED_RUNTIME_INDEPENDENT.json').write_text(json.dumps(out,indent=2)+'\n');(V/'C05_ACTUAL_INFERENCE_INDEPENDENT.json').write_bytes(pathlib.Path('/workspace/c05-actual-inference-independent.json').read_bytes());print(json.dumps(out,indent=2))
