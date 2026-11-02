"""Append one source-qualified rare chart outcome; do not change forecasts."""
import copy,json,shutil,time,resource
from pathlib import Path
from collections import Counter
from week8_grading_v9 import ROOT,RUNROOT,read,sha,pack,captures
from forward_sources_v4 import write,stamp
from prospective_v4 import grade_run
from contracts_v2 import WEIGHTS

def build():
    started=time.monotonic();cpu=time.process_time();oldid='C-W8-v9-20261102-002';newid='C-W8-v9-20261102-003';old=RUNROOT/'outcomes'/oldid;new=RUNROOT/'outcomes'/newid
    assert not new.exists(),'IMMUTABLE_OUTCOME_VERSION_EXISTS'
    packet=read(old/'OUTCOMES.json');qual=read(ROOT/'sources/nfl-stats-v9/rare-return-TD/QUALIFICATION.json');event=read(ROOT/'sources/nfl-stats-v9/rare-return-TD/EVENT_FACTS.json')
    # Admit exactly the documented native event/player. No result-based mask.
    assert qual['game_id']=='2026_08_LV_NYJ' and qual['player_id']=='00-0039407' and qual['unique_event_ids']==['1385'] and qual['actual']==6
    assert sum(WEIGHTS[k]*v for k,v in qual['score_components'].items())/50==qual['actual']
    matches=[r for r in packet['outcomes'] if r['game_id']==qual['game_id'] and r['player_id']==qual['player_id'] and r['category']=='fpts'];assert len(matches)==1
    target=matches[0];assert target['appearance']=='PLAYED' and target['actual'] is None and target['chart_state']=='RARE_TD_ATTRIBUTION_UNRESOLVED'
    target.update(actual=qual['actual'],score_components=qual['score_components'],chart_state='SUPPORTED_RARE_RETURN_WITH_NATIVE_PLAY_PROOF',unavailable_reasons=[],unique_event_credits_verified=True,unique_credit_proof=dict(native_player_game_row_unique=True,fumbles_lost='One direct official total; split repeats not added',two_points='Distinct producer statIDs77/75/104; ordinary receptions21/22',rare_TD='One nativekickoffreturnTD1385 exhausts specialTeamsTD1;fumbleRecoveryTDexplicit0',scoring_contract_id='nick-chart-ppr-v1'),observed_UTC=max(target['observed_UTC'],event['source']['observed_UTC']))
    shutil.copytree(old/'evidence',new/'evidence')
    vendor=ROOT/'sources/nfl-stats-v9/producer'
    for name in ['calculate_stats.R','COPYRIGHT','LICENSE-MIT.md','SOURCE_PINS.json','ATTRIBUTION.md','DESCRIPTION']:(new/'evidence'/('producer_'+name)).write_bytes((vendor/name).read_bytes())
    for name in ['EVENT_FACTS.json','QUALIFICATION.json']:(new/'evidence'/('rare_return_'+name)).write_bytes((ROOT/'sources/nfl-stats-v9/rare-return-TD'/name).read_bytes())
    packet.update(version=newid,created_UTC=stamp(),supersedes=oldid,correction_scope='One previouslymissing rare-TD chartactual nowqualified; source-definition evidence also retained; no other actual/forecast changes')
    packet['source_evidence']=[dict(path=str(p.relative_to(new)),SHA256=sha(p),source='NFLVERSE_CCBY4_ORDINARY_FACTS;NFLFASTR_MIT_FIELD_DEFINITIONS;NATIVE_RETURN_EVENT') for p in sorted((new/'evidence').iterdir())]
    for r in packet['outcomes']:
        if r['category']=='fpts' and r['actual'] is not None:r['unique_credit_proof']['definition_reference']='evidence/producer_calculate_stats.R;unchanged inherited/current source definition hashes'
    write(new/'OUTCOMES.json',packet)
    rows,proofs=captures();allgrades=[];files=[]
    for run,proof in proofs:
        output=RUNROOT/'grades'/(newid+'-'+run.name+'.json');gs=grade_run(run,proof,new/'OUTCOMES.json',output);allgrades+=gs;files.append(dict(path=str(output.relative_to(ROOT)),SHA256=sha(output),rows=len(gs)))
    lookup={g['forecast_id']:g for g in allgrades};lookup_out={(r['game_id'],r['player_id'],r['category']):r for r in packet['outcomes']}
    oldrows=json.loads(__import__('gzip').decompress((ROOT/'reports/week8-v9/runs'/oldid/'GRADED_FORECAST_ROWS.json.gz').read_bytes()));newrows=copy.deepcopy(oldrows);changed=[]
    for r in newrows:
        before=copy.deepcopy(r);g=lookup[r['forecast_id']];a=lookup_out.get((r['game_id'],r['player_id'],r['category']))
        for k in ['state','actual','absolute_error','median_error','mean_squared_error','CRPS','NLL']:r[k]=g.get(k)
        if a:r.update(outcome_observed_UTC=a['observed_UTC'],outcome_reasons=a['unavailable_reasons'],chart_state=a['chart_state'])
        r['grade_version']=newid
        if any(before.get(k)!=r.get(k) for k in ['state','actual','absolute_error','mean_squared_error','CRPS','NLL']):changed.append(r['forecast_id'])
    assert len(changed)==1
    dest=ROOT/'reports/week8-v9/runs'/newid;pack(dest/'GRADED_FORECAST_ROWS.json.gz',newrows)
    status=read(ROOT/'reports/week8-v9/runs'/oldid/'STATUS_CHECK.json');write(dest/'STATUS_CHECK.json',status|dict(id=newid,unchanged_status_source_clock=True))
    write(dest/'GRADING_RUN.json',dict(id=newid,created_UTC=stamp(),original_rows=len(rows),outcome_rows=len(packet['outcomes']),grade_rows=len(newrows),states=dict(Counter(r['state'] for r in newrows)),qualified_final_games=12,pending_games=1,grade_files=files,outcome_packet=str((new/'OUTCOMES.json').relative_to(ROOT)),outcome_SHA256=sha(new/'OUTCOMES.json'),new_NFL_fits=0,CPU_seconds=time.process_time()-cpu,wall_seconds=time.monotonic()-started,peak_RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024))
    write(ROOT/'reports/week8-v9/CORRECTION_V9_3.json',dict(id='C-W8-GRADE-QUALIFICATION-v9.3',supersedes=oldid,new_version=newid,changed_forecast_ids=changed,reason='Native kickoff-returnTD1385 corroborates one broadSpecialTeamsTD; exactnickchart score6,AnytimeTD remains0',original_forecasts_unchanged=True,other_actuals_unchanged=True,new_fits=0))
    print(read(dest/'GRADING_RUN.json'))

if __name__=='__main__':build()
