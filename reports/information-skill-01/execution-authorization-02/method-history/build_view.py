"""A bounded materialized reporting view of existing aggregate registries.

No model/source/archive recovery, fit, inference, or grader is invoked.
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

ENTRY = time.process_time()
ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
CATEGORIES = ['pass_yd','pass_td','pass_cmp','pass_att','pass_int','rush_yd',
              'rush_att','rec','rec_yd','rush_rec_yd','anytime_td','nick-chart-ppr-v1']
COMMIT = 'b0035adda3c38bd1b5e6770eb17c8ae24ad100ce'
sources, procedures, executions = {}, {}, []


def source(relative):
    path = ROOT / relative
    if relative not in sources:
        b = path.read_bytes()
        sources[relative] = dict(path=relative, bytes=len(b), SHA256=hashlib.sha256(b).hexdigest(),
            immutable_C_tree=None if relative.startswith('reports/information-skill-01/execution-authorization-02/') else 'https://github.com/NickNicky19/NFL-forecasting-NGS-C/blob/'+COMMIT+'/'+relative,
            binding_policy='New same-publication source; original immutable peer URLs are in the linked receipt' if relative.startswith('reports/information-skill-01/execution-authorization-02/') else 'Exact retained C base-tree reference')
    return path


def load(relative):
    path = source(relative)
    data = path.read_bytes()
    if relative.endswith('.gz'): data = gzip.decompress(data)
    return json.loads(data)


def category(value):
    # This alias is substantiated by CATEGORY_REGISTRY_V3's explicit scoring contract.
    return 'nick-chart-ppr-v1' if value == 'fpts' else value


def family_name(value):
    upper = str(value).upper()
    for token, name in [('SIGMOID','Earlier-season sigmoid calibration'),('CATBOOST','CatBoost retained procedure'),
                        ('BACKFIELD','Backfield conditional count/CDF'),('COUNT_A','Count A count-law/corrected mean'),
                        ('STUDENT','Signed Student-t distributional boosting'),('M3-1','XGBoostLSS marginal distribution'),
                        ('POISSON','Partially pooled Poisson'),('PARTIAL','Partially pooled Poisson'),
                        ('P2_LEAF','Empirical Leaf response law'),('LEAF','Empirical Leaf response law'),
                        ('P3_LOGIT','Regularized logistic threshold CDF'),('LOGIT','Regularized logistic threshold CDF'),
                        ('HGB-L1','HGB absolute-loss point forecast'),('HGB','Histogram boosting threshold/direct procedure'),
                        ('ALWAYS','Constant-side control'),('PREVALENCE','Earlier-only prevalence'),
                        ('P1_','Earlier-history point reference'),('INCUMBENT','Website incumbent'),
                        ('SLEEPER','Website provider/reference baseline')]:
        if token in upper: return name
    return 'Owner-labelled mechanism — '+str(value)[:100]


def add(owner, cat, pid, fam, record, relative, stage, product='SOURCE_TYPED_PRODUCTS'):
    cat = category(cat)
    if cat not in CATEGORIES: return None
    key = owner+'|'+cat+'|'+pid
    if key not in procedures:
        procedures[key] = dict(procedure_key=key, category=cat, owner=owner,
            origin_repository={'A':'NickNicky19/NFL-forecasting','B':'NickNicky19/NFL-forecasting-V2',
                               'C':'NickNicky19/NFL-forecasting-NGS-C','website':'NickNicky19/nicks-expert-nfl-picks'}.get(owner,'CONTROL'),
            family_id=owner+'::'+fam, family_name=fam, original_id=pid, aliases=[],
            predecessor='NOT_RETAINED_IN_THIS_EXTRACT', exact_difference='See source configuration/registration; not inferred from a renamed report',
            learner_objective_settings='SOURCE_LINKED;NOT_RECONSTRUCTED_FROM_ALIAS',
            input_groups_source_timing='SOURCE_LINKED;unknown clocks are not authenticated',
            history_update_preprocessing='SOURCE_LINKED', roles='SOURCE_LINKED',
            information_path='NOT_RETAINED_UNLESS_EXPLICIT_IN_SOURCE',
            product_types=[], milestones=[], verification_scope='C reporting extraction of existing public-safe metadata/aggregates; not independent fit or private-row reproduction',
            scientific_disposition='SOURCE_LINKED;do not infer gain from execution',
            five_week_admission='PRODUCT_SPECIFIC_SOURCE_LINKED;not inferred from training or numerical origins',
            current_query_readiness='NOT_RETAINED_IN_THIS_EXTRACT', original_site_deployment='NOT_ESTABLISHED_BY_THIS_EXTRACT',
            responsible_owner_action='Original owner supplies/qualifies missing bindings and current operational route',
            source_records=[])
    p = procedures[key]
    if stage not in p['milestones']: p['milestones'].append(stage)
    if product not in p['product_types']: p['product_types'].append(product)
    ref=dict(path=relative, record=record)
    if ref not in p['source_records']:p['source_records'].append(ref)
    return p


def csv_source(relative, kind):
    with source(relative).open() as f:
        for index, row in enumerate(csv.DictReader(f), 2):
            cat = category(row.get('target',row.get('category')))
            if kind == 'all12':
                pid='C-ALL12-v2.1::'+cat+'::'+row['history']+'::'+row['family']+'::'+row['arm']
                family=family_name(row['family'])
            elif kind == 'hgb':
                pid='C-HGB-L1-v1::'+cat+'::'+row['arm'];family=family_name('HGB-L1')
            elif kind == 'calibration':
                pid='C-OOF-v3::'+cat+'::'+row['policy'];family=family_name('SIGMOID') if 'SIGMOID' in row['policy'] else family_name('P2_LEAF')
            else:
                version=row.get('method_version',row.get('method',row.get('method_id','UNSPECIFIED')))
                policy=row.get('policy_id','SOURCE_POLICY')
                pid='C-ACTUAL::'+str(version)+'::'+policy
                family=family_name(version)
            p=add('C',cat,pid,family,{'CSV_data_row':index,'original_test_id':row.get('test_id')},relative,
                  'NUMERICAL_OR_EVENT_SCORED' if kind in ['all12','hgb','calibration'] else 'ACTUAL_LINE_VIEW_OR_EXPLICIT_NO_OFFER_CELL',
                  'NUMERICAL_AND_SYNTHETIC_GRID' if kind in ['all12','calibration'] else 'NUMERICAL_POINT' if kind=='hgb' else 'EXACT_LINE_DIRECTION')
            if p is None:continue
            execution_id=relative+'#row='+str(index)
            retained=row if row.get('horizon','ALL')=='ALL' else {k:row[k] for k in ['season','horizon','queries','outcomes','games','weeks','unknown','fallback_queries'] if k in row}
            executions.append(dict(execution_id=execution_id,procedure_key=p['procedure_key'],source_path=relative,
                                   original_test_id=row.get('test_id'),retained_aggregate=retained,full_record_location=execution_id,
                                   new_observation=False, grade_version='SOURCE_RETAINED_NOT_RECOMPUTED'))


def roster(relative, rows):
    for index, row in enumerate(rows):
        pid=row.get('procedure_id',row.get('arm','UNSPECIFIED'));cat=row.get('category','pass_cmp' if 'TEAM-COMPLETION' in pid else 'rec')
        owner=row.get('owner',row.get('origin_session','C'))
        owner='website' if owner in ['website','Website'] else owner
        fam=family_name(row.get('learner_family',row.get('family',pid)))
        if 'TARGETSHARE' in pid:fam='Receiver target-share information in retained direct model'
        if 'TEAM-COMPLETION' in pid:fam='Team completion context information'
        p=add(owner,cat,pid,fam,{'item':index},relative,row.get('status',row.get('state','REGISTERED_RETAINED_PROCEDURE')),str(row.get('output',row.get('output_type','SOURCE_TYPED_PRODUCTS'))))
        if not p:continue
        for src,dest in [('history','history_update_preprocessing'),('role_scope','roles'),('decision_or_ranking_rule','decision_policy'),
                         ('selection_rule','decision_policy'),('fallback','fallback'),('abstention','abstention'),('information_cutoff','information_cutoff')]:
            if src in row:p[dest]=row[src]
        if 'source' in row:p['predecessor']=row['source']
        if 'feature_order' in row:p['feature_source_order']=row['feature_order']
        p['aliases']=list(dict.fromkeys(p['aliases']+row.get('original_id_aliases',[])))
        p['source_status']=row.get('status',row.get('state','NOT_RETAINED'))


def result_table(relative, wave):
    data=load(relative)
    for index,row in enumerate(data.get('rows',[])):
        cat=row.get('category');arm=row.get('arm');product=row.get('product','SOURCE_OUTPUT')
        pid=wave+'::'+str(arm)+'::'+product
        fam=family_name(arm)
        if wave=='C-M3-TARGETED' and str(arm).startswith('M3-'):
            fam='Empirical Leaf response law' if arm=='M3-0' else 'Feature-dependent negative-binomial boosting' if cat=='rec' else 'Signed Student-t distributional boosting'
        if wave=='C-INFORMATION-SKILL-01':fam='Partially pooled Poisson' if str(arm).startswith('R') else family_name('LEAF')
        p=add('C',cat,pid,fam,{'rows_index':index},relative,'ACTUAL_LINE_SCORED',product)
        if p:executions.append(dict(execution_id=relative+'#rows='+str(index),procedure_key=p['procedure_key'],source_path=relative,
                                    retained_aggregate=row,new_observation=False,grade_version='SOURCE_RETAINED_NOT_RECOMPUTED'))


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    registry=load('reports/CATEGORY_REGISTRY_V3.json')
    assert next(r for r in registry if r['id']=='fpts')['scoring_contract_id']=='nick-chart-ppr-v1'
    for relative,kind in [('reports/complete-v1/RESULTS_INDEX.csv','hgb'),('reports/all12-v2.1/SCORES.csv','all12'),
                          ('reports/robustness-v3/SCORES.csv','calibration'),('reports/actual-accuracy-v6/SCORECARD.csv','actual'),
                          ('reports/reliability-v8/CATEGORY_METHOD_SCORECARD.csv','actual'),('reports/predictive-C01/ACTUAL_LINE_SCORES.csv','actual')]:csv_source(relative,kind)
    frozen=load('reports/w1w9-comparison-closure-01/roster/FROZEN_ROSTER.json')
    roster('reports/w1w9-comparison-closure-01/roster/FROZEN_ROSTER.json',frozen['candidate_products'])
    extra=load('reports/w1w9-comparison-closure-01/roster/selected-policy-amendment-v1/ROSTER_AMENDMENT_V1_1.json')
    roster('reports/w1w9-comparison-closure-01/roster/selected-policy-amendment-v1/ROSTER_AMENDMENT_V1_1.json',extra.get('additional_candidate_records',[]))
    roster('reports/abc-championship/METHOD_ROSTER-v2-C-1.json',load('reports/abc-championship/METHOD_ROSTER-v2-C-1.json'))
    roster('reports/profile-increment-v2/METHOD_ROSTER_V2.json',load('reports/profile-increment-v2/METHOD_ROSTER_V2.json')['new_registered_contenders'])
    roster('reports/player-context-matchup-01/METHOD_ROSTER_AMENDMENT.json',load('reports/player-context-matchup-01/METHOD_ROSTER_AMENDMENT.json')['procedures'])
    roster('reports/predictive-C01/CANDIDATE_ROSTER.json',load('reports/predictive-C01/CANDIDATE_ROSTER.json')['arms'])
    timing=load('reports/profile-closure-next-02/METHOD_ROSTER_AMENDMENT.json')
    roster('reports/profile-closure-next-02/METHOD_ROSTER_AMENDMENT.json',[dict(r,category='rec',owner='C',family='LEAF',state='EXECUTED_TIMING_COMPARISON;EXPOSED;SOURCE_LINKED_DIRECTION_LOSS') for r in timing['arms']])
    result_table('reports/targeted-accuracy-w1w9-01/M3/scores/RESULTS.json.gz','C-M3-TARGETED')
    result_table('reports/information-skill-01/scores/RESULTS.json.gz','C-INFORMATION-SKILL-01')
    # Recent retained peer arithmetic is a contribution, not full owner lifetime history.
    for relative,owner,group in [('reports/information-skill-01/executed-receipts-gap-closure-01/intake/B_RECEIPT.json','B','own_side_cumulative'),
                                 ('reports/information-skill-01/predictive-value-next-01/intake/B_RECEIPT.json','B','full_window_own_records')]:
        d=load(relative)
        for i,row in enumerate(d.get(group,[])):
            cat=row.get('category',row.get('target','pass_cmp'));method=row.get('method',row.get('arm','SOURCE_METHOD'));product=row.get('policy',row.get('output','SOURCE_OUTPUT'))
            p=add(owner,cat,relative.split('/intake/')[0].split('/')[-1]+'::'+str(method)+'::'+str(product),family_name(method),{'group':group,'item':i},relative,'OWNER_LOCAL_AGGREGATE_RECEIVED;NOT_PRIVATE_FIT_PARITY',str(product))
            if p:executions.append(dict(execution_id=relative+'#'+group+'='+str(i),procedure_key=p['procedure_key'],retained_aggregate=row,new_observation=False,source_path=relative))
    for arm in ['C0','C1','C2']:
        p=add('C','rec','C-DYAD-MIX-VALUE-01/v2::'+arm,'Native passer-mixture × receiver-targeting interaction',{'arm':arm},
              'reports/information-skill-01/predictive-value-next-01/proposal/C_DYAD_MIX_V2.json','APPROVED_EXECUTION_AUTHORIZATION_02;CURRENT_RESULT_PENDING', 'DIRECT_THRESHOLD_CDF')
        p['scientific_disposition']='NOT_SCORED_AT_CATALOG_EXTRACTION;root appends completed/stopped pilot after execution'
    for name in ['A_RECEIPT.json','B_RECEIPT.json','WEBSITE_RECEIPT.json','A_PUBLIC_EXPORT_INDEX.json']:
        relative='reports/information-skill-01/execution-authorization-02/intake/'+name
        if (ROOT/relative).is_file():source(relative)
    for arm,fam in [('TABICLV2','Pinned pretrained TabICLv2 direct event classifier'),('LOGISTIC','Same-information logistic event classifier')]:
        p=add('B','pass_cmp','B-TABICLV2-CMP-DIRECT-PILOT-v1::'+arm,fam,{'arm':arm},
              'reports/information-skill-01/execution-authorization-02/intake/B_RECEIPT.json',
              'APPROVED_EXECUTION_AUTHORIZATION_02;NO_RUNTIME_RESULT_IN_RECEIVED_RECEIPT','EXACT_OFFER_EVENT_PROBABILITY_DIRECTION')
        p['scientific_disposition']='NOT_SCORED_IN_RECEIVED_PUBLIC_RECEIPT;B owner executes independently'
    refs=subprocess.run(['git','for-each-ref','--format=%(refname:short) %(objectname)','refs/heads'],cwd=ROOT,capture_output=True,text=True,check=True).stdout.splitlines()
    log=subprocess.run(['git','log','--all','--max-count=120','--format=%H %s'],cwd=ROOT,capture_output=True,text=True,check=True).stdout.splitlines()
    notes={
      'Empirical Leaf response law':{'relationship':'Empirical target counts in shared tree leaves mixed with registered role prior/tails','learner_settings':'Existing LeafModel:32ExtraTrees,depth8,minleaf30,seed1701;exact procedure/source may add input blocks','code':'src/laws_v2.py'},
      'Histogram boosting threshold/direct procedure':{'relationship':'Learn P(Y<=threshold|features); threshold monotonicity and exact event orientation retained','learner_settings':'Existing ThresholdModel MONOTONE_HGB32iterations/depth3/minleaf20/L2=10/seed1701; no implied mean from point-only export','code':'src/laws_v2.py'},
      'Regularized logistic threshold CDF':{'relationship':'Regularized logistic CDF with nonnegative threshold coefficient; earlier-fit transforms','learner_settings':'L2 retained objective and fixed threshold grid; exact settings in source','code':'src/laws_v2.py'},
      'HGB absolute-loss point forecast':{'relationship':'Shared HGB fits absolute-error objective on registered base/NGS blocks','learner_settings':'C0/C1/C2 inputs and configuration preserved in registered-v1; no probability inferred','code':'protocol/REGISTERED_V1.json'},
      'Earlier-season sigmoid calibration':{'relationship':'Fit sigmoid map of earlier out-of-time probabilities; apply frozen map later','learner_settings':'Earlier2025 calibration,raw2026control; failed/no-gaincalibration findings retained','code':'reports/robustness-v3/README.md'},
      'Partially pooled Poisson':{'relationship':'Poisson mean with regularized shared features and player/team/opponent effects','learner_settings':'Registered alpha0.1/maxiter120/tol1e-7; sparse groupfallback retained','code':'src/context_experiment_c01.py'},
      'Feature-dependent negative-binomial boosting':{'relationship':'Conditional reception mean and dispersion from fixed distributional booster','learner_settings':'Exact registered XGBoostLSS negative-binomial package; no claim all NB families fail','code':'reports/targeted-accuracy-w1w9-01/M3/REGISTRATION.json'},
      'Signed Student-t distributional boosting':{'relationship':'Discretized signed-yard CDF bin masses from conditional location/scale/tails','learner_settings':'Exact frozen Student-t recipe closed to tuning; saved-output grading may continue','code':'reports/targeted-accuracy-w1w9-01/M3/REGISTRATION.json'}
    }
    for p in procedures.values():
        if p['owner']=='C' and p['family_name'] in notes:
            p.update(notes[p['family_name']])
            if p['family_name']=='Earlier-season sigmoid calibration' and 'SIGMOID' in p['original_id']:
                p['scientific_disposition']='FAILED_CALIBRATION_RETAINED;NO_PRIMARY_REPLACEMENT'
        if p['original_id'].startswith('C-INFORMATION-SKILL-01'):
            p['scientific_disposition']='FROZEN_DIRECTION_SELECTION_NO_GAIN;MIXED_NUMERICAL_PROBABILITY;not unusedfeature'
    families={}
    for p in procedures.values():
        f=families.setdefault(p['family_id'],dict(family_id=p['family_id'],name=p['family_name'],owner=p['owner'],procedure_keys=[],categories=[]))
        f['procedure_keys'].append(p['procedure_key']);f['categories']=sorted(set(f['categories']+[p['category']]))
    limitations=['PARTIAL: owner-verified new lifetime A/B/website contributions have not been supplied to this local extractor; retained public imports do not authenticate their complete history.',
                 'A 8,072-alias historical inventory is referenced but not wholly materialized locally; inaccessible contenders are not tested losers.',
                 'Separate Astra studies, private chats/transcripts, restricted archives and deleted outputs were not accessed or recovered.',
                 'All identified procedures in the listed sources are included; source output/rank/period views are executions, not separate model families. Family labels derived from explicit tokens are descriptive grouping, not code-equivalence proof.',
                 'Unmerged branch contents were not exhaustively opened. C local refs and last120 commit metadata entries plus three actual substantive historical branch artifacts were inspected (BRANCH_COVERAGE.json); retained sources span early through current work.',
                 'No universal numerical/probability/direction/selection winner is inferred from incompatible panels. Best-supported products remain in the existing scoped category decision record.',
                 'W1–9 requested coverage is not actual coverage. Source rows retain true periods, unknowns, failed/infinite scores and fallback counts. Internal/synthetic-grid scores never become actual-offer weeks.',
                 'Long selector-policy details and all own-list results remain in existing compressed result tables; this view links those records rather than copying protected row membership. ALL-horizon numerical rows retain metrics; weekly raw metrics remain at exact source-file/data-row references, not copied into another giant table.',
                 'Historical metrics are preserved as original evidence; current audit/regrade/admission overlays remain authoritative, not overridden by this catalog.',
                 'Current-query/deployed/served state cannot be inferred from historical score rows; those unsupported fields remain NOT_RETAINED/NOT_ESTABLISHED.']
    selector_refs=['reports/targeted-accuracy-w1w9-01/M3/scores/SELECTIVE.json.gz','reports/information-skill-01/scores/SELECTIVE.json.gz','reports/player-context-matchup-01/TOPK_RESULTS.json.gz','reports/topk-reference-v9/ALL_COMMON_OFFER_METHODS.json']
    for r in selector_refs:source(r)
    bundle=dict(schema='C-METHOD-HISTORY-MATERIALIZED-REPORTING-VIEW-v1',created_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                completeness='PARTIAL',categories=CATEGORIES,sources=list(sources.values()),families=list(families.values()),procedures=list(procedures.values()),
                executions=executions,selector_result_sources=selector_refs,limitations=limitations,
                branch_metadata=refs,commit_metadata_count=len(log),commit_metadata_hash=hashlib.sha256('\n'.join(log).encode()).hexdigest(),
                source_trees='Retained C workingtree atbaseb003 plus listed historical reports; peer rows retain actual originowner and immutable references in source inventories',
                new_fits=0,new_scoring=0,new_source_requests=0,new_observations=0)
    payload=json.dumps(bundle,separators=(',',':'),allow_nan=False).encode()
    (OUT/'METHOD_HISTORY.json.gz').write_bytes(gzip.compress(payload,compresslevel=6,mtime=0))
    fields=['category','owner','family_id','family_name','original_id','product_types','milestones','verification_scope','scientific_disposition','source_records']
    with gzip.open(OUT/'PROCEDURES.csv.gz','wt',newline='',compresslevel=6) as f:
        writer=csv.DictWriter(f,fields);writer.writeheader()
        for p in procedures.values():writer.writerow({k:json.dumps(p[k],separators=(',',':')) if isinstance(p[k],(list,dict)) else p[k] for k in fields})
    text=['# Recoverable method history by category','',
          '**PARTIAL within the listed retained sources.** This is a reporting view, not a new evaluator, score, fit or promotion. Owner-verified full A/B/website histories remain distinct missing contributions. C’s approved pilot executes independently; this catalog does not spend its reserve.','',
          '[Machine detail: families → exact procedures → retained aggregate executions](METHOD_HISTORY.json.gz) · [Procedure CSV from the same view](PROCEDURES.csv.gz)','',
          f'This extract contains {len(families)} descriptive family groups, {len(procedures)} exact procedure/configuration records and {len(executions)} retained evaluation views. These are **not** that many independent methods, games or new tests. Original IDs, aliases and per-source records are retained.','',
          'Current best-supported numerical, probability, broad-direction and selected-policy choices remain scoped to [the existing category/product decisions](../../../category-decision-release-01/CATEGORY_PRODUCT_DECISIONS.json) and [the current common protocol](../../../abc-championship/CURRENT_PROTOCOL.json). Disconnected panels, empty denominators and inaccessible contenders do not establish a universal winner.','']
    for cat in CATEGORIES:
        ps=[p for p in procedures.values() if p['category']==cat];fs=sorted(set(p['family_id'] for p in ps))
        text += ['## '+cat,'','| Owner / family or mechanism | Exact procedures | Retained execution/status |','| --- | ---: | --- |']
        for fid in fs:
            group=[p for p in ps if p['family_id']==fid];states=sorted(set(s for p in group for s in p['milestones']))
            text.append('| '+families[fid]['owner']+' / '+families[fid]['name'].replace('|','/')+' | '+str(len(group))+' | '+'; '.join(states).replace('|','/')+' |')
        text += ['', 'Every procedure ID/configuration and its retained own-side/numerical/probability metrics, periods, coverage and source references are in the matching machine detail. N/A or NOT_RETAINED is deliberate where source fields do not support a value.','']
    text += ['## Source coverage and remaining gaps','']+['- '+v for v in limitations]+['','### Examined retained indexes and score sources','']+['- `'+s+'`' for s in sources]+['','No protected rows, model bodies, private locators or training context are republished. No quote clock, player participation, absent statistic, route, alignment or unavailable source vintage is invented. Runtime failures and strict reproduction failures remain separate from forecasting losses. Original/corrected versions stay linked through their retained source files.','']
    (OUT/'README.md').write_text('\n'.join(text))
    oldcsv=OUT/'PROCEDURES.csv'
    if oldcsv.exists():oldcsv.unlink()  # provisional uncompressed view replaced losslessly by gzip

    resource=dict(created_UTC=bundle['created_UTC'],status='EXTRACTED_PARTIAL_WITHIN_LISTED_SOURCES',source_count=len(sources),family_groups=len(families),procedures=len(procedures),execution_views=len(executions),
                  actual_script_process_CPU_seconds=time.process_time(),prior_extraction_pass_CPU_seconds=[1.43578825,1.440308098],known_preparation_read_CPU_disclosure='Read-only schema inspection consumed bounded additional process time (largest JSON schema read2.813813seconds); exact total not independently metered.',
                  conservative_total_reporting_CPU_charge=11,reporting_subtask_CPU_cap=12,pilot_CPU_used=0,pilot_completion_reserve_used=0,
                  no_network=True,no_new_fits=True,no_grader_or_rescoring=True,
                  bytes={p.name:p.stat().st_size for p in OUT.iterdir() if p.is_file()})
    (OUT/'EXTRACTION_RECEIPT.json').write_text(json.dumps(resource,indent=2)+'\n')
    assert time.process_time()<6,'EXTRACTION_PROCESS_CPU_CEILING'
    print(json.dumps(resource))


if __name__=='__main__':main()
