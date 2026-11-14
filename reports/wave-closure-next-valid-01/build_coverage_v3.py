"""Append new owner evidence to the existing coverage ledger; no regrading/fits.

Overlapping views are named records, never additional NFL observations.
The complete decoded V2 wire remains an exact prefix of V3.
"""
import csv, gzip, hashlib, io, json, math, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
OLD=ROOT/'reports/category-decision-release-01/W1_W9_AND_HISTORY_COVERAGE_V2.csv.gz'
NEW=ROOT/'reports/category-decision-release-01/W1_W9_AND_HISTORY_COVERAGE_V3.csv.gz'
def load(p):
 b=Path(p).read_bytes();return json.loads(gzip.decompress(b) if str(p).endswith('.gz') else b)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def bind(p):return dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,SHA256=sha(p))
def txt(v):
 if v is None:return ''
 if isinstance(v,(dict,list)):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False)
 return str(v)
def sides(o,u,c):
 out={}
 for label,s in [('over',o),('under',u),('combined',c)]:
  n=s.get('decided');w=s.get('wins');l=s.get('losses')
  if n:
   assert w+l==n; rate=s.get('rate',s.get('accuracy',w/n));assert math.isclose(rate,w/n,abs_tol=1e-12)
  else:rate=None
  out.update({label+'_wins':w,label+'_losses':l,label+'_decided':n,label+'_rate':rate})
 for k in ['wins','losses','decided']:assert (o.get(k) or 0)+(u.get(k) or 0)==(c.get(k) or 0)
 return out
def main():
 start=time.process_time()
 if NEW.exists():
  # Only the independently identified, never-published initial local draft
  # may be regenerated. Any other existing version fails closed.
  import subprocess
  assert sha(NEW)=='6ff0f3a803f5a8835f380075518cf395c8c8fe1c9ed20e888c8b1cf59551dc4f','VERSION_ALREADY_EXISTS'
  assert subprocess.run(['git','ls-files','--error-unmatch',str(NEW.relative_to(ROOT))],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode!=0,'TRACKED_VERSION_CANNOT_REPLACE'
 raw=gzip.decompress(OLD.read_bytes());old=list(csv.DictReader(io.StringIO(raw.decode())));fields=list(old[0]);assert len(old)==32103
 rows=[];sources={}
 def append(owner,source,i,data):
  row={k:'' for k in fields}; row.update({k:txt(v) for k,v in data.items()});assert set(row)==set(fields)
  sources[str(source.relative_to(ROOT))]=bind(source)
  row['row_id']=hashlib.sha256(f'C-COVERAGE-V3|{owner}|{sha(source)}|{i}'.encode()).hexdigest()
  row['coverage_entry_id']=hashlib.sha256(json.dumps({k:v for k,v in row.items() if k!='coverage_entry_id'},sort_keys=True,separators=(',',':')).encode()).hexdigest();rows.append(row)
 a=HERE/'A-intake/NORMALIZED_HISTORICAL_CONTROL_ROWS.json.gz'
 for i,r in enumerate(load(a)):
  append('A',a,i,dict(owner='A',category=r['category'],procedure_id='A::'+r['procedure_id'],product=r['product_policy'],history='Original registered A 2023 earlier-only recipe; retained seven-day current-vintage policy',role_scope='QB/RB mixed; source role strata separate',source_panel=r['source_period']+'::'+r['comparison_mask'],book='Source-named representative book; main/alternate unverified',evidence_tier=r['source_evidence_tier'],season=r['season'],week=r['week_view'],status=r['execution_state'],eligible=r['eligible'],available=r['available'],selected=r['selected'],scored=r['COMBINED']['decided'],unknown=r.get('unknown'),abstained=r.get('abstentions'),fallback=r.get('fallback'),games=r.get('games'),player_games=r.get('player_games'),source_artifacts=str(a.relative_to(ROOT))+';'+r['source_projection'],verification_limit='C public aggregate/source commitment arithmetic only; no private-row, model-fit, quote-clock or simultaneous-board parity.',source_evidence_class='NAMED_BOOK_CURRENT_VINTAGE_HISTORICAL_RECONSTRUCTION',new_procedure_coverage_not_new_games=True,required_next_owner_action='Close tested unchanged direction/Top6 upgrade; retain numerical finding separately; do not refit.',row_kind='OWNER_HISTORICAL_AGGREGATE_VIEW',grading_version='Original bound A 2023 result',issuance_state='RECONSTRUCTED_NOT_ORIGINAL_ISSUANCE',additional_metrics=r,**sides(r['OVER'],r['UNDER'],r['COMBINED'])))
 b=HERE/'B-intake/NORMALIZED_COMPLETION_SIDE_AGGREGATES.json.gz'
 for i,r in enumerate(load(b)):
  direct={k:r.get(k) for k in fields if k in r};direct.pop('probability_scores',None)
  metrics=dict(r);metrics['probability_score_typing']='Companion probability-law scores from source; not inferred confidence for the typed P1 mean/median side rule.'
  product=r['product_id']
  if r.get('K') is not None:product+=f"::K{r['K']}::{r['rank_scope']}"
  append('B',b,i,dict(direct,product=product,scored=r['combined_decided'],status='OWNER_SCORED_DIAGNOSTIC' if r['combined_decided'] else 'NO_DECIDED_SELECTIONS_NA_NOT_ACCURACY',source_artifacts=str(b.relative_to(ROOT))+';reports/wave-closure-next-valid-01/B-intake/ADMISSION.json',source_evidence_class='B_FTN_TIMING_UNVERIFIED_SAVED_LINE_DIAGNOSTIC',new_procedure_coverage_not_new_games=True,required_next_owner_action='A execute exact saved W1–4 output/compatible-offer join; B grades original frozen packet. No repeated fitting.',row_kind='OWNER_COMPLETION_AGGREGATE_VIEW',grading_version='Bound B FTN source version',issuance_state='CURRENT_VINTAGE_CHRONOLOGICAL_RECONSTRUCTION',additional_metrics=metrics))
 w=HERE/'website-intake/five-week-summary-v2.json';v=load(w);review=load(HERE/'website-intake/INDEPENDENT_AGGREGATE_RECONCILIATION.json')
 panels=[(q['week'],q) for q in v['weeks']]+[('ALL',v['cumulative'])]
 for week,panel in panels:
  for component in ['control','candidate','candidate_generated','candidate_fallback']:
   r=panel[component];ss=r.get('own_sides') if week!='ALL' else review['own_sides_recomputed'][component]
   assert ss is not None
   contribution=component not in ['control','candidate']
   append('website',w,f'{week}|{component}',dict(owner='original_website',category='cross_category_top_picks',procedure_id=v['protocol']+'::'+component,product='CONTRIBUTION_ONLY_NOT_STANDALONE_POLICY' if contribution else 'COMPLETE_FROZEN_SELECTOR_POLICY',history='Frozen mapping/selector; partial conditional retrospective compatible boards; source rule unchanged',role_scope='Exact cross-category production eligibility; narrow WR/TE reception substitution',source_panel='FROZEN_W4_W8_SELECTOR_V7',book='Source-bound archived DK-labelled lines; clocks/partial board limits retained',evidence_tier='PARTIAL_CONDITIONAL_RETROSPECTIVE;FIVE_DISTINCT_COMPLETE_POLICY_BLOCKS;NOT_PRIMARY_ADMITTED',season=2026,week=week,status='SHADOW_CONTRIBUTION_ONLY' if contribution else 'SHADOW_COMPLETE_POLICY_DURATION_MET',eligible=panel.get('player_eligible_count'),available=None,selected=r['selected'],scored=r['decided'],unknown=r.get('unknown',r.get('unresolved')),abstained=None,fallback=r['selected'] if component=='candidate_fallback' else 0 if component=='candidate_generated' else (panel.get('candidate_fallback',{}).get('selected') if component=='candidate' else None),games=None,player_games=None,source_artifacts=str(w.relative_to(ROOT))+';reports/wave-closure-next-valid-01/website-intake/ADMISSION.json',verification_limit=v['row_access_limit']+' C independently reconciled public aggregates only; no new B fifth-week receipt obtained.',source_evidence_class='ORIGINAL_WEBSITE_CANONICAL_FROZEN_SELECTOR_REPLAY',new_procedure_coverage_not_new_games=True,required_next_owner_action='B independently verifies new W4 rows/membership; website retains SHADOW and captures next qualified exact-policy board via existing route.',row_kind='SELECTOR_CONTRIBUTION_ONLY' if contribution else 'COMPLETE_SELECTOR_POLICY',grading_version='Website V7 measurement-corrected frozen selections',issuance_state='RETROSPECTIVE_NOT_ORIGINAL_ADVANCE_SELECTED_TICKET',additional_metrics=dict(whole_policy_weeks=v['scored_season_weeks'],component=component,source_week_or_cumulative=panel,not_all_category_winner_deployment=True),**sides(ss['over'],ss['under'],r)))
 c=HERE/'C-shadow-grading/GRADING_RECEIPT.json';cv=load(c)
 for i,r in enumerate(cv['metrics']):
  append('C',c,i,dict(owner='C',category='rec',procedure_id=r['run_id']+'::'+r['model_id'],product='FROZEN_FORECAST_ONLY_NUMERICAL',history='Original immutable pregame packet; no refit/reissue/late lines',role_scope='Original25 known-season queries: WR/TE plus separately declared RB shadow; qualified played mask18',source_panel='C_W10_WASNYG_ORIGINAL_FROZEN_FORECASTS',book=None,evidence_tier='GITHUB_SERVER_PREGAME_PACKET;QUALIFIED_POSTGAME_OBSERVED_OUTCOMES;FORECAST_ONLY_APPEARANCE_CONDITIONED',season=2026,week=10,status='FROZEN_FORECAST_ONLY_GRADED_WITH_EXPLICIT_UNKNOWN',eligible=r['eligible'],available=r['eligible'],selected=0,scored=r['scored'],unknown=r['states'].get('UNKNOWN',0),abstained=None,fallback=None,games=1,player_games=r['eligible'],source_artifacts=str(c.relative_to(ROOT)),verification_limit='One game; C04/C06 and model views overlap. No actual offers/original selected sides/O-U product or general superiority.',source_evidence_class='ORIGINAL_C_PROSPECTIVE_FORECAST_ONLY',new_procedure_coverage_not_new_games=False,required_next_owner_action='Preserve original grades; later qualified games/offers needed. C05 stays future/pending.',row_kind='FORECAST_ONLY_NUMERICAL',grading_version=cv['id'],issuance_state='ORIGINAL_GITHUB_SERVER_QUALIFIED_FORECAST_ONLY',additional_metrics=r))
 out=io.StringIO(newline='');cw=csv.DictWriter(out,fieldnames=fields,lineterminator='\n');cw.writerows(rows)
 wire=raw+out.getvalue().encode();decoded=list(csv.DictReader(io.StringIO(wire.decode())));assert len(decoded)==32103+len(rows);assert decoded[:32103]==old
 assert len({r['coverage_entry_id'] for r in decoded})==len(decoded)
 NEW.write_bytes(gzip.compress(wire,mtime=0))
 receipt=dict(id='C-WAVE-CLOSURE-COVERAGE-V3',old=bind(OLD),new=bind(NEW),prior_entries=len(old),appended_entries=len(rows),total_entries=len(decoded),A_views=len(load(a)),B_views=len(load(b)),selector_policy_and_contribution_views=24,C_forecast_only_model_views=len(cv['metrics']),sources=list(sources.values()),old_decoded_wire_exact_prefix=True,all_complete_entry_ids_unique=True,new_2026_actual_offer_games=0,new_original_selected_sides=0,new_C_forecast_only_graded_game=1,new_C_forecast_only_week=[2026,10],scope='Named overlapping evidence views; never sum masks, windows, contribution components or model/run views into independent observations.',FTN_attribution='FTN Data via nflverse; CC BY-SA 4.0. Derived public aggregates retain attribution; no new raw charting distribution.',CPU_seconds=time.process_time()-start)
 (HERE/'LEDGER_BUILD_RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
if __name__=='__main__':main()
