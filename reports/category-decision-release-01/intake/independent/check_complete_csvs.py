"""Independent CSV aggregate arithmetic/weekly reconciliation; no scorer or fits."""
from pathlib import Path
import csv,collections,datetime,hashlib,io,json,lzma,math,time,resource
ROOT=Path(__file__).resolve().parents[1];OUT=Path(__file__).resolve().parent

def decode(p):
 b=p.read_bytes();return lzma.decompress(b) if p.suffix=='.xz' else b
def read(name):return json.loads(decode(ROOT/name))
def num(x):return None if x in ['',None,'None','null','N/A'] else float(x)
def integer(x):
 v=num(x);assert v is None or (v>=0 and v==int(v));return 0 if v is None else int(v)
def obj(x):
 if not x:return None
 try:return json.loads(x)
 except json.JSONDecodeError:return x
def close(a,b,tol=1e-9):return abs(a-b)<=tol*max(1.,abs(a),abs(b))
def material(base,name):
 a=base/name;b=base/(name+'.xz')
 if a.exists():return a
 if b.exists():return b
 raise FileNotFoundError(str(a))

def run():
 cpu=time.process_time();summaries=[];pairs=[];files=[];counts=collections.Counter();schema_failures=[]
 for group,manifest in [('B','A_B_MANIFEST.json.xz'),('C04','A_C04_MANIFEST.json.xz')]:
  m=read(manifest);base=ROOT/'aggregate'/group;got=0
  for e in m['files']:
   p=material(base,e['path']);b=decode(p);assert len(b)==e['bytes'] and hashlib.sha256(b).hexdigest()==e['sha256'],p
   rows=list(csv.DictReader(io.StringIO(b.decode())));assert len(rows)==e['rows'],p;got+=len(rows)
   kind='pair' if 'MATCHED_PAIRS' in e['path'] else 'summary'
   for x in rows:x['_group']=group;x['_member']=e['path'];(pairs if kind=='pair' else summaries).append(x)
   files.append({'group':group,'member':e['path'],'SHA256':e['sha256'],'decoded_bytes':len(b),'rows':len(rows),'kind':kind})
  assert got==m['aggregate_rows'];counts[group+'_aggregate_rows']=got
 assert len(files)==65 and len(summaries)==1686 and len(pairs)==3072 and sum(counts.values())==4758
 keyed={};cumulative_groups=collections.defaultdict(dict);null_fallback=0;probability_rows=0
 for x in summaries:
  k=(x['_group'],x['candidate_id'],x['view'],x['source_panel'],x['week_view'])
  assert k not in keyed,('DUPLICATE_SUMMARY',k);keyed[k]=x;cumulative_groups[k[:-1]][x['week_view']]=x
  for side in ['over','under','combined']:
   w,l,n,s=[integer(x[side+'_'+a]) for a in ['wins','losses','decided','selected']]
   assert w+l==n and s>=n,(k,side)
   r=num(x[side+'_rate']);assert (r is None if n==0 else r is not None and close(r,w/n)),(k,side,'rate')
  for a in ['wins','losses','decided','selected']:assert integer(x['combined_'+a])==integer(x['over_'+a])+integer(x['under_'+a]),(k,a)
  eligible=integer(x['eligible']);selected=integer(x['combined_selected']);unavailable=integer(x['unavailable']);abstentions=integer(x.get('abstentions',''))
  assert eligible==selected+unavailable+abstentions,(k,'eligible')
  cov=num(x['coverage']);assert (cov is None if eligible==0 else cov is not None and close(cov,selected/eligible)),(k,'coverage')
  states=obj(x['states']);assert isinstance(states,dict) and all(isinstance(v,int) and v>=0 for v in states.values());assert sum(states.values())==eligible,(k,'state_sum')
  assert states.get('WIN',0)==integer(x['combined_wins']) and states.get('LOSS',0)==integer(x['combined_losses'])
  n=obj(x['numerical']);assert isinstance(n,dict)
  if integer(n.get('scored',0)):
   assert all(isinstance(n[z],(int,float)) and math.isfinite(n[z]) for z in ['MAE','MSE','bias'])
   assert n['MAE']>=abs(n['bias'])-1e-10 and n['MSE']>=n['MAE']**2-1e-9
  if obj(x.get('fallback_states')) is None:null_fallback+=1
  p=obj(x.get('probability'))
  if isinstance(p,dict):
   events=integer(p.get('events',0));br=p.get('Brier')
   if events:
    assert br is not None and math.isfinite(br) and 0<=br<=1
    bins=p.get('reliability_fixed_bins',[]);assert sum(z['count'] for z in bins)==events
    for z in bins:assert 0<=z['observed_Over']<=1 and 0<=z['predicted_Over']<=1
    auc=p.get('Over_event_AUC');assert auc is None or 0<=auc<=1
   probability_rows+=1
  elif x['_group']=='C04':assert isinstance(p,str) and 'NO_PROBABILITY' in p
 weekly_checks=0;weighted_numerical=0;weighted_probability=0;duration=[]
 add=['eligible','unavailable','abstentions']+[a+'_'+b for a in ['over','under','combined'] for b in ['selected','wins','losses','decided']]
 for k,views in cumulative_groups.items():
  if 'ALL' not in views:raise AssertionError(('NO_CUMULATIVE',k))
  total=views['ALL'];weekly=[v for w,v in views.items() if w!='ALL'];assert len({v['week_view'] for v in weekly})==len(weekly)
  # Retained-control exports intentionally contain cumulative records only.
  if not weekly:continue
  for name in add:assert integer(total[name])==sum(integer(x[name]) for x in weekly),(k,name)
  nt=obj(total['numerical']);ns=[obj(x['numerical']) for x in weekly];n=integer(nt.get('scored',0));assert n==sum(integer(y.get('scored',0)) for y in ns)
  if n:
   for metric in ['MAE','MSE','bias']:
    weighted=sum(y[metric]*integer(y.get('scored',0)) for y in ns if integer(y.get('scored',0)))/n
    assert close(nt[metric],weighted),(k,metric);weighted_numerical+=1
  pt=obj(total.get('probability'));ps=[obj(x.get('probability')) for x in weekly]
  if isinstance(pt,dict):
   n=integer(pt.get('events',0));assert n==sum(integer(y.get('events',0)) for y in ps if isinstance(y,dict))
   if n:
    value=sum(y['Brier']*integer(y.get('events',0)) for y in ps if isinstance(y,dict) and integer(y.get('events',0)))/n
    assert close(pt['Brier'],value),(k,'Brier');weighted_probability+=1
  if k[3]=='ANNUAL_NAMED_NJ' and (k[0]=='B' and k[1].startswith('B-QB-ALIGNED-FRESHNESS-v1:') or k[0]=='C04' and k[1].startswith('C-RECEIVING-ALIGNED-TIMING-v1::')):
   scored=sorted(int(x['week_view']) for x in weekly if integer(x['combined_decided'])>0)
   if k[2] in ['FULL_A_BOARD','FULL_A733']:assert scored==[1,2,3,4,5],(k,'fiveweek',scored)
   else:assert all(1<=w<=5 for w in scored)
   assert all(integer(views.get(str(w),{}).get('combined_decided',''))==0 for w in [6,7,8]);duration.append({'group':k[0],'candidate':k[1],'view':k[2],'actual_scored_weeks':scored,'five_distinct_weeks_met':len(scored)>=5})
  weekly_checks+=1
 paired_checks=0;pairkeys=set()
 for x in pairs:
  # Public pair contracts retain category/product/source/period as independent masks.
  left,right=x['left'],x['right'];key=(x['_group'],left,right,x['view'],x['source_panel'],x.get('week_view','ALL'));assert key not in pairkeys,('DUPLICATE_PAIR',key);pairkeys.add(key)
  n=integer(x['common_decided']);a,b=integer(x['left_wins']),integer(x['right_wins']);assert max(a,b)<=n
  d=integer(x.get('side_disagreements',''));assert abs(a-b)<=d and (d+a-b)%2==0
  if x.get('win_change','')!='':assert close(float(x['win_change']),a-b)
  if x.get('accuracy_change','')!='':assert (num(x['accuracy_change']) is None if n==0 else close(float(x['accuracy_change']),(a-b)/n))
  for name,v in x.items():
   if 'interval95' in name and v:
    z=obj(v)
    if isinstance(z,list):assert len(z)==2 and all(isinstance(y,(int,float)) and math.isfinite(y) for y in z) and z[0]<=z[1]
  paired_checks+=1
 primary=read('A_EXECUTION_SUMMARY.json.xz');primary_compared=0;distinct_B_law_Briers={}
 for panel in primary['primary_panels']:
  group='B' if panel['category']=='pass_cmp' else 'C04';view='FULL_A_BOARD' if group=='B' else 'FULL_A733'
  for target in panel['own_products']:
   x=keyed[(group,target['candidate_id'],view,'ANNUAL_NAMED_NJ','ALL')]
   for side in ['OVER','UNDER','COMBINED']:
    for metric in ['selected','wins','losses','decided']:assert integer(x[side.lower()+'_'+metric])==target[side][metric],(target['candidate_id'],side,metric)
   if group=='B':
    prob=obj(x['probability']);assert prob['events']==88 and prob['Brier']>prob['neutral_binary_half_Brier']==.25
    arm=target['candidate_id'].split(':')[1];distinct_B_law_Briers[arm]=prob['Brier']
   primary_compared+=1
 assert primary_compared==20 and len(distinct_B_law_Briers)==4
 result={'id':'C-CATEGORY-INDEPENDENT-COMPLETE-AGGREGATE-CSV-v1','checked_UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'PASS_SEPARATE_PUBLIC_CSV_ARITHMETIC_AND_WEEKLY_RECONCILIATION','primary_products_matched_to_complete_CSVs':primary_compared,'distinct_B_law_Briers':distinct_B_law_Briers,'files_checked':len(files),'aggregate_rows_checked':len(summaries)+len(pairs),'summary_rows':len(summaries),'paired_rows':len(pairs),'manifest_counts':dict(counts),'unique_summary_groups':len(cumulative_groups),'weekly_reconciliations':weekly_checks,'weighted_numerical_reconciliations':weighted_numerical,'weighted_probability_reconciliations':weighted_probability,'paired_arithmetic_reconciliations':paired_checks,'duration_witnesses':duration,'null_fallback_fields_preserved':null_fallback,'probability_rows_checked':probability_rows,'files':files,'private_membership_source_clocks_model_fit':'UNKNOWN_NOT_INDEPENDENTLY_INSPECTED','bootstrap_intervals':'Bounds/cluster metadata arithmetic checked; no underlying private resampling reconstruction.','source_panels':'AnnualW1-W5 actual quotes timing-unverified; W6-W7 website-threshold diagnostics and mixed views are not pooled as authenticated offers.','B_W5_cross_source_overlap':'UNKNOWN;NO_A88_PLUS_NATIVE_B112_POOL','new_fits':0,'new_GETs':0,'new_NFL_observations':0,'CPU_seconds':time.process_time()-cpu,'peak_RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024}
 (OUT/'COMPLETE_CSV_ARITHMETIC_REVIEW.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ['files','duration_witnesses']}))
if __name__=='__main__':run()
