"""Zero-refit future query timing comparison; not a grader or pick selector.

The same frozen seven-day-trained model is queried with its declared observed
prefix and a seven-day proxy prefix. No claim of aligned retraining or of
authentic historical source clocks is made by this query-only comparison.
"""
import argparse,gzip,hashlib,json,math,time,subprocess,resource,signal
from pathlib import Path
import numpy as np
import pandas as pd
from data_v2 import load,History,vector
from prospective_v4 import read_json,unpack,ObservedHistory,qualified_training_frame,stamp,filehash
from safe_models_v4 import load as load_model,infer_forest,law_data

class ProxyAtCutoff(History):
    def __init__(self,rows,key,cutoff):super().__init__(rows,key);self.cutoff=cutoff
    def before(self,key,cutoff,n=8):return super().before(key,min(cutoff,self.cutoff),n)

def compare(run):
    m=read_json(run/'RUN.json');original=[r for r in unpack(run/'forecasts.json.gz') if r['category']=='rec'];assert len(original)==27
    cutoff=pd.Timestamp(m['information_cutoff_UTC']).timestamp();d,g,teams=load(run/'sources');source=read_json(run/'sources/SOURCE_MANIFEST.json');completed=source['completed_game_ids'];d=qualified_training_frame(d,completed,cutoff);teams=teams[teams.game_id.isin(completed)&(teams.kickoff<cutoff)]
    ph,th=ProxyAtCutoff(d,'player_id',cutoff),ProxyAtCutoff(teams,'team',cutoff);oh,ot=ObservedHistory(d,'player_id',cutoff),ObservedHistory(teams,'team',cutoff);model=next(x for x in read_json(run/'model_manifest.json') if x['target']=='rec');numeric=load_model(run/model['artifact'],model['model_SHA256'])
    matrices=[];diagnostics=[]
    for r in original:
        q=dict(r,kickoff=pd.Timestamp(r['kickoff_UTC']).timestamp());observed=vector(q,'rec',oh,ot,r['arm']);proxy=vector(q,'rec',ph,th,r['arm']);saved=np.asarray([np.nan if x is None else x for x in r['features']]);assert np.array_equal(observed,saved,equal_nan=True)
        matrices.append(proxy);rr=ph.before(r['player_id'],q['kickoff']);diagnostics.append(dict(forecast_id=r['forecast_id'],player_id=r['player_id'],name=r['name'],position=r['position'],game_id=r['game_id'],availability=r['availability'],selection_availability=r['selection_availability'],changed_features=int(np.sum(~np.isclose(proxy,observed,equal_nan=True))),proxy_support=int(proxy[3]),observed_support=int(observed[3]),proxy_latest_game=rr[-1]['game_id'] if rr else None,proxy_feature_age_days=(q['kickoff']-rr[-1]['kickoff'])/86400 if rr else None,observed_target_lag_age_days=r['features'][5],original_observed_mean=r['mean'],original_observed_median=r['median'],appearance_conditioning=r['appearance_conditioning'],actual=None,line=None,selected_side=None))
    laws=infer_forest(numeric,np.asarray(matrices),[r['position'] for r in original])
    for q,r,law in zip(diagnostics,original,laws):q.update(proxy_mean=law.mean(),proxy_median=law.quantile(.5),proxy_law=law_data(law),observed_law=r['law'],mean_changed=not math.isclose(law.mean(),r['mean'],abs_tol=1e-10,rel_tol=1e-12),median_changed=law.quantile(.5)!=r['median'])
    return m,model,diagnostics

def issue(run,out):
    assert not subprocess.check_output(['git','status','--porcelain'],text=True).strip(),'COMMIT_SHADOW_CODE_AND_REGISTRATION_FIRST'
    start=time.process_time();assert not out.exists();m,model,rows=compare(run)
    assert pd.Timestamp(stamp())+pd.Timedelta(seconds=300)<pd.Timestamp(m['first_kickoff_UTC'])
    out.mkdir(parents=True);b=gzip.compress(json.dumps(rows,separators=(',',':'),allow_nan=False).encode(),mtime=0);(out/'ROWS.json.gz').write_bytes(b)
    packet=dict(schema='C-FRESHNESS-QUERY-SHADOW-v1',created_UTC=stamp(),run_source=str(run),parent_RUN_SHA256=filehash(run/'RUN.json'),parent_forecast_SHA256=filehash(run/'forecasts.json.gz'),model_SHA256=model['model_SHA256'],information_cutoff_UTC=m['information_cutoff_UTC'],first_kickoff_UTC=m['first_kickoff_UTC'],target='rec',history='Same frozen H-MULTI seven-day-trained model; no feature/model refit',policies=['CAPTURED_OBSERVED_QUERY_ORIGINAL','SEVEN_DAY_PROXY_QUERY_AT_SAME_CAPTURE_CUTOFF'],rows=len(rows),feature_changed_rows=sum(r['changed_features']>0 for r in rows),mean_changed_rows=sum(r['mean_changed'] for r in rows),median_changed_rows=sum(r['median_changed'] for r in rows),source_clock_tier='Authentic current C receipt; historical source vintages remain revised and unauthenticated',forecast_only=True,actual_offers=0,selected_picks=0,new_fits=0,primitive_inferences=len(rows),CPU_seconds=time.process_time()-start,rows_SHA256=hashlib.sha256(b).hexdigest(),state='RESEARCH_SHADOW_AWAITING_SERVER_PERSISTENCE;NO_ACCURACY_YET',limitation='Query-only comparison diagnoses the disclosed training/query age mismatch. It does not repair or certify an aligned historical training procedure. Later final outcomes and real offers are needed for accuracy.')
    packet['execution_code_commit']=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();packet['execution_code_SHA256']=filehash(Path(__file__));packet['peak_RSS_bytes']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
    (out/'RUN.json').write_text(json.dumps(packet,indent=2)+'\n');assert packet['CPU_seconds']<30 and packet['peak_RSS_bytes']<805306368 and len(b)<1048576;print('FRESHNESS_QUERY_SHADOW',len(rows),packet['feature_changed_rows'],packet['mean_changed_rows'],packet['median_changed_rows'])

def verify(out):
    m=read_json(out/'RUN.json');run=Path(m['run_source']);assert m['schema']=='C-FRESHNESS-QUERY-SHADOW-v1' and m['rows_SHA256']==filehash(out/'ROWS.json.gz') and m['parent_forecast_SHA256']==filehash(run/'forecasts.json.gz') and m['parent_RUN_SHA256']==filehash(run/'RUN.json')
    _,model,expected=compare(run);saved=unpack(out/'ROWS.json.gz');assert len(saved)==m['rows']==27 and model['model_SHA256']==m['model_SHA256']
    reconcile_numeric_rows(saved,expected)
    assert all(r['actual'] is None and r['line'] is None and r['selected_side'] is None for r in saved)
    print('FRESHNESS_QUERY_SHADOW_VERIFIED_NO_FITS',len(saved))

def reconcile_numeric_rows(saved,expected):
    """Keep source/identity/support/median exact; allow only numeric reduction ULPs.

    Mean tolerance is the existing prospective_v4 safe-model restoration rule.
    Empirical weights use a tighter absolute bound. No stored value is changed.
    """
    assert len(saved)==len(expected)
    mean_delta=[];weight_delta=[]
    for a,b in zip(saved,expected):
        aa={k:v for k,v in a.items() if k not in ['proxy_mean','proxy_law']};bb={k:v for k,v in b.items() if k not in ['proxy_mean','proxy_law']}
        assert aa==bb,('NONNUMERIC_OR_TYPED_OUTPUT_MISMATCH',[k for k in aa if aa[k]!=bb.get(k)])
        la={k:v for k,v in a['proxy_law'].items() if k!='weights'};lb={k:v for k,v in b['proxy_law'].items() if k!='weights'}
        assert la==lb,'LAW_SUPPORT_PRIOR_OR_SCALE_CHANGED'
        delta=abs(a['proxy_mean']-b['proxy_mean']);mean_delta.append(delta)
        assert math.isclose(a['proxy_mean'],b['proxy_mean'],rel_tol=1e-12,abs_tol=1e-10),('MEAN_RESTORATION_MISMATCH',delta)
        w,v=a['proxy_law']['weights'],b['proxy_law']['weights'];assert len(w)==len(v)
        for x,y in zip(w,v):
            delta=abs(x-y);weight_delta.append(delta);assert math.isfinite(x) and math.isfinite(y) and delta<=1e-14,('WEIGHT_RESTORATION_MISMATCH',delta)
    print('RESTORATION_NUMERIC_DELTAS',json.dumps(dict(mean_differences=sum(x!=0 for x in mean_delta),max_mean_absolute_difference=max(mean_delta,default=0),weight_differences=sum(x!=0 for x in weight_delta),max_weight_absolute_difference=max(weight_delta,default=0)),sort_keys=True))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['issue','verify']);p.add_argument('--run',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    signal.signal(signal.SIGPROF,lambda *_:(_ for _ in ()).throw(RuntimeError('FRESHNESS_SHADOW_CPU_CAP')));signal.setitimer(signal.ITIMER_PROF,30)
    try:issue(a.run,a.output) if a.command=='issue' else verify(a.output)
    finally:signal.setitimer(signal.ITIMER_PROF,0)
