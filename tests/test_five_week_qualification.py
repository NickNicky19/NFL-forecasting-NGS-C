import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from five_week_qualification import Registry,finish,week_test_count,bound_week_panel,c_original_forward


class FiveWeekTests(unittest.TestCase):
    def test_distinct_season_week_not_folds_or_repeated_views(self):
        weeks=[dict(season=2026,week=2,scored=10)]*20+[dict(season=2026,week=3,scored=10)]
        self.assertEqual(week_test_count(weeks),2)
        self.assertEqual(week_test_count(weeks+[dict(season=2025,week=2,scored=10)]),3)

    def test_zero_selected_unknown_weeks_not_counted(self):
        rows=[dict(season=2026,week=w,scored=0,selected=0) for w in range(1,9)]
        rows[2]['scored']=1
        self.assertEqual(week_test_count(rows),1)

    def test_product_and_policy_do_not_borrow_parent_weeks(self):
        reg=Registry()
        for proc,product,policy,weeks in [('parent','NUMERICAL_MEDIAN','FULL',range(1,8)),('repair','EXACT_LINE_PROBABILITIES','FULL',[2,3]),('repair','TOP_PICKS_DIRECTION','TOP6',[2])]:
            for week in weeks:reg.add(owner='C',procedure=proc,category='rec',product=product,role='RB/WR/TE',history='FIXED',policy=policy,panel='TEST',tier='RECONSTRUCTION',source='fixture',season=2026,week=week,n=1,selected=1,eligible=1)
        rows=finish(reg);counts={(r['procedure_id'],r['product']):r['scored_week_count'] for r in rows}
        self.assertEqual(counts[('parent','NUMERICAL_MEDIAN')],7)
        self.assertEqual(counts[('repair','EXACT_LINE_PROBABILITIES')],2)
        self.assertEqual(counts[('repair','TOP_PICKS_DIRECTION')],1)

    def test_historical_floor_does_not_become_current_validation(self):
        reg=Registry()
        for year,weeks in [(2025,range(1,6)),(2026,[2,3])]:
            for week in weeks:reg.add(owner='A',procedure='exact',category='rec',product='ACTUAL_LINE_DIRECTION',role='WR',history='ROLLING',policy='FULL',panel='SAME',tier='RECONSTRUCTION',source='fixture',season=year,week=week,n=1,selected=1,eligible=1)
        r=finish(reg)[0]
        self.assertEqual(r['five_week_floor'],'MET')
        self.assertEqual(r['current_2026_scored_week_count'],2)
        self.assertTrue(r['historical_evidence_needed_for_floor'])
        self.assertTrue(r['no_automatic_primary_release'])

    def test_repeated_cumulative_view_does_not_add_weeks(self):
        reg=Registry();args=dict(owner='B',procedure='exact',category='rec',product='DIRECTION',role='WR',history='MULTI',policy='FULL',panel='SAME',tier='RECONSTRUCTION',source='fixture',season=2026,week=2,n=10,selected=10,eligible=10)
        reg.add(**args);reg.add(**args)
        self.assertEqual(finish(reg)[0]['scored_week_count'],1)

    def test_only_registered_week_aliases_merge(self):
        self.assertEqual(bound_week_panel('B_C_PINNACLE_RETAINED_LEAF_LAWS_W2'),bound_week_panel('B_C_PINNACLE_RETAINED_LEAF_LAWS_W3'))
        self.assertEqual(bound_week_panel('OTHER_DIFFERENT_COHORT_W2'),'OTHER_DIFFERENT_COHORT_W2')
        self.assertNotEqual(bound_week_panel('OTHER_DIFFERENT_COHORT_W2'),bound_week_panel('OTHER_DIFFERENT_COHORT_W3'))

    def test_original_capture_does_not_inherit_training_weeks_or_create_offers(self):
        reg=Registry();c_original_forward(reg);rows=finish(reg)
        self.assertEqual(len(rows),34)
        self.assertTrue(all(r['scored_week_count']==1 and r['five_week_floor']=='NOT_MET' for r in rows))
        self.assertTrue(all(r['metadata']['original_actual_line_selections']==0 for r in rows))
        self.assertFalse(any('ACTUAL_LINE' in r['product'] for r in rows))


if __name__=='__main__':unittest.main()
