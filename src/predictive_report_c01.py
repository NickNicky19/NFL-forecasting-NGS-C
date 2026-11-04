"""Summarize frozen C information comparisons through the adopted scorer."""
import csv
import math
from collections import Counter, defaultdict

import numpy as np

import abc_championship_v2 as common
from predictive_information_c01 import ROOT,ART,OUT,read,write,sha,now
from topk_reference_v9 import choose


def normalized(r):
    return dict(r,status=r['state'],appearance='PLAYED' if r['actual'] is not None else 'UNKNOWN',season=2026,category='rec',comparator='STRICT_OVER_UNDER')


def score(rows):
    result=common.summary(rows)
    known=[r for r in rows if r['actual'] is not None and r.get('probabilities') is not None]
    result.update(Brier=float(np.mean([r['Brier'] for r in known])) if known else None,log_loss='Infinity' if any(r['log_loss']=='Infinity' for r in known) else float(np.mean([r['log_loss'] for r in known])) if known else None,probability_n=len(known),neutral_Brier=.25 if all(r['line']%1==.5 for r in known) else None,threshold_outside_training_grid=sum(r.get('threshold_outside_training_grid',False) for r in rows))
    for side in ['OVER','UNDER','COMBINED']:
        rr=[r for r in rows if r['selected_side'] in ['OVER','UNDER'] and (side=='COMBINED' or side==r['selected_side'])]
        dec=[r for r in rr if r['status'] in ['WIN','LOSS']]
        probs=[r['probabilities'][r['selected_side'].lower()] for r in dec if r.get('probabilities')]
        result[side].update(mean_selected_probability=float(np.mean(probs)) if probs else None,expected_wins=float(sum(probs)) if probs else None)
    result['higher_observed_side']=None if not result['OVER']['decided'] or not result['UNDER']['decided'] else 'TIE' if result['OVER']['rate']==result['UNDER']['rate'] else max(['OVER','UNDER'],key=lambda s:result[s]['rate'])
    return result


def paired(a,b):
    aa={r['offer_id']:r for r in a};bb={r['offer_id']:r for r in b}
    matched=[(aa[k],bb[k]) for k in sorted(aa.keys()&bb.keys()) if aa[k]['status'] in ['WIN','LOSS'] and bb[k]['status'] in ['WIN','LOSS']]
    for x,y in matched:assert (x['actual'],x['line'],x['game_id'],x['player_id'])==(y['actual'],y['line'],y['game_id'],y['player_id'])
    groups=defaultdict(lambda:np.zeros(4))
    for x,y in matched:
        groups[x['game_id']]+=np.array([int(x['status']=='WIN')-int(y['status']=='WIN'),1,(x['Brier']-y['Brier']) if x.get('Brier') is not None and y.get('Brier') is not None else 0,int(x.get('Brier') is not None and y.get('Brier') is not None)])
    totals=np.sum(list(groups.values()),axis=0) if groups else np.zeros(4)
    ci=None;bc=None
    if len(groups)>1:
        arr=np.asarray(list(groups.values()));rng=np.random.default_rng(1701)
        draws=arr[rng.integers(len(arr),size=(2000,len(arr)))].sum(axis=1)
        ci=np.quantile(draws[:,0]/draws[:,1],[.025,.975]).tolist()
        if totals[3]:bc=np.quantile(draws[:,2]/draws[:,3],[.025,.975]).tolist()
    return dict(common_decided=len(matched),games=len(groups),win_difference=int(totals[0]),accuracy_difference=totals[0]/totals[1] if totals[1] else None,game_cluster_sensitivity95=ci,Brier_difference=totals[2]/totals[3] if totals[3] else None,Brier_game_cluster_sensitivity95=bc,method='2000pairedgameclusterresamples,seed1701;twoexposedweeks,multiplicityunadjusted;notfutureproof')


def build():
    cases=read(ART/'APPROVED_OFFER_CASES.json.gz')['cases'];bycase={r['offer_id']:r for r in cases}
    actual=[];diagnostics=[];numeric=[];features={};runtimes=[];identity_holds=[]
    for study,stage in [('share','original'),('share','actual'),('completion','original')]:
        prefix=ART/(study+'-'+stage);run=read(OUT/(study+'-'+stage+'-RUN.json'));runtimes.append(run)
        preds=read(prefix/'PREDICTIONS.json.gz');ff=read(prefix/'FEATURE_EXPORT.json.gz')
        for r in ff:features[(study,r['origin'],r['game_id'],r['player_id'])]=r
        for r in read(prefix/'EXACT_OFFER_ROWS.json.gz'):
            r=normalized(r);r['method_id']=study+':'+r['arm']
            identity=features[(study,f"2026-W{r['week']:02}",r['game_id'],r['player_id'])]
            if identity['team'] is None:
                identity_holds.append(dict(method_id=r['method_id'],offer_id=r['offer_id'],game_id=r['game_id'],player_id=r['player_id'],raw_side=r['selected_side'],raw_state=r['state'],raw_probabilities=r['probabilities'],reason='NATIVE_HISTORICAL_TEAM_QUERY_UNRESOLVED;newmissing-statqueryopponentmustnotbeassumed'))
                r['unqualified_inference']=dict(side=r['selected_side'],state=r['state'],probabilities=r['probabilities'],Brier=r['Brier'],log_loss=r['log_loss'])
                r.update(selected_side=None,status='UNAVAILABLE_FORECAST',probabilities=None,Brier=None,log_loss=None,qualification='C01-IDENTITY-HOLD-v1;rawinferencepreservednotadmitted')
            actual.append(r)
        origins=sorted({r['origin'] for r in preds})
        for origin in origins:
            rr=[r for r in preds if r['origin']==origin]
            for arm in rr[0]['arms']:
                for role in ['ALL','RB','WR','TE']:
                    qq=[r for r in rr if r['actual'] is not None and (role=='ALL' or r['position']==role)]
                    bs=[];logs=[];hits=[]
                    for r in qq:
                        for line,p in zip(r['arms'][arm]['grid'],r['arms'][arm]['p_over']):
                            y=r['actual']>line;bs.append((p-y)**2);pp=p if y else 1-p;logs.append(-math.log(pp) if pp else float('inf'));hits.append((p>.5)==y if p!=.5 else None)
                    ffq=[features[(study,origin,r['game_id'],r['player_id'])] for r in qq]
                    diagnostics.append(dict(study=study,arm=arm,origin=origin,role=role,player_game_rows=len(qq),grid_views=len(bs),Brier=float(np.mean(bs)) if bs else None,log_loss=float(np.mean(logs)) if logs else None,synthetic_grid_direction_rate=float(np.mean([h for h in hits if h is not None])) if any(h is not None for h in hits) else None,value_group_available=sum(not bool(r['support'][-1]) for r in ffq),numerical_MAE=None,reason='DIRECT_THRESHOLD_MODEL_HAS_NO_TYPED_POINT;syntheticdiagnosticnotactualprops'))
            for point in ['mean','median']:
                for role in ['ALL','RB','WR','TE']:
                    pp=[r for r in rr if r['actual'] is not None and r['retained_P2_point_reference'] and r['retained_P2_point_reference'][point] is not None and (role=='ALL' or r['position']==role)]
                    errors=np.asarray([r['retained_P2_point_reference'][point]-r['actual'] for r in pp])
                    numeric.append(dict(study=study,origin=origin,role=role,method='RetainedP2_LEAF',typed_product=point,n=len(pp),MAE=float(np.abs(errors).mean()) if len(pp) else None,RMSE=float(np.sqrt(np.square(errors).mean())) if len(pp) else None,bias=float(errors.mean()) if len(pp) else None,P90_error=float(np.quantile(np.abs(errors),.9)) if len(pp) else None,P95_error=float(np.quantile(np.abs(errors),.95)) if len(pp) else None,fallback=sum(bool(r['retained_P2_point_reference']['fallback']) for r in pp),new_fits=0))
    # Retained controls remain separate procedures, with original unavailable rows.
    for c in cases:
        for method,old in c['retained_methods'].items():
            p=dict(under=old['p_under'],push=old['p_push'],over=old['p_over']) if old['p_over'] is not None else None
            state=old['status'];brier=log=None
            if p is not None and c['actual'] is not None:
                truth={s:int(c['actual']<c['line']) if s=='under' else int(c['actual']==c['line']) if s=='push' else int(c['actual']>c['line']) for s in p}
                brier=.5*sum((p[s]-truth[s])**2 for s in p);pr=sum(p[s]*truth[s] for s in p);log=-math.log(pr) if pr else 'Infinity'
            actual.append(dict(c,method_id='retained:'+method,selected_side=old['selected_side'],status=state,comparator='STRICT_OVER_UNDER',probabilities=p,Brier=brier,log_loss=log,point=old['point']))
    scores=[]
    for method in sorted({r['method_id'] for r in actual}):
        mm=[r for r in actual if r['method_id']==method]
        for week in ['ALL',2,3]:
            for role in ['ALL','RB','WR','TE']:
                rr=[r for r in mm if (week=='ALL' or r['week']==week) and (role=='ALL' or r['position']==role)]
                scores.append(dict(category='rec',method_id=method,week_view=week,role=role,requested_weeks=list(range(1,9)),actual_weeks=sorted({r['week'] for r in rr}),tier='TIMING_UNVERIFIED_LAST_RECORDED_ACTUAL_LINES;exposedresearch;notissued',**score(rr)))
    methods={m:[r for r in actual if r['method_id']==m] for m in sorted({r['method_id'] for r in actual})}
    comparisons=[]
    for candidate,control in [('share:S1','share:S0'),('completion:C2','completion:C1'),('completion:C2','completion:C0'),('completion:C1','completion:C0')]+[(m,c) for m in ['share:S0','share:S1','completion:C0','completion:C1','completion:C2'] for c in ['retained:P2_LAW','retained:P3_DIRECT','retained:EARLIER_PREVALENCE_V8','retained:ALWAYS_UNDER']]:
        comparisons.append(dict(candidate=candidate,control=control,**paired(methods[candidate],methods[control])))
    # Reuse registered v9 one-player/tie-break rules; no new fitted selective gate.
    probability_methods=[m for m in methods if m not in ['retained:P1_MEAN','retained:P1_MEDIAN','retained:ALWAYS_OVER','retained:ALWAYS_UNDER']]
    ready={c['offer_id'] for c in cases if all(next(r for r in methods[m] if r['offer_id']==c['offer_id'])['probabilities'] is not None for m in probability_methods)}
    tops=[];members=[]
    pred=read(ART/'completion-original/PREDICTIONS.json.gz');kick={(r['game_id'],r['player_id']):r['cutoff_UTC'] for r in pred}
    for m in probability_methods:
        for week in [2,3]:
            source=[]
            for r in methods[m]:
                if r['offer_id'] in ready and r['week']==week:
                    source.append(dict(r,_confidence=max(r['probabilities']['over'],r['probabilities']['under']),kickoff_UTC=kick[(r['game_id'],r['player_id'])],category='rec'))
            for side in ['MIXED','OVER_ONLY','UNDER_ONLY']:
                for k in [6,10,20]:
                    selected,board=choose(source,side,k);known=[r for r in selected if r['status'] in ['WIN','LOSS']]
                    rid=f'{m}-W{week}-{side}-K{k}'
                    tops.append(dict(id=rid,method_id=m,week=week,scope='WITHIN_RECEPTIONS',side_variant=side,K=k,common_eligible=len(source),side_eligible=len(board),fewer_than_K=len(selected)<k,mean_confidence_decided=float(np.mean([r['_confidence'] for r in known])) if known else None,expected_wins_all_selected=sum(r['_confidence'] for r in selected),role_composition=dict(Counter(r['position'] for r in selected)),tier='EXPLORATORY_LAST_RECORDED_LINE_RANKING;NO_SIMULTANEOUS_BOARD_OR_TICKET',ninety_percent='TARGET_NOT_ESTABLISHED',**score(selected)))
                    members.extend(dict(list_id=rid,rank=i,offer_id=r['offer_id'],player_id=r['player_id'],game_id=r['game_id'],line=r['line'],side=r['selected_side'],p_selected=r['_confidence'],actual=r['actual'],state=r['status']) for i,r in enumerate(selected,1))
    write(OUT/'ACTUAL_LINE_SCORES.json.gz',scores);write(OUT/'PAIRED_CHANGES.json',comparisons)
    write(OUT/'SYNTHETIC_DIAGNOSTICS.json',diagnostics);write(OUT/'RETAINED_NUMERICAL_CONTROLS.json',numeric)
    write(OUT/'TOPK_RESULTS.json.gz',tops);write(ART/'TOPK_MEMBERS.json.gz',members)
    write(OUT/'CANONICAL_ACTUAL_ROWS.json.gz',actual)
    write(OUT/'IDENTITY_QUALIFICATION_HOLD.json',dict(id='C01-IDENTITY-HOLD-v1',correction_created_UTC=now(),original_run_predictions_changed=False,new_fits=0,unique_held_offers=len({r['offer_id'] for r in identity_holds}),held_arm_views=len(identity_holds),held_records=identity_holds,impact='One raw extra played-zero Underwin perarm is notqualified;primary C0/C1/C2 revert194/337,S0/S1 189/337;raw trees/features/inference and original v7/v4 unchanged',required_input='Nativehistoricalteam/eventmapping for22missing-statqueries;no guessed currentroster/opponent/zero'))
    cumulative=[r for r in scores if r['week_view']=='ALL' and r['role']=='ALL']
    with (OUT/'ACTUAL_LINE_SCORES.csv').open('w',newline='') as f:
        fields=['method_id','week_view','role','eligible','selected','decided','OVER_wins','OVER_losses','OVER_rate','UNDER_wins','UNDER_losses','UNDER_rate','wins','losses','rate','Brier','log_loss','states'];w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for r in scores:w.writerow(dict(method_id=r['method_id'],week_view=r['week_view'],role=r['role'],eligible=r['eligible'],selected=r['COMBINED']['selected'],decided=r['COMBINED']['decided'],**{s+'_'+k:r[s][k] for s in ['OVER','UNDER'] for k in ['wins','losses','rate']},**{k:r['COMBINED'][k] for k in ['wins','losses','rate']},Brier=r['Brier'],log_loss=r['log_loss'],states=str(r['states'])))
    def rec(x):return f"{x['wins']}-{x['losses']}/{x['decided']}/{100*x['rate']:.2f}%" if x['decided'] else 'N/A'
    text='# C receiving information tests — executed controlled comparisons\n\nActual recorded Pinnacle receptions,2026W2–3 only. Full362offerboard,338known outcomes and24unknown. Primary new-model results have337decided,3selectedunknown and22technical identity holds;zero statistical pushes/voids/pending. An initial raw inference extended22missing-stat queries with unresolved native team/context,including one played-zero Underwin. Those raw outputs remain frozen but are NOT admitted as qualified predictions. [Append-only identity hold and impact](IDENTITY_QUALIFICATION_HOLD.json). No extra win is credited. Timing-unverified last-recorded-line diagnostics,not pregame selections or settled wagers. Main/alternate tiers remain unknown. All old C forecasts and negative recipes are unchanged.\n\n|Procedure|Over W-L/n/%|Under W-L/n/%|Combined W-L/n/%|Eligible/selected/unavailable|Brier|\n|---|---|---|---|---|---|\n'
    for r in cumulative:text+=f"|{r['method_id']}|{rec(r['OVER'])}|{rec(r['UNDER'])}|{rec(r['COMBINED'])}|{r['eligible']}/{r['COMBINED']['selected']}/{r['unavailable']}|{r['Brier'] if r['Brier'] is not None else 'N/A'}|\n"
    text+='\nMatched direct changes (game-cluster sensitivity,2exposedweeks):\n\n'
    for r in comparisons[:4]:text+=f"- {r['candidate']} minus {r['control']}: {r['win_difference']:+} wins/{r['common_decided']}; direction {100*r['accuracy_difference']:+.2f}pp,95% {r['game_cluster_sensitivity95']}; Brier {r['Brier_difference']:+.6f}.\n"
    text+='\n[Every week/role/procedure](ACTUAL_LINE_SCORES.json.gz), [paired controls](PAIRED_CHANGES.json), [same canonical actual rows](CANONICAL_ACTUAL_ROWS.json.gz), [all registered Top6/10/20 variants](TOPK_RESULTS.json.gz), [2025synthetic diagnostics](SYNTHETIC_DIAGNOSTICS.json), [retained typed numerical references](RETAINED_NUMERICAL_CONTROLS.json). Synthetic diagnostic views are not extra NFL observations or actual props. New direct classifiers have no point output or full count law, so their MAE is N/A; the retainedP2 mean/median are unchanged separate numerical controls.\n\nThe unchanged safe2026C0models are reused; new-input arms and necessary2025origins receive their own fits. Team completion context is an ordinary completion/attempt rate,not NGS or a causal talent effect; target-share uses reported targets,not routes. Both use native historical team identities and earlier gamekickoff+7days reconstruction,not authenticated publication. Missing rows/denominators stay missing with training-only imputation and flags; no target-game workload, future outcomes, injury penalties or current-roster historical joins.\n\nTarget-share values and completion-quality values made no prediction change at any registered origin,including2025W9/W13. The team-completion support arm is also unchanged. Target-share support/E0_ENV differs from the E0_OPcontrol and loses5wins on337cases; that cross-recipe difference is not isolated as a target-share effect. No value group earns inclusion. All exact-line model Briers exceed neutral0.25; no confidence,EV or calibrated skill is established.\n\nTopK membership uses the existingv9 deterministic one-player/side/rank rules on a shared probability-ready board. Unknown outcomes remain selected; no common simultaneous quote board or executable entry is established. All weekly Over-only/Under-only/mixed6/10/20 lists are retained,including losses and fewer-than-K. No new B-owned selective gate is trained. Ninety-percent useful selective reliability is TARGET_NOT_ESTABLISHED; a displayed probability is not demonstrated reliability.\n\nThe feature schema and exports are prepared for A/B retrieval through GitHub,not assumed delivered/admitted. Full budgets/failures remain in run/FIT_LEDGER receipts,including the initial serialization failure after2savedfits; those models were reused without repeat. No calibrator,history/seed search or original forecast revision occurred. All12categories remain in the canonical expansion queue.\n'
    text+='\n\nAttribution: PropLine (prop-line.com), [CC BY4.0](https://creativecommons.org/licenses/by/4.0/), [immutable sample](https://huggingface.co/datasets/propline/graded-player-props-sample/tree/f37857bfdc67ac4e3ecb2851eb274aee7601057d). C adds native NFL joins, independent statistical labels, model inference, identity holds and derived scores. Publisher grades are not verified book settlement. [Source scope and modification credits](../propline-v7/SOURCE_REVIEW_V7_1.json) remain controlling; this licence does not cover held ESPN/Sleeper sources.\n'
    (OUT/'README.md').write_text(text)
    usage=dict(new_fits=sum(r['new_fits'] for r in runtimes),safe_C0_models_reused=2,CPU_seconds=sum(r['CPU_seconds'] for r in runtimes),maximum_RSS_bytes=max(r['max_RSS_bytes'] for r in runtimes),source_calls=0,new_calibrators=0,models_and_rows_bytes=sum(p.stat().st_size for p in ART.rglob('*') if p.is_file()),reports_bytes=sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file()),created_UTC=now(),completed_registered_origins=8,unique_query_origins=4,actual_offer_opportunities=362,known_outcomes=338,decided_qualified_new_model_outcomes=337,identity_held_offers=22,old_common_P3_decided_mask=337,new_original_selections=0,ninety_percent='TARGET_NOT_ESTABLISHED')
    write(OUT/'EXECUTED_RESOURCE_RECEIPT.json',usage)
    print([(r['method_id'],r['COMBINED']['wins'],r['COMBINED']['decided'],r['Brier']) for r in cumulative]);print(usage)


if __name__=='__main__':build()
