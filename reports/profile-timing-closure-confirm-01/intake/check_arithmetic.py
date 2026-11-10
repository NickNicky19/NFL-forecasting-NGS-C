"""Independent public-count checks. No owner scorer, source rows, fit or GET."""
from pathlib import Path
import json,lzma,csv,io,re,math,hashlib,datetime,time
from decimal import Decimal
P=Path(__file__).resolve().parent
start=time.process_time()
def load(n):return json.loads(lzma.decompress((P/(n+'.json.xz')).read_bytes()))['document']
def records(n):return list(csv.DictReader(io.StringIO(load(n))))
def num(x):return int(x) if x not in ('',None) else 0
def close(a,b,tol=Decimal('0.000000001')):return abs(Decimal(str(a))-Decimal(str(b)))<=tol
checks=[];head={};fail=[]
for name in ['A_C03_CUMULATIVE','A_BCMP_ANNUAL1','A_BCMP_ANNUAL2','A_TIMING_FIRST_SHARD']:
 rows=records(name);graded=0;numeric=0
 for i,r in enumerate(rows):
  prefix=(name,i,r.get('procedure',r.get('candidate_id')))
  if r.get('combined_decided') not in ('',None):
   graded+=1
   for side in ['over','under','combined']:
    n=num(r[side+'_decided']);w=num(r[side+'_wins']);l=num(r[side+'_losses']);assert w+l==n,(prefix,side,'PARTITION')
    rt=r[side+'_rate']
    if n:assert close(rt,Decimal(w)/Decimal(n)),(prefix,side,'RATE',rt,w,n)
    else:assert rt in ('',None),(prefix,side,'EMPTY_RATE')
   for s in ['wins','losses','decided']:assert num(r['over_'+s])+num(r['under_'+s])==num(r['combined_'+s]),(prefix,s,'SUM')
   if r.get('combined_selected') not in ('',None):
    assert num(r['over_selected'])+num(r['under_selected'])==num(r['combined_selected']),(prefix,'SELECTED_SIDES')
   eligible=num(r['eligible']);selected=num(r.get('selected',r.get('combined_selected')));unavail=num(r['unavailable']);abst=num(r.get('abstained',r.get('abstentions')))
   assert eligible==selected+unavail+abst,(prefix,'ELIGIBLE',eligible,selected,unavail,abst)
   if name.startswith('A_BCMP'):
    extra=sum(num(r.get(k)) for k in ['UNKNOWN_PARTICIPATION','MISSING_ACTUAL','DNP','PENDING','PUSH'])
   elif name=='A_C03_CUMULATIVE':extra=sum(num(r.get(k)) for k in ['unknown_participation','missing_actual','DNP','pending','push'])
   else:
    states=json.loads(r.get('states') or '{}');extra=sum(num(v) for k,v in states.items() if k not in ['WIN','LOSS'])
   assert selected==num(r['combined_decided'])+extra,(prefix,'SELECTED_STATE_PARTITION',selected,r['combined_decided'],extra)
  if name=='A_TIMING_FIRST_SHARD' and r.get('numerical_intended') not in ('',None) and r.get('numerical_state')!='N/A_NO_NUMERICAL_POINT_PRODUCT':
   numeric+=1;assert num(r['numerical_intended'])==num(r['numerical_scored'])+num(r['numerical_unknown_outcome'])+num(r['numerical_unavailable']),(prefix,'NUMERICAL_STATE_PARTITION')
   assert num(r['numerical_available'])+num(r['numerical_unavailable'])==num(r['numerical_intended'])
   flags=json.loads(r['numerical_fallback']);assert sum(flags.values())==num(r['numerical_available']),(prefix,'FALLBACK_SUM')
 checks.append(dict(source=name,rows=len(rows),direction_cells_checked=graded,numeric_partition_cells_checked=numeric))
# Annual completed CMP: same exact source panel/owner-defined mask, all five weeks.
cm=records('A_BCMP_ANNUAL1')+records('A_BCMP_ANNUAL2');by={}
for r in cm:by.setdefault(r['candidate_id'],[]).append(r)
weighted=0
for method,rows in by.items():
 allrow=next(r for r in rows if r['week_view']=='ALL');week=[r for r in rows if r['week_view']!='ALL'];assert {int(r['week_view']) for r in week}==set(range(1,6))
 for k in ['eligible','selected','unavailable','abstained','combined_wins','combined_losses','combined_decided','over_wins','over_losses','over_decided','under_wins','under_losses','under_decided','UNKNOWN_PARTICIPATION','MISSING_ACTUAL','DNP','PENDING','PUSH','numeric_scored','law_events']:
  assert sum(num(r[k]) for r in week)==num(allrow[k]),(method,'WEEK_SUM',k)
 for k,nkey in [('numeric_MAE','numeric_scored'),('numeric_MSE','numeric_scored'),('numeric_bias','numeric_scored'),('law_Brier','law_events')]:
  if allrow[k] not in ('',None):
   value=sum(Decimal(r[k])*Decimal(num(r[nkey])) for r in week if r[k] not in ('',None))/Decimal(num(allrow[nkey]));assert close(value,allrow[k]),(method,'WEIGHTED',k,value,allrow[k]);weighted+=1
head['B_R0_R3_annual_W1_W5']=[r for r in cm if r['week_view']=='ALL']
cr=records('A_C03_CUMULATIVE');head['C03_annual_W1_W5']=[r for r in cr if r['view']=='FULL_A733' and r['source_panel']=='ANNUAL_NAMED_NJ']
head['C03_mixed_W1_W7_diagnostic']=[r for r in cr if r['view']=='FULL_A733' and r['source_panel']=='ALL']
# B timing provided exact own-side aggregates, not old R0-R3 join.
b=load('B_DECISIONS')['exact_own_sides']
for method,r in b.items():
 for side in ['over','under','Combined']:
  s=r[side];assert s['wins']+s['losses']==s['decided'];assert close(s['hit_rate'],Decimal(s['wins'])/s['decided'])
 for field in ['wins','losses','decided']:assert r['over'][field]+r['under'][field]==r['Combined'][field]
assert b['F2']['Combined']['wins']-b['F0']['Combined']['wins']==-2
assert b['F3']['Combined']['wins']-b['F1']['Combined']['wins']==0
head['B_aligned_F0_F3_112_W5_W8']=b
# Four printed A timing records, independently parse and reconcile rounded percentages.
a=[]
for line in load('A_REPORT').splitlines():
 if not line.startswith('| rush_yd / F'):continue
 parts=[x.strip().replace('**','') for x in line.strip('|').split('|')];row={'procedure':parts[0],'period':parts[1]}
 for j,side in zip([2,3,4],['over','under','combined']):
  m=re.fullmatch(r'(\d+)–(\d+)/(\d+)/(\d+\.\d+)%',parts[j]);assert m,parts[j];w,l,n,pct=m.groups();w,l,n=int(w),int(l),int(n);assert w+l==n;assert abs(Decimal(pct)-Decimal(w)*100/n)<Decimal('.0051');row[side]=dict(wins=w,losses=l,decided=n,rate=float(Decimal(w)/n))
 for field in ['wins','losses','decided']:assert row['over'][field]+row['under'][field]==row['combined'][field]
 row['eligible_selected_unavailable']=parts[5];row['games']=int(parts[6]);a.append(row)
assert len(a)==4 and a[-1]['combined']['wins']==97 and a[-1]['combined']['decided']==177
head['A_aligned_48h_annual_W1_W5_report_records']=a
# Assert shared scope, no misleading seven-qualified-week claim.
assert all(json.loads(r['actual_retained_threshold_weeks'])==[1,2,3,4,5] for r in head['C03_annual_W1_W5'])
assert all(r['evidence']=='CURRENT_VINTAGE_7DAY_QUOTE_TIME_UNVERIFIED' for r in head['C03_annual_W1_W5'])
receipt={'id':'C05-PUBLIC-AGGREGATE-INDEPENDENT-ARITHMETIC-v1','checked_UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'PASS','checked_tables':checks,'annual_B_CMP_weekly_reconciliations':len(by),'weighted_metric_reconciliations':weighted,'B_timing_own_records':len(b),'A_timing_printed_records':len(a),'headline_records':head,'new_NFL_observations':0,'GETs':0,'fits':0,'CPU_seconds':time.process_time()-start,'independent_path':'csv.DictReader + integer/Decimal arithmetic, not owner scorer','limits':['Public aggregate partitions and weighted arithmetic only; no private row identity, grade/source-clock, fit or inference reproduction.','C03 cumulative tables declare five retained-line weeks, but no weeklyC03 shard was fetched here; per-week source chronology remains owner-local.','B aligned timing F0-F3 records are native W5-8, separate from completed older B R0-R3 A annual W1-5 join.','C04 new timing join is not inferred from C03 records.','A timing first shard is outcome-blind first shard, not full6370-cell validation. Printed97/177 headline checked from exact report.','Owner-provided Brier/MAE values are not recomputed from hidden predictions/outcomes; only available weekly weighted arithmetic is checked.']}
(P/'ARITHMETIC_REVIEW.json').write_text(json.dumps(receipt,indent=2)+'\n');print('ARITHMETIC_PASS',sum(x['rows'] for x in checks),'public rows',len(by),'weekly sets',weighted,'weighted metrics')
