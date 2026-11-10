import copy,sys,unittest
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from receiving_defense_c03 import ReceivingDefense, FEATURE_NAMES, SUPPORT_NAMES, VALUE_NAMES, TEAMS
from context_features_c01 import Context
from data_v2 import DAY

class ReceivingDefenseTests(unittest.TestCase):
 def fixture(self):
  t=pd.Timestamp('2026-09-01T18:00Z').timestamp();game='2026_01_ATL_CAR'
  g=pd.DataFrame([dict(game_id=game,season=2026,week=1,home_team='ATL',away_team='CAR',kickoff=t)])
  facts=pd.DataFrame([dict(game_id=game,player_id=pid,team='ATL',opponent_team='CAR',position=role,attempts=4 if role=='QB' else 0,targets=targets,played=True,values={'rec':rec}) for pid,role,targets,rec in [('00-0000001','WR',2,1),('00-0000002','TE',1,1),('00-0000003','QB',0,0)]])
  p=[]
  for i,(pid,comp,air,yd) in enumerate([('00-0000001',1,5.,-5.),('00-0000001',0,15.,None),('00-0000002',1,2.,0.),(None,0,None,None)]):
   p.append(dict(game_id=game,play_id=i,posteam='ATL',pass_attempt=1,sack=0,two_point_attempt=0,play_deleted=0,play_type='pass',receiver_player_id=pid,air_yards=air,down=1,complete_pass=comp,receiving_yards=yd,yards_after_catch=yd,ydstogo=10,yardline_100=50))
  pbp=pd.DataFrame(p);counts={(game,'ATL'):dict(attempts=4,completions=2,targets=3,complete=True)}
  ctx=Context([pbp],facts,g,strict=True,all_position_counts=counts)
  return t,pbp,facts,g,ctx
 def build(self,pbp,facts,g,ctx):return ReceivingDefense([pbp],facts,g,context=ctx,source_bindings={'version':'SYNTHETIC_SOFTWARE_FIXTURE'})
 def test_counts_denominators_signed_yards_and_explicit_zero(self):
  t,p,f,g,c=self.fixture();d=self.build(p,f,g,c);r=d.profile('CAR',t+8*DAY)
  self.assertEqual((r['official_attempts'],r['eligible_targeted_plays'],r['unallocated_official_attempts']),(4,3,1))
  wr=next(x for x in r['cells'] if x['role']=='WR' and x['depth']=='0_9');self.assertEqual((wr['targets'],wr['catches']),(1,1));self.assertEqual(wr['catch_yardage']['yards_per_all_receptions'],-5.)
  missing=next(x for x in r['cells'] if x['role']=='WR' and x['depth']=='10_19');self.assertIsNone(missing['target_yardage']['yards_per_all_targets']);self.assertEqual(missing['target_yardage']['known_target_yard_count'],0)
  zero=next(x for x in r['cells'] if x['role']=='TE' and x['depth']=='0_9');self.assertEqual(zero['target_yardage']['yards_per_all_targets'],0.)
  self.assertAlmostEqual(r['role_target_share'][0]['raw'],2/3)
 def test_known_zero_cell_and_no_history_differ(self):
  t,p,f,g,c=self.fixture();d=self.build(p,f,g,c)
  r=d.profile('CAR',t+8*DAY);known=next(x for x in r['cells'] if x['role']=='RB');self.assertEqual(known['state'],'KNOWN_ZERO_TARGETS_IN_OBSERVED_GAMES');self.assertIsNone(known['catch_per_target']['raw'])
  empty=d.profile('ATL',t+8*DAY);self.assertEqual(empty['state'],'UNAVAILABLE_HISTORY');self.assertEqual(empty['cells'][0]['state'],'NO_ELIGIBLE_HISTORY')
 def test_strict_boundary_and_all_teams(self):
  t,p,f,g,c=self.fixture();d=self.build(p,f,g,c);self.assertEqual(d.profile('CAR',t+7*DAY)['eligible_games'],0);self.assertEqual(d.profile('CAR',t+7*DAY+1)['eligible_games'],1)
  allteams=d.snapshot(t+8*DAY);self.assertEqual(len(allteams),32);self.assertEqual({x['team'] for x in allteams},set(TEAMS))
 def test_unknown_clock_not_filled(self):
  t,p,f,g,c=self.fixture();g['available']=None;d=self.build(p,f,g,c);self.assertEqual(d.profile('CAR',t+8*DAY)['eligible_games'],0);self.assertEqual(d.rejected[0]['reason'],'EXPLICIT_UNKNOWN_AVAILABILITY')
 def test_availability_first_then_game_time_not_publication_order(self):
  t,p,f,g,c=self.fixture();d=self.build(p,f,g,c);old=copy.deepcopy(d.rows[0]);new=copy.deepcopy(old);old.update(game_id='OLD',kickoff=t-100,available=t+50);new.update(game_id='NEW',kickoff=t,available=t+1);d.groups['CAR']=[old,new]
  self.assertEqual(d.before('CAR',t+20,1)[0]['game_id'],'NEW');self.assertEqual(d.before('CAR',t+100,1)[0]['game_id'],'NEW')
 def test_exact_identity_and_duplicate_rejection(self):
  t,p,f,g,c=self.fixture();bad=f.copy();bad.loc[bad.position=='WR','team']='CAR'
  with self.assertRaisesRegex(ValueError,'TEAM_IDENTITY'):self.build(p,bad,g,c)
  with self.assertRaisesRegex(ValueError,'DUPLICATE_PLAY'):self.build(pd.concat([p,p.iloc[:1]]),f,g,c)
 def test_vector_order_shrinkage_and_asof_cap(self):
  t,p,f,g,c=self.fixture();d=self.build(p,f,g,c);q={'opponent_team':'CAR','kickoff':t+9*DAY}
  v=d.vector(q);self.assertEqual(len(v),len(FEATURE_NAMES));self.assertEqual(len(SUPPORT_NAMES),4);self.assertEqual(len(VALUE_NAMES),10);self.assertEqual(v[:2].tolist(),[1,3]);self.assertTrue(np.isfinite(v).all());self.assertTrue(((v[4:]>=0)&(v[4:]<=1)).all())
  before=d.vector(q,cutoff=t+7*DAY);self.assertEqual(before[0],0);self.assertTrue(np.isnan(before[4:]).all())
 def test_future_mutation_no_change(self):
  t,p,f,g,c=self.fixture();d=self.build(p,f,g,c);cut=t+8*DAY;expected=d.profile('CAR',cut)
  p2=p.copy();p2.game_id='2026_02_ATL_CAR';p2.receiving_yards=99999
  f2=f.copy();f2.game_id='2026_02_ATL_CAR'
  g2=g.copy();g2.game_id='2026_02_ATL_CAR';g2.kickoff=t+10*DAY
  combo=pd.concat([p,p2],ignore_index=True);facts=pd.concat([f,f2],ignore_index=True);games=pd.concat([g,g2],ignore_index=True)
  counts={(x,'ATL'):dict(attempts=4,completions=2,targets=3,complete=True) for x in games.game_id};ctx=Context([combo],facts,games,strict=True,all_position_counts=counts);altered=self.build(combo,facts,games,ctx)
  self.assertEqual(expected,altered.profile('CAR',cut))
 def test_source_row_qualification_does_not_become_played_zero(self):
  t,p,f,g,c=self.fixture();c.quality[0]['qualified']=False;d=self.build(p,f,g,c);self.assertEqual(len(d.rows),0);self.assertEqual(d.profile('CAR',t+8*DAY)['state'],'UNAVAILABLE_HISTORY')
 def test_missing_field_and_bad_cutoff_remain_explicit(self):
  t,p,f,g,c=self.fixture();d=self.build(p.drop(columns='receiving_yards'),f,g,c);r=d.profile('CAR',t+8*DAY)
  self.assertEqual(r['yard_field_presence']['games_without_column'],1);self.assertEqual(r['yard_field_presence']['games_with_column'],0)
  self.assertIs(type(r['cells'][0]['target_yardage']['all_target_components_complete']),bool)
  with self.assertRaisesRegex(ValueError,'FINITE_CUTOFF'):d.profile('CAR',None)
  with self.assertRaisesRegex(ValueError,'TIMEZONE'):d.profile('CAR','2026-09-15')
if __name__=='__main__':unittest.main()
