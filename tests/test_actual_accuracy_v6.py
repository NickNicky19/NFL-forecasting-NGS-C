"""Fictional software rows only; none are source-qualified NFL observations."""
import copy,json,sys,tempfile,unittest
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import actual_accuracy_v6 as a

def row(i=0,side='OVER',status='WIN',**kw):
    point=20 if side=='OVER' else 10;actual=20 if (side=='OVER')==(status=='WIN') else 10
    r=dict(record_kind='ACTUAL_OFFER',record_id='FICTIONAL-'+str(i),grade_id='FICTIONAL-GRADE-'+str(i),category='pass_yd',method_id='P1_MEDIAN',method_version='FICTIONAL-MEDIAN-v1',point_type='MEDIAN',point=point,selector_id='FICTIONAL-SELECTOR',policy_id='ALL_ELIGIBLE_OFFERS',game_id='FICTIONAL-GAME-'+str(i),player_id='FICTIONAL-PLAYER-'+str(i),espn_event_id='FICTIONAL-EVENT-'+str(i),season=2026,week=1,scoring_contract_id='official-player-fullgame-OT-v1',scoring_snapshot_id='FICTIONAL-SNAPSHOT-'+str(i),evidence_tier=a.TIERS[2],decision_horizon='TIMING_UNVERIFIED',venue='FICTIONAL_NOT_A_BOOK',product='FICTIONAL',line_tier='STANDARD',period='FULL_GAME_INCLUDING_OT',line=19.5,comparator='STRICT_OVER_UNDER',offered_sides=['OVER','UNDER'],selected_side=side,status=status,actual=actual,appearance='PLAYED',decision_UTC='2026-10-01T00:00:00Z',kickoff_UTC='2026-10-04T17:00:00Z',graded_UTC='2026-10-05T00:00:00Z',outcome_evidence_reference='FICTIONAL_TEST_ONLY')
    if status in ['DNP','PENDING','UNKNOWN_PARTICIPATION','MISSING_ACTUAL','VOID']:
        r.update(actual=None,appearance={'UNKNOWN_PARTICIPATION':'UNKNOWN','MISSING_ACTUAL':'PLAYED'}.get(status,status))
    if status=='PENDING':r['graded_UTC']=None
    if status=='VOID':r['void_kind']='STATISTICAL_EVENT_VOID'
    return r|dict(position='QB',role_evidence_reference='FICTIONAL_TEST_ONLY',season_type='REG',probability_inference_evidence_reference='FICTIONAL_TEST_ONLY',information_set_id='FICTIONAL-INFO')|kw

class Accuracy(unittest.TestCase):
    def test_empty_all12_no_rates_no_losses_no_leaders(self):
        cells=a.table([]);self.assertEqual(len(cells),12)
        for c in cells:
            self.assertIsNone(c['OVER']['rate']);self.assertIsNone(c['UNDER']['wins']);self.assertIsNone(c['COMBINED']['losses']);self.assertEqual(c['COMBINED']['decided'],0)
        self.assertTrue(all(x['state']=='NOT_ESTABLISHED' for x in a.observed_leaders(cells).values()))
    def test_own_sides_weighted_combined_not_average_percentages(self):
        rs=[row(1),row(2),row(3,status='LOSS'),row(4,side='UNDER')];[a.validate_row(r) for r in rs];c=a.aggregate(rs)
        self.assertAlmostEqual(c['OVER']['rate'],2/3);self.assertEqual(c['UNDER']['rate'],1);self.assertEqual(c['COMBINED']['rate'],.75);self.assertAlmostEqual(c['Over_minus_Under_percentage_points'],-100/3)
    def test_void_push_pending_unknown_unavailable_and_abstain_separate(self):
        rs=[row(1,line=20,actual=20,status='PUSH',point=21),row(2,status='VOID',void_evidence_reference='FICTIONAL'),row(3,status='DNP',appearance='DNP',actual=None),row(4,status='PENDING',actual=None,graded_UTC=None),row(5,status='UNKNOWN_PARTICIPATION',actual=None),row(6,status='MISSING_ACTUAL',actual=None),row(7,status='UNAVAILABLE_FORECAST',selected_side=None,point=None,actual=None),row(8,status='ABSTAIN',selected_side='ABSTAIN',point=19.5)]
        [a.validate_row(r) for r in rs];c=a.aggregate(rs);self.assertEqual(c['COMBINED']['decided'],0);self.assertEqual(c['COMBINED']['pushes'],1);self.assertEqual(c['COMBINED']['voids'],1);self.assertEqual(c['COMBINED']['pending'],1);self.assertEqual(c['unavailable_forecasts'],1);self.assertEqual(c['abstentions'],1)
    def test_win_loss_and_whole_boundary_recomputed(self):
        a.validate_row(row())
        with self.assertRaises(AssertionError):a.validate_row(row(status='WIN',actual=0))
        with self.assertRaises(AssertionError):a.validate_row(row(status='WIN',actual=20,line=20,point=21))
    def test_signed_yards_and_exact_fractional_chart_tie(self):
        a.validate_row(row(side='UNDER',point=-2,line=-.5,actual=-1))
        components={key:0 for key in a.WEIGHTS};components['rushing_yards']=3
        a.validate_row(row(category='fpts',scoring_contract_id='nick-chart-ppr-v1',venue_scoring_parity_verified=True,unique_event_credits_verified=True,score_components=components,point=.5,line=.3,actual=.30000000000000004,status='PUSH'))
    def test_synthetic_fixture_and_wrong_fantasy_contract_cannot_enter(self):
        for patch in [dict(record_kind='SYNTHETIC_THRESHOLD'),dict(is_fixture=True),dict(category='fpts',scoring_contract_id='legacy-minus-two-fumbles')]:
            with self.assertRaises(AssertionError):a.validate_row(row(**patch))
    def test_mean_median_types_and_directions_are_distinct(self):
        a.validate_row(row(method_id='P1_MEAN',point_type='MEAN'))
        with self.assertRaises(AssertionError):a.validate_row(row(method_id='P1_MEAN'))
        with self.assertRaises(AssertionError):a.validate_row(row(point=10,selected_side='OVER'))
    def test_probability_exact_line_complement_and_frozen_side(self):
        r=row(method_id='P3_DIRECT',p_under=.3,p_push=0,p_over=.7,probability_line=19.5);a.validate_row(r)
        for patch in [dict(probability_line=20),dict(p_over=.8),dict(selected_side='UNDER')]:
            with self.assertRaises(AssertionError):a.validate_row(r|patch)
    def test_anytime_only_offered_yes_and_not_expected_count(self):
        r=row(category='anytime_td',scoring_contract_id='rush-or-rec-at-least-one-v1',event_components=dict(rushing_tds=0,receiving_tds=1),method_id='P3_DIRECT',comparator='AT_LEAST_ONE_RUSH_REC_TD',line=None,probability_line=None,offered_sides=['YES'],selected_side='YES',actual=1,p_under=.2,p_push=0,p_over=.8);a.validate_row(r)
        with self.assertRaises(AssertionError):a.validate_row(r|dict(offered_sides=['YES','UNDER']))
        with self.assertRaises(AssertionError):a.validate_row(r|dict(event_components=dict(rushing_tds=0,receiving_tds=0,passing_tds=3)))
    def test_duplicate_revisions_and_paired_sides_are_not_new_outcomes(self):
        r=row();self.assertEqual(len(a.deduplicate([r,r])),1)
        later=r|dict(record_id='FICTIONAL-LATER',scoring_snapshot_id='FICTIONAL-LATER',decision_UTC='2026-10-02T00:00:00Z');self.assertEqual(a.deduplicate([later,r]),[r])
        conflict=row(record_id='FICTIONAL-OTHER',point=10,selected_side='UNDER',status='LOSS')
        with self.assertRaises(AssertionError):a.deduplicate([r,conflict])
    def test_append_only_correction_preserves_original_selection(self):
        pending=row(status='PENDING',actual=None,graded_UTC=None);final=row(grade_id='FICTIONAL-GRADE-FINAL',supersedes_grade_id=pending['grade_id']);self.assertEqual(a.deduplicate([pending,final]),[final])
        with self.assertRaises(AssertionError):a.deduplicate([pending,final|dict(point=30)])
        for delta in [dict(season=2025),dict(week=3),dict(grade_id=pending['grade_id']),dict(selection_server_UTC='2026-10-06T00:00:00Z')]:
            with self.assertRaises(AssertionError):a.deduplicate([pending,final|delta])
    def test_impossible_push_and_threshold_monotonicity_rejected(self):
        r=row(method_id='P3_DIRECT',p_under=.3,p_push=.2,p_over=.5,probability_line=19.5)
        with self.assertRaises(AssertionError):a.validate_row(r)
        r.update(p_under=.3,p_push=0,p_over=.7);s=r|dict(record_id='FICTIONAL-OTHER',scoring_snapshot_id='OTHER',line=20.5,probability_line=20.5,p_under=.2,p_over=.8)
        with self.assertRaises(AssertionError):a.deduplicate([r,s])
    def test_full_law_probabilities_recomputed_at_the_offered_line(self):
        import numpy as np
        from laws_v2 import Law,Prior
        from safe_models_v4 import law_data
        from actual_offers_v4 import probabilities
        law=law_data(Law([0,10,20],[1,1,4],Prior(np.asarray([0,10,20]),'signed')));r=row(method_id='P2_LAW',law=law,probability_line=19.5)
        probs=probabilities(r,dict(category='pass_yd',law=law));r.update(**{'p_'+k:v for k,v in probs.items()});a.validate_row(r)
        with self.assertRaises(AssertionError):a.validate_row(r|dict(p_under=.1,p_over=.9))
    def test_periods_and_evidence_tiers_do_not_mix(self):
        rs=[row(),row(1,season=2025),row(2,week=8),row(3,evidence_tier=a.TIERS[1])]
        self.assertEqual(a.table(rs,method='P1_MEDIAN')[0]['COMBINED']['decided'],1)
        self.assertEqual(a.table(rs,period='2025',method='P1_MEDIAN')[0]['COMBINED']['decided'],1)
    def test_topk_requires_frozen_membership_does_not_force_k(self):
        r=row(policy_id='GLOBAL_TOP6_MIXED')
        with self.assertRaises(AssertionError):a.validate_row(r)
        r.update(slate_id='FICTIONAL-SLATE',membership_evidence_reference='FICTIONAL',candidate_universe_SHA256='FICTIONAL',slate_decision_UTC=r['decision_UTC'],slate_earliest_kickoff_UTC=r['kickoff_UTC'],frozen_rank=1)
        self.assertEqual(len(a.deduplicate([r])),1)
    def test_tiny_perfect_observed_ties_are_not_supported_leaders(self):
        c1=a.table([row()],method='P1_MEDIAN')[0];c2=copy.deepcopy(c1);c2['category']='rec';leaders=a.observed_leaders([c1,c2]);self.assertEqual(len(leaders['OVER']['observed']),2);self.assertFalse(leaders['OVER']['observed'][0]['support_eligible_for_comparison']);self.assertEqual(leaders['OVER']['evidence_supported'],'NOT_ESTABLISHED')
    def test_minimum_support_and_cluster_interval_not_a_proven_winner(self):
        rs=[row(i,week=i%5+1) for i in range(100)];c=a.aggregate(rs)['OVER'];self.assertTrue(c['support_eligible_for_comparison']);self.assertTrue(c['uncertainty']['dependence_aware']);self.assertIn('NOT_ESTABLISHED',c['evidence_supported_leader'])
    def test_missing_one_side_has_no_side_difference(self):
        c=a.aggregate([row()]);self.assertIsNone(c['higher_side']);self.assertIsNone(c['Over_minus_Under_percentage_points'])
    def test_no_silent_version_pooling(self):
        with self.assertRaises(AssertionError):a.table([row(),row(1,method_version='FICTIONAL-OTHER')],method='P1_MEDIAN')
    def test_state_and_selected_side_reconcile_in_both_directions(self):
        for r in [row(status='PENDING',selected_side=None,point=None),row(status='PENDING',selected_side='ABSTAIN',point=19.5),row(status='MISSING_ACTUAL',actual=20),row(status='UNKNOWN_PARTICIPATION',appearance='PLAYED',actual=20),row(status='VOID',appearance='PLAYED',actual=20,void_evidence_reference='FICTIONAL')]:
            with self.assertRaises(AssertionError):a.validate_row(r)
    def test_explicit_tier_and_stratum_views_not_silent_pooling(self):
        rs=[row(),row(1,venue='FICTIONAL-VENUE-B',status='LOSS'),row(2,evidence_tier=a.TIERS[0],selection_server_UTC='2026-10-01T00:00:01Z',server_receipt_reference='FICTIONAL')];j=a.scorecard(rs,[])
        v=next(v for v in j['views'] if v['period']=='2026_W1_W7' and v['method']=='P1_MEDIAN' and v['evidence_tier']==a.TIERS[2])
        self.assertEqual(v['cells'][0]['strata_count'],2);self.assertEqual(len(v['leader_groups']),2);self.assertEqual(v['leaders']['state'],'NO_POOLED_CROSS_STRATUM_LEADER');self.assertIn('TIMING_UNVERIFIED_ACTUAL_LINE_DIAGNOSTIC',a.markdown(j));self.assertTrue(a.prospective_period('2026_W8'))
    def test_prospective_first_snapshot_matches_v5_server_order(self):
        r=row(evidence_tier=a.TIERS[3],week=8,kickoff_UTC='2026-10-30T00:15:00Z',graded_UTC='2026-10-31T00:00:00Z',selection_server_UTC='2026-10-01T00:20:00Z',server_receipt_reference='FICTIONAL');s=r|dict(record_id='FICTIONAL-B',scoring_snapshot_id='FICTIONAL-B',decision_UTC='2026-10-01T00:10:00Z',selection_server_UTC='2026-10-01T00:15:00Z',line_tier='ALTERNATE')
        self.assertEqual(a.deduplicate([r,s]),[s])
        with self.assertRaises(AssertionError):a.validate_row(r|dict(selection_server_UTC='2026-10-30T00:14:59Z'))
    def test_same_information_same_threshold_and_supported_comparator(self):
        r=row(method_id='P3_DIRECT',p_under=.2,p_push=0,p_over=.8,probability_line=19.5);s=r|dict(record_id='FICTIONAL-B',venue='FICTIONAL-B',p_under=.3,p_over=.7)
        with self.assertRaises(AssertionError):a.deduplicate([r,s])
        with self.assertRaises(AssertionError):a.validate_row(r|dict(comparator='UNSUPPORTED',status='PENDING',appearance='PENDING',actual=None,graded_UTC=None))
    def test_missing_candidate_does_not_shrink_reference_coverage(self):
        cells=a.table([row()],method='P2_LAW');self.assertEqual(cells[0]['eligible_offers'],1);self.assertEqual(cells[0]['unavailable_forecasts'],1);self.assertEqual(cells[0]['COMBINED']['decided'],0)
    def test_bool_points_and_wrong_prospective_week_rejected(self):
        with self.assertRaises(AssertionError):a.validate_row(row(point=True,line=.5,actual=1))
        with self.assertRaises(AssertionError):a.validate_row(row(evidence_tier=a.TIERS[3],selection_server_UTC='2026-10-01T00:01:00Z',server_receipt_reference='FICTIONAL'))
    def test_timing_scope_requires_explicit_granted_tiers(self):
        for v in [{a.TIERS[3]:False},a.TIERS[3],None]:self.assertFalse(a.tier_allowed(dict(qualified_evidence_tiers=v),a.TIERS[3]))
        self.assertTrue(a.tier_allowed(dict(qualified_evidence_tiers=[a.TIERS[2]]),a.TIERS[2]))
    def test_genuine_import_binds_original_market_primary_and_forecast(self):
        r=row(evidence_tier=a.TIERS[3],week=8,kickoff_UTC='2026-10-30T00:15:00Z',graded_UTC='2026-10-31T00:00:00Z',selection_server_UTC='2026-10-01T00:20:00Z',server_receipt_reference='FICTIONAL',server_receipt_SHA256='FICTIONAL',selection_run_id='FICTIONAL-RUN',offer_id='FICTIONAL-OFFER',forecast_id='FICTIONAL-F',model_id='FICTIONAL-MODEL',model_SHA256='FICTIONAL-HASH',conditioning='FICTIONAL',feature_cutoff_UTC='2026-09-30T00:00:00Z',forecast_generated_UTC='2026-09-30T00:01:00Z')
        e=r|dict(tier=r['line_tier'],primary_in_packet=True,reasons=[],cutoff_UTC=r['decision_UTC'],P1_side=r['selected_side']);at=a.instant(r['selection_server_UTC']);f={k:r[k] for k in ['model_SHA256','position','season','week','game_id','player_id','category','espn_event_id','scoring_contract_id','kickoff_UTC']};packet=dict(at=at,manifest=dict(run_id=r['selection_run_id'],decision_cutoff_UTC=r['decision_UTC']),rows=[e],forecasts={r['forecast_id']:f});key=tuple(r[k] for k in ['game_id','player_id','category','venue','product'])
        with patch.object(a,'retained_paper',return_value=packet),patch.object(a,'eligible_paper_offer',return_value=True),patch.object(a,'first_paper_index',return_value={key:(at,r['selection_run_id'])}):
            a.verify_future_record(r)
            for delta in [dict(venue='OTHER'),dict(product='OTHER'),dict(line_tier='OTHER'),dict(offered_sides=['OVER']),dict(model_SHA256='CHANGED'),dict(point_type='MEAN'),dict(week=9)]:
                with self.assertRaises(AssertionError):a.verify_future_record(r|delta)
            e['primary_in_packet']=False
            with self.assertRaises(AssertionError):a.verify_future_record(r)
            e['primary_in_packet']=True
            with patch.object(a,'first_paper_index',return_value={}):
                with self.assertRaises(AssertionError):a.verify_future_record(r)
            e['forecast_id']=None;e['reasons']=['NO_MATCHED_FORECAST'];e['P1_side']=None
            unavailable=r|dict(status='UNAVAILABLE_FORECAST',forecast_id=None,model_id=None,model_SHA256=None,point=None,selected_side=None)
            a.verify_future_record(unavailable)

if __name__=='__main__':unittest.main()
