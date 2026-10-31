import sys,unittest,subprocess,tempfile,json,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from offer_validator_v2 import validate,instant
class Importer(unittest.TestCase):
 def base(self):return dict(offer_id='fixture',venue='fixture',product='fixture',native_player_id='p',native_event_id='e',player_id='p',game_id='g',category='rec',period='full_game',comparator='OVER_UNDER',offered_sides=['OVER','UNDER'],lifecycle='OPEN',line=3.5,source_evidence_reference='SYNTHETIC_FIXTURE',observed_at_UTC='2026-01-01T12:00:00Z',persisted_at_UTC='2026-01-01T12:00:01Z')
 def test_suspended_and_conflicting_lifecycle(self):
  a=self.base();b=a|{'lifecycle':'SUSPENDED'};self.assertTrue(validate({'offers':[a,b]})['errors'])
 def test_conflicting_event_ids(self):
  a=self.base();b=a|{'offer_id':'other','game_id':'wrong'};self.assertTrue(validate({'offers':[a,b]})['errors'])
 def test_timezone_and_naive(self):
  self.assertEqual(instant('2026-01-01T06:00:00-06:00'),instant('2026-01-01T12:00:00Z'))
  with self.assertRaises(ValueError):instant('2026-01-01T12:00:00')
 def test_malformed_and_corruption_exit_failure(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'bad.json';p.write_text('{broken')
   cmd=[sys.executable,str(Path(__file__).resolve().parents[1]/'src/offer_validator_v2.py'),str(p)]
   self.assertNotEqual(subprocess.run(cmd,capture_output=True).returncode,0);p.write_text(json.dumps({'offers':[self.base()]}));self.assertNotEqual(subprocess.run(cmd+['--expected-sha256','0'*64],capture_output=True).returncode,0)
 def test_schema_is_not_live_or_rights_qualification(self):
  r=validate({'offers':[self.base()]});self.assertEqual(r['state'],'SCHEMA_VALID_NOT_RIGHTS_OR_SETTLEMENT_QUALIFIED');self.assertFalse(r['live_access_verified'])
if __name__=='__main__':unittest.main()
