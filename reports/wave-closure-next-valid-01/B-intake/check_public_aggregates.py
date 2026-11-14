"""C independent aggregate identities; no NFL row/model/source-clock parity."""
import collections,gzip,hashlib,json,math,pathlib,datetime
ROOT=pathlib.Path(__file__).resolve().parent
def read(n):
 p=ROOT/n
 return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes())
a=read('SCORES_SOURCE.json.gz'); sel=[r for r in a if r['record_kind']=='prop_selection_evaluation']
fields=['procedure_id','product_id','strategy','cohort_id','K','rank_scope','time_panel_id','season','week']
g=collections.defaultdict(dict)
for r in sel:
 key=tuple(str(r.get(t)) for t in fields)
 assert r['side'] not in g[key]
 g[key][r['side']]=r
side_checks=0
for v in g.values():
 assert set(v)=={'over','under','Combined'}
 for r in v.values():
  m=r['selection_metrics']; w,l=m['WIN'],m['LOSS'];n=m['denominators']['decided']
  assert w+l==n
  assert m['hit_rate'] is None if n==0 else math.isclose(m['hit_rate'],w/n,abs_tol=1e-14)
  side_checks+=1
 for k in ['WIN','LOSS','PUSH']:
  assert v['over']['selection_metrics'][k]+v['under']['selection_metrics'][k]==v['Combined']['selection_metrics'][k]
 for k in ['decided','unresolved']:
  assert sum(v[s]['selection_metrics']['denominators'][k] for s in ['over','under'])==v['Combined']['selection_metrics']['denominators'][k]
results=[];weekly_checks=0
for method in ['B0','B2']:
 for policy in ['P1_MEAN','P1_LOWER_MEDIAN','P2_STATISTICAL_LAW','P90']:
  exact=[r for r in sel if r['procedure_id'].endswith(':'+method) and r['product_id']==policy and r['cohort_id']=='ALL']
  summary={}
  for side in ['over','under','Combined']:
   total=next(r for r in exact if r['week']=='ALL' and r['side']==side)
   weeks=[r for r in exact if isinstance(r['week'],int) and r['side']==side]
   if weeks:
    assert sorted(r['week'] for r in weeks)==[5,6,7,8,9]
    for k in ['WIN','LOSS','PUSH']:
     assert sum(r['selection_metrics'][k] for r in weeks)==total['selection_metrics'][k]
    weekly_checks+=1
   m=total['selection_metrics']; summary[side]={'wins':m['WIN'],'losses':m['LOSS'],'decided':m['denominators']['decided'],'rate':m['hit_rate'],'unknown':m['denominators']['unresolved'],'selected':total['n']}
  results.append({'method':method,'policy':policy,'sides':summary,'weekly':[{k:r.get(k) for k in ['week','side','n','selection_metrics','technical_unavailable','fallback_rows']} for r in exact if isinstance(r['week'],int)]})
# Exact B1 alias is checked only within the public recorded aggregate scope.
b0=[r for r in sel if r['procedure_id'].endswith(':B0')];b1=[r for r in sel if r['procedure_id'].endswith(':B1')]
def comparison_key(r):return tuple(str(r.get(k)) for k in fields[1:])+ (r['side'],)
m0={comparison_key(r):r for r in b0};m1={comparison_key(r):r for r in b1};assert not b1  # B1 support-equivalence alias has no separate scored rows
for k in m1:
 assert m0[k]['selection_metrics']==m1[k]['selection_metrics']
 assert m0[k]['query_membership_sha256']==m1[k]['query_membership_sha256']
# Compare two public calculations without executing B's scorer.
bcheck=read('INDEPENDENT_OUTPUT_ARITHMETIC_V1.json');checkmap={(r['method'],r['policy'],r['window']):r for r in bcheck['results']}
for r in results:
 p=checkmap[(r['method'] if r['method']!='B1' else 'B0',r['policy'],'ALL')]
 for side,v in r['sides'].items():
  for k in ['wins','losses','decided','rate','unknown','selected']: assert p['sides'][side][k]==v[k]
result={'id':'C-INDEPENDENT-B-FTN-PUBLIC-AGGREGATE-CHECK-v1','checked_UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'PASS_WITH_SCOPE_LIMITS','source_score_rows':len(a),'selection_side_rows':side_checks,'complete_triads':len(g),'weekly_to_cumulative_checks':weekly_checks,'B1_alias_selection_rows':len(b1),'B1_alias_scope':'B0 equality is owner-reported support-equivalence; no separate B1 scored rows or fit' ,'primary_mean_delta':{'wins_B2_minus_B0':72-76,'decided':142,'accuracy_difference':(72-76)/142,'reported_disagreement_arithmetic':{'B2_only_wins':3,'B0_only_wins':7,'difference':3-7,'raw_disagreements_not_inspected':True}},'results':results,'scope':['Independent sums/rates/Over+Under identities and weekly reconciliation over supplied public aggregates; matching B separate independent-public-calculation receipt.','No private offers/row grades/raw FTN/PBP/source vintage/model-fit/uncertainty bootstrap or website V7 membership parity.','No new fit, forecast, grade, NFL game, source observation, offered-line week or deployment created.']}
(ROOT/'INDEPENDENT_PUBLIC_AGGREGATE_CHECK.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='results'}))
