"""Separate arithmetic/grade path for permitted C04 saved rows; no owner scorer."""
from __future__ import annotations
import collections,datetime,gzip,hashlib,json,lzma,math,resource,time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).parent
CPU=time.process_time()
def read(p):
 p=ROOT/p if not Path(p).is_absolute() else Path(p);b=p.read_bytes()
 return json.loads(lzma.decompress(b) if p.suffix=='.xz' else gzip.decompress(b) if p.suffix=='.gz' else b)
def sha(p):return hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
def eq(a,b,tol=1e-11):
 if a is None or b is None:assert a is b,(a,b)
 elif isinstance(a,float) or isinstance(b,float):assert math.isclose(a,b,abs_tol=tol,rel_tol=tol),(a,b)
 else:assert a==b,(a,b)
def average(v):return math.fsum(v)/len(v) if v else None
def grade(r):
 side=r['selected_side']
 if side is None:return 'UNAVAILABLE_FORECAST'
 if side=='ABSTAIN':return 'ABSTAIN'
 if r['appearance']!='PLAYED':return 'UNKNOWN_PARTICIPATION'
 if r['actual'] is None:return 'MISSING_ACTUAL'
 if r['actual']==r['line']:return 'PUSH'
 return 'WIN' if (r['actual']>r['line'])==(side=='OVER') else 'LOSS'
def expected_side(r):
 if r['method']=='ALWAYS_OVER':return 'OVER'
 if r['method']=='ALWAYS_UNDER':return 'UNDER'
 if r.get('point') is not None:return 'OVER' if r['point']>r['line'] else 'UNDER' if r['point']<r['line'] else 'ABSTAIN'
 p=r.get('probabilities')
 if p:return 'OVER' if p['over']>p['under'] else 'UNDER' if p['under']>p['over'] else 'ABSTAIN'
 return r['selected_side']
def prob_score(r):
 p=r.get('probabilities')
 if not p or grade(r) not in ['WIN','LOSS','PUSH']:return None,None
 y,l=r['actual'],r['line'];truth={'over':int(y>l),'under':int(y<l),'push':int(y==l)}
 brier=math.fsum((p[k]-truth[k])**2 for k in truth)/2
 likelihood=math.fsum(p[k]*truth[k] for k in truth)
 return brier,-math.log(likelihood) if likelihood>0 else None

def main():
 paths=['artifacts/receiving-timing-c04/ACTUAL_OFFER_ROWS.json.xz','artifacts/profile-increment-v2/ACTUAL_OFFER_ROWS.json.xz','artifacts/player-context-matchup-01/CANONICAL_REPORT_ROWS.json.gz','artifacts/player-context-matchup-01/ROW_IDENTITY_CORRECTION-v1.json.gz','reports/profile-closure-next-02/timing/ACTUAL_LINE_SCORES.json.xz','reports/profile-closure-next-02/timing/PAIRED_CHANGES.json.xz']
 actual=read(paths[0]);assert len(actual)==4344
 old=read(paths[1]);source=read(paths[2]);patch=read(paths[3]);assert patch['base_CANONICAL_SHA256']==sha(paths[2])
 identity={r['offer_id']:r for r in patch['corrections']};cohorts={r['offer_id']:r['cohort'] for r in actual if r['method']=='F0_LAW'}
 controls=[]
 for r in source:
  if r['method'] not in ['E0','P1','P2','RETAINED_EARLIER_PREVALENCE_V8','ALWAYS_OVER','ALWAYS_UNDER']:continue
  c=identity[r['offer_id']];assert all(r[k]==c[k] for k in ['game_id','player_id','position'])
  controls.append(dict(r,team=c['team'],opponent_team=c['opponent_team'],cohort=cohorts[r['offer_id']]))
 controls.extend(dict(r,method='CONTROL_LEAF_'+r['method'].split('_')[-1]) for r in old if r['method'].startswith('R0_'))
 rows=actual+controls;keys=[(r['method'],r['offer_id']) for r in rows];assert len(keys)==len(set(keys))
 same={};checks=collections.Counter();observed_records=[]
 for r in rows:
  k=r['offer_id'];contract=tuple(r.get(x) for x in ['game_id','player_id','position','team','line','week','season','actual','appearance','scoring_contract_id','venue','product','line_tier'])
  if k in same:assert same[k]==contract,(k,same[k],contract)
  else:same[k]=contract
  eq(grade(r),r['status']);eq(expected_side(r),r['selected_side']);checks['exact_row_regrades']+=1
  p=r.get('probabilities')
  if p:
   assert all(math.isfinite(v) and 0<=v<=1 for v in p.values());eq(math.fsum(p.values()),1.,1e-12)
   if float(r['line']).is_integer() is False:eq(p['push'],0.)
   a,b=prob_score(r)
   if a is not None:eq(a,r.get('Brier'));eq(b,r.get('log_loss'));checks['probability_score_rows']+=1
  if r['method'].endswith('_LAW') and r.get('median') is not None and not float(r['line']).is_integer():
   # Lower median and this same law agree unless the law is exactly a50/50tie.
   if p and p['under']!=p['over']:
    eq('OVER' if r['median']>r['line'] else 'UNDER' if r['median']<r['line'] else 'ABSTAIN',r['selected_side'])
   checks['same_law_median_direction_checks']+=1
 scopes={'WR_TE':{'WR','TE'},'RB':{'RB'},'ALL_SUPPORTED':{'RB','WR','TE'}}
 score_cells=read(paths[4]);independent_scores=[]
 for saved in score_cells:
  rr=[r for r in rows if r['method']==saved['method'] and r['position'] in scopes[saved['scope']] and (saved['cohort']=='ALL' or r['cohort'].get(saved['cohort'],False)) and (saved['week']=='ALL' or r['week']==saved['week'])]
  states=dict(collections.Counter(grade(r) for r in rr));ind=dict(scope=saved['scope'],cohort=saved['cohort'],week=saved['week'],method=saved['method'],eligible=len(rr),games=len({r['game_id'] for r in rr}),player_games=len({(r['game_id'],r['player_id'])for r in rr}),states=states)
  eq(ind['eligible'],saved['eligible']);eq(ind['games'],saved['games']);eq(ind['player_games'],saved['player_games']);eq(states,saved['states'])
  for side in ['OVER','UNDER','COMBINED']:
   subset=[r for r in rr if r['selected_side']==side] if side!='COMBINED' else [r for r in rr if r['selected_side'] in ['OVER','UNDER']]
   wins=sum(grade(r)=='WIN' for r in subset);loss=sum(grade(r)=='LOSS' for r in subset);n=wins+loss
   val=dict(selected=len(subset),wins=wins if n else None,losses=loss if n else None,decided=n,rate=wins/n if n else None)
   for k,v in val.items():eq(v,saved[side][k])
   ind[side]=val
  probs=[prob_score(r)for r in rr if r.get('probabilities') and grade(r) in ['WIN','LOSS','PUSH']]
  bs=average([x[0]for x in probs]);ls=average([x[1]for x in probs])if probs and all(x[1]is not None for x in probs)else None
  eq(bs,saved.get('Brier'));eq(ls,saved.get('log_loss'));ind.update(Brier=bs,log_loss=ls)
  independent_scores.append(ind)
 checks['score_cells']=len(score_cells)
 pairs=read(paths[5]);pair_checks=[]
 for saved in pairs:
  def view(method):return {r['offer_id']:r for r in rows if r['method']==method and r['position']in scopes[saved['scope']]and(saved['cohort']=='ALL'or r['cohort'].get(saved['cohort'],False))}
  a,b=view(saved['candidate']),view(saved['control']);ids=sorted(i for i in a.keys()&b.keys()if grade(a[i])in['WIN','LOSS']and grade(b[i])in['WIN','LOSS'])
  cw=sum(grade(a[i])=='WIN'for i in ids);bw=sum(grade(b[i])=='WIN'for i in ids);dis=sum(a[i]['selected_side']!=b[i]['selected_side']for i in ids)
  for k,v in dict(decided=len(ids),candidate_wins=cw,control_wins=bw,disagreements=dis,win_change=cw-bw,change_pp=100*(cw-bw)/len(ids)).items():eq(v,saved[k])
  assert len({a[i]['game_id']for i in ids})==saved['game_id_clusters'];assert len({a[i]['week']for i in ids})==saved['week_clusters']
  week_groups=collections.defaultdict(list)
  for i in ids:week_groups[a[i]['week']].append(int(grade(a[i])=='WIN')-int(grade(b[i])=='WIN'))
  if len(week_groups)==2:
   rates=[100*average(v)for v in week_groups.values()];eq(min(rates),saved['week_sensitivity95_pp'][0]);eq(max(rates),saved['week_sensitivity95_pp'][1]);checks['exact_two_week_interval_bounds']+=1
  if saved['scope']=='WR_TE'and saved['cohort']=='ALL':pair_checks.append({k:saved[k]for k in ['candidate','control','product','decided','candidate_wins','control_wins','win_change','change_pp','game_id_sensitivity95_pp','week_sensitivity95_pp']})
 checks['paired_cells']=len(pairs)
 # Reliability checked through independent rank-sum AUC and finite-bin arithmetic.
 def auc(truth,probability):
  n1=sum(truth);n0=len(truth)-n1
  if not n1 or not n0:return None
  ordered=sorted(zip(probability,truth));i=0;positive_rank=0.
  while i<len(ordered):
   j=i+1
   while j<len(ordered)and ordered[j][0]==ordered[i][0]:j+=1
   positive_rank+=sum(t for _,t in ordered[i:j])*(i+1+j)/2;i=j
  return(positive_rank-n1*(n1+1)/2)/(n1*n0)
 for saved in read('reports/profile-closure-next-02/timing/RELIABILITY.json.xz'):
  rr=[r for r in rows if r['method']==saved['method']and r['position']in scopes[saved['scope']]and(saved['week']=='ALL'or r['week']==saved['week'])and grade(r)in['WIN','LOSS']]
  truth=[int(r['actual']>r['line'])for r in rr];prob=[r['probabilities']['over']for r in rr];confidence=[r['probabilities'][r['selected_side'].lower()]for r in rr];wins=[int(grade(r)=='WIN')for r in rr]
  values=dict(decided=len(rr),mean_predicted_over=average(prob),actual_over_frequency=average(truth),mean_selected_confidence=average(confidence),selected_accuracy=average(wins),expected_wins=math.fsum(confidence),actual_wins=sum(wins),Brier=average([prob_score(r)[0]for r in rr]),log_loss=average([prob_score(r)[1]for r in rr])if all(prob_score(r)[1]is not None for r in rr)else None,Over_AUC=auc(truth,prob),confidence_correctness_AUC=auc(wins,confidence))
  for k,v in values.items():eq(v,saved[k])
  for b in saved['fixed_selected_confidence_bins']:
   ix=[i for i,c in enumerate(confidence)if b['low']<=c<(b['high']if b['high']<1 else 1.0000000001)]
   eq(len(ix),b['n']);eq(sum(wins[i]for i in ix),b['wins']);eq(average([confidence[i]for i in ix]),b['predicted']);eq(average([wins[i]for i in ix]),b['accuracy']);eq(average([confidence[i]-wins[i]for i in ix]),b['gap'])
  checks['reliability_and_rank_cells']+=1

 # F0/F1 are exact rename-only retained R1/R2 rows, not refits/newobservations.
 lookup={(r['method'],r['offer_id']):r for r in old}
 for r in actual:
  arm=r['method'].split('_')[0]
  if arm not in ['F0','F1']:continue
  sourcekey=('R1'if arm=='F0'else'R2')+'_'+r['method'].split('_')[-1];prior=lookup[sourcekey,r['offer_id']]
  for k in ['game_id','player_id','line','actual','appearance','mean','median','point','selected_side','status','probabilities','cohort','any_imputed','profile_covered']:eq(r.get(k),prior.get(k))
  checks['old_rename_rows_exact']+=1
 numeric_reports=[]
 for year in [2026,2025]:
  sourcepath=f'artifacts/receiving-timing-c04/NUMERICAL_ROWS-{year}.json.xz';metricpath=f'reports/profile-closure-next-02/timing/NUMERICAL_SCORES-{year}.json.xz'
  if not(ROOT/sourcepath).exists()or not(ROOT/metricpath).exists():continue
  paths.extend([sourcepath,metricpath]);nr=read(sourcepath);metrics=read(metricpath)
  assert len({(r['game_id'],r['player_id'])for r in nr})==len(nr)
  for saved in metrics:
   rr=[r for r in nr if r['position']in scopes[saved['scope']]and(saved['cohort']=='ALL'or r['cohort'].get(saved['cohort'],False))and(saved['week']=='ALL'or r['week']==saved['week'])]
   method=saved['method'];aa=[r for r in rr if r.get(method)is not None];kk=[r for r in aa if r['actual']is not None]
   for k,v in dict(eligible=len(rr),available=len(aa),known=len(kk),unknown=len(aa)-len(kk),unavailable=len(rr)-len(aa),games=len({r['game_id']for r in kk}),player_games=len({(r['game_id'],r['player_id'])for r in kk}),actual_weeks=sorted({r['week']for r in kk})).items():eq(v,saved[k])
   if kk:
    e=[r[method]['mean']-r['actual']for r in kk];m=[r[method]['median']-r['actual']for r in kk];byplayer=collections.defaultdict(list)
    for r in kk:byplayer[r['player_id']].append(abs(r[method]['median']-r['actual']))
    vals=dict(mean_MAE=average([abs(x)for x in e]),median_MAE=average([abs(x)for x in m]),mean_MSE=average([x*x for x in e]),mean_RMSE=math.sqrt(average([x*x for x in e])),mean_bias=average(e),median_bias=average(m),absolute_error_p90=float(np.quantile([abs(x)for x in e],.9)),equal_player_median_MAE=average([average(v)for v in byplayer.values()]),hard_fallback=sum(bool(r[method].get('hard_fallback'))for r in kk),profile_covered_known=sum(bool(r[method].get('profile_covered'))for r in kk),any_imputed_known=sum(bool(r[method].get('any_imputed'))for r in kk))
    for k,v in vals.items():eq(v,saved[k])
   checks['numerical_score_cells']+=1
  for scope in scopes:
   numeric_reports.append({'season':year,'scope':scope,'rows':len([r for r in nr if r['position']in scopes[scope]]),'methods':[s for s in metrics if s['scope']==scope and s['cohort']=='ALL'and s['week']=='ALL']})
 # Reconcile original numerical board to source-fixed offer mask separately.
 offered=[];by={}
 context_points={(r['method'],r['offer_id']):r for r in source if r['method']in['P1','P2']}
 retained_points={(r['game_id'],r['player_id']):r for r in read('reports/player-context-matchup-01/completion-decision-v1/intake/C_RETAINED_LEAF_POINTS_W1_W7.json.gz')['rows']}
 r0_laws={r['offer_id']:r for r in old if r['method']=='R0_LAW'}
 for r in actual:
  if not r['method'].endswith('_LAW'):continue
  if r['offer_id']not in by:by[r['offer_id']]={k:r[k]for k in ['game_id','player_id','position','week','actual','cohort']}
  by[r['offer_id']][r['method'].split('_')[0]]={k:r[k]for k in ['mean','median']}
 numeric2026={(r['game_id'],r['player_id']):r for r in read('artifacts/receiving-timing-c04/NUMERICAL_ROWS-2026.json.xz')}
 for offer_id,r in by.items():
  for method in ['P1','P2']:
   q=context_points[method,offer_id];r['CONTROL_CONTEXT_'+method]={'mean':q['mean'],'median':q['median']} if q['mean']is not None else None
  old_r0=r0_laws[offer_id];point=retained_points.get((r['game_id'],r['player_id']))
  r['CONTROL_LEAF']={'mean':point['mean'],'median':point['median']}if old_r0['selected_side']is not None and point else None
  # E0 offer candidates are preserved even when no stat-row actual exists.
  n=numeric2026.get((r['game_id'],r['player_id']))
  if n:
   assert r['actual']==n['actual']
   for arm in ['F0','F1','F2','F3']:
    # Native offer origin is each game's own horizon, while broadnumeric origin is firstweekly game.
    # Do not assume the predictions themselves are equal across different horizons.
    assert r[arm]['mean'] is not None and r[arm]['median']is not None
  offered.append(r)
 offered_checks=[]
 for saved in read('reports/profile-closure-next-02/timing/OFFERED_NUMERICAL_SCORES.json.xz')+read('reports/profile-closure-next-02/timing/QUALIFIED_OFFERED_NUMERICAL_SCORES.json.xz'):
  rr=[r for r in offered if r['position']in scopes[saved['scope']]and(saved['cohort']=='ALL'or r['cohort'].get(saved['cohort'],False))and(saved['week']=='ALL'or r['week']==saved['week'])]
  aa=[r for r in rr if r.get(saved['method'])is not None];kk=[r for r in aa if r['actual']is not None]
  for k,v in dict(eligible=len(rr),available=len(aa),known=len(kk),unknown=len(aa)-len(kk),unavailable=len(rr)-len(aa)).items():eq(v,saved[k])
  if kk:
   method=saved['method'];vals={'mean_MAE':average([abs(r[method]['mean']-r['actual'])for r in kk]),'median_MAE':average([abs(r[method]['median']-r['actual'])for r in kk]),'mean_MSE':average([(r[method]['mean']-r['actual'])**2 for r in kk])}
   for k,v in vals.items():eq(v,saved[k])
  checks['offered_numeric_score_cells']+=1
 # Exact unchanged Leaf numerical control on the same broad declared masks.
 for year in [2025,2026]:
  qualified_path=f'reports/profile-closure-next-02/timing/QUALIFIED_NUMERICAL_SCORES-{year}.json.xz'
  if not (ROOT/qualified_path).exists():continue
  nr=read(f'artifacts/receiving-timing-c04/NUMERICAL_ROWS-{year}.json.xz');prior={(r['game_id'],r['player_id']):r for r in read(f'artifacts/profile-increment-v2/NUMERICAL_ROWS-{year}.json.xz')}
  for row in nr:row['CONTROL_LEAF']=prior[row['game_id'],row['player_id']].get('R0')
  for saved in read(qualified_path):
   rr=[r for r in nr if r['position']in scopes[saved['scope']]and(saved['cohort']=='ALL'or r['cohort'].get(saved['cohort'],False))and(saved['week']=='ALL'or r['week']==saved['week'])];method=saved['method'];aa=[r for r in rr if r.get(method)is not None];kk=[r for r in aa if r['actual']is not None]
   for k,v in dict(eligible=len(rr),available=len(aa),known=len(kk),unknown=len(aa)-len(kk),unavailable=len(rr)-len(aa)).items():eq(v,saved[k])
   if kk:
    vals={'mean_MAE':average([abs(r[method]['mean']-r['actual'])for r in kk]),'median_MAE':average([abs(r[method]['median']-r['actual'])for r in kk]),'mean_MSE':average([(r[method]['mean']-r['actual'])**2 for r in kk])}
    for k,v in vals.items():eq(v,saved[k])
   checks['qualified_numeric_strong_control_cells']+=1
 report={'id':'C04-INDEPENDENT-HISTORICAL-ARITHMETIC-v1','checked_UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'PASS','method':'Independent Python comparison/Counter/math.fsum grade and aggregation,not author scorer/summary call','source_bindings':[{'path':p,'SHA256':sha(p)}for p in paths],'checks':dict(checks),'native_offers':len(same),'native_WR_TE_offers':len([r for r in same.values()if r[2]in ['WR','TE']]),'periods':[2,3],'scores_headline':[s for s in independent_scores if s['scope']=='WR_TE'and s['cohort']=='ALL'and s['week']=='ALL'],'paired_headline':pair_checks,'numerical':numeric_reports,'checker_code_SHA256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'CPU_seconds':time.process_time()-CPU,'peak_RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,'new_fits':0,'new_GETs':0,'source_tier':'Timing-unverifiedactual-line/currentrevisedfootballreconstruction;one-daynotauthenticatedavailability','limits':'Arithmetic/identity/mask/probability checks; rawcontextmeaning/chronologyreusepriorboundedreview,notnewrawrebuild. Twoactualweeks/32gameclusters; broadnumericconditionalstatrowsnotpregameroster; no90%orprofitabilityclaim.'}
 (OUT/'HISTORICAL_ARITHMETIC.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
 print(json.dumps({'status':report['status'],'checks':report['checks'],'CPU_seconds':report['CPU_seconds']}))
if __name__=='__main__':main()
