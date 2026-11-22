"""Earlier-only factual component estimation for C-SHARED-GAME-SP-BOX-v1.

This module does not execute on import. Public replay records contain estimated
parameters and hashes, never literal source plays, provider anchors or outcomes.
All inference must be called by the approved single-worker runtime controller.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import csv
import gzip
import hashlib
import io
import json
import lzma
from pathlib import Path
from zoneinfo import ZoneInfo
import zipfile

import numpy as np

from shared_game_sim01_kernel import GainTupleLaw, TeamParameters

EVENT_EXPOSURE = 20.0
GAIN_EXPOSURE = 100.0
ROLLING_GAMES = 8
LAG_SECONDS = 7 * 86400
PBP_PATHS = (
    'sources/player-context-matchup-01/completion-decision-v1/pbp_facts_2024.csv.xz',
    'sources/player-context-matchup-01/pbp_facts_2025.csv.gz',
    'sources/player-context-matchup-01/pbp_facts_2026.csv.gz',
)


def _utc(x):
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, datetime):
        if x.tzinfo is None:
            raise ValueError('NAIVE_ORIGIN')
        return x.timestamp()
    d = datetime.fromisoformat(str(x).replace('Z', '+00:00'))
    if d.tzinfo is None:
        raise ValueError('NAIVE_ORIGIN')
    return d.timestamp()


def _hash(x):
    return hashlib.sha256(json.dumps(x, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def _number(x):
    if x is None or str(x).strip().lower() in ('', 'nan', 'none', 'null'):
        return None
    try:
        y = float(x)
    except (ValueError, TypeError):
        return None
    return y if np.isfinite(y) else None


def _flag(x):
    y = _number(x)
    return int(y) if y in (0, 1) else None


def _integer(x):
    y = _number(x)
    return int(y) if y is not None and y == int(y) else None


@dataclass
class SourceStore:
    # Primitive plays are private in-memory source facts, not replay exports.
    team_games: dict
    schedules: dict
    positions: dict
    body_bindings: list
    classification: dict


@dataclass
class OriginPrior:
    cutoff: float
    games: tuple
    plays: tuple
    opportunity_mean: float
    opportunity_shape: float | None
    frailty_shape: float | None
    event_probabilities: np.ndarray
    design_SHA256: str


def load_sources(root: str | Path) -> SourceStore:
    """Reopen only the already-admitted bodies; no network or alternate source."""
    root = Path(root)
    manifest = json.loads((root / 'reports/shared-game-sim-01/readiness/COMPONENT_INPUT_MANIFEST.json').read_text())
    expected = {}
    for item in manifest['pbp'] + manifest['ordinary']:
        expected[item['path']] = item
    for key in ('schedule', 'qualified_team_cache'):
        item = manifest[key]; expected[item['path']] = item
    used = []

    def read(path):
        b = (root / path).read_bytes(); e = expected[path]
        if len(b) != e['bytes'] or hashlib.sha256(b).hexdigest() != e['SHA256']:
            raise ValueError('SOURCE_BODY_LENGTH_OR_HASH:' + path)
        used.append(dict(path=path, bytes=len(b), SHA256=e['SHA256']))
        return b

    schedules, positions = {}, {}
    with zipfile.ZipFile(io.BytesIO(read('artifacts/basic-football-facts-v2.1.zip'))) as z:
        for r in csv.DictReader(io.StringIO(z.read('schedule.csv').decode())):
            if r['game_type'] == 'REG':
                d = datetime.fromisoformat(r['gameday']+'T'+r['gametime']).replace(tzinfo=ZoneInfo('America/New_York'))
                schedules[r['game_id']] = dict(kickoff=d.timestamp(), season=int(r['season']), week=int(r['week']),
                                                home=r['home_team'], away=r['away_team'])
        facts = gzip.decompress(z.read('facts.csv.gz')).decode()
        for r in csv.DictReader(io.StringIO(facts)):
            if int(r['season']) in (2024, 2025) and r.get('player_id') and r.get('position'):
                positions[r['player_id']] = r['position']
    for r in csv.DictReader(io.StringIO(read('sources/category-decision-release-01/schedule.csv').decode())):
        if r['game_type'] == 'REG':
            d = datetime.fromisoformat(r['gameday']+'T'+r['gametime']).replace(tzinfo=ZoneInfo('America/New_York'))
            schedules[r['game_id']] = dict(kickoff=d.timestamp(), season=int(r['season']), week=int(r['week']),
                                            home=r['home_team'], away=r['away_team'])
    cache = json.loads(gzip.decompress(read('reports/information-skill-01/execution-authorization-02/pilot/SOURCE_AGGREGATES.json.gz')))
    qualification = {(r['game_id'], r['team']): bool(r['qualified']) for r in cache['teams']}
    cache_clock = {(r['game_id'], r['team']): float(r['kickoff']) for r in cache['teams']}
    games = defaultdict(lambda: dict(plays=[], counts=np.zeros(5, dtype=np.int64), held=[]))
    audit = Counter(); seen = set()
    for path in PBP_PATHS:
        b = read(path); raw = lzma.decompress(b) if path.endswith('.xz') else gzip.decompress(b)
        for r in csv.DictReader(io.StringIO(raw.decode())):
            if r.get('season_type') != 'REG':
                continue
            pair = (r['game_id'], r['play_id'])
            if pair in seen:
                raise ValueError('DUPLICATE_NATIVE_GAME_PLAY')
            seen.add(pair)
            key = (r['game_id'], r['posteam'])
            if key[0] not in schedules:
                raise ValueError('SOURCE_NATIVE_KICKOFF_MISSING')
            g = games[key]
            two, deleted = _flag(r.get('two_point_attempt')), _flag(r.get('play_deleted'))
            if two is None or deleted is None:
                g['held'].append('UNKNOWN_EXCLUSION'); continue
            if two or deleted:
                audit['legitimate_two_point_or_deleted_exclusions'] += 1; continue
            a, rush, sack = (_flag(r.get(k)) for k in ('pass_attempt', 'rush_attempt', 'sack'))
            scramble, kneel = (_flag(r.get(k)) for k in ('qb_scramble', 'qb_kneel'))
            if any(x is None for x in (a, rush, sack, scramble, kneel)):
                g['held'].append('UNKNOWN_EVENT_FLAGS'); continue
            event = None
            if sack == 1 and rush == 0 and scramble == 0 and kneel == 0:
                event = 1
            elif a == 1 and sack == 0 and rush == 0 and scramble == 0 and kneel == 0:
                event = 0
            elif rush == 1 and sack == 0 and not (scramble and kneel):
                event = 4 if kneel else (2 if scramble else 3)
            elif a or rush or sack or scramble or kneel:
                g['held'].append('CONTRADICTORY_EVENT_FLAGS'); continue
            if event is None:

                if _flag(r.get('complete_pass')) == 1 or _flag(r.get('interception')) == 1:
                    g['held'].append('CONVERSION_WITHOUT_ATTEMPT')
                audit['non_opportunity_rows'] += 1; continue
            complete, intercepted, incomplete = (_flag(r.get(k)) for k in ('complete_pass', 'interception', 'incomplete_pass'))
            if event == 0 and (None in (complete, intercepted, incomplete) or complete+intercepted+incomplete != 1):
                g['held'].append('UNKNOWN_OR_CONTRADICTORY_CONVERSION'); continue
            outcome = 0 if complete else (1 if intercepted else 2)
            receiver, passer, rusher = (r.get(k) or None for k in ('receiver_player_id', 'passer_player_id', 'rusher_player_id'))
            gain = td = None
            if event == 0 and complete:
                py, ry = _integer(r.get('passing_yards')), _integer(r.get('receiving_yards'))
                td = _flag(r.get('pass_touchdown'))
                if py is not None and py == ry and td is not None:
                    gain = py
                else:
                    audit['unknown_or_incompatible_catch_gain_TD_tuple'] += 1
            elif event in (2, 3, 4):
                gain, td = _integer(r.get('rushing_yards')), _flag(r.get('rush_touchdown'))
                if gain is None or td is None or (event == 4 and td != 0):
                    gain = td = None; audit['unknown_or_incompatible_rush_gain_TD_tuple'] += 1
            p = dict(game=key[0], team=key[1], event=event, passer=passer, receiver=receiver,
                     rusher=rusher, outcome=outcome, gain=gain, td=td)
            g['plays'].append(p); g['counts'][event] += 1
    final = {}
    for key, g in games.items():
        s = schedules[key[0]]
        if key[1] not in (s['home'], s['away']):
            raise ValueError('OFFENSE_NOT_SCHEDULED')
        if key not in qualification or not qualification[key]:
            g['held'].append('EXISTING_ALL_POSITION_INTERFACE_UNQUALIFIED')
        if key in cache_clock and cache_clock[key] != s['kickoff']:
            g['held'].append('NATIVE_CACHE_SCHEDULE_CLOCK_MISMATCH')
        g.update(game_id=key[0], team=key[1], kickoff=s['kickoff'], available=s['kickoff']+LAG_SECONDS,
                 season=s['season'], week=s['week'], qualified=not g['held'])
        final[key] = g
    audit['qualified_team_games'] = sum(g['qualified'] for g in final.values())
    audit['held_team_games'] = len(final)-audit['qualified_team_games']
    return SourceStore(final, schedules, positions, used, dict(audit))


def _eligible(store, cutoff, team=None, seasons=None):
    return sorted((g for g in store.team_games.values()
                   if g['qualified'] and g['available'] < cutoff and (team is None or g['team'] == team)
                   and (seasons is None or g['season'] in seasons)), key=lambda g: (g['kickoff'], g['game_id'], g['team']))


def fit_origin(store: SourceStore, origin_cutoff) -> OriginPrior:
    """Fitted startup prior uses qualified 2024/25 labels strictly before origin."""
    cutoff = _utc(origin_cutoff)
    games = _eligible(store, cutoff, seasons=(2024, 2025))
    if not games:
        raise ValueError('NO_EARLIER_2024_2025_STARTUP')
    totals = np.array([g['counts'].sum() for g in games], dtype=float)
    mu, var = float(totals.mean()), float(totals.var())
    if mu <= 0:
        raise ValueError('EMPTY_EARLIER_OPPORTUNITY_LAW')
    between = max(0., var-mu)
    opportunity_shape = mu*mu/between if between > 0 else None
    pairs = defaultdict(list)
    for g in games:
        pairs[g['game_id']].append((g['team'], float(g['counts'].sum())))
    paired = [sorted(v) for v in pairs.values() if len(v) == 2]
    frailty_shape = None
    if len(paired) >= 2:
        a = np.array([v[0][1] for v in paired]); b = np.array([v[1][1] for v in paired])
        mixing = float(np.mean(a*b)/(a.mean()*b.mean())-1)
        if mixing > 0:
            frailty_shape = 1/mixing
    ec = np.sum([g['counts'] for g in games], axis=0).astype(float)
    plays = tuple(p for g in games for p in g['plays'])
    consumed = [dict(game=g['game_id'], team=g['team'], kickoff=g['kickoff'], available=g['available'],
                     counts=g['counts'].tolist(), plays=g['plays']) for g in games]
    return OriginPrior(cutoff, tuple(games), plays, mu, opportunity_shape, frailty_shape,
                       ec/ec.sum(), _hash(consumed))


def _norm(weights):
    x = np.asarray(weights, dtype=float)
    if not np.isfinite(x).all() or np.any(x < 0) or x.sum() <= 0:
        raise ValueError('NO_QUALIFIED_ALLOCATION_PRIOR')
    return x/x.sum()


def _conversion(plays, fallback):
    c = np.zeros(3, dtype=float)
    for p in plays:
        if p['event'] == 0:
            c[p['outcome']] += 1
    return _norm(c+EVENT_EXPOSURE*np.asarray(fallback))


def _law(recent, prior):
    # Exclude unknown tuples without replacing them by zero. Caller reports their
    # denominator; sampling is conditional on the qualified tuple distribution.
    a = Counter((p['gain'], p['td']) for p in recent if p['gain'] is not None and p['td'] is not None)
    b = Counter((p['gain'], p['td']) for p in prior if p['gain'] is not None and p['td'] is not None)
    if not b and not a:
        return None
    if b:
        den = sum(b.values())
        for key, value in b.items():
            a[key] += GAIN_EXPOSURE*value/den
    keys = sorted(a)
    w = np.array([a[k] for k in keys], dtype=float); w /= w.sum()
    return GainTupleLaw(np.array([k[0] for k in keys], dtype=np.int64),
                        np.array([k[1] for k in keys], dtype=np.int64), w)


def build_team_prior(store: SourceStore, prior: OriginPrior, team_id: str, game_cutoff, actors: list[dict]):
    """Return a coherent primitive team prior plus aggregate design/replay data.

    ``actors`` contains only canonical admitted {gsis_id,position}; no provider
    values, offered thresholds, target outcomes or current injury/status fields.
    """
    cutoff = _utc(game_cutoff)
    if prior.cutoff > cutoff:
        raise ValueError('WEEKLY_PRIOR_AFTER_GAME_QUERY')
    role = {}
    for a in actors:
        aid, pos = str(a['gsis_id']), str(a['position'])
        if aid in role and role[aid] != pos:
            raise ValueError('CONFLICTING_QUERY_ACTOR_ROLE')
        role[aid] = pos
    actor_ids = tuple(sorted(role)) + ('__OTHER__::'+team_id,)
    other = len(actor_ids)-1; index = {a:i for i,a in enumerate(actor_ids)}
    qidx = tuple(i for i,a in enumerate(actor_ids[:-1]) if role[a] == 'QB') + (other,)
    tidx = tuple(range(len(actor_ids))); ridx = tidx
    def project(a):return index.get(a, other)
    recent_games = _eligible(store, cutoff, team_id)[-ROLLING_GAMES:]
    if not recent_games:
        raise ValueError('NO_EARLIER_TEAM_USAGE')
    recent = [p for g in recent_games for p in g['plays']]
    team_pool = [p for p in prior.plays if p['team'] == team_id]
    pool = team_pool or list(prior.plays)
    n = len(recent_games); total = sum(int(g['counts'].sum()) for g in recent_games)
    if prior.opportunity_shape is None:
        lam = prior.opportunity_mean
    else:
        lam = (prior.opportunity_shape+total)/(prior.opportunity_shape/prior.opportunity_mean+n)
    ec = np.sum([g['counts'] for g in recent_games], axis=0).astype(float)
    event_alpha = ec+EVENT_EXPOSURE*prior.event_probabilities
    # Historical own-role and team-unassigned rates supply cold-start support;
    # zero observed workload is not inferred current inactivity.
    per_game = defaultdict(Counter)
    for p in prior.plays:
        key = 'pass' if p['event'] == 0 else None
        if key:per_game[(p['game'],p['passer'])]['pass'] += 1
        if p['event'] == 0 and p['receiver']:
            per_game[(p['game'],p['receiver'])]['target'] += 1
        if p['event'] == 3:per_game[(p['game'],p['rusher'])]['design'] += 1
    by_actor = defaultdict(lambda: defaultdict(list)); by_role = defaultdict(lambda: defaultdict(list))
    for (_,a), c in per_game.items():
        for kind,val in c.items():
            by_actor[a][kind].append(val)
            by_role[store.positions.get(a,'UNKNOWN')][kind].append(val)
    def role_weight(a,kind):
        values = by_actor[a].get(kind) or by_role[role[a]].get(kind) or by_role['UNKNOWN'].get(kind)
        if not values:
            values = [v for kinds in by_role.values() for v in kinds.get(kind,[])]
        return float(np.mean(values)) if values else 0.
    pool_ngames = len({p['game'] for p in pool})
    def prior_allocation(indices,kind):
        weights=[]
        for a in indices:
            if a == other:
                c = sum(1 for p in pool if ((kind=='pass' and p['event']==0 and project(p['passer'])==other)
                              or (kind=='target' and p['event']==0 and project(p['receiver'])==other)
                              or (kind=='design' and p['event']==3 and project(p['rusher'])==other)))
                weights.append(c/max(1,pool_ngames))
            else:weights.append(role_weight(actor_ids[a],kind))
        return _norm(weights)
    qa, ra = np.zeros(len(qidx)), np.zeros(len(ridx))
    qi, ri = {a:i for i,a in enumerate(qidx)}, {a:i for i,a in enumerate(ridx)}
    for p in recent:
        if p['event'] == 0:qa[qi.get(project(p['passer']),len(qidx)-1)] += 1
        if p['event'] == 3:ra[ri[project(p['rusher'])]] += 1
    qa += EVENT_EXPOSURE*prior_allocation(qidx,'pass')
    ra += EVENT_EXPOSURE*prior_allocation(ridx,'design')
    dest_prior = prior_allocation(tidx,'target')
    target_alpha = np.zeros((len(qidx),len(tidx)+1))
    conv_alpha = np.zeros((len(qidx),len(tidx)+1,3))
    league_conv = _norm(np.bincount([p['outcome'] for p in prior.plays if p['event'] == 0], minlength=3))
    team_conv = _conversion(pool,league_conv)
    catch_laws=[]
    for j,qactor in enumerate(qidx):
        pr_q=[p for p in pool if p['event']==0 and project(p['passer'])==qactor]
        re_q=[p for p in recent if p['event']==0 and (project(p['passer']) if project(p['passer']) in qi else other)==qactor]
        q_conv = _conversion(pr_q,team_conv)
        target_alpha[j,:-1] = EVENT_EXPOSURE*dest_prior
        for p in re_q:target_alpha[j,project(p['receiver'])] += 1
        laws=[]
        for d,receiver in enumerate(tidx):
            pr_d=[p for p in pr_q if project(p['receiver'])==receiver]
            re_d=[p for p in re_q if project(p['receiver'])==receiver]
            cp = _conversion(pr_d,q_conv)
            cnt=np.bincount([p['outcome'] for p in re_d],minlength=3)
            conv_alpha[j,d] = cnt+EVENT_EXPOSURE*cp
            rr=[p for p in re_d if p['outcome']==0]
            pp=[p for p in pr_d if p['outcome']==0]
            if not pp:
                pp=[p for p in pool if p['event']==0 and p['outcome']==0 and (receiver==other or store.positions.get(p['receiver'])==role[actor_ids[receiver]])]
            if not pp:pp=[p for p in prior.plays if p['event']==0 and p['outcome']==0]
            laws.append(_law(rr,pp))
        # Receiver-ID absence is unknown destination, not proven throwaway.
        # Thus no-target has zero destination mass and explicit impossible C.
        conv_alpha[j,-1]=[0,0,EVENT_EXPOSURE]
        catch_laws.append(tuple(laws))
    rush_laws={}
    for kind,event,indices in [('design',3,ridx),('scramble',2,qidx),('kneel',4,qidx)]:
        laws=[]
        for a in indices:
            rr=[p for p in recent if p['event']==event and project(p['rusher'])==a]
            pp=[p for p in pool if p['event']==event and project(p['rusher'])==a]
            if not pp:
                pp=[p for p in prior.plays if p['event']==event and (a==other or store.positions.get(p['rusher'])==role[actor_ids[a]])]
            if not pp:pp=[p for p in prior.plays if p['event']==event]
            laws.append(_law(rr,pp))
        rush_laws[kind]=tuple(laws)
    t=TeamParameters(team_id,actor_ids,other,qidx,tidx,ridx,float(lam),event_alpha,qa,target_alpha,conv_alpha,ra,
                     tuple(catch_laws),rush_laws['design'],rush_laws['scramble'],rush_laws['kneel'])
    # Prior process variance is learned from source-complete earlier team-game
    # native assignments. An absent event ID contributes to Other, not a DNP.
    variances={a:{} for a in actor_ids}
    stat_fields=('pass_att','pass_cmp','pass_int','rush_att','rec','pass_yd','pass_td','rush_yd','rec_yd')
    series={a:{f:[] for f in stat_fields} for a in actor_ids}
    for g in recent_games:
        v={a:Counter() for a in actor_ids}; unknown=set()
        for p in g['plays']:
            pa=actor_ids[project(p['passer'])]; re=actor_ids[project(p['receiver'])]; ru=actor_ids[project(p['rusher'])]
            if p['event']==0:
                v[pa]['pass_att']+=1;v[pa]['pass_cmp']+=int(p['outcome']==0);v[pa]['pass_int']+=int(p['outcome']==1)
                if p['outcome']==0:
                    v[re]['rec']+=1
                    if p['gain'] is None:unknown.update([(pa,'pass_yd'),(pa,'pass_td'),(re,'rec_yd')])
                    else:v[pa]['pass_yd']+=p['gain'];v[re]['rec_yd']+=p['gain'];v[pa]['pass_td']+=p['td']
            elif p['event'] in (2,3,4):
                v[ru]['rush_att']+=1
                if p['gain'] is None:unknown.add((ru,'rush_yd'))
                else:v[ru]['rush_yd']+=p['gain']
        for a in actor_ids:
            for f in stat_fields:
                if (a,f) not in unknown:series[a][f].append(v[a][f])
    for a in actor_ids:
        for f,values in series[a].items():
            value=float(np.var(values)) if len(values)>1 else 0.
            variances[a][f]=value if value>0 else 1.
    consumed=dict(prior=prior.design_SHA256,cutoff=cutoff,team=team_id,actors=[dict(gsis_id=a,position=role[a]) for a in actor_ids[:-1]],
                  games=[dict(game_id=g['game_id'],kickoff=g['kickoff'],available=g['available'],plays=g['plays']) for g in recent_games])
    metadata=dict(team=team_id,actor_ids=list(actor_ids),other_index=other,origin_cutoff=prior.cutoff,game_cutoff=cutoff,
                  recent_games=[g['game_id'] for g in recent_games],latest_prior_kickoff=max(g['kickoff'] for g in recent_games),
                  latest_prior_available=max(g['available'] for g in recent_games),prior_design_SHA256=prior.design_SHA256,
                  consumed_design_SHA256=_hash(consumed),process_variances=variances,source_state='CURRENT_VINTAGE_7DAY_RECONSTRUCTION',
                  participation='Usage-based pool; not authenticated roster/status; zero usage is not DNP',
                  no_target='No qualified throwaway field: unknown receiver IDs retain Other; no-target structural mass0',
                  tuple_unknowns=sum(p['gain'] is None for p in recent if (p['event']==0 and p['outcome']==0) or p['event'] in (2,3,4)),
                  tuple_eligible=sum(1 for p in recent if (p['event']==0 and p['outcome']==0) or p['event'] in (2,3,4)))
    return t,metadata


def prior_to_record(p: OriginPrior):
    return dict(cutoff=p.cutoff,opportunity_mean=p.opportunity_mean,opportunity_shape=p.opportunity_shape,
                frailty_shape=p.frailty_shape,event_probabilities=p.event_probabilities.tolist(),design_SHA256=p.design_SHA256,
                earlier_team_game_count=len(p.games),earlier_play_count=len(p.plays))


def restore_origin(store: SourceStore, record: dict) -> OriginPrior:
    """Reopen exact eligible source context and reuse frozen prior parameters.

    No estimation is repeated: the retained primitive values are bound by the
    caller's immutable replay record, while this verifies the consumed input
    identity, order, clocks, denominators and full earlier source design.
    """
    cutoff = _utc(record['cutoff'])
    games = _eligible(store, cutoff, seasons=(2024, 2025))
    plays = tuple(p for g in games for p in g['plays'])
    consumed = [dict(game=g['game_id'], team=g['team'], kickoff=g['kickoff'], available=g['available'],
                     counts=g['counts'].tolist(), plays=g['plays']) for g in games]
    design_hash = _hash(consumed)
    if design_hash != record['design_SHA256']:
        raise ValueError('RESTORED_PRIOR_CONSUMED_DESIGN_MISMATCH')
    if len(games) != record['earlier_team_game_count'] or len(plays) != record['earlier_play_count']:
        raise ValueError('RESTORED_PRIOR_DENOMINATOR_MISMATCH')
    mean = float(record['opportunity_mean'])
    opportunity_shape = record['opportunity_shape']
    frailty_shape = record['frailty_shape']
    probabilities = np.asarray(record['event_probabilities'], dtype=float)
    if not np.isfinite(mean) or mean <= 0:
        raise ValueError('RESTORED_PRIOR_OPPORTUNITY_SUPPORT')
    for shape in (opportunity_shape, frailty_shape):
        if shape is not None and (not np.isfinite(shape) or shape <= 0):
            raise ValueError('RESTORED_PRIOR_SHAPE_SUPPORT')
    if (probabilities.shape != (5,) or not np.isfinite(probabilities).all()
            or np.any(probabilities < 0) or not np.isclose(probabilities.sum(), 1., atol=1e-12, rtol=0)):
        raise ValueError('RESTORED_PRIOR_EVENT_SUPPORT')
    return OriginPrior(cutoff, tuple(games), plays, mean, opportunity_shape, frailty_shape,
                       probabilities, design_hash)


def team_to_record(t: TeamParameters):
    def law(x):
        return None if x is None else dict(gains=x.gains.tolist(),touchdowns=x.touchdowns.tolist(),weights=x.weights.tolist())
    return dict(team_id=t.team_id,actor_ids=list(t.actor_ids),other_index=t.other_index,qb_indices=list(t.qb_indices),
                target_indices=list(t.target_indices),rusher_indices=list(t.rusher_indices),opportunity_mean=t.opportunity_mean,
                event_alpha=t.event_alpha.tolist(),qb_alpha=t.qb_alpha.tolist(),target_alpha=t.target_alpha.tolist(),
                conversion_alpha=t.conversion_alpha.tolist(),rusher_alpha=t.rusher_alpha.tolist(),
                catch_laws=[[law(x) for x in row] for row in t.catch_laws] if t.catch_laws is not None else None,
                designed_laws=[law(x) for x in t.designed_laws] if t.designed_laws is not None else None,
                scramble_laws=[law(x) for x in t.scramble_laws] if t.scramble_laws is not None else None,
                kneel_laws=[law(x) for x in t.kneel_laws] if t.kneel_laws is not None else None)


def team_from_record(r):
    def law(x):
        return None if x is None else GainTupleLaw(np.array(x['gains'],dtype=np.int64),np.array(x['touchdowns'],dtype=np.int64),np.array(x['weights'],dtype=float))
    return TeamParameters(r['team_id'],tuple(r['actor_ids']),r['other_index'],tuple(r['qb_indices']),tuple(r['target_indices']),
                          tuple(r['rusher_indices']),r['opportunity_mean'],np.array(r['event_alpha']),np.array(r['qb_alpha']),
                          np.array(r['target_alpha']),np.array(r['conversion_alpha']),np.array(r['rusher_alpha']),
                          tuple(tuple(law(x) for x in row) for row in r['catch_laws']) if r.get('catch_laws') is not None else None,
                          tuple(law(x) for x in r['designed_laws']) if r.get('designed_laws') is not None else None,
                          tuple(law(x) for x in r['scramble_laws']) if r.get('scramble_laws') is not None else None,
                          tuple(law(x) for x in r['kneel_laws']) if r.get('kneel_laws') is not None else None)


if __name__ == '__main__':
    raise SystemExit('Library only: approved frozen single-worker controller required; no standalone fitting performed')
