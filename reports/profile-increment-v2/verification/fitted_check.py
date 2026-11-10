"""Independent saved-JSON forest, grade and aggregate checks; no fits or GETs."""
import collections, gzip, hashlib, json, lzma, math, resource, signal, sys, time
from pathlib import Path
START = time.process_time()
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'src'))
import numpy as np
from context_identity_view_c01 import corrected_rows
signal.signal(signal.SIGPROF, lambda *_: (_ for _ in ()).throw(RuntimeError('100CPUcap')))
signal.setitimer(signal.ITIMER_PROF, 100)
OUT = ROOT/'reports/profile-increment-v2/verification'
EXP = ROOT/'reports/profile-increment-v2/experiment'
ART = ROOT/'artifacts/profile-increment-v2'

def read(p):
    p = Path(p); b = p.read_bytes()
    return json.loads(lzma.decompress(b) if p.suffix == '.xz' else gzip.decompress(b) if p.suffix == '.gz' else b)
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def eq(a, b, where=''):
    if isinstance(a, (int,float)) and isinstance(b, (int,float)):
        assert abs(a-b) < 1e-10, (where,a,b)
    else: assert a == b, (where,a,b)

def forest(model, x, role):
    """Separate traversal/arithmetic, without producer inference/Law/Prior code."""
    assert model['schema'] == 'C-NUMERIC-LEAF-v4' and model['kind'] == 'count' and model['scale'] == 1
    missing = np.asarray([v is None or not math.isfinite(v) for v in x])
    values = np.asarray([model['imputation'][i] if missing[i] else v for i,v in enumerate(x)])
    z = np.r_[values,missing.astype(float)].astype(np.float32)
    mass = collections.defaultdict(float)
    assert len(model['trees']) == 32
    for t in model['trees']:
        node = 0
        for depth in range(10):
            if t['left'][node] < 0: break
            node = t['left'][node] if float(z[t['feature'][node]]) <= t['threshold'][node] else t['right'][node]
        else: raise AssertionError('cycle/depth')
        outcomes, counts = t['leaves'][str(node)]; den = sum(counts)*32
        for y,n in zip(outcomes,counts): mass[y] += n/den
    norm = sum(mass.values()); mass = {k:v/norm for k,v in mass.items()}
    prior = model['prior'].get(role,model['global_prior'])
    assert prior['kind'] == 'count' and not prior['empty']
    q = prior['q']; assert 0 < q < 1
    def cdf(k): return .95*sum(w for y,w in mass.items() if y <= k)+.05*(0. if k < 0 else 1-q**(math.floor(k)+1))
    def pmf(k): return .95*mass.get(k,0.)+.05*((1-q)*q**k if k >= 0 else 0.)
    def quantile(p):
        for k in range(10000):
            if cdf(k) >= p: return k
        raise AssertionError('tail quantile')
    def probability(line):
        under=cdf(math.ceil(line)-1)
        push=pmf(int(line)) if line == int(line) else 0.
        over=1-cdf(math.floor(line))
        return dict(under=under,push=push,over=over)
    mean=.95*sum(y*w for y,w in mass.items())+.05*q/(1-q)
    assert abs(sum(pmf(k) for k in range(501))+.05*q**501-1)<1e-12
    return dict(mean=mean,median=quantile(.5),p05=quantile(.05),p95=quantile(.95),cdf=cdf,pmf=pmf,probability=probability,mass=mass)

canaries = read(ART/'CANARY_QUERIES-2026.json.xz')
numeric = read(ART/'NUMERICAL_ROWS-2026.json.xz')
offered = read(ART/'ACTUAL_OFFER_ROWS.json.xz')
oldnum = read(ROOT/'artifacts/player-context-matchup-01/completion-decision-v1/lookback/EVALUATION_PREDICTIONS.json.gz')
assert {(r['game_id'],r['player_id'],r['actual']) for r in numeric} == {(r['game_id'],r['player_id'],r['actual']) for r in oldnum}
assert len({(r['game_id'],r['player_id']) for r in numeric}) == len(numeric)
savedmodels={}; laws={}; maxmean=0.; boundary_checks=0; regs=collections.Counter(); origin_members={}
numerical_map={(r['game_id'],r['player_id']):r for r in numeric}
frozen_cohorts=read(ROOT/'reports/profile-increment-v2/COHORT_MEMBERSHIP.json.xz')['rows']
frozen_cohorts={(r['game_id'],r['player_id']):r for r in frozen_cohorts}
def check_cohort(r):
    f=frozen_cohorts[(r['game_id'],r['player_id'])];c=r['cohort']
    assert c==dict(priority=f['profiling_priority'],workload_top20=f['top20_expected_targets'],reason=f['priority_reason'],reference_expected_targets=f['reference_expected_targets'],reference_cutoff=f['reference_cutoff'])
for r in numeric:check_cohort(r)
pilotsha=sha(EXP/'PILOT_REGISTRATION.json'); wavesha=sha(EXP/'INITIAL_2026_REGISTRATION.json')
for c in canaries:
    path=ROOT/c['model']; assert sha(path)==c['model_SHA256']
    payload=read(path); model=payload['model']; savedmodels[c['model']]=model
    if c['arm']!='R0':
        expected=pilotsha if (c['origin'],c['arm'])==('2026-W01','R1') else wavesha
        assert payload['registration_SHA256']==expected
        assert payload['code_SHA256']==sha(ROOT/'src/receiving_increment_c03.py')
        assert payload['defense_code_SHA256']==sha(ROOT/'src/receiving_defense_c03.py')
        regs[expected]+=1
        origin_members.setdefault(c['origin'],set()).add((payload['membership_SHA256'],payload['training_rows']))
    law=forest(model,c['feature_vector'],c['position']); laws[(c['origin'],c['arm'])]=(c,law)
    maxmean=max(maxmean,abs(law['mean']-c['expected_mean'])); eq(law['mean'],c['expected_mean']); eq(law['median'],c['expected_median'])
    r=numerical_map[(c['game_id'],c['player_id'])][c['arm']]
    for key in ['mean','median','p05','p95']:
        if key in r:eq(law[key],r[key])
    assert law['cdf'](law['median']-1)<.5<=law['cdf'](law['median'])
    previous=0.
    for line in np.arange(-.5,25,.5):
        p=law['probability'](float(line)); assert all(-1e-12<=v<=1+1e-12 for v in p.values()) and abs(sum(p.values())-1)<1e-12
        assert p['under']+1e-12>=previous; previous=p['under'];boundary_checks+=1
        if line != int(line): assert p['push']==0
        else:eq(p['push'],law['pmf'](int(line)))
assert len(canaries)==25 and all(len(v)==1 for v in origin_members.values()) and sum(regs.values())==24

# Single, batched and shuffled producer inference must agree with independent trees.
from safe_models_v4 import infer_forest
batch_checks=0
for arm in ['R1','R2','R3']:
    cc=[c for c in canaries if c['arm']==arm]; model=savedmodels[cc[0]['model']]
    expected=[forest(model,c['feature_vector'],c['position']) for c in cc]
    xx=np.array([[np.nan if v is None else v for v in c['feature_vector']] for c in cc]); roles=[c['position'] for c in cc]
    batch=infer_forest(model,xx,roles); order=list(reversed(range(len(cc)))); shuffled=infer_forest(model,xx[order],[roles[i] for i in order])
    for i,(e,law) in enumerate(zip(expected,batch)):
        single=infer_forest(model,xx[i:i+1],roles[i:i+1])[0]
        for z in [law,single,shuffled[order.index(i)]]: eq(z.mean(),e['mean']);eq(z.quantile(.5),e['median'])
        batch_checks+=1

def grade(r):
    side=r['selected_side']
    if side is None:return 'UNAVAILABLE_FORECAST'
    if side=='ABSTAIN':return 'ABSTAIN'
    if r['appearance']!='PLAYED':return 'UNKNOWN_PARTICIPATION'
    if r['actual'] is None:return 'MISSING_ACTUAL'
    if r['actual']==r['line']:return 'PUSH'
    return 'WIN' if (r['actual']>r['line'])==(side=='OVER') else 'LOSS'

source=corrected_rows(); templates={r['offer_id']:r for r in source if r['method']=='E0'}
assert len(templates)==362 and len(offered)==4344
methods=collections.defaultdict(list); representative=[]; canary_offers=0
for r in offered:
    check_cohort(r)
    original=templates[r['offer_id']]
    for k in ['game_id','player_id','category','position','team','opponent_team','line','actual','appearance','week','season','scoring_contract_id']:
        eq(r[k],original[k],k)
    assert grade(r)==r['status'];methods[r['method']].append(r)
    if r['method'].endswith(('_MEAN','_MEDIAN')):
        assert r['probabilities'] is None and not any(k in r for k in ['Brier','log_loss','infinite_log_loss'])
        point=r.get('point')
        assert r['point_type']==('mean'if r['method'].endswith('_MEAN')else'median')
        if point is None:assert r['selected_side'] is None
        else:assert r['selected_side']==('OVER' if point>r['line'] else 'UNDER' if point<r['line'] else 'ABSTAIN')
    if r['method'].startswith(('R1_','R2_','R3_')):
        if r['method'].endswith('_LAW'):
            p=r['probabilities'];assert abs(sum(p.values())-1)<1e-12 and p['push']==0
            side='OVER' if p['over']>p['under'] else 'UNDER' if p['under']>p['over'] else 'ABSTAIN';assert r['selected_side']==side
            if r['status'] in ['WIN','LOSS','PUSH']:
                truth={k:int((r['actual']<r['line']) if k=='under' else (r['actual']==r['line']) if k=='push' else r['actual']>r['line'])for k in p}
                eq(r['Brier'],.5*sum((p[k]-truth[k])**2 for k in p));pr=sum(p[k]*truth[k]for k in p)
                assert pr>0 and not r['infinite_log_loss'];eq(r['log_loss'],-math.log(pr))
        else:
            assert r['probabilities'] is None and not any(k in r for k in ['Brier','log_loss','infinite_log_loss'])
            point=r['mean'] if r['method'].endswith('_MEAN') else r['median'];eq(r['point'],point)
            assert r['selected_side']==('OVER' if point>r['line'] else 'UNDER' if point<r['line'] else 'ABSTAIN')
    if r['method'].endswith('_LAW') and r['method']!='R0_LAW':
        key=(f'2026-W{r["week"]:02}',r['method'].split('_')[0]);c,law=laws[key]
        if (r['game_id'],r['player_id'])==(c['game_id'],c['player_id']):
            for k,p in law['probability'](r['line']).items():eq(p,r['probabilities'][k])
            canary_offers+=1
    if r['status'] in ['WIN','LOSS'] and len(representative)<2 and (not representative or r['status']!=representative[0]['status']):
        representative.append({k:r[k] for k in ['method','game_id','player_id','line','actual','selected_side','status']})
assert all(len(rr)==362 and len({r['offer_id']for r in rr})==362 for rr in methods.values())
assert canary_offers>=3
cohorts_by_offer={r['offer_id']:r['cohort']for r in offered if r['method']=='R1_LAW'}
controls=[dict(r,cohort=cohorts_by_offer[r['offer_id']])for r in source if r['method'] in ['E0','P1','P2','RETAINED_EARLIER_PREVALENCE_V8','ALWAYS_OVER','ALWAYS_UNDER']]
alloffers=offered+controls

def selected(rr,co):return [r for r in rr if co=='ALL' or r['cohort'][co]]
scopes={'WR_TE':['WR','TE'],'RB':['RB'],'ALL_SUPPORTED':['RB','WR','TE']}
numchecks=0
for filename,rows in [('NUMERICAL_SCORES-2026.json.xz',numeric),('OFFERED_NUMERICAL_SCORES.json.xz',None)]:
    if rows is None:
        maps={(r['offer_id'],r['method']):r for r in offered};rows=[]
        for oid,c in templates.items():
            r={k:c[k] for k in ['game_id','player_id','position','season','week','actual']};r['cohort']=maps[(oid,'R1_LAW')]['cohort']
            for arm in ['R0','R1','R2','R3']:
                v=maps[(oid,arm+'_LAW')];r[arm]=None if v.get('mean')is None else dict(mean=v['mean'],median=v['median'],hard_fallback=v.get('hard_fallback',False),profile_covered=v.get('profile_covered',False),any_imputed=v.get('any_imputed',False))
            rows.append(r)
    for s in read(EXP/filename):
        rr=selected([r for r in rows if r['position']in scopes[s['scope']] and (s['week']=='ALL' or r['week']==s['week'])],s['cohort']);aa=[r for r in rr if r[s['method']] is not None];kk=[r for r in aa if r['actual']is not None]
        for k,v in dict(eligible=len(rr),available=len(aa),known=len(kk),unknown=len(aa)-len(kk),unavailable=len(rr)-len(aa),games=len({r['game_id']for r in kk})).items():eq(s[k],v,k)
        if kk:
            e=[r[s['method']]['mean']-r['actual']for r in kk];m=[r[s['method']]['median']-r['actual']for r in kk]
            for k,v in dict(mean_MAE=sum(map(abs,e))/len(e),median_MAE=sum(map(abs,m))/len(m),mean_MSE=sum(v*v for v in e)/len(e),mean_RMSE=math.sqrt(sum(v*v for v in e)/len(e)),mean_bias=sum(e)/len(e),median_bias=sum(m)/len(m)).items():eq(s[k],v,k)
            for key in ['hard_fallback','profile_covered','any_imputed']:
                outkey=key if key=='hard_fallback' else key+'_known';eq(s[outkey],sum(bool(r[s['method']].get(key,False))for r in kk))
        numchecks+=1

scorechecks=0;summary=[]
for s in read(EXP/'ACTUAL_LINE_SCORES.json.xz'):
    rr=selected([r for r in alloffers if r['method']==s['method'] and r['position']in scopes[s['scope']] and (s['week']=='ALL' or r['week']==s['week'])],s['cohort'])
    for k,v in dict(eligible=len(rr),unavailable=sum(r['selected_side']is None for r in rr),abstentions=sum(r['selected_side']=='ABSTAIN'for r in rr),states=dict(collections.Counter(grade(r)for r in rr)),games=len({r['game_id']for r in rr}),player_games=len({(r['game_id'],r['player_id'])for r in rr})).items():eq(s[k],v,k)
    for side in ['OVER','UNDER','COMBINED']:
        zz=[r for r in rr if r['selected_side']in ['OVER','UNDER']]if side=='COMBINED'else[r for r in rr if r['selected_side']==side]
        wins=sum(grade(r)=='WIN'for r in zz);losses=sum(grade(r)=='LOSS'for r in zz);n=wins+losses
        for k,v in dict(selected=len(zz),wins=wins if n else None,losses=losses if n else None,decided=n,rate=wins/n if n else None).items():eq(s[side][k],v,side+k)
    bp=[r for r in rr if grade(r)in ['WIN','LOSS','PUSH']and r.get('probabilities')and r.get('Brier')is not None]
    eq(s['Brier'],sum(r['Brier']for r in bp)/len(bp)if bp else None)
    eq(s['log_loss'],sum(r['log_loss']for r in bp)/len(bp)if bp and all(r.get('log_loss')is not None for r in bp)else None)
    eq(s['coverage'],s['COMBINED']['selected']/len(rr)if rr else None)
    if s['scope']=='WR_TE'and s['cohort']=='ALL'and s['week']=='ALL'and s['method']in ['R0_LAW','R1_LAW','R2_LAW','R3_LAW','P2','E0']:
        summary.append({k:s[k]for k in ['method','OVER','UNDER','COMBINED','Brier','eligible','unavailable','states']})
    scorechecks+=1

numeric_summary=[]
for arm in ['R0','R1','R2','R3']:
    rr=[r for r in numeric if r['position']in ['WR','TE']and r['actual']is not None and r[arm]is not None]
    numeric_summary.append(dict(arm=arm,n=len(rr),median_MAE=sum(abs(r[arm]['median']-r['actual'])for r in rr)/len(rr)))
run=read(EXP/'RUN-2026.json');assert run['fit_attempts_cumulative']==24 and run['registration_SHA256']==wavesha
assert all(o['latest_training_available_UTC']<o['fit_cutoff_UTC']for o in run['origins'])
receipt=dict(id='C-C03-INDEPENDENT-FITTED-v1',verdict='PASS_WITH_STRONG_CONTROL_AND_COVERAGE_LIMITS',new_fits=0,network_requests=0,
    model_cases=len(canaries),new_model_registration_bindings=dict(regs),same_arm_origin_memberships=True,maximum_mean_delta=maxmean,
    batch_single_shuffled_queries=batch_checks,statistical_probability_boundary_checks=boundary_checks,real_offer_canary_probabilities=canary_offers,
    law='95%equally-weighted-tree empirical response +5%earlier role geometric tail;not a Poisson law. Unit mass,zero/tail support,lower median and whole/half-line complements checked.',
    numerical_rows=len(numeric),original_labels_and_population_exact=True,every_saved_cohort_tag_matches_frozen_raw_checked_membership=True,numerical_summary_cells=numchecks,numerical=numeric_summary,
    offer_method_rows=len(offered),own_side_grades_and_labels_all_exact=True,offer_summary_cells=scorechecks,actual_line_summary=summary,
    representative_own_sides=representative,unavailable_R0_each_product=22,candidate_each_product_unknown=24,
    point_probability_metrics='N/A and absent for all MEAN/MEDIAN rows;legacyR0typedpoint is r.point,not nullable mean/median metadata',
    limits=['All new exact-line results only2026W2-W3;no5week law qualification','Broad stat-row and exploratory priority/top20 populations remain distinct from authenticated pregamerosters/commonboards','R0fullrole337decided differs from candidate338;WRTEsame255matched','WeakR0numerical/selection gains do not establish a win over stronger retainedP2=150/255 or directE0probability control','No independent refit/training-source regeneration performed in this fitted-inference scope'],
    code_SHA256={str(p.relative_to(ROOT)):sha(p)for p in [ROOT/'src/receiving_increment_c03.py',ROOT/'src/receiving_defense_c03.py',ROOT/'src/receiving_priority_c03.py']},
    CPU_seconds=time.process_time()-START,peak_RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,threads=1)
assert receipt['CPU_seconds']<=100 and receipt['peak_RSS_bytes']<=805306368
(OUT/'FITTED_REVIEW.json').write_text(json.dumps(receipt,separators=(',',':'))+'\n')
print(json.dumps({k:receipt[k]for k in ['verdict','model_cases','batch_single_shuffled_queries','real_offer_canary_probabilities','numerical_summary_cells','offer_summary_cells','numerical','CPU_seconds','peak_RSS_bytes']}))
