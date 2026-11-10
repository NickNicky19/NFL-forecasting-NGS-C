import copy,sys,unittest
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from context_features_c01 import Context
from data_v2 import History,DAY
from receiving_profiles_c02 import ProfileBuilder,query_universe

class ReceivingProfiles(unittest.TestCase):
 def fixtures(self):
  past=pd.Timestamp('2026-09-01T18:00:00Z').timestamp();future=pd.Timestamp('2026-09-15T18:00:00Z').timestamp();cut='2026-09-12T12:00:00Z'
  event=dict(game_id='2026_02_CAR_ATL',espn_event_id='401000001',season=2026,week=2,home_team='ATL',away_team='CAR',kickoff_UTC='2026-09-15T18:00:00Z',state='pre',completed=False,status_name='STATUS_SCHEDULED',observed_UTC=cut)
  roster=[dict(gsis_id='00-0000001',full_name='Ordinary WR',position='WR',team='ATL',status='ACT',season=2026,week=2),dict(gsis_id='00-0000002',full_name='Zero TE',position='TE',team='ATL',status='ACT',season=2026,week=2),dict(gsis_id='00-0000003',full_name='Unseen WR',position='WR',team='ATL',status='INA',season=2026,week=2),dict(gsis_id='00-0000004',full_name='QB owner B',position='QB',team='ATL',status='ACT',season=2026,week=2),dict(gsis_id='00-0000005',full_name='RB owner A',position='RB',team='CAR',status='ACT',season=2026,week=2)]
  schedule=pd.DataFrame([dict(game_id='2026_01_ATL_CAR',season=2026,week=1,home_team='ATL',away_team='CAR',kickoff=past),dict(game_id=event['game_id'],season=2026,week=2,home_team='ATL',away_team='CAR',kickoff=future)])
  rows=[]
  for pid,role,targets,rec,carries in [('00-0000001','WR',1,1,0),('00-0000002','TE',0,0,1),('00-0000004','QB',0,0,0)]:
   rows.append(dict(game_id='2026_01_ATL_CAR',player_id=pid,team='ATL',opponent_team='CAR',position=role,season=2026,week=1,home_team='ATL',kickoff=past,available=past+7*DAY,attempts=2 if role=='QB' else 0,carries=carries,targets=targets,sacks_suffered=0,values={'rec':rec},played=True))
  players=pd.DataFrame(rows)
  p=[]
  for i in range(2):p.append(dict(game_id='2026_01_ATL_CAR',play_id=i,posteam='ATL',pass_attempt=1,sack=0,two_point_attempt=0,play_deleted=0,play_type='pass',receiver_player_id='00-0000001' if i==0 else None,passer_player_id='00-0000004',air_yards=5. if i==0 else np.nan,down=1 if i==0 else 2,complete_pass=int(i==0),yards_after_catch=3. if i==0 else np.nan,ydstogo=10,yardline_100=45))
  pbp=pd.DataFrame(p);counts={('2026_01_ATL_CAR','ATL'):{'attempts':2,'completions':1,'targets':1,'complete':True}}
  context=Context([pbp],players,schedule,strict=True,all_position_counts=counts)
  teams=pd.DataFrame([dict(game_id='2026_01_ATL_CAR',team='ATL',kickoff=past,available=past+7*DAY,attempts=2,carries=1,sacks_suffered=0),dict(game_id='2026_01_ATL_CAR',team='CAR',kickoff=past,available=past+7*DAY,attempts=0,carries=0,sacks_suffered=0)])
  return roster,event,cut,players,teams,context,pbp
 def builder(self,cut,players,teams,context,pbp):return ProfileBuilder(context,History(players,'player_id'),History(teams,'team'),cut,{'source':'SYNTHETIC_SOFTWARE_FIXTURE_NOT_NFL_EVIDENCE'},pbp=pbp)
 def test_universe_no_target_actual_or_participation(self):
  roster,event,cut,players,teams,ctx,pbp=self.fixtures();q,excluded=query_universe(roster,[event],cut)
  self.assertEqual(len(q),5);self.assertFalse(excluded);self.assertEqual({r['position'] for r in q},{'QB','RB','WR','TE'})
  mutated=copy.deepcopy(roster)
  for r in mutated:r.update(actual=9999,played=True,values={'rec':9999},targets=10000)
  q2,_=query_universe(mutated,[event],cut);self.assertEqual(q,q2)
  builder=self.builder(cut,players,teams,ctx,pbp);profiles=builder.build_all(q)
  self.assertEqual(len(profiles),5)
  qb=next(p for p in profiles if p['key']['position']=='QB');self.assertEqual(qb['quarterback']['state'],'NOT_IMPLEMENTED_OWNER_B');self.assertIsNone(qb['forecast_adapter']['features'])
 def test_zero_ratio_undefined_quality_and_legacy_feature(self):
  roster,event,cut,players,teams,ctx,pbp=self.fixtures();q,_=query_universe(roster,[event],cut);builder=self.builder(cut,players,teams,ctx,pbp)
  te=builder.build(next(r for r in q if r['player_id']=='00-0000002'))
  metric=te['receiving']['metrics']['targets_per_team_attempt'];self.assertEqual((metric['state'],metric['numerator'],metric['denominator'],metric['raw_estimate']),('KNOWN_ZERO',0,2,0))
  self.assertEqual(te['receiving']['metrics']['catch_per_target']['state'],'UNDEFINED_DENOMINATOR')
  self.assertIsNone(te['forecast_adapter']['features']['own'][5]);self.assertEqual(te['forecast_adapter']['features']['own'][:3],[1.,0.,2.])
  self.assertEqual(te['receiving']['missing_source_groups']['routes']['state'],'SOURCE_BLOCKED')
 def test_unseen_never_becomes_known_zero(self):
  roster,event,cut,players,teams,ctx,pbp=self.fixtures();q,_=query_universe(roster,[event],cut);p=self.builder(cut,players,teams,ctx,pbp).build(next(r for r in q if r['player_id']=='00-0000003'))
  self.assertEqual(p['state'],'UNAVAILABLE_HISTORY');self.assertEqual(p['history']['eligible_player_games'],0);self.assertIsNone(p['receiving']['metrics']['targets_per_team_attempt']['numerator']);self.assertEqual(p['receiving']['metrics']['targets_per_team_attempt']['state'],'ABSENT_HISTORY')
 def test_cutoff_not_future_kickoff_controls_prefix(self):
  roster,event,cut,players,teams,ctx,pbp=self.fixtures();q,_=query_universe(roster,[event],cut)
  boundary='2026-09-08T18:00:00Z';p=self.builder(boundary,players,teams,ctx,pbp).build(q[0]);self.assertEqual(p['history']['eligible_player_games'],0)
  eligible='2026-09-08T18:00:01Z';p=self.builder(eligible,players,teams,ctx,pbp).build(q[0]);self.assertGreaterEqual(p['history']['eligible_player_games'],0)
  # The ordinary receiver is admitted exactly after the strict availability edge.
  r=next(r for r in q if r['player_id']=='00-0000001');self.assertEqual(self.builder(eligible,players,teams,ctx,pbp).build(r)['history']['eligible_player_games'],1)
 def test_future_history_mutation_does_not_change_features(self):
  roster,event,cut,players,teams,ctx,pbp=self.fixtures();q,_=query_universe(roster,[event],cut);r=next(r for r in q if r['player_id']=='00-0000001');p=self.builder(cut,players,teams,ctx,pbp).build(r)
  f=players.iloc[0].to_dict();f.update(game_id=event['game_id'],kickoff=pd.Timestamp(event['kickoff_UTC']).timestamp(),available=pd.Timestamp(event['kickoff_UTC']).timestamp()+7*DAY,targets=10000,values={'rec':9999})
  altered=pd.concat([players,pd.DataFrame([f])],ignore_index=True);p2=self.builder(cut,altered,teams,ctx,pbp).build(r);self.assertEqual(p['forecast_adapter']['features'],p2['forecast_adapter']['features'])
 def test_historical_team_mapping_and_qb_denominator(self):
  roster,event,cut,players,teams,ctx,pbp=self.fixtures();q,_=query_universe(roster,[event],cut);r=next(r for r in q if r['player_id']=='00-0000001');p=self.builder(cut,players,teams,ctx,pbp).build(r)
  pair=p['receiving']['QB_pair_targeting']['qualified_QB_pairs'][0];self.assertEqual((pair['targets'],pair['passer_attempts_in_same_eligible_player_appearances']),(1,2));self.assertEqual(pair['target_per_passer_attempt']['raw_estimate'],.5)
  wrong=dict(r,team='CAR',opponent_team='ATL');m=self.builder(cut,players,teams,ctx,pbp).build(wrong);self.assertEqual(m['history']['eligible_player_games'],0)
 def test_trick_passer_and_unknown_role_not_called_QB(self):
  roster,event,cut,players,teams,ctx,pbp=self.fixtures();q,_=query_universe(roster,[event],cut);r=next(r for r in q if r['player_id']=='00-0000001')
  pbp=pbp.copy();pbp.loc[0,'passer_player_id']='00-0000002';players=players.copy();players.loc[players.player_id=='00-0000002','position']='RB'
  pairs=self.builder(cut,players,teams,ctx,pbp).build(r)['receiving']['QB_pair_targeting'];other=pairs['other_or_unknown_passer_pairs'];self.assertEqual(other[0]['historical_role'],'RB');self.assertEqual(other[0]['role_qualification'],'NON_QB_PASSER')
  pbp.loc[0,'passer_player_id']='00-9999999';pairs=self.builder(cut,players,teams,ctx,pbp).build(r)['receiving']['QB_pair_targeting'];self.assertEqual(pairs['other_or_unknown_passer_pairs'][0]['role_qualification'],'UNKNOWN_PASSER_ROLE')
 def test_new_model_binding_rejects_legacy_and_order_mismatch(self):
  import json,hashlib,math
  from receiving_profiles_c02 import source_contract,infer_bound_model,bound_model_input,validate_asof_model_input
  roster,event,cut,players,teams,ctx,pbp=self.fixtures();q,_=query_universe(roster,[event],cut);profile=self.builder(cut,players,teams,ctx,pbp).build(next(r for r in q if r['player_id']=='00-0000001'))
  model={'type':'L2_POOLED_POISSON','impute':[0.]*60,'center':[0.]*120,'scale':[1.]*120,'coef':[0.]*120,'intercept':math.log(2),'categories':[],'partial':False};raw=json.dumps(model).encode();binding=dict(source_contract(profile),feature_order=profile['forecast_adapter']['features']['E2_order'],lookback=8,fit_cutoff_UTC='2026-09-12T11:00:00Z',latest_training_available_UTC='2026-09-11T11:00:00Z',target_game_exclusion_verified=True,training_game_ids=[],model_SHA256=hashlib.sha256(raw).hexdigest())
  result=infer_bound_model(profile,binding,raw,2,current_event=event,admission_UTC=cut);self.assertAlmostEqual(result['mean'],2);self.assertAlmostEqual(sum(result['probabilities_at_exact_line'].values()),1)
  for e,at,reason in [(event,'2026-09-15T18:00:00Z','STARTED'),(event,'2026-09-12T12:30:01Z','EXPIRED'),(dict(event,espn_event_id='WRONG'),cut,'IDENTITY')]:
   with self.assertRaisesRegex(ValueError,reason):bound_model_input(profile,binding,raw,current_event=e,admission_UTC=at)
  with self.assertRaisesRegex(ValueError,'REQUIRED'):bound_model_input(profile,binding,raw)
  historic=dict(profile,historical_roster_clock='RECONSTRUCTED_NOT_AUTHENTICATED')
  with self.assertRaisesRegex(ValueError,'HISTORICAL'):bound_model_input(historic,binding,raw,current_event=event,admission_UTC=cut)
  bad=dict(binding,profile_contract_id='C-v1.1-fixed8')
  with self.assertRaisesRegex(ValueError,'SOURCE_CONTRACT'):bound_model_input(profile,bad,raw,current_event=event,admission_UTC=cut)
  bad=dict(binding,feature_order=list(reversed(binding['feature_order'])))
  with self.assertRaisesRegex(ValueError,'FEATURE_ORDER'):bound_model_input(profile,bad,raw,current_event=event,admission_UTC=cut)
  historical=copy.deepcopy(profile);historical['key']['information_cutoff_UTC']='2026-09-20T00:00:00Z';later=dict(binding,fit_cutoff_UTC='2026-09-18T00:00:00Z',latest_training_available_UTC='2026-09-17T00:00:00Z')
  with self.assertRaisesRegex(ValueError,'TRAINING_CLOCK'):validate_asof_model_input(historical,later,raw)
  inactive=copy.deepcopy(profile);inactive['roster_status']='INA'
  with self.assertRaisesRegex(ValueError,'ROSTER_NOT_ACTIVE'):bound_model_input(inactive,binding,raw,current_event=event,admission_UTC=cut)
  preliminary=copy.deepcopy(profile);preliminary['forecast_adapter']['roster_status_version_qualified']=False
  with self.assertRaisesRegex(ValueError,'CURRENT_QUERY'):bound_model_input(preliminary,binding,raw,current_event=event,admission_UTC=cut)
 def test_stale_or_missing_roster_is_explicit_profile_not_forecast(self):
  roster,event,cut,players,teams,ctx,pbp=self.fixtures();roster[0]['week']=1;q,_=query_universe(roster,[event],cut);p=self.builder(cut,players,teams,ctx,pbp).build(next(r for r in q if r['player_id']=='00-0000001'))
  self.assertEqual(p['state'],'UNQUALIFIED_ROSTER_OR_STATUS_VERSION');self.assertFalse(p['forecast_adapter']['roster_status_version_qualified'])
  old=dict(event,observed_UTC='2026-09-11T00:00:00Z');q,_=query_universe(roster,[old],cut);p=self.builder(cut,players,teams,ctx,pbp).build(q[0]);self.assertEqual(p['status_clock_admission'],'UNKNOWN_OR_STALE_NATIVE_STATUS_CLOCK')
 def test_started_game_and_duplicate_native_identity(self):
  roster,event,cut,*_=self.fixtures();done=dict(event,state='post',completed=True,status_name='STATUS_FINAL');q,excluded=query_universe(roster,[done],cut);self.assertEqual(q,[]);self.assertTrue(excluded)
  with self.assertRaisesRegex(ValueError,'DUPLICATE_PLAYER_EVENT'):query_universe(roster+[roster[0]],[event],cut)
if __name__=='__main__':unittest.main()
