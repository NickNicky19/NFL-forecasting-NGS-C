"""Bounded static PropLine intake and saved-C-model exact-line diagnostics.

No acquisition, fitting, tuning, synthetic fallback line, or live-paper issuance.
Only the specifically licensed pinned sample is admitted by this adapter.
"""
import argparse,csv,gzip,hashlib,io,json,pickle,resource,time,zipfile
from collections import Counter,defaultdict
from datetime import datetime,timezone
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np
from actual_accuracy_v6 import digest,sha,stable_write,validate_row,method_version,TIERS
from contracts_v2 import CATEGORIES,grade,thresholds_for_line
from safe_models_v4 import export_forest,infer_forest,law_data
from selection import point_side

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'sources/propline-v7'
OUT=ROOT/'reports/propline-v7'
VERSION='C-PROPLINE-ACTUAL-LINES-v7'
MARKETS={'player_pass_yds':'pass_yd','player_rush_yds':'rush_yd','player_reception_yds':'rec_yd','player_receptions':'rec'}
TEAMS=dict(zip(['Arizona Cardinals','Atlanta Falcons','Baltimore Ravens','Buffalo Bills','Carolina Panthers','Chicago Bears','Cincinnati Bengals','Cleveland Browns','Dallas Cowboys','Denver Broncos','Detroit Lions','Green Bay Packers','Houston Texans','Indianapolis Colts','Jacksonville Jaguars','Kansas City Chiefs','Las Vegas Raiders','Los Angeles Chargers','Los Angeles Rams','Miami Dolphins','Minnesota Vikings','New England Patriots','New Orleans Saints','New York Giants','New York Jets','Philadelphia Eagles','Pittsburgh Steelers','San Francisco 49ers','Seattle Seahawks','Tampa Bay Buccaneers','Tennessee Titans','Washington Commanders'],['ARI','ATL','BAL','BUF','CAR','CHI','CIN','CLE','DAL','DEN','DET','GB','HOU','IND','JAX','KC','LV','LAC','LA','MIA','MIN','NE','NO','NYG','NYJ','PHI','PIT','SF','SEA','TB','TEN','WAS']))
NFL_SHA='053f6a5ef9b68ee4eb9f4f9bb71fe6daf9e3759d092c414bd1df28ea0b2a7b5c'
REV='f37857bfdc67ac4e3ecb2851eb274aee7601057d'
UTC=timezone.utc
def instant(s):return datetime.fromisoformat(s.replace('Z','+00:00'))
def now():return datetime.now(UTC).isoformat()
def encoded(j):return json.dumps(j,separators=(',',':'),allow_nan=False).encode()
def gzwrite(p,j):
    p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(gzip.compress(encoded(j),mtime=0))
def number(s):return float(Decimal(s)) if s else None
def source_rows():
    assert sha(SOURCE/'nfl_graded_props_14d.csv.gz')==NFL_SHA
    total=0
    with gzip.open(SOURCE/'nfl_graded_props_14d.csv.gz','rt',newline='') as f:
        for index,r in enumerate(csv.DictReader(f),2):
            total+=sum(len(v.encode()) for v in r.values());assert total<134217728
            assert 'customer_token' not in r and not any('(Watermark)' in v for v in r.values())
            yield index,r
def prepare(inputs,roster,event_schedule):
    """Source/identity/coverage only; does not read or rank prediction values."""
    assert not (OUT/'ELIGIBLE_OFFERS.json').exists(),'FROZEN_INTAKE_EXISTS_USE_NEW_VERSION'
    import pandas as pd
    from data_v2 import load
    d,g,_=load(inputs);assert sha(inputs/'facts.csv.gz')=='9abc681265b6bec413de2d9002aa72ac19b1a48ea2e57d4f38698b1cc8717a11'
    panel=g[(g.season==2026)&(g.game_type=='REG')&g.week.between(1,7)];assert len(panel)==107
    with event_schedule.open() as f:native_games={r['game_id']:r for r in csv.DictReader(f)}
    native_schedule_hash=sha(event_schedule);roster_hash=sha(roster)
    games={};events={};groups=defaultdict(list);counts=Counter();books=Counter();cats=Counter();lines_differ=0
    for r in panel.to_dict('records'):
        key=(r['home_team'],r['away_team'],r['gameday']);assert key not in games;games[key]=r
    for index,r in source_rows():
        counts['raw_priced_side_rows']+=1;books[r['bookmaker']]+=1;cats[MARKETS.get(r['market'],'UNSUPPORTED')]+=1
        if r['line'] and r['closing_point'] and Decimal(r['line'])!=Decimal(r['closing_point']):lines_differ+=1
        key=(TEAMS.get(r['home_team']),TEAMS.get(r['away_team']),instant(r['commence_time']).astimezone(ZoneInfo('America/New_York')).date().isoformat());game=games.get(key)
        event=dict(source_event_id=r['event_id'],source_commence_UTC=r['commence_time'],source_home=r['home_team'],source_away=r['away_team'],game_id=game['game_id'] if game else None)
        if game:
            n=native_games[game['game_id']];assert all(str(game[k])==n[k] for k in ['gameday','home_team','away_team'])
            event.update(week=int(game['week']),espn_event_id=n['espn'],scheduled_kickoff_UTC=datetime.fromtimestamp(game['kickoff'],UTC).isoformat(),source_minus_scheduled_seconds=instant(r['commence_time']).timestamp()-game['kickoff'],native_schedule_SHA256=native_schedule_hash)
        if r['event_id'] in events:assert events[r['event_id']]==event
        events[r['event_id']]=event
        if r['bookmaker']=='pinnacle':groups[(r['event_id'],r['player_id'],r['market'])].append(dict(csv_line=index,**r))
    identities=defaultdict(set)
    with gzip.open(roster,'rt') as f:
        for r in csv.DictReader(f):
            if r['season']=='2026' and r['game_type']=='REG' and r['espn_id'] and r['gsis_id'] and r['week'] in ['2','3']:
                identities[(int(r['week']),r['espn_id'])].add((r['gsis_id'],r['team'],r['position']))
    cases=[];held=[];crosswalk={};stage=Counter()
    for (event_id,native,market),rs in sorted(groups.items()):
        why=[];e=events[event_id];stage['pinnacle_footballcase_candidates']+=1
        if not e['game_id']:why.append('EVENT_NOT_FIXED_PANEL')
        if market not in MARKETS:why.append('UNSUPPORTED_MARKET')
        if not native.startswith('espn:'):why.append('NATIVE_PLAYER_ID_MISSING')
        points={Decimal(r['closing_point']) for r in rs if r['closing_point']}
        if len(points)!=1:why.append('AMBIGUOUS_OR_MISSING_CLOSING_THRESHOLD')
        pair={}
        for side in ['Over','Under']:
            rr={digest({k:v for k,v in r.items() if k!='csv_line'}):r for r in rs if r['outcome_name']==side}
            if len(rr)!=1:why.append('MISSING_OR_CONFLICTING_'+side.upper())
            else:pair[side.upper()]=next(iter(rr.values()))
        if not why:
            cutoff=min(instant(e['source_commence_UTC']),instant(e['scheduled_kickoff_UTC']))
            if any(not r['closing_at'] or instant(r['closing_at'])>=cutoff for r in pair.values()):why.append('CLOSING_NOT_STRICTLY_BEFORE_BOTH_KICKOFFS')
            if any(not r['opening_at'] or instant(r['opening_at'])>instant(r['closing_at']) for r in pair.values()):why.append('CLOCK_ORDER_INVALID')
            if any(Decimal(r['closing_point'])!=next(iter(points)) for r in pair.values()):why.append('PAIRED_LINE_CONFLICT')
        ident=[]
        if e['game_id'] and native.startswith('espn:'):
            home,away=e['game_id'].split('_')[-2:]
            ident=[v for v in identities[(e['week'],native[5:])] if v[1] in [home,away]]
            if len(ident)!=1:why.append('HISTORICAL_NATIVE_ID_AMBIGUOUS_OR_MISSING')
            elif ident[0][2] not in ['QB','RB','WR','TE']:why.append('UNSUPPORTED_HISTORICAL_ROLE')
        if why:
            held.append(dict(source_event_id=event_id,native_player_id=native,market=market,csv_lines=[r['csv_line'] for r in rs],reasons=sorted(set(why))));continue
        player,team,position=ident[0];cat=MARKETS[market];oid='PL7-'+digest([event_id,native,market,'pinnacle',str(next(iter(points)))])[:24]
        crosswalk[(e['week'],native,player,team,position)]=dict(season=2026,week=e['week'],native_player_id=native,player_id=player,team=team,position=position,mapping='NFLVERSE_WEEKLY_ROSTER_REG_EXACT_ESPN_GSIS_TEAM_WEEK',source_roster_SHA256=roster_hash)
        cases.append(dict(offer_id=oid,category=cat,player_id=player,position=position,team=team,native_player_id=native,line=float(next(iter(points))),event=e,quotes=pair))
    OUT.mkdir(parents=True,exist_ok=True);gzwrite(SOURCE/'historical_identity_crosswalk.json.gz',list(crosswalk.values()))
    stable_write(OUT/'ELIGIBLE_OFFERS.json',dict(id=VERSION,registered_population='SOURCE_QUALITY_BEFORE_MODEL_PERFORMANCE',source_revision=REV,source_SHA256=NFL_SHA,events=list(events.values()),cases=cases,held=held))
    summary=dict(id=VERSION,created_UTC=now(),source_revision=REV,raw_priced_side_rows=counts['raw_priced_side_rows'],book_rows=dict(books),category_rows=dict(cats),source_events=len(events),matched_fixed_panel_events=sum(e['game_id'] is not None for e in events.values()),unmatched_events=[e for e in events.values() if not e['game_id']],weeks=dict(Counter(e.get('week') for e in events.values())),line_vs_closing_point_differences=lines_differ,source_kickoff_differences=sum(e.get('source_minus_scheduled_seconds',0)!=0 for e in events.values()),pinnacle_raw_rows=sum(len(v) for v in groups.values()),pinnacle_candidate_cases=len(groups),qualified_identity_snapshot_cases=len(cases),eligible_by_category=dict(Counter(c['category'] for c in cases)),held_cases=len(held),held_reason_counts=dict(Counter(s for r in held for s in r['reasons'])),eligible_offers_SHA256=sha(OUT/'ELIGIBLE_OFFERS.json'),model_performance_inspected=False,new_fits=0)
    stable_write(OUT/'INVENTORY.json',summary);return summary
def saved_models():
    """Restore only C-authored model bytes from hash-pinned existing GitHub archives."""
    manifest=json.loads((ROOT/'reports/GITHUB_EVIDENCE_MANIFEST_V2.json').read_text());models={};rows={};direct={};receipts=[]
    for cat in MARKETS.values():
        entry=next(e for e in manifest if e['category']==cat);archive=ROOT/entry['path'];assert sha(archive)==entry['sha256']
        with zipfile.ZipFile(archive) as z:
            for week in [2,3]:
                slot=f'C-ALL12-LAW-THRESHOLD-v2.1-{cat}-H-MULTI-P2_LEAF-E0_OP-W{week:02}'
                names={Path(n).name:n for n in z.namelist() if slot+'/' in n};done=json.loads(z.read(names['DONE.json']))
                rb=z.read(names['rows.json.gz']);mb=z.read(names['model.pkl.gz'])
                assert hashlib.sha256(rb).hexdigest()==done['row_sha256'] and hashlib.sha256(mb).hexdigest()==done['model_sha256']
                # These are our own previously published exact-hash models, NOT third-party inputs.
                fitted=pickle.loads(gzip.decompress(mb))['model'];model=export_forest(fitted)
                packet=json.loads(gzip.decompress(rb));x=np.asarray([r['features'] for r in packet],float);roles=np.asarray([r['position'] for r in packet])
                laws=infer_forest(model,x,roles)
                for r,l in zip(packet,laws):
                    assert abs(l.mean()-r['mean'])<1e-10 and l.quantile(.5)==r['median'],'SAVED_NUMERIC_INFERENCE_CHANGED'
                    assert all(abs(l.probability(line)['over']-p)<1e-10 for line,p in zip(r['grid'],r['p_over']))
                    key=(cat,r['game_id'],r['player_id']);assert key not in rows;rows[key]=r;models[key]=l
                safe=OUT/'models'/f'{cat}-W{week:02}.json.gz';gzwrite(safe,model)
                receipts.append(dict(slot=slot,family='P2_LEAF',source_archive=entry['path'],source_archive_SHA256=entry['sha256'],model_SHA256=done['model_sha256'],rows_SHA256=done['row_sha256'],numeric_model_path=safe.relative_to(ROOT).as_posix(),numeric_model_SHA256=sha(safe),origin_UTC=done['origin_UTC'],latest_training_available=done['latest_training_available'],saved_queries=len(packet),mean_median_grid_reinference='PASS',new_fits=0))
                slot=slot.replace('P2_LEAF','P3_HGB');names={Path(n).name:n for n in z.namelist() if slot+'/' in n};done=json.loads(z.read(names['DONE.json']));mb=z.read(names['model.pkl.gz']);rb=z.read(names['rows.json.gz'])
                assert hashlib.sha256(rb).hexdigest()==done['row_sha256'] and hashlib.sha256(mb).hexdigest()==done['model_sha256']
                fitted=pickle.loads(gzip.decompress(mb))['model'];packet=json.loads(gzip.decompress(rb))
                for r in packet:
                    key=(cat,r['game_id'],r['player_id']);assert r['features']==rows[key]['features'] and r['actual']==rows[key]['actual']
                    grid=np.floor(np.asarray(r['grid']));p=1-fitted.cdfs(np.asarray([r['features']],float),grid)[0]
                    assert np.allclose(p,r['p_over'],rtol=0,atol=1e-10)
                    direct[key]=(fitted,r)
                receipts.append(dict(slot=slot,family='P3_HGB',source_archive=entry['path'],source_archive_SHA256=entry['sha256'],model_SHA256=done['model_sha256'],rows_SHA256=done['row_sha256'],origin_UTC=done['origin_UTC'],latest_training_available=done['latest_training_available'],saved_queries=len(packet),grid_reinference='PASS',direct_training='ORIGINAL_SYNTHETIC_THRESHOLDS; no fitted real-line calibration',new_fits=0))
    return models,rows,direct,receipts
def predict_offer(offer,method,r=None,law=None,direct_item=None):
    # Deliberately accepts no outcome table; source resolution/finals are not predictors.
    line=offer.get('line')
    if line is None:return None,dict(point=None,point_type='MEAN' if method=='P1_MEAN' else 'MEDIAN') if method.startswith('P1') else {}
    assert np.isfinite(line)
    ps=law.probability(line) if law else None
    side=None;extra={}
    if method.startswith('P1'):
        point=r['median' if method=='P1_MEDIAN' else 'mean'] if r else None;side=point_side(point,line);side=None if side=='UNAVAILABLE' else side;extra=dict(point=point,point_type='MEDIAN' if method=='P1_MEDIAN' else 'MEAN')
    elif method=='P2_LAW' and law:
        side='ABSTAIN' if abs(ps['over']-ps['under'])<=1e-12 else 'OVER' if ps['over']>ps['under'] else 'UNDER'
        extra=dict(law=law_data(law),probability_line=line,**{'p_'+s:v for s,v in ps.items()},information_set_id=r['slot']+':'+r['game_id']+':'+r['player_id'],probability_inference_evidence_reference='reports/propline-v7/MODEL_REPLAY.json')
    elif method=='P3_DIRECT' and direct_item is not None:
        fitted,dr=direct_item;lo,hi,on_grid=thresholds_for_line(line,1);cp=fitted.cdfs(np.asarray([dr['features']],float),np.asarray([lo,hi]))[0];dp=dict(under=float(cp[0]),push=float(cp[1]-cp[0]),over=float(1-cp[1]));assert min(dp.values())>=-1e-12
        side='ABSTAIN' if abs(dp['over']-dp['under'])<=1e-12 else 'OVER' if dp['over']>dp['under'] else 'UNDER'
        extra=dict(probability_line=line,**{'p_'+s:v for s,v in dp.items()},information_set_id=dr['slot']+':'+dr['game_id']+':'+dr['player_id'],probability_inference_evidence_reference='reports/propline-v7/MODEL_REPLAY.json',real_line_calibration='NOT_FITTED',direct_training='SYNTHETIC_GRID',training_threshold_range=[float(min(fitted.thresholds)),float(max(fitted.thresholds))],outside_training_threshold_range=bool(lo<min(fitted.thresholds) or hi>max(fitted.thresholds)))
    elif method.startswith('ALWAYS'):side='OVER' if method=='ALWAYS_OVER' else 'UNDER'
    return side,extra

def evaluate(inputs):
    """Run the frozen population; outcome columns are used only after prediction."""
    assert not (OUT/'GRADED_ROWS.json').exists(),'FROZEN_GRADES_EXIST_USE_NEW_VERSION'
    from data_v2 import load
    start=time.monotonic();assert sha(inputs/'facts.csv.gz')=='9abc681265b6bec413de2d9002aa72ac19b1a48ea2e57d4f38698b1cc8717a11'
    assert sha(inputs/'schedule.csv')=='5ac3af003131a316eadba4bf90f9758953cef7a41bb6359fb5eb7d90d8a170f0'
    d,_,_=load(inputs);facts={(r['game_id'],r['player_id']):r for r in d.to_dict('records')};models,saved,direct,receipts=saved_models()
    intake=json.loads((OUT/'ELIGIBLE_OFFERS.json').read_text());cases=intake['cases'];assert sha(OUT/'ELIGIBLE_OFFERS.json')==json.loads((OUT/'INVENTORY.json').read_text())['eligible_offers_SHA256']
    out=[];comparison=[];forecast_evidence=[];used=set()
    for c in cases:
        cat=c['category'];e=c['event'];key=(cat,e['game_id'],c['player_id']);r=saved.get(key);fact=facts.get((e['game_id'],c['player_id']))
        actual=fact['values'][cat] if fact else None;appearance='PLAYED' if fact and fact['played'] and fact['game_final'] else 'UNKNOWN'
        if r:
            assert r['position']==c['position'] and r['team']==c['team'] and r['actual']==actual
            assert instant(r['as_of_UTC'])==instant(e['scheduled_kickoff_UTC'])
            if key not in used:forecast_evidence.append(r);used.add(key)
        law=models.get(key);ps=law.probability(c['line']) if law else None
        provider=[]
        for side,q in c['quotes'].items():
            provider.append(dict(side=side,source_resolution=q['resolution'],provider_actual=number(q['actual_value']),independent_actual=actual,provider_actual_agrees=None if actual is None or not q['actual_value'] else Decimal(q['actual_value'])==Decimal(str(actual)),statistical_grade_at_general_line=grade(actual,number(q['line']),side) if actual is not None and q['line'] else None,statistical_grade_at_closing_point=grade(actual,c['line'],side) if actual is not None else None,csv_line=q['csv_line']))
        comparison.append(dict(offer_id=c['offer_id'],game_id=e['game_id'],player_id=c['player_id'],category=cat,forecast_available=r is not None,appearance=appearance,provider_rows=provider))
        for method in ['P1_MEDIAN','P1_MEAN','P2_LAW','P3_DIRECT','ALWAYS_OVER','ALWAYS_UNDER']:
            side,extra=predict_offer(c,method,r,law,direct.get(key))
            status='UNAVAILABLE_FORECAST' if side is None else 'ABSTAIN' if side=='ABSTAIN' else 'UNKNOWN_PARTICIPATION' if appearance!='PLAYED' else 'MISSING_ACTUAL' if actual is None else grade(actual,c['line'],side)
            record_id=c['offer_id']+'-'+method
            row=dict(record_kind='ACTUAL_OFFER',record_id=record_id,grade_id=record_id+'-STAT-G1',offer_id=c['offer_id'],category=cat,method_id=method,method_version=method_version(cat,method,'2026_W1_W7'),selector_id='P2_EXACT_LINE_SELECTOR-v4.1' if method=='P2_LAW' else method+'-strict-v6',policy_id='ALL_ELIGIBLE_OFFERS',game_id=e['game_id'],player_id=c['player_id'],player_name=c['quotes']['OVER']['player_name'],espn_event_id=e['espn_event_id'],season=2026,week=e['week'],season_type='REG',position=c['position'],role_evidence_reference='sources/propline-v7/historical_identity_crosswalk.json.gz',scoring_contract_id='official-player-fullgame-OT-v1',scoring_snapshot_id=c['offer_id']+'-CLOSING',evidence_tier=TIERS[2],decision_horizon='SAVED_KICKOFF_RECONSTRUCTION_VS_LAST_RECORDED_PREKICK_CLOSE',venue='pinnacle',product='SPORTSBOOK_PLAYER_PROP',line_tier='UNVERIFIED_MAIN_ALTERNATE',period='FULL_GAME_INCLUDING_OT',line=c['line'],comparator='STRICT_OVER_UNDER',offered_sides=['OVER','UNDER'],selected_side=side,status=status,actual=actual,appearance=appearance,decision_UTC=e['scheduled_kickoff_UTC'],kickoff_UTC=e['scheduled_kickoff_UTC'],graded_UTC=now(),outcome_evidence_reference='artifacts/basic-football-facts-v2.1.zip#facts.csv.gz',source_offer_evidence_reference='reports/propline-v7/ELIGIBLE_OFFERS.json',source_snapshot_clocks={s:q['closing_at'] for s,q in c['quotes'].items()},source_event_commence_UTC=e['source_commence_UTC'],forecast_id=r['slot']+':'+r['game_id']+':'+r['player_id'] if r else None,forecast_information_tier='CURRENT_REVISED_7DAY_RECONSTRUCTION' if r else None,forecast_generated_UTC=r['generated_UTC'] if r else None,conditioning='RETROSPECTIVE_PARTICIPANT_STAT_ROW_PANEL;STATISTICAL_PLAYED',venue_settlement='UNVERIFIED',fallback=r['fallback'] if r else None,**extra)
            if method=='P3_DIRECT':row['method_version']='C-ALL12-LAW-THRESHOLD-v2.1/P3_HGB/H-MULTI/E0_OP/P3_DIRECT'
            validate_row(row);out.append(row)
    gzwrite(OUT/'MATCHED_SAVED_FORECASTS.json.gz',forecast_evidence);stable_write(OUT/'MODEL_REPLAY.json',dict(models=receipts,new_fits=0,matched_saved_forecasts=len(used),forecast_values_unchanged=True));stable_write(OUT/'PROVIDER_GRADE_COMPARISON.json',comparison)
    paths=['sources/propline-v7/nfl_graded_props_14d.csv.gz','sources/propline-v7/card_pinned.md','sources/propline-v7/historical_identity_crosswalk.json.gz','sources/propline-v7/event_native_schedule.json.gz','reports/propline-v7/ELIGIBLE_OFFERS.json','reports/propline-v7/MODEL_REPLAY.json','reports/propline-v7/MATCHED_SAVED_FORECASTS.json.gz','artifacts/basic-football-facts-v2.1.zip']+[r['numeric_model_path'] for r in receipts if r['family']=='P2_LEAF']+sorted(set(r['source_archive'] for r in receipts))
    evidence=[dict(path=p,SHA256=sha(ROOT/p)) for p in paths]
    data=dict(schema='C-QUALIFIED-ACTUAL-PROP-ROWS-v6',source_review_id='C-PROPLINE-CCBY-SAMPLE-v7',retained_evidence=evidence,rows=out)
    stable_write(OUT/'GRADED_ROWS.json',data)
    summary=dict(id=VERSION,completed_UTC=now(),eligible_offers=len(cases),unique_matched_predictions=len(used),method_rows=len(out),method_status_counts={m:dict(Counter(r['status'] for r in out if r['method_id']==m)) for m in sorted({r['method_id'] for r in out})},new_fits=0,model_refits=0,restored_models=len(receipts),source_downloads=1,source_odds_endpoint_calls=0,wall_seconds=time.monotonic()-start,peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024)
    stable_write(OUT/'RUN_RECEIPT.json',summary);return summary

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['inventory','evaluate']);p.add_argument('--inputs',type=Path,required=True);p.add_argument('--roster',type=Path);p.add_argument('--event-schedule',type=Path);a=p.parse_args();print(json.dumps(prepare(a.inputs,a.roster,a.event_schedule) if a.command=='inventory' else evaluate(a.inputs),indent=2))
