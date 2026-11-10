"""Roster-driven as-of receiving profiles; no target-game stat row is required.

The legacy v1.1 feature recipe is preserved. Human-readable raw profiles expose
known-zero volume ratios rather than reproducing its deliberate coarsening.
Neither profiles nor an input adapter establish predictive or release quality.
"""
from __future__ import annotations
import argparse,copy,gzip,hashlib,json,math,re
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
import pandas as pd
from context_features_c01 import Context,OWN_NAMES,OPP_NAMES,INTER_NAMES,summed
from data_v2 import DAY,History,load,vector
from forward_sources_v4 import team

VERSION='C-ASOF-RECEIVING-PROFILE-v1'
ROLES={'QB','RB','WR','TE'}
BASE_NAMES=['rec_mean_last3','rec_known_last3','rec_mean_last8','rec_known_last8']+[f'rec_lag{i}_{s}' for i in range(1,5) for s in ['value','age_days','missing']]+['role_QB','role_RB','role_WR','role_TE']+[f'player_{s}_{k}' for s in ['attempts','carries','targets'] for k in ['mean_last3','rows_last3','last']]+['team_attempts_mean3','team_carries_mean3','team_sacks_mean3']
assert len(BASE_NAMES)==32

def instant(x):
 v=pd.Timestamp(x)
 if v.tzinfo is None:raise ValueError('TIMEZONE_REQUIRED')
 return float(v.timestamp())
def utc(t):return datetime.fromtimestamp(float(t),timezone.utc).isoformat()
def safe(x):
 if isinstance(x,dict):return {str(k):safe(v) for k,v in x.items()}
 if isinstance(x,(list,tuple,np.ndarray)):return [safe(v) for v in x]
 if isinstance(x,(np.integer,)):return int(x)
 if isinstance(x,(np.bool_,)):return bool(x)
 if isinstance(x,(float,np.floating)):return float(x) if math.isfinite(x) else None
 return x

def query_universe(roster,events,cutoff,*,historical=False):
 """Construct every offensive roster query, independently of actuals/appearance."""
 cut=instant(cutoff);by_team={};queries=[];excluded=[];seen=set()
 for event in events:
  kick=instant(event['kickoff_UTC']);eid=str(event.get('espn_event_id',event.get('event_id','')))
  if not event.get('game_id') or not eid:raise ValueError('NATIVE_EVENT_REQUIRED')
  if not historical and (kick<=cut or event.get('state')!='pre' or event.get('completed') is not False or event.get('status_name')!='STATUS_SCHEDULED'):
   excluded.append({'game_id':event['game_id'],'reason':'NOT_VERIFIED_UNPLAYED_AT_CUTOFF'});continue
  for t in [team(event['home_team']),team(event['away_team'])]:
   if t in by_team:raise ValueError('AMBIGUOUS_TEAM_EVENT_VERSION')
   by_team[t]=(event,kick,eid)
 for record in roster:
  role=record.get('position');pid=record.get('gsis_id',record.get('player_id'));t=team(record.get('team'))
  if role not in ROLES:continue
  if t not in by_team:excluded.append({'player_id':pid,'team':t,'reason':'OUTSIDE_DECLARED_EVENT_UNIVERSE'});continue
  if not isinstance(pid,str) or not re.fullmatch(r'00-\d{7}',pid):excluded.append({'player_id':None,'team':t,'position':role,'reason':'MISSING_OR_INVALID_NATIVE_PLAYER'});continue
  e,kick,eid=by_team[t];key=(e['game_id'],pid)
  if key in seen:raise ValueError('DUPLICATE_PLAYER_EVENT')
  seen.add(key)
  q=dict(game_id=e['game_id'],espn_event_id=eid,player_id=pid,name=record.get('full_name',record.get('name',pid)),team=t,opponent_team=team(e['away_team'] if t==team(e['home_team']) else e['home_team']),position=role,home_team=team(e['home_team']),season=int(e['season']),week=int(e['week']),kickoff=kick,kickoff_UTC=utc(kick),information_cutoff_UTC=utc(cut),roster_status=record.get('status'),roster_source_week=record.get('week'),roster_source_season=record.get('season'),historical_roster_clock='RECONSTRUCTED_NOT_AUTHENTICATED' if historical else 'ACTUAL_OBSERVED_SOURCE_CLOCK_REQUIRED',appearance='UNKNOWN_NOT_REQUIRED_FOR_QUERY')
  source_week_matches=(record.get('season')==int(e['season']) and record.get('week')==int(e['week']))
  q['roster_version_admission']='MATCHED_EVENT_SEASON_WEEK' if source_week_matches else 'MISSING_OR_STALE_ROSTER_VERSION'
  if historical:q['status_clock_admission']='HISTORICAL_RECONSTRUCTION_NOT_AUTHENTICATED'
  else:
   try:age=cut-instant(e['observed_UTC'])
   except (KeyError,ValueError,TypeError):age=None
   q['status_clock_admission']='FRESH_NATIVE_STATUS' if age is not None and 0<=age<=1800 else 'UNKNOWN_OR_STALE_NATIVE_STATUS_CLOCK'
  queries.append(q)
 return sorted(queries,key=lambda q:(q['kickoff'],q['game_id'],q['player_id'])),excluded

class Capped:
 def __init__(self,base,cutoff):self.base=base;self.cutoff=cutoff
 def before(self,key,requested,n=8):
  cut=min(float(requested),self.cutoff);rows=self.base.before(key,cut,n)
  if any(not isinstance(r.get('available'),(int,float,np.floating)) or not math.isfinite(r['available']) or r['available']>=cut for r in rows):raise ValueError('UNKNOWN_OR_INELIGIBLE_HISTORICAL_CLOCK')
  return rows

def _rate(n,d,definition,*,observed=True,kind='BINOMIAL',support_games=0):
 if not observed:state='ABSENT_HISTORY';n=d=value=None
 elif d is None or d<=0:state='UNDEFINED_DENOMINATOR';value=None
 else:value=n/d;state='KNOWN_ZERO' if n==0 else 'OBSERVED'
 interval=None
 if value is not None and kind=='BINOMIAL' and 0<=n<=d:
  z=1.959963984540054;den=1+z*z/d;center=(value+z*z/(2*d))/den;half=z*math.sqrt(value*(1-value)/d+z*z/(4*d*d))/den
  interval={'method':'WILSON_DESCRIPTIVE_ONLY_NOT_GAME_INDEPENDENCE_GUARANTEE','low':max(0.,center-half),'high':min(1.,center+half)}
 return {'definition':definition,'numerator':n,'denominator':d,'raw_estimate':value,'shrunk_estimate':None,'shrinkage':'NOT_APPLIED_TO_RAW_PROFILE','state':state,'eligible_games':support_games,'uncertainty':interval or {'method':'NOT_ESTIMATED','reason':'No independent-game uncertainty law established; support retained'}}

def source_blocked(reason):return {'state':'SOURCE_BLOCKED','reason':reason,'value':None}

class ProfileBuilder:
 def __init__(self,context,player_history,team_history,cutoff,source_bindings,*,pbp=None,lookback=8):
  self.cutoff=instant(cutoff);self.sources=source_bindings;self.pbp=pbp;self.lookback=int(lookback)
  if self.lookback not in [4,8,16]:raise ValueError('UNREGISTERED_PROFILE_WINDOW')
  self.context=copy.copy(context) if context is not None else None
  if self.context:
   for name in ['players','teams','defenses','league']:setattr(self.context,name,Capped(getattr(context,name),self.cutoff))
  self.hist=Capped(player_history,self.cutoff) if player_history is not None else None
  self.thist=Capped(team_history,self.cutoff) if team_history is not None else None
 def _rows(self,q):
  if not self.context:return [],[]
  attempted=self.context.players.before(q['player_id'],q['kickoff'],self.lookback)
  qualified=[r for r in attempted if r['team_complete'] and r['receptions_match'] and r['team']==q['team']]
  return qualified,attempted
 def _features(self,q):
  if self.context is None or self.hist is None or self.thist is None:return None
  base=vector(q,'rec',self.hist,self.thist,'E0_OP');own=self.context.own(q,self.lookback);_,op,_=self.context.features(q)
  rs=[r for r in self.context.defenses.before(q['opponent_team'],q['kickoff'],8) if r['passing_complete']]
  n=sum(r['targets'] for r in rs)
  if n and np.isfinite(own[12:17]).all():
   dr=summed(rs,'depth_residual')/(summed(rs,'depth_n')+40);ur=summed(rs,'down_residual')/(summed(rs,'down_n')+40);inter=[float(own[12:17]@dr),float(own[17:22]@ur)]
  else:inter=[np.nan,np.nan]
  own_names=[name[:-1]+str(self.lookback) if name.endswith('8') else name for name in OWN_NAMES]
  return safe({'recipe':'C-v1.1-fixed8' if self.lookback==8 else 'PROFILE_WINDOW_ONLY_REQUIRES_MATCHING_FIT','lookback':self.lookback,'base_order':BASE_NAMES,'base':base,'own_order':own_names,'own':own,'opponent_order':OPP_NAMES,'opponent':op,'interaction_order':INTER_NAMES,'interactions':inter,'E2_order':BASE_NAMES+own_names+OPP_NAMES,'E2':list(base)+list(own)+list(op),'E3_order':BASE_NAMES+own_names+OPP_NAMES+INTER_NAMES,'E3':list(base)+list(own)+list(op)+list(inter),'legacy_zero_coarsening_preserved':True})
 def _qb_pairs(self,q,rs):
  if self.pbp is None or 'passer_player_id' not in self.pbp:return source_blocked('Qualified passer-native target/attempt play rows not supplied')
  ids={r['game_id'] for r in rs}
  f=self.pbp[self.pbp.game_id.isin(ids)&(self.pbp.posteam==q['team'])&(self.pbp.pass_attempt==1)&(self.pbp.sack!=1)&(self.pbp.two_point_attempt!=1)&(self.pbp.play_deleted!=1)&(self.pbp.play_type!='no_play')].copy()
  targeted=f[f.receiver_player_id==q['player_id']];pairs=[];rolemap={}
  for pid in f.passer_player_id.dropna().unique():
   if self.hist:
    for row in self.hist.before(pid,q['kickoff'],100000):
     if row['game_id'] in ids:rolemap[(row['game_id'],pid)]=row.get('position','UNKNOWN')
  f['_passer_historical_role']=[rolemap.get((r.game_id,r.passer_player_id),'UNKNOWN') for r in f.itertuples()]
  for (pid,role),throws in f[f.passer_player_id.notna()].groupby(['passer_player_id','_passer_historical_role'],sort=True):
   selected=throws[throws.receiver_player_id==q['player_id']]
   pairs.append({'passer_player_id':pid,'historical_role':role,'role_qualification':'QB_VERIFIED_FOR_HISTORICAL_GAMES' if role=='QB' else 'NON_QB_PASSER' if role in ROLES else 'UNKNOWN_PASSER_ROLE','targets':len(selected),'passer_attempts_in_same_eligible_player_appearances':len(throws),'target_per_passer_attempt':_rate(len(selected),len(throws),'Player targets / official same-passer attempts in eligible player appearances; historical role qualified separately; not routes or alignment preference',support_games=len(rs)),'completions_on_targets':int((selected.complete_pass==1).sum())})
  return {'state':'OBSERVED_TARGETING_PROXY' if rs else 'ABSENT_HISTORY','pairs':pairs,'qualified_QB_pairs':[r for r in pairs if r['historical_role']=='QB'],'other_or_unknown_passer_pairs':[r for r in pairs if r['historical_role']!='QB'],'unknown_passer_target_count':int(targeted.passer_player_id.isna().sum()),'not_claimed':'Not target probability per route; no untargeted-route denominator. Passer does not automatically mean QB.'}
 def build(self,q):
  # Current query fields intentionally do not include values, played or actual.
  if q['kickoff']<=self.cutoff and q.get('historical_roster_clock')!='RECONSTRUCTED_NOT_AUTHENTICATED':raise ValueError('STARTED_CURRENT_QUERY')
  rs,attempted=self._rows(q);n=sum(r['targets'] for r in rs);a=sum(r['attempts'] for r in rs);g=len(rs);observed=bool(rs)
  f=self._features(q);games=[{'game_id':r['game_id'],'historical_team':r['team'],'kickoff_UTC':utc(r['kickoff']),'assumed_available_UTC':utc(r['available']),'targets':r['targets'],'official_team_attempts':r['attempts']} for r in rs]
  metrics={'targets_per_team_attempt':_rate(n,a,'Player targets / qualified official team passing attempts in eligible appearances',observed=observed,support_games=g),'targets_per_appearance':_rate(n,g,'Player targets / qualified same-team player appearances',observed=observed,kind='COUNT_MEAN',support_games=g),'catch_per_target':_rate(sum(r['completions'] for r in rs),n,'Official receptions / identified targets',observed=observed,support_games=g),'air_yards_per_known_target':_rate(sum(r['air_sum'] for r in rs),sum(r['air_n'] for r in rs),'Air yards over all targets with known air yards, including incomplete targets; not completed-air-only',observed=observed,kind='SIGNED_MEAN',support_games=g),'YAC_per_known_completion':_rate(sum(r['yac_sum'] for r in rs),sum(r['yac_n'] for r in rs),'YAC / completions with observed YAC',observed=observed,kind='SIGNED_MEAN',support_games=g),'redzone_target_share':_rate(sum(r['redzone'] for r in rs),n,'Targets at opponent20 or closer / all identified player targets',observed=observed,support_games=g),'short_to_go_target_share':_rate(sum(r['short'] for r in rs),n,'Targets at <=3yards to go / all identified player targets',observed=observed,support_games=g)}
  for group,names,key in [('depth',['behind_LOS','0_9','10_19','20plus','UNKNOWN'],'depth_n'),('down',['1','2','3','4','UNKNOWN'],'down_n')]:
   numer=summed(rs,key)
   for i,name in enumerate(names):metrics[group+'_share_'+name]=_rate(float(numer[i]),n,'Player '+group+'-bin targets / all identified player targets',observed=observed,support_games=g)
  if self.pbp is not None:
   selected=self.pbp[self.pbp.game_id.isin({r['game_id'] for r in rs})&(self.pbp.posteam==q['team'])&(self.pbp.receiver_player_id==q['player_id'])&(self.pbp.pass_attempt==1)&(self.pbp.sack!=1)&(self.pbp.two_point_attempt!=1)&(self.pbp.play_deleted!=1)&(self.pbp.play_type!='no_play')]
   completed=selected[selected.complete_pass==1]
   if 'receiving_yards' in selected and selected.complete_pass.isin([0,1]).all() and completed.receiving_yards.notna().all():metrics['receiving_yards_per_target']=_rate(float(completed.receiving_yards.sum()),len(selected),'Signed credited receiving yards on explicit completions / identified targets; explicit incompletions credit no reception yards',observed=observed,kind='SIGNED_MEAN',support_games=g)
   else:metrics['receiving_yards_per_target']={'state':'SOURCE_FIELD_UNQUALIFIED','reason':'Complete credited receiving-yard fields/explicitcompletion flags unavailable','raw_estimate':None}
   metrics['completed_air_yards_per_known_completion']=_rate(float(completed.air_yards.sum()),int(completed.air_yards.notna().sum()),'Air yards / completions with known air yards; incomplete targets excluded',observed=observed,kind='SIGNED_MEAN',support_games=g)
  else:
   metrics['receiving_yards_per_target']={'state':'SOURCE_NOT_PROVIDED','raw_estimate':None}
   metrics['completed_air_yards_per_known_completion']={'state':'SOURCE_NOT_PROVIDED','raw_estimate':None}
  for metric in metrics.values():metric.update(source_group='QUALIFIED_PBP_AND_ORDINARY_FACTS',lookback_player_appearances=self.lookback,latest_consumed_context_game_UTC=games[-1]['kickoff_UTC'] if games else None)
  own_games={r['game_id'] for r in rs};teamrows=[]
  if self.context:
   teamrows=[r for r in self.context.teams.before(q['team'],q['kickoff'],100000) if r['game_id'] in own_games]
  identified=sum(r['targets'] for r in teamrows)
  metrics['share_of_identified_team_targets']=_rate(n,identified,'Player targets / all identified team targets in eligible player appearances',observed=observed,support_games=g)
  opponents=[]
  if self.context:opponents=[r for r in self.context.defenses.before(q['opponent_team'],q['kickoff'],8) if r['passing_complete']]
  opponent={'state':'SHRUNK_CONTEXT_PROXY' if opponents else 'ABSENT_HISTORY','eligible_games':[r['game_id'] for r in opponents],'targets':sum(r['targets'] for r in opponents),'latest_game_UTC':utc(opponents[-1]['kickoff']) if opponents else None,'features':dict(zip(OPP_NAMES,f['opponent'])) if f else None,'interaction_features':dict(zip(INTER_NAMES,f['interactions'])) if f else None,'definition':'Eligible earlier offense-adjusted completion residual by depth/down; context-specific prior20, response shrink40; WRTE role prior40/response80. Not causal defense talent or inferred coverage.'}
  blocked={'alignment':source_blocked('No snap/route starting-alignment labels; pass destination is not alignment'),'routes':source_blocked('All relevant routes, including untargeted routes, unavailable'),'separation':source_blocked('No qualified contextual lagged-separation rows/denominators supplied'),'target_probability_per_route':source_blocked('Requires untargeted routes; targets/team attempts is separately named'),'explicit_endzone_target':source_blocked('No explicit end-zone target coordinate/flag qualified; red-zone target share is separate')}
  ordinary_player=self.hist.before(q['player_id'],q['kickoff'],8) if self.hist else []
  ordinary_team=self.thist.before(q['team'],q['kickoff'],3) if self.thist else []
  all_consumed=rs+opponents+ordinary_player+ordinary_team
  latest=max(all_consumed,key=lambda r:(r['kickoff'],r['game_id'])) if all_consumed else None
  consumed={'ordinary_player_games':[r['game_id'] for r in ordinary_player],'ordinary_team_games':[r['game_id'] for r in ordinary_team],'target_context_games':[r['game_id'] for r in rs],'opponent_context_games':[r['game_id'] for r in opponents],'actual_latest_game_id':latest['game_id'] if latest else None,'actual_latest_game_UTC':utc(latest['kickoff']) if latest else None,'actual_latest_assumed_available_UTC':utc(max(r['available'] for r in all_consumed)) if all_consumed else None,'all_available_strictly_before_cutoff':all(r['available']<self.cutoff for r in all_consumed)}
  key={k:q[k] for k in ['player_id','game_id','team','position','opponent_team','information_cutoff_UTC']};profile_id=hashlib.sha256(json.dumps([VERSION,key,self.lookback],sort_keys=True,separators=(',',':')).encode()).hexdigest()
  role=q['position'];allowed=role in ['RB','WR','TE'];status='SUPPORTED_PROXY' if g>=self.lookback else 'SPARSE_FALLBACK' if g else 'UNAVAILABLE_HISTORY'
  if role=='QB':status='UNAVAILABLE_C_QB_PROFILE_OWNER_B'
  current_qualified=q.get('roster_version_admission')=='MATCHED_EVENT_SEASON_WEEK' and q.get('status_clock_admission') in ['FRESH_NATIVE_STATUS','HISTORICAL_RECONSTRUCTION_NOT_AUTHENTICATED']
  if not current_qualified:status='UNQUALIFIED_ROSTER_OR_STATUS_VERSION'
  record={'schema':VERSION,'profile_id':profile_id,'key':key,'name':q['name'],'native_event_id':q['espn_event_id'],'kickoff_UTC':q['kickoff_UTC'],'roster_status':q['roster_status'],'roster_version_admission':q.get('roster_version_admission'),'status_clock_admission':q.get('status_clock_admission'),'roster_source_season':q['roster_source_season'],'roster_source_week':q['roster_source_week'],'query_universe':'EXPLICIT_ROSTER_EVENT_ONLY;NO_TARGET_STAT_APPEARANCE_FILTER','appearance_conditioning':'Unknown; roster status does not confirm starter/participation','state':status,'source_tier':'CURRENT_VINTAGE_SEVEN_DAY_RECONSTRUCTION','historical_roster_clock':q['historical_roster_clock'],'source_bindings':self.sources,'lookback':{'player':self.lookback,'opponent':8,'team_ordinary_feature_games':3,'selection':'Eligible availability first, then last window by game time; legacy context then filters same-team/source qualification; excludes not silently backfilled'},'history':{'eligible_player_games':g,'targets':n if observed else None,'official_team_attempts':a if observed else None,'latest_consumed_game_UTC':games[-1]['kickoff_UTC'] if games else None,'latest_assumed_available_UTC':games[-1]['assumed_available_UTC'] if games else None,'actual_context_age_at_cutoff_days':(self.cutoff-rs[-1]['kickoff'])/DAY if rs else None,'games':games,'attempted_window_games':len(attempted),'excluded_from_window':len(attempted)-g},'receiving':{'state':'SUPPORTED_PROXY' if allowed else 'NOT_APPLICABLE_C_QB_ROLE','metrics':metrics if allowed else None,'target_allocation_buckets':{'player':n,'other_identified_receivers':identified-n,'no_identified_receiver_attempts':a-identified,'denominator_official_team_attempts':a} if observed else None,'QB_pair_targeting':self._qb_pairs(q,rs) if allowed else {'state':'NOT_APPLICABLE_C_QB_ROLE'},'opponent_response':opponent,'missing_source_groups':blocked},'rushing':{'state':'NOT_IMPLEMENTED_OWNER_A'},'quarterback':{'state':'NOT_IMPLEMENTED_OWNER_B'},'forecast_adapter':{'state':'READY_PROXY_INPUTS_NOT_MODEL_ADMISSION' if allowed and f and current_qualified else 'UNAVAILABLE_C_RECEIVING_INPUTS','allowed_receiving_role':allowed,'roster_status_version_qualified':current_qualified,'features':f if allowed else None,'consumed_history':consumed,'actual_required':False,'fallback':'Declared model/role prior fallback required for sparse/unseen players; no new model is fitted','legacy_zero_coarsening':'Raw profile volume ratios can be knownzero; legacy fitted input retains NaN there. No old features/predictions rewritten.'}}
  return safe(record)
 def build_all(self,queries):return [self.build(q) for q in queries]

def source_contract(profile):
 """Bind model metadata to this new source/version contract, not array width."""
 payload={'profile_contract_id':VERSION+'/receiving-E2-window'+str(profile['lookback']['player']),'source_bindings':profile['source_bindings'],'policy':'STRICT_7D_CURRENT_VINTAGE'}
 return dict(profile_contract_id=payload['profile_contract_id'],source_contract_SHA256=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest())

def validate_asof_model_input(profile,binding,model_bytes):
 """Validate a safe new Poisson artifact and ordered inputs before inference.

 Validation alone never admits a live forecast. No legacy fit inherits admission
 from having matching dimensions. This method
 refuses the current preliminary-roster profiles before any model is loaded.
 """
 adapter=profile['forecast_adapter'];features=adapter.get('features')
 if adapter['state']!='READY_PROXY_INPUTS_NOT_MODEL_ADMISSION' or not adapter.get('roster_status_version_qualified'):raise ValueError('PROFILE_NOT_CURRENT_QUERY_QUALIFIED')
 if not adapter['allowed_receiving_role'] or features is None:raise ValueError('UNSUPPORTED_RECEIVING_ROLE')
 if profile.get('roster_status')!='ACT':raise ValueError('ROSTER_NOT_ACTIVE_FOR_CURRENT_ADMISSION')
 expected=source_contract(profile)
 for key,value in expected.items():
  if binding.get(key)!=value:raise ValueError('MODEL_PROFILE_SOURCE_CONTRACT_MISMATCH')
 if binding.get('feature_order')!=features['E2_order'] or binding.get('lookback')!=profile['lookback']['player']:raise ValueError('MODEL_FEATURE_ORDER_OR_LOOKBACK_MISMATCH')
 fit=instant(binding['fit_cutoff_UTC']);cut=min(instant(profile['key']['information_cutoff_UTC']),instant(profile['kickoff_UTC']))
 if fit>cut or instant(binding['latest_training_available_UTC'])>=fit:raise ValueError('MODEL_TRAINING_CLOCK_INVALID')
 if profile['key']['game_id'] in binding.get('training_game_ids',[]):raise ValueError('TARGET_GAME_IN_MODEL_TRAINING')
 if binding.get('target_game_exclusion_verified') is not True:raise ValueError('MODEL_TARGET_EXCLUSION_UNVERIFIED')
 if len(model_bytes)>262144 or hashlib.sha256(model_bytes).hexdigest()!=binding.get('model_SHA256'):raise ValueError('MODEL_BYTES_NOT_BOUND')
 payload=json.loads(gzip.decompress(model_bytes) if model_bytes.startswith(b'\x1f\x8b') else model_bytes);model=payload.get('model',payload)
 if model.get('type')!='L2_POOLED_POISSON':raise ValueError('UNSUPPORTED_SAFE_MODEL_TYPE')
 if len(model.get('impute',[]))!=len(features['E2']):raise ValueError('MODEL_INPUT_DIMENSION_MISMATCH')
 x=np.asarray([[np.nan if v is None else v for v in features['E2']]],float)
 return model,x,np.asarray([[profile['key']['player_id'],profile['key']['team'],profile['key']['opponent_team']]])

def bound_model_input(profile,binding,model_bytes,*,current_event=None,admission_UTC=None):
 """Live boundary; execution clock defaults to UTC now, never the old as-of."""
 if profile.get('historical_roster_clock','').startswith('RECONSTRUCTED'):raise ValueError('HISTORICAL_PROFILE_NOT_LIVE')
 at=instant(admission_UTC or datetime.now(timezone.utc));e=current_event
 if not e:raise ValueError('FRESH_NATIVE_EVENT_REQUIRED')
 if str(e.get('espn_event_id'))!=str(profile['native_event_id']) or e.get('game_id')!=profile['key']['game_id'] or {team(e.get('home_team')),team(e.get('away_team'))}!={profile['key']['team'],profile['key']['opponent_team']} or instant(e['kickoff_UTC'])!=instant(profile['kickoff_UTC']):raise ValueError('LIVE_EVENT_IDENTITY_MISMATCH')
 if e.get('state')!='pre' or e.get('status_name')!='STATUS_SCHEDULED' or e.get('completed') is not False or instant(e['kickoff_UTC'])<=at:raise ValueError('LIVE_EVENT_STARTED_OR_NOT_SCHEDULED')
 if not 0<=at-instant(e.get('observed_UTC'))<=1800:raise ValueError('LIVE_EVENT_STATUS_EXPIRED')
 if instant(profile['key']['information_cutoff_UTC'])>at:raise ValueError('PROFILE_CUTOFF_AFTER_ADMISSION')
 return validate_asof_model_input(profile,binding,model_bytes)

def infer_bound_model(profile,binding,model_bytes,line=None,*,current_event=None,admission_UTC=None):
 from context_experiment_c01 import pooled_mu,count_probs
 from scipy.stats import poisson
 admission_UTC=admission_UTC or utc(datetime.now(timezone.utc).timestamp())
 model,x,ids=bound_model_input(profile,binding,model_bytes,current_event=current_event,admission_UTC=admission_UTC);mu=float(pooled_mu(model,x,ids)[0])
 result={'actual_admission_UTC':admission_UTC,'mean':mu,'median':float(poisson.ppf(.5,mu)),'conditioning':'Participation-conditioned count law; roster does not establish appearance','model_SHA256':binding['model_SHA256'],'profile_id':profile['profile_id'],'probability_status':'EXPERIMENTAL_NOT_CALIBRATION_OR_PRIMARY_ADMISSION','qualified_offer':False}
 if line is not None:result['hypothetical_or_caller_qualified_exact_line']=float(line);result['probabilities_at_exact_line']=count_probs(mu,float(line))
 return result

def load_historical_builder(inputs,cutoff,source_bindings,*,lookback=8,pbp_files=None):
 """Reuse qualified ordinary facts with W8 append; never create target-game rows."""
 root=Path(__file__).resolve().parents[1];d,g,t=load(Path(inputs));later=root/'prospective/runs/C-FWD-v4-20261105-W09-JAXBAL-remainder/sources';dd,gg,tt=load(later)
 extra=dd[(dd.season==2026)&(dd.week==8)&~dd.game_id.isin(d.game_id)].copy();d=pd.concat([d,extra],ignore_index=True)
 extra_ids=set(extra.game_id);t=pd.concat([t,tt[tt.game_id.isin(extra_ids)]],ignore_index=True)
 g=pd.concat([g[~g.game_id.isin(extra_ids)],gg[gg.game_id.isin(extra_ids)]],ignore_index=True)
 cols=['game_id','team','season','week','attempts','completions','targets'];raw=pd.read_csv(Path(inputs)/'facts.csv.gz',usecols=cols);new=pd.read_csv(later/'facts.csv.gz',usecols=cols);raw=pd.concat([raw,new[new.game_id.isin(extra_ids)]],ignore_index=True);counts={}
 for key,f in raw.groupby(['game_id','team'],sort=False):
  v=f[['attempts','completions','targets']].to_numpy(float);counts[key]=dict(zip(['attempts','completions','targets'],v.sum(axis=0)));counts[key]['complete']=bool(np.isfinite(v).all() and (v>=0).all() and np.equal(v,np.floor(v)).all())
 if pbp_files is None:
  from context_sources_c01 import pbp_path
  pbp_files=[pbp_path(y) for y in [2025,2026]]
 frames=[pd.read_csv(p,low_memory=False) for p in pbp_files];context=Context(frames,d,g,strict=True,all_position_counts=counts)
 bound=copy.deepcopy(source_bindings)
 bound['context_files']=[{'path':str(p),'SHA256':hashlib.sha256(Path(p).read_bytes()).hexdigest()} for p in pbp_files]
 bound['ordinary_history_files']=[{'path':str(p),'SHA256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in [Path(inputs)/'facts.csv.gz',Path(inputs)/'schedule.csv',later/'facts.csv.gz',later/'SOURCE_MANIFEST.json']]
 return ProfileBuilder(context,History(d,'player_id'),History(t,'team'),cutoff,bound,pbp=pd.concat(frames,ignore_index=True),lookback=lookback)

def load_current_builder(snapshot,cutoff,*,lookback=8,pbp_files=None):
 """Current-vintage historical facts are combined in memory, never target queries.

 data_v2.load remains the ordinary-feature constructor. The CSV-like adapter
 avoids a duplicate on-disk source archive and does not fill missing statistics.
 """
 import io,zipfile
 from forward_sources_v4 import quarantine_stat_orphans
 snapshot=Path(snapshot);root=Path(__file__).resolve().parents[1];archive=root/'artifacts/basic-football-facts-v2.1.zip'
 with zipfile.ZipFile(archive) as z:
  old=pd.read_csv(io.BytesIO(z.read('facts.csv.gz')),compression='gzip',low_memory=False);oldg=pd.read_csv(io.BytesIO(z.read('schedule.csv')))
 current=pd.read_csv(snapshot/'current_facts_2026.csv.gz',low_memory=False);current,rejected=quarantine_stat_orphans(current)
 current=current[(current.season==2026)&(current.season_type=='REG')].copy()
 raw=pd.concat([old[(old.season>=2022)&(old.season<=2025)&(old.season_type=='REG')],current],ignore_index=True)
 for name in ['team','opponent_team']:raw[name]=raw[name].map(team)
 currentg=pd.read_csv(snapshot/'schedule.csv');currentg=currentg[(currentg.season==2026)&(currentg.game_type=='REG')].copy()
 combinedg=pd.concat([oldg[oldg.season<2026],currentg],ignore_index=True)
 for name in ['home_team','away_team']:combinedg[name]=combinedg[name].map(team)
 assert not combinedg.game_id.duplicated().any() and not raw.duplicated(['game_id','player_id']).any()
 class MemoryInputs:
  def __truediv__(self,name):
   if name=='facts.csv.gz':return io.StringIO(raw.to_csv(index=False))
   if name=='schedule.csv':return io.StringIO(combinedg.to_csv(index=False))
   raise ValueError('UNEXPECTED_MEMORY_SOURCE')
 d,g,t=load(MemoryInputs());counts={}
 for key,f in raw.groupby(['game_id','team'],sort=False):
  x=f[['attempts','completions','targets']].to_numpy(float);counts[key]=dict(zip(['attempts','completions','targets'],x.sum(axis=0)));counts[key]['complete']=bool(np.isfinite(x).all() and (x>=0).all() and np.equal(x,np.floor(x)).all())
 if pbp_files is None:pbp_files=[root/'sources/player-context-matchup-01/completion-decision-v1/pbp_facts_2024.csv.xz',root/'sources/player-context-matchup-01/pbp_facts_2025.csv.xz',snapshot/'pbp_context_2026.csv.xz']
 frames=[pd.read_csv(p,low_memory=False) for p in pbp_files];context=Context(frames,d,g,strict=True,all_position_counts=counts)
 manifest=snapshot/'SOURCE_MANIFEST.json';source=json.loads(manifest.read_text());bound={'current_snapshot_path':str(snapshot),'current_snapshot_manifest_SHA256':hashlib.sha256(manifest.read_bytes()).hexdigest(),'actual_source_observed_UTC':source.get('source_observed'),'current_information_cutoff_UTC':source.get('information_cutoff_UTC'),'historical_source_tier':'Current/revised versions with strict kickoff+7day reconstruction, not authenticated historic publication','ordinary_baseline_archive':{'path':str(archive.relative_to(root)),'SHA256':hashlib.sha256(archive.read_bytes()).hexdigest()},'current_facts':{'path':str(snapshot/'current_facts_2026.csv.gz'),'SHA256':hashlib.sha256((snapshot/'current_facts_2026.csv.gz').read_bytes()).hexdigest()},'context_files':[{'path':str(p),'SHA256':hashlib.sha256(Path(p).read_bytes()).hexdigest()} for p in pbp_files],'quarantined_explicit_zero_native_orphans':rejected,'old_scientific_artifacts_changed':0}
 return ProfileBuilder(context,History(d,'player_id'),History(t,'team'),cutoff,bound,pbp=pd.concat(frames,ignore_index=True),lookback=lookback)

def deterministic_examples(profiles):
 examples={}
 for label,predicate in [('ordinary',lambda p:p['key']['position'] in ['WR','TE'] and p['history']['eligible_player_games']>=8),('sparse',lambda p:p['key']['position'] in ['WR','TE'] and 0<p['history']['eligible_player_games']<8),('unseen_or_no_history',lambda p:p['key']['position'] in ['WR','TE'] and p['history']['eligible_player_games']==0),('known_zero',lambda p:p['key']['position'] in ['WR','TE'] and (p['receiving'].get('metrics') or {}).get('targets_per_team_attempt',{}).get('state')=='KNOWN_ZERO'),('missing_source',lambda p:p['key']['position'] in ['WR','TE'])]:
  found=next((p for p in sorted(profiles,key=lambda p:p['profile_id']) if predicate(p)),None);examples[label]={'profile_id':found['profile_id'],'player_id':found['key']['player_id'],'name':found['name'],'state':found['state']} if found else {'state':'NO_REAL_CASE_IN_DECLARED_UNIVERSE;software_fixture_separate'}
 return examples

def write_profiles(queries,profiles,output,excluded,*,source_manifest=None):
 output=Path(output);output.mkdir(parents=True,exist_ok=False)
 b=gzip.compress((json.dumps(safe(profiles),separators=(',',':'),allow_nan=False)+'\n').encode(),mtime=0);(output/'PROFILES.json.gz').write_bytes(b)
 index={'schema':VERSION,'profile_rows':len(profiles),'query_rows':len(queries),'role_counts':dict(Counter(q['position'] for q in queries)),'states':dict(Counter(p['state'] for p in profiles)),'source_manifest':source_manifest,'profiles':{'path':'PROFILES.json.gz','bytes':len(b),'SHA256':hashlib.sha256(b).hexdigest()},'records':[dict(profile_id=p['profile_id'],**p['key'],state=p['state']) for p in profiles],'excluded':excluded,'actuals_required':False,'models_fitted':0,'qualified_offers':0,'primary_admission':False,'examples':deterministic_examples(profiles)}
 (output/'INDEX.json').write_text(json.dumps(index,indent=2)+'\n');return index

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--snapshot',type=Path,required=True);p.add_argument('--history',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--cutoff',required=True);p.add_argument('--historical',action='store_true');p.add_argument('--lookback',type=int,choices=[4,8,16],default=8);a=p.parse_args()
 events=json.loads((a.snapshot/'events.json').read_text());roster=json.loads((a.snapshot/'roster.json').read_text());m=a.snapshot/'SOURCE_MANIFEST.json';sources={'snapshot_path':str(a.snapshot),'snapshot_manifest_SHA256':hashlib.sha256(m.read_bytes()).hexdigest()}
 queries,excluded=query_universe(roster,events,a.cutoff,historical=a.historical);builder=load_historical_builder(a.history,a.cutoff,sources,lookback=a.lookback) if a.history else load_current_builder(a.snapshot,a.cutoff,lookback=a.lookback);profiles=builder.build_all(queries);index=write_profiles(queries,profiles,a.output,excluded,source_manifest=sources);print(json.dumps({k:index[k] for k in ['profile_rows','role_counts','states','qualified_offers']}))
