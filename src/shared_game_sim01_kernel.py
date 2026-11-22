"""Prepared numeric kernel for C-SHARED-GAME-SP-BOX-v1; NOT a ready NFL worker.

No source/query/ZIP reader, parameter fitter, provider conditioner, canonical
grader, approved allocation controller, or forecast-time admission is provided
here.  Those are required upstream.  Importing this module never samples.
Only compilation was authorized for this implementation checkpoint: neither
NFL nor synthetic trajectories have been generated to qualify this code.

The count core is a shared-game box-score law, not clock/possession simulation.
Child gain/TD absence makes those fields unavailable; it never becomes a zero.
All indices/structural zeros below must arrive from the admitted primitive
parameter contract.  This kernel does not infer identities or participation.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import io
import json
import math
from pathlib import Path
import zipfile

import numpy as np
from scipy.stats import nbinom, norm, poisson

RECIPE_ID = "C-SHARED-GAME-SP-BOX-v1"
MASTER_SEED = 20261122
TRAJECTORIES = 10_000
EVENTS = ("pass_att", "sack", "scramble", "designed_rush", "kneel")
COUNT_FIELDS = ("pass_att", "pass_cmp", "pass_int", "sacks", "targets", "rec", "rush_att")
CHILD_FIELDS = ("pass_yd", "pass_td", "rec_yd", "rec_td", "rush_yd", "rush_td")


@dataclass(frozen=True)
class ExecutionPermit:
    """Technical caller assertions, not an authority-granting token/loader."""
    allocation_id: str
    input_fingerprint: str
    code_and_recipe_frozen: bool = False
    source_and_retention_ready: bool = False
    allocation_approved: bool = False

    def require(self) -> None:
        if not (self.allocation_id and self.input_fingerprint
                and self.code_and_recipe_frozen and self.source_and_retention_ready
                and self.allocation_approved):
            raise RuntimeError("NO_APPROVED_FROZEN_SOURCE_RUNTIME_RETENTION_PERMIT")


@dataclass(frozen=True)
class GainTupleLaw:
    """Earlier-qualified integer signed gain/TD tuples and frozen weights."""
    gains: np.ndarray
    touchdowns: np.ndarray
    weights: np.ndarray

    def checked(self, *, kneel: bool = False) -> "GainTupleLaw":
        g, td, w = map(np.asarray, (self.gains, self.touchdowns, self.weights))
        if g.ndim != 1 or not len(g) or td.shape != g.shape or w.shape != g.shape:
            raise ValueError("GAIN_TUPLE_SHAPE")
        if g.dtype.kind not in "iu" or td.dtype.kind not in "iu":
            raise ValueError("GAIN_TUPLES_REQUIRE_INTEGER_VALUES")
        if not np.all((td == 0) | (td == 1)):
            raise ValueError("TD_LABEL_NOT_BINARY")
        if not np.isfinite(w).all() or np.any(w < 0) or not np.isclose(w.sum(), 1., atol=1e-12, rtol=0):
            raise ValueError("GAIN_WEIGHTS_NOT_PROBABILITIES")
        if kneel and np.any(td):
            raise ValueError("KNEEL_TD_INCOMPATIBLE")
        return GainTupleLaw(g.astype(np.int64), td.astype(np.int64), w.astype(float))


@dataclass(frozen=True)
class TeamParameters:
    team_id: str
    actor_ids: tuple[str, ...]
    other_index: int
    qb_indices: tuple[int, ...]
    target_indices: tuple[int, ...]
    rusher_indices: tuple[int, ...]
    opportunity_mean: float
    event_alpha: np.ndarray                 # [attempt,sack,scramble,design,kneel]
    qb_alpha: np.ndarray                    # QB identities incl other
    target_alpha: np.ndarray                # [QB, target identity incl other + no-target]
    conversion_alpha: np.ndarray            # [QB, destination, completion/INT/incomplete]
    rusher_alpha: np.ndarray                # designed-run identities incl other
    catch_laws: tuple[tuple[GainTupleLaw | None, ...], ...] | None = None
    designed_laws: tuple[GainTupleLaw | None, ...] | None = None
    scramble_laws: tuple[GainTupleLaw | None, ...] | None = None
    kneel_laws: tuple[GainTupleLaw | None, ...] | None = None

    def __post_init__(self):
        object.__setattr__(self, 'actor_ids', tuple(self.actor_ids))
        for name in ('qb_indices', 'target_indices', 'rusher_indices'):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        for name in ('event_alpha', 'qb_alpha', 'target_alpha', 'conversion_alpha', 'rusher_alpha'):
            a = np.array(getattr(self, name), dtype=float, copy=True)
            a.setflags(write=False)
            object.__setattr__(self, name, a)


@dataclass
class GameSamples:
    arrays: dict[str, np.ndarray]
    metadata: dict
    conditional_means: dict[str, np.ndarray]
    conditional_variances: dict[str, np.ndarray]


def _alpha(a, shape=None) -> np.ndarray:
    a = np.asarray(a, dtype=float)
    if (shape is not None and a.shape != shape) or not np.isfinite(a).all() or np.any(a < 0):
        raise ValueError("INVALID_PRIMITIVE_ALPHA")
    if a.ndim != 1 or a.sum() <= 0:
        raise ValueError("EMPTY_DIRICHLET_SUPPORT")
    return a


def _dirichlet(rng, a, n) -> np.ndarray:
    """Explicit structural zero categories; never interpret missing as false."""
    a = _alpha(a)
    out = np.zeros((n, len(a)), dtype=float)
    present = np.flatnonzero(a > 0)
    if len(present) == 1:
        out[:, present[0]] = 1.
    else:
        out[:, present] = rng.dirichlet(a[present], size=n)
    return out


def _split(rng, total, probabilities) -> np.ndarray:
    """Vectorized multinomial via conditional binomials, with exact count sum."""
    total = np.asarray(total)
    p = np.asarray(probabilities, dtype=float)
    if total.dtype.kind not in "iu" or total.ndim != 1 or np.any(total < 0):
        raise ValueError("INVALID_COUNT_VECTOR")
    if p.ndim != 2 or p.shape[0] != len(total) or not np.isfinite(p).all() or np.any(p < 0):
        raise ValueError("INVALID_SPLIT_PROBABILITY")
    if not np.allclose(p.sum(axis=1), 1., atol=1e-12, rtol=0):
        raise ValueError("SPLIT_MASS_NOT_ONE")
    out = np.zeros(p.shape, dtype=np.int64)
    remaining = total.astype(np.int64).copy()
    for j in range(p.shape[1] - 1):
        denom = p[:, j:].sum(axis=1)
        fraction = np.divide(p[:, j], denom, out=np.zeros_like(denom), where=denom > 0)
        if np.any((denom == 0) & (remaining != 0)):
            raise ValueError("POSITIVE_COUNT_WITHOUT_REMAINING_SUPPORT")
        out[:, j] = rng.binomial(remaining, fraction)
        remaining -= out[:, j]
    out[:, -1] = remaining
    if not np.array_equal(out.sum(axis=1), total):
        raise ArithmeticError("MULTINOMIAL_CONSERVATION")
    return out


def _tuples(rng, counts, law: GainTupleLaw):
    """Expand only actual simulated event counts; retain signed tuple identity."""
    counts = np.asarray(counts, dtype=np.int64)
    law = law.checked()
    total = sum(map(int, counts))
    maxabs = max(abs(int(x)) for x in law.gains)
    if int(counts.max(initial=0)) * maxabs > np.iinfo(np.int64).max:
        raise OverflowError("SIGNED_GAIN_STORAGE_RANGE;NO_CLIPPING")
    if total > np.iinfo(np.intp).max:
        raise OverflowError("EVENT_EXPANSION_ADDRESS_RANGE;NO_CLIPPING")
    owners = np.repeat(np.arange(len(counts), dtype=np.int64), counts)
    draws = rng.choice(len(law.gains), size=total, p=law.weights)
    yards = np.zeros(len(counts), dtype=np.int64)
    td = np.zeros(len(counts), dtype=np.int64)
    np.add.at(yards, owners, law.gains[draws])
    np.add.at(td, owners, law.touchdowns[draws])
    return yards, td


def _team_check(t: TeamParameters) -> None:
    k, q, d, r = len(t.actor_ids), len(t.qb_indices), len(t.target_indices), len(t.rusher_indices)
    if not t.team_id or k == 0 or len(set(t.actor_ids)) != k or not 0 <= t.other_index < k:
        raise ValueError("ACTOR_IDENTITY_OR_OTHER_BUCKET")
    for indices in (t.qb_indices, t.target_indices, t.rusher_indices):
        if not indices or len(set(indices)) != len(indices) or t.other_index not in indices:
            raise ValueError("UNRESOLVED_MASS_MUST_HAVE_OTHER_ACTOR")
        if any(not 0 <= i < k for i in indices):
            raise ValueError("ACTOR_INDEX")
    if not math.isfinite(t.opportunity_mean) or t.opportunity_mean < 0:
        raise ValueError("INVALID_OPPORTUNITY_RATE")
    _alpha(t.event_alpha, (5,)); _alpha(t.qb_alpha, (q,)); _alpha(t.rusher_alpha, (r,))
    if np.asarray(t.target_alpha).shape != (q, d + 1) or np.asarray(t.conversion_alpha).shape != (q, d + 1, 3):
        raise ValueError("PASS_CHAIN_SHAPE")
    for qi in range(q):
        _alpha(t.target_alpha[qi], (d + 1,))
        for di in range(d + 1):
            _alpha(t.conversion_alpha[qi, di], (3,))
        if t.conversion_alpha[qi, -1, 0] != 0:
            raise ValueError("NO_TARGET_CANNOT_COMPLETE;UNKNOWN_RECEIVER_USES_OTHER")
    for laws, size in [(t.designed_laws, r), (t.scramble_laws, q), (t.kneel_laws, q)]:
        if laws is not None and len(laws) != size:
            raise ValueError("RUSH_GAIN_LAW_SHAPE")
    if t.catch_laws is not None and (len(t.catch_laws) != q or any(len(x) != d for x in t.catch_laws)):
        raise ValueError("CATCH_GAIN_LAW_SHAPE")


def _moment_add(means, variances, key, rate, law):
    law = law.checked()
    mu = float(law.weights @ law.gains.astype(float))
    second = float(law.weights @ np.square(law.gains.astype(float)))
    pt = float(law.weights @ law.touchdowns.astype(float))
    means[key + "_yd"] += rate * mu
    variances[key + "_yd"] += rate * second
    means[key + "_td"] += rate * pt
    variances[key + "_td"] += rate * pt


def _one_team(t, frailty, count_rng, gain_rng, n):
    _team_check(t)
    k = len(t.actor_ids)
    x = {f: np.zeros((n, k), dtype=np.int64) for f in COUNT_FIELDS}
    rates = {f: np.zeros((n, k), dtype=float) for f in COUNT_FIELDS}
    child = {f: np.zeros((n, k), dtype=np.int64) for f in CHILD_FIELDS}
    cm = {f: np.zeros((n, k), dtype=float) for f in CHILD_FIELDS}
    cv = {f: np.zeros((n, k), dtype=float) for f in CHILD_FIELDS}
    available = {f: np.ones(k, dtype=bool) for f in CHILD_FIELDS}
    opportunity_rate = frailty * t.opportunity_mean
    opportunities = count_rng.poisson(opportunity_rate)
    ep = _dirichlet(count_rng, t.event_alpha, n)
    events = _split(count_rng, opportunities, ep)
    qp = _dirichlet(count_rng, t.qb_alpha, n)
    passes = _split(count_rng, events[:, 0], qp)
    sacks = _split(count_rng, events[:, 1], qp)
    scrambles = _split(count_rng, events[:, 2], qp)
    kneels = _split(count_rng, events[:, 4], qp)
    rp = _dirichlet(count_rng, t.rusher_alpha, n)
    designed = _split(count_rng, events[:, 3], rp)
    edges = {}
    edge_rates = {}
    for qi, actor in enumerate(t.qb_indices):
        ar = opportunity_rate * ep[:, 0] * qp[:, qi]
        x['pass_att'][:, actor] += passes[:, qi]
        x['sacks'][:, actor] += sacks[:, qi]
        rates['pass_att'][:, actor] += ar
        rates['sacks'][:, actor] += opportunity_rate * ep[:, 1] * qp[:, qi]
        destp = _dirichlet(count_rng, t.target_alpha[qi], n)
        destinations = _split(count_rng, passes[:, qi], destp)
        for di in range(len(t.target_indices) + 1):
            convp = _dirichlet(count_rng, t.conversion_alpha[qi, di], n)
            counts = _split(count_rng, destinations[:, di], convp)
            cr, ir = ar * destp[:, di] * convp[:, 0], ar * destp[:, di] * convp[:, 1]
            x['pass_cmp'][:, actor] += counts[:, 0]
            x['pass_int'][:, actor] += counts[:, 1]
            rates['pass_cmp'][:, actor] += cr
            rates['pass_int'][:, actor] += ir
            edges[f'q{qi}_d{di}_targets'] = destinations[:, di]
            edges[f'q{qi}_d{di}_complete'] = counts[:, 0]
            edges[f'q{qi}_d{di}_interceptions'] = counts[:, 1]
            if di == len(t.target_indices):
                continue
            receiver = t.target_indices[di]
            x['targets'][:, receiver] += destinations[:, di]
            x['rec'][:, receiver] += counts[:, 0]
            rates['targets'][:, receiver] += ar * destp[:, di]
            rates['rec'][:, receiver] += cr
            edge_rates[(qi, di)] = cr
    for counts, probs, event, actors in [
            (designed, rp, 3, t.rusher_indices),
            (scrambles, qp, 2, t.qb_indices),
            (kneels, qp, 4, t.qb_indices)]:
        for j, actor in enumerate(actors):
            x['rush_att'][:, actor] += counts[:, j]
            rates['rush_att'][:, actor] += opportunity_rate * ep[:, event] * probs[:, j]
    # Per-edge child streams are stable when another child is unavailable.
    # Gain availability never changes count RNG consumption or existing edges.
    gain_stream_key = gain_rng.bytes(32)
    def child_rng(label):
        seed = int.from_bytes(hashlib.sha256(gain_stream_key+label.encode()).digest()[:16], 'big')
        return np.random.Generator(np.random.PCG64(seed))
    for qi, passer in enumerate(t.qb_indices):
        for di, receiver in enumerate(t.target_indices):
            supported = (t.event_alpha[0] > 0 and t.qb_alpha[qi] > 0
                         and t.target_alpha[qi, di] > 0 and t.conversion_alpha[qi, di, 0] > 0)
            law = t.catch_laws[qi][di] if t.catch_laws is not None else None
            if supported and law is None:
                for f, a in [('pass_yd', passer), ('pass_td', passer), ('rec_yd', receiver), ('rec_td', receiver)]:
                    available[f][a] = False
                continue
            if not supported:
                continue
            y, td = _tuples(child_rng(f'catch|{qi}|{di}'), edges[f'q{qi}_d{di}_complete'], law)
            child['pass_yd'][:, passer] += y; child['rec_yd'][:, receiver] += y
            child['pass_td'][:, passer] += td; child['rec_td'][:, receiver] += td
            rate = edge_rates[(qi, di)]
            for prefix, a in [('pass', passer), ('rec', receiver)]:
                local_m = {prefix+'_yd': cm[prefix+'_yd'][:, a], prefix+'_td': cm[prefix+'_td'][:, a]}
                local_v = {prefix+'_yd': cv[prefix+'_yd'][:, a], prefix+'_td': cv[prefix+'_td'][:, a]}
                _moment_add(local_m, local_v, prefix, rate, law)
    for counts, probs, event, actors, laws, kind in [
            (designed, rp, 3, t.rusher_indices, t.designed_laws, 'design'),
            (scrambles, qp, 2, t.qb_indices, t.scramble_laws, 'scramble'),
            (kneels, qp, 4, t.qb_indices, t.kneel_laws, 'kneel')]:
        for j, actor in enumerate(actors):
            supported = t.event_alpha[event] > 0 and ((t.rusher_alpha if event == 3 else t.qb_alpha)[j] > 0)
            law = laws[j] if laws is not None else None
            if supported and law is None:
                available['rush_yd'][actor] = available['rush_td'][actor] = False
                continue
            if not supported:
                continue
            law = law.checked(kneel=kind == 'kneel')
            y, td = _tuples(child_rng(f'rush|{kind}|{j}'), counts[:, j], law)
            child['rush_yd'][:, actor] += y; child['rush_td'][:, actor] += td
            rate = opportunity_rate * ep[:, event] * probs[:, j]
            _moment_add({'rush_yd': cm['rush_yd'][:, actor], 'rush_td': cm['rush_td'][:, actor]},
                        {'rush_yd': cv['rush_yd'][:, actor], 'rush_td': cv['rush_td'][:, actor]}, 'rush', rate, law)
    if np.any(x['pass_cmp'] + x['pass_int'] > x['pass_att']) or np.any(x['rec'] > x['targets']):
        raise ArithmeticError('PASS_TARGET_SUPPORT')
    if not np.array_equal(x['rec'].sum(axis=1), x['pass_cmp'].sum(axis=1)):
        raise ArithmeticError('COMPLETION_RECEPTION_CONSERVATION')
    if not np.array_equal(x['rush_att'].sum(axis=1), events[:, 2:].sum(axis=1)):
        raise ArithmeticError('RUSH_EVENT_CONSERVATION')
    if not np.array_equal(events.sum(axis=1), opportunities):
        raise ArithmeticError('OPPORTUNITY_CONSERVATION')
    if all(available['pass_td']) and all(available['rec_td']):
        if not np.array_equal(child['pass_td'].sum(axis=1), child['rec_td'].sum(axis=1)):
            raise ArithmeticError('PASS_RECEIVING_TD_CONSERVATION')
    return x, rates, child, cm, cv, available, events, opportunities, edges


def sample_game(game_id: str, origin: str, teams: tuple[TeamParameters, TeamParameters],
                frailty_shape: float | None, *, permit: ExecutionPermit | None = None) -> GameSamples:
    """Generate only after upstream allocation/freeze/source/retention admission.

    Always exactly10,000 trajectories; no optional draws or seeds to select.
    ``frailty_shape=None`` is the registered zero-mixing Poisson limit.
    """
    if permit is None:
        raise RuntimeError('NO_APPROVED_EXECUTION_PERMIT')
    permit.require()
    if len(teams) != 2 or teams[0].team_id == teams[1].team_id:
        raise ValueError('EXACTLY_TWO_DISTINCT_TEAMS')
    named = [set(t.actor_ids)-{t.actor_ids[t.other_index]} for t in teams]
    if named[0] & named[1]:
        raise ValueError('NAMED_ACTOR_ASSIGNED_TO_BOTH_TEAMS')
    if not game_id or not origin:
        raise ValueError('GAME_ORIGIN_REQUIRED')
    if frailty_shape is not None and (not math.isfinite(frailty_shape) or frailty_shape <= 0):
        raise ValueError('INVALID_SHARED_GAMMA_SHAPE')
    seed_text = f'{RECIPE_ID}|{game_id}|{origin}|{MASTER_SEED}'.encode()
    seed = int.from_bytes(hashlib.sha256(seed_text).digest()[:16], 'big')
    streams = np.random.SeedSequence(seed).spawn(5)
    rng = np.random.Generator(np.random.PCG64(streams[0]))
    frailty = np.ones(TRAJECTORIES) if frailty_shape is None else rng.gamma(frailty_shape, 1/frailty_shape, TRAJECTORIES)
    arrays = {'game_frailty': frailty}; means = {}; variances = {}; meta = {}
    for ti, team in enumerate(teams):
        crng = np.random.Generator(np.random.PCG64(streams[1 + ti*2]))
        grng = np.random.Generator(np.random.PCG64(streams[2 + ti*2]))
        x, rate, child, cm, cv, avail, events, opp, edges = _one_team(team, frailty, crng, grng, TRAJECTORIES)
        prefix = f'team{ti}/'
        arrays[prefix+'opportunities'] = opp; arrays[prefix+'events'] = events
        for key, value in edges.items():arrays[prefix+'assignments/'+key] = value
        for f in COUNT_FIELDS:
            arrays[prefix+f] = x[f]; means[prefix+f] = rate[f]; variances[prefix+f] = rate[f]
        for f in CHILD_FIELDS:
            # Store only qualified columns; manifest marks omissions unavailable.
            columns = np.flatnonzero(avail[f])
            arrays[prefix+f] = child[f][:, columns]
            means[prefix+f] = cm[f][:, columns]; variances[prefix+f] = cv[f][:, columns]
        both_y = np.flatnonzero(avail['rush_yd'] & avail['rec_yd'])
        arrays[prefix+'rush_rec_yd'] = (child['rush_yd']+child['rec_yd'])[:, both_y]
        means[prefix+'rush_rec_yd'] = (cm['rush_yd']+cm['rec_yd'])[:, both_y]
        variances[prefix+'rush_rec_yd'] = (cv['rush_yd']+cv['rec_yd'])[:, both_y]
        both_td = np.flatnonzero(avail['rush_td'] & avail['rec_td'])
        arrays[prefix+'anytime_td'] = ((child['rush_td']+child['rec_td'])[:, both_td] > 0)
        meta[prefix] = {'team_id':team.team_id,'actor_ids':team.actor_ids,'other_index':team.other_index,
                       'child_columns':{f:np.flatnonzero(avail[f]).tolist() for f in CHILD_FIELDS},
                       'rush_rec_yd_columns':both_y.tolist(),'anytime_td_columns':both_td.tolist(),
                       'unavailable_child_columns':{f:np.flatnonzero(~avail[f]).tolist() for f in CHILD_FIELDS}}
    metadata = dict(recipe=RECIPE_ID, game_id=game_id, origin=origin, trajectories=TRAJECTORIES,
                    seed_text_SHA256=hashlib.sha256(seed_text).hexdigest(), master_seed=MASTER_SEED,
                    input_fingerprint=permit.input_fingerprint, allocation_id=permit.allocation_id,
                    teams=meta, event_order=EVENTS, exact_chart_PPR='UNSUPPORTED_EVENT_CONTRACT',
                    participation='Conditional prop eligibility; role-zero is not DNP; no calibrated void law',
                    worker_scope='Numeric kernel only; source fitter/conditioner/admission/grader remain upstream')
    return GameSamples(arrays, metadata, means, variances)


def marginal_moments(conditional_mean, conditional_variance=None):
    m = np.asarray(conditional_mean, dtype=float)
    v = m if conditional_variance is None else np.asarray(conditional_variance, dtype=float)
    if m.ndim < 1 or m.shape[0] != TRAJECTORIES or m.shape != v.shape or not np.isfinite(m).all() or not np.isfinite(v).all() or np.any(v < 0):
        raise ValueError('INVALID_CONDITIONAL_MOMENTS')
    return np.mean(m, axis=0), np.mean(v, axis=0)+np.var(m, axis=0)


def direct_count_probabilities(mean: float, mixing_variance: float, line: float):
    """Valid same-information marginal NB/Poisson control; no point-gap sigmoid."""
    if not all(map(math.isfinite, (mean, mixing_variance, line))) or mean < 0 or mixing_variance < 0:
        raise ValueError('INVALID_COUNT_MOMENTS_OR_LINE')
    if mean == 0:
        return dict(under=float(0 < line),push=float(line == 0),over=float(0 > line))
    law = poisson(mean) if mixing_variance == 0 else nbinom(mean*mean/mixing_variance, mean/(mean+mixing_variance))
    integral = line == math.floor(line)
    under = float(law.cdf(math.ceil(line)-1))
    push = float(law.pmf(line)) if integral else 0.
    over = float(law.sf(math.floor(line)))
    return _probabilities(under, push, over)


def direct_signed_probabilities(location: float, variance: float, line: float):
    """Integer bins of Normal(location,variance); location is NOT exact mean."""
    if not all(map(math.isfinite, (location, variance, line))) or variance < 0:
        raise ValueError('INVALID_SIGNED_MOMENTS_OR_LINE')
    if variance == 0:
        value = math.floor(location+.5)
        return dict(under=float(value < line),push=float(value == line),over=float(value > line))
    law = norm(location, math.sqrt(variance))
    integral = line == math.floor(line)
    lower = math.ceil(line)-.5;upper = math.floor(line)+.5
    return _probabilities(float(law.cdf(lower)),float(law.cdf(upper)-law.cdf(lower)) if integral else 0.,float(law.sf(upper)))


def _probabilities(under, push, over):
    p = np.array([under,push,over])
    if not np.isfinite(p).all() or np.any(p < 0) or not np.isclose(p.sum(),1.,atol=1e-12,rtol=0):
        raise ArithmeticError('INVALID_MARGINAL_PROBABILITIES;NO_CLIP_REPAIR')
    return dict(under=under,push=push,over=over)


def write_numeric_samples(path: Path, result: GameSamples) -> str:
    """Explicit caller write; deterministic primitive numeric ZIP, no object data."""
    path = Path(path)
    if path.exists():raise FileExistsError('IMMUTABLE_FORECAST_PATH_ALREADY_EXISTS')
    path.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(path,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for name, a in sorted(result.arrays.items()):
            a = np.asarray(a)
            if a.dtype.kind not in 'biuf' or not np.isfinite(a).all():
                raise ValueError('NONFINITE_OR_NONPRIMITIVE_OUTPUT')
            b=io.BytesIO();np.lib.format.write_array(b,a,allow_pickle=False)
            info=zipfile.ZipInfo(name+'.npy',date_time=(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(info,b.getvalue())
        info=zipfile.ZipInfo('schema.json',date_time=(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
        z.writestr(info,(json.dumps(result.metadata,sort_keys=True,allow_nan=False)+'\n').encode())
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == '__main__':
    raise SystemExit('NOT_AN_ADMITTED_WORKER: source fitter/provider conditioner, allocation, freezes and retention readiness are required; no sampling performed')
