import sys,unittest
from pathlib import Path
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from forward_sources_v4 import quarantine_stat_orphans
class NativeSourcePresence(unittest.TestCase):
 def fixture(self):
  p=Path(__file__).resolve().parents[1]/'prospective/outcomes/C-NATIVE-GRADE-20261107-JAXBAL-01/evidence/player_facts.csv.gz'
  return pd.read_csv(p)
 def test_real_null_native_row_is_separate_from_reported_zero(self):
  d=self.fixture();valid,held=quarantine_stat_orphans(d);self.assertEqual(len(held),1);self.assertEqual(len(valid),len(d)-1);self.assertTrue(valid.player_id.notna().all())
  self.assertTrue((valid.receptions==0).any())
 def test_nonzero_or_unknown_orphan_cannot_disappear(self):
  for value in [1,None]:
   d=self.fixture();d.loc[d.player_id.isna(),'receptions']=value
   with self.assertRaisesRegex(AssertionError,'UNKNOWN_OR_NONZERO'):quarantine_stat_orphans(d)
if __name__=='__main__':unittest.main()
