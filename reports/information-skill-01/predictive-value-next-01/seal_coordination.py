"""Seal receipt/proposal coordination; never run the proposed experiment."""
from pathlib import Path
import datetime
import gzip
import hashlib
import json
import subprocess
import time

ROOT = Path(__file__).resolve().parents[3]
D = Path(__file__).resolve().parent
COMMON = ROOT / 'reports/abc-championship'


def read(path):
    return json.loads(Path(path).read_text())


def write(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, allow_nan=False) + '\n')


def bind(path):
    path = Path(path)
    return dict(path=str(path.relative_to(ROOT)), bytes=path.stat().st_size,
                SHA256=hashlib.sha256(path.read_bytes()).hexdigest())


def main():
    start = time.process_time()
    old = ROOT / 'reports/information-skill-01/executed-receipts-gap-closure-01/MANIFEST.json'
    prior = read(old)
    for item in prior['files']:
        assert bind(ROOT / item['path'])['SHA256'] == item['SHA256'], item['path']
    ack = read(D / 'proposal/V2_CLARIFICATION_ACK.json')
    assert bind(D / 'proposal/C_DYAD_MIX_V2.json')['SHA256'] == ack['reviewed_proposal_SHA256']
    assert ack['execution_GO'] is False
    review = read(D / 'verification/RECEIPT_SCOPE_CHECK.json')
    assert 'PASS' in review['status']
    for path in D.rglob('*.py'):
        compile(path.read_text(), str(path), 'exec')
    ledger = read(D / 'LEDGER_APPEND_RECEIPT.json')
    assert bind(ROOT / ledger['target']['path'])['SHA256'] == ledger['target']['SHA256']
    parent = gzip.decompress((ROOT / ledger['parent']['path']).read_bytes())
    current = gzip.decompress((ROOT / ledger['target']['path']).read_bytes())
    assert current.startswith(parent) and len(current) > len(parent)
    assert ledger['added_status_rows'] == 6 and ledger['new_scored_cases'] == 0
    assert not subprocess.run(['git', 'diff', '--check'], cwd=ROOT, capture_output=True).returncode
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    validation = dict(
        id='C-PREDICTIVE-VALUE-NEXT-01-VALIDATION', recorded_UTC=now,
        status='PASS_SCOPED_METADATA_AND_PROPOSAL_ONLY',
        prior_C59_sealed_members_unchanged=len(prior['files']),
        old_V9_decoded_prefix_preserved=True, new_status_rows=6,
        new_scores_fits_inference_or_source_data=0,
        proposal_V2_static_ack=bind(D / 'proposal/V2_CLARIFICATION_ACK.json'),
        actual_dyad_NFL_feature_trace='NOT_EXECUTED;INSIDE_REQUESTED_LEASE',
        no_strict_fit_reproduction_retry=True, no_primary_activation=True,
        CPU_seconds=time.process_time()-start)
    write(D / 'VALIDATION.json', validation)
    charged = 525.35995406 + 30
    resource = dict(
        id='C-PREDICTIVE-VALUE-NEXT-01-COORDINATION-RESOURCE', recorded_UTC=now,
        parent_C_information_CPU_cap_unchanged=600,
        prior_charged_CPU=525.35995406,
        conservative_coordination_feasibility_publication_charge_CPU=30,
        current_total_C_charged_CPU=charged,
        remaining_parent_CPU=600-charged,
        prior_C_information_fit_attempts=37, old_fit_attempt_cap_unchanged=40,
        new_fit_attempts=0,
        measurement_limit='30 is conservative bookkeeping for bounded reads, preparation, scoped checks, checker failures, pointer/ledger writes, retention and normal publication. It is not30 measured seconds or a complete tool/remote-CI CPU certificate. All earlier limits and costs remain.',
        includes_conservative_subtasks=dict(runtime_schema_review=6, A_intake=2, B_intake=1,
                                            B_scope_check=1, C_proposal_review=1),
        metadata_attempt_caps=dict(A=4, B=4, website=3),
        actual_attempts=dict(A=3, B=4, website=3),
        actual_successful_GitHub_GETs=dict(A=2, B=3, website=3),
        local_rejected_URL_attempts=2, new_raw_football_source_requests=0,
        publication_readback_GET_cap=4, publication_readback_byte_cap=2097152,
        A_only_cumulative_M3_grant=dict(CPU=1660, wall=2250, increment_CPU_once=400,
                                       increment_wall_once=450, reserves_CPU=140,
                                       owner_exact_private_balances_not_exported=True),
        new_C_predictive_package_request=dict(CPU=120, wall=300, fits=5, reserve_in_CPU=30,
                                              state='NOT_GRANTED;NO_BUDGET_TRANSFER'),
        no_paid_compute_or_API_allowance=True)
    write(D / 'RESOURCE_CLOSURE.json', resource)
    paths = sorted({p for p in D.rglob('*') if p.is_file() and p.name != 'MANIFEST.json'
                    and '__pycache__' not in p.parts} | {ROOT / ledger['target']['path']})
    assert sum(p.stat().st_size for p in paths) < 4194304
    write(D / 'MANIFEST.json', dict(
        id='C-PREDICTIVE-VALUE-NEXT-01-MANIFEST', recorded_UTC=now,
        base_commit='371bce3fea4e6fa620edce3e3cc55ce47bff56c3',
        files=[bind(p) for p in paths],
        scope='Permitted public scientific receipt summaries, unexecuted proposal and append-only status ledger; no new forecasts, private peer data or model results.'))
    cp_path = COMMON / 'CURRENT_PROTOCOL.json'
    cp = read(cp_path)
    checkpoint = cp['predictive_value_next_01']
    checkpoint.update(report=bind(D / 'README.md'),
                      resources=bind(D / 'RESOURCE_CLOSURE.json'),
                      validation=bind(D / 'VALIDATION.json'),
                      sealed_manifest=bind(D / 'MANIFEST.json'))
    admission_path = COMMON / 'ADMISSION_LEDGER.json'
    admission = read(admission_path)
    admission['predictive_value_next_01'] = checkpoint
    write(admission_path, admission)
    cp['admission'] = bind(admission_path)
    cp['tasks'] = bind(COMMON / 'TASK_LEDGER.json')
    write(cp_path, cp)
    export_path = COMMON / 'EXPORT_INDEX.json'
    export = read(export_path)
    export['predictive_value_next_01'] = checkpoint
    export['common_protocol'] = bind(cp_path)
    write(export_path, export)
    result = subprocess.run(['python', 'src/abc_period_validation_v2.py'], cwd=ROOT,
                            text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    print(json.dumps(dict(status='SEALED_NO_NEW_FIT_OR_SCORE', files=len(paths),
                          parent_C_charged_CPU=charged,
                          current_period_bindings=result.stdout.strip())))


if __name__ == '__main__':
    main()
