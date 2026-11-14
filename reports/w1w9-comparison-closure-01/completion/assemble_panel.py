"""Assemble admitted, pregraded public counts under the fixed common panel.

No outcome is reclassified, model fitted, selector run, or quote acquired.
The retained common evaluator remains src/abc_championship_v2.py. This is
source-qualified reporting from its owner-local count contracts, not a grader.
"""
import csv,gzip,hashlib,io,json,math,time
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent;BASE=HERE.parent
def load(p):
 b=Path(p).read_bytes();return json.loads(gzip.decompress(b) if str(p).endswith('.gz') else b)
def bind(p):p=Path(p);return dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,SHA256=hashlib.sha256(p.read_bytes()).hexdigest())
def dump(p,d):
 assert not p.exists(),'VERSION_ALREADY_EXISTS'
 p.write_text(json.dumps(d,indent=2,allow_nan=False)+'\n')
def main():
 cpu=time.process_time();frozen=load(BASE/'roster/FROZEN_ROSTER_V1_1.json');assert frozen['effective_candidate_count']==143
 decision=load(BASE/'source-contract/COMPATIBILITY_DECISION.json');assert 'ALLOW' in json.dumps(decision)
 a_path=BASE/'A-intake/NORMALIZED_COMPLETION_ROWS.json.gz';b_path=BASE/'controls/B_NATIVE_W5_W9_STRONG_CONTROLS_AND_RETAINED_PRODUCTS.json'
 aa=[x for x in load(a_path) if x['comparison_mask']=='FULL_A_EARLY_BOARD'];bb=load(b_path)['rows']
 def early(pid,week):
  r=[x for x in aa if x['procedure_id']==pid and x['week_view']==week];assert len(r)==1,(pid,week);r=r[0]
  return dict(week=week,eligible=r['eligible'],available=r['available'],selected=r['selected'],decided=r['COMBINED']['decided'],unknown=r['unknown'],unavailable=r['unavailable'],abstained=r['abstentions'],fallback=r['fallback'] if pid.startswith('B-FTN') else None,games=r['games'],own_sides={k.lower():r[k] for k in ['OVER','UNDER','COMBINED']},source='A_ANNUAL_NAMED_W1_W4',source_procedure_id=pid,source_record=r)
 def late(pid,product,week):
  r=[x for x in bb if x['procedure_id']==pid and x['product']==product and x['week']==week];assert len(r)==1,(pid,product,week);r=r[0]
  # Every complete-board selected crossing requires an available forecast;
  # both selected==eligible and technical_unavailable==0 are explicit.
  assert r['selected']==r['eligible'] and r['technical_unavailable']==0
  return dict(week=week,eligible=r['eligible'],available=r['selected'],selected=r['selected'],decided=r['combined_decided'],unknown=r['unknown'],unavailable=r['technical_unavailable'],abstained=r['abstained'],fallback=r['fallback'] if pid.startswith('B-FTN') else None,games=r['games'],own_sides=r['own_sides'],source='B_NATIVE_W5_W9',source_procedure_id=pid,source_record=r)
 rows=[];mapping=[]
 for arm in ['B0','B2']:
  for product,suffix in [('P1_MEAN','mean'),('P1_LOWER_MEDIAN','lower_median'),('P2_STATISTICAL_LAW','P2')]:
   pid='B-FTN-BALL-QUALITY-COMPLETION-v1:'+arm
   mapping.append((pid,product,pid+'::'+suffix,pid,product))
 for side in ['OVER','UNDER']:mapping.append(('COMMON::ALWAYS_'+side,'CONSTANT_SIDE','ALWAYS_'+side,'ALWAYS_'+side,'REGISTERED_DIRECTION'))
 for pid,product,aid,bid,bproduct in mapping:
  weekly=[early(aid,w) for w in range(1,5)]+[late(bid,bproduct,w) for w in range(5,10)]
  assert [w['week'] for w in weekly]==list(range(1,10))
  for w in weekly:
   ss=w['own_sides'];assert ss['over']['decided']+ss['under']['decided']==ss['combined']['decided']
   assert w['selected']==w['eligible']==w['decided'];assert w['unknown']==w['unavailable']==w['abstained']==0
  own={}
  for side in ['over','under','combined']:
   values=[w['own_sides'][side] for w in weekly]
   s={k:sum((v.get(k) or 0) for v in values) for k in ['wins','losses','decided','selected']}
   assert s['wins']+s['losses']==s['decided'];s['rate']=s['wins']/s['decided'] if s['decided'] else None;own[side]=s
  cov={k:sum(w[k] for w in weekly) for k in ['eligible','available','selected','decided','unknown','unavailable','abstained','games']};assert cov['eligible']==226 and cov['games']==119
  cov['fallback']=0 if pid.startswith('B-FTN') else None;cov['learned']=226 if pid.startswith('B-FTN') else None
  rows.append(dict(procedure_id=pid,product=product,origin_session='B' if pid.startswith('B-FTN') else 'CONTROL',actual_weeks=list(range(1,10)),own_sides=own,coverage=cov,weekly=weekly,source_tier='CONDITIONAL_RETAINED_REAL_LINES_CURRENT_VINTAGE_CHRONOLOGICAL_DIAGNOSTIC;UNKNOWN_QUOTE_CLOCK_MAIN_ALT_VENUE;NO_ORIGINAL_ISSUANCE',full_cross_session_champion=False,current_operational_readiness='SHADOW_ONLY;NO_CURRENT_NATIVE_ADMISSION',probability_scores='Source-stratified only; binary vs halfmulticlass Brier not pooled',numerical_scores='Source-stratified original typed outputs; no new mean/median mixing'))
 # Reuse the existing descriptive whole-week resampling policy, generalized
 # from seven to nine registered blocks. Integer counts are sufficient here;
 # individual paired-game membership/disagreement is not reconstructed.
 weights=np.random.default_rng(1703).multinomial(9,[1/9]*9,size=500)
 pairs=[]
 for left in rows:
  for right in rows:
   if left is right:continue
   ln=np.array([w['decided'] for w in left['weekly']]);rn=np.array([w['decided'] for w in right['weekly']]);assert np.array_equal(ln,rn)
   lw=np.array([w['own_sides']['combined']['wins'] for w in left['weekly']]);rw=np.array([w['own_sides']['combined']['wins'] for w in right['weekly']]);samples=(weights@(lw-rw))/(weights@ln)
   disagreements=None;candidate_only=None;control_only=None
   if right['procedure_id'] in ['COMMON::ALWAYS_OVER','COMMON::ALWAYS_UNDER']:
    opposite='under' if right['procedure_id'].endswith('OVER') else 'over';s=left['own_sides'][opposite];disagreements=s['decided'];candidate_only=s['wins'];control_only=s['losses']
   pairs.append(dict(left=left['procedure_id']+'::'+left['product'],right=right['procedure_id']+'::'+right['product'],common_decided=226,win_difference=int(sum(lw-rw)),accuracy_difference=float(sum(lw-rw)/226),week_interval95=np.quantile(samples,[.025,.975]).tolist(),weeks=9,resamples=500,seed=1703,side_disagreements=disagreements,candidate_only_wins=candidate_only,control_only_wins=control_only,individual_pair_scope='Constant-side disagreement derivable from own opposite-side counts only; other raw paired disagreements unavailable in C',interval_scope='Paired WHOLE_WEEK sufficient-count diagnostic; same-mask commitments conditional; no pooled game bootstrap, multiplicity adjustment or future guarantee'))
 modeled=[r for r in rows if r['origin_session']=='B'];leaders={}
 for side in ['over','under','combined']:
  valid=[r for r in modeled if r['own_sides'][side]['decided']];best=max(r['own_sides'][side]['rate'] for r in valid)
  leaders[side]=[dict(procedure_id=r['procedure_id'],product=r['product'],**r['own_sides'][side]) for r in valid if r['own_sides'][side]['rate']==best]
 scheduled={w:0 for w in range(1,10)}
 sp=ROOT/'sources/category-decision-release-01/schedule.csv'
 for r in csv.DictReader(sp.open()):
  if r['season']=='2026' and r['game_type']=='REG' and int(r['week']) in scheduled:scheduled[int(r['week'])]+=1
 sourceweeks=[dict(week=w['week'],source=w['source'],eligible_offers=w['eligible'],covered_games=w['games'],scheduled_games=scheduled[w['week']],within_week_status='PARTIAL_RETAINED_OFFER_BOARD_NOT_LEAGUE_WIDE',quote_clock='UNKNOWN',main_alternate_status='UNKNOWN_NOT_ORDINARY_MAINLINE_QUALIFIED') for w in rows[0]['weekly']]
 out=dict(id='C_AB_COMPLETIONS_A84_W1W4_B142_W5W9_DIAGNOSTIC_V1',assembled_UTC=datetime.now(timezone.utc).isoformat(),roster=bind(BASE/'roster/FROZEN_ROSTER_V1_1.json'),source_decision=bind(BASE/'source-contract/COMPATIBILITY_DECISION.json'),sources=[bind(a_path),bind(b_path)],same_panel_rows=226,unique_games_owner_reported=119,scheduled_games_current_retained_snapshot=sum(scheduled.values()),schedule=bind(sp),all_nine_weeks_represented=True,within_week_league_offer_completeness=False,duplicate_policy='Aearly1–4+Bnative5–9 disjointofficialweeks; AannualW5excluded, notsilentlydeduplicated',rows=rows,modeled_descriptive_leaders=leaders,selection='No nine-week registered TopK record completed; later5week policies retained separately; no new router',recommendation='SCOPED_SHADOW_LEADERS_ONLY;CROSS_SESSION_COMPARISON_PARTIAL_UNTIL_A_C_ON_SAME_LATE142',new_fits=0,new_outcome_grades=0,new_NFL_games=0,new_original_selected_sides=0,CPU_seconds=time.process_time()-cpu)
 dump(HERE/'NINE_WEEK_COMPLETION.json',out);dump(HERE/'PAIRED_WEEK_DIAGNOSTICS.json',dict(pairs=pairs,policy=load(HERE/'REGISTRATION.json')['uncertainty']))
 with (HERE/'WEEKLY_DIRECTION.csv').open('x',newline='') as f:
  fields=['procedure_id','product','week','source','eligible','selected','decided','unknown','unavailable','games','over_wins','over_losses','over_decided','under_wins','under_losses','under_decided','combined_wins','combined_losses','combined_decided'];wr=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');wr.writeheader()
  for r in rows:
   for w in r['weekly']:
    z={k:w[k] for k in ['week','source','eligible','selected','decided','unknown','unavailable','games']};z.update(procedure_id=r['procedure_id'],product=r['product'])
    for side in ['over','under','combined']:
     for k in ['wins','losses','decided']:z[side+'_'+k]=w['own_sides'][side][k]
    wr.writerow(z)
 dump(HERE/'WEEK_COVERAGE.json',dict(weeks=sourceweeks,all_weeks=9,covered_games=119,scheduled_games=sum(scheduled.values()),source_week_counts='FourAearly andfiveBnative; notninefullycoveredleagueboards',original_issued_record=False))
 print(json.dumps(dict(rows=len(rows),leaders=leaders,eligible=226,games=119,scheduled=sum(scheduled.values()),fits=0)))
if __name__=='__main__':main()
