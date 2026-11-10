"""Exactly one registered independent 2026-W02-R3 verification fit; no GETs."""
import gzip, hashlib, json, lzma, math, resource, signal, sys, time, warnings
from pathlib import Path
START=time.process_time()
ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'reports/profile-increment-v2/verification'
PLAN=OUT/'FRESH_FIT_PLAN.json'
ATTEMPT=OUT/'FRESH_FIT_ATTEMPT.json'
RECEIPT=OUT/'FRESH_FIT_RECEIPT.json'
assert not ATTEMPT.exists() and not RECEIPT.exists(),'No automatic retry'
def write(p,d):p.write_text(json.dumps(d,separators=(',',':'),allow_nan=False)+'\n')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
 p=Path(p);b=p.read_bytes();return json.loads(lzma.decompress(b)if p.suffix=='.xz'else gzip.decompress(b)if p.suffix=='.gz'else b)
attempt=dict(id='C03-INDEPENDENT-FRESH-FIT-v1',plan_SHA256=sha(PLAN),origin='2026-W02',arm='R3',fits=0,network=0,stage='STARTED',phases=[])
write(ATTEMPT,attempt)
def checkpoint(stage):
 attempt['stage']=stage;attempt['CPU_seconds']=time.process_time()-START;attempt['peak_RSS_bytes']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
 attempt['phases'].append([stage,attempt['CPU_seconds'],attempt['peak_RSS_bytes']]);write(ATTEMPT,attempt)
 assert attempt['CPU_seconds']<120 and attempt['peak_RSS_bytes']<=805306368
def capped(*_):raise RuntimeError('Fresh fit120CPUcap;no auto retry')
signal.signal(signal.SIGPROF,capped);signal.setitimer(signal.ITIMER_PROF,120)
try:
 sys.path.insert(0,str(ROOT/'src'))
 import numpy as np,pandas as pd
 from threadpoolctl import threadpool_limits
 from sklearn.ensemble import ExtraTreesRegressor
 import sklearn,scipy
 from data_v2 import load,History,vector
 from context_features_c01 import Context,OWN_NAMES
 from context_sources_c01 import pbp_path
 from receiving_defense_c03 import ReceivingDefense,SUPPORT_NAMES,VALUE_NAMES
 from receiving_profiles_c02 import BASE_NAMES
 from laws_v2 import LeafModel,Prior
 from safe_models_v4 import export_forest,infer_forest
 checkpoint('IMPORTS')
 inp=Path('/workspace/c-v2/corrected-inputs');late=ROOT/'prospective/runs/C-FWD-v4-20261105-W09-JAXBAL-remainder/sources'
 source24=ROOT/'sources/player-context-matchup-01/completion-decision-v1/pbp_facts_2024.csv.xz'
 d,g,teams=load(inp);dd,gg,tt=load(late)
 d=pd.concat([d,dd[(dd.season==2026)&(dd.week==8)]],ignore_index=True)
 teams=pd.concat([teams,tt[(tt.season==2026)&(tt.week==8)]],ignore_index=True)
 g=pd.concat([g[~((g.season==2026)&(g.week==8))],gg[(gg.season==2026)&(gg.week==8)]],ignore_index=True)
 cols=['game_id','team','season','week','attempts','completions','targets'];raw=pd.read_csv(inp/'facts.csv.gz',usecols=cols);fresh=pd.read_csv(late/'facts.csv.gz',usecols=cols)
 allrows=pd.concat([raw,fresh[(fresh.season==2026)&(fresh.week==8)]])
 counts={}
 for key,f in allrows.groupby(['game_id','team'],sort=False):
  a=f[['attempts','completions','targets']].to_numpy(float);counts[key]=dict(zip(['attempts','completions','targets'],a.sum(axis=0)))
  counts[key]['complete']=bool(np.isfinite(a).all()and(a>=0).all()and(a==np.floor(a)).all())
 frames=[pd.read_csv(source24,low_memory=False)]+[pd.read_csv(pbp_path(y),low_memory=False)for y in[2025,2026]]
 context=Context(frames,d,g,strict=True,all_position_counts=counts)
 pool=d[d.position.isin(['RB','WR','TE'])].to_dict('records')
 defense=ReceivingDefense(frames,pd.DataFrame(pool),g,context=context)
 hist=History(d[d.season>=2022],'player_id');th=History(teams[teams.season>=2022],'team')
 cutoff=float(g[(g.season==2026)&(g.week==2)].kickoff.min())
 training=[r for r in pool if r['available']<cutoff and r['values']['rec']is not None]
 queries=[r for r in pool if r['season']==2026 and r['week']==2]
 checkpoint('REGISTERED_SOURCE_CONSTRUCTORS')
 def features(r):
  b=vector(r,'rec',hist,th,'E0_OP');o=context.own(r,8);dv=defense.vector(r)
  return np.r_[b,o[:5],dv[:4],o[5:],dv[4:]]
 x=np.array([features(r)for r in training]);y=np.array([r['values']['rec']for r in training]);roles=np.array([r['position']for r in training])
 qx=np.array([features(r)for r in queries]);qroles=np.array([r['position']for r in queries])
 members=[(r['game_id'],r['player_id'])for r in training]
 fingerprint=hashlib.sha256(np.nan_to_num(x,nan=999999.).tobytes()+y.tobytes()).hexdigest()
 membership=hashlib.sha256(json.dumps(members,separators=(',',':')).encode()).hexdigest()
 original_path=ROOT/'artifacts/profile-increment-v2/2026-W02-R3.json.xz';original=read(original_path)
 assert fingerprint==original['fingerprint']and membership==original['membership_SHA256']and len(y)==original['training_rows']
 names=BASE_NAMES+OWN_NAMES[:5]+SUPPORT_NAMES+OWN_NAMES[5:]+VALUE_NAMES
 assert names==original['feature_order']and x.shape[1]==68
 assert max(r['available']for r in training)<cutoff and not({r['game_id']for r in training}&{r['game_id']for r in queries})
 checkpoint('MATRIX_FINGERPRINT_AND_MEMBERSHIP_VERIFIED')
 with warnings.catch_warnings():
  warnings.simplefilter('ignore',RuntimeWarning);impute=np.nanmedian(x,axis=0)
 impute=np.where(np.isfinite(impute),impute,0.)
 design=np.c_[np.where(np.isfinite(x),x,impute),~np.isfinite(x)].astype(float)
 forest=ExtraTreesRegressor(n_estimators=32,max_depth=8,min_samples_leaf=30,max_features=1.,bootstrap=False,random_state=1701,n_jobs=1)
 attempt['fits']=1;checkpoint('FIT_ATTEMPT_RECORDED')
 with threadpool_limits(limits=1):forest.fit(design,y)
 checkpoint('ONE_NATIVE_FIT_COMPLETED')
 # Reconstruct distributional wrapper independently of LeafModel.fit.
 native=LeafModel('count',1);native.m=impute;native.model=forest
 native.prior={p:Prior(y[roles==p],'count')for p in set(roles)};native.global_prior=Prior(y,'count')
 leafids=forest.apply(design);native.leaves=[]
 for j in range(32):
  native.leaves.append({int(node):np.unique(y[leafids[:,j]==node],return_counts=True)for node in np.unique(leafids[:,j])})
 primitive=export_forest(native)
 canonical=lambda obj:json.dumps(obj,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
 oldhash=hashlib.sha256(canonical(original['model'])).hexdigest();newhash=hashlib.sha256(canonical(primitive)).hexdigest()
 assert oldhash==newhash,'Decoded model differs;no automatic refit'
 with threadpool_limits(limits=1):
  native_laws=native.laws(qx,qroles);safe=infer_forest(primitive,qx,qroles)
  order=list(reversed(range(len(qx))));shuffled=infer_forest(primitive,qx[order],qroles[order])
 saved={(r['game_id'],r['player_id']):r for r in read(ROOT/'artifacts/profile-increment-v2/NUMERICAL_ROWS-2026.json.xz')}
 maxdelta=0.;probdelta=0.
 for i,(r,n,s)in enumerate(zip(queries,native_laws,safe)):
  old=saved[(r['game_id'],r['player_id'])]['R3'];maxdelta=max(maxdelta,abs(n.mean()-old['mean']),abs(s.mean()-old['mean']),abs(shuffled[len(qx)-1-i].mean()-old['mean']))
  assert n.quantile(.5)==s.quantile(.5)==old['median']
  for line in[0.,.5,2.,2.5,10.5]:
   a=n.probability(line);b=s.probability(line);probdelta=max(probdelta,max(abs(a[k]-b[k])for k in a))
 assert maxdelta<1e-10 and probdelta<1e-12
 first=next(i for i,r in enumerate(queries)if r['position']in['WR','TE'])
 single=infer_forest(primitive,qx[first:first+1],qroles[first:first+1])[0]
 assert abs(single.mean()-safe[first].mean())<1e-12
 assert names[:32]==BASE_NAMES and original['feature_order']==names
 checkpoint('NATIVE_SAFE_SAVED_BATCH_SHUFFLE_PARITY')
 receipt=dict(id=attempt['id'],status='PASS',scope='One fresh training-path verification,not an additional NFL improvement/holdout experiment',
  fits=1,improvement_fits_unchanged=48,network_requests=0,origin='2026-W02',arm='R3',source_version='Existing frozen2024/25/26 context and ordinary2022-expanding;strict kickoff+7d',
  model=str(original_path.relative_to(ROOT)),original_model_SHA256=sha(original_path),plan_SHA256=sha(PLAN),fingerprint=fingerprint,membership_SHA256=membership,
  training_rows=len(y),input_features=x.shape[1],query_rows=len(qx),latest_training_available=max(r['available']for r in training),fit_cutoff=cutoff,
  decoded_original_model_SHA256=oldhash,decoded_fresh_model_SHA256=newhash,decoded_model_exact=True,
  independent_fit_path='Explicit pinned ExtraTrees.fit once;independent imputation/design/membership/leaf counts;registered source feature constructors;safeJSON only',
  native_safe_saved_max_mean_delta=maxdelta,native_safe_max_probability_delta=probdelta,single_batch_shuffled=True,ordered_features_exact=True,all_query_mean_median_checks=len(queries),
  original_model_or_forecast_mutations=0,duplicate_model_bytes_retained=0,
  environment=dict(Python=sys.version.split()[0],numpy=np.__version__,pandas=pd.__version__,sklearn=sklearn.__version__,scipy=scipy.__version__),
  CPU_seconds=time.process_time()-START,peak_RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,threads=1)
 assert receipt['CPU_seconds']<=120 and receipt['peak_RSS_bytes']<=805306368
 write(RECEIPT,receipt);attempt['status']='PASS';checkpoint('PASS_RETAINED_ORIGINAL_EXACT_MODEL')
 print(json.dumps(receipt,separators=(',',':')))
except BaseException as exc:
 attempt['status']='FAILED_NO_AUTOMATIC_RETRY';attempt['error']=repr(exc)
 attempt['CPU_seconds']=time.process_time()-START;attempt['peak_RSS_bytes']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
 write(ATTEMPT,attempt);print(json.dumps(attempt,separators=(',',':')));raise
finally:
 signal.setitimer(signal.ITIMER_PROF,0)
