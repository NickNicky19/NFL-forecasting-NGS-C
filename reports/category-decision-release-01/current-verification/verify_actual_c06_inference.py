"""Separate standard-library safe-Poisson inference, no author predictor imports."""
import math,json,lzma,hashlib,resource,time
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path('/workspace/ngs-c');D=Path('/workspace/c06-current-draft');OUT=Path('/workspace/c06-actual-inference-independent.json')
def read(p):
 p=Path(p);b=p.read_bytes();return json.loads(lzma.decompress(b) if p.suffix=='.xz' else b)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def instant(s):
 d=datetime.fromisoformat(s.replace('Z','+00:00'));assert d.tzinfo;return d
cpu=time.process_time();draft=read(D/'DRAFT.json')
for path,b in draft['files'].items():assert (D/path).stat().st_size==b['bytes'] and sha(D/path)==b['SHA256']
rows=read(D/'FORECASTS_DRAFT.json.xz');board=read(D/'CURRENT_BOARD.json.xz');assert len(rows)==25 and len(board)==959 and len({r['player_id'] for r in rows})==25
binding=draft['lineage']['model'];p=ROOT/binding['path'];assert p.stat().st_size==binding['bytes'] and sha(p)==binding['SHA256'];meta=read(p);m=meta['model']
assert m['type']=='L2_POOLED_POISSON' and m['partial'] is False and m['categories']==[] and m['alpha']==.1
original=read(ROOT/'prospective/runs/C-C04-20261110-W10-FIRST-01/FORECASTS.json.xz');original={r['player_id']:r for r in original if r['model_id']==meta['model_id']};assert len(original)==25 and set(original)=={r['player_id'] for r in rows}
roster=read(D/'INPUT_MANIFEST.json');assert draft['information_cutoff_UTC']==roster['actual_input_cutoff_UTC']
maximum=0.;maximum_old=0.;qchecks=0;mass_error=0.;side_fields=['line','selected_side','probability_at_line','confidence','EV'];wrte=rb=0
for r in rows:
 x=r['features'];assert r['feature_order']==meta['feature_order'] and len(x)==len(m['impute'])==60 and len(m['coef'])==120
 missing=[v is None or not math.isfinite(float(v)) for v in x]
 filled=[m['impute'][i] if bad else float(x[i]) for i,bad in enumerate(missing)];design=filled+[float(v) for v in missing]
 z=[(v-m['center'][i])/m['scale'][i] for i,v in enumerate(design)]
 eta=sum(v*m['coef'][i] for i,v in enumerate(z))+m['intercept'];mu=math.exp(eta)
 maximum=max(maximum,abs(mu-r['mean']));assert abs(mu-r['mean'])<=1e-12
 def quantile(prob):
  pmf=math.exp(-mu);cdf=pmf;k=0
  while cdf<prob and k<1000:
   k+=1;pmf*=mu/k;cdf+=pmf
  assert k<1000;return k
 for name,prob in [('median',.5),('p05',.05),('p95',.95)]:assert r[name]==quantile(prob);qchecks+=1
 assert r['law']['kind']=='POISSON' and abs(r['law']['mu']-mu)<=1e-12
 pmf=math.exp(-mu);cdf=pmf;previous=0.
 for k in range(101):
  if k:pmf*=mu/k;cdf+=pmf
  assert cdf+1e-14>=previous and -1e-14<=cdf<=1+1e-13;previous=cdf
 mass_error=max(mass_error,abs(1-cdf));assert abs(1-cdf)<1e-13
 old=original[r['player_id']];assert all(r[k]==old[k] for k in ['game_id','team','position','opponent_team','kickoff','features','feature_order','model_SHA256'])
 maximum_old=max(maximum_old,abs(r['mean']-old['mean']));assert abs(r['mean']-old['mean'])<=1e-12 and all(r[k]==old[k] for k in ['median','p05','p95'])
 assert r['original_prepared_inference_UTC']==old['inference_UTC']
 assert instant(r['model_fit_cutoff_UTC'])==instant(meta['fit_information_cutoff_UTC'])<instant(r['information_cutoff_UTC'])<instant(r['inference_UTC'])<=instant(draft['created_UTC'])
 assert instant(r['original_prepared_inference_UTC'])<instant(r['inference_UTC']) and instant(old['issued_UTC'])<instant(r['inference_UTC'])
 assert all(r[k] is None for k in side_fields) and not any(k in r for k in ['actual','played','realized_starter'])
 assert r['starter_state']=='UNKNOWN_NOT_INFERRED' and r['individual_transaction_effective_UTC'] is None
 assert r['corrector']=='NO_EXTRA_CORRECTOR;TRAINING_IMPUTATION_SCALE_AND_POISSON_EXP_LINK_ONCE'
 assert r['direction_candidate_role_eligible']==(r['position'] in ['WR','TE'])
 if r['position']=='RB':assert r['RB_status']=='SEPARATE_FORECAST_ONLY_SHADOW';rb+=1
 else:assert r['position'] in ['WR','TE'];wrte+=1
assert (wrte,rb)==(18,7)
original_hashes={'prospective/runs/C-C04-20261110-W10-FIRST-01/FORECASTS.json.xz':'4334c6e93d41487011e3bedb9a0a0173e38ccfcf5c568b30efbd0b73995be362','prospective/runs/C-C05-NEDET-FIRST-01/FORECASTS.json.xz':'e3dcb454f25b3a3d6b802a72f47ec91d583fe3eeeaa7fc964a0d4d255b16d32e'}
assert all(sha(ROOT/p)==s for p,s in original_hashes.items())
report=dict(id='C06-INDEPENDENT-ACTUAL-INFERENCE-v1',checked_UTC=datetime.now(timezone.utc).isoformat(),status='PASS_INDEPENDENT_SAFE_JSON_COEFFICIENTS_POISSON_QUANTILES_AND_CLOCKS',code_commit=draft['code_commit'],draft_SHA256=sha(D/'DRAFT.json'),forecasts_SHA256=sha(D/'FORECASTS_DRAFT.json.xz'),model_SHA256=binding['SHA256'],calculation_path='Separate standard-library imputation/missing flags, standardized linear coefficients, exp link and Poisson recurrence; no pooled_mu, author predictor, scorer, SciPy or fitted estimator invoked.',mean_tolerance=1e-12,maximum_mean_absolute_delta=maximum,maximum_delta_from_original25=maximum_old,quantile_values_exact=qchecks,maximum_count_mass_error_through100=mass_error,basic_board=959,current_query_players=25,WR_TE_direction_candidate_rows=18,RB_separate_shadow_rows=7,all_offer_side_confidence_EV_fields_null=True,target_outcomes_absent=True,current_information_cutoff_UTC=draft['information_cutoff_UTC'],model_fit_information_cutoff_UTC=meta['fit_information_cutoff_UTC'],new_inference_started_UTC=draft['started_UTC'],first_row_inference_UTC=min(r['inference_UTC'] for r in rows),inference_completed_UTC=draft['created_UTC'],original25_forecast_issued_UTC=min(r['issued_UTC'] for r in original.values()),old75_and69_hashes_unchanged=original_hashes,new_fits=0,new_GETs=0,independent_inference_rows=25,new_NFL_test_observations=0,CPU_seconds=time.process_time()-cpu,peak_RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,limitations=['This verifies the new draft, not final native-event admission, actual issuance, server persistence or consumer admission.','Five-week historical WR/TE point evidence does not automatically qualify seven RB shadows, current query eligibility/horizon, probabilities or Top Picks.','No authentic current offers or original website activation is established.'])
OUT.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
