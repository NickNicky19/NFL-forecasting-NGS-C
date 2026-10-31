import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import pandas as pd,numpy as np
from data_v2 import History,vector,DAY
class Timing(unittest.TestCase):
 def test_target_future_outcomes_and_workload_do_not_enter_prefix(self):
  rows=[]
  for day in [70,80,90,100,110]:
   rows.append(dict(player_id='fixture',position='QB',team='A',opponent_team='B',home_team='A',week=7,game_id=str(day),kickoff=day*DAY,available=(day+7)*DAY,values={'pass_cmp':float(day)},attempts=30.,carries=2.,targets=0.))
  d=pd.DataFrame(rows);team=pd.DataFrame([dict(team='A',game_id=str(day),kickoff=day*DAY,available=(day+7)*DAY,attempts=30.,carries=20.,sacks_suffered=2.,allowed_passing_yards=200.,allowed_attempts=30.,allowed_rushing_yards=80.,allowed_carries=20.,allowed_receiving_yards=200.,allowed_targets=30.) for day in [70,80,90,100,110]])
  q=rows[3];h=History(d,'player_id');th=History(team,'team');a=vector(q,'pass_cmp',h,th,'E0_DEF')
  for i in d.index[d.kickoff>=100*DAY]:d.at[i,'values']={'pass_cmp':9999.};d.at[i,'attempts']=9999.
  team.loc[team.kickoff>=100*DAY,'attempts']=9999.
  b=vector(q,'pass_cmp',History(d,'player_id'),History(team,'team'),'E0_DEF');np.testing.assert_equal(a,b)
  q2=q|{'kickoff':98*DAY};self.assertEqual(len(h.before('fixture',97*DAY)),2);self.assertEqual(len(h.before('fixture',97*DAY+1)),3)
if __name__=='__main__':unittest.main()
