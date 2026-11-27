"""Mocked typed-current contracts only; no NFL inference, fit or source read."""
import copy,hashlib,json,sys,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import current_query_delivery_c06 as c
from targeted_data_m3 import feature_names
class FixtureLaw:
 a=.05
 def mean(self):return 0.
 def quantile(self,p):return 0.
 def probability(self,line):return dict(over=.5,under=.5,push=0.) if line==1. else dict(over=.1,under=.9,push=0.)
 v=np.array([0]);w=np.array([1.]);scale=1
 prior=type('P',(),dict(kind='count',empty=False,mu=0.,center=0,q=.1,event=0.))()
def fixture(target='rec'):
 names=feature_names(target);impute=[0.]*32;model=dict(schema='C-NUMERIC-LEAF-v4',kind='count' if target=='rec' else 'signed',scale=1,imputation=impute,trees=[],prior={},global_prior=dict(kind='count' if target=='rec' else 'signed'))
 raw=json.dumps(model).encode();pid=f'C-M3-v1.1::{target}::M3-0::base'
 row=dict(procedure_id=pid,category=target,forecast_id='FIXTURE',player_id='00-0000001',position='WR',game_id='2026_11_A_B',team='A',opponent_team='B',native_event_id='fixture',feature_order=names,features=[None]*32,source_contract_SHA256='a'*64,query_admission_SHA256='b'*64,source_observed_UTC='2026-11-22T11:00:00Z',information_cutoff_UTC='2026-11-22T11:01:00Z',inference_UTC='2026-11-22T11:02:00Z',issued_UTC='2026-11-22T11:03:00Z',persisted_UTC='2026-11-22T11:04:00Z',expires_UTC='2026-11-22T11:30:00Z',kickoff_UTC='2026-11-22T18:00:00Z')
 bind=dict(procedure_id=pid,feature_order=names,model_SHA256=hashlib.sha256(raw).hexdigest(),imputation_SHA256=hashlib.sha256(json.dumps(impute,separators=(',',':')).encode()).hexdigest(),source_contract_SHA256='a'*64,query_admission_SHA256='b'*64,persistence_receipt_SHA256='c'*64,model_origin='2026-W11',fit_cutoff_UTC='2026-11-22T10:30:00Z',latest_training_available_UTC='2026-11-21T10:00:00Z',target_game_exclusion_verified=True,training_game_ids=[],query_role_membership_verified=True,preprocessing='M3_E0_OP32_TRAINING_MEDIAN_PLUS_MISSING_MASK',corrector='NO_EXTRA_CORRECTOR')
 bind['query_row_SHA256']=c.m3_current_query_fingerprint(row)
 event=dict(game_id=row['game_id'],espn_event_id='fixture',home_team='A',away_team='B',kickoff_UTC=row['kickoff_UTC'],state='pre',status_name='STATUS_SCHEDULED',completed=False,observed_UTC='2026-11-22T11:04:00Z')
 offer=dict(qualified=True,admission_record_SHA256='d'*64,player_id=row['player_id'],game_id=row['game_id'],category=target,period='FULL_GAME_INCLUDING_OVERTIME',comparator_contract='OVER_GT_UNDER_LT_EQUAL_PUSH',line=1.,venue='SOFTWARE_FIXTURE_ONLY',product='SOFTWARE_NOT_NFL_EVIDENCE',state='OPEN',offered_sides=['OVER','UNDER'],observed_UTC='2026-11-22T11:02:00Z',expiry_UTC='2026-11-22T11:20:00Z')
 return row,bind,raw,event,offer
class M3TypedAdapterTests(unittest.TestCase):
 def call(self,r,b,raw,e,offers=None,at='2026-11-22T11:05:00Z',**kw):return c.m3_leaf_current_records(r,b,raw,at,current_event=e,offers=offers,**kw)
 def test_zero_missing_sparse_and_separate_types_one_inference(self):
  for target in ('rec','rec_yd'):
   r,b,raw,e,o=fixture(target);before=copy.deepcopy(r)
   with patch('safe_models_v4.infer_forest',return_value=[FixtureLaw()]) as fn:out=self.call(r,b,raw,e)
   self.assertEqual(fn.call_count,1);self.assertTrue(np.isnan(fn.call_args.args[1]).all());self.assertEqual(fn.call_args.args[2],['WR'])
   self.assertEqual([x['output_type'] for x in out],['MEAN_POINT','MEDIAN_POINT','LAW']);self.assertEqual([x['point'] for x in out],[0.,0.,None]);self.assertIsNotNone(out[2]['law']);self.assertEqual(r,before)
   self.assertTrue(all(x['corrector']=='NO_EXTRA_CORRECTOR' and not x['hard_incumbent_fallback'] and x['confidence'] is None and not x['capture_or_consumer_admission'] for x in out))
 def test_expired_unknown_role_and_missing_model_never_infer(self):
  for change,at in [(dict(position='RB'),'2026-11-22T11:05:00Z'),({},'2026-11-22T11:30:00Z'),(dict(persisted_UTC=None),'2026-11-22T11:05:00Z')]:
   r,b,raw,e,o=fixture();r.update(change);b['query_row_SHA256']=c.m3_current_query_fingerprint(r)
   with patch('safe_models_v4.infer_forest') as fn:out=self.call(r,b,raw,e,at=at)
   fn.assert_not_called();self.assertTrue(all(not x['available'] and x['selected_side'] is None for x in out))
  r,b,raw,e,o=fixture()
  with patch('safe_models_v4.infer_forest') as fn:out=self.call(r,b,None,e)
  fn.assert_not_called();self.assertEqual(out[0]['state'],'CURRENT_ORIGIN_MODEL_NOT_DELIVERED')
 def test_exact_point_and_probability_ties_not_margin_or_top_picks(self):
  r,b,raw,e,o=fixture();offers={k:o for k in ('MEAN_POINT','MEDIAN_POINT','LAW')}
  with patch('safe_models_v4.infer_forest',return_value=[FixtureLaw()]):out=self.call(r,b,raw,e,offers)
  self.assertEqual([x['selected_side'] for x in out],['UNDER','UNDER',None]);self.assertTrue(all(x['probabilities_at_line'] is None for x in out[:2]));self.assertIsNotNone(out[2]['probabilities_at_line'])
  later=dict(o,observed_UTC='2026-11-22T11:04:00Z')
  with patch('safe_models_v4.infer_forest',return_value=[FixtureLaw()]):out=self.call(r,b,raw,e,{'MEAN_POINT':later})
  self.assertIn('REPRICING',out[0]['state']);self.assertIsNone(out[0]['selected_side'])
 def test_schema_model_source_and_event_mismatches_fail_before_inference(self):
  r,b,raw,e,o=fixture()
  for bb in [dict(b,feature_order=b['feature_order'][::-1]),dict(b,corrector='EXTRA'),dict(b,model_SHA256='0'*64),dict(b,model_origin='2026-W09'),dict(b,imputation_SHA256='0'*64)]:
   with patch('safe_models_v4.infer_forest') as fn:
    with self.assertRaises(ValueError):self.call(r,bb,raw,e)
   fn.assert_not_called()
  with patch('safe_models_v4.infer_forest') as fn:
   with self.assertRaises(ValueError):self.call(r,b,raw,dict(e,state='post',completed=True))
  fn.assert_not_called()
 def test_exact_query_binding_catches_changed_features_or_identity(self):
  r,b,raw,e,o=fixture()
  for changed in (dict(r,features=[1.]+r['features'][1:]),dict(r,player_id='00-0000002')):
   with patch('safe_models_v4.infer_forest') as fn:
    with self.assertRaisesRegex(ValueError,'QUERY_ROW_BINDING'):self.call(changed,b,raw,e)
   fn.assert_not_called()
 def test_prior_kind_and_receiving_yard_offer_target(self):
  r,b,raw,e,o=fixture('rec_yd')
  offers={k:o for k in ('MEAN_POINT','MEDIAN_POINT','LAW')}
  with patch('safe_models_v4.infer_forest',return_value=[FixtureLaw()]):out=self.call(r,b,raw,e,offers)
  self.assertEqual([z['category'] for z in out],['rec_yd']*3);self.assertEqual(out[0]['selected_side'],'UNDER')
  with patch('safe_models_v4.infer_forest',return_value=[FixtureLaw()]):
   with self.assertRaisesRegex(ValueError,'OFFER_CATEGORY'):self.call(r,b,raw,e,{'LAW':dict(o,category='rec')})
  for part in ('global_prior','prior'):
   model=json.loads(raw);model[part]=dict(kind='count') if part=='global_prior' else {'WR':dict(kind='count')};bad=json.dumps(model).encode();bb=dict(b,model_SHA256=hashlib.sha256(bad).hexdigest())
   with patch('safe_models_v4.infer_forest') as fn:
    with self.assertRaisesRegex(ValueError,'PRIOR_SUPPORT'):self.call(r,bb,bad,e)
   fn.assert_not_called()
if __name__=='__main__':unittest.main()
