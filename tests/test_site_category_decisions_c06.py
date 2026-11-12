import copy,json,sys,tempfile,unittest
from unittest.mock import patch
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

class CurrentPacketProjectionTests(unittest.TestCase):
 def fixture(self,root):
  run=root/'prospective/runs/TEST';run.mkdir(parents=True)
  for n in ['RUN.json','FORECASTS.json.xz','CURRENT_REUSE_ASSESSMENT.json']:(run/n).write_bytes(b'fixture')
  (run/'INPUT_MANIFEST.json').write_text(json.dumps(dict(source_observed={'SOURCE':'2026-11-12T01:43:00Z'},roster_source={'observed_UTC':'2026-11-12T01:33:00Z'},roster_published_UTC='2026-11-11T07:04:00Z')))
  proof=root/'proof.json';proof.write_text(json.dumps(dict(server_check_completed_UTC='2026-11-12T02:25:00Z',capture_commit='a'*40,server_run_URL='https://example.invalid/software-fixture')))
  rows=[]
  for i in range(25):
   pos='WR' if i<18 else 'RB'
   rows.append(dict(forecast_id=str(i),player_id=str(i),game_id='TEST',model_id='C_V11_P1_E2_POOLED_7D',position=pos,mean=0.,median=0.,p05=0.,p95=0.,direction_candidate_role_eligible=pos=='WR',line=None,selected_side=None,probability_at_line=None,confidence=None,EV=None,model_fit_cutoff_UTC='2026-11-10T19:23:00Z',inference_UTC='2026-11-12T02:19:00Z',native_status_observed_UTC='2026-11-12T02:21:00Z',expires_UTC='2026-11-12T02:51:00Z'))
  manifest=dict(schema='C06-CURRENT-SOURCE-P1-QUERY-RUN-v1',run_id='TEST',primary_replacement=False,real_offers=0,real_selections=0,new_fits=0,new_inference_rows=25,forecast_rows=25,available_players=25,unavailable_players=0,games=['TEST'],information_policy='SOFTWARE_FIXTURE',source_input={},information_cutoff_UTC='2026-11-12T01:43:00Z',issued_UTC='2026-11-12T02:21:30Z')
  return dict(run_path='prospective/runs/TEST',receipt_path='proof.json'),manifest,rows
 def invoke(self,root,descriptor,m,rows):
  with patch.object(s,'ROOT',root),patch('prospective_v4.validate_run',return_value=(m,rows)),patch('prospective_v4.validate_receipt'):
   return s.current_projection(descriptor)
 def test_missing_packet_stays_absent(self):self.assertIsNone(s.current_projection(None))
 def test_zero_forecast_and_no_offer_remain_typed(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);desc,m,rows=self.fixture(root);x=self.invoke(root,desc,m,rows)
   self.assertEqual(x['rows'][0]['mean'],0);self.assertIsNone(x['rows'][0]['line']);self.assertFalse(x['primary_replacement']);self.assertEqual(x['RB_shadow_rows'],7)
 def test_forecast_packet_cannot_invent_a_line_or_side(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);desc,m,rows=self.fixture(root);rows[0]['line']=.5
   with self.assertRaises(AssertionError):self.invoke(root,desc,m,rows)
 def test_rb_does_not_inherit_wrte_candidate_scope(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);desc,m,rows=self.fixture(root);rows[-1]['direction_candidate_role_eligible']=True
   with self.assertRaises(AssertionError):self.invoke(root,desc,m,rows)
 def test_duplicate_forecast_identity_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);desc,m,rows=self.fixture(root);rows[-1]['forecast_id']=rows[0]['forecast_id']
   with self.assertRaises(AssertionError):self.invoke(root,desc,m,rows)

if __name__=='__main__':unittest.main()
