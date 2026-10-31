"""Independent, bounded HGB reconstruction; no upstream code is copied.

Inputs and player-level outputs must reside outside the public repository.
All clocks are reconstruction assumptions, never original publication evidence.
"""
import argparse, bisect, gzip, hashlib, json, math, pickle, platform, resource, time
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from threadpoolctl import threadpool_limits

VERSION='C-RAW-QUALITY-HGB-v1'
TARGETS={'pass_cmp':'completions','rec_yd':'receiving_yards','pass_yd':'passing_yards','rush_yd':'rushing_yards','rec':'receptions'}
ROLES={'pass_cmp':['QB'],'pass_yd':['QB'],'rush_yd':['RB','QB'],'rec_yd':['RB','WR','TE'],'rec':['RB','WR','TE']}
GROUPS={
 'pass_cmp':('passing',[('avg_intended_air_yards','attempts'),('avg_time_to_throw','attempts'),('aggressiveness','attempts')]),
 'pass_yd':('passing',[('avg_intended_air_yards','attempts'),('avg_time_to_throw','attempts'),('aggressiveness','attempts')]),
 'rec_yd':('receiving',[('avg_intended_air_yards','targets'),('avg_separation','targets')]),
 'rec':('receiving',[('avg_intended_air_yards','targets'),('avg_separation','targets'),('avg_cushion','targets')]),
 'rush_yd':('rushing',[('percent_attempts_gte_eight_defenders','rush_attempts'),('avg_time_to_los','rush_attempts')])}
PARAMS=dict(max_iter=64,max_depth=3,max_leaf_nodes=31,min_samples_leaf=10,learning_rate=.05,l2_regularization=10,random_state=1701,early_stopping=False,categorical_features=None,max_bins=255)
DAY=86400
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(v,f,indent=2,allow_nan=False)
def schedule(source):
 g=pd.read_csv(source/'schedules.csv');g=g[(g.game_type=='REG') & g.season.between(2022,2026) & ((g.season!=2026)|(g.week<=7))].copy()
 # nfldata gametime is America/New_York, including DST.
 g['kickoff']=pd.to_datetime(g.gameday+' '+g.gametime).dt.tz_localize('America/New_York').dt.tz_convert('UTC').astype('int64')/1e9
 assert not g.game_id.duplicated().any()
 return g
def load(source):
 g=schedule(source); rows=[]; counts=[]
 for year in range(2022,2027):
  d=pd.read_csv(source/f'stats_player_week_{year}.csv.gz',low_memory=False)
  d=d[(d.season_type=='REG') & (d.season==year) & ((d.season!=2026)|(d.week<=7)) & d.position.isin(['QB','RB','WR','TE'])].copy()
  assert d.player_id.str.fullmatch(r'00-\d{7}').all()
  d=d.merge(g[['game_id','season','week','home_team','away_team','kickoff']],on=['game_id','season','week'],how='left',validate='many_to_one')
  assert d.kickoff.notna().all()
  assert ((d.team==d.home_team)&(d.opponent_team==d.away_team)|(d.team==d.away_team)&(d.opponent_team==d.home_team)).all()
  assert not d.duplicated(['game_id','player_id']).any()
  physical=['attempts','carries','targets','receptions','sacks_suffered','passing_tds','rushing_tds','receiving_tds','passing_2pt_conversions','rushing_2pt_conversions','receiving_2pt_conversions','kickoff_returns','punt_returns','special_teams_tds']
  played=(d[physical].fillna(0)>0).any(axis=1)|(d[['passing_yards','rushing_yards','receiving_yards']].fillna(0)!=0).any(axis=1)
  d['played']=played;d['available']=d.kickoff+7*DAY
  # An all-zero source record without positive physical evidence stays unknown.
  for col in TARGETS.values():d.loc[~played,col]=np.nan
  counts.append(dict(season=year,queries=len(d),played=int(played.sum()),unknown=int((~played).sum()),games=int(d.game_id.nunique())))
  rows.append(d)
 d=pd.concat(rows,ignore_index=True).sort_values(['available','game_id','player_id']).reset_index(drop=True)
 ngs={};catalog=[];quarantine=[]
 teams={'LAR':'LA','STL':'LA','OAK':'LV','SD':'LAC'}
 for kind in ['passing','receiving','rushing']:
  raw=pd.read_csv(source/f'ngs_{kind}.csv.gz');n=raw[(raw.season_type=='REG')&raw.week.between(1,18)&raw.season.between(2022,2026)&((raw.season!=2026)|(raw.week<=7))].copy()
  n['team']=n.team_abbr.replace(teams)
  long=pd.concat([g.rename(columns={'home_team':'team'}),g.rename(columns={'away_team':'team'})],ignore_index=True)
  n=n.merge(long[['season','week','team','game_id','kickoff']],on=['season','week','team'],how='left',validate='many_to_one')
  invalid=n.game_id.isna()|~n.player_gsis_id.fillna('').str.fullmatch(r'00-\d{7}')
  dup=n.duplicated(['season','week','player_gsis_id'],keep=False)
  # Reject both sides of ambiguous identities, never collapse/name-join.
  quarantine.append(dict(kind=kind,invalid_schedule_or_id=int(invalid.sum()),ambiguous=int(dup.sum())))
  n=n[~invalid & ~dup].copy();n['available']=n.kickoff+7*DAY
  ngs[kind]=n.sort_values(['available','game_id']).reset_index(drop=True)
  for year in range(2022,2027):
   z=raw[raw.season==year];q=n[n.season==year]
   catalog.append(dict(source=f'ngs_{kind}.csv.gz',season=year,source_rows=len(z),excluded_week_zero=int((z.week==0).sum()),accepted_REG_target_rows=len(q),games=int(q.game_id.nunique()),weeks=sorted(map(int,q.week.unique())),fields=list(z.columns),missing={c:int(q[c].isna().sum()) for c in q if c not in ['game_id','kickoff','available']}))
 return d,g,ngs,dict(stats=counts,ngs=catalog,quarantine=quarantine)

class History:
 def __init__(self,rows,idcol):
  self.groups={k:v.sort_values(['available','game_id']).to_dict('records') for k,v in rows.groupby(idcol)}
  self.times={k:[r['available'] for r in rs] for k,rs in self.groups.items()}
 def before(self,pid,cutoff,n=8):
  right=bisect.bisect_left(self.times.get(pid,[]),cutoff)
  return self.groups.get(pid,[])[max(0,right-n):right]

def features(row,target,hist,nghist,arm):
 cutoff=row['kickoff'];pid=row['player_id'];col=TARGETS[target];rs=hist.before(pid,cutoff)
 f=[]
 for window in [3,8]:
  y=[r[col] for r in rs[-window:] if np.isfinite(r[col])];f += [float(np.mean(y)) if y else np.nan,float(len(y))]
 for lag in range(1,5):
  r=rs[-lag] if len(rs)>=lag else None;y=r[col] if r else np.nan
  f += [y,(cutoff-r['kickoff'])/DAY if r else np.nan,float(not np.isfinite(y))]
 f += [float(row['position']==p) for p in ['QB','RB','WR','TE']]
 ns=[r for r in nghist.before(pid,cutoff) if cutoff-r['kickoff']<=365*DAY]
 if arm=='C0':return f
 f += [float(len(ns)),(cutoff-ns[-1]['kickoff'])/DAY if ns else np.nan]
 vals=[]
 for metric,denom in GROUPS[target][1]:
  valid=[r for r in ns if np.isfinite(r[metric]) and np.isfinite(r[denom]) and r[denom]>0]
  exposure=sum(r[denom] for r in valid)
  f += [float(len(valid)),float(exposure)]
  vals.append(sum(r[denom]*r[metric] for r in valid)/exposure if exposure else np.nan)
 if arm=='C2':f+=vals
 return f

def impute_fit(x):
 # Training-only; all-missing columns get literal zero with no source reinterpretation.
 import warnings
 with warnings.catch_warnings():
  warnings.simplefilter('ignore',RuntimeWarning);m=np.nanmedian(x,axis=0)
 return np.where(np.isfinite(m),m,0.)
def impute(x,m):return np.where(np.isfinite(x),x,m)
def fit_predict(x,y,q,target):
 m=impute_fit(x);model=HistGradientBoostingRegressor(loss='absolute_error',**PARAMS).fit(impute(x,m),y)
 p=model.predict(impute(q,m))
 if target in ['pass_cmp','rec']:p=np.maximum(0,p)
 return p,(model,m)
def fallback(row,target,hist,train):
 own=[r[TARGETS[target]] for r in hist.before(row['player_id'],row['kickoff']) if np.isfinite(r[TARGETS[target]])]
 same=train.loc[train.position==row['position'],TARGETS[target]].dropna().tolist()
 return float(np.median(own or same)) if own or same else 0.

def run(source,private,public,seasons,weeks=None):
 start=time.monotonic();cpu=time.process_time();d,g,ngs,catalog=load(source);hist=History(d,'player_id');nh={k:History(v,'player_gsis_id') for k,v in ngs.items()}
 out=private;out.mkdir(parents=True,exist_ok=False);(out/'models').mkdir();allrows=[];fits=[]
 matrices={}
 for target in TARGETS:
  pool=d[d.position.isin(ROLES[target])]
  for arm in ['C0','C1','C2']:
   matrices[target,arm]=pd.DataFrame([features(r,target,hist,nh[GROUPS[target][0]],arm) for r in pool.to_dict('records')],index=pool.index)
 write(public/'SOURCE_COVERAGE.json',catalog)
 for season in seasons:
  for week in sorted(g.loc[g.season==season,'week'].unique()):
   if weeks and week not in weeks:continue
   origin=float(g.loc[(g.season==season)&(g.week==week),'kickoff'].min())
   for target in TARGETS:
    pool=d[d.position.isin(ROLES[target])];train=pool[(pool.available<origin)&pool[TARGETS[target]].notna()];q=pool[(pool.season==season)&(pool.week==week)]
    for arm in ['C0','C1','C2']:
     slot=f'{season}-W{week:02}-{target}-{arm}'
     x=matrices[target,arm].loc[train.index].to_numpy();qx=matrices[target,arm].loc[q.index].to_numpy()
     learned=len(train)>=40
     y=train[TARGETS[target]].to_numpy()
     if learned:
      if sum(r['learned'] for r in fits)>=1185:raise RuntimeError('fit count cap')
      if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024>2147483648:raise RuntimeError('RSS cap')
      with (out/'attempts.jsonl').open('a') as f:f.write(json.dumps(dict(slot=slot,training_rows=len(train),at_UTC=pd.Timestamp.now(tz='UTC').isoformat()))+'\n')
      with threadpool_limits(limits=1):pred,packet=fit_predict(x,y,qx,target)
      with gzip.open(out/'models'/f'{slot}.pkl.gz','wb',compresslevel=6) as f:pickle.dump(packet,f,protocol=5)
     else:pred=[fallback(r,target,hist,train) for r in q.to_dict('records')]
     packet=dict(slot=slot,origin=origin,train_rows=len(train),training_key_sha256=hashlib.sha256('\n'.join(train.game_id+':'+train.player_id).encode()).hexdigest(),learned=learned,features=int(qx.shape[1]),latest_training_available=float(train.available.max()) if len(train) else None)
     fits.append(packet)
     for (idx,r),p,fv in zip(q.iterrows(),pred,qx):
      ns=nh[GROUPS[target][0]].before(r.player_id,r.kickoff)
      allrows.append(dict(slot=slot,season=season,week=int(week),target=target,arm=arm,game_id=r.game_id,player_id=r.player_id,position=r.position,kickoff=r.kickoff,origin=origin,actual=float(r[TARGETS[target]]) if np.isfinite(r[TARGETS[target]]) else None,point=float(p),fallback=not learned,played=bool(r.played),ngs_available=bool(ns and r.kickoff-ns[-1]['kickoff']<=365*DAY),features=[float(v) if np.isfinite(v) else None for v in fv]))
     print(slot,len(q),len(train),flush=True)
     if time.process_time()-cpu>1800 or time.monotonic()-start>2400:raise RuntimeError('finite resource budget reached; preserve partial files')
     if sum(f.stat().st_size for f in out.rglob('*') if f.is_file())>256*1024**2:raise RuntimeError('private capacity bound')
    # Persist every completed category origin before continuing.
    with gzip.open(out/f'{season}-W{week:02}-{target}.json.gz','wt') as f:json.dump(allrows[-3*len(q):],f,allow_nan=False)
 write(out/'fits.json',fits)
 write(public/'RUN_RECEIPT.json',dict(version=VERSION,generated_at_UTC=pd.Timestamp.now(tz='UTC').isoformat(),wall_seconds=time.monotonic()-start,cpu_seconds=time.process_time()-cpu,peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,actual_fits=sum(r['learned'] for r in fits),fallback_slots=sum(not r['learned'] for r in fits),forecast_rows=len(allrows),private_bytes=sum(f.stat().st_size for f in out.rglob('*') if f.is_file()),python=platform.python_version(),numpy=np.__version__,pandas=pd.__version__,source_sha256={p.name:sha(p) for p in source.glob('*.csv.gz') if p.name.startswith(('stats_player_week_','ngs_'))},code_sha256=sha(__file__)))
 score(pd.DataFrame(allrows),public)

def metrics(q):
 s=q[q.actual.notna()];e=s.point-s.actual;a=e.abs();n=len(s)
 return dict(queries=len(q),outcomes=n,games=int(s.game_id.nunique()),weeks=int(s.week.nunique()),mae=float(a.mean()) if n else None,mse=float((e**2).mean()) if n else None,rmse=float(np.sqrt((e**2).mean())) if n else None,bias=float(e.mean()) if n else None,p90=float(a.quantile(.9)) if n else None,p95=float(a.quantile(.95)) if n else None,exact=int((a==0).sum()),strict1=int((a<1).sum()),inclusive1=int((a<=1).sum()),fallback_queries=int(q.fallback.sum()),fallback_scored=int(s.fallback.sum()),ngs_queries=int(q.ngs_available.sum()),unknown=int(q.actual.isna().sum()),played_zero=int((s.actual==0).sum()))
def paired(q,control,seed=1701,reps=500):
 a=q[q.arm=='C2'];b=q[q.arm==control];p=a.merge(b,on=['season','week','game_id','player_id','target','position'],suffixes=('_a','_b'),validate='one_to_one')
 assert np.array_equal(p.actual_a.fillna(-9999),p.actual_b.fillna(-9999))
 p=p[p.actual_a.notna()].copy();p['loss_delta']=(p.point_a-p.actual_a).abs()-(p.point_b-p.actual_b).abs()
 def ci(keys):
  z=p.groupby(keys).loss_delta.agg(['sum','count']);rng=np.random.default_rng(seed)
  if len(z)<2:return [None,None]
  i=rng.integers(0,len(z),(reps,len(z)));v=z['sum'].to_numpy()[i].sum(axis=1)/z['count'].to_numpy()[i].sum(axis=1)
  return list(map(float,np.quantile(v,[.025,.975])))
 return dict(control=control,n=len(p),delta=float(p.loss_delta.mean()) if len(p) else None,relative_change=float(p.loss_delta.mean()/((p.point_b-p.actual_b).abs().mean())) if len(p) else None,game_ci=ci('game_id'),week_ci=ci(['season','week']))
def score(rows,public):
 tables=[];pairs=[]
 for (season,target),q in rows.groupby(['season','target']):
  groups=[('ALL',q),('W1-4',q[q.week<=4]),('W5+',q[q.week>=5])]
  if target=='rush_yd':groups += [('RB',q[q.position=='RB']),('QB',q[q.position=='QB'])]
  groups += [('LEARNED',q[~q.fallback]),('NGS_AVAILABLE',q[q.ngs_available])]
  for horizon,z in groups:
   for arm,a in z.groupby('arm'):tables.append(dict(season=int(season),target=target,horizon=horizon,arm=arm,**metrics(a)))
   for control in ['C0','C1']:pairs.append(dict(season=int(season),target=target,horizon=horizon,**paired(z,control)))
  for week,z in q.groupby('week'):
   for arm,a in z.groupby('arm'):tables.append(dict(season=int(season),target=target,horizon=f'W{week}',arm=arm,**metrics(a)))
 pd.DataFrame(tables).to_csv(public/'NUMERICAL.csv',index=False)
 write(public/'PAIRED.json',pairs)
 # Explicit unavailable records, never zero wins or deliberate abstention.
 pd.DataFrame([dict(target=t,arm=a,period='requested seasons',probability='N/A_no_qualified_offers_and_no_HGB_law',over='N/A',under='N/A',combined='N/A',eligible_offers=None,reason='No C-accessible exact offer/cutoff/identity export; points do not imply laws') for t in TARGETS for a in ['C0','C1','C2']]).to_csv(public/'SELECTIONS.csv',index=False)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--private',type=Path,required=True);p.add_argument('--public',type=Path,required=True);p.add_argument('--seasons',type=int,nargs='+',required=True);p.add_argument('--weeks',type=int,nargs='+');a=p.parse_args();a.public.mkdir(parents=True,exist_ok=True);run(a.source,a.private,a.public,a.seasons,a.weeks)
