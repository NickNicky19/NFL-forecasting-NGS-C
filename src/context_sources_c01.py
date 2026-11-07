"""Bounded manual ordinary-PBP projection and context-source inventory.

No JavaScript, collector, credentials or protected charting rows are executed.
"""
import argparse, csv, gzip, hashlib, io, json, re, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'sources/player-context-matchup-01'
REPORT=ROOT/'reports/player-context-matchup-01'
COLS=['game_id','play_id','season','season_type','week','game_date','posteam','defteam','down','ydstogo','yardline_100','qtr','game_seconds_remaining','score_differential','play_type','pass_attempt','rush_attempt','sack','qb_dropback','qb_scramble','qb_kneel','qb_spike','two_point_attempt','play_deleted','penalty','pass_location','air_yards','complete_pass','incomplete_pass','interception','receiver_player_id','passer_player_id','rusher_player_id','receiving_yards','passing_yards','rushing_yards','yards_after_catch','run_location','run_gap','first_down_pass','first_down_rush','pass_touchdown','rush_touchdown']
def now():return datetime.now(timezone.utc).isoformat()
def sha(b):return hashlib.sha256(b).hexdigest()
def pbp_path(season):
 p=OUT/f'pbp_facts_{season}.csv.gz'
 return p if p.exists() else OUT/f'pbp_facts_{season}.csv.xz'
def write(p,x):
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')
def guard():
 from forward_budget_v4 import complete_C_roots,tree_bytes
 total=sum(tree_bytes(p) for p in complete_C_roots([ROOT]))
 if total>2684354560:raise RuntimeError('WHOLE_C_CAP')
 return total
def acquire():
 assert not (OUT/'SOURCE_MANIFEST.json').exists(),'COMPLETED_SOURCE_INTAKE_FROZEN'
 REPORT.mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
 ledger=REPORT/'SOURCE_REQUESTS.json'
 requests=json.loads(ledger.read_text()) if ledger.exists() else []
 def fetch(url,cap=1500000):
  assert len(requests)<28,'SOURCE_HTTP_CAP'
  item=dict(url=url,started_UTC=now());requests.append(item);write(ledger,requests)
  try:
   with urlopen(Request(url,headers={'User-Agent':'Session-C-manual-context-study-v1'}),timeout=35) as f:
    b=f.read(cap+1);assert len(b)<=cap,'SINGLE_RESPONSE_CAP'
    item.update(status=f.status,observed_UTC=now(),bytes=len(b),SHA256=sha(b),headers={k:f.headers.get(k) for k in ['Date','Last-Modified','ETag','Content-Length']})
   assert sum(r.get('bytes',0) for r in requests)<=33554432,'SOURCE_BYTES_CAP'
   write(ledger,requests);return b,item
  except Exception as e:
   item.update(error=str(e),observed_UTC=now());write(ledger,requests);return None,item
 docs={
 'ftn_load':'https://nflreadr.nflverse.com/reference/load_ftn_charting.html',
 'ftn_dictionary':'https://nflreadr.nflverse.com/articles/dictionary_ftn_charting.html',
 'data_schedule':'https://nflreadr.nflverse.com/articles/nflverse_data_schedule.html',
 'ngs_dictionary':'https://nflreadr.nflverse.com/articles/dictionary_nextgen_stats.html',
 'nflverse_license':'https://raw.githubusercontent.com/nflverse/nflverse-data/master/LICENSE',
 'ftn_release':'https://api.github.com/repos/nflverse/nflverse-data/releases/tags/ftn_charting',
 'participation_release':'https://api.github.com/repos/nflverse/nflverse-data/releases/tags/participation'
 }
 documentation={}
 for name,url in docs.items():
  b,m=fetch(url)
  if b is None:documentation[name]=dict(source=m,state='UNAVAILABLE');continue
  s=b.decode('utf-8');s=re.sub(r'<script\b.*?</script>','',s,flags=re.S|re.I);s=re.sub(r'<style\b.*?</style>','',s,flags=re.S|re.I);s=re.sub('<[^>]+>',' ',s);s=re.sub(r'\s+',' ',s)
  if name.endswith('release'):
   x=json.loads(b); snippets=[{k:a.get(k) for k in ['id','name','size','updated_at','digest','browser_download_url']} for a in x.get('assets',[]) if any(y in a['name'] for y in ['2025','2026'])]
   documentation[name]=dict(source=m,release_id=x.get('id'),body=x.get('body','')[:9000],actual_assets=snippets)
  else:
   words=['license','attribution','2022','2023','2024','2025','2026','route','alignment','catchable','participation','season','separation','update','ftn']
   spans=[]
   for word in words:
    for match in list(re.finditer(re.escape(word),s,re.I))[:5]:spans.append(s[max(0,match.start()-100):match.start()+330])
   documentation[name]=dict(source=m,excerpts=spans[:45])
 write(REPORT/'SOURCE_DOCUMENTATION.json',documentation)
 # Immutable existing 2026 source is reused, not relabelled a fresh capture.
 existing=Path('/workspace/c-w8-v9/pbp-2026.raw.gz');b=existing.read_bytes()
 assert sha(b)=='780a9b5fca995c2e86ab1949d6fb8c4c180f708a8ea291bad3378ff5990a7330'
 old=json.loads((ROOT/'sources/nfl-stats-v9/rare-return-TD/EVENT_FACTS.json').read_text())['source']
 sources=[(2026,b,dict(old,reused_existing=True))]
 b,m=fetch('https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_2025.csv.gz',cap=22000000)
 assert b is not None,'PBP2025_UNAVAILABLE'
 assert sha(b)=='2f135887790a013fd004e609e37096bb4816d5cc80b9f19122e1bad478961978','RELEASE_ASSET_CHANGED'
 m.update(asset_id=512957609,asset_updated_UTC='2026-08-13T12:26:09Z',reused_existing=False)
 sources.append((2025,b,m));coverage=[]
 for season,b,source in sources:
  path=OUT/f'pbp_facts_{season}.csv.gz';assert not path.exists(),'IMMUTABLE_PROJECTION_EXISTS'
  buf=io.StringIO();writer=csv.DictWriter(buf,fieldnames=COLS,lineterminator='\n');writer.writeheader()
  counts={};seen=set();missing={c:0 for c in COLS};kept=0;raw_rows=0
  with gzip.open(io.BytesIO(b),'rt') as f:
   r=csv.DictReader(f);assert set(COLS)<=set(r.fieldnames),'SOURCE_SCHEMA_CHANGED'
   for row in r:
    raw_rows+=1
    if row['season_type']!='REG':continue
    if not any(row[c]=='1' for c in ['pass_attempt','rush_attempt','qb_dropback']):continue
    key=(row['game_id'],row['play_id']);assert key not in seen,'DUPLICATE_PLAY';seen.add(key)
    projected={c:row[c] for c in COLS};writer.writerow(projected);kept+=1
    for c,v in projected.items():missing[c]+=v==''
    wk=int(row['week']);x=counts.setdefault(wk,dict(rows=0,games=set(),targets=0));x['rows']+=1;x['games'].add(row['game_id']);x['targets']+=bool(row['receiver_player_id'])
  body=gzip.compress(buf.getvalue().encode(),mtime=0);guard();path.write_bytes(body);guard()
  coverage.append(dict(season=season,source=source,raw_rows=raw_rows,projected_rows=kept,path=str(path.relative_to(ROOT)),bytes=len(body),SHA256=sha(body),missing=missing,weeks={k:dict(v,games=sorted(v['games'])) for k,v in counts.items()}))
 write(OUT/'SOURCE_MANIFEST.json',dict(id='C-PBP-CONTEXT-FACTS-v1',created_UTC=now(),sources=coverage,columns=COLS,rights='Ordinary NFL event/statistical factual projection under existing nflverse CC BY4 attribution; no descriptions, betting data, EPA/CP/CPOE, NGS or protected charting rows retained',availability='Current/revised source reconstruction; game kickoff+7day policy for experiment only, not authenticated historical publication; explicit unknown source clocks not filled',no_alignment_or_routes_claimed=True))
 (OUT/'ATTRIBUTION.md').write_text('NFL play-by-play numerical facts: nflverse/nflverse-data, https://github.com/nflverse/nflverse-data/releases/tag/pbp, CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). C projects identified event/player/context/statistic columns, excludes descriptions and model/market fields, and calculates lagged features. Source observations are current/revised, not authenticated historical vintages. No endorsement is implied. FTN charting, participation and NFL NGS have separate qualifications; this licence does not grant their rights.\n')
 print(json.dumps([dict(season=r['season'],rows=r['projected_rows'],bytes=r['bytes'],weeks=list(r['weeks'])) for r in coverage]))
if __name__=='__main__':acquire()
