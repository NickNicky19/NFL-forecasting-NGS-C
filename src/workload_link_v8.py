"""One registered attempt-marginal challenger; historical exposure only in fits.

At inference every target-game attempt/outcome is unnecessary. Conditional yard
quality is fixed between the linked control and the new workload marginal.
"""
import argparse,gzip,hashlib,json,math,pickle,resource,signal,time,zipfile
from collections import defaultdict
from pathlib import Path
import numpy as np
from threadpoolctl import threadpool_limits
from data_v2 import load,History,vector
from laws_v2 import LeafModel,Law,Prior,design
from safe_models_v4 import export_forest,infer_forest,prior_load,law_data,validate_training_model
from reliability_v8 import ROOT,ART,OUT,read,write
import actual_accuracy_v6 as a

def bins(n):return np.select([n==0,n<=14,n<=24,n<=34,n<=44],[0,1,2,3,4],default=5).astype(int)
def route(tree,z):
    node=np.zeros(len(z),int);left=np.asarray(tree['left']);right=np.asarray(tree['right']);f=np.asarray(tree['feature']);th=np.asarray(tree['threshold'])
    for _ in range(10):
        ix=np.flatnonzero(left[node]>=0)
        if not len(ix):return node
        nn=node[ix];node[ix]=np.where(z[ix,f[nn]].astype(float)<=th[nn],left[nn],right[nn])
    raise ValueError('TREE_DEPTH_OR_CYCLE')
def joint_export(y_model,x,y,n):
    assert len(x)==len(y)==len(n) and np.all(np.isfinite(n)) and np.all(n>=0) and np.all(n==np.rint(n))
    assert np.all(y[n==0]==0),'ZERO_ATTEMPT_YARD_CONTRACT_CONFLICT'
    z=design(np.asarray(x,float),np.asarray(y_model['imputation'])).astype(np.float32);bb=bins(n);trees=[]
    for tree in y_model['trees']:
        nodes=route(tree,z);joint={}
        for node in np.unique(nodes):
            ix=nodes==node;vals,counts=np.unique(y[ix],return_counts=True)
            assert [vals.tolist(),counts.tolist()]==tree['leaves'][str(node)],'JOINT_DID_NOT_MARGINALIZE_TO_RETAINED_Y_COUNTS'
            pairs,c=np.unique(np.column_stack([bb[ix],y[ix]]),axis=0,return_counts=True);joint[str(node)]=[[int(b),int(v),int(count)] for (b,v),count in zip(pairs,c)]
        trees.append({k:tree[k] for k in ['left','right','feature','threshold']}|dict(joint=joint))
    glob={}
    for b in range(1,6):
        yy=y[bb==b];fallback=False
        if not len(yy):yy=y[n>0];fallback=True
        v,c=np.unique(yy,return_counts=True);assert len(v);glob[str(b)]=dict(values=v.tolist(),counts=c.tolist(),empty_global_bin_fallback=fallback)
    return dict(schema='C-YARD-ATTEMPT-JOINT-v8',imputation=y_model['imputation'],prior=y_model['prior']['QB'],trees=trees,global_bins=glob,empirical_Y_marginal_verified=True)
def joint_components(j,features):
    z=design(np.asarray([features],float),np.asarray(j['imputation'])).astype(np.float32);mass=[defaultdict(float) for _ in range(6)]
    for tree in j['trees']:
        node=int(route(tree,z)[0]);triples=tree['joint'][str(node)];total=sum(c for b,y,c in triples)
        for b,y,c in triples:mass[b][y]+=c/total/len(j['trees'])
    weights=np.asarray([sum(m.values()) for m in mass]);assert abs(weights.sum()-1)<1e-10
    return weights,mass
def linked_law(j,features,weights=None):
    original,joint=joint_components(j,features);weights=original if weights is None else np.asarray(weights,float)
    assert len(weights)==6 and min(weights)>=-1e-10 and abs(weights.sum()-1)<1e-10
    weights=np.maximum(weights,0);weights/=weights.sum();emp=defaultdict(float);emp[0]+=float(weights[0]);fallback_mass=0.;empty_global_mass=0.
    for b in range(1,6):
        weight=float(weights[b])
        if not weight:continue
        if original[b]>0:dist={y:v/original[b] for y,v in joint[b].items()}
        else:
            g=j['global_bins'][str(b)];tot=sum(g['counts']);dist={int(y):c/tot for y,c in zip(g['values'],g['counts'])};fallback_mass+=weight
            if g['empty_global_bin_fallback']:empty_global_mass+=weight
        for y,p in dist.items():emp[y]+=.95*weight*p
    alpha=.05*float(1-weights[0])
    if alpha<=0:law=Law([],[],Prior([],'signed'))
    else:
        values=sorted(emp);assert abs(sum(emp.values())-(1-alpha))<1e-10;law=Law(values,[emp[v] for v in values],prior_load(j['prior']),alpha=alpha)
    return law,dict(bin_weights=weights.tolist(),leaf_bin_weights=original.tolist(),leaf_missing_bin_forecast_mass=fallback_mass,empty_global_bin_forecast_mass=empty_global_mass,prior_alpha=alpha)
def forecast_bins(law):
    c=np.asarray([law.cdf(n) for n in [0,14,24,34,44]]);q=np.diff(np.r_[0,c,1]);assert min(q)>=-1e-10 and abs(q.sum()-1)<1e-10;return q

def old_model(season,week):
    if season==2026:
        entry=next(e for e in read(ROOT/'reports/GITHUB_EVIDENCE_MANIFEST_V2.json') if e['category']=='pass_yd');path=entry['path'];expected=entry['sha256'];prefix=f'C-ALL12-LAW-THRESHOLD-v2.1-pass_yd-H-MULTI-P2_LEAF-E0_OP-W{week:02}'
    else:
        entry=next(e for e in read(ROOT/'reports/robustness-v3/GITHUB_RESTORE.json')['archives'] if e['category']=='pass_yd');path=entry['archive'];expected=entry['SHA256'];prefix=f'raw/pass_yd/W{week:02}'
    assert a.sha(ROOT/path)==expected
    with zipfile.ZipFile(ROOT/path) as z:
        done=json.loads(z.read(prefix+'/DONE.json'));rb=z.read(prefix+'/rows.json.gz');assert hashlib.sha256(rb).hexdigest()==done['row_sha256'];rows=json.loads(gzip.decompress(rb))
        if season==2026:model=read(ROOT/f'reports/propline-v7/models/pass_yd-W{week:02}.json.gz')
        else:
            mb=z.read(prefix+'/model.pkl.gz');assert hashlib.sha256(mb).hexdigest()==done['model_sha256'];trusted=pickle.loads(gzip.decompress(mb))['model'];model=export_forest(trusted)
    return model,rows,done,dict(path=path,SHA256=expected,prefix=prefix)

def run(inputs):
    protocol=read(ROOT/'protocol/WORKLOAD_LINK_V8.json');assert a.sha(inputs/'facts.csv.gz')==protocol['source_facts_SHA256'];assert a.sha(inputs/'schedule.csv')=='5ac3af003131a316eadba4bf90f9758953cef7a41bb6359fb5eb7d90d8a170f0'
    ledger_path=ART/'FIT_LEDGER.json';ledger=read(ledger_path) if ledger_path.exists() else dict(id=protocol['id'],fit_attempts=0,completed=[],failures=[],new_Y_fits=0,new_calibrators=0)
    assert not (ART/'WORKLOAD_PREDICTIONS.json.gz').exists(),'FROZEN_WORKLOAD_OUTPUT_EXISTS'
    start=time.monotonic();cpu=time.process_time();signal.signal(signal.SIGPROF,lambda *_:(_ for _ in ()).throw(RuntimeError('REGISTERED_CPU_CAP180')));signal.setitimer(signal.ITIMER_PROF,180)
    try:
        d,g,teams=load(inputs);pool=d[d.position=='QB'].to_dict('records');hist=History(d[d.season>=2022],'player_id');th=History(teams[teams.season>=2022],'team');xx=np.asarray([vector(r,'pass_yd',hist,th,'E0_OP') for r in pool],float);allrows=[];receipts=[]
        for origin in protocol['origins']:
            season,week=origin['season'],origin['week'];oid=f'{season}-W{week:02}';ymodel,old,done,source=old_model(season,week);stamp=a.instant(done['origin_UTC']).timestamp();ti=[i for i,r in enumerate(pool) if r['season']>=2022 and r['available']<stamp and r['values']['pass_yd'] is not None]
            train=[pool[i] for i in ti];membership='\n'.join(r['game_id']+':'+r['player_id'] for r in train);assert hashlib.sha256(membership.encode()).hexdigest()==done['training_membership_sha256'] and len(ti)==done['training_rows']
            x=xx[ti];y=np.asarray([r['values']['pass_yd'] for r in train],float);n=np.asarray([r['attempts'] for r in train],float);roles=np.asarray(['QB']*len(x));validate_training_model(ymodel,x,y,roles);joint=joint_export(ymodel,x,y,n)
            folder=ART/'workload-models'/oid;folder.mkdir(parents=True,exist_ok=True);target=folder/'attempt_model.json.gz'
            if target.exists():attempt_model=read(target)
            else:
                assert ledger['fit_attempts']<4;ledger['fit_attempts']+=1;write(ledger_path,ledger)
                with threadpool_limits(limits=1):fitted=LeafModel('count',1).fit(x,n,roles)
                attempt_model=export_forest(fitted);write(target,attempt_model)
            write(folder/'joint_model.json.gz',joint);write(folder/'membership.json.gz',[dict(game_id=r['game_id'],player_id=r['player_id']) for r in train]);query_lookup={(r['game_id'],r['player_id']):i for i,r in enumerate(pool)}
            qx=[]
            for r in old:
                rebuilt=xx[query_lookup[(r['game_id'],r['player_id'])]];assert np.allclose(rebuilt,np.asarray(r['features'],float),rtol=0,atol=1e-10,equal_nan=True),'OLD_PREGAME_FEATURE_PREFIX_CHANGED';qx.append(rebuilt)
            qx=np.asarray(qx);oldlaws=infer_forest(ymodel,qx,['QB']*len(qx));nlaws=infer_forest(attempt_model,qx,['QB']*len(qx))
            for r,fv,oldlaw,nlaw in zip(old,qx,oldlaws,nlaws):
                assert abs(oldlaw.mean()-r['mean'])<1e-10 and oldlaw.quantile(.5)==r['median']
                control,cm=linked_law(joint,fv);candidate,mm=linked_law(joint,fv,forecast_bins(nlaw));actual_n=pool[query_lookup[(r['game_id'],r['player_id'])]]['attempts']
                packet=dict(origin_id=oid,season=season,week=week,game_id=r['game_id'],player_id=r['player_id'],name=r['name'],position=r['position'],team=r['team'],opponent=r['opponent'],kickoff_UTC=r['kickoff_UTC'],as_of_UTC=r['as_of_UTC'],fit_origin_UTC=done['origin_UTC'],actual=r['actual'],appearance=r['appearance'],actual_attempts=actual_n,actual_attempts_role='POSTGAME_DIAGNOSTIC_ONLY_NOT_PREDICTOR',features=[None if not np.isfinite(v) else float(v) for v in fv],attempt_law=law_data(nlaw),attempt_mean=nlaw.mean(),fallback=False,arms={})
                for arm,law,extra in [('RETAINED_P2',oldlaw,{}),('P2_LINKED_V8',control,cm),('P2_WORKLOAD_V8',candidate,mm)]:packet['arms'][arm]=dict(law=law_data(law),mean=law.mean(),median=law.quantile(.5),p05=law.quantile(.05),p95=law.quantile(.95),CRPS=law.crps(r['actual']) if r['actual'] is not None else None,NLL=-law.logpmf(int(r['actual'])) if r['actual'] is not None else None,**extra)
                allrows.append(packet)
            receipt=dict(origin_id=oid,source_archive=source,original_model_SHA256=done['model_sha256'],training_membership_SHA256=done['training_membership_sha256'],training_rows=len(ti),latest_training_available_UTC=max(r['available'] for r in train),fit_origin_UTC=done['origin_UTC'],query_rows=len(old),numeric_attempt_model_SHA256=a.sha(target),joint_model_SHA256=a.sha(folder/'joint_model.json.gz'),same_feature_prefix_and_Y_marginal_verified=True,new_attempt_fits=1,new_Y_fits=0)
            receipts.append(receipt);ledger['completed'].append(oid) if oid not in ledger['completed'] else None;write(ledger_path,ledger)
            assert time.monotonic()-start<600 and resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024<1610612736
        write(ART/'WORKLOAD_PREDICTIONS.json.gz',allrows);result=dict(id=protocol['id'],protocol_SHA256=a.sha(ROOT/'protocol/WORKLOAD_LINK_V8.json'),origins=receipts,new_attempt_fits=ledger['fit_attempts'],new_Y_fits=0,new_calibrators=0,query_rows=len(allrows),CPU_seconds=time.process_time()-cpu,wall_seconds=time.monotonic()-start,peak_RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024);write(OUT/'WORKLOAD_RUN.json',result);return result
    except Exception as e:ledger['failures'].append(dict(error=str(e),recorded_UTC=__import__('reliability_v8').now()));write(ledger_path,ledger);raise
    finally:signal.setitimer(signal.ITIMER_PROF,0)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--inputs',type=Path,required=True);x=p.parse_args();print(json.dumps(run(x.inputs),indent=2))
