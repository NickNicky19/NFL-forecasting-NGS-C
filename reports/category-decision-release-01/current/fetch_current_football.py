"""Two authorized ordinary-football body reads and exact retained projections.

No fits, inference, source-clock reconstruction or issue. Current sources are
written once under the new wave; the old source snapshots remain unchanged.
"""
from pathlib import Path
from urllib.request import Request
from urllib.error import HTTPError
from urllib.parse import urlsplit
import csv,gzip,hashlib,importlib.util,io,json,lzma,sys,time,resource,zipfile
import pandas as pd
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'src'))
from context_sources_c01 import COLS
from forward_sources_v4 import team,quarantine_stat_orphans
REPORT=Path(__file__).resolve().parent;OUT=ROOT/'sources/category-decision-release-01'
REG=ROOT/'reports/category-decision-release-01/CURRENT_P1_DELIVERY_REGISTRATION.json'
spec=importlib.util.spec_from_file_location('existing_c05_HTTP_helpers',ROOT/'reports/profile-timing-closure-confirm-01/forward-source/acquire_forward_sources_c05.py');h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
def read(p):return json.loads(Path(p).read_text())
def write(p,j):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(j,indent=2,allow_nan=False)+'\n')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def bind(p):return dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,SHA256=sha(p))
def get(key,url):
 reg=read(REG);p=REPORT/'BODY_REQUESTS.json';log=read(p) if p.exists() else [];assert len(log)<2 and key not in {x['id'] for x in log}
 previous=read(REPORT/'SOURCE_RESOURCE.json')['body_bytes'];cap=min(reg['single_body_bytes_max'],reg['source_body_bytes_max_total']-previous-sum(x.get('body_bytes_read',0) for x in log));assert cap>0
 m=dict(id=key,url=url,method='GET',started_UTC=h.now(),state='ATTEMPTING',body_read_bound=cap);log.append(m);write(p,log)
 try:
  with h.OPENER.open(Request(url,headers={'User-Agent':'C06-bounded-current-football','Cache-Control':'no-cache','Accept-Encoding':'identity'}),timeout=45) as response:
   b=response.read(cap);heads={k.lower():v for k,v in response.headers.items()};m.update(state='RECEIVED',HTTP_status=response.status,body_bytes_read=len(b),SHA256=hashlib.sha256(b).hexdigest(),observed_UTC=h.now(),HTTP_Date=heads.get('date'),HTTP_Age=heads.get('age'),HTTP_Last_Modified=heads.get('last-modified'),ETag=heads.get('etag'),Content_Length=heads.get('content-length'),response_final_host=urlsplit(response.geturl()).hostname)
   assert response.status==200 and len(b)<cap,'SOURCE_STATUS_OR_TRUNCATED'
  write(p,log);return b,m
 except Exception as e:
  m.update(state='FAILED',observed_UTC=h.now(),error_type=type(e).__name__,error=str(e));write(p,log);raise

def frame_delta(old,new,keys):
 a=pd.read_csv(old,low_memory=False);b=pd.read_csv(new,low_memory=False)
 assert list(a.columns)==list(b.columns),'PROJECTED_COLUMN_ORDER_CHANGED';assert not a.duplicated(keys).any() and not b.duplicated(keys).any()
 a=a.sort_values(keys).reset_index(drop=True);b=b.sort_values(keys).reset_index(drop=True)
 eq=a.equals(b);same_shape=a.shape==b.shape
 cells=[]
 if same_shape and not eq:
  for col in a:
   hit=~((a[col]==b[col])|(a[col].isna()&b[col].isna()))
   for idx in hit[hit].index[:20]:
    def value(v):return None if pd.isna(v) else v.item() if hasattr(v,'item') else v
    cells.append(dict(identity={k:value(a.loc[idx,k]) for k in keys},field=col,old=value(a.loc[idx,col]),new=value(b.loc[idx,col])))
 return dict(old=bind(old),new=bind(new),old_rows=len(a),new_rows=len(b),same_columns=True,same_shape=same_shape,canonical_frame_equal=eq,byte_equal=old.read_bytes()==new.read_bytes(),old_dtypes={k:str(v) for k,v in a.dtypes.items()},new_dtypes={k:str(v) for k,v in b.dtypes.items()},changed_cell_examples=cells)

def run():
 assert not (OUT/'MODEL_INPUT_MANIFEST.json').exists(),'IMMUTABLE_CURRENT_SOURCE_ALREADY_EXISTS';OUT.mkdir(parents=True,exist_ok=True)
 cpu=time.process_time();wall=time.monotonic();reg=read(REG);a=read(REPORT/'SOURCE_ANALYSIS.json');old=read(ROOT/'sources/profile-closure-next-02/MODEL_INPUT_MANIFEST_V2.json');sources={x['id']:x for x in old['sources']}
 roster=read(REPORT/'roster_current_season.json');write(OUT/'roster_current_season.json',roster)
 for name in ['schedule.csv','candidate_schedule.json']:(OUT/name).write_bytes((ROOT/'sources/profile-closure-next-02'/name).read_bytes())
 b,sm=get('C06_CURRENT_PLAYER_STATS',sources['CURRENT_PLAYER_STATS']['url']);df=pd.read_csv(io.BytesIO(b),compression='gzip',low_memory=False);df=df[(df.season==2026)&(df.season_type=='REG')].copy();df,orphans=quarantine_stat_orphans(df)
 for k in ['team','opponent_team']:df[k]=df[k].map(team)
 with zipfile.ZipFile(ROOT/'artifacts/basic-football-facts-v2.1.zip') as z:cols=pd.read_csv(io.BytesIO(z.read('facts.csv.gz')),compression='gzip',nrows=0).columns.tolist()
 assert set(cols)<=set(df) and not df.duplicated(['game_id','player_id']).any();future={g['game_id'] for g in read(OUT/'candidate_schedule.json')['games']};assert not df.game_id.isin(future).any(),'UNEXPECTED_FUTURE_STATS'
 df[cols].to_csv(OUT/'current_facts_2026.csv.gz',index=False,compression={'method':'gzip','mtime':0});write(REPORT/'CURRENT_FACT_PROJECTION.json',dict(source=sm,rows=len(df),columns=cols,quarantined_stat_orphans=orphans,unknown_not_filled_zero=True))
 b,pm=get('C06_CURRENT_PBP',sources['CURRENT_PBP']['url']);buf=io.StringIO();writer=csv.DictWriter(buf,fieldnames=COLS,lineterminator='\n');writer.writeheader();seen=set();games=set();missing={k:0 for k in COLS};n=0
 with gzip.open(io.BytesIO(b),'rt') as f:
  rr=csv.DictReader(f);assert set(COLS)<=set(rr.fieldnames),'PBP_CONTEXT_SCHEMA'
  for row in rr:
   if row['season_type']!='REG' or not any(row[k]=='1' for k in ['pass_attempt','rush_attempt','qb_dropback']):continue
   assert row['season']=='2026';key=(row['game_id'],row['play_id']);assert key not in seen;seen.add(key);games.add(row['game_id']);n+=1
   x={k:row[k] for k in COLS};x['posteam']=team(x['posteam']) if x['posteam'] else '';x['defteam']=team(x['defteam']) if x['defteam'] else '';writer.writerow(x)
   for k,v in x.items():missing[k]+=v==''
 assert not games.intersection(future),'UNEXPECTED_FUTURE_PLAYS'
 (OUT/'pbp_facts_2026.csv.xz').write_bytes(lzma.compress(buf.getvalue().encode(),preset=6));write(REPORT/'CURRENT_PBP_PROJECTION.json',dict(source=pm,rows=n,games=len(games),columns=COLS,missing=missing,ordinary_proxies_not_alignment_or_routes=True,unknown_not_filled_zero=True))
 comparisons=[frame_delta(ROOT/'sources/profile-closure-next-02/current_facts_2026.csv.gz',OUT/'current_facts_2026.csv.gz',['game_id','player_id']),frame_delta(ROOT/'sources/profile-closure-next-02/pbp_facts_2026.csv.xz',OUT/'pbp_facts_2026.csv.xz',['game_id','play_id'])]
 write(REPORT/'CANONICAL_PROJECTION_COMPARISON.json',dict(id='C06-CURRENT-CANONICAL-PROJECTION-COMPARISON-v1',created_UTC=h.now(),comparisons=comparisons,all_canonical_projections_equal=all(x['canonical_frame_equal'] for x in comparisons),new_fits=0,new_inference=0,source_version_change_is_not_automatically_feature_change=True))
 files=[bind(OUT/n) for n in ['roster_current_season.json','schedule.csv','candidate_schedule.json','current_facts_2026.csv.gz','pbp_facts_2026.csv.xz']]
 manifest=dict(id='C06-CURRENT-INPUT-MANIFEST-v1',created_UTC=h.now(),actual_input_cutoff_UTC=h.now(),target_season=2026,target_week=10,roster_contract=a['roster']['contract'],roster_week=None,roster_source=a['roster']['source'],roster_published_UTC=a['roster']['published_UTC'],source_observed={x['id']:x['observed_UTC'] for x in [a['roster']['source'],sm,pm]},sources=[a['roster']['source'],sm,pm],files=files,old_finality_contract=bind(ROOT/'sources/profile-closure-next-02/completed_game_proof.json'),old_schedule_sources_unchanged=True,current_native_gate='DEFERRED;NO_EVENT_OR_ISSUE_ADMISSION',future_target_outcomes_absent=True,historical_vintage='Current revised football data at actual new observation; seven-day historical timing proxy remains reconstruction.',comparison=bind(REPORT/'CANONICAL_PROJECTION_COMPARISON.json'),source_execution_code=bind(Path(__file__)),rights='CCBY4 ordinary NFLverse factual projection; enough retained bytes to restore all used data; full unused descriptions/provider presentation not retained.')
 write(OUT/'MODEL_INPUT_MANIFEST.json',manifest)
 (OUT/'ATTRIBUTION.md').write_text('Ordinary player/play/roster facts: nflverse/nflverse-data, CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). Schedule: nflverse/nfldata. Only already-approved ordinary factual columns, exact identifiers, nulls and totals are projected. No sportsbook, private NGS/FTN, descriptions or account data. Actual observation/version clocks do not authenticate original historical availability. All old source and forecast snapshots remain unchanged.\n')
 body_used=read(REPORT/'SOURCE_RESOURCE.json')['body_bytes']+sum(x['body_bytes_read'] for x in read(REPORT/'BODY_REQUESTS.json'))
 resources=dict(id='C06-SOURCE-BODY-RESOURCE-v1',upstream_requests_total=5,preHTTP_local_failures=1,reserved_final_native_requests_remaining=1,body_bytes_total=body_used,body_cap_bytes=reg['source_body_bytes_max_total'],CPU_seconds=time.process_time()-cpu,wall_seconds=time.monotonic()-wall,peak_RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,new_fits=0,new_inference_rows=0,retained_source_bytes=sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file()))
 assert body_used<=reg['source_body_bytes_max_total'] and resources['CPU_seconds']<=reg['CPU_seconds_max'] and resources['peak_RSS_bytes']<=reg['RSS_bytes_max'] and resources['retained_source_bytes']<=reg['new_source_retention_bytes_max']
 write(REPORT/'BODY_RESOURCE.json',resources);print(json.dumps({'canonical_equal':[x['canonical_frame_equal'] for x in comparisons],'changed_examples':[len(x['changed_cell_examples']) for x in comparisons],**resources}))
if __name__=='__main__':run()
