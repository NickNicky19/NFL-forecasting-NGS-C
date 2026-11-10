"""Independent C04 clock/membership/candidate-source checks; no fits or GETs."""
import collections,copy,gzip,hashlib,importlib.util,json,lzma,math,resource,signal,sys,time
from pathlib import Path
from types import SimpleNamespace
START=time.process_time();ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'src'))
import numpy as np,pandas as pd
from data_v2 import load,DAY
import receiving_timing_c04 as t
import receiving_current_capture_c04 as c
signal.signal(signal.SIGPROF,lambda *_:(_ for _ in()).throw(RuntimeError('120CPUcap')))
signal.setitimer(signal.ITIMER_PROF,120)
OUT=ROOT/'reports/profile-closure-next-02/verification';OUT.mkdir(parents=True,exist_ok=True)
BASE=ROOT/'reports/profile-closure-next-02'
def read(p):
 p=Path(p);b=p.read_bytes();return json.loads(lzma.decompress(b)if p.suffix=='.xz'else gzip.decompress(b)if p.suffix=='.gz'else b)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,d):p.write_text(json.dumps(d,separators=(',',':'))+'\n')

def row(game,kick,value):return dict(game_id=game,kickoff=kick,available=kick+7*DAY,player_id='00-0000001',team='ATL',position='WR',values={'rec':value},attempts=0,carries=0,targets=3)
def own(game,kick):return dict(game_id=game,kickoff=kick,available=kick+7*DAY,player_id='00-0000001',team='ATL',team_complete=True,receptions_match=True,targets=3,attempts=30,completions=2,depth_n=np.array([0,3,0,0,0]),down_n=np.array([3,0,0,0,0]),air_n=3,air_sum=12,yac_n=2,yac_sum=8,short=0,redzone=0)
class Defense:
 def __init__(self,rows):self.rows=rows;self.groups={'CAR':rows};self._league_cache={}
 def before(self,team,cut,n=8):return sorted([r for r in self.groups.get(team,[])if r['available']<cut and r['kickoff']<cut],key=lambda r:(r['kickoff'],r['game_id']))[-n:]
 def _summary(self,*_):raise AssertionError('Old residual/value path called')
rr=[row('OLD',0,2),row('NEW',4*DAY,5)]
hist=SimpleNamespace(groups={'00-0000001':rr})
teamrows=[dict(game_id=r['game_id'],kickoff=r['kickoff'],available=r['available'],team='ATL',attempts=30,carries=20,sacks_suffered=2)for r in rr]
teams=SimpleNamespace(groups={'ATL':teamrows})
ctx=SimpleNamespace(raw_player_games=[own('OLD',0),own('NEW',4*DAY)])
defense=Defense([dict(game_id=r['game_id'],kickoff=r['kickoff'],available=r['available'],defense='CAR',cells=np.ones((4,5,6)))for r in rr])
p7=t.TimedInputs(rr,hist,teams,ctx,defense,7);p1=t.TimedInputs(rr,hist,teams,ctx,defense,1)
q=dict(game_id='QUERY',player_id='00-0000001',position='WR',team='ATL',opponent_team='CAR',home_team='ATL',kickoff=10*DAY)
a=p7.features(q);b=p1.features(q);cap=p1.features(q,information_cutoff=3*DAY)
assert a['BASE'][0]==2 and b['BASE'][0]==3.5 and cap['BASE'][0]==2
assert (a['own'][0],b['own'][0],cap['own'][0])==(1,2,1)
assert (a['defense_support'][0],b['defense_support'][0],cap['defense_support'][0])==(1,2,1)
assert len(a['SUPPORT'])==41 and len(b['PROFILE'])==58
assert [r['game_id']for r in p1.pool if r['available']<5*DAY]==['OLD']
assert [r['game_id']for r in p1.pool if r['available']<5*DAY+1]==['OLD','NEW']
before=copy.deepcopy(b);future=t.retime_proxy_record(row('QUERY',10*DAY,9999),1)
p1.hist.groups[q['player_id']].append(future)
mutated=p1.features(dict(q,actual=9999,values={'rec':9999},played=True,targets=9999))
assert all(np.array_equal(before[k],mutated[k],equal_nan=True)for k in before)
rejects=0
for v in [None,float('nan'),float('inf'),2*DAY]:
 try:t.retime_proxy_record(dict(rr[0],available=v),1)
 except ValueError:rejects+=1
 else:raise AssertionError('Unknown/inconsistent clock repaired')
missing=dict(rr[0]);missing.pop('available')
try:t.retime_proxy_record(missing,1)
except ValueError:rejects+=1
assert rejects==5 and rr[1]['available']==11*DAY

# Rebuild only ordinary temporal masks, not old PBP or fitted feature matrices.
inp=Path('/workspace/c-v2/corrected-inputs');late=ROOT/'prospective/runs/C-FWD-v4-20261105-W09-JAXBAL-remainder/sources'
d,g,_=load(inp);dd,gg,_=load(late)
d=pd.concat([d,dd[(dd.season==2026)&(dd.week==8)]],ignore_index=True)
g=pd.concat([g[~((g.season==2026)&(g.week==8))],gg[(gg.season==2026)&(gg.week==8)]],ignore_index=True)
pool=d[d.position.isin(['RB','WR','TE'])].to_dict('records');proof=read(BASE/'timing/SEVEN_DAY_REUSE_PARITY.json')
assert len(pool)==proof['raw_query_rows'] and len(proof['old_fit_contracts'])==32
assert all(r['available']==r['kickoff']+7*DAY for r in pool)
origins=[]
for y in [2025,2026]:
 for week in range(1,9):
  cut=float(g[(g.season==y)&(g.week==week)].kickoff.min())
  seven=[r for r in pool if r['available']<cut and r['values']['rec']is not None]
  one=[r for r in pool if r['kickoff']+DAY<cut and r['values']['rec']is not None]
  members=[(r['game_id'],r['player_id'])for r in seven];mh=hashlib.sha256(json.dumps(members,separators=(',',':')).encode()).hexdigest()
  assert set(members)<={(r['game_id'],r['player_id'])for r in one}
  for old in proof['old_fit_contracts']:
   if old['origin']!=f'{y}-W{week:02}':continue
   payload=read(ROOT/old['path'])
   assert sha(ROOT/old['path'])==old['SHA256']and payload['fingerprint']==old['fingerprint']and payload['membership_SHA256']==mh==old['membership_SHA256']and payload['training_rows']==len(seven)
  origins.append(dict(season=y,week=week,seven_day_labels=len(seven),one_day_labels=len(one),additional_labels=len(one)-len(seven)))
 frozen=read(ROOT/f'artifacts/profile-increment-v2/NUMERICAL_ROWS-{y}.json.xz')
 assert {(r['game_id'],r['player_id'],r['actual'])for r in frozen}=={(r['game_id'],r['player_id'],r['values']['rec'])for r in pool if r['season']==y and 1<=r['week']<=8}
spec=importlib.util.spec_from_file_location('supported_c04_route',BASE/'timing/run_preserving_diagnostics.py');wrapper=importlib.util.module_from_spec(spec);spec.loader.exec_module(wrapper)
assert not t.REG.exists()and wrapper.REGISTRATION.is_file()
assert sha(ROOT/'src/receiving_timing_c04.py')==read(BASE/'timing/DEFAULT_ROUTE_CORRECTION.json')['frozen_core']['SHA256']
timing=dict(id='C04-INDEPENDENT-CLOCK-PATH-v1',status='PASS_WITH_RECONSTRUCTION_TIER',new_fits=0,network=0,unknown_or_inconsistent_clock_rejections=rejects,training_labels_features_query_support_aligned=True,actual_input_cutoff_caps_future_query=True,future_or_target_mutation_invariant=True,old_residual_value_path_unavailable=True,separate_support_profile_dimensions=[41,58],original_7day_proxy_unmodified=True,old_model_contracts_and_memberships_verified=32,fixed_2025_2026_query_identity_labels_exact=True,origin_label_counts=origins,default_core_path_defect='Containedbyvalidatedsupportedwrapper;explicitpilotregistrationvalid;frozencoreunchanged',limits='1day is a reconstruction assumption,not authenticated publication. Prior PBP semantics reused,not re-audited;full feature-matrix parity receipt is producer evidence,not independently rerun here.',source_sha256=sha(ROOT/'src/receiving_timing_c04.py'))
write(OUT/'TIMING_PATH_REVIEW.json',timing)

source=ROOT/'sources/profile-closure-next-02';manifest=read(source/'MODEL_INPUT_MANIFEST.json');cut=c.timestamp(manifest['actual_input_cutoff_UTC']);m=c.validate_inputs(source,cut+1)
for f in manifest['files']:
 p=ROOT/f['path'];assert p.stat().st_size==f['bytes']and sha(p)==f['SHA256']
roster=read(source/'roster_current_season.json');games=read(source/'candidate_schedule.json')['games'];basic,queries=c.query_universe(roster,games,2026)
teamset={x for g in games for x in [g['home_team'],g['away_team']]}
valid=lambda r:bool(__import__('re').fullmatch(r'00-\d{7}',str(r.get('gsis_id'))))
want=[r for r in roster if r['position']in['RB','WR','TE']and r['status']=='ACT'and valid(r)and r['team']in teamset and r['season']==2026]
assert len(basic)==len(roster)==959 and len(games)==14 and len(queries)==len(want)==364
assert {(r['player_id'],r['team'])for r in queries}=={(r['gsis_id'],r['team'])for r in want}
assert all(r['roster_week']is None and not any(k in r for k in ['actual','values','played','available'])for r in queries)
assert all(r['week']==10 and r['game_id']in {g['game_id']for g in games}for r in queries)
changed=[dict(r,actual=9999,played=True,targets=9999,week=999)for r in roster]
assert c.query_universe(changed,games,2026)==(basic,queries)
facts=pd.read_csv(source/'current_facts_2026.csv.gz',low_memory=False);schedule=pd.read_csv(source/'schedule.csv')
assert len(facts)==9455 and facts.game_id.nunique()==136 and facts.week.max()==9 and not facts.duplicated(['game_id','player_id']).any()
joined=facts[['game_id']].merge(schedule[['game_id','home_score','away_score']],on='game_id',validate='many_to_one')
assert joined.home_score.notna().all()and joined.away_score.notna().all()and not set(facts.game_id)&{g['game_id']for g in games}
accepted,held=c.qualified_events(games,[],cut+1);assert not accepted and len(held)==14
qualification=read(BASE/'current-source/ROSTER_QUALIFICATION.json')
assert qualification['projection_week']is None and qualification['source_full_header'].startswith('Notretained')
current=dict(id='C04-INDEPENDENT-CURRENT-SOURCE-v1',status='CANDIDATE_SOURCE_AND_UNIVERSE_PASS_NATIVE_ISSUANCE_REVIEW_PENDING',new_fits=0,network=0,source_files_hash_verified=len(manifest['files']),actual_source_cutoff=manifest['actual_input_cutoff_UTC'],source_roster_contract=m['roster_contract'],roster_basic_records=len(basic),receiving_ACT_queries=len(queries),tentative_games=len(games),no_native_status_acceptance_without_events=True,target_stat_rows_absent=True,query_target_outcome_mutation_invariant=True,projection_week=None,upstream_week_column_presence='UNKNOWN_NOT_RETAINED_NOT_USED',future_gameday_health_starter='UNKNOWN_NOT_INFERRED',source_revision_age_at_observation_seconds=qualification['source_revision_age_seconds_at_observation'],old_weekly9_vs10_hold='Unchanged',limits='Current-known season-roster candidates only,conditional on appearance. Fresh native event/source/cache/manifest proof still required before issuance;no finalstatusGET performed.',current_capture_code_sha256=sha(ROOT/'src/receiving_current_capture_c04.py'),CPU_seconds=time.process_time()-START,peak_RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,threads=1)
assert current['CPU_seconds']<120 and current['peak_RSS_bytes']<=805306368
write(OUT/'CURRENT_SOURCE_REVIEW.json',current)
print(json.dumps(dict(timing_status=timing['status'],model_contracts=32,current_status=current['status'],basic=len(basic),queries=len(queries),CPU_seconds=current['CPU_seconds'],peak_RSS_bytes=current['peak_RSS_bytes'])))
