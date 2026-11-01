"""Derived summaries of the retained actual-line ledger; no fits or acquisition."""
import csv,gzip,io,json,math
from collections import Counter,defaultdict
from pathlib import Path
import numpy as np
import actual_accuracy_v6 as a
from contracts_v2 import CATEGORIES,grade

OUT=a.ROOT/'reports/propline-v7'
def probability_scores(rows):
    q=[r for r in rows if r['status'] in ['WIN','LOSS','PUSH']];brier=[];logs=[];bins=defaultdict(list)
    for r in q:
        truth=[int(r['actual']<r['line']),int(r['actual']==r['line']),int(r['actual']>r['line'])];p=[r['p_under'],r['p_push'],r['p_over']];brier.append(.5*sum((x-y)**2 for x,y in zip(p,truth)));hit=p[truth.index(1)];logs.append(-math.log(hit) if hit else math.inf);bins[min(9,int(r['p_over']*10))].append((r['p_over'],truth[2]))
    finite=all(math.isfinite(x) for x in logs)
    return dict(n=len(q),half_scaled_UPO_Brier=float(np.mean(brier)) if q else None,log_loss=float(np.mean(logs)) if q and finite else 'Infinity' if q else None,infinite_log_losses=sum(not math.isfinite(x) for x in logs),neutral_halfpoint_Brier=.25 if q and all(r['line']%1==.5 for r in q) else None,calibration='RAW_UNCALIBRATED; deciles are diagnostics, no calibration fit',reliability=[dict(bin=i,n=len(bins[i]),mean_p_over=float(np.mean([p for p,t in bins[i]])) if bins[i] else None,observed_over=float(np.mean([t for p,t in bins[i]])) if bins[i] else None) for i in range(10)])
def build():
    rows,receipts=a.load_records();result={};role=[];week=[];comparisons=[];provider=[]
    byoffer=defaultdict(dict)
    for r in rows:byoffer[r['offer_id']][r['method_id']]=r
    original=json.loads((OUT/'ELIGIBLE_OFFERS.json').read_text());quotes={r['offer_id']:r['quotes'] for r in original['cases']}
    for oid,methods in byoffer.items():
        r=methods['ALWAYS_OVER']
        for side,q in quotes[oid].items():
            actual=r['actual'] if r['appearance']=='PLAYED' else None;g=grade(actual,r['line'],side) if actual is not None else None;general=grade(actual,float(q['line']),side) if actual is not None and q['line'] else None;declared={'won':'WIN','lost':'LOSS','push':'PUSH','void':'VOID'}.get(q['resolution'])
            provider.append(dict(offer_id=oid,side=side,source_csv_line=q['csv_line'],source_general_line=float(q['line']) if q['line'] else None,evaluated_closing_point=r['line'],source_grade=declared,independent_actual=actual,source_actual=float(q['actual_value']) if q['actual_value'] else None,actual_agreement=None if actual is None or not q['actual_value'] else actual==float(q['actual_value']),statistical_closing_grade=g,statistical_general_line_grade=general,provider_grade_agrees_closing=None if g is None else g==declared,provider_grade_agrees_general=None if general is None else general==declared,venue_settlement='UNVERIFIED'))
    a.stable_write(OUT/'PROVIDER_GRADE_LATEST_LABELS_V7_1.json',provider)
    provider_summary=dict(side_views=len(provider),known_independent_statistical_labels=sum(r['independent_actual'] is not None for r in provider),actual_disagreements=[r for r in provider if r['actual_agreement'] is False],provider_grade_disagreements_closing=[r for r in provider if r['provider_grade_agrees_closing'] is False],provider_grade_disagreements_general=[r for r in provider if r['provider_grade_agrees_general'] is False],scope='Provider grades not assumed to bind closing_point, be original clocks or establish venue settlement. Recomputed C full-game statistical grades are primary; role correction included.')
    for cat in CATEGORIES:
        rr=[r for r in rows if r['category']==cat];models={}
        for method in a.METHODS:
            q=[r for r in rr if r['method_id']==method];models[method]=a.aggregate(q)
            if method in ['P2_LAW','P3_DIRECT']:models[method]['probability']=probability_scores(q)
            if method in ['P1_MEDIAN','P1_MEAN']:
                z=[r for r in q if r['status'] in ['WIN','LOSS','PUSH']];errors=np.asarray([r['point']-r['actual'] for r in z]);models[method]['numerical']=dict(n=len(z),MAE=float(np.mean(abs(errors))) if z else None,RMSE=float(np.sqrt(np.mean(errors**2))) if z else None,bias=float(np.mean(errors)) if z else None,P90_absolute_error=float(np.quantile(abs(errors),.9)) if z else None,typed_product='MEDIAN' if method=='P1_MEDIAN' else 'MEAN')
            for p in sorted({r['position'] for r in q}):role.append(dict(category=cat,method_id=method,position=p,**a.aggregate([r for r in q if r['position']==p])))
            for w in range(1,8):week.append(dict(category=cat,method_id=method,week=w,**a.aggregate([r for r in q if r['week']==w])))
        result[cat]=models
        ids=[oid for oid,m in byoffer.items() if m['P2_LAW']['category']==cat and m['P2_LAW']['status'] in ['WIN','LOSS']]
        for method in ['P1_MEDIAN','P1_MEAN','P3_DIRECT','ALWAYS_OVER','ALWAYS_UNDER']:
            pair=[(byoffer[i]['P2_LAW'],byoffer[i][method]) for i in ids if byoffer[i][method]['status'] in ['WIN','LOSS']];delta=[int(b['status']=='WIN')-int(p['status']=='WIN') for p,b in pair];byweek={str(w):float(np.mean([d for d,(p,b) in zip(delta,pair) if p['week']==w])) if any(p['week']==w for p,b in pair) else None for w in [2,3]}
            comparisons.append(dict(category=cat,reference='P2_LAW',candidate=method,same_offer_decided=len(pair),reference_wins=sum(p['status']=='WIN' for p,b in pair),candidate_wins=sum(b['status']=='WIN' for p,b in pair),candidate_minus_reference_hit_percentage_points=100*float(np.mean(delta)) if delta else None,by_week_candidate_minus_reference_rate=byweek,uncertainty='Only2week clusters; no supported paired superiority or promotion'))
    a.stable_write(OUT/'METHOD_RESULTS.json',result);a.stable_write(OUT/'ROLE_RESULTS.json',role);a.stable_write(OUT/'WEEK_RESULTS.json',week);a.stable_write(OUT/'MATCHED_COMPARISONS.json',comparisons);a.stable_write(OUT/'PROVIDER_RECONCILIATION.json',provider_summary)
    j=a.read(a.OUT/'scorecard.json');text='Actual recorded Pinnacle closing-line diagnostics,2026Weeks2–3 only. '+str(len(byoffer))+'unique offer cases; repeated methods are not new NFL outcomes. Full-game official totals including OT are the declared C statistical contract; Pinnacle settlement is unverified.\n\n'
    for method in ['P1_MEDIAN','P1_MEAN','P2_LAW','P3_DIRECT','ALWAYS_OVER','ALWAYS_UNDER']:text+='\n'+a.markdown(j,method=method)+'\n'
    (OUT/'ALL_METHODS.md').write_text(text)
    flat=[]
    for r in rows:
        flat.append({k:r.get(k) for k in ['record_id','grade_id','offer_id','category','method_id','method_version','game_id','player_id','player_name','position','week','venue','product','line_tier','line','comparator','decision_UTC','kickoff_UTC','point_type','point','p_under','p_push','p_over','selected_side','appearance','actual','status','evidence_tier']})
    f=io.StringIO();w=csv.DictWriter(f,fieldnames=list(flat[0]),lineterminator='\n');w.writeheader();w.writerows(flat);(OUT/'GRADED_ROWS_LATEST.csv').write_text(f.getvalue())
    return dict(unique_offers=len(byoffer),canonical_method_rows=len(rows),probability_summaries={c:{m:result[c][m]['probability']|{'reliability':'see METHOD_RESULTS.json'} for m in ['P2_LAW','P3_DIRECT']} for c in ['pass_yd','rush_yd','rec','rec_yd']},provider_reconciliation={k:len(v) if isinstance(v,list) else v for k,v in provider_summary.items()})
if __name__=='__main__':print(json.dumps(build(),indent=2))
