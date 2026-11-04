"""Adapters to the existing ABC contract: owner-local public aggregates, never raw-row parity."""
import csv,gzip,hashlib,json,time,resource,os
from collections import defaultdict,Counter
from pathlib import Path
from abc_championship_v2 import ROOT
from actual_accuracy_v6 import sha,digest
OUT=ROOT/'reports/abc-championship/continuation-v2'
BASE=Path(os.environ.get('ABC_INTAKE',str(OUT/'intake')))
def load(n):return json.loads(gzip.decompress((BASE/(n+'.gz')).read_bytes()))
def put(n,j):
 p=OUT/n;p.parent.mkdir(parents=True,exist_ok=True);b=(json.dumps(j,separators=(',',':'),allow_nan=False)+'\n').encode();p.write_bytes(gzip.compress(b,mtime=0) if n.endswith('.gz') else b)
def bound(p):return dict(path=str(p.relative_to(ROOT)),SHA256=sha(p))
def side(m):
 w,l=int(m['WIN']),int(m['LOSS']);n=w+l
 assert m['denominators']['decided']==n
 if n:assert abs(m['hit_rate']-w/n)<1e-12
 return dict(selected=m['denominators']['outer_rows'],wins=w if n else None,losses=l if n else None,decided=n,rate=w/n if n else None,states=m['status_counts'])
def normalize_b(j,source):
 groups=defaultdict(dict)
 keys=['procedure_id','product_id','strategy','target','history_regime','capture_version','availability_arm','information_policy','cohort_id','K','rank_scope','horizon_id','evaluation_panel_id','season','week','evaluation_weeks','decision_rule','method_id','population']
 for r in j:
  if r.get('record_kind')!='prop_selection_evaluation':continue
  key=json.dumps({k:r.get(k) for k in keys},sort_keys=True)
  s=r['side'].upper();assert s in ['OVER','UNDER','COMBINED'];assert s not in groups[key],('DUPLICATE_AGGREGATE_SIDE',source,key,s);groups[key][s]=r
 out=[]
 for key,g in groups.items():
  assert set(g)=={'OVER','UNDER','COMBINED'},('INCOMPLETE_TRIAD',source,key)
  v={s:side(r['selection_metrics']) for s,r in g.items()};r=g['COMBINED'];m=r['selection_metrics']
  for k in ['selected','decided']:assert v['COMBINED'][k]==v['OVER'][k]+v['UNDER'][k]
  for k in ['wins','losses']:assert (v['COMBINED'][k] or 0)==(v['OVER'][k] or 0)+(v['UNDER'][k] or 0)
  z=json.loads(key);z.update(session='B',source=source,period_id='E1',requested_weeks=list(range(1,9)),actual_weeks=r['evaluation_weeks'],OVER=v['OVER'],UNDER=v['UNDER'],COMBINED=v['COMBINED'],eligible=m.get('selection_pool_count'),selected=v['COMBINED']['selected'],abstentions_reported=m.get('admitted_rule_abstentions',m.get('abstentions_outside_selected_partition')),abstention_scope='Source-specific reported field; technical failures not converted into abstentions',unavailable=m.get('unavailable_forecast_opportunities'),games=r['unique_games'],player_games=r['unique_player_games'],membership_SHA256=r.get('query_membership_sha256'),uncertainty=m.get('game_uncertainty'),selection_evidence=r.get('selection_evidence'),source_vintage=r.get('source_vintage'),settlement=r.get('settlement_status'),admission='ADMITTED_PUBLIC_OWNER_LOCAL_AGGREGATE_ARITHMETIC_ONLY',common_row_parity=False)
  out.append(z)
 return out

def build():
 started=time.monotonic();resource.setrlimit(resource.RLIMIT_CPU,(60,61));OUT.mkdir(parents=True,exist_ok=True)
 a=load('A-LOCAL_A_C_RESULTS_V1.json');b=load('B-local_direction_results.json');allb=[]
 for name,j in [('B_LOCAL_W8',b),('B_W6_COMPLETE_LAW',load('B-w6.json')),('B_W7_COMPLETE_LAW',load('B-w7.json')),('B_W5_W7_POINT',load('B-historical-point-offer.json'))]:allb+=normalize_b(j,name)
 ar=[]
 for r in a['rows']:
  z=dict(r,session='A_C_OWNER_LOCAL',period_id='E1',requested_weeks=list(range(1,9)),actual_weeks=[8],common_row_parity=False,admission='ADMITTED_PUBLIC_OWNER_LOCAL_AGGREGATE_ARITHMETIC_ONLY',evidence_tier='TIMING_UNVERIFIED_LOCAL_A_C_REPLAY;DIFFERENT_ISSUE_CLOCKS;PRIVATEROWSNOTTRANSFERRED')
  for s in ['over','under','combined']:
   q=r[s];assert q['wins']+q['losses']==q['decided'];assert q['rate'] is None if not q['decided'] else abs(q['rate']-q['wins']/q['decided'])<1e-12
  assert r['combined']['decided']==r['over']['decided']+r['under']['decided'];ar.append(z)
 put('A_C_OWNER_LOCAL_SCORES.json',ar);put('A_C_OWNER_LOCAL_PAIRED.json',a['paired_changes']);put('B_OWNER_LOCAL_SCORES.json.gz',allb)
 original=[x for x in allb if x['strategy']=='original' and x['horizon_id']=='B_LOCAL_W8_FIXED_ORIGINAL_SOURCE_FINAL_LABELS_V2']
 assert len(original)==12
 w=sum(x['COMBINED']['wins'] or 0 for x in original);l=sum(x['COMBINED']['losses'] or 0 for x in original);overloss=sum(x['OVER']['losses'] or 0 for x in original);underwin=sum(x['UNDER']['wins'] or 0 for x in original)
 assert (w,l,overloss,underwin)==(205,210,128,96)
 put('B_ORIGINAL_SELECTED_POOL_CONTROL.json',dict(scope='ORIGINAL_SELECTED_POOL_DIAGNOSTIC_ONLY;NOT_COMMON_RESEARCH_PANEL_OR_PROPOSED_POLICY',actual_weeks=[8],original_selected=sum(x['selected'] for x in original),original_wins=w,original_losses=l,decided=w+l,unknown=sum(x['COMBINED']['states'].get('UNKNOWN_PARTICIPATION',0) for x in original),always_Under_wins=overloss+underwin,always_Under_losses=w+l-overloss-underwin,original_rate=w/(w+l),always_Under_rate=(overloss+underwin)/(w+l),paired_win_difference=overloss+underwin-w,percentage_point_difference=100*(overloss+underwin-w)/(w+l),derivation='128losingOvers+96winningUnders=224Underoutcomes;notbroaderallboardor369commonoriginalpool',price_or_profit_claim=False))
 # Full per-procedure week grid: presence of cumulative rows never becomes a weekly score.
 gaps=[]
 for session,rr in [('B',allb)]:
  by=defaultdict(list)
  for r in rr:by[(r['procedure_id']+'::'+str(r.get('method_id'))+'::'+str(r.get('decision_rule'))+'::'+str(r.get('cohort_id')),r['product_id'],r['target'],r.get('history_regime'),r['horizon_id'],r['source'])].append(r)
  for (method,product,cat,hist,horizon,src),records in by.items():
   weeks={w for x in records for w in x['actual_weeks']}
   for week in range(1,9):
    covered=week in weeks;exact=any(x['actual_weeks']==[week] for x in records)
    gaps.append(dict(session=session,source=src,category=cat,procedure_id=method,product=product,history=hist,horizon=horizon,season=2026,week=week,state='COMPLETED_OWNER_LOCAL_AGGREGATE_WEEK' if exact else 'CUMULATIVE_ONLY_WEEK_PARTITION_REQUIRED' if covered else 'NO_MATCHING_EXPORT_IN_THIS_PANEL',artifact='B_OWNER_LOCAL_SCORES.json.gz',owner='B',next_action='Commonmask/policybinding andownerindependentparity' if exact else 'Exportweekpartitionofretainedrows;no newfit' if covered else 'Checkretainedsourceinventories;qualifyactualoffers/inputs before reconstruction;donotcountnumericalyearsaslinebacktests'))
 for session,methods,cats in [('A_C_OWNER_LOCAL',sorted({r['procedure_output_rule'] for r in ar}),sorted({r['category'] for r in ar})),('C', ['P1_MEAN','P1_MEDIAN','P2_LAW','P3_DIRECT','EARLIER_PREVALENCE_V8','ALWAYS_OVER','ALWAYS_UNDER'],list(__import__('contracts_v2').CATEGORIES))]:
  for method in methods:
   for cat in cats:
    for week in range(1,9):
     ok=week==8 if session.startswith('A') else week in [2,3] and cat in ['pass_yd','rush_yd','rec','rec_yd']
     gaps.append(dict(session=session,source='A_C_OWNER_LOCAL_W8' if session.startswith('A') else 'C_PROPLINE_PINNACLE',category=cat,procedure_id=method,product='declaredpoint' if session.startswith('A') else 'retainedproduct',history='seeprocedurebindings',horizon='source-specific',season=2026,week=week,state='COMPLETED_OWNER_LOCAL_AGGREGATE_WEEK' if ok and session.startswith('A') else 'COMPLETED_C_ROW_VERIFIED' if ok else 'NO_MATCHING_EXPORT_IN_THIS_PANEL',artifact='A_C_OWNER_LOCAL_SCORES.json' if session.startswith('A') else '../SCORES-v2-C-1.json',owner='A' if session.startswith('A') else 'C',next_action='Ownerlocalmatchedmaskverification;CMPATTpaperblocksretained' if ok and session.startswith('A') else 'Existingboundrows' if ok else 'Exactsource-specificlines/inputs/export;donotassumeglobalabsence'))
 # A's newly recovered fixed W1-W7 panel is a separate source, not merged into W8.
 for r in json.loads(gzip.decompress((OUT/'A_W1_W7_ARCHIVED_SCORES.json.gz').read_bytes())):
  for week in range(1,9):
   gaps.append(dict(session='A',source=r['source'],category=r['category'],procedure_id=r['procedure_id'],product=r['product'],history=r['history'],horizon='Timing-unverified historical fixed-panel replay',season=2026,week=week,state='COMPLETED_OWNER_LOCAL_AGGREGATE_WEEK' if week<8 else 'EXACT_FIXED_RECIPE_W8_EXPORT_NOT_ESTABLISHED',artifact='A_W1_W7_ARCHIVED_SCORES.json.gz',owner='A',next_action='Common manifest/history/raw parity via permitted owner-local scoring; no new fit for retained weekly counts' if week<8 else 'Bind exact recipe eligible W8 forecast/line/outcome; do not append different W8 method'))
 fields=list(gaps[0]);f=OUT/'WEEK_BY_WEEK_GAPS.csv.gz';import io
 buf=io.StringIO();cw=csv.DictWriter(buf,fields);cw.writeheader();cw.writerows(gaps);f.write_bytes(gzip.compress(buf.getvalue().encode(),mtime=0))
 # Keep the imported historical numerical grid distinct from offered-selection evidence.
 grid=load('B-existing_exact_cell_grid.json');hist=[x for x in grid if x['season'] in [2022,2023,2024,2025]]
 put('HISTORICAL_CELL_DISPOSITION.json.gz',hist)
 put('PERIOD_COMPLETENESS.json',dict(E1='PARTIAL;A_fixed_W1-W7_79products_553weekviews;C_W2-W3;B_W6/W7/W8_andcumulativeW5-W7;A_C_W8_overlap;noincompatiblepool',E2_E3_E4='ExistingBhistoricalnumericalcellsimported/dispositionchecked;actual-lineyearsnotestablished;exactD1/D2cellsremainFIT_REQUIRED',E5_E6_E7='NOT_COMPUTED_missingmatchedactual-line_seasonsets;nostartup/yearsilentlydropped',E8='Originalcapturedandnewreplaysseparate;nonebecomeoriginalfromthisimport',B_historical_states=dict(Counter(x['state'] for x in hist)),B_exact_older_D1_D2_cells=len(load('B-historical_backtest_cell_coverage.json')),pooling='NoadditiveA/C+B+Ccounts;unknownoverlap/source/horizon/tier'))
 put('RUN.json',dict(adapted_B_complete_procedure_views=len(allb),adapted_A_C_complete_procedure_views=len(ar),week_by_week_cells=len(gaps),new_fits=0,new_inference=0,CPU_seconds=time.process_time(),wall_seconds=time.monotonic()-started,source_semantics='Importedpublicaggregatecountsverified;notregradefromunseenrawrows',C_common_evaluator='Existingabc_championship_v2 remainsunchanged;thisisaggregateadapter',contributors=['A_ownerlocalexport','B_ownerlocalexport','C_receipt_arithmetic'],A_B_common_protocol_pin_and_row_verification='AWAITING_CURRENTACKNOWLEDGEMENT'))
 print('HANDOFF_EXECUTED',len(allb),len(ar),len(gaps))
if __name__=='__main__':build()
