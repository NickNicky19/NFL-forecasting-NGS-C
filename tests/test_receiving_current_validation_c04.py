"""Schema integration and exact count-law checks; no NFL model fits."""
import copy,json,lzma,math,sys,tempfile,unittest,shutil
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import receiving_current_validation_c04 as c
import prospective_v4 as p
ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'prospective/runs/C-C04-20261110-W10-FIRST-01'

class TypedCaptureTests(unittest.TestCase):
 def test_real_run_recovers_and_dispatches_without_current_expiry_check(self):
  m,rows=p.validate_run(RUN,check_clock=False)
  self.assertEqual(len(rows),75);self.assertTrue(all(r['policy_id']=='C04::'+r['model_id'] for r in rows))
  self.assertTrue(all(r['scoring_contract_id']=='official-player-fullgame-OT-v1' for r in rows))
  self.assertNotIn('policy_id',c.read(RUN/'FORECASTS.json.xz')[0])
 def test_unknown_schema_does_not_take_typed_dispatch(self):
  with tempfile.TemporaryDirectory() as td:
   q=Path(td);(q/'RUN.json').write_text(json.dumps({'schema':'UNKNOWN','files':{}}))
   with patch.object(c,'validate_run',side_effect=AssertionError('WRONG_DISPATCH')) as typed:
    with self.assertRaises(FileNotFoundError):p.validate_run(q)
    typed.assert_not_called()
 def test_original_artifact_corruption_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   q=Path(td)/'run';shutil.copytree(RUN,q)
   (q/'FORECASTS.json.xz').write_bytes(b'corrupt')
   with self.assertRaisesRegex(AssertionError,'CAPTURE_BYTES_CHANGED'):p.validate_run(q)
 def test_nonnull_offer_rejected_even_if_payload_hash_updated(self):
  with tempfile.TemporaryDirectory() as td:
   q=Path(td)/'run';shutil.copytree(RUN,q);rows=c.read(q/'FORECASTS.json.xz');rows[0]['line']=.5
   b=lzma.compress(json.dumps(rows).encode());(q/'FORECASTS.json.xz').write_bytes(b)
   m=c.read(q/'RUN.json');m['files']['FORECASTS.json.xz']={'bytes':len(b),'SHA256':c.sha(q/'FORECASTS.json.xz')};(q/'RUN.json').write_text(json.dumps(m))
   app=c.read(q/'RECOVERY_COMPLETENESS_APPENDIX.json');app['parent_RUN_SHA256']=c.sha(q/'RUN.json');(q/'RECOVERY_COMPLETENESS_APPENDIX.json').write_text(json.dumps(app))
   with self.assertRaisesRegex(AssertionError,'UNQUALIFIED_OFFER'):p.validate_run(q)
 def test_issue_clock_checked_at_original_issue(self):
  with tempfile.TemporaryDirectory() as td:
   q=Path(td)/'run';shutil.copytree(RUN,q);m=c.read(q/'RUN.json');m['issued_UTC']='2026-11-10T21:00:00+00:00';(q/'RUN.json').write_text(json.dumps(m))
   app=c.read(q/'RECOVERY_COMPLETENESS_APPENDIX.json');app['parent_RUN_SHA256']=c.sha(q/'RUN.json');(q/'RECOVERY_COMPLETENESS_APPENDIX.json').write_text(json.dumps(app))
   with self.assertRaisesRegex(ValueError,'STALE'):p.validate_run(q)
 def test_poisson_exact_crps_against_cdf_sum_and_zero_boundary(self):
  for mu in [0.,.05,1.,7.,50.]:
   law=c.load_capture_law({'kind':'POISSON','mu':mu})
   for y in [0,1,5,60]:
    summed=sum((law.cdf(k)-(1 if y<=k else 0))**2 for k in range(500))
    self.assertAlmostEqual(law.crps(y),summed,places=10)
   self.assertEqual(law.probability(.5)['push'],0)
   self.assertAlmostEqual(sum(law.probability(1).values()),1.)
  z=c.PoissonCountLaw(0);self.assertEqual(z.quantile(.5),0);self.assertEqual(z.crps(0),0);self.assertEqual(z.crps(3),3)
  for bad in [-1,float('nan'),float('inf'),True]:
   with self.assertRaises(AssertionError):c.PoissonCountLaw(bad)
 def test_leaf_invalid_mass_not_coerced_into_poisson(self):
  d=c.read(RUN/'FORECASTS.json.xz')[0]['law'];d=copy.deepcopy(d);d['weights'][0]=-1
  with self.assertRaises(AssertionError):c.load_capture_law(d)
 def test_existing_grader_preserves_zero_unknown_and_missing_labels(self):
  # Synthetic contract fixture only; no prediction, source or NFL grade changes.
  base=dict(game_id='fixture',category='rec',policy_id='C04::fixture',mean=0.,median=0.,law={'kind':'POISSON','mu':0.},kickoff_UTC='2026-11-13T01:15:00Z',espn_event_id='123',scoring_contract_id='official-player-fullgame-OT-v1')
  rows=[dict(base,forecast_id=str(i),player_id=str(i)) for i in range(3)]
  with tempfile.TemporaryDirectory() as td:
   q=Path(td);e=q/'facts.txt';e.write_text('synthetic software fixture, not NFL evidence')
   actuals=[dict(game_id='fixture',player_id=str(i),category='rec',appearance=state,actual=actual,scoring_contract_id=base['scoring_contract_id'],event_status='FINAL',observed_UTC='2026-11-13T05:00:00Z',espn_event_id='123',kickoff_UTC=base['kickoff_UTC']) for i,(state,actual) in enumerate([('PLAYED',0),('UNKNOWN',None),('PLAYED',None)])]
   packet={'schema':'C-OUTCOMES-v4','source_qualification':'OFFICIAL_NUMERICAL_FACTS_VERIFIED','source_evidence':[{'path':'facts.txt','SHA256':c.sha(e),'source':'SYNTHETIC_SOFTWARE_FIXTURE'}],'version':'fixture','outcomes':actuals}
   (q/'outcomes.json').write_text(json.dumps(packet));(q/'receipt.json').write_text(json.dumps({'forecast_blob_SHA256':'fixture'}))
   with patch.object(p,'validate_run',return_value=({'schema':c.SCHEMA,'run_id':'fixture'},rows)),patch.object(p,'validate_receipt'),patch.object(p,'first_qualified_snapshots',return_value={}),patch.object(p,'now',return_value=c.aware('2026-11-14T00:00:00Z')):
    out=p.grade_run(q,q/'receipt.json',q/'outcomes.json',q/'grade.json')
   self.assertEqual([r['state'] for r in out],['GRADED_PLAYED','UNKNOWN','PLAYED_MISSING_ACTUAL'])
   self.assertEqual(out[0]['actual'],0);self.assertEqual(out[0]['CRPS'],0);self.assertEqual(out[0]['NLL'],0)
   self.assertIsNone(out[1]['actual']);self.assertIsNone(out[2]['actual'])
 def test_receipt_timing_and_exact_payload_bound(self):
  m,rows=p.validate_run(RUN);receipt={'schema':c.RECEIPT_SCHEMA,'qualified_prospective':True,'run_id':m['run_id'],'forecast_blob_SHA256':c.sha(RUN/'FORECASTS.json.xz'),'run_manifest_SHA256':c.sha(RUN/'RUN.json'),'fresh_GitHub_bytes_verified':True,'not_client_commit_dates':True,'server_run_created_UTC':'2026-11-10T20:00:00Z','server_run_started_UTC':'2026-11-10T20:00:01Z','server_check_completed_UTC':'2026-11-10T20:01:00Z'}
  self.assertEqual(str(p.validate_receipt(RUN,receipt,m,rows)),'2026-11-10 20:01:00+00:00')
  with self.assertRaises(AssertionError):p.validate_receipt(RUN,dict(receipt,forecast_blob_SHA256='0'*64),m,rows)
  with self.assertRaisesRegex(AssertionError,'LATE'):p.validate_receipt(RUN,dict(receipt,server_check_completed_UTC='2026-11-13T01:15:00Z'),m,rows)

if __name__=='__main__':unittest.main()
