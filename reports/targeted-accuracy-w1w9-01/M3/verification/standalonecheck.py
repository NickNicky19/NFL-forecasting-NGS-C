"""Independent C-local M3 review; no acquisition or author fitting/scoring calls.

The sole optional NFL fit is rec/W1/M3-1, selected before comparative gains.
Run --data for raw reconstruction only; --fit only after owner fitting ends.
"""
from __future__ import annotations
import argparse, collections, gzip, hashlib, io, json, math, pathlib, resource
import signal, subprocess, time, warnings, zipfile
import numpy as np
import pandas as pd
from scipy.stats import nbinom, t

ROOT = pathlib.Path(__file__).resolve().parents[4]
BASE = ROOT / 'reports/targeted-accuracy-w1w9-01/M3'
DAY = 86400
PHYSICAL = ['attempts','carries','targets','receptions','sacks_suffered','passing_tds',
 'rushing_tds','receiving_tds','passing_2pt_conversions','rushing_2pt_conversions',
 'receiving_2pt_conversions','kickoff_returns','punt_returns','special_teams_tds']
SAMPLES = [('empty',0),('ordinary',20888),('sparse',10314),('known_zero',10619),
           ('missing_stat_row',23610),('late_TE',23312)]

def read(path):
 b=pathlib.Path(path).read_bytes()
 return json.loads(gzip.decompress(b) if str(path).endswith('.gz') else b)

def digest(x):
 return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def public(x):
 if isinstance(x,dict):return {str(k):public(v) for k,v in x.items()}
 if isinstance(x,(list,tuple,np.ndarray)):return [public(v) for v in x]
 if isinstance(x,(np.integer,)):return int(x)
 if isinstance(x,(np.bool_,)):return bool(x)
 if isinstance(x,(float,np.floating)):return float(x) if math.isfinite(x) else None
 return x

def integer(v,signed=False):
 return int(v) if isinstance(v,(int,float,np.number)) and math.isfinite(v) and float(v).is_integer() and (signed or v>=0) else None

def ordinary():
 with zipfile.ZipFile(ROOT/'artifacts/basic-football-facts-v2.1.zip') as z:
  f=pd.read_csv(io.BytesIO(z.read('facts.csv.gz')),compression='gzip',low_memory=False)
  g=pd.read_csv(io.BytesIO(z.read('schedule.csv')))
 nf=pd.read_csv(ROOT/'sources/category-decision-release-01/current_facts_2026.csv.gz',low_memory=False)
 ng=pd.read_csv(ROOT/'sources/category-decision-release-01/schedule.csv')
 f=pd.concat([f,nf[(nf.season==2026)&nf.week.isin([8,9])&(nf.season_type=='REG')]],ignore_index=True)
 ng=ng[(ng.season==2026)&ng.week.isin([8,9])&(ng.game_type=='REG')]
 g=pd.concat([g,ng[list(g.columns)]],ignore_index=True)
 g['kickoff']=pd.to_datetime(g.gameday+' '+g.gametime).dt.tz_localize('America/New_York').dt.tz_convert('UTC').astype('int64')/1e9
 f=f.merge(g[['game_id','kickoff','home_team','away_team','home_score','away_score']],on='game_id',validate='many_to_one')
 f['available']=f.kickoff+7*DAY
 f['played']=((f[PHYSICAL].fillna(0)>0).any(axis=1)|
              (f[['passing_yards','rushing_yards','receiving_yards']].fillna(0)!=0).any(axis=1))
 f['final']=f.home_score.notna()&f.away_score.notna()
 assert not f[['game_id','player_id']].duplicated().any()
 assert (((f.team==f.home_team)&(f.opponent_team==f.away_team))|
         ((f.team==f.away_team)&(f.opponent_team==f.home_team))).all()
 return f,g

def qualified_label(r,target):
 if not r['played'] or not r['final']:return None
 return integer(r['receptions' if target=='rec' else 'receiving_yards'],target=='rec_yd')

def reconstruct_base(f,row,target):
 p=f[(f.player_id==row['player_id'])&(f.position.isin(['QB','RB','WR','TE']))&
     (f.season>=2022)&(f.available<row['kickoff'])].sort_values(['available','game_id']).tail(8)
 hist=p.to_dict('records');z=[]
 for n in [3,8]:
  a=[qualified_label(r,target) for r in hist[-n:]];a=[v for v in a if v is not None]
  z.extend([np.mean(a) if a else np.nan,len(a)])
 for lag in range(1,5):
  old=hist[-lag] if len(hist)>=lag else None;v=qualified_label(old,target) if old else None
  z.extend([v if v is not None else np.nan,(row['kickoff']-old['kickoff'])/DAY if old else np.nan,float(v is None)])
 z.extend([float(row['position']==role) for role in ['QB','RB','WR','TE']])
 for field in ['attempts','carries','targets']:
  v=[r[field] for r in hist[-3:] if math.isfinite(r[field])]
  z.extend([np.mean(v) if v else np.nan,len(hist[-3:]),hist[-1][field] if hist else np.nan])
 # This is the unchanged source aggregation contract, not inferred sparse zeros.
 th=f[(f.team==row['team'])&(f.season>=2022)&(f.available<row['kickoff'])].groupby(
     ['available','game_id'],sort=True)[['attempts','carries','sacks_suffered']].sum().tail(3)
 z.extend(th.mean().values if len(th) else [np.nan]*3)
 assert len(z)==32
 return np.asarray(z,float),[r['game_id'] for r in hist]

def reconstruct_context(f,g):
 paths=['sources/player-context-matchup-01/completion-decision-v1/pbp_facts_2024.csv.xz',
 'sources/player-context-matchup-01/pbp_facts_2025.csv.gz','sources/player-context-matchup-01/pbp_facts_2026.csv.gz']
 cols=['game_id','play_id','posteam','pass_attempt','sack','two_point_attempt','play_deleted',
       'play_type','receiver_player_id','air_yards','down','complete_pass']
 p=pd.concat([pd.read_csv(ROOT/x,usecols=cols,low_memory=False) for x in paths],ignore_index=True)
 assert not p[['game_id','play_id']].duplicated().any()
 valid=p[(p.pass_attempt==1)&(p.sack!=1)&(p.two_point_attempt!=1)&(p.play_deleted!=1)&(p.play_type!='no_play')].copy()
 assert valid[['pass_attempt','sack','two_point_attempt','play_deleted','complete_pass']].notna().all().all()
 assert set(valid.complete_pass.unique())<=set([0,1])
 gm={r['game_id']:r for r in g.to_dict('records')};fm={(r['game_id'],r['player_id']):r for r in f.to_dict('records')}
 official={}
 for key,z in f.groupby(['game_id','team'],sort=False):
  v=z[['attempts','completions','targets']].to_numpy(float)
  official[key]=(bool(np.isfinite(v).all() and (v>=0).all() and (v==np.floor(v)).all()),v.sum(axis=0))
 teams=[];players=[]
 for (game,team),z in valid.groupby(['game_id','posteam'],sort=False):
  if game not in gm:continue
  qg=gm[game];op=qg['away_team'] if team==qg['home_team'] else qg['home_team'];comp,ct=official[(game,team)]
  qual=comp and np.array_equal([len(z),int((z.complete_pass==1).sum()),int(z.receiver_player_id.notna().sum())],ct)
  a=np.where(z.air_yards.isna(),4,np.where(z.air_yards<0,0,np.where(z.air_yards<10,1,np.where(z.air_yards<20,2,3))))
  known=z.receiver_player_id.notna().to_numpy();good=(z.complete_pass==1).to_numpy()
  dn=np.bincount(a[known],minlength=5);dc=np.bincount(a[known&good],minlength=5)
  wrte=0;observed=set()
  for pid,zp in z[z.receiver_player_id.notna()].groupby('receiver_player_id',sort=False):
   observed.add(pid);nr=fm.get((game,pid));role=nr['position'] if nr else None
   if nr:assert nr['team']==team and nr['opponent_team']==op
   n=len(zp);c=int((zp.complete_pass==1).sum());db=np.where(zp.air_yards.isna(),4,np.where(zp.air_yards<0,0,np.where(zp.air_yards<10,1,np.where(zp.air_yards<20,2,3))))
   players.append(dict(game_id=game,player=pid,team=team,kickoff=qg['kickoff'],available=qg['kickoff']+7*DAY,
    qualified=bool(qual and nr and qualified_label(nr,'rec')==c),targets=n,attempts=len(z),depth=np.bincount(db,minlength=5),air_n=int(zp.air_yards.notna().sum()),air_sum=float(zp.air_yards.sum())))
   if role in ['WR','TE']:wrte+=n
  for nr in f[(f.game_id==game)&(f.team==team)&f.position.isin(['RB','WR','TE'])].to_dict('records'):
   if nr['player_id'] not in observed and nr['played'] and nr['targets']==0 and qualified_label(nr,'rec')==0:
    players.append(dict(game_id=game,player=nr['player_id'],team=team,kickoff=qg['kickoff'],available=qg['kickoff']+7*DAY,
     qualified=bool(qual),targets=0,attempts=len(z),depth=np.zeros(5),air_n=0,air_sum=0.))
  teams.append(dict(game_id=game,team=team,opponent=op,kickoff=qg['kickoff'],available=qg['kickoff']+7*DAY,
    qualified=bool(qual),attempts=len(z),targets=int(known.sum()),wrte=wrte,depth=dn,completed=dc))
 teams.sort(key=lambda r:(r['kickoff'],r['game_id'],r['team']))
 def prefix(rs,cut,n):return sorted([x for x in rs if x['available']<cut],key=lambda x:(x['kickoff'],x['game_id']))[-n:]
 def vsum(rs,key):return sum((r[key] for r in rs),np.zeros(5))
 for q in teams:
  earlier=prefix([r for r in teams if r['qualified']],q['kickoff'],100000)
  own=prefix([r for r in teams if r['team']==q['team'] and r['qualified']],q['kickoff'],8)
  ld=vsum(earlier,'depth');lc=vsum(earlier,'completed');base=np.divide(lc,ld,out=np.full(5,.5),where=ld>0)
  rate=(vsum(own,'completed')+20*base)/(vsum(own,'depth')+20)
  attempts=sum(r['attempts'] for r in earlier);league=sum(r['wrte'] for r in earlier)/attempts if attempts else .5
  op=(sum(r['wrte'] for r in own)+40*league)/(sum(r['attempts'] for r in own)+40)
  q['residual']=q['completed']-q['depth']*rate;q['role_residual']=q['wrte']-q['attempts']*op
  q['offense_prior_games']=[r['game_id'] for r in own]
 def vector(row):
  own=prefix([r for r in players if r['player']==row['player_id']],row['kickoff'],8)
  own=[r for r in own if r['qualified'] and r['team']==row['team']]
  n=sum(r['targets'] for r in own);a=sum(r['attempts'] for r in own)
  v=[len(own),n,a,(row['kickoff']-own[-1]['kickoff'])/DAY if own else np.nan,float(not n)]
  an=sum(r['air_n'] for r in own)
  v.extend(([sum(r['air_sum'] for r in own)/an if an else np.nan]+(vsum(own,'depth')/n).tolist()) if n else [np.nan]*6)
  window=prefix([r for r in teams if r['opponent']==row['opponent_team']],row['kickoff'],8)
  opp=[r for r in window if r['qualified']];n=sum(r['targets'] for r in opp);a=sum(r['attempts'] for r in opp)
  v.extend([len(opp),n,(row['kickoff']-opp[-1]['kickoff'])/DAY if opp else np.nan,float(not n)])
  v.extend([sum(float(r['residual'].sum()) for r in opp)/(n+40),sum(r['role_residual'] for r in opp)/(a+80)] if n else [np.nan,np.nan])
  return np.array(v),dict(own_games=[r['game_id'] for r in own],opponent_games=[r['game_id'] for r in opp],
    own_known_air_targets=an,opponent_targets=n,opponent_attempts=a,window_before_quality_filter=len(window),
    opponent_completion_residual_numerator=sum(float(r['residual'].sum()) for r in opp),
    opponent_role_residual_numerator=sum(r['role_residual'] for r in opp),
    latest_own_available=max([r['available'] for r in own],default=None),latest_opponent_available=max([r['available'] for r in opp],default=None))
 return vector,teams,dict(qualified=sum(r['qualified'] for r in teams),held=[{k:r[k] for k in ['game_id','team']} for r in teams if not r['qualified']],valid_plays=len(valid),flag_missing_in_valid=0)

def data_checks():
 start=time.process_time();prep=read(BASE/'inputs/FEATURES_AND_MEMBER_FACTS.json.gz');ctx=read(BASE/'inputs/COMPACT_CONTEXT_MATRIX.json.gz');rows=prep['rows'];f,g=ordinary()
 raw={(r['game_id'],r['player_id']):r for r in f.to_dict('records')}
 for r in rows:
  v=raw.get((r['game_id'],r['player_id']))
  if r['query_only']:
   assert (v is None or v['position'] not in ['RB','WR','TE']) and r['available'] is None and r['values']==dict(rec=None,rec_yd=None)
  else:
   assert v is not None and r['team']==v['team'] and r['position']==v['position']
   assert r['available']==v['kickoff']+7*DAY
   for target in ['rec','rec_yd']:assert r['values'][target]==qualified_label(v,target)
 vc,teams,context_source=reconstruct_context(f,g);cases=[]
 for tag,i in SAMPLES:
  row=rows[i];case=dict(case=tag,index=i,game_id=row['game_id'],player_id=row['player_id'],position=row['position'],values=row['values'])
  for target in ['rec','rec_yd']:
   z,history=reconstruct_base(f,row,target);saved=np.asarray(prep['X_by_target'][target][i],float)
   assert np.allclose(z,saved,equal_nan=True,atol=1e-12,rtol=0),(tag,target,z,saved)
   case[target+'_earlier_games']=history
  z,detail=vc(row);assert np.allclose(z,np.asarray(ctx['matrix'][i],float),equal_nan=True,atol=1e-12,rtol=0),(tag,z,ctx['matrix'][i])
  case['context']=public(z);case['context_calculation']=detail;cases.append(case)
 # Schema source absence, zero-support and undefined quality stay distinct.
 cx=np.asarray(ctx['matrix'],float);early=[i for i,r in enumerate(rows) if r['season']<2024]
 assert np.isnan(cx[np.ix_(early,[5,6,7,8,9,10,15,16])]).all()
 assert cx[10619,0]==1 and cx[10619,1]==0 and np.isnan(cx[10619,5:11]).all()
 offers=read(BASE/'inputs/NATIVE_OFFERS.json.gz');assert len(offers['primary'])==586
 keys=[(r['game_id'],r['player_id'],r['category']) for r in offers['primary']];assert len(keys)==len(set(keys))
 precedence={'pinnacle':0,'draftkings':1,'fanduel':2};groups=collections.defaultdict(list)
 for o in offers['repeated_book_views']:groups[(o['game_id'],o['player_id'],o['category'])].append(o)
 for o in offers['primary']:
  expected=min(groups[(o['game_id'],o['player_id'],o['category'])],key=lambda x:(precedence.get(x['venue'],99),x['venue'],x['offer_id']))
  assert expected['offer_id']==o['offer_id']
  assert o['quote_clock_qualification']=='UNVERIFIED_RETAINED_LINE_DIAGNOSTIC' and o['authentic_pregame_role'] is False
  assert any(r['game_id']==o['game_id'] and r['player_id']==o['player_id'] for r in rows)
 cuts={w:float(g[(g.season==2026)&(g.week==w)].kickoff.min()) for w in range(1,10)}
 memberships=[]
 for w,cut in cuts.items():
  qi=prep['query_indices_2026'][str(w)];query={rows[i]['game_id'] for i in qi}
  assert qi==[i for i,r in enumerate(rows) if r['season']==2026 and r['week']==w and r['position'] in ['WR','TE']]
  for target in ['rec','rec_yd']:
   members=[(r['game_id'],r['player_id']) for r in rows if not r['query_only'] and r['available'] is not None and r['available']<cut and r['values'][target] is not None]
   assert not query&{m[0] for m in members}
   checked=0
   for path in sorted((BASE/'models'/target/f'W{w:02}').glob('*.binding.json')):
    b=read(path);assert b['rows']==len(members) and b['membership_SHA256']==digest(members);checked+=1
   memberships.append(dict(week=w,target=target,training_rows=len(members),checked_model_bindings=checked,origin=cut))
 # Independent future-value mutation: observed future/player rows excluded by
 # the cutoff predicate cannot enter raw reconstructions or origin labels.
 mutations=[]
 for _,i in SAMPLES:
  row=rows[i];sub=f.copy();future=sub.available>=row['kickoff'];sub.loc[future,['receptions','receiving_yards','attempts','carries','targets']]=999999
  for target in ['rec','rec_yd']:
   old,_=reconstruct_base(f,row,target);new,_=reconstruct_base(sub,row,target)
   assert np.array_equal(old,new,equal_nan=True)
  mutations.append(dict(index=i,future_rows_changed=int(future.sum()),features_unchanged=True))
 return dict(status='PASS',CPU_seconds=time.process_time()-start,all_primitive_labels_reconstructed=len(rows),
  cases=cases,context_source=context_source,native_primary=586,native_repeated=len(offers['repeated_book_views']),
  native_offer_weeks=sorted({o['week'] for o in offers['primary']}),origin_memberships=memberships,
  future_target_mutation=mutations,limitations=['Current-vintage seven-day reconstruction; historical publication clocks are not authenticated.',
  'Statistical-row-conditioned query universe plus retained offer identities is not a pregame roster.',
  'Context lookback selects up to eight source appearances/games before quality/team filtering, preserving existing C01 semantics.',
  'No raw-provider acquisition, full route/alignment claim, private A/B rows or original-site parity checked.'])

def probability_checks():
 # References computed directly from SciPy; author law methods are the objects
 # under test, not the source of the expected boundaries or masses.
 from targeted_laws_m3 import NegativeBinomialLaw,DiscretizedStudentTLaw
 result=[]
 for kind,params in [('NB',(2.5,.6)),('NB',(.05,.001001)),('T',(5.,12.25,18.)),('T',(2.1,-.25,.1)),('T',(5.,.25,.1))]:
  law=NegativeBinomialLaw(*params) if kind=='NB' else DiscretizedStudentTLaw(*params)
  dist=nbinom(params[0],1-params[1]) if kind=='NB' else t(params[0],loc=params[1],scale=params[2])
  def F(k):return float(dist.cdf(math.floor(k)+(0 if kind=='NB' else .5)))
  def S(k):return float(dist.sf(math.floor(k)+(0 if kind=='NB' else .5)))
  def mass(k):return float(dist.pmf(k)) if kind=='NB' else float(dist.cdf(k+.5)-dist.cdf(k-.5))
  for line in [-3,-1,-.5,0,.5,1,5,5.5,1000000]:
   lo=math.ceil(line)-1;hi=math.floor(line);ref={'under':F(lo),'over':S(hi),'push':mass(hi) if line==hi else 0.}
   actual=law.probability(line);assert max(abs(actual[k]-ref[k]) for k in ref)<1e-12
  grid=np.arange(0,2001) if kind=='NB' else np.arange(-20000,20001)
  massv=dist.pmf(grid) if kind=='NB' else np.where(grid>=params[1],dist.sf(grid-.5)-dist.sf(grid+.5),dist.cdf(grid+.5)-dist.cdf(grid-.5))
  assert np.isfinite(massv).all() and (massv>=0).all()
  assert abs(float(massv.sum())+F(grid[0]-1)+S(grid[-1])-1)<1e-12
  assert law.pmf(-1)==0 if kind=='NB' else law.pmf(-1)>0
  assert np.all(np.diff([law.cdf(v) for v in [-100,-1,0,1,5,20,100]])>=0)
  if kind=='NB':assert abs(law.mean()-params[0]*params[1]/(1-params[1]))<1e-12
  if kind=='T' and params==(5.,.25,.1):
   reference_mean=float(grid@massv);reference_variance=float(((grid-reference_mean)**2)@massv)
   assert abs(law.mean()-reference_mean)<1e-8 and abs(law.variance()-reference_variance)<1e-8
  for p in [.01,.5,.99]:
   q=law.quantile(p);assert F(q)>=p and F(q-1)<p
  result.append(dict(kind=kind,parameters=params,normalization_with_tails=float(massv.sum())+F(grid[0]-1)+S(grid[-1])))
 return dict(status='PASS',fixtures=result,StudentT='Continuous-density training and exact integer-bin evaluation are distinct.',
  support='Receptions integer >=0 with genuine zero mass and no observed-max clipping; signed yards all integer Z; no joint receptions/targets product claimed.')

def fresh_fit():
 # Parent must signal RUNFITSFINISHED. No author fit/design/medians/start helper
 # is called here, and no new fitted model is retained.
 import torch,xgboost as xgb
 from xgboostlss.model import XGBoostLSS
 from xgboostlss.distributions.NegativeBinomial import NegativeBinomial
 from threadpoolctl import threadpool_limits
 from targeted_boost_m3 import DistributionBoost
 start=time.process_time();torch.set_num_threads(1)
 signal.signal(signal.SIGPROF,lambda *_:(_ for _ in ()).throw(RuntimeError('INDEPENDENT_FIT_20_CPU_CAP')))
 signal.setitimer(signal.ITIMER_PROF,20.)
 try:
  p=read(BASE/'inputs/FEATURES_AND_MEMBER_FACTS.json.gz');rows=p['rows'];rec=read(BASE/'models/rec/W01/M3-1.recipe.json');binding=read(BASE/'models/rec/W01/M3-1.binding.json')
  _,g=ordinary();cut=float(g[(g.season==2026)&(g.week==1)].kickoff.min())
  ids=[i for i,r in enumerate(rows) if not r['query_only'] and r['available'] is not None and r['available']<cut and r['values']['rec'] is not None]
  x=np.asarray(p['X_by_target']['rec'],float)[ids];y=np.asarray([rows[i]['values']['rec'] for i in ids],float)
  assert len(y)==19605 and digest([(rows[i]['game_id'],rows[i]['player_id']) for i in ids])==binding['membership_SHA256']
  med=np.array([np.median(col[np.isfinite(col)]) if np.isfinite(col).any() else 0. for col in x.T])
  assert np.array_equal(med,np.asarray(rec['training_medians']))
  mean=float(y.mean());variance=float(y.var());mu=max(.05,mean);r=min(10000.,max(.05,mu*mu/max(variance-mu,.01)))
  prob=min(.998999,max(.001001,mu/(r+mu)));inverse=prob-1e-6
  starts=[math.log(r-1e-6),math.log(inverse/(1-inverse))]
  assert starts==rec['start_values']
  design=np.concatenate([np.where(np.isfinite(x),x,med),~np.isfinite(x)],axis=1).astype(float)
  names=['v'+str(i) for i in range(32)]+['missing'+str(i) for i in range(32)]
  data=xgb.DMatrix(design,label=y,feature_names=names,nthread=1)
  distribution=NegativeBinomial(stabilization='L2',response_fn_total_count='exp',response_fn_probs='sigmoid',loss_fn='nll',initialize=False)
  model=XGBoostLSS(distribution);model.start_values=starts
  params=dict(max_depth=3,eta=.05,min_child_weight=30,subsample=1.,colsample_bytree=1.,reg_lambda=10.,seed=1703,nthread=1,tree_method='hist',verbosity=0)
  with threadpool_limits(limits=1):model.train(params,data,num_boost_round=32,verbose_eval=False)
  qi=p['query_indices_2026']['1'];q=np.asarray(p['X_by_target']['rec'],float)[qi];qdesign=np.concatenate([np.where(np.isfinite(q),q,med),~np.isfinite(q)],axis=1).astype(float)
  test=xgb.DMatrix(qdesign,feature_names=names,nthread=1)
  actual=distribution.predict_dist(model.booster,np.asarray(starts),test,pred_type='parameters').to_numpy(dtype=float)
  saved=DistributionBoost.load(BASE/'models/rec/W01/M3-1.json');native=saved.predict_params(q,p['feature_names']['rec']);expected=np.column_stack([native['total_count'],native['probs']])
  native_torch_difference=float(abs(actual-expected).max());assert native_torch_difference<2e-6,native_torch_difference
  raw_model=xgb.Booster(params={'nthread':1});raw_model.load_model(str(BASE/'models/rec/W01/M3-1.json'))
  test.set_base_margin(np.tile(np.asarray(starts),(len(q),1)))
  margins=raw_model.predict(test,output_margin=True);fresh_margins=model.booster.predict(test,output_margin=True)
  assert np.array_equal(margins,fresh_margins)
  margins64=np.asarray(fresh_margins,dtype=np.float64)
  independently_transformed=np.column_stack([np.exp(margins64[:,0])+1e-6,np.clip(1/(1+np.exp(-margins64[:,1]))+1e-6,.001,.999)])
  response_difference=float(abs(independently_transformed-expected).max());assert response_difference<1e-12
  difference=response_difference
  roundtrip=xgb.Booster(params={'nthread':1});roundtrip.load_model(bytearray(raw_model.save_raw(raw_format='json')))
  assert np.array_equal(roundtrip.predict(test,output_margin=True),margins)
  single=saved.predict_params(q[:1],p['feature_names']['rec']);assert all(abs(single[k][0]-native[k][0])<1e-6 for k in native)
  order=np.arange(len(q))[::-1];shuffled=saved.predict_params(q[order],p['feature_names']['rec']);assert all(np.array_equal(shuffled[k][::-1],native[k]) for k in native)
  try:saved.predict_params(q,p['feature_names']['rec'][::-1]);raise AssertionError('FEATURE_ORDER_NOT_ENFORCED')
  except ValueError:pass
  assert model.booster.get_dump(dump_format='json')==saved.booster.get_dump(dump_format='json')
  fresh_sha=hashlib.sha256(model.booster.save_raw(raw_format='json')).hexdigest()
  assert resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024<=1288490188
  return dict(status='PASS',preselected='rec/W01/M3-1',fresh_fit_attempts=1,training_rows=len(y),query_rows=len(q),
   CPU_seconds=time.process_time()-start,peak_RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
   independent_training_medians=True,independent_MOM_start=True,direct_native_XGBoostLSS_train=True,
   author_fit_helpers_called=False,parameter_max_abs_difference=difference,tree_structures_exact=True,
   batch_single_tolerance=1e-6,shuffled_row_identity='EXACT',feature_order_rejection='PASS',
   selected_before_comparative_gains=True,new_model_retained=False,model_SHA256=rec['model_SHA256'],
   fresh_native_model_SHA256=fresh_sha,native_model_bytes_exact=fresh_sha==rec['model_SHA256'],
   independent_response_transform_max_abs=response_difference,native_Torch_float32_transform_max_abs=native_torch_difference,
   float64_numeric_adapter='Raw margins unchanged; independent float64 response functions checked separately from released Torch float32 response.',
   native_JSON_roundtrip_margin_identity='EXACT')
 finally:signal.setitimer(signal.ITIMER_PROF,0)

def score_checks(score_folder='scores'):
 start=time.process_time();source=BASE/score_folder
 rr=read(BASE/'base-OFFER_ROWS.json.gz')+read(BASE/'context-OFFER_ROWS.json.gz')
 pp=read(BASE/'base-PREDICTIONS.json.gz')+read(BASE/'context-PREDICTIONS.json.gz')
 groups=collections.defaultdict(list);preds=collections.defaultdict(list)
 def key(r):return (r['category'],r['game_id'],r['player_id'])
 def grade(r):
  if r['selected_side'] is None:return 'UNAVAILABLE_FORECAST'
  if r['selected_side']=='ABSTAIN':return 'ABSTAIN'
  if r['appearance']!='PLAYED':return 'UNKNOWN_PARTICIPATION'
  if r['actual'] is None:return 'MISSING_ACTUAL'
  if r['actual']==r['line']:return 'PUSH'
  return 'WIN' if (r['actual']>r['line'])==(r['selected_side']=='OVER') else 'LOSS'
 def finite(v):return v is not None and isinstance(v,(int,float)) and math.isfinite(v)
 def assert_number(a,b):assert (a is None and b is None) or (a is not None and b is not None and abs(a-b)<=1e-10*max(1,abs(a),abs(b))),(a,b)
 def validate_summary(claim,rows):
  selected=[r for r in rows if r['selected_side'] in ['OVER','UNDER']]
  for side in ['OVER','UNDER','COMBINED']:
   z=selected if side=='COMBINED' else [r for r in selected if r['selected_side']==side]
   win=sum(grade(r)=='WIN' for r in z);loss=sum(grade(r)=='LOSS' for r in z);n=win+loss
   for k,v in dict(selected=len(z),decided=n,wins=win if n else None,losses=loss if n else None,rate=win/n if n else None).items():assert_number(claim[side][k],v)
  assert claim['unknown']==sum(grade(r) in ['UNKNOWN_PARTICIPATION','MISSING_ACTUAL','PENDING'] for r in selected)
  assert claim['unavailable']==sum(grade(r)=='UNAVAILABLE_FORECAST' for r in rows)
  assert claim['abstentions']==sum(grade(r)=='ABSTAIN' for r in rows)
  assert claim['fallback_selected']==sum(r.get('fallback') is True for r in selected)
  pknown=[r for r in rows if r.get('probabilities') is not None and r['appearance']=='PLAYED' and finite(r['actual'])]
  bs=[];ll=[]
  for r in pknown:
   truth='under' if r['actual']<r['line'] else 'over' if r['actual']>r['line'] else 'push';prob=r['probabilities']
   bs.append(sum((prob[k]-(k==truth))**2 for k in ['under','push','over'])/2)
   ll.append(-math.log(prob[truth]) if prob[truth]>0 else math.inf)
  quality=claim['probability_quality'];assert quality['probability_scored']==len(pknown)
  assert_number(quality['Brier_half_multiclass'],math.fsum(bs)/len(bs) if bs else None)
  assert_number(quality['log_loss'],math.fsum(ll)/len(ll) if ll and all(math.isfinite(v) for v in ll) else None)
 def confidence(r):
  p=r.get('probabilities');return p[r['selected_side'].lower()]/(p['over']+p['under']) if p and r['selected_side'] in ['OVER','UNDER'] and p['over']+p['under']>0 else None
 seen=set()
 for r in rr:
  z=(*key(r),r['arm'],r['product']);assert z not in seen;seen.add(z)
  assert grade(r)==r['status'],(z,grade(r),r['status'])
  if r.get('probabilities'):
   p=r['probabilities'];assert all(finite(v) and v>=0 for v in p.values()) and abs(sum(p.values())-1)<1e-10
  groups[(r['category'],r['arm'],r['product'])].append(r)
 for r in pp:preds[(r['category'],r['arm'])].append(r)
 results=read(source/'RESULTS.json.gz')['rows']
 for r in results:
  z=groups[(r['category'],r['arm'],r['product'])];z=z if r['week']=='ALL' else [v for v in z if v['week']==r['week']]
  validate_summary(r,z)
 members=read(source/'SELECTED_MEMBERSHIP.json.gz')['rows'];by_policy=collections.defaultdict(list)
 for r in members:
  weekly=[x for x in groups[(r['category'],r['arm'],r['product'])] if x['week']==r['week']]
  pool=[x for x in weekly if confidence(x) is not None and (r['side_scope']=='COMBINED' or x['selected_side']==r['side_scope'])]
  pool=sorted(pool,key=lambda x:(-confidence(x),x['game_id'],x['player_id'],x['offer_id']))
  policy=r['policy']
  if policy.startswith('COVERAGE_'):chosen=pool[:math.ceil(int(policy.split('_')[-1])/100*len(weekly))]
  elif policy.startswith('TOP_'):chosen=pool[:int(policy.split('_')[-1])]
  else:chosen=[x for x in pool if confidence(x)>=int(policy.split('_')[-1])/100]
  assert [x['offer_id'] for x in chosen]==r['selected_offer_ids'] and [x['selected_side'] for x in chosen]==r['selected_sides']
  by_policy[(r['category'],r['arm'],r['product'],r['side_scope'],policy)].extend(chosen)
 selective=read(source/'SELECTIVE.json.gz')['rows']
 selected_control_issues=[]
 for r in selective:
  if r.get('status')=='BLOCKED':continue
  chosen=by_policy[(r['category'],r['arm'],r['product'],r['side_scope'],r['policy'])]
  validate_summary(r,chosen)
  for weekly in r.get('weekly_results',[]):
   subset=[x for x in chosen if x['week']==weekly['week']];validate_summary(weekly,subset)
   board=[x for x in groups[(r['category'],r['arm'],r['product'])] if x['week']==weekly['week']]
   assert weekly['forecast_unavailable_on_board']==sum(grade(x)=='UNAVAILABLE_FORECAST' for x in board)
   assert weekly['intentional_abstentions_on_board']==sum(grade(x)=='ABSTAIN' for x in board)
  ids={key(x) for x in chosen}
  for control in r.get('controls_same_selected_cases',[]):
   expected=[x for x in groups[(r['category'],control['arm'],control['product'])] if key(x) in ids]
   if control['matched_offers']!=len(expected):selected_control_issues.append(dict(category=r['category'],arm=r['arm'],scope=r['side_scope'],policy=r['policy'],reported=control['matched_offers'],expected=len(expected)))
   else:
    lookup={key(x):x for x in expected};common=[x for x in chosen if key(x) in lookup]
    validate_summary(control['common_mask_candidate'],common);validate_summary(control['common_mask_control'],expected)
    joint=[(x,lookup[key(x)]) for x in common if grade(x) in ['WIN','LOSS'] and grade(lookup[key(x)]) in ['WIN','LOSS']]
    assert control['common_decided']==len(joint)
    assert control['candidate_wins']==sum(grade(x)=='WIN' for x,y in joint)
    assert control['control_wins']==sum(grade(y)=='WIN' for x,y in joint)
    assert control['win_difference']==control['candidate_wins']-control['control_wins']
 numerical=read(source/'NUMERICAL.json.gz')['rows']
 for r in numerical:
  broad=preds[(r['category'],r['arm'])];broad=broad if r['week']=='ALL' else [x for x in broad if x['week']==r['week']]
  offered={key(x):x for method,z in groups.items() if method[:2]==(r['category'],r['arm']) for x in z if r['week']=='ALL' or x['week']==r['week']}
  for field,rows in [('broad',broad),('identical_offered_player_rows',list(offered.values()))]:
   for point in ['mean','median']:
    claim=r[field][point];errors=[x[point]-x['actual'] for x in rows if finite(x.get(point)) and finite(x.get('actual'))]
    assert claim['eligible']==len(rows) and claim['known']==len(errors)
    assert_number(claim['MAE'],math.fsum(abs(e) for e in errors)/len(errors) if errors else None)
    assert_number(claim['MSE'],math.fsum(e*e for e in errors)/len(errors) if errors else None)
    assert_number(claim['bias'],math.fsum(errors)/len(errors) if errors else None)
 # Reproduce paired arithmetic and whole-week resampling independently of the
 # author summarizer; keys and sums below are reconstructed from frozen rows.
 def paired(candidate,control):
  right={key(x):x for x in control};pairs=[(x,right[key(x)]) for x in candidate if key(x) in right]
  for a,b in pairs:assert all(a[f]==b[f] for f in ['offer_id','line','actual','appearance'])
  decided=[(a,b) for a,b in pairs if grade(a) in ['WIN','LOSS'] and grade(b) in ['WIN','LOSS']]
  cw=sum(grade(a)=='WIN' for a,b in decided);rw=sum(grade(b)=='WIN' for a,b in decided)
  weeks=sorted({a['week'] for a,b in decided});net={w:[sum((grade(a)=='WIN')-(grade(b)=='WIN') for a,b in decided if a['week']==w),sum(a['week']==w for a,b in decided)] for w in weeks}
  interval=None
  if weeks:
   draws=np.random.default_rng(1703).integers(0,len(weeks),size=(500,len(weeks)))
   samples=sorted(sum(net[weeks[i]][0] for i in draw)/sum(net[weeks[i]][1] for i in draw) for draw in draws)
   def quantile(p):j=p*(len(samples)-1);lo=math.floor(j);return samples[lo]+(samples[math.ceil(j)]-samples[lo])*(j-lo)
   interval=[quantile(.025),quantile(.975)]
  return dict(matched_offers=len(pairs),common_decided=len(decided),candidate_wins=cw,control_wins=rw,win_difference=cw-rw,disagreements=sum(a['selected_side']!=b['selected_side'] for a,b in decided),candidate_only_wins=sum(grade(a)=='WIN' and grade(b)=='LOSS' for a,b in decided),control_only_wins=sum(grade(a)=='LOSS' and grade(b)=='WIN' for a,b in decided),week_interval=interval)
 pair_rows=read(source/'PAIRS.json.gz')['rows']
 for claim in pair_rows:
  computed=paired(groups[(claim['category'],claim['arm'],claim['product'])],groups[(claim['category'],claim['control_arm'],claim['control_product'])])
  for k,v in computed.items():
   if k=='week_interval':
    if v:
     assert_number(claim['uncertainty']['low'],v[0]);assert_number(claim['uncertainty']['high'],v[1])
   else:assert claim[k]==v
 important=[]
 for cat in ['rec','rec_yd']:
  for ca,co in [('M3-1','M3-0'),('M3-2','M3-1'),('M3-0+BLOCK','M3-0'),('M3-2','M3-0+BLOCK'),('M3-2','CONTROL_P3_DIRECT'),('M3-1','CONTROL_ALWAYS_UNDER')]:
   important.append(dict(category=cat,candidate=ca,control=co,product='LAW',**paired(groups[(cat,ca,'LAW')],groups[(cat,co,'CONSTANT' if co.startswith('CONTROL_ALWAYS') else 'LAW')])))
 return dict(status='PASS_OWN_COUNTS_MEMBERSHIPS_NUMERICAL_AND_EXISTING_PAIRS',CPU_seconds=time.process_time()-start,
  source_score_folder=score_folder,independently_regraded_rows=len(rr),broad_aggregate_views=len(results),numerical_views=len(numerical),
  exact_selected_membership_rows=len(members),existing_paired_views=len(pair_rows),selected_control_mask_issues=len(selected_control_issues),
  selected_control_first_issue=selected_control_issues[:1],representative_independent_contrasts=important,
  new_NFL_fits=0,author_grader_or_summary_functions_called=False)

if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--data',action='store_true');a.add_argument('--fit',action='store_true');a.add_argument('--law',action='store_true');a.add_argument('--scores',nargs='?',const='scores');args=a.parse_args()
 if args.data:print(json.dumps(public(dict(data=data_checks(),probability=probability_checks())),allow_nan=False))
 if args.fit:print(json.dumps(public(fresh_fit()),allow_nan=False))
 if args.law:print(json.dumps(public(probability_checks()),allow_nan=False))
 if args.scores:print(json.dumps(public(score_checks(args.scores)),allow_nan=False))
