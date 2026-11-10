import copy,hashlib,json,lzma,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import site_timing_confirm_c05 as s

class TimingConfirmPublicationTests(unittest.TestCase):
 def test_known_zero_and_missing_metric_are_distinct(self):
  r=dict(procedure='control',category='rec',roles='WR_TE',source_panel='ANNUAL_NAMED_NJ',week_view='ALL',actual_retained_threshold_weeks='[1,2,3,4,5]',eligible='1',selected='1',unavailable='0',abstained='0',unknown_participation='0',games='1',numerical_MAE='0',numerical_MSE='')
  for side in ['over','under','combined']:
   n=0 if side=='under' else 1;r.update({side+'_wins':'0',side+'_losses':str(n),side+'_decided':str(n),side+'_rate':'' if n==0 else '0'})
  x=s.normalize(r);self.assertEqual(x['numerical_MAE'],0);self.assertIsNone(x['numerical_MSE']);self.assertEqual(x['OVER']['rate'],0);self.assertIsNone(x['UNDER']['rate'])
  r['actual_retained_threshold_weeks']='[1,2,3,4,5,6,7]'
  with self.assertRaisesRegex(AssertionError,'MIXED_PANEL'):s.normalize(r)
 def test_csv_empty_side_is_na_without_hiding_missing_decisions(self):
  r=dict(under_decided='0',under_wins='',under_losses='',under_rate='')
  self.assertEqual(s.record(r,'under'),dict(wins=0,losses=0,decided=0,rate=None))
  r['under_decided']='1'
  with self.assertRaises(ValueError):s.record(r,'under')
 def fixture(self,root):
  base=root/'reports';base.mkdir();run=root/'prospective/runs/FIXTURE';run.mkdir(parents=True);old=root/s.OLD;old.mkdir(parents=True)
  (old/'RUN.json').write_text(json.dumps(dict(run_id=old.name,forecast_rows=75)));(old/'FORECASTS.json.xz').write_bytes(b'old-fixture')
  rows=[]
  for model in s.MODELS:
   rows.append(dict(forecast_id=model,model_id=model,model_SHA256='1'*64,player_id='00-0000001',name='Fixture',position='WR',team='NE',opponent_team='DET',game_id=s.TARGET,category='rec',kickoff_UTC='2026-11-15T14:30:00+00:00',mean=0.,median=0.,p05=0.,p95=0.,information_cutoff_UTC='2026-11-10T19:23:00+00:00',original_prepared_inference_UTC='2026-11-10T19:32:00+00:00',inference_UTC='2026-11-10T23:01:00+00:00',eligibility_information_cutoff_UTC='2026-11-10T22:51:00+00:00',current_roster_observed_UTC='2026-11-10T22:50:00+00:00',native_status_observed_UTC='2026-11-10T23:02:00+00:00',issued_UTC='2026-11-10T23:03:00+00:00',expires_UTC='2026-11-12T03:34:00+00:00',line=None,selected_side=None,probability_at_line=None,confidence=None,EV=None))
  p=run/'FORECASTS.json.xz';p.write_bytes(lzma.compress(json.dumps(rows).encode()))
  m=dict(schema='C05-FROZEN-FOOTBALL-CURRENT-QUERY-RUN-v1',run_id='FIXTURE',new_fits=0,real_offers=0,real_selections=0,primary_replacement=False,issued_UTC=rows[0]['issued_UTC'],first_kickoff_UTC=rows[0]['kickoff_UTC'],forecast_rows=3,unique_players=1,available_players=1,unavailable_players=0,current_eligible_players=1,new_inference_rows=3,games=[s.TARGET],information_policy='FROZEN_FOOTBALL_SNAPSHOT_FIRST_PUBLICATION_SHADOW',information_cutoff_UTC=rows[0]['information_cutoff_UTC'],eligibility_input_cutoff_UTC=rows[0]['eligibility_information_cutoff_UTC'],lineage=dict(football_source_cutoff_UTC='2026-11-10T18:55:00+00:00'),files={'FORECASTS.json.xz':dict(bytes=p.stat().st_size,SHA256=hashlib.sha256(p.read_bytes()).hexdigest())})
  (run/'RUN.json').write_text(json.dumps(m));proof=dict(schema='C05-SERVER-PREGAME-RECEIPT-v1',run_id='FIXTURE',qualified_prospective=True,fresh_GitHub_bytes_verified=True,capture_commit='a'*40,forecast_blob_SHA256=s.sha(p),run_manifest_SHA256=s.sha(run/'RUN.json'),not_client_commit_dates=True,server_run_created_UTC='2026-11-10T23:04:00+00:00',server_run_started_UTC='2026-11-10T23:04:30+00:00',server_check_completed_UTC='2026-11-10T23:05:00+00:00',server_run_URL='https://example.invalid/software-fixture')
  (base/'CURRENT_PUBLICATION_RECEIPT.json').write_text(json.dumps(proof));return base,run,rows,proof
 def current(self,root,base):
  real=s.sha
  def controlled(p):
   return '4334c6e93d41487011e3bedb9a0a0173e38ccfcf5c568b30efbd0b73995be362' if Path(p)==root/s.OLD/'FORECASTS.json.xz' else real(p)
  with patch.object(s,'ROOT',root),patch.object(s,'BASE',base),patch.object(s,'sha',side_effect=controlled):return s.current()
 def test_frozen_clocks_nulls_and_zero_survive_projection(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);base,_,_,_=self.fixture(root);x=self.current(root,base)
   self.assertEqual(x['rows'][0]['mean'],0);self.assertIsNone(x['rows'][0]['line']);self.assertEqual(x['old_packet_preserved']['rows'],75)
   self.assertNotEqual(x['model_feature_cutoff_UTC'],x['first_inference_UTC']);self.assertNotEqual(x['first_prepared_inference_UTC'],x['first_inference_UTC'])
 def test_late_persistence_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);base,_,_,proof=self.fixture(root);proof['server_check_completed_UTC']='2026-11-15T14:30:01+00:00';(base/'CURRENT_PUBLICATION_RECEIPT.json').write_text(json.dumps(proof))
   with self.assertRaises(AssertionError):self.current(root,base)
 def test_unordered_or_client_clock_proof_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);base,_,_,proof=self.fixture(root);proof['server_run_started_UTC']='2026-11-10T23:06:00+00:00';(base/'CURRENT_PUBLICATION_RECEIPT.json').write_text(json.dumps(proof))
   with self.assertRaises(AssertionError):self.current(root,base)
   proof['server_run_started_UTC']='2026-11-10T23:04:30+00:00';proof['not_client_commit_dates']=False;(base/'CURRENT_PUBLICATION_RECEIPT.json').write_text(json.dumps(proof))
   with self.assertRaises(AssertionError):self.current(root,base)
 def test_corrupt_capture_bytes_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);base,run,_,_=self.fixture(root);p=run/'FORECASTS.json.xz';p.write_bytes(p.read_bytes()+b'bad')
   with self.assertRaises(AssertionError):self.current(root,base)
 def test_different_model_masks_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);base,run,rows,proof=self.fixture(root);rows[-1]['player_id']='00-0000002';p=run/'FORECASTS.json.xz';p.write_bytes(lzma.compress(json.dumps(rows).encode()));m=json.loads((run/'RUN.json').read_text());m['files']['FORECASTS.json.xz']=dict(bytes=p.stat().st_size,SHA256=s.sha(p));(run/'RUN.json').write_text(json.dumps(m));proof.update(forecast_blob_SHA256=s.sha(p),run_manifest_SHA256=s.sha(run/'RUN.json'));(base/'CURRENT_PUBLICATION_RECEIPT.json').write_text(json.dumps(proof))
   with self.assertRaises(AssertionError):self.current(root,base)
 def test_timezone_required(self):
  with self.assertRaises(ValueError):s.clock('2026-11-10T23:00:00')

if __name__=='__main__':unittest.main()
