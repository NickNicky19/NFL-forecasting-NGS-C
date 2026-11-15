"""Independent public arithmetic/binding check; no fitting, grading, acquisition."""
from pathlib import Path
from decimal import Decimal
from collections import defaultdict
import csv, gzip, hashlib, io, json, re, time, datetime
from urllib.parse import unquote
R=Path(__file__).resolve().parents[4]
D=R/'reports/targeted-accuracy-w1w9-01/checkpoint-closure-01'

def read(p):
 p=Path(p);b=p.read_bytes();return json.loads(gzip.decompress(b) if p.suffix=='.gz' else b)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def bind(p):p=Path(p);return {'path':str(p.relative_to(R)),'bytes':p.stat().st_size,'SHA256':sha(p)}
def main():
 started=time.process_time();a=read(D/'intake/A_RECEIPT.json');b=read(D/'intake/B_RECEIPT.json')
 A=gzip.decompress((D/'intake/A_EXECUTED_M1_CHECKPOINT_V1.md.gz').read_bytes()).decode()
 B=gzip.decompress((D/'intake/B_README.md.gz').read_bytes()).decode()
 assert hashlib.sha256(A.encode()).hexdigest()==a['actual_public_receipt']['SHA256']
 rb=next(x for x in b['obtained'] if x['source_path'].endswith('/README.md'))
 assert hashlib.sha256(B.encode()).hexdigest()==rb['source_SHA256']
 old,new,used,reserve=map(Decimal,['1200','1800','1000.166','120'])
 assert new-old==600 and old-used==Decimal('199.834') and new-used==Decimal('799.834') and new-used-reserve==Decimal('679.834')
 assert 'unmetered tail' in A and 'not a complete' in A and 'It has not been executed on NFL data' in A
 table=[]
 rate=re.compile(r'^(\d+)–(\d+)/(\d+)/(\d+\.\d+)%$')
 for line in B.splitlines():
  if not re.match(r'^\| (M2_|D_M2\s*\||UNCHANGED_ATT\s*\|)',line):continue
  c=[x.strip() for x in line.split('|')[1:-1]]
  if len(c)!=9:continue
  parsed=[]
  for s in c[3:6]:
   z=rate.match(s);assert z,(c,s)
   w,l,n=int(z[1]),int(z[2]),int(z[3]);p=Decimal(z[4]);assert w+l==n and abs(Decimal(w)*100/n-p)<=Decimal('.0051')
   parsed.append({'wins':w,'losses':l,'decided':n,'rate':str(Decimal(w)/n)})
  o,u,total=parsed;assert o['wins']+u['wins']==total['wins'] and o['losses']+u['losses']==total['losses'] and total['decided']==142
  table.append({'method':c[0],'product':c[1],'period':c[2],'OVER':o,'UNDER':u,'COMBINED':total,'MAE':None if c[6]=='N/A' else c[6],'Brier':c[7],'log_loss':c[8]})
 assert len(table)==24,len(table)
 lookup={(x['method'],x['product']):x for x in table}
 effects=[]
 for parent in ['P2','C1','C2']:
  for product in ['MEAN','MEDIAN','LAW']:
   x,y=lookup[(f'M2_{parent}_BIN',product)],lookup[(f'M2_{parent}_BB',product)]
   assert [x[s] for s in ['OVER','UNDER','COMBINED']]==[y[s] for s in ['OVER','UNDER','COMBINED']]
   if product=='MEAN':assert x['MAE']==y['MAE']
  x,y=lookup[(f'M2_{parent}_BIN','LAW')],lookup[(f'M2_{parent}_BB','LAW')]
  effects.append({'parent':parent,'delta_wins':0,'delta_Brier_BB_minus_BIN':str(Decimal(y['Brier'])-Decimal(x['Brier'])),'delta_log_loss_BB_minus_BIN':str(Decimal(y['log_loss'])-Decimal(x['log_loss']))})
 week=[]
 for line in B.splitlines():
  if not re.match(r'^\| [5-9] \|',line):continue
  c=[v.strip() for v in line.split('|')[1:-1]]
  if len(c)!=8:continue
  if not c[2].isdigit():continue
  vals=[]
  for q in c[3:7]:
   w,l=map(int,q.split('–'));assert w+l==int(c[2]);vals.append((w,l))
  week.append((int(c[0]),int(c[2]),vals))
 assert len(week)==5 and [x[0] for x in week]==[5,6,7,8,9]
 assert sum(x[1] for x in week)==142
 totals=[tuple(sum(r[2][j][k] for r in week) for k in [0,1]) for j in range(4)]
 assert totals==[(69,73),(70,72),(65,77),(76,66)],totals
 bridge=read(D/'intake/B_OWNER_LOCAL_NATIVE_ORDINAL_BRIDGE_V2.json.gz')
 forward=bridge['canonical_to_original_filtered_index'];inverse=bridge['original_filtered_to_canonical_index']
 assert len(forward)==len(inverse)==142 and sorted(forward)==sorted(inverse)==list(range(142))
 assert all(inverse[v]==i for i,v in enumerate(forward)) and all(forward[v]==i for i,v in enumerate(inverse))
 ids=bridge['identity_hash_lookup'];assert len(ids)==142 and len({r['identity_sha256'] for r in ids})==142
 assert all(inverse[r['original_filtered_index']]==r['canonical_rank'] for r in ids)
 def policy(x):return tuple(x[k] for k in ['method','policy','K','rank_scope'])
 cumulative=bridge['all20_original_policy_commitments'];weekly=bridge['weekly_commitments'];assert len(cumulative)==20 and len(weekly)==100
 by=defaultdict(list)
 for z in weekly:by[policy(z)].append(z)
 for z in cumulative:
  w=by[policy(z)];assert sorted(x['week'] for x in w)==[5,6,7,8,9]
  assert sum(x['selected'] for x in w)==z['selected'] and z['wins']+z['losses']==z['selected']
 assert 'C E0_ENV point controls' in B and 'mean64–78 and median67–75' in B
 assert 'Fixed' in B or 'fixed' in B
 # All original sealed C M3 members remain exact; no fits/inference repeated.
 manifest=read(R/'reports/targeted-accuracy-w1w9-01/M3/MANIFEST.json')
 assert len(manifest['files'])==379
 for q in manifest['files']:
  p=R/q['path'];assert p.stat().st_size==q['bytes'] and sha(p)==q['SHA256'],q['path']
 delivery=read(D/'C_M3_IMMUTABLE_DELIVERY.json');assert delivery['immutable_commit']=='d662c16a3d2a5ae13640860e38d4d1e044234c5e'
 assert delivery['readback_requests']==5 and delivery['readback_total_response_bytes']==sum(x['bytes'] for x in delivery['readback'])==7496953
 checked={}
 def visit(x):
  if isinstance(x,dict):
   if {'repository','commit','path','bytes','SHA256','raw_url'}<=x.keys():
    assert x['repository']=='NickNicky19/NFL-forecasting-NGS-C' and x['commit']==delivery['immutable_commit']
    p=R/x['path'];assert p.is_relative_to(R) and p.stat().st_size==x['bytes'] and sha(p)==x['SHA256'],x['path']
    assert unquote(x['raw_url'])=='https://raw.githubusercontent.com/'+x['repository']+'/'+x['commit']+'/'+x['path']
    checked[x['path']]=x['SHA256']
   for v in x.values():visit(v)
  elif isinstance(x,list):
   for v in x:visit(v)
 visit(delivery)
 for z in delivery['weekly_output_coverage']:
  assert z['query_rows']==z['unique_player_games']==sum(z['weekly_query_rows'].values())==1975
  assert sorted(map(int,z['weekly_query_rows']))==list(range(1,10)) and z['actual_offer_weeks_scored_by_C']==[2,3]
 assert delivery['milestones']['A_receipt']=='NOT_ESTABLISHED_BY_THIS_C_ARTIFACT_READBACK'
 handoff=read(D/'intake/B_OWNER_LOCAL_M2_HANDOFF_V1.json.gz');assert handoff['requested_new_cells']['owner_bound_existing_offers']==[10,25,26,23] and sum(handoff['requested_new_cells']['owner_bound_existing_offers'])==84
 for f in handoff['prediction_files']:assert f['path'].startswith('reports/targeted-accuracy-w1w9-01/B/wave-v1/predictions/') and len(f['sha256'])==64
 cpu=time.process_time()-started;assert cpu<30
 receipt={'id':'C-CHECKPOINT-CLOSURE-01-INDEPENDENT-INTAKE-v1','recorded_UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'PASS_PUBLIC_ARITHMETIC_AND_BINDINGS;PARTIAL_OWNER_LOCAL_PRIVATE_FIT_CLOCK_SCOPE','reviewer':'Independent C sub-agent; not external B/A acknowledgement','scope':{'A_budget':{'old_cap':str(old),'approved_cap':str(new),'increment':str(new-old),'recorded_consumption':str(used),'recorded_remainder':str(new-used),'retention_reserve':str(reserve),'recorded_ceiling_after_reserve':str(new-used-reserve),'unmetered_tail_and_qualification_overhead':'UNKNOWN_NOT_A_COMPLETE_MEASURED_CPU_CERTIFICATE','NFL_mutation_fixture':'NOT_EXECUTED_IN_RETRIEVED_CHECKPOINT;NO_NEW_PASS_RECEIVED;CURRENT_JOB_ACTIVITY_NOT_INFERRED'},'B':{'table_rows_checked':24,'weekly_rows_checked':5,'native_completion_cases':142,'native_attempt_cases_owner_reported':142,'weekly_counts':dict((str(w),n) for w,n,_ in week),'weekly_own_totals':dict(zip(['P2_BB_LAW','C2_BB_LAW','D_M2_LAW','RETAINED_B0_MEAN'],totals)),'BIN_BB_direction_pairs_equal':9,'mean_MAE_pairs_fixed':3,'probability_deltas_from_published_rounded_tables':effects,'source_rounded_delta_qualification':'P2 Brier -0.000120 and logloss -0.000287 agree with finer owner-reported -0.00011998/-0.00028664 within displayed rounding; C1/C2 changes similarly small. No calibration/superiority claim.','fixed_exposure_and_conversion_means':'Explicit owner declaration; source/fit independently uninspected','selected_19_policy_invariance':'Owner-reported declaration only; new raw M2 membership not independently recomputed here','older_C_control_identity':'C E0_ENV completions mean64/142, median67/142; not new receiving M3 coverage','bridge':{'permutation_size':142,'inverse_and_identity_hash_lookup':'PASS','cumulative_policies_checked':20,'weekly_selected_counts_checked':100,'membership_hash_contents':'NOT_RECOMPUTED_WITHOUT_PRIVATE_IDENTITIES;COUNTS_AND_ENCODING_ONLY','new_M2_early_grades_added':0}},'C':{'unchanged_sealed_M3_members_checked':379,'immutable_delivery_local_artifact_bindings_checked':len(checked),'delivery_file_sha256':sha(D/'C_M3_IMMUTABLE_DELIVERY.json'),'public_readback_reports':'Exact delivery-source receipt; independent reviewer made zero network calls','typed_7900_native_inference_parity':'REUSED_EXISTING_PROOF_NOT_REEXECUTED','actual_line_weeks':[2,3],'new_actual_line_weeks_added':0,'A_consumer_receipt':'NOT_ESTABLISHED'}},'verdicts':{'public_counts_rates_budget_and_permutation':'PASS','private_row_source_clock_fit_parity':'UNKNOWN_NOT_INSPECTED','A_NFL_fixture_pass':'NOT_RECEIVED_NOT_CERTIFIED','new_M2_M3_early_or_later_joins':'NOT_RECEIVED_NO_ZERO_RESULTS_FABRICATED','new_primary_admission':'NOT_AUTHORIZED_OR_CERTIFIED'},'bindings':[bind(D/'intake'/n) for n in ['A_RECEIPT.json','B_RECEIPT.json','A_EXECUTED_M1_CHECKPOINT_V1.md.gz','B_README.md.gz','B_OWNER_LOCAL_M2_HANDOFF_V1.json.gz','B_OWNER_LOCAL_NATIVE_ORDINAL_BRIDGE_V2.json.gz']]+[bind(D/'C_M3_IMMUTABLE_DELIVERY.json'),bind(R/'reports/targeted-accuracy-w1w9-01/M3/MANIFEST.json')],'resources':{'CPU_seconds':cpu,'CPU_cap':30,'new_model_fits':0,'inference_runs':0,'NFL_grades':0,'source_requests':0,'peer_writes':0,'initial_reviewer_literal_URL_check_failed':True,'reviewer_failure_reason':'Reviewer compared encoded %2B URL with literal plus instead of decodedpath; validdeliveryURL unchanged. Corrected onlyreviewcheck; no data/model/receipt rewritten.','failed_review_CPU_conservative_charge_seconds':1}}
 return receipt
if __name__=='__main__':
 x=main();p=D/'verification/INDEPENDENT_INTAKE_REVIEW.json';assert not p.exists();p.write_text(json.dumps(x,indent=2)+'\n');print(p,sha(p),x['resources']['CPU_seconds'])
