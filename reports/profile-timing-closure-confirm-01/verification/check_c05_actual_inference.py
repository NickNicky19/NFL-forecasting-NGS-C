import pathlib,json,lzma,hashlib,math,struct,datetime,time,resource,subprocess
cpu=time.process_time();root=pathlib.Path('/workspace/ngs-c');draft=pathlib.Path('/workspace/c05-current-draft')
def load(p):
 b=p.read_bytes();return json.loads(lzma.decompress(b) if p.suffix=='.xz' else b)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dt(x):
 d=datetime.datetime.fromisoformat(x);assert d.tzinfo;return d
D=load(draft/'DRAFT.json'); rows=load(draft/'FORECASTS_DRAFT.json.xz');board=load(draft/'CURRENT_BOARD.json.xz')
assert D['code_commit']=='0e1768af6134a66fc71d6eaec3f92ef5a10693bb'
for rel,b in D['files'].items():assert (draft/rel).stat().st_size==b['bytes'] and sha(draft/rel)==b['SHA256']
for rel,h in D['code_SHA256'].items():assert sha(root/rel)==h and hashlib.sha256(subprocess.check_output(['git','show',D['code_commit']+':'+rel],cwd=root)).hexdigest()==h
reg=root/'protocol/PROFILE_TIMING_CLOSURE_CONFIRM_01_C.json';assert sha(reg)==D['registration_SHA256']
source=root/D['source_input']['path'];assert sha(source)==D['source_input']['SHA256'];S=load(source)
assert D['information_policy']=='FROZEN_FOOTBALL_SNAPSHOT_FIRST_PUBLICATION_SHADOW' and S['forecast_information_policy'].startswith('EXPLICIT_FROZEN_FOOTBALL_SNAPSHOT_FIRST_PUBLICATION_SHADOW;') and 'Notclaimedlatest-football-inputupdate.' in S['forecast_information_policy']
assert D['information_cutoff_UTC']==S['model_feature_cutoff_UTC']=='2026-11-10T19:23:09.469852+00:00'
assert S['football_source_cutoff_UTC']=='2026-11-10T18:55:28.982066+00:00'
assert D['eligibility_input_cutoff_UTC']==S['actual_eligibility_cutoff_UTC']=='2026-11-10T22:51:53.312826+00:00'
assert dt(S['football_source_cutoff_UTC'])<dt(D['information_cutoff_UTC'])<dt(D['eligibility_input_cutoff_UTC'])<dt(D['started_UTC'])<dt(D['created_UTC'])
O=root/'prospective/runs/C-C04-20261110-W10-FIRST-01';assert sha(O/'RUN.json')=='a951398153017f5dcf30a4b201821ca5bcc4798f9ae58ac36184012b402cb40d'
OR=load(O/'RUN.json');assert sha(O/'FORECASTS.json.xz')=='4334c6e93d41487011e3bedb9a0a0173e38ccfcf5c568b30efbd0b73995be362'
for rel,b in OR['files'].items():assert sha(O/rel)==b['SHA256'] and (O/rel).stat().st_size==b['bytes']
old=load(O/'draft/DRAFT_FORECASTS.json.xz');lookup={(r['model_id'],r['game_id'],r['player_id']):r for r in old}
roster=load(root/'sources/profile-timing-closure-confirm-01/forward/roster_current_season.json');R={r['gsis_id']:r for r in roster}
assert len(R)==len(roster)==len(board)==959
want={k for k,r in R.items() if r['status']=='ACT' and r['team'] in ['NE','DET'] and r['position'] in ['RB','WR','TE']}
assert len(want)==23
actual_board={r['player_id'] for r in board if r['eligible_current_query']};assert want==actual_board
assert all(r['available_all_models'] for r in board if r['eligible_current_query'])
models={}
for ref in D['lineage']['models']:
 p=root/ref['path'];assert sha(p)==ref['SHA256'];models[ref['model_id']]=load(p)
assert len(rows)==69 and len({(r['model_id'],r['player_id']) for r in rows})==69
assert {r['player_id'] for r in rows}==want
assert {r['game_id'] for r in rows}=={'2026_10_NE_DET'}
assert len(load(O/'FORECASTS.json.xz'))==75
assert all(r['game_id']!='2026_10_NE_DET' for r in load(O/'FORECASTS.json.xz'))
# Separate pure-Python reconstruction of numeric forest paths and pooled coefficients.
def design(v,impute,float32=False):
 missing=[not isinstance(x,(int,float)) or not math.isfinite(x) for x in v];z=[impute[i] if m else v[i] for i,m in enumerate(missing)]+[float(m) for m in missing]
 return [struct.unpack('f',struct.pack('f',float(x)))[0] for x in z] if float32 else z
def quantile(cdf,p):
 for k in range(10001):
  if cdf(k)>=p:return float(k)
 raise AssertionError('tail bound exceeded')
def leaf(m,v,role):
 z=design(v,m['imputation'],True);mass={};trees=m['trees'];assert len(trees)==32
 for t in trees:
  n=0
  for _ in range(10):
   if t['left'][n]<0:break
   f=t['feature'][n];assert 0<=f<len(z);n=t['left'][n] if z[f]<=t['threshold'][n] else t['right'][n]
  else:raise AssertionError('tree depth')
  vs,cs=t['leaves'][str(n)];den=sum(cs)
  for vv,c in zip(vs,cs):mass[vv]=mass.get(vv,0.0)+c/den/32
 total=math.fsum(mass.values());mass={v:w/total for v,w in mass.items()};prior=m['prior'].get(role,m['global_prior']);assert prior['kind']=='count' and not prior['empty'];q=prior['q'];assert 0<=q<1
 mean=.95*math.fsum(v*w for v,w in mass.items())+.05*q/(1-q)
 def cdf(k):return .95*math.fsum(w for v,w in mass.items() if v<=k)+.05*(1-q**(k+1))
 return mean,{p:quantile(cdf,p) for p in [.05,.5,.95]},mass
max_mean_delta=0.0;max_weight_delta=0.0;max_old_delta=0.0;fam_counts={};clock=[]
for r in rows:
 model=models[r['model_id']];m=model['model'];o=lookup[(r['model_id'],r['game_id'],r['player_id'])]
 assert r['features']==o['features'] and r['feature_order']==o['feature_order']==model['feature_order']
 assert r['model_SHA256']==sha(root/next(x['path'] for x in D['lineage']['models'] if x['model_id']==r['model_id']))
 assert r['team']==R[r['player_id']]['team'] and r['position']==R[r['player_id']]['position']
 assert r['kickoff_UTC']=='2026-11-15T14:30:00+00:00' and r['opponent_team']==('NE' if r['team']=='DET' else 'DET')
 assert r['information_cutoff_UTC']==D['information_cutoff_UTC'] and r['information_policy']==D['information_policy']
 assert r['original_prepared_inference_UTC']==o['inference_UTC']
 assert dt(o['inference_UTC'])<dt(D['started_UTC'])<=dt(r['inference_UTC'])<=dt(D['created_UTC'])
 assert not ({'actual','outcome','played','participated','realized_targets','realized_carries'}&r.keys())
 assert all(r[k] is None for k in ['line','selected_side','probability_at_line','confidence','EV'])
 assert all(h['game_id']!=r['game_id'] and h['kickoff']<dt(r['information_cutoff_UTC']).timestamp() for h in r['admitted_prior_games'])
 fam_counts[model['family']]=fam_counts.get(model['family'],0)+1
 if model['family']=='LEAF':
  mean,qs,mass=leaf(m,r['features'],r['position']);law=r['law'];assert law['alpha']==.05 and law['scale']==1
  assert law['values']==sorted(mass)
  max_weight_delta=max(max_weight_delta,max(abs(mass[v]-w) for v,w in zip(law['values'],law['weights'])))
  assert abs(math.fsum(law['weights'])-1)<1e-12 and law['prior']==m['prior'].get(r['position'],m['global_prior'])
 else:
  assert model['family']=='POISSON' and not m['partial'] and not m['categories'];z=design(r['features'],m['impute']);z=[(v-c)/s for v,c,s in zip(z,m['center'],m['scale'])]
  mean=math.exp(m['intercept']+math.fsum(v*c for v,c in zip(z,m['coef'])))
  def cdf(k):
   term=math.exp(-mean);result=term
   for i in range(1,k+1):term*=mean/i;result+=term
   return result
  qs={p:quantile(cdf,p) for p in [.05,.5,.95]};assert r['law']['kind']=='POISSON' and abs(r['law']['mu']-mean)<1e-12
 max_mean_delta=max(max_mean_delta,abs(mean-r['mean']));max_old_delta=max(max_old_delta,abs(r['mean']-o['mean']))
 assert abs(mean-r['mean'])<1e-12 and qs[.5]==r['median'] and qs[.05]==r['p05'] and qs[.95]==r['p95']
 clock.append(r['inference_UTC'])
assert max_weight_delta<1e-12 and D['new_fits']==0 and D['new_inference_rows']==69
out={'id':'C05-INDEPENDENT-ACTUAL-INFERENCE-v1','status':'PASS_INDEPENDENT_SAFE_JSON_INFERENCE_AND_BINDINGS','checked_UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'code_commit':D['code_commit'],'draft_SHA256':sha(draft/'DRAFT.json'),'forecasts_SHA256':sha(draft/'FORECASTS_DRAFT.json.xz'),'basic_board':959,'current_eligible_receiving_players':23,'actual_inference_rows':69,'families':fam_counts,'calculation_path':'Independent standard-library tree traversal, float32 feature conversion, normalized empirical/geometric mixtures, and pooled-Poisson coefficients/quantiles; no author inference or scoring function invoked.','mean_tolerance':1e-12,'maximum_mean_absolute_delta':max_mean_delta,'maximum_leaf_weight_absolute_delta':max_weight_delta,'maximum_mean_delta_from_original_prepared':max_old_delta,'quantiles_all_exact':True,'target_outcomes_absent':True,'all_offer_selection_confidence_EV_fields_null':True,'frozen_feature_cutoff_UTC':D['information_cutoff_UTC'],'current_eligibility_cutoff_UTC':D['eligibility_input_cutoff_UTC'],'inference_start_UTC':D['started_UTC'],'first_inference_UTC':min(clock),'last_inference_UTC':max(clock),'inference_completed_UTC':D['created_UTC'],'original_75_RUN_unchanged':True,'original_75_FORECASTS_unchanged':True,'new_fits':0,'new_GETs':0,'limitations':['This verifies the new inference draft, not issuance, native-event freshness, publication, or consumer admission.','The football source and features remain explicitly frozen; current roster receipt does not establish newer football inputs.','Receiving forecasts remain appearance-conditioned, with no starter, injury, participation, or actual-offer assertion.'],'CPU_seconds':time.process_time()-cpu,'peak_RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024}
assert out['CPU_seconds']<28 and out['peak_RSS_bytes']<=768*1024**2
pathlib.Path('/workspace/c05-actual-inference-independent.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
