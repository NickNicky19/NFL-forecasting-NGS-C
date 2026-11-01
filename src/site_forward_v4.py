"""Project verified immutable future captures to a static site; never fits."""
import argparse,hashlib,json
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
import pandas as pd
from contracts_v2 import CATEGORIES
from prospective_v4 import read_json,validate_run,validate_receipt
from safe_models_v4 import law_load
from coherence_v4 import state_for

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,j):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(j,separators=(',',':'),allow_nan=False))
def display_and_primary(rows):
    latest={};first={}
    for r in rows:
        key=(r['game_id'],r['player_id'],r['category'],r['policy_id']);order=(pd.Timestamp(r['server_persisted_UTC']),r['forecast_id'])
        if key not in first or order<first[key][0]:first[key]=(order,r['forecast_id'],r['server_persisted_UTC'])
        if key not in latest or order>latest[key][0]:latest[key]=(order,r)
    for key,(_,r) in latest.items():
        r['primary_scoring_forecast_id']=first[key][1];r['primary_scoring_server_UTC']=first[key][2];r['primary_scoring_snapshot']=r['forecast_id']==first[key][1]
    return {key:r for key,(_,r) in latest.items()}
def consumed(r):
    f=r['features'];out={'own_outcome_mean_last3':f[0],'own_outcome_supported_last3':f[1],'own_outcome_mean_last8':f[2],'own_outcome_supported_last8':f[3]}
    if len(f)>=32:out.update(player_attempts_mean_last3=f[20],player_carries_mean_last3=f[23],player_targets_mean_last3=f[26],team_attempts_mean_last3=f[29],team_carries_mean_last3=f[30],team_sacks_mean_last3=f[31])
    if len(f)>=35:out.update(home_indicator=f[32],week=f[33],team_rest_days=f[34])
    if len(f)>=41:out.update(opponent_allowed_passing_yards_per_attempt=f[35],opponent_pass_attempt_support=f[36],opponent_allowed_rushing_yards_per_carry=f[37],opponent_carry_support=f[38],opponent_allowed_receiving_yards_per_target=f[39],opponent_target_support=f[40])
    return out

def build(root,docs):
    captures=[];runs=[]
    for receipt_path in sorted((root/'receipts').glob('*.json')):
        proof=read_json(receipt_path);run=root/'runs'/proof['run_id'];m,rows=validate_run(run);persisted=validate_receipt(run,proof,m,rows)
        source=read_json(run/'sources/SOURCE_MANIFEST.json');status=read_json(run/'status_before_persistence.json')
        status_at=max(s['observed_UTC'] for s in status['sources']);source_at=max(s['observed_UTC'] for s in source['sources'])
        for r in rows:
            keys=['forecast_id','run_id','game_id','event_version','espn_event_id','player_id','name','position','team','opponent_team','season','week','category','kickoff_UTC','availability','practice_status','selection_availability','family','arm','model_id','model_SHA256','policy_id','information_cutoff_UTC','generated_UTC','product_type','mean','median','p05','p95','event_probability','scoring_contract_id','appearance_conditioning','history_support','sparse_player','model_fallback','readiness','limitation']
            captures.append({k:r[k] for k in keys}|dict(source_stat_rows=r.get('historical_stat_row_support',r['history_support']),target_history_support=int(r['features'][3]),target_sparse=int(r['features'][3])<3,support_metadata_correction='C-SUPPORT-DEFINITION-CLARIFICATION-v4.4',server_persisted_UTC=proof['server_check_completed_UTC'],source_snapshot_observed_UTC=source_at,status_observed_UTC=status_at,evidence_tier='GITHUB_SERVER_VERIFIED_PREGAME',primary_scoring_snapshot=True,prop_state='Forecast only—prop line unavailable',line=None,venue=None,product=None,offer_observed_UTC=None,p_under=None,p_push=None,p_over=None,selected_side=None,selection_state='NO_QUALIFIED_CURRENT_OFFER',outcome_state='PENDING',actual=None,consumed_inputs=consumed(r),coherence_state='INDEPENDENT_MARGINALS_NOT_JOINTLY_VALIDATED',forecast_evidence_URL='https://github.com/NickNicky19/NFL-forecasting-NGS-C/blob/'+proof['capture_commit']+'/prospective/runs/'+proof['run_id']+'/RUN.json',server_receipt_URL=proof['server_run_URL']))
        runs.append(dict(run_id=m['run_id'],rows=len(rows),source_manifest_SHA256=m['source_manifest_SHA256'],capture_commit=proof['capture_commit'],server_persisted_UTC=proof['server_check_completed_UTC'],first_kickoff_UTC=m['first_kickoff_UTC'],earliest_lead_seconds=proof['earliest_actual_lead_seconds'],new_fits=m['new_fits']))
    selected=display_and_primary(captures);rows=list(selected.values());assert rows and not any('law' in r or r['actual'] is not None for r in rows)
    passing={}
    for r in rows:
        if r['category'] in ['pass_cmp','pass_att']:passing.setdefault((r['game_id'],r['player_id']),{})[r['category']]=r
    contradictions=0
    for pair in passing.values():
        if len(pair)!=2:continue
        for r in pair.values():r['coherence_state']=state_for(r['forecast_id'],root/'metadata')
        if any(r['coherence_state']=='COMPLETION_ATTEMPT_CONTRADICTION' for r in pair.values()):contradictions+=1
    files=[];categories=[]
    for target,(label,*_) in CATEGORIES.items():
        q=sorted([r for r in rows if r['category']==target],key=lambda r:(r['kickoff_UTC'],r['team'],r['name']));p=docs/'data/forward'/f'{target}.json';dump(p,q)
        files.append(dict(category=target,file='forward/'+p.name,SHA256=sha(p),rows=len(q)))
        categories.append(dict(id=target,label=label,rows=len(q),players=len({r['player_id'] for r in q}),games=len({r['game_id'] for r in q}),sparse_players=sum(r['target_sparse'] for r in q),zero_history=sum(r['target_history_support']==0 for r in q),OUT_or_doubtful=sum(r['selection_availability']=='BLOCKED_OUT' for r in q),model_fallback=sum(r['model_fallback'] for r in q),real_offers=0,real_selections=0,graded=0,implementation='P2_CORE_IMPLEMENTED_LABEL_COVERAGE_PARTIAL' if target=='fpts' else 'P2_CORE_IMPLEMENTED_SIX_COMPONENT_GAPS_REMAIN',issuance='SHADOW_SERVER_CAPTURED' if target=='fpts' else 'FORECAST_ONLY_SERVER_CAPTURED',improvement='NOT_DEMONSTRATED_PROSPECTIVE_PENDING'))
    manifest=dict(schema='C-UPCOMING-SITE-v4',generated_UTC=datetime.now(timezone.utc).isoformat(),policy_id='C-PROSPECTIVE-v4',runs=runs,files=files,categories=categories,forecast_rows=len(rows),unique_players=len({r['player_id'] for r in rows}),games=len({r['game_id'] for r in rows}),first_kickoff_UTC=min(r['kickoff_UTC'] for r in rows),appearance_conditioning=rows[0]['appearance_conditioning'],real_offers=0,real_selections=0,graded_outcomes=0,six_leg_state='NO_QUALIFIED_SIX_LEG_ENTRY',completion_attempt_contradictions=contradictions,publication='GITHUB_SERVER_VERIFIED_PREGAME',manual_only=True,source_status_max_age_seconds=1800,entries=[],real_offer_results=[],historical_real_offer_results=[],components_reference='https://github.com/NickNicky19/NFL-forecasting-NGS-C/blob/main/reports/prospective-v4/COMPONENT_STATUS.json')
    dump(docs/'data/forward-manifest.json',manifest)
    build=read_json(docs/'build.json');build.update(forward_manifest_SHA256=sha(docs/'data/forward-manifest.json'),forward_model_version='C-FORWARD-P2-v4; chartPPRcoverage-limitedshadow',forward_feature_cutoff_UTC=max(r['information_cutoff_UTC'] for r in rows),forward_source_observed_UTC=max(r['source_snapshot_observed_UTC'] for r in rows),forward_server_persisted_UTC=max(r['server_persisted_UTC'] for r in rows),status='UPCOMING_FORECAST_ONLY_AND_SEPARATE_HISTORICAL_RESEARCH');dump(docs/'build.json',build)
    print('FUTURE_SITE_PROJECTION',len(rows),len(categories),contradictions);return manifest

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('prospective'));p.add_argument('--docs',type=Path,default=Path('docs'));a=p.parse_args();build(a.root,a.docs)
