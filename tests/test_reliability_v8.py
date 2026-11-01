"""Software-only joint/ranking/calibration boundaries, never NFL fit counts."""
import copy,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import numpy as np
from laws_v2 import Prior,Law
from safe_models_v4 import prior_data,law_data
from workload_link_v8 import linked_law,forecast_bins
from diagnose_v8 import probability,metrics,rank_diagnostic

def joint():
    return dict(imputation=[0],prior=prior_data(Prior(np.array([0,10,20,50,60]),'signed')),trees=[dict(left=[-1],right=[-1],feature=[0],threshold=[0],joint={'0':[[1,10,9],[2,50,1]]}),dict(left=[-1],right=[-1],feature=[0],threshold=[0],joint={'0':[[1,20,1],[2,60,9]]})],global_bins={str(b):dict(values=[25],counts=[1],empty_global_bin_fallback=b==5) for b in range(1,6)})
def row(i,p=.8,status='WIN',side='OVER'):
    return dict(record_kind='FICTIONAL_TEST',record_id=str(i),offer_id='FICTIONAL-'+str(i),category='pass_yd',game_id='FICTIONAL-GAME-'+str(i),player_id='FICTIONAL-PLAYER-'+str(i),method_id='P2_LAW',venue='pinnacle',week=2,kickoff_UTC='2026-09-20T17:00:00Z',decision_UTC='2026-09-20T17:00:00Z',source_snapshot_clocks={'OVER':'2026-09-20T16:00:00Z','UNDER':'2026-09-20T16:00:00Z'},position='QB',selected_side=side,line=19.5,actual=20 if status=='WIN' else None if status=='UNKNOWN_PARTICIPATION' else 0,status=status,p_over=p,p_under=1-p,p_push=0,_confidence=p,_ps={'over':p,'under':1-p,'push':0},_provider_void=False,appearance='UNKNOWN' if status=='UNKNOWN_PARTICIPATION' else 'PLAYED')

class ReliabilityMechanism(unittest.TestCase):
    def test_pool_joint_mass_before_conditioning(self):
        j=joint();law,m=linked_law(j,[0]);self.assertEqual(m['bin_weights'],[0,.5,.5,0,0,0]);self.assertAlmostEqual(law.mean(),34.25)
        changed,mm=linked_law(j,[0],[0,.8,.2,0,0,0]);self.assertAlmostEqual(changed.mean(),20.57);self.assertEqual(mm['leaf_missing_bin_forecast_mass'],0)
    def test_zero_attempt_pointmass_and_fallbacks(self):
        j=joint();zero,_=linked_law(j,[0],[1,0,0,0,0,0]);self.assertEqual(zero.mean(),0);self.assertEqual(zero.probability(0),{'under':0,'push':1,'over':0})
        law,m=linked_law(j,[0],[0,0,0,0,0,1]);self.assertEqual(m['leaf_missing_bin_forecast_mass'],1);self.assertEqual(m['empty_global_bin_forecast_mass'],1)
        self.assertAlmostEqual(sum(law.probability(25).values()),1)
    def test_attempt_bin_forecast_integrates_full_count_support(self):
        n=Law([0,10,20,30,40,50],[1]*6,Prior(np.array([0,10,20,30,40,50]),'count'));q=forecast_bins(n);self.assertAlmostEqual(sum(q),1);self.assertTrue(all(q>=0))
    def test_target_attempts_and_outcomes_unnecessary_to_inference(self):
        j=joint();a,_=linked_law(j,[0],[0,.8,.2,0,0,0]);j['unused_target_actual_attempts']=999;j['unused_future_yards']=999;b,_=linked_law(j,[0],[0,.8,.2,0,0,0]);self.assertEqual(law_data(a),law_data(b))
    def test_p1_mean_uses_own_side_even_below_half(self):
        law=Law([0,100],[9,1],Prior(np.array([0,100]),'signed'));r=dict(method_id='P1_MEAN',category='pass_yd',game_id='FICTIONAL',player_id='FICTIONAL',selected_side='OVER',line=5.5);bank={'references':{'pass_yd|FICTIONAL|FICTIONAL':{'law':law_data(law)}}};p=probability(r,bank);self.assertLess(p['over'],.5)
    def test_unknown_is_not_a_loss_and_expected_wins_uses_same_known_mask(self):
        m=metrics([row(1,p=.8),row(2,p=.7,status='LOSS'),row(3,p=.99,status='UNKNOWN_PARTICIPATION')]);self.assertEqual(m['decided'],2);self.assertEqual(m['wins'],1);self.assertEqual(m['expected_wins'],1.5)
    def test_rank_ties_unknowns_and_player_overlap_are_outcome_blind(self):
        rr=[row(1,.8),row(2,.8,status='UNKNOWN_PARTICIPATION'),row(3,.7)];rr[2]['player_id']=rr[0]['player_id']
        with patch('diagnose_v8.write'):
            before,_=rank_diagnostic(rr,{},{});mut=copy.deepcopy(rr);mut[0].update(actual=0,status='LOSS');mut[1].update(actual=100,status='WIN');after,_=rank_diagnostic(mut,{},{});
        identity=lambda rows:[(r['diagnostic_id'],r['rank'],r['record_id']) for r in rows]
        self.assertEqual(identity(before),identity(after));self.assertTrue(any(r['status']=='UNKNOWN_PARTICIPATION' for r in before));q=[r for r in before if r['diagnostic_id']=='LRL8-pinnacle-W2-P2_LAW-GLOBAL-ALL-MIXED-K6'];self.assertEqual([r['record_id'] for r in q],['1','2'])

if __name__=='__main__':unittest.main()
