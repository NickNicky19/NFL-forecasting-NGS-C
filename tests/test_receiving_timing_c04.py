import copy,sys,unittest
from pathlib import Path
from types import SimpleNamespace
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from receiving_timing_c04 import DAY,AdmittedPrefix,TimedInputs,retime_proxy_record,OwnContext

def ordinary(game,kick,player='00-0000001',team='A',value=2):
 return dict(game_id=game,kickoff=kick,available=kick+7*DAY,player_id=player,team=team,position='WR',values={'rec':value},attempts=0,carries=0,targets=3)
def own(game,kick,team='A',targets=3):
 return dict(game_id=game,kickoff=kick,available=kick+7*DAY,player_id='00-0000001',team=team,team_complete=True,receptions_match=True,targets=targets,attempts=30,completions=2 if targets else 0,depth_n=np.array([0,targets,0,0,0]),down_n=np.array([targets,0,0,0,0]),air_n=targets,air_sum=targets*4,yac_n=2 if targets else 0,yac_sum=8 if targets else 0,short=0,redzone=0)
class Defense:
 def __init__(self,rows):self.rows=rows;self.groups={'D':rows};self._league_cache={}
 def before(self,team,cut,n=8):return sorted([r for r in self.groups.get(team,[]) if r['available']<cut and r['kickoff']<cut],key=lambda r:(r['kickoff'],r['game_id']))[-n:]
def parts(lag=1):
 rows=[ordinary('old',0),ordinary('new',4*DAY,value=5)];hist=AdmittedPrefix(rows,'player_id')
 teams=[dict(game_id=r['game_id'],kickoff=r['kickoff'],available=r['available'],team='A',attempts=30,carries=20,sacks_suffered=2) for r in rows]
 th=AdmittedPrefix(teams,'team');ctx=SimpleNamespace(raw_player_games=[own('old',0),own('new',4*DAY)])
 defense=Defense([dict(game_id=r['game_id'],kickoff=r['kickoff'],available=r['available'],defense='D',cells=np.ones((4,5,6))) for r in rows])
 return TimedInputs(rows,hist,th,ctx,defense,lag)
def query():return dict(game_id='target',player_id='00-0000001',team='A',opponent_team='D',position='WR',kickoff=10*DAY,home_team='A',week=2)

class TimingTests(unittest.TestCase):
 def test_proxy_not_unknown_or_observed_clock(self):
  r=ordinary('g',0);self.assertEqual(retime_proxy_record(r,1)['available'],DAY);self.assertEqual(r['available'],7*DAY)
  for v in [None,float('nan'),0]:
   q=dict(r,available=v)
   with self.assertRaises(ValueError):retime_proxy_record(q,1)
  q=dict(r);q.pop('available')
  with self.assertRaises(ValueError):retime_proxy_record(q,1)
 def test_strict_boundary_and_admit_before_recency(self):
  rows=[dict(game_id='older',kickoff=1,available=20,key='x'),dict(game_id='newer',kickoff=2,available=3,key='x')]
  h=AdmittedPrefix(rows,'key');self.assertEqual([r['game_id'] for r in h.before('x',20,1)],['newer']);self.assertEqual(h.before('x',3),[])
  self.assertEqual([r['game_id'] for r in h.before('x',21,1)],['newer'])
 def test_alignment_changes_history_and_labels_together(self):
  p7,p1=parts(7),parts(1);q=query()
  self.assertEqual(p7.hist.before(q['player_id'],q['kickoff'])[-1]['game_id'],'old')
  self.assertEqual(p1.hist.before(q['player_id'],q['kickoff'])[-1]['game_id'],'new')
  self.assertEqual([r['game_id'] for r in p7.pool if r['available']<q['kickoff']],['old'])
  self.assertEqual([r['game_id'] for r in p1.pool if r['available']<q['kickoff']],['old','new'])
  self.assertEqual(p7.features(q)['own'][0],1);self.assertEqual(p1.features(q)['own'][0],2)
 def test_future_query_without_outcome_and_actual_clock_cap(self):
  p=parts(1);q=query();x=p.features(q,information_cutoff=3*DAY)
  self.assertEqual(x['BASE'][0],2);self.assertEqual(x['own'][0],1);self.assertEqual(x['defense_support'][0],1)
  self.assertEqual(len(x['SUPPORT']),41);self.assertEqual(len(x['PROFILE']),58)
  self.assertNotIn('actual',q);self.assertNotIn('available',q)
 def test_future_target_mutations_do_not_change_earlier_features(self):
  p=parts(1);q=query();before=p.features(q)
  future=retime_proxy_record(ordinary('target',10*DAY,value=99),1)
  p.hist.groups[q['player_id']].append(future)
  after=p.features(q)
  for key in ['BASE','SUPPORT','PROFILE']:self.assertTrue(np.array_equal(before[key],after[key],equal_nan=True))
 def test_known_zero_legacy_coarsening_is_not_source_absence(self):
  ctx=OwnContext([retime_proxy_record(own('zero',0,targets=0),1)])
  v=ctx.own(query());self.assertEqual(v[0],1);self.assertEqual(v[1],0);self.assertEqual(v[2],30);self.assertTrue(np.isnan(v[5]))
  self.assertFalse(hasattr(ctx,'features'))
 def test_team_change_is_not_current_team_history(self):
  ctx=OwnContext([retime_proxy_record(own('other',0,team='B'),1)])
  v=ctx.own(query());self.assertEqual(v[0],0);self.assertEqual(v[1],0)
 def test_role_and_cutoff_validation(self):
  p=parts(1);q=query()
  with self.assertRaises(ValueError):p.features(dict(q,position='QB'))
  with self.assertRaises(ValueError):p.features(q,information_cutoff=float('nan'))
 def test_no_source_mutation(self):
  r=ordinary('g',0);before=copy.deepcopy(r);out=retime_proxy_record(r,1);self.assertEqual(r,before);self.assertNotEqual(out['available'],r['available'])

if __name__=='__main__':unittest.main()
