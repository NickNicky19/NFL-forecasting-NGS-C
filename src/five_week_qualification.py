"""Product-specific week accounting over existing immutable ABC results.

This is a qualification projection, not a new grader or model tournament.
"""
import csv
import gzip
import io
import json
import re
import time
from collections import Counter,defaultdict
from pathlib import Path

import abc_championship_v2 as common
import actual_accuracy_v6 as accuracy
from abc_handoff_adapters_v2 import normalize_b
from predictive_information_c01 import ROOT,read,write,sha,now

OUT=ROOT/'reports/post-wave-5w-v1'
CATS=list(__import__('contracts_v2').CATEGORIES)


def number(x):
    try:return None if x in ['',None,'nan','NaN'] else float(x)
    except (ValueError,TypeError):return None


def week_test_count(weeks):
    """Resolved statistical pushes count as tested; all-zero/unknown weeks do not."""
    return len({(w['season'],w['week']) for w in weeks if w.get('scored',0)>0})


def role_contract(category):
    return 'QB' if category.startswith('pass_') else 'QB/RB/WR/TE_SOURCE_ELIGIBILITY' if category in ['rush_yd','rush_att'] else 'RB/WR/TE' if category in ['rec','rec_yd'] else 'QB/RB/WR/TE'


class Registry:
    def __init__(self):self.rows={};self.sources={};self.B_new=[]
    def source(self,path):
        path=Path(path);key=str(path.relative_to(ROOT));self.sources[key]=dict(path=key,SHA256=sha(path));return key
    def add(self,*,owner,procedure,category,product,role,history,policy,panel,tier,source,season,week,n,selected=None,eligible=None,sides=None,states=None,metrics=None,coverage=None,window=None,metadata=None):
        assert isinstance(season,int) and isinstance(week,int) and 1<=week<=18
        identity=dict(owner=owner,procedure_id=procedure,category=category,product=product,role_scope=role,history=history,policy=policy,source_panel=panel,evidence_tier=tier)
        key=accuracy.digest(identity)
        if key not in self.rows:self.rows[key]=dict(row_id=key,**identity,weeks={},source_artifacts=set(),windows=set(),metadata=metadata or {})
        r=self.rows[key];w=dict(season=season,week=week,scored=int(n or 0),selected=selected,eligible=eligible,states=states or {},metrics=metrics or {},sides=sides,coverage=coverage)
        old=r['weeks'].get((season,week))
        if old is not None:
            # Repeated cumulative/source views may refer to one week, never add it twice.
            assert old['scored']==w['scored'],('CONFLICTING_WEEK_N',identity,old,w)
            if old.get('sides') and w.get('sides'):assert old['sides']==w['sides'],('CONFLICTING_WEEK_SIDES',identity)
        else:r['weeks'][(season,week)]=w
        r['source_artifacts'].add(source)
        if window:r['windows'].add(window)


def sides_from_week(r):
    out={}
    for side in ['OVER','UNDER']:
        s=side.lower();w=int(r[s+'_wins']);l=int(r[s+'_losses']);out[side]=dict(wins=w if w+l else None,losses=l if w+l else None,decided=w+l,rate=w/(w+l) if w+l else None)
    w=sum(out[s]['wins'] or 0 for s in out);l=sum(out[s]['losses'] or 0 for s in out)
    out['COMBINED']=dict(wins=w if w+l else None,losses=l if w+l else None,decided=w+l,rate=w/(w+l) if w+l else None)
    return out


def a_results(reg):
    source=reg.source(ROOT/'reports/abc-championship/continuation-v2/A_W1_W7_ARCHIVED_SCORES.json.gz')
    for r in read(ROOT/source):
        for w in r['week_rows']:
            ss=sides_from_week(w);push=int(w.get('over_pushes',0))+int(w.get('under_pushes',0))
            states=dict(PUSH=push,UNKNOWN_OR_UNRESOLVED=int(w.get('over_unresolved',0))+int(w.get('under_unresolved',0)),DNP=int(w.get('over_DNP',0))+int(w.get('under_DNP',0)),ABSTAIN=int(w.get('no_lean',0)))
            selected=ss['COMBINED']['decided']+push+states['UNKNOWN_OR_UNRESOLVED']+states['DNP']
            states['UNAVAILABLE_OFFER_OR_FORECAST']=int(w['opportunities'])-states['ABSTAIN']-selected
            assert states['UNAVAILABLE_OFFER_OR_FORECAST']>=0
            reg.add(owner='A',procedure=r['procedure_id'],category=r['category'],product='ACTUAL_LINE_DIRECTION:'+r['product'],role='QB' if r['category'].startswith('pass_') else 'RB' if r['category'] in ['rush_yd','rush_att'] else 'RB/WR/TE',history=r['history'],policy='P1_UNROUNDED_POINT_VS_ACTUAL_LINE_ALL_ELIGIBLE',panel=r['source'],tier='TIMING_UNVERIFIED_OWNER_LOCAL_CHRONOLOGICAL_RECONSTRUCTION',source=source,season=2026,week=int(w['week']),n=ss['COMBINED']['decided']+push,selected=selected,eligible=int(w['opportunities']),sides=ss,states=states,metrics={'MAE_saved_point':number(w.get('MAE_offered'))},window='E1_REQUESTED_W1_W8_ACTUAL_W1_W7',metadata=dict(chronology='Owner-local fixed origin/source bindings; private feature/model re-inference notperformed',operational_export='NOT_VERIFIED_CURRENT_QUERY_EXPORT',point_type=r['product']))
    # One original procedure across compatible years; count each weekly record once.
    source=reg.source(ROOT/'reports/abc-championship/shared-intake-v3/A_HISTORICAL_SCORES.json.gz')
    for r in read(ROOT/source):
        if not r['period_id'].startswith('WEEKLY_'):continue
        year=int(r['period_id'].split('_')[-1]);week=int(r['week_view']);ss={s:r[s] for s in ['OVER','UNDER','COMBINED']};states=r['states']
        reg.add(owner='A',procedure=r['procedure_id'],category=r['category'],product='ACTUAL_LINE_DIRECTION:REGISTERED_POINT_OR_CONDITIONAL_RULE',role='QB' if r['category']=='pass_att' else 'RB' if r['category']=='rush_att' else 'RB/WR/TE',history=r['history'],policy=r['procedure_id'].split('::')[-1],panel=r['source_panel'],tier=r['evidence_tier']+';OWNER_LOCAL_ONLY',source=source,season=year,week=week,n=r['COMBINED']['decided']+states.get('PUSH',0),selected=r['COMBINED']['selected'],eligible=r['eligible'],sides=ss,states=states,window='2024_FULL_AND_2026_W1_W5',metadata=dict(chronology='Original owner-reported earlier-only procedure/source; no private re-inference',operational_export='NO_CURRENT_ADMISSION_RECEIPT'))
    # A own-population C-offer and Week8 panels remain separate.
    for filename,panel in [('A_C_SCORES.json.gz','A_ON_C_PINNACLE'),('A_WEEK8_FINAL_SCORES.json.gz','A_W8_FINAL_SOURCE_SPECIFIC')]:
        source=reg.source(ROOT/'reports/abc-championship/shared-intake-v3'/filename)
        for r in read(ROOT/source):
            view=r.get('week_view');week=int(view) if str(view).isdigit() else 8 if filename.startswith('A_WEEK8') else None
            if week is None:continue
            states=r.get('states',{});ss={s:r[s] for s in ['OVER','UNDER','COMBINED']}
            cohort=r.get('cohort',r.get('population',r.get('panel_id',r.get('cohort_id',r.get('selection_policy','SOURCE_RULE')))))
            role='QB' if r['category'].startswith('pass_') else 'RB' if filename=='A_C_SCORES.json.gz' and r['category']=='rush_yd' else 'SOURCE_REGISTERED_ROLE_SCOPE:'+str(cohort)
            product='TOP_PICKS_DIRECTION' if 'TOP' in str(cohort) else 'ACTUAL_LINE_DIRECTION:SOURCE_BOUND_POINT_OR_ORIGINAL_RULE'
            tier='TIMING_UNVERIFIED_RETROSPECTIVE_POINT_REPLAY' if any(x in str(cohort) for x in ['RETROSPECTIVE','FULL_MATCHED_BOARD']) else r.get('evidence_tier','TIMING_UNVERIFIED_OWNER_LOCAL_EXACT_LINE_DIAGNOSTIC')
            reg.add(owner='A',procedure=r['procedure_id'],category=r['category'],product=product,role=role,history=r.get('history','Exactproducer/sourceversion,notexpandedhere'),policy=str(cohort)+':'+str(r.get('kind','POINT_REPLAY')),panel=panel+':'+str(cohort)+':'+str(r.get('kind','POINT_REPLAY')),tier=tier,source=source,season=2026,week=week,n=r['COMBINED']['decided']+states.get('PUSH',0),selected=r['COMBINED']['selected'],eligible=r.get('eligible'),sides=ss,states=states,window='E1_PARTIAL',metadata=dict(operational_export='NOT_CURRENT_QUERY_EXPORT',original_source_kind=r.get('kind'),source_cohort_controls_issuance_claim=True,missingness_hold='80A/Csourceclassificationviewsheld;decidedW/Lunchanged' if filename=='A_C_SCORES.json.gz' else None))


def c_numeric(reg):
    for filename,version in [('reports/all12-v2.1/SCORES.csv','C-ALL12-LAW-THRESHOLD-v2.1'),('reports/robustness-v3/SCORES.csv','C-2025-OOF-P2-v3'),('reports/complete-v1/RESULTS_INDEX.csv','C-ORIGINAL-NGS-HGB-L1-v1')]:
        source=reg.source(ROOT/filename)
        for r in csv.DictReader((ROOT/filename).open()):
            match=re.fullmatch(r'W(\d+)(?:-(QB|RB|WR|TE|PRIMARY))?',r['horizon'])
            if not match:continue
            week=int(match[1]);cat=r['target'];role=match[2] or 'ALL_REGISTERED_SOURCE_ROLES';year=int(r.get('season') or 2026)
            family=r.get('family',r.get('method','P2_LEAF'));history=r.get('history','Expandingfrom2022;registered7dayprefix');arm=r.get('arm',r.get('policy','C0'))
            proc='C::'+version+'::'+family+'::'+history+'::'+arm
            common_args=dict(owner='C',procedure=proc,category=cat,role=role,history=history,policy='FULL_SYSTEM_REGISTERED_WEEKLY_REFIT',panel=version+':RETROSPECTIVE_SOURCE_POPULATION',tier='CURRENT_REVISED_7DAY_CHRONOLOGICAL_RECONSTRUCTION;RESEARCH_EXPOSED',source=source,season=year,week=week,n=int(float(r['outcomes'])),selected=int(float(r['queries'])),eligible=int(float(r['queries'])),states=dict(UNKNOWN=int(float(r.get('unknown') or 0)),MODEL_FALLBACK=int(float(r.get('fallback_queries') or 0))),window='FULL_SUPPORTED_SEASON' if year<2026 else '2026_W1_W7',metadata=dict(chronology='Registeredrollingorigins/sourceassumptions;trainingsamplesnotcountedasweeks',operational_export='EXPERIMENTAL_V4_CAPTURE_IS_DISTINCT_PROCEDURE_NOT_INHERITED',source_label_limit='Fantasylabel/tailshadow;notadmittedchartoffer' if cat=='fpts' else None))
            products=[]
            if version=='C-ORIGINAL-NGS-HGB-L1-v1':products=[('NUMERICAL_MAE_OBJECTIVE_POINT',{'MAE':number(r.get('mae')),'bias':number(r.get('bias'))})]
            else:
                calibrated='RAW' not in arm and version=='C-2025-OOF-P2-v3'
                if not calibrated and number(r.get('median_mae')) is not None:products.append(('NUMERICAL_MEDIAN',{'MAE':number(r.get('median_mae'))}))
                if not calibrated and number(r.get('mean_rmse')) is not None:products.append(('NUMERICAL_EXPECTED_MEAN',{'RMSE':number(r.get('mean_rmse')),'bias':number(r.get('bias',r.get('mean_bias')))}))
                if not calibrated and number(r.get('crps')) is not None:products.append(('OUTCOME_DISTRIBUTION',{'CRPS':number(r.get('crps')),'NLL':number(r.get('nll'))}))
                if number(r.get('grid_brier')) is not None:products.append(('EVENT_PROBABILITY' if cat=='anytime_td' and not calibrated else 'SYNTHETIC_THRESHOLD_PROBABILITY_DIAGNOSTIC',{'Brier':number(r.get('grid_brier')),'reference_Brier':number(r.get('prevalence_brier'))}))
            for product,metrics in products:reg.add(**common_args,product=product,metrics=metrics)


def c_actual(reg):
    records,_=accuracy.load_records();source=reg.source(ROOT/'reporting/actual-props-v6/DATASETS.json');groups=defaultdict(list)
    for r in records:
        if r['season']!=2026 or r['week'] not in [2,3]:continue
        for role in ['ALL_REGISTERED_SOURCE_ROLES',r['position']]:groups[(common.procedure(r),r['category'],role,r['venue'],r['week'],r['method_id'])].append(r)
    for (procedure,cat,role,book,week,alias),rr in groups.items():
        summary=common.summary(rr);states=summary['states'];base=dict(owner='C',procedure=procedure,category=cat,role=role,history='Exactv2.1H-MULTI/source-specificv8extension;seeprocedure_id',policy=rr[0]['selector_id'],panel='C_PROPLINE_'+book.upper()+'_LAST_RECORDED_LINE',tier=rr[0]['evidence_tier'],source=source,season=2026,week=week,selected=summary['COMBINED']['selected'],eligible=len(rr),states=states,window='E1_PARTIAL_2026_W2_W3',metadata=dict(chronology='Historicalprefixreconstruction;notauthenticatedpregamequote/sourceavailability',operational_export='NO_NEW_REAL_LINE_PAPER_SELECTION',price='No qualifiedvalue/settlementclaim'))
        reg.add(**base,product='ACTUAL_LINE_DIRECTION:'+alias,n=summary['COMBINED']['decided']+states.get('PUSH',0),sides={s:summary[s] for s in ['OVER','UNDER','COMBINED']})
        known=[r for r in rr if r.get('p_over') is not None and r.get('actual') is not None and r['appearance']=='PLAYED']
        if any(r.get('p_over') is not None for r in rr):reg.add(**base,product='EXACT_LINE_PROBABILITIES:'+alias,n=len(known),metrics={'proper_score_source':'Existingcanonicalrows;seeBrier/reliabilityreports'})
    source=reg.source(ROOT/'reports/predictive-C01/ACTUAL_LINE_SCORES.json.gz')
    for r in read(ROOT/source):
        if not isinstance(r['week_view'],int) or r['method_id'].startswith('retained:'):continue
        study,arm=r['method_id'].split(':');pid=read(ROOT/('protocol/RECEIVING_TARGETSHARE_V10.json' if study=='share' else 'protocol/TEAM_COMPLETION_CONTEXT_V11.json'))['id'];ss={s:r[s] for s in ['OVER','UNDER','COMBINED']}
        base=dict(owner='C',procedure='C::'+pid+'::'+arm,category='rec',role=r['role'],history='H-MULTI expanding2022;7dayprefix',policy='LARGER_COMPATIBLE_WIN_PROBABILITY_IDENTITY_HOLD_v1',panel='C01_PINNACLE_SAME_362_OFFER_BOARD',tier=r['tier'],source=source,season=2026,week=r['week_view'],selected=r['COMBINED']['selected'],eligible=r['eligible'],states=r['states'],window='REGISTERED_ACTUAL_LINE_W2_W3',metadata=dict(operational_export='CLOSED_NO_INCREMENT_NOT_PROMOTED',chronology='Exactregisteredoriginrefits;sourcevintagereconstruction',matched_control='S1minusS0=0wins;C2minusC1/C0=0wins;allprobabilitiesunchanged'))
        reg.add(**base,product='ACTUAL_LINE_DIRECTION:DIRECT_THRESHOLD',n=r['COMBINED']['decided'],sides=ss)
        reg.add(**base,product='EXACT_LINE_PROBABILITIES:DIRECT_THRESHOLD',n=r['probability_n'],metrics={'Brier':r['Brier'],'log_loss':r['log_loss']})
    source=reg.source(ROOT/'reports/predictive-C01/SYNTHETIC_DIAGNOSTICS.json')
    for r in read(ROOT/source):
        study=r['study'];pid=read(ROOT/('protocol/RECEIVING_TARGETSHARE_V10.json' if study=='share' else 'protocol/TEAM_COMPLETION_CONTEXT_V11.json'))['id'];year,week=r['origin'].split('-W')
        reg.add(owner='C',procedure='C::'+pid+'::'+r['arm'],category='rec',product='SYNTHETIC_THRESHOLD_PROBABILITY_DIAGNOSTIC',role=r['role'],history='H-MULTI expanding2022;7dayprefix',policy='FULL_REGISTERED_FIXED_GRID_NO_SELECTED_PICKS',panel='C01_REGISTERED_FOUR_ORIGINS',tier='CURRENT_REVISED_7DAY_RECONSTRUCTION;EXPOSED_NOT_SPORTSBOOK',source=source,season=int(year),week=int(week),n=r['player_game_rows'],selected=r['player_game_rows'],eligible=r['player_game_rows'],metrics={'Brier':r['Brier'],'value_group_available':r['value_group_available']},window='2025W9W13_PLUS_2026W2W3',metadata={'operational_export':'CLOSED_NO_INCREMENT_NOT_PROMOTED'})
    # Frozen Top-K policies, not parent-law full-board qualification.
    for filename,owner_prefix in [('reports/topk-reference-v9/WEEKLY_RESULTS.json.gz','C_TOPK_v9'),('reports/predictive-C01/TOPK_RESULTS.json.gz','C_C01_TOPK')]:
        source=reg.source(ROOT/filename)
        for r in read(ROOT/source):
            category=r.get('category','rec');method=r.get('method',r.get('method_id'));scope=r.get('scope');side=r['side_variant'];k=r['K']
            if 'COMBINED' in r:n=r['COMBINED']['decided']+r['states'].get('PUSH',0);ss={s:r[s] for s in ['OVER','UNDER','COMBINED']};sel=r['COMBINED']['selected'];states=r['states']
            else:n=r['decided']+r.get('pushes',0);ss=None;sel=r['selected_count'];states=r.get('states',{})
            reg.add(owner='C',procedure=owner_prefix+'::'+str(method),category=category,product='TOP_PICKS_DIRECTION',role='REGISTERED_ONE_PLAYER_SCOPE',history='Earlier-onlyretainedmethod;no newfit',policy=f'{scope}:{side}:K{k}:ONE_PLAYER_FROZEN_TIEBREAK',panel=str(r.get('book','pinnacle'))+':LAST_RECORDED_LINE_NO_COMMON_LIVE_BOARD',tier=r.get('tier','EXPLORATORY_LAST_RECORDED_LINE_RANKING'),source=source,season=2026,week=int(r['week']),n=n,selected=sel,eligible=r['common_eligible'],sides=ss,states=states,metrics={'mean_selected_confidence':r.get('mean_confidence_decided')},window='W2_W3_EXPLORATORY_LISTS',metadata={'operational_export':'NO_EXECUTABLE_TICKET_OR_SIMULTANEOUS_BOARD'})


def c_original_forward(reg):
    source=reg.source(ROOT/'reports/abc-championship/continuation-v2/C_WEEK8_FINAL_FORECAST_GRADES.json')
    saved=read(ROOT/source);policy=read(ROOT/'protocol/PROSPECTIVE_V4.json')
    for r in saved['categories']:
        cat=r['category'];arm=policy['primary']['arms'][cat]
        base=dict(owner='C',procedure='C::C-FORWARD-P2-v4::P2_LEAF::H-MULTI::'+arm,category=cat,role=role_contract(cat)+';ORIGINAL_ROSTER_APPEARANCE_CONDITIONED',history='Registered2022onwardplusobservedcompletedpregameinformation;notinheritedparenttests',policy='FIRST_QUALIFIED_ON_DEMAND-v1:ORIGINAL_FORECAST_ONLY',panel='C_ORIGINAL_W8_13_CAPTURED_GAMES_THURSDAY_EXCLUDED',tier='ORIGINAL_AUTHENTICATED_PREGAME_FORECAST;APPEND_ONLY_FINAL_GRADES;NO_OFFER_SELECTIONS',source=source,season=2026,week=8,n=r['graded'],selected=r['issued'],eligible=r['issued'],states=r['states'],window='E1_W8_ONLY_ORIGINAL_CAPTURE',metadata=dict(operational_export='ORIGINAL_FORECAST_ONLY_CAPTURE_RETAINED;NO_QUALIFIED_REAL_LINE_PAPER_SELECTION',scoring_limits='CMP/ATTselectionblocks;fantasylabelshadowpreserved;rosterisnotconfirmedparticipation',source_outcome_SHA256=saved['outcome_SHA256'],captured_games=saved['captured_games'],original_actual_line_selections=0))
        if r['median_MAE'] is not None:reg.add(**base,product='NUMERICAL_MEDIAN',metrics={'MAE':r['median_MAE']})
        if r['mean_RMSE'] is not None:reg.add(**base,product='NUMERICAL_EXPECTED_MEAN',metrics={'RMSE':r['mean_RMSE']})
        reg.add(**base,product='EVENT_PROBABILITY' if cat=='anytime_td' else 'OUTCOME_DISTRIBUTION',metrics={'Brier' if cat=='anytime_td' else 'CRPS':r['CRPS']})


def bound_week_panel(panel):
    """Only registered ALL64 terminal weekly aliases vary; retain source IDs separately."""
    return re.sub(r'_(?:W?[23]|ALL)$','_REGISTERED_W2_W3',panel) if panel.startswith('B_C_PINNACLE_RETAINED_LEAF_LAWS_') else panel


def b_results(reg):
    # Already admitted source exports remain separate from newly received repairs.
    for path in ['reports/abc-championship/shared-intake-v3/B_ADMITTED_SCORES.json.gz','reports/abc-championship/continuation-v2/B_OWNER_LOCAL_SCORES.json.gz']:
        source=reg.source(ROOT/path)
        for r in read(ROOT/source):
            weeks=r['actual_weeks'];raw_week=r.get('week');week=int(raw_week) if str(raw_week).isdigit() else weeks[0] if len(weeks)==1 else None
            if week is None:continue
            states=r['COMBINED'].get('states',{})
            reg.add(owner='B',procedure=r['procedure_id'],category=r['target'],product='ACTUAL_LINE_DIRECTION:'+str(r.get('product_id')),role=str(r.get('population') or r.get('cohort_id') or 'REGISTERED_SOURCE_ROLES'),history=str(r.get('history_regime'))+';featurememory='+str(r.get('information_policy')),policy=str(r.get('strategy'))+':'+str(r.get('decision_rule'))+':'+str(r.get('rank_scope'))+':K'+str(r.get('K')),panel=str(r['source'])+':'+str(r.get('evaluation_panel_id'))+':'+str(r.get('cohort_id')),tier=str(r.get('evidence_tier') or r.get('source_vintage')),source=source,season=int(r.get('season') or 2026),week=week,n=r['COMBINED']['decided']+states.get('PUSH',0),selected=r['COMBINED']['selected'],eligible=r.get('eligible'),sides={s:r[s] for s in ['OVER','UNDER','COMBINED']},states=states,metrics={'probability_scores':r.get('probability_scores')},window='E1_SOURCE_SPECIFIC_PARTIAL',metadata={'operational_export':'OWNER_LOCAL_EXPORT_NOT_PRIMARY_ADMISSION','chronology':'Ownerreported;privateBraw/modelrecoverylimitsunchanged'})
    pairs=[('B_SCORES.json.gz','B_SCORES_SOURCE_CLOCK_AND_ATTRIBUTION_ANNOTATIONS_V3.json.gz'),('B_POLICY_COHORT_SCORES.json.gz','B_POLICY_COHORT_SCORES_SOURCE_CLOCK_AND_ATTRIBUTION_ANNOTATIONS_V3.json.gz')]
    pairs += [('B_'+name+'.json.gz','B_'+name+'_SOURCE_CLOCK_AND_ATTRIBUTION_ANNOTATIONS_V3.json.gz') for name in ['MATCHED_SELECTED_CONTROL_SCORES','REFERENCE_PROBABILITY_SCORES','ANCILLARY_POINT_SCORES']]
    for raw_name,annotation_name in pairs:
        source=reg.source(OUT/raw_name);annotation_source=reg.source(OUT/annotation_name);raw=read(OUT/raw_name);ann=read(OUT/annotation_name)
        assert sha_uncompressed(OUT/raw_name)==ann['source_score_sha256']
        for a in ann['rows']:
            r=raw[a['source_row_index']];assert r['record_id']==a['record_id'];r['source_vintage']=a['source_vintage'];r['horizon_id']=a['source_horizon_qualification']['horizon_id']
            r['ancillary_point_attribution']=a.get('ancillary_point_attribution')
            if 'registered_rolling_rank' in a:r['K']=a['registered_rolling_rank']['K'];r['rank_scope']=a['registered_rolling_rank']['rank_scope']
        normalized=normalize_b(raw,raw_name);reg.B_new.extend(normalized)
        for r in normalized:
            week=int(r['week']) if str(r['week']).isdigit() else None
            if week is None:continue
            ss={s:r[s] for s in ['OVER','UNDER','COMBINED']};states=ss['COMBINED']['states'];sample=next(x for x in raw if x['procedure_id']==r['procedure_id'] and str(x.get('side','')).upper()=='COMBINED' and x.get('cohort_id')==r.get('cohort_id') and x.get('week')==r.get('week') and x.get('strategy')==r.get('strategy'))
            policy=str(r['strategy'])+':'+str(r.get('rank_scope'))+':K'+str(r.get('K'))
            reg.add(owner='B',procedure=r['procedure_id'],category=r['target'],product='ACTUAL_LINE_DIRECTION:EXACT_LINE_EVENT_POLICY',role=str(r.get('cohort_id')),history=str(r.get('history_regime'))+';'+str(r.get('information_policy')),policy=policy,panel=raw_name+':'+str(r['evaluation_panel_id'])+':'+str(r.get('cohort_id'))+':'+r['horizon_id'],tier=r['source_vintage'],source=source,season=2026,week=week,n=ss['COMBINED']['decided']+states.get('PUSH',0),selected=ss['COMBINED']['selected'],eligible=r.get('eligible'),sides=ss,states=states,metrics={'probability_scores':sample['selection_metrics'].get('probability_scores')},window='W2_W3_RECEP_OR_W8_PASS_TD_NOT_COMBINED',metadata=dict(operational_export='FAILED_REPAIR_OR_GATE_RESEARCH_ONLY;NO_NEW_CAPTURE',source_annotation=annotation_source,chronology='Earliertrainedrepair/gateownerreported;actualexecutionretrospective;qualifiedV3/V4source/horizonrequired',point='No repaired-law mean;source ancillaryB0pointsnotattributedtoB1/B2'))
        for r in raw:
            if r.get('record_kind')!='forecast_evaluation_view':continue
            reg.add(owner='B',procedure=r['procedure_id'],category=r['target'],product='NUMERICAL_EXPECTED_MEAN',role='QB',history=r['history_regime'],policy='ORIGINAL_B0_UNCHANGED_ANCILLARY_POINT',panel=r['evaluation_panel_id'],tier=r['source_vintage'],source=source,season=r['season'],week=int(r['week']),n=r['n'],selected=r['admitted_forecast_rows'],eligible=r['forecast_rows'],states={'UNAVAILABLE_FORECAST':r['unavailable_forecasts']},metrics={k:r.get(k) for k in ['mae','rmse','bias']},window='E1_W8_ONLY',metadata={'operational_export':'RESEARCH_ONLY_NOT_CURRENT_ADAPTER','source_annotation':annotation_source,'not_B1_repaired_mean':True})
        for r in raw:
            if r.get('record_kind')!='prop_threshold_probability_evaluation':continue
            week=int(r['week']) if str(r['week']).isdigit() else None
            if week is None:continue
            reg.add(owner='B',procedure=r['procedure_id'],category=r['target'],product='EXACT_LINE_PROBABILITIES',role='REGISTERED_SOURCE_ROLES',history=str(r.get('history_regime')),policy='FULL_SUPPORTED_BOARD_PROPER_SCORE',panel=r['evaluation_panel_id']+':'+r['horizon_id'],tier=r['source_vintage'],source=source,season=2026,week=week,n=r['n'],selected=r.get('admitted_forecast_rows'),eligible=r.get('forecast_rows'),metrics={'Brier':r.get('brier'),'log_loss':r.get('log_loss')},window='W2_W3_RECEP_OR_W8_PASS_TD',metadata={'operational_export':'RESEARCH_ONLY_NOT_CURRENT_ADAPTER','source_annotation':annotation_source})
    if (OUT/'B_ALL_RETAINED_LAWS_SCORES.json.gz').exists():
        source=reg.source(OUT/'B_ALL_RETAINED_LAWS_SCORES.json.gz');raw=read(ROOT/source)
        for r in normalize_b(raw,'B_ALL64_RETAINED_LAWS'):
            weeks=r['actual_weeks'];week=int(r['week']) if str(r['week']).isdigit() else weeks[0] if len(weeks)==1 else None
            if week is None:continue
            states=r['COMBINED']['states'];reg.add(owner='B',procedure=r['procedure_id'],category=r['target'],product='ACTUAL_LINE_DIRECTION:'+str(r['product_id']),role=str(r.get('population') or r.get('cohort_id')),history=str(r.get('history_regime'))+';'+str(r.get('information_policy')),policy=str(r['strategy']),panel='B_ALL64_LAWS:'+bound_week_panel(str(r['evaluation_panel_id'])),tier=str(r.get('source_vintage')),source=source,season=2026,week=week,n=r['COMBINED']['decided']+states.get('PUSH',0),selected=r['COMBINED']['selected'],eligible=r.get('eligible'),sides={s:r[s] for s in ['OVER','UNDER','COMBINED']},states=states,window='SOURCE_W2_W3',metadata={'operational_export':'OWNER_LOCAL_RESEARCH_NOT_CURRENT_DELIVERY','weekly_panel_alias_rule':'Only terminal W2/W3 aliases normalized; exact source IDs retained in immutable source'})
        for r in raw:
            if 'probability' not in r.get('record_kind',''):continue
            week=int(r['week']) if str(r.get('week')).isdigit() else None
            if week is None:continue
            reg.add(owner='B',procedure=r['procedure_id'],category=r['target'],product='EXACT_LINE_PROBABILITIES:'+str(r.get('product_id')),role=str(r.get('population') or r.get('cohort_id') or 'REGISTERED_SOURCE_ROLES'),history=str(r.get('history_regime')),policy='FULL_SUPPORTED_BOARD_PROPER_SCORE',panel='B_ALL64_LAWS:'+bound_week_panel(str(r['evaluation_panel_id'])),tier=str(r.get('source_vintage',r.get('evidence_tier'))),source=source,season=2026,week=week,n=r.get('n') or 0,selected=r.get('admitted_forecast_rows'),eligible=r.get('forecast_rows'),metrics={'Brier':r.get('brier'),'log_loss':r.get('log_loss')},window='SOURCE_W2_W3',metadata={'operational_export':'OWNER_LOCAL_RESEARCH_NOT_CURRENT_DELIVERY'})


def sha_uncompressed(p):
    import hashlib
    return hashlib.sha256(gzip.decompress(Path(p).read_bytes())).hexdigest()


def finish(reg):
    rows=[]
    for r in reg.rows.values():
        weeks=sorted(r.pop('weeks').values(),key=lambda w:(w['season'],w['week']));r['source_artifacts']=sorted(r['source_artifacts']);r['windows']=sorted(r['windows'])
        counted=[w for w in weeks if w['scored']>0];unresolved=[w for w in weeks if not w['scored'] and w.get('selected') and sum(w['states'].get(s,0) for s in ['UNKNOWN','UNKNOWN_PARTICIPATION','MISSING_ACTUAL','PENDING'])]
        n=week_test_count(weeks);scored=sum(w['scored'] for w in counted);current=[w for w in weeks if w['season']==2026]
        r.update(week_records=weeks,tested_season_weeks=[[w['season'],w['week']] for w in counted],attempted_season_weeks=[[w['season'],w['week']] for w in weeks],zero_selection_weeks=[[w['season'],w['week']] for w in weeks if w.get('selected')==0],unresolved_only_weeks=[[w['season'],w['week']] for w in unresolved],scored_week_count=n,current_2026_scored_week_count=week_test_count(current),scored_cases=scored,five_week_floor='MET' if n>=5 else 'NOT_MET',historical_evidence_needed_for_floor=n>=5 and week_test_count(current)<5,operational_export=r['metadata'].get('operational_export','NOT_VERIFIED_CURRENT_QUERY_EXPORT'),no_automatic_primary_release=True)
        seasons=[]
        for year in sorted({w['season'] for w in weeks}):
            rr=[w for w in weeks if w['season']==year];seasons.append(dict(season=year,scored_weeks=[w['week'] for w in rr if w['scored']],attempted_weeks=[w['week'] for w in rr],scored_cases=sum(w['scored'] for w in rr),selected=sum(w['selected'] or 0 for w in rr),eligible=sum(w['eligible'] or 0 for w in rr)))
        r['season_records']=seasons
        ss=[w['sides'] for w in weeks if w.get('sides')]
        if ss:
            total={}
            for side in ['OVER','UNDER','COMBINED']:
                wins=sum(s[side]['wins'] or 0 for s in ss);losses=sum(s[side]['losses'] or 0 for s in ss);total[side]=dict(wins=wins if wins+losses else None,losses=losses if wins+losses else None,decided=wins+losses,rate=wins/(wins+losses) if wins+losses else None)
            r['own_side_record']=total
            ow,ol,uw,ul=[total[s][k] or 0 for s,k in [('OVER','wins'),('OVER','losses'),('UNDER','wins'),('UNDER','losses')]]
            r['same_decided_constants']=dict(AlwaysOver_wins=ow+ul,AlwaysUnder_wins=ol+uw,decided=ow+ol+uw+ul)
        else:r['own_side_record']=None
        if r['category']=='fpts':r['remaining_gates']='Exactchartlabel/offer/source/admissionlimitsremain;neverlegacyfantasy'
        elif 'SYNTHETIC' in r['product']:r['remaining_gates']='Diagnosticproductcannotqualifyactualprops,probabilitytransferorTopPicks'
        else:r['remaining_gates']='Fiveweeksnecessaryonly;currentinputs/source/coverage/strongcontrols/operationalexportandowneradmissionremain'
        if 'f8607aa99a94c7c1c9ab5c89599e07eba9b15527749b092b225f368032881e83' in r['procedure_id']:
            r['named_delivery_product']='pass_td__COUNT_A_MEAN';r['operational_export']='BLOCKED_W9_ROUTE_ABSENT;EXACT_CORRECTED_MEAN_ADAPTER_NOT_RECEIVED';r['consumer_acknowledgement']='PRODUCTION_COMMENT_6642441018_BLOCKED_NOT_ADMITTED';r['strongest_bound_model_control']='Leafmedian85/142vsCountA87/142,+2;gameclusterintervalcrosses0;ownerpublicreceipt;notprivateCparity'
        rows.append(r)
    rows.sort(key=lambda r:(r['category']!='pass_td','named_delivery_product' not in r,r['category'],r['owner'],r['procedure_id'],r['product'],r['role_scope']))
    return rows


def build():
    start=time.monotonic();reg=Registry();a_results(reg);c_numeric(reg);c_actual(reg);c_original_forward(reg);b_results(reg);rows=finish(reg)
    write(OUT/'QUALIFICATION_TABLE.json.gz',dict(schema='ABC-POST-WAVE-5W-v1',generated_UTC=now(),rule=dict(minimum_distinct_completed_scored_weeks=5,unit='(season,week)',scored_direction_includes_resolved_pushes=True,training_folds_repeats_other_products_do_not_count=True,admission_not_automatic=True),rows=rows,sources=list(reg.sources.values()),limits='Onlyreceivedverifiedexports;ownerlocalprivateinference/sourceclocksremainunverified. No universal ranking; no new NFL observations or scores from this accounting.'))
    write(OUT/'B_NEW_ADMITTED_SELECTIONS.json.gz',reg.B_new)
    cat=[]
    for category in CATS:
        rr=[r for r in rows if r['category']==category];actual=[r for r in rr if r['product'].startswith('ACTUAL_LINE_DIRECTION')]
        cat.append(dict(category=category,received_product_profiles=len(rr),actual_line_profiles=len(actual),actual_line_profiles_with_scored_cases=sum(r['scored_cases']>0 for r in actual),actual_line_floor_met=sum(r['five_week_floor']=='MET' for r in actual),numerical_projection_floor_met=sum(r['five_week_floor']=='MET' and r['product'].startswith('NUMERICAL') for r in rr),probability_floor_met=sum(r['five_week_floor']=='MET' and r['product'].startswith('EXACT_LINE_PROBABILITIES') for r in rr),TopPicks_floor_met=sum(r['five_week_floor']=='MET' and r['product']=='TOP_PICKS_DIRECTION' for r in rr),new_primary_replacements=0,status='Noqualifiedsamecontractactualoffer' if not any(r['scored_cases'] for r in actual) else 'Product/source-specificpartialtests;notfullchampionship'))
    write(OUT/'TWELVE_CATEGORY_QUALIFICATION.json',cat)
    buf=io.StringIO();fields=['row_id','owner','procedure_id','category','product','role_scope','history','policy','source_panel','evidence_tier','scored_week_count','current_2026_scored_week_count','five_week_floor','scored_cases','operational_export','tested_season_weeks'];w=csv.DictWriter(buf,fieldnames=fields);w.writeheader()
    for r in rows:w.writerow({k:json.dumps(r[k],separators=(',',':')) if isinstance(r[k],(list,dict)) else r[k] for k in fields})
    (OUT/'QUALIFICATION_TABLE.csv.gz').write_bytes(gzip.compress(buf.getvalue().encode(),mtime=0))
    write(OUT/'QUALIFICATION_RUN.json',dict(completed_UTC=now(),product_profiles=len(rows),by_owner=dict(Counter(r['owner'] for r in rows)),floor_states=dict(Counter(r['five_week_floor'] for r in rows)),B_new_normalized_triads=len(reg.B_new),new_football_fits=0,new_NFL_outcomes=0,new_forecasts=0,CPU_seconds=time.process_time(),wall_seconds=time.monotonic()-start,common_scorer_unchanged_SHA256=sha(ROOT/'src/abc_championship_v2.py')))
    print('QUALIFICATION_PROJECTED',len(rows),'PROFILES',len(reg.B_new),'NEW_B_OWNER_LOCAL_TRIADS;NO_NEW_FOOTBALL_OBSERVATIONS')


if __name__=='__main__':build()
