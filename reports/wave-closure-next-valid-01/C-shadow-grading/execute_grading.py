"""Bounded append-only adapter for frozen C04/C06; canonical grader unchanged."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'src'))
import gzip,hashlib,io,json,lzma,math,resource,time
from collections import Counter,defaultdict
from urllib.request import Request,urlopen
import pandas as pd
from contracts_v2 import CATEGORIES,SIGNED,integer,target
from data_v2 import PHYSICAL
from forward_sources_v4 import scoreboard_projection,kickoff_frame,team,stamp,write
from prospective_v4 import validate_run,validate_receipt,grade_run,first_qualified_snapshots
REPORT=Path(__file__).resolve().parent
VERSION='C-NATIVE-GRADE-20261114-WASNYG-01'
OUT=ROOT/'prospective/outcomes'/VERSION
RUNS=['C-C04-20261110-W10-FIRST-01','C-C06-20261112-W10-CURRENT-P1-01']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_bytes())
def main():
 start=time.monotonic();cpu=time.process_time();assert not OUT.exists(),'ALREADY_GRADED_DO_NOT_OVERWRITE'
 rows=[];captures=[];original_hashes={}
 for runid in RUNS:
  folder=ROOT/'prospective/runs'/runid;receipt=ROOT/'prospective/receipts'/(runid+'-server.json');m,q=validate_run(folder);validate_receipt(folder,read(receipt),m,q)
  assert len(q)==(75 if 'C04' in runid else 25) and all(r['espn_event_id']=='401873052' and r['category']=='rec' for r in q)
  captures.append((folder,receipt));rows+=q
  for p in [folder/'RUN.json',folder/'FORECASTS.json.xz',receipt]:original_hashes[str(p.relative_to(ROOT))]=sha(p)
 manifest=[]
 def fetch(key,url):
  assert len(manifest)<3;started=stamp()
  with urlopen(Request(url,headers={'User-Agent':'Session-C-bounded-frozen-outcome-grading','Cache-Control':'no-cache'}),timeout=35) as r:
   body=r.read(5242881);assert len(body)<=5242880
   item=dict(id=key,url=url,started_UTC=started,observed_UTC=stamp(),HTTP_status=r.status,HTTP_Date=r.headers.get('Date'),HTTP_Age=r.headers.get('Age'),HTTP_Last_Modified=r.headers.get('Last-Modified'),bytes=len(body),raw_SHA256=hashlib.sha256(body).hexdigest(),raw_retention='Memory-only; permitted minimum factual projections retained')
  manifest.append(item);assert sum(x['bytes'] for x in manifest)<=5242880
  return body,item
 b,ns=fetch('native_status','https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates=20261112&limit=100')
 states=scoreboard_projection(json.loads(b),'native_status',ns['observed_UTC']);s=next(r for r in states if r['espn_event_id']=='401873052')
 assert s['season']==2026 and s['week']==10 and s['state']=='post' and s['completed'] and s['status_name']=='STATUS_FINAL','NOT_QUALIFIED_FINAL'
 assert s['home_team']=='NYG' and s['away_team']=='WAS' and all(pd.Timestamp(s['kickoff_UTC'])==pd.Timestamp(r['kickoff_UTC']) for r in rows)
 b,ss=fetch('schedule','https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv');g=kickoff_frame(pd.read_csv(io.BytesIO(b),low_memory=False));g=g[g.game_id=='2026_10_WAS_NYG'];assert len(g)==1
 game=g.iloc[0];assert abs(game.kickoff-s['kickoff'])<1 and team(game.home_team)==s['home_team'] and team(game.away_team)==s['away_team'] and pd.notna(game.home_score) and pd.notna(game.away_score)
 b,ps=fetch('stats','https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_2026.csv.gz');raw=pd.read_csv(io.BytesIO(b),compression='gzip',low_memory=False)
 frame=raw[(raw.game_id=='2026_10_WAS_NYG')&(raw.season==2026)&(raw.week==10)&(raw.season_type=='REG')].copy();assert len(frame),'FINAL_GAME_WEEKLY_STATS_NOT_YET_AVAILABLE'
 cols=list(dict.fromkeys(['player_id','game_id','team','opponent_team','position','season','week','season_type']+PHYSICAL+list(SIGNED)+['receptions']))
 assert set(cols)<=set(frame);frame=frame[cols];assert not frame.duplicated(['game_id','player_id']).any();frame['team']=frame.team.map(team);frame['opponent_team']=frame.opponent_team.map(team)
 facts={(r['game_id'],r['player_id']):r for r in frame.astype(object).where(pd.notna(frame),None).to_dict('records')}
 unique={}
 for r in rows:
  k=(r['game_id'],r['player_id'],r['category'])
  if k in unique:assert unique[k]['team']==r['team'] and unique[k]['opponent_team']==r['opponent_team'] and unique[k]['scoring_contract_id']==r['scoring_contract_id']
  else:unique[k]=r
 outcomes=[]
 for k,r in sorted(unique.items()):
  f=facts.get(k[:2]);appearance='UNKNOWN';actual=None;reasons=[];proof=[]
  if f is None:reasons.append('MISSING_STAT_ROW_NOT_ZERO_OR_DNP')
  elif f['team']!=r['team'] or f['opponent_team']!=r['opponent_team']:reasons.append('PLAYER_TEAM_EVENT_CONFLICT')
  else:
   proof=[c for c in PHYSICAL if integer(f.get(c)) is not None and integer(f[c])>0]+[c for c in SIGNED if integer(f.get(c),True) not in [None,0]]
   if proof:appearance='PLAYED';actual=target(f,r['category'],True)
   else:reasons.append('PARTICIPATION_UNRESOLVED_NOT_DNP')
   if appearance=='PLAYED' and actual is None:reasons.append('MISSING_REQUIRED_STAT_COMPONENT')
  outcomes.append(dict(game_id=r['game_id'],player_id=r['player_id'],category=r['category'],espn_event_id='401873052',kickoff_UTC=r['kickoff_UTC'],scoring_contract_id=r['scoring_contract_id'],event_status='FINAL',observed_UTC=ps['observed_UTC'],appearance=appearance,actual=actual,participation_proof_fields=proof,unavailable_reasons=reasons))
 (OUT/'evidence').mkdir(parents=True)
 write(OUT/'evidence/native_status.json',dict(event=s,source=ns))
 # Deterministic LF / gzip wire; no raw provider descriptions/model columns retained.
 csv=frame.to_csv(index=False,lineterminator='\n').encode();(OUT/'evidence/player_facts.csv.gz').write_bytes(gzip.compress(csv,mtime=0))
 g[['game_id','season','week','game_type','gameday','gametime','home_team','away_team','home_score','away_score']].to_csv(OUT/'evidence/schedule.csv',index=False,lineterminator='\n')
 write(OUT/'evidence/SOURCE_MANIFEST.json',dict(created_UTC=stamp(),sources=manifest,rows=len(frame),rights='Existing qualified ordinaryNFL numerical facts, nflverse CC BY4; minimal native final-status facts only; no presentation, odds, charting or model columns'))
 (OUT/'evidence/ATTRIBUTION.md').write_text('Ordinary NFL numerical player facts: nflverse/nflverse-data (CC BY 4.0); schedule: nflverse/nfldata. Minimal native final-status facts: public ESPN scoreboard. C retains permitted factual projections and computes append-only forecast-only grades. Observation is postgame, not a historical pregame publication clock. Missing statistics are not filled from participation. No offered lines or venue settlements are inferred.\n')
 evidence=[dict(path=str(p.relative_to(OUT)),SHA256=sha(p),source='QUALIFIED_ORDINARY_FACTS') for p in sorted((OUT/'evidence').iterdir())]
 write(OUT/'OUTCOMES.json',dict(schema='C-OUTCOMES-v4',version=VERSION,created_UTC=stamp(),source_qualification='OFFICIAL_NUMERICAL_FACTS_VERIFIED',source_evidence=evidence,outcomes=outcomes))
 grades=[];grade_files=[]
 for folder,receipt in captures:
  dest=ROOT/'prospective/grades'/(VERSION+'-'+folder.name+'.json');gg=grade_run(folder,receipt,OUT/'OUTCOMES.json',dest);grades+=gg;grade_files.append(dict(path=str(dest.relative_to(ROOT)),SHA256=sha(dest),rows=len(gg),states=dict(Counter(x['state'] for x in gg))))
 assert all(sha(ROOT/p)==h for p,h in original_hashes.items()),'FROZEN_PACKET_CHANGED'
 write(OUT/'RUN.json',dict(version=VERSION,created_UTC=stamp(),event=s,forecast_rows=len(rows),unique_outcome_rows=len(outcomes),states=dict(Counter(r['state'] for r in grades)),original_forecasts_changed=0,prop_selections=0,new_fits=0,CPU_seconds=time.process_time()-cpu,wall_seconds=time.monotonic()-start,peak_RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024))
 lookup={r['forecast_id']:r for r in rows};metrics=[]
 for folder,receipt in captures:
  runid=folder.name
  for model in sorted({r['model_id'] for r in rows if r['forecast_id'] in {g['forecast_id'] for g in read(ROOT/'prospective/grades'/(VERSION+'-'+runid+'.json'))['grades']}}):
   gs=[g for g in read(ROOT/'prospective/grades'/(VERSION+'-'+runid+'.json'))['grades'] if lookup[g['forecast_id']]['model_id']==model];scored=[g for g in gs if g['state']=='GRADED_PLAYED']
   errors=[lookup[g['forecast_id']]['mean']-g['actual'] for g in scored];mederrs=[lookup[g['forecast_id']]['median']-g['actual'] for g in scored]
   metrics.append(dict(run_id=runid,model_id=model,eligible=len(gs),states=dict(Counter(x['state'] for x in gs)),scored=len(scored),mean_MAE=sum(abs(x) for x in errors)/len(errors) if errors else None,mean_MSE=sum(x*x for x in errors)/len(errors) if errors else None,mean_bias=sum(errors)/len(errors) if errors else None,median_MAE=sum(abs(x) for x in mederrs)/len(mederrs) if mederrs else None,CRPS=sum(g['CRPS'] for g in scored)/len(scored) if scored else None,forecast_only=True,actual_offers=0,OU_direction=None))
 receipt=dict(id=VERSION,created_UTC=stamp(),original_packet_hashes=original_hashes,outcome_packet=dict(path=str((OUT/'OUTCOMES.json').relative_to(ROOT)),SHA256=sha(OUT/'OUTCOMES.json')),grade_files=grade_files,metrics=metrics,source_reads=len(manifest),response_bytes=sum(x['bytes'] for x in manifest),new_real_games=1,new_season_weeks=[[2026,10]],new_actual_offers=0,new_original_selected_sides=0,new_fits=0,first_snapshot_guard_preserved=True,source_vintage='Postgame current observed outcome facts; original pregame forecast lineage unchanged',C05='Future NEDET packet not graded or refreshed',remaining='Qualified offer capture and later games needed; one appearance-conditioned game does not establish superiority')
 write(REPORT/'GRADING_RECEIPT.json',receipt);print(json.dumps(dict(states=dict(Counter(g['state'] for g in grades)),metrics=metrics,source_reads=len(manifest),response_bytes=receipt['response_bytes'])))
if __name__=='__main__':main()
