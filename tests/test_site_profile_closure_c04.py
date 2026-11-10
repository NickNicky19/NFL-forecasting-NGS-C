"""Publication adapter contracts; synthetic files are not NFL observations."""
import copy, hashlib, json, lzma, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import site_profile_closure_c04 as s

class C04PublicationTests(unittest.TestCase):
 def fixture(self,root):
  base=root/'reports/profile-closure-next-02';base.mkdir(parents=True)
  run=root/'prospective/runs/FIXTURE';run.mkdir(parents=True)
  rows=[]
  for model in s.MODELS:
   rows.append(dict(model_id=model,player_id='00-0000001',name='Fixture',position='WR',team='WAS',opponent_team='NYG',game_id='2026_10_WAS_NYG',category='rec',line=None,selected_side=None,probability_at_line=None,confidence=None,EV=None,mean=0.,median=0.,p05=0.,p95=0.,information_cutoff_UTC='2026-11-10T18:00:00+00:00',inference_UTC='2026-11-10T19:00:00+00:00',issued_UTC='2026-11-10T20:00:00+00:00',native_status_observed_UTC='2026-11-10T19:59:00+00:00',expires_UTC='2026-11-11T20:00:00+00:00',kickoff_UTC='2026-11-13T01:15:00+00:00'))
  self.write(run/'FORECASTS.json.xz',rows)
  manifest=dict(forecast_rows=3,unique_players=1,games=['2026_10_WAS_NYG'],models=[],basic_rows=2,real_offers=0,real_selections=0,primary_replacement=False,information_cutoff_UTC=rows[0]['information_cutoff_UTC'],issued_UTC=rows[0]['issued_UTC'],roster_contract='CURRENT_KNOWN_SEASON_ROSTER',first_kickoff_UTC=rows[0]['kickoff_UTC'],files={'FORECASTS.json.xz':dict(bytes=(run/'FORECASTS.json.xz').stat().st_size,SHA256=s.sha(run/'FORECASTS.json.xz'))})
  self.write(run/'RUN.json',manifest)
  proof=dict(run_id='FIXTURE',fresh_download_verified=True,qualified_before_first_kickoff=True,capture_commit='a'*40,run_manifest_SHA256=s.sha(run/'RUN.json'),forecast_SHA256=s.sha(run/'FORECASTS.json.xz'),server_check_completed_UTC='2026-11-10T20:01:00+00:00',server_run_URL='https://github.com/example/actions/runs/1')
  self.write(base/'CURRENT_PUBLICATION_RECEIPT.json',proof)
  return base,run,rows,manifest,proof
 def write(self,path,value):
  body=s.encoded(value)
  path.write_bytes(lzma.compress(body) if path.suffix=='.xz' else body)
 def test_verified_three_models_preserve_observed_zero_and_null_offers(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);base,*_=self.fixture(root)
   with patch.object(s,'ROOT',root),patch.object(s,'BASE',base):out=s.current()
   self.assertEqual(len(out['rows']),3);self.assertEqual(out['rows'][0]['mean'],0.)
   for r in out['rows']:
    self.assertIsNone(r['line']);self.assertIsNone(r['selected_side']);self.assertIsNone(r['confidence'])
   self.assertFalse(out['primary_replacement']);self.assertFalse(out['original_website_incumbent'])
 def test_packet_corruption_is_rejected_before_projection(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);base,run,*_=self.fixture(root)
   with (run/'FORECASTS.json.xz').open('ab') as f:f.write(b'changed')
   with patch.object(s,'ROOT',root),patch.object(s,'BASE',base),self.assertRaises(AssertionError):s.current()
 def test_server_time_after_kickoff_is_not_pregame(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);base,run,rows,m,p=self.fixture(root);p['server_check_completed_UTC']='2026-11-13T01:15:01+00:00';self.write(base/'CURRENT_PUBLICATION_RECEIPT.json',p)
   with patch.object(s,'ROOT',root),patch.object(s,'BASE',base),self.assertRaises(AssertionError):s.current()
 def test_changed_side_or_line_is_not_forecast_only(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);base,run,rows,m,p=self.fixture(root);rows[0]['line']=.5
   self.write(run/'FORECASTS.json.xz',rows);m['files']['FORECASTS.json.xz']=dict(bytes=(run/'FORECASTS.json.xz').stat().st_size,SHA256=s.sha(run/'FORECASTS.json.xz'));self.write(run/'RUN.json',m);p.update(forecast_SHA256=s.sha(run/'FORECASTS.json.xz'),run_manifest_SHA256=s.sha(run/'RUN.json'));self.write(base/'CURRENT_PUBLICATION_RECEIPT.json',p)
   with patch.object(s,'ROOT',root),patch.object(s,'BASE',base),self.assertRaises(AssertionError):s.current()
 def test_different_model_query_masks_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);base,run,rows,m,p=self.fixture(root);rows[0]['player_id']='00-0000002'
   self.write(run/'FORECASTS.json.xz',rows);m['files']['FORECASTS.json.xz']=dict(bytes=(run/'FORECASTS.json.xz').stat().st_size,SHA256=s.sha(run/'FORECASTS.json.xz'));self.write(run/'RUN.json',m);p.update(forecast_SHA256=s.sha(run/'FORECASTS.json.xz'),run_manifest_SHA256=s.sha(run/'RUN.json'));self.write(base/'CURRENT_PUBLICATION_RECEIPT.json',p)
   with patch.object(s,'ROOT',root),patch.object(s,'BASE',base),self.assertRaisesRegex(AssertionError,'CURRENT_MODEL_QUERY_MASK'):s.current()
 def test_naive_clock_rejected(self):
  with self.assertRaisesRegex(ValueError,'CLOCK_MUST'):s.stamp('2026-11-10T20:00:00')

if __name__=='__main__':unittest.main()
