"""Deterministic mocked solver/control tests; no NFL fit or optimization."""
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase,main
from unittest.mock import patch
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import shared_game_sim01_condition as condition


def value(x):
    return 2.,np.zeros_like(x)


def result(x,fun=2.,success=True,status=0,message='mock success',nit=0,nfev=1):
    return SimpleNamespace(x=np.asarray(x),fun=fun,success=success,status=status,
        message=message,nit=nit,nfev=nfev)


class RepairConditionContracts(TestCase):
    def test_approved_settings_and_checkpoint_use_counted_cache(self):
        events=[];calls=[]
        def objective(x):calls.append(tuple(x));return value(x)
        def mock_minimize(fun,x,**kwargs):
            self.assertEqual(kwargs['method'],'L-BFGS-B')
            self.assertTrue(kwargs['jac'])
            self.assertEqual(kwargs['options'],dict(maxiter=500,maxfun=1000,ftol=1e-10,gtol=1e-6))
            fun(x)
            for _ in range(10):kwargs['callback'](x)
            return result(x,nit=10)
        with patch.object(condition,'minimize',side_effect=mock_minimize):
            _,record=condition._solve(objective,np.array([1.]),stage='CORE',execution=events.append)
        self.assertEqual(calls,[(1.,)])
        self.assertEqual(record['nfev'],1);self.assertEqual(record['nit'],10)
        self.assertEqual(record['gradient_infinity_norm'],0.)
        self.assertEqual([e['event'] for e in events].count('CHECKPOINT'),1)
        self.assertEqual([e['event'] for e in events].count('BEFORE_OBJECTIVE'),1)
        self.assertEqual(events[0]['event'],'STAGE_STARTED')
        self.assertEqual(events[-1]['event'],'TERMINATED')
        check=next(e for e in events if e['event']=='CHECKPOINT')
        self.assertEqual(check['last_accepted']['vector'],[1.])

    def test_hard_evaluation_counter_refuses_1001st_call(self):
        events=[];calls=0
        def objective(x):
            nonlocal calls
            calls+=1;return value(x)
        def mock_minimize(fun,x,**kwargs):
            for _ in range(1001):fun(x)
            self.fail('hard evaluation guard did not stop')
        with patch.object(condition,'minimize',side_effect=mock_minimize):
            with self.assertRaisesRegex(RuntimeError,'HARD_OBJECTIVE_EVALUATION_LIMIT') as caught:
                condition._solve(objective,np.array([1.]),execution=events.append)
        self.assertEqual(calls,1000)
        self.assertEqual(caught.exception.record['nfev'],1000)
        self.assertEqual(events[-1]['event'],'EXCEPTION')
        self.assertEqual(caught.exception.record['last_evaluated']['objective'],2.)

    def test_hard_iteration_counter_refuses_501st_callback(self):
        events=[]
        def mock_minimize(fun,x,**kwargs):
            fun(x)
            for _ in range(501):kwargs['callback'](x)
            self.fail('hard iteration guard did not stop')
        with patch.object(condition,'minimize',side_effect=mock_minimize):
            with self.assertRaisesRegex(RuntimeError,'HARD_ACCEPTED_ITERATION_LIMIT') as caught:
                condition._solve(value,np.array([1.]),execution=events.append)
        self.assertEqual(caught.exception.record['nit'],500)
        self.assertEqual([e['event'] for e in events].count('ACCEPTED_ITERATION'),500)
        self.assertEqual([e['event'] for e in events].count('CHECKPOINT'),50)

    def test_uncached_accepted_iterate_fails_without_extra_evaluation(self):
        calls=[]
        def objective(x):calls.append(tuple(x));return value(x)
        def mock_minimize(fun,x,**kwargs):
            fun(x);kwargs['callback'](x+1)
        with patch.object(condition,'minimize',side_effect=mock_minimize):
            with self.assertRaisesRegex(RuntimeError,'NOT_IN_COUNTED_OBJECTIVE_CACHE'):
                condition._solve(objective,np.array([1.]))
        self.assertEqual(calls,[(1.,)])

    def test_original_failed_success_requirement_stays_failed(self):
        events=[]
        def mock_minimize(fun,x,**kwargs):
            fun(x);return result(x,success=False,status=1,message='iteration stop')
        with patch.object(condition,'minimize',side_effect=mock_minimize):
            with self.assertRaisesRegex(RuntimeError,'PROVIDER_CONDITIONING_FAILED') as caught:
                condition._solve(value,np.array([1.]),execution=events.append)
        self.assertFalse(caught.exception.record['success'])
        self.assertEqual(caught.exception.record['status'],1)
        self.assertEqual(events[-1]['event'],'TERMINATED')

    def test_aggregate_callback_refuses_work_before_objective(self):
        calls=[]
        def objective(x):calls.append(tuple(x));return value(x)
        def audit(event):
            if event['event']=='BEFORE_OBJECTIVE':raise RuntimeError('AGGREGATE_CAP')
        def mock_minimize(fun,x,**kwargs):fun(x)
        with patch.object(condition,'minimize',side_effect=mock_minimize):
            with self.assertRaisesRegex(RuntimeError,'AGGREGATE_CAP') as caught:
                condition._solve(objective,np.array([1.]),execution=audit)
        self.assertEqual(calls,[]);self.assertEqual(caught.exception.record['nfev'],0)

    def test_zero_parameter_stage_counts_evaluation_without_optimizer(self):
        events=[];calls=[]
        def objective(x):calls.append(len(x));return 0.,np.empty(0)
        with patch.object(condition,'minimize') as solver:
            _,record=condition._solve(objective,np.empty(0),execution=events.append)
        solver.assert_not_called();self.assertEqual(calls,[0]);self.assertEqual(record['nfev'],1)
        self.assertEqual(events[0]['optimizer_invocation'],0)
        self.assertEqual(record['message'],'NO_FREE_PARAMETERS')


if __name__=='__main__':main()
