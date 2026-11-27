"""Software contracts only: no NFL fitter, optimizer or trajectory generator."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from shared_game_sim01_kernel import TeamParameters,GainTupleLaw,GameSamples,COUNT_FIELDS,CHILD_FIELDS,TRAJECTORIES
from shared_game_sim01_condition import _targets,CORE
from shared_game_sim01_retention import write_replay_bundle,reopen_replay_bundle
from shared_game_sim01_metrics import build_raw_grades
import shared_game_sim01_run as run_worker
from shared_game_sim01_run import failure_record_path,canary_game,retained_mutation_game,verify_private_inputs,restore_retained_prior

def team(name):
 law=GainTupleLaw(np.array([-1,2]),np.array([0,1]),np.array([.5,.5]))
 kneel=GainTupleLaw(np.array([-1]),np.array([0]),np.array([1.]))
 return TeamParameters(name,('__OTHER__::'+name,),0,(0,),(0,),(0,),60.,np.ones(5),np.ones(1),np.array([[1.,0.]]),np.array([[[1.,1.,1.],[0.,1.,1.]]]),np.ones(1),((law,),),(law,),(law,),(kneel,))

class SharedSimContracts(unittest.TestCase):
 def test_canary_is_one_predeclared_origin_and_never_skips_failure(self):
  wanted=dict(native_game_id=run_worker.CANARY_NATIVE_GAME_ID)
  games=[dict(native_game_id='different_game'),wanted]
  self.assertIs(canary_game(games,[],set()),wanted)
  with self.assertRaisesRegex(RuntimeError,'ALREADY_ATTEMPTED'):
   canary_game(games,[],{run_worker.CANARY_NATIVE_GAME_ID})
  with self.assertRaisesRegex(ValueError,'NOT_UNIQUE'):
   canary_game([wanted,wanted],[],set())

 def test_closed_canary_guard_precedes_any_scientific_call(self):
  with tempfile.TemporaryDirectory() as tmp:
   d=Path(tmp);(d/'CANARY_REMAINDER_GATE.json').write_text(json.dumps({'decision':'STOP_NO_VALID_CANARY'}))
   with patch.object(run_worker,'D',d),patch.object(run_worker,'load_sources') as sources,patch.object(run_worker,'game_params') as fits,patch.object(run_worker,'generation') as sampler:
    with self.assertRaisesRegex(RuntimeError,'REGISTERED_CANARY_CLOSED'):
     run_worker.canary_or_full('canary')
    sources.assert_not_called();fits.assert_not_called();sampler.assert_not_called()

 def test_failed_repair_canary_stops_before_any_second_game(self):
  # All model/data entry points mocked: controller behavior only, no NFL fit.
  with tempfile.TemporaryDirectory() as tmp:
   d=Path(tmp);private=d/'private';private.mkdir();(private/'frozen_startup_prior.json').write_text('{}')
   game=dict(native_game_id=run_worker.CANARY_NATIVE_GAME_ID)
   games=[game,dict(native_game_id='different_game')]
   store=SimpleNamespace(classification={},body_bindings=[])
   with patch.multiple(run_worker,D=d,PRIVATE=private,RAW=private/'samples'),patch.object(run_worker,'verify_freeze',return_value={}),patch.object(run_worker,'verify_private_inputs',return_value=[]),patch.object(run_worker,'storage_guard',return_value={}),patch.object(run_worker,'load_context',return_value=(games,[])),patch.object(run_worker,'load_sources',return_value=store),patch.object(run_worker,'restore_origin',return_value=object()),patch.object(run_worker,'prior_to_record',return_value={}),patch.object(run_worker,'begin_attempt',return_value=d/'attempt'),patch.object(run_worker,'progress'),patch.object(run_worker,'game_params',side_effect=RuntimeError('PROVIDER_CONDITIONING_FAILED;NO_RETRY')) as fits,patch.object(run_worker,'generation') as sampler:
    with self.assertRaisesRegex(RuntimeError,'PROVIDER_CONDITIONING_FAILED'):
     run_worker.canary_or_full('canary')
    self.assertEqual(fits.call_count,1);self.assertIs(fits.call_args.args[2],game);sampler.assert_not_called()
    self.assertTrue((d/('STOP_'+run_worker.CANARY_NATIVE_GAME_ID+'.json')).exists())

 def test_mutation_binds_retained_native_game_and_exact_input_hashes(self):
  selected=dict(native_game_id='retained_game',game_origin_key='source_origin',native_cutoff_utc='native',source_schedule_cutoff_utc='source',model_cutoff_utc='effective')
  row=dict(native_game_id='retained_game',source_game_origin_key='source_origin',input_design_SHA256='design')
  inputs=[dict(private_role='fixture.json',bytes=2,SHA256='fixture_hash')];sources=[dict(SHA256='source_hash')]
  freeze=dict(actual_private_inputs_reopened=inputs)
  record=dict(native_game_id='retained_game',native_cutoff_utc='native',archived_schedule_cutoff_utc='source',effective_cutoff_utc='effective',consumed_design_SHA256='design',replay_input_bindings=dict(private_inputs=inputs,source_bodies=sources))
  kept=SimpleNamespace(fit_record=record,metadata=dict(game_id='retained_game',origin='effective'))
  games=[dict(native_game_id='different_game'),selected]
  self.assertIs(retained_mutation_game(games,row,kept,freeze,sources),selected)
  with self.assertRaisesRegex(ValueError,'INPUT_BINDINGS_MISMATCH'):
   retained_mutation_game(games,row,kept,freeze,[dict(SHA256='changed')])
  with self.assertRaisesRegex(ValueError,'DESIGN_HASH_MISMATCH'):
   retained_mutation_game(games,dict(row,input_design_SHA256='different'),kept,freeze,sources)
  record['native_game_id']='different_game'
  with self.assertRaisesRegex(ValueError,'GAME_ID_MISMATCH'):
   retained_mutation_game(games,row,kept,freeze,sources)

 def test_frozen_input_check_reopens_actual_bytes(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);body=b'{}';(root/'fixture.json').write_bytes(body)
   info=dict(private_role='fixture.json',bytes=len(body),SHA256=hashlib.sha256(body).hexdigest())
   freeze=dict(actual_private_inputs_reopened=[info])
   self.assertEqual(verify_private_inputs(freeze,root),[info])
   (root/'fixture.json').write_bytes(b'[]')
   with self.assertRaisesRegex(ValueError,'BODY_MISMATCH'):
    verify_private_inputs(freeze,root)

 def test_mutation_prior_binds_all_retained_parameters_before_restore(self):
  prior=dict(design_SHA256='same_design',parameters=dict(shape=2.0))
  kept=SimpleNamespace(fit_record=dict(earlier_prior=prior))
  with patch.object(run_worker,'restore_origin',return_value='restored') as restore,patch.object(run_worker,'game_params') as fits,patch.object(run_worker,'generation') as sampler:
   with self.assertRaisesRegex(ValueError,'STARTUP_PRIOR_MISMATCH'):
    restore_retained_prior(object(),dict(prior,parameters=dict(shape=3.0)),kept)
   restore.assert_not_called();fits.assert_not_called();sampler.assert_not_called()
   self.assertEqual(restore_retained_prior('store',dict(prior),kept),'restored')
   restore.assert_called_once_with('store',prior)

 def test_failed_game_record_path_is_a_path(self):
  p=failure_record_path('2026_04_DET_CAR')
  self.assertIsInstance(p,Path);self.assertEqual(p.name,'STOP_2026_04_DET_CAR.json')
  with self.assertRaises(ValueError):failure_record_path('../escape')

 def test_zero_anchor_is_known_and_null_is_unavailable(self):
  t=team('A');a={t.actor_ids[0]:{'pass_att':0.,'rec':None}}
  records,missing=_targets(t,a,{},CORE)
  self.assertEqual(len(records),1);self.assertEqual(records[0]['value'],0.)
  self.assertEqual([r['category'] for r in missing],['rec'])

 def test_no_offer_product_does_not_become_other_categories(self):
  c=dict(case_id='fixture',identity=dict(category='rec',season=2026,week=4,game_id='fixture',player_id='fixture',line=.5,venue='fixture',position='TE'),player_game_key='fixture',game_origin_key='fixture',canonical_case_key='fixture')
  o=dict(case_id='fixture',actual=0.,outcome_version='fixture')
  self.assertEqual(build_raw_grades([c],[o],{'ANYTIME_TD_NO_MATCHING_MARKET':[]}),[])

 def test_codec_reopens_dp_moments_and_full_fitted_state(self):
  # Deterministic numeric codec fixture, not sampled/fictional NFL evidence.
  teams=(team('A'),team('B'));arrays={};means={};variances={};meta={}
  v=np.linspace(0.,2.,TRAJECTORIES).reshape(-1,1)
  for ti,t in enumerate(teams):
   prefix=f'team{ti}/'
   for field in (*COUNT_FIELDS,*CHILD_FIELDS,'rush_rec_yd'):
    arrays[prefix+field]=np.zeros((TRAJECTORIES,1),dtype=np.int64)
    means[prefix+field]=v.copy();variances[prefix+field]=np.ones_like(v)*.75
   meta[prefix]=dict(team_id=t.team_id,actor_ids=t.actor_ids,other_index=0,child_columns={f:[0] for f in CHILD_FIELDS},unavailable_child_columns={f:[] for f in CHILD_FIELDS},rush_rec_yd_columns=[0],anytime_td_columns=[0])
  result=GameSamples(arrays,dict(trajectories=TRAJECTORIES,teams=meta,scope='DETERMINISTIC_CODEC_FIXTURE_NOT_A_FORECAST'),means,variances)
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'fixture.zip';receipt=write_replay_bundle(p,result,teams,None,{'scope':'fixture'})
   kept=reopen_replay_bundle(p,receipt['SHA256'])
   self.assertTrue(np.array_equal(kept.dp_moments['team0/rec']['mean'],v.mean(axis=0)))
   self.assertTrue(np.array_equal(kept.dp_moments['team0/rec']['conditional_mean_variance'],v.var(axis=0)))
   self.assertEqual(kept.teams[0].actor_ids,teams[0].actor_ids)
   self.assertTrue(np.array_equal(kept.teams[0].catch_laws[0][0].gains,teams[0].catch_laws[0][0].gains))
   self.assertTrue(np.array_equal(kept.arrays['team1/rec'],arrays['team1/rec']))
   with self.assertRaises(ValueError):reopen_replay_bundle(p,'0'*64)

if __name__=='__main__':unittest.main()
