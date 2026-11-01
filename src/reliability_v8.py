"""Frozen-book intake and selected-side diagnostics; no provider acquisition.

Full evidence uses deterministic gzip. Original v7 data is read-only.
"""
import argparse,csv,gzip,hashlib,io,json,math,pickle,time,zipfile
from collections import Counter,defaultdict
from datetime import datetime,timezone
from decimal import Decimal
from pathlib import Path
import numpy as np
from scipy.special import expit
from sklearn.metrics import roc_auc_score,average_precision_score
import actual_accuracy_v6 as a
from propline_v7 import source_rows,MARKETS,REV,NFL_SHA,predict_offer
from safe_models_v4 import infer_forest,law_data,law_load
from contracts_v2 import CATEGORIES,integer,grade,thresholds_for_line
from data_v2 import PHYSICAL

ROOT=a.ROOT;OUT=ROOT/'reports/reliability-v8';ART=ROOT/'artifacts/reliability-v8'
def now():return datetime.now(timezone.utc).isoformat()
def read(p):
    p=Path(p);return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes())
def write(p,j):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);b=json.dumps(j,separators=(',',':'),allow_nan=False).encode()+b'\n';p.write_bytes(gzip.compress(b,mtime=0) if p.suffix=='.gz' else b)
def key(r):return (r['category'],r['game_id'],r['player_id'])
def inventory(roster):
    dest=ART/'BOOK_CASES.json.gz';assert not dest.exists(),'FROZEN_INVENTORY_EXISTS'
    events={e['source_event_id']:e for e in read(ROOT/'reports/propline-v7/ELIGIBLE_OFFERS.json')['events']};ident=defaultdict(set)
    with gzip.open(roster,'rt') as f:
        for r in csv.DictReader(f):
            if r['season']=='2026' and r['week'] in ['2','3'] and r['game_type']=='REG' and r['espn_id'] and r['gsis_id']:ident[(int(r['week']),r['espn_id'])].add((r['gsis_id'],r['team'],r['position']))
    groups=defaultdict(list);raw=Counter();skipped=Counter()
    for i,r in source_rows():
        if r['bookmaker'] not in ['draftkings','fanduel']:continue
        book=r['bookmaker'];raw[book]+=1
        if r['outcome_name'] not in ['Over','Under']:skipped[book]+=1;continue
        groups[(book,r['event_id'],r['player_id'],r['market'])].append(dict(csv_line=i,**r))
    cases=[];held=[];cross={}
    for (book,event,native,market),rs in sorted(groups.items()):
        why=[];e=events.get(event);pair={}
        if e is None or not e['game_id']:why.append('EVENT_NOT_FIXED_PANEL')
        if market not in MARKETS:why.append('UNSUPPORTED_MARKET')
        if not native.startswith('espn:'):why.append('NATIVE_PLAYER_ID_MISSING')
        points={Decimal(r['closing_point']) for r in rs if r['closing_point']}
        if len(points)!=1:why.append('AMBIGUOUS_OR_MISSING_CLOSING_THRESHOLD')
        for side in ['Over','Under']:
            rr={a.digest({k:v for k,v in r.items() if k!='csv_line'}):r for r in rs if r['outcome_name']==side}
            if len(rr)!=1:why.append('MISSING_OR_CONFLICTING_'+side.upper())
            else:pair[side.upper()]=next(iter(rr.values()))
        if not why:
            cutoff=min(a.instant(e['source_commence_UTC']),a.instant(e['scheduled_kickoff_UTC']))
            if any(not r['closing_at'] or a.instant(r['closing_at'])>=cutoff for r in pair.values()):why.append('CLOSING_NOT_STRICTLY_BEFORE_BOTH_KICKOFFS')
            if any(not r['opening_at'] or a.instant(r['opening_at'])>a.instant(r['closing_at']) for r in pair.values()):why.append('CLOCK_ORDER_INVALID')
            if any(not r['closing_point'] or Decimal(r['closing_point'])!=next(iter(points)) for r in pair.values()):why.append('PAIRED_LINE_CONFLICT')
        ids=[]
        if e and native.startswith('espn:'):
            ids=[v for v in ident[(e['week'],native[5:])] if v[1] in e['game_id'].split('_')[-2:]]
            if len(ids)!=1:why.append('HISTORICAL_NATIVE_ID_AMBIGUOUS_OR_MISSING')
            elif ids[0][2] not in ['QB','RB','WR','TE']:why.append('UNSUPPORTED_HISTORICAL_ROLE')
        if why:held.append(dict(book=book,source_event_id=event,native_player_id=native,market=market,csv_lines=[r['csv_line'] for r in rs],reasons=sorted(set(why))));continue
        pid,team,position=ids[0];cat=MARKETS[market];oid='PL8-'+a.digest([book,event,native,market,str(next(iter(points)))])[:24]
        cases.append(dict(offer_id=oid,venue=book,category=cat,player_id=pid,position=position,team=team,native_player_id=native,line=float(next(iter(points))),event=e,quotes=pair))
        cross[(e['week'],native)]=dict(week=e['week'],native_player_id=native,player_id=pid,team=team,position=position,source_roster_SHA256=a.sha(roster))
    assert len(cases)<=2000
    payload=dict(id='C-BOOK-ROBUSTNESS-v8',source_revision=REV,source_SHA256=NFL_SHA,created_UTC=now(),cases=cases,held=held,performance_inspected=False)
    write(dest,payload);write(ART/'IDENTITY_CROSSWALK.json.gz',list(cross.values()))
    report=dict(id=payload['id'],created_UTC=payload['created_UTC'],book_rows=dict(raw),non_Over_Under_rows_excluded=dict(skipped),candidate_cases=dict(Counter(k[0] for k in groups)),qualified_cases=dict(Counter(c['venue'] for c in cases)),qualified_by_book_category={b:dict(Counter(c['category'] for c in cases if c['venue']==b)) for b in raw},held_cases=dict(Counter(h['book'] for h in held)),held_reason_counts={b:dict(Counter(v for h in held if h['book']==b for v in h['reasons'])) for b in raw},case_bytes_SHA256=a.sha(dest),source_quality_only=True,unknown_market_OPEN_state=True,performance_inspected=False)
    write(OUT/'BOOK_INVENTORY.json',report);return report

def hgb_export(m):
    trees=[]
    for stage in m.model._predictors:
        assert len(stage)==1;t=stage[0].nodes;assert not np.any(t['is_categorical'])
        trees.append({k:t[k].tolist() for k in ['value','feature_idx','num_threshold','missing_go_to_left','left','right','is_leaf']})
    return dict(schema='C-NUMERIC-HGB-CDF-v8',imputation=m.m.tolist(),baseline=float(m.model._baseline_prediction[0,0]),trees=trees,thresholds=m.thresholds.tolist())
def hgb_cdf(m,features,thresholds):
    x=np.asarray(features,float);med=np.asarray(m['imputation']);z=np.r_[np.where(np.isfinite(x),x,med),~np.isfinite(x)];out=[]
    for threshold in thresholds:
        row=np.r_[z,threshold];value=m['baseline']
        for tree in m['trees']:
            n=0
            for _ in range(8):
                if tree['is_leaf'][n]:break
                v=row[tree['feature_idx'][n]];left=bool(tree['missing_go_to_left'][n]) if np.isnan(v) else v<=tree['num_threshold'][n];n=tree['left'][n] if left else tree['right'][n]
            else:raise ValueError('TREE_DEPTH_OR_CYCLE')
            value+=tree['value'][n]
        out.append(float(expit(value)))
    return out
def references():
    path=ART/'REFERENCE_BANK.json.gz'
    if path.exists():return read(path)
    manifest=read(ROOT/'reports/GITHUB_EVIDENCE_MANIFEST_V2.json');bank={};meta=[];safe={}
    for cat in MARKETS.values():
        entry=next(e for e in manifest if e['category']==cat);assert a.sha(ROOT/entry['path'])==entry['sha256']
        with zipfile.ZipFile(ROOT/entry['path']) as z:
            for w in [2,3]:
                slot=f'C-ALL12-LAW-THRESHOLD-v2.1-{cat}-H-MULTI-P2_LEAF-E0_OP-W{w:02}';names={Path(n).name:n for n in z.namelist() if slot+'/' in n};done=json.loads(z.read(names['DONE.json']));b=z.read(names['rows.json.gz']);assert hashlib.sha256(b).hexdigest()==done['row_sha256'];rr=json.loads(gzip.decompress(b))
                model=read(ROOT/f'reports/propline-v7/models/{cat}-W{w:02}.json.gz');laws=infer_forest(model,np.asarray([r['features'] for r in rr],float),[r['position'] for r in rr])
                for r,law in zip(rr,laws):
                    assert abs(law.mean()-r['mean'])<1e-10 and law.quantile(.5)==r['median'];bank['|'.join([cat,r['game_id'],r['player_id']])]=dict(saved=r,law=law_data(law),fit_origin_UTC=done['origin_UTC'])
                direct=slot.replace('P2_LEAF','P3_HGB');names={Path(n).name:n for n in z.namelist() if direct+'/' in n};dd=json.loads(z.read(names['DONE.json']));mb=z.read(names['model.pkl.gz']);rb=z.read(names['rows.json.gz']);assert hashlib.sha256(mb).hexdigest()==dd['model_sha256'] and hashlib.sha256(rb).hexdigest()==dd['row_sha256']
                # Only our own previously hash-pinned, independently audited C model is read.
                # Third-party/user pickle input is never accepted; persisted inference is numeric.
                fitted=pickle.loads(gzip.decompress(mb))['model'];numeric=hgb_export(fitted);safe[direct]=numeric
                for r in json.loads(gzip.decompress(rb)):
                    item=bank['|'.join([cat,r['game_id'],r['player_id']])];assert r['features']==item['saved']['features']
                    p=1-np.asarray(hgb_cdf(numeric,r['features'],np.floor(r['grid'])));assert np.allclose(p,r['p_over'],rtol=0,atol=1e-10);item['direct_model_id']=direct
                meta.append(dict(category=cat,week=w,source_archive=entry['path'],source_archive_SHA256=entry['sha256'],rows_SHA256=done['row_sha256'],direct_model_SHA256=dd['model_sha256'],direct_rows_SHA256=dd['row_sha256'],fit_origin_UTC=done['origin_UTC'],saved_grid_and_point_parity=True))
    data=dict(schema='C-SAFE-REFERENCE-BANK-v8',references=bank,direct_models=safe,provenance=meta,new_fits=0);write(path,data);return data

def independent_facts(inputs):
    assert a.sha(inputs/'facts.csv.gz')=='9abc681265b6bec413de2d9002aa72ac19b1a48ea2e57d4f38698b1cc8717a11'
    with gzip.open(inputs/'facts.csv.gz','rt') as f:facts={(r['game_id'],r['player_id']):r for r in csv.DictReader(f)}
    with (inputs/'schedule.csv').open() as f:games={r['game_id']:r for r in csv.DictReader(f)}
    return facts,games
def label(fact,game,cat):
    if not fact:return None,'UNKNOWN'
    proof=[integer(fact.get(c),c.endswith('_yards')) for c in PHYSICAL+['passing_yards','rushing_yards','receiving_yards']]
    played=any(v is not None and v>0 for v in proof[:len(PHYSICAL)]) or any(v not in [None,0] for v in proof[len(PHYSICAL):]);final=game['home_score']!='' and game['away_score']!=''
    return (integer(fact.get(CATEGORIES[cat][1]),CATEGORIES[cat][2]=='signed'),'PLAYED') if played and final else (None,'UNKNOWN')

def evaluate(inputs):
    dest=ART/'BOOK_GRADED_ROWS.json.gz';assert not dest.exists(),'FROZEN_GRADES_EXIST'
    payload=read(ART/'BOOK_CASES.json.gz');assert a.sha(ART/'BOOK_CASES.json.gz')==read(OUT/'BOOK_INVENTORY.json')['case_bytes_SHA256'];refs=references();facts,games=independent_facts(inputs);rows=[]
    for c in payload['cases']:
        e=c['event'];ref=refs['references'].get('|'.join([c['category'],e['game_id'],c['player_id']]));r=ref['saved'] if ref else None
        if r and (r['position']!=c['position'] or r['team']!=c['team']):r=None
        actual,appearance=label(facts.get((e['game_id'],c['player_id'])),games[e['game_id']],c['category']);law=law_load(ref['law']) if r else None
        if r:assert r['actual']==actual
        for method in ['P1_MEDIAN','P1_MEAN','P2_LAW','P3_DIRECT','ALWAYS_OVER','ALWAYS_UNDER']:
            side,extra=predict_offer(c,method,r,law) if method!='P3_DIRECT' else (None,{})
            if method=='P3_DIRECT' and r:
                lo,hi,_=thresholds_for_line(c['line'],1);cp=hgb_cdf(refs['direct_models'][ref['direct_model_id']],r['features'],[lo,hi]);ps=dict(under=cp[0],push=cp[1]-cp[0],over=1-cp[1]);side='ABSTAIN' if abs(ps['over']-ps['under'])<=1e-12 else 'OVER' if ps['over']>ps['under'] else 'UNDER';extra=dict(**{'p_'+k:v for k,v in ps.items()},probability_line=c['line'],information_set_id=ref['direct_model_id']+':'+r['game_id']+':'+r['player_id'],probability_inference_evidence_reference='artifacts/reliability-v8/REFERENCE_BANK.json.gz',direct_training='ORIGINAL_SYNTHETIC_THRESHOLDS;UNTRANSLATED_EXACT_CDF',real_line_calibration='NOT_FITTED')
            status='UNAVAILABLE_FORECAST' if side is None else 'ABSTAIN' if side=='ABSTAIN' else 'UNKNOWN_PARTICIPATION' if appearance!='PLAYED' else 'MISSING_ACTUAL' if actual is None else grade(actual,c['line'],side)
            rid=c['offer_id']+'-'+method;version=a.method_version(c['category'],method,'2026_W1_W7')
            if method=='P3_DIRECT':version='C-ALL12-LAW-THRESHOLD-v2.1/P3_HGB/H-MULTI/E0_OP/P3_DIRECT'
            row=dict(record_kind='ACTUAL_OFFER',record_id=rid,grade_id=rid+'-STAT-G1',offer_id=c['offer_id'],category=c['category'],method_id=method,method_version=version,selector_id='P2_EXACT_LINE_SELECTOR-v4.1' if method=='P2_LAW' else method+'-strict-v6',policy_id='ALL_ELIGIBLE_OFFERS',game_id=e['game_id'],player_id=c['player_id'],player_name=c['quotes']['OVER']['player_name'],espn_event_id=e['espn_event_id'],season=2026,week=e['week'],season_type='REG',position=c['position'],role_evidence_reference='artifacts/reliability-v8/IDENTITY_CROSSWALK.json.gz',scoring_contract_id='official-player-fullgame-OT-v1',scoring_snapshot_id=c['offer_id']+'-CLOSING',evidence_tier=a.TIERS[2],decision_horizon='SAVED_KICKOFF_RECONSTRUCTION_VS_LAST_RECORDED_PREKICK_CLOSE',venue=c['venue'],product='SPORTSBOOK_PLAYER_PROP',line_tier='UNVERIFIED_MAIN_ALTERNATE',period='FULL_GAME_INCLUDING_OT',line=c['line'],comparator='STRICT_OVER_UNDER',offered_sides=['OVER','UNDER'],selected_side=side,status=status,actual=actual,appearance=appearance,decision_UTC=e['scheduled_kickoff_UTC'],kickoff_UTC=e['scheduled_kickoff_UTC'],graded_UTC=now(),outcome_evidence_reference='artifacts/basic-football-facts-v2.1.zip#facts.csv.gz',source_offer_evidence_reference='artifacts/reliability-v8/BOOK_CASES.json.gz',source_snapshot_clocks={s:q['closing_at'] for s,q in c['quotes'].items()},source_event_commence_UTC=e['source_commence_UTC'],forecast_id=r['slot']+':'+r['game_id']+':'+r['player_id'] if r else None,forecast_information_tier='CURRENT_REVISED_7DAY_RECONSTRUCTION' if r else None,forecast_generated_UTC=r['generated_UTC'] if r else None,conditioning='RETROSPECTIVE_PARTICIPANT_STAT_ROW_PANEL;STATISTICAL_PLAYED',venue_settlement='UNVERIFIED',fallback=r['fallback'] if r else None,**extra)
            a.validate_row(row);rows.append(row)
    paths=['sources/propline-v7/nfl_graded_props_14d.csv.gz','sources/propline-v7/card_pinned.md','artifacts/basic-football-facts-v2.1.zip','artifacts/reliability-v8/REFERENCE_BANK.json.gz','artifacts/reliability-v8/BOOK_CASES.json.gz','artifacts/reliability-v8/IDENTITY_CROSSWALK.json.gz']
    write(dest,dict(schema='C-QUALIFIED-ACTUAL-PROP-ROWS-v6',source_review_id='C-PROPLINE-CCBY-BOOKS-v8',retained_evidence=[dict(path=p,SHA256=a.sha(ROOT/p)) for p in paths],rows=rows))
    result=dict(id='C-BOOK-ROBUSTNESS-v8',new_fits=0,graded_rows=len(rows),per_book={book:{m:dict(Counter(r['status'] for r in rows if r['venue']==book and r['method_id']==m)) for m in ['P2_LAW','P3_DIRECT']} for book in ['draftkings','fanduel']});write(OUT/'BOOK_RUN.json',result);return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['inventory','evaluate']);p.add_argument('--inputs',type=Path);p.add_argument('--roster',type=Path);x=p.parse_args();print(json.dumps(inventory(x.roster) if x.stage=='inventory' else evaluate(x.inputs),indent=2))
