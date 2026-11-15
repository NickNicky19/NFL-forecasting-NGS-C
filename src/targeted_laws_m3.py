"""Typed integer laws for C's bounded M3 distribution experiment.

No fitting, acquisition or artifact deserialization happens here.  Parameter
rows are *transformed distribution parameters* returned by the pinned library,
not unconstrained XGBoost margins.  PyTorch NegativeBinomial uses ``probs`` as
failure odds: mean=r*p/(1-p).  SciPy's success probability is therefore 1-p.
StudentT training uses the library's continuous likelihood; evaluation below
uses a separately declared integer-bin law, never continuous density as mass.
"""
from __future__ import annotations

import math
from decimal import Decimal
from typing import Mapping, Sequence

import numpy as np
from scipy.special import gammaln, kve
from scipy.stats import nbinom, t
from contracts_v2 import probs, thresholds_for_line

MOMENT_TOLERANCE = 1e-10
MAX_MOMENT_TERMS = 10000


def _finite(name, value):
    if isinstance(value, (bool, np.bool_)):
        raise ValueError(name + '_NOT_NUMERIC')
    z = float(value)
    if not math.isfinite(z):
        raise ValueError(name + '_NONFINITE')
    return z


def _integer(k):
    try:
        v = _finite('outcome', k)
        return int(v) if v.is_integer() else None
    except (TypeError, ValueError, OverflowError):
        return None


def _logdiff(log_large, log_small):
    """log(exp(a)-exp(b)) without subtracting nearly equal probabilities."""
    a, b = float(log_large), float(log_small)
    if b == -math.inf:
        return a
    if a < b:
        if b-a < 1e-12:
            return -math.inf
        raise ArithmeticError('NONMONOTONE_LOG_CDF')
    if a == b:
        return -math.inf
    return a + math.log(-math.expm1(b-a))


def _stable_probability(law, line):
    # Use the adopted exact boundary contract.  SF supplies extreme upper tails
    # which 1-CDF may lose to floating-point cancellation.  The common helper is
    # still checked on every call at the existing complementary-law tolerance.
    reference = probs(law.cdf, line, 1)
    lo, hi, on_grid = thresholds_for_line(line, 1)
    under, over = law.cdf(lo), law.sf(hi)
    push = law.pmf(hi) if on_grid else 0.
    result = dict(under=float(under), push=float(push), over=float(over))
    if any(not math.isfinite(v) or v < 0 for v in result.values()):
        raise ArithmeticError('INVALID_PROBABILITY')
    if abs(sum(result.values())-1.) > 1e-10:
        raise ArithmeticError('NONNORMALIZED_PROBABILITY')
    if max(abs(result[k]-reference[k]) for k in result) > 1e-10:
        raise ArithmeticError('BOUNDARY_CONTRACT_MISMATCH')
    return result


class NegativeBinomialLaw:
    kind = 'count'
    scale = 1
    parameterization = 'TORCH_NB_TOTAL_COUNT_PROBS;SCIPY_SUCCESS_PROB=1-PROBS'
    variance_type = 'INTEGER_LAW_VARIANCE'
    mean_type = 'INTEGER_LAW_EXPECTATION'

    def __init__(self, total_count, probs):
        self.r = _finite('total_count', total_count)
        self.p = _finite('probs', probs)
        if self.r <= 0 or not 0 < self.p < 1:
            raise ValueError('INVALID_NB_PARAMETERS')
        self.dist = nbinom(self.r, 1-self.p)

    def parameters(self):
        return dict(total_count=self.r, probs=self.p)

    def cdf(self, k):
        return float(self.dist.cdf(math.floor(k)))

    def sf(self, k):
        return float(self.dist.sf(math.floor(k)))

    def logpmf(self, k):
        k = _integer(k)
        return -math.inf if k is None or k < 0 else float(self.dist.logpmf(k))

    def pmf(self, k):
        return math.exp(self.logpmf(k))

    def mean(self):
        return self.r*self.p/(1-self.p)

    def variance(self):
        return self.r*self.p/(1-self.p)**2

    def quantile(self, p):
        if not 0 <= p <= 1:
            raise ValueError('INVALID_QUANTILE')
        if p == 0:
            return 0
        return float(self.dist.ppf(p))

    def probability(self, line):
        return _stable_probability(self, line)


class DiscretizedStudentTLaw:
    """P(Y=k)=T(k+.5)-T(k-.5), k any signed integer.

    Location is the *latent continuous* mean when df>1.  It is not silently
    reported as the discrete mean.  Fourier corrections calculate the integer
    law's moments to the declared truncation bound.  Mean is undefined for
    df<=1; variance is undefined for df<=2.  There is no observed-max clipping.
    """
    kind = 'signed'
    scale = 1
    parameterization = 'INTEGER_NEAREST_BIN_STUDENT_T_DF_LOC_SCALE'
    variance_type = 'INTEGER_BIN_LAW_VARIANCE;DEFINED_ONLY_DF_GT_2'
    mean_type = 'INTEGER_BIN_LAW_EXPECTATION;DEFINED_ONLY_DF_GT_1'

    def __init__(self, df, loc, scale):
        self.df, self.loc, self.sigma = (
            _finite('df', df), _finite('loc', loc), _finite('scale', scale))
        if self.df <= 0 or self.sigma <= 0:
            raise ValueError('INVALID_STUDENT_T_PARAMETERS')
        self.dist = t(self.df, loc=self.loc, scale=self.sigma)
        self._moment_cache = None

    def parameters(self):
        return dict(df=self.df, loc=self.loc, scale=self.sigma)

    def cdf(self, k):
        return float(self.dist.cdf(math.floor(k)+.5))

    def sf(self, k):
        return float(self.dist.sf(math.floor(k)+.5))

    def logpmf(self, k):
        k = _integer(k)
        if k is None:
            return -math.inf
        left, right = k-.5, k+.5
        if right <= self.loc:
            return _logdiff(self.dist.logcdf(right), self.dist.logcdf(left))
        if left >= self.loc:
            return _logdiff(self.dist.logsf(left), self.dist.logsf(right))
        return _logdiff(self.dist.logcdf(right), self.dist.logcdf(left))

    def pmf(self, k):
        return math.exp(self.logpmf(k))

    def latent_mean(self):
        return self.loc if self.df > 1 else None

    def latent_variance(self):
        return self.sigma**2*self.df/(self.df-2) if self.df > 2 else None

    def _moments(self):
        if self._moment_cache is not None:
            return self._moment_cache
        if self.df <= 1:
            self._moment_cache = dict(mean=None, variance=None, terms=0,
                                      error_bound=None)
            return self._moment_cache
        # Rounding-error Fourier series.  If psi(t) is the centered Student-t
        # characteristic function, E[round(X)-X] = sum (-1)^n sin(2pi*n*loc)
        # psi(2pi*n)/(pi*n).  K_h(z+d)<=exp(-d)*K_h(z) bounds the omitted series.
        h = self.df/2
        a = 2*math.pi*self.sigma*math.sqrt(self.df)
        bias = 0.
        error_second = 1/12
        covariance = 0.
        tail = math.inf
        for n in range(1, MAX_MOMENT_TERMS+1):
            z = a*n
            bessel = float(kve(h, z))
            if not math.isfinite(bessel) or bessel <= 0:
                raise ArithmeticError('MOMENT_BESSEL_NUMERICAL_LIMIT')
            lp = h*math.log(z)+math.log(bessel)-z-(h-1)*math.log(2)-float(gammaln(h))
            psi = math.exp(min(0., lp))
            angle = 2*math.pi*n*(self.loc % 1.)
            sign = -1. if n % 2 else 1.
            bias += sign*math.sin(angle)*psi/(math.pi*n)
            if self.df > 2:
                # psi'(t)=-sigma*sqrt(df)*psi(t)*K_(h-1)(z)/K_h(z).
                ratio = float(kve(h-1, z))/bessel
                derivative = -self.sigma*math.sqrt(self.df)*psi*ratio
                covariance += sign*math.cos(angle)*derivative/(math.pi*n)
                error_second += sign*math.cos(angle)*psi/(math.pi*n)**2
            if a > h/n:
                q = math.exp(-a+h/n)
                # Bound both the mean and variance series; variance covariance
                # term uses K_(h-1)/K_h<=1 for h>1.
                coefficient = 1/(math.pi*n)
                if self.df > 2:
                    coefficient = max(coefficient,
                        2*self.sigma*math.sqrt(self.df)/(math.pi*n)+1/(math.pi*n)**2)
                tail = psi*coefficient*q/(1-q) if q else 0.
                if tail <= MOMENT_TOLERANCE:
                    break
        else:
            raise ArithmeticError('MOMENT_SERIES_TOLERANCE_NOT_REACHED')
        variance = (self.latent_variance()+error_second-2*covariance-bias*bias
                    if self.df > 2 else None)
        if variance is not None and variance < -1e-9:
            raise ArithmeticError('NEGATIVE_INTEGER_VARIANCE')
        self._moment_cache = dict(mean=self.loc+bias,
            variance=max(0., variance) if variance is not None else None,
            terms=n, error_bound=float(tail),
            variance_error_bound=float(tail*(2+abs(bias)*2)) if variance is not None else None)
        return self._moment_cache

    def mean(self):
        return self._moments()['mean']

    def variance(self):
        return self._moments()['variance']

    def moment_receipt(self):
        return dict(self._moments(), tolerance=MOMENT_TOLERANCE,
                    max_terms=MAX_MOMENT_TERMS)

    def quantile(self, p):
        if not 0 <= p <= 1:
            raise ValueError('INVALID_QUANTILE')
        q = float(self.dist.ppf(p))
        if not math.isfinite(q):
            return q
        k = math.ceil(q-.5)
        # Resolve floating-point ppf boundary ties against the declared CDF.
        while self.cdf(k) < p:
            k += 1
        while self.cdf(k-1) >= p:
            k -= 1
        return k

    def probability(self, line):
        return _stable_probability(self, line)


def law_from_parameters(category: str, parameters: Mapping):
    if category == 'rec':
        return NegativeBinomialLaw(parameters['total_count'], parameters['probs'])
    if category == 'rec_yd':
        return DiscretizedStudentTLaw(parameters['df'], parameters['loc'], parameters['scale'])
    raise ValueError('M3_TARGET_NOT_REGISTERED')


def laws_from_parameter_rows(category: str, parameter_rows: Sequence[Mapping]):
    """Order-preserving wrapper; never joins rows by their position alone."""
    return [law_from_parameters(category, row) for row in parameter_rows]


def nb_nll(y, total_count, probs):
    return -NegativeBinomialLaw(total_count, probs).logpmf(y)


def student_t_continuous_nll(y, df, loc, scale):
    """Training-density reference, explicitly separate from integer-bin NLL."""
    return -float(t.logpdf(y, df, loc=loc, scale=scale))


def central_difference_gradient(function, parameter_values, relative_step=1e-5):
    """Natural-parameter finite differences for a later Torch-autograd check."""
    x = np.asarray(parameter_values, dtype=float)
    result = []
    for i, v in enumerate(x):
        h = relative_step*max(1., abs(v))
        plus, minus = x.copy(), x.copy()
        plus[i] += h
        minus[i] -= h
        result.append((function(*plus)-function(*minus))/(2*h))
    return np.asarray(result)


def deterministic_fixtures():
    checks = []
    nb = NegativeBinomialLaw(2.5, .6)
    sy = DiscretizedStudentTLaw(5., 12.25, 18.)
    for name, law, lo, hi in [('NB', nb, 0, 1000), ('STUDENT_T_BIN', sy, -10000, 10000)]:
        grid = np.arange(lo, hi+1)
        mass = np.asarray([law.pmf(k) for k in grid])
        cdf = np.asarray([law.cdf(k) for k in grid])
        total = law.cdf(lo-1)+float(mass.sum())+law.sf(hi)
        assert np.isfinite(mass).all() and np.all(mass >= 0)
        assert abs(total-1) < 1e-10
        assert np.isfinite(cdf).all() and np.all(np.diff(cdf) >= -1e-14)
        for line in [-1., -.5, 0., .5, 5., 5.5, 1000000.]:
            p = law.probability(line)
            assert abs(sum(p.values())-1) < 1e-10
            assert (p['push'] == 0) if Decimal(str(line)) % 1 else abs(p['push']-law.pmf(int(line))) < 1e-12
        for p in [.01, .5, .99]:
            k = law.quantile(p)
            assert law.cdf(k) >= p and law.cdf(k-1) < p
        checks.append(dict(law=name, mass_with_tails=total,
                           negative_mass=law.pmf(-1), zero_mass=law.pmf(0),
                           mean=law.mean(), variance=law.variance()))
    assert nb.pmf(-1) == 0 and nb.variance() > nb.mean()
    assert sy.pmf(-1) > 0 and sy.pmf(0) > 0
    assert DiscretizedStudentTLaw(.9, 0., 1.).mean() is None
    assert DiscretizedStudentTLaw(1.5, 0., 1.).variance() is None
    near = DiscretizedStudentTLaw(5., .25, .1)
    points = np.arange(-10000, 10001)
    weights = np.asarray([near.pmf(k) for k in points])
    assert abs(near.mean()-float(points@weights)) < 1e-8
    assert abs(near.variance()-float((points-near.mean())**2@weights)) < 1e-8
    batch = laws_from_parameter_rows('rec', [nb.parameters(), dict(total_count=3, probs=.25)])
    assert all(a.probability(3.5) == law_from_parameters('rec', p).probability(3.5)
               for a, p in zip(batch, [nb.parameters(), dict(total_count=3, probs=.25)]))
    gradients = dict(
        NB_natural=central_difference_gradient(lambda r,p: nb_nll(4,r,p), [2.5,.6]).tolist(),
        StudentT_continuous_natural=central_difference_gradient(
            lambda df,loc,scale: student_t_continuous_nll(18,df,loc,scale), [5.,12.25,18.]).tolist())
    assert all(math.isfinite(v) for a in gradients.values() for v in a)
    return dict(checks=checks, gradients=gradients,
                continuous_density_not_integer_mass=True,
                NB_underdispersion_supported=False,
                no_zero_inflation_or_test_max_clipping=True)
