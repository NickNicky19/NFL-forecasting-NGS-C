"""Validation adapter for immutable typed C04 captures; no acquisition or fit.

The producer and its saved bytes stay frozen. Expiry affects current display,
not the original issuance, so source/event admission is checked at issue time.
"""
from pathlib import Path
import hashlib,json,lzma,math
import numpy as np
import pandas as pd
from scipy.stats import poisson
from scipy.special import ive
from contracts_v2 import probs
from safe_models_v4 import infer_forest,law_load
from context_experiment_c01 import pooled_mu

SCHEMA='C04-CURRENT-FORECAST-ONLY-RUN-v1'
RECEIPT_SCHEMA='C04-SERVER-PREGAME-RECEIPT-v1'
ROOT=Path(__file__).resolve().parents[1]

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):
 p=Path(path);b=p.read_bytes();return json.loads(lzma.decompress(b) if p.suffix=='.xz' else b)
def aware(value):
 t=pd.Timestamp(value);assert t.tzinfo is not None,'C04_NAIVE_CLOCK';return t

def bound_files(base,files):
 for name,info in files.items():
  p=(base/name).resolve();assert p.is_relative_to(base.resolve()),'C04_PATH_ESCAPE'
  assert p.stat().st_size==info['bytes'] and sha(p)==info['SHA256'],'C04_CAPTURE_BYTES_CHANGED:'+name

def close(a,b):return math.isclose(float(a),float(b),rel_tol=1e-12,abs_tol=1e-10)

class PoissonCountLaw:
 """Typed count-law view of an already saved Poisson mean; no fitted repair."""
 scale=1
 def __init__(self,mu):
  assert not isinstance(mu,bool) and isinstance(mu,(int,float)) and math.isfinite(mu) and mu>=0,'C04_INVALID_POISSON_MU'
  self.mu=float(mu)
 def mean(self):return self.mu
 def cdf(self,k):return float(poisson.cdf(math.floor(k),self.mu))
 def pmf(self,k):return float(poisson.pmf(k,self.mu))
 def logpmf(self,k):return float(poisson.logpmf(k,self.mu))
 def quantile(self,p):
  assert 0<p<1
  return float(poisson.ppf(p,self.mu))
 def probability(self,line):return probs(self.cdf,line,1)
 def crps(self,y):
  assert math.isfinite(y) and float(y).is_integer(),'C04_NONINTEGER_COUNT_LABEL'
  if not self.mu:return abs(float(y))
  first=self.mu-y if y<0 else y*(2*self.cdf(y)-1)+self.mu*(1-2*self.cdf(y-1))
  # E|X-X'|/2 for independent Poisson(mu), using scaled Bessel
  # functions to avoid overflow; this is a score, not a new forecast law.
  return max(0.,float(first-self.mu*(ive(0,2*self.mu)+ive(1,2*self.mu))))

def load_capture_law(data):
 if data.get('kind')=='POISSON':return PoissonCountLaw(data['mu'])
 return law_load(data)

def validate_run(run,check_clock=False):
 from receiving_current_capture_c04 import validate_status_snapshot,qualified_events,timestamp
 run=Path(run);m=read(run/'RUN.json');assert m['schema']==SCHEMA
 bound_files(run,m['files'])
 appendix=read(run/'RECOVERY_COMPLETENESS_APPENDIX.json');assert appendix['parent_RUN_SHA256']==sha(run/'RUN.json') and appendix['fits_added']==0,'C04_RECOVERY_PARENT_MISMATCH'
 bound_files(run,{x['path']:x for x in appendix['added_files']})
 draft=read(run/'draft/DRAFT.json');bound_files(run/'draft',draft['files'])
 assert m['code_commit']==draft['code_commit'] and m['registration_SHA256']==draft['registration_SHA256'] and m['code_SHA256']==draft['code_SHA256'],'C04_PRODUCER_BINDING_CHANGED'
 rows=read(run/'FORECASTS.json.xz');assert len(rows)==m['forecast_rows'] and rows
 assert len({r['forecast_id'] for r in rows})==len(rows) and len({(r['model_id'],r['game_id'],r['player_id']) for r in rows})==len(rows),'C04_DUPLICATE_FORECAST'
 assert m['real_offers']==m['real_selections']==0 and m['primary_replacement'] is False
 source=read(run/'STATUS_SOURCE_MANIFEST.json');proof=read(run/'CLEAN_START_PROOF.json');issued=aware(m['issued_UTC']);at=issued.timestamp()
 assert proof['git_status']=='' and proof['code_commit']==m['code_commit'] and proof['registration_SHA256']==m['registration_SHA256']
 # Validate the retained original response bytes and clocks, never today's age.
 events,verified=validate_status_snapshot(ROOT/source['events_binding']['path'],at,input_manifest_SHA256=m['source_input_manifest_SHA256'],after=timestamp(proof['created_UTC']))
 assert events==read(run/'NATIVE_STATUS.json')==source['events'],'C04_NATIVE_EVENT_BYTES_MISMATCH'
 saved=read(run/'INDEPENDENT_STATUS_VERIFICATION.json');assert saved==verified,'C04_STATUS_VERIFICATION_CHANGED'
 assert read(ROOT/'sources/profile-closure-next-02/SOURCE_MANIFEST.json')==source,'C04_SOURCE_MANIFEST_CHANGED'
 accepted,rejected=qualified_events(draft['candidate_games'],events,at,after=timestamp(proof['created_UTC']))
 admission=read(run/'EVENT_ADMISSION.json');assert accepted==admission['accepted'] and rejected==admission['rejected']
 assert sorted(accepted)==sorted(m['games']) and len({r['player_id'] for r in rows})==m['unique_players']
 originals={(r['model_id'],r['game_id'],r['player_id']):r for r in read(run/'draft/DRAFT_FORECASTS.json.xz')}
 modelmap={x['model_id']:x for x in m['models']};assert len(modelmap)==3
 models={}
 held=set(read(ROOT/source['model_inputs']['path'])['held_recent_game_ids'])
 for name,spec in modelmap.items():
  path=run/'draft'/spec['path'];assert sha(path)==spec['SHA256'],'C04_MODEL_BYTES_CHANGED'
  meta=read(path);models[name]=meta
  assert meta['model_id']==name and len(meta['feature_order'])==spec['feature_count']
  assert len(meta['training_membership'])==len(meta['training_feature_rows'])==len(meta['training_labels'])==len(meta['training_roles'])==meta['training_rows']
  assert all(len(x)==spec['feature_count'] for x in meta['training_feature_rows']),'C04_TRAINING_FEATURE_ORDER_SHAPE'
  assert all(isinstance(y,(int,float)) and not isinstance(y,bool) and math.isfinite(y) and y>=0 and float(y).is_integer() for y in meta['training_labels']),'C04_INVALID_TRAINING_COUNT'
  impute=meta['model']['imputation'] if meta['family']=='LEAF' else meta['model']['impute']
  assert len(impute)==spec['feature_count']
  assert not held.intersection(r['game_id'] for r in meta['training_membership']),'C04_HELD_HISTORY_CONSUMED'
  assert all(r['kickoff']<timestamp(meta['fit_information_cutoff_UTC']) for r in meta['training_membership'])
  if name!='C_V4_RETAINED_REFERENCE_OBSERVED':assert all(r['available']<timestamp(meta['fit_information_cutoff_UTC']) for r in meta['training_membership'])
 for r in rows:
  assert r['category']=='rec' and r['position'] in ['RB','WR','TE'] and r['roster_status']=='ACT'
  assert all(r[k] is None for k in ['line','selected_side','probability_at_line','confidence','EV']),'C04_UNQUALIFIED_OFFER_OUTPUT'
  assert not any(k in r for k in ['actual','played','values','realized_starter']),'C04_FUTURE_OUTCOME_INPUT'
  assert r['game_id'] in accepted and r['event_version']==accepted[r['game_id']]['event_version']
  assert aware(r['information_cutoff_UTC'])<=aware(r['inference_UTC'])<issued and issued+pd.Timedelta(seconds=300)<aware(r['kickoff_UTC']),'C04_INVALID_ISSUE_CLOCK'
  assert issued<aware(r['expires_UTC'])<=aware(r['kickoff_UTC']),'C04_EXPIRED_AT_ISSUE'
  q=originals[(r['model_id'],r['game_id'],r['player_id'])]
  assert all(r[k]==v for k,v in q.items() if k!='state'),'C04_DRAFT_PREDICTION_CHANGED'
  meta=models[r['model_id']];assert r['model_SHA256']==modelmap[r['model_id']]['SHA256'] and r['feature_order']==meta['feature_order'] and len(r['features'])==len(meta['feature_order'])
  assert all(isinstance(r[k],(float,int)) and not isinstance(r[k],bool) and math.isfinite(r[k]) and r[k]>=0 for k in ['mean','median','p05','p95']),'C04_NONFINITE_POINT'
  assert r['p05']<=r['median']<=r['p95'] and all(float(r[k]).is_integer() for k in ['median','p05','p95'])
  if meta['family']=='LEAF':
   law=law_load(r['law']);assert law.prior.kind=='count' and law.scale==1
   assert close(r['mean'],law.mean()) and r['median']==law.quantile(.5) and r['p05']==law.quantile(.05) and r['p95']==law.quantile(.95),'C04_LAW_POINT_MISMATCH'
   assert 0<=law.a<=1 and 0<=law.prior.q<1 and abs(law.cdf(100000)-1)<1e-10
  else:
   assert meta['family']=='POISSON' and r['law']['kind']=='POISSON'
   mu=r['law']['mu'];assert math.isfinite(mu) and mu>=0 and close(mu,r['mean'])
   assert r['median']==poisson.ppf(.5,mu) and r['p05']==poisson.ppf(.05,mu) and r['p95']==poisson.ppf(.95,mu)
 # Small fixed restoration sample per family. All saved points/laws above are
 # checked; this adds an independent saved-model-to-query check without fitting.
 for name,meta in models.items():
  sample=sorted([r for r in rows if r['model_id']==name],key=lambda r:r['forecast_id'])[:3]
  x=np.asarray([r['features'] for r in sample],float)
  if meta['family']=='LEAF':
   inferred=infer_forest(meta['model'],x,[r['position'] for r in sample])
   assert all(close(r['mean'],law.mean()) and r['median']==law.quantile(.5) for r,law in zip(sample,inferred)),'C04_RESTORATION_PARITY'
  else:
   inferred=pooled_mu(meta['model'],x,None);assert all(close(r['mean'],v) for r,v in zip(sample,inferred)),'C04_RESTORATION_PARITY'
 if check_clock:assert pd.Timestamp.now(tz='UTC')+pd.Timedelta(seconds=300)<min(aware(r['kickoff_UTC']) for r in rows),'CAPTURE_SERVER_CHECK_TOO_LATE'
 # In-memory adapter for the established first-snapshot registry; original rows
 # and their hashes remain untouched. This is not a new selection or grader.
 return m,[dict(r,policy_id='C04::'+r['model_id'],scoring_contract_id='official-player-fullgame-OT-v1') for r in rows]

def validate_receipt(run,receipt,m,rows):
 run=Path(run);assert receipt['schema']==RECEIPT_SCHEMA and receipt['qualified_prospective'] is True
 assert receipt['run_id']==m['run_id'] and receipt['forecast_blob_SHA256']==sha(run/'FORECASTS.json.xz') and receipt['run_manifest_SHA256']==sha(run/'RUN.json')
 assert receipt['fresh_GitHub_bytes_verified'] is True and receipt['not_client_commit_dates'] is True
 created=aware(receipt['server_run_created_UTC']);started=aware(receipt['server_run_started_UTC']);completed=aware(receipt['server_check_completed_UTC'])
 assert created<=started<=completed and aware(m['created_UTC'])<=completed
 assert all(completed+pd.Timedelta(seconds=300)<aware(r['kickoff_UTC']) for r in rows),'LATE_GITHUB_PERSISTENCE'
 return completed
