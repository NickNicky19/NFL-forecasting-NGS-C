"""Append report views to existing saved grades; no fits, forecasts or regrades."""
from __future__ import annotations
import csv,gzip,hashlib,json,math,datetime
from collections import defaultdict,Counter
from pathlib import Path
from shared_game_sim01_budget import ROOT,D,save,initialize,charge,footprint

P=ROOT/'private/shared-game-sim-01'
CATS=('pass_yd','pass_td','pass_cmp','pass_att','pass_int','rush_yd','rush_att','rec','rec_yd','rush_rec_yd','anytime_td','nick-chart-ppr-v1')
def load(p):return json.loads(p.read_bytes())
def role_ok(method,position,category):
 if 'C-M3-' in method or 'PLAYER-CONTEXT-' in method:return position in ('WR','TE')
 if category.startswith('pass_'):return position=='QB'
 if category in ('rec','rec_yd','rush_rec_yd'):return position in ('RB','WR','TE')
 return True
def enrich(s,rows):
 for kind,pred in [('represented',lambda r:True),('available',lambda r:r['available']),('selected',lambda r:r['selected_side'] in ('OVER','UNDER')),('decided',lambda r:r['status'] in ('WIN','LOSS'))]:
  rr=[r for r in rows if pred(r)]
  s[kind+'_weeks']=sorted({r['week'] for r in rr});s[kind+'_games']=len({r['game_id'] for r in rr});s['unique_'+kind+'_player_games']=len({(r['game_id'],r['player_id']) for r in rr})
 s['legacy_weeks_field']='Represented full frame, not automatically available/decided weeks'
 s['declared_role_eligible']=sum(role_ok(r['method'],r['position'],r['category']) for r in rows)
 s['out_of_scope_role']=len(rows)-s['declared_role_eligible']
 s['technical_unavailable_in_role']=sum(not r['available'] and role_ok(r['method'],r['position'],r['category']) for r in rows)
 s['unavailable_reasons']=dict(Counter(r['unavailable_reason'] for r in rows if not r['available']))
 s['correctness_holds']=sorted({r['correctness_hold'] for r in rows if r.get('correctness_hold')})
 s['missingness_diagnostic']=dict(available_known=sum(r['available'] and r['actual'] is not None for r in rows),available_unknown=sum(r['available'] and r['actual'] is None for r in rows),unavailable_known=sum(not r['available'] and r['actual'] is not None for r in rows),unavailable_unknown=sum(not r['available'] and r['actual'] is None for r in rows),scope='No assumption decided subset is representative; retained stat-row-conditioned populations and unknown clocks remain limitations')
 for side in ('OVER','UNDER','COMBINED'):
  rr=[r for r in rows if r['selected_side'] in ('OVER','UNDER') and (side=='COMBINED' or r['selected_side']==side)]
  u=sum(r['actual'] is None for r in rr);n=s[side]['decided'];w=s[side]['wins']
  s[side]['selected_unknown']=u
  s[side]['unknown_resolution_sensitivity']=dict(low=w/(n+u) if w is not None and n+u else None,high=(w+u)/(n+u) if w is not None and n+u else None,scope='Sensitivity bound only; unknowns not resolved/imputed, participation/voids unknown')
 return s
def numeric_pair(rows,control):
 cc={r['case_id']:r for r in control};a=[];b=[]
 for r in rows:
  q=cc.get(r['case_id'])
  if q is not None and r['available'] and q['available'] and r['actual'] is not None and r['point'] is not None and q['point'] is not None:a.append(r['point']-r['actual']);b.append(q['point']-q['actual'])
 def stats(x):return dict(n=len(x),MAE=sum(abs(y) for y in x)/len(x) if x else None,bias=sum(x)/len(x) if x else None,RMSE=math.sqrt(sum(y*y for y in x)/len(x)) if x else None)
 return dict(candidate=stats(a),control=stats(b),scope='Same available known-statistic cases, including point ties; no probability invented')
def main():
 raw=json.loads(gzip.decompress((P/'raw_grades.json.gz').read_bytes()));result=load(D/'COMPARISON_RESULTS.json')
 complete=load(P/'complete_results_with_membership.json');groups=defaultdict(list)
 for r in raw:groups[r['method'],r['category']].append(r)
 for s in result['scores']:
  rr=groups[s['method'],s['category']];enrich(s,rr if s['week']=='ALL' else [r for r in rr if r['week']==s['week']])
 for i,s in enumerate(result['own_selection_policies']):
  original=complete['own_selection_policies'][i];ids=set(original['case_ids']);rr=[r for r in groups[s['method'],s['category']] if r['case_id'] in ids];enrich(s['own_selected_summary'],rr)
 for pair in result['saved_control_vs_website']['paired']:
  if pair['week']=='ALL':pair['same_case_numerical']=numeric_pair(groups[pair['candidate'],pair['category']],groups[pair['control'],pair['category']])
 result['panel_represented_weeks']=result['actual_weeks'];result['actual_week_rule']='Per-product decided_weeks, not the panel represented weeks or numerical origins'
 result['simulator_execution']=load(D/'CANARY_REMAINDER_GATE.json')
 result['new_work']='One startup prior fit, failed unchanged provider-conditioner attempts, saved C actual-line coverage completion; zero simulator games/trajectories, not a new forecasting gain'
 # Deterministic exact-mask leader view: incompatible availability pools are
 # never sorted together. Empty/unavailable arms are listed elsewhere.
 bymask=defaultdict(list)
 for (method,cat),rr in groups.items():
  available=sorted(r['case_id'] for r in rr if r['available'])
  if available:bymask[cat,hashlib.sha256(json.dumps(available,separators=(',',':')).encode()).hexdigest()].append(method)
 score={(s['method'],s['category']):s for s in result['scores'] if s['week']=='ALL'}
 masks=[]
 for (cat,mask),methods in sorted(bymask.items()):
  valid=[score[m,cat] for m in methods if score[m,cat]['COMBINED']['decided']]
  highest=max((s['COMBINED']['rate'] for s in valid),default=None)
  candidates=[s for s in valid if s['method'] not in ('ALWAYS_OVER','ALWAYS_UNDER')];bestforecast=max((s['COMBINED']['rate'] for s in candidates),default=None)
  masks.append(dict(category=cat,available_case_mask_SHA256=mask,available=score[methods[0],cat]['available'],methods=methods,largest_own_combined=[dict(method=s['method'],OVER=s['OVER'],UNDER=s['UNDER'],COMBINED=s['COMBINED'],actual_decided_weeks=s['decided_weeks']) for s in valid if s['COMBINED']['rate']==highest],largest_forecast_product=[s['method'] for s in candidates if s['COMBINED']['rate']==bestforecast],scope='Exact same available opportunities; own complete decisions/ties differ and are disclosed. Historical descriptive maximum; no total ranking across masks or future superiority.'))
 save(D/'COMPARABLE_MASK_LEADERS.json',dict(groups=masks,unavailable_arms_not_losers=True,global_ABC_champion='NOT_ESTABLISHED;A/B new-frame joins pending, simulator unavailable'))
 # Complete machine-readable aggregates, without protected membership/rows.
 body=(json.dumps(result,indent=2,allow_nan=False)+'\n').encode();z=gzip.compress(body,mtime=0);(D/'COMPARISON_RESULTS.json.gz').write_bytes(z);assert gzip.decompress((D/'COMPARISON_RESULTS.json.gz').read_bytes())==body
 (D/'COMPARISON_RESULTS.json').unlink() # lossless duplicate of retained gzip only
 save(D/'COMPARISON_MACHINE_BINDING.json',dict(path='reports/shared-game-sim-01/execution-v1/COMPARISON_RESULTS.json.gz',bytes=len(z),SHA256=hashlib.sha256(z).hexdigest(),decoded_bytes=len(body),decoded_SHA256=hashlib.sha256(body).hexdigest(),local_independent_reopen='PASS',raw_membership_rows='Not in public aggregate; private/original-source reconstruction route'))
 def records(s):
  d=dict(category=s['category'],method=s['method'],week=s['week'],actual_decided_weeks=';'.join(map(str,s['decided_weeks'])),represented_weeks=';'.join(map(str,s['represented_weeks'])),eligible_full_board=s['eligible'],role_eligible=s['declared_role_eligible'],available=s['available'],selected=s['COMBINED']['selected'],decided=s['COMBINED']['decided'],unavailable=s['unavailable'],unknown=s['unknown_outcomes'],selected_unknown=s['selected_unknown'],native=s['native'],fallback=s['fallback'],actual_decided_games=s['decided_games'],actual_decided_player_games=s['unique_decided_player_games'],MAE=s['numerical']['MAE'],Brier=s['probability']['half_multiclass_Brier'],log_loss=s['probability']['raw_log_loss'])
  for k in ('OVER','UNDER','COMBINED'):
   for v in ('wins','losses','decided','rate'):d[k+'_'+v]=s[k][v]
  d['evidence']='CONDITIONAL_EXPOSED_RECONSTRUCTION;UNVERIFIED_QUOTES_ISSUES;UNCLASSIFIED_LINES'
  d['correctness_hold']=';'.join(s['correctness_holds']);return d
 for name,ss in [('ALL_PRODUCTS.csv',[s for s in result['scores'] if s['week']=='ALL']),('WEEKLY_PRODUCTS.csv',[s for s in result['scores'] if s['week']!='ALL'])]:
  rr=[records(s) for s in ss]
  with (D/name).open('w',newline='') as h:w=csv.DictWriter(h,fieldnames=list(rr[0]),lineterminator='\n');w.writeheader();w.writerows(rr)
 cases=[json.loads(s) for s in (P/'views/comparison_inputs/cases.jsonl').read_bytes().splitlines()]
 schedules=list(csv.DictReader((ROOT/'sources/category-decision-release-01/schedule.csv').open()));scheduled=Counter(int(r['week']) for r in schedules if r['season']=='2026' and r['game_type']=='REG')
 coverage=[]
 for cat in CATS:
  for week in range(1,10):
   rr=[r for r in cases if r['identity']['category']==cat and r['identity']['week']==week]
   coverage.append(dict(category=cat,season=2026,week=week,frame_rows=len(rr),covered_games=len({r['identity']['game_id'] for r in rr}),scheduled_games=scheduled[week],source_state='CONDITIONAL_ACTUAL_OFFER_UNCLASSIFIED_UNKNOWN_CLOCKS' if rr else 'NO_STARTER_MATCHING_OFFERS',simulator_completed_games=0,simulator_trajectories=0,simulator_forecasts='NOT_GENERATED;RUNTIME_GATE_STOP',S_P_fallback='NONE;6NULL_PROVIDER_OUTPUTS_HELD',A_join='A_OWNED_PENDING',B_join='B_OWNED_PENDING'))
 with (D/'COVERAGE_W1_W9.csv').open('w',newline='') as h:w=csv.DictWriter(h,fieldnames=list(coverage[0]),lineterminator='\n');w.writeheader();w.writerows(coverage)
 allstatus=[]
 for cat in CATS:
  full=[r for r in cases if r['identity']['category']==cat]
  if cat in ('rec','rec_yd'):display='C-M3-v1.1::'+cat+'::M3-0::base::MEAN_POINT'
  else:display='C-ALL12-LAW-THRESHOLD-v2.1::'+cat+'::H-MULTI::P2_LEAF::E0_OP::MEAN_POINT'
  s=score.get((display,cat));pairs=[r for r in result['saved_control_vs_website']['paired'] if r['candidate']==display and r['category']==cat and r['week']=='ALL' and r['control'] in ('W0','W1','ALWAYS_OVER','ALWAYS_UNDER')]
  allstatus.append(dict(category=cat,full_frame_rows=len(full),S_P_native_forecasts=0,S_P_fallback_forecasts=0,S_P_unavailable=len(full),S_P_scored_weeks=[],D_P_actual_scope='NOT_EXECUTED_NO_VALID_CONDITIONED_GAME',frozen_display_control=display if s else None,display_choice='Named retained Leaf mean for readable coverage; not a largest-own-pool winner',control_summary=s,matched_controls=pairs,A_candidates=2 if cat=='pass_yd' else 3,B_candidates=3,C_nominations=3,A_B_actual_frame_grades='PENDING_OWNER_OUTPUTS',duration='Floor met only as conditional partial retrospective evidence' if s and len(s['decided_weeks'])>=5 else 'Exact scored-week floor not met in this panel' if s else 'NO_MATCHING_OFFER',research_decision='SHADOW_SAVED_CONTROL;BLOCKED_SIMULATOR' if full else 'NO_OFFER_BLOCKED',original_website='Owner-reported CURRENT_BASELINE; no C activation/served verification',release='No new primary replacement authorized or established by this package',remaining_action='C scoped numerical completion for unchanged objective;A/B owned joins/B checks;website owner admission/replay/release' if full else 'Qualified exact event/scoring/offer contract, no invented market'))
 save(D/'CATEGORY_DECISIONS.json',dict(scope='All12 explicit statuses; no all-session winner manufactured from incompatible masks',categories=allstatus))
 # Readable checkpoint emphasizes executed evidence, not test/model counts.
 def fmt(s,key='COMBINED'):
  if not s or not s[key]['decided']:return 'N/A'
  q=s[key];return f"{q['wins']}–{q['losses']} / {q['decided']} / {q['rate']:.2%}"
 lines=['# Shared-game simulator v3 — executed bounded stop and saved-method comparison','',
 '**0 games and 0 trajectories completed.** The unchanged provider-conditioner could not produce a valid canary. Thirty-three origins have failure records; the32 retained optimizer records all hit the frozen100-iteration limit. The first optimizer vector/status was lost because of a failure-report path defect, now repaired. The final in-flight stage was interrupted by the cumulative canary CPU guard. No failed origin was retried; no setting, seed, outcome threshold or offered line was changed. This is a runtime-incomplete experiment, not an accuracy loss.','',
 '**New evidence:** C’s saved M3-0 Leaf reception mean now has339–239/578 decided cases; its law has331–247/578, each from638 available forecasts with60 selected unknowns. Both cover W4–9, including only two games in W4. These are additional exact-procedure grades on already-retained games, not new NFL observations, fits or original pregame picks.','',
 'The mean gains17 wins over W0 on575 common decided cases (+2.96 percentage points; descriptive game-block95% interval −2.61 to +8.55), and5 over W1 on571 (+0.88 points; −4.22 to +5.99). Law gains9 versus W0/575 and loses3 versus W1/571. No dependable superiority or80–90% result is established. The law’s own Over115–51/166 and Under216–196/412 remain one complete procedure; they are not spliced with another product.','',
 '## Receptions: own records and selection coverage','',
 '| Exact product | Actual scored weeks | Own Over W–L/N/% | Own Under W–L/N/% | Combined W–L/N/% | Available / full frame; selected unknown |','|---|---|---|---|---|---|']
 for method in ['C-M3-v1.1::rec::M3-0::base::MEAN_POINT','C-M3-v1.1::rec::M3-0::base::LAW','W0','W1']:
  s=score[method,'rec'];lines.append(f"| {method} | {s['decided_weeks']} | {fmt(s,'OVER')} | {fmt(s,'UNDER')} | {fmt(s)} | {s['available']}/922; {s['selected_unknown']} unknown |")
 lines +=['','Leaf remains WR/TE-only. Its full-frame unavailability includes unsupported roles, identity and missing saved rows; declared-role and technical-missingness counts are separate in the machine export. Source stat-row conditioning and current-vintage reconstruction remain limitations. Availability is associated with outcome completeness; the decided subset is not assumed representative. Unknown-resolution bounds are sensitivity only.','',
 'Raw law Brier0.248943 and log loss0.693959 are absolute probability scores on578 known cases; W0/W1 have no invented probabilities. The Leaf mean’s own MAE is1.48402 on578 cases. Same-case numerical comparisons, point ties, law/median siblings and adverse weekly results remain in the full detail.','',
 '| Frozen law capacity | Selected / full board | Decided W–L | Selected unknown | Actual coverage |','|---|---|---|---|---|']
 for frac in (.5,.25,.1):
  s=next(s for s in result['own_selection_policies'] if s['method']=='C-M3-v1.1::rec::M3-0::base::LAW' and s['category']=='rec' and s['fraction']==frac);q=s['own_selected_summary'];lines.append(f"| {frac:.0%} cap | {q['COMBINED']['selected']}/922 | {q['COMBINED']['wins']}–{q['COMBINED']['losses']} | {q['selected_unknown']} | {s['achieved_coverage']:.2%} |")
 lines +=['','Capacity means at most floor(fraction × full category/game-origin board), with stable ties. Lists were chosen before grades, including selected unknowns. The50/25/10% law lists had53/24/5 selected unknowns. Own-list matched-capacity results and same-selected-case directions are distinct. Mean/W0/W1 gap ranks are descriptive point policies, not calibrated confidence or website Top Picks.','',
 '## All twelve category/product statuses','',
 'The table displays a fixed retained Leaf mean control for coverage. It does not rank incompatible masks or declare C a winning repository. [Exact-mask observed leaders](COMPARABLE_MASK_LEADERS.json) preserve ties and the strongest forecast product even where a constant wins. A/B nominations are received; their new-frame owned joins are still pending.','',
 '| Category | S-P native/fallback/unavailable | Named C control own O/U/combined W–L/N/% | Actually decided weeks | Decision |','|---|---|---|---|---|']
 for r in allstatus:
  s=r['control_summary'];lines.append(f"| {r['category']} | 0/0/{r['S_P_unavailable']} | {fmt(s,'OVER')}; {fmt(s,'UNDER')}; {fmt(s)} | {s['decided_weeks'] if s else 'None; no offer'} | {r['research_decision']} |")
 lines +=['','C CMP/ATT coherence and population holds remain. Exact chart-PPR and inherited rushing-or-receiving anytime-TD have no matching offers; no fantasy substitution or invented NO/Under market was added. W1–3 are absent from this new panel. Six files are represented weeks, not six qualified native simulator weeks. [W1–9 cells](COVERAGE_W1_W9.csv) and [weekly products](WEEKLY_PRODUCTS.csv) distinguish actual decisions from unavailable/no-selection weeks.','',
 '## Source, integration, execution and verification','',
 'PR63 merged at approved head ebf9a0b (merge fe57cd8). The user-approved1800CPU/7200wall, one-worker/thread, RSS1288490188, retained512MiB/maximum new peak768MiB and unchanged whole-C cap were recorded once. Prior45CPU/190wall were carried, as were failures; old M3/Tab/dyad accounts were untouched. The canary guard stopped at59.093234438 CPU of60; no valid generation/subcap or whole-remainder storage/runtime projection exists. Actual usage is in [LEDGER](LEDGER.json), not a claimed complete assistant-time certificate.','',
 'Website metadata/code and deterministic private views were actually recovered. All3474cases/464unknown outcomes and the closed S-P manifest match exactly. C received A35/B36 nominations and its own36 category nominations; these are not107 independent families or new grades. One B nested QB metadata fetch failed body integrity and was preserved without retry; the full roster remains available.','',
 'The six raw-provider nulls are held unavailable at their actor/category outputs. Adjusted comparator fields never enter S-P; W1 fallback remains unchanged. Exact LAR/LA normalization repaired33 player-game namespace mismatches before generation. Archived and native schedule clocks are both retained; all archived clocks are identical or later, so the conservative dual-clock rule does not admit extra information. Original issue/quote clocks remain unknown, all line tiers unclassified, and venue settlements are not newly authenticated.','',
 'The source fitter executed against1327qualified team-games with one held team, preserving47 unknown/incompatible catch gain/TD tuples. The single earlier prior consumed1087 team-games/67080 plays and was restored, not refitted, afterward. The numeric kernel, provider conditioner, source fitter and D-P sufficient-moment/fitted-state writer are implemented. **Actual D-P canary serialization/reopening, forecast-worker mutation and trajectory conservation remain NOT_RUN because no core fit qualified.**','',
 'A separate NFL-design initial analytic-gradient check passed132 parameters with maximum absolute discrepancies below5e−9; it is not optimizer convergence or fit reproduction. Independent C arithmetic reconstructed28 weekly/cumulative reception records, four paired totals and the exact law selection memberships without calling the common scorer. That receipt is [here](verification/INDEPENDENT_ARITHMETIC.json). B’s new freeze/forecast/runtime review has not been received; public arithmetic is not private-row/fit parity.','',
 'The private raw47,006 method/case grade rows were persisted and reopened before selective summaries. They are repeated method views over3474 cases, not47,006 independent NFL opportunities. No raw provider/case/outcome rows, private membership lists or private locators are published. The [forecast-byte binding](FREEZE_B.json) was remotely restored before grade joining; no S-P forecast bundle is implied.','',
 '## Product decisions and exact remaining actions','',
 '- **C:** retain the numerical stop and failed vectors. Any changed100-iteration ceiling or additional canary/resumption needs one scoped numerical-completion approval; the unspent global balance is not permission to change these guards. No automatic extension or original-result overwrite.','- **A:** execute the single protected saved-output join on the admitted frame; preserve absent W8–9 outputs and arbitrary-line-law gaps. [C’s proposed three-event bridge](C_PROPOSED_GAME_BRIDGE_FOR_OWNER_ADMISSION.json) is for owner admission, not an acknowledgment or authenticated issuance claim.','- **B:** complete owned candidate joins and scoped checks on the delivered C freezes. No duplicate simulator, old failed-fit retry or inferred private parity.','- **Website:** owns identity supplements, ordinary-margin/Top Picks replay, capture and product release. Its conditional frame is admitted; no C research activation or new served-value check occurred. Existing independently eligible releases and CountA producer/connection work continue separately.','',
 'Simulator direction/probability/numerical products remain **BLOCKED**. Saved C procedures remain **SHADOW/conditional research**, with duration, scientific admission and current-query delivery separate. Original-site operational retention is KEEP_INCUMBENT, not proof that incumbent is globally most accurate. No new universal MAE/log-loss/two-point/four-winning-week/80%/future-wait gate was added.','',
 'Prospective confirmation remains planned and not started: no current qualified S-P inference/capture path exists yet. One primary reception contrast and a fixed six-calendar-week cohort would be frozen before future outcomes once ready, through existing jobs only. No new scheduler, backdating or later-line attachment.','',
 '## Complete permitted detail','',
 '[Machine comparison JSON.gz](COMPARISON_RESULTS.json.gz), [all products CSV](ALL_PRODUCTS.csv), [category decisions](CATEGORY_DECISIONS.json), [machine binding](COMPARISON_MACHINE_BINDING.json), [owner handoff intake](intake/HANDOFF_INTAKE_RECEIPT.json), and the existing parent [method-history entry](../METHOD_HISTORY_ENTRY.json). Historical W4–9 is exposed development. This package adds coverage for saved methods and records a runtime failure; it establishes no new simulator forecasting advantage, high-accuracy claim, future win, website release or actual wager.']
 (D/'README.md').write_text('\n'.join(lines)+'\n')
 print('COMPARISON_REPORT_VIEWS_COMPLETE',len(allstatus),len(result['scores']),len(masks),len(z))
if __name__=='__main__':main()
