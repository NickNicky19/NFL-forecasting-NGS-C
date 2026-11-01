"""Earlier-only controls, cutoff audits, paired records and workload summaries."""
import argparse,csv,gzip,io,json,math
from collections import Counter,defaultdict
from pathlib import Path
import numpy as np
from reliability_v8 import ROOT,OUT,ART,read,write,key,references,now
from diagnose_v8 import latest,cases,classify,metrics,ci
from data_v2 import load,History,admitted_roles
from contracts_v2 import CATEGORIES,grade
from safe_models_v4 import law_load
import actual_accuracy_v6 as a

def build(inputs):
    raw=latest();cmap=cases();bank=references();d,g,teams=load(inputs);records=d.to_dict('records');hist=History(d[d.season>=2022],'player_id');th=History(teams[teams.season>=2022],'team');fact={(r['game_id'],r['player_id']):r for r in records};cache={};bench=[];timing=[];prior=[];pair=[]
    for old in raw:
        if old['method_id']!='P2_LAW':continue
        c=cmap[old['offer_id']];ref=bank['references'].get('|'.join(key(old)));fit_origin=ref['fit_origin_UTC'] if ref else min(e['scheduled_kickoff_UTC'] for e in [v['event'] for v in cmap.values()] if e['week']==old['week']);pkey=(old['category'],old['week'],old['position'])
        if abs(old['line']%1-.5)>=1e-12:
            r={k:v for k,v in old.items() if k not in ['law','p_under','p_push','p_over','probability_line','information_set_id','probability_inference_evidence_reference']};rid=old['offer_id']+'-EARLIER_PREVALENCE_V8';r.update(record_id=rid,grade_id=rid+'-G1',method_id='EARLIER_PREVALENCE_V8',method_version='C-EARLIER-ROLE-PREVALENCE-v8',selector_id='EARLIER_PREVALENCE_V8-strict-v8',selected_side=None,status='UNAVAILABLE_FORECAST',unavailable_reason='REFERENCE_REGISTERED_FOR_DECISIVE_HALFPOINT_ONLY;NO_PUSH_PROBABILITY_INVENTED',forecast_id=None,graded_UTC=now());a.validate_row(r);bench.append(r);continue
        if pkey not in cache:
            train=[r for r in records if r['position'] in admitted_roles(old['category']) and r['available']<a.instant(fit_origin).timestamp() and r['values'][old['category']] is not None];yr=[r['values'][old['category']] for r in train if r['position']==old['position']];fallback=not len(yr);yr=yr if yr else [r['values'][old['category']] for r in train];cache[pkey]=(np.asarray(yr,float),fallback,max([r['available'] for r in train],default=None))
        y,fallback,last=cache[pkey];assert len(y) and abs(old['line']%1-.5)<1e-12,'REFERENCE_REGISTERED_FOR_DECISIVE_HALFPOINT_ONLY';p=(float(np.sum(y>old['line']))+1)/(len(y)+2);side='ABSTAIN' if p==.5 else 'OVER' if p>.5 else 'UNDER';r={k:v for k,v in old.items() if k not in ['law','information_set_id','probability_inference_evidence_reference']};rid=old['offer_id']+'-EARLIER_PREVALENCE_V8';r.update(record_id=rid,grade_id=rid+'-G1',method_id='EARLIER_PREVALENCE_V8',method_version='C-EARLIER-ROLE-PREVALENCE-v8',selector_id='EARLIER_PREVALENCE_V8-strict-v8',selected_side=side,status='ABSTAIN' if side=='ABSTAIN' else 'UNKNOWN_PARTICIPATION' if old['appearance']!='PLAYED' else grade(old['actual'],old['line'],side),p_over=p,p_under=1-p,p_push=0,probability_line=old['line'],information_set_id='C-EARLIER-ROLE-PREVALENCE-v8:'+':'.join(map(str,pkey)),probability_inference_evidence_reference='artifacts/reliability-v8/PREVALENCE_GRADED_ROWS.json.gz',earlier_role_observations=len(y),role_to_global_fallback=fallback,latest_training_available=last,fit_origin_UTC=fit_origin,forecast_generated_UTC=now(),graded_UTC=now());a.validate_row(r);bench.append(r)
        if ref:
            saved=ref['saved'];kick=a.instant(old['decision_UTC']).timestamp();at=max(a.instant(q['closing_at']).timestamp() for q in c['quotes'].values());pid=old['player_id'];player_before=[(r['game_id'],r['player_id']) for r in hist.before(pid,kick)];quote_before=[(r['game_id'],r['player_id']) for r in hist.before(pid,at)];team_before=[r['game_id'] for r in th.before(saved['team'],kick,3)];team_quote=[r['game_id'] for r in th.before(saved['team'],at,3)]
            timing.append(dict(offer_id=old['offer_id'],book=old['venue'],category=old['category'],game_id=old['game_id'],player_id=pid,quote_cutoff_UTC=__import__('datetime').datetime.fromtimestamp(at,__import__('datetime').timezone.utc).isoformat(),saved_feature_cutoff_UTC=old['decision_UTC'],model_fit_origin_UTC=fit_origin,max_side_quote_before_nominal_fit_origin=at<a.instant(fit_origin).timestamp(),min_side_quote_before_nominal_fit_origin=min(a.instant(q['closing_at']).timestamp() for q in c['quotes'].values())<a.instant(fit_origin).timestamp(),quote_cutoff_basis='MAX_OF_BOTH_SOURCE_SIDE_CLOCKS;NOT_SELECTED_SIDE_OR_BOARD_AUTHENTICATION',player_membership_changed=player_before!=quote_before,team_membership_changed=team_before!=team_quote,player_saved_prefix=player_before,player_quote_prefix=quote_before,team_saved_prefix=team_before,team_quote_prefix=team_quote,old_lag_assumption='kickoff+7days;not authenticated publication',age_seconds=kick-at))
            law=law_load(ref['law']);emp=float(law.v@law.w)/law.scale;prior_mean=law.prior.mean()/law.scale;prior_over=1-law.prior.cdf(math.floor(old['line']));emp_over=float(law.w[law.v>old['line']].sum());prior.append(dict(offer_id=old['offer_id'],book=old['venue'],category=old['category'],prior_alpha=law.a,empirical_mean=emp,prior_true_mean=prior_mean,stored_prior_mu=law.prior.mu,mean_contribution=law.a*(prior_mean-emp),pOver_contribution=law.a*(prior_over-emp_over)))
    target=ART/'PREVALENCE_GRADED_ROWS.json.gz'
    if not target.exists():write(target,dict(schema='C-QUALIFIED-ACTUAL-PROP-ROWS-v6',source_review_id='C-PROPLINE-CCBY-PREVALENCE-v8',retained_evidence=[dict(path=p,SHA256=a.sha(ROOT/p)) for p in ['artifacts/basic-football-facts-v2.1.zip','sources/propline-v7/nfl_graded_props_14d.csv.gz','protocol/SELECTED_RELIABILITY_V8.json']],rows=bench))
    else:bench=read(target)['rows']
    write(ART/'CUTOFF_AUDIT.json.gz',timing);write(OUT/'PRIOR_AUDIT.json.gz',prior)
    intersection=read(OUT/'BOOK_INTERSECTIONS.json.gz');byoffer={(r['venue'],key(r),r['method_id']):r for r in raw};same_scores=[]
    for group in intersection:
      for cat in ['pass_yd','rush_yd','rec','rec_yd']:
       for method in ['P2_LAW','P3_DIRECT','P1_MEAN','P1_MEDIAN','P2_LINKED_V8','P2_WORKLOAD_V8']:
        if method in ['P2_LINKED_V8','P2_WORKLOAD_V8'] and cat!='pass_yd':continue
        common=[(x['category'],x['game_id'],x['player_id']) for x in group['same_cases'] if x['category']==cat];panel=[]
        for book in group['books']:
            rr=[classify(byoffer[(book,k,method)],cmap[byoffer[(book,k,method)]['offer_id']],bank) for k in common if (book,k,method) in byoffer];panel.append(dict(book=book,**metrics(rr)))
        same_scores.append(dict(books=group['books'],category=cat,method=method,exact_same_line_cases=len(common),panels=panel,only_same_threshold_period_role_cutoff=True,price_and_observation_times_can_differ=True))
    write(OUT/'EXACT_INTERSECTION_RESULTS.json.gz',same_scores)
    market=[]
    for c in cmap.values():
        qq=c['quotes'];same=qq['OVER']['closing_at']==qq['UNDER']['closing_at'];valid=all(q['closing_price'] and abs(float(q['closing_price']))>=100 for q in qq.values());market.append(dict(offer_id=c['offer_id'],book=c['venue'],same_point=True,same_side_clock=same,compatible_american_prices_present=valid,observed_market_OPEN_state=False,qualified_market_reference=False,reason='CSV_HAS_NO_HISTORICAL_OPEN_LIFECYCLE_STATE;NO_MANUFACTURED_PAIRED_MARKET'))
    write(OUT/'MARKET_BENCHMARK_GATES.json.gz',market)
    benchmark=[]
    for book in ['pinnacle','draftkings','fanduel']:
     for cat in ['pass_yd','rush_yd','rec','rec_yd']:
      q=[r for r in raw if r['venue']==book and r['category']==cat and r['method_id']=='P2_LAW'];matched={r['offer_id'] for r in q if r['status'] in ['WIN','LOSS','PUSH']};br=[classify(r,cmap[r['offer_id']],bank) for r in bench if r['venue']==book and r['category']==cat and r['offer_id'] in matched];benchmark.append(dict(book=book,category=cat,method='EARLIER_ROLE_PREVALENCE',same_P2_known_mask=True,**metrics(br)))
    write(OUT/'EARLIER_REFERENCE_RESULTS.json',benchmark)
    enriched=[classify(r,cmap[r['offer_id']],bank) for r in raw];timegroups=[]
    bytime={r['offer_id']:r for r in timing}
    for book in ['pinnacle','draftkings','fanduel']:
     for cat in ['pass_yd','rush_yd','rec','rec_yd']:
      for method in ['P2_LAW','P3_DIRECT']:
       for changed in [False,True]:
        q=[r for r in enriched if r['venue']==book and r['category']==cat and r['method_id']==method and r['offer_id'] in bytime and (bytime[r['offer_id']]['player_membership_changed'] or bytime[r['offer_id']]['team_membership_changed'])==changed];timegroups.append(dict(book=book,category=cat,method=method,membership_changed_between_quote_and_saved_cutoff=changed,**metrics(q)))
    write(OUT/'CUTOFF_SENSITIVITY.json.gz',timegroups)
    workloads=read(ART/'WORKLOAD_PREDICTIONS.json.gz');numerical=[]
    for oid in sorted({r['origin_id'] for r in workloads}):
      pp=[r for r in workloads if r['origin_id']==oid and r['actual'] is not None]
      for arm in ['RETAINED_P2','P2_LINKED_V8','P2_WORKLOAD_V8']:
        aa=[r['arms'][arm] for r in pp];errors=np.asarray([x['median']-r['actual'] for x,r in zip(aa,pp)]);meanerror=np.asarray([x['mean']-r['actual'] for x,r in zip(aa,pp)]);nll=[float(x['NLL']) for x in aa]
        numerical.append(dict(origin_id=oid,method=arm,n=len(pp),games=len({r['game_id'] for r in pp}),MAE_median=float(np.mean(abs(errors))),MAE_mean=float(np.mean(abs(meanerror))),RMSE_mean=float(np.sqrt(np.mean(meanerror**2))),mean_bias=float(meanerror.mean()),CRPS=float(np.mean([x['CRPS'] for x in aa])),NLL=float(np.mean(nll)) if all(np.isfinite(nll)) else 'Infinity',infinite_NLL=sum(not np.isfinite(x) for x in nll),actual_attempt_mean=float(np.mean([r['actual_attempts'] for r in pp])),forecast_attempt_mean=float(np.mean([r['attempt_mean'] for r in pp])),leaf_missing_bin_forecast_mass=float(np.mean([x.get('leaf_missing_bin_forecast_mass',0) for x in aa])),scope='ONLY_REGISTERED_WEEK;RETROSPECTIVE_PARTICIPANT_PANEL'))
    write(OUT/'WORKLOAD_NUMERICAL.json',numerical)
    opportunity=[]
    for oid in sorted({r['origin_id'] for r in workloads}):
        pp=[r for r in workloads if r['origin_id']==oid];err=np.asarray([r['attempt_mean']-r['actual_attempts'] for r in pp]);laws=[law_load(r['attempt_law']) for r in pp]
        opportunity.append(dict(origin_id=oid,n=len(pp),MAE_mean=float(np.mean(abs(err))),RMSE_mean=float(np.sqrt(np.mean(err**2))),signed_bias=float(err.mean()),CRPS=float(np.mean([law.crps(r['actual_attempts']) for law,r in zip(laws,pp)])),NLL=float(np.mean([-law.logpmf(int(r['actual_attempts'])) for law,r in zip(laws,pp)])),postgame_actual_exposure_used_only_for_grading=True))
    write(OUT/'WORKLOAD_OPPORTUNITY_ERRORS.json',opportunity)
    fieldnames=['category','season','week','book','qualified_offers','state','scoring_contract']
    f=io.StringIO();w=csv.DictWriter(f,fieldnames=fieldnames,lineterminator='\n');w.writeheader()
    for cat in CATEGORIES:
      for season in [2022,2023,2024,2025,2026]:
       for week in range(1,8 if season==2026 else 19):
        for book in ['pinnacle','draftkings','fanduel']:
            nn=sum(c['category']==cat and c['event']['week']==week and season==2026 and c['venue']==book for c in cmap.values());w.writerow(dict(category=cat,season=season,week=week,book=book,qualified_offers=nn,state='EXECUTED_LAST_RECORDED_LINE_DIAGNOSTIC' if nn else 'SOURCE_HAS_NO_MARKET' if cat not in ['pass_yd','rush_yd','rec','rec_yd'] else 'SOURCE_HAS_NO_WEEK_OR_SEASON',scoring_contract='nick-chart-ppr-v1' if cat=='fpts' else 'rush-or-rec-at-least-one-v1' if cat=='anytime_td' else 'official-player-fullgame-OT-v1'))
    (OUT/'OFFER_COVERAGE.csv').write_text(f.getvalue())
    summaries=[]
    for book in ['pinnacle','draftkings','fanduel']:
      for method in ['P2_LAW','P3_DIRECT','P1_MEAN','P1_MEDIAN','ALWAYS_OVER','ALWAYS_UNDER','P2_LINKED_V8','P2_WORKLOAD_V8']:
        rr=[r for r in raw if r['venue']==book and r['method_id']==method];summaries.append(dict(book=book,method=method,**a.aggregate(rr)))
    write(OUT/'BOOK_TOTALS.json',summaries)
    output=dict(canonical_method_rows=len(raw),unique_offer_quotes=len(cmap),unique_football_cases=len({key(r) for r in raw}),unique_player_games=len({(r['game_id'],r['player_id']) for r in raw}),games=len({r['game_id'] for r in raw}),weeks=2,cutoff_membership_changed=sum(r['player_membership_changed'] or r['team_membership_changed'] for r in timing),cutoff_audited=len(timing),max_side_quote_before_nominal_fit_origin=sum(r['max_side_quote_before_nominal_fit_origin'] for r in timing),qualified_no_vig_market_cases=0,shared_source_football_not_new_confirmation=True)
    write(OUT/'OVERVIEW.json',output);return output
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--inputs',type=Path,required=True);x=p.parse_args();print(json.dumps(build(x.inputs),indent=2))
