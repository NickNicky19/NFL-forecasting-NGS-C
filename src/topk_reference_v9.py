"""One frozen zero-refit, common-pool ranking benchmark. Exposed diagnostics only."""
import argparse,gzip,hashlib,json,math,time,resource,signal
from collections import Counter,defaultdict
from pathlib import Path
import numpy as np
import actual_accuracy_v6 as a
from reliability_v8 import read,write,key
from diagnose_v8 import classify,cases,metrics

ROOT=a.ROOT;OUT=ROOT/'reports/topk-reference-v9';ART=ROOT/'artifacts/topk-reference-v9'
METHODS=['P2_LAW','P3_DIRECT','EARLIER_PREVALENCE_V8']
def common_pool(rows):
    by=defaultdict(dict)
    for r in rows:
        if r['method_id'] in METHODS and r['season']==2026 and r['week'] in [2,3]:by[r['offer_id']][r['method_id']]=r
    admitted={};held=[]
    for oid,group in sorted(by.items()):
        reasons=[]
        for m in METHODS:
            r=group.get(m);p=[r.get('p_'+s) for s in ['under','push','over']] if r else []
            if not r:reasons.append(m+':MISSING_RECORD')
            elif len(p)!=3 or any(not isinstance(v,(int,float)) or not math.isfinite(v) or not 0<=v<=1 for v in p) or abs(sum(p)-1)>1e-10:reasons.append(m+':PROBABILITY_TECHNICALLY_UNAVAILABLE')
        if not reasons:
            assert len({(r['venue'],r['week'],r['category'],r['game_id'],r['player_id'],r['line'],r['period'],r['scoring_contract_id'],r['decision_UTC']) for r in group.values()})==1
            admitted[oid]=group
        else:held.append(dict(offer_id=oid,reasons=reasons))
    return admitted,held

def choose(rows,side,K):
    board=[r for r in rows if r.get('_confidence') is not None and r['selected_side'] in ['OVER','UNDER'] and (side=='MIXED' or r['selected_side']==side.split('_')[0])]
    ordered=sorted(board,key=lambda r:(-r['_confidence'],r['kickoff_UTC'],r['game_id'],r['player_id'],r['category'],r['offer_id']));selected=[];seen=set()
    for r in ordered:
        if r['player_id'] in seen:continue
        seen.add(r['player_id']);selected.append(r)
        if len(selected)==K:break
    return selected,board

def implied(price):
    try:
        x=float(price)
        if not math.isfinite(x) or abs(x)<100:return None
        return 100/(100+x) if x>0 else -x/(100-x)
    except (TypeError,ValueError):return None

def build():
    assert not (OUT/'RUN.json').exists(),'FROZEN_AUDIT_EXISTS'
    start=time.monotonic();cpu=time.process_time();signal.signal(signal.SIGPROF,lambda *_:(_ for _ in ()).throw(RuntimeError('V9_TOPK_CPU_CAP180')));signal.setitimer(signal.ITIMER_PROF,180)
    rows,receipts=a.load_records();pool,excluded=common_pool(rows);cmap=cases();bank=read(ROOT/'artifacts/reliability-v8/REFERENCE_BANK.json.gz');classified={oid:{m:classify(r,cmap[oid],bank) for m,r in g.items()} for oid,g in pool.items()};results=[];members=[]
    for book in ['pinnacle','draftkings','fanduel']:
     for week in [2,3]:
      universe=[g for g in classified.values() if g[METHODS[0]]['venue']==book and g[METHODS[0]]['week']==week]
      for scope,category in [('GLOBAL','ALL')]+[('WITHIN_CATEGORY',c) for c in ['pass_yd','rush_yd','rec','rec_yd']]:
       base=[g for g in universe if category=='ALL' or g[METHODS[0]]['category']==category]
       for side in ['MIXED','OVER_ONLY','UNDER_ONLY']:
        for K in [6,10,20]:
         for method in METHODS:
            source=[g[method] for g in base];selected,board=choose(source,side,K);rid=f'TKR9-{book}-W{week}-{method}-{scope}-{category}-{side}-K{K}';known=[r for r in selected if r['status'] in ['WIN','LOSS']];first=min((r['kickoff_UTC'] for r in selected),default=None)
            prices=[implied(cmap[r['offer_id']]['quotes'][r['selected_side']]['closing_price']) for r in selected];priceknown=[p for p in prices if p is not None]
            result=dict(diagnostic_id=rid,book=book,week=week,method=method,scope=scope,category=category,side_variant=side,K=K,common_eligible=len(source),side_eligible=len(board),unique_side_eligible_players=len({r['player_id'] for r in board}),intentional_ties=sum(r['selected_side']=='ABSTAIN' for r in source),selected_count=len(selected),fewer_than_K=len(selected)<K,role_composition=dict(Counter(r['position'] for r in selected)),category_composition=dict(Counter(r['category'] for r in selected)),tier='EXPLORATORY_LAST_RECORDED_LINE_RANKING_DIAGNOSTIC',no_common_live_board=True,no_entry_or_payout=True,mean_confidence_decided=sum(r['_confidence'] for r in known)/len(known) if known else None,expected_wins_decided=sum(r['_confidence'] for r in known) if known else None,selected_quotes_after_first_selected_kickoff=sum(any(a.instant(t)>a.instant(first) for t in r['source_snapshot_clocks'].values()) for r in selected) if first else None,selected_forecast_cutoffs_after_first_selected_kickoff=sum(a.instant(r['decision_UTC'])>a.instant(first) for r in selected) if first else None,main_alternate_tier='UNVERIFIED',unilateral_price_diagnostic=dict(priced_selected=len(priceknown),mean_raw_implied_probability=sum(priceknown)/len(priceknown) if priceknown else None,qualification='SINGLE_SIDE_RECORDED_CLOSE;VIG_NOT_REMOVED;NO_SHARED_OPEN_PROOF;NOT_A_MARKET_CONTROL_OR_VALUE_CLAIM'),**metrics(selected));results.append(result)
            for rank,r in enumerate(selected,1):members.append(dict(diagnostic_id=rid,rank=rank,record_id=r['record_id'],offer_id=r['offer_id'],player_id=r['player_id'],player_name=r['player_name'],game_id=r['game_id'],week=week,book=book,category=r['category'],role=r['position'],line=r['line'],side=r['selected_side'],p_selected=r['_confidence'],p_under=r['_ps']['under'],p_push=r['_ps']['push'],p_over=r['_ps']['over'],statistical_status=r['status'],actual=r['actual'],source_closing_clocks=r['source_snapshot_clocks'],forecast_cutoff=r['decision_UTC'],source_conditioning=r['conditioning'],tier=result['tier']))
    assert len(results)==810
    lookup={r['diagnostic_id']:r for r in results};byid=defaultdict(list)
    for r in members:byid[r['diagnostic_id']].append(r)
    overlaps=[]
    for book in ['pinnacle','draftkings','fanduel']:
     for week in [2,3]:
      for scope,category in [('GLOBAL','ALL')]+[('WITHIN_CATEGORY',c) for c in ['pass_yd','rush_yd','rec','rec_yd']]:
       for side in ['MIXED','OVER_ONLY','UNDER_ONLY']:
        for K in [6,10,20]:
         for x,y in [('P2_LAW','P3_DIRECT'),('P2_LAW','EARLIER_PREVALENCE_V8'),('P3_DIRECT','EARLIER_PREVALENCE_V8')]:
            ids=[f'TKR9-{book}-W{week}-{m}-{scope}-{category}-{side}-K{K}' for m in [x,y]];aa,bb=[byid[i] for i in ids];aset,bset=[{r['offer_id'] for r in rr} for rr in [aa,bb]];ap,bp=[{(r['game_id'],r['player_id']) for r in rr} for rr in [aa,bb]]
            overlaps.append(dict(book=book,week=week,scope=scope,category=category,side_variant=side,K=K,methods=[x,y],diagnostic_ids=ids,selected=[len(aa),len(bb)],exact_offer_overlap=len(aset&bset),exact_offer_Jaccard=len(aset&bset)/len(aset|bset) if aset|bset else None,player_game_overlap=len(ap&bp),player_game_Jaccard=len(ap&bp)/len(ap|bp) if ap|bp else None,whole_policy_records=[{k:lookup[i][k] for k in ['wins','losses','decided','selected_count','mean_confidence_decided','expected_wins_decided','all_selected_expected_wins','all_selected_mean_confidence']} for i in ids],comparison='Ownselectedsets preserved;not reduced to intersection;overlap is dependence/context only'))
    cumulative=[]
    for book in ['pinnacle','draftkings','fanduel']:
     for method in METHODS:
      for scope,category in [('GLOBAL','ALL')]+[('WITHIN_CATEGORY',c) for c in ['pass_yd','rush_yd','rec','rec_yd']]:
       for side in ['MIXED','OVER_ONLY','UNDER_ONLY']:
        for K in [6,10,20]:
            lists=[r for r in results if (r['book'],r['method'],r['scope'],r['category'],r['side_variant'],r['K'])==(book,method,scope,category,side,K)];ids={r['diagnostic_id'] for r in lists};selected=[classified[r['offer_id']][method] for r in members if r['diagnostic_id'] in ids];known=[r for r in selected if r['status'] in ['WIN','LOSS']]
            cumulative.append(dict(book=book,method=method,scope=scope,category=category,side_variant=side,K=K,weekly_lists=len(lists),selected_count=len(selected),common_eligible=sum(r['common_eligible'] for r in lists),side_eligible=sum(r['side_eligible'] for r in lists),mean_confidence_decided=sum(r['_confidence'] for r in known)/len(known) if known else None,expected_wins_decided=sum(r['_confidence'] for r in known) if known else None,role_composition=dict(Counter(r['position'] for r in selected)),category_composition=dict(Counter(r['category'] for r in selected)),tier='EXPLORATORY_LAST_RECORDED_LINE_RANKING_DIAGNOSTIC',**metrics(selected)))
    OUT.mkdir(parents=True,exist_ok=True);ART.mkdir(parents=True,exist_ok=True)
    write(ART/'COMMON_POOL.json.gz',dict(source_eligible_offers=len(pool)+len(excluded),common_offer_ids=list(pool),excluded=excluded,selection_uses_no_outcomes=True,inputs=receipts));write(ART/'MEMBERSHIP.json.gz',members);write(OUT/'WEEKLY_RESULTS.json.gz',results);write(OUT/'OVERLAPS.json.gz',overlaps);write(OUT/'CUMULATIVE.json.gz',cumulative)
    result=dict(id='C-EXPOSED-TOPK-REFERENCE-AUDIT-v9',completed_UTC=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),protocol_SHA256=a.sha(ROOT/'protocol/TOPK_REFERENCE_AUDIT_V9.json'),code_SHA256=a.sha(Path(__file__)),common_cases=len(pool),excluded_cases=len(excluded),unique_games=len({g[METHODS[0]]['game_id'] for g in pool.values()}),weeks=2,weekly_lists=len(results),cumulative_views=len(cumulative),membership_views=len(members),overlap_views=len(overlaps),new_fits=0,source_calls=0,market_only_reference='NOT_ESTABLISHED;retained source lacks synchronized same-contract OPEN price evidence',main_alternate_classification='UNKNOWN_NOT_INVENTED',CPU_seconds=time.process_time()-cpu,wall_seconds=time.monotonic()-start,peak_RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024)
    assert result['CPU_seconds']<180 and result['wall_seconds']<300 and result['peak_RSS_bytes']<1073741824;write(OUT/'RUN.json',result);signal.setitimer(signal.ITIMER_PROF,0);print(result)

if __name__=='__main__':build()
