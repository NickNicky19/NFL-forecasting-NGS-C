"""Exact C Pages assets plus rendered append-only grades and saved list membership."""
import argparse,hashlib,json,sys
from pathlib import Path
from urllib.request import Request,urlopen
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from browser_qa_week8_v9 import check as new_check
from browser_qa_forward_v4 import check as forward_check
from verified_https_browser import verified_public_transport

def main():
    p=argparse.ArgumentParser();p.add_argument('--url',required=True);p.add_argument('--commit',required=True);p.add_argument('--root',type=Path,default=Path('docs'));p.add_argument('--work',type=Path,required=True);p.add_argument('--receipt',type=Path,required=True);a=p.parse_args();a.work.mkdir(parents=True,exist_ok=False);assets=[];base=a.url.rstrip('/')+'/'
    def get(name):
        with urlopen(Request(base+name,headers={'Cache-Control':'no-cache','Accept-Encoding':'identity'}),timeout=30) as r:b=r.read(33554433)
        assert len(b)<=33554432;assets.append(dict(path=name,SHA256=hashlib.sha256(b).hexdigest(),bytes=len(b),system_TLS_verified=True));return b
    before=json.loads(get('build.json'));assert before['served_commit']==a.commit
    files=['index.html','app.js','forward.js','paper.js','accuracy.js','reliability.js','week8.js','topk.js','style.css','data/manifest.json','data/actual-props-v5.json','data/actual-accuracy-v6.json','data/reliability-v8.json','data/week8-results-v9.json','data/topk-reference-v9.json','data/topk-membership-v9.json.gz','data/forward-manifest.json']
    m=json.loads((a.root/'data/forward-manifest.json').read_bytes());files+=['data/'+f['file'] for f in m['files']]
    for path in files:assert get(path)==(a.root/path).read_bytes(),'SERVED_BYTE_MISMATCH:'+path
    with verified_public_transport(a.url) as responses:
        new_check(base+'#prospective',a.root,a.work/'new/RENDERED.json',a.commit)
        forward_check(base+'#upcoming',a.root,a.work/'forward/RENDERED.json',a.commit)
    after=json.loads(get('build.json'));assert before==after,'PUBLIC_BUILD_CHANGED_DURING_CHECK'
    grade=json.loads((a.root/'data/week8-results-v9.json').read_bytes());rank=json.loads((a.root/'data/topk-reference-v9.json').read_bytes())
    a.receipt.parent.mkdir(parents=True,exist_ok=True)
    # Assertions and row values are durable evidence. Screenshots are local preview aids.
    rendered={name:json.loads((a.work/folder/'RENDERED.json').read_bytes()) for name,folder in [('week8_and_ranks','new'),('upcoming_regression','forward')]}
    result=dict(id='C-WEEK8-TOPK-PUBLIC-SERVED-v9',served_commit=a.commit,build_before=before,build_after=after,assets=assets,actual_public_responses=responses,rendered=rendered,transport='ACTUAL_PUBLIC_RESPONSES_SYSTEM_TLS_BRIDGE',native_Chromium_TLS_validated=False,TLS_checks_disabled=False,forecast_grade_version=grade['version'],graded=grade['graded_forecasts'],unknown=grade['states']['UNKNOWN'],pending=grade['states']['PENDING'],actual_Week8_original_selections=0,actual_Week8_qualified_replays=0,TopK_weekly_lists=len(rank['weekly']),all_12categories_visible=True,mobile_desktop_DST_failure_closed=True,original_forecast_assets_unchanged=True,forecasts_or_quotes_refreshed_by_deployment=False,scientific_promotion=False,new_NFL_fits=0,website_state='SERVED_VERIFIED_WEEK8_TO_DATE_AND_EXPOSED_RANKING_AUDIT')
    with a.receipt.open('x') as f:json.dump(result,f,indent=2)
    print('PUBLIC_WEEK8_RANKING_SERVED_PASS',a.commit,len(assets),1441,810)

if __name__=='__main__':main()
