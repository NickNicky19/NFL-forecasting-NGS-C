"""Separate arithmetic review of permitted public aggregates; no author scorer/fit."""
from pathlib import Path
import collections,datetime,hashlib,json,lzma,math,resource,time
ROOT=Path(__file__).resolve().parents[1]
OUT=Path(__file__).resolve().parent

def load(name):
 p=ROOT/name;b=p.read_bytes();return json.loads(lzma.decompress(b) if p.suffix=='.xz' else b)
def bind(name):
 p=ROOT/name;return {'path':str(p.relative_to(ROOT.parent.parent.parent)),'bytes':p.stat().st_size,'SHA256':hashlib.sha256(p.read_bytes()).hexdigest()}
def near(a,b):return abs(float(a)-float(b))<=1e-12

def main():
 started=time.process_time();s=load('A_EXECUTION_SUMMARY.json.xz');assert len(s['primary_panels'])==2
 products=[];controls=[];contrasts=[];allchecks=0
 for panel in s['primary_panels']:
  cat=panel['category'];assert panel['actual_retained_line_weeks']==[1,2,3,4,5]
  assert panel['separate_diagnostic_weeks']==[6,7]
  expected=88 if cat=='pass_cmp' else 412
  own={x['candidate_id']:x for x in panel['own_products']}
  for x in [*panel['own_products'],*panel['strongest_retained_controls']]:
   o,u,c=x['OVER'],x['UNDER'],x['COMBINED']
   for z in [o,u,c]:
    assert all(isinstance(z[k],int) and z[k]>=0 for k in ['wins','losses','decided','selected'])
    assert z['decided']==z['wins']+z['losses'] and z['selected']>=z['decided']
    assert near(z['rate'],z['wins']/z['decided']) if z['decided'] else z['rate'] is None
   assert all(c[k]==o[k]+u[k] for k in ['wins','losses','decided','selected'])
   assert c['decided']==expected and near(x['coverage'],c['selected']/x['eligible'])
   n=x['numerical']
   if x['candidate_id'].endswith('::P2'):
    assert n['scored']==0 and all(n[k] is None for k in ['MAE','MSE','bias'])
   else:
    assert n['scored']==expected and all(math.isfinite(n[k]) for k in ['MAE','MSE','bias'])
    assert n['MAE']>=abs(n['bias'])-1e-12 and n['MSE']>=n['MAE']**2-1e-10
   if 'states' in x:
    states=x['states'];assert states['WIN']==c['wins'] and states['LOSS']==c['losses'];assert sum(states.values())==x['eligible']
    assert states.get('UNAVAILABLE_FORECAST',0)==x['unavailable']
    unknown=states.get('UNKNOWN_PARTICIPATION',0)
    assert x['eligible']==c['selected']+x['unavailable']
    assert c['selected']==c['decided']+unknown
   row={'category':cat,'candidate_id':x['candidate_id'],'O':o,'U':u,'combined':c,'eligible':x['eligible'],'games':x['games'],'evidence':panel['evidence_tier']}
   (products if x['candidate_id'] in own else controls).append(row);allchecks+=1
  for x in panel['within_method_contrasts']:
   l,r=x['left'],x['right'];a,b=own[l],own[r]
   delta=a['COMBINED']['wins']-b['COMBINED']['wins']
   assert x['left_wins']==a['COMBINED']['wins'] and x['right_wins']==b['COMBINED']['wins']
   assert x['common_decided']==expected and x['game_clusters']==(51 if cat=='pass_cmp' else 53) and x['week_clusters']==5
   assert abs(delta)<=x['side_disagreements'] and (x['side_disagreements']+delta)%2==0
   if 'win_change' in x:assert x['win_change']==delta
   if 'accuracy_change' in x:assert near(x['accuracy_change'],delta/expected)
   if 'MAE_change' in x:
    if x['MAE_change'] is None:assert a['numerical']['MAE'] is None and b['numerical']['MAE'] is None
    else:assert near(x['MAE_change'],a['numerical']['MAE']-b['numerical']['MAE'])
   if 'numerical_paired' in x:assert near(x['numerical_paired']['MAE_change'],a['numerical']['MAE']-b['numerical']['MAE'])
   for k,v in x.items():
    if 'interval95' in k and isinstance(v,list):assert len(v)==2 and all(math.isfinite(z) for z in v) and v[0]<=v[1]
   contrasts.append({'left':l,'right':r,'win_change':delta,'decided':expected,'percentage_point_change':100*delta/expected,'disagreements':x['side_disagreements']});allchecks+=1
 # Check product identities separately, even when observed totals happen to match.
 b=s['primary_panels'][0];d={x['candidate_id']:x for x in b['own_products']}
 f0=d['B-QB-ALIGNED-FRESHNESS-v1:F0::lower_median'];f2=d['B-QB-ALIGNED-FRESHNESS-v1:F2::mean']
 assert f0['COMBINED']['wins']==f2['COMBINED']['wins']==47
 assert f0['candidate_id']!=f2['candidate_id']
 assert s['W5_overlap']['state']=='UNKNOWN_PRIVATE_NORMALIZED_MEMBERSHIP_NOT_EXPORTED'
 assert s['actual_new_comparison_coverage']['B']['annual_W1_W5_offers_decided']==88
 assert s['actual_new_comparison_coverage']['B']['separate_W6_W7_diagnostic_offers']==56
 assert s['actual_new_comparison_coverage']['C04']['annual_decided']==412
 assert s['actual_new_comparison_coverage']['C04']['all_decided']==667
 assert 'No transfer from typed point join' in s['five_week']['C_probability']
 assert all(d['B-QB-ALIGNED-FRESHNESS-v1:'+f+'::P2']['COMBINED']==d['B-QB-ALIGNED-FRESHNESS-v1:'+f+'::lower_median']['COMBINED'] for f in ['F0','F1','F2','F3'])
 assert all(d['B-QB-ALIGNED-FRESHNESS-v1:'+f+'::mean']['COMBINED']['wins']<=47 for f in ['F0','F1','F2','F3'])
 rec=s['primary_panels'][1];dr={x['candidate_id']:x for x in rec['own_products']}
 assert dr['C-RECEIVING-ALIGNED-TIMING-v1::F2::MEAN']['COMBINED']['wins']-dr['C-RECEIVING-ALIGNED-TIMING-v1::F0::MEAN']['COMBINED']['wins']==-20
 assert dr['C-RECEIVING-ALIGNED-TIMING-v1::F3::MEAN']['COMBINED']['wins']-dr['C-RECEIVING-ALIGNED-TIMING-v1::F1::MEAN']['COMBINED']['wins']==-8
 assert dr['C-RECEIVING-ALIGNED-TIMING-v1::F2::MEDIAN']['COMBINED']['wins']==dr['C-RECEIVING-ALIGNED-TIMING-v1::F0::MEDIAN']['COMBINED']['wins']
 assert dr['C-RECEIVING-ALIGNED-TIMING-v1::F3::MEDIAN']['COMBINED']['wins']-dr['C-RECEIVING-ALIGNED-TIMING-v1::F1::MEDIAN']['COMBINED']['wins']==-1
 receipt={'id':'C-CATEGORY-INDEPENDENT-PUBLIC-ARITHMETIC-v1','checked_UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'PASS_PRIMARY_PUBLIC_AGGREGATE_ARITHMETIC_AND_COMPLETE_CSV_PARITY' if (OUT/'COMPLETE_CSV_ARITHMETIC_REVIEW.json').exists() else 'PASS_PRIMARY_PUBLIC_AGGREGATE_ARITHMETIC;FULL_CSV_REVIEW_PENDING','input':bind('A_EXECUTION_SUMMARY.json.xz'),'distinct_products_checked':len(products),'strong_control_products_checked':len(controls),'within_method_contrasts_checked':len(contrasts),'checks_of_products_controls_and_contrasts':allchecks,'products':products,'controls':controls,'contrasts':contrasts,'B_F0_median_vs_F2_mean':'SAME_OBSERVED_TOTAL_NOT_SAME_PROCEDURE','B_P2_vs_median':'Direction counts equal on this panel; laws/probability and point product identities remain separate.','C_F2_F3_fallback_or_imputation_flags':'UNKNOWN_NOT_EXPORTED;NULL_NOT_ZERO','duration':'Five scored2026W1-W5 actual-offer weeks at quote/decision-time-unverified retrospective tier only.','W5_overlap':'UNKNOWN_PRIVATE_NORMALIZED_MEMBERSHIP_NOT_EXPORTED;DO_NOT_ADD_A88_AND_B112','confidence_intervals':'Arithmetic/bounds and reported cluster counts checked; private per-game/week vectors not received, so bootstrap intervals remain OWNER_REPORTED_NOT_INDEPENDENTLY_RECONSTRUCTED.','private_limits':['No private offer/forecast/label membership independently read.','No historical source clocks or underlying fitted model parity established.','No future packet/consumer admission or release verified by this calculation.'],'new_fits':0,'GETs':0,'new_NFL_observations':0,'CPU_seconds':time.process_time()-started,'peak_RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024}
 (OUT/'PRIMARY_ARITHMETIC_REVIEW.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({k:v for k,v in receipt.items() if k not in ['products','controls','contrasts']}))
if __name__=='__main__':main()
