from pathlib import Path
from urllib.request import Request,urlopen
import hashlib,json,lzma,sys,datetime,numpy as np
R=Path('/workspace/ngs-c');sys.path.insert(0,str(R/'src'))
from safe_models_v4 import infer_forest
commit='0913ce73e31c8189a5191e7e7e019f280dac889c';paths=['reports/profile-closure-next-02/timing/POINT_HANDOFF.json.xz','artifacts/receiving-timing-c04/2025-W01-F3.json.xz','artifacts/receiving-timing-c04/CANARY_QUERIES-2025.json.xz'];rows=[];download={};cache=Path('/workspace/c04-historical-readback');cache.mkdir(exist_ok=True)
for name in paths:
 with urlopen(Request('https://raw.githubusercontent.com/NickNicky19/NFL-forecasting-NGS-C/'+commit+'/'+name,headers={'User-Agent':'C04-permitted-restoration'}),timeout=30) as r:b=r.read(2*1024*1024);assert r.status==200 and len(b)<2*1024*1024
 expected=(R/name).read_bytes();assert b==expected;target=cache/Path(name).name;target.write_bytes(b);download[name]=json.loads(lzma.decompress(b));rows.append(dict(path=name,bytes=len(b),SHA256=hashlib.sha256(b).hexdigest(),actual_readback=True))
can=next(x for x in download[paths[2]] if x['origin']=='2025-W01' and x['arm']=='F3');law=infer_forest(download[paths[1]]['model'],np.array([[float('nan') if x is None else x for x in can['feature_vector']]]),[can['position']])[0]
assert abs(law.mean()-can['expected_mean'])<1e-10 and law.quantile(.5)==can['expected_median']
receipt=dict(id='C04-FRESH-HISTORICAL-POINT-RESTORATION-v1',at_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),commit=commit,files=rows,GETs=3,bytes=sum(r['bytes'] for r in rows),primitive_JSON_restoration=True,model_origin='2025-W01-F3',expected_mean=can['expected_mean'],restored_mean=law.mean(),restored_median=law.quantile(.5),tolerance=1e-10,unsafe_model_loading=False,new_fits=0,new_NFL_observations=0,peer_receipt='A_NOT_VERIFIED;publisherreadbackonly')
(R/'reports/profile-closure-next-02/FRESH_HISTORICAL_GITHUB_RESTORE.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
