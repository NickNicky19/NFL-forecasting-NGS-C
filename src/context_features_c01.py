"""Earlier-only target-location proxies; never receiver alignment or routes."""
import bisect
from collections import defaultdict
from pathlib import Path
import numpy as np
import pandas as pd
from data_v2 import DAY

OWN_NAMES=['ctx_player_games8','ctx_targets8','ctx_team_attempts8','ctx_age_days','ctx_missing','ctx_targets_per_team_attempt','ctx_targets_per_appearance','ctx_catch_per_target','ctx_mean_air_per_known_target','ctx_mean_YAC_per_complete_known_target','ctx_short_to_go_target_share','ctx_redzone_target_share']+[f'ctx_depth_share_{x}' for x in ['behind','0_9','10_19','20plus','unknown']]+[f'ctx_down_share_{x}' for x in ['1','2','3','4','unknown']]
OPP_NAMES=['opp_context_games8','opp_target_support8','opp_age_days','opp_missing','opp_offense_adjusted_completion_residual','opp_offense_adjusted_WRTE_target_share_residual']
INTER_NAMES=['predicted_depth_mix_x_opponent_catch_residual','predicted_down_mix_x_opponent_catch_residual']
def depth_bin(v):
 if v is None or not np.isfinite(v):return 4
 return 0 if v<0 else 1 if v<10 else 2 if v<20 else 3
def down_bin(v):return int(v)-1 if v is not None and np.isfinite(v) and v in [1,2,3,4] else 4
def summed(rs,name,n=5):return sum((r[name] for r in rs),np.zeros(n))
class Prefix:
 def __init__(self,rows,key):
  self.groups=defaultdict(list)
  for r in rows:self.groups[r[key]].append(r)
  for rs in self.groups.values():rs.sort(key=lambda r:(r['kickoff'],r['game_id']))
  self.times={k:[r['available'] for r in rs] for k,rs in self.groups.items()}
 def before(self,key,cutoff,n=8):
  # The declared constant lag makes game-time and availability order compatible.
  rs=self.groups.get(key,[]);right=bisect.bisect_left(self.times.get(key,[]),cutoff)
  return rs[max(0,right-n):right]
class Context:
 def __init__(self,frames,players,schedule):
  pbp=pd.concat(frames,ignore_index=True)
  assert not pbp.duplicated(['game_id','play_id']).any()
  games={r['game_id']:r for r in schedule.to_dict('records')}
  facts={(r['game_id'],r['player_id']):r for r in players.to_dict('records')}
  teamfacts=players.groupby(['game_id','team'],sort=False).attempts.sum().to_dict()
  # Preserve official attempts: sacks/no-plays/deleted/two-point plays excluded;
  # spikes remain attempts. Missing receiver is an unallocated target bucket.
  valid=pbp[(pbp.pass_attempt==1)&(pbp.sack!=1)&(pbp.two_point_attempt!=1)&(pbp.play_deleted!=1)&(pbp.play_type!='no_play')].copy()
  teamrows=[];playerrows=[];quality=[]
  for (game,team),f in valid.groupby(['game_id','posteam'],sort=False):
   if game not in games:continue
   g=games[game];opp=g['away_team'] if team==g['home_team'] else g['home_team']
   if team not in [g['home_team'],g['away_team']]:raise ValueError('TEAM_EVENT_CONFLICT')
   attempts=len(f);official=teamfacts.get((game,team));qualified=official is not None and np.isfinite(official) and attempts==official
   q=dict(game_id=game,team=team,opponent=opp,kickoff=float(g['kickoff']),available=float(g['kickoff'])+7*DAY,attempts=attempts,official_attempts=official,passing_complete=bool(qualified),targets=0,wrte_targets=0,depth_n=np.zeros(5),depth_c=np.zeros(5),down_n=np.zeros(5),down_c=np.zeros(5))
   observed_ids=set()
   for pid,pf in f[f.receiver_player_id.notna()].groupby('receiver_player_id',sort=False):
    observed_ids.add(pid)
    native=facts.get((game,pid));role=native.get('position') if native else None
    if native is not None:assert native['team']==team and native['opponent_team']==opp,'PLAYER_TEAM_CONFLICT'
    dn=np.zeros(5);dc=np.zeros(5);un=np.zeros(5);uc=np.zeros(5)
    for r in pf.to_dict('records'):
     k=depth_bin(r['air_yards']);h=down_bin(r['down']);dn[k]+=1;un[h]+=1
     if r['complete_pass']==1:dc[k]+=1;uc[h]+=1
    n=len(pf);comp=int((pf.complete_pass==1).sum());label=native['values']['rec'] if native else None
    matched=label is not None and label==comp
    p=dict(game_id=game,team=team,player_id=pid,role=role,kickoff=q['kickoff'],available=q['available'],targets=n,completions=comp,depth_n=dn,depth_c=dc,down_n=un,down_c=uc,attempts=attempts,team_complete=bool(qualified),receptions_match=bool(matched),air_sum=float(pf.air_yards.sum()),air_n=int(pf.air_yards.notna().sum()),yac_sum=float(pf.loc[pf.complete_pass==1,'yards_after_catch'].sum()),yac_n=int(((pf.complete_pass==1)&pf.yards_after_catch.notna()).sum()),short=int((pf.ydstogo<=3).sum()),redzone=int((pf.yardline_100<=20).sum()))
    playerrows.append(p);q['targets']+=n
    if role in ['WR','TE']:q['wrte_targets']+=n
    q['depth_n']+=dn;q['depth_c']+=dc;q['down_n']+=un;q['down_c']+=uc
   # Include verified played-zero target appearances only with explicit ordinary
   # count evidence; absence from a targeted-pass table alone proves nothing.
   for native in players[(players.game_id==game)&(players.team==team)&players.position.isin(['RB','WR','TE'])].to_dict('records'):
    if native['player_id'] in observed_ids or not native['played']:continue
    if native.get('targets')!=0 or native['values']['rec']!=0:continue
    playerrows.append(dict(game_id=game,team=team,player_id=native['player_id'],role=native['position'],kickoff=q['kickoff'],available=q['available'],targets=0,completions=0,depth_n=np.zeros(5),depth_c=np.zeros(5),down_n=np.zeros(5),down_c=np.zeros(5),attempts=attempts,team_complete=bool(qualified),receptions_match=True,air_sum=0.,air_n=0,yac_sum=0.,yac_n=0,short=0,redzone=0))
   teamrows.append(q);quality.append(dict(game_id=game,team=team,pbp_attempts=attempts,official_attempts=float(official) if official is not None else None,qualified=bool(qualified)))
  self.players=Prefix(playerrows,'player_id');self.teams=Prefix(teamrows,'team')
  self.quality=quality;self.raw_player_games=playerrows
  ordered=sorted(teamrows,key=lambda r:(r['kickoff'],r['game_id'],r['team']))
  self.league=Prefix([dict(r,league='ALL') for r in teamrows],'league')
  defenses=[]
  for r in ordered:
   prior=self.teams.before(r['team'],r['kickoff'],8)
   league=self.league.before('ALL',r['kickoff'],100000)
   ln=summed(league,'depth_n');lc=summed(league,'depth_c');base=np.divide(lc,ln,out=np.full(5,.5),where=ln>0)
   # Shrink to the earlier league, then account for offense faced before this game.
   rate=(summed(prior,'depth_c')+20*base)/(summed(prior,'depth_n')+20)
   un=summed(league,'down_n');uc=summed(league,'down_c');ub=np.divide(uc,un,out=np.full(5,.5),where=un>0)
   urate=(summed(prior,'down_c')+20*ub)/(summed(prior,'down_n')+20)
   la=sum(x['attempts'] for x in league);lp=sum(x['wrte_targets'] for x in league)/la if la else .5
   op=(sum(x['wrte_targets'] for x in prior)+40*lp)/(sum(x['attempts'] for x in prior)+40)
   defenses.append(dict(r,defense=r['opponent'],depth_residual=r['depth_c']-r['depth_n']*rate,down_residual=r['down_c']-r['down_n']*urate,role_residual=r['wrte_targets']-r['attempts']*op))
  self.defenses=Prefix(defenses,'defense')
 def own(self,row,lookback=8):
  rs=self.players.before(row['player_id'],row['kickoff'],lookback)
  # Missing stat rows and mismatched totals are not filled as zero.
  rs=[r for r in rs if r['team_complete'] and r['receptions_match'] and r['team']==row['team']]
  n=sum(r['targets'] for r in rs);a=sum(r['attempts'] for r in rs)
  first=[len(rs),n,a,(row['kickoff']-rs[-1]['kickoff'])/DAY if rs else np.nan,float(not n)]
  if not n:return np.asarray(first+[np.nan]*(len(OWN_NAMES)-len(first)))
  dn=summed(rs,'depth_n')/n;un=summed(rs,'down_n')/n
  an=sum(r['air_n'] for r in rs);yn=sum(r['yac_n'] for r in rs)
  extra=[n/a if a else np.nan,n/len(rs),sum(r['completions'] for r in rs)/n,sum(r['air_sum'] for r in rs)/an if an else np.nan,sum(r['yac_sum'] for r in rs)/yn if yn else np.nan,sum(r['short'] for r in rs)/n,sum(r['redzone'] for r in rs)/n]
  return np.asarray(first+extra+dn.tolist()+un.tolist())
 def features(self,row):
  own=self.own(row);rs=self.defenses.before(row['opponent_team'],row['kickoff'],8)
  rs=[r for r in rs if r['passing_complete']]
  n=sum(r['targets'] for r in rs);a=sum(r['attempts'] for r in rs)
  opp=[len(rs),n,(row['kickoff']-rs[-1]['kickoff'])/DAY if rs else np.nan,float(not n)]
  if not n:return own,np.asarray(opp+[np.nan,np.nan]),np.full(2,np.nan)
  dr=summed(rs,'depth_residual')/(summed(rs,'depth_n')+40)
  ur=summed(rs,'down_residual')/(summed(rs,'down_n')+40)
  opp += [sum(float(r['depth_residual'].sum()) for r in rs)/(n+40),sum(r['role_residual'] for r in rs)/(a+80)]
  mix=own[12:17];dm=own[17:22]
  inter=[float(mix@dr),float(dm@ur)] if np.isfinite(mix).all() else [np.nan,np.nan]
  return own,np.asarray(opp),np.asarray(inter)
 def opponent_export(self,row):
  _,op,it=self.features(row)
  return dict(game_id=row['game_id'],player_id=row['player_id'],team=row['team'],opponent=row['opponent_team'],kickoff=row['kickoff'],own=self.own(row).tolist(),opponent_context=op.tolist(),predicted_mix_interactions=it.tolist())
