import sys
import unittest
from pathlib import Path
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from forward_sources_v4 import restrict_future_batch

class FutureBatchTests(unittest.TestCase):
    def setUp(self):
        self.future=pd.DataFrame([{'game_id':'2026_09_JAX_BAL','kickoff':1},{'game_id':'2026_09_LV_SF','kickoff':2}])
    def test_default_keeps_original_full_week_and_explicit_batch_needs_no_outcomes(self):
        self.assertIs(restrict_future_batch(self.future),self.future)
        selected=restrict_future_batch(self.future,['2026_09_JAX_BAL'])
        self.assertEqual(selected.game_id.tolist(),['2026_09_JAX_BAL'])
        self.assertFalse(any(x in selected.columns for x in ['actual','played','starter']))
    def test_started_unknown_or_duplicate_game_cannot_enter_future_batch(self):
        for values in [[],['2026_09_JAX_BAL']*2,['STARTED_GAME'],['2026_09_JAX_BAL','UNKNOWN']]:
            with self.assertRaises(AssertionError):restrict_future_batch(self.future,values)

if __name__=='__main__':unittest.main()
