"""Reuse already-reported leaders to propose a finite comparison roster.

No NFL scoring, model selection on new outcomes, network calls or fitting.
This is a proposal for the coordinator to freeze, not an activated roster.
"""
import collections,gzip,hashlib,json,re,time
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
def load(p):
 p=ROOT/p;b=p.read_bytes();return json.loads(gzip.decompress(b) if p.suffix=='.gz' else b)
def bind(p):
 p=ROOT/p;return dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,SHA256=hashlib.sha256(p.read_bytes()).hexdigest())
def dump(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
start=time.process_time()
MASTER='reports/category-decision-release-01/CATEGORY_PRODUCT_DECISIONS.json'
QUAL='reports/abc-championship/execution-closure-02/QUALIFICATION_TABLE.json.gz'
SIDE='reports/abc-championship/execution-closure-02/SIDE_QUALIFICATION_AND_LEADERS.json'
BLEAD='reports/abc-championship/continuation-v2/B_SOURCE_STRATIFIED_RAW_LEADERS.json.gz'
NATIVE='reports/abc-championship/METHOD_ROSTER-v2-C-1.json'
CTX='reports/player-context-matchup-01/ACTUAL_LINE_SCORES.json.gz'
master=load(MASTER);qual=load(QUAL)['rows'];catmeta={r['category']:r for r in master['categories']};candidates={}
def normA(pid,cat,out):
 parts=pid.split('::');h=next((x for x in parts if re.fullmatch('[a-f0-9]{64}',x)),None)
 if h and parts[0]=='A':
  alias=next((x for x in parts[2:] if x!=h and x!=out),None)
  if alias:return f'A::{cat}::{h}::{alias}::{out}'
 return pid
def add(owner,cat,pid,out,reason,source,history=None,scope=None,policy=None,status='RETAINED_SUPPORTED_PARTIAL',priority='SECONDARY_EXISTING_CONTENDER',extra=None):
 if pid is None:return
 original=pid;pid=normA(pid,cat,out) if owner=='A' else pid
 key=(owner,cat,pid,out,history or '')
 if key in candidates:
  r=candidates[key];r['reasons_for_inclusion']=sorted(set(r['reasons_for_inclusion']+[reason]));r['source_paths']=sorted(set(r['source_paths']+[source]));r['original_id_aliases']=sorted(set(r['original_id_aliases']+[original]));return
 cm=catmeta[cat];role=scope or cm.get('role_scope')
 candidates[key]=dict(owner=owner,category=cat,procedure_id=pid,output=out,history=history,role_scope=role,decision_or_ranking_rule=policy,abstention='Preserve bound source rule; technical unavailable is never intentional abstention',fallback='Preserve exact saved full-system contract; never infer missing flags as zero or replace unseen support. Exact binding below/owner needed.',origin_repository={'A':'NickNicky19/NFL-forecasting','B':'NickNicky19/NFL-forecasting-V2','C':'NickNicky19/NFL-forecasting-NGS-C','website':'NickNicky19/nicks-expert-nfl-picks','control':'COMMON_REGISTERED_CONTROLS'}[owner],retained_C_tree_commit='1bd6d071e2083ae060e601da0ac8c281296babc5',origin_executing_code_commit=None,information_cutoff='Eligible earlier information under the exact origin/history policy; current-vintage reconstruction clocks remain assumptions unless authenticated',reasons_for_inclusion=[reason],source_paths=[source],original_id_aliases=[original],status=status,priority=priority,metadata=extra or {})
# Primary complete-direction leaders and ties; no new result search.
for c,r in catmeta.items():
 pid=r.get('exact_procedure');out=r.get('output')
 add(r.get('origin') or 'A',c,pid,out,'Existing category decision complete-procedure leader/scoped recommendation',MASTER,r.get('history_policy'),r.get('role_scope'),r.get('decision_policy'),priority='PRIMARY_EXISTING_LEADER_OR_TIE')
 for pid in (r.get('preferred_eligible_candidate') or {}).get('tied_candidate_set',[]):
  out=pid.split('::')[-1];add('A' if pid.startswith('A::') else r.get('origin'),c,pid,out,'Existing exact-panel tied complete-procedure leader',MASTER,r.get('history_policy'),r.get('role_scope'),r.get('decision_policy'),priority='PRIMARY_EXISTING_LEADER_OR_TIE')
 for panel in r.get('highest_observed_panels',[]):
  if panel.get('procedure_id'):
   pp=panel['procedure_id'];oo=panel.get('output') or pp.split('::')[-1]
   add(panel.get('origin') or r.get('origin'),c,pp,oo,'Earlier reported complete leader on a distinct archived panel; retained as a scoped contender, not nine-week winner',MASTER,r.get('history_policy'),panel.get('role_scope') or r.get('role_scope'),r.get('decision_policy'),extra={'panel_id':panel.get('panel_id'),'source_week_qualification':panel.get('source_week_qualification'),'no_automatic_union':True})
  if panel.get('panel_id','').startswith('C_NATIVE'):
   for q in panel.get('records',[]):
    if q.get('method') in ['P1_MEAN','P1_MEDIAN','P2_LAW','P3_DIRECT']:
     add('C',c,q['procedure_id'],q['method'],'Retained native C full-board point/law/direct contrast; source-specific competitor to A/B',MASTER,'H-MULTI/E0_OP exact saved v2.1 contract',q.get('role_scope'),'Exact selector encoded in procedure_id; point crossing or saved exact law as typed',extra={'source_native_weeks':[2,3],'source_tier':panel.get('evidence_tier')})
# Reported A own-side leaders are complete procedures, never side-stitched routers.
for r in load(SIDE):
 for q in r['raw_observed']:
  if q.get('method') in ['ALWAYS_OVER','ALWAYS_UNDER']:continue
  c=r['category'];p=f"A::{c}::{q['procedure_id']}::{q['method']}::{q['output']}"
  add('A',c,p,q['output'],'Already-published own-'+r['side']+' leader; evaluate its entire own-side policy, never stitch side maxima',SIDE,catmeta[c].get('history_policy'),catmeta[c].get('role_scope'),catmeta[c].get('decision_policy'),extra={'own_side_leader_scope':r['side'],'reported_weeks_are_not_requalified_here':q.get('scored_weeks')})
# Existing multiweek B point leaders and W6/W7 exact-law leaders. W8 is not the filter.
for g in load(BLEAD):
 st=[json.loads(x) for x in g['stratum']]
 wanted=st[0]=='B_W5_W7_POINT' or st[0] in ['B_W6_COMPLETE_LAW','B_W7_COMPLETE_LAW'] and st[3]=='H-MULTI'
 if not wanted or g['side']!='COMBINED':continue
 for q in g['raw_observed_ties']:
  c=q.get('target') or st[2];pid=q['procedure_id'];out=q.get('product_id');h=q.get('history_regime')
  if c not in catmeta:continue
  add('B',c,pid,out,'Already-published B source-stratified complete-direction/law leader or tie; not screened solely by W8',BLEAD,h,'QB' if c.startswith('pass_') else 'Exact admitted B source roles','Preserve source point or exact-law rule; bound policy witnesses below',extra={'source_panels':[st[0]],'source_stratum':st,'probability_not_inferred_from_point':True})
# Newer already-tested completion pair and leading opportunity median.
for arm in ['B0','B2']:
 for product in ['P1_MEAN','P1_LOWER_MEDIAN','P2_STATISTICAL_LAW']:
  add('B','pass_cmp','B-FTN-BALL-QUALITY-COMPLETION-v1:'+arm,product,'Existing unchanged R3/FTN completed controlled comparison; B2 loss preserved, no new fit authorized by inclusion','reports/wave-closure-next-valid-01/B-intake/ADMISSION.json','H-RECENT; source registered frozen settings and last8 eligible QB appearances','QB','Typed source mean/lower-median crossing, or exact statistical law; ties/unknowns preserved',priority='PRIMARY_COMPLETION_EXACT_VERSION',extra={'B1':'Support-equivalent B0 alias, not independent product/fit','origin_publication_commit':'d79acddf5f094c85001c9b17a525ac7d9e25f9ec'})
# C receiving products with genuine point-v-law/partial-pooling distinctions.
for method in ['P1','P2']:
 for output in ['mean','median']:
  add('C','rec',f'C::PLAYER-CONTEXT-MATCHUP-01::v1.1::{method}::{output}',output,'Retained pooled/partially pooled receiving comparison; means and medians remain distinct products',CTX,catmeta['rec']['history_policy'] if method=='P1' and output=='mean' else 'Exact C01 v1.1 earlier-origin seven-day reconstruction','WR/TE','Unrounded typed point versus exact line; equal abstain',priority='PRIMARY_RECEIVING_RETAINED',extra={'method_label_requires_exact_saved_binding':method,'no_new_fits':True})
 add('C','rec',f'C::PLAYER-CONTEXT-MATCHUP-01::v1.1::{method}','POISSON_LAW','Retained receiving pooled/partially pooled probability-law endpoint, not inferred from point handoff','reports/player-context-matchup-01/OWNER_EXPORT.json','Exact C01 v1.1 earlier-origin seven-day reconstruction','WR/TE','Saved supported Poisson law evaluated at exact line, integer push mass retained',status='NATIVE_LAW_AVAILABLE_LONGER_BOARD_PROBABILITY_NOT_INHERITED',extra={'native_source_method':method})
for item in load(NATIVE):
 if item.get('local_alias')=='EARLIER_PREVALENCE_V8':
  for c in item['categories']:
   add('C',c,item['procedure_id'],item['output_type'],'Retained earlier-only role-prevalence strong football control',NATIVE,item.get('history'),'Exact source role/mask','Original earlier-only prevalence event/side rule; not future labels',priority='REQUIRED_MATCHED_CONTROL')
# User specifically requests supported C completion point control, not a fabricated tested leader.
for output in ['NUMERICAL_EXPECTED_MEAN','NUMERICAL_MEDIAN']:
 add('C','pass_cmp','C::C-ALL12-LAW-THRESHOLD-v2.1::P2_LEAF::H-MULTI::E0_ENV',output,'Existing C retained historical-origin point output admitted only as a limited pending actual-line baseline',QUAL,'H-MULTI','QB at offered-player join; historical query source is stat-row conditioned','STRICT_TYPED_POINT_VS_LINE_IF_COMPARISON_ACCEPTED',status='UNTESTED_ACTUAL_OFFERS_HOLD_CMP_ATT_COHERENCE;STAT_ROW_CONDITIONED;W8_W9_ORIGIN_GAPS',priority='PRIMARY_COMPLETION_HOLD_CONTROL',extra={'W1_W7':'Retained safe origin outputs; parent C panel owner preparing handoff','W8_W9':'Inference/fit required only after actual origin model inventory; never assume saved models','law_not_promoted':'No probability product inferred from these point exports'})
# Distinct selection policies stay outside broad-board leader calculation.
add('A','rush_att','BACKFIELD_CDF_P2_TOP6','EXACT_LAW_P2_DIRECTION_AND_FROZEN_TOP6','Existing registered selective rushing policy; preserve 2023 failure and 2024/2026 source tiers','reports/wave-closure-next-valid-01/A-intake/README.md','Exact retained original law/ranking/refit policy','Exact mixed QB/RB source scope','Frozen Top6 eligible law confidence/ranking/ties; no forced picks',status='RETAINED_SELECTIVE_SOURCE_LIMITED')
for k in [6,10,20]:
 add('C','rec','C::C-ALL12-LAW-THRESHOLD-v2.1/P3_HGB/H-MULTI/E0_OP/P3_DIRECT',f'REGISTERED_TOP{k}','Existing registered category selective policy; not website cross-category selector','reports/topk-reference-v9/WEEKLY_RESULTS.json.gz','H-MULTI/E0_OP','Source roles and admitted mask','Original TopK schedule, own side/ranking/fallback/tie policy',status='RETAINED_SELECTIVE_SOURCE_LIMITED')
# Market-assisted old controls are already reported; no new acquisition or model.
for c,pid in [('pass_att','A::opportunity-four-ou-v1::P2_CONDITIONAL_M'),('rec','A::opportunity-four-ou-v1::P1_M')]:
 add('A',c,pid,'RETAINED_SELECTED_MARKET_OR_HYBRID_RULE','Already-reported selective market/hybrid contender; source/price role must remain distinct','reports/abc-championship/shared-intake-v3/HISTORICAL_RAW_LEADERS.json.gz','Retained original F model-year2024 history and calibration','Original exact offered-source role scope','Retained saved complete selection rule, no new price/odds inference',status='RETAINED_SELECTIVE_SOURCE_LIMITED')
# Basic controls and exact incumbent are mandatory, with source gaps visible.
for c,r in catmeta.items():
 if c in ['anytime_td','nick-chart-ppr-v1']:
  add('control',c,'NO_QUALIFIED_ACTUAL_OFFER_PRODUCT',None,'Required target retained; no invented Anytime NO/Under or substitute fantasy contract',MASTER,None,r.get('role_scope'),'No actual-line decision possible without exact offered contract',status='SOURCE_BLOCKED_EXACT_OFFER_CONTRACT',priority='REQUIRED_MISSING_TARGET')
 else:
  for side in ['OVER','UNDER']:
   add('control',c,'COMMON::ALWAYS_'+side,'CONSTANT_SIDE','Required same-panel simple control; not automatic live recommendation',MASTER,'NONE',r.get('role_scope'),'Select '+side+' on every eligible qualified opportunity; push/unknown remain distinct',priority='REQUIRED_MATCHED_CONTROL')
 add('website',c,'sleeper-matchup-classic-presence-strict-v2','SAVED_ADJUSTED_REFERENCE_POINT','Exact installed incumbent comparator where original historical inputs qualify; installed does not mean proven best','reports/category-decision-release-01/website/LIVE_PRODUCT_BINDINGS.json','Retained original source/observation history, no reconstruction from today revised provider projections',r.get('role_scope'),'Actual source-bound consumer side/margin/abstention/fallback policy, separately typed from strict research crossing',status='PARTIAL_ORIGINAL_INPUT_HISTORY_REQUIRED',priority='REQUIRED_INCUMBENT')
# Attach exact inherited binding witnesses where present; never upgrade missing fields.
def matches(r,c):
 if r['owner']!=c['owner'] or r['category']!=c['category']:return False
 if r['procedure_id'] in c['original_id_aliases'] or r['procedure_id']==c['procedure_id']:return True
 hashes=re.findall('[a-f0-9]{64}',c['procedure_id'])
 return bool(hashes and any(h in r['procedure_id'] for h in hashes))
for c in candidates.values():
 ws=[r for r in qual if matches(r,c)]
 compact=[]
 for r in ws:
  compact.append({k:r.get(k) for k in ['row_id','procedure_id','product','history','role_scope','policy','source_panel','evidence_tier','source_artifacts','metadata','tested_season_weeks']})
 c['retained_binding_witnesses']=compact
 c['binding_status']='EXACT_SAVED_ARTIFACT_AND_POLICY_WITNESSES;ORIGIN_EXECUTION_SCOPE_STILL_OWNER_BOUND' if compact else 'OWNER_EXACT_BINDING_REQUIRED_OR_SEPARATE_SOURCE_RECEIPT'
 c['missing_fields']=['Exact executing code/model/corrector feature-order and original availability bindings must resolve from owner artifact before new inference; publication tree is not fresh-fit parity.']
 if not c['history']:c['missing_fields'].append('Training/update history not located for this declared candidate; owner must bind or label inapplicable.')
 if not c['decision_or_ranking_rule']:c['missing_fields'].append('Exact side/ranking/abstention rule not located; no guessed substitution.')
 c['candidate_id']='W1W9-'+hashlib.sha256(json.dumps({k:c[k] for k in ['owner','category','procedure_id','output','history']},sort_keys=True).encode()).hexdigest()[:20]
ordered=sorted(candidates.values(),key=lambda c:(list(catmeta).index(c['category']),c['priority'],c['owner'],c['procedure_id'],str(c['output']),str(c['history'])))
sources=[MASTER,QUAL,SIDE,BLEAD,NATIVE,CTX,'reports/wave-closure-next-valid-01/B-intake/ADMISSION.json','reports/category-decision-release-01/website/LIVE_PRODUCT_BINDINGS.json']
proposal=dict(id='ABC-W1W9-C-EXISTING-CONTENDER-PROPOSAL-v1',state='DRAFT_FOR_COORDINATOR_FREEZE_BEFORE_NEW_COMPARATIVE_SCORING',generated_UTC=datetime.now(timezone.utc).isoformat(),scope='Finite already-reported leaders/ties, point/probability/selective contrasts and mandatory controls; not every8072 historical alias or new algorithm search.',source_policy_constraints=['A annual W1–5 retained actual lines; older mixed W6–7 references never fill actual offers','Different books/sources may form a named compatible diagnostic union after identity/target/line/horizon selection/deduplication; not prohibited merely by source name','Native B later real-line panels remain distinct until exact common policy established','Unknown main/alternate and clocks remain unknown; no original live claim from reconstruction','No common ranking from disconnected pairwise masks; no chosen Over/Under router'],counts=dict(candidate_products=len(ordered),by_owner=dict(collections.Counter(c['owner'] for c in ordered)),by_category=dict(collections.Counter(c['category'] for c in ordered)),by_priority=dict(collections.Counter(c['priority'] for c in ordered))),candidate_products=ordered,source_bindings=[bind(s) for s in sources],aliases='Only identical category/owner/procedure/output/history keys deduplicated; source witnesses preserved. Mean, median, law and selected policies are distinct. Source policy/history variants remain distinct until parity established.',new_scores=0,new_fits=0,new_source_reads=0,CPU_seconds=time.process_time()-start)
dump(HERE/'DRAFT_ROSTER.json',proposal)
dump(HERE/'MISSING_BINDINGS.json',dict(id='W1W9-CANDIDATE-BINDING-GAPS-v1',rows=[dict(candidate_id=c['candidate_id'],owner=c['owner'],category=c['category'],procedure_id=c['procedure_id'],output=c['output'],binding_status=c['binding_status'],missing_fields=c['missing_fields'],next_executor=c['owner'],minimum_action='Use existing immutable owner saved-output/model/contract binding first; no new refit merely for report formatting.') for c in ordered]))
dump(HERE/'REGISTRATION.json',dict(id='C-W1W9-ROSTER-RECONCILIATION-v1',scope='Local proposal only; no scorer/model/source calls',CPU_seconds_limit=90,RSS_bytes_limit=1073741824,retention_bytes_limit=3145728,network_reads=0,NFL_fits=0,new_score_calculations=0,measured_CPU_seconds=time.process_time()-start))
print(json.dumps(proposal['counts']))
