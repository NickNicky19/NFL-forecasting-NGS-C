"""Synthetic software fixtures, never sportsbook observations or hit-rate evidence."""
import copy,sys,unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from actual_offers_v4 import probabilities,evaluate,reconcile
from laws_v2 import Law,Prior
from safe_models_v4 import law_data
from offer_validator_v2 import instant

class ExactOffers(unittest.TestCase):
    def setUp(self):
        self.cutoff=instant('2026-11-01T00:00:00Z')
        self.f=dict(forecast_id='fixture-f',game_id='fixture-g',player_id='fixture-p',category='pass_yd',espn_event_id='fixture-e',kickoff_UTC='2026-11-01T18:00:00Z',information_cutoff_UTC='2026-10-31T23:45:00Z',generated_UTC='2026-10-31T23:50:00Z',scoring_contract_id='official-player-fullgame-OT-v1',median=10.,mean=10.,law=law_data(Law([0,10,20],[1,2,1],Prior(np.asarray([0,10,20]),'signed'))))
        self.o=dict(record_kind='ACTUAL_OFFER',offer_id='fixture-o',venue='FIXTURE_NOT_A_BOOK',product='FIXTURE',tier='STANDARD',player_id='fixture-p',game_id='fixture-g',category='pass_yd',espn_event_id='fixture-e',kickoff_UTC=self.f['kickoff_UTC'],period='FULL_GAME_INCLUDING_OT',scoring_contract_id=self.f['scoring_contract_id'],comparator='STRICT_OVER_UNDER',line=9.5,identity_evidence_reference='fixture-only',source_evidence_reference='fixture-only',observed_at_UTC='2026-10-31T23:59:00Z',source_asof_UTC='2026-10-31T23:58:00Z',persisted_at_UTC='2026-10-31T23:59:01Z',lifecycle='OPEN',offered_sides=['OVER','UNDER'],side_states={'OVER':'OPEN','UNDER':'OPEN'})
    def test_players_have_their_own_exact_lines_and_changed_line_recomputes(self):
        a=evaluate(self.o,self.f,self.cutoff)
        other=self.o|dict(player_id='fixture-p2',line=19.5);f=self.f|dict(player_id='fixture-p2')
        b=evaluate(other,f,self.cutoff)
        self.assertEqual((a['line'],b['line']),(9.5,19.5));self.assertGreater(a['p_over'],b['p_over'])
        self.assertEqual((a['P2_side'],b['P2_side']),('OVER','UNDER'))
        self.assertEqual(b['p_over'],probabilities(other,f)['over'])
    def test_missing_line_never_gets_a_shared_threshold(self):
        for value in [None,float('nan')]:
            a=evaluate(self.o|dict(line=value),self.f,self.cutoff)
            self.assertEqual(a['state'],'UNAVAILABLE_NOT_ABSTENTION');self.assertIsNone(a['p_over']);self.assertIsNone(a['P2_side'])
    def test_synthetic_rows_cannot_enter_real_offer_probabilities_or_results(self):
        with self.assertRaises(ValueError):probabilities(self.o|dict(record_kind='SYNTHETIC_THRESHOLD'),self.f)
        a=evaluate(self.o,self.f,self.cutoff)
        with self.assertRaises(ValueError):reconcile([a|dict(record_kind='SYNTHETIC_THRESHOLD')],{})
        with self.assertRaises(ValueError):reconcile([a],{}) # no server proof yet
    def test_whole_push_half_point_and_inclusive_milestone_are_distinct(self):
        whole=probabilities(self.o|dict(line=10),self.f);half=probabilities(self.o|dict(line=9.5),self.f)
        milestone=probabilities(self.o|dict(line=10,comparator='AT_LEAST'),self.f)
        self.assertGreater(whole['push'],0);self.assertAlmostEqual(half['push'],0)
        self.assertAlmostEqual(half['over'],milestone['over']);self.assertAlmostEqual(sum(whole.values()),1)
    def test_stale_or_suspended_offers_are_technical_unavailable(self):
        for patch in [dict(source_asof_UTC='2026-10-31T22:00:00Z'),dict(side_states={'OVER':'SUSPENDED','UNDER':'OPEN'})]:
            r=evaluate(self.o|patch,self.f,self.cutoff);self.assertEqual(r['state'],'UNAVAILABLE_NOT_ABSTENTION')
    def test_own_sides_reconcile_win_loss_and_push_without_averaging_rates(self):
        a=evaluate(self.o,self.f,self.cutoff,'HISTORICAL_DIAGNOSTIC')
        b=evaluate(self.o|dict(line=19.5),self.f,self.cutoff,'HISTORICAL_DIAGNOSTIC')
        c=evaluate(self.o|dict(line=10),self.f,self.cutoff,'HISTORICAL_DIAGNOSTIC')
        r=reconcile([a,b,c],{('fixture-g','fixture-p','pass_yd'):dict(appearance='PLAYED',actual=10)})['P2']
        self.assertEqual(r['COMBINED']['wins'],2);self.assertEqual(r['COMBINED']['decided'],2);self.assertEqual(r['other_states']['PUSH'],1)
    def test_anytime_does_not_create_an_under_or_no_offer(self):
        f=self.f|dict(category='anytime_td',scoring_contract_id='rush-or-rec-at-least-one-v1',median=None,law=law_data(Law([0,1],[1,3],Prior(np.asarray([0,1]),'event'))))
        o=self.o|dict(category='anytime_td',scoring_contract_id=f['scoring_contract_id'],comparator='AT_LEAST_ONE_RUSH_REC_TD',offered_sides=['YES'],side_states={'YES':'OPEN'},line=None)
        a=evaluate(o,f,self.cutoff);self.assertEqual(a['P2_side'],'YES');self.assertIsNone(a['P1_side'])
