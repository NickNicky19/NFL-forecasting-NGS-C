"""Public receipt/consumer arithmetic only; no producer, selector, fit or grader."""
import hashlib
import json
import resource
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
NOW = datetime.now(timezone.utc).isoformat()

def read(n):
    return json.loads((P / n).read_text())

def sha(b):
    return hashlib.sha256(b).hexdigest()

def save(n, d):
    (P / n).write_text(json.dumps(d, indent=2, sort_keys=True) + '\n')

bundle=read('SOURCE_FOLLOW_THROUGH_BUNDLE.json')
main=read('SOURCE_MAIN_REF.json')['object']['sha']
comments=read('SOURCE_RECENT_COMMENTS.json')
latest=next(r for r in comments if r['id']==6814781492)
served=read('SERVED_READ_RECEIPTS.json')
overlay_pointer=read('SOURCE_CURRENT_OVERLAY_POINTER.json')
top_pointer=read('SOURCE_CURRENT_TOP_POINTER.json')
overlay=read('SERVED_OVERLAY_LEAF.json')
top=read('SERVED_TOP_LEAF.json')
meta=read('SERVED_META.json')
app=(P/'SERVED_APP.js').read_bytes()
assert sha(app)=='8aa97d75b8a444e4711e972535211208f8ee72414ad48b8840a17075c8a5b52f'
assert sha((P/'SERVED_OVERLAY_LEAF.json').read_bytes())==overlay_pointer['sha256']
assert sha((P/'SERVED_TOP_LEAF.json').read_bytes())==top_pointer['sha256']
assert meta==read('SOURCE_CURRENT_META.json')
assert main=='869d9a8839ae83dfccdb3bbb6610a0e0df867667'
assert overlay['state']=='DISABLED_USE_R0' and not overlay['rows']
assert len(top['picks']['over'])==len(top['picks']['under'])==12
assert 'const lean = selected ? effectiveGap?.lean : prop.lean;' in app.decode()
assert 'if (selected && !selected.binary) lean = selectedPropGap(p, prop, true)?.lean ?? null;' in app.decode()
assert next(x for x in served if x['name']=='MAE_DISPLAY')['HTTP_status']==404

# Verify public saved ranking payload arithmetic, without reselecting or reranking.
point_checks=[]
for side in ['over','under']:
    for r in top['picks'][side]:
        assert r['direction']==side and r['forecast_source']=='CURRENT_BASELINE'
        assert r['model_version']=='sleeper-matchup-classic-presence-strict-v2'
        scale=top['policy']['categories'][r['key']]['scale']
        score=(r['adj']-r['line'])/scale
        assert abs(score-r['score'])<1e-12
        assert (score>0)==(side=='over')
        point_checks.append({'player_id':r['player_id'],'game_id':r['game_id'],'category':r['key'],'side':side,'point':r['adj'],'line':r['line'],'line_from':r['line_from'],'scaled_gap':score,'source':r['forecast_source']})
save('CURRENT_RANKING_PAYLOAD_CHECK.json',{'schema':'C-FINAL-MILE-CURRENT-RANKING-CHECK-v1','observed_UTC':NOW,
    'status':'PASS_SAVED_PAYLOAD_FIELDS_AND_SCALED_GAP_ONLY','rows':point_checks,'rows_checked':24,
    'no_reselection_or_new_selector':True,'no_outcome_grade':True,
    'source_counts':dict(Counter(r['source'] for r in point_checks)),
    'quote_clocks_authenticated':False,'confidence_or_EV':None})

# Public aggregate checks are deliberately distinct from underlying pick verification.
contrib=bundle['selector_contributions']; weeks=contrib['weeks']; cum=contrib['cumulative']
assert [r['week'] for r in weeks]==[5,6,7,8]
keys=['hit','miss','push','dnp','unresolved','pending']
for r in weeks:
    assert r['candidate_generated_selected']+r['fallback_generated_selected']==24
    for k in keys:
        assert r['candidate_generated_results'][k]+r['fallback_generated_results'][k]==r['full_candidate_policy_results'][k]
    assert r['membership_symmetric_difference']==r['candidate_only_memberships']+r['control_only_memberships']
    assert r['membership_common_same_side']+r['candidate_only_memberships']==24
for name in ['candidate_generated_results','fallback_generated_results','full_candidate_policy_results','control_policy_results']:
    for k in keys: assert sum(r[name][k] for r in weeks)==cum[name][k]
assert [r['candidate_generated_selected'] for r in weeks]==[2,4,2,0]
assert [r['fallback_generated_selected'] for r in weeks]==[22,20,22,24]
assert cum['candidate_generated_results']['hit']==5 and cum['candidate_generated_results']['miss']==3
assert cum['full_candidate_policy_results']['hit']==50 and cum['control_policy_results']['hit']==48
save('SELECTOR_CONTRIBUTIONS.json',{'schema':'C-FINAL-MILE-SELECTOR-CONTRIBUTIONS-v1','source_comment':6814781492,
    'source_owner_receipt':contrib,'public_arithmetic_verdict':'PASS','source_membership_rows_checked_by_C':False,
    'source_selected_generated_tag_meaning':'Frozen reconstructed C source tag, not an invented learned/prior decomposition.',
    'full_system_scored_season_weeks':[[2026,w] for w in [5,6,7,8]],
    'W8_fallback_only_counts_as_full_system_week':True,
    'five_week_primary_status':'NOT_MET_4_FULL_SYSTEM_WEEKS',
    'no_new_replay_or_football_observations':True})

w4=bundle['W4_decision'];assert w4['archive_exists'] and w4['players']==539
assert 'proj_ppr for all539players' in w4['preserved_available_fields']
assert w4['save_after_every_game_kickoff']
save('W4_DECISION.json',{'schema':'C-FINAL-MILE-W4-DECISION-v1','status':'ASSESSED_UNQUALIFIED_THIS_ACCESSIBLE_ARCHIVE',
    'owner_receipt':w4,'superseded_claim':'PPR absent is incorrect for this539-player forecast archive; PPR exists on all539.',
    'C_scope':'Independent public aggregate/contract review; archive source not downloaded or raw-inspected by C in this package.',
    'not_a_global_archive_absence_claim':True,'not_a_zero_selection_week':True,
    'next_owner':'NFL-WEB-PRODUCTION-REPORT-INTEGRATION-20261025-122500Z; retained owner lease178 reported',
    'next_action':'Reopen only on genuine fullboard pregame/source-bound closure with exact missing gates and candidate recipe timing, otherwise capture the next qualified same-policy shadow through existing route; no invented W4 board or new selector.'})

research_path=ROOT/'docs/data/category-decisions-c06.json'
research_bytes=research_path.read_bytes();research=json.loads(research_bytes)
research_decisions={r['category']:r['decision'] for r in research['categories']}
records=[]
for r in bundle['LIVE_PRODUCT_BINDINGS']:
    r=dict(r)
    if r['category'] not in ['anytime_td','nick-chart-ppr-v1']:
        r['owner_reported_selected_override_direction']=r['category_direction']
        r['category_direction']='Current no-selected-row branch renders serialized prop.lean. selectedPropGap is the selected-only override and also serves filtering/sorting; edited customlines have an explicit margin branch.'
        r['active_baseline_trace']='app.propChip:selected ? effectiveGap?.lean : prop.lean; unedited detail starts prop.lean'
        r['selected_override_trace']='selected && !selected.binary -> selectedPropGap(...).lean; not activated by empty overlay'
    source=next(x for x in bundle['category_decisions'] if x['category']==r['category'])
    r['C_scientific_review_snapshot_decision']=research_decisions[r['category']]
    r['website_operational_candidate_disposition']=source['website_candidate_disposition']
    r['website_actual_primary']=source['actual_live_method']
    r['operational_effect']='No research activation; incumbent operational branch retained. Scientific SHADOW review does not mean public replacement.'
    records.append(r)
assert len(records)==12
for cat in ['pass_yd','rec_yd','rush_rec_yd']:
    r=next(x for x in records if x['category']==cat)
    assert r['C_scientific_review_snapshot_decision']=='SHADOW'
    assert r['website_operational_candidate_disposition']=='KEEP_INCUMBENT'
save('LIVE_BINDINGS.json',{'schema':'C-FINAL-MILE-WEBSITE-LIVE-BINDINGS-v1','observed_UTC':NOW,'main':main,
    'category_records':records,'scientific_review_snapshot':{'path':str(research_path.relative_to(ROOT)),'SHA256':sha(research_bytes),'scope':'Existing C research consumer snapshot, not a new master ranking.'},
    'source_overlay':{'state':overlay['state'],'rows':len(overlay['rows']),'SHA256':overlay_pointer['sha256']},
    'actual_served_meta':meta,'served_receipts':'SERVED_READ_RECEIPTS.json',
    'actual_saved_top_payload':{'rows':24,'over':12,'under':12,'research_rows':0,'policy':top['policy'],'SHA256':top_pointer['sha256']},
    'MAE_display_feed_status':404,'CountA_actual_consumer_active_rows':0,
    'new_C_browser_run':False,'owner_fresh_browser_scope':bundle['fresh_browser']['result'],
    'served_byte_checks_are_not_C_DOM_checks':True,'original_site_write_or_dispatch':False})

capture=bundle['fresh_baseline_capture']
assert capture['capture']['current_rows']==1614
assert capture['capture']['original_rows']==capture['capture']['paired']+capture['capture']['original_only']==2486
assert sum(capture['offer_limits']['captured_line_sources'].values())==1614
save('CURRENT_CAPTURE_RECEIPT.json',{'schema':'C-FINAL-MILE-INCUMBENT-CAPTURE-RECEIPT-v1','owner_receipt':capture,
    'C_independently_checked':'Public arithmetic, exact current immutable pointers and actual CA-verified served metadata/overlay/ranking/app bytes.',
    'C_not_checked':['Raw1614/2486 forecast packets','New originalsite browser rendering','Model fit/inference','Authenticated quote clocks'],
    'is_CountA_or_C_activation':False,'is_new_qualified_actual_offer_accuracy_evidence':False,
    'manual_success_not_scheduled_reliability':True})

owner='NFL-WEB-PRODUCTION-REPORT-INTEGRATION-20261025-122500Z; reported retained lease178'
actions=[{'task':'CountA native/current packet','executor':'Existing actual A native producer owner/PR88 executor, separate from C and website lease',
    'dependency':'Current source/query admission, exact corrected-mean native issuance/persistence and readable derived-feed bytes; source PR88 alone does not deliver.',
    'next_action':'Reuse existing native source integration/restoration under actual native lease; execute the authorized current packet/feed or name its exact enforced dependency. C does not duplicate PR88 execution.',
    'completion':'Actual immutable corrected-mean feed with source/model/corrector/role/cutoff/fallback/expiry and real issue/persistence clocks.'},
    {'task':'CountA original-site consumer','executor':owner,'dependency':'That exact current readable native feed plus product admission evidence',
    'next_action':'Retrieve complete corrected-mean outputs; check exact FORECASTS.point/corrector once, live/source policy and isolated tested consumer, then admit only if eligible.',
    'completion':'Recorded receipt/admission and actual intended served values/labels/fallback, independently of TopPicks.'},
    {'task':'Fifth selector policy week','executor':owner,'dependency':'Qualified new fullboard/current recipe or genuine retained missing-gate closure; W4 inspected archive rejected',
    'next_action':'Use existing frozen same-policy shadow capture at actual eligible cutoff, or inspect only genuinely newly supplied W4 closure.',
    'completion':'Fifth exact-policy scored season-week with actual fullboard/decision clocks and scoped B verification; no automatic primary promotion.'}]
save('FINITE_OWNER_ACTIONS.json',{'schema':'C-FINAL-MILE-WEBSITE-ACTIONS-v1','actions':actions,
    'CountA_existing_coordination':bundle['Count_A_coordination'],
    'website_owner_last_operator_ack_check':bundle['Count_A_post_request_check'],
    'native_current_PR88_status':'UNKNOWN_IN_THIS_C_WEBSITE_SCOPE; owned by separate actual native execution task. Oldfa919 unimplemented report is an as-of04:37 receipt, not a current native assertion.',
    'no_extra_current_input_dependencies':'CountA minimum38QB count/support inputs; EPA/PBP/defensive workbook not automatically required. Future query does not need final outcome.',
    'no_external_permission_request_from_C':True})

save('ADMISSION.json',{'schema':'C-FINAL-MILE-WEBSITE-ADMISSION-v1','prepared_UTC':NOW,
    'status':'RECEIVED_AND_VERIFIED_PUBLIC_ARITHMETIC_AND_ACTUAL_SERVED_FEED_SCOPE',
    'source_comment':{'id':latest['id'],'created_at':latest['created_at'],'updated_at':latest['updated_at'],'body_SHA256':sha(latest['body'].encode())},
    'latest_returned_comment_ids':[r['id'] for r in comments],
    'head':main,'new_originalsite_capture':{'rows':1614,'original_reference_rows':2486,'provider_run':43155203267,'generated_UTC':'2026-11-12T04:31:02Z','data_commit':main,'research_model_activation':False},
    'actual_current_consumer':{'model':'sleeper-matchup-classic-presence-strict-v2','overlay_state':'DISABLED_USE_R0','research_overlay_rows':0,'top_rows':24,'top_source':'CURRENT_BASELINE/reference_point','optional_numerical_feed_HTTP':404,'CountA_admitted_active_rows':0},
    'selector':{'status':'EXECUTED_4_CONDITIONAL_RETROSPECTIVE_POLICY_WEEKS','control':[48,45,93],'candidate':[50,43,93],'selected_each':96,'unknown_each':3,
        'candidate_generated_selected_by_week':[2,4,2,0],'fallback_selected_by_week':[22,20,22,24],'added_membership_by_week':[2,4,2,0],'removed_membership_by_week':[2,4,2,0],
        'generated_and_membership_counts_separately_reported_and_reconciled':True,'generated_W_L_U':[5,3,0],'fallback_W_L_U':[45,40,3],
        'W8_fallback_only_counts_as_fourth_policy_week':True,'fifth_status':'W4_ARCHIVE_ASSESSED_UNQUALIFIED_NOT_MISSING_GLOBAL_PROOF','new_replay_by_C':False},
    'CountA':{'source_corrector_publication':'ALREADY_RECEIVED_NOT_REPEATED','source_PR88_is_delivery':False,'native_current_status':'SEPARATE_ACTUAL_EXECUTOR_NOT_RECHECKED_HERE','website_current_typed_feed_retrieval_receipt':'NOT_OBSERVED','website_consumer_admission':'NOT_OBSERVED','actual_current_overlay_CountA_rows':0,'wrong_field_substitution_allowed':False},
    'scientific_SHADOW_versus_operational_KEEP':['pass_yd','rec_yd','rush_rec_yd'],
    'independent_C_scope':['Public receipt transport/hash and aggregate arithmetic','Actual CA-verified served meta/overlay/ranking/app bytes','24 saved payload scalar score/direction/source checks without reselection'],
    'not_verified_by_C':['Underlying192 historical membership/grades','Original source publication clocks','Rawcurrent1614/2486 captures','New original-site DOM/mobile run','Native CountA producer implementation/current source/inference'],
    'new_fits':0,'new_inference':0,'new_selector_executions':0,'original_site_mutations':0,
    'receipts':{'current':'LIVE_BINDINGS.json','capture':'CURRENT_CAPTURE_RECEIPT.json','selector':'SELECTOR_CONTRIBUTIONS.json','W4':'W4_DECISION.json','queue':'FINITE_OWNER_ACTIONS.json'}})

entries=read('CONNECTOR_READ_ACCOUNTING.json')['entries']
for r in entries:
    raw=(P/r['retained_path']).read_bytes();r['normalized_SHA256']=sha(raw[:r['normalized_bytes']]);r['retained_bytes']=len(raw);r['retained_SHA256']=sha(raw)
for r in served:
    entries.append(dict(r,normalized_bytes=r['bytes']))
total=sum(r['normalized_bytes'] for r in entries)
assert len(entries)==10 and total<=8388608
save('READ_LEDGER.json',{'schema':'C-FINAL-MILE-WEBSITE-READ-LEDGER-v1','finalized_UTC':NOW,'reads':10,'normalized_bytes':total,'entries':entries,
    'unused_registered_reads':2,'no_polling':True,'terminal_current_route_pass_complete':True,
    'helper_failure':'New receipt fenced block is rawbase64(XZ), notJSON transport. Initial JSON parsing failed locally; decoded as documented, verified both exact hashes; no refetch.'})
usage=resource.getrusage(resource.RUSAGE_SELF)
save('RESOURCE_RECEIPT.json',{'schema':'C-FINAL-MILE-WEBSITE-RESOURCE-v1','prepared_UTC':NOW,'reads':10,'normalized_bytes':total,
    'verification_script_CPU_seconds':usage.ru_utime+usage.ru_stime,'verification_script_max_RSS_KiB':usage.ru_maxrss,
    'registered_plan':'READ_PLAN.json','new_fits':0,'new_inference':0,'new_selector_replay':0,'code_or_originalsite_writes':0})
print(json.dumps({'status':'PASS','reads':10,'normalized_bytes':total,'current_overlay_rows':0,'current_top_rows':24,'generated_selected_by_week':[2,4,2,0]}))
