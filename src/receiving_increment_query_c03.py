"""Explicitly bound current-query adapter for the C03 receiving Leaf arms.

Profiles and safe inference are not primary admission, probability calibration,
provider authentication or proof of a published selection. No acquisition/fits.
"""
from __future__ import annotations
import copy,gzip,hashlib,io,json,lzma,math,re
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
from context_features_c01 import OWN_NAMES
from receiving_defense_c03 import SUPPORT_NAMES,VALUE_NAMES
from receiving_profiles_c02 import BASE_NAMES,instant,utc,source_contract
from forward_sources_v4 import team
from safe_models_v4 import infer_forest

VERSION='C-RECEIVING-PROFILE-INCREMENT-v2'
ADAPTER_VERSION='C03-RECEIVING-QUERY-ADAPTER-v1'
ROOT=Path(__file__).resolve().parents[1]
ORDERS={'R1':BASE_NAMES+OWN_NAMES[:5]+SUPPORT_NAMES,'R2':BASE_NAMES+OWN_NAMES[:5]+SUPPORT_NAMES+OWN_NAMES[5:],'R3':BASE_NAMES+OWN_NAMES[:5]+SUPPORT_NAMES+OWN_NAMES[5:]+VALUE_NAMES}


def digest(obj):return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def finite(value):return value is not None and not isinstance(value,(bool,np.bool_)) and isinstance(value,(int,float,np.number)) and math.isfinite(float(value))
def values(xs):return [float(v) if np.isfinite(v) else None for v in xs]
def file_sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def build_query_profile(builder,defense,query):
 """Build from an explicit roster query. Actual/played/targets never consulted.

 Both original histories and new defense prefixes are capped at the real source
 cutoff, rather than the future kickoff. This does not relax the roster gate.
 """
 base=builder.build(query);features=base['forecast_adapter'].get('features');out={'schema':ADAPTER_VERSION,'recipe_id':VERSION,'base_profile':base,'arms':{},'actual_required':False,'current_model_or_offer_admitted':False}
 if not features:return out
 if int(base['lookback']['player'])!=8:raise ValueError('C03_FIXED_EIGHT_WINDOW_REQUIRED')
 b=features['base'];o=features['own'];dv=defense.vector(query,cutoff=builder.cutoff)
 vectors={'R1':list(b)+list(o[:5])+values(dv[:4]),'R2':list(b)+list(o[:5])+values(dv[:4])+list(o[5:]),'R3':list(b)+list(o[:5])+values(dv[:4])+list(o[5:])+values(dv[4:])}
 for arm,x in vectors.items():
  if len(x)!=len(ORDERS[arm]):raise ValueError('C03_FEATURE_CONSTRUCTION_ORDER')
  out['arms'][arm]={'feature_order':list(ORDERS[arm]),'features':x}
 out['defense_source_bindings']=copy.deepcopy(defense.sources)
 out['defense_code_SHA256']=file_sha(ROOT/'src/receiving_defense_c03.py')
 out['feature_engine_code_SHA256']=file_sha(ROOT/'src/receiving_increment_c03.py')
 return out

def query_contract(profile):
 base=profile['base_profile'];bound={'recipe_id':VERSION,'query_adapter':ADAPTER_VERSION,'base_source_contract':source_contract(base),'defense_source_bindings':profile.get('defense_source_bindings'),'defense_code_SHA256':profile.get('defense_code_SHA256'),'feature_engine_code_SHA256':profile.get('feature_engine_code_SHA256'),'information_policy':'CURRENT_REVISED_KICKOFF_PLUS7D_STRICT_RECONSTRUCTION;ACTUAL_QUERY_CUTOFF_CAPPED','own_lookback':8,'defense_lookback':8}
 return {'profile_contract_id':ADAPTER_VERSION,'source_contract_SHA256':digest(bound)}

def _load_bytes(raw):
 if not isinstance(raw,bytes) or len(raw)>8388608:raise ValueError('C03_MODEL_BYTES_LIMIT')
 if raw.startswith(b'\xfd7zXZ\x00'):
  decoder=lzma.LZMADecompressor(memlimit=268435456);data=decoder.decompress(raw,max_length=67108865)
  if not decoder.eof:raise ValueError('C03_DECODED_MODEL_LIMIT_OR_TRUNCATION')
 elif raw.startswith(b'\x1f\x8b'):
  with gzip.GzipFile(fileobj=io.BytesIO(raw)) as handle:data=handle.read(67108865)
 else:data=raw
 if len(data)>67108864:raise ValueError('C03_DECODED_MODEL_LIMIT')
 return json.loads(data)

def validate_asof_query(profile,binding,model_bytes):
 """Historical/as-of validation only. It does not permit current issuance."""
 if profile.get('schema')!=ADAPTER_VERSION or profile.get('recipe_id')!=VERSION:raise ValueError('C03_QUERY_SCHEMA')
 base=profile['base_profile'];key=base['key'];adapter=base['forecast_adapter'];arm=binding.get('arm')
 if key['position'] not in ['RB','WR','TE'] or not adapter.get('allowed_receiving_role'):raise ValueError('C03_UNSUPPORTED_ROLE')
 if arm not in ORDERS or arm not in profile['arms']:raise ValueError('C03_UNSUPPORTED_ARM')
 if binding.get('selection_product') not in ['LAW','MEAN','MEDIAN']:raise ValueError('C03_UNREGISTERED_SELECTION_PRODUCT')
 if adapter.get('state')!='READY_PROXY_INPUTS_NOT_MODEL_ADMISSION' or not adapter.get('roster_status_version_qualified'):raise ValueError('C03_QUERY_ROSTER_OR_STATUS_UNQUALIFIED')
 if base.get('roster_status')!='ACT':raise ValueError('C03_ROSTER_NOT_ACTIVE')
 season,week=int(key['game_id'].split('_')[0]),int(key['game_id'].split('_')[1])
 if base.get('roster_source_season')!=season or base.get('roster_source_week')!=week or base.get('roster_version_admission')!='MATCHED_EVENT_SEASON_WEEK':raise ValueError('C03_ROSTER_EVENT_VERSION_MISMATCH')
 for k,v in query_contract(profile).items():
  if binding.get(k)!=v:raise ValueError('C03_SOURCE_CONTRACT_MISMATCH')
 f=profile['arms'][arm]
 if f['feature_order']!=ORDERS[arm] or binding.get('feature_order')!=ORDERS[arm]:raise ValueError('C03_FEATURE_ORDER_MISMATCH')
 x=f['features']
 if len(x)!=len(ORDERS[arm]) or any(v is not None and not finite(v) for v in x):raise ValueError('C03_FEATURE_NONFINITE_OR_DIMENSION')
 cut=instant(key['information_cutoff_UTC']);kick=instant(base['kickoff_UTC']);fit=instant(binding.get('fit_cutoff_UTC'));latest=instant(binding.get('latest_training_available_UTC'))
 if not latest<fit<=cut<kick:raise ValueError('C03_FIT_QUERY_CLOCK_INVALID')
 evidence=binding.get('roster_admission',{})
 required={'admission':'QUALIFIED_FOR_EVENT_VERSION','player_id':key['player_id'],'game_id':key['game_id'],'team':key['team'],'season':season,'week':week,'status':'ACT'}
 if any(evidence.get(k)!=v for k,v in required.items()) or not re.fullmatch('[0-9a-f]{64}',str(evidence.get('source_SHA256',''))):raise ValueError('C03_ROSTER_ADMISSION_RECEIPT_REQUIRED')
 if not instant(evidence.get('source_effective_UTC'))<=instant(evidence.get('observed_UTC'))<=cut:raise ValueError('C03_ROSTER_EFFECTIVE_CLOCK_UNQUALIFIED')
 origin=f'{season}-W{week:02}'
 if binding.get('recipe_id')!=VERSION or binding.get('model_origin')!=origin:raise ValueError('C03_MODEL_ORIGIN_MISMATCH')
 if binding.get('target_game_exclusion_verified') is not True or key['game_id'] in binding.get('training_game_ids',[]):raise ValueError('C03_TARGET_EXCLUSION_UNVERIFIED')
 if not isinstance(model_bytes,bytes) or len(model_bytes)>8388608:raise ValueError('C03_MODEL_BYTES_LIMIT')
 if hashlib.sha256(model_bytes).hexdigest()!=binding.get('model_SHA256'):raise ValueError('C03_MODEL_SHA_MISMATCH')
 payload=_load_bytes(model_bytes)
 if not isinstance(payload,dict):raise ValueError('C03_SAFE_MODEL_ENVELOPE_REQUIRED')
 if payload.get('id')!=VERSION or payload.get('arm')!=arm or payload.get('origin')!=origin or payload.get('feature_order')!=ORDERS[arm]:raise ValueError('C03_MODEL_RECIPE_OR_ORDER_MISMATCH')
 for p,b in [('code_SHA256','feature_engine_code_SHA256'),('defense_code_SHA256','defense_code_SHA256')]:
  if payload.get(p)!=profile.get(b) or binding.get(p)!=payload.get(p):raise ValueError('C03_EXECUTING_CODE_MISMATCH')
 if not re.fullmatch('[0-9a-f]{64}',str(binding.get('registration_SHA256',''))) or binding['registration_SHA256']!=payload.get('registration_SHA256'):raise ValueError('C03_REGISTRATION_UNBOUND')
 model=payload.get('model',{})
 if model.get('schema')!='C-NUMERIC-LEAF-v4' or model.get('kind')!='count' or model.get('scale')!=1 or len(model.get('imputation',[]))!=len(x):raise ValueError('C03_SAFE_LEAF_MODEL_REQUIRED')
 if not all(finite(v) for v in model['imputation']):raise ValueError('C03_IMPUTATION_NONFINITE')
 if model.get('global_prior',{}).get('kind')!='count' or any(p.get('kind')!='count' for p in model.get('prior',{}).values()) or any(any(v<0 for v in leaf[0]) for tree in model.get('trees',[]) for leaf in tree.get('leaves',{}).values()):raise ValueError('C03_COUNT_SUPPORT_INVALID')
 return model,np.array([[np.nan if v is None else v for v in x]],float),key['position']

def _live_boundary(profile,current_event,at):
 base=profile['base_profile'];key=base['key'];e=current_event
 if base.get('historical_roster_clock','').startswith('RECONSTRUCTED'):raise ValueError('C03_HISTORICAL_PROFILE_NOT_LIVE')
 if not e:raise ValueError('C03_FRESH_NATIVE_EVENT_REQUIRED')
 if str(e.get('espn_event_id'))!=str(base['native_event_id']) or e.get('game_id')!=key['game_id'] or {team(e.get('home_team')),team(e.get('away_team'))}!={key['team'],key['opponent_team']} or instant(e.get('kickoff_UTC'))!=instant(base['kickoff_UTC']):raise ValueError('C03_LIVE_EVENT_IDENTITY')
 if e.get('state')!='pre' or e.get('status_name')!='STATUS_SCHEDULED' or e.get('completed') is not False or instant(e['kickoff_UTC'])<=at:raise ValueError('C03_EVENT_STARTED_OR_UNSCHEDULED')
 if not 0<=at-instant(e.get('observed_UTC'))<=1800:raise ValueError('C03_EVENT_STATUS_EXPIRED')
 if instant(key['information_cutoff_UTC'])>at:raise ValueError('C03_PROFILE_AFTER_ADMISSION')

def _qualified_offer(offer,profile,line,at):
 """External rights/source/contract admission remains separately required."""
 if not offer or offer.get('qualified') is not True:return False
 b=profile['base_profile'];k=b['key']
 if not re.fullmatch('[0-9a-f]{64}',str(offer.get('admission_record_SHA256',''))):raise ValueError('C03_OFFER_ADMISSION_UNBOUND')
 if offer.get('player_id')!=k['player_id'] or offer.get('game_id')!=k['game_id'] or offer.get('category')!='rec' or offer.get('period')!='FULL_GAME_INCLUDING_OVERTIME' or offer.get('comparator_contract')!='OVER_GT_UNDER_LT_EQUAL_PUSH':raise ValueError('C03_OFFER_IDENTITY_OR_CONTRACT')
 if not finite(offer.get('line')) or float(offer['line'])!=line:raise ValueError('C03_OFFER_LINE_MISMATCH')
 if not offer.get('venue') or not offer.get('product') or offer.get('state')!='OPEN' or not offer.get('offered_sides') or any(s not in ['OVER','UNDER'] for s in offer['offered_sides']):raise ValueError('C03_OFFER_MARKET_STATE')
 observed=instant(offer.get('observed_UTC'));expiry=instant(offer.get('expiry_UTC'))
 if not 0<=at-observed<=1800 or not at<expiry<=instant(b['kickoff_UTC']):raise ValueError('C03_OFFER_STALE_OR_EXPIRED')
 return True

def infer_current_query(profile,binding,model_bytes,*,current_event,admission_UTC=None,line=None,offer=None):
 """Safe current inference; no persisted capture or production claim is made."""
 at=instant(admission_UTC or datetime.now(timezone.utc));_live_boundary(profile,current_event,at)
 model,x,role=validate_asof_query(profile,binding,model_bytes);law=infer_forest(model,x,[role])[0]
 out={'schema':ADAPTER_VERSION,'actual_admission_UTC':utc(at),'recipe_id':VERSION,'arm':binding['arm'],'model_SHA256':binding['model_SHA256'],'model_origin':binding['model_origin'],'profile_id':profile['base_profile']['profile_id'],'information_cutoff_UTC':profile['base_profile']['key']['information_cutoff_UTC'],'native_event_id':profile['base_profile']['native_event_id'],'player_id':profile['base_profile']['key']['player_id'],'game_id':profile['base_profile']['key']['game_id'],'expected_mean':law.mean(),'lower_median':law.quantile(.5),'mean_type':'EXPECTED_MEAN','median_type':'LOWER_MEDIAN','conditioning':'PARTICIPATION_CONDITIONED;roster does not establish appearance or starter','probability_status':'EXPERIMENTAL_NOT_CALIBRATION_OR_PRIMARY_ADMISSION','qualified_offer':False,'selected_side':None,'forecast_only':True,'primary_or_consumer_admission':False}
 out.update(input_missing_count=int((~np.isfinite(x)).sum()),profile_state=profile['base_profile']['state'],hard_model_fallback=False,prior_mixture_mass=law.a,prior_scope='ROLE_PRIOR' if role in model['prior'] else 'GLOBAL_PRIOR',fallback_policy='No silent incumbent substitution; invalid source/model fails closed')
 if line is None and offer is not None:line=offer.get('line')
 if line is not None:
  if not finite(line):raise ValueError('C03_FINITE_EXACT_LINE_REQUIRED')
  line=float(line);p=law.probability(line)
  if any(not finite(v) or v<0 or v>1 for v in p.values()) or abs(sum(p.values())-1)>1e-10:raise ValueError('C03_PROBABILITY_INCOHERENT')
  side='OVER' if p['over']>p['under'] else 'UNDER' if p['under']>p['over'] else 'ABSTAIN'
  qualified=_qualified_offer(offer,profile,line,at)
  out.update(exact_line=line,probabilities_at_exact_line=p,threshold_evidence='EXTERNALLY_QUALIFIED_OFFER' if qualified else 'UNQUALIFIED_OR_HYPOTHETICAL_CALLER_THRESHOLD',diagnostic_probability_direction=side,qualified_offer=qualified,forecast_only=not qualified)
  if offer is not None:out['offer_binding']={k:offer.get(k) for k in ['admission_record_SHA256','venue','product','tier','source','source_snapshot_SHA256','observed_UTC','source_updated_UTC','expiry_UTC','offered_sides','state']}
  product=binding['selection_product']
  if product not in ['LAW','MEAN','MEDIAN']:raise ValueError('C03_UNREGISTERED_SELECTION_PRODUCT')
  point=out['expected_mean'] if product=='MEAN' else out['lower_median'] if product=='MEDIAN' else None
  selected=side if point is None else 'OVER' if point>line else 'UNDER' if point<line else 'ABSTAIN'
  out['selection_product']=product
  if qualified:out['selected_side']=selected if selected in offer['offered_sides'] else None;out['selection_state']='SELECTED_EXPERIMENTAL' if out['selected_side'] else 'ABSTAIN_UNOFFERED_SIDE_OR_TIE'
 return out
