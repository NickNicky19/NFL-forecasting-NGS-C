"""One frozen provider-moment conditioner; no solve runs at import.

Inputs are admitted raw provider points keyed by GSIS, never comparator columns.
Core and child optimizations are separate: child anchors cannot change counts.
Only root's admitted worker may call ``condition_game`` after freeze A.
"""
from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import math

import numpy as np
from scipy.optimize import minimize
from scipy.special import logsumexp

from shared_game_sim01_kernel import TeamParameters, GainTupleLaw, _team_check

CORE = ('pass_att', 'pass_cmp', 'pass_int', 'rush_att', 'rec')
CHILD = ('pass_yd', 'rec_yd', 'rush_yd', 'pass_td')
SETTINGS = dict(method='L-BFGS-B', maxiter=500, maxfun=1000, ftol=1e-10, gtol=1e-6,
                initialization='one earlier-prior state', retries=0)


def _primitive(x):
    if isinstance(x, np.ndarray): return x.tolist()
    if isinstance(x, np.generic): return x.item()
    if isinstance(x, dict): return {str(k): _primitive(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)): return [_primitive(v) for v in x]
    return x


def fitted_state(t):
    """Complete primitive parameter replay record (no pickle/context)."""
    d = {k: _primitive(getattr(t, k)) for k in
         ('team_id', 'actor_ids', 'other_index', 'qb_indices', 'target_indices',
          'rusher_indices', 'opportunity_mean', 'event_alpha', 'qb_alpha',
          'target_alpha', 'conversion_alpha', 'rusher_alpha')}
    def law(x):
        return None if x is None else dict(gains=x.gains.tolist(),
            touchdowns=x.touchdowns.tolist(), weights=x.weights.tolist())
    d['catch_laws'] = None if t.catch_laws is None else [[law(x) for x in row] for row in t.catch_laws]
    for key in ('designed_laws', 'scramble_laws', 'kneel_laws'):
        d[key] = None if getattr(t, key) is None else [law(x) for x in getattr(t, key)]
    return d


def restore_fitted_state(d):
    def law(x):
        return None if x is None else GainTupleLaw(np.asarray(x['gains'],dtype=np.int64),
            np.asarray(x['touchdowns'],dtype=np.int64),np.asarray(x['weights'],dtype=float)).checked()
    args = {k: d[k] for k in ('team_id','actor_ids','other_index','qb_indices',
        'target_indices','rusher_indices','opportunity_mean','event_alpha','qb_alpha',
        'target_alpha','conversion_alpha','rusher_alpha')}
    args['catch_laws'] = None if d['catch_laws'] is None else tuple(tuple(law(x) for x in row) for row in d['catch_laws'])
    for key in ('designed_laws','scramble_laws','kneel_laws'):
        args[key] = None if d[key] is None else tuple(law(x) for x in d[key])
    t=TeamParameters(**args); _team_check(t); return t


class _Simplex:
    """Fixed prior concentration/support; minimal free softmax coordinates."""
    def __init__(self, prior):
        self.prior=np.asarray(prior,dtype=float); self.active=np.flatnonzero(self.prior>0)
        if self.prior.ndim!=1 or not len(self.active) or np.any(self.prior<0) or not np.isfinite(self.prior).all():
            raise ValueError('INVALID_PRIOR_SIMPLEX')
        self.total=float(self.prior.sum()); self.p0=self.prior[self.active]/self.total
        self.initial=np.log(self.p0[:-1]/self.p0[-1]); self.size=len(self.initial)
    def values(self, x):
        logits=np.append(x,0.); lp=logits-logsumexp(logits); p=np.exp(lp)
        if np.any(p==0) or not np.isfinite(p).all():raise FloatingPointError('SIMPLEX_NUMERICAL_UNDERFLOW;NO_REPAIR')
        full=np.zeros_like(self.prior); full[self.active]=p
        return full, p, lp
    def penalty_grad(self, x, full_grad):
        full,p,lp=self.values(x); logratio=lp-np.log(self.p0)
        g=np.asarray(full_grad)[self.active]+logratio+1.
        return float(p@logratio), (p*(g-float(p@g)))[:-1]


def core_means(t):
    """Analytic unconditional means; E[shared game frailty]=1."""
    e=t.event_alpha/t.event_alpha.sum(); q=t.qb_alpha/t.qb_alpha.sum()
    dest=t.target_alpha/t.target_alpha.sum(axis=1,keepdims=True)
    conv=t.conversion_alpha/t.conversion_alpha.sum(axis=2,keepdims=True)
    rp=t.rusher_alpha/t.rusher_alpha.sum(); lam=t.opportunity_mean
    aq=lam*e[0]*q; out={f:np.zeros(len(t.actor_ids)) for f in CORE}
    out['pass_att'][list(t.qb_indices)]=aq
    out['pass_cmp'][list(t.qb_indices)]=aq*np.sum(dest*conv[:,:,0],axis=1)
    out['pass_int'][list(t.qb_indices)]=aq*np.sum(dest*conv[:,:,1],axis=1)
    out['rec'][list(t.target_indices)]=np.sum(aq[:,None]*dest[:,:-1]*conv[:,:-1,0],axis=0)
    np.add.at(out['rush_att'],list(t.rusher_indices),lam*e[3]*rp)
    np.add.at(out['rush_att'],list(t.qb_indices),lam*(e[2]+e[4])*q)
    return out, (e,q,dest,conv,rp,aq)


def _targets(t, anchors, variances, categories, available=None):
    records=[]; missing=[]
    for ai,actor in enumerate(t.actor_ids):
        for category,value in anchors.get(actor,{}).items():
            if category not in categories: continue
            if value is None:
                missing.append(dict(actor_id=actor,category=category,reason='UNAVAILABLE_PROVIDER_RAW'))
                continue
            if not isinstance(value,(float,int)) or not math.isfinite(value):raise ValueError('INVALID_PROVIDER_POINT')
            if category in CORE and value<0:raise ValueError('NEGATIVE_COUNT_PROVIDER_ANCHOR')
            if available is not None and not available[category][ai]:
                missing.append(dict(actor_id=actor,category=category,reason='UNAVAILABLE_QUALIFIED_CHILD_LAW'));continue
            v=variances.get(actor,{}).get(category)
            # One-unit positive variance prior was frozen in recipe; not estimated from test outcomes.
            if v is None:v=1.; variance_origin='FROZEN_ONE_UNIT_SUPPORT_FALLBACK'
            else:variance_origin='EARLIER_PROCESS_VARIANCE'
            if not isinstance(v,(float,int)) or not math.isfinite(v) or v<=0:raise ValueError('INVALID_EARLIER_PROCESS_VARIANCE')
            records.append(dict(actor_id=actor,actor_index=ai,category=category,value=float(value),variance=float(v),variance_origin=variance_origin))
    return records,missing


def _squared(means, records):
    grad={f:np.zeros_like(v) for f,v in means.items()}; loss=0.
    for r in records:
        f,a=r['category'],r['actor_index']; delta=means[f][a]-r['value']
        loss+=delta*delta/r['variance'];grad[f][a]+=2*delta/r['variance']
    return float(loss),grad


def _solve(objective, x0, *, stage='UNSPECIFIED_STAGE', execution=None):
    """One bounded solve, with no objective evaluations for logging.

    ``execution(event)`` is the worker-owned durable logger/aggregate limiter.
    It is called before a stage/evaluation and at every accepted iteration, so
    it can refuse work before an aggregate limit is exceeded.  The local hard
    guards apply independently of SciPy's advisory ``maxfun``/``maxiter``.
    Production freezes require that worker callback; optionality supports the
    deterministic software contracts without opening source/model state.
    """
    x0=np.asarray(x0,dtype=float)
    evaluations=iterations=0; cache={};last_evaluated=last_accepted=None
    initial_objective=None
    def emit(event, **fields):
        if execution is not None:
            execution(dict(event=event,stage=stage,nfev=evaluations,nit=iterations,**fields))
    def key(x):
        a=np.ascontiguousarray(x,dtype=float)
        return a.shape,a.tobytes()
    def snapshot(x):
        k=key(x)
        if k not in cache:raise RuntimeError('ACCEPTED_ITERATE_NOT_IN_COUNTED_OBJECTIVE_CACHE')
        return cache[k]
    def counted(x):
        nonlocal evaluations,last_evaluated,initial_objective
        if evaluations>=SETTINGS['maxfun']:
            raise RuntimeError('HARD_OBJECTIVE_EVALUATION_LIMIT;NO_RETRY')
        # The parent consumes its aggregate count before this actual call.
        emit('BEFORE_OBJECTIVE',next_nfev=evaluations+1)
        evaluations+=1
        value,gradient=objective(x)
        value=float(value);gradient=np.asarray(gradient,dtype=float)
        if not math.isfinite(value) or gradient.shape!=np.asarray(x).shape or not np.isfinite(gradient).all():
            raise FloatingPointError('NONFINITE_OR_INVALID_CONDITION_OBJECTIVE')
        entry=dict(vector=np.asarray(x,dtype=float).tolist(),objective=value,
            gradient=gradient.tolist(),gradient_infinity_norm=float(np.max(np.abs(gradient))) if gradient.size else 0.)
        cache[key(x)]=entry;last_evaluated=entry
        if initial_objective is None and np.array_equal(x,x0):initial_objective=value
        return value,gradient
    def accepted(x):
        nonlocal iterations,last_accepted
        if iterations>=SETTINGS['maxiter']:
            raise RuntimeError('HARD_ACCEPTED_ITERATION_LIMIT;NO_RETRY')
        entry=snapshot(x)
        emit('ACCEPTED_ITERATION',next_nit=iterations+1)
        iterations+=1;last_accepted=entry
        if iterations%10==0:
            emit('CHECKPOINT',last_accepted=entry,last_evaluated=last_evaluated,
                 initial_objective=initial_objective)
    def record_base():
        return dict(stage=stage,nit=iterations,nfev=evaluations,initial=x0.tolist(),
            initial_objective=initial_objective,last_accepted=last_accepted,
            last_evaluated=last_evaluated,settings=dict(SETTINGS),
            objective_change=None if initial_objective is None or last_evaluated is None else last_evaluated['objective']-initial_objective,
            checkpoint_evaluation_policy='COUNTED_CACHE_ONLY;NO_LOGGING_EVALUATIONS')
    try:
        emit('STAGE_STARTED',initial=x0.tolist(),settings=dict(SETTINGS),
            initial_SHA256=hashlib.sha256(np.ascontiguousarray(x0).tobytes()).hexdigest(),
            optimizer_invocation=int(bool(len(x0))))
        if not len(x0):
            value,gradient=counted(x0)
            record=dict(record_base(),success=True,status=0,message='NO_FREE_PARAMETERS',
                objective=value,solution=x0.tolist(),final_gradient=gradient.tolist(),
                gradient_infinity_norm=0.,scipy_nit=0,scipy_nfev=0)
            emit('TERMINATED',record=record)
            return x0,record
        result=minimize(counted,x0,method=SETTINGS['method'],jac=True,callback=accepted,
            options={k:SETTINGS[k] for k in ('maxiter','maxfun','ftol','gtol')})
        final=snapshot(result.x)
        record=dict(record_base(),success=bool(result.success),status=int(result.status),
            message=str(result.message),objective=float(result.fun),solution=result.x.tolist(),
            final_gradient=final['gradient'],gradient_infinity_norm=final['gradient_infinity_norm'],
            scipy_nit=int(result.nit),scipy_nfev=int(result.nfev))
        emit('TERMINATED',record=record)
    except BaseException as error:
        record=dict(record_base(),success=False,status='EXCEPTION',message=str(error),
            exception_type=type(error).__name__)
        error.record=record
        try:emit('EXCEPTION',record=record)
        except BaseException as logging_error:
            record['exception_logging_failure']=dict(type=type(logging_error).__name__,message=str(logging_error))
            raise error from logging_error
        raise
    if not result.success or not np.isfinite(result.x).all() or not math.isfinite(result.fun):
        # Worker persists this failed termination and stops; never a retry/loss.
        error=RuntimeError('PROVIDER_CONDITIONING_FAILED;NO_RETRY');error.record=record;raise error
    return result.x,record


def _prepare_core(t, records):
    _team_check(t)
    names=[('event_alpha',None),('qb_alpha',None),('rusher_alpha',None)]
    names += [('target_alpha',i) for i in range(len(t.qb_indices))]
    names += [('conversion_alpha',(i,j)) for i in range(len(t.qb_indices)) for j in range(len(t.target_indices)+1)]
    groups=[_Simplex(getattr(t,n) if ix is None else getattr(t,n)[ix]) for n,ix in names]
    slices=[];start=1
    for g in groups:slices.append(slice(start,start+g.size));start+=g.size
    if t.opportunity_mean<=0:
        if records:raise ValueError('ZERO_PRIOR_OPPORTUNITY_WITH_PROVIDER_ANCHOR;NO_INVENTED_RATE')
        return (lambda x:(0.,np.zeros_like(x))),np.empty(0),(lambda x:t)
    x0=np.concatenate(([math.log(t.opportunity_mean)],*[g.initial for g in groups]))
    def decode(x):
        args={n:np.array(getattr(t,n),copy=True) for n in ('event_alpha','qb_alpha','rusher_alpha','target_alpha','conversion_alpha')}
        for (name,ix),g,sl in zip(names,groups,slices):
            alpha=g.values(x[sl])[0]*g.total
            if ix is None:args[name]=alpha
            else:args[name][ix]=alpha
        lam=math.exp(float(x[0])); return replace(t,opportunity_mean=lam,**args)
    def objective(x):
        u=decode(x); means,(e,q,d,c,r,aq)=core_means(u);loss,adj=_squared(means,records)
        qb=list(u.qb_indices);dest=list(u.target_indices);rush=list(u.rusher_indices)
        recadj=np.append(adj['rec'][dest],0.)
        fc=np.sum(d*c[:,:,0],axis=1); fi=np.sum(d*c[:,:,1],axis=1)
        ga=adj['pass_att'][qb]+adj['pass_cmp'][qb]*fc+adj['pass_int'][qb]*fi+np.sum(d*c[:,:,0]*recadj[None,:],axis=1)
        gd=aq[:,None]*(adj['pass_cmp'][qb,None]*c[:,:,0]+adj['pass_int'][qb,None]*c[:,:,1]+recadj[None,:]*c[:,:,0])
        gc=np.zeros_like(c);gc[:,:,0]=aq[:,None]*d*(adj['pass_cmp'][qb,None]+recadj[None,:]);gc[:,:,1]=aq[:,None]*d*adj['pass_int'][qb,None]
        rq=adj['rush_att'][qb];rr=adj['rush_att'][rush];lam=u.opportunity_mean
        gl=float(e[0]*(q@ga)+e[3]*(r@rr)+(e[2]+e[4])*(q@rq))
        ge=np.zeros(5);ge[0]=lam*(q@ga);ge[2]=ge[4]=lam*(q@rq);ge[3]=lam*(r@rr)
        gq=lam*e[0]*ga+lam*(e[2]+e[4])*rq;gr=lam*e[3]*rr
        allgrad=[ge,gq,gr]+[gd[i] for i in range(len(q))]+[gc[i,j] for i in range(len(q)) for j in range(len(dest)+1)]
        # KL(Poisson rate||prior rate) plus categorical probability KL for every chain simplex.
        ratio=math.log(lam/t.opportunity_mean);loss+=lam*ratio-lam+t.opportunity_mean
        gradient=np.zeros_like(x);gradient[0]=lam*(gl+ratio)
        for g,sl,a in zip(groups,slices,allgrad):
            penalty,gg=g.penalty_grad(x[sl],a);loss+=penalty;gradient[sl]=gg
        if not math.isfinite(loss) or not np.isfinite(gradient).all():raise FloatingPointError('NONFINITE_CONDITION_OBJECTIVE')
        return float(loss),gradient
    if not records:
        return (lambda x:(0.,np.zeros_like(x))),np.empty(0),(lambda x:t)
    return objective,x0,decode


def _child_edges(t):
    """Conditional expected counts fixed by core; unknown law blocks affected fields."""
    _,(e,q,d,c,r,aq)=core_means(t);k=len(t.actor_ids)
    available={f:np.ones(k,dtype=bool) for f in CHILD};edges=[]
    for qi,p in enumerate(t.qb_indices):
        for di,a in enumerate(t.target_indices):
            rate=float(aq[qi]*d[qi,di]*c[qi,di,0]);law=None if t.catch_laws is None else t.catch_laws[qi][di]
            if rate>0 and law is None:
                available['pass_yd'][p]=available['pass_td'][p]=available['rec_yd'][a]=False
            elif rate>0:edges.append((('catch_laws',qi,di),law.checked(),rate,(('pass_yd',p,'gain'),('pass_td',p,'td'),('rec_yd',a,'gain'))))
    for kind,actors,rates in [('designed_laws',t.rusher_indices,t.opportunity_mean*e[3]*r),
            ('scramble_laws',t.qb_indices,t.opportunity_mean*e[2]*q),('kneel_laws',t.qb_indices,t.opportunity_mean*e[4]*q)]:
        laws=getattr(t,kind)
        for j,a in enumerate(actors):
            law=None if laws is None else laws[j];rate=float(rates[j])
            if rate>0 and law is None:available['rush_yd'][a]=False
            elif rate>0:edges.append(((kind,j),law.checked(kneel=kind=='kneel_laws'),rate,(('rush_yd',a,'gain'),)))
    return edges,available


def _prepare_child(t,anchors,variances):
    edges,available=_child_edges(t);records,missing=_targets(t,anchors,variances,CHILD,available)
    blocks=[];start=0
    for key,law,rate,credits in edges:
        active=np.flatnonzero(law.weights>0);p0=law.weights[active];p0=p0/p0.sum()
        values=[law.gains[active].astype(float),law.touchdowns[active].astype(float)]
        basis=[]
        for v in values:
            center=float(p0@v);scale=math.sqrt(float(p0@np.square(v-center)))
            if scale>0:basis.append((v-center)/scale)
        features=np.array(basis).T if basis else np.empty((len(active),0))
        sl=slice(start,start+features.shape[1]);start=sl.stop
        blocks.append((key,law,rate,credits,active,p0,features,sl))
    x0=np.zeros(start)
    def decode(x):
        out=[]
        for key,law,rate,credits,active,p0,features,sl in blocks:
            lp=np.log(p0)+features@x[sl];lp-=logsumexp(lp);p=np.exp(lp)
            if np.any(p==0):raise FloatingPointError('CHILD_TILT_UNDERFLOW;NO_REPAIR')
            weights=np.zeros_like(law.weights);weights[active]=p
            out.append((replace(law,weights=weights),p,lp))
        return out
    def objective(x):
        decoded=decode(x);means={f:np.zeros(len(t.actor_ids)) for f in CHILD}
        for block,(law,p,lp) in zip(blocks,decoded):
            _,_,rate,credits,active,p0,features,sl=block
            for f,a,kind in credits:means[f][a]+=rate*float(law.weights@(law.gains if kind=='gain' else law.touchdowns))
        loss,adj=_squared(means,records);gradient=np.zeros_like(x)
        for block,(law,p,lp) in zip(blocks,decoded):
            _,_,rate,credits,active,p0,features,sl=block;g=np.zeros(len(active))
            for f,a,kind in credits:g+=rate*adj[f][a]*(law.gains[active] if kind=='gain' else law.touchdowns[active])
            logratio=lp-np.log(p0);loss+=float(p@logratio);g+=logratio+1.
            gradient[sl]=features.T@(p*(g-float(p@g)))
        if not math.isfinite(loss) or not np.isfinite(gradient).all():raise FloatingPointError('NONFINITE_CHILD_CONDITION_OBJECTIVE')
        return float(loss),gradient
    def decode_team(x):
        args={}
        if t.catch_laws is not None:args['catch_laws']=[list(row) for row in t.catch_laws]
        for key in ('designed_laws','scramble_laws','kneel_laws'):
            if getattr(t,key) is not None:args[key]=list(getattr(t,key))
        for block,(law,_,_) in zip(blocks,decode(x)):
            key=block[0]
            if len(key)==3:args[key[0]][key[1]][key[2]]=law
            else:args[key[0]][key[1]]=law
        if 'catch_laws' in args:args['catch_laws']=tuple(tuple(row) for row in args['catch_laws'])
        for key in ('designed_laws','scramble_laws','kneel_laws'):
            if key in args:args[key]=tuple(args[key])
        return replace(t,**args)
    pack=(objective,x0,decode_team) if records else ((lambda x:(0.,np.zeros_like(x))),np.empty(0),(lambda x:t))
    return pack,records,missing,{f:available[f].tolist() for f in available}


def _joint_stage(packs, stage, execution=None):
    """One both-team solve of the unchanged separable sum objective."""
    offsets=np.cumsum([0]+[len(p[1]) for p in packs]);x0=np.concatenate([p[1] for p in packs])
    def objective(x):
        total=0.;gradient=np.zeros_like(x)
        for j,(fun,_,_) in enumerate(packs):
            sl=slice(offsets[j],offsets[j+1]);value,grad=fun(x[sl]);total+=value;gradient[sl]=grad
        return float(total),gradient
    x,record=_solve(objective,x0,stage=stage,execution=execution)
    record.update(stage=stage,team_parameter_offsets=offsets.tolist(),
        component_stage_invocations=1,scipy_minimize_invocations=int(bool(len(x0))),
        jointly_separable_teams=True)
    return tuple(p[2](x[offsets[j]:offsets[j+1]]) for j,p in enumerate(packs)),record


def condition_game(teams, anchors, process_variances=None, *, execution=None):
    """Return conditioned two-team state + complete primitive replay/design record.

    ``anchors[team_id][GSIS][category]`` is a finite raw point or explicit None.
    Keys outside CORE/CHILD do not enter the objective; no lines or W0/W1 read.
    Missing raw points hold only that actor/category's S-P output; no hidden fallback.
    """
    if len(teams)!=2 or teams[0].team_id==teams[1].team_id:raise ValueError('TWO_TEAM_PRIOR_REQUIRED')
    process_variances={} if process_variances is None else process_variances
    inputs=[];corepacks=[]
    for t in teams:
        a=anchors.get(t.team_id,{});v=process_variances.get(t.team_id,{})
        core,missing=_targets(t,a,v,CORE);inputs.append((a,v,core,missing));corepacks.append(_prepare_core(t,core))
    coreteams,corefit=_joint_stage(corepacks,'BOTH_TEAM_COUNT_CORE',execution)
    childpreps=[_prepare_child(u,a,v) for u,(a,v,_,_) in zip(coreteams,inputs)]
    conditioned,childfit=_joint_stage([p[0] for p in childpreps],'BOTH_TEAM_CHILD_CORE_HELD',execution)
    records=[]
    for t,u,(_,_,core,missing),(_,child,childmissing,available) in zip(teams,conditioned,inputs,childpreps):
        _team_check(u)
        records.append(dict(team_id=t.team_id,prior_state=fitted_state(t),fitted_state=fitted_state(u),
            consumed_core_anchors=core,consumed_child_anchors=child,unavailable=missing+childmissing,
            source_child_availability=available,core_optimizer=corefit,child_optimizer=childfit,
            count_core_unchanged_by_child=True))
    design=dict(recipe='C-SHARED-GAME-SP-BOX-v1',conditioner='ONE_KL_MOMENT_PROJECTION_CORE_THEN_CHILD',
        settings=SETTINGS,teams=records,component_stage_invocations=2,
        scipy_minimize_invocations=corefit['scipy_minimize_invocations']+childfit['scipy_minimize_invocations'],
        provider_missing_policy='UNAVAILABLE_AFFECTED_ACTOR_CATEGORY;NO_COMPARATOR_FALLBACK',
        variance_policy='Earlier supplied positive process variance; explicitly frozen one-unit support fallback if missing')
    # Bind the actual consumed anchor-bearing design before reducing the public
    # replay record. Fitted state exactly replays forecasts; public retention
    # does not need to disclose the provider input points or residual vectors.
    canonical=json.dumps(design,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    design['consumed_design_SHA256']=hashlib.sha256(canonical).hexdigest()
    for record in design['teams']:
        for field in ('consumed_core_anchors','consumed_child_anchors'):
            record[field]=[{k:v for k,v in anchor.items() if k!='value'} for anchor in record[field]]
    design['retention_scope']='Own primitive fitted state and aggregate fit/support metadata; literal provider anchors excluded'
    return tuple(conditioned),design
