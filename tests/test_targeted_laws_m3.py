"""Scientific support/boundary checks independent of the optional fit runtime."""
import math
import unittest
import numpy as np
from scipy.stats import nbinom, t
from targeted_laws_m3 import NegativeBinomialLaw,DiscretizedStudentTLaw,deterministic_fixtures

class TargetedLawSupport(unittest.TestCase):
 def test_count_parameterization_and_full_tail(self):
  law=NegativeBinomialLaw(2.5,.7)
  self.assertAlmostEqual(law.mean(),2.5*.7/.3,places=12)
  self.assertAlmostEqual(law.variance(),2.5*.7/.3**2,places=12)
  self.assertEqual(law.pmf(-1),0)
  self.assertGreater(law.sf(200),0)
  self.assertAlmostEqual(sum(law.pmf(k) for k in range(100))+law.sf(99),1,places=12)
  self.assertAlmostEqual(law.pmf(3),nbinom.pmf(3,2.5,.3),places=12)
 def test_integer_push_and_half_point(self):
  for law in [NegativeBinomialLaw(2,.6),DiscretizedStudentTLaw(5,-2,3)]:
   p=law.probability(0)
   self.assertAlmostEqual(p['push'],law.pmf(0),places=12)
   self.assertAlmostEqual(sum(p.values()),1,places=12)
   q=law.probability(.5)
   self.assertEqual(q['push'],0)
   self.assertAlmostEqual(q['under'],law.cdf(0),places=12)
 def test_signed_yard_mass_is_bin_not_density(self):
  law=DiscretizedStudentTLaw(5,-2,3)
  self.assertGreater(law.pmf(-4),0)
  self.assertAlmostEqual(law.pmf(-4),t.cdf(-3.5,5,loc=-2,scale=3)-t.cdf(-4.5,5,loc=-2,scale=3),places=12)
  self.assertAlmostEqual(sum(law.pmf(k) for k in range(-100,101))+law.cdf(-101)+law.sf(100),1,places=12)
 def test_monotone_and_finite_variance_scope(self):
  law=DiscretizedStudentTLaw(2.5,0,.2)
  self.assertTrue(np.all(np.diff([law.cdf(k) for k in range(-20,21)])>=0))
  self.assertIsNone(DiscretizedStudentTLaw(2,0,1).variance())
  self.assertIsNone(DiscretizedStudentTLaw(1,0,1).mean())
 def test_deterministic_boundary_fixture(self):
  self.assertIsInstance(deterministic_fixtures(),dict)
if __name__=='__main__':unittest.main()
