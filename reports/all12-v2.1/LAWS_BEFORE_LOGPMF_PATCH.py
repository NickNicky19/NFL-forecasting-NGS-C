"""Proper discrete empirical-leaf mixtures and monotonic threshold references."""
import math
import numpy as np
from scipy.special import expit
from scipy.optimize import minimize
from sklearn.ensemble import ExtraTreesRegressor,HistGradientBoostingClassifier
from contracts_v2 import probs

def medians(x):
 import warnings
 with warnings.catch_warnings():
  warnings.simplefilter('ignore',RuntimeWarning);m=np.nanmedian(x,axis=0)
 return np.where(np.isfinite(m),m,0.)
def design(x,m):return np.column_stack([np.where(np.isfinite(x),x,m),~np.isfinite(x)]).astype(float)
class Prior:
 def __init__(self,y,kind):
  self.kind=kind;self.empty=not len(y)
  self.mu=float(np.mean(y)) if len(y) else 0.;self.center=int(np.median(y)) if len(y) else 0
  self.q=(max(.05,self.mu)/(1+max(.05,self.mu))) if kind=='count' else max(1.,float(np.mean(abs(y-self.center))) if len(y) else 1.)/(1+max(1.,float(np.mean(abs(y-self.center))) if len(y) else 1.))
  self.event=(float(np.sum(y))+1)/(len(y)+2)
 def cdf(self,k):
  k=math.floor(k)
  if self.kind=='event':return 0. if k<0 else 1. if k>=1 else 1-self.event
  if self.empty:return float(k>=0)
  q=self.q
  if self.kind=='count':return 0. if k<0 else 1-q**(k+1)
  d=k-self.center;return 1-q**(d+1)/(1+q) if d>=0 else q**(-d)/(1+q)
 def pmf(self,k):return max(0.,self.cdf(k)-self.cdf(k-1))
 def mean(self):
  if self.kind=='event':return self.event
  if self.empty:return 0.
  return self.q/(1-self.q) if self.kind=='count' else float(self.center)
 def abs_to(self,y):
  y=np.asarray(y,dtype=float)
  if self.kind=='event':return (1-self.event)*abs(y)+self.event*abs(1-y)
  if self.empty:return abs(y)
  q=self.q
  if self.kind=='count':return np.where(y<0,self.mean()-y,y-self.mean()+2*q**(y+1)/(1-q))
  d=abs(y-self.center);return d+2*q**(d+1)/(1-q*q)
 def pair_abs(self):
  if self.kind=='event':return 2*self.event*(1-self.event)
  if self.empty:return 0.
  q=self.q
  return 2*q/((1-q)*(1+q)) if self.kind=='count' else 4*q*(1+q+q*q)/((1-q)*(1+q)**3)

class Law:
 def __init__(self,values,weights,prior,scale=1,alpha=.05):
  self.v=np.asarray(values);self.w=np.asarray(weights);self.prior=prior;self.scale=scale;self.a=alpha if len(values) else 1.
  if len(values):self.w=self.w/self.w.sum()
 def cdf(self,k):return (1-self.a)*float(self.w[self.v<=k].sum())+self.a*self.prior.cdf(k)
 def pmf(self,k):return (1-self.a)*float(self.w[self.v==k].sum())+self.a*self.prior.pmf(k)
 def mean(self):return ((1-self.a)*float(self.v@self.w)+self.a*self.prior.mean())/self.scale
 def quantile(self,p):
  lo=min(-1,int(self.v.min())-1 if len(self.v) else -1,self.prior.center-1);hi=max(1,int(self.v.max())+1 if len(self.v) else 1,self.prior.center+1)
  while self.cdf(lo)>=p:lo=2*lo-1
  while self.cdf(hi)<p:hi=2*hi+1
  while hi-lo>1:
   m=(lo+hi)//2
   if self.cdf(m)>=p:hi=m
   else:lo=m
  return hi/self.scale
 def crps(self,y):
  y=int(round(y*self.scale));a=self.a;v,w=self.v,self.w
  first=(1-a)*float(w@abs(v-y))+a*float(self.prior.abs_to(y))
  cumw=np.cumsum(w)-w;cumv=np.cumsum(w*v)-w*v
  emp=2*float(np.sum(w*(v*cumw-cumv)))
  pair=(1-a)**2*emp+2*a*(1-a)*float(w@self.prior.abs_to(v))+a*a*self.prior.pair_abs()
  return max(0.,first-.5*pair)/self.scale
 def probability(self,line):return probs(self.cdf,line,self.scale)

class LeafModel:
 def __init__(self,kind,scale):self.kind,self.scale=kind,scale
 def fit(self,x,y,roles):
  self.m=medians(x);self.prior={p:Prior(y[roles==p],self.kind) for p in set(roles)};self.global_prior=Prior(y,self.kind)
  self.model=ExtraTreesRegressor(n_estimators=32,max_depth=8,min_samples_leaf=30,max_features=1.,bootstrap=False,random_state=1701,n_jobs=1).fit(design(x,self.m),y)
  leaves=self.model.apply(design(x,self.m));self.leaves=[]
  for j in range(32):
   self.leaves.append({int(node):np.unique(y[leaves[:,j]==node],return_counts=True) for node in np.unique(leaves[:,j])})
  return self
 def laws(self,x,roles):
  ids=self.model.apply(design(x,self.m));out=[]
  for nodes,role in zip(ids,roles):
   mass={}
   for j,node in enumerate(nodes):
    v,c=self.leaves[j][int(node)];w=c/c.sum()/32
    for a,b in zip(v,w):mass[int(a)]=mass.get(int(a),0.)+float(b)
   v=sorted(mass);out.append(Law(v,[mass[a] for a in v],self.prior.get(role,self.global_prior),self.scale))
  return out

class ThresholdModel:
 def __init__(self,family,event,thresholds):self.family,self.event,self.thresholds=family,event,np.asarray(thresholds)
 def fit(self,x,y):
  self.m=medians(x);z=design(x,self.m);self.center=z.mean(axis=0);self.std=np.maximum(z.std(axis=0),1.)
  if self.event:xx=z;yy=y.astype(int)
  else:
   # Every game has total weight one across its registered synthetic thresholds.
   xx=np.column_stack([np.repeat(z,len(self.thresholds),axis=0),np.tile(self.thresholds,len(z))]);yy=(np.repeat(y,len(self.thresholds))<=np.tile(self.thresholds,len(y))).astype(int)
  self.input_center=xx.mean(axis=0);self.input_std=np.maximum(xx.std(axis=0),1.)
  if self.family=='MONOTONE_HGB':
   c=[0]*xx.shape[1]
   if not self.event:c[-1]=1
   self.model=HistGradientBoostingClassifier(max_iter=32,max_depth=3,min_samples_leaf=20,learning_rate=.05,l2_regularization=10,random_state=1701,early_stopping=False,monotonic_cst=c).fit(xx,yy)
  else:
   xx=(xx-self.input_center)/self.input_std;xx=np.column_stack([np.ones(len(xx)),xx]);pen=np.r_[0.,np.ones(xx.shape[1]-1)*.1]
   def fun(b):
    t=xx@b;loss=np.mean(np.logaddexp(0,t)-yy*t)+.5*np.sum(pen*b*b);grad=xx.T@(expit(t)-yy)/len(yy)+pen*b;return loss,grad
   bounds=[(None,None)]*xx.shape[1]
   if not self.event:bounds[-1]=(0,None)
   result=minimize(fun,np.zeros(xx.shape[1]),jac=True,bounds=bounds,method='L-BFGS-B',options={'maxiter':100,'ftol':1e-9})
   self.coef=result.x;self.converged=bool(result.success)
  return self
 def cdfs(self,x,thresholds):
  z=design(x,self.m)
  xx=z if self.event else np.column_stack([np.repeat(z,len(thresholds),axis=0),np.tile(thresholds,len(z))])
  if self.family=='MONOTONE_HGB':p=self.model.predict_proba(xx)[:,1]
  else:p=expit(np.column_stack([np.ones(len(xx)),(xx-self.input_center)/self.input_std])@self.coef)
  return p[:,None] if self.event else p.reshape(len(z),len(thresholds))
