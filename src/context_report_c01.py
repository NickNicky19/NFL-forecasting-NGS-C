"""Report the same retained actual-line rows with the pinned common scorer."""
import csv,gzip,hashlib,json,math
from collections import Counter,defaultdict
from pathlib import Path
import numpy as np
from scipy.stats import poisson
import abc_championship_v2 as common
from topk_reference_v9 import choose
from context_experiment_c01 import ROOT,read,write,sha,now

OUT=ROOT/'reports/player-context-matchup-01';ART=ROOT/'artifacts/player-context-matchup-01'
ALIASES={'E0':'Retained HGB direct/E0_OP','E1':'HGB + own target depth/down','E2':'E1 + opponent main effects','E3':'E2 + predicted-mix interactions','P1':'Pooled contextual Poisson law','P2':'Partially pooled contextual Poisson law','P3':'Player-only law / pooled fallback'}
def group_score(rows):
 result=common.summary(rows);known=[r for r in rows if r['status'] in ['WIN','LOSS']]
 p=[r for r in known if r.get('probabilities')];result.update(mean_Brier=float(np.mean([r['Brier'] for r in p])) if p else None,mean_log_loss=float(np.mean([r['log_loss'] for r in p])) if p and all(not r.get('infinite_log_loss') for r in p) else None,infinite_log_losses=sum(r.get('infinite_log_loss',False) for r in p),mean_selected_confidence=float(np.mean([r['probabilities'][r['selected_side'].lower()] for r in p])) if p else None,expected_wins=sum(r['probabilities'][r['selected_side'].lower()] for r in p) if p else None,fallback_selected=sum(r.get('fallback',False) and r['selected_side'] in ['OVER','UNDER'] for r in rows),fallback_decided=sum(r.get('fallback',False) for r in known))
 by=defaultdict(list)
 for r in known:by[r['game_id']].append(r['status']=='WIN')
 if by:
  a=np.array([[sum(v),len(v)] for v in by.values()]);rng=np.random.default_rng(661107);s=a[rng.integers(len(a),size=(2000,len(a)))].sum(axis=1);lo,hi=np.quantile(s[:,0]/s[:,1],[.025,.975]);result['game_cluster_sensitivity95']=dict(low=float(lo),high=float(hi),games=len(a),week_count=len({r['week'] for r in known}),note='Only two exposed week clusters;game intervals are descriptive,not independent-season confirmation')
 return result
def build():
 primary=read(ART/'native-query-extension-v1/FULL_OFFER_ROWS.json.gz');original=read(ART/'v1.1/EXACT_OFFER_ROWS.json.gz');cases=read(ROOT/'artifacts/predictive-C01/APPROVED_OFFER_CASES.json.gz')['cases'];bycase={r['offer_id']:r for r in cases}
 import zipfile,io,pandas as pd
 with zipfile.ZipFile(ROOT/'artifacts/basic-football-facts-v2.1.zip') as z:scheduled=pd.read_csv(io.BytesIO(z.read('schedule.csv')))
 scheduled['kickoff_UTC']=pd.to_datetime(scheduled.gameday+' '+scheduled.gametime).dt.tz_localize('America/New_York').dt.tz_convert('UTC').astype(str);kickoffs=dict(zip(scheduled.game_id,scheduled.kickoff_UTC))
 rows=list(primary)
 for r in primary:
  if r['method'] not in ['P1','P2','P3']:continue
  for product in ['mean','median']:
   q=dict(r);point=r.get(product);side=None if point is None else 'OVER' if point>r['line'] else 'UNDER' if point<r['line'] else 'ABSTAIN';q.update(method=r['method']+'_'+product.upper()+'_DIRECTION',procedure=r['procedure']+'::'+product.upper()+'_POINT_DIRECTION',selected_side=side,probabilities=None,point=point,point_type=product,status='UNAVAILABLE_FORECAST' if side is None else 'ABSTAIN' if side=='ABSTAIN' else 'UNKNOWN_PARTICIPATION' if r['appearance']!='PLAYED' else 'MISSING_ACTUAL' if r['actual'] is None else 'PUSH' if r['actual']==r['line'] else 'WIN' if (r['actual']>r['line'])==(side=='OVER') else 'LOSS');rows.append(q)
 for case in cases:
  base=next(r for r in primary if r['offer_id']==case['offer_id'] and r['method']=='E0')
  for method,side in [('ALWAYS_OVER','OVER'),('ALWAYS_UNDER','UNDER')]:
   q=dict(base,method=method,procedure='CONTROL::'+method,selected_side=side,probabilities=None,mean=None,median=None);q['status']='UNKNOWN_PARTICIPATION' if q['appearance']!='PLAYED' else 'PUSH' if q['actual']==q['line'] else 'WIN' if (q['actual']>q['line'])==(side=='OVER') else 'LOSS';rows.append(q)
  for method in ['P1_MEAN','P1_MEDIAN','P2_LAW','EARLIER_PREVALENCE_V8']:
   old=case['retained_methods'].get(method)
   if not old:continue
   q=dict(base,method='RETAINED_'+method,procedure='RETAINED::'+method,selected_side=old['selected_side'],status=old['status'],point=old.get('point'),probabilities=None,mean=None,median=None,fallback=False)
   if old.get('p_over') is not None:
    q['probabilities']=dict(under=old['p_under'],push=old['p_push'],over=old['p_over'])
    if q['actual'] is not None:
     truth=dict(under=int(q['actual']<q['line']),push=int(q['actual']==q['line']),over=int(q['actual']>q['line']));q['Brier']=.5*sum((q['probabilities'][k]-truth[k])**2 for k in truth);v=sum(q['probabilities'][k]*truth[k] for k in truth);q['log_loss']=-math.log(v) if v else None;q['infinite_log_loss']=v==0
   rows.append(q)
 for r in rows:assert common.status(r)==r['status']
 write(ART/'CANONICAL_REPORT_ROWS.json.gz',rows)
 groups=[];methods=sorted({r['method'] for r in rows})
 roles={'ALL_SUPPORTED':['RB','WR','TE'],'WR_TE':['WR','TE'],'RB':['RB'],'WR':['WR'],'TE':['TE']}
 for name,positions in roles.items():
  for week in ['ALL',2,3]:
   for method in methods:
    rr=[r for r in rows if r['position'] in positions and (week=='ALL' or r['week']==week) and r['method']==method]
    groups.append(dict(category='rec',method=method,label=ALIASES.get(method,method),scope=name,actual_weeks=[2,3] if week=='ALL' else [week],week=week,policy='ALL_ELIGIBLE_EXACT_OFFERS',venue='pinnacle',tier='TIMING_UNVERIFIED_LAST_RECORDED_ACTUAL_LINE_DIAGNOSTIC',five_week_actual_line=False,**group_score(rr)))
 write(OUT/'ACTUAL_LINE_SCORES.json.gz',groups)
 pairs=[]
 for scope,positions in roles.items():
  for a,b in [('E1','E0'),('E2','E1'),('E3','E2'),('E3','E0'),('P1','E0'),('P2','E0'),('P3','E0'),('P2','P1'),('P3','P1')]+[(m,c) for m in ['E0','E1','E2','E3','P1','P2','P3'] for c in ['ALWAYS_OVER','ALWAYS_UNDER','RETAINED_EARLIER_PREVALENCE_V8']]:
   aa={r['offer_id']:r for r in rows if r['method']==a and r['position'] in positions};bb={r['offer_id']:r for r in rows if r['method']==b and r['position'] in positions};commonids=sorted(aa.keys()&bb.keys());dec=[i for i in commonids if aa[i]['status'] in ['WIN','LOSS'] and bb[i]['status'] in ['WIN','LOSS']]
   if not dec:continue
   for oid in commonids:assert all(aa[oid][k]==bb[oid][k] for k in ['game_id','player_id','line','venue','actual','appearance'])
   wins_a=sum(aa[i]['status']=='WIN' for i in dec);wins_b=sum(bb[i]['status']=='WIN' for i in dec);by=defaultdict(lambda:np.zeros(2))
   for i in dec:by[aa[i]['game_id']]+=[int(aa[i]['status']=='WIN')-int(bb[i]['status']=='WIN'),1]
   arr=np.asarray(list(by.values()));rng=np.random.default_rng(661107);sample=arr[rng.integers(len(arr),size=(2000,len(arr)))].sum(axis=1);ci=np.quantile(sample[:,0]/sample[:,1],[.025,.975])
   pairs.append(dict(scope=scope,candidate=a,control=b,eligible_common=len(commonids),decided_common=len(dec),candidate_wins=wins_a,control_wins=wins_b,win_difference=wins_a-wins_b,direction_change_pp=100*(wins_a-wins_b)/len(dec),game_cluster_sensitivity_pp=(100*ci).tolist(),Brier_change=float(np.mean([aa[i]['Brier']-bb[i]['Brier'] for i in dec])) if all(aa[i].get('probabilities') and bb[i].get('probabilities') for i in dec) else None))
 write(OUT/'PAIRED_CHANGES.json.gz',pairs)
 supported_ids={r['offer_id'] for r in primary if r['method']=='P3' and not r['fallback']};personal=[]
 for scope,positions in roles.items():
  for method in ['E0','P1','P2','P3']:
   rr=[r for r in primary if r['method']==method and r['position'] in positions and r['offer_id'] in supported_ids]
   personal.append(dict(scope=scope,method=method,mask='COMMON_PLAYER_WITH_AT_LEAST8_EARLIER_KNOWN_APPEARANCES',**group_score(rr)))
 write(OUT/'PERSONALIZATION_COMMON_MASK.json.gz',personal)
 lists=[];members=[]
 for scope,positions in roles.items():
  for week in [2,3]:
   for method in list(ALIASES):
    source=[]
    for r in rows:
     if r['method']==method and r['week']==week and r['position'] in positions and r['probabilities']:
      x=dict(r,_confidence=r['probabilities'][r['selected_side'].lower()] if r['selected_side'] in ['OVER','UNDER'] else None,kickoff_UTC=kickoffs[r['game_id']]);source.append(x)
    for side in ['MIXED','OVER_ONLY','UNDER_ONLY']:
     for K in [6,10,20]:
      selected,board=choose(source,side,K);rid=f'{scope}-W{week}-{method}-{side}-K{K}'
      lists.append(dict(id=rid,scope='WITHIN_REC_'+scope,week=week,method=method,K=K,side=side,candidate_eligible=len(source),side_board=len(board),selected_count=len(selected),fewer_than_K=len(selected)<K,role_composition=dict(Counter(r['position'] for r in selected)),member_ids=[r['offer_id'] for r in selected],tier='EXPLORATORY_LAST_RECORDED_LINE_RANKING_DIAGNOSTIC;NO_SIMULTANEOUS_BOARD_OR_AVAILABLE_TICKET',**group_score(selected)))
      members.extend(dict(list_id=rid,offer_id=r['offer_id'],rank=i+1,side=r['selected_side'],confidence=r['_confidence'],status=r['status'],player_id=r['player_id'],game_id=r['game_id']) for i,r in enumerate(selected))
 write(OUT/'TOPK_RESULTS.json.gz',lists);write(ART/'TOPK_MEMBERSHIP.json.gz',members)
 numerical=read(ART/'v1.1/NUMERICAL_ROWS.json.gz');ngroups=[]
 for scope,positions in roles.items():
  for method in ['P1','P2','P3']:
   for week in ['ALL']+list(range(1,9)):
    rr=[r for r in numerical if r['procedure']==method and r['position'] in positions and (week=='ALL' or r['origin'].endswith(f'W{week:02}'))];known=[r for r in rr if r['actual'] is not None];by=defaultdict(list)
    for r in known:by[r['player_id']].append(abs(r['median']-r['actual']))
    ngroups.append(dict(category='rec',scope=scope,procedure=method,period='2026W1-W8',actual_weeks=list(range(1,9)) if week=='ALL' else [week],rows=len(rr),known=len(known),unknown=len(rr)-len(known),fallback_rows=sum(r['fallback'] for r in rr),scored_distinct_weeks=len({r['origin'] for r in known}),MAE_median=float(np.mean([abs(r['median']-r['actual']) for r in known])) if known else None,MSE_mean=float(np.mean([(r['mean']-r['actual'])**2 for r in known])) if known else None,bias_mean=float(np.mean([r['mean']-r['actual'] for r in known])) if known else None,equal_player_MAE=float(np.mean([np.mean(v) for v in by.values()])) if by else None,players=len(by),five_week_duration=len({r['origin'] for r in known})>=5,admission='DURATION_ONLY_NOT_PRIMARY_QUALIFICATION;context/source/support/proper-score/release review remains'))
 write(OUT/'NUMERICAL_RESULTS.json.gz',ngroups)
 player=[]
 for method in methods:
  for pid in sorted({r['player_id'] for r in rows}):
   rr=[r for r in rows if r['method']==method and r['player_id']==pid]
   if rr:player.append(dict(method=method,player_id=pid,position=rr[0]['position'],**common.summary(rr),interpretation='One/two exposed actual-offer weeks;not a player-specific winner or router'))
 write(OUT/'PLAYER_RESULTS.json.gz',player)
 write(OUT/'RESULT_BINDINGS.json',dict(created_UTC=now(),protocol='PLAYER-CONTEXT-MATCHUP-01-C-v1.1',scorer=dict(path='src/abc_championship_v2.py',SHA256=sha(ROOT/'src/abc_championship_v2.py')),canonical_rows=dict(path=str((ART/'CANONICAL_REPORT_ROWS.json.gz').relative_to(ROOT)),SHA256=sha(ART/'CANONICAL_REPORT_ROWS.json.gz')),rows=len(rows),unique_offers=len({r['offer_id'] for r in primary}),actual_weeks=[2,3],new_independent_games=0,original_mask=dict(available=340,decided=337),expanded_mask=dict(available=362,known=338,unknown=24),original_forecasts_changed=0,entries=0,primary_releases=0))
 with (OUT/'ACTUAL_LINE_HEADLINE.csv').open('w') as f:
  w=csv.writer(f);w.writerow(['category','method','scope','weeks','over_wins','over_losses','over_decided','over_rate','under_wins','under_losses','under_decided','under_rate','combined_wins','combined_losses','combined_decided','combined_rate','eligible','selected','unavailable','games','Brier','evidence'])
  for s in groups:
   if s['week']!='ALL':continue
   w.writerow(['rec',s['method'],s['scope'],'2,3',*[s[k][v] for k in ['OVER','UNDER','COMBINED'] for v in ['wins','losses','decided','rate']],s['eligible'],s['COMBINED']['selected'],s['unavailable'],s['games'],s['mean_Brier'],s['tier']])
 print(json.dumps([dict(method=s['method'],over=s['OVER'],under=s['UNDER'],combined=s['COMBINED'],eligible=s['eligible'],Brier=s['mean_Brier']) for s in groups if s['scope']=='WR_TE' and s['week']=='ALL' and s['method'] in ALIASES],indent=2))
if __name__=='__main__':build()
