"""Fresh GitHub restoration with numeric-JSON inference, never pickle/code execution."""
import argparse,hashlib,json,sys,time,math
from pathlib import Path
from urllib.request import urlopen
from concurrent.futures import ThreadPoolExecutor
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from prospective_v4 import validate_run,validate_receipt,read_json,stamp
from safe_models_v4 import load,infer_forest

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('prospective'));p.add_argument('--output',type=Path,required=True);p.add_argument('--receipt',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False);start=time.monotonic();downloads=[];checks=[]
    for receipt_path in sorted((a.root/'receipts').glob('*.json')):
        proof=read_json(receipt_path);run=a.root/'runs'/proof['run_id'];m=read_json(run/'RUN.json');dest=a.output/'prospective/runs'/proof['run_id'];dest.mkdir(parents=True)
        files={'RUN.json':dict(SHA256=hashlib.sha256((run/'RUN.json').read_bytes()).hexdigest())}|m['files'];assert len(files)<=64
        def fetch(item):
            name,info=item;url='https://raw.githubusercontent.com/NickNicky19/NFL-forecasting-NGS-C/'+proof['capture_commit']+'/prospective/runs/'+proof['run_id']+'/'+name
            with urlopen(url,timeout=30) as response:b=response.read(16*1024*1024+1);assert len(b)<=16*1024*1024
            digest=hashlib.sha256(b).hexdigest();assert digest==info['SHA256'];p=dest/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
            return dict(run_id=proof['run_id'],path=name,bytes=len(b),SHA256=digest)
        with ThreadPoolExecutor(max_workers=4) as pool:downloads.extend(pool.map(fetch,files.items()))
        restored,rows=validate_run(dest);validate_receipt(dest,proof,restored,rows)
        for model in read_json(dest/'model_manifest.json'):
            category=model['target'];q=[r for r in rows if r['category']==category];numeric=load(dest/model['artifact'],model['model_SHA256']);x=np.asarray([[np.nan if v is None else v for v in r['features']] for r in q]);laws=infer_forest(numeric,x,[r['position'] for r in q])
            for r,law in zip(q,laws):
                if category=='anytime_td':assert math.isclose(r['event_probability'],law.probability(.5)['over'],rel_tol=1e-12,abs_tol=1e-12)
                else:assert math.isclose(r['mean'],law.mean(),rel_tol=1e-12,abs_tol=1e-10) and r['median']==law.quantile(.5) and r['p05']==law.quantile(.05) and r['p95']==law.quantile(.95)
            checks.append(dict(category=category,models=1,forecasts=len(q),numeric_JSON_inference='PASS',future_outcomes_used=False,new_fits=0))
    result=dict(id='C-GITHUB-FORWARD-RESTORATION-v4',verified_UTC=stamp(),downloads=downloads,files=len(downloads),bytes=sum(r['bytes'] for r in downloads),models=len(checks),forecasts_reproduced=sum(r['forecasts'] for r in checks),checks=checks,wall_seconds=time.monotonic()-start,downloaded_code_executed=False,pickle_loaded=False,new_fits=0,prospective_scores='PENDING_NO_OUTCOMES; forecast-only snapshots cannot have scores before games',source='Exact C capture commits and retained receipt chains')
    a.receipt.parent.mkdir(parents=True,exist_ok=True)
    with a.receipt.open('x') as f:json.dump(result,f,indent=2)
    print('FORWARD_GITHUB_RESTORE_PASS',result['models'],result['forecasts_reproduced'],result['bytes'])
