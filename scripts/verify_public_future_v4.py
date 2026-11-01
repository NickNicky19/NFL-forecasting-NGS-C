"""Actual public served-commit/asset/rendered verification, no source refresh."""
import argparse,json,sys,hashlib
from pathlib import Path
from urllib.request import Request,urlopen
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from browser_qa_forward_v4 import check
from verified_https_browser import verified_public_transport

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--url',required=True);p.add_argument('--commit',required=True);p.add_argument('--root',type=Path,default=Path('docs'));p.add_argument('--receipt',type=Path,required=True);a=p.parse_args();base=a.url.rstrip('/')+'/';assets=[]
    def get(name):
        with urlopen(Request(base+name,headers={'Cache-Control':'no-cache','Accept-Encoding':'identity'}),timeout=30) as r:b=r.read(8*1024*1024+1);assert len(b)<=8*1024*1024
        assets.append(dict(path=name,SHA256=hashlib.sha256(b).hexdigest(),bytes=len(b),system_TLS_verified=True));return b
    before=json.loads(get('build.json'));assert before['served_commit']==a.commit
    for name in ['index.html','app.js','forward.js','style.css','data/manifest.json','data/forward-manifest.json']:
        assert hashlib.sha256(get(name)).hexdigest()==hashlib.sha256((a.root/name).read_bytes()).hexdigest(),'SERVED_ASSET_MISMATCH_'+name
    m=json.loads((a.root/'data/forward-manifest.json').read_text())
    for item in m['files']:assert hashlib.sha256(get('data/'+item['file'])).hexdigest()==item['SHA256']
    with verified_public_transport(a.url) as received:check(a.url,a.root,a.receipt,a.commit)
    after=json.loads(get('build.json'));assert after==before,'DEPLOYMENT_CHANGED_DURING_ACCEPTANCE'
    j=json.loads(a.receipt.read_text());j.update(served=True,build_before=before,build_after=after,assets=assets,actual_public_responses=received,transport='VERIFIED_SYSTEM_HTTPS_RENDERING_BRIDGE',native_Chromium_TLS_validated=False,scope='Exact actual public responses/rendered rows. Managed native Chromium proxy CA unavailable; no TLS checks disabled. Build never refreshes forecasts or quotes.')
    a.receipt.write_text(json.dumps(j,indent=2)+'\n');print('PUBLIC_FUTURE_ACCEPTANCE_PASS',a.commit,len(assets))
