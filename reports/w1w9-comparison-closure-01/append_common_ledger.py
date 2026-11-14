"""Append this evidence version to the existing shared ledger, never regrade."""
import csv,gzip,hashlib,io,json,collections,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];BASE=Path(__file__).resolve().parent
OLD=ROOT/'reports/category-decision-release-01/W1_W9_AND_HISTORY_COVERAGE_V3.csv.gz';NEW=OLD.with_name('W1_W9_AND_HISTORY_COVERAGE_V4.csv.gz')
def load(p):
 b=Path(p).read_bytes();return json.loads(gzip.decompress(b) if str(p).endswith('.gz') else b)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def bind(p):p=Path(p);return dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,SHA256=sha(p))
def text(x):return '' if x is None else json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False) if isinstance(x,(dict,list)) else str(x)
def sidefields(s):
 s={k.lower():v for k,v in s.items()};d={}
 for side in ['over','under','combined']:
  z=s.get(side,{})
  for k in ['wins','losses','decided','rate']:d[side+'_'+k]=z.get(k,z.get('hit_rate') if k=='rate' else None)
 return d
def main():
 start=time.process_time()
 if NEW.exists():
  import subprocess
  assert sha(NEW)=='08cc706f6b9f8f2a1350a3b967aa67bd219a066564e876c946fe1210d4364564','VERSION_ALREADY_EXISTS'
  assert subprocess.run(['git','ls-files','--error-unmatch',str(NEW.relative_to(ROOT))],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode!=0,'TRACKED_VERSION_CANNOT_REPLACE'
 raw=gzip.decompress(OLD.read_bytes());old=list(csv.DictReader(io.StringIO(raw.decode())));fields=list(old[0]);assert len(old)==32422
 rows=[];counts=collections.Counter()
 def add(source,index,owner,category,procedure,product,week,coverage,sides=None,status='OWNER_REPORTED_DIAGNOSTIC',tier='',metrics=None,kind='SOURCE_AGGREGATE_VIEW',role='Exact bound source role scope',history='Exact bound procedure history; no refit/reforecast in this report'):
  r={k:'' for k in fields};r.update({k:text(v) for k,v in dict(owner=owner,category=category,procedure_id=procedure,product=product,history=history,role_scope=role,source_panel=(metrics or {}).get('panel',source.name),book='Source-bound heterogeneous retained books; unknown clocks/main-alt remain unknown',evidence_tier=tier,season=2026,week=week,status=status,source_artifacts=str(source.relative_to(ROOT)),verification_limit='C source-qualified public aggregate arithmetic only; private row/source-clock/model-fit scope remains with owners. Overlapping source/alias/policy views are not additional NFL observations.',source_evidence_class=tier,new_procedure_coverage_not_new_games=True,required_next_owner_action=(metrics or {}).get('next_action','Exact next executor/action in FINITE_QUEUE.json'),row_kind=kind,grading_version='SOURCE_FROZEN_VERSION;NO_NEW_C_NFL_GRADE',issuance_state='EXPOSED_RECONSTRUCTION_OR_SAVED_SOURCE_VIEW;NOT_NEW_ORIGINAL_PICKS',additional_metrics=metrics or {}).items()})
  r.update({k:text(v) for k,v in coverage.items() if k in fields});r.update({k:text(v) for k,v in sidefields(sides).items()} if sides else {})
  assert set(r)==set(fields)
  r['row_id']=hashlib.sha256(f'C-W1W9-V4|{sha(source)}|{index}|{procedure}|{product}'.encode()).hexdigest();r['coverage_entry_id']=hashlib.sha256(json.dumps({k:v for k,v in r.items() if k!='coverage_entry_id'},sort_keys=True,separators=(',',':')).encode()).hexdigest();rows.append(r);counts[kind]+=1
 ap=BASE/'A-intake/NORMALIZED_COMPLETION_ROWS.json.gz'
 for i,z in enumerate(load(ap)):
  cov={k:z.get(k) for k in ['eligible','available','selected','unknown','unavailable','fallback','games','player_games']};cov['scored']=z['COMBINED']['decided'];cov['abstained']=z['abstentions']
  if z['procedure_id'].startswith('A::'):cov['fallback']=None
  add(ap,i,'A' if z['procedure_id'].startswith('A::') else 'B' if z['procedure_id'].startswith('B-FTN') else 'control','pass_cmp',z['procedure_id'],z['product_policy'],z['week_view'],cov,{k:z[k] for k in ['OVER','UNDER','COMBINED']},status='OUTSIDE_SOURCE_WINDOW_NOT_TESTED' if not z['actual_scored_weeks'] else z['execution_state'],tier=z['source_evidence_tier'],metrics=z,kind='A_OWNER_COMPLETED_EARLY_JOIN_VIEW')
 bp=BASE/'controls/B_NATIVE_W5_W9_STRONG_CONTROLS_AND_RETAINED_PRODUCTS.json'
 for i,z in enumerate(load(bp)['rows']):
  cov={k:z.get(k) for k in ['eligible','available','selected','unknown','fallback','games']};cov.update(scored=z['combined_decided'],abstained=z['abstained'],unavailable=z['technical_unavailable'])
  add(bp,i,z['owner'],'pass_cmp',z['procedure_id'],z['product'],z['week'],cov,z['own_sides'],tier=z['evidence_tier'],metrics=z,kind='B_RETAINED_NATIVE_CONTROL_VIEW')
 cp=BASE/'completion/NINE_WEEK_COMPLETION.json';c=load(cp)
 for r in c['rows']:
  for week,z in [('ALL',r)]+[(w['week'],w) for w in r['weekly']]:
   v=r['coverage'] if week=='ALL' else z;cov={k:v.get(k) for k in ['eligible','available','selected','unknown','unavailable','abstained','fallback','games']};cov['scored']=v['decided']
   add(cp,f"{r['product']}|{week}",r['origin_session'],'pass_cmp',r['procedure_id'],r['product'],week,cov,z['own_sides'],status='COMPLETED_NAMED_W1_W9_CONDITIONAL_PANEL',tier=r['source_tier'],metrics=dict(panel=c['id'],data=z,next_action='A/C exact later competing outputs and owner-local scores still required; no full cross-session winner'),kind='SOURCE_COMBINED_COMPLETE_PROCEDURE_VIEW',role='QB')
 tp=BASE/'attempt-check/EIGHT_WEEK_ATTEMPTS.json';t=load(tp)
 for week,z in [('ALL',t)]+[(w['week'],w) for w in t['weekly']]:
  v=t['coverage'] if week=='ALL' else z;cov={k:v.get(k) for k in ['eligible','available','selected','unknown','unavailable','fallback','games']};cov.update(scored=v['decided'],abstained=0)
  add(tp,week,'B','pass_att',t['procedure_id'],'P1_LOWER_MEDIAN',week,cov,z['own_sides'],status='COMPLETED_W1_W8_PARTIAL_W9_EXACT_OUTPUT_MISSING',tier=t['evidence_tier'],metrics=dict(panel=t['id'],data=z,next_action=t['W9_action']),kind='SOURCE_COMBINED_EIGHT_WEEK_PROCEDURE',role='QB')
 mp=BASE/'CANDIDATE_WEEK_MATRIX.json'
 for i,z in enumerate(load(mp)['cells']):
  q=z['source_slices'][0] if len(z['source_slices'])==1 else {};cov={k:q.get(k) for k in ['eligible','available','selected','unknown','unavailable','fallback','games']};cov['scored']=q.get('decided')
  add(mp,i,z['owner'],z['category'],z['procedure_id'],z['output'],z['week'],cov,q.get('own_sides'),status=z['status'],tier='EXPLICIT_FROZEN_ROSTER_CELL;SOURCE_SPECIFIC_COMPLETENESS_NOT_UNIVERSAL_ACTUAL_OFFER_COVERAGE',metrics=dict(z,panel=z['comparison_panel']),kind='FROZEN_CANDIDATE_WEEK_COMPLETION_CELL')
 wp=BASE/'A-intake/LATER_ALL12_RETAINED_CELL_CHECK.json'
 for i,z in enumerate(load(wp)['ready_corrected_measurement_triads']):
  for version in ['original','corrected']:
   v=z[version+'_grading'];states=v.get('qualified_states',v.get('states',{}));assert set(states)<={'WIN','LOSS','UNKNOWN_PARTICIPATION','MISSING_ACTUAL','UNRESOLVED'}
   assert sum(states.values())==v['COMBINED']['selected']
   assert states.get('WIN',0)+states.get('LOSS',0)==v['COMBINED']['decided']
   unknown=sum(states.get(k,0) for k in ['UNKNOWN_PARTICIPATION','MISSING_ACTUAL','UNRESOLVED'])
   cov=dict(eligible=v.get('issued_or_board_rows'),available=v.get('issued_or_board_rows'),selected=v['COMBINED']['selected'],scored=v['COMBINED']['decided'],unknown=unknown,games=v.get('games'),player_games=v.get('player_games'),fallback=None)
   add(wp,f'{i}|{version}','A',z['category'],z['frozen_control_policy_alias'],'UNCHANGED_FROZEN_CONSTANT_SIDE',8,cov,{k:v[k] for k in ['OVER','UNDER','COMBINED']},status='CORRECTED_MEASUREMENT_SOURCE_PROVENANCE_UNRESOLVED' if version=='corrected' else 'PRESERVED_ORIGINAL_MEASUREMENT',tier='OWNER_REPORTED_ORIGINAL_THRESHOLDS;QUOTE_BOOK_ROLE_SOURCE_QUALIFICATION_UNRESOLVED;NOT_NEW_ACTUAL_OFFER_DURATION',metrics=dict(panel='A_W8_FROZEN_MEASUREMENT_REPAIR',version=version,source=z,next_action='A qualifies exact underlying source/threshold/role/horizon before actual-offer claims'),kind='ORIGINAL_AND_CORRECTED_MEASUREMENT_VERSION')
 out=io.StringIO(newline='');wr=csv.DictWriter(out,fieldnames=fields,lineterminator='\n');wr.writerows(rows);wire=raw+out.getvalue().encode();decoded=list(csv.DictReader(io.StringIO(wire.decode())));assert decoded[:len(old)]==old and len({r['coverage_entry_id'] for r in decoded})==len(decoded)
 NEW.write_bytes(gzip.compress(wire,mtime=0));receipt=dict(id='C-W1W9-COMPARISON-COVERAGE-V4',old=bind(OLD),new=bind(NEW),prior_entries=len(old),appended_entries=len(rows),total_entries=len(decoded),by_kind=dict(counts),old_decoded_wire_exact_prefix=True,all_complete_entry_ids_unique=True,new_NFL_games=0,new_original_selected_sides=0,new_C_outcome_grades=0,newly_assembled_completion_weeks=list(range(1,10)),newly_assembled_attempt_weeks=list(range(1,9)),note='Named overlapping views/cells, not additive NFL observations; unresolved fields stay empty. Source-specific original and corrected measurements preserved separately.',CPU_seconds=time.process_time()-start)
 (BASE/'LEDGER_BUILD_RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
if __name__=='__main__':main()
