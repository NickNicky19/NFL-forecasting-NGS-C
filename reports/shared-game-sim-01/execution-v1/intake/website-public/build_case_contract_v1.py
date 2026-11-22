"""Lossless website case bridge and strict provider-only S-P query projection.

No grader, model, training, trajectory generation or source networking. Run only
in website preparation, never as the simulator's forecast worker. The forecast
worker consumes only load_forecast_inputs(output/forecast_worker), plus C's
separately admitted earlier training/query context. Original ZIP remains intact.
"""
import argparse, collections, hashlib, json, math
from pathlib import Path
VERSION='NFL-WEBSITE-SHARED-GAME-CASE-v1'
OUTCOME_VERSION='NFL-WEBSITE-PINNED-STATISTICAL-OUTCOME-v1'
EXPECTED_HASH_MANIFEST='1ff8f6318b4feb47e7cf3568e5db0b60f0fa53f1eb16eccf10cf336b55c4a6af'
QUERY_KEYS=set('case_id source_revision season week game_id player_id category line venue name position point_source saved_raw_point saved_adjusted_point provider_first_point saved_lean forecast_issuance_authentication quote_clock_authentication scope'.split())
CATEGORIES=('pass_yd','pass_td','pass_cmp','pass_att','pass_int','rush_yd','rush_att','rec','rec_yd','rush_rec_yd')
FORBIDDEN={'actual','outcome','result','grade','label','correct','win','loss','line','venue','book','price','saved_lean','saved_adjusted_point','provider_first_point','target_stats','final_score','score','actual_participation','eventual_participant'}
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sha(b):return hashlib.sha256(b).hexdigest()
def finite(x):return type(x) in (int,float) and math.isfinite(x)
def jsonl(rows):return b''.join(canonical(r)+b'\n' for r in rows)
def read_rows(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size>16<<20:raise ValueError('Bounded regular JSONL required')
    return [json.loads(x,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('NonfiniteJSON'))) for x in path.read_bytes().splitlines()]
def context_from_archives(package):
    context={}
    for week in range(4,10):
        a=json.loads((package/f'comparison/archives/2026_w{week:02d}.json').read_bytes())
        games={g['id']:g for g in a['games']}
        for p in a['players']:
            key=(a['season'],week,p['game_id'],p['id']);g=games[p['game_id']]
            if key in context:raise ValueError('Duplicate source player-game')
            # Only identity/schedule fields: never finality, odds, statistics,
            # late/participation, matchup, snap history or computed team totals.
            context[key]=dict(team=p['team'],opponent=p['opp'],position=p['pos'],kickoff_utc=g['kickoff'],home=g['home'],away=g['away'])
    return context
def derive(queries,context):
    cases=[];bench=[];players={};games={};seen=set()
    for q in queries:
        if set(q)!=QUERY_KEYS:raise ValueError('Unregistered query schema')
        cid=q['case_id'];cat=q['category'];key=(q['season'],q['week'],q['game_id'],q['player_id']);ctx=context[key]
        if cid in seen or cat not in CATEGORIES or not finite(q['line']) or q['position']!=ctx['position']:raise ValueError('Case/role/line identity')
        if ctx['team'] not in {ctx['home'],ctx['away']} or ctx['opponent'] not in {ctx['home'],ctx['away']} or ctx['team']==ctx['opponent']:raise ValueError('Team/event identity')
        seen.add(cid);pg='/'.join(map(str,key));gk='/'.join(map(str,key[:3]))
        identity=dict(source_revision=q['source_revision'],season=q['season'],week=q['week'],game_id=q['game_id'],player_id=q['player_id'],category=cat,position=q['position'],team=ctx['team'],opponent=ctx['opponent'],line=q['line'],venue=q['venue'],decision_horizon='UNKNOWN_ARCHIVED_ISSUANCE',quote_clock='UNKNOWN',settlement_contract='STATISTICAL_CROSSING_NOT_VERIFIED_VENUE_SETTLEMENT')
        cases.append(dict(case_id=cid,canonical_case_key=sha(canonical(identity)),identity=identity,player_game_key=pg,game_origin_key=gk,kickoff_utc=ctx['kickoff_utc'],line_classification='UNCLASSIFIED_ORDINARY_OR_ALTERNATE',original_case_id_derivation='OPAQUE_DELIVERED_ALIAS_RETAINED_NOT_REVERSE_ENGINEERED',case_contract=VERSION))
        native=q['point_source']=='model' and finite(q['saved_raw_point']);w0=q['saved_adjusted_point'];w1=q['saved_raw_point'] if native else w0
        if not finite(w0) or q['provider_first_point']!=w1:raise ValueError('Literal benchmark identity')
        bench.append(dict(case_id=cid,W0_literal_saved_adj=w0,W1_literal_provider_or_adjusted_fallback=w1,W1_source='SAVED_PROVIDER_NATIVE' if native else 'INCUMBENT_ADJUSTED_FALLBACK',saved_margin_side=q['saved_lean'],point_source=q['point_source']))
        if pg not in players:players[pg]=dict(player_game_key=pg,game_origin_key=gk,season=q['season'],week=q['week'],game_id=q['game_id'],player_id=q['player_id'],position=q['position'],team=ctx['team'],opponent=ctx['opponent'],provider_points={},provider_missing={},requested_targets=[],scope='OFFER_FRAME_PLAYER_NOT_COMPLETE_TEAM_ROSTER',provider_availability='SAVED_ARCHIVE_POINT_RECONSTRUCTED_DEVELOPMENT_ORIGINAL_CLOCK_UNKNOWN')
        p=players[pg];value=q['saved_raw_point'] if native else None
        if cat in p['provider_points'] and (p['provider_points'][cat]!=value or p['provider_missing'][cat]!=(not native)):raise ValueError('Inconsistent same-player provider point')
        p['provider_points'][cat]=value;p['provider_missing'][cat]=not native
        if cat not in p['requested_targets']:p['requested_targets'].append(cat)
        g=dict(game_origin_key=gk,season=q['season'],week=q['week'],game_id=q['game_id'],home=ctx['home'],away=ctx['away'],kickoff_utc=ctx['kickoff_utc'],team_context='INCOMPLETE; C separately qualifies pregame roster/opportunity/other-player bucket')
        if gk in games and games[gk]!=g:raise ValueError('Inconsistent game context')
        games[gk]=g
    for p in players.values():p['requested_targets'].sort()
    return dict(cases=jsonl(cases),benchmarks=jsonl(bench),players_sp=jsonl([players[k] for k in sorted(players)]),games_sp=jsonl([games[k] for k in sorted(games)]))
def assert_no_target_fields(x):
    if isinstance(x,dict):
        if set(x)&FORBIDDEN:raise ValueError('Forbidden forecast-query field')
        for v in x.values():assert_no_target_fields(v)
    elif isinstance(x,list):
        for v in x:assert_no_target_fields(v)
def load_forecast_inputs(root, expected_manifest_sha256):
    root=Path(root)
    if root.is_symlink() or {x.name for x in root.iterdir()}!={'players_sp.jsonl','games_sp.jsonl','manifest.json'}:raise ValueError('Closed forecast worker directory required')
    manifest_body=(root/'manifest.json').read_bytes()
    if sha(manifest_body)!=expected_manifest_sha256:raise ValueError('Unfrozen forecast manifest')
    m=json.loads(manifest_body);docs={}
    if m.get('schema')!='NFL-SP-QUERY-ALLOWLIST-v1' or set(m.get('files',{}))!={'players_sp.jsonl','games_sp.jsonl'}:raise ValueError('Forecast file allowlist')
    for f in ['players_sp.jsonl','games_sp.jsonl']:
        p=root/f
        if p.is_symlink() or p.resolve().parent!=root.resolve():raise ValueError('Forecast path escape')
        if sha(p.read_bytes())!=m['files'][f]['sha256']:raise ValueError('Forecast body hash')
        docs[f]=read_rows(p);assert_no_target_fields(docs[f])
    return docs

def prepare(package,output):
    package=Path(package);output=Path(output)
    if output.exists():raise ValueError('Fresh destination required; preserve original artifacts')
    bound=(package/'SHA256SUMS.json').read_bytes()
    if sha(bound)!=EXPECTED_HASH_MANIFEST:raise ValueError('Unregistered source hash manifest')
    for f,entry in json.loads(bound).items():
        path=package/f
        if Path(f).is_absolute() or '..' in Path(f).parts or path.is_symlink() or not path.is_file() or path.stat().st_size!=entry['bytes'] or sha(path.read_bytes())!=entry['sha256']:raise ValueError('Frozen source body mismatch:'+f)
    q=read_rows(package/'queries/evaluation_cases_ungraded.jsonl');views=derive(q,context_from_archives(package));o=read_rows(package/'grading_only/outcomes.jsonl')
    if len(q)!=3474 or len(o)!=3474 or {x['case_id'] for x in q}!={x['case_id'] for x in o}:raise ValueError('Complete fixed case/outcome frame required')
    normalized=[]
    for x in o:
        if set(x)!=set('case_id actual extraction_status_for_over_query outcome_source'.split()) or x['actual'] is not None and not finite(x['actual']):raise ValueError('Outcome schema')
        normalized.append(dict(case_id=x['case_id'],outcome_version=OUTCOME_VERSION,actual=x['actual'],statistic_state='UNKNOWN' if x['actual'] is None else 'REUSED_SUPPORTED_STATISTIC',unresolved_reason='NOT_RETAINED' if x['actual'] is None else None,outcome_source=x['outcome_source'],source_over_extraction_status_audit_only=x['extraction_status_for_over_query'],venue_settlement='NOT_VERIFIED',participation_reaudit='NOT_PERFORMED'))
    files={'comparison_inputs/cases.jsonl':views['cases'],'comparison_inputs/benchmarks.jsonl':views['benchmarks'],'forecast_worker/players_sp.jsonl':views['players_sp'],'forecast_worker/games_sp.jsonl':views['games_sp'],'grading_only/outcomes.v1.jsonl':jsonl(normalized)}
    output.mkdir(mode=0o700)
    for f,data in files.items():t=output/f;t.parent.mkdir(parents=True,exist_ok=True);t.write_bytes(data)
    mf=dict(schema='NFL-SP-QUERY-ALLOWLIST-v1',input_files='Only these two files; source/input bodies are not a complete simulator training matrix',files={f.split('/')[-1]:dict(bytes=len(v),sha256=sha(v)) for f,v in files.items() if f.startswith('forecast_worker/')},earlier_football_context='C separately declares/admit existing permitted earlier inputs, traininglabels, complete team/other-player context and missing-provider fallback before generation.',seed_rule='Registered seed+game_origin_key; never case_id, offer/line/book, outcomes, row order or a whole ZIP hash.',provider_assistance='Only literal finite saved raw provider points where source=model. Zero is known; missing remains explicit. W1 fallback is a benchmark definition, not an automatically admitted S-P model fallback.')
    (output/'forecast_worker/manifest.json').write_bytes(canonical(mf)+b'\n');files['forecast_worker/manifest.json']=(output/'forecast_worker/manifest.json').read_bytes();load_forecast_inputs(output/'forecast_worker',sha(files['forecast_worker/manifest.json']))
    manifest=dict(schema=VERSION,state='CONDITIONAL_ARCHIVED_STATISTICAL_COMPARISON_FRAME',source_commit='f15790bc1396e532eb0f6991f8e05dbf6a66fb2d',source_query_sha256=sha((package/'queries/evaluation_cases_ungraded.jsonl').read_bytes()),source_outcome_sha256=sha((package/'grading_only/outcomes.jsonl').read_bytes()),files={f:dict(bytes=len(v),sha256=sha(v)) for f,v in files.items()},case_count=len(q),outcome_count=len(o),unknown_outcome_count=sum(x['actual'] is None for x in o),native_provider_cases=sum(x['point_source']=='model' and finite(x['saved_raw_point']) for x in q),missing_provider_cases=sum(not(x['point_source']=='model' and finite(x['saved_raw_point'])) for x in q),represented_games=len(json.loads(b'['+b','.join(views['games_sp'].splitlines())+b']')),forecast_worker_player_games=len(views['players_sp'].splitlines()),statistical_grade_version='statistical-presence-verified-int-v7-20261112',outcome_version=OUTCOME_VERSION,original60cell_replay='REUSED_RECORDED_COMPLETE; no grader/replay called',original_points='W0 literal saved adj; W1 literal saved proj only ifsource=model and finite, else literal adjustedfallback. Strict ties abstain; no point probabilities.',timing='Unknown original source/issue/quote clocks remain unknown; exposed reconstructed development, not original issuance.',labels='464 unknowns retained; Over extractionstatus is not pick correctness; no zero/DNP imputation; grade/selection joined only after forecast freeze.',source_limit='Typed caches semantic copies,88 exact identity-bound INT ledger outcomes reused; no new raw-boxscore/venue-settlement audit; no missing nativeweeks certified.',source_ledger_wrapper='One extra terminalLF relative to pinned source additionally disclosed in sourceobjectv1.1; original bytes/values preserved.',scope='Ten numerical target offer frame; anytimeTD and exactchart require separate event/scoring/outcome/offer contracts; no invented markets.',engine_readiness='NOT_CERTIFIED; C soleexecutor must classify READY_STATEFUL/READY_BOX_SCORE/BLOCKED using its retained training/opportunity/role/event bodies and whole cost. Case admission doesnot block preliminary readiness/candidate work.')
    (output/'CASE_MANIFEST.json').write_bytes(canonical(manifest)+b'\n');return manifest
if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--package',required=True,type=Path);ap.add_argument('--output',required=True,type=Path);args=ap.parse_args();r=prepare(args.package,args.output);print(json.dumps({k:r[k] for k in ['schema','state','case_count','unknown_outcome_count','native_provider_cases','missing_provider_cases','represented_games','forecast_worker_player_games']}))
