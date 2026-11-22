"""Outcome-free saved C control join for the admitted SIM comparison.

This module does not fit, infer from a model, read outcomes, grade, simulate or
network.  The caller supplies the canonical cases and the already-admitted
identity mapping.  Mixed saved documents are projected onto an explicit
forecast/identity allowlist; their target statistics never enter this join.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import math
from pathlib import Path
from shared_game_sim01_inputs import canonical_team

FORECAST_KEYS = frozenset((
    'game_id', 'player_id', 'position', 'team', 'opponent', 'opponent_team',
    'season', 'week', 'category', 'target', 'arm', 'mean', 'median', 'law',
    'grid', 'p_over', 'p_push', 'fallback', 'learned', 'model_binding',
))


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _read_bound(root, binding):
    p = (root / binding['path']).resolve()
    if root.resolve() not in p.parents or p.is_symlink():
        raise ValueError('CONTROL_BINDING_PATH_ESCAPE')
    body = p.read_bytes()
    if len(body) != binding['bytes'] or hashlib.sha256(body).hexdigest() != binding['SHA256']:
        raise ValueError('CONTROL_SAVED_BODY_BINDING_MISMATCH:' + binding['path'])
    obj = json.loads(gzip.decompress(body) if p.suffix == '.gz' else body)
    if not isinstance(obj, list):
        raise ValueError('CONTROL_SAVED_BODY_MUST_BE_ROWS')
    # Do not retain source actuals, appearance, correctness or scores.
    return [{k: row[k] for k in FORECAST_KEYS if k in row} for row in obj]


def _identity(case, identity):
    c = case.get('identity', case)
    # The website canonical case has season/week/game/role but not GSIS.  Only
    # the externally admitted row mapping supplies canonical GSIS/native game.
    if not identity or not str(identity.get('status', '')).startswith('READY_'):
        return None, 'UNAVAILABLE_CANONICAL_IDENTITY'
    if int(identity['week']) != int(c['week']):
        raise ValueError('CONTROL_IDENTITY_WEEK_MISMATCH')
    return (int(c['season']), int(c['week']),
            identity['canonical_game_id'], identity['canonical_player_id']), None


def _allowed_role(entry, position):
    category = entry['category']
    if category.startswith('pass_'):
        return position == 'QB'
    if entry['procedure_id'].startswith('C-M3-') or '::PLAYER-CONTEXT-' in entry['procedure_id']:
        return position in ('WR', 'TE')
    if category in ('rec', 'rec_yd', 'rush_rec_yd'):
        return position in ('RB', 'WR', 'TE')
    if category in ('rush_yd', 'rush_att'):
        return position in ('QB', 'RB', 'WR', 'TE')
    return position in ('QB', 'RB', 'WR', 'TE')


def _side(point, line):
    return 'OVER' if point > line else 'UNDER' if point < line else 'ABSTAIN'


def _saved_law_probabilities(record, line):
    """Restore the exact primitive empirical/prior mixture, not a new fit."""
    from laws_v2 import Law, Prior
    if set(record) != {'values', 'weights', 'prior', 'scale', 'alpha'}:
        raise ValueError('UNKNOWN_SAVED_LAW_FIELDS')
    p = record['prior']
    if set(p) != {'kind', 'empty', 'mu', 'center', 'q', 'event'}:
        raise ValueError('UNKNOWN_SAVED_PRIOR_FIELDS')
    if p['kind'] not in ('count', 'signed', 'event'):
        raise ValueError('UNKNOWN_SAVED_PRIOR_KIND')
    prior = Prior.__new__(Prior)
    for k, v in p.items():
        setattr(prior, k, v)
    if not (0 < prior.q < 1) or not (0 <= record['alpha'] <= 1) or record['scale'] <= 0:
        raise ValueError('INVALID_SAVED_LAW_SUPPORT')
    if len(record['values']) != len(record['weights']) or any(
            not _finite(v) or v < 0 for v in record['weights']):
        raise ValueError('INVALID_SAVED_LAW_WEIGHTS')
    law = Law(record['values'], record['weights'], prior,
              scale=record['scale'], alpha=record['alpha'])
    return law.probability(line)


def _grid_probabilities(row, line):
    grid = row.get('grid', [])
    # Float equality is intentional: no line rounding, interpolation or nearest
    # saved threshold substitution is admitted by this adapter.
    indices = [i for i, value in enumerate(grid) if value == line]
    if len(indices) != 1:
        return None
    j = indices[0]
    over, push = row.get('p_over', []), row.get('p_push', [])
    if len(over) != len(grid) or len(push) != len(grid):
        return None
    o, p = over[j], push[j]
    if not _finite(o) or not _finite(p) or o < 0 or p < 0 or o+p > 1+1e-12:
        raise ValueError('INVALID_SAVED_THRESHOLD_PROBABILITIES')
    u = 1-o-p
    if u < 0:
        raise ValueError('NEGATIVE_SAVED_UNDER_MASS')
    return dict(under=u, push=p, over=o)


def build_controls(root, case_rows, identity_rows):
    """Join saved controls only; return exact product ID -> typed rows.

    All category cases remain represented under each nominated product, with
    absent origin/body/role/law support explicitly unavailable.  P1 models need
    separately authorized origin inference and are not loaded here.  The M3-0
    full empirical mixture supports arbitrary exact thresholds; old grid-only
    ALL12 packets support probabilities only at their literal stored thresholds.
    """
    root = Path(root).resolve()
    roster_path = root / 'reports/shared-game-sim-01/roster/C_SHORTLIST.json'
    roster = json.loads(roster_path.read_bytes())
    identity_map = identity_rows if isinstance(identity_rows, dict) else {
        row['case_id']: row for row in identity_rows}
    if len({r['case_id'] for r in case_rows}) != len(case_rows):
        raise ValueError('DUPLICATE_CANONICAL_CASE_ID')
    cache, outputs = {}, {}
    def saved(binding):
        key = (binding['path'], binding['SHA256'])
        if key not in cache:
            cache[key] = _read_bound(root, binding)
        return cache[key]
    for entry in roster['entries']:
        family = entry['procedure_id']
        rows, row_bindings = [], {}
        if entry.get('saved_output_body'):
            binding = entry['saved_output_body']
            mask = entry['saved_output_row_mask']
            rows = [r for r in saved(binding) if all(r.get(k) == v for k, v in mask.items())]
            row_bindings = {id(r): binding for r in rows}
        else:
            for binding in entry.get('saved_frames', []):
                rr = saved(binding); rows.extend(rr)
                row_bindings.update({id(r): binding for r in rr})
        index = {}
        for row in rows:
            key = (int(row['season']), int(row['week']), row['game_id'], row['player_id'])
            if key in index:
                raise ValueError('DUPLICATE_SAVED_CONTROL_IDENTITY:' + family)
            index[key] = row
        products = [('LAW', None)]
        if 'P2_LEAF' in family or family.startswith('C-M3-') or '::PLAYER-CONTEXT-' in family:
            products = [('MEAN_POINT', 'mean'), ('MEDIAN_POINT', 'median'), ('LAW', None)]
        for product, field in products:
            method = family + '::' + product
            result = []
            for case in case_rows:
                c = case.get('identity', case)
                if c['category'] != entry['category']:
                    continue
                identity = identity_map.get(case['case_id'])
                key, reason = _identity(case, identity)
                row = index.get(key) if key else None
                r = dict(case_id=case['case_id'], category=c['category'],
                         season=int(c['season']), week=int(c['week']),
                         game_id=identity.get('canonical_game_id') if identity else None,
                         player_id=identity.get('canonical_player_id') if identity else None,
                         method=method, procedure_id=family, product=product,
                         available=False, point=None, probabilities=None,
                         selected_side=None, fallback=None,
                         verification='SAVED_OUTPUT_JOIN_NOT_NEW_FIT_OR_ISSUANCE',
                         correctness_hold=entry.get('correctness_hold'))
                if reason is None and not _allowed_role(entry, c['position']):
                    reason = 'UNSUPPORTED_ROLE'
                if reason is None and row is None:
                    reason = ('SAVED_ORIGIN_INFERENCE_REQUIRED' if entry.get('saved_origin_models')
                              else 'NO_EXACT_SAVED_ORIGIN_PREDICTION')
                if reason is None and row.get('position') != c['position']:
                    reason = 'SAVED_ROLE_MISMATCH'
                if reason is None and canonical_team(row.get('team')) != canonical_team(c.get('team')):
                    reason = 'SAVED_TEAM_MISMATCH'
                if reason is None:
                    b = row_bindings[id(row)]
                    r['source_binding'] = dict(path=b['path'], SHA256=b['SHA256'])
                    r['fallback'] = row.get('fallback')
                    learned = row.get('learned')
                    r['native'] = (learned if isinstance(learned, bool) else
                                   (not r['fallback'] if isinstance(r['fallback'], bool) else None))
                    line = c['line']
                    if not _finite(line):
                        raise ValueError('INVALID_CANONICAL_LINE')
                    if field:
                        point = row.get(field)
                        if not _finite(point):
                            reason = 'SAVED_POINT_PRODUCT_UNAVAILABLE'
                        else:
                            r.update(point=point, selected_side=_side(point, line), available=True)
                    else:
                        p = (_saved_law_probabilities(row['law'], line) if row.get('law')
                             else _grid_probabilities(row, line))
                        if p is None:
                            reason = 'EXACT_ARBITRARY_LINE_LAW_UNAVAILABLE_GRID_ONLY'
                        else:
                            r.update(probabilities=p, selected_side=_side(p['over'], p['under']), available=True)
                r['unavailable_reason'] = reason
                result.append(r)
            outputs[method] = result
    return outputs
