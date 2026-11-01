"""Verify the public accuracy-first site and unchanged forecast assets via TLS."""
import argparse,hashlib,json,sys
from pathlib import Path
from urllib.request import Request,urlopen
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from browser_qa_accuracy_v6 import check as accuracy_check
from browser_qa_forward_v4 import check as forward_check
from browser_qa_reliability_v8 import check as reliability_check
from verified_https_browser import verified_public_transport

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--url',required=True);p.add_argument('--commit',required=True);p.add_argument('--root',type=Path,default=Path('docs'));p.add_argument('--receipt',type=Path,required=True);a=p.parse_args();a.receipt.parent.mkdir(parents=True,exist_ok=True);base=a.url.rstrip('/')+'/';assets=[]
    def get(name):
        cap=33554432 if name=='data/actual-accuracy-v6.json' else 8388608
        with urlopen(Request(base+name,headers={'Cache-Control':'no-cache','Accept-Encoding':'identity'}),timeout=30) as r:b=r.read(cap+1)
        assert len(b)<=cap;assets.append(dict(path=name,SHA256=hashlib.sha256(b).hexdigest(),bytes=len(b),system_TLS_verified=True));return b
    before=json.loads(get('build.json'));assert before['served_commit']==a.commit,'SERVED_COMMIT_MISMATCH'
    for path in ['index.html','app.js','forward.js','paper.js','accuracy.js','reliability.js','style.css','data/manifest.json','data/forward-manifest.json','data/actual-props-v5.json','data/actual-accuracy-v6.json','data/reliability-v8.json']:assert get(path)==(a.root/path).read_bytes(),'SERVED_ASSET_MISMATCH:'+path
    assert hashlib.sha256((a.root/'data/actual-accuracy-v6.json').read_bytes()).hexdigest()==before['actual_accuracy_SHA256']
    assert hashlib.sha256((a.root/'data/reliability-v8.json').read_bytes()).hexdigest()==before['reliability_v8_SHA256']
    m=json.loads((a.root/'data/forward-manifest.json').read_text())
    for row in m['files']:assert hashlib.sha256(get('data/'+row['file'])).hexdigest()==row['SHA256']
    with verified_public_transport(a.url) as responses:
        ar=a.receipt.parent/'accuracy-public/RENDERED.json';ar.parent.mkdir(parents=True,exist_ok=True);accuracy_check(a.url,a.root,ar,a.commit)
        fr=a.receipt.parent/'forward-public/RENDERED.json';fr.parent.mkdir(parents=True,exist_ok=True);forward_check(base+'#upcoming',a.root,fr,a.commit)
        rr=a.receipt.parent/'reliability-public/RENDERED.json';rr.parent.mkdir(parents=True,exist_ok=True);reliability_check(base+'#reliability',a.root,rr,a.commit)
    after=json.loads(get('build.json'));assert before==after,'DEPLOYMENT_CHANGED_DURING_ACCEPTANCE'
    accuracy=json.loads((a.root/'data/actual-accuracy-v6.json').read_text());primary=next(v for v in accuracy['views'] if v['period']=='2026_W1_W7' and v['method']=='PRIMARY')
    a.receipt.write_text(json.dumps(dict(id='C-ACTUAL-RELIABILITY-PUBLIC-SERVED-v8',served_commit=a.commit,build_before=before,build_after=after,assets=assets,actual_public_responses=responses,transport='VERIFIED_SYSTEM_HTTPS_RENDERING_BRIDGE',native_Chromium_TLS_validated=False,TLS_checks_disabled=False,default_view='ACTUAL_PROP_ACCURACY',forward_regression_scope='Explicit #upcoming deep link; earlier helper default-upcoming field refers to that supplied URL, not the v6 root landing',accuracy_rendered='accuracy-public/RENDERED.json',forward_rendered='forward-public/RENDERED.json',reliability_rendered='reliability-public/RENDERED.json',NFL_unique_offers=len({r['offer_id'] for r in accuracy['records']}),primary_decided=sum(c['COMBINED']['decided'] for c in primary['cells']),new_NFL_fits=0,website_state='SERVED_VERIFIED_SELECTED_SIDE_DIAGNOSTICS' if accuracy['records'] else 'SERVED_VERIFIED_ACCURACY_FIRST_SOURCE_HOLDS',forecasts_or_quotes_refreshed=False),indent=2)+'\n');print('PUBLIC_ACCURACY_FIRST_PASS',a.commit,len(assets))
