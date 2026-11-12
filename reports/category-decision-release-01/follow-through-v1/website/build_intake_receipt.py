"""Read-only public-receipt verification; never executes the production selector."""
import base64
import csv
import gzip
import hashlib
import json
import re
import resource
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
NOW = datetime.now(timezone.utc).isoformat()

def sha(b):
    return hashlib.sha256(b).hexdigest()

def read(n):
    return json.loads((P / n).read_text())

def save(n, v):
    (P / n).write_text(json.dumps(v, indent=2, sort_keys=True) + '\n')

def scoped(v):
    if isinstance(v, dict):
        return {k: scoped(x) for k, x in v.items()}
    if isinstance(v, list):
        return [scoped(x) for x in v]
    if isinstance(v, str):
        return v.replace('/tmp/NFL-CATEGORY-RELEASE-20261112/', 'OWNER_PUBLIC_RECEIPT_LOGICAL_ROOT/')
    return v

def blocks(d):
    return re.findall(r'```[^\n]*\n(.*?)```', d['body'], re.S)

c1, c2 = read('SOURCE_COMMENT_6812058949.json'), read('SOURCE_COMMENT_6812397309.json')
b = blocks(c1)
protocol = json.loads(b[0])
manifest = json.loads(b[4])
proof_bytes = gzip.decompress(base64.b64decode(manifest['proof_gzip_base64']))
assert sha(proof_bytes) == manifest['proof_uncompressed_sha256']
proof = json.loads(proof_bytes)
transport = json.loads(blocks(c2)[0])
review_gz = base64.b64decode(transport['data'])
review_bytes = gzip.decompress(review_gz)
assert sha(review_gz) == transport['gzip_sha256']
assert sha(review_bytes) == transport['uncompressed_sha256']
assert len(review_bytes) == transport['uncompressed_bytes']
review = json.loads(review_bytes)
save('PUBLIC_PROTOCOL.json', scoped(protocol))
save('PUBLIC_MANIFEST.json', scoped({k: v for k, v in manifest.items() if k != 'proof_gzip_base64'}))
save('CONDITIONAL_PREFIX_PROOF.json', scoped(proof))
save('SOURCE_TRANSPORT_VERIFICATION.json', {
    'code_executed': False,
    'fenced_block_SHA256': [sha(x.encode()) for x in b],
    'conditional_proof_decoded_SHA256': sha(proof_bytes),
    'review_gzip_SHA256': sha(review_gz),
    'review_decoded_SHA256': sha(review_bytes),
    'review_decoded_bytes': len(review_bytes),
    'review_files': list(review['files']),
    'raw_192_policy_pick_rows_delivered': False,
    'canonical_membership': manifest['canonical_membership'],
    'decoded_projection': 'Absolute owner staging prefixes replaced by logical-root labels; exact public comment bytes and decoded hashes retained.'
})

# Verify the declared sufficient schedule-boundary predicate from already local,
# hash-bound schedule bytes. This is not feature/model/replay reproduction.
schedule_rows = []
schedule_receipts = []
for item in proof['source_schedules']:
    relative = item['path'].split('/selector-inputs/C/', 1)[1]
    path = ROOT / relative
    raw = path.read_bytes()
    assert sha(raw) == item['sha256']
    rows = list(csv.DictReader(raw.decode().splitlines()))
    schedule_receipts.append({'path': relative, 'SHA256': sha(raw), 'rows': len(rows)})
    schedule_rows.extend(rows)
games = {}
for r in schedule_rows:
    if r['season'] != '2026' or r['game_type'] != 'REG' or not 1 <= int(r['week']) <= 8:
        continue
    k = datetime.fromisoformat(r['gameday'] + 'T' + r['gametime']).replace(tzinfo=ZoneInfo('America/New_York')).astimezone(timezone.utc)
    if r['game_id'] in games:
        assert games[r['game_id']] == k
    games[r['game_id']] = k
assert len(games) == proof['complete2026W1_W8sourcegames']
boundary_checks = []
for game, item in proof['games'].items():
    board = datetime.fromisoformat(item['board_clock'])
    target = datetime.fromisoformat(item['target_kickoff'])
    boundaries = sorted([g for g, k in games.items() if board <= k + timedelta(days=7) < target])
    predicate = board < target and item['fitted_origin_before_board'] and item['complete_weekly_source_census'] and not boundaries
    observed = item['status'] == 'RECONSTRUCTED_PREFIX_INVARIANT'
    assert bool(predicate) == observed, (game, boundaries, item)
    boundary_checks.append({'game_key': game, 'claimed_status': item['status'], 'independent_predicate': bool(predicate), 'boundary_count': len(boundaries)})
save('CONDITIONAL_PREFIX_CHECK.json', {
    'status': 'PASS_FOR_DECLARED_RECONSTRUCTION_PREDICATE_ONLY',
    'schedules': schedule_receipts, 'source_games': len(games),
    'proof_game_entries': len(boundary_checks),
    'invariant_entries': sum(x['independent_predicate'] for x in boundary_checks),
    'checks': boundary_checks,
    'not_checked': ['Original unavailable schedule bytes', 'Original explicit-unknown source header', 'Historical source publication clocks', 'Feature vectors', 'Fits or inference', 'Private selector membership or grades'],
    'qualifies_live_inputs_or_primary_release': False
})

def counts(w, l):
    return {'wins': w, 'losses': l, 'decided': w+l, 'rate': w/(w+l) if w+l else None}

weekly = []
for week, cw, vw, d, u, override in [(5,12,13,24,0,41),(6,11,12,23,1,35),(7,15,15,24,0,7),(8,10,10,22,2,0)]:
    weekly.append({'season': 2026, 'week': week, 'control': counts(cw,d-cw), 'candidate': counts(vw,d-vw),
        'control_selected': 24, 'candidate_selected': 24, 'unknown_each': u,
        'candidate_input_overrides_owner_reported': override,
        'candidate_generated_selected_owner_reported': 0 if week == 8 else None,
        'candidate_generated_selected_status': 'OWNER_REPORTED_ZERO_PUBLIC_ARITHMETIC_ADMITTED' if week == 8 else 'UNKNOWN_NOT_EXPORTED_PER_WEEK',
        'candidate_fallback_selected': 24 if week == 8 else None,
        'candidate_only_membership_count': None,
        'full_system_scored_policy_week': True,
        'candidate_generated_scored_week': False if week == 8 else None,
        'evidence': 'Owner-reported conditional retrospective aggregate; C independently checks sums, not private rows.'})
assert sum(x['control']['wins'] for x in weekly) == 48
assert sum(x['candidate']['wins'] for x in weekly) == 50
assert sum(x['control']['losses'] for x in weekly) == 45
assert sum(x['candidate']['losses'] for x in weekly) == 43
assert sum(x['unknown_each'] for x in weekly) == 3
assert sum(x['candidate_input_overrides_owner_reported'] for x in weekly) == 83
save('WEEKLY_CONTRIBUTION_TABLE.json', {'schema':'C-WEBSITE-WEEKLY-CONTRIBUTION-v1','weeks':weekly,
    'aggregate_candidate_generated_selected_owner_reported':8,
    'aggregate_candidate_generated_selected_weeks_owner_reported':3,
    'aggregate_candidate_fallback_selected_derived_from_owner_count':88,
    'candidate_only_memberships_owner_reported':8,'removed_control_memberships_owner_reported':8,
    'membership_changes_are_not_candidate_generated_counts':True,
    'learned_only_win_loss':None})
own = {'control': {'OVER':counts(22,23),'UNDER':counts(26,22),'COMBINED':counts(48,45)},
       'candidate': {'OVER':counts(21,24),'UNDER':counts(29,19),'COMBINED':counts(50,43)}}
for arm in own.values():
    assert arm['OVER']['wins'] + arm['UNDER']['wins'] == arm['COMBINED']['wins']
    assert arm['OVER']['losses'] + arm['UNDER']['losses'] == arm['COMBINED']['losses']
save('REPLAY_ARITHMETIC.json', {'schema':'C-REPLAY-ARITHMETIC-v1','own_records':own,
    'selected_each':96,'unknown_each':3,'decided_each':93,
    'candidate_minus_control_wins':2,'candidate_minus_control_percentage_points':100*2/93,
    'changed_memberships': {'candidate_only':{'wins':5,'losses':3}, 'removed_control_only':{'wins':3,'losses':5},
        'net_win_change':2, 'evidence':'Owner reported; underlying public rows unavailable.'},
    'uncertainty':'Four exposed week clusters; no supported replacement superiority, no learned-only gain inference, no confidence/EV/six-leg claim.'})

live = review['files']['LIVE_PRODUCT_BINDINGS.json']
overlay = read('SOURCE_CURRENT_OVERLAY_LEAF.json')
meta = read('SERVED_CURRENT_META_RECEIPT.json')
app_path = ROOT / 'reports/category-decision-release-01/website/CURRENT_APP_JS.decoded.js'
app_bytes = app_path.read_bytes()
assert sha(app_bytes) == live['app_sha256']
app_text = app_bytes.decode()
assert 'const lean = selected ? effectiveGap?.lean : prop.lean;' in app_text
assert 'if (selected && !selected.binary) lean = selectedPropGap(p, prop, true)?.lean ?? null;' in app_text
for item in live['categories']:
    if item['category'] in {'anytime_td','nick-chart-ppr-v1'}:
        continue
    item['owner_reported_selected_override_direction'] = item['direction']
    item['direction'] = 'Active baseline/no-selected-row branch renders serialized prop.lean; current research overlay has0rows. This receipt does not substitute selectedPropGap for that active baseline field.'
    item['direction_branches'] = {
        'baseline_current_active': 'propChip: selected ? effectiveGap?.lean : prop.lean; unedited prop detail starts prop.lean',
        'selected_override_if_admitted': item['owner_reported_selected_override_direction'],
        'custom_edited_line_detail': 'Recomputes margin from selected?.value ?? prop.adj against edited line; separate explicit user-edit branch.',
        'selectedPropGap_other_uses': 'Also filters/sorts; these uses do not prove baseline rendered lean is recalculated there.'
    }
    item['trace']['direction'] = 'app.propChip baseline serialized prop.lean; selected-only override app.selectedPropGap; prop detail explicit edited-line margin branch'
live['C_follow_through_verification'] = {
    'at_UTC':NOW,'source_main':read('SOURCE_MAIN_REF.json')['object']['sha'],
    'source_overlay_state':overlay['state'],'source_overlay_rows':len(overlay['rows']),
    'source_overlay_frozen_rows':len(overlay['frozen_rows']),
    'source_overlay_fallback_counts':overlay['fallback_counts'],
    'served_metadata':meta,'current_top_pointer':read('SOURCE_CURRENT_TOP_POINTER.json'),
    'actual_current_browser_repeated_by_C':False,
    'current_top_leaf_or_membership_fetched_by_C':False,
    'owner_browser_verification':'112 assertions at390/1280 via CA-verified served-byte replay; owner reports direct browser TLS ERR_CERT_AUTHORITY_INVALID; no TLS bypass.',
    'new_primary_research_activation_observed':False,
    'source_overlay_byte_SHA256':sha((P/'SOURCE_CURRENT_OVERLAY_LEAF.json').read_bytes()[:-1]),
    'scope':'Current immutable source pointers/overlay and actual served metadata; remaining rendered membership/value claims are owner receipt, not a new C browser check.'
}
live['C_follow_through_verification']['direction_branch_source'] = {'path':str(app_path.relative_to(ROOT)), 'SHA256':sha(app_bytes), 'source_main_unchanged':True,'lines':[1286,1287,1323,1324], 'correction':'Owner supplied direction strings describe selected-only override; active baseline consumes serialized prop.lean.'}
save('LIVE_PRODUCT_BINDINGS.json',live)

ca=read('SOURCE_COUNTA_EXTENSION.json')
save('COUNTA_OWNER_QUEUE.json',{'schema':'C-COUNTA-OWNER-QUEUE-v1','source_ref':'e88d979f70a6483b404e39532b0002400f87d005',
    'source_package':'PRODUCER_COUNTA_EXTENSION_PACKAGE_V1.json',
    'source_SHA256':sha((P/'SOURCE_COUNTA_EXTENSION.json').read_bytes()[:-1]),
    'identity':ca['identity'],'exact_callable':ca['exact_callable'],'executors':ca['executors'],
    'owner_reported_stages':ca['stages'],'native_branch_readback':read('SOURCE_NATIVE_A_BRANCH.json'),
    'superseding_fact':'Exact31195B corrector aa7c002506b57d7c1ca643f4236e5fb8b5132bebb00ad86720ee11221b6d9fb6 is publicly delivered at e88; old d7 source-absent status is superseded.',
    'next_executor':ca['executors']['native_child'],
    'next_action':'Actual authorized native producer integrates the additional template/runtime/hosted/archive/export binding without changing existing18-model slots/caps, admits candidate-specific current sources, issues corrected-mean point packet with actual persistence clocks, publishes derived feed; website owner verifies receipt/admission and isolated consumption.',
    'current_feed_or_activation_verified':False,'repeat_local_restoration_needed':False,
    'future_outcome_EPA_or_new_profile_required':False})

save('W4_DISPOSITION.json',{'schema':'C-W4-REPLAY-DISPOSITION-v1','status':'NO_SUPERSEDING_FIFTH_BOARD_RECEIPT_OBSERVED',
    'latest_owner_receipt_UTC':c2['updated_at'],
    'superseding_query_result_ids':[x['id'] for x in read('SOURCE_RECENT_COMMENTS.json')],
    'executor':'NFL-WEB-PRODUCTION-REPORT-INTEGRATION-20261025-122500Z, retained lease178',
    'missing':'Fifth authentic complete candidate board with games/snap/PPR/line/identity/source/as-of fields plus compatible candidate query-timing proof.',
    'prior_owner_assessment':'Private W1–7 vector archive lacks games/snap/PPR/decision-origin fields;14alternate local boards add only W7/W8. Owner-reported scope, not C raw archive inspection or proof no W4 archive exists anywhere.',
    'next_action':'Website owner qualifies one retained full W4 (or another fifth distinct scored block) board and exact frozen-policy inputs/timing, then executes existing owner replay; if unavailable return exact unavailable fields. C does not reconstruct a private board or rerun selector.',
    'no_newer_receipt_does_not_prove_no_owner_local_work':True,
    'full_system_weeks':[5,6,7,8],'W8_fallback_only_counts_as_policy_week':True,
    'five_week_status':'NOT_MET_4_DISTINCT_FULL_SYSTEM_WEEKS','new_primary_switch':False})

save('ADMISSION.json',{'schema':'C-WEBSITE-FOLLOW-THROUGH-ADMISSION-v1','prepared_UTC':NOW,
    'status':'ADMITTED_PUBLIC_AGGREGATE_ARITHMETIC_AND_CONDITIONAL_TIMING_PREDICATE_ONLY',
    'source_comments':[{'id':d['id'],'updated_at':d['updated_at'],'URL':d['html_url']} for d in [c1,c2]],
    'original_website_head':'ccfaa987f5416ca6abce2570f9fee8c4c41c1d3e',
    'procedure':protocol['id'],'output':'P1 expected_mean WR/TE receptions; complete frozen website selector with saved baseline fallback',
    'actual_scored_season_weeks':[[2026,w] for w in [5,6,7,8]],
    'replay_status':'EXECUTED_4_CONDITIONAL_RETROSPECTIVE_POLICY_WEEKS',
    'own_records':own,'selected_each':96,'unknown_each':3,
    'candidate_generated_selected':{'total_owner_reported':8,'weeks_owner_reported':3,'weekly':{'5':None,'6':None,'7':None,'8':0},'independently_row_verified':False},
    'membership_changes':{'candidate_only_owner_reported':8,'removed_control_owner_reported':8,'independently_row_verified':False},
    'full_system_fallback_selected':{'count_derived_from_owner_report':88,'W8':24},
    'five_week_status':'NOT_MET_4_POLICY_WEEKS;NO_FIVE_LEARNED_WEEKS_OR_PRIMARY_QUALIFICATION',
    'C_independent_scope':['Exact public source/transport hash checks','Own-side and weekly aggregate arithmetic','Schedule bytes and declared reconstructed no-boundary predicate','Current source overlay and served metadata'],
    'B_actual_verification_scope':'B receipt supplied separately to root; this C public package does not claim B private rows were inspected by C.',
    'unverified_scope':['Private192 policy-pick rows','Per-week selected-source distribution exceptW8 zero','Raw grades/membership','Actual original source clocks/header','Fit/inference parity','New live player browser values'],
    'CountA_status':'PUBLIC_CORRECTOR_AND_EXECUTABLE_ARITHMETIC_HANDOFF_RECEIVED;NATIVE_INTEGRATION_CURRENT_PACKET_FEED_CONSUMER_NOT_VERIFIED',
    'current_overlay_state':overlay['state'],'current_research_overlay_rows':len(overlay['rows']),
    'live_primary':'sleeper-matchup-classic-presence-strict-v2; exact chart product unavailable; per-product trace in LIVE_PRODUCT_BINDINGS.json',
    'decisions':{'TopPicks':'SHADOW_REPLAY_NOT_PRIMARY','CountA':'BLOCKED_NATIVE_INTEGRATION_AND_CURRENT_DELIVERY','original_website':'KEEP_EXISTING_OPERATIONAL_PRODUCTS_NO_RESEARCH_ACTIVATION_PROVEN'},
    'no_original_site_write_dispatch_or_comment':True,
    'receipts':{'weekly':'WEEKLY_CONTRIBUTION_TABLE.json','arithmetic':'REPLAY_ARITHMETIC.json','current':'LIVE_PRODUCT_BINDINGS.json','CountA':'COUNTA_OWNER_QUEUE.json','fifth_week':'W4_DISPOSITION.json','prefix':'CONDITIONAL_PREFIX_CHECK.json'}})

# A read is one actual source fetch; no retries/polling after the registered12.
entries=read('CONNECTOR_READ_ACCOUNTING.json')['entries']
files=['SOURCE_COMMENT_6812058949.json','SOURCE_COMMENT_6812397309.json','SOURCE_MAIN_REF.json',None,'SOURCE_TREE_RELEVANT.json','SOURCE_RECENT_COMMENTS.json','SOURCE_COUNTA_EXTENSION.json','SOURCE_NATIVE_A_BRANCH.json','SOURCE_CURRENT_OVERLAY_POINTER.json','SOURCE_CURRENT_TOP_POINTER.json','SOURCE_CURRENT_OVERLAY_LEAF.json']
for e,f in zip(entries,files):
    e['retained_source_or_projection']=f
    if f:
        raw=(P/f).read_bytes();e['retained_bytes']=len(raw);e['retained_SHA256']=sha(raw)
        e['retained_is_exact_normalized_response_plus_LF']=e['read']!=5
    if e['read']==4:e['note']='First comments page was oldest100, not newer receipts; irrelevant bodies not durably retained, consumed bytes counted.'
    if e['read']==5:e['note']='Complete2517-entry tree received; relevant path projection retained, not raw full tree.'
entries.append({'read':12,'URL':meta['URL'],'normalized_bytes':meta['bytes'],'retained_source_or_projection':'SERVED_CURRENT_META.json','retained_SHA256':meta['SHA256'],'observed_UTC':meta['observed_UTC'],'HTTP_status':200})
total=sum(e['normalized_bytes'] for e in entries)
assert len(entries)==12 and total<=8388608
save('READ_LEDGER.json',{'schema':'FOLLOW-WEBSITE-READ-LEDGER-v2','finalized_UTC':NOW,'reads_used':12,'normalized_bytes':total,'entries':entries,
    'no_further_reads':True,'helper_failures':['TextEncoder unavailable after first retainedfile write; corrected locally without source refetch.','Initial comments page returned oldest100; one since-filtered read then resolved latest receipts.'],'requests_max':12})

usage=resource.getrusage(resource.RUSAGE_SELF)
save('RESOURCE_RECEIPT.json',{'prepared_UTC':NOW,'new_GETs':12,'normalized_bytes':total,'registered_caps':read('READ_PLAN.json'),
    'verification_script_CPU_seconds':usage.ru_utime+usage.ru_stime,'verification_script_maxRSS_KiB':usage.ru_maxrss,
    'new_fits':0,'new_inference':0,'production_selector_executions':0,'original_site_mutations':0,
    'script_scope':'Receipt parsing, deterministic public arithmetic, hash checks, retained local schedule predicate; no model or grader.'})
print(json.dumps({'status':'PASS','source_reads':12,'normalized_bytes':total,'proof_entries':len(boundary_checks),'invariant_entries':sum(x['independent_predicate'] for x in boundary_checks),'receipt':'ADMISSION.json'}))
