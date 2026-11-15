"""Earlier-fit, same-information sanity controls for C's bounded M3 wave.

The count control learns a regularized log-linear mean and ONE global positive
NB shape.  It does not claim feature-dependent dispersion.  The signed control
is ridge location plus one training-residual scale, with Student-t df fixed at5.
All preprocessing is fitted on the supplied eligible training rows only.
Only primitive JSON is persisted; pickle and model convenience loaders are unused.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import time
import warnings

import numpy as np
from scipy.optimize import minimize
from scipy.special import expit, gammaln
from scipy.stats import t

SCHEMA = 'C-M3-EARLIER-FIT-SANITY-v1'
ETA_CAP = 30.
NB_L2 = .1
RIDGE_L2 = 10.
STUDENT_DF = 5.
STUDENT_SCALE_FLOOR = .05
MAX_ITERATIONS = 100


def _x_matrix(x):
    a = np.asarray(x, dtype=float)
    if a.ndim == 1:
        a = a.reshape(1, -1)
    if a.ndim != 2 or not a.shape[1]:
        raise ValueError('SANITY_EXPECTED_NONEMPTY_FEATURE_MATRIX')
    return a


def _names(feature_names, columns):
    out = list(feature_names)
    if len(out) != columns or len(set(out)) != columns or not all(isinstance(n,str) and n for n in out):
        raise ValueError('SANITY_FEATURE_ORDER_INVALID')
    return out


def _fit_design(x):
    finite = np.isfinite(x)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', RuntimeWarning)
        m = np.nanmedian(np.where(finite, x, np.nan), axis=0)
    m = np.where(np.isfinite(m), m, 0.)
    raw = np.column_stack([np.where(finite, x, m), ~finite]).astype(float)
    center = raw.mean(axis=0)
    scale = raw.std(axis=0)
    scale = np.where(scale > 1e-8, scale, 1.)
    z = np.column_stack([np.ones(len(x)), (raw-center)/scale])
    return z, m, center, scale


def _apply_design(x, medians, center, scale):
    finite = np.isfinite(x)
    raw = np.column_stack([np.where(finite, x, medians), ~finite]).astype(float)
    return np.column_stack([np.ones(len(x)), (raw-center)/scale])


def nb_objective(theta, z, y, regularization=NB_L2):
    """Mean NLL plus L2, with analytic derivative of the explicit clipped loss.

    For integer counts the log-gamma ratio is an exact finite sum.  Combining its
    y*log(r) term algebraically avoids catastrophic cancellation near Poisson.
    The ±30 caps are numerical parts of this declared control, not test tuning.
    Intercept and global log-shape are unpenalized.
    """
    theta = np.asarray(theta, dtype=float)
    beta, raw_log_r = theta[:-1], float(theta[-1])
    raw_eta = z @ beta
    eta = np.clip(raw_eta, -ETA_CAP, ETA_CAP)
    log_r = float(np.clip(raw_log_r, -ETA_CAP, ETA_CAP))
    mu, r = np.exp(eta), math.exp(log_r)
    # Integer identity: logGamma(y+r)-logGamma(r)-y*log(r)
    # = sum_{j=0}^{y-1} log1p(j/r).  Its log-r derivative is -sum j/(r+j).
    counts = np.asarray(y, dtype=int)
    gamma_difference = np.zeros(len(y), dtype=float)
    gamma_shape_gradient = np.zeros(len(y), dtype=float)
    for j in range(1, int(counts.max(initial=0))):
        mask = counts > j
        gamma_difference[mask] += math.log1p(j/r)
        gamma_shape_gradient[mask] += j/(r+j)
    log_ratio = np.log1p(mu/r)
    nll = gammaln(y+1)-gamma_difference+(r+y)*log_ratio-y*eta
    loss = float(nll.mean()+.5*regularization*np.dot(beta[1:],beta[1:]))
    eta_gradient = r*(mu-y)/(r+mu)
    eta_gradient *= (raw_eta > -ETA_CAP) & (raw_eta < ETA_CAP)
    beta_gradient = z.T@eta_gradient/len(y)
    beta_gradient[1:] += regularization*beta[1:]
    shape_gradient = gamma_shape_gradient+r*log_ratio-(r+y)*mu/(r+mu)
    log_r_gradient = float(shape_gradient.mean()) if -ETA_CAP < raw_log_r < ETA_CAP else 0.
    return loss, np.r_[beta_gradient,log_r_gradient]


class SanityModel:
    def __init__(self, payload):
        self.payload = payload
        if payload.get('schema') != SCHEMA or payload.get('kind') not in ['count','signed']:
            raise ValueError('SANITY_SCHEMA_INVALID')
        self.kind = payload['kind']
        self.feature_names = _names(payload['feature_order'],len(payload['medians']))
        self.m = np.asarray(payload['medians'],float)
        self.center = np.asarray(payload['center'],float)
        self.scale = np.asarray(payload['scale'],float)
        self.coef = np.asarray(payload['coef'],float)
        p = len(self.feature_names)
        if self.center.shape != (2*p,) or self.scale.shape != (2*p,) or self.coef.shape != (2*p+1,):
            raise ValueError('SANITY_PARAMETER_SHAPE_INVALID')
        if not all(np.isfinite(v).all() for v in [self.m,self.center,self.scale,self.coef]) or not np.all(self.scale > 0):
            raise ValueError('SANITY_NONFINITE_PARAMETER')
        if self.kind == 'count':
            if not math.isfinite(payload['log_shape']) or abs(payload['log_shape']) > ETA_CAP:
                raise ValueError('SANITY_NB_SHAPE_INVALID')
        elif payload['df'] != STUDENT_DF or not math.isfinite(payload['residual_scale']) or payload['residual_scale'] < STUDENT_SCALE_FLOOR:
            raise ValueError('SANITY_STUDENT_PARAMETERS_INVALID')
        self.training = dict(payload['training'])
        self.diagnostics = self.training

    def predict_params(self, x, feature_names=None):
        x = _x_matrix(x)
        if x.shape[1] != len(self.feature_names):
            raise ValueError('SANITY_FEATURE_COUNT_MISMATCH')
        if feature_names is not None and list(feature_names) != self.feature_names:
            raise ValueError('SANITY_FEATURE_ORDER_MISMATCH')
        z = _apply_design(x,self.m,self.center,self.scale)
        location = z@self.coef
        if self.kind == 'count':
            shape = math.exp(self.payload['log_shape'])
            eta = np.clip(location,-ETA_CAP,ETA_CAP)
            probability = expit(eta-self.payload['log_shape'])
            if not np.all((probability > 0) & (probability < 1)):
                # Do not silently repair a saturated response into a different law.
                raise ArithmeticError('SANITY_NB_PROBABILITY_FLOAT_SATURATION')
            return dict(total_count=np.full(len(x),shape,dtype=float),probs=np.asarray(probability,dtype=float))
        if not np.isfinite(location).all():
            raise ArithmeticError('SANITY_STUDENT_LOCATION_NONFINITE')
        return dict(df=np.full(len(x),STUDENT_DF,dtype=float),loc=np.asarray(location,dtype=float),
                    scale=np.full(len(x),self.payload['residual_scale'],dtype=float))

    def to_dict(self):
        # A JSON round trip also rejects any accidental nonprimitive mutation.
        return json.loads(json.dumps(self.payload,allow_nan=False))

    def save(self, path):
        path = Path(path)
        data = (json.dumps(self.to_dict(),sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
        path.parent.mkdir(parents=True,exist_ok=True)
        if path.exists():
            if path.read_bytes() != data:
                raise FileExistsError('SANITY_FROZEN_MODEL_EXISTS')
        else:
            path.write_bytes(data)
        return dict(path=str(path),bytes=len(data),SHA256=hashlib.sha256(data).hexdigest())

    @classmethod
    def load(cls,path):
        return cls(json.loads(Path(path).read_text()))


def load(path):
    return SanityModel.load(path)


def fit(x,y,kind,feature_names):
    aliases={'count':'count','rec':'count','NB':'count','nb':'count',
             'signed':'signed','rec_yd':'signed','StudentT':'signed','student_t':'signed'}
    if kind not in aliases:
        raise ValueError('SANITY_KIND_UNSUPPORTED')
    kind = aliases[kind]
    x = _x_matrix(x)
    names = _names(feature_names,x.shape[1])
    y = np.asarray(y,dtype=float)
    if y.ndim != 1 or len(y) != len(x) or len(y) < 2 or not np.isfinite(y).all():
        raise ValueError('SANITY_LABELS_REQUIRE_QUALIFIED_FINITE_TRAINING_ROWS')
    if kind == 'count' and (np.any(y < 0) or np.any(y != np.floor(y))):
        raise ValueError('SANITY_COUNT_LABELS_INVALID')
    z,medians,center,scale = _fit_design(x)
    common = dict(schema=SCHEMA,kind=kind,feature_order=names,
        medians=medians.tolist(),center=center.tolist(),scale=scale.tolist(),
        preprocessing='TRAIN_ONLY_MEDIAN_AND_MISSING_INDICATORS;TRAIN_ONLY_STANDARDIZATION',
        label_policy='CALLER_SUPPLIED_ELIGIBLE_EARLIER_QUALIFIED_LABELS;NO_UNKNOWN_TO_ZERO',
        training_rows=len(y))
    if kind == 'count':
        mu = max(float(y.mean()),.05)
        variance = float(y.var())
        shape = min(1e4,max(1e-3,mu*mu/(variance-mu))) if variance > mu else 100.
        initial = np.r_[math.log(mu),np.zeros(z.shape[1]-1),math.log(shape)]
        result = minimize(nb_objective,initial,args=(z,y,NB_L2),jac=True,
                          method='L-BFGS-B',options=dict(maxiter=MAX_ITERATIONS,ftol=1e-10,gtol=1e-6))
        coef = result.x[:-1]
        log_shape = float(np.clip(result.x[-1],-ETA_CAP,ETA_CAP))
        objective,gradient = nb_objective(result.x,z,y,NB_L2)
        unpenalized = nb_objective(result.x,z,y,0.)[0]
        common.update(coef=coef.tolist(),log_shape=log_shape,
            numeric_contract=dict(eta_cap=ETA_CAP,log_shape_cap=ETA_CAP,
                                  clip_chain_derivative='ZERO_OUTSIDE_CAP;ZERO_SUBGRADIENT_AT_BOUNDARY'),
            objective='MEAN_NB_NLL_PLUS_HALF_L2_SLOPES',regularization=NB_L2,
            training=dict(optimizer='L-BFGS-B',success=bool(result.success),
                message=str(result.message),iterations=int(result.nit),function_evaluations=int(result.nfev),
                max_iterations=MAX_ITERATIONS,penalized_objective=float(objective),
                mean_training_NLL=float(unpenalized),gradient_max_abs=float(abs(gradient).max()),
                eligible_label_mean=float(y.mean()),eligible_label_variance=float(y.var()),
                shape=float(math.exp(log_shape)),feature_dependent_dispersion=False))
    else:
        penalty = np.eye(z.shape[1])*RIDGE_L2
        penalty[0,0] = 0.
        coef = np.linalg.solve(z.T@z+penalty,z.T@y)
        residuals = y-z@coef
        rms = float(np.sqrt(np.mean(residuals**2)))
        sigma = max(STUDENT_SCALE_FLOOR,rms*math.sqrt((STUDENT_DF-2)/STUDENT_DF))
        mean_nll = float(-t.logpdf(y,STUDENT_DF,loc=z@coef,scale=sigma).mean())
        common.update(coef=coef.tolist(),df=STUDENT_DF,residual_scale=sigma,
            objective='RIDGE_LOCATION_PLUS_TRAINING_RMS_STUDENT_SCALE',regularization=RIDGE_L2,
            training=dict(optimizer='DETERMINISTIC_LINEAR_SOLVE',success=True,
                mean_training_continuous_NLL=mean_nll,residual_RMS=rms,
                scale_rule='MAX(.05,RMS*SQRT(3/5));FIXED_DF_5',
                scale_floor=STUDENT_SCALE_FLOOR,feature_dependent_dispersion=False))
    return SanityModel(common)


def deterministic_fixtures(cpu_limit=5.):
    """Small non-NFL eligible-signal and safe-restoration checks only."""
    start = time.process_time()
    from tempfile import TemporaryDirectory
    rng = np.random.default_rng(1701)
    x = rng.normal(size=(180,3))
    x[::13,2] = np.nan
    y = rng.negative_binomial(3.,3./(3.+np.exp(.7+.8*x[:,0]))).astype(float)
    z,*_ = _fit_design(x)
    theta = np.r_[.5,np.array([.1,-.2,.05,.03,-.02,.01]),math.log(3.)]
    _,analytic = nb_objective(theta,z,y)
    numeric=[]
    for i in range(len(theta)):
        h=1e-5*max(1.,abs(theta[i]));up=theta.copy();down=theta.copy();up[i]+=h;down[i]-=h
        numeric.append((nb_objective(up,z,y)[0]-nb_objective(down,z,y)[0])/(2*h))
    gradient_error=float(np.max(abs(analytic-np.asarray(numeric))))
    assert gradient_error < 1e-6
    count = fit(x,y,'rec',['signal','nuisance','sparse'])
    assert count.training['success'] and count.coef[1] > .1
    signed_y = 12.+8*x[:,0]+rng.standard_t(5,len(x))*2.
    signed = fit(x,signed_y,'rec_yd',['signal','nuisance','sparse'])
    assert signed.coef[1] > 1
    checks=[]
    for model in [count,signed]:
        batch=model.predict_params(x[:3],model.feature_names)
        single=[model.predict_params(r,model.feature_names) for r in x[:3]]
        assert all(np.allclose(batch[k],[row[k][0] for row in single],rtol=0,atol=1e-12) for k in batch)
        with TemporaryDirectory(prefix='m3-sanity-fixture-') as tmp:
            p=Path(tmp)/'model.json';wire=model.save(p);restored=load(p)
            restored_params=restored.predict_params(x[:3],model.feature_names)
            assert all(np.array_equal(restored_params[k],batch[k]) for k in batch)
            model.save(p) # Output-preserving save is allowed; changed bytes are not.
        try:model.predict_params(x[:1],list(reversed(model.feature_names)))
        except ValueError:pass
        else:raise AssertionError('FEATURE_ORDER_NOT_ENFORCED')
        checks.append(dict(kind=model.kind,success=model.training['success'],
                           model_wire_bytes=wire['bytes'],training=model.training))
    used=time.process_time()-start
    assert used <= cpu_limit,'SANITY_SYNTHETIC_CPU_CAP'
    return dict(gradient_max_abs_error=gradient_error,checks=checks,CPU_seconds=used,
                no_NFL_rows=True,no_feature_or_settings_search=True)
