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
s=io.StringIO();w=csv.DictWriter(s,fieldnames=fields);w.writeheader();w.writerows(rows);p=R/'W1_W8_COVERAGE.csv.gz';p.write_bytes(gzip.compress(s.getvalue().encode(),mtime=0))
summary=dict(id='C-CATEGORY-W1-W8-COVERAGE-v1',retained_exact_profile_week_cells=30072,new_exact_product_week_cells=160,total_rows=len(rows),exact_product_week_rows=30232,category_level_no_offer_rows=16,new_exact_products=20,new_actual_NFL_games=0,new_actual_NFL_weeks=0,new_completed_product_week_cells=sum(x['week_view'] in [1,2,3,4,5] and (x.get('combined_decided') or 0)>0 for x in new),source=p.name,source_SHA256=hashlib.sha256(p.read_bytes()).hexdigest(),all_twelve_complete_comparable_W1_W8_champions='NOT_ESTABLISHED; source/product/horizon gaps retained',provisional_decisions='Partial compatible evidence may support existing owner review. No blanket eight-week or all-category waiting gate.',separate_panels=['A archived owner-reportedW1-W7:latest source-week mapping pending','A annual named retainedW1-W5: exact C04/B joins','B nativeW5-W8: P2 differs from mean','C nativePinnacleW2-W3: overlaps annual weeks','W6-W7 internal/reference diagnostics in annual reports','W8 reference rows in annual reports; other W8 sources retained separately'])
(R/'COVERAGE_SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))
