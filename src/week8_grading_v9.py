"""Append Week8 outcomes/grades to immutable pregame snapshots. Never fits.

Input is the bounded, temporary acquisition manifest plus ordinary NFL facts.
Only the consumed factual projection is retained publicly, with real clocks.
"""
import argparse,csv,gzip,hashlib,io,json,math,time,resource
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path
import pandas as pd
from contracts_v2 import CATEGORIES,WEIGHTS,RARE,SIGNED,CHART,integer,target,chart
from data_v2 import PHYSICAL
from prospective_v4 import validate_run,validate_receipt,first_qualified_snapshots,grade_run
from forward_sources_v4 import kickoff_frame,team,write,digest,stamp

ROOT=Path(__file__).resolve().parents[1]
ID='C-W8-v9-20261102-001'
OUT=ROOT/'reports/week8-v9'
PACK=ROOT/'prospective/outcomes'/ID
RUNROOT=ROOT/'prospective'

def read(p):return json.loads(Path(p).read_bytes())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def pack(p,j):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('xb') as f:f.write(gzip.compress(json.dumps(j,separators=(',',':'),allow_nan=False).encode()+b'\n',mtime=0))
def captures():
    rows=[];proofs=[]
    for p in sorted((RUNROOT/'receipts').glob('*.json')):
        proof=read(p);run=RUNROOT/'runs'/proof['run_id'];m,q=validate_run(run);validate_receipt(run,proof,m,q);rows+=q;proofs.append((run,p))
    first=first_qualified_snapshots(RUNROOT)
    rows=[r for r in rows if first[(r['game_id'],r['player_id'],r['category'],r['policy_id'])][1]==r['forecast_id']]
    assert len(rows)==2513 and len({r['forecast_id'] for r in rows})==2513
    return rows,proofs

def build(raw,version=ID):
    global ID,PACK,OUT
    ID=version;PACK=ROOT/'prospective/outcomes'/ID;OUT=ROOT/'reports/week8-v9/runs'/ID
    start=time.monotonic();cpu=time.process_time();manifest=read(raw.parent/'INTAKE_RAW_MANIFEST.json');source={r['id']:r for r in manifest['sources']}
    for key,m in source.items():assert sha(raw/(key+'.raw'))==m['raw_SHA256'],'RAW_SOURCE_CHANGED:'+key
    rows,proofs=captures();original={r['espn_event_id']:r for r in manifest['original_events']};current={r['espn_event_id']:r for r in manifest['status']};schedule_frame=pd.read_csv(raw/'schedule.raw',low_memory=False);schedules=kickoff_frame(schedule_frame[(schedule_frame.season==2026)&(schedule_frame.week==8)&(schedule_frame.game_type=='REG')].copy());gmap={r['game_id']:r for r in schedules.to_dict('records')};status=[];final=set()
    for native,e in original.items():
        s=current.get(native);why=[];g=gmap.get(e['game_id'])
        if s is None:why.append('CURRENT_NATIVE_STATUS_UNAVAILABLE')
        else:
            if s['home_team']!=e['home_team'] or s['away_team']!=e['away_team'] or abs(s['kickoff']-e['kickoff'])>=1 or s['season']!=2026 or s['week']!=8 or s['season_type']!=2:why.append('EVENT_VERSION_RECONCILIATION_REQUIRED')
            if not (s['state']=='post' and s['completed'] and s['status_name']=='STATUS_FINAL'):why.append('GAME_NOT_FINAL')
        if g is None:why.append('SCHEDULE_IDENTITY_MISSING')
        elif g['home_team']!=e['home_team'] or g['away_team']!=e['away_team'] or abs(g['kickoff']-e['kickoff'])>=1 or int(g['season'])!=2026 or int(g['week'])!=8 or g['game_type']!='REG':why.append('SCHEDULE_IDENTITY_CONFLICT')
        elif pd.isna(g['home_score']) or pd.isna(g['away_score']):why.append('FINAL_SCORE_FACTS_UNAVAILABLE')
        if not why:final.add(e['game_id'])
        status.append(dict(game_id=e['game_id'],espn_event_id=native,original_event_version=e['event_version'],current=s,qualified_final=not why,reasons=why))
    df=pd.read_csv(raw/'stats.raw',compression='gzip',low_memory=False);frame=df[(df.season==2026)&(df.week==8)&(df.season_type=='REG')&df.game_id.isin({e['game_id'] for e in original.values()})].copy()
    cols=['player_id','season','week','season_type','game_id','team','opponent_team','position',*dict.fromkeys(PHYSICAL+[c[1] for c in CATEGORIES.values() if c[1]]+list(SIGNED)+list(WEIGHTS)+['fumble_recovery_tds','special_teams_tds','sack_fumbles_lost','rushing_fumbles_lost','receiving_fumbles_lost'])]
    cols=list(dict.fromkeys(c for c in cols if c not in RARE))
    assert set(cols)<=set(frame.columns),'MISSING_CONSUMED_SOURCE_FIELDS';frame=frame[cols];assert frame.player_id.str.fullmatch(r'00-\d{7}').all()
    duplicates=frame[frame.duplicated(['game_id','player_id'],keep=False)];assert duplicates.empty,'AMBIGUOUS_PLAYER_GAME_STAT_ROWS'
    frame['team']=frame.team.map(team);frame['opponent_team']=frame.opponent_team.map(team)
    facts={(r['game_id'],r['player_id']):r for r in frame.astype(object).where(pd.notna(frame),None).to_dict('records')};bygame={x['game_id']:x for x in status};outcomes=[];audit=[]
    for r in rows:
        if r['game_id'] not in final:continue
        f=facts.get((r['game_id'],r['player_id']));reason=[];proof=[];appearance='UNKNOWN';actual=None;chart_state=None
        if f is None:reason.append('MISSING_PLAYER_STAT_ROW_NOT_DNP_OR_ZERO')
        elif f['team']!=r['team'] or f['opponent_team']!=r['opponent_team']:reason.append('PLAYER_TEAM_EVENT_CONFLICT')
        else:
            proof=[c for c in PHYSICAL if integer(f.get(c)) is not None and integer(f[c])>0]+[c for c in SIGNED if integer(f.get(c),True) not in [None,0]]
            if proof:appearance='PLAYED';actual=target(f,r['category'],True)
            else:reason.append('NO_QUALIFIED_PHYSICAL_PARTICIPATION_PROOF;ROW_ABSENCE_OR_ALLZERO_NOT_DNP')
            if appearance=='PLAYED' and actual is None:reason.append('MISSING_DIRECT_OR_QUALIFIED_COMPONENT_ACTUAL')
            if r['category']=='fpts' and appearance=='PLAYED':actual,chart_state=chart(f,True)
        s=bygame[r['game_id']]['current'];a=dict(game_id=r['game_id'],player_id=r['player_id'],category=r['category'],espn_event_id=r['espn_event_id'],kickoff_UTC=r['kickoff_UTC'],scoring_contract_id=r['scoring_contract_id'],event_status='FINAL',observed_UTC=max(s['observed_UTC'],source['stats']['observed_UTC'],source['schedule']['observed_UTC']),appearance=appearance,actual=actual,participation_proof_fields=proof,unavailable_reasons=reason,source_stat_row_key=[r['game_id'],r['player_id']],chart_state=chart_state)
        if r['category']=='anytime_td' and appearance=='PLAYED':a['event_components']={c:integer(f.get(c)) for c in ['rushing_tds','receiving_tds']}
        if r['category']=='fpts' and actual is not None:
            components={c:integer(f.get(c),c in SIGNED) for c in WEIGHTS if c not in RARE};components.update({c:0 for c in RARE})
            assert f['fumble_recovery_tds']==0 and f['special_teams_tds']==0 and all(v is not None for v in components.values())
            assert abs(sum(WEIGHTS[c]*v for c,v in components.items())/50-actual)<1e-10
            a.update(score_components=components,unique_event_credits_verified=True,unique_credit_proof=dict(native_player_game_row_unique=True,fumbles_lost='ONE_DIRECT_OFFICIAL_fumbles_lost_total;splitlostcounts_not_added',two_points='ONE_EACH_DIRECT_CREDITED_PASS_RUSH_REC_CONVERSION_COLUMN;ordinaryreceptions_used_once',rare_TD='All4zerosonlyfromexplicit_fumble_recovery_tds0_AND_special_teams_tds0;positivebroadtotalsblockattribution',scoring_contract_id=CHART))
        outcomes.append(a);audit.append(dict(forecast_id=r['forecast_id'],game_id=r['game_id'],player_id=r['player_id'],category=r['category'],appearance=appearance,actual=actual,reasons=reason,chart_state=chart_state,participation_proof=proof))
    assert not PACK.exists(),'IMMUTABLE_OUTCOME_PACKET_EXISTS';(PACK/'evidence').mkdir(parents=True)
    raw_provenance={k:{kk:v for kk,v in m.items() if kk not in ['raw_retention']} for k,m in source.items()}
    write(PACK/'evidence/status.json',dict(id=ID,events=status,sources={k:v for k,v in raw_provenance.items() if k.startswith('status_')},status_score_note='Explicit native game FINAL plus independently retained schedule score facts; no source presentation/media/odds retained'))
    scols=['game_id','season','week','game_type','gameday','gametime','home_team','away_team','home_score','away_score']
    gs=schedules[schedules.game_id.isin({e['game_id'] for e in original.values()})][scols];gs.to_csv(PACK/'evidence/schedule.csv',index=False)
    frame.to_csv(PACK/'evidence/player_facts.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    write(PACK/'evidence/SOURCE_MANIFEST.json',dict(id=ID,sources=raw_provenance,consumed_columns=cols,stat_rows=len(frame),raw_total_Week8_REG_rows=len(df[(df.season==2026)&(df.week==8)&(df.season_type=='REG')]),raw_total_Week8_games=int(df[(df.season==2026)&(df.week==8)&(df.season_type=='REG')].game_id.nunique()),qualified_final_game_ids=sorted(final),candidate_membership='Original2513forecasts;no currentstat-row filtering of issued population',rights='Minimum ordinary NFL factual projection under existing nflverseCCBY4 qualification; no EPA/CPOE/NGS/headshots/publisherfantasyvalues or marketpayload. Public ESPN native status facts only.',field_qualification=dict(numerical='Directofficialindividualstatisticfields,not net team yardage;fullgame/OT labels',fumbles='Direct fumbles_lost_total once; do not sum category repeats',two_points='Direct credited conversion fields separately from ordinary receptions',rare='Only explicitzero broad supersets qualify fourrarezeros; positive/missingbroadcountsunresolved')))
    license=RUNROOT/'runs/C-FWD-v4-20261101-0009-P2-pass_yd/sources/LICENSE-CC-BY-4.0.md';(PACK/'evidence/LICENSE-CC-BY-4.0.md').write_bytes(license.read_bytes())
    (PACK/'evidence/ATTRIBUTION.md').write_text('Ordinary NFL player statistics: nflverse/nflverse-data stats_player release, CC BY 4.0. Schedule: nflverse/nfldata. Current native event/final-status facts: public ESPN scoreboard; source presentation/media/odds excluded. C filters numerical fields, joins original immutable GSIS/event identities, reconstructs nick-chart-ppr-v1 explicitly and calculates new postgame grades. These source observations are postgame and do not change original pregame data or issuance clocks. No generic fantasy totals are used.\n')
    evidence=[dict(path=str(p.relative_to(PACK)),SHA256=sha(p),source='NFLVERSE_CCBY4_ORDINARY_FACTS_AND_NATIVE_FINAL_STATUS') for p in sorted((PACK/'evidence').iterdir())]
    packet=dict(schema='C-OUTCOMES-v4',version=ID,created_UTC=stamp(),source_qualification='OFFICIAL_NUMERICAL_FACTS_VERIFIED',source_evidence=evidence,outcomes=outcomes)
    write(PACK/'OUTCOMES.json',packet);write(PACK/'APPEARANCE_AND_LABEL_AUDIT.json',audit)
    OUT.mkdir(parents=True,exist_ok=True);write(OUT/'STATUS_CHECK.json',dict(id=ID,created_UTC=stamp(),events=status,qualified_final_games=len(final),original_games=len(original),original_forecasts=len(rows),new_fits=0,source_evidence_reference=str((PACK/'evidence/status.json').relative_to(ROOT))))
    grades=[];receipts=[]
    for run,proof in proofs:
        output=RUNROOT/'grades'/(ID+'-'+run.name+'.json');g=grade_run(run,proof,PACK/'OUTCOMES.json',output);grades+=g;receipts.append(dict(path=str(output.relative_to(ROOT)),SHA256=sha(output),rows=len(g)))
    combined={r['forecast_id']:r for r in grades};full=[]
    for r in rows:
        g=combined[r['forecast_id']];a=next((x for x in outcomes if (x['game_id'],x['player_id'],x['category'])==(r['game_id'],r['player_id'],r['category'])),None)
        full.append(dict(forecast_id=r['forecast_id'],run_id=r['run_id'],game_id=r['game_id'],espn_event_id=r['espn_event_id'],player_id=r['player_id'],name=r['name'],position=r['position'],team=r['team'],opponent_team=r['opponent_team'],category=r['category'],kickoff_UTC=r['kickoff_UTC'],mean=r['mean'],median=r['median'],p05=r['p05'],p95=r['p95'],event_probability=r['event_probability'],model_id=r['model_id'],model_SHA256=r['model_SHA256'],scoring_contract_id=r['scoring_contract_id'],information_cutoff_UTC=r['information_cutoff_UTC'],generated_UTC=r['generated_UTC'],appearance_conditioning=r['appearance_conditioning'],readiness=r['readiness'],model_fallback=r['model_fallback'],target_history_support=int(r['features'][3]),state=g['state'],actual=g.get('actual'),absolute_error=g.get('absolute_error'),median_error=g.get('median_error'),mean_squared_error=g.get('mean_squared_error'),CRPS=g.get('CRPS'),NLL=g.get('NLL'),outcome_observed_UTC=a['observed_UTC'] if a else None,outcome_reasons=a['unavailable_reasons'] if a else bygame[r['game_id']]['reasons'],chart_state=a['chart_state'] if a else None,grade_version=ID,evidence_tier='GITHUB_SERVER_VERIFIED_PREGAME_FORECAST_ONLY;POSTGAME_STATISTICAL_GRADING',offer_state='NO_QUALIFIED_ACTUAL_LINE',line=None,selected_side=None))
    pack(OUT/'GRADED_FORECAST_ROWS.json.gz',full)
    write(OUT/'GRADING_RUN.json',dict(id=ID,created_UTC=stamp(),original_rows=len(rows),outcome_rows=len(outcomes),grade_rows=len(grades),states=dict(Counter(g['state'] for g in grades)),qualified_final_games=len(final),pending_games=len(original)-len(final),grade_files=receipts,outcome_packet=str((PACK/'OUTCOMES.json').relative_to(ROOT)),outcome_SHA256=sha(PACK/'OUTCOMES.json'),new_NFL_fits=0,CPU_seconds=time.process_time()-cpu,wall_seconds=time.monotonic()-start,peak_RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024))
    print(read(OUT/'GRADING_RUN.json'))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--raw',type=Path,required=True);p.add_argument('--version',default=ID);x=p.parse_args();build(x.raw,x.version)
