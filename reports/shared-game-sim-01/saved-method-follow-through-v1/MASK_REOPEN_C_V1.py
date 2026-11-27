"""Reopen existing C availability/exclusion ordinals only; no outcomes or fits.

Inputs are the already-retained frozen C bodies. Outputs containing ordinals
and per-case exclusion metadata remain private. Public projection has only
counts, commitments, policy and explicit peer-verification limits.
"""
from __future__ import annotations
import collections,hashlib,json,resource,time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
PUB=Path(__file__).resolve().parent
PRIV=ROOT/'private/shared-game-sim-01'
OUT=PRIV/'mask-reconciliation-v1'
EXPECTED={
 'cases':'19ccf34b3037e1790ee3b2bf61d3357f33e63916779c2f36023a232f6a66ea18',
 'identity':'e01dfa51555680772144ed89bd6c26a62c135bb6d3795dae5e0976a81f816d0e',
 'predictions':'e44f25e8a9a53b30a0c2ced5d55daa9f8c85fcc13561eb836db8e3d34ae723c9',
}
PUBLISHED={
 'rec':('8a0b7aeaeafa260a2d63f2e0f40185de7599710831cdca5abdcef95636f6e963','276c31f35a4380b1278ad9c5dbf3fc28dce91c0b86d6879733eed74f69e650b5'),
 'rec_yd':('2995d71a621a0b6d224ec6c8078a413f135033efe3e94514e332b29394729358','0ebea032f5e7315edf948f9638230bd44548e248e1e399c84fc9f1688c18d9bc'),
}
def encoded(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def digest(b):return hashlib.sha256(b).hexdigest()
def read_bound(path,key):
 b=path.read_bytes()
 if digest(b)!=EXPECTED[key]:raise ValueError('FROZEN_'+key.upper()+'_BODY_MISMATCH')
 return b
def bind(path):
 b=path.read_bytes();return dict(path=str(path.relative_to(ROOT)),bytes=len(b),SHA256=digest(b))
def write(path,obj):
 path.parent.mkdir(parents=True,exist_ok=True);b=encoded(obj)+b'\n';path.write_bytes(b)
 if path.read_bytes()!=b:raise ValueError('PRIVATE_MASK_REOPEN_FAILED')
 return dict(bytes=len(b),SHA256=digest(b))
def main():
 cpu=time.process_time();wall=time.monotonic()
 cp=PRIV/'views/comparison_inputs/cases.jsonl';ip=PRIV/'identity_rows.json';pp=PRIV/'typed_all_predictions.json'
 cases=[json.loads(x) for x in read_bound(cp,'cases').splitlines()]
 identity=json.loads(read_bound(ip,'identity'));pred=json.loads(read_bound(pp,'predictions'))
 imap={r['case_id']:r for r in identity};ordinals={r['case_id']:i for i,r in enumerate(cases)}
 if len(ordinals)!=3474 or len(imap)!=3474:raise ValueError('CANONICAL_CASE_ID_NOT_UNIQUE')
 products=[];private_products=[];bycat={}
 for cat in ('rec','rec_yd'):
  masks=[]
  for output in ('MEAN_POINT','MEDIAN_POINT','LAW'):
   method=f'C-M3-v1.1::{cat}::M3-0::base::{output}';rows=pred[method]
   if {r['case_id'] for r in rows}!={r['case_id'] for r in cases if r['identity']['category']==cat}:raise ValueError('FULL_CATEGORY_FRAME_MISMATCH')
   available=sorted(ordinals[r['case_id']] for r in rows if r['available'])
   ids=sorted(r['case_id'] for r in rows if r['available'])
   oldhash=digest(json.dumps(ids,separators=(',',':')).encode())
   if len(available)!=638 or oldhash!=PUBLISHED[cat][0]:raise ValueError('EXISTING_C_MASK_REOPEN_MISMATCH')
   exclusions=[];reasons=collections.Counter();ident=collections.Counter();weekly=collections.defaultdict(lambda:collections.Counter())
   for row in rows:
    i=ordinals[row['case_id']];case=cases[i];q=case['identity'];reason=row.get('unavailable_reason')
    weekly[q['week']]['full_category']+=1
    if row['available']:weekly[q['week']]['available']+=1
    else:
     reasons[reason]+=1;ident[imap[row['case_id']]['status']]+=1;weekly[q['week']]['excluded']+=1
     exclusions.append(dict(case_ordinal=i,exclusion=reason,identity_status=imap[row['case_id']]['status'],role=q['position'],week=q['week']))
   record=dict(method=method,category=cat,available_case_ordinals=available,excluded=sorted(exclusions,key=lambda r:r['case_ordinal']))
   private_products.append(record);masks.append(available)
   products.append(dict(method=method,category=cat,full_category=len(rows),available=len(available),excluded=len(exclusions),available_sorted_case_ID_mask_SHA256=oldhash,available_ordinal_SHA256=digest(encoded(available)),unavailable_ordinal_reason_SHA256=digest(encoded(record['excluded'])),exclusions=dict(reasons),exclusion_identity_states=dict(ident),weekly=[dict(week=k,**v) for k,v in sorted(weekly.items())],peer_B_reported_available=671,peer_B_sorted_case_ID_mask_SHA256=PUBLISHED[cat][1],pair_scope='C_BODY_REOPEN_PASS;B_COUNT_AND_HASH_RETRIEVED;B_FIXED_ORDINAL_BODY_NOT_DELIVERED',intersection=None,C_only=None,B_only=None,comparison_state='AWAITING_B_EXACT_FIXED_SET_COMPARISON'))
  if masks[0]!=masks[1] or masks[0]!=masks[2]:raise ValueError('TYPED_C_PRODUCTS_AVAILABILITY_DIFFER')
  bycat[cat]=masks[0]
 private=dict(schema='C-EXISTING-RECEIVING-AVAILABILITY-ORDINALS-v1',full_canonical_case_SHA256=EXPECTED['cases'],full_frame_count=3474,products=private_products,scope='Availability/exclusion metadata only. No point/probability/line/book/source identities/outcomes; remains private pending existing approved exchange. No grade or prediction altered.')
 receipt=write(OUT/'C_AVAILABLE_EXCLUSIONS_V1.json',private)
 if json.loads((OUT/'C_AVAILABLE_EXCLUSIONS_V1.json').read_bytes())!=private:raise ValueError('PRIVATE_MASK_REOPEN_DIFFER')
 policy=dict(identity='Exact per-query UnicodeNFKDcasefoldalphanumeric name plus exact declared role; uniqueGSIS. No fuzzy/suffix matching. Current roster identity only; no currentteam/status.',source_ID_alias='Global per-source-ID alias union detects conflicts; cannot resolve an early row from later query alias.',team='Latest prior ordinary statistical-row team with strict prior kickoff+7days < reconstructed native kickoff−90minutes; team must be in target schedule. Unknown/missing/trade cannot be assumed playable.',join='Exact season/week/nativegame/GSIS; allowed WR/TE only, same savedposition and canonical team; LAR→LA franchise alias only.',fallback='Missing exact saved origin/identity remains unavailable; no anotherproduct or reference threshold substitute.',role_exclusion_precedence='Canonical identity unavailable is checked before role; reason counts are mutually exclusive adapter branches, not independent dimensions.',availability_policy_scope='Current-vintage reconstruction; not authentic pregame roster, injury, quote or issue-clock proof.',outcomes_used=False)
 report=dict(id='C-RECEIVING-CASE-MASK-REOPEN-v1',state='PASS_C_EXISTING_FIXED_MASK_REOPEN;PEER_SET_COMPARISON_PENDING',products=products,private_body=dict(**receipt,products=6,permitted_route='Existing approved private/reconstruction handoff only; not publicly uploaded',reopen='ACTUAL_DISK_BODY_PASS'),input_bindings=[dict(role=k,bytes=p.stat().st_size,SHA256=EXPECTED[k]) for k,p in [('cases',cp),('identity',ip),('predictions',pp)]],code_bindings=[bind(ROOT/'src/shared_game_sim01_controls.py'),bind(ROOT/'src/shared_game_sim01_inputs.py'),bind(ROOT/'src/shared_game_sim01_prepare.py'),bind(ROOT/'reports/shared-game-sim-01/readiness/inspect_identity_adapter.py'),bind(ROOT/'reports/shared-game-sim-01/readiness/IDENTITY_ORIGIN_READINESS.json'),bind(ROOT/'reports/shared-game-sim-01/roster/C_SHORTLIST.json')],identity_policy=policy,peer_review=dict(repository='NickNicky19/NFL-forecasting-V2',commit='e8c242b8ef60a24494296659b8c02d867f157cc5',C_mask_addendum='reports/shared-game-sim-01/B/saved-comparison-review-v1/C_MASK_SCOPE_ADDENDUM_V1.json',verifier='tools/verify_saved_ac_comparison_b_v1.py',private_identity_body_SHA256='990bd7fab9e65a20a640790c35800cf619d5bc5c34c6b6f93606defb38878cb1',private_identity_body_available_to_C=False),no_defect_demonstrated=True,no_changed_results=True,no_fit=True,no_source_collection=True,no_outcomes_opened=True,net_difference='671−638=33 is only a net count; intersection and each asymmetric difference are unknown until fixed Bset and Cset are compared.',next_action=dict(executor='B existing independent reviewer',artifact='Already-retained C availability ordinal/exclusion body and B original671 ordinalset through existing permitted route',action='Compare exact fixed sets on the same canonicalcaseSHA; report intersection/C-only/B-only and case-reason breakdown. No outcome-driven matching or changed inputset; no newfit/source/A task.',completion='Per target exact set counts/hash and reason reconciliation. Public raw source/case/outcome uploads remain prohibited.'),resource=dict(task='EXISTING_SAVED_METHOD_REPORTING_AND_RECONCILIATION;SEPARATE_FROM_SIM_EXECUTION',selected_CPU_cap=15,CPU_seconds=time.process_time()-cpu,wall_seconds=time.monotonic()-wall,peak_RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,network='4permitted Bpublicmetadata/code GETs, no rawfootball source collection',metering='Selected reopen/metadataworker only; preparation/connector/assistant overhead not fully metered; no SIM budget transfer.'))
 if report['resource']['CPU_seconds']>15:raise RuntimeError('MASK_REOPEN_CPU_LIMIT')
 write(PUB/'MASK_REOPEN_RESULT_V1.json',report)
 print(json.dumps(dict(state=report['state'],C_available_each_target=638,CPU=report['resource']['CPU_seconds'],private_body_bytes=receipt['bytes'])))
if __name__=='__main__':main()
