"""Software contracts only: no NFL fitter, optimizer or trajectory generator."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from shared_game_sim01_kernel import TeamParameters,GainTupleLaw,GameSamples,COUNT_FIELDS,CHILD_FIELDS,TRAJECTORIES
from shared_game_sim01_condition import _targets,CORE
from shared_game_sim01_retention import write_replay_bundle,reopen_replay_bundle
from shared_game_sim01_metrics import build_raw_grades
from shared_game_sim01_run import failure_record_path

def team(name):
 law=GainTupleLaw(np.array([-1,2]),np.array([0,1]),np.array([.5,.5]))
 kneel=GainTupleLaw(np.array([-1]),np.array([0]),np.array([1.]))
 return TeamParameters(name,('__OTHER__::'+name,),0,(0,),(0,),(0,),60.,np.ones(5),np.ones(1),np.array([[1.,0.]]),np.array([[[1.,1.,1.],[0.,1.,1.]]]),np.ones(1),((law,),),(law,),(law,),(kneel,))

class SharedSimContracts(unittest.TestCase):
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
