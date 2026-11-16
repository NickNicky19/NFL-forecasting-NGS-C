"""One independent, frozen representative fit. Never invoked without root GO.

No author fit/design/probability/grader helper is imported. Primitive numeric
trees and probability vectors are retained even if strict comparison fails.
"""
import time
ENTRY_CPU=time.process_time()
ENTRY_WALL=time.monotonic()
import datetime,gzip,hashlib,json,math,resource,signal,warnings
from collections import Counter
from decimal import Decimal
from pathlib import Path

ROOT=Path(__file__).resolve().parents[5]
HERE=Path(__file__).resolve().parent
PILOT=ROOT/'reports/information-skill-01/execution-authorization-02/pilot'
PARENT=ROOT/'reports/targeted-accuracy-w1w9-01/M3'
KEY='INDEPENDENT-W2-C2_VALUE'
TOL=1e-12
PREP_CHARGE=1.0

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):
    p=Path(path);b=p.read_bytes()
    return json.loads(gzip.decompress(b) if p.suffix=='.gz' else b)
def stamp():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def immutable(path,obj):
    b=(json.dumps(obj,separators=(',',':'),allow_nan=False)+'\n').encode()
    if Path(path).suffix=='.gz':b=gzip.compress(b,mtime=0)
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    with Path(path).open('xb') as f:f.write(b)
def mutable(path,obj):
    p=Path(path);t=p.with_name(p.name+'.tmp')
    t.write_text(json.dumps(obj,separators=(',',':'),allow_nan=False)+'\n');t.replace(p)
def canonical(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def numeric_cdf(model,x,threshold):
    # The retained source design is numeric and has no categorical trees.
    row=list(x)+[float(threshold)];score=float(model['baseline'])
    for tree in model['trees']:
        node=0
        for depth in range(9):
            if tree['is_leaf'][node]:break
            v=row[tree['feature_idx'][node]]
            left=bool(tree['missing_go_to_left'][node]) if math.isnan(v) else v<=tree['num_threshold'][node]
            node=tree['left'][node] if left else tree['right'][node]
        else:raise AssertionError('INDEPENDENT_TREE_DEPTH_OR_CYCLE')
        score+=float(tree['value'][node])
    return 1/(1+math.exp(-score))
def own_grade(row,side):
    if side=='ABSTAIN':return 'ABSTAIN'
    if row['appearance']!='PLAYED':return 'UNKNOWN_PARTICIPATION'
    if row['actual'] is None:return 'MISSING_ACTUAL'
    y,line=Decimal(str(row['actual'])),Decimal(str(row['line']))
    if y==line:return 'PUSH'
    return 'WIN' if (y>line)==(side=='OVER') else 'LOSS'

def main():
    go=read(HERE/'GO.json')
    assert go['authorized'] is True and go['code_SHA256']==sha(__file__) and go['tolerance']==TOL
    assert not (HERE/'RESULT.json').exists(),'NO_RETRY_OF_FROZEN_VERIFICATION'
    ledger_path=PILOT/'LEDGER.json';state=read(ledger_path)
    assert not state['active'] and len(state['attempts'])==4 and len(state['completed'])==4
    assert (PILOT/'RAW_GRADES_COMPLETE.json').is_file()
    assert state['CPU_seconds']+10+30<=120 and state['wall_seconds']+20<=300
    initial_CPU=state['CPU_seconds'];initial_wall=state['wall_seconds']
    state.update(active=True,stage='independent-representative-fit')
    mutable(ledger_path,state)
    signal.signal(signal.SIGPROF,lambda *_:(_ for _ in ()).throw(RuntimeError('INDEPENDENT_CPU_CAP')))
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(RuntimeError('INDEPENDENT_WALL_CAP')))
    # 8.5 processCPU plus1 conservative prep leaves0.5 for final retention.
    signal.setitimer(signal.ITIMER_PROF,max(.01,8.5-time.process_time()))
    signal.setitimer(signal.ITIMER_REAL,max(.01,19-(time.monotonic()-ENTRY_WALL)))
    status='FAILED';reason=None;attempted=False;checks=[];metrics={};bindings={};errors={}
    try:
        import numpy as np
        from sklearn.ensemble import HistGradientBoostingClassifier
        from threadpoolctl import threadpool_limits
        model_path=PILOT/'models/W2-C2_VALUE.json.gz';saved=read(model_path)
        data_path=PARENT/'inputs/FEATURES_AND_MEMBER_FACTS.json.gz';matrix_path=PILOT/'FEATURE_MATRIX.json.gz'
        assert sha(data_path)==saved['input_SHA256'] and sha(matrix_path)==saved['feature_matrix_SHA256']
        data=read(data_path);block=read(matrix_path);rows=data['rows']
        base=np.asarray(data['X_by_target']['rec'],dtype=float)
        extra=np.asarray(block['matrix'],dtype=float)
        xx=np.column_stack([base,extra]);assert xx.shape[1]==39
        origin=saved['origin'];ti=[i for i,r in enumerate(rows) if not r['query_only'] and r['available'] is not None and r['available']<origin and r['values']['rec'] is not None]
        y=np.asarray([rows[i]['values']['rec'] for i in ti],dtype=float)
        members=[[rows[i]['game_id'],rows[i]['player_id']] for i in ti]
        assert len(ti)==saved['training_rows'] and canonical(members)==saved['training_membership_SHA256']
        assert hashlib.sha256(np.nan_to_num(xx[ti],nan=999999.).tobytes()+y.tobytes()).hexdigest()==saved['design_X_y_SHA256']
        assert saved['feature_names']==data['feature_names']['rec']+block['feature_names']
        assert np.isfinite(y).all() and (y>=0).all() and np.equal(y,np.floor(y)).all()
        raw=read(PILOT/'raw/W2-C2_VALUE.json.gz');assert raw and all(r['week']==2 for r in raw)
        index={(r['game_id'],r['player_id']):i for i,r in enumerate(rows)}
        assert not(set(r['game_id'] for r in raw)&set(rows[i]['game_id'] for i in ti))
        # Separate implementation of the original median/missing transform.
        with warnings.catch_warnings():
            warnings.simplefilter('ignore',RuntimeWarning);median=np.nanmedian(xx[ti],axis=0)
        median=np.where(np.isfinite(median),median,0.)
        assert np.array_equal(np.asarray(saved['model']['imputation'],float),median),'SAVED_IMPUTATION_VECTOR_MISMATCH'
        assert saved['model']['thresholds']==[0,1,2,3,4,5,7]
        train_raw=xx[ti];z=np.concatenate([np.where(np.isfinite(train_raw),train_raw,median),~np.isfinite(train_raw)],axis=1).astype(float)
        grid=np.asarray([0,1,2,3,4,5,7])
        train=np.column_stack([np.repeat(z,len(grid),axis=0),np.tile(grid,len(z))])
        labels=(np.repeat(y,len(grid))<=np.tile(grid,len(y))).astype(int)
        monotone=[0]*train.shape[1];monotone[-1]=1
        assert len(state['attempts'])==4 and KEY not in state['attempts']
        state['attempts'].append(KEY);attempted=True
        state['CPU_seconds']=initial_CPU+PREP_CHARGE+time.process_time()
        state['wall_seconds']=initial_wall+time.monotonic()-ENTRY_WALL
        mutable(ledger_path,state)
        with threadpool_limits(limits=1):
            fitted=HistGradientBoostingClassifier(max_iter=32,max_depth=3,min_samples_leaf=20,
                learning_rate=.05,l2_regularization=10,random_state=1701,early_stopping=False,
                monotonic_cst=monotone).fit(train,labels)
        # Full independent coefficient/tree vector is retained before parity assertions.
        trees=[]
        for stage in fitted._predictors:
            assert len(stage)==1;nodes=stage[0].nodes;assert not np.any(nodes['is_categorical'])
            trees.append({k:nodes[k].tolist() for k in ['value','feature_idx','num_threshold','missing_go_to_left','left','right','is_leaf']})
        independent=dict(schema='C-INDEPENDENT-NUMERIC-HGB-CDF',imputation=median.tolist(),
                         baseline=float(fitted._baseline_prediction[0,0]),trees=trees,thresholds=grid.tolist())
        immutable(HERE/'INDEPENDENT_NUMERIC_MODEL.json.gz',dict(model=independent,
            parent_model_binding=dict(path=str(model_path.relative_to(ROOT)),SHA256=sha(model_path)),
            membership_SHA256=canonical(members),tolerance=TOL,training_rows=len(ti)))
        qindices=[index[(r['game_id'],r['player_id'])] for r in raw]
        qraw=xx[qindices];qdesign=np.column_stack([np.where(np.isfinite(qraw),qraw,median),~np.isfinite(qraw)]).astype(float)
        low=[];high=[]
        for r in raw:
            k=math.floor(r['line']);low.append(k-1 if float(r['line']).is_integer() else k);high.append(k)
        thresholds=np.asarray(list(zip(low,high)),dtype=float)
        query=np.column_stack([np.repeat(qdesign,2,axis=0),thresholds.reshape(-1)])
        with threadpool_limits(limits=1):
            fresh=fitted.predict_proba(query)[:,1].reshape(len(raw),2)
            single=fitted.predict_proba(query[:2])[:,1]
        assert np.max(np.abs(single-fresh[0]))<=TOL
        vectors=[];max_numeric=0.;max_raw=0.;counts=Counter();side_changes=0;grade_changes=0
        for j,r in enumerate(raw):
            f=[0. if k<0 else float(v) for k,v in zip([low[j],high[j]],fresh[j])]
            restored=[0. if k<0 else numeric_cdf(saved['model'],qdesign[j],k) for k in [low[j],high[j]]]
            max_numeric=max(max_numeric,max(abs(a-b) for a,b in zip(f,restored)))
            p=dict(under=f[0],push=max(0.,f[1]-f[0]),over=1-f[1])
            assert all(math.isfinite(v) and v>=0 for v in p.values()) and abs(sum(p.values())-1)<=TOL
            max_raw=max(max_raw,max(abs(p[k]-r['probabilities'][k]) for k in p))
            side='OVER' if p['over']>p['under']+TOL else 'UNDER' if p['under']>p['over']+TOL else 'ABSTAIN'
            grade=own_grade(r,side);counts[grade]+=1
            side_changes+=side!=r['selected_side'];grade_changes+=grade!=r['status']
            vectors.append(dict(offer_id=r['offer_id'],game_id=r['game_id'],player_id=r['player_id'],
                thresholds=[low[j],high[j]],fresh_CDF=f,saved_numeric_CDF=restored,
                fresh_probabilities=p,saved_probabilities=r['probabilities'],side=side,status=grade,
                saved_side=r['selected_side'],saved_status=r['status']))
        immutable(HERE/'INDEPENDENT_PROBABILITY_VECTOR.json.gz',dict(rows=vectors,tolerance=TOL))
        metrics=dict(training_rows=len(ti),offer_rows=len(raw),max_fresh_vs_saved_numeric_CDF=max_numeric,
            max_fresh_vs_raw_probability=max_raw,changed_sides=side_changes,changed_grades=grade_changes,
            independent_status_counts=dict(counts),batch_single_tolerance=TOL,
            complete_numeric_vector_equal=all(independent[k]==saved['model'][k] for k in ['imputation','baseline','trees','thresholds']))
        for side in ['OVER','UNDER','COMBINED']:
            rr=[r for r in vectors if r['side'] in ['OVER','UNDER'] and (side=='COMBINED' or r['side']==side)]
            wins=sum(r['status']=='WIN' for r in rr);losses=sum(r['status']=='LOSS' for r in rr)
            metrics[side]=dict(selected=len(rr),wins=wins,losses=losses,decided=wins+losses,
                               rate=wins/(wins+losses) if wins+losses else None)
        errors=dict(max_numeric=max_numeric,max_raw_probability=max_raw,changed_sides=side_changes,changed_grades=grade_changes)
        assert max_numeric<=TOL and max_raw<=TOL,'STRICT_FIT_REPRODUCTION_FAILED'
        assert side_changes==0 and grade_changes==0,'INDEPENDENT_SIDE_OR_GRADE_MISMATCH'
        assert resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024<=1288490188
        checks=['membership/design fingerprint','manual median/missing transform','fresh fixed HGB fit',
                'independent primitive-tree traversal','batch/single','event orientation/mass/push',
                'manual exact-line grades','full independent vectors retained']
        state['completed'].append(KEY);status='PASS_STRICT_REPRESENTATIVE_FIT_AND_GRADING'
        bindings=dict(input_SHA256=sha(data_path),new_feature_SHA256=sha(matrix_path),
            saved_model_SHA256=sha(model_path),independent_model_SHA256=sha(HERE/'INDEPENDENT_NUMERIC_MODEL.json.gz'),
            independent_probability_SHA256=sha(HERE/'INDEPENDENT_PROBABILITY_VECTOR.json.gz'))
    except Exception as error:
        reason=type(error).__name__+': '+str(error)
        state['failures'].append(dict(stage='independent-representative-fit',error=reason))
    finally:
        signal.setitimer(signal.ITIMER_PROF,0);signal.setitimer(signal.ITIMER_REAL,0)
        charge=PREP_CHARGE+time.process_time()
        wall=time.monotonic()-ENTRY_WALL
        state.update(active=False,CPU_seconds=initial_CPU+charge,wall_seconds=initial_wall+wall,
                     peak_RSS_bytes=max(state.get('peak_RSS_bytes',0),resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024))
        mutable(ledger_path,state)
        result=dict(id='C-DYAD-INDEPENDENT-W2-C2-v1',recorded_UTC=stamp(),status=status,reason=reason,
            attempted_fit=attempted,tolerance=TOL,metrics=metrics,checks=checks,bindings=bindings,
            measured_full_process_CPU=time.process_time(),conservative_preparation_CPU=PREP_CHARGE,
            total_subtask_charged_CPU=charge,measured_process_wall=wall,
            parent_cumulative_CPU=state['CPU_seconds'],parent_cumulative_wall=state['wall_seconds'],
            frozen_scientific_config=True,no_retry=True,new_source_GETs=0,
            scope='One W2 C2 representative fit only; no W3 or C1 fit reproduction. Parent original32/newfeature bytes trusted after hash checks, not independently reconstructed historical vintages.',
            prior_B_C1_and_opportunity_team_strict_reproduction='FAILED_UNCHANGED;THIS_IS_A_DIFFERENT_FIT',
            accounting_limit='Full current interpreter CPU plus one conservative prep second. Tool/assistant orchestration is not a complete elapsed-work certificate.')
        immutable(HERE/'RESULT.json',result)
        print(json.dumps(result))
    return 0 if status.startswith('PASS') else 2

if __name__=='__main__':raise SystemExit(main())
