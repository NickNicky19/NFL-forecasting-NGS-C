"""Project immutable row evidence into category/role/week scores. Never fits."""
import gzip,json,math,argparse
from pathlib import Path
import pandas as pd,numpy as np
from contracts_v2 import CATEGORIES
from data_v2 import load,admitted_roles
def finite_mean(v):
 a=np.asarray([float(x) for x in v if x is not None],float)
 return None if not len(a) else 'Infinity' if np.isinf(a).any() else float(a.mean())
def metric(q):
 s=q[q.actual.notna()];out=dict(queries=len(q),outcomes=len(s),games=int(s.game_id.nunique()),weeks=int(s.week.nunique()),fallback_queries=int(q.fallback.sum()),unknown=int(q.actual.isna().sum()),grid_brier=float(s.grid_brier.mean()) if len(s) else None,reference_brier=float(s.reference_brier.mean()) if len(s) else None,prevalence_brier=float(s.prevalence_brier.mean()) if len(s) else None,always_over_brier=float(s.always_over_brier.mean()) if len(s) else None,always_under_brier=float(s.always_under_brier.mean()) if len(s) else None,neutral_brier=.25 if len(s) else None,grid_logloss=finite_mean(s.grid_logloss.tolist()),grid_infinite_logloss=int(sum(math.isinf(float(v)) for v in s.grid_logloss)),median_mae=None,mean_mse=None,mean_rmse=None,bias=None,p95_absolute_error=None,crps=None,nll=None,nll_infinite=0,interval90_coverage=None)
 if q.family.iloc[0]=='P2_LEAF' and len(s):
  e=s['median']-s.actual;me=s['mean']-s.actual
  out.update(median_mae=float(e.abs().mean()),mean_mse=float((me**2).mean()),mean_rmse=float(np.sqrt((me**2).mean())),bias=float(me.mean()),p95_absolute_error=float(e.abs().quantile(.95)),crps=float(s.crps.mean()),nll=finite_mean(s.nll.tolist()),nll_infinite=int(sum(math.isinf(float(v)) for v in s.nll)),interval90_coverage=float(((s.actual>=s.p05)&(s.actual<=s.p95)).mean()))
 return out
def summarize(root,public,inputs):
 records=[];receipts=[]
 for done in sorted(root.glob('*/DONE.json')):
  d=done.parent;rows=json.loads(gzip.decompress((d/'rows.json.gz').read_bytes()));receipts.append(json.load(open(done)))
  overlay=d/'NLL_ANALYTIC_V1.json.gz'
  if overlay.exists():
   values=json.loads(gzip.decompress(overlay.read_bytes()))['nll'];assert len(values)==len(rows)
   for r,v in zip(rows,values):r['nll']=v;r['nll_version']='ANALYTIC_LOGPMF_V1'
  records.extend(rows)
 r=pd.DataFrame(records);keys=['target','history','family','arm','week','game_id','player_id'];assert not r.duplicated(keys).any();scores=[]
 # Earlier-only same-role prevalence is a distinct reference from parametric prior.
 facts,g,teams=load(inputs);allfacts=facts.to_dict('records');refs={}
 for row in records:
  key=(row['target'],row['history'],row['week'],row['position'])
  if key not in refs:
   target,h,w,role=key;floor={'H-CURRENT':2026,'H-RECENT':2025,'H-MULTI':2022}[h];origin=float(g[(g.season==2026)&(g.week==w)].kickoff.min())
   ys=np.asarray([f['values'][target] for f in allfacts if f['season']>=floor and f['available']<origin and f['position']==role and f['values'][target] is not None],float)
   grid=np.asarray(row['grid']);refs[key]=((ys[:,None]>grid).sum(axis=0)+1)/(len(ys)+2)
  if row['actual'] is not None:
   truth=(row['actual']>np.asarray(row['grid'])).astype(float);row['prevalence_brier']=float(np.mean((refs[key]-truth)**2));row['always_over_brier']=float(np.mean((1-truth)**2));row['always_under_brier']=float(np.mean(truth**2))
 r=pd.DataFrame(records)
 for (t,h,f,a),q in r.groupby(['target','history','family','arm']):
  subsets=[('ALL',q),('PRIMARY',q[q.position.isin(CATEGORIES[t][4])]),('W1-4',q[q.week<=4]),('W5-7',q[q.week>=5]),('LEARNED',q[~q.fallback])]+[(p,z) for p,z in q.groupby('position')]+[(f'W{w}',z) for w,z in q.groupby('week')]
  subsets += [(f'W{w}-{p}',z) for (w,p),z in q.groupby(['week','position'])]
  subsets += [(f'W1-4-{p}',z[z.week<=4]) for p,z in q.groupby('position')]+[(f'W5-7-{p}',z[z.week>=5]) for p,z in q.groupby('position')]
  for horizon,z in subsets:
   if len(z):scores.append(dict(test_id=f'{t}-{h}-{f}-{a}-{horizon}',target=t,history=h,family=f,arm=a,horizon=horizon,**metric(z)))
 public.mkdir(parents=True,exist_ok=True);pd.DataFrame(scores).to_csv(public/'SCORES.csv',index=False)
 comparisons=[]
 # Entire methods and their masks, not hindsight spliced sides.
 for t,q in r.groupby('target'):
  pairs=[(('H-MULTI','P2_LEAF','E0_OP'),('H-MULTI','P2_LEAF','E0_BASE'),'grid_brier'),(('H-MULTI','P2_LEAF','E0_ENV'),('H-MULTI','P2_LEAF','E0_OP'),'grid_brier'),(('H-MULTI','P2_LEAF','E0_DEF'),('H-MULTI','P2_LEAF','E0_ENV'),'grid_brier')]
  for h in ['H-CURRENT','H-RECENT','H-MULTI']:pairs += [((h,'P3_HGB','E0_OP'),(h,'P2_LEAF','E0_OP'),'grid_brier'),((h,'P3_LOGIT','E0_OP'),(h,'P2_LEAF','E0_OP'),'grid_brier')]
  pairs += [(('H-RECENT','P2_LEAF','E0_OP'),('H-MULTI','P2_LEAF','E0_OP'),'grid_brier'),(('H-CURRENT','P2_LEAF','E0_OP'),('H-MULTI','P2_LEAF','E0_OP'),'grid_brier')]
  for cand,control,loss in pairs:
   a=q[(q['history']==cand[0])&(q.family==cand[1])&(q.arm==cand[2])];b=q[(q['history']==control[0])&(q.family==control[1])&(q.arm==control[2])]
   p=a.merge(b,on=['week','game_id','player_id'],suffixes=('_a','_b'),validate='one_to_one');assert len(p)==len(a)==len(b)
   assert np.array_equal(p.actual_a.fillna(-999),p.actual_b.fillna(-999));p=p[p.actual_a.notna()].copy();p['delta']=p[loss+'_a']-p[loss+'_b'];v=dict(target=t,candidate='/'.join(cand),control='/'.join(control),metric=loss,n=len(p),delta=float(p.delta.mean()))
   for cluster in ['game_id','week']:
    z=p.groupby(cluster).delta.agg(['sum','count']);rng=np.random.default_rng(1701);i=rng.integers(0,len(z),(500,len(z)));samples=z['sum'].to_numpy()[i].sum(axis=1)/z['count'].to_numpy()[i].sum(axis=1);v[cluster+'_ci95']=list(map(float,np.quantile(samples,[.025,.975])))
   comparisons.append(v)
 (public/'PAIRED.json').write_text(json.dumps(comparisons,indent=2))
 # Calibration is a diagnostic, not a fitted calibration transform.
 calibration=[]
 for (t,h,f,a),q in r[r.actual.notna()].groupby(['target','history','family','arm']):
  p=np.concatenate(q.p_over.to_numpy());y=np.concatenate([(v>np.asarray(g)).astype(float) for v,g in zip(q.actual,q.grid)])
  for k in range(10):
   mask=(p>=k/10)&((p<(k+1)/10) if k<9 else (p<=1))
   calibration.append(dict(target=t,history=h,family=f,arm=a,bin=k,n_threshold_views=int(mask.sum()),mean_probability=float(p[mask].mean()) if mask.any() else None,observed_frequency=float(y[mask].mean()) if mask.any() else None,meaning='synthetic_threshold_diagnostic_not_fitted_calibration'))
 pd.DataFrame(calibration).to_csv(public/'CALIBRATION_DIAGNOSTICS.csv',index=False)
 total=dict(slots=len(receipts),learned_slots=sum(x['learned'] for x in receipts),fallback_slots=sum(not x['learned'] for x in receipts),forecast_views=len(r),unique_player_game_category_rows=len(r.drop_duplicates(['target','game_id','player_id'])),games=int(r.game_id.nunique()),weeks=int(r.week.nunique()),categories=len(r.target.unique()),current_week1='strict2026information; fallbackretained',offers='N/A rights/quote/settlementunqualified',numerical_status='EXECUTED_ALL12_SUPPORTED_SOURCE_SUBSETS',probability_status='EXECUTED_SYNTHETIC_GRID_DIAGNOSTICS_AND_ANYTIME_EVENT_NOT_SPORTSBOOK_SKILL',old_NGS='FROZEN_NO_RERUN',NGS_new='HELD_RIGHTS',model_source='C-authored architecture reconstructions, no unlicensed code copied')
 (public/'EXECUTED.json').write_text(json.dumps(total,indent=2));print(total)
 return r,pd.DataFrame(scores)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--public',type=Path,required=True);p.add_argument('--inputs',type=Path,required=True);a=p.parse_args();summarize(a.run,a.public,a.inputs)
