"""Registered 2025 rolling forecasts and 2025-trained threshold calibration.

Imports the frozen C law/feature implementations. Never edits or refits v2 rows.
"""
import argparse,gzip,hashlib,json,math,os,pickle,resource,signal,time
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit,logit
from threadpoolctl import threadpool_limits
from contracts_v2 import CATEGORIES,CHART
from data_v2 import load,History,vector,admitted_roles
from laws_v2 import LeafModel,Prior,Law
from wave_v2 import GRIDS,clean,sha

VERSION='C-2025-OOF-RAW-P2-v3'
CAL_VERSION='C-2025-TRAINED-SIGMOID-v3'

def write(path,value,immutable=False):
    path.parent.mkdir(parents=True,exist_ok=True)
    data=json.dumps(clean(value),allow_nan=False,separators=(',',':'))
    if immutable:
        with path.open('x') as f:f.write(data)
    else:
        temp=path.with_suffix(path.suffix+'.tmp');temp.write_text(data);temp.replace(path)

def tree_bytes(root):
    return sum(os.stat(Path(d)/n,follow_symlinks=False).st_size for d,_,names in os.walk(root) for n in names)

class Budget:
    """Cumulative active-worker budget, persisted across pilot and broad stages."""
    def __init__(self,path,out,roots):
        self.path,self.out,self.roots=path,out,roots
        self.state=json.loads(path.read_text()) if path.exists() else dict(cpu_seconds=0.,wall_seconds=0.,base_fit_attempts=0,calibrator_attempts=0,peak_RSS_bytes=0,peak_cache_bytes=0,stage_receipts=[])
        self.cpu=time.process_time();self.wall=time.monotonic();self.check()
    def check(self):
        cpu=self.state['cpu_seconds']+time.process_time()-self.cpu
        wall=self.state['wall_seconds']+time.monotonic()-self.wall
        rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
        cache=sum(tree_bytes(r) for r in self.roots)
        self.state['peak_RSS_bytes']=max(rss,self.state['peak_RSS_bytes'])
        self.state['peak_cache_bytes']=max(cache,self.state['peak_cache_bytes'])
        if cpu>600 or wall>900:raise RuntimeError('CUMULATIVE_TIME_CAP')
        if rss>1073741824:raise RuntimeError('RSS_CAP')
        if cache>2147483648:raise RuntimeError('WHOLE_C_CACHE_CAP')
        if tree_bytes(self.out)>67108864:raise RuntimeError('NEW_SCIENCE_CAP')
        self.persist()
    def persist(self):write(self.path,self.state)
    def attempt(self,kind):
        key='base_fit_attempts' if kind=='base' else 'calibrator_attempts';cap=216 if kind=='base' else 12
        if self.state[key]>=cap:raise RuntimeError('FIT_ATTEMPT_CAP')
        self.state[key]+=1;self.persist()
    def __enter__(self):
        self.old=signal.signal(signal.SIGPROF,lambda *_:(_ for _ in ()).throw(RuntimeError('CUMULATIVE_CPU_TIMER')))
        signal.setitimer(signal.ITIMER_PROF,max(.01,600-self.state['cpu_seconds']));return self
    def __exit__(self,typ,value,tb):
        signal.setitimer(signal.ITIMER_PROF,0);signal.signal(signal.SIGPROF,self.old)
        c=time.process_time()-self.cpu;w=time.monotonic()-self.wall
        self.state['cpu_seconds']+=c;self.state['wall_seconds']+=w
        self.state['peak_RSS_bytes']=max(self.state['peak_RSS_bytes'],resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024)
        self.state['stage_receipts'].append(dict(finished_UTC=pd.Timestamp.now(tz='UTC').isoformat(),cpu_seconds=c,wall_seconds=w,state='PASS' if typ is None else str(value)))
        self.persist()

def training_indices(pool,target,origin):
    return [i for i,r in enumerate(pool) if 2022<=r['season']<=2025 and r['available']<origin and r['values'][target] is not None]

def raw_wave(inputs,out,budget,pilot=False):
    d,g,teams=load(inputs);d=d[d.season<=2025];teams=teams[teams.season<=2025]
    assert len(g[(g.season==2025)&g.week.between(1,18)])==272
    sources={p.name:sha(p) for p in inputs.iterdir() if p.is_file()}
    code={n:sha(Path(__file__).with_name(n)) for n in ['robustness_v3.py','laws_v2.py','data_v2.py','contracts_v2.py','wave_v2.py']}
    hist,th=History(d,'player_id'),History(teams,'team');records=d.to_dict('records')
    for target in (['pass_cmp'] if pilot else CATEGORIES):
        weeks=[1] if pilot else list(range(1,19))
        if all((out/'raw'/target/f'W{w:02}'/'DONE.json').exists() for w in weeks):continue
        pool=[r for r in records if r['position'] in admitted_roles(target)]
        x=np.asarray([vector(r,target,hist,th,'E0_OP') for r in pool],float)
        kind,scale=CATEGORIES[target][2:4];grid=np.asarray(GRIDS[target]);budget.check()
        for week in weeks:
            dest=out/'raw'/target/f'W{week:02}'
            if (dest/'DONE.json').exists():continue
            origin=float(g.loc[(g.season==2025)&(g.week==week),'kickoff'].min())
            ti=training_indices(pool,target,origin);qi=[i for i,r in enumerate(pool) if r['season']==2025 and r['week']==week]
            train=[pool[i] for i in ti];query=[pool[i] for i in qi];tx,qx=x[ti],x[qi]
            y=np.rint([r['values'][target]*scale for r in train]);roles=np.asarray([r['position'] for r in train]);qr=np.asarray([r['position'] for r in query])
            learned=len(ti)>=60 and (kind!='event' or len(np.unique(y))==2)
            meta=dict(version=VERSION,target=target,season=2025,week=week,family='P2_LEAF',arm='E0_OP',history='H-MULTI',origin_UTC=pd.Timestamp(origin,unit='s',tz='UTC').isoformat(),training_rows=len(ti),latest_training_available=max([r['available'] for r in train],default=None),training_membership_sha256=hashlib.sha256('\n'.join(r['game_id']+':'+r['player_id'] for r in train).encode()).hexdigest(),learned=learned,source_sha256=sources,code_sha256=code)
            if (dest/'ATTEMPT.json').exists():
                old=json.loads((dest/'ATTEMPT.json').read_text());assert old['training_membership_sha256']==meta['training_membership_sha256']
                if not (dest/'model.pkl.gz').exists():raise RuntimeError('UNRETAINED_ATTEMPT_NEEDS_EXPLICIT_FAILURE_REVIEW')
            else:write(dest/'ATTEMPT.json',meta,True)
            if (dest/'model.pkl.gz').exists():
                model=pickle.loads(gzip.decompress((dest/'model.pkl.gz').read_bytes()))['model']
            else:
                budget.check();budget.attempt('base') if learned else None
                with threadpool_limits(limits=1):model=LeafModel(kind,scale).fit(tx,y,roles) if learned else None
                prior={r:Prior(y[roles==r],kind) for r in set(roles)};global_prior=Prior(y,kind)
                with gzip.open(dest/'model.pkl.gz','wb',compresslevel=5) as f:pickle.dump(dict(model=model,prior=prior,global_prior=global_prior,kind=kind,scale=scale,attempt=meta),f,protocol=5)
            packet=pickle.loads(gzip.decompress((dest/'model.pkl.gz').read_bytes()));prior=packet['prior'];glob=packet['global_prior']
            with threadpool_limits(limits=1):laws=model.laws(qx,qr) if model else [Law([],[],prior.get(r,glob),scale) for r in qr]
            prevalence={r:((y[roles==r,None]/scale>grid).sum(axis=0)+1)/(sum(roles==r)+2) for r in set(qr)}
            rows=[]
            for r,fv,law in zip(query,qx,laws):
                actual=r['values'][target];ref=prior.get(r['position'],glob)
                po=[law.probability(line)['over'] for line in grid]
                p=dict(version=VERSION,target=target,season=2025,week=week,family='P2_LEAF',history='H-MULTI',arm='E0_OP',game_id=r['game_id'],player_id=r['player_id'],name=r['player_display_name'],position=r['position'],team=r['team'],opponent=r['opponent_team'],kickoff_UTC=pd.Timestamp(r['kickoff'],unit='s',tz='UTC').isoformat(),as_of_UTC=pd.Timestamp(r['kickoff'],unit='s',tz='UTC').isoformat(),fit_origin_UTC=meta['origin_UTC'],generated_UTC=pd.Timestamp.now(tz='UTC').isoformat(),information_tier='CURRENT_REVISED_7DAY_RECONSTRUCTION',scoring_contract_id=CHART if target=='fpts' else 'rush-or-rec-at-least-one-v1' if kind=='event' else 'official-player-fullgame-OT-v1',actual=actual,appearance='PLAYED' if r['played'] else 'UNKNOWN',chart_state=r['chart_state'] if target=='fpts' else None,features=fv.tolist(),fallback=not learned,grid=grid.tolist(),p_over=po,p_push=[0.]*len(grid),mean=law.mean(),median=law.quantile(.5),p05=law.quantile(.05),p95=law.quantile(.95),product_type='EVENT_PROBABILITY' if kind=='event' else 'DISCRETE_OUTCOME_LAW',prevalence_over=prevalence[r['position']].tolist(),reference_over=[ref.event] if kind=='event' else [1-ref.cdf(math.floor(line*scale)) for line in grid])
                if actual is not None:
                    truth=(actual>grid).astype(float);p.update(grid_brier=float(np.mean((np.asarray(po)-truth)**2)),crps=law.crps(actual),nll=-law.logpmf(int(round(actual*scale))))
                rows.append(clean(p))
            with gzip.open(dest/'rows.json.gz','wt',compresslevel=5) as f:json.dump(rows,f,separators=(',',':'),allow_nan=False)
            write(dest/'DONE.json',meta|dict(rows=len(rows),model_sha256=sha(dest/'model.pkl.gz'),row_sha256=sha(dest/'rows.json.gz'),finished_UTC=pd.Timestamp.now(tz='UTC').isoformat()),True)
            print('DONE',target,week,len(rows),len(ti),flush=True);budget.check()

def fit_calibrator(rows):
    assert rows and all(r['season']==2025 for r in rows),'CALIBRATION_REQUIRES_2025_OOF_ONLY'
    known=[r for r in rows if r['actual'] is not None]
    p=np.concatenate([r['p_over'] for r in known]);truth=np.concatenate([(r['actual']>np.asarray(r['grid'])).astype(float) for r in known])
    weights=np.concatenate([np.full(len(r['grid']),1/len(r['grid'])) for r in known]);weights/=len(known)
    if len(known)<200 or min(float(weights@truth),float(weights@(1-truth)))*len(known)<20:
        return dict(a=0.,b=1.,identity_fallback=True,training_queries=len(known),converged=True)
    z=logit(np.clip(p,1e-6,1-1e-6))
    def fun(beta):
        a,b=beta;t=a+b*z;loss=weights@(np.logaddexp(0,t)-truth*t)+.0005*(a*a+(b-1)**2)
        residual=weights*(expit(t)-truth)
        return float(loss),np.asarray([residual.sum()+.001*a,residual@z+.001*(b-1)])
    result=minimize(fun,[0.,1.],jac=True,bounds=[(None,None),(0,None)],method='L-BFGS-B',options={'maxiter':200,'ftol':1e-10})
    if not result.success:raise RuntimeError('CALIBRATOR_CONVERGENCE_FAILURE')
    return dict(a=float(result.x[0]),b=float(result.x[1]),identity_fallback=False,training_queries=len(known),converged=True,objective=float(result.fun))

def calibrated(cal,p):
    p=np.asarray(p,float)
    return p.copy() if cal['identity_fallback'] else expit(cal['a']+cal['b']*logit(np.clip(p,1e-6,1-1e-6)))

def calibrate(out,old,budget):
    for target in CATEGORIES:
        dest=out/'calibration'/target
        if (dest/'DONE.json').exists():continue
        files=sorted((out/'raw'/target).glob('W*/rows.json.gz'));assert len(files)==18
        rows=[r for f in files for r in json.loads(gzip.decompress(f.read_bytes()))]
        hashes={f.parent.name:sha(f) for f in files}
        if (dest/'calibrator.json').exists():cal=json.loads((dest/'calibrator.json').read_text())
        else:
            budget.check();budget.attempt('cal')
            with threadpool_limits(limits=1):cal=fit_calibrator(rows)
            cal.update(version=CAL_VERSION,target=target,training_season=2025,OOF_row_hashes=hashes,fit_UTC=pd.Timestamp.now(tz='UTC').isoformat(),formula='sigmoid(a+b*logit(clip(p,1e-6,1-1e-6))),b>=0',penalty='.001/2*(a^2+(b-1)^2)',product='REGISTERED_THRESHOLD_EVENT_PROBABILITIES_ONLY_NOT_COMPLETE_LAW')
            write(dest/'calibrator.json',cal,True)
        packet=[]
        paths=sorted(old.glob(f'*-{target}-H-MULTI-P2_LEAF-E0_OP-W*/rows.json.gz'));assert len(paths)==7
        earliest=min(pd.Timestamp(r['as_of_UTC']).timestamp() for path in paths for r in json.loads(gzip.decompress(path.read_bytes())))
        assert max(pd.Timestamp(r['kickoff_UTC']).timestamp()+7*86400 for r in rows)<earliest
        # No 2026 actual is read by fit_calibrator; the fixed transform is already frozen.
        for path in paths:
            for r in json.loads(gzip.decompress(path.read_bytes())):
                q=calibrated(cal,r['p_over']);assert np.all(np.diff(q)<=1e-12) and np.all((q>=0)&(q<=1))
                packet.append({k:r[k] for k in ['target','week','game_id','player_id','name','position','team','opponent','actual','appearance','fallback','grid','scoring_contract_id','information_tier','as_of_UTC','kickoff_UTC']}|dict(version=CAL_VERSION,source_forecast_version=r['version'],source_forecast_row_sha256=sha(path),source_forecast_generated_UTC=r['generated_UTC'],generated_UTC=pd.Timestamp.now(tz='UTC').isoformat(),training_season=2025,product_type='CALIBRATED_EVENT_PROBABILITY' if target=='anytime_td' else 'CALIBRATED_THRESHOLD_PROBABILITIES',p_raw=r['p_over'],p_over=q.tolist(),p_under=(1-q).tolist(),p_push=[0.]*len(q),mean=None,median=None))
        with gzip.open(dest/'rows-2026.json.gz','wt',compresslevel=5) as f:json.dump(packet,f,separators=(',',':'),allow_nan=False)
        write(dest/'DONE.json',dict(target=target,rows=len(packet),calibrator_sha256=sha(dest/'calibrator.json'),row_sha256=sha(dest/'rows-2026.json.gz'),training_queries=cal['training_queries']),True)
        print('CALIBRATED',target,len(packet),flush=True);budget.check()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--inputs',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--old-wave',type=Path,required=True);p.add_argument('--budget-ledger',type=Path,required=True);p.add_argument('--cache-root',type=Path,action='append',required=True);p.add_argument('--stage',choices=['pilot','raw','calibration'],required=True);a=p.parse_args()
    with Budget(a.budget_ledger,a.out,a.cache_root) as b:
        if a.stage=='calibration':calibrate(a.out,a.old_wave,b)
        else:raw_wave(a.inputs,a.out,b,a.stage=='pilot')
