import sys,pathlib,json,gzip,io,lzma,csv,hashlib,datetime
from urllib.request import Request,urlopen
import pandas as pd
root=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'src'))
from context_sources_c01 import COLS,guard
from forward_sources_v4 import kickoff_frame,scoreboard_projection,team,native,records,quarantine_stat_orphans
out=root/'sources/player-context-matchup-01/completion-decision-v1';out.mkdir(parents=True,exist_ok=True);report=root/'reports/player-context-matchup-01/completion-decision-v1';ledger=[]
assert not (out/'PBP2024_MANIFEST.json').exists(), 'Completed acquisition frozen; register a new snapshot/version before another retrieval'
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def get(key,url,cap=28*1024*1024):
 assert len(ledger)<16
 started=now()
 with urlopen(Request(url,headers={'User-Agent':'C-manual-completion-decision-v1','Cache-Control':'no-cache'}),timeout=45) as f:
  b=f.read(cap+1);assert len(b)<=cap;h={k.lower():v for k,v in f.headers.items()}
 d={'id':key,'url':url,'started_UTC':started,'observed_UTC':now(),'bytes':len(b),'SHA256':hashlib.sha256(b).hexdigest(),'Date':h.get('date'),'Last-Modified':h.get('last-modified'),'ETag':h.get('etag')};ledger.append(d);assert sum(x['bytes'] for x in ledger)<=83886080
 (report/'SOURCE_GETS.json').write_text(json.dumps(ledger,indent=2)+'\n');return b,d
def project(b,cols,path):
 buf=io.StringIO();w=csv.DictWriter(buf,fieldnames=cols,lineterminator='\n');w.writeheader();count=0;games=set()
 with gzip.open(io.BytesIO(b),'rt') as f:
  reader=csv.DictReader(f);assert set(cols)<=set(reader.fieldnames)
  for row in reader:
   if row['season_type']!='REG' or not any(row[k]=='1' for k in ['pass_attempt','rush_attempt','qb_dropback']):continue
   w.writerow({k:row[k] for k in cols});count+=1;games.add(row['game_id'])
 body=lzma.compress(buf.getvalue().encode(),preset=6);guard();assert not path.exists();path.write_bytes(body);guard();return {'path':str(path.relative_to(root)),'bytes':len(body),'SHA256':hashlib.sha256(body).hexdigest(),'decoded_SHA256':hashlib.sha256(buf.getvalue().encode()).hexdigest(),'rows':count,'games':len(games),'columns':cols}
# New historic source, not a replacement for frozen2025/26 sources.
b,m=get('PBP2024','https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_2024.csv.gz');p=project(b,COLS,out/'pbp_facts_2024.csv.xz');(out/'PBP2024_MANIFEST.json').write_text(json.dumps({'source':m,'projection':p,'rights':'ExistingpublisherCCBY4ordinaryfacts, same retainedlicense2a82ac9...;notFTN/NGSgrant','tier':'Currentrevisedhistoricalreconstruction;+7daypolicyonly'},indent=2)+'\n');print('PBP2024_READY',p['bytes'],p['rows'],flush=True)
# Current query uses a current factual snapshot. No game actual is queried to
# construct player membership. Whole upstream payloads stay only in memory.
q=out/'current-query';q.mkdir();b,sm=get('SCHEDULE_CURRENT','https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv',4*1024*1024);g=kickoff_frame(pd.read_csv(io.BytesIO(b),low_memory=False));future=g[(g.season==2026)&(g.game_type=='REG')&(g.kickoff>pd.Timestamp.now(tz='UTC').timestamp()+300)].sort_values(['kickoff','game_id']);assert len(future);game=future.iloc[0];day=pd.Timestamp(game.kickoff,unit='s',tz='UTC').tz_convert('America/New_York').strftime('%Y%m%d')
b,em=get('STATUS_CURRENT','https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates='+day+'&limit=100',2*1024*1024);events=scoreboard_projection(json.loads(b),'STATUS_CURRENT',em['observed_UTC']);e=next(x for x in events if x['espn_event_id']==native(game.espn));assert e['state']=='pre' and not e['completed'] and e['status_name']=='STATUS_SCHEDULED' and abs(e['kickoff']-game.kickoff)<1;e['game_id']=game.game_id;assert {e['home_team'],e['away_team']}=={team(game.home_team),team(game.away_team)}
b,rm=get('ROSTER_CURRENT','https://github.com/nflverse/nflverse-data/releases/download/weekly_rosters/roster_weekly_2026.csv.gz',8*1024*1024);r=pd.read_csv(io.BytesIO(b),compression='gzip',low_memory=False);r=r[(r.season==2026)&(r.week<=int(game.week))&r.team.map(team).isin([e['home_team'],e['away_team']])&r.position.isin(['QB','RB','WR','TE'])].copy();week=int(r.week.max());r=r[r.week==week][['season','week','team','gsis_id','full_name','position','status','depth_chart_position']];r['team']=r.team.map(team);assert not r.dropna(subset=['gsis_id']).duplicated(['gsis_id']).any()
(q/'roster.json').write_text(json.dumps(records(r),separators=(',',':'))+'\n');(q/'events.json').write_text(json.dumps([e],indent=2)+'\n')
b,pm=get('PBP2026_CURRENT','https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_2026.csv.gz');cols=['game_id','play_id','season','season_type','week','posteam','down','ydstogo','yardline_100','play_type','pass_attempt','rush_attempt','qb_dropback','sack','two_point_attempt','play_deleted','receiver_player_id','passer_player_id','air_yards','complete_pass','yards_after_catch'];projection=project(b,cols,q/'pbp_context_2026.csv.xz')
b,tm=get('STATS_CURRENT','https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_2026.csv.gz',8*1024*1024);df=pd.read_csv(io.BytesIO(b),compression='gzip',low_memory=False);df=df[(df.season==2026)&(df.season_type=='REG')].copy();df,rejected=quarantine_stat_orphans(df)
# Same factualcolumncontract as baseline; currentyearonly retains no offers.
with __import__('zipfile').ZipFile(root/'artifacts/basic-football-facts-v2.1.zip') as z:old=pd.read_csv(io.BytesIO(z.read('facts.csv.gz')),compression='gzip',low_memory=False)
cols=list(old.columns);assert set(cols)<=set(df);df[cols].to_csv(q/'current_facts_2026.csv.gz',index=False,compression={'method':'gzip','mtime':0});scols=['game_id','season','week','game_type','gameday','gametime','home_team','away_team','home_score','away_score'];g[(g.season==2026)&(g.game_type=='REG')][scols].to_csv(q/'schedule.csv',index=False)
cut=now();manifest={'id':'C-CURRENT-PROFILE-SOURCE-v1','created_UTC':cut,'information_cutoff_UTC':cut,'event':e,'target_week':int(game.week),'roster_source_week':week,'roster_version_qualification':'EXACT_WEEK' if week==int(game.week) else 'PRELIMINARY_PRIOR_WEEK_NOT_CONFIRMED_EVENT_ROSTER','source_observed':{x['id']:x['observed_UTC'] for x in ledger},'sources':[sm,em,rm,pm,tm],'current_PBP_projection':projection,'baseline_ordinary_facts':dict(path='artifacts/basic-football-facts-v2.1.zip',SHA256=hashlib.sha256((root/'artifacts/basic-football-facts-v2.1.zip').read_bytes()).hexdigest()),'quarantined_explicit_zero_orphans':rejected,'future_actuals_required_for_universe':False,'rights':'Ordinarynflversefacts/rosterCCBY4;minimalnativeeventfacts; no odds/NGS/FTN/presentation retained','source_clock_tier':'Actuallyobservedcurrentbytesbeforefuturekickoff;historicalgamefacts stillcurrentvintage; strict+7dayproxyforfeatures'}
(q/'SOURCE_MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n');(q/'ATTRIBUTION.md').write_text('Ordinary roster/player/play facts: nflverse/nflverse-data, CC BY 4.0; schedule: nflverse/nfldata. Native event-status facts: public ESPN scoreboard. Source versions are actually observed now; original historical publication times remain unknown. No odds, presentation, tracking or protected alignment/route data.\n');guard();print('CURRENT_QUERY_READY',game.game_id,week,int(game.week),len(r),flush=True)
