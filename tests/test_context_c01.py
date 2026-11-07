import sys,unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from context_features_c01 import Prefix,depth_bin,down_bin
from context_experiment_c01 import count_probs,pooled_fit,pooled_mu

class ContextContracts(unittest.TestCase):
 def test_context_labels_are_not_alignment(self):
  self.assertEqual([depth_bin(x) for x in [-2,0,9,10,19,20,None,float('nan')]],[0,1,1,2,2,3,4,4])
  self.assertEqual([down_bin(x) for x in [1,4,0,None]],[0,3,4,4])
 def test_eligible_prefix_strict_cutoff_and_last_by_game_time(self):
  rows=[dict(player='P',game_id=str(i),kickoff=i*10,available=i*10+7) for i in range(5)]
  p=Prefix(rows,'player');self.assertEqual([r['game_id'] for r in p.before('P',37,3)],['0','1','2'])
  changed=rows+[dict(player='P',game_id='FUTURE',kickoff=100,available=107)]
  self.assertEqual(p.before('P',37,3),Prefix(changed,'player').before('P',37,3))
 def test_exact_count_line_and_integer_push(self):
  p=count_probs(4.,2.5);q=count_probs(4.,5.5);self.assertGreater(p['over'],q['over']);self.assertEqual(p['push'],0.)
  z=count_probs(4.,4.);self.assertGreater(z['push'],0.)
  for x in [p,q,z]:self.assertAlmostEqual(sum(x.values()),1.);self.assertGreaterEqual(min(x.values()),0.)
 def test_safe_personalization_inference_and_unseen_player(self):
  x=np.array([[0.],[1.],[2.],[3.],[4.],[5.]]);y=np.array([0,1,1,2,2,3.]);ids=np.array([['A','T','D']]*3+[['B','T','E']]*3)
  m=pooled_fit(x,y,ids,True);p=pooled_mu(m,x,ids);self.assertTrue(np.isfinite(p).all());self.assertTrue((p>0).all())
  q=pooled_mu(m,x[:1],np.array([['ROOKIE','NEW','NEW']]));self.assertTrue(np.isfinite(q[0]))
if __name__=='__main__':unittest.main()
