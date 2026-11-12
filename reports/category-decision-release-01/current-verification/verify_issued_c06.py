"""Independent hash/clock/recovery check of issued C06 bytes; no inference."""
import json,lzma,hashlib,time,resource
from pathlib import Path
from datetime import datetime,timezone
from email.utils import parsedate_to_datetime
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent;RUN=ROOT/'prospective/runs/C-C06-20261112-W10-CURRENT-P1-01'
def read(p):
 p=Path(p);b=p.read_bytes();return json.loads(lzma.decompress(b) if p.suffix=='.xz' else b)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def instant(s):
 d=datetime.fromisoformat(s.replace('Z','+00:00'));assert d.tzinfo;return d
cpu=time.process_time();m=read(RUN/'RUN.json');assert m['schema']=='C06-CURRENT-SOURCE-P1-QUERY-RUN-v1' and m['code_commit']=='e9b56a314acea2fbe958dc4415e8693c56516970'
for name,b in m['files'].items():assert (RUN/name).stat().st_size==b['bytes'] and sha(RUN/name)==b['SHA256']
d=read(RUN/'INFERENCE_DRAFT.json');assert d==read(RUN/'inference_draft/DRAFT.json')
for name,b in d['files'].items():assert (RUN/'inference_draft'/name).stat().st_size==b['bytes'] and sha(RUN/'inference_draft'/name)==b['SHA256']
check=read(OUT/'C06_ACTUAL_INFERENCE_INDEPENDENT.json');assert check['status'].startswith('PASS_') and sha(RUN/'inference_draft/FORECASTS_DRAFT.json.xz')==check['forecasts_SHA256'] and sha(RUN/'inference_draft/DRAFT.json')==check['draft_SHA256']
proof=read(RUN/'CLEAN_START_PROOF.json');assert proof['git_status']==''
for k in ['code_commit','code_SHA256','registration_SHA256']:assert proof[k]==m[k]==d[k]
issued=instant(m['issued_UTC']);clean=instant(proof['created_UTC']);assert 0<=(issued-clean).total_seconds()<=1800
status=read(RUN/'NATIVE_STATUS.json');assert status==read(ROOT/m['source_status_path']) and status['source_input']==m['source_input'];eb=status['event_binding'];p=ROOT/eb['path'];assert p.stat().st_size==eb['bytes'] and sha(p)==eb['SHA256'];events=read(p);e=status['target_event'];assert e in events
s=status['source'];observed=instant(s['observed_UTC']);httpdate=parsedate_to_datetime(s['HTTP_Date']);assert httpdate.tzinfo and s['HTTP_Age'] is None and status['response_clock']['HTTP_Age_seconds'] is None
assert s['state']=='RECEIVED' and s['HTTP_status']==200 and clean<=observed<issued
assert -5<=(observed-httpdate).total_seconds()<=1800 and -5<=(issued-httpdate).total_seconds()<=1800 and 0<=(issued-observed).total_seconds()<=1800
assert e['espn_event_id']==e['competition_id']=='401873052' and e['competition_state_agreement'] is True
assert e['state']=='pre' and e['status_name']=='STATUS_SCHEDULED' and e['completed'] is False and e['season']==2026 and e['week']==10 and e['season_type']==2 and (e['home_team'],e['away_team'])==('NYG','WAS')
assert e['source_id']==s['id'] and e['observed_UTC']==s['observed_UTC']
kick=instant(e['kickoff_UTC']);assert kick.isoformat()=='2026-11-13T01:15:00+00:00' and (kick-issued).total_seconds()>300
input_m=read(RUN/'INPUT_MANIFEST.json');assert input_m==read(ROOT/m['source_input']['path']) and sha(ROOT/m['source_input']['path'])==m['source_input']['SHA256']
assert (RUN/'CURRENT_BOARD.json.xz').read_bytes()==(RUN/'inference_draft/CURRENT_BOARD.json.xz').read_bytes();board=read(RUN/'CURRENT_BOARD.json.xz');assert len(board)==959
rows=read(RUN/'FORECASTS.json.xz');draftrows=read(RUN/'inference_draft/FORECASTS_DRAFT.json.xz');byid={r['player_id']:r for r in draftrows};assert len(rows)==len(byid)==25 and len({r['forecast_id'] for r in rows})==25
for r in rows:
 q=byid[r['player_id']];assert all(r[k]==v for k,v in q.items() if k!='state')
 assert r['run_id']==m['run_id'] and r['issued_UTC']==m['issued_UTC'] and r['native_status_observed_UTC']==s['observed_UTC']
 assert instant(r['model_fit_cutoff_UTC'])<instant(r['information_cutoff_UTC'])<instant(r['inference_UTC'])<issued<instant(r['expires_UTC'])<kick
 assert instant(r['expires_UTC'])<=observed+__import__('datetime').timedelta(seconds=1800)
 assert all(r[k] is None for k in ['line','selected_side','probability_at_line','confidence','EV'])
 assert not any(k in r for k in ['actual','played','realized_starter'])
assert sum(r['direction_candidate_role_eligible'] for r in rows)==18 and sum(r['position']=='RB' and r['RB_status']=='SEPARATE_FORECAST_ONLY_SHADOW' for r in rows)==7
assert m['new_fits']==m['real_offers']==m['real_selections']==0 and m['primary_replacement'] is False and m['original_website_incumbent'] is False
assert m['supplementary_revision_of']=='C-C04-20261110-W10-FIRST-01' and m['original_first_scoring_snapshot_unchanged'] is True
for original_path,original_digest in check['old75_and69_hashes_unchanged'].items():assert sha(ROOT/original_path)==original_digest
r=dict(id='C06-INDEPENDENT-ISSUED-RUNTIME-v1',checked_UTC=datetime.now(timezone.utc).isoformat(),status='PASS_LOCAL_ISSUED_RECOVERY_CLOCKS_ROLES_AND_ORIGINAL_IMMUTABILITY;SERVER_PUBLICATION_PENDING',run_id=m['run_id'],RUN_SHA256=sha(RUN/'RUN.json'),FORECASTS_SHA256=sha(RUN/'FORECASTS.json.xz'),bound_run_members=len(m['files']),fully_restored_inference_draft_members=len(d['files']),forecast_rows=25,current_query_players=25,current_basic_board=959,WR_TE_direction_candidate_rows=18,RB_shadow_only_rows=7,code_commit=m['code_commit'],clean_start_UTC=proof['created_UTC'],native_observed_UTC=status['source']['observed_UTC'],native_HTTP_Date=s['HTTP_Date'],native_HTTP_Age_seconds=None,native_Date_age_at_observation_seconds=(observed-httpdate).total_seconds(),native_Date_age_at_issue_seconds=(issued-httpdate).total_seconds(),actual_issued_UTC=m['issued_UTC'],kickoff_UTC=e['kickoff_UTC'],lead_seconds_at_issuance=(kick-issued).total_seconds(),forecast_expiry_UTC=min(x['expires_UTC'] for x in rows),original75_and69_unchanged=True,real_offers=0,real_selections=0,new_fits=0,new_GETs=0,new_inference_rows=0,new_NFL_observations=0,CPU_seconds=time.process_time()-cpu,peak_RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,limitations=['No new coefficient inference repeated; actual25 separate computation is bound by its receipt.','GitHub server persistence, remote restoration and consumer/served admission remain to verify.','Current roster is not starter, health or participation proof; all forecasts remain appearance-conditioned shadow.','Historical quote/mask/fit parity and five-week whole-product qualification limits are unchanged.'])
(OUT/'C06_ISSUED_RUNTIME_INDEPENDENT.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
