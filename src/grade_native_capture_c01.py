"""Manual final-outcome adapter for immutable native-event captures.

Uses the existing prospective grader, source-presence contracts and server
receipts. It neither fits nor invents offered lines.
"""
import argparse,gzip,hashlib,io,json,math,resource,time
from collections import Counter
from pathlib import Path
import pandas as pd
from contracts_v2 import CATEGORIES,WEIGHTS,RARE,SIGNED,CHART,integer,target,chart
from data_v2 import PHYSICAL
from forward_sources_v4 import Retriever,scoreboard_projection,kickoff_frame,team,stamp,write
from prospective_v4 import validate_run,validate_receipt,grade_run
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_bytes())
def run(event,version):
 start=time.process_time();out=ROOT/'prospective/outcomes'/version;assert not out.exists()
 captures=[];rows=[]
 for path in (ROOT/'prospective/receipts').glob('*.json'):
  receipt=read(path);folder=ROOT/'prospective/runs'/receipt['run_id'];m,q=validate_run(folder)
  if not any(r['espn_event_id']==event for r in q):continue
  assert all(r['espn_event_id']==event for r in q),'SINGLE_NATIVE_BATCH_REQUIRED';validate_receipt(folder,receipt,m,q);captures.append((folder,path));rows+=q
 assert rows and len({r['forecast_id'] for r in rows})==len(rows)
 original=rows[0];season=int(original['season']);week=int(original['week']);date=pd.Timestamp(original['kickoff_UTC']).tz_convert('America/New_York').strftime('%Y%m%d')
 retriever=Retriever(Path('/workspace/c-context-native-grade-raw-02'),limit=3)
 b,statussrc=retriever.fetch('native_status','https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates='+date+'&limit=100')
 states=scoreboard_projection(json.loads(b),'native_status',statussrc['observed_UTC']);s=next(r for r in states if r['espn_event_id']==event)
 assert s['state']=='post' and s['completed'] and s['status_name']=='STATUS_FINAL','NOT_FINAL_NO_GRADE'
 assert s['season']==season and s['week']==week and pd.Timestamp(s['kickoff_UTC'])==pd.Timestamp(original['kickoff_UTC'])
 b,schedulesrc=retriever.fetch('schedule','https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv');g=kickoff_frame(pd.read_csv(io.BytesIO(b),low_memory=False));g=g[g.game_id==original['game_id']];assert len(g)==1
 game=g.iloc[0];assert abs(game.kickoff-s['kickoff'])<1 and team(game.home_team)==s['home_team'] and team(game.away_team)==s['away_team'] and pd.notna(game.home_score) and pd.notna(game.away_score)
 b,statsrc=retriever.fetch('stats',f'https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_{season}.csv.gz')
 frame=pd.read_csv(io.BytesIO(b),compression='gzip',low_memory=False);frame=frame[(frame.game_id==original['game_id'])&(frame.season==season)&(frame.week==week)&(frame.season_type=='REG')].copy()
 cols=list(dict.fromkeys(['player_id','game_id','team','opponent_team','position','season','week','season_type']+PHYSICAL+[v[1] for v in CATEGORIES.values() if v[1]]+list(SIGNED)+list(WEIGHTS)+['fumble_recovery_tds','special_teams_tds']))
 cols=[c for c in cols if c not in RARE];assert set(cols)<=set(frame)
 frame=frame[cols];assert not frame.duplicated(['game_id','player_id']).any();frame['team']=frame.team.map(team);frame['opponent_team']=frame.opponent_team.map(team)
 facts={(r['game_id'],r['player_id']):r for r in frame.astype(object).where(pd.notna(frame),None).to_dict('records')};outcomes=[]
 for r in rows:
  f=facts.get((r['game_id'],r['player_id']));appearance='UNKNOWN';actual=None;reasons=[];proof=[];chartstate=None
  if f is None:reasons.append('MISSING_STAT_ROW_NOT_ZERO_OR_DNP')
  elif f['team']!=r['team'] or f['opponent_team']!=r['opponent_team']:reasons.append('PLAYER_TEAM_EVENT_CONFLICT')
  else:
   proof=[c for c in PHYSICAL if integer(f.get(c)) is not None and integer(f[c])>0]+[c for c in SIGNED if integer(f.get(c),True) not in [None,0]]
   if proof:appearance='PLAYED';actual=target(f,r['category'],True)
   else:reasons.append('PARTICIPATION_UNRESOLVED_NOT_DNP')
   if appearance=='PLAYED' and r['category']=='fpts':actual,chartstate=chart(f,True)
   if appearance=='PLAYED' and actual is None:reasons.append('MISSING_REQUIRED_STAT_COMPONENT')
  a=dict(game_id=r['game_id'],player_id=r['player_id'],category=r['category'],espn_event_id=event,kickoff_UTC=r['kickoff_UTC'],scoring_contract_id=r['scoring_contract_id'],event_status='FINAL',observed_UTC=max(m['observed_UTC'] for m in retriever.manifest),appearance=appearance,actual=actual,participation_proof_fields=proof,unavailable_reasons=reasons,chart_state=chartstate)
  if r['category']=='anytime_td' and appearance=='PLAYED':a['event_components']={c:integer(f.get(c)) for c in ['rushing_tds','receiving_tds']}
  if r['category']=='fpts' and actual is not None:
   components={c:integer(f.get(c),c in SIGNED) for c in WEIGHTS if c not in RARE};components.update({c:0 for c in RARE});assert f['fumble_recovery_tds']==0 and f['special_teams_tds']==0
   a.update(score_components=components,unique_event_credits_verified=True,unique_credit_proof=dict(native_row_unique=True,fumbles='Direct unique total once',two_points='Separate credited pass/rush/rec conversions;ordinaryreceptions once',rare='Fourzeroes only from explicit broad fumbleRecoveryTD0 and specialTeamsTD0',contract=CHART))
  outcomes.append(a)
 (out/'evidence').mkdir(parents=True);write(out/'evidence/native_status.json',dict(event=s,source=statussrc));frame.to_csv(out/'evidence/player_facts.csv.gz',index=False,compression={'method':'gzip','mtime':0});g[['game_id','season','week','game_type','gameday','gametime','home_team','away_team','home_score','away_score']].to_csv(out/'evidence/schedule.csv',index=False)
 write(out/'evidence/SOURCE_MANIFEST.json',dict(created_UTC=stamp(),sources=retriever.manifest,rows=len(frame),rights='Existing qualified ordinaryNFL numerical facts, nflverse CC BY4;minimal native final-status facts only;no presentation/odds/model columns'))
 (out/'evidence/ATTRIBUTION.md').write_text('NFL numerical player facts: nflverse/nflverse-data, CC BY 4.0; schedule:nflverse/nfldata. Native final-status facts: public ESPN scoreboard. C retains minimal factual projections, preserves missingness and computes append-only statistical grades with the existing grader. No actual prop line or venue settlement is inferred.\n')
 evidence=[dict(path=str(p.relative_to(out)),SHA256=sha(p),source='QUALIFIED_ORDINARY_FACTS') for p in (out/'evidence').iterdir()]
 write(out/'OUTCOMES.json',dict(schema='C-OUTCOMES-v4',version=version,created_UTC=stamp(),source_qualification='OFFICIAL_NUMERICAL_FACTS_VERIFIED',source_evidence=evidence,outcomes=outcomes))
 grades=[]
 for folder,receipt in captures:grades+=grade_run(folder,receipt,out/'OUTCOMES.json',ROOT/'prospective/grades'/(version+'-'+folder.name+'.json'))
 write(out/'RUN.json',dict(version=version,created_UTC=stamp(),event=s,forecast_rows=len(rows),states=dict(Counter(r['state'] for r in grades)),original_forecasts_changed=0,prop_selections=0,new_fits=0,CPU_seconds=time.process_time()-start,peak_RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024))
 print(read(out/'RUN.json'))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--event',required=True);p.add_argument('--version',required=True);a=p.parse_args();run(a.event,a.version)
