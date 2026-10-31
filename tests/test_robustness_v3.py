import json,tempfile,unittest
from pathlib import Path
import numpy as np
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from robustness_v3 import Budget,fit_calibrator,calibrated,training_indices
from data_v2 import History,vector
import pandas as pd

class Robustness(unittest.TestCase):
    def test_training_prefix_strict_and_future_exclusion(self):
        rows=[dict(season=2024,available=99,values={'pass_cmp':4}),dict(season=2025,available=100,values={'pass_cmp':999}),dict(season=2026,available=1,values={'pass_cmp':999})]
        self.assertEqual(training_indices(rows,'pass_cmp',100),[0])
        rows[1]['values']['pass_cmp']=-99;rows[2]['values']['pass_cmp']=-99
        self.assertEqual(training_indices(rows,'pass_cmp',100),[0])

    def test_calibration_2025_only_complements_and_monotonicity(self):
        rows=[dict(season=2025,actual=i%4,grid=[.5,1.5,2.5],p_over=[.85,.6,.25]) for i in range(240)]
        cal=fit_calibrator(rows);q=calibrated(cal,[.9,.6,.3,.01]);self.assertGreaterEqual(cal['b'],0)
        self.assertTrue(np.all(np.diff(q)<=0));np.testing.assert_allclose(q+(1-q),1)
        with self.assertRaisesRegex(AssertionError,'2025_OOF_ONLY'):fit_calibrator(rows+[dict(season=2026)])
        self.assertTrue(cal['converged']);self.assertFalse(cal['identity_fallback'])

    def test_sparse_calibration_keeps_exact_raw_probability(self):
        rows=[dict(season=2025,actual=0,grid=[.5],p_over=[0.]) for _ in range(20)]
        cal=fit_calibrator(rows);self.assertTrue(cal['identity_fallback'])
        np.testing.assert_array_equal(calibrated(cal,[0.,.4,1.]),[0.,.4,1.])

    def test_budget_persists_and_caps_attempts_across_resume(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root);ledger=root/'ledger.json';out=root/'out'
            with Budget(ledger,out,[root]) as b:b.attempt('base')
            with Budget(ledger,out,[root]) as b:
                self.assertEqual(b.state['base_fit_attempts'],1);b.state['base_fit_attempts']=216
                with self.assertRaisesRegex(RuntimeError,'FIT_ATTEMPT_CAP'):b.attempt('base')
            data=json.loads(ledger.read_text());self.assertEqual(len(data['stage_receipts']),2)
            self.assertGreater(data['cpu_seconds'],0)
