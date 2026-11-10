import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import pandas as pd
from data_v2 import History
from receiving_priority_c03 import memberships

class PriorityTests(unittest.TestCase):
 def setup_data(self):
  past=[dict(player_id='00-0000001',position='WR',available=5.,game_id='past1',targets=4.,kickoff=1.),dict(player_id='00-0000002',position='TE',available=6.,game_id='past2',targets=0.,kickoff=2.)]
  q=[dict(player_id='00-0000001',position='WR',season=2026,week=2,game_id='future1'),dict(player_id='00-0000002',position='TE',season=2026,week=2,game_id='future1'),dict(player_id='00-0000003',position='WR',season=2026,week=2,game_id='future2')]
  g=pd.DataFrame([dict(season=2026,week=2,kickoff=10.)]);return past,q,g
 def test_future_mutation_and_zero(self):
  past,q,g=self.setup_data();a=memberships(q,History(pd.DataFrame(past),'player_id'),g)
  future=dict(player_id='00-0000001',position='WR',available=15.,game_id='later',targets=100.,kickoff=11.)
  b=memberships(q,History(pd.DataFrame(past+[future]),'player_id'),g);self.assertEqual(a,b)
  self.assertTrue(a[0]['profiling_priority']);self.assertFalse(a[1]['profiling_priority']);self.assertEqual(a[1]['reference_expected_targets'],0.)
  self.assertEqual(a[2]['reference_fallback'],'EARLIER_ROLE_MEAN');self.assertEqual(a[2]['reference_expected_targets'],4.)
 def test_offer_priority_separate_from_top20(self):
  past,q,g=self.setup_data();q[2]['qualified_offer']=True
  a=memberships(q,History(pd.DataFrame(past),'player_id'),g)
  self.assertTrue(a[2]['profiling_priority']);self.assertIn('TIMING_UNVERIFIED',a[2]['priority_reason'])
  self.assertEqual(len(a),3);self.assertTrue(all(x['top20_expected_targets'] for x in a))
 def test_top20_limit_and_native_id_ties(self):
  past,q,g=self.setup_data();q=[dict(player_id=f'00-{i:07}',position='WR',season=2026,week=2,game_id='future') for i in range(1,26)]
  a=memberships(q,History(pd.DataFrame(past),'player_id'),g)
  self.assertEqual(sum(x['top20_expected_targets'] for x in a),20)
  # Player2 has observed zero history; it must not inherit the positive prior.
  self.assertEqual([x['player_id'] for x in a if x['top20_expected_targets']],[f'00-{i:07}' for i in [1]+list(range(3,22))])

if __name__=='__main__':unittest.main()
