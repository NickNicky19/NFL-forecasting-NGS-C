"""Historical features from GitHub-qualified ordinary facts only."""
import bisect
import numpy as np
import pandas as pd
from contracts_v2 import CATEGORIES,target,chart
DAY=86400
PHYSICAL=['attempts','carries','targets','receptions','sacks_suffered','passing_tds','rushing_tds','receiving_tds','passing_2pt_conversions','rushing_2pt_conversions','receiving_2pt_conversions','kickoff_returns','punt_returns','special_teams_tds']
def load(root):
 d=pd.read_csv(root/'facts.csv.gz',low_memory=False);g=pd.read_csv(root/'schedule.csv')
 required={c[1] for c in CATEGORIES.values() if c[1]}|set(PHYSICAL)
 if not required<=set(d):raise ValueError('MISSING_SOURCE_COLUMNS: '+','.join(sorted(required-set(d))))
 g['kickoff']=pd.to_datetime(g.gameday+' '+g.gametime).dt.tz_localize('America/New_York').dt.tz_convert('UTC').astype('int64')/1e9
 d=d.merge(g[['game_id','kickoff','home_team','away_team','home_score','away_score']],on='game_id',validate='many_to_one')
 assert d.player_id.str.fullmatch(r'00-\d{7}').all();assert not d.duplicated(['game_id','player_id']).any()
 assert ((d.team==d.home_team)&(d.opponent_team==d.away_team)|(d.team==d.away_team)&(d.opponent_team==d.home_team)).all()
 d['available']=d.kickoff+7*DAY
 played=(d[PHYSICAL].fillna(0)>0).any(axis=1)|(d[['passing_yards','rushing_yards','receiving_yards']].fillna(0)!=0).any(axis=1)
 d['played']=played;d['game_final']=d.home_score.notna()&d.away_score.notna()
 cs=['attempts','carries','targets','sacks_suffered','passing_yards','rushing_yards','receiving_yards']
 teams=d.groupby(['season','week','game_id','team','opponent_team','kickoff','available'],as_index=False)[cs].sum()
 opp=teams.rename(columns={'team':'opponent_team','opponent_team':'team',**{c:'allowed_'+c for c in cs}})
 teams=teams.merge(opp[['game_id','team']+['allowed_'+c for c in cs]],on=['game_id','team'],validate='one_to_one')
 d=d[d.position.isin(['QB','RB','WR','TE'])].copy();values=[];states=[]
 for r in d.to_dict('records'):
  known=bool(r['played'] and r['game_final']);values.append({t:target(r,t,known) for t in CATEGORIES});states.append(chart(r,known)[1])
 d['values']=values;d['chart_state']=states
 return d.reset_index(drop=True),g,teams
class History:
 def __init__(self,rows,key):
  self.groups={k:v.sort_values(['available','game_id']).to_dict('records') for k,v in rows.groupby(key)}
  self.times={k:[r['available'] for r in rs] for k,rs in self.groups.items()}
 def before(self,key,cutoff,n=8):
  right=bisect.bisect_left(self.times.get(key,[]),cutoff);return self.groups.get(key,[])[max(0,right-n):right]
def avg(rs,col):
 z=[r[col] for r in rs if r.get(col) is not None and np.isfinite(r[col])];return float(np.mean(z)) if z else np.nan
def vector(row,t,hist,teamhist,arm):
 rs=hist.before(row['player_id'],row['kickoff']);f=[]
 for win in [3,8]:
  y=[r['values'][t] for r in rs[-win:] if r['values'][t] is not None];f += [float(np.mean(y)) if y else np.nan,float(len(y))]
 for lag in range(1,5):
  r=rs[-lag] if len(rs)>=lag else None;v=r['values'][t] if r else None
  f += [v if v is not None else np.nan,(row['kickoff']-r['kickoff'])/DAY if r else np.nan,float(v is None)]
 f += [float(row['position']==p) for p in ['QB','RB','WR','TE']]
 if arm=='E0_BASE':return f
 for c in ['attempts','carries','targets']:
  f += [avg(rs[-3:],c),float(len(rs[-3:])),float(rs[-1][c]) if rs else np.nan]
 ts=teamhist.before(row['team'],row['kickoff'],3);f += [avg(ts,c) for c in ['attempts','carries','sacks_suffered']]
 if arm=='E0_OP':return f
 f += [float(row['team']==row['home_team']),float(row['week']), (row['kickoff']-ts[-1]['kickoff'])/DAY if ts else np.nan]
 if arm=='E0_ENV':return f
 os=teamhist.before(row['opponent_team'],row['kickoff'],3)
 for num,den in [('allowed_passing_yards','allowed_attempts'),('allowed_rushing_yards','allowed_carries'),('allowed_receiving_yards','allowed_targets')]:
  exposure=sum(r[den] for r in os);f += [sum(r[num] for r in os)/exposure if exposure>0 else np.nan,float(exposure)]
 return f
def admitted_roles(t):
 return ['QB','RB','WR','TE'] if t in ['rush_yd','rush_att','rush_rec_yd'] else CATEGORIES[t][4]
