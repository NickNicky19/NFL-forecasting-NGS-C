"""Bounded independent stdlib verification of received operational metadata only."""
from pathlib import Path
from datetime import datetime,timezone
from email.utils import parsedate_to_datetime
import collections,hashlib,json,lzma,math,resource,time,re,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent

def read(n):return json.loads(lzma.decompress((ROOT/n).read_bytes()))
def stamp(x):
 d=datetime.fromisoformat(x.replace('Z','+00:00'));assert d.tzinfo is not None;return d.timestamp()
def bind(n):
 p=ROOT/n;return {'path':str(p.relative_to(Path(__file__).resolve().parents[4])),'bytes':p.stat().st_size,'retained_SHA256':hashlib.sha256(p.read_bytes()).hexdigest(),'decoded_SHA256':hashlib.sha256(lzma.decompress(p.read_bytes())).hexdigest()}
def near(a,b,tol=1e-12):return abs(a-b)<=tol*max(1.,abs(a),abs(b))
def main():
 cpu=time.process_time();b=read('B_CAPTURE_METADATA_V2.json.xz');a1=read('A_OPERATIONAL_REFRESH_V1.json.xz');a2=read('A_OPERATIONAL_REFRESH_V2.json.xz');src=read('A_CURRENT_SOURCE.json.xz')
 assert b['id']=='B-F0-F2-20261110-W10-FIRST-01' and len(b['forecasts'])==16
 issue=stamp(b['issue_UTC']);cutoff=b['feature_cutoff'];ev=b['event'];kickoff=ev['kickoff'];native=stamp(ev['observed_UTC']);expiry=ev['expires_at'];now=datetime.now(timezone.utc).timestamp()
 assert ev['game_id']=='2026_10_WAS_NYG' and ev['native_event_id']==ev['competition_id']=='401873052'
 assert ev['home_team']=='NYG' and ev['away_team']=='WAS' and ev['season']==2026 and ev['week']==10 and ev['season_type']==2
 assert ev['state']=='pre' and ev['completed'] is False and ev['status_name']=='STATUS_SCHEDULED' and ev['competition_state_agreement'] is True
 assert cutoff<native<issue<expiry<kickoff and expiry-native<=1800.000001 and now>expiry and now<kickoff
 assert ev['HTTP_status']==200 and ev['HTTP_Age'] is None
 http=parsedate_to_datetime(ev['HTTP_Date']).timestamp();assert 0<=native-http<=5
 assert b['offers']==b['actual_line_selections']==0 and b['primary_switch'] is False
 assert b['outcomes']=='FUTURE_UNKNOWN_NOT_GRADED' and b['expected_starters']=='UNKNOWN_NOT_INFERRED' and b['transaction_effective_clocks']=='UNKNOWN_NOT_FILLED'
 assert b['original_website_consumer']=='NOT_DELIVERED_OR_ADMITTED' and 'REQUIRES_SEPARATE' in b['later_line_use']
 ids=set();present=[];missing=[];byarm=collections.Counter();missing_byarm=collections.Counter();mean_delta=0.;mass_delta=0.;quantile_exact=True
 for r in b['forecasts']:
  who=r['identity'];pid=who['player_id'];arm=r['arm'];key=(pid,arm);assert key not in ids;ids.add(key)
  assert re.fullmatch(r'00-\d{7}',pid) and arm in ['F0','F2']
  assert who['game_id']==ev['game_id'] and who['native_event_id']==ev['native_event_id'] and who['kickoff']==kickoff
  assert who['team'] in ['NYG','WAS'] and who['opponent']==('WAS' if who['team']=='NYG' else 'NYG') and who['position']=='QB' and who['season']==2026 and who['week']==10
  assert r['recipe']=='B-QB-ALIGNED-FRESHNESS-v1:'+arm and r['current_shadow_id']=='B-QB-FORWARD-TIMING-SHADOW-v1:'+arm
  assert r['feature_cutoff']==cutoff and cutoff<=stamp(r['actual_inferred_utc'])<native and stamp(r['actual_issued_UTC'])==issue
  assert r['actual'] is None and r['actual_status']=='FUTURE_NOT_GRADED' and r['exact_offer'] is None and r['side'] is None
  assert r['selection'] is False and r['original_website_selection'] is False
  assert 'CONDITIONAL_APPEARANCE_NOT_STARTER' in r['role_contract'] and 'NO_OFFER_OR_PICK' in r['issue_scope']
  assert re.fullmatch('[0-9a-f]{64}',r['model_sha256']) and re.fullmatch('[0-9a-f]{64}',r['prepared_record_sha256'])
  if r['basic_unavailable_record']:
   assert r['status']=='BASIC_ONLY_UNAVAILABLE_FORECAST' and r['original_pregame_forecast'] is False
   assert all(k not in r for k in ['mean','lower_median','law']) and who['provider_status']!='ACT'
   missing.append({'player_id':pid,'arm':arm,'status':who['provider_status'],'reason':r['reason']});missing_byarm[arm]+=1;continue
  assert r['status']=='ISSUED_FUTURE_FORECAST_ONLY_SHADOW' and r['original_pregame_forecast'] is True and who['provider_status']=='ACT'
  assert r['mean_type']=='EXPECTED_MEAN' and r['median_type']=='LOWER_MEDIAN' and math.isfinite(r['mean']) and r['mean']>=0
  assert r['target_outcome_not_accessed'] is True and r['probability_status']=='EXPERIMENTAL_COUNT_LAW_NOT_CALIBRATED_CONFIDENCE_OR_EV'
  assert len(r['own_game_ids'])==len(set(r['own_game_ids']))==r['own_prior_games'] and ev['game_id'] not in r['own_game_ids']
  if r['own_prior_games']:
   assert r['latest_own_game'] in r['own_game_ids'] and r['latest_own_game_time']<r['latest_own_reconstructed_available']<=cutoff
   lag=r['latest_own_reconstructed_available']-r['latest_own_game_time'];assert near(lag,7*86400 if arm=='F0' else 48*3600)
   assert near(r['last_source_age_days'],(cutoff-r['latest_own_reconstructed_available'])/86400)
  law=r['law'];assert law['kind']=='leaf_mixture' and law['prior']['kind']=='geometric'
  v,w=law['support'],law['weights'];q=law['prior']['q'];mix=law['mixture']
  assert len(v)==len(w)>0 and v==sorted(set(v)) and all(isinstance(k,int) and k>=0 for k in v)
  assert all(math.isfinite(k) and k>=0 for k in w) and 0<=q<1 and 0<=mix<=1
  weight_sum=sum(w);mass_delta=max(mass_delta,abs((1-mix)*weight_sum+mix-1));assert near(weight_sum,1.)
  # Explicit geometric prior q suffices despite the serialized redundant mean=null.
  m=(1-mix)*sum(k*z for k,z in zip(v,w))+mix*q/(1-q);mean_delta=max(mean_delta,abs(m-r['mean']));assert near(m,r['mean'])
  def cdf(k):return 0. if k<0 else (1-mix)*sum(z for value,z in zip(v,w) if value<=k)+mix*(1-q**(k+1))
  med=r['lower_median'];assert isinstance(med,int) and med>=0 and cdf(med)>=.5 and cdf(med-1)<.5
  # Verify proper support/tail, finite nonnegative mass and CDF monotonicity independently.
  previous=0.
  for k in range(max(v)+2):
   value=cdf(k);assert math.isfinite(value) and value>=previous-1e-12 and -1e-12<=value<=1+1e-12;previous=value
  assert near(cdf(10000),1.)
  present.append({'player_id':pid,'arm':arm,'mean':r['mean'],'lower_median':med,'own_prior_games':r['own_prior_games'],'latest_own_game':r['latest_own_game'],'reconstructed_admitted_history':True});byarm[arm]+=1
 assert len(present)==10 and len(missing)==6 and byarm=={'F0':5,'F2':5} and missing_byarm=={'F0':3,'F2':3}
 assert len({x['player_id'] for x in present})==5 and len({x['player_id'] for x in missing})==3
 corr=b['metadata_correction'];assert corr['version']==2 and corr['original_packet_retained'] is True and corr['new_fits']==corr['new_inference']==corr['new_forecasts']==0
 dep=a1['producer_current_dependency'];assert dep['registered_producer_branch']=='research/weekly-storage-probe-v1' and dep['registered_producer_head']=='fa91988e65939d2b3516371a90a6380aeee3acb3'
 assert dep['product']=='pass_td__COUNT_A_MEAN' and dep['procedure']=='f8607aa99a94c7c1c9ab5c89599e07eba9b15527749b092b225f368032881e83'
 assert 'SOURCE.json' in dep['first_dependency'] and 'feature_capture_receipt' in dep['first_dependency'] and '61440' in dep['first_dependency']
 assert dep['website_owner_lease']['lease']==178 and dep['website_owner_lease']['owner']=='NFL-WEB-PRODUCTION-REPORT-INTEGRATION-20261025-122500Z'
 assert 'Corrected FORECASTS.parquet.point is mean' in dep['typed_output'] and 'legacy_point is mixed fallback' in dep['typed_output'] and 'mean field NaN' in dep['typed_output']
 gaps={x['id']:x for x in src['exact_contract_gaps']};assert gaps['A_F3_EPA']['affected']=='F3 profile efficiency/success features'
 assert 'F0 andF3' in gaps['A_HISTORY_CENSUS']['affected'] and 'outcome_available_utc' in gaps['A_CURRENT_CLOCKS']['reason']
 findings={'B_record_count':16,'B_forecast_count':10,'B_basic_unavailable_count':6,'B_forecast_players':5,'B_basic_only_players':3,'B_arms':dict(byarm),'B_basic_only_arms':dict(missing_byarm),'B_forecasts':present,'B_unavailable':missing,'B_offers':0,'B_actual_line_selections':0,'B_native_gate':'VALID_AT_ORIGINAL_ISSUE;EXPIRED_FOR_NEW_ISSUANCE_OR_REPRICING','B_native_observed_UTC':ev['observed_UTC'],'B_native_expiry_UTC':datetime.fromtimestamp(expiry,timezone.utc).isoformat(),'B_issue_UTC':b['issue_UTC'],'B_kickoff_UTC':datetime.fromtimestamp(kickoff,timezone.utc).isoformat(),'B_field_law_checks':{'normalization_support_CDF':True,'geometric_prior_interpretation':'P(K=k)=(1-q)*q^k,k>=0; mean=q/(1-q); no model inference','maximum_mass_error':mass_delta,'maximum_saved_mean_error':mean_delta,'lower_medians_exact':True,'new_fits':0,'re_inference':0},'B_original_metadata_V1_parity':'NOT_RECHECKED_HERE;ONLY_RECEIVED_V2_INTERNAL_CONSISTENCY','B_new_original_site_admission':False,'producer':{'registered_branch':dep['registered_producer_branch'],'registered_head_as_of_A_receipt':dep['registered_producer_head'],'workflow':'lab.yml (owner-reported Nov10 receipt)','current_route':dep['current_W10_route'],'minimum_dependency':dep['first_dependency'],'named_executor':'Registered A producer execution owner; unique lease-holder identifier not published in inspected receipt','website_lease_not_producer_lease':dep['website_owner_lease'],'current_status_limit':'As-of received A Nov10 receipt, not fresh producer execution inspection'},'EPA_scope':'The inspected A source gap attaches EPA to F3 efficiency only. No EPA requirement is inferred for Count A or C P1 without their own recipe contract.','old_current_role_scope':'Known basic ACT snapshot, not expected starters, health or event-effective transaction authentication.'}
 receipt={'id':'C-CATEGORY-INDEPENDENT-OPERATIONAL-METADATA-v1','checked_UTC':datetime.now(timezone.utc).isoformat(),'status':'PASS_RECEIVED_PACKET_INTERNAL_METADATA_AND_DECLARED_LAW_ARITHMETIC','inputs':[bind(n) for n in ['B_CAPTURE_METADATA_V2.json.xz','A_OPERATIONAL_REFRESH_V1.json.xz','A_OPERATIONAL_REFRESH_V2.json.xz','A_CURRENT_SOURCE.json.xz']],'findings':findings,'limits':['No B model loading, fitted-model inference, raw-source reconstruction or performance/quality validation.','Native HTTP/source facts are owner metadata; no new observation or original-source-vintage authentication.','No received original-site consumption, saved-pick, deployment or scientific admission is established.','Prepared-record hashes are commitments only; no unseen prepared rows were independently restored.'],'GETs':0,'new_fits':0,'new_model_inference':0,'new_NFL_observations':0,'CPU_seconds':time.process_time()-cpu,'peak_RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,'python':sys.version}
 (HERE/'OPERATIONAL_METADATA_REVIEW.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({k:v for k,v in receipt.items() if k not in ['findings','inputs']}))
if __name__=='__main__':main()
