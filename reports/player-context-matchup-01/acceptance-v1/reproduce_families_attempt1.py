"""Acceptance-only fresh-fit reproduction; not new football evidence or tuning.

Run from pinned C checkout with requirements.txt, one thread. Raw feature
semantics are a separate independently reconstructed acceptance check.
"""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1');os.environ.setdefault('OMP_NUM_THREADS','1')
import gzip,hashlib,json,sys,time,resource,signal,warnings,platform,importlib.metadata
from pathlib import Path
import numpy as np
from scipy import sparse
from scipy.stats import poisson
from sklearn.linear_model import PoissonRegressor
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.preprocessing import OneHotEncoder
from sklearn.metrics import mean_poisson_deviance,log_loss
from threadpoolctl import threadpool_limits
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'src'))
import context_experiment_c01 as author
from reliability_v8 import hgb_export,hgb_cdf
from contracts_v2 import thresholds_for_line
from laws_v2 import Prior,Law
OUT=Path(__file__).resolve().parent
TOL_MEAN=1e-10;TOL_HGB=1e-12
START=time.process_time();WALL=time.monotonic();FITS=[]
def read(p):return json.loads(gzip.decompress(p.read_bytes())) if p.suffix=='.gz' else json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def safe(v):
 if isinstance(v,np.ndarray):return [safe(x) for x in v.tolist()]
 if isinstance(v,dict):return {str(k):safe(x) for k,x in v.items()}
 if isinstance(v,(list,tuple)):return [safe(x) for x in v]
 if isinstance(v,(np.integer,np.floating,np.bool_)):return v.item()
 return v
def checkpoint():
 assert time.process_time()-START<240,'VERIFICATION_CPU_CAP'
 assert resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024<=1288490188,'VERIFICATION_RSS_CAP'
def primitive_mu(model,x,ids):
 # Separate implementation from author's pooled_mu; feature-order binding is
 # checked by exact input dimension and stored training fingerprints below.
 d=len(model['impute']);assert x.shape[1]==d
 z=np.column_stack((np.where(np.isfinite(x),x,np.asarray(model['impute'])),(~np.isfinite(x)).astype(float)))
 z=(z-np.asarray(model['center']))/np.asarray(model['scale'])
 coef=np.asarray(model['coef']);eta=z@coef[:2*d]+model['intercept'];offset=2*d
 for c,cats in enumerate(model['categories']):
  lookup={v:i for i,v in enumerate(cats)}
  eta+=np.array([coef[offset+lookup[row[c]]] if row[c] in lookup else 0 for row in ids])
  offset+=len(cats)
 assert offset==len(coef)
 return np.exp(eta)
def main():
 previous=read(ROOT/'reports/player-context-matchup-01/INDEPENDENT_VERIFICATION.json.gz');assert previous['new_fits']==0
 inputs=Path('/workspace/c-v2/corrected-inputs');assert sha(inputs/'facts.csv.gz')=='9abc681265b6bec413de2d9002aa72ac19b1a48ea2e57d4f38698b1cc8717a11'
 author.STRICT=True;author.OUT=OUT/'fit-scratch';author.OUT.mkdir(exist_ok=True)
 with threadpool_limits(limits=1):pool,schedule,hist,mats=author.setup(inputs)
 ids=np.asarray([[r['player_id'],r['team'],r['opponent_team']] for r in pool]);football_fits=0
 report={'id':'C-CONTEXT-ACCEPTANCE-FRESH-FITS-v1','status':'RUNNING','scope':'Internal independent fit constructors and inference checks; raw feature semantics checked separately; not A peer endorsement','pin':'fa503c1e1a9993e655a905195ce428edf630add5','selected_before_results':['2026-W01-P1','2026-W01-P2','2026-W02-E3'],'tolerances_before_fits':{'Poisson_absolute_parameter_and_relative_mean':TOL_MEAN,'HGB_absolute_probability':TOL_HGB},'prior_fresh_fit_reuse':'No matching prior freshfit; prior receipt explicitly0fits','environment':{'python':platform.python_version(),**{k:importlib.metadata.version(k) for k in ['numpy','pandas','scikit-learn','scipy','threadpoolctl']}},'source_facts_SHA256':sha(inputs/'facts.csv.gz'),'fits':FITS}
 try:
  for week,label in [(1,'P1'),(1,'P2'),(2,'E3')]:
   checkpoint();cut=float(schedule.loc[(schedule.season==2026)&(schedule.week==week),'kickoff'].min())
   train=[i for i,r in enumerate(pool) if r['season']>=2022 and r['available']<cut and r['values']['rec'] is not None]
   query=[i for i,r in enumerate(pool) if r['season']==2026 and r['week']==week]
   x=mats['E3' if label=='E3' else 'E2'][train];y=np.asarray([pool[i]['values']['rec'] for i in train]);q=mats['E3' if label=='E3' else 'E2'][query]
   path=ROOT/'artifacts/player-context-matchup-01/v1.1'/f'2026-W{week:02}-{label}.json.gz';saved=read(path);model=saved['model']
   membership=[{'game_id':pool[i]['game_id'],'player_id':pool[i]['player_id']} for i in train]
   membership_sha=hashlib.sha256(json.dumps(membership,separators=(',',':')).encode()).hexdigest()
   fp=hashlib.sha256(np.nan_to_num(x,nan=999999.).tobytes()+y.tobytes()).hexdigest();assert fp==saved['training_fingerprint'] and membership_sha==saved['membership_SHA256']
   # Independent train-only median and missing indicator construction.
   with warnings.catch_warnings():warnings.simplefilter('ignore',RuntimeWarning);med=np.nanmedian(x,axis=0)
   med=np.where(np.isfinite(med),med,0.);z=np.column_stack([np.where(np.isfinite(x),x,med),(~np.isfinite(x)).astype(float)])
   initial=time.process_time();rec={'family':label,'origin':f'2026-W{week:02}','path':str(path.relative_to(ROOT)),'saved_SHA256':sha(path),'training_rows':len(train),'training_membership_SHA256':membership_sha,'fingerprint':fp,'training_latest_available':max(pool[i]['available'] for i in train),'cutoff':cut,'query_rows':len(query)}
   (OUT/'FIT_ATTEMPTS.json').write_text(json.dumps({'attempts':FITS+[dict(rec,state='RESERVED')],'football_fit_limit':3},separators=(',',':'))+'\n')
   football_fits+=1
   if label!='E3':
    center=z.mean(axis=0);scale=np.maximum(z.std(axis=0),1.);zz=(z-center)/scale
    encoder=None
    if label=='P2':
     encoder=OneHotEncoder(handle_unknown='ignore',sparse_output=True,dtype=float);cats=encoder.fit_transform(ids[train]);zz=sparse.hstack([sparse.csr_matrix(zz),cats],format='csr')
    with threadpool_limits(limits=1):fitted=PoissonRegressor(alpha=.1,max_iter=120,tol=1e-7).fit(zz,y)
    fresh={'type':'L2_POOLED_POISSON','partial':label=='P2','impute':med.tolist(),'center':center.tolist(),'scale':scale.tolist(),'coef':fitted.coef_.tolist(),'intercept':float(fitted.intercept_),'categories':[v.tolist() for v in encoder.categories_] if encoder else [],'iterations':int(fitted.n_iter_),'converged':fitted.n_iter_<120,'alpha':.1}
    for field in ['impute','center','scale','coef']:
     delta=float(np.max(abs(np.asarray(fresh[field])-np.asarray(model[field]))));rec[field+'_max_delta']=delta;assert delta<=TOL_MEAN,(label,field,delta)
    assert abs(fresh['intercept']-model['intercept'])<=TOL_MEAN and fresh['categories']==model['categories']
    sm=primitive_mu(model,q,ids[query]);fm=primitive_mu(fresh,q,ids[query]);delta=float(np.max(abs(sm-fm)/np.maximum(1,abs(sm))));assert delta<=TOL_MEAN
    author_m=author.pooled_mu(model,q,ids[query]);assert np.allclose(sm,author_m,rtol=0,atol=TOL_MEAN)
    order=np.arange(len(q))[::-1];shuffled=primitive_mu(model,q[order],ids[query][order]);assert np.allclose(sm[order],shuffled,rtol=0,atol=TOL_MEAN)
    assert max(abs(primitive_mu(model,q[j:j+1],ids[query][j:j+1])[0]-sm[j]) for j in range(min(8,len(q))))<=TOL_MEAN
    roundtripped=json.loads(json.dumps(model));assert np.array_equal(primitive_mu(roundtripped,q,ids[query]),sm)
    unseen=np.array([['UNSEEN_PLAYER','UNSEEN_TEAM','UNSEEN_DEFENSE']]);missing=np.full((1,q.shape[1]),np.nan);unknown_mu=primitive_mu(model,missing,unseen);assert np.isfinite(unknown_mu).all() and (unknown_mu>0).all()
    rec.update(iterations=fresh['iterations'],converged=fresh['converged'],max_relative_mean_delta=delta,single_batch_shuffle_serialization='PASS',missing_unseen_ids='Finite same pooled fallback;no identity coefficient applied',missing_unseen_mean=float(unknown_mu[0]),training_poisson_deviance=float(mean_poisson_deviance(y,fitted.predict(zz))),constant_training_deviance=float(mean_poisson_deviance(y,np.full(len(y),y.mean()))))
    # Exact-law validity independently, including integer pushes and negative lines.
    for mu in list(sm[:12])+[0.,1e-9,100.]:
     c=poisson.cdf(np.arange(0,600),mu);mass=poisson.pmf(np.arange(0,600),mu);assert np.isfinite(mass).all() and min(mass)>=0 and abs(mass.sum()-1)<1e-10 and np.all(np.diff(c)>=-1e-14)
     for line in [-.5,0.,.5,1.,1.5,10.]:
      p=author.count_probs(mu,line);assert min(p.values())>=-1e-14 and abs(sum(p.values())-1)<1e-12
      assert abs(p['push']-(float(poisson.pmf(int(line),mu)) if line>=0 and line==int(line) else 0))<1e-12
     assert author.count_probs(mu,.5)['over']>=author.count_probs(mu,1.5)['over']
    rec['law_normalization_CDF_push_support_changed_line']='PASS'
   else:
    thresholds=np.array([0,1,2,3,4,5,7]);xx=np.column_stack([np.repeat(z,len(thresholds),axis=0),np.tile(thresholds,len(z))]);yy=(np.repeat(y,len(thresholds))<=np.tile(thresholds,len(y))).astype(int);constraints=[0]*(xx.shape[1]-1)+[1]
    with threadpool_limits(limits=1):fitted=HistGradientBoostingClassifier(max_iter=32,max_depth=3,min_samples_leaf=20,learning_rate=.05,l2_regularization=10,random_state=1701,early_stopping=False,monotonic_cst=constraints).fit(xx,yy)
    # The author serializer requires the metadata holder; no author's fit used.
    class Holder:pass
    holder=Holder();holder.model=fitted;holder.m=med;holder.event=False;fresh=hgb_export(holder)
    grid=[-1,0,.5,1,2,3,5,7,10];new=np.array([hgb_cdf(fresh,f,grid) for f in q]);old=np.array([hgb_cdf(model,f,grid) for f in q]);delta=float(np.max(abs(new-old)));assert delta<=TOL_HGB
    rawq=np.column_stack([np.where(np.isfinite(q),q,med),(~np.isfinite(q)).astype(float)]);dx=np.column_stack([np.repeat(rawq,len(grid),axis=0),np.tile(grid,len(rawq))]);direct=fitted.predict_proba(dx)[:,1].reshape(len(q),len(grid));assert np.max(abs(direct-new))<=TOL_HGB
    roundtrip=json.loads(json.dumps(fresh));assert np.array_equal(np.array([hgb_cdf(roundtrip,f,grid) for f in q]),new)
    assert np.all(np.isfinite(new)) and min(new.ravel())>=0 and max(new.ravel())<=1 and np.all(np.diff(new,axis=1)>=-1e-12)
    assert np.array_equal(np.array([hgb_cdf(model,f,grid) for f in q[::-1]]),old[::-1])
    rec.update(max_CDF_delta=delta,single_batch_shuffle_serialization='PASS',changed_threshold_monotonicity='PASS',training_binary_logloss=float(log_loss(yy,fitted.predict_proba(xx)[:,1])),iterations=int(fitted.n_iter_))
   rec['CPU_seconds']=time.process_time()-initial;rec['state']='PASS';FITS.append(rec);checkpoint()
  # Pure player empirical law and declared insufficient-history fallback.
  ys=[0,0,1,2,3,3,4,8];law=Law(*np.unique(ys,return_counts=True),Prior(ys,'count'),alpha=.05)
  mass=np.array([law.pmf(k) for k in range(600)]);assert min(mass)>=0 and abs(mass.sum()-1)<1e-10
  for line in [0,.5,1.,1.5,20.]:assert abs(sum(law.probability(line).values())-1)<1e-12
  # Synthetic positive control deliberately separate from football evidence.
  sx=np.repeat([0.,1.],400)[:,None];sy=np.repeat([0,1],400)
  with threadpool_limits(limits=1):syn=HistGradientBoostingClassifier(max_iter=32,max_depth=3,min_samples_leaf=20,learning_rate=.05,l2_regularization=10,random_state=1701,early_stopping=False).fit(sx,sy)
  signal=syn.predict_proba([[0.],[1.]])[:,1];assert signal[1]-signal[0]>.5
  report.update(status='PASS',football_fits=football_fits,synthetic_software_fits=1,synthetic_signal_probabilities=signal.tolist(),synthetic_not_NFL_observation=True,player_empirical_tail_normalization='PASS',P3_insufficient_history_fallback='Reused independently verified P1fallback membership, not new law',feature_order='Position-bound array API;dimensionality and fingerprints checked. Same-dimension semantic permutation is caller error and not automatically rejected; no named-column enforcement in adapter.',output_typing='P1/P2 conditional Poisson mean and lower median;P3empirical mean/median withP1 fallback;HGB onlythresholdprobabilities. No point-to-probability/corrector.',release_qualification='No new testweek or promotion',CPU_seconds=time.process_time()-START,wall_seconds=time.monotonic()-WALL,peak_RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024)
 except Exception as e:
  report.update(status='FAIL',error=repr(e),football_fits=football_fits,CPU_seconds=time.process_time()-START,wall_seconds=time.monotonic()-WALL,peak_RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024)
  (OUT/'FIT_REPRODUCTION.json').write_text(json.dumps(safe(report),separators=(',',':'))+'\n');raise
 (OUT/'FIT_REPRODUCTION.json').write_text(json.dumps(safe(report),separators=(',',':'))+'\n');print(json.dumps(safe(report),indent=2))
if __name__=='__main__':
 signal.signal(signal.SIGPROF,lambda *_:(_ for _ in ()).throw(RuntimeError('VERIFICATION_CPU_TIMER')));signal.setitimer(signal.ITIMER_PROF,240)
 try:main()
 finally:signal.setitimer(signal.ITIMER_PROF,0)
