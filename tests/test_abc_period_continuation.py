import csv
import gzip
import io
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from abc_period_report_v2 import OUT, ROOT, read


class PeriodContinuation(unittest.TestCase):
    def test_A_selected_and_unknown_are_not_double_counted(self):
        rows = read('A_W1_W7_ARCHIVED_SCORES.json.gz')
        self.assertEqual(len(rows), 79)
        self.assertEqual(sum(len(r['week_rows']) for r in rows), 553)
        for r in rows:
            self.assertEqual([int(w['week']) for w in r['week_rows']], list(range(1, 8)))
            self.assertEqual(r['selected'], r['eligible']-r['no_lean']-r['missing_offer_or_prediction'])
            self.assertEqual(r['selected'], r['COMBINED']['decided']+r['unresolved']+r['pushes']+r['DNP'])
            self.assertEqual(r['unresolved'], r['unknown_participation']+r['played_missing'])

    def test_B_original_and_control_are_same_selected_pool(self):
        r = read('B_ORIGINAL_SELECTED_POOL_CONTROL.json')
        self.assertEqual((r['original_wins'],r['original_losses'],r['decided']), (205,210,415))
        self.assertEqual(r['always_Under_wins'],128+96)
        self.assertEqual(r['original_selected'],427)
        self.assertEqual(r['unknown'],12)
        self.assertEqual(r['paired_win_difference'],19)

    def test_triads_and_no_claim_of_raw_parity(self):
        rows=read('B_OWNER_LOCAL_SCORES.json.gz')
        self.assertEqual(len(rows),1691)
        for r in rows:
            self.assertFalse(r['common_row_parity'])
            for k in ['selected','decided']:
                self.assertEqual(r['OVER'][k]+r['UNDER'][k],r['COMBINED'][k])

    def test_week_grid_preserves_A_seven_and_missing_eighth(self):
        rows=list(csv.DictReader(io.StringIO(gzip.decompress((OUT/'WEEK_BY_WEEK_GAPS.csv.gz').read_bytes()).decode())))
        a=[r for r in rows if r['source']=='A_FIXED_W1_W7_ARCHIVED_POINT_PANEL']
        self.assertEqual(len(a),79*8)
        self.assertEqual(sum(r['state']=='COMPLETED_OWNER_LOCAL_AGGREGATE_WEEK' for r in a),553)
        self.assertTrue(all(r['state']=='EXACT_FIXED_RECIPE_W8_EXPORT_NOT_ESTABLISHED' for r in a if r['week']=='8'))

    def test_original_C_forecast_fields_are_unchanged(self):
        old=list(csv.DictReader(gzip.open(ROOT/'reports/week8-v9/GRADED_FORECAST_ROWS.csv.gz','rt')))
        new=list(csv.DictReader(gzip.open(OUT/'C_WEEK8_FINAL_GRADED_FORECAST_ROWS.csv.gz','rt')))
        allowed={'state','actual','absolute_error','median_error','mean_squared_error','CRPS','NLL','outcome_observed_UTC','grade_version'}
        self.assertEqual(len(old),2513)
        self.assertEqual(len(new),2513)
        for a,b in zip(old,new):
            self.assertEqual({k:v for k,v in a.items() if k not in allowed},{k:v for k,v in b.items() if k not in allowed})
            if a['game_id']!='2026_08_CHI_SEA':
                self.assertEqual(a['actual'],b['actual'])
        self.assertFalse(any(r['state']=='PENDING' for r in new))
        self.assertEqual(sum(r['state']=='GRADED_PLAYED' for r in new),1532)

    def test_twelve_categories_and_missing_event_markets(self):
        rows=read('HEADLINE_A_W1_W7.json')
        self.assertEqual(len(rows),12)
        for r in rows:
            if r['category'] in ['anytime_td','fpts']:
                self.assertIsNone(r['COMBINED'])
            else:
                self.assertEqual(r['COMBINED']['decided'],r['OVER']['decided']+r['UNDER']['decided'])


if __name__=='__main__':
    unittest.main()
