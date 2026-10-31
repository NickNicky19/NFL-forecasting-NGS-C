import sys,unittest,math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import numpy as np
from laws_v2 import Prior,Law
class Tail(unittest.TestCase):
 def test_positive_tail_not_false_zero(self):
  p=Prior(np.zeros(100),'count');self.assertGreater(p.pmf(15),0);self.assertTrue(math.isfinite(p.logpmf(15)))
  law=Law([0],[1.],p);self.assertTrue(math.isfinite(law.logpmf(2000)))
 def test_true_empty_history_impossible_loss_remains(self):
  p=Prior(np.array([]),'count');law=Law([],[],p);self.assertEqual(law.logpmf(1),-math.inf)
if __name__=='__main__':unittest.main()
