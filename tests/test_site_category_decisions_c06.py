import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import site_category_decisions_c06 as s

def doc():
 rows=[]
 for category in sorted(s.CATEGORIES):
  r={k:None for k in s.REQUIRED};r.update(category=category,label=category,decision='KEEP_INCUMBENT',highest_observed_panels=[],other_products=[],actual_weeks_by_season={},coverage={k:None for k in ['eligible','available','selected','unknown','unavailable','fallback','games','player_games']})
  rows.append(r)
 return dict(schema=s.SCHEMA,prepared_UTC='2026-11-12T01:00:00Z',status='PARTIAL',categories=rows,source_bindings=[])

class CategoryDecisionPublicationTests(unittest.TestCase):
 def test_unknown_is_not_filled_from_zero(self):
  x=doc();r=x['categories'][0];r['coverage']['eligible']=0;r['OVER']=dict(wins=0,losses=0,decided=0,rate=None)
  y=s.validate_document(x);self.assertEqual(y['categories'][0]['coverage']['eligible'],0);self.assertIsNone(y['categories'][0]['coverage']['available']);self.assertIsNone(y['categories'][0]['OVER']['rate']);self.assertIsNone(y['categories'][0]['preferred_eligible_candidate'])
 def test_combined_uses_counts_not_side_average(self):
  x=doc();r=x['categories'][0];r.update(OVER=dict(wins=1,losses=0,decided=1,rate=1.),UNDER=dict(wins=0,losses=3,decided=3,rate=0.),COMBINED=dict(wins=1,losses=3,decided=4,rate=.5))
  with self.assertRaisesRegex(AssertionError,'RATE'):s.validate_document(x)
  r['COMBINED']['rate']=.25;s.validate_document(x)
 def test_disjoint_side_denominators_must_reconcile(self):
  x=doc();r=x['categories'][0];r.update(OVER=dict(wins=1,losses=0,decided=1,rate=1.),UNDER=dict(wins=0,losses=0,decided=0,rate=None),COMBINED=dict(wins=2,losses=0,decided=2,rate=1.))
  with self.assertRaisesRegex(AssertionError,'SUM_COUNTS'):s.validate_document(x)
 def test_alias_cannot_duplicate_chart_category(self):
  x=doc();x['categories'][0]['category']='fpts'
  with self.assertRaisesRegex(AssertionError,'DUPLICATE'):s.validate_document(x)
 def test_nonfinite_is_not_rendered_as_missing(self):
  x=doc();x['categories'][0]['controls']={'metric':float('nan')}
  with self.assertRaisesRegex(ValueError,'NONFINITE'):s.validate_document(x)
 def test_repeated_week_does_not_add_duration(self):
  x=doc();x['categories'][0]['actual_weeks_by_season']={'2026':[1,1,2,3,4]}
  with self.assertRaisesRegex(AssertionError,'WEEK_LIST'):s.validate_document(x)
 def test_unknown_operation_is_rejected_without_inventing_switch(self):
  x=doc();x['categories'][0]['decision']='AUTO_CHAMPION_SWITCH'
  with self.assertRaisesRegex(AssertionError,'UNKNOWN_OPERATIONAL'):s.validate_document(x)

if __name__=='__main__':unittest.main()
