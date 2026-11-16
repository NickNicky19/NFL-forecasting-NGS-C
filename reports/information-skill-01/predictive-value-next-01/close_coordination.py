"""Append scoped receipt/proposal statuses to the existing C coordination system.

No model fit, inference, source request, historical regrade or new result.
"""
from pathlib import Path
import csv
import datetime
import gzip
import hashlib
import io
import json
import subprocess
import time

START = time.process_time()
ROOT = Path(__file__).resolve().parents[3]
D = Path(__file__).resolve().parent
COMMON = ROOT / 'reports/abc-championship'


def read(path):
    return json.loads(Path(path).read_text())


def write(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, allow_nan=False) + '\n')


def binding(path):
    path = Path(path)
    return dict(path=str(path.relative_to(ROOT)), bytes=path.stat().st_size,
                SHA256=hashlib.sha256(path.read_bytes()).hexdigest())


def main():
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    a, b, website = [read(D / p) for p in ['intake/A_RECEIPT.json', 'intake/B_RECEIPT.json', 'delivery/RECEIPT.json']]
    proposal = read(D / 'proposal/C_DYAD_MIX_V2.json')
    admission = dict(
        id='C-PREDICTIVE-VALUE-NEXT-01-ADMISSION', recorded_UTC=now,
        source_receipts=dict(A=binding(D / 'intake/A_RECEIPT.json'),
                             B=binding(D / 'intake/B_RECEIPT.json'),
                             website=binding(D / 'delivery/RECEIPT.json')),
        A_head=a['actual_head'], B_head=b['actual_head'],
        A_M3='REPAIRED_142_ROW_FIVE_WEEK_FIXTURE_OWNER_REPORTED_PASS;NO_NEW_RAW_GRADES',
        A_fixture_private_bindings_received=False,
        A_M3_authority=dict(CPU_cap=1660, wall_cap=2250, CPU_increment_once=400,
                            wall_increment_once=450, retention_CPU_reserve=120,
                            reporting_CPU_reserve=20,
                            exact_current_charge='A carries actual private ledger and all failures/overhead; not imported or inferred from public summary',
                            state='AUTHORIZED_OWNER_COMPLETION_PENDING_BALANCE_AND_RETAINED_BINDING_CHECK',
                            no_C_worker_or_budget_transfer=True),
        B_SKILL_independent_review='ACTUALLY_RECEIVED_PUBLIC_AGGREGATE_AND_NATIVE_BINDING_SCOPE',
        private_rows_membership_fit_and_original_clocks_reproduced=False,
        opportunity_early='DISTINCT_OUTPUT_JOIN_PENDING_SEPARATE_A_ALLOCATION;SKILL84_NOT_SUBSTITUTE',
        strict_reproduction=dict(C1='FAILED', opportunity_team='FAILED', retries=0),
        C05='UNCHANGED_PRIOR57_GRADED_VIEWS_12_UNKNOWN;ZERO_ACTUAL_OFFERS',
        website_head_once=website['actual_head_once'],
        website='OWNER_COMMENT237_BASELINE_ROWS;CURRENT_IMMUTABLE_META_READ_ONLY;ZERO_RESEARCH_ACTIVATION_CLAIM',
        C_proposal=binding(D / 'proposal/C_DYAD_MIX_V2.json'),
        C_proposal_state='SPECIFIED_UNLEASED_NOT_FITTED_OR_SCORED',
        single_C_external_prerequisite='Dedicated120CPU/300wall/5fit allocation including30CPUcheck-retentionreserve',
        C_new_fits=0, C_new_inference=0, C_new_grades=0,
        new_actual_offer_weeks=0, new_original_picks=0, new_primary_activation=False,
        source_and_scope_review=binding(D / 'verification/RECEIPT_SCOPE_CHECK.json'),
        proposal_static_review=binding(D / 'proposal/V2_CLARIFICATION_ACK.json'),
        protected_peer_rows_private_locators_or_internal_execution_metadata_published=False)
    write(D / 'ADMISSION.json', admission)
    parent = ROOT / 'reports/category-decision-release-01/W1_W9_AND_HISTORY_COVERAGE_V9.csv.gz'
    target = ROOT / 'reports/category-decision-release-01/W1_W9_AND_HISTORY_COVERAGE_V10.csv.gz'
    assert not target.exists(), 'Append-only V10 already exists'
    original = gzip.decompress(parent.read_bytes())
    fields = next(csv.reader(io.StringIO(original.decode())))
    rows = []

    def status_row(owner, category, procedure, week, status, kind, action, extra):
        row = dict.fromkeys(fields, '')
        row.update(owner=owner, category=category, procedure_id=procedure,
            product='EVIDENCE_OR_EXECUTION_STATUS_ONLY', season=2026, week=week,
            status=status, row_kind=kind,
            evidence_tier='STATUS_NOT_NEW_FORECAST_OR_ACTUAL_LINE_SCORE',
            source_artifacts=json.dumps([str((D / 'ADMISSION.json').relative_to(ROOT))]),
            verification_limit='No new score denominator. Public receipt/static proposal scope; private parity not inferred.',
            required_next_owner_action=action,
            issuance_state='NO_NEW_ISSUANCE_SELECTION_OR_ACTIVATION',
            additional_metrics=json.dumps(extra, sort_keys=True))
        digest = hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest()
        row['row_id'] = row['coverage_entry_id'] = digest
        rows.append(row)

    for category in ['rec', 'rec_yd']:
        status_row('A', category, 'FROZEN_C_M3::REPAIRED_ADMISSION', 'PENDING_JOIN',
            'OWNER_FIXTURE_PASS;CUMULATIVE_COMPLETION_GRANT_AUTHORIZED;NO_RAW_GRADES_RECEIVED',
            'A_M3_REPAIR_AUTHORITY_STATUS',
            'A authenticates retained fixture and private CPU/wall balances, then rawgrades before unchanged views within1660CPU2250wall and reserves.',
            dict(full_identity_rows=142, weekly_fingerprints=5,
                 owner_reported_not_C_reproduced=True, new_grades=None,
                 CPU_cap=1660, wall_cap=2250, no_transfer=True))
    status_row('B', 'pass_cmp', 'SKILL::INDEPENDENT_REVIEW', 'ALL_W1_W9',
        'INDEPENDENT_PUBLIC_REVIEW_RECEIVED;PRIOR226_CASE_SCORES_UNCHANGED',
        'B_SKILL_SCOPE_ADMISSION_STATUS',
        'Preserve fullwindow negative evidence and scoped verification; no repeatedjoin/fit.',
        dict(existing_scored_cases=226, new_scored_cases=0, review_commit=b['actual_head'], private_parity=False))
    for week in [2, 3]:
        status_row('C', 'rec', 'C-DYAD-MIX-VALUE-01/v2', week,
            'PROPOSED_NOT_EXECUTION_LEASED;NOT_FITTED_OR_SCORED',
            'C_NEW_RELATIONSHIP_REQUEST_ONLY_STATUS',
            'Obtain single dedicated120CPU300wall5fit allocation; execute unchanged fixed control/support/value package only after resourceGO.',
            dict(candidate_scores=None, existing_board_eligible=295,
                 board_outcome_unknown=27, common_decided_control_rows=268,
                 new_offer_weeks=0, no_new_fit=True, target_status='TARGET_NOT_ESTABLISHED;TEST_NOT_RUN'))
    status_row('Original website', 'ALL12', 'CURRENT_BASELINE/reference_point', 'CAPTURE_STATUS',
        'RECEIVED237_BASELINE_CAPTURE;CURRENT_META_READ;NO_RESEARCH_ACTIVATION',
        'BASELINE_CAPTURE_SCOPE_STATUS',
        'Existing website owner alone maintains qualified capture, admission, consumer/served verification and independently eligible releases.',
        dict(owner_reported_archived_baseline_rows=237,
             archived_data_commit=website['published_data_commit'],
             current_meta_commit=website['actual_head_once'],
             current_row_count_not_inferred=True, research_rows_admitted_by_this_checkpoint=0))
    buffer = io.StringIO(newline='')
    csv.DictWriter(buffer, fieldnames=fields, lineterminator='\n').writerows(rows)
    final = original + buffer.getvalue().encode()
    target.write_bytes(gzip.compress(final, compresslevel=9, mtime=0))
    assert final.startswith(original) and len(fields) == 44
    write(D / 'LEDGER_APPEND_RECEIPT.json', dict(
        recorded_UTC=now, parent=binding(parent), target=binding(target),
        original_rows=37451, added_status_rows=6, total_rows=37457,
        exact_decoded_parent_prefix_preserved=True, new_scored_cases=0,
        no_result_records_or_forecasts_changed=True,
        status_rows_are_not_six_new_tests_or_weeks=True,
        CPU_seconds=time.process_time()-START))
    checkpoint = dict(
        id='INFORMATION-SKILL-01-PREDICTIVE-VALUE-NEXT-01-C',
        stage='M3_FIXTURE_AND_B_REVIEW_RECEIVED;NO_M3_GRADES;ONE_C_PROPOSAL_REQUIRES_ALLOCATION',
        report=binding(D / 'README.md'), registration=binding(D / 'REGISTRATION.json'),
        admission=binding(D / 'ADMISSION.json'), queue=binding(D / 'FINITE_QUEUE.json'),
        proposal=admission['C_proposal'], proposal_request=proposal['request'],
        coverage_ledger=binding(target), coverage_append=binding(D / 'LEDGER_APPEND_RECEIPT.json'),
        A_M3_authority=admission['A_M3_authority'],
        B_independent_SKILL_review=admission['B_SKILL_independent_review'],
        new_C_predictive_experiment_executed=False, new_C_fits=0,
        new_grades_or_offered_weeks=0, original_site_changed=False,
        primary_activation=False, later_roster_only=True)
    ledger_path = COMMON / 'ADMISSION_LEDGER.json'
    ledger = read(ledger_path)
    ledger['predictive_value_next_01'] = checkpoint
    write(ledger_path, ledger)
    tasks_path = COMMON / 'TASK_LEDGER.json'
    tasks = read(tasks_path)
    updates = {
        'A_FROZEN_C_M3_OWNER_LOCAL_JOIN': dict(
            state='REPAIRED_FIXTURE_OWNER_REPORTED_PASS;AUTHORIZED_NEW_CUMULATIVE_COMPLETION_CAPS;RAW_GRADES_PENDING',
            artifact=str((D / 'intake/A_RECEIPT.json').relative_to(ROOT)),
            budget=admission['A_M3_authority'],
            next_action='A authenticates retained fixture and latest private CPU/wall ledger, proves complete path/reserves fit, then rawgrades before unchanged summaries. No new Cworker or new approval needed for already-authorized scope.'),
        'A_B_INFORMATION_SKILL_EARLY_JOIN': dict(
            state='COMPLETED84_EARLY_AND226_FULL;B_PUBLIC_REVIEW_ACTUALLY_RECEIVED;C_ADMITTED_SCOPE',
            artifact=str((D / 'intake/B_RECEIPT.json').relative_to(ROOT)),
            next_action='Preserve completed ownside records and private-parity limits; do not rerun or substitute opportunity outputs.'),
    }
    for task in tasks:
        if task.get('task_id') in updates:
            task.update(updates[task['task_id']])
    tasks.append(dict(task_id='C_DYAD_MIX_VALUE_01', owner='C',
        state='SPECIFIED_NOT_LEASED;NO_EXECUTION_GO',
        artifact=str((D / 'proposal/C_DYAD_MIX_V2.json').relative_to(ROOT)),
        next_action=admission['single_C_external_prerequisite'],
        not_funded_by_A_M3_or_old_closed_C_package=True))
    write(tasks_path, tasks)
    cp_path = COMMON / 'CURRENT_PROTOCOL.json'
    cp = read(cp_path)
    cp['predictive_value_next_01'] = checkpoint
    cp['information_skill_follow_through_01']['current_A_M3_accounting'] = admission['A_M3_authority']
    cp['executed_receipts_gap_closure_01']['superseded_forward_by'] = binding(D / 'ADMISSION.json')
    cp['executed_receipts_gap_closure_01']['original_A_M3_status_is_historical'] = True
    cp['category_decision_release_01']['coverage_matrix'] = binding(target)
    cp['category_decision_release_01']['latest_received_delivery'] = binding(D / 'delivery/RECEIPT.json')
    cp['admission'] = binding(ledger_path)
    cp['tasks'] = binding(tasks_path)
    write(cp_path, cp)
    export_path = COMMON / 'EXPORT_INDEX.json'
    export = read(export_path)
    export['predictive_value_next_01'] = checkpoint
    export['information_skill_follow_through_01']['current_A_M3_accounting'] = admission['A_M3_authority']
    export['executed_receipts_gap_closure_01']['superseded_forward_by'] = binding(D / 'ADMISSION.json')
    export['category_decision_release_01']['coverage_matrix'] = binding(target)
    export['common_protocol'] = binding(cp_path)
    write(export_path, export)
    print(json.dumps(dict(status='APPENDED_SCOPED_STATUS', new_scores=0, new_fits=0, ledger_rows=37457)))


if __name__ == '__main__':
    main()
