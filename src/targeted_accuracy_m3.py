"""One registered M3 rolling-origin comparison; no acquisition or new grader."""
from __future__ import annotations
import argparse,collections,gzip,hashlib,json,math,os,pathlib,resource,signal,time,zipfile
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
from targeted_data_m3 import clean,read,digest,sha
from targeted_laws_m3 import law_from_parameters,deterministic_fixtures
from targeted_boost_m3 import DistributionBoost,fit as boost_fit
from targeted_sanity_m3 import fit as sanity_fit,load as sanity_load
from laws_v2 import LeafModel
from safe_models_v4 import infer_forest,export_forest,validate_training_model,law_data
from forward_budget_v4 import complete_C_roots,tree_bytes
import abc_championship_v2 as common
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/targeted-accuracy-w1w9-01/M3'
def resource_roots():
 candidates=complete_C_roots([ROOT])+[pathlib.Path(r['path']) for r in read(ROOT/'reports/wave-closure-next-valid-01/RESOURCE_CLOSURE.json')['whole_C_roots']]+list(pathlib.Path('/tmp').glob('m3*'))+list(pathlib.Path('/tmp').glob('w1w9*'))+list(pathlib.Path('/tmp').glob('c-w1w9*'))
 result=[]
 for p in sorted(set(candidates),key=lambda x:(len(x.parts),str(x))):
  if not any(p.is_relative_to(q) for q in result):result.append(p)
 return result

REG=OUT/'REGISTRATION.json'

def write(path,obj):
 path=pathlib.Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 b=(json.dumps(clean(obj),separators=(',',':'),allow_nan=False)+'\n').encode()
 if path.suffix=='.gz':b=gzip.compress(b,mtime=0)
 if path.exists():assert path.read_bytes()==b,'FROZEN_OUTPUT_CHANGED:'+str(path)
 else:path.write_bytes(b)
 return sha(path)

def run(stage):
 reg=read(REG);assert reg['id']=='NFL-TARGETED-ACCURACY-W1W9-01-C-M3-v1'
 statefile=OUT/'FIT_LEDGER.json';state=read(statefile) if statefile.exists() else dict(attempts=[],completed=[],failures=[],CPU_seconds=0.,stages=[])
 assert not state.get('active'),'UNCLEAN_RUN_REQUIRES_SCOPED_RECOVERY'
 cp=time.process_time();wall=time.monotonic();cpu0=cp;state['active']=True
 prep=read(OUT/'inputs/FEATURES_AND_MEMBER_FACTS.json.gz');offers=read(OUT/'inputs/NATIVE_OFFERS.json.gz')['primary'];rows=prep['rows'];names=prep['feature_names'];X={t:np.array(a,float) for t,a in prep['X_by_target'].items()};index={(r['game_id'],r['player_id']):i for i,r in enumerate(rows)}
 schedule=pd.read_csv(ROOT/'sources/category-decision-release-01/schedule.csv');schedule['kickoff']=pd.to_datetime(schedule.gameday+' '+schedule.gametime).dt.tz_localize('America/New_York').dt.tz_convert('UTC').astype('int64')/1e9
 context=None
 if stage=='context':
  amendment=read(OUT/'registration/CONTEXT_ARM_AMENDMENT.json');assert amendment['execution_authorized'] and amendment['comparison_blind']
  context=read(OUT/'inputs/COMPACT_CONTEXT_MATRIX.json.gz');CX=np.array(context['matrix'],float)
  assert len(CX)==len(rows) and context['identity_order_SHA256']==digest([(r['game_id'],r['player_id']) for r in rows])
  X={t:np.c_[xx,CX] for t,xx in X.items()};names={t:nn+context['feature_names'] for t,nn in names.items()}
 arms=['M3-0','M3-1','SANITY'] if stage=='base' else ['M3-0+BLOCK','M3-2']
 allpred=[];alloffer=[];origins=[];checks=[]
 def checkpoint():
  nonlocal cp
  cur=time.process_time();state['CPU_seconds']+=cur-cp;cp=cur
  state['peak_RSS_bytes']=max(state.get('peak_RSS_bytes',0),resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024)
  state['peak_C_bytes']=max(state.get('peak_C_bytes',0),sum(tree_bytes(p) for p in resource_roots()))
  state['public_bytes']=tree_bytes(OUT);statefile.write_text(json.dumps(clean(state),separators=(',',':'))+'\n')
  assert state['CPU_seconds']<=800,'M3_SHARED_CPU_CAP_RESERVE100'
  assert time.monotonic()-wall<=2400,'M3_WALL_CAP'
  assert state['peak_RSS_bytes']<=1288490188,'M3_RSS_CAP'
  assert state['peak_C_bytes']<=2684354560,'M3_WHOLE_C_CAP'
  assert state['public_bytes']<=33554432,'M3_PUBLIC_RETENTION_CAP'
 def reserve(key):
  assert key not in state['attempts'],'FROZEN_FIT_ATTEMPT_WITHOUT_RESTORATION'
  assert len(state['attempts'])<90
  state['attempts'].append(key);checkpoint()
 def finish(key):state['completed'].append(key);checkpoint()
 def fitted(t,w,arm,xx,yy,roles,members):
  key=f'{t}-W{w:02}-{arm}';folder=OUT/'models'/t/f'W{w:02}';folder.mkdir(parents=True,exist_ok=True)
  binding=dict(id=key,rows=len(yy),membership_SHA256=digest(members),X_y_SHA256=hashlib.sha256(np.nan_to_num(xx,nan=999999.).tobytes()+yy.tobytes()).hexdigest(),feature_names=names[t],source_inputs_SHA256=sha(OUT/'inputs/FEATURES_AND_MEMBER_FACTS.json.gz'),registration_SHA256=sha(REG),code_SHA256=sha(pathlib.Path(__file__)))
  isleaf=arm.startswith('M3-0');p=folder/(arm+'.json.gz' if isleaf else arm+'.json')
  if p.exists():
   old=read(folder/(arm+'.binding.json'))
   accepted=read(OUT/'registration/RESUMPTION_METADATA_REPAIR.json')['accepted_execution_code_SHA256']
   assert all(old.get(k)==v for k,v in binding.items() if k!='code_SHA256') and old['code_SHA256'] in accepted,'RESTORE_CONTRACT_MISMATCH'
   if isleaf:model=read(p)
   elif arm=='SANITY':model=sanity_load(p)
   else:model=DistributionBoost.load(p)
   return model,p,key in state['attempts']
  if isleaf and stage=='base' and w in [2,3]:
   source=ROOT/f'reports/propline-v7/models/{t}-W{w:02}.json.gz';model=read(source)
   proof=validate_training_model(model,xx,yy,roles);binding.update(reused_model=str(source.relative_to(ROOT)),reused_model_SHA256=sha(source),training_restore=proof)
   write(p,model);write(folder/(arm+'.binding.json'),binding)
   return model,p,False
  reserve(key)
  if isleaf:
   model0=LeafModel('count' if t=='rec' else 'signed',1).fit(xx,yy,roles);model=export_forest(model0);write(p,model)
   probe=infer_forest(model,xx[:2],roles[:2]);native=model0.laws(xx[:2],roles[:2]);assert max(abs(a.mean()-b.mean()) for a,b in zip(probe,native))<1e-10
  elif arm=='SANITY':model=sanity_fit(xx,yy,t,names[t]);model.save(p)
  else:model=boost_fit(xx,yy,t,names[t]);model.save(p)
  write(folder/(arm+'.binding.json'),binding);finish(key)
  return model,p,True
 def params_laws(t,model,xx,roles,isleaf):
  if isleaf:return infer_forest(model,xx,roles),None
  pp=model.predict_params(xx,names[t]);laws=[law_from_parameters(t,{k:float(v[j]) for k,v in pp.items()}) for j in range(len(xx))]
  return laws,pp
 def output_offer(o,arm,product,law,pred):
  p=law.probability(o['line']);mean=pred['mean'];median=pred['median']
  if product=='LAW':side='OVER' if p['over']>p['under']+1e-12 else 'UNDER' if p['under']>p['over']+1e-12 else 'ABSTAIN'
  else:
   point=mean if product=='MEAN' else median
   side=None if point is None else 'OVER' if point>o['line'] else 'UNDER' if point<o['line'] else 'ABSTAIN'
  status='UNAVAILABLE_FORECAST' if side is None else 'ABSTAIN' if side=='ABSTAIN' else 'UNKNOWN_PARTICIPATION' if o['appearance']!='PLAYED' else 'MISSING_ACTUAL' if o['actual'] is None else 'PUSH' if o['actual']==o['line'] else 'WIN' if (o['actual']>o['line'])==(side=='OVER') else 'LOSS'
  rr={k:v for k,v in o.items() if k not in ['retained_methods','repeated_offer_ids']};rr.update(arm=arm,product=product,method=arm+'_'+product,procedure=reg['id']+'::'+arm+'::'+product,selected_side=side,status=status,probabilities=p,mean=mean,median=median,point=mean if product=='MEAN' else median if product=='MEDIAN' else None,point_type=product if product!='LAW' else None,learned=True,fallback=False,model_binding=pred['model_binding'],query_universe_tier=pred['query_universe_tier'])
  assert common.status(rr)==status
  if o['actual'] is not None and o['appearance']=='PLAYED':rr['outcome_log_mass']=law.logpmf(o['actual'])
  return rr
 try:
  signal.signal(signal.SIGPROF,lambda *_:(_ for _ in ()).throw(RuntimeError('M3_CPU_TIMER')));signal.setitimer(signal.ITIMER_PROF,max(.01,800-state['CPU_seconds']))
  checkpoint()
  for w in range(1,10):
   cut=float(schedule.loc[(schedule.season==2026)&(schedule.week==w),'kickoff'].min());qi=prep['query_indices_2026'][str(w)];qroles=np.array([rows[i]['position'] for i in qi]);assert all(rows[i]['kickoff']>=cut for i in qi)
   for t in ['rec','rec_yd']:
    ti=[i for i,r in enumerate(rows) if not r['query_only'] and r['available'] is not None and r['available']<cut and r['values'][t] is not None]
    yy=np.array([rows[i]['values'][t] for i in ti],float);roles=np.array([rows[i]['position'] for i in ti]);members=[(rows[i]['game_id'],rows[i]['player_id']) for i in ti]
    assert not ({rows[i]['game_id'] for i in ti}&{rows[i]['game_id'] for i in qi})
    base_origin=dict(target=t,week=w,origin_UTC=pd.Timestamp(cut,unit='s',tz='UTC').isoformat(),latest_training_available_UTC=pd.Timestamp(max(rows[i]['available'] for i in ti),unit='s',tz='UTC').isoformat(),training_rows=len(ti),query_rows=len(qi),membership_SHA256=digest(members),strict_latest_before_origin=True)
    for arm in arms:
     model,path,newfit=fitted(t,w,arm,X[t][ti],yy,roles,members);laws,pp=params_laws(t,model,X[t][qi],qroles,arm.startswith('M3-0'))
     # Representative saved restoration plus order/single inference; no fresh refit.
     restored=read(path) if arm.startswith('M3-0') else sanity_load(path) if arm=='SANITY' else DistributionBoost.load(path)
     probe,_=params_laws(t,restored,X[t][qi[:2]],qroles[:2],arm.startswith('M3-0'))
     assert all(abs(a.cdf(3)-b.cdf(3))<1e-10 for a,b in zip(laws[:2],probe))
     if not arm.startswith('M3-0'):
      p1=model.predict_params(X[t][qi[:1]],names[t]);assert all(abs(float(p1[k][0])-float(pp[k][0]))<1e-6 for k in pp)
     modelbind={'path':str(path.relative_to(ROOT)),'SHA256':sha(path),'output':'DISCRETE_LAW','stage':stage}
     origin=dict(base_origin,arm=arm,model_binding=modelbind,new_fit=newfit)
     if pp is not None:origin['parameter_spread']={k:{'min':float(np.min(v)),'max':float(np.max(v)),'std':float(np.std(v)),'distinct':len(np.unique(v))} for k,v in pp.items()}
     if not arm.startswith('M3-0') and arm!='SANITY':origin['fitted_feature_usage']=model.feature_usage()
     if arm=='SANITY':origin['convergence']=model.diagnostics
     origins.append(origin)
     native={(o['game_id'],o['player_id']):o for o in offers if o['category']==t and o['week']==w}
     for j,i in enumerate(qi):
      r=rows[i];law=laws[j]
      probs=[law.cdf(k) for k in ([-20,-1,0,1,5,30,300] if t=='rec_yd' else [-1,0,1,5,30,300])];assert np.isfinite(probs).all() and np.all(np.diff(probs)>=-1e-12)
      y=r['values'][t];pred={k:r.get(k) for k in ['game_id','player_id','position','team','opponent_team','season','week','query_only','native_offer_query','query_universe_tier']};pred.update(category=t,arm=arm,actual=y,mean=law.mean(),median=law.quantile(.5),variance=law.variance() if hasattr(law,'variance') else None,learned=True,fallback=False,model_binding=modelbind,feature_age_policy=reg['history'])
      if pp is not None:pred['parameters']={k:float(v[j]) for k,v in pp.items()}
      else:pred['law']=law_data(law)
      if y is not None:pred['outcome_log_mass']=law.logpmf(y)
      allpred.append(pred)
      o=native.get((r['game_id'],r['player_id']))
      if o:
       for product in ['LAW','MEAN','MEDIAN']:alloffer.append(output_offer(o,arm,product,law,pred))
     checkpoint()
     write(OUT/'checkpoints'/f'{stage}-{t}-W{w:02}-{arm}.json',origin)
    print('ORIGIN_COMPLETE',stage,t,w,len(ti),len(qi),round(state['CPU_seconds'],2),flush=True)
   write(OUT/f'{stage}-PREDICTIONS.json.gz',allpred) if w==9 else None
  # Append retained same-case controls, never a revised incumbent recreation.
  if stage=='base':
   for o in offers:
    for method in ['ALWAYS_OVER','ALWAYS_UNDER','P1_MEAN','P1_MEDIAN','P3_DIRECT']:
     m=o['retained_methods'].get(method)
     if m is None:continue
     r={k:v for k,v in o.items() if k not in ['retained_methods','repeated_offer_ids']};arm='CONTROL_'+method
     pp={s:m.get('p_'+s) for s in ['under','push','over']};pp=pp if all(v is not None for v in pp.values()) else None
     r.update(arm=arm,product='LAW' if method=='P3_DIRECT' else 'MEAN' if method=='P1_MEAN' else 'MEDIAN' if method=='P1_MEDIAN' else 'CONSTANT',selected_side=m['selected_side'],status=m['status'],probabilities=pp,mean=m.get('point') if method=='P1_MEAN' else None,median=m.get('point') if method=='P1_MEDIAN' else None,fallback=m.get('fallback'),learned=method not in ['ALWAYS_OVER','ALWAYS_UNDER'],method_version=m['method_version'])
     assert common.status(r)==r['status'];alloffer.append(r)
  write(OUT/f'{stage}-OFFER_ROWS.json.gz',alloffer);write(OUT/f'{stage}-ORIGINS.json',origins)
  # Test fixed policy admission against future/target label mutation on all origins.
  for origin in origins:
   t,w=origin['target'],origin['week'];cut=pd.Timestamp(origin['origin_UTC']).timestamp();old=[i for i,r in enumerate(rows) if not r['query_only'] and r['available'] is not None and r['available']<cut and r['values'][t] is not None]
   mutated=[dict(r,values={k:(999999 if r['available'] is None or r['available']>=cut else v) for k,v in r['values'].items()}) for r in rows]
   new=[i for i,r in enumerate(mutated) if not r['query_only'] and r['available'] is not None and r['available']<cut and r['values'][t] is not None]
   assert old==new and np.array_equal(np.array([rows[i]['values'][t] for i in old]),np.array([mutated[i]['values'][t] for i in new]))
  checks.append({'future_target_label_admission_mutation':'PASS_ALL_ORIGINS','scope':'Training memberships and labels under fixed admitted primitivefeatures; does not authenticate vintage or independently rebuildfeatures.'})
  write(OUT/f'{stage}-CHECKS.json',checks)
  state['stages'].append({'stage':stage,'status':'COMPLETE','CPU_seconds':time.process_time()-cpu0,'wall_seconds':time.monotonic()-wall,'origin_products':len(origins),'query_product_rows':len(allpred),'offer_product_rows':len(alloffer)})
 except Exception as e:
  state['failures'].append({'stage':stage,'error':type(e).__name__+':'+str(e)});raise
 finally:
  signal.setitimer(signal.ITIMER_PROF,0);state['active']=False;checkpoint()
 return state
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('stage',choices=['base','context']);a=p.parse_args()
 with threadpool_limits(limits=1):print(json.dumps(run(a.stage),indent=2))
