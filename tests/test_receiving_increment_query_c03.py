import copy,gzip,hashlib,json,lzma,sys,unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import test_receiving_profiles_c02 as profile_fixtures
from receiving_profiles_c02 import query_universe
from receiving_defense_c03 import ReceivingDefense
from receiving_increment_query_c03 import build_query_profile,query_contract,validate_asof_query,infer_current_query,ORDERS,VERSION
from laws_v2 import Prior
from safe_models_v4 import prior_data

class ReceivingIncrementQueryTests(unittest.TestCase):
 def fixture(self,arm='R3',compressed='xz'):
  old=profile_fixtures.ReceivingProfiles();roster,event,cut,players,teams,context,pbp=old.fixtures();queries,_=query_universe(roster,[event],cut);q=next(r for r in queries if r['player_id']=='00-0000001');builder=old.builder(cut,players,teams,context,pbp)
  defense=ReceivingDefense([pbp],players,context_schedule(event,context),context=context,source_bindings={'version':'SYNTHETIC_SOFTWARE_ONLY'})
  profile=build_query_profile(builder,defense,q);prior=prior_data(Prior(np.array([0,1,2]),'count'))
  model={'schema':'C-NUMERIC-LEAF-v4','kind':'count','scale':1,'imputation':[0.]*len(ORDERS[arm]),'prior':{'WR':prior},'global_prior':prior,'trees':[{'left':[-1],'right':[-1],'feature':[-2],'threshold':[-2.],'leaves':{'0':[[1,3],[1,1]]}} for _ in range(32)]}
  code=profile['feature_engine_code_SHA256'];payload={'id':VERSION,'origin':'2026-W02','arm':arm,'model':model,'feature_order':ORDERS[arm],'code_SHA256':code,'defense_code_SHA256':profile['defense_code_SHA256'],'registration_SHA256':'a'*64}
  raw=json.dumps(payload,separators=(',',':')).encode();raw=lzma.compress(raw) if compressed=='xz' else gzip.compress(raw) if compressed=='gz' else raw
  binding=dict(query_contract(profile),recipe_id=VERSION,arm=arm,feature_order=ORDERS[arm],fit_cutoff_UTC='2026-09-12T11:00:00Z',latest_training_available_UTC='2026-09-11T11:00:00Z',model_origin='2026-W02',model_SHA256=hashlib.sha256(raw).hexdigest(),target_game_exclusion_verified=True,training_game_ids=[],code_SHA256=code,defense_code_SHA256=profile['defense_code_SHA256'],registration_SHA256='a'*64,selection_product='LAW',roster_admission={'admission':'QUALIFIED_FOR_EVENT_VERSION','player_id':q['player_id'],'game_id':q['game_id'],'team':q['team'],'season':2026,'week':2,'status':'ACT','observed_UTC':cut,'source_effective_UTC':'2026-09-12T10:00:00Z','source_SHA256':'b'*64})
  return profile,binding,raw,event,cut,(builder,defense,q)
 def test_exact_arm_order_and_typed_safe_leaf_inference(self):
  for arm in ['R1','R2','R3']:
   for compression in ['xz','gz','json']:
    p,b,raw,e,at,_=self.fixture(arm,compression);out=infer_current_query(p,b,raw,current_event=e,admission_UTC=at)
    self.assertEqual(p['arms'][arm]['feature_order'],ORDERS[arm]);self.assertEqual(out['mean_type'],'EXPECTED_MEAN');self.assertEqual(out['median_type'],'LOWER_MEDIAN');self.assertFalse(out['qualified_offer']);self.assertIsNone(out['selected_side']);self.assertNotIn('probabilities_at_exact_line',out);self.assertAlmostEqual(out['prior_mixture_mass'],.05);self.assertFalse(out['hard_model_fallback'])
 def test_current_status_required_started_stale_identity(self):
  p,b,raw,e,at,_=self.fixture()
  for event,clock in [(dict(e,state='post',completed=True),at),(e,'2026-09-15T18:00:00Z'),(e,'2026-09-12T12:30:01Z'),(dict(e,espn_event_id='WRONG'),at)]:
   with self.assertRaises(ValueError):infer_current_query(p,b,raw,current_event=event,admission_UTC=clock)
  with self.assertRaisesRegex(ValueError,'REQUIRED'):infer_current_query(p,b,raw,current_event=None,admission_UTC=at)
 def test_seven_week_old_roster_never_relabelled_from_headers(self):
  p,b,raw,e,at,_=self.fixture();p=copy.deepcopy(p);p['base_profile']['roster_source_week']=1;p['base_profile']['source_bindings']['Last-Modified']=at
  with self.assertRaisesRegex(ValueError,'ROSTER_EVENT_VERSION'):infer_current_query(p,b,raw,current_event=e,admission_UTC=at)
  p,b,raw,e,at,_=self.fixture();p['base_profile']['forecast_adapter']['roster_status_version_qualified']=False
  with self.assertRaisesRegex(ValueError,'UNQUALIFIED'):infer_current_query(p,b,raw,current_event=e,admission_UTC=at)
 def test_binding_origin_order_SHA_and_old_model_rejected(self):
  p,b,raw,e,at,_=self.fixture()
  for mutation in [dict(model_origin='2026-W01'),dict(feature_order=list(reversed(b['feature_order']))),dict(model_SHA256='0'*64),dict(profile_contract_id='OLD_POISSON'),dict(target_game_exclusion_verified=False),dict(registration_SHA256='c'*64)]:
   with self.assertRaises(ValueError):infer_current_query(p,dict(b,**mutation),raw,current_event=e,admission_UTC=at)
  bad=json.loads(lzma.decompress(raw));bad['model']={'type':'L2_POOLED_POISSON'};raw2=json.dumps(bad).encode();bb=dict(b,model_SHA256=hashlib.sha256(raw2).hexdigest())
  with self.assertRaisesRegex(ValueError,'SAFE_LEAF'):infer_current_query(p,bb,raw2,current_event=e,admission_UTC=at)
 def test_target_actual_mutation_does_not_change_query_inputs(self):
  p,b,raw,e,at,(builder,defense,q)=self.fixture();changed=dict(q,actual=9999,played=True,targets=99999,values={'rec':9999});p2=build_query_profile(builder,defense,changed)
  self.assertEqual(p,p2);self.assertEqual(infer_current_query(p,b,raw,current_event=e,admission_UTC=at,line=2.5),infer_current_query(p2,b,raw,current_event=e,admission_UTC=at,line=2.5))
 def test_null_feature_vs_infinite_and_source_contract(self):
  p,b,raw,e,at,_=self.fixture();p=copy.deepcopy(p);p['arms']['R3']['features'][0]=None;out=infer_current_query(p,b,raw,current_event=e,admission_UTC=at);self.assertTrue(np.isfinite(out['expected_mean']))
  p['arms']['R3']['features'][0]=float('inf')
  with self.assertRaisesRegex(ValueError,'NONFINITE'):infer_current_query(p,b,raw,current_event=e,admission_UTC=at)
  p,b,raw,e,at,_=self.fixture();p['defense_source_bindings']['version']='OTHER'
  with self.assertRaisesRegex(ValueError,'SOURCE_CONTRACT'):infer_current_query(p,b,raw,current_event=e,admission_UTC=at)
 def test_changed_line_recomputes_mass_and_push(self):
  p,b,raw,e,at,_=self.fixture();one=infer_current_query(p,b,raw,current_event=e,admission_UTC=at,line=.5);two=infer_current_query(p,b,raw,current_event=e,admission_UTC=at,line=2.5);integer=infer_current_query(p,b,raw,current_event=e,admission_UTC=at,line=1.)
  self.assertGreater(one['probabilities_at_exact_line']['over'],two['probabilities_at_exact_line']['over']);self.assertGreater(integer['probabilities_at_exact_line']['push'],0)
  for out in [one,two,integer]:self.assertAlmostEqual(sum(out['probabilities_at_exact_line'].values()),1);self.assertFalse(out['qualified_offer']);self.assertIsNone(out['selected_side'])
 def test_external_offer_gate_and_unoffered_side_abstention(self):
  p,b,raw,e,at,_=self.fixture();offer={'qualified':True,'admission_record_SHA256':'d'*64,'player_id':p['base_profile']['key']['player_id'],'game_id':p['base_profile']['key']['game_id'],'category':'rec','period':'FULL_GAME_INCLUDING_OVERTIME','comparator_contract':'OVER_GT_UNDER_LT_EQUAL_PUSH','line':2.5,'venue':'SOFTWARE_FIXTURE_ONLY','product':'STRAIGHT_PROP','offered_sides':['OVER','UNDER'],'state':'OPEN','observed_UTC':at,'expiry_UTC':'2026-09-12T12:10:00Z'}
  out=infer_current_query(p,b,raw,current_event=e,admission_UTC=at,offer=offer);self.assertTrue(out['qualified_offer']);self.assertEqual(out['selected_side'],'UNDER')
  only=dict(offer,offered_sides=['OVER']);out=infer_current_query(p,b,raw,current_event=e,admission_UTC=at,offer=only);self.assertIsNone(out['selected_side']);self.assertEqual(out['selection_state'],'ABSTAIN_UNOFFERED_SIDE_OR_TIE')
  for bad in [dict(offer,line=1.5),dict(offer,state='CLOSED'),dict(offer,expiry_UTC=at),dict(offer,admission_record_SHA256=None)]:
   with self.assertRaises(ValueError):infer_current_query(p,b,raw,current_event=e,admission_UTC=at,line=2.5,offer=bad)
 def test_asof_validation_cannot_issue_historical_profile(self):
  p,b,raw,e,at,_=self.fixture();p=copy.deepcopy(p);p['base_profile']['historical_roster_clock']='RECONSTRUCTED_NOT_AUTHENTICATED';validate_asof_query(p,b,raw)
  with self.assertRaisesRegex(ValueError,'HISTORICAL'):infer_current_query(p,b,raw,current_event=e,admission_UTC=at)
 def test_roster_effective_receipt_and_future_fit_required(self):
  p,b,raw,e,at,_=self.fixture()
  for bb in [dict(b,roster_admission={}),dict(b,fit_cutoff_UTC='2026-09-12T12:00:01Z'),dict(b,training_game_ids=[p['base_profile']['key']['game_id']]),dict(b,roster_admission=dict(b['roster_admission'],source_effective_UTC='2026-09-13T00:00Z'))]:
   with self.assertRaises(ValueError):infer_current_query(p,bb,raw,current_event=e,admission_UTC=at)

def context_schedule(event,context):
 r=context.quality[0];base=next(iter(context.teams.groups.values()))[0]
 return __import__('pandas').DataFrame([dict(game_id=r['game_id'],season=2026,week=1,home_team='ATL',away_team='CAR',kickoff=base['kickoff'])])
if __name__=='__main__':unittest.main()
