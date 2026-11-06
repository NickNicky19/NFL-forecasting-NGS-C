import copy,unittest
from freshness_query_shadow_v1 import reconcile_numeric_rows

class FrozenPrecisionTest(unittest.TestCase):
    def row(self):return dict(player_id='fixed',actual=None,line=None,selected_side=None,proxy_median=2,proxy_mean=2.123456789,proxy_law=dict(values=[0,2],weights=[.25,.75],prior={'fixed':True},scale=1,alpha=.05))
    def test_only_small_reduction_differences_pass(self):
        a=self.row();b=copy.deepcopy(a);b['proxy_mean']+=1e-14;b['proxy_law']['weights']=[.25+1e-16,.75-1e-16];reconcile_numeric_rows([a],[b])
        for field,value in [('player_id','wrong'),('proxy_median',3),('proxy_mean',2.13)]:
            b=copy.deepcopy(a);b[field]=value
            with self.assertRaises(AssertionError):reconcile_numeric_rows([a],[b])
        b=copy.deepcopy(a);b['proxy_law']['weights']=[.250001,.749999]
        with self.assertRaises(AssertionError):reconcile_numeric_rows([a],[b])
