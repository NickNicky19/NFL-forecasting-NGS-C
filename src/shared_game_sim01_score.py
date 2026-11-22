"""Post-freeze comparison view using the existing canonical grade semantics.

Only this separate postforecast stage opens offers, comparator values/outcomes.
Protected case/grade/selection rows remain private; public outputs are aggregates.
"""
from __future__ import annotations
import argparse,gzip,hashlib,json,math
from collections import defaultdict
from pathlib import Path
import numpy as np
from shared_game_sim01_budget import ROOT,D,save
from shared_game_sim01_inputs import canonical_team
from shared_game_sim01_kernel import direct_count_probabilities,direct_signed_probabilities,COUNT_FIELDS
from shared_game_sim01_retention import reopen_replay_bundle
from shared_game_sim01_controls import build_controls

PRIVATE=ROOT/'private/shared-game-sim-01'
def readl(p):return [json.loads(s) for s in p.read_bytes().splitlines()]
def side(p):return 'OVER' if p['over']>p['under'] else 'UNDER' if p['under']>p['over'] else 'ABSTAIN'
def point_side(x,line):return 'OVER' if x>line else 'UNDER' if x<line else 'ABSTAIN'
def sample_column(game,team,player,field):
 for prefix,m in game.metadata['teams'].items():
  if m['team_id']!=team:continue
  if player not in m['actor_ids']:return None,None,None
  ai=m['actor_ids'].index(player)
  if field in COUNT_FIELDS:col=ai
  else:
   columns=m['rush_rec_yd_columns'] if field=='rush_rec_yd' else m['anytime_td_columns'] if field=='anytime_td' else m['child_columns'].get(field,[])
   if ai not in columns:return None,None,None
   col=columns.index(ai)
  k=prefix+field
  if k not in game.arrays:return None,None,None
  return game.arrays[k][:,col],game.dp_moments.get(k),col
 return None,None,None
def predictions():
 # The actual remote-restored raw forecast shard identities must already be
 # frozen before any grade/outcome row is opened.
 freeze=json.loads((D/'FREEZE_B.json').read_text())
 if freeze['state']!='FORECAST_BYTES_DURABLY_REOPENED_BEFORE_GRADES':raise ValueError('FORECAST_FREEZE_NOT_READY')
 cases=readl(PRIVATE/'views/comparison_inputs/cases.jsonl')
 bench={r['case_id']:r for r in readl(PRIVATE/'views/comparison_inputs/benchmarks.jsonl')}
 ident=json.loads((PRIVATE/'identity_rows.json').read_text());imap={r['case_id']:r for r in ident}
 rawplayers=json.loads((PRIVATE/'mapped_players.json').read_text());pgmap={r['player_game_key']:r for r in rawplayers}
 index=json.loads((D/'GAME_EXECUTION_INDEX.json').read_text());gmap={r['native_game_id']:r for r in index}
 out={m:[] for m in ('S-P::LAW','S-P::MEAN_POINT','S-P::MEDIAN_POINT','D-P::LAW','W0','W1','ALWAYS_OVER','ALWAYS_UNDER')}
 bygame=defaultdict(list)
 for c in cases:bygame[imap[c['case_id']].get('canonical_game_id')].append(c)
 for gid,cc in bygame.items():
  kept=None
  if gid in gmap:kept=reopen_replay_bundle(PRIVATE/'samples'/(gid+'.zip'),expected_sha256=gmap[gid]['SHA256'])
  for c in cc:
   cid=c['case_id'];q=c['identity'];r=imap[cid];p=pgmap[c['player_game_key']];field=q['category'];line=q['line']
   base=dict(case_id=cid,category=field,season=q['season'],week=q['week'],game_id=q['game_id'],player_id=q['player_id'],point=None,probabilities=None,available=False,selected_side=None,fallback=False,native=False)
   reason=None;x=None;dp=None;col=None
   if not r['status'].startswith('READY_') or not p['identity_available']:reason='UNAVAILABLE_CANONICAL_IDENTITY'
   elif p['provider_missing'].get(field,True):reason='UNAVAILABLE_PROVIDER_RAW'
   elif kept is None:reason='GAME_NOT_EXECUTED'
   else:
    x,dp,col=sample_column(kept,canonical_team(q['team']),r['canonical_player_id'],field)
    if x is None:reason='UNAVAILABLE_QUALIFIED_COMPONENT'
   if reason:
    for m in ('S-P::LAW','S-P::MEAN_POINT','S-P::MEDIAN_POINT','D-P::LAW'):out[m].append(dict(base,unavailable_reason=reason))
   else:
    probabilities=dict(under=float(np.mean(x<line)),push=float(np.mean(x==line)),over=float(np.mean(x>line)))
    mean=float(np.mean(x));median=float(np.quantile(x,.5,method='inverted_cdf'))
    lo,hi=map(float,np.quantile(x,[.05,.95],method='inverted_cdf'))
    out['S-P::LAW'].append(dict(base,available=True,native=True,point=mean,probabilities=probabilities,selected_side=side(probabilities),interval90=[lo,hi]))
    for m,value in [('S-P::MEAN_POINT',mean),('S-P::MEDIAN_POINT',median)]:out[m].append(dict(base,available=True,native=True,point=value,selected_side=point_side(value,line)))
    if dp is None:out['D-P::LAW'].append(dict(base,unavailable_reason='DP_COMPONENT_UNAVAILABLE'))
    else:
     mu=float(dp['mean'][col]);variance=float(dp['total_variance'][col]);mix=float(dp['conditional_mean_variance'][col])
     prob=direct_count_probabilities(mu,mix,line) if field in COUNT_FIELDS or field=='pass_td' else direct_signed_probabilities(mu,variance,line)
     out['D-P::LAW'].append(dict(base,available=True,native=True,point=mu if field in COUNT_FIELDS or field=='pass_td' else None,probabilities=prob,selected_side=side(prob)))
   for m,key in [('W0','W0_literal_saved_adj'),('W1','W1_literal_provider_or_adjusted_fallback')]:
    value=bench[cid][key];fb=bench[cid]['point_source']!='model'
    out[m].append(dict(base,available=True,point=value,selected_side=point_side(value,line),fallback=fb,native=not fb))
   for m,s in [('ALWAYS_OVER','OVER'),('ALWAYS_UNDER','UNDER')]:out[m].append(dict(base,available=True,selected_side=s,native=False))
  del kept
 out.update(build_controls(ROOT,cases,ident))
 save(PRIVATE/'typed_all_predictions.json',out)
 save(D/'PREDICTION_ADAPTER_RECEIPT.json',dict(methods=list(out),full_case_count=len(cases),scope='Saved point/law and generated output adapters only, no outcomes read here',source_clock='Unverified historical issuance/quotes retained',case_rows_public=False))
 return cases,out
def score():
 from shared_game_sim01_metrics import evaluate,build_raw_grades
 cases,preds=predictions();outcomes=readl(PRIVATE/'views/grading_only/outcomes.v1.jsonl')
 assert len(cases)==len(outcomes)==3474 and sum(r['actual'] is None for r in outcomes)==464
 # Durable private raw grades first, before summaries or selective views.
 raw=build_raw_grades(cases,outcomes,preds)
 body=json.dumps(raw,separators=(',',':'),allow_nan=False).encode();p=PRIVATE/'raw_grades.json.gz';p.write_bytes(gzip.compress(body,mtime=0))
 assert gzip.decompress(p.read_bytes())==body
 save(D/'RAW_GRADE_PERSISTENCE.json',dict(rows=len(raw),uncompressed_bytes=len(body),compressed_bytes=p.stat().st_size,SHA256=hashlib.sha256(p.read_bytes()).hexdigest(),scope='Private grades retain exact canonical cases/outcomes/versions; original source untouched; no public raw publication',before_selective_summaries=True))
 result=evaluate(cases,outcomes,preds,raw_grades=json.loads(gzip.decompress(p.read_bytes())))
 result.pop('raw_grades',None)
 # Lists identify offered cases and stay in the approved private reconstruction
 # route; published summaries are counts/metrics/paired aggregates only.
 save(PRIVATE/'complete_results_with_membership.json',result)
 def public_view(x):
  if isinstance(x,dict):return {k:public_view(v) for k,v in x.items() if k not in ('case_ids','raw_grades','selection_records','membership')}
  if isinstance(x,list):return [public_view(v) for v in x]
  return x
 result=public_view(result)
 save(D/'COMPARISON_RESULTS.json',result)
 print('NEW_CANONICAL_COMPARISON_COMPLETE',len(preds),len(raw))
if __name__=='__main__':score()
