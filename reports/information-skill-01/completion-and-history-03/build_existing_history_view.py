"""Permitted reporting projection of existing history; never fit, infer or grade."""
import csv,gzip,hashlib,io,json,time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
D=Path(__file__).resolve().parent
OLD=ROOT/'reports/information-skill-01/execution-authorization-02/method-history/METHOD_HISTORY.json.gz'
def read(p):
    b=Path(p).read_bytes()
    return json.loads(gzip.decompress(b) if str(p).endswith('.gz') else b)
def encoded(x):return json.dumps(x,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def gz(p,x):Path(p).write_bytes(gzip.compress(encoded(x),mtime=0))
def save(p,x):Path(p).write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def binding(p):
    p=Path(p);b=p.read_bytes();return dict(path=p.relative_to(ROOT).as_posix(),bytes=len(b),SHA256=hashlib.sha256(b).hexdigest())
def cell(x):return json.dumps(x,ensure_ascii=False,separators=(',',':')) if isinstance(x,(list,dict)) else x

def main():
    cpu=time.process_time();wall=time.monotonic()
    bundle=read(OLD);web=read(D/'intake/WEBSITE_HISTORY.json.gz');br=read(D/'intake/B_RECEIPT.json');bthin=read(D/'intake/B_PUBLIC_CATEGORY_HISTORY_V1.json')
    oldweb=[p for p in bundle['procedures'] if p.get('owner')=='website']
    procedures=[p for p in bundle['procedures'] if p.get('owner')!='website']
    aliases=[]
    for p in oldweb:
        cat=p['category'];match=next((q for q in web['procedures'] if q.get('canonical_id')==p['original_id'] and q.get('category_links')==[cat]),None)
        aliases.append(dict(original_procedure_key=p['procedure_key'],original_source_unchanged=binding(OLD),canonical_owner_procedure_key=('website|'+match['inventory_id']) if match else None,status='REPLACED_GENERIC_DISCOVERY_ALIAS_WITH_OWNER_EXACT_PRODUCT' if match else 'GENERIC_DISCOVERY_ALIAS_NOT_PROOF_OF_EXACT_EVENT_OR_CHART_PRODUCT',not_additional_method=True))
    for w in web['procedures']:
        procedures.append(dict(procedure_key='website|'+w['inventory_id'],category_links=w['category_links'],category=w['category_links'][0] if len(w['category_links'])==1 else 'MULTI_CATEGORY_POLICY',owner='website',origin_repository=web['producer_repository'],family_id='website::'+w['family_id'],family_name=next((f['name'] for f in web['families'] if f['inventory_id']==w['family_id']),w['family_id']),original_id=w.get('canonical_id') or w['inventory_id'],aliases=w.get('aliases',[]),predecessor=w.get('predecessors','NOT_RETAINED'),exact_difference=w.get('difference_from_closest_predecessor','NOT_RETAINED'),learner_objective_settings=w.get('learner_objective','NOT_RETAINED'),input_groups_source_timing=dict(inputs=w.get('inputs'),timing=w.get('source_timing_requirements')),history_update_preprocessing=dict(history=w.get('history_update_rule'),preprocessing=w.get('preprocessing_correctors')),roles=w.get('role_scope'),product_types=[w.get('output_type','SEE_OWNER_PRODUCT')],milestones=w.get('milestones'),verification_scope=w.get('verification_scope'),scientific_disposition=w.get('scientific_disposition'),five_week_admission=w.get('five_week_status'),current_query_readiness=w.get('current_query_readiness'),original_site_deployment=w.get('state'),responsible_owner_action=w.get('remaining_owner_action'),source_records=w.get('source_refs'),selection_calibration_fallback=w.get('selection_calibration_fallback'),owner_exact_public_record=w,owner_source_binding=binding(D/'intake/WEBSITE_HISTORY.json.gz'),new_NFL_observation=False))
    assert len({p['procedure_key'] for p in procedures})==len(procedures)
    new_execution=[]
    for suffix,source_id in [('TABICLV2','TABICLV2_DIRECT'),('LOGISTIC','SAME_INFORMATION_LOGISTIC')]:
        key='B|pass_cmp|B-TABICLV2-CMP-DIRECT-PILOT-v1::'+suffix;p=next(p for p in procedures if p['procedure_key']==key)
        record=next(x for x in br['own_W7_records'] if x['procedure']==source_id)
        p['prior_extraction_milestones']=p['milestones'];p['milestones']=['PARTIAL_EXECUTED;W7_LEARNED;W5_W6_FALLBACK;W8_W9_COST_STOP_UNAVAILABLE']
        p['scientific_disposition']='PARTIAL_RESEARCH_SHADOW;NO_PRIMARY_REPLACEMENT;ONE_LEARNED_WEEK_NOT_FAMILY_VERDICT'
        p['verification_scope']='Published aggregate received and additive arithmetic checked; owner reported independent saved-row checks, no C individual-row or fit reproduction'
        p['five_week_admission']='NOT_MET:3system_scored_weeks_only1learned;W8_W9unavailable'
        p['owner_received_W7']=record;p['owner_received_system_populations']=br['populations'] if suffix=='TABICLV2' else 'Exact comparator complete-system totals NOT_RETAINED in received public report'
        p['runtime_exception']=br['runtime_source_reported'];p['responsible_owner_action']='B preserve frozen W7 and elapsed-wall exception; no new worker; any later request must cover complete remainder and all current ledgers/costs'
        new_execution.append(dict(execution_id='B_TABICL_RECEIVED_W7_'+suffix,procedure_key=key,source_path='intake/B_PUBLIC_AGGREGATE_CHECKPOINT_V1.md',original_test_id='B-TABICLV2-CMP-DIRECT-PILOT-v1',retained_aggregate=record,full_record_location='Owner frozen rows/context remain under permitted owner route; not received by C',new_observation=False,grade_version='OWNER_FROZEN_ORIGINAL_GRADES;NO_C_RESCORING'))
    families=[f for f in bundle['families'] if f.get('owner')!='website']
    for f in web['families']:
        families.append(dict(family_id='website::'+f['inventory_id'],name=f['name'],owner='website',procedure_keys=[p['procedure_key'] for p in procedures if p['owner']=='website' and p['family_id']=='website::'+f['inventory_id']],categories=f.get('targets',[]),owner_exact_public_record=f))
    for f in families:f['procedure_keys']=[p['procedure_key'] for p in procedures if p['family_id']==f['family_id']]
    website_exec=[dict(execution_id='website|'+e['inventory_id'],procedure_keys=['website|'+p for p in e.get('procedure_ids',[])],source_path='intake/WEBSITE_HISTORY.json.gz',retained_aggregate=e,new_observation=False,grade_version='OWNER_ORIGINAL_AND_CORRECTED_VERSIONS_SEPARATE;NO_C_REGRADING') for e in web['executions']]
    bundle.update(schema='EXISTING_RECOVERABLE_HISTORY_VIEW_COMPLETION03',completeness='PARTIAL_WITH_EXACT_OWNER_PUBLICATION_GAPS',procedures=procedures,families=families,executions=bundle['executions']+new_execution+website_exec,prior_view_binding=binding(OLD),generic_website_alias_supersession=aliases,
        owner_contributions=dict(A=read(D/'intake/A_RECEIPT.json'),B=dict(receipt=br,public_category_family_view=bthin,exact_configuration_export='NOT_PUBLISHED_OR_RECEIVED;NO_PRIVATE15683CONFIGURATION_ROWS_IMPORTED'),website=dict(receipt=read(D/'intake/WEBSITE_BODY_RECEIPT.json'),current_capture_receipt=read(D/'intake/WEBSITE_RECEIPT.json'),completeness=web['completeness'],category_assessments=web['categories'])),
        current_category_audit=read(D/'CATEGORY_AUDIT.json'),new_scoring=0,new_fits=0,new_inference=0,new_raw_source_GETs=0,new_observations=0,
        count_interpretation='Presentation groups/exact configurations/catalog views are not independent methods or NFL observations; B thin labels overlap retained imports and are NOT summed as new mechanisms.',
        exact_missing_contributions=['A new permitted method report/PUBLIC_METHOD_HISTORY_INDEX_V1 immutable body not received; full private catalog remains private','B full exact configuration JSON/CSV and PUBLICATION_ALLOWLIST_REVIEW_V2/publication receipt unreceived; only two thin public histories and aggregate checkpoint admitted','Private/deleted transcripts/restricted archives/Astra and unlocated original source vintages remain previous exact gaps'],
        closed_C_increment=dict(procedure='C-DYAD-MIX-VALUE-01/v2',state='CLOSED_EXACT_REPRESENTATION_LEARNER_INCREMENT_NO_GAIN;NO_FURTHER_TUNING',actual_weeks=[2,3],own_over=[38,22,60],own_under=[117,91,208],own_combined=[155,113,268],C0_available=272,C1_C2_available=295,extra_unknown_forecasts=23,substantive_value_splits=0,probabilities_identical=True,no_primary=True),
        scientific_package_resources='Original C600 and dedicatedC120 ledgers unchanged; report costs separate; no additional B/A/C scientific worker commissioned')
    gz(D/'METHOD_HISTORY.json.gz',bundle)
    fields=['procedure_key','category_links','owner','origin_repository','family_id','original_id','aliases','predecessor','exact_difference','learner_objective_settings','input_groups_source_timing','history_update_preprocessing','roles','product_types','milestones','scientific_disposition','verification_scope','five_week_admission','current_query_readiness','original_site_deployment','responsible_owner_action','execution_record_keys','detail_JSON_pointer']
    out=io.StringIO(newline='');writer=csv.DictWriter(out,fieldnames=fields);writer.writeheader()
    for i,p in enumerate(procedures):
        r={k:cell(p.get(k,'NOT_RETAINED')) for k in fields};r['category_links']=cell(p.get('category_links',[p.get('category')]));r['execution_record_keys']=cell([e['execution_id'] for e in bundle['executions'] if e.get('procedure_key')==p['procedure_key'] or p['procedure_key'] in e.get('procedure_keys',[])]);r['detail_JSON_pointer']='/procedures/'+str(i);writer.writerow(r)
    (D/'PROCEDURES.csv.gz').write_bytes(gzip.compress(out.getvalue().encode(),mtime=0))
    # All identified family labels remain visible; detailed exact procedures and executions share this single view.
    lines=['# Cross-session recoverable method history','', '**PARTIAL within the listed sources.** [Complete permitted machine view](METHOD_HISTORY.json.gz) · [Matching exact-procedure CSV](PROCEDURES.csv.gz) · [Category scientific audit](CATEGORY_AUDIT.md).', '',
        'This is the existing registry reporting view extended with actually received owner contributions. Ten generic website point aliases are replaced by exact owner records; two generic event/chart discovery aliases remain in the supersession trail. B family labels are not added to retained B imports as independent mechanisms. No new fits, games or grades result from this catalog.', '',
        'A’s reviewed new public index/report is not received. B’s public family/category views are received; its full exact configuration export and V2 publication review are not. The original-site owner’s complete listed public production-history metadata is received, with PARTIAL lifetime completeness and explicit source/quote/served limits. Existing inaccessible/private/Astra/deleted evidence remains a gap, not a tested loser.', '']
    bc={x['category']:x for x in bthin['categories']}
    for cat in bundle['categories']:
        lines += ['## '+cat,'', '[Audit narrative and named own-side results](CATEGORY_AUDIT.md#'+cat+'). Exact parameters, history, clocks, roles, results, controls, verification, failures and dispositions are preserved per procedure/execution in the machine view; unsupported fields remain NOT_RETAINED.', '', '| Owner / identified family or mechanism | Exact procedure records in this view | Evidence scope |','| --- | ---: | --- |']
        for f in sorted(families,key=lambda f:(f['owner'],f['name'])):
            pp=[p for p in procedures if p['family_id']==f['family_id'] and cat in p.get('category_links',[p.get('category')])]
            if pp:lines.append('| '+f['owner']+' / '+f['name'].replace('|','/')+' | '+str(len(pp))+' | Source-linked retained procedure/execution detail; family alone does not imply end-to-end scoring |')
        labels=bc.get(cat,{}).get('families',[])
        if labels:
            lines += ['', '**B owner public thin-view labels** (not independent additions to the rows above; full exact configuration/metric rows remain unreceived): '+ '; '.join(x['name'] for x in labels)+'.']
        lines += ['', 'Original-site source-specific assessments and exact active-vs-historical product identities: [received owner metadata](intake/WEBSITE_HISTORY.json.gz). Broader population or numerical evidence cannot fill this category’s missing actual-offer cells.', '']
    lines+=['## Sources, lineage and limits','', 'The prior C view remains unchanged at `4b8ac9dad92902d58a0526e7bf7c9bbbb1d1f0c9/reports/information-skill-01/execution-authorization-02/method-history/`. Its examined source indexes/branches, aliases, source records and correction trail are carried forward, not silently discarded. New source bytes/destinations/review scope are bound in [admission](ADMISSION.json) and [publication review](PUBLICATION_REVIEW.json).', '',
        'B exact public source: `NickNicky19/NFL-forecasting-V2@932c968ad8ee90774ada7fe9f2ae13e92c7b40f2`; original website: `NickNicky19/nicks-expert-nfl-picks@968ce0ecb63c33868ed1eeba8c030050deef3e25`. A last accessible scientific discovery pin remains `a4a46eb18865d3609c445a622f819d24a24f1b82`; no assertion that it is the current owner-local HEAD. No inaccessible contender is graded as a loss.', '',
        'Readable owner contributions are retained separately: [B](intake/B_PUBLIC_READABLE_HISTORY_V1.md), [website](intake/WEBSITE_HISTORY.md). Formula names, configurations and repeated execution views are not summed as independent methods. No universal leader is inferred from incompatible panels; use exact matching population/control records. This view authorizes no next fit or primary product.']
    (D/'METHOD_HISTORY.md').write_text('\n'.join(lines)+'\n')
    save(D/'HISTORY_BUILD_RECEIPT.json',dict(state='PASS_EXISTING_VIEW_ONLY',prior=binding(OLD),current=binding(D/'METHOD_HISTORY.json.gz'),CSV=binding(D/'PROCEDURES.csv.gz'),exact_procedure_records=len(procedures),legacy_generic_website_aliases_replaced=len(oldweb),website_owner_exact_procedures=len(web['procedures']),website_owner_execution_records=len(web['executions']),owner_B_new_learned_week_received=7,new_fits=0,new_grading=0,new_NFL_observations=0,CPU_seconds=time.process_time()-cpu,wall_seconds=time.monotonic()-wall,scope='Reporting projection only; not lifetime completeness, fit reproduction or new scientific allowance'))
    print(json.dumps(dict(procedures=len(procedures),families=len(families),execution_views=len(bundle['executions']),CPU=time.process_time()-cpu)))

if __name__=='__main__':main()
