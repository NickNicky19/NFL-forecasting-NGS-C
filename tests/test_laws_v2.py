import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import numpy as np
from laws_v2 import *
class Laws(unittest.TestCase):
 def test_prior_support_and_crps_analytic(self):
  for kind,y in [('count',np.array([0,1,3.])),('signed',np.array([-3,0,7.]))]:
   p=Prior(y,kind);x=np.arange(-1000,1001);mass=np.array([p.pmf(k) for k in x]);self.assertAlmostEqual(mass.sum(),1.,12)
   self.assertAlmostEqual(float(p.abs_to(2)),float(mass@abs(x-2)),10)
   self.assertAlmostEqual(p.pair_abs(),float((mass[:,None]*mass[None,:]*abs(x[:,None]-x[None,:])).sum()),9)
 def test_mixture_crps_matches_integer_cdf_sum(self):
  p=Prior(np.array([-2.,3.,8.]),'signed');law=Law([-2,3,8],[.2,.5,.3],p)
  exact=sum((law.cdf(k)-float(4<=k))**2 for k in range(-500,501));self.assertAlmostEqual(law.crps(4),exact,10)
 def test_complements_whole_half_and_signed(self):
  law=Law([0,1,2],[.1,.3,.6],Prior(np.array([0.,1,2]),'count'))
  for line in [-.5,.5,1,1.5,3]:
   p=law.probability(line);self.assertAlmostEqual(sum(p.values()),1.,12)
  self.assertGreater(law.probability(1)['push'],0);self.assertEqual(law.probability(1.5)['push'],0.)
 def test_threshold_monotonic_fitting(self):
  rng=np.random.default_rng(5);x=rng.normal(size=(80,4));y=np.maximum(0,np.round(2+x[:,0]));grid=np.array([.5,1.5,2.5,3.5])
  from threadpoolctl import threadpool_limits
  for fam in ['LOGIT','MONOTONE_HGB']:
   with threadpool_limits(limits=1):m=ThresholdModel(fam,False,grid).fit(x,y);p=m.cdfs(x[:10],grid)
   self.assertTrue((np.diff(p,axis=1)>=-1e-12).all());self.assertTrue(((p>=0)&(p<=1)).all())
if __name__=='__main__':unittest.main()
