"""Numeric-only C forest/law format. Loading never executes pickle or code."""
import gzip,json,hashlib
from pathlib import Path
import numpy as np
from laws_v2 import Law,Prior,design

def prior_data(p):return {k:getattr(p,k) for k in ['kind','empty','mu','center','q','event']}
def prior_load(d):
    assert d['kind'] in ['count','signed','event'] and all(np.isfinite(d[k]) for k in ['mu','center','q','event']) and int(d['center'])==d['center'] and 0<=d['q']<1
    # Prior.event is an unused legacy summary for non-event priors, not a probability.
    if d['kind']=='event':assert 0<=d['event']<=1
    p=Prior([],d['kind'])
    for k in ['kind','empty','mu','center','q','event']:setattr(p,k,d[k])
    return p
def law_data(l):return dict(values=l.v.tolist(),weights=l.w.tolist(),prior=prior_data(l.prior),scale=l.scale,alpha=l.a)
def law_load(d):
    assert d['scale'] in [1,50] and 0<d['alpha']<=1 and len(d['values'])==len(d['weights'])<=20000
    v,w=np.asarray(d['values']),np.asarray(d['weights'],float);assert np.all(np.isfinite(v)) and np.all(v==np.rint(v)) and np.all(np.diff(v)>0) and np.all(np.isfinite(w)) and np.all(w>=0)
    if d['prior']['kind']=='count':assert np.all(v>=0)
    if d['prior']['kind']=='event':assert np.all(np.isin(v,[0,1]))
    assert not len(w) or abs(w.sum()-1)<1e-10
    l=Law([],[],prior_load(d['prior']),d['scale']);l.v,l.w,l.a=v,w,d['alpha'];return l
def export_forest(model):
    trees=[]
    for estimator,leaves in zip(model.model.estimators_,model.leaves):
        t=estimator.tree_;trees.append(dict(left=t.children_left.tolist(),right=t.children_right.tolist(),feature=t.feature.tolist(),threshold=t.threshold.tolist(),leaves={str(k):[v.tolist(),c.tolist()] for k,(v,c) in leaves.items()}))
    return dict(schema='C-NUMERIC-LEAF-v4',kind=model.kind,scale=model.scale,imputation=model.m.tolist(),prior={str(k):prior_data(v) for k,v in model.prior.items()},global_prior=prior_data(model.global_prior),trees=trees)
def validate_training_model(d,x,y,roles):
    """Recover a saved numeric fit without refitting or executing model code."""
    from laws_v2 import medians
    assert np.array_equal(np.asarray(d['imputation']),medians(x))
    assert d['global_prior']==prior_data(Prior(y,d['kind']))
    assert d['prior']=={str(p):prior_data(Prior(y[roles==p],d['kind'])) for p in set(roles)}
    z=design(x,np.asarray(d['imputation'])).astype(np.float32)
    assert d['schema']=='C-NUMERIC-LEAF-v4' and len(d['trees'])==32
    for t in d['trees']:
        left,right,feature,threshold=[np.asarray(t[k]) for k in ['left','right','feature','threshold']];nodes=np.zeros(len(y),int)
        for _ in range(9):
            active=np.flatnonzero(left[nodes]>=0)
            if not len(active):break
            n=nodes[active];assert np.all((feature[n]>=0)&(feature[n]<z.shape[1]))
            choose=z[active,feature[n]].astype(float)<=threshold[n].astype(float)
            nodes[active]=np.where(choose,left[n],right[n])
        assert np.all(left[nodes]<0)
        assert set(map(str,np.unique(nodes)))==set(t['leaves'])
        for n in np.unique(nodes):
            v,c=np.unique(y[nodes==n],return_counts=True);assert [v.tolist(),c.tolist()]==t['leaves'][str(n)],'RECOVERED_LEAF_LABEL_COUNTS_DIFFER'
    return dict(training_rows=len(y),trees=32,imputation_priors_all_leaf_counts_verified=True,new_fits=0)
def infer_forest(d,x,roles):
    assert d['schema']=='C-NUMERIC-LEAF-v4' and len(d['trees'])==32
    z=design(np.asarray(x,float),np.asarray(d['imputation'],float)).astype(np.float32)
    assert z.shape[1]==2*len(d['imputation']);out=[]
    for row,role in zip(z,roles):
        mass={}
        for tree in d['trees']:
            n=len(tree['left']);assert n==len(tree['right'])==len(tree['feature'])==len(tree['threshold']) and n<=511
            node=0
            for _ in range(10):
                if tree['left'][node]<0:break
                feature=tree['feature'][node];assert 0<=feature<len(row)
                node=tree['left'][node] if float(row[feature])<=float(tree['threshold'][node]) else tree['right'][node];assert 0<=node<n
            else:raise ValueError('NUMERIC_TREE_CYCLE_OR_DEPTH')
            v,c=tree['leaves'][str(node)];c=np.asarray(c);v=np.asarray(v);assert len(v)==len(c)<=20000 and np.all(np.isfinite(v)) and np.all(v==np.rint(v)) and np.all(c>0) and np.all(c==np.rint(c))
            for value,weight in zip(v,c/c.sum()/32):mass[int(value)]=mass.get(int(value),0.)+float(weight)
        values=sorted(mass);out.append(Law(values,[mass[v] for v in values],prior_load(d['prior'].get(str(role),d['global_prior'])),d['scale']))
    return out
def save(path,data):
    b=gzip.compress(json.dumps(data,separators=(',',':'),allow_nan=False).encode(),compresslevel=6,mtime=0);Path(path).parent.mkdir(parents=True,exist_ok=True)
    with Path(path).open('xb') as f:f.write(b)
    return hashlib.sha256(b).hexdigest()
def load(path,expected_hash):
    b=Path(path).read_bytes();assert hashlib.sha256(b).hexdigest()==expected_hash
    return json.loads(gzip.decompress(b))
