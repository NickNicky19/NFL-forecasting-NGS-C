import math,unittest
from selection import grade,brier
from contracts_v2 import grade as canonical_grade

class NonfiniteGradingTest(unittest.TestCase):
    def test_missing_and_nonfinite_actuals_never_become_wins(self):
        for actual in [None,float('nan'),float('inf'),float('-inf')]:
            for side in ['UNDER','OVER']:
                self.assertEqual(grade(side,actual,2.5),'MISSING_ACTUAL')
                self.assertEqual(canonical_grade(actual,2.5,side),'MISSING_ACTUAL')
            self.assertIsNone(brier(.5,0,.5,actual,2.5))

    def test_missing_or_nonfinite_line_has_no_grade_or_score(self):
        for line in [None,float('nan'),float('inf'),float('-inf')]:
            self.assertEqual(grade('UNDER',0,line),'UNAVAILABLE')
            self.assertIsNone(brier(.5,0,.5,0,line))

    def test_valid_zero_signed_and_fractional_boundaries_are_preserved(self):
        for side,actual,line,expected in [('UNDER',0,.5,'WIN'),('OVER',0,.5,'LOSS'),('UNDER',-2,-1.5,'WIN'),('OVER',19.2,19.2,'PUSH')]:
            self.assertEqual(grade(side,actual,line),expected)
        self.assertEqual(brier(.5,0,.5,0,.5),.25)
        self.assertEqual(grade('UNDER',None,.5,'UNKNOWN_PARTICIPATION'),'UNKNOWN_PARTICIPATION')
        self.assertIsNone(brier(float('nan'),0,.5,0,.5))
