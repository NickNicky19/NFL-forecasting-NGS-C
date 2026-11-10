"""Independent point alias and public aggregate arithmetic; no private replay."""
from pathlib import Path
from datetime import datetime,timezone
from decimal import Decimal
import csv,io,json,lzma,hashlib,math,resource,time
R=Path(__file__).resolve().parents[3];B=R/'reports/profile-timing-closure-confirm-01';start=time.process_time()
def read(p):
 p=Path(p);b=p.read_bytes();return json.loads(lzma.decompress(b) if p.suffix=='.xz' else b)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
binding=read(B/'intake/EXACT_C03_SOURCE_BINDING.json');assert binding['status']=='PASS'
c03path=R/binding['C_current_forecast_path'];assert c03path.stat().st_size==binding['A_executed_forecast_bytes']==246128
assert sha(c03path)==binding['A_executed_forecast_SHA256']==binding['C_current_forecast_SHA256']=='0a374a147bdad11bf3226265894b00b39928903f62740e0a4d2344f91eeb8497'
c03=read(c03path);c04path=R/'reports/profile-closure-next-02/timing/POINT_HANDOFF.json.xz';c04=read(c04path)
old={}
for row in c03['rows']:
 k=(row['game_id'],row['player_id'],row['procedure']);assert k not in old;old[k]=row
point_count=0;identity_count=0
for row in c04['rows']:
 for new,prior in [('F0','R1'),('F1','R2')]:
  previous=old[(row['game_id'],row['player_id'],'C-RECEIVING-PROFILE-INCREMENT-v2::'+prior)]
  assert (row['team'],row['opponent_team'],row['position'],row['season'],row['week'])==(previous['team'],previous['opponent'],previous['role'],previous['season'],previous['week'])
  for product in ['mean','median']:
   assert row['forecasts'][new][product]==previous[product];point_count+=1
  identity_count+=1
assert point_count==19244 and identity_count==9622
execution=read(B/'intake/A_C03_EXECUTION_RECEIPT.json.xz')['document'];public_manifest=read(B/'intake/A_C03_MANIFEST.json.xz')['document']
assert execution['private_source']['sha256']==sha(c03path)
assert execution['score_sha256']==public_manifest['source_score_sha256']=='f50f710c41de70e6ff4998f701e259ef532a5cf3c99d3ac7f3be9bfb6e1035e8'
wrapper=read(B/'intake/A_C03_CUMULATIVE.json.xz');text=wrapper['document'];assert hashlib.sha256(text.encode()).hexdigest()==wrapper['source']['decoded_SHA256']
assert wrapper['source']['decoded_SHA256']==next(f['sha256'] for f in public_manifest['files'] if f['path']=='CUMULATIVE_ALL_PROCEDURES_001.csv')
rows=list(csv.DictReader(io.StringIO(text)));assert len(rows)==132
for row in rows:
 for s in ['over','under','combined']:
  n=int(row[s+'_decided']);w=int(row[s+'_wins'] or 0);l=int(row[s+'_losses'] or 0)
  assert w+l==n
  if n:assert abs(Decimal(row[s+'_rate'])-Decimal(w)/Decimal(n))<Decimal('1e-14')
  else:assert row[s+'_rate']==''
 for label in ['wins','losses','decided','selected']:
  assert int(row['combined_'+label] or 0)==int(row['over_'+label] or 0)+int(row['under_'+label] or 0)
 assert int(row['eligible'])==int(row['selected'])+int(row['unavailable'])+int(row['abstained'])
 assert int(row['selected'])==sum(int(row[k]) for k in ['combined_decided','unknown_participation','missing_actual','pending','DNP','push'])
 assert json.loads(row['actual_retained_threshold_weeks'])==([1,2,3,4,5] if row['source_panel'] in ['ALL','ANNUAL_NAMED_NJ'] else [])
annual={(r['view'],r['procedure']):r for r in rows if r['source_panel']=='ANNUAL_NAMED_NJ'}
products=[]
for arm,oldarm in [('F0','R1'),('F1','R2')]:
 for point in ['MEAN','MEDIAN']:
  source_id='C-RECEIVING-PROFILE-INCREMENT-v2::'+oldarm+'::'+point
  full=annual['FULL_A733',source_id];fixed=annual['FIXED_C667',source_id]
  assert (full['eligible'],full['selected'],full['unavailable'],full['unknown_participation'],full['combined_decided'],full['games'])==('469','421','48','9','412','53')
  for k in ['over_wins','over_losses','over_decided','under_wins','under_losses','under_decided','combined_wins','combined_losses','combined_decided','numerical_scored','numerical_MAE','numerical_MSE','numerical_bias']:assert full[k]==fixed[k]
  assert json.loads(full['all_graded_weeks'])==[1,2,3,4,5] and json.loads(full['actual_retained_threshold_weeks'])==[1,2,3,4,5]
  strong=annual['FIXED_C667','C::PLAYER-CONTEXT-MATCHUP-01::v1.1::P1::'+point.lower()]
  def partition(prefix):
   n=int(full[prefix+'_decided']);return {'wins':int(full[prefix+'_wins']),'losses':int(full[prefix+'_losses']),'decided':n,'rate':int(full[prefix+'_wins'])/n}
  products.append({'procedure_id':'C-RECEIVING-ALIGNED-TIMING-v1::'+arm+'::'+point,'source_C03_procedure_id':source_id,'rule':'Unrounded saved point > retained exact line OVER; < UNDER; equality abstains; inherited A statistical outcome contract','source_panel':full['source_panel'],'requested_period':full['requested_period'],'actual_retained_threshold_weeks':json.loads(full['actual_retained_threshold_weeks']),'role':'WR_TE','eligible':469,'selected':421,'unavailable_forecasts':48,'selected_unknown_participation':9,'decided':412,'games':53,'OVER':partition('over'),'UNDER':partition('under'),'COMBINED':partition('combined'),'same_offered_player_numerical_owner_reported':{k:float(full['numerical_'+k]) for k in ['MAE','MSE','bias']},'strong_compatible_C_control_id':strong['procedure'],'strong_control_wins':int(strong['combined_wins']),'strong_control_decided':412,'candidate_minus_control_wins':int(full['combined_wins'])-int(strong['combined_wins']),'candidate_minus_control_percentage_points':100*(int(full['combined_wins'])-int(strong['combined_wins']))/412,'probabilities':'N/A_SAVED_POINTS_ONLY','evidence_tier':full['evidence'],'source_views_not_additive':['FULL_A733','FIXED_C667']})
for p,w in zip(products,[236,232,225,235]):assert p['COMBINED']['wins']==w
old_control_median=annual['FULL_A733','C::PLAYER-CONTEXT-MATCHUP-01::v1.1::P1::median'];defense=annual['FULL_A733','C-RECEIVING-PROFILE-INCREMENT-v2::R3::MEDIAN'];assert int(old_control_median['combined_wins'])==238 and int(defense['combined_wins'])==237
report={'id':'C05-C04-F0-F1-EXACT-BASELINE-ALIAS-REUSE-v1','status':'PASS_EXACT_POINTS_PLUS_PUBLIC_AGGREGATE_ARITHMETIC;PRIVATE_ROW_PARITY_UNKNOWN','checked_UTC':datetime.now(timezone.utc).isoformat(),'A_ref':binding['A_immutable_ref'],'A_C03_source_bytes_exact':{'path':binding['C_current_forecast_path'],'bytes':246128,'SHA256':sha(c03path)},'C04_point_export_SHA256':sha(c04path),'point_values_independently_compared':point_count,'identity_arm_records_compared':identity_count,'public_C03_summary_rows_arithmetic_checked':len(rows),'A_execution_score_to_public_CSV_hash_chain_verified':True,'baseline_products':products,'within_method_profile_increment_point_only':{'MEAN':{'F1_minus_F0_wins':-11,'percentage_points':-11/412*100},'MEDIAN':{'F1_minus_F0_wins':3,'percentage_points':3/412*100}},'C03_defense_median_control':{'procedure_id':defense['procedure'],'wins':237,'decided':412,'R3_minus_R2_wins':2,'strong_old_C_P1_median_wins':238},'view_label_caution':'FULL_A733 and FIXED_C667 are retained panel names; annual actual counts469eligible/412decided. Source/fixed/full views overlap; do not add.','new_C04_F2_F3_joins':'NOT_EXECUTED_BY_THIS_ALIAS_VIEW;newtimingproductsstillrequireAownedjoin','what_was_executed':'Read-only exact-output alias verification plus independent integer/Decimal aggregate calculation; no private scorer/re-inference/fit','new_tests_weeks_or_NFL_observations':0,'same_original_C03_test_reused':True,'probability_confidence_TopPicks_or_EV_qualification':'NOT_SUPPLIED_NOT_TRANSFERRED','five_week_scope':'Owner reports actual retained thresholds/scored W1-5 for exact point rules, at timing-unverified reconstruction tier. Per-week/private opportunity membership not independently reconstructed. No seven actual-offer-week claim and no original-issuance upgrade.','W6_W7':'SITE_RECORDED_DK_JURISDICTION_UNKNOWN diagnostic only; excludes them from annual actual-line fiveweek alias record','paired_uncertainty':'No new interval computed. Point alias shares source paired evidence only when exact masks/rules match; private disagreements/clock evidence not independently inspected.','verification_limits':['Public412decidedmaskidentityisownerreported;arithmeticandpointidentityverifiedindependently','Privateplayer/event/quote/timing/outcome/participationrowsnotreceivedorreplayed','NumericalMAE/MSE/biasretainedasownerreported;notrecomputedfromprivateactuals','NoC04F2/F3pointjoinorlaw/rankingqualificationiscreatedbyrenamingbaselines'],'CPU_seconds':time.process_time()-start,'peak_RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,'new_fits':0,'new_inference':0,'new_GETs':0}
assert report['CPU_seconds']<30 and report['peak_RSS_bytes']<805306368
(B/'verification/BASELINE_ALIAS_REUSE.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'status':report['status'],'point_values':point_count,'summary_rows':len(rows),'CPU_seconds':report['CPU_seconds']}))
