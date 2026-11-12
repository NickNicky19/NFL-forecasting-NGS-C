"""C public B receipt arithmetic only; no B models, raw grader or network."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import lzma
import resource
import time

P = Path(__file__).resolve().parent
ROOT = P.parents[2]


def read(name):
    p = P / name
    raw = p.read_bytes()
    return json.loads(lzma.decompress(raw) if p.suffix == '.xz' else raw)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    started = time.process_time()
    index_raw = lzma.decompress((P / 'CURRENT_EXPORT_INDEX.json.xz').read_bytes())
    index = json.loads(index_raw)
    fallback = read('INDEX_FALLBACK_READ6.json')
    assert fallback['git_blob_matches'] and len(index_raw) == 1467592
    assert digest(index_raw) == fallback['source_SHA256']
    exports = {r['path']: r for r in index['exports']}
    report_path = 'reports/next-generation-information-research-01/B/B_NEXT_GENERATION_CHECKPOINT_V1.md'
    table_path = 'reports/next-generation-information-research-01/B/depth-role-scores-v1/COMMON_CONTROL_TABLE.json'
    table_raw = lzma.decompress((P / 'COMMON_CONTROL_TABLE.json.xz').read_bytes())
    report_raw = (P / 'B_NEXT_GENERATION_CHECKPOINT_V1.md').read_bytes()
    manifest_raw = (P / 'NEXT_GEN_PUBLICATION_MEMBERS_V1.json').read_bytes()
    assert digest(table_raw) == exports[table_path]['sha256']
    assert digest(report_raw) == exports[report_path]['sha256']
    assert digest(manifest_raw) == index['next_generation_information_research_01']['manifest_sha256']
    manifest = json.loads(manifest_raw)
    for path, raw in [(table_path, table_raw), (report_path, report_raw)]:
        x = next(r for r in manifest['members'] if r['path'] == path)
        assert x['sha256'] == digest(raw) and x['bytes'] == len(raw)
    rows = json.loads(table_raw)
    triads = 0
    empty = 0
    for r in rows:
        sides = {x['side'].upper(): x['metrics'] for x in r['sides']}
        assert set(sides) == {'OVER', 'UNDER', 'COMBINED'}
        for s, m in sides.items():
            assert isinstance(m['WIN'], int) and isinstance(m['LOSS'], int)
            n = m['denominators']['decided']
            assert m['WIN'] + m['LOSS'] == n
            if n:
                assert abs(m['hit_rate'] - m['WIN'] / n) < 1e-12
            else:
                assert m['hit_rate'] is None
                empty += 1
        for k in ['WIN', 'LOSS']:
            assert sides['OVER'][k] + sides['UNDER'][k] == sides['COMBINED'][k]
        assert sides['OVER']['denominators']['decided'] + sides['UNDER']['denominators']['decided'] == sides['COMBINED']['denominators']['decided']
        triads += 1
    focal = []
    for method in ['S0', 'S1', 'S2']:
        for policy in ['P1_MEAN', 'P2_STATISTICAL_LAW']:
            r = next(x for x in rows if x['method'] == method and x['policy'] == policy and x['window'] == 'ALL')
            own = {}
            for x in r['sides']:
                m = x['metrics']
                own[x['side'].upper()] = {'wins': m['WIN'], 'losses': m['LOSS'], 'decided': m['denominators']['decided'], 'rate': m['hit_rate']}
            focal.append({'method': method, 'policy': policy, 'own_sides': own,
                          'probability_score_binding': 'Complete underlying law, not confidence inferred from this point policy',
                          'law_Brier': r['probability']['brier']})
    for policy, expected in [('P1_MEAN', [61, 53, 53]), ('P2_STATISTICAL_LAW', [59, 52, 57])]:
        actual = [next(x for x in focal if x['method'] == m and x['policy'] == policy)['own_sides']['COMBINED']['wins'] for m in ['S0', 'S1', 'S2']]
        assert actual == expected
    directories = read('REPORTS_DIRECTORY.json')
    assert len(directories) == 57
    names = [r['name'] for r in directories]
    assert not any('interception-history-closure' in x for x in names)
    current_specific_paths = [p for p in exports if 'interception-history-closure' in p.lower()]
    connector = read('CONNECTOR_READ_LEDGER.json')['reads']
    cli = [read('INDEX_FALLBACK_READ5.json'), read('INDEX_FALLBACK_READ6.json')]
    returned = sum(r['returned_bytes'] for r in connector) + sum(r['response_bytes'] for r in cli)
    assert sorted([r['read'] for r in connector] + [r['read'] for r in cli]) == list(range(1, 11))
    assert returned == 3114914 and returned <= 4194304
    result = {
        'id': 'C-INTERCEPTION-B-PUBLIC-RECEIPT-VERIFICATION-v1',
        'checked_UTC': datetime.now(timezone.utc).isoformat(),
        'status': 'PASS_RECEIVED_PUBLIC_ARITHMETIC;NEW_INT_AND_SELECTOR_REVIEW_RECEIPTS_NOT_LOCATED_IN_SCOPE',
        'research_ref': read('BRANCH_REF.json')['object']['sha'],
        'index_publication_clock': index['at_utc'],
        'exports_inspected': len(exports),
        'exact_index_source_bytes': len(index_raw),
        'exact_index_source_SHA256': digest(index_raw),
        'exact_index_git_blob_sha': '15b4bdd72dbfd75a50c3712c79726c8703d499da',
        'decoded_report_SHA256': digest(report_raw),
        'decoded_table_SHA256': digest(table_raw),
        'package_manifest_SHA256': digest(manifest_raw),
        'independent_side_triads': triads,
        'empty_side_rate_NA_checks': empty,
        'new_QB_depth_focal_records': focal,
        'new_INT_receipt_paths_in_index': current_specific_paths,
        'reports_directory_entries': len(directories),
        'missing_INT_receipt_scope': 'No matching assignment export or report directory at the inspected immutable B head. Not proof unshared/uncommitted or later B work is absent.',
        'not_a_regrade': 'Only supplied public table arithmetic and source-byte commitments checked. No prediction, threshold, source label, original selection or grade was recomputed.',
        'resources': {'bound_GitHub_reads': 10, 'response_bytes': returned,
                      'new_fits': 0, 'new_inference': 0, 'new_grading': 0,
                      'peer_writes_messages_dispatch': 0,
                      'CPU_seconds': time.process_time() - started,
                      'peak_RSS_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024}
    }
    (P / 'INDEPENDENT_ARITHMETIC_AND_BINDINGS.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'status': result['status'], 'triads': triads, 'empty_sides': empty,
                      'response_bytes': returned, 'fits_inference_grading': 0}))


if __name__ == '__main__':
    main()
