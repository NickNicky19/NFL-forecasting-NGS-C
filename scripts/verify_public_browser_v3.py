"""Public acceptance wrapper; model/offer acquisition and fitting are absent."""
import argparse,json,sys
from pathlib import Path
from urllib.request import urlopen
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from browser_qa_v3 import check
from verified_https_browser import verified_public_transport

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--url',required=True);p.add_argument('--commit',required=True);p.add_argument('--root',type=Path,default=Path('docs'));p.add_argument('--receipt',type=Path,required=True);p.add_argument('--verified-https-bridge',action='store_true');a=p.parse_args()
    def served():
        with urlopen(a.url.rstrip('/')+'/build.json',timeout=30) as r:j=json.load(r)
        assert j['served_commit']==a.commit;return j
    before=served();received=[]
    if a.verified_https_bridge:
        with verified_public_transport(a.url) as received:check(a.url,a.root,a.receipt)
    else:check(a.url,a.root,a.receipt)
    after=served()
    assert before['asset_release_id']==after['asset_release_id']
    # The reused QA helper's local-only flag does not assert publication.
    # This wrapper establishes public serving from the actual build responses.
    j=json.loads(a.receipt.read_text());j['original_helper_served_flag']=j['served']
    j.update(served=True,expected_served_commit=a.commit,build_before=before,build_after=after,publication_scope='Actual public URL, exact commit checked before/after rendered acceptance; no scientific admission')
    j.update(transport='VERIFIED_SYSTEM_HTTPS_RENDERING_BRIDGE' if a.verified_https_bridge else 'NATIVE_BROWSER',native_Chromium_TLS_validated=not a.verified_https_bridge,actual_public_responses=received)
    a.receipt.write_text(json.dumps(j,indent=2)+'\n');print('PUBLIC_BROWSER_ACCEPTANCE_PASS',a.commit)
