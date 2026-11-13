"""C receipt-only check: stdlib aggregates/hashes, no B grader/model/source GET."""
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict
import hashlib
import json
import lzma
import resource
import time

P = Path(__file__).resolve().parent


def read(name):
    p = P / name
    return json.loads(lzma.decompress(p.read_bytes()) if p.suffix == '.xz' else p.read_bytes())


def main():
    started = time.process_time()
    index = read('CURRENT_EXPORT_INDEX.json.xz')
    export = {r['path']: r for r in index['exports']}
    receipt = read('EXACT_RECEIPT_BINDINGS.json')
    bindings = []
    ledger = read('CONNECTOR_READ_LEDGER.json')['reads']
    for r in ledger:
        if r['read'] == 1:
            continue
        p = P / r['local']
        raw = p.read_bytes()
        x = export[r['path']]
        assert len(raw) == x['bytes'] and hashlib.sha256(raw).hexdigest() == x['sha256']
        bindings.append({'path': str(p), 'source_path': r['path'], 'source_ref': r['ref'],
                         'bytes': len(raw), 'SHA256': x['sha256']})
    source = read('OFFICIAL_INTERCEPTION_EVIDENCE_V1.json')
    review = read('INDEPENDENT_CORRECTED_GRADE_REVIEW_V1.json')
    trans = read('MEASUREMENT_TRANSITIONS_V1.json')
    method = read('INDEPENDENT_METHOD_ARITHMETIC_V1.json')
    assert source['original_cohort_rows'] == source['private_correction_map_rows'] == 86
    assert source['original_missing_count'] == source['missing_supported_explicit_zero'] == 46
    assert source['missing_supported_nonzero'] == source['unknown_or_conflicting'] == 0
    assert source['original_missing_value_counts'] == {'0': 46}
    assert sum(source['all_corrected_value_counts'].values()) == 86
    assert source['existing_reported_count'] == 40 and source['existing_reported_all_match']
    assert source['original_cohort_sha256'] == review['private_inputs']['selected_sha256']
    assert 'passing_interceptions' in source['target_definition'] and 'passing.interceptions' in source['target_definition']
    assert 'defensive interceptions excluded' in source['target_definition']
    assert trans['transitions'] == review['transitions'] == {
        'WIN -> WIN': 33, 'MISSING_ACTUAL -> LOSS': 32,
        'LOSS -> LOSS': 7, 'MISSING_ACTUAL -> WIN': 14}
    assert trans['predictions_changed'] == trans['sides_changed'] == trans['lines_changed'] == trans['original_rows_overwritten'] == 0
    groups = defaultdict(dict)
    for r in review['results']:
        assert r['selected'] == r['decided'] + r['unknown'] + r['push']
        assert r['wins'] + r['losses'] == r['decided']
        assert abs(r['rate'] - r['wins'] / r['decided']) < 1e-12 if r['decided'] else r['rate'] is None
        groups[(r['strategy'], r['window'])][r['side'].upper()] = r
    assert len(review['results']) == 144 and len(groups) == 48
    for sides in groups.values():
        assert set(sides) == {'OVER', 'UNDER', 'COMBINED'}
        for k in ['selected', 'wins', 'losses', 'push', 'decided', 'unknown']:
            assert sides['OVER'][k] + sides['UNDER'][k] == sides['COMBINED'][k]
    focal = {}
    for name in ['CURRENT_PUBLISHED_PRESENCE_V5', 'CORRECTED_CURRENT_FINAL_LABELS',
                 'CONSTANT_OVER_ON_SAME86', 'CONSTANT_UNDER_ON_SAME86']:
        focal[name] = {side: {k: r[k] for k in ['selected', 'wins', 'losses', 'decided', 'unknown', 'rate']}
                       for side, r in groups[(name, 'ALL')].items()}
    old = focal['CURRENT_PUBLISHED_PRESENCE_V5']
    corrected = focal['CORRECTED_CURRENT_FINAL_LABELS']
    assert [old['COMBINED'][x] for x in ['wins', 'losses', 'decided', 'unknown']] == [33, 7, 40, 46]
    assert [corrected['COMBINED'][x] for x in ['wins', 'losses', 'decided', 'unknown']] == [47, 39, 86, 0]
    assert [corrected['OVER'][x] for x in ['wins', 'losses', 'decided']] == [33, 32, 65]
    assert [corrected['UNDER'][x] for x in ['wins', 'losses', 'decided']] == [14, 7, 21]
    assert focal['CONSTANT_UNDER_ON_SAME86']['COMBINED']['wins'] == 46
    assert focal['CONSTANT_OVER_ON_SAME86']['COMBINED']['wins'] == 40
    top = next(x for x in method['Top6_periods'] if x['period'] == 'ANNUAL_W1_5')
    over, under = top['own_sides']['over'], top['own_sides']['under']
    top_under = over['losses'] + under['wins']
    top_over = over['wins'] + under['losses']
    assert top['combined']['wins'] == 23 and top['combined']['decided'] == 30
    assert top_under == 21 and top_over == 9
    cmp = []
    for r in method['retained_CMP_records']:
        assert int(r['over_wins']) + int(r['under_wins']) == int(r['combined_wins']) == 52
        assert int(r['over_decided']) + int(r['under_decided']) == int(r['combined_decided']) == 88
        co = int(r['over_wins']) + int(r['under_losses'])
        cu = int(r['over_losses']) + int(r['under_wins'])
        assert co == 48 and cu == 40
        cmp.append({'method': r['method'], 'procedure_version': r['procedure_version'],
                    'wins': 52, 'decided': 88, 'constant_over_same88': co, 'constant_under_same88': cu})
    assert len(cmp) == 2
    index_read = read('INDEX_READ_RECEIPT.json')
    returned = sum(r['returned_bytes'] for r in ledger) + index_read['response_bytes']
    assert sorted([r['read'] for r in ledger] + [index_read['read']]) == list(range(1, 9))
    assert returned <= 4194304
    no_new_ftn = [k for k in index if 'information_first' in k.lower() or 'information-first' in k.lower()]
    assert not no_new_ftn
    result = {
        'id': 'C-INFORMATION-FIRST-B-RECEIPT-INDEPENDENT-v1',
        'checked_UTC': datetime.now(timezone.utc).isoformat(),
        'status': 'PASS_RECEIVED_INT_MEASUREMENT_PUBLIC_ARITHMETIC;NEW_FTN_RECEIPT_NOT_LOCATED',
        'research_ref': read('BRANCH_REF.json')['object']['sha'],
        'index_UTC': index['at_utc'], 'source_exports': len(index['exports']),
        'source_unique_export_paths': len(export),
        'exact_received_bindings': bindings,
        'aggregate_rows_checked': 144, 'O_U_Combined_triads_checked': 48,
        'original_and_corrected_records': focal,
        'transitions': trans['transitions'],
        'source_label_qualification_scope': 'B actual public independent dual-source final-label receipt received. C checks cohort/label/hash/aggregate consistency, not the private per-player correction map or raw NFLverse/ESPN bodies. Explicit46zeros is B observed evidence, never C participation-based imputation.',
        'source_selected_mask_SHA256': source['original_cohort_sha256'],
        'source_private_correction_map_SHA256': source['private_correction_map_sha256'],
        'source_board_mask_SHA256': review['private_inputs']['board_sha256'],
        'source_labels_SHA256': review['private_inputs']['labels_sha256'],
        'corrected_score_artifact_SHA256': review['root_score_artifact_sha256'],
        'original_unknown_full_pool_sensitivity': {'pool': 86, 'lower': 33 / 86, 'upper': 79 / 86,
                                                  'meaning': 'Logical extremes for old46unknowns, not actual accuracy/CI or future confidence. Actual corrected47/86 is separately observed final-label replay.'},
        'same_case_constant_algebra': {'Top6_annual': {'own': [23, 7, 30], 'always_under': [21, 9, 30], 'always_over': [9, 21, 30]},
                                       'CatBoost_HGB': cmp,
                                       'limit': 'Derived from bound published own-side partitions. Private selected identity/model/feature/clock parity and stronger learned selected controls remain unverified by C.'},
        'book_and_timing': 'B report says86DK-labeled stored lines:85at0.5 and1at1.5. Independent provider quote payload, main/alternative classification, quote/decision clocks and venue settlement are not authenticated. Do not call this an authenticated ordinary main-line full board.',
        'historical_coverage': 'Only native stored-side W5-W9 labels in this receipt. Not W1-W4 closure, fullW1-W9 championship, new predictions or a fifth cross-category selector week.',
        'prior_FTN': {'file': 'FTN_PRIOR_SOURCE_DENOMINATOR_AND_CLOCK_SCOPE_V2.json',
                      'scope': 'Existing charting quantity/clock correction metadata only. Not new B0/B1/B2 qualification/fit; no FTN dataset/docs collected.'},
        'resources': {'bound_GitHub_reads': 8, 'returned_response_bytes': returned,
                      'new_fits': 0, 'new_inference': 0, 'new_grading': 0,
                      'FTN_source_collection': 0, 'peer_writes_messages_workflow_merge': 0,
                      'CPU_seconds': time.process_time() - started,
                      'peak_RSS_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024}}
    p = P / 'INDEPENDENT_REVIEW.json'
    p.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'status': result['status'], 'triads': 48, 'response_bytes': returned,
                      'corrected': [47, 39, 86], 'file': str(p), 'SHA256': hashlib.sha256(p.read_bytes()).hexdigest()}))


if __name__ == '__main__':
    main()
