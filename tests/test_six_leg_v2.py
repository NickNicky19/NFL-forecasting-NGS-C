import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from six_leg_v2 import *
class Entries(unittest.TestCase):
 def test_missing_quote_and_no_forced_entry(self):
  r=qualify([],None,'2026-10-31T20:00:00Z');self.assertEqual(r['state'],'NO_QUALIFIED_SIX_LEG_ENTRY');self.assertEqual(r['entries'],0)
 def test_suspended_sides_and_late_records(self):
  base=dict(offer_id='x',venue='v',product='p',player_id='player',game_id='g',category='rec',line=3.5,side='UNDER',observed_at_UTC='2026-01-01T00:00:00Z',persisted_at_UTC='2026-01-01T00:00:00Z',settlement_contract='c',rights_status='PUBLIC_RETENTION_QUALIFIED',lifecycle='SUSPENDED',offered_sides=['OVER'],p_win=.9)
  self.assertEqual(qualify([base]*6,None,'2026-01-02T00:00:00Z')['eligible_candidates'],0)
 def test_independence_is_only_reference_and_overlap(self):
  self.assertAlmostEqual(independent_all_win([.5]*6),1/64);self.assertEqual(overlap(['a','b'],['b','c'])['shared_legs'],1)
if __name__=='__main__':unittest.main()
