"""Exact C served assets and actual rendered rows, with system-verified TLS."""
import argparse,hashlib,json,sys
from pathlib import Path
from urllib.request import Request,urlopen
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from browser_qa_forward_v4 import check as forward_check
from browser_qa_paper_v5 import check as paper_check
from verified_https_browser import verified_public_transport

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--url',required=True);p.add_argument('--commit',required=True);p.add_argument('--root',type=Path,default=Path('docs'));p.add_argument('--receipt',type=Path,required=True);a=p.parse_args();a.receipt.parent.mkdir(parents=True,exist_ok=True);base=a.url.rstrip('/')+'/';assets=[]
    def get(name):
        with urlopen(Request(base+name,headers={'Cache-Control':'no-cache','Accept-Encoding':'identity'}),timeout=30) as r:b=r.read(8388609)
        assert len(b)<=8388608;assets.append(dict(path=name,SHA256=hashlib.sha256(b).hexdigest(),bytes=len(b),system_TLS_verified=True));return b
    before=json.loads(get('build.json'));assert before['served_commit']==a.commit,'SERVED_COMMIT_MISMATCH'
    for path in ['index.html','app.js','forward.js','paper.js','style.css','data/manifest.json','data/forward-manifest.json','data/actual-props-v5.json']:
        assert get(path)==(a.root/path).read_bytes(),'SERVED_ASSET_MISMATCH:'+path
    assert hashlib.sha256((a.root/'data/actual-props-v5.json').read_bytes()).hexdigest()==before['actual_props_SHA256']
    manifest=json.loads((a.root/'data/forward-manifest.json').read_text())
    for row in manifest['files']:assert hashlib.sha256(get('data/'+row['file'])).hexdigest()==row['SHA256']
    with verified_public_transport(a.url) as responses:
        forward_path=a.receipt.parent/'forward-public/RENDERED.json';forward_path.parent.mkdir(parents=True,exist_ok=True);forward_check(a.url,a.root,forward_path,a.commit)
        paper_path=a.receipt.parent/'paper-public/RENDERED.json';paper_path.parent.mkdir(parents=True,exist_ok=True);paper_check(a.url,paper_path)
    after=json.loads(get('build.json'));assert before==after,'DEPLOYMENT_CHANGED_DURING_ACCEPTANCE'
    a.receipt.write_text(json.dumps(dict(id='C-ACTUAL-OFFER-PUBLIC-SERVED-v5',served_commit=a.commit,build_before=before,build_after=after,assets=assets,actual_public_responses=responses,transport='VERIFIED_SYSTEM_HTTPS_RENDERING_BRIDGE',native_Chromium_TLS_validated=False,TLS_checks_disabled=False,forward_rendered='forward-public/RENDERED.json',actual_offer_rendered='paper-public/RENDERED.json',NFL_offers_graded=0,website_state='SERVED_VERIFIED_SOURCE_HELD_ADAPTER',quotes_or_forecasts_refreshed=False),indent=2)+'\n');print('PUBLIC_EXACT_OFFER_PARITY_PASS',a.commit,len(assets))
