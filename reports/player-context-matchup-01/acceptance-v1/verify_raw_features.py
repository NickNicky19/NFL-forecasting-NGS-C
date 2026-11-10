"""Offline independent raw-meaning audit; no fit, HTTP, extraction or peer write.

Run from any directory with Python, numpy and pandas. Only C_RAW_REVIEW.json is
written beside this script. Reference arithmetic below does not call Context's
aggregation, prefix or feature functions. Production Context is used solely as
a second comparison and for the target/future mutation regression.
"""
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
os.environ['OMP_NUM_THREADS']='1'
import bisect, collections, datetime, gzip, hashlib, io, json, math, resource
import signal, sys, time, zipfile
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).with_name('C_RAW_REVIEW.json')
PIN='fa503c1e1a9993e655a905195ce428edf630add5'
ART=ROOT/'artifacts/player-context-matchup-01'
SOURCE=ROOT/'sources/player-context-matchup-01'
START=time.process_time()
signal.signal(signal.SIGPROF,lambda *_:(_ for _ in ()).throw(RuntimeError('AUDIT_90_CPU_SECOND_CAP')))
signal.setitimer(signal.ITIMER_PROF,90)
sys.path.insert(0,str(ROOT/'src'))
DAY=86400.
PHYSICAL=['attempts','carries','targets','receptions','sacks_suffered','passing_tds',
 'rushing_tds','receiving_tds','passing_2pt_conversions','rushing_2pt_conversions',
 'receiving_2pt_conversions','kickoff_returns','punt_returns','special_teams_tds']
SIGNED=['passing_yards','rushing_yards','receiving_yards']
OWN=['ctx_player_games8','ctx_targets8','ctx_team_attempts8','ctx_age_days','ctx_missing',
 'ctx_targets_per_team_attempt','ctx_targets_per_appearance','ctx_catch_per_target',
 'ctx_mean_air_per_known_target','ctx_mean_YAC_per_complete_known_target',
 'ctx_short_to_go_target_share','ctx_redzone_target_share']
OWN += ['ctx_depth_share_'+s for s in ['behind','0_9','10_19','20plus','unknown']]
OWN += ['ctx_down_share_'+s for s in ['1','2','3','4','unknown']]
OPP=['opp_context_games8','opp_target_support8','opp_age_days','opp_missing',
 'opp_offense_adjusted_completion_residual','opp_offense_adjusted_WRTE_target_share_residual']
INTER=['predicted_depth_mix_x_opponent_catch_residual','predicted_down_mix_x_opponent_catch_residual']

def read(p):
    b=Path(p).read_bytes()
    return json.loads(gzip.decompress(b) if str(p).endswith('.gz') else b)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(x):
    if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple,np.ndarray)):return [clean(v) for v in x]
    if isinstance(x,(np.integer,)):return int(x)
    if isinstance(x,(float,np.floating)):return float(x) if math.isfinite(x) else None
    if isinstance(x,np.bool_):return bool(x)
    return x
def equal(a,b):
    np.testing.assert_allclose(np.asarray(a,float),np.asarray(b,float),rtol=0,atol=2e-12,equal_nan=True)
def finite(x):return x is not None and np.isfinite(x)
def depth(x):return 4 if not finite(x) else 0 if x<0 else 1 if x<10 else 2 if x<20 else 3
def down(x):return int(x)-1 if finite(x) and x in (1,2,3,4) else 4
def sorted_rows(rs):return sorted(rs,key=lambda r:(r['kickoff'],r['game_id']))
def prior(rs,cut,n=None):
    selected=[r for r in rs if r['available']<cut]
    return selected if n is None else selected[-n:]
def vector_sum(rs,key):return np.sum([r[key] for r in rs],axis=0) if rs else np.zeros(5)
def grouped(rs,key):
    out=collections.defaultdict(list)
    for r in rs:out[r[key]].append(r)
    return {k:sorted_rows(v) for k,v in out.items()}

def inputs():
    """Read licensed retained bytes in memory; reproduce rec appearance independently."""
    with zipfile.ZipFile(ROOT/'artifacts/basic-football-facts-v2.1.zip') as z:
        raw=pd.read_csv(io.BytesIO(z.read('facts.csv.gz')),compression='gzip',low_memory=False)
        schedule=pd.read_csv(io.BytesIO(z.read('schedule.csv')))
    later=ROOT/'prospective/runs/C-FWD-v4-20261105-W09-JAXBAL-remainder/sources'
    extra=pd.read_csv(later/'facts.csv.gz',low_memory=False)
    extra=extra[(extra.season==2026)&(extra.week==8)]
    assert not ((raw.season==2026)&(raw.week==8)).any()
    raw=pd.concat([raw,extra],ignore_index=True)
    g2=pd.read_csv(later/'schedule.csv')
    schedule=pd.concat([schedule[~((schedule.season==2026)&(schedule.week==8))],
                        g2[(g2.season==2026)&(g2.week==8)]],ignore_index=True)
    schedule['kickoff']=pd.to_datetime(schedule.gameday+' '+schedule.gametime).dt.tz_localize('America/New_York').dt.tz_convert('UTC').astype('int64')/1e9
    data=raw.merge(schedule[['game_id','kickoff','home_team','away_team','home_score','away_score']],on='game_id',validate='many_to_one')
    assert not data.duplicated(['game_id','player_id']).any()
    data['available']=data.kickoff+7*DAY
    data['played']=(data[PHYSICAL].fillna(0)>0).any(axis=1)|(data[SIGNED].fillna(0)!=0).any(axis=1)
    known=data.played&data.home_score.notna()&data.away_score.notna()
    data['values']=[{'rec':int(y) if k and finite(y) else None} for y,k in zip(data.receptions,known)]
    players=data[data.position.isin(['QB','RB','WR','TE'])].copy()
    cols=['game_id','play_id','posteam','defteam','pass_attempt','sack','two_point_attempt',
          'play_deleted','play_type','receiver_player_id','complete_pass','air_yards',
          'down','yards_after_catch','ydstogo','yardline_100','season','week']
    frames=[pd.read_csv(SOURCE/f'pbp_facts_{y}.csv.xz',usecols=cols,low_memory=False) for y in [2025,2026]]
    return raw,players,schedule,frames

class RawArithmetic:
    def __init__(self,raw,players,schedule,frames):
        self.games={r['game_id']:r for r in schedule.to_dict('records')}
        self.native={(r['game_id'],r['player_id']):r for r in players.to_dict('records')}
        self.counts={}
        for k,f in raw.groupby(['game_id','team'],sort=False):
            x=f[['attempts','completions','targets']].to_numpy(float)
            self.counts[k]={'attempts':float(x[:,0].sum()),'completions':float(x[:,1].sum()),
                'targets':float(x[:,2].sum()),'complete':bool(np.isfinite(x).all() and (x>=0).all() and (x==np.floor(x)).all())}
        pbp=pd.concat(frames,ignore_index=True)
        assert not pbp.duplicated(['game_id','play_id']).any()
        p=pbp[(pbp.pass_attempt==1)&(pbp.sack!=1)&(pbp.two_point_attempt!=1)&(pbp.play_deleted!=1)&(pbp.play_type!='no_play')]
        self.play_groups={(game,team):f.to_dict('records') for (game,team),f in p.groupby(['game_id','posteam'],sort=False)}
        by_native=grouped(players.to_dict('records'),'game_id')
        teams=[];playergames=[]
        for (game,team),plays in self.play_groups.items():
            if game not in self.games:continue
            g=self.games[game];opponent=g['away_team'] if team==g['home_team'] else g['home_team']
            assert team in [g['home_team'],g['away_team']]
            assert all(r['defteam']==opponent for r in plays)
            q=dict(game_id=game,team=team,opponent=opponent,kickoff=float(g['kickoff']),
                available=float(g['kickoff'])+7*DAY,attempts=len(plays),targets=0,wrte_targets=0,
                N=np.zeros(5),C=np.zeros(5),U=np.zeros(5),V=np.zeros(5))
            official=self.counts.get((game,team));named=[r for r in plays if pd.notna(r['receiver_player_id'])]
            q['complete']=bool(official and official['complete'] and len(plays)==official['attempts']
                and sum(r['complete_pass']==1 for r in plays)==official['completions'] and len(named)==official['targets'])
            q['official']=official
            groups=collections.defaultdict(list)
            for r in named:groups[r['receiver_player_id']].append(r)
            for pid,rs in groups.items():
                native=self.native.get((game,pid));role=native['position'] if native else None
                if native:assert native['team']==team and native['opponent_team']==opponent
                n=np.zeros(5);c=np.zeros(5);u=np.zeros(5);v=np.zeros(5)
                for r in rs:
                    b=depth(r['air_yards']);h=down(r['down']);n[b]+=1;u[h]+=1
                    if r['complete_pass']==1:c[b]+=1;v[h]+=1
                label=native['values']['rec'] if native else None
                caught=sum(r['complete_pass']==1 for r in rs)
                row=dict(q,player_id=pid,role=role,targets=len(rs),completions=caught,N=n,C=c,U=u,V=v,
                    reception_match=label is not None and label==caught,
                    air_sum=sum(r['air_yards'] for r in rs if finite(r['air_yards'])),
                    air_n=sum(finite(r['air_yards']) for r in rs),
                    yac_sum=sum(r['yards_after_catch'] for r in rs if r['complete_pass']==1 and finite(r['yards_after_catch'])),
                    yac_n=sum(r['complete_pass']==1 and finite(r['yards_after_catch']) for r in rs),
                    short=sum(finite(r['ydstogo']) and r['ydstogo']<=3 for r in rs),
                    redzone=sum(finite(r['yardline_100']) and r['yardline_100']<=20 for r in rs),zero_proof=False)
                playergames.append(row);q['targets']+=len(rs);q['wrte_targets']+=len(rs) if role in ['WR','TE'] else 0
                q['N']+=n;q['C']+=c;q['U']+=u;q['V']+=v
            for native in by_native[game]:
                if native['team']!=team or native['position'] not in ['RB','WR','TE'] or native['player_id'] in groups:continue
                if not native['played'] or native['targets']!=0 or native['values']['rec']!=0:continue
                playergames.append(dict(q,player_id=native['player_id'],role=native['position'],targets=0,completions=0,
                    N=np.zeros(5),C=np.zeros(5),U=np.zeros(5),V=np.zeros(5),reception_match=True,
                    air_sum=0.,air_n=0,yac_sum=0.,yac_n=0,short=0,redzone=0,zero_proof=True))
            teams.append(q)
        self.all_teams=sorted_rows(teams);self.players=grouped(playergames,'player_id')
        qualified=[q for q in self.all_teams if q['complete']]
        self.offenses=grouped(qualified,'team');self.league=qualified
        self.defenses=grouped([dict(r,defense=r['opponent']) for r in self.all_teams],'defense')
        self.residual_cache={}

    def residual(self,g):
        key=(g['game_id'],g['team'])
        if key in self.residual_cache:return self.residual_cache[key]
        offense=prior(self.offenses.get(g['team'],[]),g['kickoff'],8)
        league=prior(self.league,g['kickoff'])
        ln=vector_sum(league,'N');lc=vector_sum(league,'C')
        baseline=np.divide(lc,ln,out=np.full(5,.5),where=ln>0)
        on=vector_sum(offense,'N');oc=vector_sum(offense,'C');rate=(oc+20*baseline)/(on+20)
        un=vector_sum(league,'U');uc=vector_sum(league,'V')
        downbase=np.divide(uc,un,out=np.full(5,.5),where=un>0)
        ou=vector_sum(offense,'U');ov=vector_sum(offense,'V');downrate=(ov+20*downbase)/(ou+20)
        la=sum(r['attempts'] for r in league);lw=sum(r['wrte_targets'] for r in league)
        lb=lw/la if la else .5;oa=sum(r['attempts'] for r in offense);ow=sum(r['wrte_targets'] for r in offense)
        role_rate=(ow+40*lb)/(oa+40)
        result={'R':g['C']-g['N']*rate,'S':g['V']-g['U']*downrate,
            'role_R':g['wrte_targets']-g['attempts']*role_rate,
            'offense_games':[r['game_id'] for r in offense],'league_games':len(league),
            'offense_N':on,'offense_C':oc,'league_N':ln,'league_C':lc,'baseline':baseline,'rate':rate,
            'role_league_attempts':la,'role_league_targets':lw,'role_offense_attempts':oa,
            'role_offense_targets':ow,'role_baseline':lb,'role_expected_rate':role_rate}
        self.residual_cache[key]=result
        return result

    def features(self,q,details=False):
        recent=prior(self.players.get(q['player_id'],[]),q['kickoff'],8)
        games=[r for r in recent if r['complete'] and r['reception_match'] and r['team']==q['team']]
        n=sum(r['targets'] for r in games);a=sum(r['attempts'] for r in games)
        own=[len(games),n,a,(q['kickoff']-games[-1]['kickoff'])/DAY if games else np.nan,float(n==0)]
        if n:
            an=sum(r['air_n'] for r in games);yn=sum(r['yac_n'] for r in games)
            own += [n/a if a else np.nan,n/len(games),sum(r['completions'] for r in games)/n,
                sum(r['air_sum'] for r in games)/an if an else np.nan,
                sum(r['yac_sum'] for r in games)/yn if yn else np.nan,
                sum(r['short'] for r in games)/n,sum(r['redzone'] for r in games)/n]
            own += (vector_sum(games,'N')/n).tolist()+(vector_sum(games,'U')/n).tolist()
        else:own += [np.nan]*17
        window=prior(self.defenses.get(q['opponent_team'],[]),q['kickoff'],8)
        defense=[r for r in window if r['complete']]
        nopp=sum(r['targets'] for r in defense);aopp=sum(r['attempts'] for r in defense)
        opp=[len(defense),nopp,(q['kickoff']-defense[-1]['kickoff'])/DAY if defense else np.nan,float(nopp==0)]
        if nopp:
            rs=[self.residual(g) for g in defense];R=sum((r['R'] for r in rs),np.zeros(5));S=sum((r['S'] for r in rs),np.zeros(5))
            bydepth=R/(vector_sum(defense,'N')+40);bydown=S/(vector_sum(defense,'U')+40)
            opp += [float(R.sum())/(nopp+40),sum(r['role_R'] for r in rs)/(aopp+80)]
            it=[float(np.asarray(own[12:17])@bydepth),float(np.asarray(own[17:22])@bydown)] if n else [np.nan,np.nan]
        else:opp += [np.nan,np.nan];it=[np.nan,np.nan]
        info={'own_window':recent,'own_used':games,'defense_window':window,'defense_used':defense}
        return (np.asarray(own),np.asarray(opp),np.asarray(it),info) if details else (np.asarray(own),np.asarray(opp),np.asarray(it))

def numerical(q):
    known=[r for r in q if r.get('actual') is not None and r.get('mean') is not None and r.get('median') is not None]
    if not known:return {'eligible':len(q),'known':0}
    return {'eligible':len(q),'known':len(known),'median_MAE':sum(abs(r['median']-r['actual']) for r in known)/len(known),
        'mean_MAE':sum(abs(r['mean']-r['actual']) for r in known)/len(known),
        'mean_RMSE':math.sqrt(sum((r['mean']-r['actual'])**2 for r in known)/len(known)),
        'mean_bias':sum(r['mean']-r['actual'] for r in known)/len(known),
        'played_zero':sum(r['actual']==0 for r in known),'fallback_known':sum(r.get('fallback',False) for r in known)}

def lattice_crps(law,y):
    """Independent CDF-squared lattice sum; does not call law.crps()."""
    v=np.asarray(law['values']);w=np.asarray(law['weights']);p=law['prior'];a=law['alpha'];k=round(y*law['scale'])
    tail=0 if p['empty'] or p['kind']=='event' else math.ceil(math.log(1e-15)/math.log(p['q']))
    lo=min(law['values']+[0,k,p['center']])-tail-3;hi=max(law['values']+[1,k,p['center']])+tail+3
    grid=np.arange(lo,hi+1);emp=np.r_[0.,np.cumsum(w)][np.searchsorted(v,grid,side='right')]
    if p['kind']=='event':priorcdf=np.where(grid<0,0.,np.where(grid>=1,1.,1-p['event']))
    elif p['empty']:priorcdf=(grid>=0).astype(float)
    elif p['kind']=='count':priorcdf=np.where(grid<0,0.,1-p['q']**(np.maximum(grid,0)+1))
    else:
        d=grid-p['center'];priorcdf=np.where(d>=0,1-p['q']**(np.maximum(d,0)+1)/(1+p['q']),p['q']**np.maximum(-d,0)/(1+p['q']))
    F=(1-a)*emp+a*priorcdf
    return float(np.sum((F-(grid>=k))**2))/law['scale']

def frozen_grades():
    """Optional finite follow-up: frozen freshness rows and new native grades."""
    shadow=ROOT/'prospective/shadows/AUDIT-D2-C-REC-W09-01'
    manifest=read(shadow/'RUN.json');proof=read(shadow/'SERVER_RECEIPT.json')
    graded=read(Path(__file__).with_name('FRESHNESS_SHADOW_GRADE.json'))
    assert sha(shadow/'ROWS.json.gz')==manifest['rows_SHA256']==graded['original_shadow_SHA256']
    for f in proof['fresh_GitHub_bytes']:assert sha(shadow/f['path'])==f['SHA256']
    lead=(pd.Timestamp(manifest['first_kickoff_UTC'])-pd.Timestamp(proof['server_completed_UTC'])).total_seconds()
    assert lead==3200 and manifest['new_fits']==0
    gp=ROOT/'prospective/grades/C-NATIVE-GRADE-20261107-JAXBAL-01-C-FWD-v4-20261105-W09-JAXBAL-remainder.json'
    assert sha(gp)==graded['canonical_grade_SHA256'];labels={r['forecast_id']:r for r in read(gp)['grades']}
    parent=ROOT/manifest['run_source'];assert sha(parent/'RUN.json')==manifest['parent_RUN_SHA256']
    assert sha(parent/'forecasts.json.gz')==manifest['parent_forecast_SHA256']
    original={r['forecast_id']:r for r in read(parent/'forecasts.json.gz')}
    saved={r['forecast_id']:r for r in graded['rows']};values=collections.defaultdict(list);adverse=collections.Counter();maxdelta=0.
    rows=read(shadow/'ROWS.json.gz');assert len(rows)==27
    for r in rows:
        g=labels[r['forecast_id']];s=saved[r['forecast_id']]
        assert g['state']==s['state'] and g['actual']==s['actual'] and r['actual'] is None and r['line'] is None and r['selected_side'] is None
        assert r['observed_law']==original[r['forecast_id']]['law']
        if g['state']!='GRADED_PLAYED':assert g['state']=='UNKNOWN';continue
        y=g['actual']
        for arm,mkey,medkey in [('observed','original_observed_mean','original_observed_median'),('proxy','proxy_mean','proxy_median')]:
            vals={arm+'_median_AE':abs(r[medkey]-y),arm+'_mean_SE':(r[mkey]-y)**2,
                  arm+'_CRPS':lattice_crps(r[arm+'_law'],y)}
            for key,val in vals.items():assert abs(val-s[key])<2e-11;values[key].append(val);maxdelta=max(maxdelta,abs(val-s[key]))
        adverse['observed_CRPS_lower' if s['observed_CRPS']<s['proxy_CRPS'] else 'proxy_CRPS_lower' if s['observed_CRPS']>s['proxy_CRPS'] else 'tied_CRPS']+=1
    metrics={k:float(np.mean(v)) for k,v in values.items()}
    for k,v in metrics.items():assert abs(v-graded['metrics'][k])<2e-11
    assert len(values['observed_CRPS'])==graded['graded']==19 and graded['unknown']==8
    freshness=dict(rows=27,known=19,unknown=8,pregame_server_lead_seconds=lead,metrics=metrics,
        max_independent_CDF_CRPS_or_error_difference=maxdelta,case_reversals=dict(adverse),
        frozen_rows_SHA256=sha(shadow/'ROWS.json.gz'),canonical_grade_SHA256=sha(gp),
        method='Independent squared-CDF lattice sum;tail probability below1e-15;not law.crps()',
        limits='One game,zero offers/query-only comparison under same seven-day-trained model;not aligned training/query repair or primary qualification.')
    # Small independent label/error check of the new original CINATL grade packet.
    version='C-NATIVE-GRADE-20261110-CINATL-01';packet=ROOT/'prospective/outcomes'/version/'OUTCOMES.json'
    outcome=read(packet)
    for e in outcome['source_evidence']:assert sha(packet.parent/e['path'])==e['SHA256']
    facts=pd.read_csv(packet.parent/'evidence/player_facts.csv.gz').astype(object)
    facts=facts.where(pd.notna(facts),None);facts={(r['game_id'],r['player_id']):r for r in facts.to_dict('records')}
    outcomes={(r['game_id'],r['player_id'],r['category']):r for r in outcome['outcomes']}
    grades=[];forecasts={}
    for label in ['pass_yd','remainder']:
        run=ROOT/'prospective/runs'/('C-FWD-v4-20261107-W09-CINATL-'+label)
        forecasts.update({r['forecast_id']:r for r in read(run/'forecasts.json.gz')})
        p=ROOT/'prospective/grades'/(version+'-'+run.name+'.json');g=read(p)
        assert g['forecast_SHA256']==sha(run/'forecasts.json.gz') and g['outcome_packet_SHA256']==sha(packet);grades+=g['grades']
    direct={'pass_yd':'passing_yards','pass_td':'passing_tds','pass_cmp':'completions','pass_att':'attempts',
            'pass_int':'passing_interceptions','rush_yd':'rushing_yards','rush_att':'carries','rec':'receptions','rec_yd':'receiving_yards'}
    weights={'passing_yards':2,'passing_tds':200,'passing_interceptions':-50,'rushing_yards':5,'rushing_tds':300,
             'receptions':50,'receiving_yards':5,'receiving_tds':300,'fumbles_lost_total':-50,
             'passing_2pt_conversions':100,'rushing_2pt_conversions':100,'receiving_2pt_conversions':100}
    states=collections.Counter();delta=0.
    for g in grades:
        r=forecasts[g['forecast_id']];key=(r['game_id'],r['player_id']);f=facts.get(key);a=outcomes[(*key,r['category'])];states[g['state']]+=1
        assert r['espn_event_id']==a['espn_event_id']=='401873038' and a['event_status']=='FINAL'
        assert pd.Timestamp(a['observed_UTC'])>pd.Timestamp(r['kickoff_UTC'])
        played=f is not None and (any(finite(f.get(k)) and f[k]>0 for k in PHYSICAL) or any(finite(f.get(k)) and f[k]!=0 for k in SIGNED))
        if not played:assert g['state']=='UNKNOWN' and g['actual'] is None;continue
        assert f['team']==r['team'] and f['opponent_team']==r['opponent_team'];cat=r['category']
        y=f[direct[cat]] if cat in direct else f['rushing_yards']+f['receiving_yards'] if cat=='rush_rec_yd' else int(f['rushing_tds']+f['receiving_tds']>0) if cat=='anytime_td' else None
        if cat=='fpts':assert f['fumble_recovery_tds']==f['special_teams_tds']==0;y=sum(f[k]*w for k,w in weights.items())/50
        assert g['state']=='GRADED_PLAYED' and y==g['actual']==a['actual'];score=lattice_crps(r['law'],y);assert abs(score-g['CRPS'])<2e-10;delta=max(delta,abs(score-g['CRPS']))
        if r['mean'] is not None:assert abs(g['absolute_error']-abs(r['median']-y))<1e-12 and abs(g['mean_squared_error']-(r['mean']-y)**2)<1e-12
    assert len(grades)==179 and states=={'GRADED_PLAYED':99,'UNKNOWN':80}
    return {'freshness_shadow':freshness,'CINATL_native_minimal':dict(issued=179,states=dict(states),
        appended_outcome_version=version,outcome_packet_SHA256=sha(packet),
        all_direct_signed_anytime_chart_labels_and_point_errors='PASS',independent_lattice_CRPS_max_difference=delta,
        offers=0,new_fits=0,source_scope='Retained qualified outcome projection and existing immutable original forecasts;no new source request')}

def run():
    raw,players,schedule,frames=inputs();audit=RawArithmetic(raw,players,schedule,frames)
    from context_features_c01 import Context,OWN_NAMES,OPP_NAMES,INTER_NAMES
    assert OWN==OWN_NAMES and OPP==OPP_NAMES and INTER==INTER_NAMES
    implementation=Context(frames,players,schedule,strict=True,all_position_counts=audit.counts)
    exports={(r['game_id'],r['player_id']):r for r in read(ART/'v1.1/FEATURE_EXPORT.json.gz')}
    native={r['offer_id']:r for r in read(ART/'native-query-extension-v1/FEATURES.json.gz')}
    from context_identity_view_c01 import corrected_rows
    rows=corrected_rows();e2=sorted([r for r in rows if r['method']=='E2'],key=lambda r:(r['game_id'],r['player_id']))
    def query(r):
        g=audit.games[r['game_id']]
        return dict(game_id=r['game_id'],player_id=r['player_id'],team=r['team'],opponent_team=r['opponent_team'],
            position=r['position'],kickoff=g['kickoff'])
    selected=[];used=set()
    for label,predicate in [('win',lambda r:r['status']=='WIN'),('loss',lambda r:r['status']=='LOSS'),
                            ('ordinary',lambda r:r['actual'] is not None and r['actual']>0),
                            ('unknown',lambda r:r['appearance']=='UNKNOWN' and r['offer_id'] in native)]:
        r=next(r for r in e2 if predicate(r) and (r['game_id'],r['player_id']) not in used
            and audit.features(query(r))[0][1]>0 and audit.features(query(r))[1][1]>0)
        used.add((r['game_id'],r['player_id']));selected.append((label,r,query(r)))
    zeros=sorted([r for r in exports.values() if r['own'][0]>0 and r['own'][1]==0 and r['own'][2]>0],key=lambda r:(r['origin'],r['game_id'],r['player_id']))
    z=next(r for r in zeros if audit.native[(r['game_id'],r['player_id'])]['values']['rec']==0)
    q=dict(z,opponent_team=z['opponent'],kickoff=audit.games[z['game_id']]['kickoff']);selected.append(('zero_target',dict(z,actual=0,status='FORECAST_ONLY_NUMERICAL;NO_OFFER'),q))
    cases=[]
    for label,r,q in selected:
        own,opp,it,info=audit.features(q,True);actual=implementation.features(q)
        for a,b in zip((own,opp,it),actual):equal(a,b)
        saved=exports.get((q['game_id'],q['player_id']))
        ref=(saved['own'],saved['opponent_values'],saved['predicted_mix_interactions']) if saved else (native[r['offer_id']]['own'],native[r['offer_id']]['opponent'],native[r['offer_id']]['interactions'])
        for a,b in zip((own,opp,it),ref):equal(a,b)
        games=info['own_used'];detail=[]
        for g in games:
            detail.append(dict(game_id=g['game_id'],kickoff_UTC=pd.Timestamp(g['kickoff'],unit='s',tz='UTC').isoformat(),
                available_UTC=pd.Timestamp(g['available'],unit='s',tz='UTC').isoformat(),targets=g['targets'],receptions=g['completions'],
                official_team_attempts=g['attempts'],depth_target_counts=g['N'],down_target_counts=g['U'],
                air_sum=g['air_sum'],known_air_targets=g['air_n'],YAC_sum=g['yac_sum'],known_YAC_catches=g['yac_n'],
                played_zero_target_proof=g['zero_proof']))
        case=dict(id='C-RAW-'+label.upper(),game_id=q['game_id'],player_id=q['player_id'],team=q['team'],opponent=q['opponent_team'],role=q['position'],
            cutoff_UTC=pd.Timestamp(q['kickoff'],unit='s',tz='UTC').isoformat(),target_actual=r.get('actual'),target_grade=r.get('status'),
            fields=dict(zip(OWN+OPP+INTER,np.r_[own,opp,it])),own_prior_games=detail,
            raw_targets_denominator=int(own[1]),raw_official_attempt_denominator=int(own[2]),
            matched_saved_vector=True,matched_production_vector=True)
        if label=='zero_target':
            assert own[0]>0 and own[2]>0 and own[1]==0 and all(g['zero_proof'] for g in games)
            case['known_but_omitted_volume_ratios']={'targets_per_team_attempt':0.,'targets_per_appearance':0.}
            case['quality_rates']='Catch/target,depth/down mixture,mean air/YAC have zero eligible target/catch denominator and are undefined;storedNaN is appropriate there.'
        if label=='unknown':
            case['target_source_row_present']=(q['game_id'],q['player_id']) in audit.native
            assert r['actual'] is None and r['appearance']=='UNKNOWN'
            case['unknown_not_DNP_or_zero']=True
        # One source play demonstrates that air/down binning is targeted-pass context, not alignment.
        if games and games[-1]['targets']:
            g=games[-1];play=next(p for p in audit.play_groups[(g['game_id'],g['team'])] if p['receiver_player_id']==q['player_id'])
            case['one_retained_play']=dict(game_id=g['game_id'],play_id=play['play_id'],air_yards=play['air_yards'],depth_bin=depth(play['air_yards']),
                down=play['down'],down_bin=down(play['down']),complete_pass=play['complete_pass'],yards_after_catch=play['yards_after_catch'])
        cases.append(case)
    # Work through an actual prior defense game, adjusted using the offense's own pregame prefix.
    q=selected[2][2];own,opp,it,info=audit.features(q,True);defense=info['defense_used'];g=defense[-1];res=audit.residual(g);b=1
    totalN=sum(r['targets'] for r in defense);totalA=sum(r['attempts'] for r in defense);Rs=[audit.residual(r) for r in defense];sumR=sum((r['R'] for r in Rs),np.zeros(5));sumRole=sum(r['role_R'] for r in Rs)
    equal([sumR.sum()/(totalN+40),sumRole/(totalA+80)],opp[-2:])
    bybin=sumR/(vector_sum(defense,'N')+40);equal([np.asarray(own[12:17])@bybin],[it[0]])
    example={'future_query':q,'prior_defense_games':[r['game_id'] for r in defense],'prior_game':g['game_id'],'offense':g['team'],'defense':g['opponent'],
        'depth_bin':'0_to_9_air_yards','earlier_league_targets':res['league_N'][b],'earlier_league_catches':res['league_C'][b],
        'earlier_league_completion_rate':res['baseline'][b],'earlier_offense_games':res['offense_games'],
        'earlier_offense_targets':res['offense_N'][b],'earlier_offense_catches':res['offense_C'][b],
        'offense_expected_catch_rate':res['rate'][b],'observed_game_targets':g['N'][b],'observed_game_catches':g['C'][b],
        'game_catch_residual':res['R'][b],'all_bins_all_defense_games_residual_sum':sumR.sum(),
        'defense_identified_targets':totalN,'main_completion_feature':opp[-2],
        'defense_official_attempts':totalA,'WRTE_role_residual_sum':sumRole,'main_WRTE_role_feature':opp[-1],
        'depth_bin_residual_sums':sumR,'depth_bin_target_totals':vector_sum(defense,'N'),'depth_bin_shrunk_residuals':bybin,
        'predicted_own_depth_mix':own[12:17],'own_mix_weighted_depth_interaction':it[0],
        'naive_unweighted_mean_game_catch_residual_rate':float(np.mean([r['R'].sum()/g['targets'] for r,g in zip(Rs,defense)]))}
    # Prefix and production mutation checks: only memory changes, no fit/source rewrite.
    base_query=selected[2][2];before=implementation.features(base_query);cut=base_query['kickoff'];modified=players.copy(deep=True);modified['values']=[dict(v) for v in players['values']]
    for i in modified.index[modified.kickoff>=cut]:modified.at[i,'values']['rec']=999
    ff=[f.copy(deep=True) for f in frames];times=dict(zip(schedule.game_id,schedule.kickoff))
    for f in ff:
        m=f.game_id.map(times)>=cut;f.loc[m,'air_yards']=777.;f.loc[m,'complete_pass']=1-f.loc[m,'complete_pass']
    future=ff[-1][ff[-1].game_id.map(times)>cut].iloc[0].copy();future['play_id']=99999999;ff[-1]=pd.concat([ff[-1],pd.DataFrame([future])],ignore_index=True)
    altered=Context(ff,modified,schedule,strict=True,all_position_counts=audit.counts)
    for a,bv in zip(before,altered.features(base_query)):equal(a,bv)
    pgame=audit.features(base_query,True)[3]['own_used'][-1];boundary=pgame['available'];rs=audit.players[base_query['player_id']]
    assert pgame not in prior(rs,boundary) and pgame in prior(rs,boundary+.001)
    pp=implementation.players.before(base_query['player_id'],boundary,100000);qq=implementation.players.before(base_query['player_id'],boundary+.001,100000)
    assert not any(x['game_id']==pgame['game_id'] for x in pp) and any(x['game_id']==pgame['game_id'] for x in qq)
    # Same-row numerical views: preserve the broader panel and native-extension row separately.
    numbers=read(ART/'v1.1/NUMERICAL_ROWS.json.gz');pop=[];pairs=[]
    for scope,roles in [('ALL_SUPPORTED',['RB','WR','TE']),('WR_TE',['WR','TE']),('RB',['RB'])]:
        for method in ['P1','P2','P3']:
            broad=[r for r in numbers if r['procedure']==method and r['position'] in roles]
            sameweeks=[r for r in broad if r['origin'] in ['2026-W02','2026-W03']]
            offered=[r for r in rows if r['method']==method and r['position'] in roles]
            for panel,qs in [('2026W1_W8_stat_row_panel',broad),('2026W2_W3_stat_row_panel',sameweeks),('2026W2_W3_all_offers_native_extended',offered)]:
                pop.append(dict(scope=scope,method=method,panel=panel,**numerical(qs)))
        mean={r['offer_id']:r for r in rows if r['method']=='RETAINED_P1_MEAN' and r['position'] in roles}
        median={r['offer_id']:r for r in rows if r['method']=='RETAINED_P1_MEDIAN' and r['position'] in roles}
        common={k for k,r in mean.items() if r['actual'] is not None and r.get('point') is not None and median[k].get('point') is not None}
        reference=[dict(actual=mean[k]['actual'],mean=mean[k]['point'],median=median[k]['point']) for k in sorted(common)]
        pairs.append(dict(scope=scope,method='RETAINED_LEAF_typed_mean_median',common_player_games=len(common),**numerical(reference)))
        for method in ['P1','P2','P3']:
            q=[r for r in rows if r['method']==method and r['position'] in roles and r['offer_id'] in common]
            pairs.append(dict(scope=scope,method=method,common_player_games=len(common),**numerical(q)))
    # Reconcile every own-side/control row from original selections, never from the winner.
    saved=read(ROOT/'reports/player-context-matchup-01/ACTUAL_LINE_SCORES.json.gz');checks=[]
    for scope,roles in [('ALL_SUPPORTED',['RB','WR','TE']),('WR_TE',['WR','TE']),('RB',['RB'])]:
        for method in sorted({r['method'] for r in rows}):
            q=[r for r in rows if r['method']==method and r['position'] in roles]
            s=next(r for r in saved if r['week']=='ALL' and r['scope']==scope and r['method']==method)
            for r in q:
                if r['status'] in ['WIN','LOSS']:assert ((r['actual']>r['line'])==(r['selected_side']=='OVER'))==(r['status']=='WIN')
            item=dict(scope=scope,method=method,eligible=len(q),unknown=sum(r['status']=='UNKNOWN_PARTICIPATION' for r in q),sides={})
            for name,ss in [('OVER',['OVER']),('UNDER',['UNDER']),('COMBINED',['OVER','UNDER'])]:
                v=[r for r in q if r['selected_side'] in ss];w=sum(r['status']=='WIN' for r in v);l=sum(r['status']=='LOSS' for r in v);x=s[name]
                assert x['selected']==len(v) and (x['wins'] or 0)==w and (x['losses'] or 0)==l and x['decided']==w+l
                rate=w/(w+l) if w+l else None
                if rate is None:assert x['rate'] is None
                else:assert abs(rate-x['rate'])<1e-14
                item['sides'][name]=[w,l,w+l,rate]
            checks.append(item)
    held=[dict(game_id=r['game_id'],team=r['team'],PBP_attempts=r['attempts'],PBP_named_targets=r['targets'],PBP_completions=float(r['C'].sum()),official=r['official']) for r in audit.all_teams if not r['complete']]
    report={'id':'PLAYER-CONTEXT-ACCEPTANCE-01-C-RAW-v1','evidence_pin':PIN,
        'verdict':'PASS_WITH_EXPLICIT_ZERO_REPRESENTATION_AND_RECONSTRUCTION_LIMITS','new_fits':0,'network_requests':0,
        'reference_arithmetic':'Independent raw-play/stat grouping and direct eligible-prefix enumeration; production Context used only for comparison/mutation.',
        'cases':cases,'opponent_worked_example':example,'held_source_team_games':held,
        'equations':{'availability':'prior_game_kickoff+7days < query_cutoff; current/revised reconstruction assumption, not authenticated publication.',
            'offense_expected_bin_rate':'r(g,b)=(sum_C_of_last8_qualified_own_games_before_g +20*earlier_league_C_b/N_b)/(sum_N_of_those_own_games +20);empty league bin=0.5.',
            'prior_game_residual':'R(g,b)=observed_catches(g,b)-identified_targets(g,b)*r(g,b); offense baseline is constructed BEFORE g.',
            'opponent_main':'sum_g,b R(g,b)/(sum_g identified_targets_g+40); signed unitless completion residual, not a causal defense score.',
            'role':'WRTE targets per OFFICIAL TEAM ATTEMPT; prior offense shrink40attempts, final opponent residual shrink80attempts.',
            'interaction':'sum_b(predicted own earlier target-depth share_b * sum_g R(g,b)/(sum_g N(g,b)+40)); down interaction analogous.',
            'windows':'Own/defense take eight eligible game-context rows THEN hold unqualified rows without backfill. Historical offense prior filters qualified team games BEFORE last8. League prior uses all earlier qualified games.',
            'weighting':'Counts pooled by their actual exposure, not equal weighting of game percentages; bin-specific interactions add40pseudo-targets perbin while main completion adds40total.'},
        'meaning_limits':['Targeted-pass depth/down/field position are not alignment, routes, matchup responsibility or all-route openness.',
            'Team attempts include official spikes/throwaways/unallocated attempts; named-target bin summaries omit unidentified receivers, not silently allocating them.',
            'Air yards denominator=known-air named targets; YAC denominator=completed named targets with known YAC, not all targets/receptions.',
            'Knownzero-target volume ratios are mathematically0 but omitted in saved vectors; quality ratios with zero target/catch denominator are undefined. Games/targets=0/teamattempt counts remain observed, not unknown/DNP.',
            'Verification case selection by win/loss class is an audit only; it does not change experiment membership or choose a forecasting recipe.'],
        'mutation_and_cutoff':{'actual_production_current_future_outcome_and_PBP_mutation_plus_appended_future_play':'UNCHANGED',
            'strict_equal_availability_excluded_then_included_1ms_later':'PASS','only_memory_mutated':True,
            'forecast_mutation_trace_reused':'reports/player-context-matchup-01/INDEPENDENT_VERIFICATION.json.gz; no closed tree-use diagnosis repeated'},
        'population_numerical_views':pop,'paired_retained_point_control_common_mask':pairs,
        'population_limit':'All-offers native extension includes one playedzero RB outside the original stat-role numerical panel; pairwise reference has337known rows, full new counts338. Same-period panel and W1-W8 panel are different populations; no gain is attributed merely to membership.',
        'own_side_and_control_arithmetic':checks,'neutral_probability_reference':{'half_scaled_U_P_O_Brier':.25,'scope':'decisive half-point event only;not a fitted law or sportsbook price'},
        'qualification':'Two exposed actual-line weeks; statistical box-score direction, book settlement unverified. No primary admission or A/B acknowledgement.',
        'frozen_grade_followup':frozen_grades(),
        'bindings':[dict(path=str(p.relative_to(ROOT)),SHA256=sha(p)) for p in [ROOT/'src/context_features_c01.py',SOURCE/'pbp_facts_2025.csv.xz',SOURCE/'pbp_facts_2026.csv.xz',ROOT/'artifacts/basic-football-facts-v2.1.zip',ART/'v1.1/FEATURE_EXPORT.json.gz',ART/'ROW_IDENTITY_CORRECTION-v1.json.gz',ART/'CANONICAL_REPORT_ROWS.json.gz']],
        'reproduction_script_SHA256':sha(__file__),'resources':{'CPU_seconds':time.process_time()-START,'peak_RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,'one_thread':True,'large_temporary_copies':0}}
    assert report['resources']['CPU_seconds']<=90 and report['resources']['peak_RSS_bytes']<=1288490188
    body=(json.dumps(clean(report),indent=2,allow_nan=False)+'\n').encode()
    assert len(body)+Path(__file__).stat().st_size<=120*1024
    OUT.write_bytes(body)
    print(json.dumps({'verdict':report['verdict'],'cases':len(cases),'held_team_games':held,'CPU_seconds':report['resources']['CPU_seconds'],'RSS':report['resources']['peak_RSS_bytes'],'combined_bytes':len(body)+Path(__file__).stat().st_size}))

if __name__=='__main__':
    try:run()
    finally:signal.setitimer(signal.ITIMER_PROF,0)
