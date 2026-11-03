"""Common championship adapter/evaluator. Zero fits; exact existing contracts."""
import csv,gzip,hashlib,json,time
from collections import defaultdict,Counter
from decimal import Decimal
from pathlib import Path
import actual_accuracy_v6 as a
ROOT=a.ROOT;OUT=ROOT/'reports/abc-championship'
def write(name,j):a.stable_write(OUT/name,j)
def bound(path):return dict(path=path,SHA256=a.sha(ROOT/path))
def status(r):
 side=r['selected_side'];y=r.get('actual');state=r['status']
 if side in [None,'ABSTAIN'] or r['appearance']!='PLAYED' or y is None:return state
 if r['comparator']=='AT_LEAST':return 'WIN' if (Decimal(str(y))>=Decimal(str(r['line'])))==(side=='OVER') else 'LOSS'
 if r['comparator']=='AT_LEAST_ONE_RUSH_REC_TD':return 'WIN' if y==1 else 'LOSS'
 y,l=Decimal(str(y)),Decimal(str(r['line']))
 return 'PUSH' if y==l else 'WIN' if (y>l)==(side=='OVER') else 'LOSS'
def procedure(r):return 'C::'+r['method_version']+'::'+r['method_id']+'::'+r['selector_id']
def summary(rows):
 out={}
 for side in ['OVER','UNDER','COMBINED']:
  rr=[r for r in rows if r['selected_side'] in ['OVER','UNDER','YES']] if side=='COMBINED' else [r for r in rows if (r['selected_side']==side or (side=='OVER' and r['selected_side']=='YES'))]
  counts=Counter(status(r) for r in rr);w,l=counts['WIN'],counts['LOSS'];out[side]=dict(selected=len(rr),wins=w if w+l else None,losses=l if w+l else None,decided=w+l,rate=w/(w+l) if w+l else None)
 out.update(eligible=len(rows),unavailable=sum(r['selected_side'] is None for r in rows),abstentions=sum(r['selected_side']=='ABSTAIN' for r in rows),states=dict(Counter(status(r) for r in rows)),games=len({r['game_id'] for r in rows}),player_games=len({(r['game_id'],r['player_id']) for r in rows}),weeks=sorted({r['week'] for r in rows}),uncertainty=a.interval(rows),coverage=out['COMBINED']['selected']/len(rows) if rows else None)
 return out

def build():
 start=time.monotonic();rows,receipts=a.load_records();protocol=a.read(OUT/'PROTOCOL-v2-C-1.json');primary=[r for r in rows if r['venue']=='pinnacle' and r['season']==2026 and r['week']<=8];assert all(status(r)==r['status'] for r in rows)
 roster={};groups=defaultdict(list)
 for r in rows:
  pid=procedure(r)
  if pid in roster:continue
  roster[pid]=dict(procedure_id=pid,origin_session='C',local_alias=r['method_id'],method_version=r['method_version'],selector_id=r['selector_id'],output_type=r.get('point_type') or ('EXACT_LINE_PROBABILITIES' if r.get('p_over') is not None else 'CONSTANT_SIDE'),history='Inherited exactproducer configuration;not inferredfromalias',binding_dataset_ids=[x['dataset_id'] for x in receipts],categories=sorted({q['category'] for q in rows if procedure(q)==pid}),status='IMPLEMENTED_SAVED_ACTUAL_LINE_ROWS',source_configs=['protocol/PROPLINE_PILOT_V7.json','protocol/SELECTED_RELIABILITY_V8.json','protocol/WORKLOAD_LINK_V8.json'])
 for r in primary:
  for week in ['ALL',r['week']]:groups[(r['category'],procedure(r),r['method_id'],str(week))].append(r)
 scores=[dict(category=c,procedure_id=p,local_alias=m,period_id='E1',actual_weeks=[2,3] if w=='ALL' else [int(w)],requested_weeks=list(range(1,9)),week_view=w,evidence_tier=protocol['primary_panel']['tier'],scope='C_ONLY_PARTIAL_NOT_ABC',**summary(rr)) for (c,p,m,w),rr in sorted(groups.items())]
 byoffer=defaultdict(dict)
 for r in primary:byoffer[r['offer_id']][r['method_id']]=r
 pairs=[]
 for method in sorted({r['method_id'] for r in primary}):
  for cat in a.CATEGORIES:
   paired=[(g[method],g['P2_LAW']) for g in byoffer.values() if method in g and 'P2_LAW' in g and g[method]['category']==cat]
   for x,y in paired:assert a.offer_case(x)==a.offer_case(y) and x['decision_UTC']==y['decision_UTC'] and (x['actual'] is None or y['actual'] is None or x['actual']==y['actual']) and x['position']==y['position'] and x['scoring_contract_id']==y['scoring_contract_id']
   decided=[(x,y) for x,y in paired if status(x) in ['WIN','LOSS'] and status(y) in ['WIN','LOSS']]
   if paired:pairs.append(dict(category=cat,method=method,control='P2_LAW',matched_offers=len(paired),common_decided=len(decided),candidate_wins=sum(status(x)=='WIN' for x,y in decided),control_wins=sum(status(y)=='WIN' for x,y in decided),win_difference=sum((status(x)=='WIN')-(status(y)=='WIN') for x,y in decided),disagreements=sum(x['selected_side']!=y['selected_side'] for x,y in decided)))
 core=[oid for oid,g in byoffer.items() if all(m in g and g[m]['selected_side'] is not None for m in protocol['primary_panel']['core'])]
 core_scores=[dict(category=c,method=m,**summary([byoffer[o][m] for o in core if byoffer[o][m]['category']==c])) for c in a.CATEGORIES for m in protocol['primary_panel']['core'] if any(byoffer[o][m]['category']==c for o in core)]
 leaders=[]
 for c in a.CATEGORIES:
  rr=[s for s in scores if s['category']==c and s['week_view']=='ALL'];x=dict(category=c,period_id='E1',actual_weeks=[2,3] if rr else [],scope='PARTIAL_C_ONLY' if rr else 'MISSING_ACTUAL_LINES',operational_recommendation='RETAIN_EXISTING_PROVISIONAL_REFERENCE;NO_CHAMPIONSHIP_PROMOTION',supported_leader='NOT_ESTABLISHED',leaders={})
  for side in ['OVER','UNDER','COMBINED']:
   valid=[s for s in rr if s[side]['decided']];best=max((s[side]['rate'] for s in valid),default=None);x['leaders'][side]=[dict(procedure_id=s['procedure_id'],alias=s['local_alias'],**s[side]) for s in valid if s[side]['rate']==best]
  leaders.append(x)
 write('METHOD_ROSTER-v2-C-1.json',list(roster.values()));write('SCORES-v2-C-1.json',scores);write('PAIRED-v2-C-1.json',pairs);write('COMMON_CORE-v2-C-1.json',dict(offer_ids=core,scores=core_scores));write('LEADERS-v2-C-1.json',leaders)
 write('C_INPUT_BINDINGS.json',dict(source_dataset_manifest=bound('reporting/actual-props-v6/DATASETS.json'),datasets=receipts,other_implemented_roster_bindings=[bound(x) for x in ['protocol/REGISTERED_V1.json','protocol/BROAD_V2_1.json','protocol/PROSPECTIVE_V4.json','protocol/WORKLOAD_LINK_V8.json']],not_all_roster_actual_line_ready=True,TopK_existing=bound('reports/topk-reference-v9/RUN.json'),TopK_members=bound('artifacts/topk-reference-v9/MEMBERSHIP.json.gz')))
 with gzip.open(OUT/'ROW_MEMBERSHIP.json.gz','wt') as f:json.dump([dict(record_id=r['record_id'],offer_id=r['offer_id'],procedure_id=procedure(r),status=status(r)) for r in primary],f,separators=(',',':'))
 write('EXPORT_INDEX.json',dict(schema='ABC-EXPORT-v2',origin_session='C',producer_repository='NickNicky19/NFL-forecasting-NGS-C',producer_commit='2d684f22830b817669ecf89f46eb6fdcace8335b',state='ACTUAL_BYTES_READ_VALIDATED_LOCAL_C_ONLY',actual_weeks=[2,3],requested_periods=['E1','E2','E3','E4','E5','E6','E7','E8'],method_roster=bound('reports/abc-championship/METHOD_ROSTER-v2-C-1.json'),bindings=bound('reports/abc-championship/C_INPUT_BINDINGS.json'),rights='Inherited exact5approvedCdatasets;analysis/GitHubretention/aggregatequalified;not a grant for otherproducerrows',missing='No qualifiedotherweeks/eightabsentcategories;noA/Bpinnedcontractexportsoracknowledgements',files=[bound('reports/abc-championship/'+n) for n in ['SCORES-v2-C-1.json','PAIRED-v2-C-1.json','COMMON_CORE-v2-C-1.json','LEADERS-v2-C-1.json']]))
 write('CURRENT_PROTOCOL.json',dict(protocol_id=protocol['id'],protocol=bound('reports/abc-championship/PROTOCOL-v2-C-1.json'),scorer=bound('src/abc_championship_v2.py'),dependencies=[bound('src/'+x) for x in ['actual_accuracy_v6.py','selection.py','contracts_v2.py','actual_offers_v4.py','offer_validator_v2.py']],schema=bound('reports/abc-championship/EXPORT_SCHEMA-v2.json'),roster=bound('reports/abc-championship/METHOD_ROSTER-v2-C-1.json'),population_offers_outcomes=bound('reports/abc-championship/C_INPUT_BINDINGS.json'),masks=bound('reports/abc-championship/COMMON_CORE-v2-C-1.json'),scores=bound('reports/abc-championship/SCORES-v2-C-1.json'),corrections='Originalv7.1gradechains validated; no newoutcomes changed',contributions=['C'],A_B_independent_acknowledgement='NOT_RECEIVED',stage='EXECUTED_LOCAL_MATCHED_C_ONLY_PARTIAL_E1;NOT_COMPLETED_CHAMPIONSHIP'))
 pointer=a.read(OUT/'CURRENT_PROTOCOL.json')
 for k,n in [('admission','ADMISSION_LEDGER.json'),('tasks','TASK_LEDGER.json'),('roster_coverage','METHOD_COVERAGE.json'),('failed_attempts','FAILED_ATTEMPTS.json')]:
  if (OUT/n).exists():pointer[k]=bound('reports/abc-championship/'+n)
 write('CURRENT_PROTOCOL.json',pointer)
 text='# Common actual-prop championship v2\n\nC coordinates. This first executed comparison is **C-only**, Pinnacle2026W2–3, timing-unverified actual-line diagnostics; **PARTIAL E1**, not eight weeks and not A/B/C parity. Primarybook was frozen from sourcequalification, not wins. No new fits.\n\n|Category|Highest observed complete procedure (controls included)|Over W-L/n/rate|Under W-L/n/rate|Combined W-L/n/rate|Eligible/unavailable|\n|---|---|---|---|---|---|\n'
 def fmt(q):return 'N/A' if not q['decided'] else f"{q['wins']}-{q['losses']}/{q['decided']}/{q['rate']:.2%}"
 for l in leaders:
  cand=l['leaders']['COMBINED'];winning=[s for s in scores if s['category']==l['category'] and s['week_view']=='ALL' and any(s['procedure_id']==w['procedure_id'] for w in cand)]
  if not winning:text+=f"|{a.LABELS[l['category']]}|N/A: no qualifiedmarket|N/A|N/A|N/A|Unknown|\n"
  for s in winning:text+=f"|{a.LABELS[l['category']]}|{s['local_alias']}|{fmt(s['OVER'])}|{fmt(s['UNDER'])}|{fmt(s['COMBINED'])}|{s['eligible']}/{s['unavailable']}|\n"
 text+='\nFull identities/history/products/rules are bound by CURRENT_PROTOCOL and METHOD_ROSTER. Constant winners are controls, not learnedmodels. Raw side leaders, everymethod/week, same-rowpairedchanges, full-system and stablecore are separateJSONs. All twelve remainvisible. ExistingTopK810lists remain exploratory and C-only; see ../topk-reference-v9.\n\nE1 is PARTIAL(W2-W3);E2/E3/E4/E5/E6/E7 have no qualifiedadditionalactual-lineyears. Trainingyears are not testyears. E8 no genuineactualofferselections; originalv4forecast-onlyaccuracy is separate. No cross-season persistence or chronologicalselector win established. Equal-season pooled results unavailable on requestedseasonset, not silently computed from2026alone. A/B/productionread-only; no privatearchive transfer. A/Bverification NOT RECEIVED.\n\nRun `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python src/abc_championship_v2.py` to replay retained Crows (zero fits). A/B can prepare EXPORT_INDEX against EXPORT_SCHEMA and pin CURRENT_PROTOCOL; ownerlocal permitted deterministic outputs may be assessed where transferrestricted. No secrets or private locators. See ADMISSION_LEDGER and TASK_LEDGER for exact dependencies.\n'
 (OUT/'README.md').write_text(text)
 write('RUN.json',dict(new_fits=0,wall_seconds=time.monotonic()-start,canonical_input_rows=len(rows),primary_method_rows=len(primary),primary_unique_offers=len(byoffer),core_offers=len(core),primary_games=len({r['game_id'] for r in primary}),contributors=['C'],all_registered_contenders_compared='PARTIAL;implementedsourceboundroster preserved, othermodelsneedeligibleinference/lines/exports'))
 print('CHAMPIONSHIP_EXECUTED',len(primary),len(byoffer),len(core),len(scores))
if __name__=='__main__':build()
