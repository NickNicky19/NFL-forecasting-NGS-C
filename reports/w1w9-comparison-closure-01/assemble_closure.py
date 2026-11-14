"""Consolidated owner evidence and explicit cells; no new grader or learner."""
from pathlib import Path
from datetime import datetime,timezone
import csv,gzip,hashlib,json,lzma,collections
ROOT=Path(__file__).resolve().parents[2];BASE=Path(__file__).resolve().parent
def load(p):
 b=Path(p).read_bytes();return json.loads(gzip.decompress(b) if str(p).endswith('.gz') else lzma.decompress(b) if str(p).endswith('.xz') else b)
def bind(p):p=Path(p);return dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,SHA256=hashlib.sha256(p.read_bytes()).hexdigest())
def dump(name,d):
 p=BASE/name;p.write_text(json.dumps(d,indent=2,allow_nan=False)+'\n')
def int_or_none(v):return v if isinstance(v,int) else None
def main():
 frozen=load(BASE/'roster/FROZEN_ROSTER.json');amend=load(BASE/'roster/selected-policy-amendment-v1/ROSTER_AMENDMENT_V1_1.json');roster=frozen['candidate_products']+amend['additional_candidate_records'];assert len(roster)==143
 cmp=load(BASE/'completion/NINE_WEEK_COMPLETION.json');att=load(BASE/'attempt-check/EIGHT_WEEK_ATTEMPTS.json');old=load(ROOT/'reports/category-decision-release-01/CATEGORY_PRODUCT_DECISIONS.json')['categories']
 awp=ROOT/'reports/category-decision-release-01/follow-through-v1/peer-intake/A_WEEKLY_COVERAGE.json.xz';aw=load(awp)
 ah=load(BASE/'A-intake/NORMALIZED_COMPLETION_ROWS.json.gz');native=load(ROOT/'reports/wave-closure-next-valid-01/B-intake/NORMALIZED_COMPLETION_SIDE_AGGREGATES.json.gz')
 def cname(r):return r.get('candidate_id') or hashlib.sha256(json.dumps([r['owner'],r['category'],r['procedure_id'],r['output']],sort_keys=True).encode()).hexdigest()[:24]
 assert len({cname(r) for r in roster})==143
 def slice_a(r):
  c=r['counts'];return dict(panel=r['panel'],source=str(awp.relative_to(ROOT)),status=r['status'],evidence_tier=r['evidence_tier'],eligible=c['eligible'],available=c['available'],selected=c['selected'],decided=c['decided'],unknown=c['unknown'],unavailable=c['unavailable'],fallback=int_or_none(c.get('fallback')),games=c.get('games'),own_sides={s:r[s] for s in ['OVER','UNDER','COMBINED']},eligible_mask=r.get('eligible_mask_sha256'),source_role='Source contract preserved; not inferred from positions or output label')
 def source_lookup(r,w):
  aliases={r['procedure_id'],*r.get('original_id_aliases',[])};refs={k for k,v in aw['procedures'].items() if v['candidate_id'] in aliases}
  slices=[slice_a(z) for z in aw['rows'] if z['procedure_ref'] in refs and z['week']==w and z['status']=='SCORED_ACTUAL_LINES_TIMING_UNVERIFIED' and z['counts']['eligible']]
  unique={json.dumps(x,sort_keys=True):x for x in slices};return list(unique.values())
 cells=[]
 for r in roster:
  for w in range(1,10):
   cat=r['category'];slices=source_lookup(r,w);state='COMPLETED_NAMED_PARTIAL_SOURCE_PANEL' if slices else 'EXACT_SAVED_OUTPUT_AND_SOURCE_MEMBERSHIP_REQUIRED';owner=r['owner'];action='Owner reuse exact saved outputs on approved retained offers; verify source/history/role/output before inference or necessary origin fitting.';panel='Source-specific partial panels; no universal common nine-week board'
   if cat in ['anytime_td','nick-chart-ppr-v1']:
    state='MISSING_QUALIFIED_EXACT_MARKET';action='Existing source owner supplies inherited rush-or-rec TD actually offered side or exact nick-chart-ppr-v1 contract/components; no invented NO/Under or league-fantasy substitution.'
   if r['owner']=='website':state='ACCESS_BLOCKED_ORIGINAL_INCUMBENT_INPUT_BINDING';action='Original website owner supplies exact archived provider inputs/side/margin/fallback version; current revised projections cannot reconstruct original issuance.'
   if cat=='pass_cmp':
    hit=[x for x in cmp['rows'] if x['procedure_id']==r['procedure_id'] and x['product']==r['output']]
    if r['owner']=='control':hit=[x for x in cmp['rows'] if x['procedure_id']==r['procedure_id']]
    if hit:
     q=hit[0]['weekly'][w-1];slices=[dict(panel=cmp['id'],source='completion/NINE_WEEK_COMPLETION.json',status='COMPLETED',evidence_tier=hit[0]['source_tier'],**{k:q[k] for k in ['eligible','available','selected','decided','unknown','unavailable','fallback','games']},own_sides=q['own_sides'])];state='COMPLETED_COMMON_NINE_WEEK_DIAGNOSTIC';panel=cmp['id'];action='Completed exact panel. Preserve exposure/source limits; A/C competing later rows remain separate.'
    elif r['output'].startswith('ROLLING_TOP_K_DIAGNOSTIC') or r['output']=='P90':
     meta=r['metadata'];rows=[z for z in native if z['procedure_id']==r['procedure_id'] and z['product_id']==meta['source_product_id'] and z['week']==w and z.get('K')==meta.get('K') and z.get('rank_scope')==meta.get('rank_scope')]
     if rows:
      z=rows[0];slices=[dict(panel=z['source_panel'],source='reports/wave-closure-next-valid-01/B-intake/NORMALIZED_COMPLETION_SIDE_AGGREGATES.json.gz',status='EVALUATED_BOARD_EMPTY_POLICY_NA' if not z['selected'] else 'COMPLETED_SELECTED_POLICY_DIAGNOSTIC',eligible=z['eligible'],available=z['available'],selected=z['selected'],decided=z['combined_decided'],unknown=z['unknown'],unavailable=z['unavailable'],fallback=z['fallback'],games=z['games'],own_sides={s:{k:z[s+'_'+k] for k in ['wins','losses','decided','rate']} for s in ['over','under','combined']})];state='COMPLETED_NATIVE_SELECTED_POLICY_BOARD';panel='B_NATIVE_W5_W9_ONLY';action='Keep evaluated board weeks separate from selected/decided weeks. No W1–4 rank record borrowed.'
     else:state='READY_TO_SCORE_OWNER_LOCAL_REGISTERED_SELECTION';owner='A';action='A applies this existing frozen B ranking/gate to complete protected W1–4 board using saved laws under exact source/refresh rules; no new K/gate/fit.'
    elif r['owner']=='A' and ('CATBOOST_MEDIUM' in r['procedure_id'] or 'HGB_MAE_DIRECT' in r['procedure_id']):
     if w<=4:
      name='A::CATBOOST_MEDIUM::mean_objective_point' if 'CATBOOST_MEDIUM' in r['procedure_id'] else 'A::HGB_MAE_DIRECT::mae_objective_point';z=[z for z in ah if z['procedure_id']==name and z['comparison_mask']=='FULL_A_EARLY_BOARD' and z['week_view']==w];assert len(z)==1;z=z[0]
      slices=[dict(panel=cmp['id']+'::A_EARLY_SLICE',source='A-intake/NORMALIZED_COMPLETION_ROWS.json.gz',eligible=z['eligible'],available=z['available'],selected=z['selected'],decided=z['COMBINED']['decided'],unknown=z['unknown'],unavailable=z['unavailable'],fallback=None,reported_fallback_count=z['fallback'],fallback_attribution='Blank source flags remain UNSPECIFIED; not learned-only proof',games=z['games'],own_sides={s:z[s] for s in ['OVER','UNDER','COMBINED']})];state='COMPLETED_COMMON_PANEL_EARLY_SLICE';panel=cmp['id']
     else:state='INFERENCE_REQUIRED_OR_EXACT_SAVED_VECTOR_RECOVERY';owner='A';panel=cmp['id'];action='A authenticates retained CatBoost/HGB origin vectors/models, emits exact typed points for B native142 canonical queries; B scores on its protected later offers. Fit only a genuinely missing historical origin.'
    elif r['owner']=='C':
     extended=(BASE/'C-panels/C_RETAINED_COMPLETION_POINTS_W1_W9.json.gz').exists()
     state='READY_TO_SCORE_OWNER_LOCAL_SAVED_POINT_JOIN' if w<=7 or extended else 'HISTORICAL_FIT_REQUIRED_EXISTING_PRIMARY_HOLD';owner='A' if w<=4 else 'B' if w<=7 or extended else 'C';panel=cmp['id'];action=('Join C315 original/extended typed mean/median handoff to owner offers; C W8/W9 exact missing origins now executed, no further fit required. This distinct C contender join is not repetition of completed B84. Existing CMP/ATT coherence/conditional-population primary hold remains.' if extended else 'Join C242 original typed mean/median query handoff to owner offers; no fit for W1–7. W8–9 need exact C origins; existing CMP/ATT primary hold remains.')
    elif r['owner']=='B' and not hit:state='READY_TO_SCORE_IF_EXACT_SAVED_OUTPUT_RECOVERED';action='B resolves exact earlier/later retained product identity and emits own outputs for this same226mask; A joins early private offers. No alias/history/mean/law substitutions.'
   if cat=='pass_att' and r['procedure_id']==att['procedure_id']:
    panel=att['id']
    if w<=8:
     q=att['weekly'][w-1];slices=[dict(panel=panel,source='attempt-check/EIGHT_WEEK_ATTEMPTS.json',status='COMPLETED',evidence_tier=att['evidence_tier'],**{k:q[k] for k in ['eligible','available','selected','decided','unknown','unavailable','fallback','games']},own_sides=q['own_sides'])];state='COMPLETED_COMMON_EIGHT_WEEK_DIAGNOSTIC';action='Completed exact median, not borrowed P2-law scores.'
    else:state='EXACT_OUTPUT_OR_HISTORICAL_ORIGIN_INFERENCE_REQUIRED';owner='B';action=att['W9_action']
   if cat not in ['pass_cmp','pass_att','anytime_td','nick-chart-ppr-v1'] and not slices:
    action='Existing '+('A protected-board source/model owner' if r['owner']=='A' else 'B source/output owner' if r['owner']=='B' else 'C source/output owner' if r['owner']=='C' else 'shared source owner')+' qualifies retained real-line/output/source-role bindings for this exact week first; annual W6–7 references excluded. Existing W8 reported-line corrections remain a separate unresolved-provenance measurement panel.'
   cells.append(dict(candidate_id=cname(r),category=cat,owner=r['owner'],procedure_id=r['procedure_id'],output=r['output'],week=w,status=state,comparison_panel=panel,source_slices=slices,executor=owner,next_action=action,raw_private_access_by_C=False))
 assert len(cells)==1287
 dump('CANDIDATE_WEEK_MATRIX.json',dict(id='C-W1W9-FROZEN143-WEEK-MATRIX-v1',roster=bind(BASE/'roster/FROZEN_ROSTER_V1_1.json'),cells=cells,counts_by_status=dict(collections.Counter(x['status'] for x in cells)),source_slices_not_additive=True,no_missing_cell_imputed_zero=True))
 with (BASE/'CANDIDATE_WEEK_MATRIX.csv').open('w',newline='') as f:
  fields=['candidate_id','category','owner','procedure_id','output','week','status','comparison_panel','executor','source_slices_count','eligible','available','selected','decided','unknown','unavailable','fallback','games','next_action'];wr=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');wr.writeheader()
  for c in cells:
   z={k:c[k] for k in ['candidate_id','category','owner','procedure_id','output','week','status','comparison_panel','executor','next_action']};z['source_slices_count']=len(c['source_slices']);s=c['source_slices'][0] if len(c['source_slices'])==1 else {};z.update({k:s.get(k) for k in ['eligible','available','selected','decided','unknown','unavailable','fallback','games']});wr.writerow(z)
 # Headline rows preserve a single procedure's own sides; other source panels
 # remain linked rather than supplying missing weeks or stitched side maxima.
 headlines=[]
 for d in old:
  cat=d['category'];r=dict(category=cat,origin=d['origin'],exact_procedure=d['exact_procedure'],output=d['output'],decision_policy=d['decision_policy'],actual_weeks=d['actual_weeks_by_season'].get('2026',[]),own_sides={s.lower():d[s] for s in ['OVER','UNDER','COMBINED']},coverage=d['coverage'],matched_control=d['controls'],uncertainty=d['uncertainty'],evidence_tier=d['evidence_tier'],recommendation=d['decision'],actual_live_method=d['actual_live_method'],source_panel='A_SOURCE_BOUND_ANNUAL_W1_W5' if cat not in ['rec','anytime_td','nick-chart-ppr-v1'] else 'A_C_WRTE_COMMON_W1_W5' if cat=='rec' else 'NO_QUALIFIED_EXACT_MARKET',nine_week_status='PARTIAL;actualW1–5;W6–9same-procedure real-line/source/output bindings missing',five_week_status=d['five_week_status'],operational_readiness=d['current_query'],source='reports/category-decision-release-01/CATEGORY_PRODUCT_DECISIONS.json',exact_next_action=d['remaining_owner_action'],no_global_cross_panel_winner=True)
  if cat=='pass_cmp':
   q=[q for q in cmp['rows'] if q['procedure_id'].endswith(':B2') and q['product']=='P2_STATISTICAL_LAW'][0]
   r.update(origin='B',exact_procedure=q['procedure_id'],output='TIED_P1_LOWER_MEDIAN_AND_P2_STATISTICAL_LAW',decision_policy='Separate strict saved lower-median crossing and strict max(POver,PUnder) law policies; no router; identical observed side record',actual_weeks=list(range(1,10)),own_sides=q['own_sides'],coverage=q['coverage'],matched_control={'ALWAYS_OVER':{'wins':115,'decided':226,'win_change':7},'B0_P1_MEAN':{'wins':119,'decided':226,'win_change':3},'B0_SAME_LAW':{'wins':117,'decided':226,'win_change':5}},uncertainty='Paired week-count 95% sensitivity: vsB0mean −2.03..+4.89pp;vsAlwaysOver −4.90..+10.60pp;9exposedclusters. Rawgame/pairdisagreements unavailable.',evidence_tier=q['source_tier'],recommendation='SHADOW',source_panel=cmp['id'],nine_week_status='COMPLETE_NINE_WEEK_NAMED_PANEL_FOR_6_B_PRODUCTS_AND_CONSTANTS;FULL_CROSS_SESSION_PARTIAL',five_week_status='Nine diagnostic actual-line blocks; durationonly, quote/source/mainline/admission limits remain',operational_readiness='No current admitted B2 native product/consumer; not a new primary switch',source='completion/NINE_WEEK_COMPLETION.json',exact_next_action='A supplies CatBoost/HGB points on B later142; B grades them on its same offers. Existing Cpoint handoff must be joined; held C W8–9 origins remain separate. B2 mean failure preserved.')
  if cat=='pass_att':
   r.update(actual_weeks=list(range(1,9)),own_sides=att['own_sides'],coverage=att['coverage'],matched_control=att['matched_controls'],uncertainty='Eight exposed weekclusters; median tiesAlwaysUnder; native savedadjusted69/112 exceedsmedian55/112 onlatermask; no fullreferenceunion',evidence_tier=att['evidence_tier'],recommendation='KEEP_INCUMBENT',source_panel=att['id'],nine_week_status='PARTIAL_W1_W8;W9exactoutput/scoremissing_30realoffersalreadyavailable',five_week_status='Eight diagnostic actual-line blocks; not primaryadmission',source='attempt-check/EIGHT_WEEK_ATTEMPTS.json',exact_next_action=att['W9_action'])
  if cat not in ['pass_cmp','pass_att','anytime_td','nick-chart-ppr-v1']:
   r['delivery_remaining_owner_action']=r['exact_next_action']
   sourceowner='B native QB offer owner' if cat.startswith('pass_') else 'A protected offer/source owner'
   modelowner='C receiving owner' if cat=='rec' else 'A retained method owner'
   r['exact_next_action']=sourceowner+' qualifies exact later W6–9 real-line/source/role/horizon bindings for '+cat+'; '+modelowner+' reuses saved outputs, then origin inference or only necessary missing fits, and designated offer owner scores the frozen contenders on a stable common panel. Annual W6–7 references and unresolved-provenance W8 controls do not silently fill actual offers. Existing delivery action stays separate.'
  if cat in ['anytime_td','nick-chart-ppr-v1']:r.update(nine_week_status='SOURCE_BLOCKED;noqualifiedexactofferpanel',exact_next_action='Existing source owner qualifies exact inherited TD offered side or exact chart contract/components; no invented Under/NO or alternate fantasy system.')
  c=r['own_sides']['combined'];u=r['coverage'].get('unknown')
  r['unresolved_selected_accuracy_sensitivity_if_all_become_decided']=[c['wins']/(c['decided']+u),(c['wins']+u)/(c['decided']+u)] if c and isinstance(u,int) and u>0 else None
  headlines.append(r)
 dump('TWELVE_CATEGORY_HEADLINE.json',dict(id='C-W1W9-RELEASE-ROSTER-HEADLINE-v1',scope='Scoped observed leaders/partial recommendations; not a complete12categorynineweekchampionship or activation',rows=headlines,known_incomplete_roster_rows_remain_visible=True,original_website_modified=False,new_primary_switches=0))
 # Selective views were registered before this comparison; preserve all, not
 # whichever tiny bucket wins. Empty gates have N/A accuracy.
 selected=[]
 for r in amend['additional_candidate_records']:
  m=r['metadata'];rr=[x for x in native if x['procedure_id']==r['procedure_id'] and x['product_id']==m['source_product_id'] and x.get('K')==m.get('K') and x.get('rank_scope')==m.get('rank_scope')];whole=[x for x in rr if x['week']=='ALL'];assert len(whole)==1;z=whole[0];decweeks=[x['week'] for x in rr if isinstance(x['week'],int) and x['combined_decided']];selweeks=[x['week'] for x in rr if isinstance(x['week'],int) and x['selected']]
  selected.append(dict(candidate_id=cname(r),procedure_id=r['procedure_id'],policy=r['output'],evaluated_board_weeks=[5,6,7,8,9],selected_weeks=selweeks,decided_weeks=decweeks,source_sides=z,accuracy=z['combined_wins']/z['combined_decided'] if z['combined_decided'] else None,missing_weeks=[1,2,3,4],nine_week_status='PARTIAL_NOT_NINE_WEEK_POLICY',duration_policy='Existing policy/week-count rule unchanged; evaluatedboards,selectedweeks,decidedweeks distinguished. Emptyselectedgate cannotestablish accuracy.',next_action='A executes exact frozenselectionon earlycompleteprotectedboard withsavedlaws; no newK/gates orfit.'))
 dump('SELECTIVE_POLICY_STATUS.json',dict(id='C-W1W9-EXISTING-SELECTIVE-STATUS-v1',rows=selected,nine_week_selected_winner='NOT_ESTABLISHED',other_categories='Existing registered selected contenders retained in frozen roster and source-bound category records; no new ranker/threshold. Website exact TopPicks separate.',website='Preserve conditional5week fullpolicy SHADOW,10candidate100fallback; BnewW4reviewcomplete.'))
 print(json.dumps({'headline_categories':len(headlines),'candidate_week_cells':len(cells),'source_policy':'Aearly/Bnative calendarfixed; noAannualW5','new_fits':0}))
if __name__=='__main__':main()
