"""Finite C-owned receiver information comparisons; no unsafe model loading."""
import argparse
import gzip
import hashlib
import json
import math
import resource
import signal
import time
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

import actual_accuracy_v6 as accuracy
from contracts_v2 import thresholds_for_line
from data_v2 import load, History, vector
from laws_v2 import ThresholdModel
from receiving_information_v10 import ReceivingInformation, team_projection, feature_schema
from reliability_v8 import hgb_export, hgb_cdf
from wave_v2 import GRIDS, clean as original_clean

ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/'artifacts/predictive-C01'
OUT=ROOT/'reports/predictive-C01'


def clean(value):
    # Preserve numeric feature vectors without changing any fitted model.
    if isinstance(value,np.ndarray):return clean(value.tolist())
    if isinstance(value,dict):return {str(k):clean(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [clean(v) for v in value]
    return original_clean(value)


def now():return datetime.now(timezone.utc).isoformat()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
    p=Path(p);b=p.read_bytes()
    return json.loads(gzip.decompress(b) if p.suffix=='.gz' else b)
def write(p,obj):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    b=(json.dumps(clean(obj),separators=(',',':'),allow_nan=False)+'\n').encode()
    p.write_bytes(gzip.compress(b,mtime=0) if p.suffix=='.gz' else b)


def probabilities(model,features,line,count_support=True):
    under_at,over_at,_=thresholds_for_line(line,1)
    # F(under_at)=P(Y<line); F(over_at)=P(Y<=line), on the integer lattice.
    f=hgb_cdf(model,features,[under_at,over_at])
    if count_support:
        f=[0. if k<0 else v for k,v in zip([under_at,over_at],f)]
    p=dict(under=f[0],push=max(0.,f[1]-f[0]),over=1-f[1])
    assert min(p.values())>=-1e-12 and abs(sum(p.values())-1)<1e-12
    return p


def prepare():
    """Project only already qualified C football/offer evidence; no new source GET."""
    bank=read(ROOT/'artifacts/reliability-v8/REFERENCE_BANK.json.gz')
    models={k:v for k,v in bank['direct_models'].items() if '-rec-' in k}
    refs={k:dict(saved=dict(features=v['saved']['features']),fit_origin_UTC=v['fit_origin_UTC']) for k,v in bank['references'].items() if k.startswith('rec|')}
    assert len(models)==2
    write(ART/'REUSED_REFERENCE.json.gz',dict(source='artifacts/reliability-v8/REFERENCE_BANK.json.gz',source_SHA256=sha(ROOT/'artifacts/reliability-v8/REFERENCE_BANK.json.gz'),direct_models=models,references=refs,new_fits=0))
    del bank
    rows,_=accuracy.load_records();cases={}
    for r in rows:
        if r['venue']=='pinnacle' and r['category']=='rec' and r['season']==2026 and r['week'] in [2,3]:
            if r['offer_id'] not in cases:
                cases[r['offer_id']]={k:r.get(k) for k in ['offer_id','game_id','player_id','category','position','team','line','week','season','actual','appearance','decision_UTC','scoring_contract_id','evidence_tier','venue','product','line_tier']}
            cases[r['offer_id']].setdefault('retained_methods',{})[r['method_id']]={k:r.get(k) for k in ['selected_side','status','point','p_over','p_under','p_push','method_version']}
    assert len(cases)==362
    write(ART/'APPROVED_OFFER_CASES.json.gz',dict(source='Pinned C corrected PropLine f37857 sample;CCBY4;fullgameOTstatistical,booksettlementunverified',cases=list(cases.values()),new_source_rows=0))
    write(OUT/'INPUT_SCHEMA.json',feature_schema())


def storage_guard():
    roots=[ROOT]+[p for p in Path('/workspace').iterdir() if p.is_dir() and p.name.startswith('c-')]
    total=sum(f.stat().st_size for p in roots for f in p.rglob('*') if f.is_file())
    assert total<=2684354560, 'EXISTING_WHOLE_C_RETENTION_CAP'
    return total


def old_points(season,week):
    if season==2025:
        e=next(x for x in read(ROOT/'reports/robustness-v3/GITHUB_RESTORE.json')['archives'] if x['category']=='rec')
        path=e['archive'];expected=e['SHA256'];prefix=f'raw/rec/W{week:02}'
    else:
        e=next(x for x in read(ROOT/'reports/GITHUB_EVIDENCE_MANIFEST_V2.json') if x['category']=='rec')
        path=e['path'];expected=e['sha256'];prefix=f'C-ALL12-LAW-THRESHOLD-v2.1-rec-H-MULTI-P2_LEAF-E0_OP-W{week:02}'
    assert sha(ROOT/path)==expected
    with zipfile.ZipFile(ROOT/path) as z:
        done=json.loads(z.read(prefix+'/DONE.json'));b=z.read(prefix+'/rows.json.gz')
        assert hashlib.sha256(b).hexdigest()==done['row_sha256']
        return json.loads(gzip.decompress(b)),dict(path=path,SHA256=expected,prefix=prefix,rows_SHA256=done['row_sha256'])


def run(inputs,study,stage):
    protocol=read(ROOT/('protocol/RECEIVING_TARGETSHARE_V10.json' if study=='share' else 'protocol/TEAM_COMPLETION_CONTEXT_V11.json'))
    assert sha(inputs/'facts.csv.gz')=='9abc681265b6bec413de2d9002aa72ac19b1a48ea2e57d4f38698b1cc8717a11'
    assert sha(inputs/'schedule.csv')=='5ac3af003131a316eadba4bf90f9758953cef7a41bb6359fb5eb7d90d8a170f0'
    if study=='share':
        origins=protocol['primary_origins'] if stage=='original' else protocol['actual_line_extension']['origins']
        cap=4;cpu_cap=120;arms=['S0','S1'];base_arm='E0_ENV'
    else:
        assert (OUT/'share-original-RUN.json').exists() and read(OUT/'share-original-RUN.json')['completed_origins']==2
        origins=protocol['origins'];cap=10;cpu_cap=240;arms=['C0','C1','C2'];base_arm='E0_OP'
    out=ART/(study+'-'+stage);out.mkdir(parents=True,exist_ok=True)
    ledger_path=out/'FIT_LEDGER.json';ledger=read(ledger_path) if ledger_path.exists() else dict(fit_attempts=0,completed=[],failures=[],CPU_seconds=0.,wall_seconds=0.)
    assert not (out/'PREDICTIONS.json.gz').exists(),'COMPLETED_PREDICTIONS_FROZEN_DO_NOT_RERUN'
    start=time.monotonic();cpu=time.process_time()
    signal.signal(signal.SIGPROF,lambda *_:(_ for _ in ()).throw(RuntimeError('REGISTERED_CPU_CAP')))
    signal.setitimer(signal.ITIMER_PROF,max(.1,cpu_cap-ledger['CPU_seconds']))
    try:
        reused=read(ART/'REUSED_REFERENCE.json.gz');cases=read(ART/'APPROVED_OFFER_CASES.json.gz')['cases']
        d,g,teams=load(inputs);raw=pd.read_csv(inputs/'facts.csv.gz',low_memory=False)
        completion_teams=team_projection(raw,g);del raw
        info=ReceivingInformation(d,completion_teams)
        hist,teamhist=History(d[d.season>=2022],'player_id'),History(teams[teams.season>=2022],'team')
        identity=['game_id','player_id','team','opponent_team','position','season','week','home_team','kickoff','available','values','played']
        pool=d.loc[d.position.isin(['RB','WR','TE']),identity].to_dict('records')
        key=lambda r:(r['game_id'],r['player_id'])
        lookup={key(r):r for r in pool};schedule={r['game_id']:r for r in g.to_dict('records')}
        for c in cases:
            if key(c) not in lookup:
                gg=schedule[c['game_id']];team=c['team']
                q=dict(game_id=c['game_id'],player_id=c['player_id'],team=team,opponent_team=gg['away_team'] if team==gg['home_team'] else gg['home_team'],position=c['position'],season=2026,week=c['week'],home_team=gg['home_team'],kickoff=gg['kickoff'],available=gg['kickoff']+7*86400,values={'rec':None},played=False)
                assert q['position'] in ['RB','WR','TE'];pool.append(q);lookup[key(q)]=q
        base=np.asarray([vector(r,'rec',hist,teamhist,base_arm) for r in pool],float)
        extra=[info.share(r) if study=='share' else info.completion(r) for r in pool]
        support=np.asarray([x[0] for x in extra],float);values=np.asarray([x[1] for x in extra],float)
        matrices={'S0':np.column_stack([base,support]),'S1':np.column_stack([base,support,values])} if study=='share' else {'C0':base,'C1':np.column_stack([base,support]),'C2':np.column_stack([base,support,values])}
        assert resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024<=805306368,'RSS_PREFIT_CAP'
        storage_guard()
        index={key(r):i for i,r in enumerate(pool)};allrows=[];features=[];receipts=[]
        for origin in origins:
            season,week=origin['season'],origin['week'];oid=f'{season}-W{week:02}'
            cutoff=float(g.loc[(g.season==season)&(g.week==week),'kickoff'].min())
            ti=[i for i,r in enumerate(pool) if r['season']>=2022 and r['available']<cutoff and r['values']['rec'] is not None]
            qi=[i for i,r in enumerate(pool) if r['season']==season and r['week']==week]
            y=np.asarray([pool[i]['values']['rec'] for i in ti],float)
            train_ids=[dict(game_id=pool[i]['game_id'],player_id=pool[i]['player_id']) for i in ti]
            member_SHA=accuracy.digest(train_ids);member_path=ART/'members'/(member_SHA+'.json.gz')
            if member_path.exists():assert read(member_path)==train_ids
            else:write(member_path,train_ids)
            points,point_ref=old_points(season,week);point_by={key(r):r for r in points}
            models={};meta={}
            for arm in arms:
                x=matrices[arm][ti];qx=matrices[arm][qi]
                fingerprint=hashlib.sha256(np.nan_to_num(x,nan=999999.).tobytes()+y.tobytes()).hexdigest()
                cached=out/(oid+'-'+arm+'-MODEL.json.gz')
                if cached.exists():
                    packet=read(cached);assert packet['training_fingerprint']==fingerprint and packet['training_membership_SHA256']==member_SHA
                    model=packet['model'];reuse='Completed exact fit reused;no repeat'
                elif study=='completion' and season==2026 and arm=='C0':
                    mid=f'C-ALL12-LAW-THRESHOLD-v2.1-rec-H-MULTI-P3_HGB-E0_OP-W{week:02}'
                    model=reused['direct_models'][mid];reuse='Original safe numeric C0 reused;no equivalent refit'
                    # Every original compatible query must retain its exact feature prefix.
                    for i in qi:
                        old=reused['references'].get('rec|'+pool[i]['game_id']+'|'+pool[i]['player_id'])
                        if old:assert np.allclose(matrices[arm][i],np.asarray(old['saved']['features'],float),rtol=0,atol=1e-10,equal_nan=True)
                    write(cached,dict(model=model,training_fingerprint=fingerprint,training_membership_SHA256=member_SHA,source_reference_SHA256=sha(ART/'REUSED_REFERENCE.json.gz'),reused=True))
                else:
                    assert ledger['fit_attempts']<cap
                    storage_guard()
                    ledger['fit_attempts']+=1;write(ledger_path,ledger)
                    with threadpool_limits(limits=1):fitted=ThresholdModel('MONOTONE_HGB',False,np.floor(GRIDS['rec'])).fit(x,y)
                    model=hgb_export(fitted)
                    # Numeric-only retained inference must match sklearn before scoring.
                    sample=qx[:20];expected=fitted.cdfs(sample,np.floor(GRIDS['rec']))
                    rebuilt=np.asarray([hgb_cdf(model,r,np.floor(GRIDS['rec'])) for r in sample])
                    assert np.allclose(expected,rebuilt,rtol=0,atol=1e-12)
                    write(cached,dict(model=model,training_fingerprint=fingerprint,training_membership_SHA256=member_SHA,protocol_SHA256=sha(ROOT/('protocol/RECEIVING_TARGETSHARE_V10.json' if study=='share' else 'protocol/TEAM_COMPLETION_CONTEXT_V11.json')),fit_code_SHA256=sha(__file__),reused=False))
                    del fitted
                    reuse='NEW_NECESSARY_FEATURE_OR_ORIGIN_FIT'
                models[arm]=model;meta[arm]=dict(model_path=str(cached.relative_to(ROOT)),model_SHA256=sha(cached),feature_count=matrices[arm].shape[1],fit_status=reuse)
                assert resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024<=805306368,'RSS_CAP'
            for i in qi:
                r=pool[i];ref=point_by.get(key(r));record=dict(origin=oid,season=season,week=week,game_id=r['game_id'],player_id=r['player_id'],position=r['position'],team=r['team'],cutoff_UTC=pd.Timestamp(r['kickoff'],unit='s',tz='UTC').isoformat(),fit_origin_UTC=pd.Timestamp(cutoff,unit='s',tz='UTC').isoformat(),created_UTC=now(),actual=r['values']['rec'],appearance='PLAYED' if r['played'] else 'UNKNOWN',retained_P2_point_reference={k:ref.get(k) for k in ['mean','median','actual','fallback']} if ref else None,arms={})
                ff=dict(origin=oid,game_id=r['game_id'],player_id=r['player_id'],position=r['position'],team=r['team'],cutoff_UTC=record['cutoff_UTC'],support=clean(support[i]),values=clean(values[i]),feature_input_hashes={})
                for arm in arms:
                    fv=matrices[arm][i];cdf=np.asarray(hgb_cdf(models[arm],fv,np.floor(GRIDS['rec'])))
                    assert np.all(np.diff(cdf)>=-1e-12)
                    record['arms'][arm]=dict(features=clean(fv),grid=GRIDS['rec'],p_over=(1-cdf).tolist(),typed_output='DIRECT_THRESHOLD_PROBABILITIES;NO_MEAN_MEDIAN_OR_COMPLETE_LAW',fallback=False)
                    ff['feature_input_hashes'][arm]=accuracy.digest(clean(fv))
                allrows.append(record);features.append(ff)
            receipts.append(dict(origin=oid,training_rows=len(ti),training_membership_SHA256=member_SHA,training_members_path=str(member_path.relative_to(ROOT)),query_rows=len(qi),fit_origin_UTC=pd.Timestamp(cutoff,unit='s',tz='UTC').isoformat(),latest_training_available=max(pool[i]['available'] for i in ti),models=meta,retained_point_reference=point_ref))
            if oid not in ledger['completed']:ledger['completed'].append(oid)
            write(ledger_path,ledger)
            assert ledger['wall_seconds']+time.monotonic()-start <= (240 if study=='share' else 480)
        offers=[]
        bypred={(r['game_id'],r['player_id']):r for r in allrows}
        for case in cases:
            if (case['game_id'],case['player_id']) not in bypred:continue
            r=bypred[(case['game_id'],case['player_id'])]
            for arm in arms:
                model_path=next(x['models'][arm]['model_path'] for x in receipts if x['origin']==r['origin']);model=read(ROOT/model_path)['model'];p=probabilities(model,np.asarray(r['arms'][arm]['features'],float),case['line'])
                side='OVER' if p['over']>p['under'] else 'UNDER' if p['under']>p['over'] else 'ABSTAIN'
                actual=case['actual'];state='ABSTAIN' if side=='ABSTAIN' else 'DNP' if case['appearance']=='DNP' else 'MISSING_ACTUAL' if actual is None and case['appearance']=='PLAYED' else 'UNKNOWN_PARTICIPATION' if actual is None else 'PUSH' if actual==case['line'] else 'WIN' if (actual>case['line'])==(side=='OVER') else 'LOSS'
                brier=logloss=None
                if actual is not None:
                    truth={'under':int(actual<case['line']),'push':int(actual==case['line']),'over':int(actual>case['line'])}
                    brier=.5*sum((p[s]-truth[s])**2 for s in truth);prob=sum(p[s]*truth[s] for s in truth);logloss=-math.log(prob) if prob else float('inf')
                offers.append(dict(study=study,stage=stage,arm=arm,procedure_id='C::'+protocol['id']+'::'+arm,offer_id=case['offer_id'],game_id=case['game_id'],player_id=case['player_id'],position=case['position'],week=case['week'],line=case['line'],venue=case['venue'],line_tier=case['line_tier'],selected_side=side,actual=actual,state=state,probabilities=p,Brier=brier,log_loss=logloss,evidence_tier='TIMING_UNVERIFIED_ACTUAL_LINE_RECONSTRUCTION_NOT_ISSUED_PICK',book_settlement='UNVERIFIED',trained_on_synthetic_thresholds=True,threshold_outside_training_grid=math.floor(case['line'])<min(model['thresholds']) or math.floor(case['line'])>max(model['thresholds'])))
        write(out/'PREDICTIONS.json.gz',allrows);write(out/'FEATURE_EXPORT.json.gz',features);write(out/'EXACT_OFFER_ROWS.json.gz',offers)
        storage_guard()
        result=dict(id=protocol['id'],study=study,stage=stage,completed_origins=len(origins),origin_receipts=receipts,new_fits=ledger['fit_attempts'],retained_C0_models_reused=2 if study=='completion' else 0,query_player_game_rows=len(allrows),query_arm_views=len(allrows)*len(arms),actual_offer_arm_views=len(offers),created_UTC=now(),CPU_seconds=ledger['CPU_seconds']+time.process_time()-cpu,wall_seconds=ledger['wall_seconds']+time.monotonic()-start,max_RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,new_calibrators=0,unsafe_models_loaded=False,source_inputs='Existingbasic-football-facts-v2.1.zip hash-pinned;current/revised7dayreconstruction',all_periods_research_exposed=True,no_original_forecasts_changed=True,ninety_percent='TARGET_NOT_ESTABLISHED;B_owns_new_selective_gate',retention='Safe primitive JSON trees/features/memberIDs/predictions inC;no solelocalmodel')
        write(OUT/(study+'-'+stage+'-RUN.json'),result)
        return result
    except Exception as exc:
        ledger['failures'].append(dict(created_UTC=now(),error=str(exc),new_fits_consumed=ledger['fit_attempts']));write(ledger_path,ledger);raise
    finally:
        signal.setitimer(signal.ITIMER_PROF,0)
        ledger['CPU_seconds']+=time.process_time()-cpu;ledger['wall_seconds']+=time.monotonic()-start;write(ledger_path,ledger)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--inputs',type=Path);p.add_argument('--prepare',action='store_true');p.add_argument('--study',choices=['share','completion']);p.add_argument('--stage',choices=['original','actual'],default='original');args=p.parse_args()
    if args.prepare:prepare();print('SOURCE_AND_REUSED_REFERENCE_PREPARED_NO_FITS')
    else:print(json.dumps(run(args.inputs,args.study,args.stage),indent=2))
