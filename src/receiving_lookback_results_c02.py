"""Qualified metric view and zero-refit strong-control closure for C02.

The immutable original prediction rows copied ancillary E0 metric fields. This
view removes those fields, recomputes law metrics, and leaves all scientific
predictions, identities, side selections and statistical grades unchanged.
"""
from pathlib import Path
import json,gzip,hashlib,math,collections,datetime,zipfile,io
import numpy as np
import pandas as pd
import abc_championship_v2 as common
from context_identity_view_c01 import corrected_rows
from topk_reference_v9 import choose
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/player-context-matchup-01/completion-decision-v1/lookback'
ART=ROOT/'artifacts/player-context-matchup-01/completion-decision-v1/lookback'
def read(p):return json.loads(gzip.decompress(Path(p).read_bytes()) if str(p).endswith('.gz') else Path(p).read_bytes())
def write(p,x):
 b=(json.dumps(x,separators=(',',':'),allow_nan=False)+'\n').encode();p.write_bytes(gzip.compress(b,mtime=0) if p.suffix=='.gz' else b)
def metric_rows():
 rows=read(ART/'ACTUAL_OFFER_ROWS.json.gz');out=[];chosen=read(OUT/'SELECTION.json')['selected_own_appearances'];modelcache={}
 for r in rows:
  q=dict(r)
  for k in ['Brier','log_loss','infinite_log_loss']:q.pop(k,None)
  arm='ordinary' if q['method'].startswith('ORDINARY_') else '8' if q['method'].startswith('CONTEXT8_') else str(chosen)
  key=(q['week'],arm)
  if key not in modelcache:
   path=ART/f'2026-W{q["week"]:02}-{arm}.json.gz';m=read(path);modelcache[key]=dict(path=str(path.relative_to(ROOT)),SHA256=hashlib.sha256(path.read_bytes()).hexdigest(),training_fingerprint=m['fingerprint'],source24_SHA256=read(OUT/'INPUT_BINDINGS.json')['source24_sha'])
  q['model_binding']=modelcache[key];q['fit_origin']=f'2026-W{q["week"]:02}';q['information_policy']='CURRENT_REVISED_STRICT_KICKOFF_PLUS7D_RECONSTRUCTION';q['source_model_version']='C-RECEIVING-LOOKBACK-C02';q['appearance_conditioning']='CONDITIONAL_ON_APPEARANCE;SOURCE_ROW_HISTORICAL_RECONSTRUCTION'
  p=q.get('probabilities')
  if p and q['appearance']=='PLAYED' and q['actual'] is not None:
   y,l=q['actual'],q['line'];truth=dict(under=int(y<l),push=int(y==l),over=int(y>l));q['Brier']=.5*sum((p[k]-truth[k])**2 for k in p);v=sum(p[k]*truth[k] for k in p);q['log_loss']=-math.log(v) if v else None;q['infinite_log_loss']=v==0
  out.append(q)
 return out

def main():
 new=metric_rows();base=read(ART/'ACTUAL_OFFER_ROWS.json.gz')
 keys=['offer_id','game_id','player_id','position','week','actual','appearance','mean','median','point','point_type','selected_side','probabilities','status']
 assert all(all(a.get(k)==b.get(k) for k in keys) for a,b in zip(new,base))
 correction=dict(id='C02-ANCILLARY-METRIC-CORRECTION-v1',created_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),original_rows=dict(path=str((ART/'ACTUAL_OFFER_ROWS.json.gz').relative_to(ROOT)),SHA256=hashlib.sha256((ART/'ACTUAL_OFFER_ROWS.json.gz').read_bytes()).hexdigest()),current_view='src/receiving_lookback_results_c02.py:metric_rows',reason='CopiedretainedE0ancillarylogloss/pointBrierwere notthe newproceduresmetrics. LAW Brieraggregatesalreadycorrect; unusedinheritedmetricsremoved/recomputed inappend-onlyview.',predictions_sides_or_grades_changed=0,already_reported_Brier_or_counts_changed=0,point_probability_metrics='NOT_AVAILABLE',old_rows_preserved=True)
 write(OUT/'METRIC_VIEW_CORRECTION.json',correction)
 old=[]
 for r in corrected_rows():
  if r['method'] in ['P1','P2','P3']:
   q=dict(r);q['method']='PREVIOUS_CONTEXT_'+r['method'];old.append(q)
  elif r['method'] in ['E0','RETAINED_P2_LAW','RETAINED_EARLIER_PREVALENCE_V8','ALWAYS_OVER','ALWAYS_UNDER']:old.append(r)
 scores=[]
 for scope,positions in [('WR_TE',['WR','TE']),('ALL_SUPPORTED',['RB','WR','TE']),('RB',['RB'])]:
  for week in ['ALL',2,3]:
   for method in sorted({r['method'] for r in new+old}):
    rr=[r for r in new+old if r['method']==method and r['position'] in positions and (week=='ALL' or r['week']==week)];known=[r for r in rr if r['status'] in ['WIN','LOSS']];p=[r for r in known if r.get('probabilities')]
    scores.append(dict(scope=scope,week=week,method=method,**common.summary(rr),Brier=sum(r['Brier'] for r in p)/len(p) if p else None,log_loss=sum(r['log_loss'] for r in p)/len(p) if p and all(r.get('log_loss') is not None for r in p) else None,infinite_log_losses=sum(r.get('infinite_log_loss',False) for r in p),evidence_tier='TIMING_UNVERIFIED_LAST_RECORDED_ACTUAL_LINES',actual_weeks=[2,3] if week=='ALL' else [week]))
 write(OUT/'STRONG_CONTROL_SCORES.json.gz',scores)
 pairs=[]
 for scope,positions in [('WR_TE',['WR','TE']),('ALL_SUPPORTED',['RB','WR','TE'])]:
  for a,b in [('CHOSEN_LAW','PREVIOUS_CONTEXT_P2'),('CHOSEN_MEDIAN','PREVIOUS_CONTEXT_P2'),('CHOSEN_MEAN','PREVIOUS_CONTEXT_P1')]:
   aa={r['offer_id']:r for r in new if r['method']==a and r['position'] in positions};bb={r['offer_id']:r for r in old if r['method']==b and r['position'] in positions};ids=sorted(aa.keys()&bb.keys());ids=[i for i in ids if aa[i]['status'] in ['WIN','LOSS'] and bb[i]['status'] in ['WIN','LOSS']];groups=collections.defaultdict(lambda:np.zeros(2))
   for i in ids:
    assert all(aa[i][k]==bb[i][k] for k in ['game_id','player_id','actual','line','appearance']);groups[aa[i]['game_id']]+=[int(aa[i]['status']=='WIN')-int(bb[i]['status']=='WIN'),1]
   blocks=np.asarray(list(groups.values()));rng=np.random.default_rng(661107);s=blocks[rng.integers(len(blocks),size=(2000,len(blocks)))].sum(axis=1);ci=np.quantile(s[:,0]/s[:,1],[.025,.975])*100
   aw=sum(aa[i]['status']=='WIN' for i in ids);bw=sum(bb[i]['status']=='WIN' for i in ids);bp=[i for i in ids if aa[i].get('probabilities') and bb[i].get('probabilities')]
   pairs.append(dict(scope=scope,candidate=a,control=b,decided=len(ids),candidate_wins=aw,control_wins=bw,win_difference=aw-bw,sensitivity95_pp=ci.tolist(),Brier_change=sum(aa[i]['Brier']-bb[i]['Brier'] for i in bp)/len(bp) if bp else None))
 write(OUT/'STRONG_CONTROL_PAIRS.json',pairs)
 # Exactly the existing exploratory list rule, no new gate or timing claim.
 with zipfile.ZipFile(ROOT/'artifacts/basic-football-facts-v2.1.zip') as z:sch=pd.read_csv(io.BytesIO(z.read('schedule.csv')))
 sch['kickoff_UTC']=pd.to_datetime(sch.gameday+' '+sch.gametime).dt.tz_localize('America/New_York').dt.tz_convert('UTC').astype(str);kick=dict(zip(sch.game_id,sch.kickoff_UTC))
 top=[]
 for scope,positions in [('WR_TE',['WR','TE']),('ALL_SUPPORTED',['RB','WR','TE'])]:
  for week in [2,3]:
   for method in ['ORDINARY_LAW','CONTEXT8_LAW','CHOSEN_LAW','PREVIOUS_CONTEXT_P2','E0']:
    source=[dict(r,_confidence=r['probabilities'][r['selected_side'].lower()],kickoff_UTC=kick[r['game_id']]) for r in new+old if r['method']==method and r['week']==week and r['position'] in positions and r['selected_side'] in ['OVER','UNDER'] and r.get('probabilities')]
    for side in ['MIXED','OVER_ONLY','UNDER_ONLY']:
     for K in [6,10,20]:
      selected,board=choose(source,side,K);top.append(dict(scope=scope,week=week,method=method,side=side,K=K,candidate_eligible=len(source),side_board=len(board),member_ids=[r['offer_id'] for r in selected],**common.summary(selected),mean_selected_confidence=sum(r['_confidence'] for r in selected)/len(selected) if selected else None,tier='EXPLORATORY_LAST_RECORDED_LINES;NO_SIMULTANEOUS_BOARD_OR_ENTRY'))
 write(OUT/'TOPK_DIAGNOSTIC.json.gz',top)
 # Native same-mask game/week-aware numerical differences against strongLeaf.
 numeric=read(ART/'EVALUATION_PREDICTIONS.json.gz');num=[]
 for scope,positions in [('WR_TE',['WR','TE']),('ALL_SUPPORTED',['RB','WR','TE'])]:
  for control in ['ORDINARY','CONTEXT8','LEAF']:
   rr=[r for r in numeric if r['position'] in positions and r['actual'] is not None and r.get(control) is not None];delta=[abs(r['CHOSEN']['median']-r['actual'])-abs(r[control]['median']-r['actual']) for r in rr]
   entry=dict(scope=scope,candidate='CHOSEN',control=control,known=len(rr),median_MAE_difference=sum(delta)/len(delta))
   for blockkey in ['game_id','week']:
    groups=collections.defaultdict(lambda:np.zeros(2))
    for r,d in zip(rr,delta):groups[r[blockkey]]+=[d,1]
    blocks=np.asarray(list(groups.values()));rng=np.random.default_rng(661107);s=blocks[rng.integers(len(blocks),size=(2000,len(blocks)))].sum(axis=1);ci=np.quantile(s[:,0]/s[:,1],[.025,.975]);entry[blockkey+'_clusters']=len(blocks);entry[blockkey+'_sensitivity95']=ci.tolist()
   num.append(entry)
 write(OUT/'NUMERICAL_PAIRED_CHANGES.json',num)
 print('ZERO_REFIT_STRONG_CONTROL_CLOSURE',pairs[:3])
if __name__=='__main__':main()
