from pathlib import Path
import sys,json,gzip,io,zipfile,hashlib,datetime
import pandas as pd
root=Path('/workspace/ngs-c');sys.path.insert(0,str(root/'src'))
from data_v2 import History,DAY
from receiving_priority_c03 import memberships
from receiving_profiles_c02 import query_universe
from forward_sources_v4 import kickoff_frame,team
source=root/'sources/profile-increment-v2';manifest=json.loads((source/'SOURCE_MANIFEST.json').read_text());cut=manifest['cutoff_UTC'];cutn=pd.Timestamp(cut).timestamp()
roster=json.loads((source/'roster.json').read_text());events=json.loads((source/'events.json').read_text());queries,excluded=query_universe(roster,events,cut)
archive=root/'artifacts/basic-football-facts-v2.1.zip';oldcurrent=root/'sources/player-context-matchup-01/completion-decision-v1/current-query'
with zipfile.ZipFile(archive) as z:old=pd.read_csv(io.BytesIO(z.read('facts.csv.gz')),compression='gzip',low_memory=False);oldg=pd.read_csv(io.BytesIO(z.read('schedule.csv')))
current=pd.read_csv(oldcurrent/'current_facts_2026.csv.gz',low_memory=False);raw=pd.concat([old[(old.season>=2022)&(old.season<=2025)],current[current.season==2026]],ignore_index=True);sch=pd.concat([oldg[oldg.season<2026],pd.read_csv(source/'schedule.csv')],ignore_index=True);sch=kickoff_frame(sch);raw=raw.merge(sch[['game_id','kickoff']],on='game_id',validate='many_to_one');raw=raw[raw.position.isin(['QB','RB','WR','TE'])];raw['available']=raw.kickoff+7*DAY
assert not raw.duplicated(['game_id','player_id']).any();hist=History(raw,'player_id')
# This is the ACTUAL current information cutoff, never the future event time.
cohort_clock=pd.DataFrame([dict(season=2026,week=manifest['target_week'],kickoff=cutn)])
priority=memberships(queries,hist,cohort_clock);prior={r['player_id']:r for r in priority}
profiles_path=root/'reports/player-context-matchup-01/completion-decision-v1/profiles/current-W10/PROFILES.json.gz';oldprofiles=json.loads(gzip.decompress(profiles_path.read_bytes()));byid={r['key']['player_id']:r for r in oldprofiles};rows=[]
for q in queries:
 p=prior[q['player_id']];base=byid.get(q['player_id']);rows.append(dict(player_id=q['player_id'],name=q['name'],game_id=q['game_id'],team=q['team'],opponent=q['opponent_team'],role=q['position'],basic_identity_state='OBSERVED_PRIOR_WEEK_ROSTER;FUTURE_EVENT_EFFECTIVE_NOT_ESTABLISHED',expected_starter='UNKNOWN_NO_QUALIFIED_ROLE_SOURCE',receiving_priority=p['profiling_priority'] if q['position']!='QB' else False,priority_reason=p['priority_reason'] if q['position']!='QB' else 'QB_ROLE_OWNED_BY_B;BASIC_COVERAGE_RETAINED',top20_expected_targets=p['top20_expected_targets'],expected_targets_reference=p['reference_expected_targets'] if q['position']!='QB' else None,reference_fallback=p['reference_fallback'],latest_admitted_game=p['latest_admitted_game'],reference_cutoff=cut,profile_base_id=base['profile_id'] if base else None,profile_base_cutoff=base['key']['information_cutoff_UTC'] if base else None,forecast_admitted=False,offer_eligible=False))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
out={'schema':'C-PLAYER-DEFENSE-ENVELOPE-v2','profile_rows':len(rows),'all_basic_players_retained':True,'target_actuals_required':False,'current_source_cutoff_UTC':cut,'profile_base':{'path':str(profiles_path.relative_to(root)),'SHA256':sha(profiles_path),'original_cutoff_preserved':True,'mandatory_passer_overlay':'reports/player-context-matchup-01/completion-decision-v1/profiles/current-W10/PASSER_ROLE_OVERLAY.json.gz'},'reference_policy':'C-RECENT3-TARGET-WORKLOAD-PRIORITY-v1;currentcutoffcapnotfuturekickoff','source_binding':{'original_facts_archive_SHA256':sha(archive),'prior_observed_current_facts_SHA256':sha(oldcurrent/'current_facts_2026.csv.gz'),'new_roster_manifest_SHA256':sha(source/'SOURCE_MANIFEST.json')},'counts':{'receiving_priority':sum(r['receiving_priority'] for r in rows),'WR_top20':sum(r['top20_expected_targets'] for r in rows if r['role']=='WR'),'TE_top20':sum(r['top20_expected_targets'] for r in rows if r['role']=='TE'),'forecast_admitted':0,'offers':0},'rows':rows,'excluded':excluded,'current_model_packet':'NOT_ISSUED;event-effective rosterandboundcurrentmodelnotadmitted'}
p=root/'reports/profile-increment-v2/CURRENT_BASIC_INDEX.json';p.write_text(json.dumps(out,separators=(',',':'))+'\n');print('CURRENT_BASIC_INDEX',out['profile_rows'],out['counts'])
