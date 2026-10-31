import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import study as s
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

class LeakageTests(unittest.TestCase):
 def setUp(self):
  self.row=dict(player_id='00-0000001',position='QB',kickoff=100*s.DAY)
  self.raw=pd.DataFrame([dict(player_id='00-0000001',game_id=str(i),kickoff=i*s.DAY,available=(i+7)*s.DAY,completions=float(i)) for i in [80,90,100,110]])
  self.ngs=pd.DataFrame([dict(player_gsis_id='00-0000001',game_id=str(i),kickoff=i*s.DAY,available=(i+7)*s.DAY,avg_intended_air_yards=7.,avg_time_to_throw=2.5,aggressiveness=12.,attempts=30.) for i in [80,90,100,110]])
 def vector(self,raw,ngs):return s.features(self.row,'pass_cmp',s.History(raw,'player_id'),s.History(ngs,'player_gsis_id'),'C2')
 def test_target_and_future_ngs_invariant(self):
  a=self.vector(self.raw,self.ngs);n=self.ngs.copy();n.loc[n.kickoff>=100*s.DAY,'avg_intended_air_yards']=9999
  n=pd.concat([n,n.iloc[[-1]].assign(available=200*s.DAY,game_id='future')]);np.testing.assert_equal(a,self.vector(self.raw,n))
 def test_target_and_later_outcomes_invariant(self):
  a=self.vector(self.raw,self.ngs);r=self.raw.copy();r.loc[r.kickoff>=100*s.DAY,'completions']=9999
  np.testing.assert_equal(a,self.vector(r,self.ngs))
 def test_seven_day_strict_boundary(self):
  h=s.History(self.raw,'player_id');self.assertEqual(len(h.before('00-0000001',97*s.DAY)),1)
  self.assertEqual(len(h.before('00-0000001',97*s.DAY+1)),2)
 def test_missing_not_zero_and_support_arms(self):
  empty=self.ngs.iloc[:0];a=self.vector(self.raw,empty);self.assertTrue(np.isnan(a[-1]));self.assertEqual(a[20],0.)
  h=s.History(self.raw,'player_id');n=s.History(self.ngs,'player_gsis_id');c0=s.features(self.row,'pass_cmp',h,n,'C0');c1=s.features(self.row,'pass_cmp',h,n,'C1');c2=s.features(self.row,'pass_cmp',h,n,'C2')
  np.testing.assert_equal(c0,c1[:20]);np.testing.assert_equal(c1,c2[:len(c1)])
 def test_training_only_imputation(self):
  x=np.array([[1.,np.nan],[3.,np.nan]]);m=s.impute_fit(x);np.testing.assert_equal(m,[2.,0.]);self.assertEqual(s.impute(np.array([[999.,np.nan]]),m)[0,1],0.)
 def test_forecast_invariant_to_future_rows(self):
  # Actual estimator inference, with training eligibility chosen before outcomes.
  rng=np.random.default_rng(2);x=rng.normal(size=(80,20));y=rng.normal(size=80);q=x[:2]
  avail=np.arange(100);cutoff=80;all_y=np.r_[y,[1.]*20]
  with threadpool_limits(limits=1):
   a,_=s.fit_predict(x,all_y[avail<cutoff],q,'pass_yd');all_y[80:]=9999;b,_=s.fit_predict(x,all_y[avail<cutoff],q,'pass_yd')
  np.testing.assert_equal(a,b)
 def test_paired_masks_and_sign(self):
  z=pd.DataFrame([dict(season=2023,week=1,game_id='g',player_id='p',position='QB',target='pass_cmp',actual=20.,point=p,arm=a) for a,p in [('C0',19.),('C2',17.)]])
  r=s.paired(z,'C0');self.assertEqual(r['delta'],2.);self.assertEqual(r['n'],1)

if __name__=='__main__':unittest.main()
