"""C06 current-source parity/admission fixtures; zero NFL fits/inference."""
import copy,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import current_query_delivery_c06 as c
import prospective_v4 as p
import site_forward_v4 as site

def game():return dict(game_id=c.TARGET,home_team='NYG',away_team='WAS',season=2026,week=10,kickoff=1794532500.,espn=401873052)
def player(pid='00-0000001',role='WR',status='ACT'):
 return dict(gsis_id=pid,team='WAS',position=role,status=status,season=2026,full_name='Synthetic fixture')
def query(pid='00-0000001',role='WR'):
 return dict(player_id=pid,position=role,team='WAS',opponent_team='NYG',game_id=c.TARGET,kickoff=game()['kickoff'],kickoff_UTC='2026-11-13T01:15:00Z')
def prepared(pid='00-0000001',role='WR',mean=0.):
 return dict(query(pid,role),feature_order=['x'],features=[None],mean=mean,median=0.,p05=0.,p95=0.,model_SHA256='fixture',information_cutoff_UTC='2026-11-10T19:23:09Z',inference_UTC='2026-11-10T19:32:00Z',admitted_prior_games=[],latest_admitted_game=None,history_support=0,sparse_history=True,any_imputed=True,prior_provenance='TRAINING_ONLY_IMPUTATION')

class CurrentP1Tests(unittest.TestCase):
 def test_strict_boundary_finality_and_future_mutation(self):
  cut=1000000.;f=pd.DataFrame([dict(game_id='earlier',kickoff=cut-7*86400-1,home_score=0,away_score=0),dict(game_id='equal',kickoff=cut-7*86400,home_score=7,away_score=0),dict(game_id='unknown',kickoff=cut-8*86400,home_score=None,away_score=0),dict(game_id='future',kickoff=cut+100,home_score=None,away_score=None)])
  self.assertEqual(c.eligible_seven_day_games(f,cut),{'earlier'})
  f.loc[f.game_id=='future',['home_score','away_score']]=999
  self.assertEqual(c.eligible_seven_day_games(f,cut),{'earlier'})
 def test_raw_projection_unknown_zero_and_off_window_changes(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);a=root/'old.csv';b=root/'new.csv';old=pd.DataFrame([dict(game_id='eligible',player_id='one',count=np.nan),dict(game_id='excluded',player_id='two',count=3.)]);new=old.copy();new.loc[new.game_id=='excluded','count']=999
   old.to_csv(a,index=False);new.to_csv(b,index=False);self.assertEqual(c.canonical_equal(a,b,['game_id','player_id'],{'eligible'}),(True,1,1))
   new.loc[new.game_id=='eligible','count']=0.;new.to_csv(b,index=False);self.assertFalse(c.canonical_equal(a,b,['game_id','player_id'],{'eligible'})[0])
 def test_current_universe_needs_no_target_outcomes_and_keeps_basic(self):
  roster=[player(),player('00-0000002','RB'),player('00-0000003','QB'),player('00-0000004','TE','RES')]
  b,q=c.query_universe(roster,[game()],2026);self.assertEqual(len(b),4);self.assertEqual(len(q),2)
  changed=[dict(r,actual=999,played=True,targets=99,outcome_available=None) for r in roster]
  self.assertEqual(c.query_universe(changed,[game()],2026),(b,q));self.assertTrue(all(r['starter_state']=='UNKNOWN_NOT_INFERRED' for r in b))
 def test_auth_gate_precedes_sources_or_inference(self):
  with patch.object(c,'read',return_value={'execution_authorized':False}),patch.object(c,'committed') as bind,patch.object(c,'current_rows') as infer:
   with self.assertRaisesRegex(AssertionError,'ROOT_COMMITTED_EXECUTION_AUTHORIZATION'):c.infer_draft('/tmp/c06-not-created-fixture')
   bind.assert_not_called();infer.assert_not_called()
 def test_typed_zero_and_role_scope_corrector_once(self):
  meta=dict(feature_order=['x'],fit_information_cutoff_UTC='2026-11-10T19:23:09Z',feature_policy='REGISTERED7D',model={})
  with patch.object(c,'pooled_mu',return_value=np.array([0.,0.])) as link:
   rows=c.current_rows([query(),query('00-0000002','RB')],[prepared(),prepared('00-0000002','RB')],meta,'2026-11-12T01:43:52Z','2026-11-12T02:00:00Z')
  link.assert_called_once();self.assertEqual(len(rows),2)
  self.assertEqual([r['mean'] for r in rows],[0.,0.]);self.assertEqual([r['direction_candidate_role_eligible'] for r in rows],[True,False])
  self.assertEqual(rows[1]['RB_status'],'SEPARATE_FORECAST_ONLY_SHADOW')
  for r in rows:
   self.assertEqual(r['model_fit_cutoff_UTC'],'2026-11-10T19:23:09Z');self.assertEqual(r['information_cutoff_UTC'],'2026-11-12T01:43:52Z');self.assertEqual(r['original_prepared_inference_UTC'],'2026-11-10T19:32:00Z');self.assertIsNone(r['selected_side']);self.assertIsNone(r['confidence']);self.assertIsNone(r['EV'])
  self.assertEqual(json.loads(json.dumps(rows)),rows)
 def test_unseen_or_mismatched_current_identity_is_not_assigned_cached_output(self):
  meta=dict(feature_order=['x'],fit_information_cutoff_UTC='2026-11-10T19:23:09Z',feature_policy='7D',model={})
  for q in [query('00-0000002'),dict(query(),team='NYG'),dict(query(),position='TE'),dict(query(),kickoff=game()['kickoff']+1)]:
   with patch.object(c,'pooled_mu') as fn:self.assertEqual(c.current_rows([q],[prepared()],meta,'2026-11-12T01:43:52Z','2026-11-12T02:00:00Z'),[]);fn.assert_not_called()
 def test_model_parity_failure_cannot_be_called_current_reuse(self):
  meta=dict(feature_order=['x'],fit_information_cutoff_UTC='2026-11-10T19:23:09Z',feature_policy='7D',model={})
  with patch.object(c,'pooled_mu',return_value=np.array([1.])):
   with self.assertRaisesRegex(AssertionError,'RETAINED_MEAN_PARITY'):c.current_rows([query()],[prepared()],meta,'2026-11-12T01:43:52Z','2026-11-12T02:00:00Z')
 def test_common_pipeline_dispatch_and_legacy_feed_isolation(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);(root/'RUN.json').write_text(json.dumps({'schema':c.SCHEMA}))
   with patch.object(c,'validate_run',return_value=({'schema':c.SCHEMA},[])) as fn:self.assertEqual(p.validate_run(root),({'schema':c.SCHEMA},[]));fn.assert_called_once_with(root,False)
  self.assertFalse(site.legacy_feed_run({'schema':c.SCHEMA}))
  with self.assertRaisesRegex(AssertionError,'UNKNOWN'):site.legacy_feed_run({'schema':'C06-UNKNOWN'})
 def test_actual_source_basis_metadata_no_fit_or_nfl_inference(self):
  cutoff=c.read(c.SOURCE/'MODEL_INPUT_MANIFEST.json')['actual_input_cutoff_UTC']
  with patch.object(c,'pooled_mu') as infer,patch.object(c.subprocess,'check_output',side_effect=AssertionError('Assessment must work without historical Git objects')) as git_history:
   a=c.assess(at=c.aware(cutoff).timestamp())
  git_history.assert_not_called()
  infer.assert_not_called();self.assertEqual(a['state'],'EXACT_RETAINED_FIT_AND_VECTOR_REUSE_PROVED');self.assertEqual(a['available_players'],25);self.assertEqual(a['WR_TE_current_query_rows'],18);self.assertEqual(a['RB_shadow_rows'],7);self.assertEqual(a['eligible_fact_rows_current'],8420);self.assertEqual(a['eligible_PBP_rows_current'],15136);self.assertEqual(a['new_fits_required'],0)
 def test_exact_mean_offer_boundary_zero_and_explicit_repricing(self):
  r=dict(query(),model_id=c.MODEL,mean=0.,forecast_id='fixture',issued_UTC='2026-11-12T02:00:00Z',expires_UTC='2026-11-12T02:30:00Z')
  offer=dict(qualified=True,admission_record_SHA256='a'*64,player_id=r['player_id'],game_id=r['game_id'],category='rec',period='FULL_GAME_INCLUDING_OVERTIME',comparator_contract='OVER_GT_UNDER_LT_EQUAL_PUSH',line=.5,venue='SYNTHETIC_SOFTWARE_FIXTURE',product='SYNTHETIC_NOT_NFL_EVIDENCE',tier='FIXTURE',state='OPEN',offered_sides=['OVER','UNDER'],observed_UTC='2026-11-12T02:01:00Z',expiry_UTC='2026-11-12T02:20:00Z')
  before=copy.deepcopy(r)
  x=c.point_direction_record(r,offer,'2026-11-12T02:02:00Z');self.assertIsNone(x['selected_side']);self.assertIn('REPRICING',x['state'])
  x=c.point_direction_record(r,offer,'2026-11-12T02:02:00Z',repricing_policy='LATER_CAPTURED_PREGAME_LINE_BOTH_CLOCKS_PRESERVED');self.assertEqual(x['selected_side'],'UNDER');self.assertEqual(x['expected_mean'],0.);self.assertIsNone(x['confidence']);self.assertIsNone(x['EV']);self.assertEqual(r,before)
  x=c.point_direction_record(r,dict(offer,line=0.),'2026-11-12T02:02:00Z',repricing_policy='LATER_CAPTURED_PREGAME_LINE_BOTH_CLOCKS_PRESERVED');self.assertIsNone(x['selected_side']);self.assertIn('ABSTAIN_EQUAL',x['state'])
 def test_unqualified_expired_missing_or_wrong_role_cannot_make_a_pick(self):
  r=dict(query(),model_id=c.MODEL,mean=0.,forecast_id='fixture',issued_UTC='2026-11-12T02:00:00Z',expires_UTC='2026-11-12T02:30:00Z')
  self.assertEqual(c.point_direction_record(r,None,'2026-11-12T02:02:00Z')['state'],'NO_QUALIFIED_CURRENT_OFFER')
  self.assertIn('EXPIRED',c.point_direction_record(r,None,'2026-11-12T02:31:00Z')['state'])
  self.assertIn('UNSUPPORTED',c.point_direction_record(dict(r,position='RB'),None,'2026-11-12T02:02:00Z')['state'])
  with self.assertRaisesRegex(ValueError,'FINITE_EXPECTED_MEAN'):c.point_direction_record(dict(r,mean=None),None,'2026-11-12T02:02:00Z')
 def test_source_snapshot_validation_uses_explicit_clock_not_future_outcome(self):
  m=c.read(c.SOURCE/'MODEL_INPUT_MANIFEST.json');cut=c.aware(m['actual_input_cutoff_UTC']).timestamp()
  x,roster=c.source_inputs(at=cut);self.assertEqual(x,m);self.assertEqual(len(roster),959)
  with self.assertRaisesRegex(AssertionError,'EXPIRED_OR_FUTURE'):c.source_inputs(at=cut+3*86400)

if __name__=='__main__':unittest.main()
