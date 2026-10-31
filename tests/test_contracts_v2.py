import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from contracts_v2 import *
class Contracts(unittest.TestCase):
 def base(self):return {k:0 for k in WEIGHTS if k not in RARE}|{'fumble_recovery_tds':0,'special_teams_tds':0}
 def test_chart_exact_and_negative(self):
  r=self.base()|{'passing_yards':250,'passing_tds':2,'passing_interceptions':1,'rushing_yards':-2,'receptions':3,'receiving_yards':20,'fumbles_lost_total':1}
  self.assertEqual(chart(r,True),(20.8,'SUPPORTED_EXPLICIT_ZERO_SUBSET'))
  self.assertEqual(chart(self.base()|{'rushing_yards':-1},True)[0],-.1)
 def test_chart_unknown_rare_and_missing(self):
  self.assertIsNone(chart(self.base()|{'special_teams_tds':1},True)[0]);r=self.base();del r['receptions'];self.assertIsNone(chart(r,True)[0])
 def test_chart_unique_lost_and_two_point(self):
  r=self.base()|{'fumbles_lost_total':1,'sack_fumbles_lost':1,'receiving_fumbles_lost':1,'receiving_2pt_conversions':1}
  self.assertEqual(chart(r,True)[0],1.);self.assertEqual(r['receptions'],0)
 def test_anytime_is_event_not_passing_or_count(self):
  self.assertEqual(target({'rushing_tds':0,'receiving_tds':0,'passing_tds':4},'anytime_td'),0)
  self.assertEqual(target({'rushing_tds':2,'receiving_tds':1},'anytime_td'),1)
 def test_boundaries(self):
  self.assertEqual(grade(6,6,'OVER'),'PUSH');self.assertEqual(grade(6,6.5,'UNDER'),'WIN');self.assertEqual(grade(7,6,'OVER'),'WIN')
  self.assertEqual(thresholds_for_line(-.02,50),(-2,-1,True));self.assertEqual(thresholds_for_line(19.5,1),(19,19,False))
if __name__=='__main__':unittest.main()
