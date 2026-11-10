"""Receiving-defense role/depth profiles from eligible, qualified official attempts.

Raw contextual response, not opponent-adjusted talent or receiver alignment.
All historical clocks retain the declared current-vintage seven-day assumption.
"""
from collections import defaultdict
import math
import numpy as np
import pandas as pd
from context_features_c01 import Context, depth_bin
from data_v2 import DAY

VERSION='C-RECEIVING-DEFENSE-C03-v1'
TEAMS=['ARI','ATL','BAL','BUF','CAR','CHI','CIN','CLE','DAL','DEN','DET','GB','HOU','IND','JAX','KC','LA','LAC','LV','MIA','MIN','NE','NO','NYG','NYJ','PHI','PIT','SEA','SF','TB','TEN','WAS']
ROLES=['WR','TE','RB','OTHER_OR_UNKNOWN']
DEPTH=['behind_LOS','0_9','10_19','20plus','UNKNOWN']
SUPPORT_NAMES=['receiving_defense_games8','receiving_defense_target_support8','receiving_defense_age_days','receiving_defense_missing']
VALUE_NAMES=[f'receiving_defense_{r}_catch_per_target_{d}' for r in ['WR','TE'] for d in DEPTH[:4]]+[f'receiving_defense_{r}_target_share' for r in ['WR','TE']]
FEATURE_NAMES=SUPPORT_NAMES+VALUE_NAMES
CELL_NAMES=['targets','catches','known_target_yard_count','known_target_yard_sum','known_catch_yard_count','known_catch_yard_sum']

def finite(x):
 try:return x is not None and math.isfinite(float(x))
 except (TypeError,ValueError):return False

def when(value):
 if isinstance(value,str):
  t=pd.Timestamp(value)
  if t.tzinfo is None:raise ValueError('TIMEZONE_AWARE_CUTOFF_REQUIRED')
  value=t.timestamp()
 if not finite(value):raise ValueError('FINITE_CUTOFF_REQUIRED')
 return float(value)

def safe(x):
 if isinstance(x,dict):return {k:safe(v) for k,v in x.items()}
 if isinstance(x,(list,tuple,np.ndarray)):return [safe(v) for v in x]
 if isinstance(x,(float,np.floating)):return float(x) if finite(x) else None
 if isinstance(x,(bool,np.bool_)):return bool(x)
 if isinstance(x,(int,np.integer)):return int(x)
 return x

def ratio(n,d):return float(n/d) if d>0 else None

def wilson(n,d):
 if not d:return None
 z=1.959963984540054;p=n/d;den=1+z*z/d;c=(p+z*z/(2*d))/den;h=z*math.sqrt(p*(1-p)/d+z*z/(4*d*d))/den
 return {'low':max(0.,c-h),'high':min(1.,c+h),'method':'WILSON_DESCRIPTIVE_TARGET_COUNTS_NOT_INDEPENDENT_GAME_GUARANTEE'}

class ReceivingDefense:
 """No acquisition, inference or fitting occurs at import/construction.

 ``context`` is the existing strict reconciliation object. Supplying it avoids a
 second source extraction. Without it, construction performs that same check.
 """
 def __init__(self,frames,players,schedule,*,context=None,all_position_counts=None,source_bindings=None):
  self.sources=source_bindings or {};self.lookback=8;self._league_cache={}
  context=context or Context(frames,players,schedule,strict=True,all_position_counts=all_position_counts)
  quality={(r['game_id'],r['team']):bool(r['qualified']) for r in context.quality}
  facts=players.to_dict('records') if hasattr(players,'to_dict') else list(players)
  factmap={}
  for r in facts:
   key=(r['game_id'],r['player_id'])
   if key in factmap:raise ValueError('DUPLICATE_NATIVE_PLAYER_EVENT')
   factmap[key]=r
  games={r['game_id']:r for r in schedule.to_dict('records')}
  yard_field={game:('receiving_yards' in frame.columns) for frame in frames for game in frame.game_id.unique()}
  pbp=pd.concat(frames,ignore_index=True)
  if pbp.duplicated(['game_id','play_id']).any():raise ValueError('DUPLICATE_PLAY_VERSION')
  needed={'game_id','play_id','posteam','pass_attempt','sack','two_point_attempt','play_deleted','play_type','receiver_player_id','air_yards','complete_pass'}
  if not needed<=set(pbp):raise ValueError('MISSING_RECEIVING_PBP_FIELDS')
  valid=pbp[(pbp.pass_attempt==1)&(pbp.sack!=1)&(pbp.two_point_attempt!=1)&(pbp.play_deleted!=1)&(pbp.play_type!='no_play')]
  self.rows=[];self.rejected=[];self.groups=defaultdict(list)
  for (game,offense),f in valid.groupby(['game_id','posteam'],sort=False):
   if game not in games or not quality.get((game,offense),False):
    self.rejected.append({'game_id':game,'offense':offense,'reason':'UNQUALIFIED_OFFICIAL_ATTEMPT_TARGET_COMPLETION_TOTALS'});continue
   g=games[game];kick=g.get('kickoff')
   if not finite(kick):raise ValueError('UNKNOWN_GAME_TIME')
   # An explicitly unknown clock is not repaired by the absent-column policy.
   av=g.get('available') if 'available' in g else float(kick)+7*DAY
   if not finite(av):
    self.rejected.append({'game_id':game,'offense':offense,'reason':'EXPLICIT_UNKNOWN_AVAILABILITY'});continue
   if float(av)<float(kick):
    self.rejected.append({'game_id':game,'offense':offense,'reason':'OUTCOME_AVAILABILITY_BEFORE_GAME'});continue
   if offense not in [g['home_team'],g['away_team']]:raise ValueError('OFFENSE_EVENT_IDENTITY')
   defense=g['away_team'] if offense==g['home_team'] else g['home_team']
   cells=np.zeros((4,5,6));unallocated=0
   for p in f.to_dict('records'):
    pid=p.get('receiver_player_id')
    if pd.isna(pid):unallocated+=1;continue
    native=factmap.get((game,pid));role=native.get('position') if native else None
    if native and (native['team']!=offense or native['opponent_team']!=defense):raise ValueError('RECEIVER_HISTORICAL_TEAM_IDENTITY')
    ri=ROLES.index(role) if role in ROLES[:3] else 3;di=depth_bin(p.get('air_yards'))
    c=cells[ri,di];c[0]+=1;complete=p.get('complete_pass')==1;c[1]+=int(complete)
    y=p.get('receiving_yards')
    if finite(y):
     c[2]+=1;c[3]+=float(y)
     if complete:c[4]+=1;c[5]+=float(y)
   r={'game_id':game,'season':int(g['season']) if 'season' in g else None,'week':int(g['week']) if 'week' in g else None,'offense':offense,'defense':defense,'kickoff':float(kick),'available':float(av),'attempts':len(f),'unallocated_attempts':unallocated,'yard_field_present':yard_field.get(game,False),'cells':cells}
   assert int(cells[:,:,0].sum())+unallocated==len(f)
   self.rows.append(r);self.groups[defense].append(r)
  for rs in self.groups.values():rs.sort(key=lambda r:(r['kickoff'],r['game_id'],r['offense']))
  self.rows.sort(key=lambda r:(r['kickoff'],r['game_id'],r['offense']))
 def before(self,team,cutoff,n=8):
  cut=when(cutoff)
  # Admit by availability first, then choose latest games by GAME time.
  return sorted([r for r in self.groups.get(team,[]) if r['available']<cut and r['kickoff']<cut],key=lambda r:(r['kickoff'],r['game_id'],r['offense']))[-n:]
 def _summary(self,team,cutoff):
  cut=when(cutoff);rs=self.before(team,cut)
  if cut not in self._league_cache:
   league=[r for r in self.rows if r['available']<cut and r['kickoff']<cut]
   self._league_cache[cut]=(len(league),sum((r['cells'] for r in league),np.zeros((4,5,6))))
  league,prior=self._league_cache[cut]
  cell=sum((r['cells'] for r in rs),np.zeros((4,5,6)))
  total=float(cell[:,:,0].sum());lt=float(prior[:,:,0].sum());lc=float(prior[:,:,1].sum());base=lc/lt if lt else .5
  # Neutral .5 only at complete league startup; row/cell support remains explicit.
  league_rate=np.divide(prior[:,:,1],prior[:,:,0],out=np.full((4,5),base),where=prior[:,:,0]>0)
  rate=(cell[:,:,1]+20*league_rate)/(cell[:,:,0]+20)
  lshare=prior[:,:,0].sum(axis=1)/lt if lt else np.full(4,np.nan)
  share=(cell[:,:,0].sum(axis=1)+40*lshare)/(total+40)
  return cut,rs,league,cell,prior,rate,share
 def vector(self,row,cutoff=None):
  cut=min(when(row['kickoff']),when(cutoff)) if cutoff is not None else when(row['kickoff'])
  _,rs,_,cell,_,rate,share=self._summary(row['opponent_team'],cut)
  n=float(cell[:,:,0].sum());support=[len(rs),n,(cut-rs[-1]['kickoff'])/DAY if rs else np.nan,float(not n)]
  values=list(rate[:2,:4].reshape(-1))+list(share[:2]) if n else [np.nan]*10
  return np.asarray(support+values,dtype=float)
 def profile(self,team,cutoff,event_id=None):
  if team not in TEAMS:raise ValueError('UNKNOWN_CANONICAL_DEFENSE_TEAM')
  cut,rs,league,cells,prior,rates,shares=self._summary(team,cutoff);n=float(cells[:,:,0].sum());lt=float(prior[:,:,0].sum());out=[]
  for ri,role in enumerate(ROLES):
   for di,depth in enumerate(DEPTH):
    t,c,yn,ys,cyn,cys=cells[ri,di];pt,pc,_,_,_,_=prior[ri,di]
    out.append({'role':role,'depth':depth,'targets':int(t),'catches':int(c),'catch_per_target':{'numerator':int(c),'denominator':int(t),'raw':ratio(c,t),'shrunk':float(rates[ri,di]),'prior_numerator':int(pc),'prior_denominator':int(pt),'pseudo_targets':20,'interval':wilson(c,t)},'target_yardage':{'known_target_yard_count':int(yn),'known_target_yard_sum':float(ys),'known_yard_target_mean':ratio(ys,yn),'yards_per_all_targets':ratio(ys,t) if yn==t and t else None,'all_target_components_complete':bool(t and yn==t)},'catch_yardage':{'known_catch_yard_count':int(cyn),'known_catch_yard_sum':float(cys),'known_yard_reception_mean':ratio(cys,cyn),'yards_per_all_receptions':ratio(cys,c) if cyn==c and c else None,'all_catch_components_complete':bool(c and cyn==c)},'state':'KNOWN_ZERO_TARGETS_IN_OBSERVED_GAMES' if rs and t==0 else 'OBSERVED' if t else 'NO_ELIGIBLE_HISTORY'})
  return safe({'schema':VERSION,'team':team,'event_id':event_id,'information_cutoff_UTC':pd.Timestamp(cut,unit='s',tz='UTC').isoformat(),'state':'HISTORICAL_PROFILE_AVAILABLE' if rs else 'UNAVAILABLE_HISTORY','lookback_eligible_team_games':8,'eligible_games':len(rs),'eligible_targeted_plays':int(n),'official_attempts':sum(r['attempts'] for r in rs),'unallocated_official_attempts':sum(r['unallocated_attempts'] for r in rs),'history':[{'game_id':r['game_id'],'offense':r['offense'],'kickoff':r['kickoff'],'assumed_available':r['available']} for r in rs],'latest_source_game':rs[-1]['game_id'] if rs else None,'latest_source_assumed_available':max((r['available'] for r in rs),default=None),'availability':'CURRENT_VINTAGE_RECONSTRUCTED_KICKOFF_PLUS7D;explicit supplied unknown clocks rejected','sources':self.sources,'role_target_share':[{'role':role,'targets':int(cells[i,:,0].sum()),'all_role_targets':int(n),'raw':ratio(cells[i,:,0].sum(),n),'shrunk':shares[i],'pseudo_targets':40} for i,role in enumerate(ROLES)],'cells':out,'yard_field_presence':{'games_with_column':sum(r['yard_field_present'] for r in rs),'games_without_column':sum(not r['yard_field_present'] for r in rs),'parsed_null_or_nonfinite':'Not converted to zero; raw CSV token distinctions not authenticated by passed DataFrames.'},'league_prior_eligible_team_games':league,'league_prior_targets':int(lt),'field_orientation':'Depth from air_yards relative to line of scrimmage; not receiver starting alignment; no left/right field inferred','opponent_quality':'RAW_CONTEXT_CONDITIONAL_RESPONSE;not opponent-adjusted talent. Earlier faced-offense/game mix remains a limitation. Oldcontext residual is a separate existing block, not double applied.','missingness':'Known zero cell counts differ from absent history; unknown yardage not filled from participation or incompletion. Known-yard denominators and complete-all-target/reception flags are explicit.','uncertainty':'Catch intervals descriptive target-level only; games/teams remain dependent. Yardage uncertainty not estimated; raw signed sums and support retained.','unavailable_components':{'rushing':'OWNER_A','passing_dropback_conversion':'OWNER_B','alignment_routes_coverage':'SOURCE_BLOCKED'},'model_vector_order':FEATURE_NAMES})
 def snapshot(self,cutoff,event_map=None):return [self.profile(t,cutoff,(event_map or {}).get(t)) for t in TEAMS]
