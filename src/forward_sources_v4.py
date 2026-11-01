"""Bounded on-demand factual source qualification for future C forecasts.

Source HTML/scripts, tracking, pictures, articles and sportsbook data are absent.
"""
import argparse,gzip,hashlib,io,json,math
from datetime import datetime,timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.request import Request,urlopen
import pandas as pd

UTC=timezone.utc
ALIASES={'LAR':'LA','WSH':'WAS','JAC':'JAX','LVR':'LV','AZ':'ARI'}
def now():return datetime.now(UTC)
def stamp(t=None):return (t or now()).isoformat()
def digest(b):return hashlib.sha256(b).hexdigest()
def team(x):return ALIASES.get(str(x),str(x))
def native(x):
    if pd.isna(x):return None
    s=str(x)
    return str(int(s[:-2])) if s.endswith('.0') and s[:-2].isdigit() else s
def records(frame):return frame.astype(object).where(pd.notna(frame),None).to_dict('records')
def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as f:json.dump(value,f,separators=(',',':'),allow_nan=False)

class Retriever:
    def __init__(self,cache,limit=14):self.cache=cache;cache.mkdir(parents=True,exist_ok=False);self.manifest=[];self.limit=limit
    def fetch(self,key,url):
        if len(self.manifest)>=self.limit:raise RuntimeError('SOURCE_HTTP_CAP')
        started=stamp();request=Request(url,headers={'User-Agent':'Session-C-manual-pregame-v4','Accept-Encoding':'identity','Cache-Control':'no-cache'})
        with urlopen(request,timeout=30) as r:
            body=r.read(16*1024*1024+1);assert len(body)<=16*1024*1024
            headers={k.lower():v for k,v in r.headers.items()};status=r.status
        observed=stamp();(self.cache/(key+'.raw')).write_bytes(body)
        item=dict(id=key,url=url,started_UTC=started,observed_UTC=observed,HTTP_status=status,HTTP_Date=headers.get('date'),HTTP_Age=headers.get('age'),HTTP_Last_Modified=headers.get('last-modified'),bytes=len(body),raw_SHA256=digest(body),raw_retention='Temporaryonly; publicsnapshot retains consumed factualprojection, not upstream presentation')
        self.manifest.append(item);return body,item

def kickoff_frame(g):
    g=g.copy();g['kickoff']=pd.to_datetime(g.gameday+' '+g.gametime).dt.tz_localize('America/New_York').dt.tz_convert('UTC').astype('int64')/1e9
    return g

def scoreboard_projection(payload,source,observed):
    result=[]
    for e in payload.get('events',[]):
        c=e['competitions'][0];teams={p['homeAway']:team(p['team']['abbreviation']) for p in c['competitors']};s=e['status']['type'];kick=pd.Timestamp(e['date']).timestamp()
        assert str(c['id'])==str(e['id']),'COMPETITION_EVENT_ID_CONFLICT'
        cs=c.get('status',{}).get('type')
        if cs:assert all(cs[k]==s[k] for k in ['state','name','completed']),'COMPETITION_EVENT_STATE_CONFLICT'
        result.append(dict(espn_event_id=str(e['id']),competition_id=str(c['id']),competition_state_agreement=bool(cs) if cs else 'NOT_SEPARATELY_PROVIDED',week=int(e.get('week',payload.get('week',{}))['number']),kickoff_UTC=pd.Timestamp(kick,unit='s',tz='UTC').isoformat(),kickoff=kick,home_team=teams['home'],away_team=teams['away'],season=int(e['season']['year']),season_type=int(e['season']['type']),state=s['state'],status_name=s['name'],completed=bool(s['completed']),observed_UTC=observed,source_id=source))
    return result

def match_event(row,event,cutoff):
    assert native(row['espn'])==event['espn_event_id'],'NATIVE_EVENT_ID_MISMATCH'
    assert team(row['home_team'])==event['home_team'] and team(row['away_team'])==event['away_team'],'EVENT_TEAMS_MISMATCH'
    assert abs(float(row['kickoff'])-event['kickoff'])<1,'EVENT_KICKOFF_MISMATCH'
    assert int(row['season'])==event['season'] and int(row['week'])==event['week'] and event['season_type']==2,'EVENT_SEASON_WEEK_MISMATCH'
    return event['state']=='pre' and event['status_name']=='STATUS_SCHEDULED' and not event['completed'] and event['kickoff']>cutoff

def acquire(season,week,out,cache,historical):
    if out.exists():raise FileExistsError('Immutable snapshot destination already exists')
    out.mkdir(parents=True);retriever=Retriever(cache);cutoff=now().timestamp()
    b,gm=retriever.fetch('schedule','https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv');full=pd.read_csv(io.BytesIO(b),low_memory=False);full=full[(full.game_type=='REG')&full.season.between(2022,season)].copy();full=kickoff_frame(full)
    future=full[(full.season==season)&(full.week==week)&(full.kickoff>cutoff+300)]
    if future.empty:raise RuntimeError('NO_FUTURE_SCHEDULE_CANDIDATES')
    recent=full[(full.season==season)&(full.kickoff<cutoff)&(full.kickoff>=cutoff-7*86400)&full.home_score.notna()&full.away_score.notna()]
    dates=sorted(set(future.gameday)|set(recent.gameday));events=[]
    for day in dates:
        key='status_'+day.replace('-','');b,m=retriever.fetch(key,'https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates='+day.replace('-','')+'&limit=100');events+=scoreboard_projection(json.loads(b),key,m['observed_UTC'])
    eventmap={e['espn_event_id']:e for e in events};upcoming=[];excluded=[]
    for r in future.to_dict('records'):
        e=eventmap.get(native(r['espn']))
        if e is None:excluded.append(dict(game_id=r['game_id'],reason='NO_CURRENT_EXPLICIT_STATUS'));continue
        if not match_event(r,e,cutoff):excluded.append(dict(game_id=r['game_id'],reason='NOT_VERIFIED_PREGAME'));continue
        item={k:r.get(k) for k in ['game_id','season','week','home_team','away_team','gameday','gametime','home_rest','away_rest','stadium','roof']};item={k:(None if pd.isna(v) else v) for k,v in item.items()}
        item.update(e);item['event_version']=digest(json.dumps({k:item[k] for k in ['game_id','espn_event_id','kickoff_UTC','state']},sort_keys=True).encode());upcoming.append(item)
    if not upcoming:raise RuntimeError('NO_VERIFIED_UNPLAYED_EVENTS')
    completed=[]
    for r in full[full.kickoff<cutoff].to_dict('records'):
        if pd.isna(r['home_score']) or pd.isna(r['away_score']):continue
        if r['kickoff']<=cutoff-7*86400:completed.append(r['game_id']);continue
        e=eventmap.get(native(r['espn']))
        if e and e['state']=='post' and e['completed'] and abs(e['kickoff']-r['kickoff'])<1 and e['home_team']==team(r['home_team']) and e['away_team']==team(r['away_team']):completed.append(r['game_id'])
    urls={'roster':f'https://github.com/nflverse/nflverse-data/releases/download/weekly_rosters/roster_weekly_{season}.csv.gz','injuries':f'https://github.com/nflverse/nflverse-data/releases/download/injuries/injuries_{season}.csv.gz','stats':f'https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_{season}.csv.gz'}
    tables={}
    for key,url in urls.items():
        b,m=retriever.fetch(key,url);tables[key]=pd.read_csv(io.BytesIO(b),compression='gzip',low_memory=False)
        if key in ['roster','injuries']:
            if not m['HTTP_Last_Modified']:raise RuntimeError('UNKNOWN_'+key.upper()+'_PUBLICATION_FRESHNESS')
            age=(now()-parsedate_to_datetime(m['HTTP_Last_Modified'])).total_seconds()
            if age<0 or age>36*3600:raise RuntimeError('STALE_OR_FUTURE_'+key.upper())
    roster=tables['roster'];roster=roster[(roster.season==season)&(roster.week==week)&roster.position.isin(['QB','RB','WR','TE'])].copy()
    rcols=['season','week','team','gsis_id','full_name','position','status','depth_chart_position'];roster=roster[rcols];roster['team']=roster.team.map(team)
    bad=roster.gsis_id.isna()|~roster.gsis_id.fillna('').str.fullmatch(r'00-\d{7}')
    rejected=records(roster[bad]);roster=roster[~bad]
    if roster.duplicated(['gsis_id'],keep=False).any():raise RuntimeError('AMBIGUOUS_CURRENT_ROSTER_ID')
    allowed={t for e in upcoming for t in [e['home_team'],e['away_team']]};eligible=roster[roster.team.isin(allowed)]
    injuries=tables['injuries'];injuries=injuries[(injuries.season==season)&(injuries.week==week)]
    icols=['season','week','team','gsis_id','position','report_status','practice_status'];injuries=injuries[icols].copy();injuries['team']=injuries.team.map(team)
    if injuries.dropna(subset=['gsis_id']).duplicated(['gsis_id','team'],keep=False).any():raise RuntimeError('AMBIGUOUS_CURRENT_INJURY_ID')
    # Replace current-season history with a minimal, completed-only factual projection.
    old=pd.read_csv(historical/'facts.csv.gz',low_memory=False);cols=list(old.columns)
    current=tables['stats'];current=current[(current.season==season)&(current.season_type=='REG')&current.game_id.isin(completed)]
    assert set(cols)<=set(current),'CURRENT_STAT_SCHEMA_CHANGED'
    facts=pd.concat([old[old.season<season],current[cols]],ignore_index=True)
    assert not facts.duplicated(['game_id','player_id']).any()
    facts.to_csv(out/'facts.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    scols=['game_id','season','week','game_type','gameday','gametime','home_team','away_team','home_score','away_score'];full[scols].to_csv(out/'schedule.csv',index=False)
    write(out/'events.json',upcoming);write(out/'roster.json',records(eligible));write(out/'injuries.json',records(injuries));write(out/'status_facts.json',events)
    source_observed={m['id']:m['observed_UTC'] for m in retriever.manifest}
    coverage={t:int(((eligible.team==t)&(eligible.status=='ACT')).sum()) for t in sorted(allowed)}
    manifest=dict(id='C-CURRENT-SOURCE-SNAPSHOT-v4',season=season,week=week,created_UTC=stamp(),sources=retriever.manifest,completed_game_ids=completed,events=len(upcoming),offense_roster_rows=len(eligible),active_roster_rows=int((eligible.status=='ACT').sum()),active_team_coverage=coverage,missing_team_coverage=[t for t,n in coverage.items() if not n],invalid_native_roster_rows=len(rejected),invalid_roster_reasons=[dict(reason='MISSING_OR_INVALID_GSIS',position=r['position'],team=r['team']) for r in rejected],excluded_events=excluded,source_observed=source_observed,history_original='GitHub-qualified basic-football-facts-v2.1, older seasons retained unchanged',current_stat_rows=len(current),future_stat_rows_ignored=int(((tables['stats'].season==season)&~tables['stats'].game_id.isin(completed)).sum()),rights='Minimal factual roster/status/designation/statistical projection with nflverseCCBY4attribution. No upstream pictures/biographies/articles/NGS/EPA/CPOE/marketpayload. Rawfullresponses temporaryonly.',future_actuals_required=False)
    (out/'ATTRIBUTION.md').write_text('NFL numerical statistics, weekly roster and public report-designation facts: nflverse/nflverse-data (publisher CC-BY-4.0). Schedule/native event facts: nflverse/nfldata. Explicit current event state facts: public ESPN scoreboard, with exact native event IDs; presentation/media/articles are excluded. Captured before the listed future games. Original publication/revision clocks remain separately recorded or unknown. Missing news is not healthy. No source scripts executed.\n')
    (out/'LICENSE-CC-BY-4.0.md').write_bytes((historical/'LICENSE-CC-BY-4.0.md').read_bytes())
    manifest['files']={p.name:dict(bytes=p.stat().st_size,SHA256=digest(p.read_bytes())) for p in out.iterdir() if p.is_file()}
    write(out/'SOURCE_MANIFEST.json',manifest)
    print(json.dumps({k:manifest[k] for k in ['created_UTC','events','offense_roster_rows','active_roster_rows','current_stat_rows','future_stat_rows_ignored','invalid_native_roster_rows']}));return manifest

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--season',type=int,required=True);p.add_argument('--week',type=int,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--temporary-raw',type=Path,required=True);p.add_argument('--historical',type=Path,required=True);a=p.parse_args();acquire(a.season,a.week,a.output,a.temporary_raw,a.historical)
