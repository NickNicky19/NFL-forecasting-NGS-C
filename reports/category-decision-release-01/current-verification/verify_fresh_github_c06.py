"""Decode and validate one bounded immutable C06 GitHub restoration; no inference."""
from pathlib import Path
import json,base64,lzma,hashlib,time,resource,datetime
from email.utils import parsedate_to_datetime
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent;CACHE=Path('/workspace/c06-fresh-restore')
def read(p):
 p=Path(p);b=p.read_bytes();return json.loads(lzma.decompress(b) if p.suffix=='.xz' else b)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dt(s):
 d=datetime.datetime.fromisoformat(s.replace('Z','+00:00'));assert d.tzinfo;return d
cpu=time.process_time();payload=read(CACHE/'FETCH_RESPONSES.json');assert payload['commit']=='97b80a91ea2b6dd42851c02553ad6bc3f09adaa1' and payload['repository']=='NickNicky19/NFL-forecasting-NGS-C';plan={x['path']:x for x in payload['plan']};assert len(plan)==len(payload['records'])==22
records=[];returned_base64=returned_structured=0
for row in payload['records']:
 p=row['path'];assert p in plan and not Path(p).is_absolute() and '..' not in Path(p).parts
 assert row['encoding']=='base64';content=''.join(row['content'].split());b=base64.b64decode(content,validate=True)
 assert len(b)==plan[p]['bytes'] and hashlib.sha256(b).hexdigest()==plan[p]['SHA256']
 assert hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==row['sha']
 dest=CACHE/p;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(b)
 returned_base64+=len(row['content'].encode());returned_structured+=len(json.dumps({k:row[k] for k in ['content','encoding','sha','display_url','display_title']},separators=(',',':'),ensure_ascii=False).encode())
 records.append(dict(path=p,bytes=len(b),SHA256=hashlib.sha256(b).hexdigest(),Git_blob_SHA1=row['sha'],exact_immutable_bytes=True,started_UTC=row.get('started_UTC'),completed_UTC=row['completed_UTC'],request_clock_state=row['request_clock_state']))
run=CACHE/'prospective/runs/C-C06-20261112-W10-CURRENT-P1-01';m=read(run/'RUN.json');d=read(run/'INFERENCE_DRAFT.json');assert d==read(run/'inference_draft/DRAFT.json')
for p,x in m['files'].items():assert sha(run/p)==x['SHA256'] and (run/p).stat().st_size==x['bytes']
for p,x in d['files'].items():assert sha(run/'inference_draft'/p)==x['SHA256'] and (run/'inference_draft'/p).stat().st_size==x['bytes']
assert m['code_commit']=='e9b56a314acea2fbe958dc4415e8693c56516970' and m['supplementary_revision_of']=='C-C04-20261110-W10-FIRST-01' and m['original_first_scoring_snapshot_unchanged'] is True
assert m['new_fits']==m['real_offers']==m['real_selections']==0 and m['primary_replacement'] is False and m['publication_state']=='AWAITING_GITHUB_SERVER_PROOF'
source=CACHE/'sources/category-decision-release-01';im=read(source/'MODEL_INPUT_MANIFEST.json');assert im==read(run/'INPUT_MANIFEST.json') and sha(source/'MODEL_INPUT_MANIFEST.json')==m['source_input']['SHA256']
for x in im['files']:
 p=CACHE/x['path'];assert p.is_file() and p.stat().st_size==x['bytes'] and sha(p)==x['SHA256']
facts=source/'current_facts_2026.csv.gz';assert facts.stat().st_size==161446 and sha(facts)=='7f73c05da0b01e76023c070c1ec43d5c372e5badc6ca8fcd8298cdf4901b7b21'
status=read(run/'NATIVE_STATUS.json');assert status==read(CACHE/m['source_status_path']);events=read(CACHE/status['event_binding']['path']);assert sha(CACHE/status['event_binding']['path'])==status['event_binding']['SHA256'] and status['target_event'] in events
p=CACHE/m['lineage']['model']['path'];model=read(p);assert sha(p)==m['lineage']['model']['SHA256'] and model['model']['type']=='L2_POOLED_POISSON' and model['model']['partial'] is False and len(model['feature_order'])==60
rows=read(run/'FORECASTS.json.xz');original=read(run/'inference_draft/FORECASTS_DRAFT.json.xz');byid={r['player_id']:r for r in original};board=read(run/'CURRENT_BOARD.json.xz');assert len(rows)==len(byid)==25 and len(board)==959
prior=read(OUT/'C06_ACTUAL_INFERENCE_INDEPENDENT.json');assert sha(run/'inference_draft/FORECASTS_DRAFT.json.xz')==prior['forecasts_SHA256'] and sha(run/'INFERENCE_DRAFT.json')==prior['draft_SHA256']
proof=read(run/'CLEAN_START_PROOF.json');assert proof['git_status']=='';issued=dt(m['issued_UTC']);clean=dt(proof['created_UTC']);native=dt(status['source']['observed_UTC']);http=parsedate_to_datetime(status['source']['HTTP_Date']);assert clean<native<issued and status['source']['HTTP_Age'] is None and 0<=(issued-http).total_seconds()<1800
for r in rows:
 assert all(r[k]==v for k,v in byid[r['player_id']].items() if k!='state')
 assert all(r[k] is None for k in ['line','selected_side','probability_at_line','confidence','EV']) and not any(k in r for k in ['actual','played','realized_starter'])
 assert dt(r['model_fit_cutoff_UTC'])<dt(r['information_cutoff_UTC'])<dt(r['inference_UTC'])<issued<dt(r['expires_UTC'])<dt(r['kickoff_UTC'])
assert sum(r['direction_candidate_role_eligible'] for r in rows)==18 and sum(r['position']=='RB' and r['RB_status']=='SEPARATE_FORECAST_ONLY_SHADOW' for r in rows)==7
for p,s in prior['old75_and69_hashes_unchanged'].items():assert sha(ROOT/p)==s
result=dict(id='C06-INDEPENDENT-FRESH-GITHUB-RESTORATION-v1',checked_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),status='PASS_FRESH_IMMUTABLE_BYTES_AND_DECODED_CONTRACTS;EXACT_HEAD_SERVER_CHECK_PENDING',repository=payload['repository'],immutable_commit=payload['commit'],read_operations=22,file_read_cap=22,restored_decoded_bytes=sum(r['bytes'] for r in records),returned_base64_content_bytes=returned_base64,returned_structured_content_bytes=returned_structured,returned_byte_cap=3145728,transport_limit='Connector-returned content bytes and read operations are measured; hidden internal HTTP headers/envelopes are not raw-transport measurements.',restored_files=records,RUN_SHA256=sha(run/'RUN.json'),FORECASTS_SHA256=sha(run/'FORECASTS.json.xz'),complete_RUN_members=len(m['files']),complete_inference_draft_members=len(d['files']),missing_before_guard_fix_source_facts_now_read_back=dict(path='sources/category-decision-release-01/current_facts_2026.csv.gz',bytes=facts.stat().st_size,SHA256=sha(facts)),safe_P1_model_readback=True,forecast_rows=25,WR_TE_direction_candidate_rows=18,RB_separate_shadow_rows=7,complete_basic_board=959,source_cutoff_UTC=m['information_cutoff_UTC'],fit_cutoff_UTC=model['fit_information_cutoff_UTC'],native_observed_UTC=status['source']['observed_UTC'],issued_UTC=m['issued_UTC'],all_original75_and69_hashes_unchanged=True,new_fits=0,new_upstream_source_collection=0,extra_NFL_inference=0,new_NFL_test_observations=0,CPU_seconds=time.process_time()-cpu,peak_RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,limitations=['This is actual remote readback, not a local path/hash-only claim.','Exact-head CI/server persistence binding is pending the parent’s successful-check metadata.','No original-site consumer activation, qualified offers, current recommendations or five-week product admission inferred.','Original immutable RUN retains its awaiting-server state; any server qualification is appended as a separate receipt.'])
assert result['returned_structured_content_bytes']<result['returned_byte_cap'] and result['CPU_seconds']<15 and result['peak_RSS_bytes']<768*1024**2
(OUT/'FRESH_GITHUB_RESTORATION.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='restored_files'}))
