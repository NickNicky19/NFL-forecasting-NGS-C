"""Selected-side reliability and expressly retrospective capacity diagnostics."""
import argparse,csv,gzip,io,json,math,zipfile
from collections import Counter,defaultdict
from pathlib import Path
import numpy as np
from sklearn.metrics import roc_auc_score,average_precision_score
import actual_accuracy_v6 as a
from reliability_v8 import ROOT,OUT,ART,read,write,key,references
from safe_models_v4 import law_load
from contracts_v2 import CATEGORIES

def latest():
    base,_=a.load_records();extra=read(ART/'BOOK_GRADED_ROWS.json.gz')['rows']
    if (ART/'WORKLOAD_GRADED_ROWS.json.gz').exists():extra+=read(ART/'WORKLOAD_GRADED_ROWS.json.gz')['rows']
    return a.deduplicate(base+extra)
def cases():
    p=read(ROOT/'reports/propline-v7/ELIGIBLE_OFFERS.json')['cases']+read(ART/'BOOK_CASES.json.gz')['cases']
    return {c['offer_id']:c|dict(venue=c.get('venue','pinnacle')) for c in p}
def wilson(w,n):
    if not n:return [None,None]
    z=1.959963984540054;p=w/n;d=1+z*z/n;m=(p+z*z/(2*n))/d;h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d;return [m-h,m+h]
def ci(rows):
    q=[r for r in rows if r['status'] in ['WIN','LOSS']];by=defaultdict(lambda:[0,0])
    for r in q:by[r['game_id']][r['status']=='LOSS']+=1
    if len(by)<20:return dict(kind='WILSON_INDEPENDENCE_DIAGNOSTIC',interval=wilson(sum(r['status']=='WIN' for r in q),len(q)),games=len(by),week_clusters=len({r['week'] for r in q}),qualification='SMALL_GAME_POOL;ONLY_TWO_WEEKS')
    z=np.asarray(list(by.values()));rng=np.random.default_rng(881102);s=z[rng.integers(len(z),size=(2000,len(z)))].sum(axis=1);v=s[:,0]/s.sum(axis=1)
    return dict(kind='GAME_BLOCK_BOOTSTRAP_2000',interval=np.quantile(v,[.025,.975]).tolist(),games=len(by),week_clusters=len({r['week'] for r in q}),qualification='CONDITIONAL_ON_TWO_RESEARCH_EXPOSED_WEEKS;NOT_MULTISEASON_CONFIRMATION')
def probability(r,bank):
    if r['method_id'] in ['P2_LAW','P3_DIRECT','P2_WORKLOAD_V8','P2_LINKED_V8','EARLIER_PREVALENCE_V8']:return {s:r['p_'+s] for s in ['under','push','over']} if r.get('p_over') is not None else None
    if r['method_id'] in ['P1_MEAN','P1_MEDIAN']:
        ref=bank['references'].get('|'.join(key(r)))
        return law_load(ref['law']).probability(r['line']) if ref and r['selected_side'] in ['OVER','UNDER'] else None
    return None
def classify(r,c,bank):
    ref=bank['references'].get('|'.join(key(r)));ps=probability(r,bank);side=r.get('selected_side');sprob=ps[side.lower()] if ps and side in ['OVER','UNDER'] else None
    quote=c['quotes'].get(side) or c['quotes']['OVER'];age=(a.instant(r['kickoff_UTC'])-a.instant(quote['closing_at'])).total_seconds();hist=ref['saved']['features'][3] if ref else None
    return r|dict(_ps=ps,_confidence=sprob,_age=age,_age_band='LE15MIN' if age<=900 else '15TO60MIN' if age<=3600 else '1TO24H' if age<=86400 else 'GT24H',_history='UNKNOWN' if hist is None else 'ZERO' if hist==0 else 'ONE_TWO' if hist<3 else 'THREE_PLUS',_clock_pair='EQUAL' if c['quotes']['OVER']['closing_at']==c['quotes']['UNDER']['closing_at'] else 'DIFFERENT',_provider_void=any(q['resolution']=='void' for q in c['quotes'].values()))
def metrics(rows):
    known=[r for r in rows if r['status'] in ['WIN','LOSS','PUSH'] and r['_ps'] is not None];dec=[r for r in known if r['status']!='PUSH'];n=len(known);wins=sum(r['status']=='WIN' for r in known)
    ps=np.asarray([[r['_ps'][s] for s in ['under','push','over']] for r in known]);truth=np.asarray([[r['actual']<r['line'],r['actual']==r['line'],r['actual']>r['line']] for r in known],float)
    conf=np.asarray([r['_confidence'] for r in known]);over=ps[:,2] if n else np.asarray([]);y=truth[:,2] if n else np.asarray([]);logs=[-math.log(float(p@t)) if p@t>0 else math.inf for p,t in zip(ps,truth)];points=[(r.get('point'),r['actual'],r['line']) for r in known if r.get('point') is not None]
    bins=[]
    for i in range(10):
        rr=[r for r in known if min(9,int(r['_confidence']*10))==i];w=sum(r['status']=='WIN' for r in rr);nn=len(rr);pred=sum(r['_confidence'] for r in rr)/nn if nn else None;interval=wilson(w,nn)
        bins.append(dict(bin=i,n=nn,wins=w,mean_selected_probability=pred,observed_win_rate=w/nn if nn else None,probability_minus_observed=None if not nn else pred-w/nn,winrate_interval=interval,gap_interval=None if not nn else [pred-interval[1],pred-interval[0]],uncertainty='WILSON_INDEPENDENCE_DIAGNOSTIC;small/dependentbins',role_counts=dict(Counter(r['position'] for r in rr))))
    expected=float(conf.sum()) if n else None;half=[i for i,r in enumerate(known) if abs(r['line']%1-.5)<1e-12];allconf=[r['_confidence'] for r in rows if r['_confidence'] is not None]
    return dict(eligible_rows=len(rows),known_probability_rows=n,all_selected_probability_rows=len(allconf),all_selected_mean_confidence=float(np.mean(allconf)) if allconf else None,all_selected_expected_wins=float(sum(allconf)) if allconf else None,decided=len(dec),wins=wins,losses=sum(r['status']=='LOSS' for r in known),pushes=sum(r['status']=='PUSH' for r in known),hit_rate=wins/len(dec) if dec else None,mean_predicted_over=float(over.mean()) if n else None,actual_over_frequency=float(y.mean()) if n else None,over_probability_bias=float(over.mean()-y.mean()) if n else None,mean_selected_confidence=float(conf.mean()) if n else None,selected_confidence_minus_unconditional_winrate=float(conf.mean()-wins/n) if n else None,expected_wins=expected,actual_wins=wins,expected_minus_actual_wins=None if expected is None else expected-wins,half_scaled_UPO_Brier=float(np.mean(.5*np.sum((ps-truth)**2,axis=1))) if n else None,log_loss=float(np.mean(logs)) if n and all(math.isfinite(l) for l in logs) else 'Infinity' if n else None,infinite_log_losses=sum(not math.isfinite(l) for l in logs),neutral_halfpoint_Brier=.25 if half else None,halfpoint_n=len(half),over_ROC_AUC=float(roc_auc_score(y,over)) if n and len(set(y))==2 else None,over_average_precision=float(average_precision_score(y,over)) if n and len(set(y))==2 else None,selected_confidence_ROC_AUC=float(roc_auc_score([r['status']=='WIN' for r in known],conf)) if n and len({r['status']=='WIN' for r in known})==2 else None,point_signed_error=float(np.mean([p-y for p,y,l in points])) if points else None,point_minus_line=float(np.mean([p-l for p,y,l in points])) if points else None,selection_counts=dict(Counter(r.get('selected_side') for r in rows)),states=dict(Counter(r['status'] for r in rows)),confidence_bins=bins,uncertainty=ci(rows),games=len({r['game_id'] for r in rows}),weeks=len({r['week'] for r in rows}),unique_football_cases=len({key(r) for r in rows}),fallback=sum(r.get('fallback') is True for r in rows),note='P1confidence uses OWN selected side under retained law, including below50%; known-mask confidence/expectedwins are separate from all-selected expectations; raw winprobabilities retain push conditioning')

def intersections(cmap,rows):
    bybook={b:{key(c|dict(game_id=c['event']['game_id'])):c for c in cmap.values() if c['venue']==b} for b in ['pinnacle','draftkings','fanduel']};out=[]
    for books in [('pinnacle','draftkings'),('pinnacle','fanduel'),('draftkings','fanduel'),('pinnacle','draftkings','fanduel')]:
        common=set.intersection(*(set(bybook[b]) for b in books));same=[];different=[]
        for k in sorted(common):
            cc=[bybook[b][k] for b in books];points={c['line'] for c in cc};record=dict(category=k[0],game_id=k[1],player_id=k[2],lines={b:bybook[b][k]['line'] for b in books},closing_prices={b:{s:q['closing_price'] for s,q in bybook[b][k]['quotes'].items()} for b in books},quote_clocks={b:{s:q['closing_at'] for s,q in bybook[b][k]['quotes'].items()} for b in books},role_match=len({c['position'] for c in cc})==1,cutoff_match=len({c['event']['scheduled_kickoff_UTC'] for c in cc})==1)
            (same if len(points)==1 and record['role_match'] and record['cutoff_match'] else different).append(record)
        out.append(dict(books=list(books),common_football_cases=len(common),exact_same_line_period_role_cutoff=len(same),changed_line_or_role_or_cutoff=len(different),same_cases=same,mismatches=different,price_or_quote_clock_equality_not_assumed=True,no_independent_confirmation=True))
    return out
def rank_diagnostic(rows,cmap,bank):
    membership=[];summaries=[];exclusions=[];methods=['P2_LAW','P3_DIRECT']+[m for m in ['P2_WORKLOAD_V8','P2_LINKED_V8'] if any(r['method_id']==m for r in rows)]
    for book in ['pinnacle','draftkings','fanduel']:
      for week in [2,3]:
       for method in methods:
        source=[r for r in rows if r['venue']==book and r['week']==week and r['method_id']==method]
        board=[r for r in source if r['_confidence'] is not None and r['selected_side'] in ['OVER','UNDER']]
        for r in source:
            if r not in board:exclusions.append(dict(book=book,week=week,method=method,record_id=r['record_id'],offer_id=r['offer_id'],reason='TECHNICAL_UNAVAILABLE' if r['status']=='UNAVAILABLE_FORECAST' else 'INTENTIONAL_TIE_ABSTENTION' if r['selected_side']=='ABSTAIN' else 'PROBABILITY_OR_SIDE_UNAVAILABLE'))
        digest=a.digest([{k:r[k] for k in ['record_id','offer_id','line','p_under','p_push','p_over','selected_side']} for r in sorted(board,key=lambda r:r['record_id'])]);earliest=min((r['kickoff_UTC'] for r in board),default=None)
        for scope,cat in [('GLOBAL','ALL')]+[('WITHIN_CATEGORY',c) for c in MARKETS.values()]:
         if method in ['P2_WORKLOAD_V8','P2_LINKED_V8'] and (scope=='GLOBAL' or cat!='pass_yd'):continue
         for side in ['MIXED','OVER_ONLY','UNDER_ONLY']:
          candidate=[r for r in board if (cat=='ALL' or r['category']==cat) and (side=='MIXED' or r['selected_side']==side.split('_')[0])];ordered=sorted(candidate,key=lambda r:(-r['_confidence'],r['kickoff_UTC'],r['game_id'],r['player_id'],r['category'],r['offer_id']))
          for kmax in [6,10,20]:
           used=set();selected=[]
           for r in ordered:
            if r['player_id'] in used:continue
            used.add(r['player_id']);selected.append(r)
            if len(selected)==kmax:break
           rid=f'LRL8-{book}-W{week}-{method}-{scope}-{cat}-{side}-K{kmax}';summary=dict(diagnostic_id=rid,tier='EXPLORATORY_LAST_RECORDED_LINE_RANKING_DIAGNOSTIC',book=book,week=week,method=method,scope=scope,category=cat,side_variant=side,K=kmax,source_eligible_count=len(source),technical_or_tie_excluded=len(source)-len(board),valid_board_count=len(board),candidate_count=len(candidate),selected_count=len(selected),fewer_than_K=len(selected)<kmax,board_SHA256=digest,role_composition=dict(Counter(r['position'] for r in selected)),**metrics(selected));summary['timing_limitation']='NOT_A_SIMULTANEOUS_PREGAME_SLATE;lastrecordedquotes may occur after firstincludedgame;no linecontinuity/marketOPEN evidence;not a ticket or 6/6';summary['board_quotes_after_first_kickoff']=sum(any(a.instant(q)>a.instant(earliest) for q in r['source_snapshot_clocks'].values()) for r in board) if earliest else None
           first=min((r['kickoff_UTC'] for r in selected),default=None);summary['selected_quotes_after_earliest_selected_kickoff']=sum(any(a.instant(q)>a.instant(first) for q in r['source_snapshot_clocks'].values()) for r in selected) if first else None;summary['selected_forecast_cutoffs_after_earliest_selected_kickoff']=sum(a.instant(r['decision_UTC'])>a.instant(first) for r in selected) if first else None
           no_void=[r for r in selected if not r['_provider_void']];summary['provider_VOID_sensitivity_fixed_membership']=dict(excluded_offer_ids=[r['offer_id'] for r in selected if r['_provider_void']],replacement_performed=False,**metrics(no_void));summaries.append(summary)
           for rank,r in enumerate(selected,1):membership.append(dict(diagnostic_id=rid,rank=rank,record_id=r['record_id'],offer_id=r['offer_id'],category=r['category'],game_id=r['game_id'],player_id=r['player_id'],line=r['line'],selected_side=r['selected_side'],selected_probability=r['_confidence'],status=r['status'],actual=r['actual'],role=r['position'],board_SHA256=digest,timing_limitation=summary['timing_limitation']))
    write(ART/'RANK_EXCLUSIONS.json.gz',exclusions);return membership,summaries

def diagnose():
    from reliability_v8 import MARKETS
    raw=latest();cmap=cases();bank=references();rows=[classify(r,cmap[r['offer_id']],bank) for r in raw];reports=[];void=[]
    for book in ['pinnacle','draftkings','fanduel']:
     for cat in MARKETS.values():
      for method in ['P1_MEAN','P1_MEDIAN','P2_LAW','P3_DIRECT','P2_LINKED_V8','P2_WORKLOAD_V8']:
       if method in ['P2_LINKED_V8','P2_WORKLOAD_V8'] and cat!='pass_yd':continue
       rr=[r for r in rows if r['venue']==book and r['category']==cat and r['method_id']==method]
       groups=[('ALL','ALL',rr)]+[('SIDE',s,[r for r in rr if r['selected_side']==s]) for s in ['OVER','UNDER']]+[('WEEK',str(w),[r for r in rr if r['week']==w]) for w in [2,3]]
       for field,values in [('_history',['ZERO','ONE_TWO','THREE_PLUS']),('_age_band',['LE15MIN','15TO60MIN','1TO24H','GT24H']),('_clock_pair',['EQUAL','DIFFERENT']),('position',['QB','RB','WR','TE'])]:groups += [(field,v,[r for r in rr if r[field]==v]) for v in values]
       for kind,value,q in groups:reports.append(dict(book=book,category=cat,method=method,group=kind,value=value,**metrics(q)))
       for rule in ['PRIMARY_C_STATISTICAL_PLAYED','EXCLUDE_CASE_IF_EITHER_SOURCE_SIDE_VOID']:
        qq=rr if rule.startswith('PRIMARY') else [r for r in rr if not r['_provider_void']];void.append(dict(book=book,category=cat,method=method,sensitivity=rule,excluded_ids=[r['offer_id'] for r in rr if r not in qq],provider_VOID_cases=sum(r['_provider_void'] for r in rr),**metrics(qq)))
    write(OUT/'RELIABILITY.json.gz',reports);write(OUT/'VOID_SENSITIVITY.json.gz',void);write(OUT/'BOOK_INTERSECTIONS.json.gz',intersections(cmap,rows))
    membership,ranking=rank_diagnostic(rows,cmap,bank);write(ART/'RANK_MEMBERSHIP.json.gz',membership);write(OUT/'RANK_RESULTS.json.gz',ranking)
    headline=[r for r in reports if r['group']=='ALL' and r['method'] in ['P2_LAW','P3_DIRECT']];write(OUT/'RELIABILITY_HEADLINE.json',headline)
    return dict(books=3,unique_football_cases=len({key(r) for r in raw}),unique_player_games=len({(r['game_id'],r['player_id']) for r in raw}),unique_games=len({r['game_id'] for r in raw}),weeks=len({r['week'] for r in raw}),method_rows=len(raw),source_offer_cases=len(cmap),reliability_views=len(reports),exploratory_ranked_lists=len(ranking),ranked_membership_rows=len(membership),headline=[{k:r[k] for k in ['book','category','method','known_probability_rows','hit_rate','mean_selected_confidence','mean_predicted_over','actual_over_frequency','half_scaled_UPO_Brier','over_ROC_AUC','selected_confidence_ROC_AUC']} for r in headline])

from reliability_v8 import MARKETS
if __name__=='__main__':print(json.dumps(diagnose(),indent=2))
