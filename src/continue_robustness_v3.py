"""Explicit retention-only continuation; scientific functions stay byte-frozen."""
import argparse,hashlib,json,resource
from pathlib import Path
from robustness_v3 import Budget,raw_wave,calibrate,tree_bytes,write,sha

class RetentionBudget(Budget):
    def __init__(self,path,out,roots):
        super().__init__(path,out,roots)
        self.state['resource_amendment']='C-V3-RETENTION-CONTINUATION-R1'
        self.state['resource_driver_SHA256']=sha(Path(__file__))
        self.persist()
    def check(self):
        self.checkpoint();cpu=self.state['cpu_seconds'];wall=self.state['wall_seconds']
        rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024;cache=sum(tree_bytes(r) for r in self.roots)
        self.state['peak_RSS_bytes']=max(rss,self.state['peak_RSS_bytes']);self.state['peak_cache_bytes']=max(cache,self.state['peak_cache_bytes']);self.persist()
        if cpu>600 or wall>900:raise RuntimeError('CUMULATIVE_TIME_CAP')
        if rss>1073741824:raise RuntimeError('RSS_CAP')
        if cache>2684354560:raise RuntimeError('WHOLE_C_CACHE_CAP_R1')
        if tree_bytes(self.out)>100663296:raise RuntimeError('NEW_SCIENCE_CAP_R1')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--inputs',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--old-wave',type=Path,required=True);p.add_argument('--budget-ledger',type=Path,required=True);p.add_argument('--cache-root',type=Path,action='append',required=True);p.add_argument('--stage',choices=['raw','calibration','report'],required=True);p.add_argument('--report',type=Path);a=p.parse_args()
    amendment=json.loads(Path('protocol/OOF_RETENTION_CONTINUATION_V3_R1.json').read_text());assert amendment['remaining_raw_slots']==9 and amendment['max_total_base_attempts']==216
    with RetentionBudget(a.budget_ledger,a.out,a.cache_root) as b:
        if a.stage=='raw':raw_wave(a.inputs,a.out,b)
        elif a.stage=='calibration':calibrate(a.out,a.old_wave,b)
        else:
            from report_robustness_v3 import report
            assert a.report is not None;report(a.out,a.report)
