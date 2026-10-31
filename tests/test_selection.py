import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import selection as s

class SelectionTests(unittest.TestCase):
 def test_integer_half_boundaries(self):
  self.assertEqual(s.grade('OVER',20,19.5),'WIN');self.assertEqual(s.grade('OVER',19,19.5),'LOSS')
  self.assertEqual(s.grade('UNDER',49,49.5),'WIN');self.assertEqual(s.grade('UNDER',50,49.5),'LOSS')
 def test_whole_signed_zero_and_unknown(self):
  self.assertEqual(s.grade('OVER',20,20),'PUSH');self.assertEqual(s.grade('UNDER',-2,.5),'WIN')
  self.assertEqual(s.grade('UNDER',0,.5),'WIN');self.assertEqual(s.grade('UNDER',None,.5,'UNKNOWN'),'UNKNOWN')
 def test_direction_and_complements(self):
  self.assertEqual(s.point_side(19.5,19.5),'ABSTAIN');self.assertEqual(s.probability_side(None,None,None),'UNAVAILABLE')
  self.assertEqual(s.probability_side(.5,0,.5),'ABSTAIN');self.assertEqual(s.brier(.5,0,.5,20,19.5),.25)
  with self.assertRaises(ValueError):s.probability_side(.5,.5,.5)
 def test_combined_weighting(self):
  rows=[{'side':'OVER','grade':'WIN'}]+[{'side':'UNDER','grade':'LOSS'}]*3
  self.assertEqual(s.counts(rows)['COMBINED']['rate'],.25);self.assertIsNone(s.counts([])['OVER']['rate'])
if __name__=='__main__':unittest.main()
