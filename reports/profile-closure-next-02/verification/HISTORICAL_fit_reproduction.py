"""One preregistered fresh fit through a separate sklearn assembly; primitive state."""
import collections,datetime,hashlib,json,lzma,math,resource,time
from pathlib import Path
import numpy as np
from sklearn.ensemble import ExtraTreesRegressor
from threadpoolctl import threadpool_limits
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).parent
CPU=time.process_time()
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def read(p):
 p=ROOT/p if not Path(p).is_absolute()else Path(p);b=p.read_bytes();return json.loads(lzma.decompress(b)if p.suffix=='.xz'else b)
def sha(p):return hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
def write(p,obj):
 b=(json.dumps(obj,separators=(',',':'),allow_nan=False)+'\n').encode();p.write_bytes(lzma.compress(b)if p.suffix=='.xz'else b)
def prior(y):
 return dict(kind='count',empty=len(y)==0,mu=float(np.mean(y))if len(y)else 0.,center=int(np.median(y))if len(y)else 0,q=(max(.05,float(np.mean(y)))/(1+max(.05,float(np.mean(y)))))if len(y)else .05/1.05,event=(float(np.sum(y))+1)/(len(y)+2))

def main():
 dataset=Path('artifacts/receiving-timing-c04/FIT_REPRODUCTION_DATASET-2025-W01-F3.json.xz');expectedfile=Path('artifacts/receiving-timing-c04/2025-W01-F3.json.xz');d=read(dataset);e=read(expectedfile)
 assert sha(dataset)=='2f757c8376dd3b1e1bf2f56f10efcf2e1f7fe9890224f41f146e1acfb89b877d'
 assert d['origin']=='2025-W01'and d['arm']=='F3'and d['chosen_before_2025_comparative_scores']is True
 def arr(v):
  a=np.asarray(v['values'],dtype=np.dtype(v['dtype']));assert list(a.shape)==v['shape'];return a
 X,y,roles=arr(d['X']),arr(d['y']),arr(d['roles'])
 assert X.shape==(14611,58)and y.shape==roles.shape==(14611,)
 members=d['membership'];assert len(members)==len({tuple(m)for m in members})==len(y)
 assert all(int(m[0][:4])<2025 for m in members),'TARGET_OR_FUTURE_TRAINING_ID'
 mh=hashlib.sha256(json.dumps(members,separators=(',',':')).encode()).hexdigest();assert mh==d['membership_SHA256']==e['membership_SHA256']
 fp=hashlib.sha256(np.nan_to_num(X,nan=999999.).tobytes()+y.tobytes()).hexdigest();assert fp==d['fingerprint']==e['fingerprint']
 assert d['feature_order']==e['feature_order']and d['core_code_SHA256']==e['code_SHA256']
 impute=np.asarray([np.median(c[np.isfinite(c)])if np.isfinite(c).any()else 0. for c in X.T]);Z=np.concatenate([np.where(np.isfinite(X),X,impute),~np.isfinite(X)],axis=1)
 target=OUT/'HISTORICAL_REPRODUCED_MODEL.json.xz';attempt=OUT/'HISTORICAL_FIT_ATTEMPT.json'
 if target.exists():
  fitted=read(target);newfit=0
 else:
  assert not attempt.exists(),'PREVIOUS_ATTEMPT_NO_RECOVERED_MODEL_DO_NOT_REFIT'
  a=dict(id='C04-INDEPENDENT-ONE-FIT-ATTEMPT-v1',origin=d['origin'],arm=d['arm'],started_UTC=now(),dataset_SHA256=sha(dataset),fit_limit=1,fit_started=True,state='STARTED');write(attempt,a)
  try:
   with threadpool_limits(limits=1):
    forest=ExtraTreesRegressor(n_estimators=32,max_depth=8,min_samples_leaf=30,max_features=1.,bootstrap=False,random_state=1701,n_jobs=1).fit(Z,y)
   leaves=forest.apply(Z);trees=[]
   for j,estimator in enumerate(forest.estimators_):
    t=estimator.tree_;nodes={}
    for k in np.unique(leaves[:,j]):
     values,counts=np.unique(y[leaves[:,j]==k],return_counts=True);nodes[str(int(k))]=[values.tolist(),counts.tolist()]
    trees.append(dict(left=t.children_left.tolist(),right=t.children_right.tolist(),feature=t.feature.tolist(),threshold=t.threshold.tolist(),leaves=nodes))
   fitted=dict(schema='C-NUMERIC-LEAF-v4',kind='count',scale=1,imputation=impute.tolist(),prior={str(p):prior(y[roles==p])for p in set(roles)},global_prior=prior(y),trees=trees)
   write(target,fitted);a.update(completed_UTC=now(),state='COMPLETED_MODEL_RETAINED',new_fits=1,CPU_seconds=time.process_time()-CPU);write(attempt,a);newfit=1
  except BaseException as error:
   a.update(failed_UTC=now(),state='FAILED_PRESERVE_ATTEMPT',error=repr(error),CPU_seconds=time.process_time()-CPU);write(attempt,a);raise
 expected=e['model'];assert fitted==expected,'FRESH_PRIMITIVE_FOREST_DIFFERS'
 def law(x,role):
  x=np.asarray(x,float);z=np.concatenate([np.where(np.isfinite(x),x,impute),~np.isfinite(x)]).astype(np.float32);mass=collections.defaultdict(float)
  for tree in fitted['trees']:
   n=0
   while tree['left'][n]!=tree['right'][n]:n=tree['left'][n]if z[tree['feature'][n]]<=tree['threshold'][n]else tree['right'][n]
   values,counts=tree['leaves'][str(n)];total=sum(counts)
   for v,c in zip(values,counts):mass[v]+=c/(32*total)
  p=fitted['prior'].get(role,fitted['global_prior']);q=p['q'];a=.05 if mass else 1.
  def cdf(k):return(1-a)*math.fsum(v for y,v in mass.items()if y<=k)+a*(0. if k<0 else 1-q**(math.floor(k)+1))
  def quantile(t):
   for k in range(10000):
    if cdf(k)>=t:return float(k)
   raise AssertionError('TAIL_NOT_REACHED')
  mean=(1-a)*math.fsum(y*v for y,v in mass.items())+a*q/(1-q)
  return cdf,quantile,mean
 numerical={ (r['game_id'],r['player_id']):r for r in read('artifacts/receiving-timing-c04/NUMERICAL_ROWS-2025.json.xz') }
 sample=[];monotone=0;pushchecks=0
 for r in d['query_sample']:
  cdf,q,mean=law(r['features'],r['role']);saved=numerical[r['game_id'],r['player_id']]['F3'];diffs=[abs(mean-saved['mean'])]
  assert diffs[0]<1e-10
  for key,t in [('median',.5),('p05',.05),('p95',.95)]:assert q(t)==saved[key]
  grid=list(range(-1,51));p=[cdf(k)for k in grid];assert all(0<=v<=1+1e-12 for v in p)and all(a<=b+1e-12 for a,b in zip(p,p[1:]));monotone+=len(grid)-1
  for k in range(16):
   under,push,over=cdf(k-1),cdf(k)-cdf(k-1),1-cdf(k);assert min(under,push,over)>=-1e-12 and abs(under+push+over-1)<1e-12;pushchecks+=1
  sample.append(dict(game_id=r['game_id'],player_id=r['player_id'],role=r['role'],mean=mean,median=q(.5),max_mean_delta=diffs[0]))
 report=dict(id='C04-INDEPENDENT-FRESH-FIT-2025W01F3-v1',status='PASS',checked_UTC=now(),origin='2025-W01',arm='F3',new_fits=newfit,total_verification_fit_attempts=1,training_rows=len(y),features=X.shape[1],membership_SHA256=mh,fingerprint=fp,dataset_SHA256=sha(dataset),expected_model_SHA256=sha(expectedfile),fresh_model_path=str(target.relative_to(ROOT)),fresh_model_SHA256=sha(target.relative_to(ROOT)),primitive_forest_exact=True,representative_queries=sample,monotonic_steps=monotone,integer_push_normalizations=pushchecks,CPU_seconds=time.process_time()-CPU,peak_RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,method='Independent median/imputation/design, directsklearnExtraTreesfit and primitiveforest/roleprior/leafcounts reconstruction; ownCDF/quantile calculation',scope='Freshfitofretaineddeclaredtrainingdesign;notanewraw-source reconstruction or NFL observation; earliersemantic/chronology receipts reused',NFL_observations_added=0)
 receipt=OUT/'HISTORICAL_FIT_REPRODUCTION.json'
 if receipt.exists():receipt=OUT/'HISTORICAL_FIT_REPEAT_READBACK.json'
 write(receipt,report);print(json.dumps({k:v for k,v in report.items()if k in['status','new_fits','CPU_seconds','primitive_forest_exact']}))
if __name__=='__main__':main()
