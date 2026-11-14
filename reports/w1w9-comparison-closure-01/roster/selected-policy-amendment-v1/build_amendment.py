"""Restore omitted existing selected-policy IDs before any new union scoring.

Adds the entire registered 2 x (3K x 3 scopes + P90) set, never winners.
References the unchanged 123-product base instead of duplicating its wire.
No source calls, model fitting or comparative score calculations.
"""
import copy,gzip,hashlib,json,time
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[4];HERE=Path(__file__).resolve().parent
BASE=ROOT/'reports/w1w9-comparison-closure-01/roster/FROZEN_ROSTER.json'
NORM=ROOT/'reports/wave-closure-next-valid-01/B-intake/NORMALIZED_COMPLETION_SIDE_AGGREGATES.json.gz'
RAW=ROOT/'reports/wave-closure-next-valid-01/B-intake/SCORES_SOURCE.json.gz'
EXPECTED='85ae5c3b263d05d4fafe11294877e88147450fad3f6b38a79810da2e71cac97e'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def bind(p):return dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,SHA256=sha(p))
def dump(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
start=time.process_time();assert sha(BASE)==EXPECTED,'BASE_ROSTER_CHANGED'
base=json.loads(BASE.read_bytes());assert len(base['candidate_products'])==123
norm=json.loads(gzip.decompress(NORM.read_bytes()));raw=json.loads(gzip.decompress(RAW.read_bytes()))
assert len(norm)==204
records=[];identities=[]
for arm in ['B0','B2']:
 pid='B-FTN-BALL-QUALITY-COMPLETION-v1:'+arm
 specs=[('ROLLING_TOP_K_DIAGNOSTIC',k,scope) for k in [6,10,20] for scope in ['Combined','over','under']]+[('P90',None,None)]
 template=next(r for r in base['candidate_products'] if r['procedure_id']==pid and r['output']=='P2_STATISTICAL_LAW')
 for product,k,scope in specs:
  witnesses=[r for r in norm if r['procedure_id']==pid and r['product_id']==product and r.get('K')==k and r.get('rank_scope')==scope and r['week'] in [5,6,7,8,9,'ALL']]
  assert len(witnesses)==6 and {r['week'] for r in witnesses}=={5,6,7,8,9,'ALL'}
  rw=[r for r in raw if r['procedure_id']==pid and r['product_id']==product and r.get('K')==k and r.get('rank_scope')==scope and r['week']=='ALL' and r.get('side')=='Combined' and r.get('cohort_id')=='ALL']
  assert len(rw)==1
  output=product if product=='P90' else f'{product}::K{k}::{scope}'
  c=copy.deepcopy(template);c.update(output=output,priority='REQUIRED_EXISTING_SELECTED_CONTENDER',status='EXISTING_SELECTED_POLICY_SOURCE_LIMITED;W1_W4_POLICY_SCORES_MISSING',decision_or_ranking_rule=f'Existing B registered {product}, K={k}, rank_scope={scope}; preserve original exact code/side/ranking/tie/rolling schedule. This amendment neither reimplements nor changes that policy.',reasons_for_inclusion=['Pre-score correction of omission: already-registered selected-pick endpoint required by parent assignment; all18TopK and2P90 cells included without viewing new comparative gains.'],source_paths=[str(NORM.relative_to(ROOT)),str(RAW.relative_to(ROOT))],original_id_aliases=[pid],retained_binding_witnesses=[])
  c['metadata'].update(source_product_id=product,K=k,rank_scope=scope,registered_evaluated_weeks=[5,6,7,8,9],native_source_panel='B_FTN_INFORMATION_142_W5_W9_v1',no_w1_w4_selected_policy_coverage_borrowed=True,not_website_complete_Top_Picks=True,source_record_id=rw[0]['record_id'],source_horizon_id=rw[0]['horizon_id'],source_period=rw[0]['period'],source_statistic_period=rw[0]['statistic_period'],source_settlement_status=rw[0].get('settlement_status'),query_membership_sha256=rw[0]['query_membership_sha256'],source_definition_limit='Metadata supplies registered policy ID/K/scope and bindings. Exact ranking/tie/boundary code is not restored here; use the existing B implementation rather than invent a comparator or gate.')
  c['metadata']['identity_witnesses']=[dict(source_row_index=norm.index(r),week=r['week'],time_panel_id=r['time_panel_id'],query_membership_sha256=r['query_membership_sha256']) for r in witnesses]
  if product=='P90':
   # This empty policy's support is already a preserved prior-wave finding.
   # Do not confuse evaluation weeks with weeks containing scored decisions.
   assert rw[0]['unique_weeks']==0 and rw[0]['selection_metrics']['denominators']['outer_rows']==0 and rw[0]['selection_metrics']['denominators']['decided']==0 and rw[0]['selection_metrics']['hit_rate'] is None
   c['metadata'].update(previously_reported_selected=0,decision_weeks=[],decided_weeks=[],accuracy=None,empty_denominator='N/A;not90percent',duration='Five evaluated native boards, zero decision/scored blocks; no actual-pick primary qualification from empty selections.',source_normalized_actual_scored_weeks_label='Preexisting normalized rows carry[5..9] here as evaluated weeks; original raw unique_weeks=0. Source retained unchanged, no duration/decision claim.')
  c['candidate_id']='W1W9-'+hashlib.sha256(json.dumps({key:c[key] for key in ['owner','category','procedure_id','output','history']},sort_keys=True).encode()).hexdigest()[:20]
  identities.append((pid,product,k,scope));records.append(c)
assert len(records)==20 and len(set(identities))==20
allids=[r['candidate_id'] for r in base['candidate_products']]+[r['candidate_id'] for r in records];assert len(allids)==143==len(set(allids))
counts=copy.deepcopy(base['counts']);counts['candidate_products']=143;counts['by_owner']['B']+=20;counts['by_category']['pass_cmp']+=20;counts['by_priority']['REQUIRED_EXISTING_SELECTED_CONTENDER']=20
now=datetime.now(timezone.utc).isoformat()
proposal=dict(id='ABC-W1W9-C-ROSTER-v1.1-SELECTED-ENDPOINT-OMISSION-ADDENDUM',version='1.1',state='PROPOSED_BEFORE_NEW_UNION_SCORING;COORDINATOR_APPROVAL_REQUIRED',created_UTC=now,base_roster=bind(BASE),base_candidate_products=123,additional_candidate_products=20,effective_candidate_products=143,effective_counts=counts,reason='Initial freeze omitted explicit already-registered completion B0/B2Top6/10/20 andP90 endpoints. This restores required existing policies before any new comparison, without new algorithms/K/gates or gain-based expansion.',resolution='Effective v1.1 roster is the original123 candidate_products followed by these20 additional_candidate_records. The original frozen v1wire remains unchanged; coordinator may materialize and freeze this exact concatenation.',additional_candidate_records=records,source_bindings=[bind(NORM),bind(RAW)],new_comparative_scores_inspected=0,new_fits=0,new_source_reads=0,new_hyperparameters_or_selection_rules=0,old_loss_records_preserved=True,CPU_seconds=time.process_time()-start)
(HERE/'ROSTER_AMENDMENT_V1_1.json').write_text(json.dumps(proposal,separators=(',',':'),allow_nan=False)+'\n')
dump(HERE/'IDENTITY_CHECK.json',dict(id='C-W1W9-SELECTED-OMISSION-IDENTITY-CHECK-v1',checked_UTC=now,status='PASS_IDENTITY_SCOPE_ONLY',base_roster_sha256_unchanged=sha(BASE),base_entries=123,topk_entries=18,p90_entries=2,effective_entries=143,all_candidate_ids_unique=True,complete_registered_cross_product=True,all20_prior_native_policy_cells_have_six_identity_witnesses=True,no_metric_winner_screening=True,new_comparative_scores_inspected=0,new_fits=0,new_source_reads=0,empty_P90='Evaluated W5–9;zero decisions/decisionweeks;accuracyN/A',definition_limit='Exact upstream selector implementation still owner-bound; no new tie/boundary/schedule invented.'))
dump(HERE/'REGISTRATION.json',dict(id='C-W1W9-SELECTED-POLICY-OMISSION-REPAIR-v1',registered_before_new_union_scoring=True,parent_executor_authorized_scope='Add only existing18TopK+2P90 IDs; no new candidate mechanisms',CPU_seconds_limit=30,RSS_bytes_limit=268435456,additional_retention_bytes_limit=131072,network_reads=0,new_fits=0,new_score_calculations=0))
print(json.dumps({'base':123,'added':20,'effective':143,'base_sha_unchanged':sha(BASE),'amendment_sha':sha(HERE/'ROSTER_AMENDMENT_V1_1.json')}))
