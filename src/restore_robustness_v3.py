"""Fresh C GitHub archive readback and representative inference; zero fits."""
import argparse,gzip,hashlib,io,json,math,pickle,zipfile
from pathlib import Path
from urllib.request import urlopen
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
from robustness_v3 import calibrated

def restore(commit,report):
    manifest=json.loads((report/'ARTIFACTS.json').read_text());scores=pd.read_csv(report/'SCORES.csv');receipts=[]
    for e in manifest:
        b=urlopen('https://raw.githubusercontent.com/NickNicky19/NFL-forecasting-NGS-C/'+commit+'/'+e['path'],timeout=60).read()
        assert len(b)==e['bytes'] and hashlib.sha256(b).hexdigest()==e['SHA256']
        target=e['category'];rows=[]
        with zipfile.ZipFile(io.BytesIO(b)) as z:
            assert sum(x.file_size for x in z.infolist())<100663296 and z.testzip() is None
            for week in range(1,19):
                prefix=f'raw/{target}/W{week:02}/';d=json.loads(z.read(prefix+'DONE.json'))
                assert hashlib.sha256(z.read(prefix+'model.pkl.gz')).hexdigest()==d['model_sha256']
                assert hashlib.sha256(z.read(prefix+'rows.json.gz')).hexdigest()==d['row_sha256']
                rows+=json.loads(gzip.decompress(z.read(prefix+'rows.json.gz')))
            known=[r for r in rows if r['actual'] is not None];score=scores[(scores.target==target)&(scores.policy=='RAW_2025')&(scores.horizon=='ALL')].iloc[0]
            assert len(rows)==score.queries and len(known)==score.outcomes
            brier=np.mean([np.mean((np.asarray(r['p_over'])-(r['actual']>np.asarray(r['grid'])))**2) for r in known]);assert abs(brier-score.grid_brier)<1e-13
            if target!='anytime_td':assert abs(np.mean([abs(r['median']-r['actual']) for r in known])-score.median_mae)<1e-12
            prefix=f'raw/{target}/W18/';packet=pickle.loads(gzip.decompress(z.read(prefix+'model.pkl.gz')));query=json.loads(gzip.decompress(z.read(prefix+'rows.json.gz')))
            with threadpool_limits(limits=1):laws=packet['model'].laws(np.asarray([r['features'] for r in query],float),[r['position'] for r in query])
            for r,law in zip(query,laws):
                assert r['p_over']==[law.probability(v)['over'] for v in r['grid']]
                assert r['mean']==law.mean() and r['median']==law.quantile(.5) and r['p05']==law.quantile(.05) and r['p95']==law.quantile(.95)
                if r['actual'] is not None:assert r['crps']==law.crps(r['actual']) and r['nll']==-law.logpmf(int(round(r['actual']*packet['scale'])))
            prefix=f'calibration/{target}/';done=json.loads(z.read(prefix+'DONE.json'));cal=json.loads(z.read(prefix+'calibrator.json'));future=json.loads(gzip.decompress(z.read(prefix+'rows-2026.json.gz')))
            assert hashlib.sha256(z.read(prefix+'calibrator.json')).hexdigest()==done['calibrator_sha256'] and hashlib.sha256(z.read(prefix+'rows-2026.json.gz')).hexdigest()==done['row_sha256']
            for r in future:
                expected=calibrated(cal,r['p_raw']);assert r['p_over']==expected.tolist() and r['p_under']==(1-expected).tolist()
            receipts.append(dict(category=target,archive=e['path'],bytes=len(b),SHA256=e['SHA256'],zip_and_all_slot_hashes='PASS',raw2025_queries=len(rows),raw2025_outcomes=len(known),representative_W18_inference_queries=len(query),raw_inference='BIT_EXACT_probabilities_mean_median_intervals_CRPS_NLL',calibration_queries=len(future),calibration_inference='ALL_BIT_EXACT',scores_recomputed='PASS',new_fits=0));print('RESTORED',target,len(rows),len(query),len(future),flush=True)
    result=dict(id='C-V3-GITHUB-RESTORATION-v1',commit=commit,archives=receipts,bytes=sum(r['bytes'] for r in receipts),raw2025_queries=sum(r['raw2025_queries'] for r in receipts),raw2025_inference_queries=sum(r['representative_W18_inference_queries'] for r in receipts),calibration_inference_queries=sum(r['calibration_queries'] for r in receipts),new_fits=0)
    (report/'GITHUB_RESTORE.json').write_text(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--commit',required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args();restore(a.commit,a.report)
