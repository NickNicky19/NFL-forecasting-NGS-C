"""Version the existing common coverage table from admitted saved aggregates.
No model, forecast, outcome grader, selector, network call or source acquisition.
Original records are preserved; newly received views are not new NFL games.
"""
from __future__ import annotations
import csv,gzip,hashlib,io,json,lzma
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'reports/interception-history-closure-01/ledger'
OLD=ROOT/'reports/category-decision-release-01/W1_W8_COVERAGE.csv.gz'
TARGET=ROOT/'reports/category-decision-release-01/W1_W9_AND_HISTORY_COVERAGE.csv.gz'
def j(p):return json.loads(p.read_text())
def ident(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def run():
 old=list(csv.DictReader(io.StringIO(gzip.decompress(OLD.read_bytes()).decode())))
 fields=list(old[0])+['coverage_entry_id','row_kind','grading_version','issuance_state','additional_metrics','over_decided','over_rate','under_decided','under_rate','combined_wins','combined_losses','combined_decided','combined_rate']
 rows=[dict(x,row_kind='PRESERVED_PROCEDURE_WEEK',grading_version='SEE_ORIGINAL_BINDING',issuance_state='SEE_ORIGINAL_EVIDENCE_TIER',additional_metrics='')for x in old]
 def add(x):
  x={'row_id':ident(x),**x};rows.append(x)
 # Historical actual-line source cells are not tests or invented procedure results.
 historical=list(csv.DictReader(io.StringIO((ROOT/'reports/abc-championship/SOURCE_COVERAGE.csv').read_text())))
 for s in historical:
  if int(s['season']) not in [2022,2023,2024,2025]:continue
  add(dict(owner=s['owner'],category=s['category'],procedure_id='SOURCE_COVERAGE_ONLY_NO_EVALUATED_PROCEDURE',product='ACTUAL_LINE_SOURCE_COVERAGE',role_scope='EXACT_CATEGORY_SCOPE_REQUIRED',source_panel=s['source'],season=s['season'],week=s['week'],status=s['state'],evidence_tier='UNAVAILABLE_ADMITTED_ACTUAL_LINE_EVIDENCE',source_artifacts='reports/abc-championship/SOURCE_COVERAGE.csv',verification_limit='No admitted actual-offer result in this source cell; numerical/history fits elsewhere are not invalidated.',required_next_owner_action=s['next'],row_kind='HISTORICAL_SOURCE_CELL_NOT_TEST',grading_version='N/A',issuance_state='UNAVAILABLE'))
 cats=['pass_yd','pass_td','pass_cmp','pass_att','pass_int','rush_yd','rush_att','rec','rec_yd','rush_rec_yd','anytime_td','nick-chart-ppr-v1']
 for cat in cats:
  add(dict(owner='C_COORDINATOR',category=cat,procedure_id='SOURCE_COVERAGE_ONLY_NO_EVALUATED_PROCEDURE',product='ACTUAL_LINE_SOURCE_COVERAGE',season=2026,week=9,status='NO_NEW_ADMITTED_W9_ACTUAL_OFFER_RESULT;SOURCE_SPECIFIC_EXISTING_PANELS_REMAIN',evidence_tier='UNAVAILABLE_ADMITTED_ACTUAL_LINE_EVIDENCE',source_artifacts='reports/interception-history-closure-01/A-intake/A_INTAKE_RECEIPT.json;reports/interception-history-closure-01/B-intake/ADMISSION.json',verification_limit='This is a bounded current intake gap, not proof no private/later result exists. C W9 numerical rows are separate.',required_next_owner_action='A/B exactnewhistorical packages and originalwebsite/B exactINTsource-grade receipt through existing routes',row_kind='W9_ACTUAL_LINE_SOURCE_CELL_NOT_TEST',grading_version='N/A',issuance_state='UNAVAILABLE'))
 # B's genuinely received aggregate recipe: own sides, exact named policy, unchanged source panel.
 tables=json.loads(lzma.decompress((ROOT/'reports/interception-history-closure-01/B-intake/COMMON_CONTROL_TABLE.json.xz').read_bytes()))
 for t in tables:
  sides={x['side'].lower():x['metrics']for x in t['sides']};o,u,c=sides['over'],sides['under'],sides['combined']
  assert c['WIN']==o['WIN']+u['WIN'] and c['LOSS']==o['LOSS']+u['LOSS']
  add(dict(owner='B',category='pass_cmp',procedure_id=t['procedure_id'],product='ACTUAL_LINE_DIRECTION:'+t['policy'],history='B_QB_DEPTH_ROLE_FROZEN_SEVEN_DAY_EARLIER_ONLY;SEE_BOUND_REPORT',role_scope='QB',source_panel='B_QB_DEPTH_NATIVE_W5_W8_PUBLIC_AGGREGATES',book='',evidence_tier='OBSERVED_ACTUAL_LINES_TIMING_UNVERIFIED;CURRENT_VINTAGE_ASOF_RECONSTRUCTION;EXPOSED_DEVELOPMENT',season=2026,week=t['window'],status='RECEIVED_PUBLIC_AGGREGATE_ARITHMETIC_ONLY;NOT_NEW_NFL_TEST',eligible=c['selection_pool_count'],available=c['selection_pool_count']-c.get('technical_unavailable',0),selected=c['denominators']['outer_rows'],scored=c['denominators']['decided'],unknown=c['denominators']['unresolved'],abstained=c.get('admitted_rule_abstentions',''),fallback=c.get('fallback_issued',''),games=t['games'],over_wins=o['WIN'],over_losses=o['LOSS'],under_wins=u['WIN'],under_losses=u['LOSS'],source_artifacts='reports/interception-history-closure-01/B-intake/COMMON_CONTROL_TABLE.json.xz',verification_limit='C checks publictriads/hashes, not privateidentity/timing/fit/commonmaskparity. Do not concatenate overlapping A/Bweeks.',source_evidence_class='TIMING_UNVERIFIED_ACTUAL_LINE_AGGREGATE',new_procedure_coverage_not_new_games=True,required_next_owner_action='Directionrecipeclosednogain; numericalshadowrequires ownqualifiedcurrentdelivery andlaterconfirmation.',row_kind='RECEIVED_PROCEDURE_WEEK_OR_CUMULATIVE',grading_version='B_BOUND_SCORING_PROTOCOL;NO_C_REGRADE',issuance_state='RECONSTRUCTED_DIAGNOSTIC_NOT_ORIGINAL_ISSUE',additional_metrics=json.dumps({'law_probability':t.get('probability'),'status_counts':c.get('status_counts'),'uncertainty':c.get('game_uncertainty'),'bookmaker_settlement':c.get('bookmaker_settlement_status_counts'),'new_release_roster_member':False},sort_keys=True)))
 # Exact original C run/model/output views; lines are absent, so every O/U remains N/A.
 numerics=j(ROOT/'reports/interception-history-closure-01/C-W9-grading/CATEGORY_NUMERICAL.json')['exact_run_rows']
 for x in numerics:
  assert len(x['exact_method_ids'])==1
  outputs=['EVENT_PROBABILITY']if x['category']=='anytime_td'else['EXPECTED_MEAN','LOWER_MEDIAN']
  for output in outputs:
   add(dict(owner='C',category=x['category'],procedure_id=x['exact_method_ids'][0],product='ORIGINAL_FORECAST_ONLY:'+output,history='Frozenoriginalrun/model/origin; exactP2v4artifactbindings retained; no current refit.',role_scope='|'.join(x['role_scope']),source_panel=x['run_id'],evidence_tier='ORIGINAL_GITHUB_PERSISTED_PREGAME_FORECAST_ONLY;NO_QUALIFIED_ACTUAL_OFFERS',season=2026,week=9,status='REUSED_EXISTING_APPEND_ONLY_GRADE;NO_NEW_GRADING_OR_TEST',eligible=x['eligible_forecasts'],available=x['eligible_forecasts'],selected='',scored=x['graded_played'],unknown=x['unknown'],fallback=x['fallback_outputs'],games=x['games'],player_games=x['player_games'],source_artifacts='reports/interception-history-closure-01/C-W9-grading/REUSE_RECEIPT.json;reports/interception-history-closure-01/C-W9-grading/CATEGORY_NUMERICAL.json',verification_limit='Mean/median/event views do not add NFLobservations or offered-line weeks. CMP/ATT papercoherence and exactchart tail restrictions retained.',source_evidence_class='NUMERICAL_OR_EVENT_ONLY_NO_MATCHING_OFFER',new_procedure_coverage_not_new_games=True,required_next_owner_action='Futuregrading continues through existingowners; no O/U/primarypromotion from forecast-only views.',row_kind='EXISTING_ORIGINAL_FORECAST_GRADE_VIEW',grading_version='SEE_RUN_BOUND_APPEND_ONLY_GRADE_VERSION',issuance_state='ORIGINAL_PREGAME_SOURCE_AND_SERVER_RECEIPT_VERIFIED',additional_metrics=json.dumps({'typed_output':output,'retained_category_metrics':x},sort_keys=True)))
 for x in rows:
  def side(s):
   a,b=x.get(s+'_wins',''),x.get(s+'_losses','')
   if a in ('',None)or b in ('',None):return None
   w,l=int(a),int(b);assert w>=0 and l>=0;return w,l
  so,su=side('over'),side('under')
  for s,v in [('over',so),('under',su)]:
   x[s+'_decided']=sum(v)if v else '';x[s+'_rate']=v[0]/sum(v)if v and sum(v)else ''
  if so and su:
   w,l=so[0]+su[0],so[1]+su[1];x.update(combined_wins=w,combined_losses=l,combined_decided=w+l,combined_rate=w/(w+l)if w+l else '')
 assert [{k:x.get(k,'')for k in old[0]}for x in rows[:len(old)]]==old
 # Legacy row_id identifies a logical cell, with distinct source/version records.
 # Preserve those IDs; bind the complete record for a unique coverage entry.
 for x in rows:x['coverage_entry_id']=ident(x)
 assert len({x['coverage_entry_id']for x in rows})==len(rows)
 stream=io.StringIO(newline='');writer=csv.DictWriter(stream,fieldnames=fields,lineterminator='\n');writer.writeheader();writer.writerows(rows);TARGET.write_bytes(gzip.compress(stream.getvalue().encode(),mtime=0))
 summary={'schema':'C-COMMON-PERIOD-LEDGER-THROUGH-W9-v1','old_rows_preserved':len(old),'total_rows':len(rows),'row_kinds':dict(Counter(x['row_kind']for x in rows)),'new_NFL_games_or_tests':0,'new_actual_offer_weeks':0,'new_grade_calls':0,'newly_received_scope':'B QBdepthcompletion110weekly/cumulativeaggregateviewsW5–8 and existingCtwo-gameW9forecast-onlygrades; these are evidenceadmissions, notnewfootballtesting.','historical_scope':'2022–2025 actual-line sourcecells retained fromexistingSOURCE_COVERAGE; no fabricatedoldseasonresults. Existingnumericalhistoryresearchremainsvalidwithinits ownbindings.','offer_scope':'2026W1–9; no mergingdisconnectedoroverlappingA/Bsourcepanels. ALL is cumulative, notanadditionalweek.','path':str(TARGET.relative_to(ROOT)),'SHA256':hashlib.sha256(TARGET.read_bytes()).hexdigest(),'bytes':TARGET.stat().st_size,'source_bindings':[{'path':str(p.relative_to(ROOT)),'SHA256':hashlib.sha256(p.read_bytes()).hexdigest()}for p in [OLD,ROOT/'reports/abc-championship/SOURCE_COVERAGE.csv',ROOT/'reports/interception-history-closure-01/B-intake/COMMON_CONTROL_TABLE.json.xz',ROOT/'reports/interception-history-closure-01/C-W9-grading/CATEGORY_NUMERICAL.json']]}
 summary['identity_contract']='coverage_entry_id commits complete record/version. Legacy row_id is a logical cell and is not globally unique across source/version/missingness records; records are not independent NFL cases and must never be summed into accuracy.'
 summary['legacy_logical_ids']=len({x['row_id']for x in old})
 (OUT/'PERIOD_COVERAGE_SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps({k:summary[k]for k in ['old_rows_preserved','total_rows','row_kinds','bytes','new_actual_offer_weeks']}))
if __name__=='__main__':run()
