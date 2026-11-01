import copy,json,tempfile,unittest,sys,gzip,hashlib
from pathlib import Path
from unittest.mock import patch
import numpy as np,pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from safe_models_v4 import prior_data,law_data,law_load,export_forest,infer_forest,validate_training_model
from laws_v2 import Prior,LeafModel
from prospective_v4 import features_for_future,qualified_training_frame,grade_run,held_ungraded_games
from forward_sources_v4 import match_event
from site_forward_v4 import display_and_primary

class Prospective(unittest.TestCase):
    def test_latest_display_does_not_replace_the_first_scoring_snapshot(self):
        first=dict(game_id='g',player_id='p',category='pass_yd',policy_id='policy',forecast_id='a',server_persisted_UTC='2026-11-01T00:00:00Z',mean=100)
        revision=first|dict(forecast_id='b',server_persisted_UTC='2026-11-01T01:00:00Z',mean=200)
        r=list(display_and_primary([revision,first]).values())[0]
        self.assertEqual(r['forecast_id'],'b');self.assertEqual(r['mean'],200);self.assertEqual(r['primary_scoring_forecast_id'],'a');self.assertFalse(r['primary_scoring_snapshot']);self.assertEqual(first['mean'],100)
    def test_numeric_tree_float32_double_threshold_boundary(self):
        prior=prior_data(Prior(np.asarray([0,1]),'count'))
        tree=dict(left=[1,-1,-1],right=[2,-1,-1],feature=[0,-2,-2],threshold=[1.0000001788139343,-2,-2],leaves={'1':[[0],[1]],'2':[[1],[1]]})
        model=dict(schema='C-NUMERIC-LEAF-v4',kind='count',scale=1,imputation=[0.],prior={'QB':prior},global_prior=prior,trees=[tree]*32)
        law=infer_forest(model,[[1.000000238418579]],['QB'])[0]
        self.assertEqual(law.v.tolist(),[1]);self.assertEqual(law.quantile(.5),1)

    def test_safe_model_export_matches_missing_signed_and_count_inference(self):
        # Synthetic software fixture, not an NFL fit/outcome.
        x=np.arange(240,dtype=float).reshape(120,2);x[::13,0]=np.nan;y=np.arange(120)%7-2;roles=np.asarray(['QB']*120)
        m=LeafModel('signed',1).fit(x,y,roles);query=np.asarray([[np.nan,3],[20.125,43],[238,239]],float)
        a=m.laws(query,['QB']*3);b=infer_forest(json.loads(json.dumps(export_forest(m))),query,['QB']*3)
        self.assertEqual(validate_training_model(export_forest(m),x,y,roles)['new_fits'],0)
        for left,right in zip(a,b):
            self.assertEqual(left.mean(),right.mean());self.assertEqual(left.w.tolist(),right.w.tolist())
            for line in [-1,.5,2,3.5]:self.assertEqual(left.probability(line),right.probability(line))

    def test_invalid_numeric_law_support_rejected(self):
        d=dict(values=[.5],weights=[1.],prior=prior_data(Prior(np.asarray([0,1]),'count')),scale=1,alpha=.05)
        with self.assertRaises(AssertionError):law_load(d)
        d['values']=[-1]
        with self.assertRaises(AssertionError):law_load(d)
        d['values']=[0];d['prior']['q']=float('nan')
        with self.assertRaises(AssertionError):law_load(d)

    def test_non_event_unused_summary_is_not_a_probability(self):
        from laws_v2 import Law
        d=law_data(Law([250],[1],Prior(np.asarray([200,250,300]),'signed')))
        self.assertGreater(d['prior']['event'],1)
        self.assertEqual(law_load(d).mean(),250)

    def test_future_candidate_needs_no_actuals_and_future_mutations_are_invariant(self):
        cutoff=2_000_000.;past=dict(player_id='00-0000001',game_id='PAST',team='BUF',position='QB',kickoff=cutoff-10*86400,available=cutoff-3*86400,game_final=True,values={'pass_cmp':10},attempts=20,carries=1,targets=0)
        future=dict(past,game_id='FUTURE',kickoff=cutoff+86400,available=0,values={'pass_cmp':999},attempts=999)
        history=pd.DataFrame([past,future]);teamrow=dict(team='BUF',game_id='PAST',kickoff=past['kickoff'],available=past['available'],attempts=30,carries=20,sacks_suffered=2)
        teams=pd.DataFrame([teamrow]);candidate=dict(player_id=past['player_id'],position='QB',team='BUF',opponent_team='KC',home_team='BUF',week=8,kickoff=cutoff+2*86400)
        a=features_for_future(history,teams,candidate,'pass_cmp','E0_ENV',cutoff)
        history.loc[1,'attempts']=-888;history.at[1,'values']={'pass_cmp':-888}
        b=features_for_future(history,teams,candidate,'pass_cmp','E0_ENV',cutoff)
        np.testing.assert_array_equal(a,b)
        self.assertEqual(len(qualified_training_frame(history,['PAST','FUTURE'],cutoff)),1)
        history.at[0,'values']={'pass_cmp':20}
        self.assertNotEqual(a[0],features_for_future(history,teams,candidate,'pass_cmp','E0_ENV',cutoff)[0])

    def test_started_postponed_and_rescheduled_events_do_not_issue(self):
        r=dict(espn='123',home_team='BUF',away_team='KC',kickoff=100,season=2026,week=8)
        e=dict(espn_event_id='123',home_team='BUF',away_team='KC',kickoff=100,season=2026,week=8,season_type=2,state='pre',status_name='STATUS_SCHEDULED',completed=False)
        self.assertTrue(match_event(r,e,99));self.assertFalse(match_event(r,e,101))
        self.assertFalse(match_event(r,dict(e,status_name='STATUS_POSTPONED'),99))
        self.assertFalse(match_event(r,dict(e,state='in'),99))
        with self.assertRaises(AssertionError):match_event(r,dict(e,kickoff=200),99)

    def test_grading_rejects_future_outcomes_and_keeps_played_zero(self):
        prior=Prior(np.asarray([0,1,2]),'count')
        from laws_v2 import Law
        law=law_data(Law([0,1,2],[1,1,1],prior))
        row=dict(forecast_id='f',game_id='g',player_id='p',category='pass_cmp',policy_id='fixture',kickoff_UTC='2026-11-01T18:00:00+00:00',espn_event_id='1',scoring_contract_id='official-player-fullgame-OT-v1',mean=1.,median=1.,law=law)
        outcome=dict(game_id='g',player_id='p',category='pass_cmp',kickoff_UTC=row['kickoff_UTC'],espn_event_id='1',scoring_contract_id=row['scoring_contract_id'],event_status='FINAL',appearance='PLAYED',observed_UTC='2026-11-01T22:00:00+00:00',actual=0)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'forecasts.json.gz').write_bytes(b'fixture');(root/'RUN.json').write_bytes(b'{}');proof=root/'proof.json';proof.write_text(json.dumps(dict(schema='C-SERVER-PREGAME-RECEIPT-v4',run_id='run',qualified_prospective=True,run_manifest_SHA256=hashlib.sha256(b'{}').hexdigest(),forecast_blob_SHA256=hashlib.sha256(b'fixture').hexdigest(),fresh_GitHub_bytes_verified=True,not_client_commit_dates=True,server_run_created_UTC='2026-11-01T00:00:00Z',server_run_started_UTC='2026-11-01T00:00:01Z',server_check_completed_UTC='2026-11-01T00:00:10Z')));out=root/'outcomes.json';(root/'facts-fixture.json').write_bytes(b'fixture facts');out.write_text(json.dumps(dict(schema='C-OUTCOMES-v4',version='fixture',source_qualification='OFFICIAL_NUMERICAL_FACTS_VERIFIED',source_evidence=[dict(path='facts-fixture.json',SHA256=hashlib.sha256(b'fixture facts').hexdigest(),source='SOFTWARE_FIXTURE')],outcomes=[outcome])))
            meta={'run_id':'run','created_UTC':'2026-10-31T23:00:00Z'}
            with patch('prospective_v4.validate_run',return_value=(meta,[row])),patch('prospective_v4.now',return_value=pd.Timestamp('2026-10-31T23:00:00Z').to_pydatetime()):
                with self.assertRaises(AssertionError):grade_run(root,proof,out,root/'bad.json')
            with patch('prospective_v4.validate_run',return_value=(meta,[row])),patch('prospective_v4.now',return_value=pd.Timestamp('2026-11-02T00:00:00Z').to_pydatetime()):
                r=grade_run(root,proof,out,root/'good.json');self.assertEqual(r[0]['state'],'GRADED_PLAYED');self.assertEqual(r[0]['actual'],0)
                packet=json.loads(out.read_text());packet['outcomes'][0]['actual']=True;out.write_text(json.dumps(packet))
                with self.assertRaises(AssertionError):grade_run(root,proof,out,root/'bool.json')
                packet['outcomes'][0]['actual']=None;out.write_text(json.dumps(packet));r=grade_run(root,proof,out,root/'missing.json');self.assertEqual(r[0]['state'],'PLAYED_MISSING_ACTUAL')
                packet['outcomes'][0]['appearance']='DNP';packet['outcomes'][0]['actual']=0;out.write_text(json.dumps(packet));r=grade_run(root,proof,out,root/'dnp.json');self.assertEqual(r[0]['state'],'DNP');self.assertIsNone(r[0]['actual'])
            eventrow=row|dict(category='anytime_td',scoring_contract_id='rush-or-rec-at-least-one-v1',mean=None,median=None,law=law_data(Law([0,1],[1,1],Prior(np.asarray([0,1]),'event'))))
            packet['outcomes'][0].update(category='anytime_td',scoring_contract_id=eventrow['scoring_contract_id'],appearance='PLAYED',actual=1,event_components=dict(rushing_tds=0,receiving_tds=0,passing_tds=3));out.write_text(json.dumps(packet))
            with patch('prospective_v4.validate_run',return_value=(meta,[eventrow])),patch('prospective_v4.now',return_value=pd.Timestamp('2026-11-02T00:00:00Z').to_pydatetime()):
                with self.assertRaises(AssertionError):grade_run(root,proof,out,root/'passing-is-not-anytime.json')

    def test_own_completed_games_wait_for_append_only_grade_or_unknown_marker(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);first={('g','p','pass_cmp','policy'):(pd.Timestamp('2026-11-01T00:00:00Z'),'f')}
            with patch('prospective_v4.first_qualified_snapshots',return_value=first):
                self.assertEqual(held_ungraded_games({'g','other'},root),['g'])
                (root/'runs/run').mkdir(parents=True);(root/'runs/run/forecasts.json.gz').write_bytes(b'fixture');(root/'grades').mkdir()
                marker=dict(run_id='run',created_UTC='2026-10-31T23:00:00Z',confirmed_final_game_ids=[],forecast_SHA256=hashlib.sha256(b'fixture').hexdigest(),grades=[dict(forecast_id='f',game_id='g',state='PENDING',actual=None)])
                (root/'grades/marker.json').write_text(json.dumps(marker));self.assertEqual(held_ungraded_games({'g','other'},root),['g'])
                marker['confirmed_final_game_ids']=['g'];marker['grades'][0]['state']='UNKNOWN';(root/'grades/marker.json').write_text(json.dumps(marker))
                self.assertEqual(held_ungraded_games({'g','other'},root),[])
