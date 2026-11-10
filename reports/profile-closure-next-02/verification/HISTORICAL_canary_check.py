"""Independent primitive-tree/CDF restoration of all32new historical canaries."""
import collections,datetime,hashlib,json,lzma,math,resource,time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).parent;start=time.process_time()
def read(p):return json.loads(lzma.decompress((ROOT/p).read_bytes()))
rows=[];models={};maxdelta=0.;steps=0
for year in [2025,2026]:
 for r in read(f'artifacts/receiving-timing-c04/CANARY_QUERIES-{year}.json.xz'):
  p=Path(r['model']);assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==r['model_SHA256'];a=read(p);m=a['model'];models[str(p)]=r['model_SHA256'];impute=np.asarray(m['imputation']);x=np.asarray(r['feature_vector'],float)
  assert len(x)==len(a['feature_order'])==len(impute)and m['schema']=='C-NUMERIC-LEAF-v4'and m['kind']=='count'and m['scale']==1 and len(m['trees'])==32
  z=np.concatenate([np.where(np.isfinite(x),x,impute),~np.isfinite(x)]).astype(np.float32);mass=collections.defaultdict(float)
  for tree in m['trees']:
   node=0
   while tree['left'][node]!=tree['right'][node]:node=tree['left'][node]if z[tree['feature'][node]]<=tree['threshold'][node]else tree['right'][node]
   values,counts=tree['leaves'][str(node)];assert all(v>=0 and float(v).is_integer()for v in values)and all(c>0 for c in counts)
   for value,count in zip(values,counts):mass[value]+=count/(32*sum(counts))
  assert abs(math.fsum(mass.values())-1)<1e-12
  prior=m['prior'].get(r['position'],m['global_prior']);q=prior['q'];assert 0<=q<1 and prior['kind']=='count'
  def cdf(k):return .95*math.fsum(p for v,p in mass.items()if v<=k)+.05*(0. if k<0 else 1-q**(math.floor(k)+1))
  mean=.95*math.fsum(v*p for v,p in mass.items())+.05*q/(1-q)
  median=next(k for k in range(1000)if cdf(k)>=.5);delta=abs(mean-r['expected_mean']);maxdelta=max(maxdelta,delta)
  assert delta<1e-10 and median==r['expected_median']and cdf(median-1)<.5<=cdf(median)
  grid=[cdf(k)for k in range(-1,51)];assert all(0<=p<=1+1e-12 for p in grid)and all(a<=b+1e-12 for a,b in zip(grid,grid[1:]));steps+=len(grid)-1
  rows.append(dict(origin=r['origin'],arm=r['arm'],model=str(p),mean_delta=delta,median=median))
report=dict(id='C04-INDEPENDENT-SAVED-CANARY-RESTORATION-v1',checked_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),status='PASS',new_models=len(models),canaries=len(rows),models=models,rows=rows,max_mean_absolute_difference=maxdelta,monotonic_steps=steps,CPU_seconds=time.process_time()-start,peak_RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,new_fits=0,new_NFL_observations=0,unsafe_model_loads=0,scope='SafeprimitiveJSONrestoration/independenttreewalkandempirical-geometricCDF;notrawfeature reconstruction')
(OUT/'HISTORICAL_CANARY_RESTORATION.json').write_text(json.dumps(report,indent=2)+'\n');print('C04_HISTORICAL_CANARIES_PASS',len(rows),maxdelta,report['CPU_seconds'])
