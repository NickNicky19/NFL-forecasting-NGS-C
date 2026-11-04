import gzip
import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/abc-championship/shared-intake-v3'
def read(n):
    b=(OUT/n).read_bytes()
    return json.loads(gzip.decompress(b) if n.endswith('.gz') else b)


class SharedIntakeTests(unittest.TestCase):
    def test_exact_masks_three_way_scope_and_side_gaps(self):
        panels=read('SAME_OFFER_COMPARISONS.json.gz')
        common=[p for p in panels if p['sessions']==['A','B','C']]
        self.assertEqual({(p['category'],p['decided']) for p in common},{('pass_yd',63),('rec',337),('rec_yd',337)})
        self.assertTrue(all(p['temporal_parity'].startswith('NOT_ESTABLISHED') for p in common))
        r=next(p for p in common if p['category']=='rec')
        self.assertTrue(all(x['OVER'] is None for x in r['rows'] if x['session']=='A'))

    def test_state_hold_is_not_eighty_missing_predictions(self):
        hold=read('A_STATE_CLASSIFICATION_HOLD.json')
        self.assertEqual(len(hold['affected_views']),80)
        self.assertFalse(hold['decided_counts_changed'])
        self.assertTrue(any(r['unavailable_header']==0 for r in hold['affected_views']))

    def test_weekly_side_views_not_numerical_views(self):
        rows=read('B_ADMITTED_SCORES.json.gz')
        self.assertEqual(len(rows),903)
        self.assertEqual(sum(r['source'] in ['weekly_retained_method_scores','weekly_full_board_and_matched_controls','B_WEEKLY_FULL'] for r in rows),219)

    def test_pooled_same_years_same_weeks_weighted_counts(self):
        rows=read('PARTIAL_E5_E7_ALL_PROCEDURES.json')
        self.assertEqual(len(rows),42)
        for r in rows:
            self.assertEqual(r['actual_seasons'],[2024,2026])
            self.assertEqual(r['actual_weeks'],[1,2,3,4,5])
            for s in ['OVER','UNDER','COMBINED']:
                q=r[s];self.assertEqual(q['wins'] or 0,sum(x[s]['wins'] or 0 for x in r['season_records']))
                if q['decided']:self.assertAlmostEqual(q['rate'],q['wins']/q['decided'])
                if q['equal_season_rate'] is not None:self.assertAlmostEqual(q['equal_season_rate'],sum(x[s]['rate'] for x in r['season_records'])/2)


if __name__=='__main__':unittest.main()
