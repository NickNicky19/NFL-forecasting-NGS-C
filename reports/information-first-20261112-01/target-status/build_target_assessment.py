"""Summarize retained aggregate receipts; never infer outcomes or select a policy.

No fitting, row grading, threshold search, model routing or new NFL score occurs.
The displayed sensitivity is algebra on each already-defined selected population.
"""
from pathlib import Path
import collections
import csv
import datetime
import gzip
import hashlib
import json
import resource
import time

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
START = time.process_time()


def read(name):
    p = ROOT / name
    b = p.read_bytes()
    return json.loads(gzip.decompress(b) if p.suffix == '.gz' else b)


def write(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def bounds(wins, decided, unresolved):
    total = decided + unresolved
    return {
        'wins': wins, 'decided': decided, 'unresolved_selected': unresolved,
        'population_for_bounds': total,
        'lower': wins / total if total else None,
        'upper': (wins + unresolved) / total if total else None,
        'meaning': 'All unresolved lose to all unresolved win; not grades, probability, confidence interval or imputation',
    }


base_path = 'reports/category-decision-release-01/CATEGORY_PRODUCT_DECISIONS.json'
base = read(base_path)
categories = []
week_matrix = []
for r in base['categories']:
    category = r['category']
    actual = r.get('actual_weeks_by_season', {}).get('2026', [])
    controls = r.get('controls', {})
    combined = r.get('COMBINED')
    coverage = r.get('coverage', {})
    row = {
        'category': category,
        'declared_retained_procedure': r.get('exact_procedure'),
        'output': r.get('output'), 'decision_policy': r.get('decision_policy'),
        'broad_90_status': 'TARGET_NOT_ESTABLISHED',
        'selective_90_status': 'TARGET_NOT_ESTABLISHED',
        'named_scored_actual_line_diagnostic_weeks_2026': actual,
        'named_panel_missing_weeks_2026_W1_W9': [w for w in range(1, 10) if w not in actual],
        'ordinary_mainline_decision_time_qualified_weeks': None,
        'ordinary_mainline_qualification': 'NOT_ESTABLISHED_FOR_REQUIRED_W1_W9_CONTRACT; no blanket invalidation of other source-specific panels',
        'OVER': r.get('OVER'), 'UNDER': r.get('UNDER'), 'COMBINED': combined,
        'coverage': coverage,
        'same_own_pool_controls': {k: controls[k] for k in ['ALWAYS_OVER', 'ALWAYS_UNDER'] if k in controls},
        'retained_paired_controls': controls.get('matched_owner_pairs'),
        'exact_incumbent_comparison': controls.get('incumbent_comparison'),
        'uncertainty': r.get('uncertainty'),
        'evidence_tier': r.get('evidence_tier'),
        'five_week_status': r.get('five_week_status'),
        'evidence_limit': 'Named candidate is retained declaration, not a new largest-percentage winner or original-site active model; point direction is not probability',
    }
    if combined and isinstance(coverage.get('unknown'), int):
        row['broad_missing_outcome_sensitivity'] = bounds(combined['wins'], combined['decided'], coverage['unknown'])
    if category == 'rec':
        row['strong_same_mask_control'] = 'Retained A Leaf mean238/412 versus C P1 mean239/412; C03R3median237/412. Different broad A median328/579 is not this mask.'
    if category == 'pass_int':
        row['specific_unknown_outcome_scope'] = 'User-reported46 website missing INT cells are separate unresolved owner-grade/source records; not assumed losses/zeros/wins in this A87-case panel.'
    if category == 'anytime_td':
        row['contract_gap'] = 'Inherited rushing-or-receiving event only; no invented NO/Under offer; forecast-only event grades do not establish actual-line90.'
    if category == 'nick-chart-ppr-v1':
        row['contract_gap'] = 'No compatible exactchart actual-offer panel; legacyfantasy, syntheticthresholds and forecast-only tests do not supply it.'
    categories.append(row)
    for week in range(1, 10):
        state = 'SCORED_NAMED_ACTUAL_LINE_DIAGNOSTIC;QUOTE_TIME_AND_MAIN_ALTERNATE_UNESTABLISHED' if week in actual else 'MISSING_THIS_EXACT_NAMED_COMPARISON_PANEL'
        if week == 9:
            state = 'NO_NEW_ADMITTED_W9_ACTUAL_OFFER_RESULT;C_FORECAST_ONLY_GRADES_SEPARATE'
        if category in ['anytime_td', 'nick-chart-ppr-v1']:
            state = 'NO_COMPATIBLE_ACTUAL_OFFER_CONTRACT'
        week_matrix.append({'category': category, 'procedure': r.get('exact_procedure'), 'season': 2026, 'week': week, 'state': state, 'other_panels': 'Existing archiveW1-W7/nativeW2-W3/BW5-W8 source-specific records remain separately bound; never concatenate aliases/sources by week label'})
write('TWELVE_CATEGORY_TARGET_STATUS.json', categories)
with (OUT / 'W1_W9_TARGET_COVERAGE.csv').open('w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=list(week_matrix[0]))
    writer.writeheader()
    writer.writerows(week_matrix)

# Every pre-existing WR/TE mixed Top6/10/20 arm in the named fixed contrast is
# reported. No maximum is selected, and no new member is chosen from outcomes.
top_source = 'reports/player-context-matchup-01/TOPK_RESULTS.json.gz'
top = read(top_source)
selected = [r for r in top if r['scope'] == 'WITHIN_REC_WR_TE' and r['side'] == 'MIXED' and r['method'] in ['E0', 'P1', 'P2', 'P3'] and r['K'] in [6, 10, 20]]
top_views = []
for method in ['E0', 'P1', 'P2', 'P3']:
    for k in [6, 10, 20]:
        group = [r for r in selected if r['method'] == method and r['K'] == k]
        states = collections.Counter()
        for r in group:
            states.update(r['states'])
            assert sum(r['states'].values()) == r['selected_count']
        wins = states['WIN']; losses = states['LOSS']
        resolved_other = sum(states[x] for x in ['PUSH', 'VOID', 'DNP', 'ABSTAIN'])
        unresolved = sum(states.values()) - wins - losses - resolved_other
        selected_count = sum(r['selected_count'] for r in group)
        assert unresolved >= 0
        side_records = {}
        for side in ['OVER', 'UNDER']:
            ss = {name: sum(r[side][name] or 0 for r in group) for name in ['selected', 'wins', 'losses', 'decided']}
            ss['rate'] = ss['wins'] / ss['decided'] if ss['decided'] else None
            side_records[side] = ss
        top_views.append({
            'preexisting_policy': f'C::PLAYER-CONTEXT-MATCHUP-01::v1.1::{method}::WR_TE::MIXED::TOP_{k}',
            'scope': 'Retained two-week within-reception ranking, not cross-category TopPicks or an admitted90selector',
            'weeks': sorted(r['week'] for r in group), 'season': 2026,
            'eligible_candidates': sum(r['candidate_eligible'] for r in group),
            'selected': selected_count, 'decided': wins + losses,
            'sides': side_records, 'wins': wins, 'losses': losses,
            'decided_rate': wins / (wins + losses) if wins + losses else None,
            'unresolved': unresolved, 'states': dict(states),
            'technical_unavailability_reported_in_ranking_receipt': sum(r['unavailable'] for r in group),
            'technical_unavailability_limit': 'These ranking diagnostics do not certify absent source offers or unknown pregame universe as zero unavailability',
            'fallback_selected': sum(r['fallback_selected'] for r in group),
            'missing_outcome_sensitivity': bounds(wins, wins + losses, unresolved),
            'weekly_frozen_receipts': [{key: r[key] for key in ['id', 'week', 'candidate_eligible', 'selected_count', 'OVER', 'UNDER', 'COMBINED', 'states', 'fallback_selected', 'game_cluster_sensitivity95']} for r in group],
            'evidence': group[0]['tier'],
            'ordinary_mainline_qualified': False,
            'source_qualification_limit': 'NativePinnacle last-recorded lines; main/alternate tier and simultaneous pregameboard/quote availability unverified',
            'target_status': 'TARGET_NOT_ESTABLISHED',
            'controls': 'All E0/P1/P2/P3 arms at sameK retained; different selected memberships are not same-case paired superiority. BroadP1/P2 laws149/150 of255,Brier.279560/.280738; AlwaysUnder on broadmask is separate. No subset constantcontrol invented.',
        })
write('PREEXISTING_TOPK_SENSITIVITY.json', top_views)

# Include all methods in the originally frozen .90 diagnostic for the native
# book, including empty sets and the adverse prevalence control.
gate_source = 'reports/reliability-v8/CONFIDENCE_COVERAGE.json.gz'
gate = read(gate_source)
gate_views = []
for r in gate:
    if r['book'] != 'pinnacle' or r['minimum_nominal_probability'] != .9:
        continue
    selected_count = r['all_selected_probability_rows']
    excluded = sum(r['states'].get(k, 0) for k in ['PUSH', 'VOID', 'DNP', 'ABSTAIN'])
    unresolved = selected_count - r['decided'] - excluded
    assert unresolved >= 0
    gate_views.append({
        'book': r['book'], 'category': r['category'], 'method': r['method'],
        'frozen_minimum_nominal_probability': .9, 'rule': r['rule'],
        'eligible': r['parent_eligible'], 'selected': selected_count,
        'selection_sides': r['selection_counts'], 'states': r['states'],
        'wins': r['wins'], 'losses': r['losses'], 'decided': r['decided'],
        'decided_rate': r['hit_rate'], 'weeks': r['weeks'], 'games': r['games'],
        'fallback': r['fallback'],
        'missing_outcome_sensitivity': bounds(r['wins'], r['decided'], unresolved),
        'target_status': 'TARGET_NOT_ESTABLISHED',
        'ordinary_mainline_qualified': False,
        'limit': 'Legacyexposed diagnostic;0selections isN/A. Tiny2/2or3/3Under-only samples do not establish90. Main/alternate and quote-time contracts unresolved; later identity/current-product admission not inherited. No new side filter or threshold chosen.',
    })
write('PREEXISTING_NOMINAL_90_GATE_SENSITIVITY.json', gate_views)

source_names = [base_path, top_source, gate_source,
    'reports/abc-championship/execution-closure-02/QUALIFICATION_TABLE.json.gz',
    'reports/interception-history-closure-01/CATEGORY_PRODUCT_SUPPLEMENT.json',
    'reports/interception-history-closure-01/ledger/PERIOD_COVERAGE_SUMMARY.json',
    'reports/category-decision-release-01/W1_W9_AND_HISTORY_COVERAGE.csv.gz',
    'reports/reliability-v8/README.md',
    'reports/profile-closure-next-02/KEEP_STOP.json',
    'reports/profile-increment-v2/KEEP_STOP.json',
    'reports/interception-history-closure-01/B-intake/ADMISSION.json']
sources = []
for name in source_names:
    p = ROOT / name; b = p.read_bytes()
    sources.append({'path': name, 'bytes': len(b), 'SHA256': hashlib.sha256(b).hexdigest()})
write('ASSESSMENT_RECEIPT.json', {
    'id': 'C-INFORMATION-FIRST-90-TARGET-STATUS-v1',
    'created_UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'headline': 'No category has established broad or selective90 on the required2026W1-W9 ordinary/mainline decision-time contract.',
    'broad_90_categories_established': [], 'selective_90_categories_established': [],
    'requested_one_to_five_categories': 'ZERO_ESTABLISHED; do not manufacture1-5 winners or reinterpret a side specialist as two-sided success',
    'new_fits': 0, 'new_policy': 0, 'new_grader': 0, 'new_threshold_or_subgroup_search': 0,
    'new_scored_games_or_weeks': 0, 'new_network_reads': 0,
    'analysis': 'Only retained declared products, original fixed diagnosticarms and algebraic missing-outcome bounds; no original forecast or grade modified',
    'missingness': 'Bounds condition on identified selected population. Missing actualoffers, missingforecast/technicalunavailability, unresolved participation, abstention, push and void remain distinct. Bounds cannot certify unknown universe or clock.',
    'week_coverage': 'Named five-week rows and nativeW2-W3 are source-specific. W6-W8 other panels require exactpolicy/source agreement; W9 has no new admittedactualoffer result;forecast-onlygrades stayforecast-only.',
    'mainline_contract': 'Observed actualthreshold does not prove ordinary/main line or authenticated decision-time availability; no qualifiedalternative-to-mainline substitution.',
    'negative_findings_preserved': ['C01 identicalE0-E3/partialpoolinginconclusive', 'C03newdefensevaluesused;direction/probabilityclosedwithoutgain', 'C04one-dayloses10/255toownbaselines', 'Bdepthcompletiondirectionclosed;Brierworsethanneutral', 'Broadboardandhighconfidencegatesweak;emptysetsnot90'],
    'uncertainty': 'Fewexposedweek/gameclusters, repeatedplayers/modelselection and disconnectedpanels; no independentseason confirmation or per-pickconfidence fromhistoricalpercentages.',
    'sources': sources,
    'resource': {'CPU_seconds_this_summary': time.process_time() - START, 'peak_RSS_KiB_this_summary': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, 'retention_cap_bytes': 1048576},
})
assert sum(p.stat().st_size for p in OUT.iterdir() if p.is_file()) < 1048576
print('Retained aggregate assessment complete; zero new NFL scores or selected policies.')
