"""Project existing exact-product coverage; no model inference or NFL grading."""
from pathlib import Path
import json,csv,gzip,io,lzma,hashlib
ROOT=Path(__file__).resolve().parents[2];R=ROOT/'reports/category-decision-release-01'
base=R/'evidence/RETAINED_W1_W8_COVERAGE.csv.gz'
rows=list(csv.DictReader(gzip.decompress(base.read_bytes()).decode().splitlines()))
fields=list(rows[0])+['source_evidence_class','new_procedure_coverage_not_new_games','required_next_owner_action']
for x in rows:
 x['source_evidence_class']='OWNER_REPORTED_ACTUAL_LINE;QUOTE_CLOCK_UNVERIFIED'
 if 'MISSING' in x['status'] or x['status'].startswith('NOT_'):x['source_evidence_class']='MISSING_OR_DIFFERENT_CONTRACT'
 if x['source_panel']=='A_FIXED_W1_W7_ARCHIVED_POINT_PANEL':x['source_evidence_class']='OWNER_REPORTED_ACTUAL_LINE;SOURCE_WEEK_BINDING_PENDING;NOT_BLANKET_INVALIDATED'
 x['new_procedure_coverage_not_new_games']='False'
 x['required_next_owner_action']='Use exact-product/source status; no cross-panel calendar union. Archive source/week classification belongs to its source owner.'
new=json.loads(lzma.decompress((R/'intake/NEW_EXACT_PRODUCT_WEEK_MATRIX.json.xz').read_bytes()))
for x in new:
 w=x['week_view'];pid=x['candidate_id'];fam=x.get('family','B' if pid.startswith('B-') else 'C')
 done=w in [1,2,3,4,5] and (x.get('combined_decided') or 0)>0
 y={k:'' for k in fields}
 y.update(row_id='C06-NEW-'+pid+'-W'+str(w),owner=fam,category=x['category'],procedure_id=pid,product='ACTUAL_LINE_DIRECTION:'+pid.rsplit('::',1)[-1],history='Exact origin bindings in intake/A_EXECUTION_SUMMARY; C7D/1D or B F0-F3 remain separate.',role_scope=x.get('role',''),source_panel=x.get('source_panel','ANNUAL_NAMED_NJ'),book='Owner-local annual named book; exact quote clocks/private membership not independently transferred.',evidence_tier='CURRENT_VINTAGE_CHRONOLOGICAL_ACTUAL_LINES_QUOTE_AND_DECISION_TIMING_UNVERIFIED_EXPOSED_DEVELOPMENT',season=2026,week=w,status='COMPLETED_OWNER_LOCAL_PUBLIC_ARITHMETIC_ADMISSION' if done else 'MISSING_THIS_SOURCE;OTHER_PANELS_NOT_INVALIDATED',eligible=x.get('eligible'),available=None if x.get('eligible') is None or x.get('unavailable') is None else x['eligible']-x['unavailable'],selected=x.get('combined_selected'),scored=x.get('combined_decided'),unknown=x.get('unknown_participation',x.get('states',{}).get('UNKNOWN_PARTICIPATION')),abstained=x.get('abstentions'),fallback=x.get('fallback_outputs'),games=x.get('games'),player_games=x.get('player_games'),over_wins=x.get('over_wins'),over_losses=x.get('over_losses'),under_wins=x.get('under_wins'),under_losses=x.get('under_losses'),source_artifacts=json.dumps(['reports/category-decision-release-01/intake/NEW_EXACT_PRODUCT_WEEK_MATRIX.json.xz',x.get('member')]),verification_limit='Independent public arithmetic/weekly/hash checks only; private row/source-clock/fit parity not asserted.',source_evidence_class='OBSERVED_ACTUAL_OFFERS_UNVERIFIED_TIMING' if done else 'MISSING_OR_INCOMPATIBLE_THIS_SOURCE',new_procedure_coverage_not_new_games='True',required_next_owner_action='Exact A owner-local join completed. Missing annual W6-W8 quotes require A source qualification; preserve B native W5-W8 and separate diagnostics.')
 rows.append(y)
assert len(rows)==30232
# No actual-line product exists for these contracts: make all eight requested
# weeks explicit, while retaining numerical/event-only evidence separately.
for category in ['anytime_td','nick-chart-ppr-v1']:
 for week in range(1,9):
  y={k:'' for k in fields}
  y.update(row_id='C06-NO-OFFER-'+category+'-W'+str(week),owner='A/B/C/incumbent source owners',category=category,procedure_id='ALL_APPLICABLE_INHERITED_PRODUCTS_NO_COMPATIBLE_OFFER',product='ACTUAL_LINE_DIRECTION_NOT_TESTED;NUMERICAL_EVENT_ONLY_SEPARATE',history='Inherited exact event/chart contracts; no opposite TD side or legacy fantasy substitution.',role_scope='Registered source/product-specific role',source_panel='NO_ADMITTED_MATCHING_OFFER_PANEL',book='',evidence_tier='NUMERICAL_EVENT_ONLY_OR_MISSING_MATCHING_ACTUAL_OFFER',season=2026,week=week,status='NO_QUALIFIED_ACTUAL_OFFER_DIRECTION;NOT_TESTED',source_artifacts='reports/category-decision-release-01/legacy-handoff/EXISTING_FORECAST_RETRIEVAL_MAP.json',verification_limit='Existing numerical/event forecast availability is not an actual-line test.',source_evidence_class='NUMERICAL_EVENT_ONLY_WITHOUT_MATCHING_OFFER',new_procedure_coverage_not_new_games='False',required_next_owner_action='Existing source/label owner provides exact offered event/chart contract and qualified outcomes/participation; no fabricated thresholds.')
  rows.append(y)
assert len(rows)==30248
# The received follow-through adds source dispositions to existing scores. It
# does not create observations or turn site thresholds into offered props.
ft=R/'follow-through-v1';additional_source_rows=0
if (ft/'peer-intake/A_WEEKLY_COVERAGE.json.xz').exists():
 for y in rows:
  if y['source_panel']=='A_FIXED_W1_W7_ARCHIVED_POINT_PANEL':
   week=int(y['week'])
   if week in [6,7]:
    y['source_evidence_class']='INTERNAL_REFERENCE_THRESHOLD_DIAGNOSTIC_IN_THIS_A_SOURCE'
    y['required_next_owner_action']='A14a source-week classification received: preserve this scored diagnostic, exclude from actual-offer duration. Other source-specific W6-W8 panels remain independent.'
   elif week in [1,2,3,4,5]:
    y['source_evidence_class']='OWNER_BOUND_ANNUAL_W1_W5_SCOPE;QUOTE_AND_ROLE_BINDINGS_REMAIN_SCOPED'
    y['required_next_owner_action']='Source-week classification is received; retain exact procedure/alias scope and unknown quote/source clocks. No duplicate historical scoring.'
 weekly=json.loads(lzma.decompress((ft/'peer-intake/A_WEEKLY_COVERAGE.json.xz').read_bytes()))
 for index,x in enumerate(weekly['rows']):
  proc=weekly['procedures'][x['procedure_ref']] if x['procedure_ref'] is not None else dict(candidate_id='NO_COMPATIBLE_OFFER_PRODUCT',origin_session='A',output='NOT_TESTED',role_scope='Inherited exact event/chart contract')
  c={k:v if type(v)==int else None for k,v in x['counts'].items()};panel=x['panel']
  y={k:'' for k in fields}
  tier='MISSING_OR_INCOMPATIBLE_THIS_SOURCE'
  if x['status']=='SCORED_ACTUAL_LINES_TIMING_UNVERIFIED' or panel=='PEER_ANNUAL_SUBPANEL':tier='OBSERVED_ACTUAL_OFFERS_UNVERIFIED_TIMING_AT_OWNER_SCOPE'
  if 'SITE_DIAGNOSTIC' in panel:tier='INTERNAL_REFERENCE_THRESHOLD_DIAGNOSTIC'
  if panel.startswith('W8_'):tier='ORIGINAL_FROZEN_W8_SEPARATE_PRODUCT;OWNER_AUDIT_SCOPE'
  y.update(row_id='C07-A14-SOURCE-'+str(index),owner=proc.get('origin_session','A'),category=x['category'],procedure_id=proc['candidate_id'],product=proc.get('output','SOURCE_BOUND_PRODUCT'),history='Exact owner procedure_ref '+str(x['procedure_ref'])+'; source/hash bindings retained in A_WEEKLY_COVERAGE',role_scope=json.dumps(proc.get('role_scope')),source_panel='A14_SOURCE_DISPOSITION::'+panel,book=x.get('book_venue',''),evidence_tier=x.get('evidence_tier',''),season=x['season'],week=x['week'],status=x['status'],eligible=c.get('eligible'),available=c.get('available'),selected=c.get('selected'),scored=c.get('decided'),unknown=c.get('unknown'),abstained=c.get('abstentions'),fallback=c.get('fallback'),games=c.get('games'),player_games=c.get('unique_player_games'),over_wins=(x.get('OVER') or {}).get('wins'),over_losses=(x.get('OVER') or {}).get('losses'),under_wins=(x.get('UNDER') or {}).get('wins'),under_losses=(x.get('UNDER') or {}).get('losses'),source_artifacts='reports/category-decision-release-01/follow-through-v1/peer-intake/A_WEEKLY_COVERAGE.json.xz',verification_limit='Owner-local public aggregate/source classification; source-vintage, exact clocks and private membership not independently authenticated.',source_evidence_class=tier,new_procedure_coverage_not_new_games='False;SOURCE_DISPOSITION_OF_EXISTING_RESULTS',required_next_owner_action=x.get('missing_requirement','Preserve exact source/product; no calendar union.'))
  rows.append(y);additional_source_rows+=1
 own_mean=json.loads((ft/'peer-intake/COUNT_A_MEAN_OWN_WEEKLY_REUSE.json').read_text())
 for x in own_mean['actual_own_rows']:
  y={k:'' for k in fields};c=x['COMBINED']
  y.update(row_id='C07-COUNT-A-MEAN-OWN-W'+str(x['week']),owner='A',category='pass_td',procedure_id=x['exact_procedure'],product=x['product'],history=x['reconstruction'],role_scope='Original bound QB recipe; raw historical role parity not independently transferred',source_panel=x['source_panel'],book='BOOK_POLICY_PRIORITY;QUOTE_TIME_UNKNOWN',evidence_tier='OWNER_LOCAL_RECONSTRUCTED_TIMING_UNVERIFIED_ACTUAL_LINE',season=x['season'],week=x['week'],status='SCORED_EXACT_CORRECTED_MEAN_OWN_WEEK;NOT_LEGACY_SUBSTITUTION',eligible=x['eligible'],selected=sum(x[s]['decided'] for s in ['OVER','UNDER']),scored=c['decided'],abstained=x['no_lean'],over_wins=x['OVER']['wins'],over_losses=x['OVER']['losses'],under_wins=x['UNDER']['wins'],under_losses=x['UNDER']['losses'],source_artifacts='reports/category-decision-release-01/follow-through-v1/peer-intake/COUNT_A_MEAN_OWN_WEEKLY_REUSE.json',verification_limit='Direct retained mean-own weekly CSV, not legacy ties; games/fallback/private mask/vintage remain unexported or independently unverified.',source_evidence_class='OBSERVED_ACTUAL_OFFERS_UNVERIFIED_TIMING_AT_OWNER_SCOPE',new_procedure_coverage_not_new_games='False;SOURCE_DISPOSITION_OF_EXISTING_RESULTS',required_next_owner_action='No repeated fit/grade. Native CountA producer integration/current feed remains a separate owner task.')
  rows.append(y);additional_source_rows+=1
 assert additional_source_rows==247 and len(rows)==30495
s=io.StringIO();w=csv.DictWriter(s,fieldnames=fields);w.writeheader();w.writerows(rows);p=R/'W1_W8_COVERAGE.csv.gz';p.write_bytes(gzip.compress(s.getvalue().encode(),mtime=0))
summary=dict(id='C-CATEGORY-W1-W8-COVERAGE-v1',retained_exact_profile_week_cells=30072,new_exact_product_week_cells=160,total_rows=len(rows),exact_product_week_rows=30232,category_level_no_offer_rows=16,new_exact_products=20,new_actual_NFL_games=0,new_actual_NFL_weeks=0,new_completed_product_week_cells=sum(x['week_view'] in [1,2,3,4,5] and (x.get('combined_decided') or 0)>0 for x in new),source=p.name,source_SHA256=hashlib.sha256(p.read_bytes()).hexdigest(),all_twelve_complete_comparable_W1_W8_champions='NOT_ESTABLISHED; source/product/horizon gaps retained',provisional_decisions='Partial compatible evidence may support existing owner review. No blanket eight-week or all-category waiting gate.',separate_panels=['A archived owner-reportedW1-W7:latest source-week mapping pending','A annual named retainedW1-W5: exact C04/B joins','B nativeW5-W8: P2 differs from mean','C nativePinnacleW2-W3: overlaps annual weeks','W6-W7 internal/reference diagnostics in annual reports','W8 reference rows in annual reports; other W8 sources retained separately'])
if additional_source_rows:
 summary['follow_through_source_disposition_rows']=additional_source_rows
 summary['follow_through_new_NFL_games_or_weeks']=0
 summary['source_week_resolution']='A14 annualW1-W5, same-source siteW6-W7 diagnostics, separate audited frozenW8 products; no cross-panel union.'
 summary['separate_panels'][0]='A oldW1-W7 mixed diagnostic: source-week classification received, annual actualW1-W5 and siteW6-W7 kept separate'
 summary['separate_panels'][-1]='Annual sourceW8missing; separate A audited frozenW8 and BnativeW5-W8 panels retained with their own contracts'
(R/'COVERAGE_SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))
