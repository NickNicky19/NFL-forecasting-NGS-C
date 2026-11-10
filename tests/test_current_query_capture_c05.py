"""Bounded C05 source/clock/lineage software fixtures; no NFL fits or inference."""
import copy,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import current_query_capture_c05 as c
import prospective_v4 as p
import site_forward_v4 as site
AT=c.aware('2026-11-10T23:00:00Z').timestamp()
def game():return dict(game_id=c.TARGET,home_team='DET',away_team='NE',season=2026,week=10,kickoff=1794753000.,espn=401873053)
def player(pid='00-0000001',team='NE',role='RB',status='ACT'):
 return dict(gsis_id=pid,team=team,position=role,status=status,season=2026,full_name='Synthetic fixture')
def rows(pid='00-0000001',role='RB',team='NE'):
 return [dict(model_id=m,player_id=pid,game_id=c.TARGET,team=team,position=role,opponent_team='DET',kickoff=game()['kickoff'],feature_order=['synthetic_x'],features=[None],model_SHA256='fixture',mean=0.,median=0.,p05=0.,p95=0.,information_cutoff_UTC='2026-11-10T19:23:09.469852Z',inference_UTC='2026-11-10T19:32:00Z') for m in c.MODEL_IDS]

class FitlessCaptureTests(unittest.TestCase):
 def test_current_board_needs_no_target_outcome_and_retains_new_player(self):
  r=[player(),player('00-0000002'),player('00-0000003',role='QB'),player('00-0000004',status='RES'),player('00-0000005',team='BUF')]
  b,selected=c.current_board(r,game(),rows())
  self.assertEqual(len(b),5);self.assertEqual(len(selected),3)
  self.assertEqual([x['reason'] for x in b],['AVAILABLE_ALL_THREE_BOUND_MODELS','FROZEN_FEATURE_UNAVAILABLE','B_OWNED_QB_BASIC_ONLY','CURRENT_ROSTER_RES','NOT_SELECTED_EVENT_TEAM'])
  self.assertTrue(b[1]['eligible_current_query']);self.assertFalse(b[1]['available_all_models'])
  changed=[dict(x,actual=99,played=True,targets=50,available=None) for x in r]
  self.assertEqual(c.current_board(changed,game(),rows()),(b,selected))
 def test_duplicate_missing_team_role_event_conflicts_not_reassigned(self):
  b,q=c.current_board([player(),player()],game(),rows());self.assertFalse(q);self.assertTrue(all(x['reason']=='DUPLICATE_NATIVE_PLAYER_ID'for x in b))
  self.assertEqual(c.current_board([player(None)],game(),rows())[0][0]['reason'],'INVALID_NATIVE_PLAYER_ID')
  for field,value in [('team','DET'),('position','WR'),('kickoff',game()['kickoff']+1)]:
   old=rows();old[0][field]=value;b,q=c.current_board([player()],game(),old);self.assertFalse(q);self.assertEqual(b[0]['reason'],'FROZEN_FEATURE_UNAVAILABLE')
 def test_auth_gate_before_any_source_model_or_fit_activity(self):
  with patch.object(c,'read',return_value={'forward_capture':{'new_fits_max':0,'new_capture_execution_authorized':False}}),patch.object(c,'committed_bindings') as bindings,patch.object(c,'infer_rows') as inference:
   with self.assertRaisesRegex(AssertionError,'ROOT_AUTHORIZATION'):c.infer_draft('/tmp/not-created-c05-fixture')
   bindings.assert_not_called();inference.assert_not_called()
 def test_safe_inference_clock_lineage_and_real_zero_not_null(self):
  meta=dict(family='POISSON',feature_order=['synthetic_x'],model={});specs={m:dict(path='fixture',SHA256='fixture')for m in c.MODEL_IDS}
  with patch.object(c,'read',return_value=meta),patch.object(c,'pooled_mu',return_value=np.array([0.])):
   out,delta=c.infer_rows(rows(),specs,executed_UTC='2026-11-10T23:00:00Z')
  self.assertEqual(len(out),3);self.assertEqual(delta,0.)
  for r in out:
   self.assertEqual(r['mean'],0.);self.assertEqual(r['median'],0.);self.assertIsNone(r['line']);self.assertIsNone(r['selected_side']);self.assertIsNone(r['confidence']);self.assertIsNone(r['EV'])
   self.assertEqual(r['information_cutoff_UTC'],'2026-11-10T19:23:09.469852Z');self.assertEqual(r['original_prepared_inference_UTC'],'2026-11-10T19:32:00Z');self.assertEqual(r['inference_UTC'],'2026-11-10T23:00:00Z')
  bad=rows();bad[0]['mean']=1.
  with patch.object(c,'read',return_value=meta),patch.object(c,'pooled_mu',return_value=np.array([0.])):
   with self.assertRaisesRegex(AssertionError,'MODEL_PARITY_FAILED'):c.infer_rows(bad,specs)
 def test_actual_retained_metadata_restores_no_inference(self):
  before=c.sha(c.ORIGINAL/'RUN.json');m,d,specs,old,lin=c.lineage()
  self.assertEqual(m['forecast_rows'],75);self.assertEqual(lin['target_event']['game_id'],c.TARGET);self.assertEqual(len(specs),3);self.assertEqual(sum(r['game_id']==c.TARGET for r in old),69)
  self.assertEqual(c.sha(c.ORIGINAL/'RUN.json'),before);self.assertEqual(lin['model_feature_cutoff_UTC'],'2026-11-10T19:23:09.469852+00:00')
 def test_typed_pipeline_dispatch_and_isolated_legacy_consumer(self):
  with tempfile.TemporaryDirectory() as td:
   q=Path(td);(q/'RUN.json').write_text(json.dumps({'schema':c.SCHEMA}))
   with patch.object(c,'validate_run',return_value=({'schema':c.SCHEMA},[])) as fn:
    self.assertEqual(p.validate_run(q),({'schema':c.SCHEMA},[]));fn.assert_called_once_with(q,False)
  self.assertFalse(site.legacy_feed_run({'schema':c.SCHEMA}))
  with self.assertRaisesRegex(AssertionError,'UNKNOWN'):site.legacy_feed_run({'schema':'UNKNOWN_C05'})
 def test_native_response_age_unknown_date_and_exact_byte_binding(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);source=root/'source';source.mkdir();collector=root/'collector.py';collector.write_text('synthetic, not a collector execution')
   s=dict(id='fixture',state='RECEIVED',HTTP_status=200,SHA256='0'*64,observed_UTC='2026-11-10T22:59:59Z',HTTP_Date='Tue, 10 Nov 2026 22:59:59 GMT',HTTP_Age=None)
   events=[dict(source_id='fixture',observed_UTC=s['observed_UTC'])];c.write(source/'events.json',events)
   clock=dict(c.independent_response_clock(s,c.aware(s['observed_UTC']).timestamp()),state='HTTP_RESPONSE_CLOCK_QUALIFIED',max_age_seconds=1800,future_Date_clock_skew_tolerance_seconds=5)
   manifest=dict(status_source=s,status_HTTP_response_clock=clock,model_inputs={'SHA256':'input'},status_execution_code_path='collector.py',status_execution_code_SHA256=c.sha(collector),events_binding=dict(path='source/events.json',bytes=(source/'events.json').stat().st_size,SHA256=c.sha(source/'events.json'),rows=1,source_id='fixture',observed_UTC=s['observed_UTC'],status_response_raw_SHA256='0'*64));c.write(source/'SOURCE_MANIFEST.json',manifest)
   with patch.object(c,'ROOT',root),patch.object(c,'COLLECTOR',collector):
    _,_,proof=c.validate_status(source,AT,'input',AT-2);self.assertIsNone(proof['HTTP_Age_seconds'])
    for k,v in [('HTTP_Age','7200'),('HTTP_Date','Tue, 10 Nov 2026 20:00:00 GMT')]:
     bad=copy.deepcopy(manifest);bad['status_source'][k]=v;c.write(source/'SOURCE_MANIFEST.json',bad)
     with self.assertRaises(ValueError):c.validate_status(source,AT,'input',AT-2)
    c.write(source/'SOURCE_MANIFEST.json',manifest)
    with self.assertRaisesRegex(AssertionError,'PRECEDES'):c.validate_status(source,AT,'input',AT)
    c.write(source/'events.json',[])
    with self.assertRaisesRegex(AssertionError,'BYTE_BINDING'):c.validate_status(source,AT,'input',AT-2)
 def test_complete_inference_draft_recovery_required(self):
  with tempfile.TemporaryDirectory() as td:
   run=Path(td);(run/'inference_draft').mkdir();lin={'target_event':game()}
   draft={'files':{'ATTEMPT.json':{'bytes':2,'SHA256':'f'*64}}}
   c.write(run/'INFERENCE_DRAFT.json',draft);c.write(run/'inference_draft/DRAFT.json',draft)
   m=dict(schema=c.SCHEMA,information_policy=c.POLICY,new_fits=0,real_offers=0,real_selections=0,primary_replacement=False,lineage=lin,files={})
   c.write(run/'RUN.json',m)
   with patch.object(c,'lineage',return_value=({}, {}, {}, [],lin)):
    with self.assertRaises(FileNotFoundError):c.validate_run(run)
    (run/'inference_draft/ATTEMPT.json').write_bytes(b'{}')
    with self.assertRaisesRegex(AssertionError,'BYTES_CHANGED'):c.validate_run(run)
 def test_event_version_has_no_observation_clock_shortcut(self):
  e=dict(game_id=c.TARGET,espn_event_id='401873053',kickoff_UTC='2026-11-15T14:30:00Z',state='pre',observed_UTC='2026-11-10T23:00:00Z')
  self.assertEqual(c.event_version(e),c.event_version(dict(e,observed_UTC='2026-11-10T23:01:00Z')))
  self.assertNotEqual(c.event_version(e),c.event_version(dict(e,state='in')))
 def test_naive_or_unknown_clock_not_authenticated(self):
  for v in ['2026-11-10T23:00:00',None]:
   with self.assertRaises(AssertionError):c.aware(v)

if __name__=='__main__':unittest.main()
