import copy
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from receiving_information_v10 import ReceivingInformation, team_projection
from predictive_information_c01 import probabilities


def fixture():
    players=[];teams=[]
    for i,(t,p) in enumerate(zip([10,10,10,20,20,30],[1,1,1,5,5,8])):
        base=dict(game_id='g'+str(i),team='T',kickoff=i*8*86400,available=(i*8+7)*86400,targets_complete=True,passing_complete=True,targets=t,attempts=20,completions=10+i)
        teams.append(base)
        players.append(dict(game_id=base['game_id'],player_id='p',team='T',available=base['available'],targets=p))
    return players,teams,dict(player_id='p',team='T',kickoff=40*86400)


class ReceivingInformationTests(unittest.TestCase):
    def test_true_target_exposure_weighting(self):
        p,t,q=fixture();support,value=ReceivingInformation(pd.DataFrame(p),pd.DataFrame(t)).share(q)
        self.assertEqual(support[:4],[5.,5.,70.,13.])
        self.assertAlmostEqual(value[0],.25)
        self.assertAlmostEqual(value[1],.25-.1)

    def test_absent_player_record_not_zero(self):
        p,t,q=fixture();p=[r for r in p if r['game_id']!='g4']
        support,value=ReceivingInformation(pd.DataFrame(p),pd.DataFrame(t)).share(q)
        self.assertEqual(support[1],4.)
        self.assertEqual(support[-1],1.)
        self.assertTrue(np.isnan(value).all())

    def test_target_future_stats_and_ngs_cannot_change_prefix(self):
        p,t,q=fixture();old=ReceivingInformation(pd.DataFrame(p),pd.DataFrame(t))
        expected=old.share(q),old.completion(q)
        p[-1].update(targets=999,target_game_NGS=999)
        t[-1].update(targets=999,completions=20,attempts=20,target_game_NGS=-999)
        new=ReceivingInformation(pd.DataFrame(p),pd.DataFrame(t))
        self.assertEqual(expected,(new.share(q),new.completion(q)))
        # Earlier changes may affect a later eligible prefix, not the earlier one.
        q2=dict(q,kickoff=48*86400)
        self.assertNotEqual(old.completion(q2),new.completion(q2))

    def test_exact_availability_boundary_excluded(self):
        p,t,q=fixture();q['kickoff']=t[4]['available']
        support,value=ReceivingInformation(pd.DataFrame(p),pd.DataFrame(t)).share(q)
        self.assertEqual(support[0],4.)
        self.assertTrue(np.isnan(value).all())

    def test_completion_prior_uses_earlier_passes_only(self):
        p,t,q=fixture();support,value=ReceivingInformation(pd.DataFrame(p),pd.DataFrame(t)).completion(q)
        # Five earlier games:60 completions/100 attempts; same earlier league prior.
        self.assertEqual(support[:2],[5.,100.])
        self.assertAlmostEqual(value[0],.6)

    def test_exact_line_push_and_monotonicity(self):
        model=dict(imputation=[0.],baseline=0.,trees=[dict(value=[0.,-1.,1.],feature_idx=[2,0,0],num_threshold=[2.,0.,0.],missing_go_to_left=[True,False,False],left=[1,0,0],right=[2,0,0],is_leaf=[False,True,True])])
        half=probabilities(model,[0.],2.5);whole=probabilities(model,[0.],3.)
        self.assertEqual(half['push'],0.)
        self.assertGreater(whole['push'],0.)
        self.assertAlmostEqual(sum(whole.values()),1.)
        self.assertEqual(probabilities(model,[0.],-.5),dict(under=0.,push=0.,over=1.))
        self.assertGreaterEqual(probabilities(model,[0.],-.5)['over'],probabilities(model,[0.],3.5)['over'])


if __name__=='__main__':unittest.main()
