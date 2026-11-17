"""Frozen C-DYAD-MIX-VALUE-01/v2; no acquisition or unsafe restoration.

The two public-source origins share one cumulative controller.  Source and
design checks run before any fit.  Raw arm grades precede selector views.
"""
from __future__ import annotations
import time
ENTRY_CPU=time.process_time()
ENTRY_WALL=time.monotonic()
import argparse,bisect,copy,gzip,hashlib,io,json,math,resource,signal,zipfile
from collections import Counter,defaultdict
from pathlib import Path
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
from laws_v2 import ThresholdModel,design,medians
from reliability_v8 import hgb_export,hgb_cdf
from context_experiment_c01 import hgb_probs
from targeted_data_m3 import clean,read,sha,digest,_immutable_sources
from targeted_context_m3 import SOURCE_FILES,EXPECTED_SOURCE_HASHES
from forward_budget_v4 import complete_C_roots,tree_bytes
import abc_championship_v2 as common
import targeted_scores_m3 as views

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/information-skill-01/execution-authorization-02/pilot'
PARENT=ROOT/'reports/targeted-accuracy-w1w9-01/M3'
GRID=np.array([0,1,2,3,4,5,7])
UNKNOWN='__UNKNOWN_PASSER__'
SUPPORT=['eligible_history_games','eligible_history_attempts','latest_complete_attempts',
         'latest_eligible_game_age_days','latest_unknown_passer_fraction','latest_unseen_passer_weight']
NAMES=SUPPORT+['passer_mixture_shift_x_receiver_targeting']

def write(path,obj,mutable=False):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    wire=(json.dumps(clean(obj),separators=(',',':'),allow_nan=False)+'\n').encode()
    if path.suffix=='.gz':wire=gzip.compress(wire,mtime=0)
    if path.exists() and not mutable:
        assert path.read_bytes()==wire,'FROZEN_BYTES_DIFFER:'+str(path)
    else:
        temp=path.with_name(path.name+'.tmp');temp.write_bytes(wire);temp.replace(path)
    return sha(path)

class Budget:
    def __init__(self,stage):
        self.path=OUT/'LEDGER.json';self.s=read(self.path);self.reg=read(OUT/'REGISTRATION.json')
        assert not self.s['active'],'UNCLEAN_EXECUTION_REQUIRES_SCOPED_RECOVERY'
        self.c0=self.s['CPU_seconds'];self.w0=self.s['wall_seconds'];self.stage=stage
        self.s.update(active=True,stage=stage)
        self.check()
        signal.signal(signal.SIGPROF,lambda *_:(_ for _ in ()).throw(RuntimeError('PILOT_CPU_CAP')))
        ceiling=90 if stage in ['prepare','fit'] else 120
        signal.setitimer(signal.ITIMER_PROF,max(.01,ceiling-self.c0-time.process_time()+ENTRY_CPU))
        signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(RuntimeError('PILOT_WALL_CAP')))
        signal.setitimer(signal.ITIMER_REAL,max(.01,300-self.w0-time.monotonic()+ENTRY_WALL))
    def check(self,reserve=0):
        self.s['CPU_seconds']=self.c0+time.process_time()-ENTRY_CPU
        self.s['wall_seconds']=self.w0+time.monotonic()-ENTRY_WALL
        self.s['peak_RSS_bytes']=max(self.s.get('peak_RSS_bytes',0),resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024)
        write(self.path,self.s,True)
        assert self.s['CPU_seconds']+reserve<=120,'PILOT_CPU_RESERVE'
        assert self.s['wall_seconds']<=300,'PILOT_WALL_CAP'
        assert self.s['peak_RSS_bytes']<=1288490188,'PILOT_RSS_CAP'
        return self.s['CPU_seconds']
    def attempt(self,key):
        assert key not in self.s['attempts'] and len(self.s['attempts'])<5,'FIT_ATTEMPT_CAP_OR_DUPLICATE'
        self.s['attempts'].append(key);self.check(30)
    def finish(self,error=None):
        signal.setitimer(signal.ITIMER_PROF,0);signal.setitimer(signal.ITIMER_REAL,0)
        if error:self.s['failures'].append(dict(stage=self.stage,error=type(error).__name__+':'+str(error)))
        self.s['active']=False;self.check()

def inputs():
    p=PARENT/'inputs/FEATURES_AND_MEMBER_FACTS.json.gz';data=read(p)
    x=np.asarray(data['X_by_target']['rec'],float);rows=data['rows']
    assert x.shape==(len(rows),32)
    offers=[o for o in read(PARENT/'inputs/NATIVE_OFFERS.json.gz')['primary'] if o['category']=='rec']
    assert len(offers)==295 and {o['week'] for o in offers}=={2,3}
    return data,rows,x,offers

def origins():
    schedule=pd.read_csv(ROOT/'sources/category-decision-release-01/schedule.csv')
    times=pd.to_datetime(schedule.gameday+' '+schedule.gametime).dt.tz_localize('America/New_York').dt.tz_convert('UTC').astype('int64')/1e9
    return {w:float(times[(schedule.season==2026)&(schedule.week==w)].min()) for w in [2,3]}

def sources(rows):
    cache=OUT/'SOURCE_AGGREGATES.json.gz'
    if cache.exists():
        assert sha(cache)==read(OUT/'SOURCE_AGGREGATE_BINDING.json')['SHA256']
        saved=read(cache)
        for path,expected in zip(SOURCE_FILES,EXPECTED_SOURCE_HASHES):assert sha(ROOT/path)==expected
        teams={}
        for raw in saved['teams']:
            t=dict(raw,T={(q,p):v for q,p,v in raw['T']})
            teams[(t['game_id'],t['team'])]=t
        return teams,{(g,p):v for g,p,v in saved['player_targets']}
    columns=['game_id','team','player_id','season','week','attempts','completions','targets']
    with zipfile.ZipFile(ROOT/'artifacts/basic-football-facts-v2.1.zip') as z:
        old=pd.read_csv(io.BytesIO(z.read('facts.csv.gz')),compression='gzip',usecols=columns,low_memory=False)
    cur=pd.read_csv(ROOT/'sources/category-decision-release-01/current_facts_2026.csv.gz',usecols=columns+['season_type'],low_memory=False)
    extra=cur[(cur.season==2026)&cur.week.isin([8,9])&(cur.season_type=='REG')][columns]
    facts=pd.concat([old,extra],ignore_index=True)
    assert not facts.duplicated(['game_id','player_id']).any()
    player_targets={(r.game_id,r.player_id):None if pd.isna(r.targets) else int(r.targets) for r in facts.itertuples()}
    official={}
    for key,f in facts.groupby(['game_id','team'],sort=False):
        a=f[['attempts','completions','targets']].to_numpy(float)
        official[key]=(bool(np.isfinite(a).all() and (a>=0).all() and np.equal(a,np.floor(a)).all()),a.sum(axis=0))
    game={}
    for r in rows:
        if r['query_only']:continue
        if r['game_id'] in game:assert game[r['game_id']]==r['kickoff'],'CANONICAL_GAME_CLOCK_CONFLICT'
        game[r['game_id']]=r['kickoff']
    cols=['game_id','play_id','posteam','pass_attempt','sack','two_point_attempt','play_deleted','play_type','receiver_player_id','passer_player_id','complete_pass']
    frames=[];bindings=[]
    for path,expected in zip(SOURCE_FILES,EXPECTED_SOURCE_HASHES):
        p=ROOT/path;assert sha(p)==expected,'SOURCE_BYTES_CHANGED'
        frames.append(pd.read_csv(p,usecols=cols,low_memory=False))
        bindings.append(dict(path=path,SHA256=expected,bytes=p.stat().st_size))
    pbp=pd.concat(frames,ignore_index=True)
    assert not pbp.duplicated(['game_id','play_id']).any()
    valid=pbp[(pbp.pass_attempt==1)&(pbp.sack!=1)&(pbp.two_point_attempt!=1)&(pbp.play_deleted!=1)&(pbp.play_type!='no_play')].copy()
    teams={};counts=Counter()
    for key,f in valid.groupby(['game_id','posteam'],sort=False):
        if key[0] not in game:counts['missing_game_clock']+=1;continue
        known,total=official.get(key,(False,None))
        qualified=bool(known and len(f)==total[0] and (f.complete_pass==1).sum()==total[1] and f.receiver_player_id.notna().sum()==total[2])
        q=f.passer_player_id.fillna(UNKNOWN).tolist();p=f.receiver_player_id.where(f.receiver_player_id.notna(),None).tolist()
        attempts=Counter(q);pairs=Counter((a,b) for a,b in zip(q,p) if b is not None)
        completions=Counter(f.loc[(f.complete_pass==1)&f.receiver_player_id.notna(),'receiver_player_id'])
        targets=Counter(b for b in p if b is not None)
        assert sum(attempts.values())==len(f) and all(v<=attempts[a] for (a,b),v in pairs.items())
        teams[key]=dict(game_id=key[0],team=key[1],kickoff=game[key[0]],available=game[key[0]]+604800,
                        qualified=qualified,A=dict(attempts),T=dict(pairs),C=dict(completions),targets=dict(targets))
        counts['qualified' if qualified else 'held_incomplete']+=1
        counts['unknown_passer_attempts']+=attempts[UNKNOWN]
    write(OUT/'SOURCE_CHECK.json',dict(bindings=bindings,teams=dict(counts),raw_rows=len(pbp),qualified_attempt_rows=len(valid),
        ordinary_sources=[dict(path=n,SHA256=sha(ROOT/n)) for n in ['artifacts/basic-football-facts-v2.1.zip','sources/category-decision-release-01/current_facts_2026.csv.gz']],
        clock_contract='Current-vintage, prior kickoff+7d strictly<casecutoff; not original publication clocks',
        qualifier='Existing strict all-position attempt/completion/target totals; player targets/rec additionally reconciled; missing neverzero'))
    serial=dict(teams=[dict(t,T=[[q,p,v] for (q,p),v in t['T'].items()]) for t in teams.values()],
                player_targets=[[g,p,v] for (g,p),v in player_targets.items()])
    write(cache,serial)
    assert digest(read(cache))==digest(serial),'SOURCE_AGGREGATE_REOPEN_PARITY'
    write(OUT/'SOURCE_AGGREGATE_BINDING.json',dict(path=str(cache.relative_to(ROOT)),SHA256=sha(cache),
          source_check_SHA256=sha(OUT/'SOURCE_CHECK.json'),independently_reopened=True,
          scope='Minimum derived ordinary-count/PBP relationship cache; original observation/vintage unchanged.'))
    return teams,player_targets

class Engine:
    def __init__(self,rows,teams,player_targets):
        self.teams=teams;self.players=defaultdict(list);self.byteam=defaultdict(list)
        for t in teams.values():
            if t['qualified']:self.byteam[t['team']].append(t)
        for rr in rows:
            if rr['query_only'] or not rr.get('played'):continue
            t=teams.get((rr['game_id'],rr['team']))
            if t is None or not t['qualified']:continue
            p=rr['player_id'];target=player_targets.get((rr['game_id'],p))
            if target is None or target!=t['targets'].get(p,0):continue
            rec=rr['values']['rec']
            if rec is None or rec!=t['C'].get(p,0):continue
            # Known played-zero requires explicit targets=0 and rec=0 above.
            self.players[(p,rr['team'])].append(t)
        for d in [self.players,self.byteam]:
            for v in d.values():v.sort(key=lambda r:(r['kickoff'],r['game_id']))
        self.ptimes={k:[r['available'] for r in v] for k,v in self.players.items()}
        self.ttimes={k:[r['available'] for r in v] for k,v in self.byteam.items()}
    def record(self,r):
        cut=min(r['kickoff'],r.get('information_cutoff_epoch',r['kickoff']))
        key=(r['player_id'],r['team']);a=self.players.get(key,[])
        hist=a[:bisect.bisect_left(self.ptimes.get(key,[]),cut)][-8:]
        tt=self.byteam.get(r['team'],[]);latest=tt[:bisect.bisect_left(self.ttimes.get(r['team'],[]),cut)]
        latest=latest[-1] if latest else None
        assert all(t['available']<cut and t['kickoff']<cut for t in hist+([latest] if latest else []))
        A=Counter();T=Counter()
        for t in hist:
            A.update(t['A']);T.update({q:v for (q,p),v in t['T'].items() if p==r['player_id']})
        na=sum(A.values());la=sum(latest['A'].values()) if latest else 0
        union=set(A)|set(latest['A'] if latest else {})
        missing=not na or not la
        wh={q:A[q]/na for q in union} if na else {}
        wl={q:latest['A'].get(q,0)/la for q in union} if la else {}
        s=sum(T.values())/na if na else None
        rates={q:(T[q]+20*s)/(A[q]+20) for q in union} if na else {}
        value=sum((wl[q]-wh[q])*rates[q] for q in union) if not missing else np.nan
        if not missing:assert abs(sum(wh.values())-1)<1e-12 and abs(sum(wl.values())-1)<1e-12 and -1<=value<=1
        support=[len(hist),na,la,(cut-latest['kickoff'])/86400 if latest else np.nan,
                 latest['A'].get(UNKNOWN,0)/la if la else np.nan,
                 sum(wl[q] for q in union if A[q]==0) if not missing else np.nan]
        return np.asarray(support+[value],float),dict(game_id=r['game_id'],player_id=r['player_id'],team=r['team'],cutoff=cut,
            history=[dict(game_id=t['game_id'],kickoff=t['kickoff'],available=t['available']) for t in hist],
            latest=None if not latest else dict(game_id=latest['game_id'],kickoff=latest['kickoff'],available=latest['available']),
            attempts=dict(A),receiver_targets=dict(T),w_history=wh,w_latest=wl,rates=rates,history_share=s,
            forecast_share=sum(wl[q]*rates[q] for q in union) if not missing else None,substantive=value)

def prepare(budget):
    data,rows,x,offers=inputs()
    write(OUT/'ORDINARY_SOURCE_PARITY.json',dict(status='PASS',bindings=_immutable_sources(ROOT)))
    teams,pt=sources(rows);engine=Engine(rows,teams,pt)
    matrix=OUT/'FEATURE_MATRIX.json.gz'
    if matrix.exists():
        cached=read(matrix)
        assert cached['identity_order_SHA256']==digest([(r['game_id'],r['player_id']) for r in rows])
        assert cached['input_SHA256']==sha(PARENT/'inputs/FEATURES_AND_MEMBER_FACTS.json.gz') and cached['feature_names']==NAMES
        bx=np.asarray(cached['matrix'],float)
    else:
        bx=np.array([engine.record(r)[0] for r in rows])
        write(matrix,dict(matrix=bx,feature_names=NAMES,identity_order_SHA256=digest([(r['game_id'],r['player_id']) for r in rows]),
            input_SHA256=sha(PARENT/'inputs/FEATURES_AND_MEMBER_FACTS.json.gz')))
    assert bx.shape==(len(rows),7)
    # Compare all actual retained parent vectors; no parent fit or pickle load.
    bank=read(ROOT/'artifacts/reliability-v8/REFERENCE_BANK.json.gz');idx={(r['game_id'],r['player_id']):i for i,r in enumerate(rows)}
    parent=0
    for o in offers:
        m=o['retained_methods'].get('P3_DIRECT')
        if m is None or m.get('selected_side') is None:
            assert m is None or m['status']=='UNAVAILABLE_FORECAST'
            continue
        ref=bank['references'].get('|'.join(['rec',o['game_id'],o['player_id']]))
        assert ref is not None and np.allclose(x[idx[(o['game_id'],o['player_id'])]],np.asarray(ref['saved']['features'],float),rtol=0,atol=0,equal_nan=True),'PARENT32_PARITY'
        assert bank['direct_models'][ref['direct_model_id']]['thresholds']==GRID.tolist()
        parent+=1
    assert parent==272
    cutoffs=origins();origin_checks=[]
    for w,cut in cutoffs.items():
        assert cut==min(r['kickoff'] for r in rows if r['season']==2026 and r['week']==w)
        provenance=[p for p in bank['provenance'] if p['category']=='rec' and p['week']==w]
        assert len(provenance)==1 and pd.Timestamp(provenance[0]['fit_origin_UTC']).timestamp()==cut
        origin_checks.append(dict(week=w,origin=cut,parent_provenance=provenance[0],exact_scheduled_origin=True))
    write(OUT/'ORIGIN_PARITY.json',origin_checks)
    checks=[];fixed=[]
    for week,role in [(2,'WR'),(2,'TE'),(3,'WR'),(3,'TE')]:
        q=[i for i in data['query_indices_2026'][str(week)] if rows[i]['position']==role]
        fixed.extend(q[:1])
    fixed+= [i for i in data['query_indices_2026']['2'] if np.isfinite(bx[i,-1]) and abs(bx[i,-1])>1e-12][:2]
    for i in dict.fromkeys(fixed):
        r=rows[i];cut=r['kickoff'];altered=copy.deepcopy(teams);changed=0
        for key,t in altered.items():
            if t['available']<cut:continue
            cells=[(q,p) for (q,p),v in t['T'].items() if v>0]
            pair=next(((a,c) for a in cells for c in cells if a[0]!=c[0] and a[1]!=c[1]),None)
            if pair:
                (q1,p1),(q2,p2)=pair
                t['T'][(q1,p1)]-=1;t['T'][(q2,p2)]-=1
                t['T'][(q1,p2)]=t['T'].get((q1,p2),0)+1;t['T'][(q2,p1)]=t['T'].get((q2,p1),0)+1;changed+=1
                assert t['A']==teams[key]['A'] and t['targets']==teams[key]['targets']
        assert changed>0,'NFL_MUTATION_NO_AFFECTED_FUTURE_RELATIONSHIPS'
        mutated_rows=[dict(a,values=dict(a['values'],rec=(None if a['values']['rec'] is None else (a['values']['rec']+17 if a['available'] is None or a['available']>=cut else a['values']['rec'])))) for a in rows]
        other=Engine(mutated_rows,altered,pt)
        v,trace=other.record(r);assert np.array_equal(v,bx[i],equal_nan=True),'NFL_QUERY_FEATURE_LEAKAGE'
        origin=cutoffs[r['week']]
        ti=[j for j,a in enumerate(rows) if not a['query_only'] and a['available'] is not None and a['available']<origin and a['values']['rec'] is not None]
        block=np.array([other.record(rows[j])[0] for j in ti]);assert np.array_equal(block,bx[ti],equal_nan=True),'NFL_TRAIN_FEATURE_LEAKAGE'
        old=np.c_[x[ti],bx[ti]];new=np.c_[x[ti],block]
        assert np.array_equal(design(old,medians(old)),design(new,medians(old)))
        assert all(mutated_rows[j]['values']['rec']==rows[j]['values']['rec'] for j in ti)
        checks.append(dict(query=trace,mutated_future_team_games=changed,full_context_team_records=len(teams),
            full_query_universe_rows=len(rows),training_rows=len(ti),raw_and_transformed_design_equal=True))
    write(OUT/'NFL_MUTATION_CHECK.json',dict(status='PASS',cases=checks,
        scope='Actual retained NFL full team/player/query context. Future native passer-target associations and unadmitted rec outcomes mutated; clocks/identities/order, attempt/target denominators and legitimate prior inputs fixed. Aggregated source-bound relation layer, not an independently re-downloaded source vintage.'))
    sample=[engine.record(rows[i])[1] for i in list(dict.fromkeys(fixed))]
    write(OUT/'FEATURE_TRACE.json',dict(cases=sample,qualified_player_histories=len(engine.players),
        source_supported_rows=int(np.isfinite(bx[:,-1]).sum()),nonzero_substantive_rows=int((np.nan_to_num(abs(bx[:,-1]))>1e-12).sum()),
        parent_original32_available_vectors_verified=parent,original32_unchanged=True))
    budget.check(30)
    assert budget.s['CPU_seconds']+5*8+10+30<=120,'COMPLETE_PATH_PROJECTION_DOES_NOT_FIT'
    write(OUT/'READY.json',dict(status='PASS_NFL_SOURCE_AND_DESIGN',feature_matrix_SHA256=sha(OUT/'FEATURE_MATRIX.json.gz'),
        source_check_SHA256=sha(OUT/'SOURCE_CHECK.json'),NFL_check_SHA256=sha(OUT/'NFL_MUTATION_CHECK.json'),
        projected_fits_CPU=40,projected_scoring_CPU=10,reserve_CPU=30,charged_CPU=budget.s['CPU_seconds'],
        remaining_complete_path_fits=True,source_GETs=0,raw_input_bodies_present_and_reopened=True))

def offer_record(o,arm,p=None,source=None):
    r={k:v for k,v in o.items() if k not in ['retained_methods','repeated_offer_ids']}
    side=None if p is None else 'OVER' if p['over']>p['under']+1e-12 else 'UNDER' if p['under']>p['over']+1e-12 else 'ABSTAIN'
    r.update(arm=arm,product='LAW',method=arm,procedure='C-DYAD-MIX-VALUE-01/v2::'+arm,selected_side=side,probabilities=p,
             mean=None,median=None,point=None,point_type=None,learned=p is not None,fallback=False if p else None,model_binding=source)
    r['status']=common.status(r);return r

def fit_all(budget):
    assert read(OUT/'EXECUTION_GO.json')['authorized'] is True
    ready=read(OUT/'READY.json');assert sha(OUT/'FEATURE_MATRIX.json.gz')==ready['feature_matrix_SHA256']
    data,rows,x,offers=inputs();bx=np.asarray(read(OUT/'FEATURE_MATRIX.json.gz')['matrix'],float)
    idx={(r['game_id'],r['player_id']):i for i,r in enumerate(rows)}
    raw=[];fit_times=[]
    for w in [2,3]:
        origin=origins()[w]
        ti=[i for i,r in enumerate(rows) if not r['query_only'] and r['available'] is not None and r['available']<origin and r['values']['rec'] is not None]
        y=np.array([rows[i]['values']['rec'] for i in ti],float)
        assert not ({rows[i]['game_id'] for i in ti}&{o['game_id'] for o in offers if o['week']==w})
        qi=sorted({idx[(o['game_id'],o['player_id'])] for o in offers if o['week']==w})
        for arm,n in [('C1_SUPPORT',6),('C2_VALUE',7)]:
            key=f'W{w}-{arm}';path=OUT/'models'/(key+'.json.gz');xx=np.c_[x,bx[:,:n]]
            if path.exists():model=read(path)['model']
            else:
                budget.attempt(key);t=time.process_time()
                with threadpool_limits(limits=1):fitted=ThresholdModel('MONOTONE_HGB',False,GRID).fit(xx[ti],y)
                model=hgb_export(fitted);fit_times.append(time.process_time()-t)
                native=fitted.cdfs(xx[qi[:3]],GRID)
                restored=np.array([hgb_cdf(model,xx[i],GRID) for i in qi[:3]])
                assert np.allclose(native,restored,rtol=0,atol=1e-12),'NUMERIC_RESTORE_PARITY'
                assert np.allclose(fitted.cdfs(xx[qi[:1]],GRID)[0],native[0],rtol=0,atol=1e-12),'BATCH_SINGLE_PARITY'
                write(path,dict(model=model,week=w,arm=arm,training_rows=len(ti),origin=origin,
                    training_membership_SHA256=digest([(rows[i]['game_id'],rows[i]['player_id']) for i in ti]),
                    design_X_y_SHA256=hashlib.sha256(np.nan_to_num(xx[ti],nan=999999.).tobytes()+y.tobytes()).hexdigest(),
                    feature_names=data['feature_names']['rec']+NAMES[:n],feature_matrix_SHA256=sha(OUT/'FEATURE_MATRIX.json.gz'),
                    input_SHA256=sha(PARENT/'inputs/FEATURES_AND_MEMBER_FACTS.json.gz'),fit_code_SHA256=sha(__file__)))
                budget.s['completed'].append(key);budget.check(30)
                remaining=5-len(budget.s['attempts'])
                projected=max(8.,2*max(fit_times))*remaining+10+30
                assert budget.s['CPU_seconds']+projected<=120,'MEASURED_REMAINING_PATH_AND_RESERVES_DO_NOT_FIT'
            rr=[]
            for o in offers:
                if o['week']!=w:continue
                p=hgb_probs(model,xx[idx[(o['game_id'],o['player_id'])]],o['line'])
                assert min(p.values())>=0 and abs(sum(p.values())-1)<1e-10
                row=offer_record(o,arm,p,dict(path=str(path.relative_to(ROOT)),SHA256=sha(path)))
                row['dyad_source_covered']=bool(np.isfinite(bx[idx[(o['game_id'],o['player_id'])],-1]))
                rr.append(row)
            write(OUT/'raw'/(key+'.json.gz'),rr);raw.extend(rr)
            budget.check(30)
    for o in offers:
        m=o['retained_methods'].get('P3_DIRECT');p=None if m is None else {k:m.get('p_'+k) for k in ['under','push','over']}
        if p is not None and any(v is None for v in p.values()):p=None
        r=offer_record(o,'C0_SAVED_P3',p)
        if m:
            assert r['status']==m['status'] and r['selected_side']==m['selected_side']
            r['fallback']=m.get('fallback');r['learned']=(not m['fallback']) if isinstance(m.get('fallback'),bool) else None
        r['dyad_source_covered']=bool(np.isfinite(bx[idx[(o['game_id'],o['player_id'])],-1]))
        raw.append(r)
    existing=read(PARENT/'base-OFFER_ROWS.json.gz')
    for r in existing:
        if r['category']=='rec' and ((r['arm']=='M3-0' and r['product']=='LAW') or r['arm'].startswith('CONTROL_')):
            if r['arm']=='CONTROL_P3_DIRECT':continue
            raw.append(dict(r,arm='LEAF' if r['arm']=='M3-0' else r['arm'],
                            dyad_source_covered=bool(np.isfinite(bx[idx[(r['game_id'],r['player_id'])],-1]))))
    write(OUT/'RAW_GRADED_ROWS.json.gz',raw)
    write(OUT/'RAW_GRADES_COMPLETE.json',dict(rows=len(raw),new_arm_rows=590,
        raw_SHA256=sha(OUT/'RAW_GRADED_ROWS.json.gz'),fit_attempts=len(budget.s['attempts']),
        saved_before_selectors=True,fit_times_CPU=fit_times,new_source_GETs=0))

def score(budget):
    assert (OUT/'RAW_GRADES_COMPLETE.json').exists()
    raw=read(OUT/'RAW_GRADED_ROWS.json.gz');groups=defaultdict(list)
    for r in raw:groups[(r['arm'],r['product'])].append(r)
    # Use existing grader/view implementation; no numerical point fabricated.
    views.summarize(raw,[],OUT/'scores')
    pairs=[]
    for c,k in [('C2_VALUE','C1_SUPPORT'),('C2_VALUE','C0_SAVED_P3'),('C1_SUPPORT','C0_SAVED_P3'),('C2_VALUE','LEAF')]:
        pairs.append(dict(candidate=c,control=k,**views._paired(groups[(c,'LAW')],groups[(k,'LAW')])))
    write(OUT/'scores/DECLARED_PAIRS.json.gz',pairs)
    source_groups=[]
    for covered in [True,False]:
        for arm in ['C0_SAVED_P3','C1_SUPPORT','C2_VALUE','LEAF']:
            rr=[r for r in groups[(arm,'LAW')] if r['dyad_source_covered']==covered]
            source_groups.append(dict(arm=arm,dyad_source_covered=covered,**views._summary(rr,[2,3])))
    write(OUT/'scores/SOURCE_GROUPS.json.gz',source_groups)
    memberships=read(OUT/'scores/SELECTED_MEMBERSHIP.json.gz')['rows'];lists=defaultdict(list)
    for r in memberships:lists[(r['arm'],r['side_scope'],r['policy'])].extend(r['selected_offer_ids'])
    boards={a:{r['offer_id']:r for r in groups[(a,'LAW')]} for a in ['C0_SAVED_P3','C1_SUPPORT','C2_VALUE','LEAF']}
    own=[]
    for c,k in [('C2_VALUE','C1_SUPPORT'),('C2_VALUE','C0_SAVED_P3'),('C1_SUPPORT','C0_SAVED_P3')]:
        for side in ['COMBINED','OVER','UNDER']:
            for policy in sorted({key[2] for key in lists if key[:2]==(c,side)}):
                ci=set(lists[(c,side,policy)]);ki=set(lists[(k,side,policy)])
                cr=[boards[c][i] for i in sorted(ci)];kr=[boards[k][i] for i in sorted(ki)]
                own.append(dict(candidate=c,control=k,side_scope=side,policy=policy,
                    candidate_own=views._summary(cr,[2,3]),control_own=views._summary(kr,[2,3]),
                    same_candidate_selected_case_control=views._paired(cr,[boards[k][i] for i in sorted(ci)]),
                    common_members=len(ci&ki),candidate_only=len(ci-ki),control_only=len(ki-ci)))
    write(OUT/'scores/OWN_LIST_COMPARISONS.json.gz',own)
    usage=[]
    for p in sorted((OUT/'models').glob('*.json.gz')):
        obj=read(p);n=len(obj['feature_names']);counts=Counter()
        for tree in obj['model']['trees']:
            counts.update(v for v,leaf in zip(tree['feature_idx'],tree['is_leaf']) if not leaf)
        usage.append(dict(model=str(p.relative_to(ROOT)),feature_split_counts=dict(counts),
                          substantive_value_splits=counts.get(38,0) if obj['arm']=='C2_VALUE' else None,
                          substantive_missing_indicator_splits=counts.get(38+n,0) if obj['arm']=='C2_VALUE' else None))
    write(OUT/'FITTED_USE.json',usage)
    data,rows,x,offers=inputs();cached=read(OUT/'SOURCE_AGGREGATES.json.gz')
    teams={(t['game_id'],t['team']):dict(t,T={(q,p):v for q,p,v in t['T']}) for t in cached['teams']}
    pt={(g,p):v for g,p,v in cached['player_targets']};engine=Engine(rows,teams,pt)
    index={(r['game_id'],r['player_id']):r for r in rows};components=[]
    for o in offers:
        t=teams.get((o['game_id'],o['team']));target=pt.get((o['game_id'],o['player_id']))
        if not t or not t['qualified'] or target is None or o['appearance']!='PLAYED' or o['actual'] is None:continue
        v,z=engine.record(index[(o['game_id'],o['player_id'])])
        if not np.isfinite(v[-1]):continue
        history=sum(z['w_history'][q]*z['rates'][q] for q in z['rates'])
        actual=target/sum(t['A'].values())
        components.append(dict(game_id=o['game_id'],player_id=o['player_id'],week=o['week'],
            historical_mixture_share=history,forecast_mixture_share=z['forecast_share'],actual_share=actual))
    metric={}
    for key in ['historical_mixture_share','forecast_mixture_share']:
        e=np.array([r[key]-r['actual_share'] for r in components])
        metric[key]=dict(n=len(e),MAE=float(np.mean(abs(e))) if len(e) else None,MSE=float(np.mean(e*e)) if len(e) else None)
    write(OUT/'scores/COMPONENT.json',dict(metrics=metric,rows=components,
        scope='Conditional-on-qualified participation target share diagnostic. Realized team attempts form outcome denominator only, never query input. Not a reception mean forecast or actual-line gain.'))
    budget.check()
    write(OUT/'RUN_COMPLETE.json',dict(status='FROZEN_FOUR_AUGMENTATION_FITS_AND_SCORING_COMPLETE',
        independent_representative_fit='PENDING_WITHIN_FIFTH_SLOT',actual_offer_weeks=[2,3],
        exposed_history=True,primary_activation=False,point_mean_median=None))

def main():
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['prepare','fit','score']);args=p.parse_args()
    budget=Budget(args.stage)
    try:
        if args.stage=='prepare':prepare(budget)
        elif args.stage=='fit':fit_all(budget)
        else:score(budget)
    except Exception as e:
        budget.finish(e);raise
    else:budget.finish()
    print(json.dumps(budget.s))

if __name__=='__main__':
    with threadpool_limits(limits=1):main()
