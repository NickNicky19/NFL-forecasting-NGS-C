"""Metadata/mock controller tests; no NFL optimizer or sampler."""
import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import shared_game_sim01_repair as r

class RepairControllerContracts(unittest.TestCase):
 def test_original_deadline_is_not_reset(self):
  import datetime
  with patch.object(r,'now',return_value=datetime.datetime(2026,11,23,0,5,21,tzinfo=datetime.timezone.utc)):
   with self.assertRaisesRegex(RuntimeError,'FIXED_DEADLINE_EXPIRED'):
    r.deadline_guard()

 def test_attempt_is_separate_and_cannot_repeat(self):
  with tempfile.TemporaryDirectory() as td:
   d=Path(td);old=d/'old';old.mkdir();legacy=old/'STOP_2026_04_DET_CAR.json';legacy.write_text('{"old":"failure"}')
   original=legacy.read_bytes()
   x={'counters':{'stages':0,'iterations':0,'evaluations':0,'game_attempts':0}}
   with patch.multiple(r,D=d/'repair',OLD=old,LEDGER=d/'repair/LEDGER.json'),patch.object(r,'initialize',side_effect=lambda:json.loads((d/'repair/LEDGER.json').read_text()) if (d/'repair/LEDGER.json').exists() else x),patch.object(r,'binding',side_effect=lambda p:{'path':p.name,'SHA256':r.sha(p)}):
    a=r.Attempt({'native_game_id':r.GAME},'canary')
    with self.assertRaisesRegex(RuntimeError,'ALREADY_EXISTS'):
     r.Attempt({'native_game_id':r.GAME},'canary')
    a({'event':'STAGE_STARTED','stage':'CORE','initial':[1.],'initial_SHA256':'initial'})
    a({'event':'BEFORE_OBJECTIVE','stage':'CORE'})
    a({'event':'ACCEPTED_ITERATION','stage':'CORE'})
    a({'event':'CHECKPOINT','stage':'CORE','last_accepted':{'vector':[2.]}})
    kept=json.loads(a.path.read_text())
    self.assertEqual(kept['stage_starts']['CORE']['initial'],[1.])
    self.assertEqual(kept['stage_checkpoints']['CORE'][0]['last_accepted']['vector'],[2.])
    a.fail(RuntimeError('test_failure'))
    self.assertTrue((d/'repair/PACKAGE_STOP.json').exists())
   self.assertEqual(legacy.read_bytes(),original)

 def test_global_evaluation_count_refuses_work_without_reset(self):
  with tempfile.TemporaryDirectory() as td:
   d=Path(td);x={'counters':{'stages':0,'iterations':0,'evaluations':152000,'game_attempts':0}}
   with patch.multiple(r,D=d,OLD=d/'old',LEDGER=d/'LEDGER.json'),patch.object(r,'initialize',return_value=x):
    a=r.Attempt({'native_game_id':r.GAME},'canary')
    with self.assertRaisesRegex(RuntimeError,'AGGREGATE_EVALUATION_LIMIT'):
     a({'event':'BEFORE_OBJECTIVE','stage':'CORE'})
    self.assertEqual(x['counters']['evaluations'],152000)

if __name__=='__main__':unittest.main()
