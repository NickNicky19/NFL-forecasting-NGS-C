"""Independent local C04 point/lineage contract checks. No fit or network."""
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
import hashlib,json,lzma,math,re,resource,signal,time
R=Path(__file__).resolve().parents[3]
O=R/'reports/profile-timing-closure-confirm-01/verification'
start=time.process_time();signal.setitimer(signal.ITIMER_PROF,30)
def read(path):
 p=R/path;b=p.read_bytes();return json.loads(lzma.decompress(b) if p.suffix=='.xz' else b)
def sha(path):return hashlib.sha256((R/path).read_bytes()).hexdigest()
def utc(s):
 d=datetime.fromisoformat(s.replace('Z','+00:00'));assert d.tzinfo is not None;return d
pointer=read('reports/abc-championship/CURRENT_PROTOCOL.json')
core={k:pointer[k] for k in ['protocol','scorer','schema','roster']}
for descriptor in core.values():assert sha(descriptor['path'])==descriptor['SHA256']
assert core['protocol']['SHA256']=='fa19581487519a854948269bc1ce328cbbcdc734afee2464f1ff778d1ff241a1'
assert core['scorer']['SHA256']=='2ba450f91bb5fac869ce3adde031099390ec70408a91204653869032b49b2bce'
manifest=read('reports/profile-closure-next-02/timing/POINT_HANDOFF_MANIFEST.json')
assert manifest['export']['SHA256']==sha(manifest['export']['path'])=='4fd67d7915f9da3df9bec152155e809eb34d60f89d3ea751e26da9eb0a5c8abc'
payload=read(manifest['export']['path']);assert set(payload)=={'id','rows'}
rows=payload['rows'];assert len(rows)==4811
num={};baseline={};counts=Counter();roles=Counter();changed=Counter();models=0;typed=0;clockchecks=0
for year in [2025,2026]:
 nrows=read(f'artifacts/receiving-timing-c04/NUMERICAL_ROWS-{year}.json.xz')
 brows=read(f'artifacts/profile-increment-v2/NUMERICAL_ROWS-{year}.json.xz')
 for r in nrows:
  key=(r['game_id'],r['player_id']);assert key not in num;num[key]=r
 for r in brows:
  key=(r['game_id'],r['player_id']);assert key not in baseline;baseline[key]=r
 for origin in read(f'reports/profile-closure-next-02/timing/RUN-{year}.json')['origins']:
  assert utc(origin['latest_training_available_UTC'])<utc(origin['fit_cutoff_UTC']);clockchecks+=1
for source in manifest['source_predictions']:assert sha(source['path'])==source['SHA256']
featureorder=read(manifest['feature_order']['path']);assert sha(manifest['feature_order']['path'])==manifest['feature_order']['SHA256']
for key,modelref in manifest['origins'].items():
 assert sha(modelref['path'])==modelref['SHA256'];model=read(modelref['path'])
 assert modelref['fingerprint']==model['fingerprint'] and modelref['membership_SHA256']==model['membership_SHA256']
 assert modelref['feature_order_SHA256']==hashlib.sha256(json.dumps(model['feature_order'],separators=(',',':')).encode()).hexdigest()
 assert model['feature_order']==featureorder[modelref['arm']]
 if modelref['arm'] in ['F0','F1']:
  old={'F0':'R1','F1':'R2'}[modelref['arm']];assert modelref['original_C03_arm']==old and modelref['reused_original_fit'] is True
  assert modelref['path'].endswith('-'+old+'.json.xz') and 'PLUS7D' in modelref['availability_policy']
 else:assert modelref['original_C03_arm'] is None and not modelref['reused_original_fit'] and 'PLUS1D' in modelref['availability_policy']
 models+=1
assert models==64
seen=set()
rowfields={'game_id','player_id','position','team','opponent_team','season','week','query_cutoff_UTC','category','forecasts'}
forecastfields={'mean','median','mean_procedure_id','median_procedure_id','origin_ref'}
for row in rows:
 assert set(row)==rowfields and row['category']=='rec' and row['position'] in ['RB','WR','TE']
 assert re.fullmatch(r'00-\d{7}',row['player_id'])
 key=(row['game_id'],row['player_id']);assert key not in seen;seen.add(key)
 n=num[key];b=baseline[key]
 for field in ['game_id','player_id','position','team','opponent_team','season','week']:assert row[field]==n[field]==b[field]
 assert set(row['forecasts'])=={'F0','F1','F2','F3'}
 cutoff=utc(row['query_cutoff_UTC']);counts[(row['season'],row['week'])]+=1;roles[row['position']]+=1
 for arm,f in row['forecasts'].items():
  assert set(f)==forecastfields
  assert f['origin_ref']==f"{row['season']}-W{row['week']:02}-{arm}"
  assert utc(manifest['origins'][f['origin_ref']]['model_fit_cutoff_UTC'])<=cutoff
  for point in ['mean','median']:
   assert not isinstance(f[point],bool) and isinstance(f[point],(int,float)) and math.isfinite(f[point]) and f[point]>=0
   assert f[point]==n[arm][point]
   assert f[point+'_procedure_id']==f'C-RECEIVING-ALIGNED-TIMING-v1::{arm}::{point.upper()}'
   if arm in ['F0','F1']:assert f[point]==b[{'F0':'R1','F1':'R2'}[arm]][point]
   typed+=1
  assert f['median']==math.floor(f['median'])
 for old,new in [('F0','F2'),('F1','F3')]:
  for point in ['mean','median']:
   if row['forecasts'][old][point]!=row['forecasts'][new][point]:changed[(old,new,point)]+=1
assert seen==set(num)==set(baseline) and typed==38488
# Check emitted JSON floats retain their binary64 source values and aren't a saved rounded control.
assert any(f['mean']!=round(f['mean'],2) for r in rows for f in r['forecasts'].values())
previous=read('reports/profile-closure-next-02/FRESH_HISTORICAL_GITHUB_RESTORE.json')
assert previous['files'][0]['SHA256']==manifest['export']['SHA256'] and previous['files'][0]['actual_readback'] is True
runpath='prospective/runs/C-C04-20261110-W10-FIRST-01';run=read(runpath+'/RUN.json')
assert sha(runpath+'/RUN.json')=='a951398153017f5dcf30a4b201821ca5bcc4798f9ae58ac36184012b402cb40d'
for name,binding in run['files'].items():assert sha(runpath+'/'+name)==binding['SHA256'] and (R/runpath/name).stat().st_size==binding['bytes']
append=read(runpath+'/RECOVERY_COMPLETENESS_APPENDIX.json');assert append['parent_RUN_SHA256']==sha(runpath+'/RUN.json')
for binding in append['added_files']:assert sha(runpath+'/'+binding['path'])==binding['SHA256']
draft=read(runpath+'/draft/DRAFT.json')
for name,binding in draft['files'].items():assert sha(runpath+'/draft/'+name)==binding['SHA256']
forecasts=read(runpath+'/FORECASTS.json.xz');receiptpath='prospective/receipts/C-C04-20261110-W10-FIRST-01-server.json';receipt=read(receiptpath)
assert len(forecasts)==75 and len({r['player_id'] for r in forecasts})==25 and len({r['game_id'] for r in forecasts})==1
assert sha(runpath+'/FORECASTS.json.xz')==receipt['forecast_blob_SHA256']=='4334c6e93d41487011e3bedb9a0a0173e38ccfcf5c568b30efbd0b73995be362'
assert receipt['run_manifest_SHA256']==sha(runpath+'/RUN.json') and receipt['qualified_prospective'] is True
assert utc(receipt['server_check_completed_UTC'])<utc(run['first_kickoff_UTC'])
assert all(all(r.get(k) is None for k in ['line','selected_side','probability_at_line','confidence','EV']) for r in forecasts)
now=datetime.now(timezone.utc);kick=utc(run['first_kickoff_UTC'])
report={'id':'C05-INDEPENDENT-C04-POINT-CONTRACT-v1','checked_UTC':now.isoformat(),'status':'PASS_LOCAL_EXACT_POINT_AND_IMMUTABLE_PACKET_SCOPE','protocol':core,'point_artifact':manifest['export'],'source_rows':len(rows),'point_values_exact':typed,'origin_model_bindings_verified':models,'weekly_training_cutoff_metadata_checked':clockchecks,'seasons_weeks':[{'season':y,'week':w,'queries':n} for (y,w),n in sorted(counts.items())],'role_counts':dict(roles),'changed_points':[{'old':a,'new':b,'product':p,'rows':n} for (a,b,p),n in sorted(changed.items())],'F0_F1_C03_mapping':{'F0':'C03::R1::same_output','F1':'C03::R2::same_output'},'mean_median_source_precision_exact':True,'point_payload_probability_line_side_actual_participation_fields':False,'laws_or_probability_scores_supported_by_point_export':False,'past_GitHub_actual_readback_receipt_reused':'reports/profile-closure-next-02/FRESH_HISTORICAL_GITHUB_RESTORE.json','new_network_GETs':0,'new_fits':0,'new_NFL_observations':0,'old75packet':{'files_exact':True,'forecasts':75,'players':25,'games':1,'RUN_SHA256':sha(runpath+'/RUN.json'),'forecasts_SHA256':sha(runpath+'/FORECASTS.json.xz'),'receipt_SHA256':sha(receiptpath),'recorded_kickoff_UTC':run['first_kickoff_UTC'],'recorded_kickoff_still_future_at_check':kick>now,'new_native_status_checked':False,'grading':'NO_NEW_QUALIFIED_FINAL_OUTCOMES;DO_NOT_GRADE_OR_BACKDATE'},'A_private_board_access':'NOT_INSPECTED;no733privateoffersorprivateclocksreceived','join_ready':'A_can_bind_saved_exact_points_to_its_owned_qualified_offer/outcome_manifest_without_fit;F0/F1_baseline_reuse_only_if_exact_same_row/source/line/horizon/outcome/rule','source_separation':'W1-5_retained_actual_line_panel_must_be_separate_from_W6-7_internal_or_unqualified_threshold_diagnostics_and_W8_reference_rows;do_not_call_mixed7weeks_actual-offer_evidence','qualification':'Numerical16season-weeks_does_not_supply_actual-line_weeks/probability/TopPicks_history;newAjoinsmay_extend_only_exact_typed_point_rule','CPU_seconds':time.process_time()-start,'peak_RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,'budget_CPU_seconds':30,'scope_limit':'Checks_saved_point/metadata/byte_contracts;reuses_prior_raw_feature/chronology_and_fresh-fit_receipts;not_another_model_fit_or_independent_private-row_replay'}
assert report['CPU_seconds']<30 and report['peak_RSS_bytes']<805306368
(O/'C04_POINT_CONTRACT.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ['status','source_rows','point_values_exact','origin_model_bindings_verified','CPU_seconds','peak_RSS_bytes']}))
