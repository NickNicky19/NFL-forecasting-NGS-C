"""Project permitted numerical facts from existing downloads. No NGS is copied."""
from pathlib import Path
import gzip,json,hashlib,zipfile,sys
import pandas as pd
from contracts_v2 import WEIGHTS

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def prepare(source,reference,out,old_runs):
 out.mkdir(parents=True,exist_ok=False); facts=[];manifest=[]
 physical=['attempts','carries','targets','receptions','sacks_suffered','passing_tds','rushing_tds','receiving_tds','passing_2pt_conversions','rushing_2pt_conversions','receiving_2pt_conversions','kickoff_returns','punt_returns','special_teams_tds']
 cols=list(dict.fromkeys(['player_id','player_display_name','position','season','week','season_type','game_id','team','opponent_team']+physical+list(WEIGHTS.keys()-{'offensive_fumble_recovery_td','kick_return_td','punt_return_td','field_goal_return_td'})+['fumble_recovery_tds']))
 for year in range(2022,2027):
  p=source/f'stats_player_week_{year}.csv.gz';d=pd.read_csv(p,low_memory=False);d=d[(d.season_type=='REG')&((d.season!=2026)|(d.week<=7))]
  facts.append(d[cols]);manifest.append(dict(id=f'NFLVERSE-STATS-{year}',url=f'https://github.com/nflverse/nflverse-data/releases/download/stats_player/{p.name}',original_gzip_sha256=sha(p),original_csv_sha256=hashlib.sha256(gzip.decompress(p.read_bytes())).hexdigest(),rows=len(d),retained_fields=cols,rights='ordinary numerical facts and stable identifiers; publisher CC-BY-4.0 attribution; NGS/EPA/CPoE/headshot and other unconsumed fields excluded'))
 data=pd.concat(facts,ignore_index=True);data.to_csv(out/'facts.csv.gz',index=False,compression={'method':'gzip','mtime':0})
 g=pd.read_csv(source/'schedules.csv');g=g[(g.game_type=='REG')&g.season.between(2022,2026)&((g.season!=2026)|(g.week<=7))]
 g[['game_id','season','week','game_type','gameday','gametime','home_team','away_team','home_score','away_score']].to_csv(out/'schedule.csv',index=False)
 # Identity mapping only. Current roster/position/team fields are never used.
 players=pd.read_csv(reference/'dp-ids.csv',low_memory=False,dtype={'sleeper_id':'string','gsis_id':'string'})
 players[['gsis_id','sleeper_id']].dropna().drop_duplicates().to_csv(out/'identity.csv.gz',index=False,compression={'method':'gzip','mtime':0})
 pinfo=[];offers=[]
 for week in range(4,8):
  p=reference/f'archive-w{week:02}.json';j=json.loads(p.read_text());pinfo.append(dict(week=week,raw_sha256=sha(p),source_commit='57269ffc451e81d19ace9fea263c97b6d79b4060',path=f'output/data/archive/2026_w{week:02}.json',observed_archive_saved_at=j['saved_at']))
  for player in j['players']:
   for prop in player.get('props',[]):
    if prop.get('line_from')!='dk' or prop['key'] in ['fpts','anytime_td']:continue
    offers.append(dict(offer_id=f'C-DK-DIAG-W{week}-{player["id"]}-{prop["key"]}',season=2026,week=week,sleeper_id=player['id'],historical_team=player['team'],historical_opponent=player['opp'],native_event_id=player.get('game_id'),category=prop['key'],line=prop['line'],venue='DraftKings recorded attribution',offered_sides='OVER|UNDER',price=None,quote_time_UTC=None,archive_saved_at_UTC=j['saved_at'],evidence_tier='TIMING_UNVERIFIED_LINE_DIAGNOSTIC',settlement_contract='UNKNOWN',entry_eligibility='UNKNOWN'))
 pd.DataFrame(offers).to_csv(out/'offers.csv',index=False)
 manifest.append(dict(id='SITE-DK-FACTS',sources=pinfo,rows=len(offers),rights='C-authored minimal normalized factual lines/IDs, no original code/UI/raw archive copied',timing='Saved archive clock does not prove quote time or earlier availability; postgame clocks retained'))
 manifest.append(dict(id='IDENTITY-FACTS',source='https://raw.githubusercontent.com/dynastyprocess/data/master/files/db_playerids.csv',source_sha256=sha(reference/'dp-ids.csv'),retained='Only stable GSIS/Sleeper identifier pairs; current roster/team/position and name joins excluded'))
 manifest.append(dict(id='SCHEDULE-FACTS',source='https://github.com/nflverse/nfldata',source_sha256=sha(source/'schedules.csv'),retained='Minimal numerical schedule/team/event/date/finality facts; no source code copied',rows=len(g)))
 (out/'manifest.json').write_text(json.dumps(manifest,indent=2));(out/'ATTRIBUTION.md').write_text('Numerical NFL statistics supplied by nflverse/nflverse-data (CC-BY-4.0), generated with nflfastR calculate_stats. Stable GSIS/Sleeper identifier facts from dynastyprocess/data, db_playerids.csv. Minimal schedule facts from nflverse/nfldata. Recorded DraftKings line facts extracted from NickNicky19/nicks-expert-nfl-picks at pinned commit57269ffc451e81d19ace9fea263c97b6d79b4060; timing/settlement unverified. C filtered fields, normalized records and excluded NGS/derived fields. NFL/team/player marks and upstream source rights are not licensed by C. No player pictures, logos or source website code copied.\n')
 (out/'LICENSE-CC-BY-4.0.md').write_bytes((reference/'nflverse-LICENSE.md').read_bytes())
 archive=out.parent/'inputs-v2.zip'
 with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
  for p in out.iterdir():z.write(p,p.name)
 # Preserve exact C0 model bytes and consumed row projection. No NGS availability field.
 old=out.parent/'c0-frozen-v1.zip';c0rows=[];fits=[]
 with zipfile.ZipFile(old,'w',zipfile.ZIP_DEFLATED) as z:
  for run in old_runs:
   for p in run.glob('*.json.gz'):
    for r in json.loads(gzip.decompress(p.read_bytes())):
     if r['arm']=='C0':c0rows.append({k:v for k,v in r.items() if k!='ngs_available'})
   fits += [r for r in json.load(open(run/'fits.json')) if r['slot'].endswith('-C0')]
   for p in (run/'models').glob('*-C0.pkl.gz'):z.write(p,'models/'+p.name)
  z.writestr('rows.json.gz',gzip.compress(json.dumps(c0rows,allow_nan=False,separators=(',',':')).encode(),mtime=0));z.writestr('fits.json',json.dumps(fits));z.writestr('SCOPE.txt','Original C0 points, labels, masks, consumed features and exact model bytes only. Omitted nonconsumed NGS-availability metadata. C1/C2/NGS bytes are not GitHub-qualified. No fits repeated.\n')
 print(json.dumps(dict(inputs_bytes=archive.stat().st_size,inputs_sha256=sha(archive),old_C0_bytes=old.stat().st_size,old_C0_sha256=sha(old),C0_rows=len(c0rows),C0_slots=len(fits))))
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--reference',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--old-runs',nargs='+',type=Path,required=True);a=p.parse_args();prepare(a.source,a.reference,a.output,a.old_runs)
