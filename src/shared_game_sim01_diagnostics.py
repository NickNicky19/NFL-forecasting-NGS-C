"""One NFL-design analytic-gradient check; never calls an optimizer or sampler."""
from __future__ import annotations
import json
import numpy as np
from shared_game_sim01_budget import ROOT,D,save
from shared_game_sim01_inputs import load_context
from shared_game_sim01_fit import load_sources,restore_origin,build_team_prior
from shared_game_sim01_condition import _targets,_prepare_core,CORE

def check():
 private=ROOT/'private/shared-game-sim-01';games,players=load_context(private);g=games[0]
 store=load_sources(ROOT);prior=restore_origin(store,json.loads((private/'frozen_startup_prior.json').read_text()))
 reports=[];vectors=[]
 for team in (g['home'],g['away']):
  pp=[p for p in players if p['identity_available'] and p['game_origin_key']==g['game_origin_key'] and p['team']==team]
  actors=[dict(gsis_id=k,position=v) for k,v in sorted({p['gsis_id']:p['position'] for p in pp}.items())]
  t,m=build_team_prior(store,prior,team,g['model_cutoff_utc'],actors)
  anchors={p['gsis_id']:p['provider_points'] for p in pp}
  records,_=_targets(t,anchors,m['process_variances'],CORE)
  f,x0,_=_prepare_core(t,records);value,analytic=f(x0);finite=np.zeros_like(x0)
  # Chosen before inspecting this check: central difference1e-6; absolute1e-5
  # plus relative1e-5 criterion; no fit retries or tolerance adjustment.
  for j in range(len(x0)):
   plus=x0.copy();minus=x0.copy();plus[j]+=1e-6;minus[j]-=1e-6
   finite[j]=(f(plus)[0]-f(minus)[0])/(2e-6)
  delta=np.abs(analytic-finite);ok=bool(np.all(delta<=1e-5+1e-5*np.abs(finite)))
  reports.append(dict(team=team,parameters=len(x0),max_absolute_gradient_difference=float(delta.max(initial=0)),PASS=ok,consumed_earlier_design_SHA256=m['consumed_design_SHA256']))
  vectors.append(dict(team=team,analytic=analytic.tolist(),finite_difference=finite.tolist()))
 save(private/'gradient_vectors.json',vectors)
 save(D/'NFL_INITIAL_GRADIENT_CHECK.json',dict(state='PASS' if all(r['PASS'] for r in reports) else 'FAILED',scope='NFL full earlier/query context objective gradient only; no solve, fit reproduction, forecast or sampling',native_game_id=g['native_game_id'],central_step=1e-6,absolute_tolerance=1e-5,relative_tolerance=1e-5,teams=reports,failed_canary_optimizer_status='NOT_RETAINED_DUE_TO_FAILURE_REPORT_PATH_DEFECT; do not infer termination or maxiter',optimizer_invocations=0))
 print('NFL_INITIAL_GRADIENT_CHECK',all(r['PASS'] for r in reports),sum(r['parameters'] for r in reports))
if __name__=='__main__':check()
