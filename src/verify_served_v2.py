"""Bounded public served-byte verification. No acquisition or forecast refresh."""
import argparse,hashlib,json
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import Request,urlopen

def verify(url,root,commit,receipt):
    fetched=[]
    def get(path):
        req=Request(url.rstrip('/')+'/'+path,headers={'Cache-Control':'no-cache','User-Agent':'Session-C-served-verifier-v2'})
        with urlopen(req,timeout=30) as r:
            value=r.read(8*1024*1024+1)
            assert len(value)<=8*1024*1024,'per-file verification budget'
        return value
    build=json.loads(get('build.json'))
    assert build['served_commit']==commit,(build['served_commit'],commit)
    assert build['status']=='HISTORICAL_RECONSTRUCTION_NOT_LIVE'
    assert build['data_as_of_UTC'] is None,'unknown authenticated clock must remain unknown'
    manifest=json.loads((root/'data/manifest.json').read_bytes())
    paths=['index.html','app.js','style.css','data/manifest.json','data/calibration.json','data/six-leg.json']
    paths += ['data/'+e['file'] for e in manifest['files'] if e['week']==7 and e['history']=='H-MULTI']
    for path in paths:
        remote=get(path);expected=hashlib.sha256((root/path).read_bytes()).hexdigest()
        actual=hashlib.sha256(remote).hexdigest();assert actual==expected,path
        fetched.append(dict(path=path,bytes=len(remote),sha256=actual,parity='EXACT'))
    assert build['asset_release_id']==hashlib.sha256((root/'data/manifest.json').read_bytes()).hexdigest()
    result=dict(checked_UTC=datetime.now(timezone.utc).isoformat(),url=url,served_commit=commit,build=build,assets=fetched,verified_bytes=sum(x['bytes'] for x in fetched),scope='Root assets and full manifest plus all W7 H-MULTI P2/P3 row assets across twelve categories; not all 756 row payloads independently downloaded',source_data_refreshed=False,new_fits=0)
    receipt.write_text(json.dumps(result,indent=2)+'\n');print('SERVED_ASSET_PARITY_PASS',commit,len(fetched),result['verified_bytes'])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--url',required=True);p.add_argument('--root',type=Path,default=Path('docs'));p.add_argument('--commit',required=True);p.add_argument('--receipt',type=Path,required=True);a=p.parse_args();verify(a.url,a.root,a.commit,a.receipt)
