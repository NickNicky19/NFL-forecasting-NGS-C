"""Owner-local admissions and public-mask checks through C's existing evaluator.

No model fitting, model deserialization, private-row access or new grader.
"""
import gzip
import hashlib
import json
import os
import resource
import time
from collections import Counter, defaultdict
from pathlib import Path

import abc_championship_v2 as common
from abc_handoff_adapters_v2 import normalize_b
from actual_accuracy_v6 import digest

ROOT = common.ROOT
OUT = ROOT/'reports/abc-championship/shared-intake-v3'
INTAKE = Path(os.environ.get('ABC_V3_INTAKE', str(OUT/'intake')))


def load(name):
    p = INTAKE/(name+'.source.gz')
    raw = p.read_bytes()
    receipt = next(r for r in json.loads((INTAKE/'ARTIFACT_RECEIPTS.json').read_text()) if r['local']==name)
    if receipt['source_encoding']!='SOURCE_GZIP':
        raw = gzip.decompress(raw)
    assert hashlib.sha256(raw).hexdigest()==receipt['SHA256'], ('SOURCE_HASH',name)
    return json.loads(gzip.decompress(raw) if receipt['source_encoding']=='SOURCE_GZIP' else raw)


def emit(name,obj):
    b=(json.dumps(obj,separators=(',',':'),allow_nan=False)+'\n').encode()
    (OUT/name).write_bytes(gzip.compress(b,mtime=0) if name.endswith('.gz') else b)


def validate_partition(row):
    for side in ['OVER','UNDER','COMBINED']:
        r=row[side]
        assert (r['wins'] or 0)+(r['losses'] or 0)==r['decided']
        assert r['rate'] is None if not r['decided'] else abs(r['rate']-r['wins']/r['decided'])<1e-12
    for key in ['selected','decided']:
        assert row['OVER'][key]+row['UNDER'][key]==row['COMBINED'][key]


def c_board():
    rows,bindings=common.a.load_records()
    board=defaultdict(dict)
    for r in rows:
        if r['venue']=='pinnacle' and r['season']==2026 and r['week'] in [2,3]:
            assert r['method_id'] not in board[r['offer_id']]
            board[r['offer_id']][r['method_id']]=r
    assert len(board)==968
    return board,bindings


def build():
    started=time.monotonic()
    resource.setrlimit(resource.RLIMIT_CPU,(60,61))
    OUT.mkdir(exist_ok=True)
    a=load('A_ON_C_BOUND_OFFERS_UNCERTAINTY_APPEND_V1')
    hist=load('A_HISTORICAL_COMMON_SCORER_V1')
    w8=load('A_WEEK8_COMMON_SCORER_FINAL_V1')
    for source in [a,hist,w8]:
        for r in source['scores']:
            validate_partition(r)
    assert (len(a['scores']),len(a['paired']),len(hist['scores']),len(w8['scores']))==(87,203,1092,446)
    # Original bytes stay retained; these are scoped admissions, not source rewrites.
    emit('A_C_SCORES.json.gz',a['scores'])
    emit('A_HISTORICAL_SCORES.json.gz',hist['scores'])
    emit('A_WEEK8_FINAL_SCORES.json.gz',w8['scores'])
    emit('A_HISTORICAL_PAIRED_CONTROLS.json',load('A_HISTORICAL_PAIRS'))
    b=[]
    for name in ['B_D1_D2_ordered_actual_line_saved_points','B_additional_actual_line_saved_points','B_restored_GLM_law_P2_and_proper_probability_scores','weekly_retained_method_scores','weekly_full_board_and_matched_controls','B_WEEKLY_FULL']:
        raw=load(name)
        lookup={r['record_id']:r for r in raw}
        normalized=normalize_b(raw,name)
        for r in normalized:
            source=next(q for q in raw if q.get('record_kind')=='prop_selection_evaluation' and q['procedure_id']==r['procedure_id'] and q['target']==r['target'] and q['side'].lower()=='combined' and q['evaluation_panel_id']==r['evaluation_panel_id'] and q.get('cohort_id')==r['cohort_id'])
            m=source['selection_metrics']
            r.update(unavailable=m.get('technical_unavailable',r['unavailable']),fallback_issued=m.get('fallback_issued'),fallback_status_unknown=m.get('fallback_status_unknown'),probability_scores=m.get('probability_scores'),MAE=source.get('mae'),bias=source.get('bias'),numerical_n=source.get('numerical_n'),evidence_tier=source.get('evidence_tier'),base_procedure_id=source.get('base_procedure_id'),window_contract=source.get('window_contract'),source_record_id=source['record_id'])
        b+=normalized
    assert len(b)==903 # 684 C-board triads +219 source-specific weekly triads.
    emit('B_ADMITTED_SCORES.json.gz',b)
    board,bindings=c_board()
    controls=['P1_MEDIAN','P1_MEAN','P2_LAW','P3_DIRECT','ALWAYS_OVER','ALWAYS_UNDER','EARLIER_PREVALENCE_V8']
    masks={}
    def remember(ids,category):
        ids=sorted(ids);key=digest(ids)
        if key not in masks:
            assert len(set(ids))==len(ids) and all(oid in board for oid in ids)
            cc={}
            for control in controls:
                rr=[board[oid][control] for oid in ids if control in board[oid]]
                cc[control]=common.summary(rr)
            masks[key]=dict(mask_id=key,category=category,offer_ids=ids,actual_weeks=sorted({next(iter(board[o].values()))['week'] for o in ids}),C_controls=cc,rights='Existing licensed public C offer IDs/records only; no A/B private predictions')
        return key
    b_masks=load('public_safe_C_opportunity_mask_members')
    by_b={}
    for m in b_masks:
        ids=m['common_decided_offer_ids']
        assert digest(ids)==m['common_decided_sha256']
        key=remember(ids,m['target'])
        by_b[(m['procedure_id'],m['target'],m['week_view'])]=key
    assert len(by_b)==684
    pairs=[]
    for r in a['paired']:
        category=r['category'];control=r['control'].removeprefix('C::')
        ids=[]
        for oid,methods in board.items():
            proto=next(iter(methods.values()))
            if proto['category']!=category or (category=='rush_yd' and proto['position']!='RB'):
                continue
            if proto['appearance']!='PLAYED' or proto['actual'] is None:
                continue
            q=methods.get(control)
            if q is not None and common.status(q) in ['WIN','LOSS']:
                ids.append(oid)
        assert hashlib.sha256(json.dumps(sorted(ids)).encode()).hexdigest()==r['mask_sha256']
        assert len(ids)==r['common_decided']
        key=remember(ids,category)
        assert masks[key]['C_controls'][control]['COMBINED']['wins']==r['control_wins']
        pairs.append(dict(**r,canonical_mask_id=key,C_mask_and_control_recomputed=True,private_candidate_wins='Owner-local A export; not reinferred by C',temporal_parity='NOT_ESTABLISHED; diagnostic horizon only'))
    emit('A_C_VERIFIED_PAIRS.json.gz',pairs)
    emit('PUBLIC_C_MASKS_AND_CONTROLS.json.gz',list(masks.values()))
    # Never relabel 80 source states in place. Explain the inherited-state path.
    problems=[]
    for r in a['scores']:
        if r['states'].get('UNAVAILABLE_FORECAST',0)!=r['unavailable']:
            problems.append(dict(procedure_id=r['procedure_id'],category=r['category'],week_view=r['week_view'],selected=r['COMBINED']['selected'],unavailable_header=r['unavailable'],source_states=r['states'],qualification='DECIDED_WL_ADMITTED;MISSINGNESS_CLASSIFICATION_OWNER_CORRECTION_REQUIRED'))
    assert len(problems)==80
    emit('A_STATE_CLASSIFICATION_HOLD.json',dict(affected_views=problems,cause='A_COMMON_CODE copies first C method record, replaces point/selected_side but preserves inherited status when actual/appearance absent through C.status. Not80 absent A forecasts.',correction='A must issue a new scoped state-classification version; originals unchanged; no retrospective side/model changes',decided_counts_changed=False))
    # Same public opportunity masks: retain full systems and exact masked comparisons separately.
    group=defaultdict(list)
    for r in b:
        if r['source'].startswith('weekly') or r['source']=='B_WEEKLY_FULL' or r['actual_weeks']!=[2,3]:
            continue
        key=by_b.get((r['procedure_id'],r['target'],'ALL'))
        if key:
            assert len(masks[key]['offer_ids'])==r['COMBINED']['decided']
            group[(r['target'],key)].append(dict(session='B',procedure_id=r['procedure_id'],product=r['product_id'],history=r['history_regime'],information_policy=r['information_policy'],OVER=r['OVER'],UNDER=r['UNDER'],COMBINED=r['COMBINED'],eligible=r['eligible'],selected=r['selected'],unavailable=r['unavailable'],fallback_issued=r['fallback_issued'],uncertainty=r['uncertainty']))
    for r in pairs:
        if r['control']!='C::P3_DIRECT':
            continue
        full=next(x for x in a['scores'] if x['category']==r['category'] and x['procedure_id']==r['procedure_id'] and x['week_view']=='ALL')
        own_sides={s:None for s in ['OVER','UNDER']}
        if full['COMBINED']['decided']==r['common_decided'] and full['COMBINED']['wins']==r['A_wins']:
            # This pair is the entire A decided set; no missing-member side is inferred.
            own_sides={s:dict(full[s],selected=full[s]['decided']) for s in ['OVER','UNDER']}
        group[(r['category'],r['canonical_mask_id'])].append(dict(session='A',procedure_id=r['procedure_id'],product='Source-bound P1 point',history='A fixed recipe, exact source export; seven-day reconstruction',**own_sides,COMBINED=dict(wins=r['A_wins'],losses=r['common_decided']-r['A_wins'],decided=r['common_decided'],rate=r['A_wins']/r['common_decided']),paired_side_counts='FULL_DECIDED_SET_SAME;original selected/unknown counts retained separately' if own_sides['OVER'] is not None else 'NOT_EXPORTED;full-population own-side counts in A_C_SCORES',uncertainty=r['paired_accuracy_difference_interval95']))
    comparisons=[]
    for (category,key),rr in group.items():
        for control,score in masks[key]['C_controls'].items():
            if score['COMBINED']['decided']==len(masks[key]['offer_ids']):
                rr.append(dict(session='C',procedure_id='C::'+control,product='Retained exact source product',OVER=score['OVER'],UNDER=score['UNDER'],COMBINED=score['COMBINED'],uncertainty=score['uncertainty']))
        comparisons.append(dict(category=category,mask_id=key,decided=len(masks[key]['offer_ids']),sessions=sorted({r['session'] for r in rr}),rows=rr,tier='TIMING_UNVERIFIED_EXACT_OFFER_OWNER_LOCAL_DIAGNOSTIC;notauthenticatedissuance',temporal_parity='NOT_ESTABLISHED_ACROSS_A_B_C',not_new_NFL_observations=True))
    emit('SAME_OFFER_COMPARISONS.json.gz',comparisons)
    # Registered partial E5/E7: exact common years/weeks and all fixed procedures.
    grouped=defaultdict(dict)
    for r in hist['scores']:
        if r['period_id'].startswith('WEEKLY_') and int(r['week_view'])<=5:
            year=int(r['period_id'].removeprefix('WEEKLY_'))
            if year in [2024,2026]:
                grouped[(r['category'],r['procedure_id'])].setdefault(year,[]).append(r)
    pooled=[]
    for (category,procedure),years in sorted(grouped.items()):
        assert set(years)=={2024,2026}
        yrecords=[]
        for year,rr in sorted(years.items()):
            assert sorted(int(r['week_view']) for r in rr)==list(range(1,6))
            v={}
            for side in ['OVER','UNDER','COMBINED']:
                w=sum(r[side]['wins'] or 0 for r in rr);l=sum(r[side]['losses'] or 0 for r in rr)
                v[side]=dict(selected=sum(r[side]['selected'] for r in rr),wins=w if w+l else None,losses=l if w+l else None,decided=w+l,rate=w/(w+l) if w+l else None)
            v.update(season=year,weeks=list(range(1,6)),eligible=sum(r['eligible'] for r in rr),unavailable=sum(r['unavailable'] for r in rr),abstentions=sum(r['abstentions'] for r in rr),states=dict(sum((Counter(r['states']) for r in rr),Counter())))
            yrecords.append(v)
        totals={}
        for side in ['OVER','UNDER','COMBINED']:
            w=sum(r[side]['wins'] or 0 for r in yrecords);l=sum(r[side]['losses'] or 0 for r in yrecords)
            totals[side]=dict(selected=sum(r[side]['selected'] for r in yrecords),wins=w if w+l else None,losses=l if w+l else None,decided=w+l,rate=w/(w+l) if w+l else None,equal_season_rate=sum(r[side]['rate'] for r in yrecords)/2 if all(r[side]['decided'] for r in yrecords) else None)
        ow,ol,uw,ul=[totals[s][k] or 0 for s,k in [('OVER','wins'),('OVER','losses'),('UNDER','wins'),('UNDER','losses')]]
        pooled.append(dict(category=category,procedure_id=procedure,period_id='E5_PARTIAL_A_2024_2026_SHARED_W1_W5',equal_season_period_id='E7_PARTIAL_SAME_TWO_SEASONS_SHARED_W1_W5',actual_seasons=[2024,2026],actual_weeks=list(range(1,6)),season_records=yrecords,**totals,eligible=sum(r['eligible'] for r in yrecords),unavailable=sum(r['unavailable'] for r in yrecords),abstentions=sum(r['abstentions'] for r in yrecords),same_decided_constants=dict(AlwaysOver_wins=ow+ul,AlwaysUnder_wins=ol+uw),scope='A-only owner-local record aggregation;no requestedfullseasonset/ABC/common-horizon claim'))
    assert len(pooled)==42
    emit('PARTIAL_E5_E7_ALL_PROCEDURES.json',pooled)
    suites=[]
    for suffix in sorted({r['procedure_id'].split('::')[-1] for r in pooled}):
        rr=[r for r in pooled if r['procedure_id'].endswith('::'+suffix)]
        assert {r['category'] for r in rr}=={'pass_att','rush_att','rec'}
        w=sum(r['COMBINED']['wins'] or 0 for r in rr);n=sum(r['COMBINED']['decided'] for r in rr)
        suites.append(dict(fixed_procedure='A::opportunity-four-ou-v1::'+suffix,categories=['pass_att','rush_att','rec'],seasons=[2024,2026],weeks=list(range(1,6)),wins=w,decided=n,micro_rate=w/n if n else None,category_balanced_rate=sum(r['COMBINED']['rate'] for r in rr)/3 if all(r['COMBINED']['decided'] for r in rr) else None,equal_season_category_balanced_rate=sum(r['COMBINED']['equal_season_rate'] for r in rr)/3 if all(r['COMBINED']['equal_season_rate'] is not None for r in rr) else None,scope='Fixed original procedure across supported three categories only; no hindsight category router; correlated categories not independent games; not all12 championship'))
    emit('PARTIAL_FIXED_SUITE_SUMMARIES.json',suites)
    # Full original/cumulative panels remain before pooled views.
    leaders=[]
    for period in sorted({r['period_id'] for r in hist['scores'] if r['week_view']=='ALL'}):
        for category in ['pass_att','rush_att','rec']:
            rr=[r for r in hist['scores'] if r['period_id']==period and r['category']==category and r['week_view']=='ALL']
            for side in ['OVER','UNDER','COMBINED']:
                valid=[r for r in rr if r[side]['decided']]
                best=max((r[side]['rate'] for r in valid),default=None)
                leaders.append(dict(period_id=period,category=category,side=side,raw_ties=[r for r in valid if r[side]['rate']==best],scope='Same source panel;different selected populations remain;no hindsight router or release'))
    emit('HISTORICAL_RAW_LEADERS.json.gz',leaders)
    emit('RUN.json',dict(id='ABC-C-SHARED-INTAKE-v3-1',A_common_views=87,A_common_pairs=203,A_historical_views=1092,A_W8_views=446,B_complete_triads=len(b),B_C_board_triads=684,B_weekly_triads=219,B_safe_masks=684,deduplicated_public_C_masks=len(masks),same_offer_panels=len(comparisons),three_session_diagnostic_panels=sum(set(x['sessions'])=={'A','B','C'} for x in comparisons),partial_pooled_procedure_category_cells=len(pooled),source_GETs=32,source_cap=32,new_fits=0,new_inference=0,new_predictions=0,wall_seconds=time.monotonic()-started,process_CPU_seconds=time.process_time(),max_RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,original_C_bindings=bindings,qualification='Exactpublicmask/C-controlrecomputation;A/Bprivatecandidatevaluesownerlocalonly;horizon/evidence tiers unchanged'))
    print('SHARED_INTAKE_EXECUTED',len(b),len(masks),len(comparisons),len(pooled))


if __name__=='__main__':
    build()
