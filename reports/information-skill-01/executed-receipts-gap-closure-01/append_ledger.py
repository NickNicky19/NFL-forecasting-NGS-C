#!/usr/bin/env python3
"""Append received public aggregates/statuses to the existing ledger; never grade.

V8's decoded bytes remain an exact prefix. Early/full/cumulative/selected views
overlap and must not be summed as observations. No network, model, or grader use.
"""
import collections
import csv
import datetime
import gzip
import hashlib
import io
import json
from pathlib import Path
import resource
import time
from decimal import Decimal


ROOT = Path(__file__).resolve().parents[3]
D = Path(__file__).resolve().parent
BASE = ROOT / 'reports/category-decision-release-01/W1_W9_AND_HISTORY_COVERAGE_V8.csv.gz'
TARGET = ROOT / 'reports/category-decision-release-01/W1_W9_AND_HISTORY_COVERAGE_V9.csv.gz'
RECEIPT = D / 'LEDGER_APPEND_RECEIPT.json'
BASE_SHA256 = 'ffea1b60525061e93f8f0f51eed950c598eaa7b385e6f1ed50a19ec020958e13'
A_COMMIT = 'f79c05835ba3a41a7e73a5c6fd26c05896011e4e'
B_COMMIT = 'a0f5b91c61c9d1c7c2a3e39c4bdd6da29435e98e'
SKILL_COMMIT = '78383a9d29948b90056415c2274a83d6054acf79'
SKILL_FAMILY = 'INFORMATION-SKILL-01_B_expected_conversion_pass_mix_v1'
OPP_FAMILY = 'B-OPPORTUNITY-v1'
A_DIR = 'reports/abc-championship/info-skill-B-early-join-v1/A'
B_DIR = 'reports/information-skill-follow-through-01/B/opportunity-v1'
A_LINKS = [f'https://github.com/NickNicky19/NFL-forecasting/blob/{A_COMMIT}/{A_DIR}/{name}'
           for name in ['FOLLOW_THROUGH_V1.md', 'SCIENTIFIC_TABLES_V1.zip']]
B_LINKS = [f'https://github.com/NickNicky19/NFL-forecasting-V2/blob/{B_COMMIT}/{B_DIR}/{name}'
           for name in ['README.md', 'HISTORICAL_TYPED_HANDOFF_V1.json', 'REQUIRED_CHECKS_V1.json']]
SKILL_LINK = (f'https://github.com/NickNicky19/NFL-forecasting-V2/blob/{SKILL_COMMIT}/'
              'reports/information-skill-01/B/README.md')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def compact(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def string(value):
    return '' if value is None else str(value)


def append_row(rows, fields, row):
    assert not (set(row) - set(fields)), set(row) - set(fields)
    row = {key: string(row.get(key, '')) for key in fields}
    identity = {key: value for key, value in row.items() if key not in ['row_id', 'coverage_entry_id']}
    key = sha(('C_EXECUTED_RECEIPTS_GAP_CLOSURE_V9:' + compact(identity)).encode())
    row['row_id'] = key
    row['coverage_entry_id'] = key
    rows.append(row)


def source_value_count(states, selected=None):
    if not states:
        return ''
    states = json.loads(states)
    if all(key == 'none' for key in states):
        return '0'
    # Source dictionary's semantics are retained; do not guess non-none kinds.
    return ''


def skill_row(raw, panel, kind, selected_view=False):
    _, arm, output = raw['procedure'].split('::')
    policy = raw['policy'] or 'FROZEN_FULL_BOARD_' + output + '_DIRECTION'
    procedure = f'{SKILL_FAMILY}::{arm}::{output}'
    if selected_view:
        procedure += '::' + policy
    metrics = {
        'source_record': raw,
        'source_record_not_regraded': True,
        'source_procedure_alias': raw['procedure'],
        'model_origin_session': 'B',
        'protected_early_execution_owner': 'A',
        'frozen_policy': policy,
        'associated_law_scores_only': output != 'LAW',
        'probability_score_procedure': f'{SKILL_FAMILY}::{arm}::LAW',
        'point_direction_has_no_implied_probability': output != 'LAW',
        'raw_source_scored_may_mean_numerical_scoring': True,
        'ledger_scored_is_direction_COMBINED_decided': True,
        'proper_metrics_scope': 'Only this supplied record; no ALL-to-week imputation.',
        'aggregation_warning': 'Non-additive panel/output/policy views; early subset overlaps full source-bound union and prior native rows.',
        'new_games': 0,
        'new_original_selections': 0,
        'unavailable': raw.get('unavailable', ''),
        'board_games': raw.get('eligible_games', ''),
        'board_player_games': raw.get('eligible_player_games', ''),
    }
    if selected_view:
        metrics.update({
            'selector_nine_week_qualification': False,
            'membership_verified_by_C': False,
            'capacity10_note': 'All four early COVERAGE_10 policies have owner-reported identical seven Under selections/6-1; not four independent discoveries.',
            'calibrated_startup': 'Frozen identity startup with no earlier native calibration cases; not demonstrated probability calibration.',
            'numerical_scored_source_value': raw.get('scored', ''),
        })
    fallback = raw.get('parent_fallback', '')
    if fallback == '':
        fallback = source_value_count(raw.get('fallback_states', ''))
    return dict(
        owner='B', category='pass_cmp', procedure_id=procedure,
        product=('SELECTED_' if selected_view else 'DIRECTION_') + output,
        history='Frozen B strict-seven-day current-vintage historical-origin procedure; no authenticated vintage claim.',
        role_scope='Qualified QB offered-player population; complete panel is partial league coverage.',
        source_panel=panel,
        book='Source-labelled A early retained offers plus B native DK/Sleeper where applicable; see immutable bindings.',
        evidence_tier='TIMING_UNVERIFIED_ACTUAL_LINE_DIAGNOSTIC',
        season='2026', week=raw['week'],
        status='OWNER_AGGREGATE_RECEIVED_PUBLIC_ARITHMETIC_ADMITTED',
        eligible=raw['eligible'], available=raw['available'],
        selected=raw['COMBINED_selected'], scored=raw['COMBINED_decided'],
        unknown=raw['unknown_selected'], abstained=raw['abstentions'], fallback=fallback,
        games=raw.get('selected_games', '') if selected_view else raw.get('eligible_games', ''),
        player_games=raw.get('selected_player_games', '') if selected_view else raw.get('eligible_player_games', ''),
        over_wins=raw['OVER_wins'], over_losses=raw['OVER_losses'],
        under_wins=raw['UNDER_wins'], under_losses=raw['UNDER_losses'],
        over_decided=raw['OVER_decided'], over_rate=raw['OVER_rate'],
        under_decided=raw['UNDER_decided'], under_rate=raw['UNDER_rate'],
        combined_wins=raw['COMBINED_wins'], combined_losses=raw['COMBINED_losses'],
        combined_decided=raw['COMBINED_decided'], combined_rate=raw['COMBINED_rate'],
        source_artifacts=compact(A_LINKS + [SKILL_LINK]),
        verification_limit='Public aggregate arithmetic only; no C protected-row/membership/source-clock or fit parity. Preserve supplied independent-Bernoulli intervals as diagnostics, not dependence-aware guarantees.',
        source_evidence_class='RETAINED_REAL_OFFERS;QUOTE_CLOCK_AND_MAIN_ALT_UNVERIFIED;EXPOSED_CURRENT_VINTAGE_RECONSTRUCTION',
        new_procedure_coverage_not_new_games='True',
        required_next_owner_action='Keep frozen negative/limited findings and stronger controls; B checks permitted new early contribution; no retuning, selector union or primary promotion.',
        row_kind=kind, grading_version='OWNER_FROZEN_SKILL_JOIN_V1;NO_C_REGRADE',
        issuance_state='RETROSPECTIVE_NOT_ORIGINAL_PREGAME_PICKS', additional_metrics=compact(metrics),
    )


def opportunity_row(raw, b):
    arm, output = raw['exact_output'].split()
    scope = b['actual_line_scope']
    associated = next(r for r in b['proper_scores'] if r['target'] == raw['target'] and r['law'] == arm)
    metrics = {
        'source_record': raw,
        'source_record_not_regraded': True,
        'exact_experiment': OPP_FAMILY,
        'frozen_output': output,
        'frozen_full_board_policy': output + '_DIRECTION_FROM_TYPED_OWNER_BINDINGS',
        'associated_law_scores_only': output != 'LAW',
        'probability_score_procedure': f'{OPP_FAMILY}::{raw["target"]}::{arm}::LAW',
        'associated_law_proper_scores': associated,
        'proper_metrics_scope': 'Owner-reported rounded cumulative W5-W9 scores only; no derived weekly metrics.',
        'partial_weekly_counts_not_retrieved': True,
        'fallback_contract': 'One parent/no-history fallback per full-board arm/target, included in complete system.',
        'unknown_quote_clocks': True,
        'main_alternate': 'UNCLASSIFIED',
        'team_fit_strict_reproduction': 'FAILED',
        'share_fit_and_saved_row_checks': 'PASS_SEPARATE_SCOPE',
        'old_C1_strict_reproduction': 'FAILED',
        'C_prediction_adapter_and_fit_parity': 'NOT_REPRODUCED',
        'new_games': 0, 'new_original_selections': 0,
        'aggregation_warning': 'Outputs and ATT/CMP share repeated player-games; never sum views as independent outcomes.',
    }
    row = dict(
        owner='B', category=raw['target'], procedure_id=f'{OPP_FAMILY}::{raw["target"]}::{arm}::{output}',
        product='DIRECTION_' + output,
        history=b['new_relationship']['history'], role_scope='Usage-only single-QB conditional marginal; no observed personnel/injury input.',
        source_panel='B_OPPORTUNITY_NATIVE_2026_W5_W9', book='DK141;Sleeper1;main-altunclassified',
        evidence_tier='TIMING_UNVERIFIED_ACTUAL_LINE_DIAGNOSTIC', season='2026', week='ALL_W5_W9',
        status='OWNER_CUMULATIVE_AGGREGATE_RECEIVED_PUBLIC_ARITHMETIC_ADMITTED',
        eligible=scope['eligible'], available=scope['available'], selected=scope['selected'], scored=scope['decided'],
        unknown=scope['unknown'], abstained=scope['abstentions'], fallback=scope['parent_no_history_fallback_per_arm_target'],
        games=scope['games'], player_games=scope['unique_player_games_shared_across_ATT_CMP'],
        source_artifacts=compact(B_LINKS),
        verification_limit='C received 24 cumulative own-side records and exact handoff; no private rows, weekly own-side totals, raw probabilities, fitted models or source clocks independently inspected.',
        source_evidence_class='RETAINED_REAL_OFFERS;QUOTE_CLOCK_UNKNOWN;MAIN_ALT_UNCLASSIFIED;EXPOSED_CURRENT_VINTAGE_RECONSTRUCTION',
        new_procedure_coverage_not_new_games='True',
        required_next_owner_action='A assesses exact typed saved-output W1-W4 join under its separate task authority/accounting. Close frozen unsuccessful joint recipe; no primary activation or refit for score view.',
        row_kind='B_OPPORTUNITY_CUMULATIVE_OWN_SIDE_VIEW',
        grading_version='OWNER_FROZEN_OPPORTUNITY_V1;NO_C_REGRADE',
        issuance_state='RETROSPECTIVE_NOT_ORIGINAL_PREGAME_PICKS', additional_metrics=compact(metrics),
    )
    for side, prefix in [('Over', 'over'), ('Under', 'under'), ('Combined', 'combined')]:
        for key in ['wins', 'losses', 'decided', 'rate']:
            row[prefix + '_' + key] = raw[side][key]
    return row


def main():
    started_cpu = time.process_time()
    started_wall = time.monotonic()
    base_compressed = BASE.read_bytes()
    assert sha(base_compressed) == BASE_SHA256, 'V8 changed; stop rather than replace historical prefix.'
    base = gzip.decompress(base_compressed)
    assert base.endswith(b'\n')
    old_reader = csv.DictReader(io.StringIO(base.decode(), newline=''))
    fields = old_reader.fieldnames
    old_rows = list(old_reader)
    assert len(fields) == 44 and len(old_rows) == 36557
    inputs = {name: D / 'intake' / (name + '_RECEIPT.json') for name in ['A', 'B']}
    a, b = [json.loads(inputs[name].read_text()) for name in ['A', 'B']]
    assert a['actual_head'] == A_COMMIT
    assert b['source']['scientific_commit'] == B_COMMIT
    assert len(a['new_SKILL_source_bound_W1_W9_broad_records']) == 120
    assert len(a['new_SKILL_early_own_records']) == 60
    assert len(a['early_own_selection_records']) == 380
    assert len(b['own_side_cumulative']) == 24
    new = []
    for raw in a['new_SKILL_source_bound_W1_W9_broad_records']:
        append_row(new, fields, skill_row(raw, 'A_B_SKILL_SOURCE_BOUND_W1_W9_AGGREGATE_UNION', 'B_SKILL_SOURCE_BOUND_NINE_WEEK_VIEW'))
    for raw in a['new_SKILL_early_own_records']:
        append_row(new, fields, skill_row(raw, 'A_PROTECTED_NEW_B_SKILL_EARLY_W1_W4', 'B_SKILL_EARLY_OWN_SIDE_NONADDITIVE_SUBPANEL_VIEW'))
    for raw in a['early_own_selection_records']:
        append_row(new, fields, skill_row(raw, 'A_PROTECTED_NEW_B_SKILL_EARLY_W1_W4', 'B_SKILL_EARLY_FROZEN_OWN_SELECTION_VIEW', True))
    for raw in b['own_side_cumulative']:
        row = opportunity_row(raw, b)
        append_row(new, fields, row)
        for week in range(1, 5):
            pending = {key: value for key, value in row.items() if key not in [
                'eligible', 'available', 'selected', 'scored', 'unknown', 'abstained', 'fallback', 'games', 'player_games',
                'over_wins', 'over_losses', 'under_wins', 'under_losses', 'over_decided', 'over_rate',
                'under_decided', 'under_rate', 'combined_wins', 'combined_losses', 'combined_decided', 'combined_rate']}
            pending.update(
                source_panel='A_PROTECTED_DISTINCT_B_OPPORTUNITY_EARLY_JOIN_PENDING',
                evidence_tier='EXECUTION_PENDING_NO_RESULT', week=week,
                status='EXACT_OPPORTUNITY_SAVED_OUTPUT_JOIN_PENDING;NOT_COMPLETED_SKILL_OR_OLD_M2',
                row_kind='B_OPPORTUNITY_DISTINCT_EARLY_JOIN_PENDING_CELL',
                grading_version='NO_GRADE_CREATED',
                additional_metrics=compact({'execution_owner': 'A', 'model_origin': 'B', 'exact_experiment': OPP_FAMILY,
                    'distinct_from_SKILL_and_old_M2': True, 'numerical_origins_do_not_fill_actual_line_cells': True,
                    'accounting': 'Separate task authority/budget; no M1 or frozen C-M3 allowance transfer.',
                    'new_grade_count': None, 'missing_execution_not_zero_selected': True}),
            )
            append_row(new, fields, pending)
    m3 = a['M3_admission_and_budget']
    charged = Decimal('1056.334180015')
    remaining_total = Decimal(1260) - charged
    worker = remaining_total - Decimal(120) - Decimal(20)
    assert Decimal(str(m3['charged_CPU'])) == charged
    prior_m3 = [r for r in old_rows if r['row_kind'] == 'FROZEN_C_M3_OWNER_SOURCE_ADMITTED_PENDING_GRADE']
    assert len(prior_m3) == 210
    for prior in prior_m3:
        row = dict(prior)
        row.update(
            evidence_tier='EXECUTION_BLOCKED_NO_NEW_MODEL_RESULT',
            status='A_ADAPTER_DUAL_CLOCK_OMISSION_BEFORE_GRADING;REPAIR_NOT_EXECUTED;NO_NEW_C_GRADES',
            source_artifacts=compact(A_LINKS),
            verification_limit='A public stop/accounting received; C did not repair or execute A adapter, inspect private rows/fingerprints, run fit or receive a repaired-fixture PASS. Stop is not a C model loss.',
            source_evidence_class='OWNER_ADAPTER_STOP;EXACT_FULL142_IDENTITY_FINGERPRINT_GATE_PENDING',
            required_next_owner_action='A reviews scoped dual-clock adapter repair/small existing contract fixture under remaining cap. Full worker reported not safely fitting: supply one bounded completion request with latest charge, reusable checkpoints, stages, 120+20 reserves and exact extra allowance. No automatic grant/retry.',
            row_kind='FROZEN_C_M3_ADAPTER_STOP_SUPERSEDING_STATUS_CELL',
            grading_version='NO_NEW_GRADES;ORIGINAL_FAILURES_PRESERVED',
            additional_metrics=compact({
                'supersedes_coverage_entry_id': prior['coverage_entry_id'], 'prior_status_preserved_in_exact_V8_prefix': True,
                'execution_owner': 'A', 'model_origin': 'C', 'frozen_M3_not_new_C_information': True,
                'charged_CPU': str(charged), 'cumulative_cap_CPU': '1260',
                'remaining_total_including_reserves_CPU': str(remaining_total),
                'retention_reserve_CPU': '120', 'reporting_reserve_CPU': '20',
                'remaining_worker_before_reserves_CPU': str(worker),
                'old_429_031742_remainder_superseded': True, 'additional_CPU_granted': '0',
                'exact_additional_CPU_request_received': None, 'new_C_grades': None,
                'required_source_rows': 142, 'required_reference_rows': 142,
                'required_full_membership_and_fingerprint_parity': True,
                'known_dual_clock_admission': m3['known_dual_clock_admission'],
                'differences_before_repair': m3['differences'],
                'repair_status': m3['repair_status'], 'fixture_PASS_received': False,
                'full_worker_reported_safe': False, 'metering_limit': m3['metering_limit'],
                'M1_budget_unchanged_and_other_joins_separately_accounted': True,
            }),
        )
        append_row(new, fields, row)
    ids = [r['row_id'] for r in new]
    assert len(ids) == len(set(ids)) == 890
    assert not (set(ids) & {r['row_id'] for r in old_rows})
    output = io.StringIO(newline='')
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator='\r\n')
    writer.writerows(new)
    appended = output.getvalue().encode()
    decoded = base + appended
    assert decoded[:len(base)] == base
    parsed = csv.DictReader(io.StringIO(decoded.decode(), newline=''))
    parsed_rows = list(parsed)
    assert parsed.fieldnames == fields and len(parsed_rows) == len(old_rows) + len(new)
    # These checks only reconcile supplied public counts; they create no grades.
    score_checks = 0
    for row in new:
        if row['combined_decided'] == '':
            continue
        for prefix in ['over', 'under', 'combined']:
            n = int(row[prefix + '_decided'])
            if n:
                assert int(row[prefix + '_wins']) + int(row[prefix + '_losses']) == n
            else:
                assert row[prefix + '_wins'] in ['', '0'] and row[prefix + '_losses'] in ['', '0']
            score_checks += 1
        assert int(row['over_decided']) + int(row['under_decided']) == int(row['combined_decided'])
    compressed = io.BytesIO()
    with gzip.GzipFile(filename='', mode='wb', fileobj=compressed, mtime=0, compresslevel=9) as file:
        file.write(decoded)
    target = compressed.getvalue()
    if TARGET.exists():
        assert TARGET.read_bytes() == target, 'Existing V9 differs; do not overwrite another version.'
    else:
        TARGET.write_bytes(target)
    assert gzip.decompress(TARGET.read_bytes()) == decoded
    elapsed_cpu = time.process_time() - started_cpu
    receipt = {
        'id': 'C-EXECUTED-RECEIPTS-GAP-CLOSURE-LEDGER-V9',
        'recorded_UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'script': str(Path(__file__).relative_to(ROOT)), 'script_SHA256': sha(Path(__file__).read_bytes()),
        'parent': str(BASE.relative_to(ROOT)), 'parent_SHA256': sha(base_compressed),
        'parent_decoded_SHA256': sha(base), 'parent_decoded_bytes': len(base),
        'target': str(TARGET.relative_to(ROOT)), 'bytes': len(target), 'SHA256': sha(target),
        'decoded_bytes': len(decoded), 'decoded_SHA256': sha(decoded),
        'exact_decoded_V8_prefix_preserved': True, 'schema_unchanged_columns': len(fields),
        'deterministic_gzip': 'Empty filename, mtime0, compresslevel9; existing-output byte identity checked on rerun.',
        'old_rows': len(old_rows), 'added_rows': len(new), 'total_rows': len(parsed_rows),
        'new_row_kind_counts': dict(collections.Counter(r['row_kind'] for r in new)),
        'actual_B_opportunity_own_side_cumulative_rows_received': len(b['own_side_cumulative']),
        'A_full_SKILL_rows': 120, 'A_early_SKILL_nonadditive_rows': 60, 'A_early_selection_rows': 380,
        'pending_distinct_early_opportunity_cells': 96, 'superseding_M3_adapter_stop_cells': 210,
        'source_receipt_hashes': {str(path.relative_to(ROOT)): sha(path.read_bytes()) for path in inputs.values()},
        'new_row_id_uniqueness': True, 'new_old_row_id_disjoint': True,
        'public_own_side_triads_checked': score_checks,
        'probability_scores_attached_to_point_rows_are_associated_law_only': True,
        'no_ALL_metric_imputation_to_weekly_rows': True,
        'overlapping_early_full_and_selected_views_nonadditive': True,
        'new_scoring_or_private_row_parity': False, 'new_fits': 0, 'new_inference': 0,
        'new_original_picks': 0, 'new_NFL_games': 0, 'network_requests': 0,
        'root_canonical_pointers_or_old_reports_modified': False,
        'C05_and_website_additions': 'Reserved for root; not appended here.',
        'resource': {'process_CPU_seconds_through_target_write_and_checks': elapsed_cpu,
            'wall_seconds_through_target_write_and_checks': time.monotonic() - started_wall,
            'max_RSS_KiB_linux': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            'accounting': 'C metadata/retention package only. Excludes interpreter import/startup, receipt final serialization and outer tool overhead; no A M3/M1 budget charge.'},
    }
    RECEIPT.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
