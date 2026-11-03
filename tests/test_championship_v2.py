import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from abc_championship_v2 import status,summary
class CommonScorer(unittest.TestCase):
 def row(self,side,y,l):return dict(selected_side=side,actual=y,line=l,appearance='PLAYED',status='WIN',comparator='STRICT_OVER_UNDER',season=2026,week=2,game_id='fixture',player_id='fixture')
 def test_exact_boundary(self):
  self.assertEqual(status(self.row('OVER',20,19.5)),'WIN');self.assertEqual(status(self.row('OVER',19,19.5)),'LOSS');self.assertEqual(status(self.row('UNDER',-2,-2)),'PUSH')
 def test_weighted_combined_and_unknown(self):
  rr=[self.row('OVER',20,19.5),self.row('OVER',19,19.5),self.row('UNDER',0,.5)];[r.update(status=status(r)) for r in rr];s=summary(rr);self.assertEqual(s['COMBINED']['rate'],2/3);self.assertEqual(s['OVER']['decided'],2)
 def test_unavailable_not_loss(self):
  r=self.row(None,None,19.5)|dict(status='UNAVAILABLE_FORECAST',appearance='UNKNOWN');s=summary([r]);self.assertEqual(s['unavailable'],1);self.assertIsNone(s['COMBINED']['rate'])
