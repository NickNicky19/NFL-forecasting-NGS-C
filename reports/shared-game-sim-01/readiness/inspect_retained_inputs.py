"""Bounded source-body inspection only: no model, inference, trajectory or grade."""
import csv,gzip,lzma,zipfile,io,json,hashlib,time
from collections import Counter,defaultdict
from pathlib import Path
START=time.process_time(); WALL=time.monotonic(); ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
PBP=[('sources/player-context-matchup-01/completion-decision-v1/pbp_facts_2024.csv.xz','2e4ce6ad4f0a11bee49c1ecfc4f895e39de0a42566f230b57e00d555afca3a7b'),('sources/player-context-matchup-01/pbp_facts_2025.csv.gz','27828cc322333bd67602aea6df6a032cfb6c74cee34737bbe8b20fe02590dc8f'),('sources/player-context-matchup-01/pbp_facts_2026.csv.gz','36b6f89ea3a17de230d27a3b93c50294cf8febd9d0fd665b14c0eb979fc82e4e')]
def sha(b):return hashlib.sha256(b).hexdigest()
def binding(rel):
 p=ROOT/rel;b=p.read_bytes();return dict(path=rel,bytes=len(b),SHA256=sha(b),body_reopened=True)
records=[]
for rel,expected in PBP:
 p=ROOT/rel;b=p.read_bytes();assert sha(b)==expected
 raw=lzma.decompress(b) if p.suffix=='.xz' else gzip.decompress(b)
 reader=csv.DictReader(io.StringIO(raw.decode()));fields=reader.fieldnames;keys=set();dupes=0;weeks=defaultdict(lambda:dict(rows=0,games=set()));missing=Counter();eligible=0;missingeligible=Counter();component=Counter()
 for r in reader:
  key=(r['game_id'],r['play_id']);dupes+=key in keys;keys.add(key)
  wk=weeks[r['week']];wk['rows']+=1;wk['games'].add(r['game_id'])
  for k in ['posteam','defteam','down','ydstogo','game_seconds_remaining','score_differential','passer_player_id','receiver_player_id','rusher_player_id']:
   missing[k]+=r[k] in ['', 'NA','NaN']
  valid=r['pass_attempt']=='1' and r['sack']!='1' and r['two_point_attempt']!='1' and r['play_deleted']!='1' and r['play_type']!='no_play'
  if valid:
   eligible+=1
   for k in ['passer_player_id','complete_pass','interception','sack','two_point_attempt','play_deleted','receiver_player_id','passing_yards','receiving_yards']:
    missingeligible[k]+=r[k] in ['', 'NA','NaN']
  for k in ['sack','qb_scramble','qb_kneel','pass_touchdown','rush_touchdown']:
   component[k]+=r[k]=='1'
 assert dupes==0
 records.append(dict(**binding(rel),decoded_bytes=len(raw),decoded_SHA256=sha(raw),fields=fields,rows=len(keys),duplicate_game_play=dupes,week_coverage={k:dict(rows=v['rows'],games=len(v['games'])) for k,v in sorted(weeks.items(),key=lambda x:int(x[0]))},all_row_missing=dict(missing),eligible_attempts=eligible,eligible_attempt_missing=dict(missingeligible),observed_component_labels=dict(component),information_tier='EXPLICIT_CURRENT_VINTAGE_CHRONOLOGICAL_RECONSTRUCTION_ONLY',availability='Prior game kickoff +7days strictly before forecast cutoff; registered assumption, not observed historical publication',rights='Existing retained PBP factual subset CC-BY4 attribution; no FTN/NGS requalification or new source access'))
ordinary=[]
ziprel='artifacts/basic-football-facts-v2.1.zip'
with zipfile.ZipFile(ROOT/ziprel) as z:
 assert {'facts.csv.gz','schedule.csv','manifest.json','ATTRIBUTION.md','LICENSE-CC-BY-4.0.md'}<=set(z.namelist())
 raw=gzip.decompress(z.read('facts.csv.gz')); rr=csv.DictReader(io.StringIO(raw.decode()));counts=Counter();games=defaultdict(set);missingqb=Counter();seen=set();dup=0
 for r in rr:
  key=(r['game_id'],r['player_id']);dup+=key in seen;seen.add(key);counts[r['season']]+=1;games[r['season']].add(r['game_id'])
  if r['position']=='QB':
   for k in ['attempts','completions','passing_interceptions']:missingqb[k]+=r[k] in ['', 'NA','NaN']
 assert dup==0
 ordinary.append(dict(**binding(ziprel),members_reopened=z.namelist(),facts_decoded_SHA256=sha(raw),fields=rr.fieldnames,season_rows=dict(counts),season_games={k:len(v) for k,v in games.items()},QB_missing_fields=dict(missingqb),duplicate_player_game=dup,rights='Manifest CC-BY4 ordinary numeric facts/stableIDs with attribution; original NGS/EPA/CPoE/headshots and offers excluded',availability='Retained revised source; earlier-game +7day reconstruction, not original issue clocks'))
rel='sources/category-decision-release-01/current_facts_2026.csv.gz';raw=gzip.decompress((ROOT/rel).read_bytes());rr=csv.DictReader(io.StringIO(raw.decode()));counts=Counter();games=defaultdict(set);seen=set();dup=0
for r in rr:
 key=(r['game_id'],r['player_id']);dup+=key in seen;seen.add(key);counts[r['week']]+=1;games[r['week']].add(r['game_id'])
assert dup==0
ordinary.append(dict(**binding(rel),decoded_SHA256=sha(raw),fields=rr.fieldnames,week_rows=dict(counts),week_games={k:len(v) for k,v in games.items()},duplicate_player_game=dup,rights='Existing ordinary factual source subset; retain attribution and explicit nulls',availability='Observed current/revised file, not authenticated row vintages; use only earlier-origin labels under frozen7day policy'))
schedule=binding('sources/category-decision-release-01/schedule.csv');sr=list(csv.DictReader(io.StringIO((ROOT/schedule['path']).read_text())));schedule.update(fields=list(sr[0]),season_week_games=dict(Counter(r['season']+'W'+r['week'] for r in sr)),target_score_columns='home_score/away_score strictly grading or earlier-training labels; no target-origin predictor')
roster=binding('sources/category-decision-release-01/roster_current_season.json');r=json.loads((ROOT/roster['path']).read_text());roster.update(rows=len(r),fields=sorted(set().union(*(x.keys() for x in r))),status='UNAVAILABLE_AS_AUTHENTICATED_HISTORICAL_ROSTER_OR_INJURY_UNIVERSE',reason='Current-season snapshot lacks per-row observation/effective game clocks; no backward ACT/roster inference. Optional if engine explicitly uses prior-usage pool plus unresolved bucket.')
cache=binding('reports/information-skill-01/execution-authorization-02/pilot/SOURCE_AGGREGATES.json.gz');c=json.loads(gzip.decompress((ROOT/cache['path']).read_bytes()));cache.update(teams=len(c['teams']),qualified_teams=sum(x['qualified'] for x in c['teams']),scope='Existing1327complete/1held all-position attempt-completion-target interface. Reuse qualification, not new model evidence; additional gain/TD/event interfaces still need recipe-specific checks.')
result=dict(id='SHARED-GAME-SIM-01-C-RETAINED-SOURCE-READINESS',state='READY_BOX_SCORE_EARLIER_SOURCE_LAYER;FULL_S_P_PATH_NOT_YET_ADMITTED',no_engine_worker_or_grade=True,source_rows_are_not_target_features=True,pbp=records,ordinary=ordinary,schedule=schedule,roster=roster,qualified_team_cache=cache,source_training_periods='Ordinary2022–2025 and eligible earlier2026; PBP2024–2025+2026W1–8. Parent must freeze exact origin/window and inner training before scores.',usable_development_origins=[4,5,6,7,8,9],origin_limit='AllW4–9 can use earlier2024–25 startup+eligible prior2026; W9 may use only W8 games passing7day rule. No W1–3 comparison fabricated; provider/case bindings not inspected by this worker.',required_external_cells=['Outcome-free provider query bodies/allowlist and W0/W1 source-model/fallback identity from website frame','Exact player/game/team/role/cutoff mapping between nativeGSIS prior facts and canonical website cases','Frozen shared-game box-score component laws/fallback and same-informationD-P; no existing ready shared engine found here','Complete cost/retention and specific runtime authority before any canary/full worker'],component_support={'team_pace_opportunity':'Earlier team PBP counts and game durations available as reconstructed factual inputs; no trained future pace model executed','QB_attempt_sack_scramble_kneel':'Native passer/rusher flags and official counts available; maintain distinct exclusions and explicit unknown','receiver_target_allocation':'Native passer/receiver identities and earlier targets/completions available, qualified aggregate interface retained; route participation/alignment not supplied','completion_interception':'Eligible-attempt labels/official earlier stats available; compatible multinomial outcomes must be registered, not independent contradictory counts','signed_yards':'Passing/receiving/rushing play gains retained; no gain law fitted','coherent_TD':'Pass/rushTD play flags and receiver/rusher IDs plus box labels retained; passTD-receivingTD must share events; unresolved IDs need bucket','compound_yards':'Can derive from future trajectory components once law exists; no independent sum-of-medians','anytime_td':'Derive rushing-or-receivingTD event only if TD mechanism exists; no passingTD inclusion or invented Under offer','nick_chart_ppr_v1':'Exact chart-component/scoring admission required separately; ordinary 2pt/fumbles/returnTD labels exist but no full simulator event recipe established'},not_ready_stateful='Raw state fields exist but no verified possession/clock/down-distance/field/score transition engine or complete duration/state training interface registered. Do not label box-score engine play-by-play.',resource=dict(measured_CPU=time.process_time()-START,measured_wall=time.monotonic()-WALL,conservative_total_charge_CPU=6,cap_CPU=6,known_limits='Measured one bounded stdlib source pass plus conservative preparation/read/serialization; not full assistant orchestration certificate; no old scientific allowance consumed'),new_raw_GETs=0,new_fits=0,new_inference=0,new_trajectories=0,new_grades=0)
assert result['resource']['measured_CPU']<5.5
(OUT/'COMPONENT_INPUT_MANIFEST.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(CPU=result['resource']['measured_CPU'],files=len(records)+len(ordinary)+3,pbp_week_coverage=[x['week_coverage'] for x in records],ordinary_seasons=ordinary[0]['season_rows'])))
