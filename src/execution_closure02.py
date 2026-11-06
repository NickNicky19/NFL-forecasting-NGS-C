"""Bounded intake/qualification projection; uses the retained common scorer.

No football fit, new outcome, changed selector, or production-site replay.
Owner-local aggregate arithmetic is not private-row parity.
"""
import csv,gzip,hashlib,io,json,time,resource
from collections import Counter
from pathlib import Path
from abc_handoff_adapters_v2 import normalize_b

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/abc-championship/execution-closure-02'
IN=OUT/'intake'
CATS=['pass_yd','pass_td','pass_cmp','pass_att','pass_int','rush_yd','rush_att','rec','rec_yd','rush_rec_yd','anytime_td','fpts']

def read(p):
    b=p.read_bytes();return json.loads(gzip.decompress(b) if p.suffix=='.gz' else b)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,d):
    b=(json.dumps(d,separators=(',',':'),allow_nan=False)+'\n').encode();p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(gzip.compress(b,mtime=0) if p.suffix=='.gz' else b)
def bound(p):return dict(path=str(p.relative_to(ROOT)),SHA256=sha(p))
def sides(m):
    o=m.get('over',m.get('OVER'));u=m.get('under',m.get('UNDER'))
    if o is None or u is None:return None
    out={}
    for s,x in [('OVER',o),('UNDER',u)]:
        w,l=int(x['wins'] or 0),int(x['losses'] or 0);n=w+l;assert n==x['decided']
        r=x.get('rate',x.get('hit_rate'));assert r is None if not n else abs(r-w/n)<1e-10
        out[s]=dict(wins=w if n else None,losses=l if n else None,decided=n,rate=w/n if n else None,selected=x.get('selected'))
    w=sum(x['wins'] or 0 for x in out.values());l=sum(x['losses'] or 0 for x in out.values());n=w+l
    out['COMBINED']=dict(wins=w if n else None,losses=l if n else None,decided=n,rate=w/n if n else None,selected=m.get('COMBINED',{}).get('selected'))
    if m.get('decided') is not None:assert n==m['decided'] and w==m['correct']
    if m.get('COMBINED') is not None:assert n==m['COMBINED']['decided'] and w==(m['COMBINED']['wins'] or 0)
    return out
def a_records():
    records=[]
    for p in sorted(IN.glob('A_A_FIVE_WEEK_QUALIFICATION_V3__*.json.gz')):
        records.extend((r,p,i) for i,r in enumerate(read(p)['records']))
    descriptor=read(IN/'A_A_PROPER_SCORE_FIVE_WEEK_SUPPLEMENT_V2.json.gz')
    p=IN/('A_'+descriptor['content_reference']['file'])
    records.extend((r,p,i) for i,r in enumerate(read(p)['records']))
    assert len(records)==800
    amend=read(IN/'A_A_FIVE_WEEK_QUALIFICATION_AMENDMENT_V4.json.gz')
    corr={r['key_sha256']:r for r in amend['corrections']}
    four={r['key_sha256']:r['scored_weeks'] for r in amend['four_week_historical_views']}
    out=[]
    for r,p,i in records:
        k=r['key'];cat='fpts' if k['target']=='chart_ppr' else k['target'];weeks=sorted({(int(w['season']),int(w['week'])) for w in r['completed_scored_weeks']})
        assert len(weeks)==r['completed_scored_week_count']
        if r['key_sha256'] in four and weeks and all(y==2025 for y,w in weeks):
            weeks=sorted({(int(w['season']),int(w['week'])) for w in four[r['key_sha256']]})
        metrics=r.get('retained_aggregate_metrics',r.get('retained_metrics',{}));own=sides(metrics)
        support=r.get('weekly_support',r.get('weekly_score_support',[]))
        if own and support:
            for side in ['OVER','UNDER']:
                ww=[x[side.lower()] for x in support if side.lower() in x]
                if len(ww)==len(weeks):
                    assert sum(x['wins'] or 0 for x in ww)==(own[side]['wins'] or 0)
                    assert sum(x['losses'] or 0 for x in ww)==(own[side]['losses'] or 0)
        unsupported=r['key_sha256'] in corr
        floor='NOT_APPLICABLE' if unsupported else 'MET' if len(weeks)>=5 else 'NOT_MET'
        if r['key_sha256'] in four and weeks and all(y==2025 for y,w in weeks):assert len(weeks)==4 and floor=='NOT_MET'
        role=k['role_scope']
        if cat=='rush_att' and metrics.get('opportunities')==335:role='MIXED_POSITION_QB_RB_WR;335_OFFERS;NOT_RB_ONLY'
        wr=[]
        for w in support:
            n=w.get('scored',w.get('scored_eligible_cases'));eligible=w.get('eligible',w.get('eligible_or_opportunities',w.get('planned')))
            wr.append(dict(season=w['season'],week=w['week'],scored=n,selected=w.get('selected',eligible),eligible=eligible,states=w.get('states',{}),metrics={q:w[q] for q in ['MAE','MSE_or_event_Brier'] if q in w},sides=None,coverage=None))
        seasons=[]
        for y in sorted({y for y,w in weeks}):
            ww=[w for yy,w in weeks if yy==y];ss=[x for x in wr if x['season']==y]
            seasons.append(dict(season=y,scored_weeks=ww,scored_cases=sum(x['scored'] or 0 for x in ss),selected=sum(x['selected'] or 0 for x in ss),eligible=sum(x['eligible'] or 0 for x in ss)))
        out.append(dict(row_id='A-CLOSURE02-'+sha_key([r['key_sha256'],str(p.relative_to(ROOT)),i]),owner='A',procedure_id='A::'+k['procedure_version'],category=cat,product=k['output'],role_scope=role,history=k['history_rule'],policy=k['selection_policy'],source_panel=r.get('source','A_BOUND_PROPER_SCORE_OR_NUMERICAL_PANEL'),evidence_tier=r.get('evidence_tier'),scored_week_count=len(weeks) if not unsupported else 0,current_2026_scored_week_count=sum(y==2026 for y,w in weeks) if not unsupported else 0,tested_season_weeks=weeks if not unsupported else [],five_week_floor=floor,scored_cases=metrics.get('scored',metrics.get('decided')),week_records=wr,season_records=seasons,zero_selection_weeks=r.get('attempted_empty_or_unresolved_weeks',[]),unresolved_only_weeks=[],own_side_record=own,retained_metrics=metrics,metric=r.get('metric',r.get('kind')),method_alias=r.get('method_alias'),operational_export='OWNER_LOCAL_RESTORATION_VERIFIED;HOSTED_CURRENT_QUERY_AND_CONSUMER_BLOCKED' if 'f8607aa99a94c7c1c9ab5c89599e07eba9b15527749b092b225f368032881e83' in k['procedure_version'] else 'CURRENT_QUERY_DERIVED_EXPORT_NOT_VERIFIED_BY_INTAKE',remaining_gates='Private-row/source continuity and exact product admission remain; five weeks is duration only.',source_artifacts=[str(p.relative_to(ROOT))],source_record_index=i,source_key_sha256=r['key_sha256'],unsupported_output=unsupported,source_profile_status=r['five_week_floor']))
    return out
def sha_key(x):return hashlib.sha256(json.dumps(x,sort_keys=True).encode()).hexdigest()
def a3_profiles():
    p=IN/'A_A3_CONDITIONAL_RESULTS_V1.json.gz';d=read(p);out=[]
    for item in d['numerical_results']:
        if item['arm']!='A3_CONDITIONAL_PLAYED_EXPOSURE' or item['week']!='ALL':continue
        y=item['season'];weeks=[[y,w] for w in item['actual_weeks']]
        product='NUMERICAL_MAE' if item['product']=='median' else 'EXPECTED_MEAN_MSE'
        out.append(dict(row_id='A3-'+sha_key([y,item['product']]),owner='A',procedure_id='A::'+d['procedure_version'],category='rush_att',product=item['product'],role_scope='RB',history='Original earlier-only A3 conditional-played exposure; original controls unchanged',policy=product,source_panel='A_CARRY_RB239' if y==2026 else 'A_CARRY_2025_W5_W8',evidence_tier='OWNER_LOCAL_TIMING_UNVERIFIED_RECONSTRUCTED_ACTUAL_LINE_AND_NUMERICAL',scored_week_count=len(weeks),current_2026_scored_week_count=len(weeks) if y==2026 else 0,tested_season_weeks=weeks,five_week_floor='MET' if len(weeks)>=5 else 'NOT_MET',scored_cases=item['scored'],week_records=[],season_records=[dict(season=y,scored_weeks=item['actual_weeks'],scored_cases=item['scored'],selected=None,eligible=item['expected'])],zero_selection_weeks=[],unresolved_only_weeks=[],own_side_record=None,retained_metrics=item,metric=product,method_alias='A3_CONDITIONAL_PLAYED_EXPOSURE',operational_export='LOSING_RECIPE_CLOSED;NOT_PROMOTED',remaining_gates='No measured improvement; no new current producer or release admitted',source_artifacts=[str(p.relative_to(ROOT))],source_record_index=d['numerical_results'].index(item)))
    for item in d['actual_line_results']:
        if item['week']!='ALL':continue
        own=sides(item);weekly=[r for r in d['actual_line_results'] if r['policy']==item['policy'] and r['week']!='ALL' and r['COMBINED']['decided']>0];weeks=[[2026,int(r['week'])] for r in weekly]
        for s in ['OVER','UNDER']:
            assert sum(r[s]['wins'] or 0 for r in weekly)==(own[s]['wins'] or 0)
            assert sum(r[s]['losses'] or 0 for r in weekly)==(own[s]['losses'] or 0)
        out.append(dict(row_id='A3-'+sha_key(item['policy']),owner='A',procedure_id='A::'+d['procedure_version'],category='rush_att',product='mean' if item['policy']=='P1_MEAN' else 'median' if item['policy']=='P1_MEDIAN' else 'exact_line_probability',role_scope='RB',history='Original earlier-only A3 conditional-played exposure; original controls unchanged',policy=item['policy'],source_panel='A_CARRY_RB239',evidence_tier='TIMING_UNVERIFIED_RECONSTRUCTED_ACTUAL_LINE',scored_week_count=len(weeks),current_2026_scored_week_count=len(weeks),tested_season_weeks=weeks,five_week_floor='MET' if len(weeks)>=5 else 'NOT_MET',scored_cases=own['COMBINED']['decided'],week_records=[],season_records=[dict(season=2026,scored_weeks=[w for y,w in weeks],scored_cases=own['COMBINED']['decided'],selected=item['COMBINED']['selected'],eligible=item['eligible'])],zero_selection_weeks=[],unresolved_only_weeks=[],own_side_record=own,retained_metrics=item,metric='statistical_decisive_hit_rate',method_alias='A3_CONDITIONAL_PLAYED_EXPOSURE',operational_export='LOSING_RECIPE_CLOSED;NOT_PROMOTED',remaining_gates='Strong A1 and constant controls outperform this recipe; no promotion',source_artifacts=[str(p.relative_to(ROOT))],source_record_index=d['actual_line_results'].index(item)))
    assert len(out)==8
    return out
def b_profiles():
    p=IN/'B_B_PRODUCT_WEEK_QUALIFICATION.json.gz';profiles=read(p);assert len(profiles)==41404;out=[]
    for i,r in enumerate(profiles):
        weeks=sorted({tuple(w) for w in r['verified_scored_season_weeks']});assert len(weeks)==r['verified_scored_week_count']
        seasons=[dict(season=int(y),scored_weeks=x['weeks'],scored_cases=x['supported_cases'],selected=None,eligible=None) for y,x in r['per_season'].items()]
        out.append(dict(row_id=r['qualification_id'],owner='B',procedure_id='B::'+r['procedure_id'],category='fpts' if r['category'] in ['nick-chart-ppr-v1','chart_ppr'] else r['category'],product=r['product_id'],role_scope=r.get('position') or r.get('population'),history=r.get('history'),policy='::'.join(str(r.get(k)) for k in ['selection_rule','selected_side_view','K','rank_scope','fallback_view']),source_panel=r.get('horizon') or 'SOURCE_PROFILE_BOUND_PANEL',evidence_tier=r.get('source_vintage'),scored_week_count=len(weeks),current_2026_scored_week_count=sum(y==2026 for y,w in weeks),tested_season_weeks=[list(w) for w in weeks],five_week_floor='MET' if len(weeks)>=5 else 'UNESTABLISHED_AGGREGATE_ONLY' if r['minimum_week_floor_status'].startswith('UNESTABLISHED') else 'NOT_MET',scored_cases=sum(x['supported_cases'] for x in r['per_season'].values()),week_records=[],season_records=seasons,zero_selection_weeks=r.get('attempted_zero_or_unresolved_weeks',[]),unresolved_only_weeks=[],own_side_record=None,operational_export=r['operational_export_status'],remaining_gates=r['typed_contract_scope']+';'+r['qualification_limit'],source_artifacts=[str(p.relative_to(ROOT))],source_record_index=i,strongest_bound_model_control=r.get('strongest_comparator'),verified_support_is='Owner canonical weekly-profile support; not a new independent regrade or winner admission'))
    return out
def b_scores():
    names=['B_b-confidence-ordering-v1_SCORES.json.gz','B_context-ranker-v1_SCORES.json.gz','B_B-111-RB-common-mask-v3_SCORES.json.gz'];allrows=[];admissions=[]
    for name in names:
        p=IN/name;d=read(p)
        if 'context-ranker' not in name:
            ap=p.with_name(name.replace('SCORES','SOURCE_HORIZON_QUALIFICATION_V2'));a=read(ap)
            assert a['source_score_sha256']==hashlib.sha256(gzip.decompress(p.read_bytes())).hexdigest()
            for r in a['rows']:
                x=d[r['source_row_index']];assert x['record_id']==r['record_id'];x['horizon_id']=r['source_horizon_qualification']['horizon_id']
        else:
            a=read(IN/'B_context-ranker-v1_METADATA_QUALIFICATION_V2.json.gz');assert a['current_scores']['sha256']==hashlib.sha256(gzip.decompress(p.read_bytes())).hexdigest() and a['current_scores']['rows']==len(d)
        normalized=normalize_b(d,name)
        allrows.extend(normalized);admissions.append(dict(source=bound(p),state='ADMITTED_PUBLIC_OWNER_LOCAL_AGGREGATE_ARITHMETIC_AND_BOUND_METADATA',normalized_views=len(normalized),raw_rows=len(d),raw_row_or_model_access=False,independent_reinference=False))
    write(OUT/'B_ADMITTED_SCORE_VIEWS.json.gz',allrows);return admissions
def recommendation(rank):
    return 'FIVE_WEEK_ELIGIBLE_CATEGORY_REVIEW_CANDIDATE;CURRENT_EXPORT_AND_SOURCE_ADMISSION_REQUIRED' if rank else 'NOT_ESTABLISHED_ON_THIS_PANEL'
def decisions(a):
    out=[];ranks=[]
    for cat in CATS:
        for product in ['NUMERICAL_MAE','EXPECTED_MEAN','ACTUAL_LINE_DIRECTION','OUTCOME_DISTRIBUTION','PROBABILITY','TOP_PICKS']:
            policies={'NUMERICAL_MAE':['NUMERIC_MAE'],'EXPECTED_MEAN':['EXPECTED_MEAN_MSE'],'ACTUAL_LINE_DIRECTION':['FULL_PRIMARY_ROSTER_INTERSECTION_RECORDED_BOARD'],'OUTCOME_DISTRIBUTION':['PROPER_DISTRIBUTION_SCORE'],'PROBABILITY':['EVENT_PROBABILITY','PROPER_EXACT_LINE_PROBABILITY_SCORE'],'TOP_PICKS':[]}[product]
            q=[r for r in a if r['category']==cat and r['policy'] in policies and not r['unsupported_output'] and r['current_2026_scored_week_count']>=5]
            # No pooling across populations or horizons: each exact support panel has its own observed leader.
            groups={}
            for r in q:
                m=r['retained_metrics'];support=(m.get('scored',m.get('decided')),m.get('planned',m.get('opportunities')),m.get('games'),str(r['role_scope']))
                if product=='ACTUAL_LINE_DIRECTION':value=r['own_side_record']['COMBINED']['rate'] if r['own_side_record'] else None
                elif product=='NUMERICAL_MAE':value=m.get('MAE')
                elif product=='EXPECTED_MEAN':value=m.get('MSE')
                elif product=='OUTCOME_DISTRIBUTION':value=m.get('CRPS',{}).get('value')
                else:
                    value=m.get('Brier',m.get('brier',m.get('event_Brier',m.get('MSE') if r['policy']=='EVENT_PROBABILITY' else None)))
                    if isinstance(value,dict):value=value.get('value')
                if value is not None:groups.setdefault(support,[]).append((value,r))
            leaders=[]
            for support,items in groups.items():
                best=(max if product=='ACTUAL_LINE_DIRECTION' else min)(v for v,r in items)
                ll=[r for v,r in items if v==best]
                for value,r in sorted(items,key=lambda x:(-x[0] if product=='ACTUAL_LINE_DIRECTION' else x[0],x[1]['row_id'])):ranks.append(dict(category=cat,product=product,support=support,metric_value=value,row_id=r['row_id'],procedure_id=r['procedure_id'],method_alias=r['method_alias'],output=r['product'],policy=r['policy'],evidence_tier=r['evidence_tier'],scope='A_COMPATIBLE_DECLARED_SOURCE_PANEL_ONLY;OWNER_LOCAL_PRIVATE_MASK_UNVERIFIED'))
                leaders.append(dict(panel_support=support,metric_value=best,procedures=[dict(row_id=r['row_id'],procedure_id=r['procedure_id'],alias=r['method_alias'],output=r['product'],policy=r['policy'],role_scope=r['role_scope'],tested_season_weeks=r['tested_season_weeks'],own_side_record=r['own_side_record']) for r in ll]))
            out.append(dict(category=cat,product=product,highest_observed_comparable=leaders,comparison_scope='Named A source panels only; B/C/incumbent compatible panels retained separately below. No universal cross-panel winner.',five_week_eligible_recommendation=recommendation(leaders) if product!='TOP_PICKS' else 'NO_CHANGED_CROSS_CATEGORY_SELECTOR_FIVE_WEEK_REPLAY;ORIGINAL_SITE_OWNER_OWNS_EXECUTION',operational_ready_choice='ORIGINAL_SITE_METADATA_DISALLOWS_NEW_OVERLAY;INCUMBENT_R0_PATH;C_W09_SHADOW_FORECAST_ONLY_NOT_PRIMARY_SWITCH',operational_difference='A/B current-query/feed and actual consumer admission not established; original-site rendered player values not independently checked here; C shadow has zero future scored weeks.',B_C_comparison='Existing shared C-board exact matched comparisons remain two-week exposed diagnostics; new B ranker loses and RB111 strict-law gain is two weeks, below replacement floor.',required_next_owner='Original-site owner: exact mapping/selector replay and independent eligible product release; A/B: source-qualified current derived outputs. C: supplied full-board historical typed outputs and independent source checks.'))
    write(OUT/'CATEGORY_PRODUCT_DECISIONS.json',out);write(OUT/'A_PANEL_PRODUCT_RANKINGS.json.gz',ranks);return out
def build():
    start=time.monotonic();prior=ROOT/'reports/post-wave-5w-v1/QUALIFICATION_TABLE.json.gz';base=read(prior);a=a_records();a3=a3_profiles();b=b_profiles();admissions=b_scores()
    # The prior immutable table stays retained. Scoped metadata corrections only in this new version.
    for r in base['rows']:
        if r.get('named_delivery_product')=='pass_td__COUNT_A_MEAN':
            r['operational_export']='OWNER_LOCAL_RESTORATION_PARITY_VERIFIED;BLOCKED_HOSTED_CURRENT_QUERY_FEED_CONSUMER'
            r['history']='2019-2025 frozen fit; model cutoff2026-09-01; actual fit2026-10-31 reconstruction; exact qualified recent context stream.'
        if r['owner']=='A' and r['category']=='rush_att' and r.get('own_side_record') and sum(w.get('eligible') or 0 for w in r['week_records'])==335:r['role_scope']='MIXED_POSITION_QB_RB_WR;335_OFFERS;NOT_RB_ONLY'
    base['schema']='ABC-PRODUCT-QUALIFICATION-5W-v2';base['generated_UTC']=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat();base['prior_table']=bound(prior);base['rows']+=a
    write(OUT/'A3_PROFILE_OVERLAPS.json',dict(direct_validated_profiles=a3,qualification='These eight direct source views overlap the A V3 contribution. Retain source mapping and adverse scores; do not add them as new tested products or NFL cases.'))
    base['profile_partitions']=[dict(owner='B',source=bound(IN/'B_B_PRODUCT_WEEK_QUALIFICATION.json.gz'),rows=len(b),adapter='src/execution_closure02.py:b_profiles',semantics='Part of this single canonical table; retained once rather than duplicate 41404 profiles. Profile views overlap older summaries, not new models or NFL observations.')]
    base['current_limits']='Latest A V4/V2 and B exact product profiles are owner-local aggregate/source admissions, not private raw-row parity or primary release.'
    write(OUT/'QUALIFICATION_TABLE.json.gz',base)
    dd=decisions(a)
    write(OUT/'INTAKE_ADMISSION.json',dict(A='800 profile views verified, V4 exclusions and proper-score V2 applied; private raw rows not received',B=admissions,B_41404_profile_floor_counts=dict(Counter(r['five_week_floor'] for r in b)),all_profile_views=len(base['rows'])+len(b),new_football_outcomes=0,new_mechanism_fits=0,closed_findings='C feature consumption, A allocation/A3, B confidence failures preserved; no unchanged diagnosis rerun'))
    write(OUT/'RUN.json',dict(common_CPU_seconds=time.process_time(),wall_seconds=time.monotonic()-start,RSS_peak_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,A_profile_views=len(a),A3_closed_recipe_profiles=len(a3),B_profile_views=len(b),total_profile_views=len(base['rows'])+len(b),category_product_decisions=len(dd),new_mechanism_fits=0,new_NFL_test_weeks=0,new_actual_offers=0,new_paper_selections=0,routine_future_refits=12,original_forecasts_and_grades_unchanged=True))
    print('CLOSURE02_INTAKE_DECISIONS',len(base['rows'])+len(b),len(a),len(b),len(dd))

if __name__=='__main__':build()
