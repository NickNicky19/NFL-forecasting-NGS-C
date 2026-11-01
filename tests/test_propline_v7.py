"""Fictional adapter fixtures; not NFL forecasts, offers, grades or victories."""
import copy,sys,unittest,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import numpy as np
from laws_v2 import Law,Prior
from propline_v7 import predict_offer

class ExactOfferAdapter(unittest.TestCase):
    def setUp(self):
        self.law=Law([-2,0,30,50,80],[1,2,3,3,1],Prior(np.array([-2,0,30,50,80]),'signed'))
        self.saved=dict(slot='FICTIONAL-SAVED',game_id='FICTIONAL-GAME',player_id='FICTIONAL-PLAYER',mean=40.25,median=30,actual=0,features=[1,None])
    def test_players_keep_distinct_exact_lines_and_recompute_law(self):
        a=predict_offer(dict(player_id='FICTIONAL-A',line=29.5),'P2_LAW',self.saved,self.law)[1]
        b=predict_offer(dict(player_id='FICTIONAL-B',line=50.5),'P2_LAW',self.saved,self.law)[1]
        self.assertEqual(a['probability_line'],29.5);self.assertEqual(b['probability_line'],50.5)
        self.assertGreater(a['p_over'],b['p_over']);self.assertLess(a['p_under'],b['p_under'])
        self.assertAlmostEqual(a['p_under']+a['p_push']+a['p_over'],1)
    def test_no_line_never_gets_grid_default_or_selected_side(self):
        for method in ['P1_MEAN','P1_MEDIAN','P2_LAW','P3_DIRECT','ALWAYS_OVER','ALWAYS_UNDER']:
            side,p=predict_offer(dict(line=None,grid=[49.5]),method,self.saved,self.law)
            self.assertIsNone(side);self.assertNotIn('probability_line',p)
    def test_typed_points_keep_own_direction_and_equality_abstains(self):
        self.assertEqual(predict_offer(dict(line=35.5),'P1_MEDIAN',self.saved)[0],'UNDER')
        self.assertEqual(predict_offer(dict(line=35.5),'P1_MEAN',self.saved)[0],'OVER')
        self.assertEqual(predict_offer(dict(line=30),'P1_MEDIAN',self.saved)[0],'ABSTAIN')
    def test_source_outcomes_resolution_and_future_ngs_never_change_inference(self):
        a=dict(line=29.5,actual_value=0,resolution='lost',home_score=0,away_score=0)
        b=copy.deepcopy(a);b.update(actual_value=999,resolution='won',home_score=99,away_score=99,target_game_ngs={'separation':999},future_ngs=[999])
        other=copy.deepcopy(self.saved);other.update(actual=999,target_game_ngs=999,later_outcomes=[999])
        for method in ['P1_MEAN','P1_MEDIAN','P2_LAW']:
            self.assertEqual(predict_offer(a,method,self.saved,self.law),predict_offer(b,method,other,self.law))
    def test_signed_lattice_whole_boundary_and_no_nearest_grid(self):
        for line in [-2,-.5,0,30,30.2,79.5]:
            p=predict_offer(dict(line=line),'P2_LAW',self.saved,self.law)[1]
            self.assertAlmostEqual(sum(p['p_'+s] for s in ['under','push','over']),1)
            self.assertEqual(p['probability_line'],line)
            self.assertEqual(p['p_push']>0,line==int(line))
        self.assertGreater(predict_offer(dict(line=30),'P2_LAW',self.saved,self.law)[1]['p_push'],.28)
    def test_direct_exact_cdf_flags_serialize_and_outcome_changes_are_inert(self):
        class NoFitCDF:
            thresholds=np.array([9,24,49])
            def cdfs(self,x,thresholds):return np.asarray([[(float(t)+1)/100 for t in thresholds]])
        model=NoFitCDF();base=predict_offer(dict(line=35.2),'P3_DIRECT',self.saved,direct_item=(model,self.saved))
        changed=self.saved|dict(actual=999,future_ngs=[999]);other=predict_offer(dict(line=35.2,resolution='won',actual_value=999),'P3_DIRECT',changed,direct_item=(model,changed))
        self.assertEqual(base,other);self.assertEqual(base[1]['probability_line'],35.2)
        self.assertEqual(type(base[1]['outside_training_threshold_range']),bool);json.dumps(base,allow_nan=False)

if __name__=='__main__':unittest.main()
