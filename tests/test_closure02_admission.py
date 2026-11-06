import json,tempfile,unittest
from pathlib import Path
from site_forward_v4 import admission_for,refreshed_status

class ShadowAndStatusTest(unittest.TestCase):
    def test_admission_is_bound_to_frozen_forecast_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'metadata').mkdir();m=dict(run_id='r',files={'forecasts.json.gz':{'SHA256':'a'}})
            p=root/'metadata/r-admission.json';p.write_text(json.dumps(dict(run_id='r',forecast_SHA256='a',admission='SHADOW_FORECAST_ONLY_NOT_PRIMARY_REPLACEMENT',qualified_actual_offers=0)))
            self.assertEqual(admission_for(root,root/'runs/r',m),'SHADOW_FORECAST_ONLY_NOT_PRIMARY_REPLACEMENT')
            m['files']['forecasts.json.gz']['SHA256']='b'
            with self.assertRaises(AssertionError):admission_for(root,root/'runs/r',m)

    def test_status_does_not_transfer_to_another_forecast_or_changed_event(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'metadata').mkdir();r=dict(run_id='r',game_id='g',espn_event_id='1',kickoff_UTC='2026-11-06T01:15:00+00:00')
            q=dict(schema='C-FORWARD-STATUS-REFRESH-v1',forecast_sources_SHA256={'r':'a'},created_UTC='2026-11-05T23:54:00+00:00',events=[dict(game_id='g',espn_event_id='1',kickoff_UTC=r['kickoff_UTC'],observed_UTC='2026-11-05T23:54:00+00:00',state='pre')],rejected=[])
            p=root/'metadata/STATUS_test.json';p.write_text(json.dumps(q))
            self.assertTrue(refreshed_status(root,r,'a')['current_event_permitted'])
            self.assertEqual(refreshed_status(root,r,'b'),{})
            q['events'][0]['espn_event_id']='2';p.write_text(json.dumps(q))
            with self.assertRaises(AssertionError):refreshed_status(root,r,'a')
            q['events']=[];q['rejected']=[dict(game_id='g',reason='STARTED')];p.write_text(json.dumps(q))
            self.assertFalse(refreshed_status(root,r,'a')['current_event_permitted'])
