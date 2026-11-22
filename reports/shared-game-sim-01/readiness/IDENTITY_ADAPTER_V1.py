"""Outcome-free identity/origin readiness; no forecast, fit, canary or grade.

Only identity/team/time metadata are selected from ordinary fact bodies.
Current roster team/status fields and query points/lines/outcomes are never used.
"""
from __future__ import annotations
import argparse,bisect,csv,gzip,hashlib,io,json,signal,time,unicodedata,zipfile
from collections import Counter,defaultdict
from datetime import datetime,timedelta,timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
QUERY='queries/evaluation_cases_ungraded.jsonl'
DAY=86400
META=['player_id','player_display_name','position','season','week','game_id','team']
def norm(s):
    return ''.join(c for c in unicodedata.normalize('NFKD',str(s)).casefold() if c.isalnum())
def digest(x):
    return hashlib.sha256(json.dumps(x,separators=(',',':'),sort_keys=True,allow_nan=False).encode()).hexdigest()
def bind(p):
    b=p.read_bytes();return dict(path=p.relative_to(ROOT).as_posix(),bytes=len(b),SHA256=hashlib.sha256(b).hexdigest())
def kickoff(r):
    return datetime.fromisoformat(r['gameday']+'T'+r['gametime']).replace(tzinfo=ZoneInfo('America/New_York')).astimezone(timezone.utc).timestamp()
def iso(x):return datetime.fromtimestamp(x,timezone.utc).isoformat().replace('+00:00','Z')

def build_adapter(attachment):
    """Returns metadata mappings in memory; main publishes aggregates, not rows."""
    paths=[ROOT/'artifacts/basic-football-facts-v2.1.zip',ROOT/'sources/category-decision-release-01/current_facts_2026.csv.gz',ROOT/'sources/category-decision-release-01/schedule.csv',ROOT/'sources/category-decision-release-01/roster_current_season.json']
    with zipfile.ZipFile(attachment) as z:
        qb=z.read(QUERY)
        # Select the admitted identity metadata immediately; provider values are not inputs here.
        queries=[{k:r[k] for k in ['case_id','season','week','game_id','player_id','name','position','category']} for r in map(json.loads,qb.splitlines())]
    with zipfile.ZipFile(paths[0]) as z:
        older=list(csv.DictReader(io.StringIO(z.read('schedule.csv').decode())))
        factmeta=[{k:r[k] for k in META} for r in csv.DictReader(io.StringIO(gzip.decompress(z.read('facts.csv.gz')).decode()))]
    with gzip.open(paths[1],'rt') as f:
        # Preserve original earlier body; extend only missing W8/9 metadata.
        factmeta += [{k:r[k] for k in META} for r in csv.DictReader(f) if r['season']=='2026' and int(r['week'])>=8]
    current=list(csv.DictReader(paths[2].open()))
    # Scores are deliberately not copied into the retained schedule interface.
    schedules={r['game_id']:{k:r[k] for k in ['game_id','season','week','gameday','gametime','home_team','away_team']} for r in older if r['season']!='2026'}
    schedules.update({r['game_id']:{k:r[k] for k in ['game_id','season','week','gameday','gametime','home_team','away_team']} for r in current})
    for r in schedules.values():r['kickoff']=kickoff(r)
    espn=defaultdict(set)
    for r in current:
        if r.get('espn'):espn[str(r['espn'])].add(r['game_id'])
    querygames={q['game_id'] for q in queries}
    cutoffs={g:schedules[next(iter(espn[g]))]['kickoff']-90*60 for g in querygames if len(espn[g])==1}
    first_cut=min(cutoffs.values())
    candidates=defaultdict(set);names_sources=defaultdict(set)
    # Current snapshot contributes a stable person/role identity bridge only.
    roster=json.loads(paths[3].read_bytes())
    for r in roster:
        if r.get('gsis_id') and r.get('full_name') and r.get('position'):
            key=(norm(r['full_name']),r['position']);candidates[key].add(r['gsis_id']);names_sources[key].add('CURRENT_VINTAGE_ROSTER_IDENTITY_ONLY')
    history=defaultdict(list);seen={};teamgames=defaultdict(set)
    for r in factmeta:
        g=schedules.get(r['game_id'])
        if not g:continue
        key=(r['player_id'],r['game_id']);v=(r['team'],r['position'])
        assert key not in seen or seen[key]==v,'CONFLICTING_IDENTITY_METADATA'
        if key in seen:continue
        seen[key]=v
        history[r['player_id']].append((g['kickoff'],r['game_id'],r['team'],r['position']))
        teamgames[r['team']].add((g['kickoff'],r['game_id']))
        # Older aliases use only pre-first-query admitted metadata, not target rows.
        if g['kickoff']+7*DAY<first_cut:
            nk=(norm(r['player_display_name']),r['position']);candidates[nk].add(r['player_id']);names_sources[nk].add('ADMITTED_PRIOR_ORDINARY_NAME_POSITION')
    for arr in history.values():arr.sort()
    times={p:[x[0] for x in arr] for p,arr in history.items()}
    byquery=defaultdict(set)
    for q in queries:byquery[q['player_id']].add((norm(q['name']),q['position']))
    query_id_candidates={pid:set().union(*(candidates[key] for key in nk)) for pid,nk in byquery.items()}
    rows=[];poolmap={}
    for q in queries:
        row=dict(case_id=q['case_id'],source_game_id=q['game_id'],source_player_id=q['player_id'],week=q['week'],category=q['category'],query_role=q['position'])
        gs=espn[q['game_id']]
        if len(gs)!=1:
            row['status']='UNAVAILABLE_GAME_IDENTITY';rows.append(row);continue
        game=schedules[next(iter(gs))];cut=game['kickoff']-90*60
        row.update(canonical_game_id=game['game_id'],canonical_kickoff_UTC=iso(game['kickoff']),assumed_model_cutoff_UTC=iso(cut),source_issue_UTC=None,source_quote_UTC=None)
        if int(game['season'])!=int(q['season']) or int(game['week'])!=int(q['week']):
            row['status']='UNAVAILABLE_GAME_SEASON_WEEK_CONFLICT';rows.append(row);continue
        ids=query_id_candidates[q['player_id']]
        if len(ids)!=1:
            row['status']='UNAVAILABLE_IDENTITY_MISSING' if not ids else 'UNAVAILABLE_IDENTITY_AMBIGUOUS';rows.append(row);continue
        pid=next(iter(ids));row['canonical_player_id']=pid
        available=bisect.bisect_left(times.get(pid,[]),cut-7*DAY)
        if not available:
            row['status']='UNAVAILABLE_NO_ADMITTED_PRIOR_TEAM';rows.append(row);continue
        prior=history[pid][available-1]
        assert prior[0]+7*DAY<cut
        row.update(latest_prior_game=prior[1],latest_prior_kickoff_UTC=iso(prior[0]),prior_team=prior[2],prior_metadata_role=prior[3])
        if prior[2] not in [game['home_team'],game['away_team']]:
            row['status']='UNAVAILABLE_PRIOR_TEAM_NOT_IN_TARGET_GAME';rows.append(row);continue
        row.update(status='READY_RECONSTRUCTED_IDENTITY_USAGE_TEAM',team=prior[2],opponent=game['away_team'] if prior[2]==game['home_team'] else game['home_team'])
        rows.append(row)
        for team in [game['home_team'],game['away_team']]:
            pkey=(game['game_id'],team)
            if pkey in poolmap:continue
            games=sorted(v for v in teamgames[team] if v[0]+7*DAY<cut)[-8:];gset={v[1] for v in games};members=[]
            for p,arr in history.items():
                ix=bisect.bisect_left(times[p],cut-7*DAY)
                if ix and arr[ix-1][2]==team and any(v[1] in gset and v[2]==team for v in arr[:ix]):members.append(p)
            poolmap[pkey]=dict(admitted_prior_team_games=len(games),prior_stat_row_members=len(members),member_identity_fingerprint=digest(sorted(members)),other_unknown_required=True,not_authenticated_roster=True)
    return rows,poolmap,queries,paths,qb

def main():
    c=time.process_time();w=time.monotonic()
    parser=argparse.ArgumentParser();parser.add_argument("attachment",type=Path);args=parser.parse_args()
    previous_path=OUT/"IDENTITY_ORIGIN_READINESS.json"
    previous=json.loads(previous_path.read_text()) if previous_path.exists() else None
    signal.signal(signal.SIGPROF,lambda *_:(_ for _ in ()).throw(RuntimeError('READINESS5CPU_STOP')))
    signal.setitimer(signal.ITIMER_PROF,4.5)
    rows,pools,queries,paths,qb=build_adapter(args.attachment)
    week={};cats={}
    for field,out in [('week',week),('category',cats)]:
        for val in sorted({r[field] for r in rows},key=str):
            rr=[r for r in rows if r[field]==val];out[str(val)]=dict(rows=len(rr),player_games=len({(r['source_game_id'],r['source_player_id']) for r in rr}),states=dict(Counter(r['status'] for r in rr)))
    states=Counter(r['status'] for r in rows)
    blocked=[dict(case_id_SHA256=hashlib.sha256(r['case_id'].encode()).hexdigest(),week=r['week'],category=r['category'],reason=r['status']) for r in rows if not r['status'].startswith('READY_')]
    supported=[r for r in rows if r['status'].startswith('READY_')]
    report=dict(id='SHARED-GAME-SIM-01-C-IDENTITY-ORIGIN-READINESS',state='PARTIAL_READY_BOX_SCORE_RECONSTRUCTED_IDENTITY_USAGE_TEAM',sources=[bind(p) for p in paths],query_body_SHA256=hashlib.sha256(qb).hexdigest(),code=bind(Path(__file__)),rows=len(rows),player_games=len({(r['source_game_id'],r['source_player_id']) for r in rows}),games=len({r['source_game_id'] for r in rows}),states=dict(states),supported_rows=len(supported),supported_player_games=len({(r['source_game_id'],r['source_player_id']) for r in supported}),supported_games=len({r['source_game_id'] for r in supported}),by_week=week,by_category=cats,blocked_cells=blocked,adapter_full_metadata_fingerprint=digest(rows),prior_pool_summary=dict(team_game_pools=len(pools),minimum_prior_games=min((v['admitted_prior_team_games'] for v in pools.values()),default=0),minimum_members=min((v['prior_stat_row_members'] for v in pools.values()),default=0),maximum_members=max((v['prior_stat_row_members'] for v in pools.values()),default=0),fingerprint=digest([[g,t,v] for (g,t),v in sorted(pools.items())])),policy=dict(identity='ExactUnicodeNFKDcasefoldalphanumericfullname+exactdeclaredrole; unambiguousGSISonly. No suffix removal/fuzzyalias; currentrosterteam/statusnotused.',availability='Strict prior kickoff+7days < ASSUMED target canonical kickoff-90minutes; not observed original data clock.',team='Latest admitted PRIOR ordinary statistical-row team must be one scheduled opponent; no target-stat/current-roster-team assignment.',population='Prior-stat-row usage pool plus explicit other/unresolved bucket. Not complete roster or actual participation.',prohibited_query_fields_used=[]),scope_limits=['Roster/source identity is current-vintage reconstruction, not authenticated origin-time roster or injury status.','No claim player stayed on team or will participate; trade/return/new-player uncertainty remains.','The full3474 board must remain declared; unsupported rows are technical unavailability, not losses/intentional abstentions.','No provider points/lines/savedleans/outcomes are published or consumed by this adapter.','Canonical website case/settlement and retention admission remain separate.'],new_fits=0,new_forecasts=0,new_simulations=0,new_grading=0,new_network=0,CPU_seconds=time.process_time()-c,wall_seconds=time.monotonic()-w,conservative_housekeeping_CPU_charge=5,measurement_limit='Selectedprocess+boundedpreparation;notcompleteassistantorchestrationcertificate')
    if previous:
        assert previous['adapter_full_metadata_fingerprint']==report['adapter_full_metadata_fingerprint'],'PACKAGING_REPAIR_CHANGED_ADAPTER'
        report['initial_pass_CPU_seconds']=previous['CPU_seconds']
        report['total_measured_pass_CPU_seconds']=previous['CPU_seconds']+report['CPU_seconds']
        report['packaging_repair']='Private attachment location replaced by CLIargument; full adapter fingerprint unchanged; no source/model/tolerance change.'
        report['prior_code_SHA256']=previous['code']['SHA256']
    assert report.get('total_measured_pass_CPU_seconds',report['CPU_seconds'])<5
    signal.setitimer(signal.ITIMER_PROF,0)
    (OUT/'IDENTITY_ORIGIN_READINESS.json').write_text(json.dumps(report,indent=2)+'\n')
    lines=['# Outcome-free identity and origin adapter','',f"**{len(supported)}/{len(rows)} offer rows; {report['supported_player_games']}/{report['player_games']} player-games** qualify for this exact reconstructed identity/usage-team interface. Full-board unavailable cells remain in the JSON. This is not inference or an authentic pregame roster admission.",'','| Status | Offer rows |','| --- | ---: |']+[f'| {k} | {v} |' for k,v in states.items()]
    lines+=['','Sleeper query IDs are bridged only by an unambiguous exact normalized full-name plus declared position to retained GSIS identities. The current roster contributes person identity only; neither its team nor ACT/status is used. No fuzzy matching or suffix removal is applied.','', 'ESPN game IDs map uniquely through the retained schedule to native games and canonical kickoff UTC. T90 is explicitly an assumed development cutoff, not a discovered source/quote/issue timestamp. Latest prior team comes from an ordinary statistical row satisfying `prior kickoff +7days < assumed cutoff`; target-game rows and current roster membership never determine it.','', 'Prior pools contain recorded earlier stat-row members, not a complete roster or known future participants. Other/unresolved mass and explicit participation uncertainty remain required. Unsupported players are technical unavailable, not zeros, losses or intentional abstentions.','', '[Machine coverage/hashed blocked cells/source/code fingerprints](IDENTITY_ORIGIN_READINESS.json). Raw provider/query rows and full adapter rows are not published; the script returns metadata mappings in memory for the parent to bind under its admitted engine/retention contract. No target outcomes/statistics, fits, forecasts, simulation, grading or network calls occurred.']
    (OUT/'IDENTITY_ORIGIN_READINESS.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({k:report[k] for k in ['rows','supported_rows','player_games','supported_player_games','supported_games','states','CPU_seconds','wall_seconds']}))

if __name__=='__main__':main()
