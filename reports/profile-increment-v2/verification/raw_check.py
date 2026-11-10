"""Independent no-fit checks of new C03 counters/cohorts, using retained bytes."""
import collections, hashlib, json, lzma, math, resource, signal, sys, time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'src'))
import numpy as np
import pandas as pd
from data_v2 import load, DAY
from context_sources_c01 import pbp_path
from receiving_defense_c03 import ReceivingDefense

START = time.process_time()
signal.signal(signal.SIGPROF, lambda *_: (_ for _ in ()).throw(RuntimeError('120CPUcap')))
signal.setitimer(signal.ITIMER_PROF, 120)
OUT = ROOT / 'reports/profile-increment-v2/verification'
inp = Path('/workspace/c-v2/corrected-inputs')
late = ROOT / 'prospective/runs/C-FWD-v4-20261105-W09-JAXBAL-remainder/sources'
d, g, _ = load(inp)
dd, gg, _ = load(late)
d = pd.concat([d, dd[(dd.season == 2026) & (dd.week == 8)]], ignore_index=True)
g = pd.concat([g[~((g.season == 2026) & (g.week == 8))], gg[(gg.season == 2026) & (gg.week == 8)]], ignore_index=True)
pool = d[d.position.isin(['RB', 'WR', 'TE'])]
facts = {(r['game_id'], r['player_id']): r for r in d.to_dict('records')}
schedule = {r['game_id']: r for r in g.to_dict('records')}
cols = ['game_id', 'team', 'season', 'week', 'attempts', 'completions', 'targets']
raw = pd.read_csv(inp / 'facts.csv.gz', usecols=cols)
rawlate = pd.read_csv(late / 'facts.csv.gz', usecols=cols)
raw = pd.concat([raw, rawlate[(rawlate.season == 2026) & (rawlate.week == 8)]])
official = {}
for key, f in raw.groupby(['game_id', 'team'], sort=False):
    a = f[['attempts', 'completions', 'targets']].to_numpy(float)
    official[key] = (a.sum(axis=0), bool(np.isfinite(a).all() and (a >= 0).all() and (a == np.floor(a)).all()))
files = [ROOT / 'sources/player-context-matchup-01/completion-decision-v1/pbp_facts_2024.csv.xz'] + [pbp_path(y) for y in [2025, 2026]]
frames = [pd.read_csv(p, low_memory=False) for p in files]
pbp = pd.concat(frames, ignore_index=True)
valid = pbp[(pbp.pass_attempt == 1) & (pbp.sack != 1) & (pbp.two_point_attempt != 1) & (pbp.play_deleted != 1) & (pbp.play_type != 'no_play')]
quality, expected, target_rows = [], {}, []
roles = ['WR', 'TE', 'RB', 'OTHER_OR_UNKNOWN']
depths = ['behind_LOS', '0_9', '10_19', '20plus', 'UNKNOWN']

def finite(v):
    return v is not None and math.isfinite(float(v))

for (game, offense), f in valid.groupby(['game_id', 'posteam'], sort=False):
    counts, good = official.get((game, offense), (None, False))
    observed = np.array([len(f), int((f.complete_pass == 1).sum()), int(f.receiver_player_id.notna().sum())])
    qualified = bool(good and np.array_equal(counts, observed))
    quality.append(dict(game_id=game, team=offense, qualified=qualified))
    if not qualified or game not in schedule:
        continue
    event = schedule[game]
    defense = event['away_team'] if offense == event['home_team'] else event['home_team']
    cells = np.zeros((4, 5, 6))
    unallocated = 0
    for r in f.to_dict('records'):
        pid = r['receiver_player_id']
        if pd.isna(pid):
            unallocated += 1
            continue
        fact = facts.get((game, pid))
        role = fact['position'] if fact else None
        ri = roles.index(role) if role in roles[:3] else 3
        air = r['air_yards']
        di = 4 if not finite(air) else 0 if air < 0 else 1 if air < 10 else 2 if air < 20 else 3
        caught = int(r['complete_pass'] == 1)
        yard = r.get('receiving_yards')
        known = finite(yard)
        cells[ri, di] += [1, caught, int(known), float(yard) if known else 0., int(known and caught), float(yard) if known and caught else 0.]
        target_rows.append(dict(game_id=game, player_id=pid, native_role=role, role=roles[ri], depth=depths[di], caught=caught, yards=float(yard) if known else None))
    expected[(game, offense)] = dict(game_id=game, offense=offense, defense=defense, kickoff=float(event['kickoff']), available=float(event['kickoff']) + 7 * DAY, cells=cells, attempts=len(f), unallocated=unallocated)

# The independent official-total reconciliation supplies only the old gate;
# new module counters, clocks and shrinkage are checked against separate sums.
ctx = SimpleNamespace(quality=quality)
defense = ReceivingDefense(frames, pool, g, context=ctx)
assert len(defense.rows) == len(expected)
for r in defense.rows:
    e = expected[(r['game_id'], r['offense'])]
    assert np.array_equal(r['cells'], e['cells'])
    assert (r['attempts'], r['unallocated_attempts'], r['defense'], r['available']) == (e['attempts'], e['unallocated'], e['defense'], e['available'])

cut = float(g[(g.season == 2026) & (g.week == 3)].kickoff.min())
team = 'CAR'
eligible = [r for r in expected.values() if r['available'] < cut and r['kickoff'] < cut]
last = sorted([r for r in eligible if r['defense'] == team], key=lambda r: (r['kickoff'], r['game_id'], r['offense']))[-8:]
cell = sum((r['cells'] for r in last), np.zeros((4, 5, 6)))
prior = sum((r['cells'] for r in eligible), np.zeros((4, 5, 6)))
nt, nc = prior[:, :, 0].sum(), prior[:, :, 1].sum()
base = nc / nt if nt else .5
rate = np.empty((4, 5))
for ri in range(4):
    for di in range(5):
        n, c = prior[ri, di, :2]
        rate[ri, di] = (cell[ri, di, 1] + 20 * (c / n if n else base)) / (cell[ri, di, 0] + 20)
share = (cell[:, :, 0].sum(axis=1) + 40 * prior[:, :, 0].sum(axis=1) / nt) / (cell[:, :, 0].sum() + 40)
profile = defense.profile(team, cut)
assert profile['eligible_games'] == len(last) and profile['eligible_targeted_plays'] == int(cell[:, :, 0].sum())
for i, r in enumerate(profile['cells']):
    ri, di = divmod(i, 5)
    assert (r['targets'], r['catches']) == tuple(cell[ri, di, :2].astype(int))
    assert abs(r['catch_per_target']['shrunk'] - rate[ri, di]) < 1e-14
for i, r in enumerate(profile['role_target_share']):
    assert abs(r['shrunk'] - share[i]) < 1e-14
q = dict(opponent_team=team, kickoff=cut + DAY)
v = defense.vector(q, cutoff=cut)
assert np.allclose(v[4:], np.r_[rate[:2, :4].reshape(-1), share[:2]])
assert defense.before(team, last[-1]['available'], 100) == [r for r in defense.before(team, last[-1]['available'] + .1, 100) if r['available'] < last[-1]['available']]

# Appending synthetic future outcomes cannot alter the existing as-of profile.
first = defense.rows[0]
futp = valid[(valid.game_id == first['game_id']) & (valid.posteam == first['offense'])].copy()
futp.game_id = 'FUTURE_INVARIANCE_FIXTURE'
futp['receiving_yards'] = 99999.
futf = pool[pool.game_id == first['game_id']].copy()
futf.game_id = 'FUTURE_INVARIANCE_FIXTURE'
futg = g[g.game_id == first['game_id']].copy()
futg.game_id = 'FUTURE_INVARIANCE_FIXTURE'
futg.kickoff = cut + DAY
future_quality = quality + [dict(game_id='FUTURE_INVARIANCE_FIXTURE', team=first['offense'], qualified=True)]
altered = ReceivingDefense(frames + [futp], pd.concat([pool, futf]), pd.concat([g, futg]), context=SimpleNamespace(quality=future_quality))
assert altered.profile(team, cut) == profile

# Every frozen cohort row is recomputed without the producer's memberships or History.before.
cohort = json.loads(lzma.decompress((ROOT / 'reports/profile-increment-v2/COHORT_MEMBERSHIP.json.xz').read_bytes()))['rows']
from context_identity_view_c01 import corrected_rows
offers = {(r['game_id'], r['player_id']) for r in corrected_rows() if r['method'] == 'E0'}
allhist = d[d.season >= 2022].to_dict('records')
byplayer = collections.defaultdict(list)
for r in allhist:
    byplayer[r['player_id']].append(r)
for rr in byplayer.values():
    rr.sort(key=lambda r: (r['available'], r['game_id']))
priors, recomputed, filtered_recent = {}, [], 0
for r in cohort:
    key = (r['season'], r['week'])
    common = float(g[(g.season == key[0]) & (g.week == key[1])].kickoff.min())
    if key not in priors:
        sums = collections.defaultdict(list)
        for x in allhist:
            if x['available'] < common and finite(x.get('targets')) and x['targets'] >= 0:
                sums[x['position']].append(x['targets'])
        priors[key] = {role: sum(z) / len(z) for role, z in sums.items()}
    recent = [x for x in byplayer[r['player_id']] if x['available'] < common][-3:]
    known = [x for x in recent if finite(x.get('targets')) and x['targets'] >= 0]
    filtered_recent += int(len(known) != len(recent))
    mean = sum(x['targets'] for x in known) / len(known) if known else priors[key].get(r['position'])
    offered = (r['game_id'], r['player_id']) in offers
    priority = offered or any(x['targets'] > 0 for x in known)
    reason = 'RECORDED_QUALIFIED_OFFER_TIMING_UNVERIFIED' if offered else 'POSITIVE_TARGETS_IN_ELIGIBLE_RECENT3' if priority else 'BASIC_COVERAGE_SPARSE_OR_NO_RECENT_TARGETS'
    assert mean == r['reference_expected_targets'] and common == r['reference_cutoff'] and priority == r['profiling_priority'] and reason == r['priority_reason']
    recomputed.append(dict(r, top20_expected_targets=False))
groups = collections.defaultdict(list)
for r in recomputed:
    if r['position'] in ['WR', 'TE'] and r['reference_expected_targets'] is not None:
        groups[(r['season'], r['week'], r['position'])].append(r)
for rr in groups.values():
    seen = set()
    for r in sorted(rr, key=lambda x: (-x['reference_expected_targets'], x['player_id'], x['game_id'])):
        if r['player_id'] not in seen:
            if len(seen) < 20:
                r['top20_expected_targets'] = True
            seen.add(r['player_id'])
assert [r['top20_expected_targets'] for r in recomputed] == [r['top20_expected_targets'] for r in cohort]

role_history = collections.defaultdict(dict)
for r in target_rows:
    if r['native_role']:
        role_history[r['player_id']][r['game_id']] = r['native_role']
changes = [(pid, sorted(games.items())) for pid, games in role_history.items() if len(set(games.values())) > 1]
examples = dict(ordinary=next(r for r in target_rows if r['role'] == 'WR' and r['caught']),
    explicit_zero_yards=next((r for r in target_rows if r['yards'] == 0), None),
    negative_yards=next((r for r in target_rows if r['yards'] is not None and r['yards'] < 0), None),
    missing_yards=next((r for r in target_rows if r['yards'] is None), None),
    other_or_unknown=next((r for r in target_rows if r['role'] == 'OTHER_OR_UNKNOWN'), None),
    native_role_change=changes[0] if changes else None)
for e in expected.values():
    zero = np.argwhere(e['cells'][:3, :, 0] == 0)
    if len(zero):
        ri, di = map(int, zero[0])
        examples['known_zero_target_cell'] = dict(game_id=e['game_id'], offense=e['offense'], defense=e['defense'], role=roles[ri], depth=depths[di], targets=0, catches=0, qualified_team_game=True)
        break
summary = dict(id='C-C03-INDEPENDENT-RAW-v1', verdict='PASS_WITH_RECONSTRUCTION_AND_CONDITIONAL_POPULATION_LIMITS',
    new_fits=0, network_requests=0, source_files=[dict(path=str(p.relative_to(ROOT)), SHA256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in files],
    official_gate='Independent attempts/completions/identified-target reconciliation; prior ingestion recipe not reopened',
    qualified_team_games=len(expected), target_rows=len(target_rows), all_counter_arrays_exact=True,
    profile_check=dict(team=team, cutoff=cut, eligible_games=len(last), targets=profile['eligible_targeted_plays'], all20_role_depth_shrinkage_cells=True, all4_role_share_shrinkage=True, vector_order=True, availability_then_gametime=True, strict_boundary=True, future_mutation_invariant=True),
    examples=examples, role_changing_targeted_players=len(changes),
    cohorts=dict(rows=len(cohort), all_reference_values_priority_and_top20_exact=True, last3_rows_with_unknown_targets_filtered=filtered_recent, offered_priority=sum((r['game_id'],r['player_id']) in offers for r in cohort), limitation='Stat-row/native-offer query universe; last-recorded offer flag timing unverified, not an authenticated common board. Earlier-role prior is source-row-conditional. Last3 takes last3 eligible rows then filters targets, not last3 known values.'),
    limitations=['Raw defense response, not adjusted talent or causal defense effect','Known zero cells differ from absent history; incomplete yard support is not zero','No probabilities or NFL improvement established by this source/counter audit','No independent fits authorized or executed'],
    CPU_seconds=time.process_time()-START, CPU_measurement_scope='Timed body excludes Python imports; software tests run separately', peak_RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024, threads=1)
assert summary['CPU_seconds'] <= 120 and summary['peak_RSS_bytes'] <= 805306368
OUT.mkdir(parents=True, exist_ok=True)
(OUT/'RAW_REVIEW.json').write_text(json.dumps(summary, separators=(',', ':'))+'\n')
print(json.dumps({k:summary[k] for k in ['verdict','qualified_team_games','target_rows','role_changing_targeted_players','cohorts','CPU_seconds','peak_RSS_bytes']}))
