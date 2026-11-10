"""Zero-refit matched uncertainty and inherited exploratory Top-K summaries."""
import collections,json,sys,gzip,zipfile,io
import pandas as pd
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'src'))
import receiving_increment_c03 as d
from context_identity_view_c01 import corrected_rows
from topk_reference_v9 import choose
import abc_championship_v2 as common

def ci(rows,delta):
 out={}
 for field in ['game_id','week']:
  groups=collections.defaultdict(lambda:np.zeros(2))
  for r,v in zip(rows,delta):groups[r[field]]+=[v,1]
  if not groups:out[field]={'clusters':0,'interval':None};continue
  a=np.asarray(list(groups.values()));rng=np.random.default_rng(661107);s=a[rng.integers(len(a),size=(2000,len(a)))].sum(axis=1)
  out[field]={'clusters':len(a),'interval':np.quantile(s[:,0]/s[:,1],[.025,.975]).tolist()}
 return out

def main(year=2026):
 rows=d.read(d.ART/f'NUMERICAL_ROWS-{year}.json.xz');pairs=[]
 for scope,roles in [('WR_TE',['WR','TE']),('RB',['RB']),('ALL_SUPPORTED',['RB','WR','TE'])]:
  for cohort in ['ALL','priority','workload_top20']:
   for a,b in [('R1','R0'),('R2','R0'),('R2','R1'),('R3','R2'),('R3','R0')]:
    rr=[r for r in rows if r['position'] in roles and (cohort=='ALL' or r['cohort'].get(cohort,False)) and r.get(a) and r.get(b) and r['actual'] is not None]
    for metric in ['median_absolute_error','mean_absolute_error','mean_squared_error']:
     def error(r,method):
      e=r[method]['median' if metric.startswith('median') else 'mean']-r['actual'];return e*e if metric.endswith('squared_error') else abs(e)
     dif=[error(r,a)-error(r,b) for r in rr]
     pairs.append(dict(season=year,scope=scope,cohort=cohort,candidate=a,control=b,metric=metric,matched_known=len(rr),candidate_score=float(np.mean([error(r,a) for r in rr])) if rr else None,control_score=float(np.mean([error(r,b) for r in rr])) if rr else None,change=float(np.mean(dif)) if dif else None,uncertainty=ci(rr,dif),limits='Exposed current-vintage chronological reconstruction; dependent football opportunities; unadjusted multiple-comparison diagnostics'))
 d.write(d.OUT/f'NUMERICAL_PAIRED_CHANGES-{year}.json.xz',pairs)
 if year!=2026:return
 with zipfile.ZipFile(ROOT/'artifacts/basic-football-facts-v2.1.zip') as archive:sch=pd.read_csv(io.BytesIO(archive.read('schedule.csv')))
 sch['kickoff_UTC']=pd.to_datetime(sch.gameday+' '+sch.gametime).dt.tz_localize('America/New_York').dt.tz_convert('UTC').astype(str);kick=dict(zip(sch.game_id,sch.kickoff_UTC))
 offers=d.read(d.ART/'ACTUAL_OFFER_ROWS.json.xz');old=[r for r in corrected_rows() if r['method'] in ['E0','P2','RETAINED_EARLIER_PREVALENCE_V8','ALWAYS_OVER','ALWAYS_UNDER']]
 # Use cohort bits already frozen on the new rows, never infer eligibility from wins.
 tag={r['offer_id']:r['cohort'] for r in offers}
 rows=offers+[dict(r,cohort=tag[r['offer_id']]) for r in old]
 direct=[]
 for scope,roles in [('WR_TE',['WR','TE']),('RB',['RB']),('ALL_SUPPORTED',['RB','WR','TE'])]:
  for cohort in ['ALL','priority','workload_top20']:
   for product in ['MEAN','MEDIAN','LAW']:
    for a,b in [('R1','R0'),('R2','R0'),('R2','R1'),('R3','R2'),('R3','R0')]:
     aa={r['offer_id']:r for r in rows if r['method']==a+'_'+product and r['position'] in roles and (cohort=='ALL' or r['cohort'].get(cohort,False))};bb={r['offer_id']:r for r in rows if r['method']==b+'_'+product and r['position'] in roles and (cohort=='ALL' or r['cohort'].get(cohort,False))};ids=sorted(aa.keys()&bb.keys());ids=[k for k in ids if aa[k]['status'] in ['WIN','LOSS'] and bb[k]['status'] in ['WIN','LOSS']]
     rr=[aa[k] for k in ids];delta=[int(aa[k]['status']=='WIN')-int(bb[k]['status']=='WIN') for k in ids]
     direct.append(dict(scope=scope,cohort=cohort,product=product,candidate=a,control=b,decided=len(ids),candidate_wins=sum(aa[k]['status']=='WIN' for k in ids),control_wins=sum(bb[k]['status']=='WIN' for k in ids),win_change=sum(delta),change_pp=100*sum(delta)/len(delta) if delta else None,uncertainty=ci(rr,[100*x for x in delta]),candidate_own_sides=common.summary(rr),control_own_sides=common.summary([bb[k] for k in ids]),evidence='TIMING_UNVERIFIED_LAST_RECORDED_ACTUAL_LINE_DIAGNOSTIC'))
 d.write(d.OUT/'PRODUCT_PAIRED_CHANGES.json.xz',direct)
 top=[]
 for scope,roles in [('WR_TE',['WR','TE']),('ALL_SUPPORTED',['RB','WR','TE'])]:
  for wk in [2,3]:
   source=[r for r in rows if r['position'] in roles and r['week']==wk and r['method'] in ['R0_LAW','R1_LAW','R2_LAW','R3_LAW','E0','P2','RETAINED_EARLIER_PREVALENCE_V8']]
   methods=sorted({r['method'] for r in source});available={m:{r['offer_id'] for r in source if r['method']==m and r['selected_side'] in ['OVER','UNDER'] and r.get('probabilities')} for m in methods};core=set.intersection(*(available[m] for m in methods)) if methods else set()
   for mask in ['FULL_SYSTEM','COMMON_AVAILABLE_CORE']:
    for m in methods:
     eligible=[r for r in source if r['method']==m and (mask=='FULL_SYSTEM' or r['offer_id'] in core)]
     ready=[dict(r,_confidence=r['probabilities'][r['selected_side'].lower()],kickoff_UTC=kick[r['game_id']]) for r in eligible if r['selected_side'] in ['OVER','UNDER'] and r.get('probabilities')]
     for side in ['MIXED','OVER_ONLY','UNDER_ONLY']:
      for K in [6,10,20]:
       selected,board=choose(ready,side,K);known=[r for r in selected if r['status'] in ['WIN','LOSS']]
       top.append(dict(scope=scope,week=wk,mask=mask,method=m,side=side,K=K,source_eligible=len(eligible),forecast_available=len(ready),achieved_coverage=len(selected)/len(eligible) if eligible else None,candidate_board=len(board),member_ids=[r['offer_id'] for r in selected],**common.summary(selected),mean_decided_selected_confidence=float(np.mean([r['_confidence'] for r in known])) if known else None,all_selected_expected_wins=sum(r['_confidence'] for r in selected),mean_all_selected_confidence=float(np.mean([r['_confidence'] for r in selected])) if selected else None,evidence='EXPLORATORY_LAST_RECORDED_LINES;NO_AUTHENTIC_SIMULTANEOUS_BOARD_OR_ENTRY',core_opportunities=len(core)))
 d.write(d.OUT/'TOPK_DIAGNOSTICS.json.xz',top)
 print('C03_ZERO_REFIT_SUMMARIES',year,len(pairs),len(direct),len(top))
if __name__=='__main__':main(int(sys.argv[1]) if len(sys.argv)>1 else 2026)
