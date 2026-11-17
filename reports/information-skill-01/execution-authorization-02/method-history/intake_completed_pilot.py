"""Append the already-scored C pilot to the same reporting view; no scoring."""
from pathlib import Path
import csv
import datetime
import gzip
import hashlib
import io
import json
import re
import time

START=time.process_time()
D=Path(__file__).resolve().parent
ROOT=D.parents[3]
source_relative='reports/information-skill-01/execution-authorization-02/pilot/scores/RESULTS.json.gz'
source_path=ROOT/source_relative
table=json.loads(gzip.decompress(source_path.read_bytes()))
view_path=D/'METHOD_HISTORY.json.gz'
before=hashlib.sha256(view_path.read_bytes()).hexdigest()
view=json.loads(gzip.decompress(view_path.read_bytes()))
pilot=[(i,r) for i,r in enumerate(table['rows']) if str(r.get('arm',''))[:2] in ['C0','C1','C2']]
by_arm={code:[r for _,r in pilot if str(r['arm']).startswith(code)] for code in ['C0','C1','C2']}
assert all(any(r.get('week')=='ALL' for r in rows) for rows in by_arm.values())
updated=[];source_bindings=[]
for suffix in ['RESULTS.json.gz','SELECTIVE.json.gz']:
    path=source_path.parent/suffix
    if path.is_file():
        record=dict(path=str(path.relative_to(ROOT)),bytes=path.stat().st_size,
                    SHA256=hashlib.sha256(path.read_bytes()).hexdigest(),immutable_C_tree=None,
                    binding_policy='Same immutable publication as this catalog; no old-base URL invented')
        if not any(r['path']==record['path'] for r in view['sources']):view['sources'].append(record)
        source_bindings.append(record)
        if suffix=='SELECTIVE.json.gz' and record['path'] not in view['selector_result_sources']:
            view['selector_result_sources'].append(record['path'])
for code in ['C0','C1','C2']:
    matches=[p for p in view['procedures'] if p['owner']=='C' and p['original_id']=='C-DYAD-MIX-VALUE-01/v2::'+code]
    assert len(matches)==1
    p=matches[0];updated.append(p['procedure_key'])
    p['milestones']=['SAVED_CONTROL_REUSED' if code=='C0' else 'FITTED_PREDICTIONS_GENERATED',
                     'ACTUAL_LINE_SCORED_W2_W3;TIMING_UNVERIFIED_EXPOSED_DIAGNOSTIC']
    p['scientific_disposition']='UNCHANGED_STRONG_CONTROL_REUSED_NOT_NEW_FIT' if code=='C0' else 'NO_INCREMENTAL_DIRECTION_OR_PROBABILITY_GAIN;RESEARCH_SHADOW_ONLY_TWO_OFFER_WEEKS'
    p['verification_scope']='Already executed/scored owner result intake; this catalog performs no independent fit, inference or grading. Independent pilot check scope remains in the original phase evidence.'
    p['source_records'].append(dict(path=source_relative,record={'arm_prefix':code,'all_actual_scored_weeks':[2,3]}))
    p['actual_line_weeks']=[2,3]
    p['missing_2026_W1_W9_actual_offer_weeks']=[1,4,5,6,7,8,9]
    p['five_week_admission']='NOT_QUALIFIED:two actual-offer weeks; no primary promotion'
    p['current_query_readiness']='NOT_ESTABLISHED_BY_THIS_HISTORICAL_PILOT'
    p['original_site_deployment']='NOT_ACTIVATED_BY_THIS_PILOT'
    p['exact_difference']={'C0':'Exact saved P3 original32 HGB control, reused without refitting',
                           'C1':'Same HGB and original inputs plus frozen new dyad support indicators',
                           'C2':'C1 plus the passer-mixture-change × targeting-preference scalar; value and missing flag splits0'}[code]
    if code in ['C0','C1']:
        old=p['family_id'];p['family_id']='C::Histogram boosting threshold/direct procedure';p['family_name']='Histogram boosting threshold/direct procedure'
        p['family_aliases']=list(dict.fromkeys(p.get('family_aliases',[])+[old]))
        p['family_alias_evidence']='Exact approved pilot retained P3 source and unchanged HGB implementation; support-only augmentation is not a distinct learner family.'
        if code=='C0':p['aliases']=list(dict.fromkeys(p.get('aliases',[])+['C0_SAVED_P3','CONTROL_P3_DIRECT']))
    for index,row in pilot:
        if not str(row['arm']).startswith(code):continue
        eid=source_relative+'#rows='+str(index)
        assert not any(r['execution_id']==eid for r in view['executions'])
        view['executions'].append(dict(execution_id=eid,procedure_key=p['procedure_key'],source_path=source_relative,
                                      retained_aggregate=row,new_observation=False,
                                      grade_version='ORIGINAL_PILOT_SCORES_INTAKE_NOT_RECOMPUTED'))
families={}
for p in view['procedures']:
    f=families.setdefault(p['family_id'],dict(family_id=p['family_id'],name=p['family_name'],owner=p['owner'],procedure_keys=[],categories=[]))
    f['procedure_keys'].append(p['procedure_key']);f['categories']=sorted(set(f['categories']+[p['category']]))
view['families']=list(families.values())
view['current_C_pilot_result']=dict(source=source_relative,actual_line_weeks=[2,3],
    paired_decided=268,own_combined_wins=155,own_combined_losses=113,
    own_over_wins=38,own_over_losses=22,own_under_wins=117,own_under_losses=91,
    Brier=0.2641086577930243,log_loss=0.728988341457127,
    C0_available=272,C0_selected_unknown=4,C0_unavailable=23,
    C1_C2_available=295,C1_C2_selected_unknown=27,fallback=0,
    source_value_and_missing_flag_splits=0,incremental_substantive_gain=False,
    no_new_accuracy_or_primary_claim=True,
    qualification='Exact already-scored owner outputs, not a catalog rescore. Changed availability is distinct from substantive value; own-list selection records remain in the linked source.')
view_path.write_bytes(gzip.compress(json.dumps(view,separators=(',',':'),allow_nan=False).encode(),compresslevel=6,mtime=0))
fields=['category','owner','family_id','family_name','original_id','product_types','milestones','verification_scope','scientific_disposition','source_records']
stream=io.StringIO(newline='');writer=csv.DictWriter(stream,fields);writer.writeheader()
for p in view['procedures']:writer.writerow({k:json.dumps(p[k],separators=(',',':')) if isinstance(p[k],(list,dict)) else p[k] for k in fields})
(D/'PROCEDURES.csv.gz').write_bytes(gzip.compress(stream.getvalue().encode(),compresslevel=6,mtime=0))
readme=(D/'README.md').read_text();prefix=readme.split('## pass_yd',1)[0];suffix=readme.split('## Source coverage and remaining gaps',1)[1]
prefix=re.sub(r'This extract contains \d+ descriptive family groups, \d+ exact procedure/configuration records and \d+ retained evaluation views\.',f'This extract contains {len(families)} descriptive family groups, {len(view["procedures"])} exact procedure/configuration records and {len(view["executions"])} retained evaluation views.',prefix)
text=[prefix.rstrip(),'']
for cat in view['categories']:
    ps=[p for p in view['procedures'] if p['category']==cat];ids=sorted(set(p['family_id'] for p in ps))
    text+=['## '+cat,'','| Owner / family or mechanism | Exact procedures | Retained execution/status |','| --- | ---: | --- | --- |']
    for fid in ids:
        group=[p for p in ps if p['family_id']==fid];states=sorted(set(s for p in group for s in p['milestones']))
        text.append('| '+families[fid]['owner']+' / '+families[fid]['name'].replace('|','/')+' | '+str(len(group))+' | '+'; '.join(states).replace('|','/')+' |')
    text+=['','All exact IDs and retained metrics/periods/source locations are in the same machine view. Coverage gaps remain separate from methods.','']
text+=['## Source coverage and remaining gaps',suffix,
    '\n## Completed C passer-mixture pilot intake\n',
    'C0, C1 support-only and C2 value arms all score **155–113 /268 decided**: Over38–22, Under117–91; W2:74–58/132, W3:81–55/136. Brier0.2641086577930243 and event log loss0.728988341457127 are identical on those decided cases. The scalar and its missing flag have zero fitted splits. This exact information increment establishes no gain; it does not disprove all QB–receiver relationships.',
    'Full-system coverage differs: C0 has272/295available,4selectedunknown and23technicalunavailable; C1/C2 have295available and27selectedunknown. No unavailable forecast becomes an intentional abstention or a win. Complete own-list selection results remain in the linked frozen selector table; identical paired directions alone do not prove identical selection ability.',
    'C0 is explicitly the reused HGB control, not a new dyad learner/family. The experiment remains research/shadow with onlyW2–3actual lines, missingW1/W4–9, nofive-weekqualification or primaryactivation. [Original score source](../pilot/scores/RESULTS.json.gz) · [Original own-selection source](../pilot/scores/SELECTIVE.json.gz).']
# Correct the three-column separator, kept explicit to avoid a renderer mismatch.
text=[line.replace('| --- | ---: | --- | --- |','| --- | ---: | --- |') for line in text]
(D/'README.md').write_text('\n'.join(text))
receipt=dict(status='PASS_ALREADY_SCORED_PILOT_INTAKE',before_view_SHA256=before,
    final_view_SHA256=hashlib.sha256(view_path.read_bytes()).hexdigest(),
    families=len(families),procedures=len(view['procedures']),execution_views=len(view['executions']),
    added_existing_score_views=len(pilot),updated_procedures=updated,source_bindings=source_bindings,
    process_CPU_seconds=time.process_time()-START,conservative_reporting_CPU_charge=2,
    new_fits=0,new_scoring_or_grading=0,new_network=0,pilot_reserve_used=0,
    scope='Parent-approved2CPU reporting followup; no source/method/grade mutations, preserved quality-gap normalization and exact keys.')
(D/'PILOT_RESULT_INTAKE.json').write_text(json.dumps(receipt,indent=2)+'\n')
assert time.process_time()-START<1.7,'REPORTING_UPDATE_CPU_GUARD'
print(json.dumps(receipt))
