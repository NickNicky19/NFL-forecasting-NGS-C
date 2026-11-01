"""Recover fresh immutable GitHub bytes and recompute grades/inference, no fits.

Only JSON, gzip, CSV and the facts ZIP are parsed. No downloaded pickle/code runs.
"""
import argparse,csv,gzip,hashlib,io,json,sys,zipfile
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import Request,urlopen
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import numpy as np
import actual_accuracy_v6 as a
from contracts_v2 import CATEGORIES,grade,thresholds_for_line
from safe_models_v4 import infer_forest,law_load,law_data
from reliability_v8 import hgb_cdf,key
from workload_link_v8 import forecast_bins,linked_law

def run(commit,dest,receipt):
    assert len(commit)==40 and all(c in '0123456789abcdef' for c in commit)
    dest.mkdir(parents=True,exist_ok=False);base='https://raw.githubusercontent.com/NickNicky19/NFL-forecasting-NGS-C/'+commit+'/';files=[];cache={}
    def get(path):
        if path in cache:return cache[path]
        with urlopen(Request(base+path,headers={'Cache-Control':'no-cache','Accept-Encoding':'identity'}),timeout=45) as r:b=r.read(33554433);assert r.status==200
        assert len(b)<=33554432 and hashlib.sha256(b).hexdigest()==a.sha(a.ROOT/path),'RESTORE_HASH_MISMATCH:'+path
        target=dest/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(b);cache[path]=b;files.append(dict(path=path,SHA256=hashlib.sha256(b).hexdigest(),bytes=len(b),fresh_GitHub_download=True));return b
    def read(path):return json.loads(gzip.decompress(get(path)) if path.endswith('.gz') else get(path))
    registry=read('reporting/actual-props-v6/DATASETS.json');rows=[];receipts=[]
    for d in registry['datasets']:
        j=read(d['path']);review=read(d['review_path']);assert a.digest(review)==registry['trusted_review_SHA256'][j['source_review_id']]
        assert hashlib.sha256(get(d['path'])).hexdigest()==d['SHA256'];rows+=j['rows'];receipts.append(dict(dataset_id=d['dataset_id'],path=d['path'],SHA256=d['SHA256'],rows=len(j['rows']),review_id=j['source_review_id']))
    for path in ['protocol/ACTUAL_ACCURACY_POLICY_V6.json','protocol/PROSPECTIVE_V4.json','protocol/SOURCE_FACETS_V6.json','protocol/SELECTED_RELIABILITY_V8.json','protocol/WORKLOAD_LINK_V8.json','sources/propline-v7/card_pinned.md','sources/propline-v7/ATTRIBUTION.md']:
        get(path)
    latest=a.deduplicate(rows);score=read('reports/actual-accuracy-v6/scorecard.json');oldroot,oldpolicy,oldmanifest=a.ROOT,a.POLICY,a.MANIFEST
    try:
        a.ROOT=dest;a.POLICY=dest/'protocol/ACTUAL_ACCURACY_POLICY_V6.json';a.MANIFEST=dest/'reporting/actual-props-v6/DATASETS.json';assert a.scorecard(latest,receipts)==score,'RESTORED_CANONICAL_SCORECARD_DIFFERS'
    finally:a.ROOT,a.POLICY,a.MANIFEST=oldroot,oldpolicy,oldmanifest
    with zipfile.ZipFile(io.BytesIO(get('artifacts/basic-football-facts-v2.1.zip'))) as z:
        assert z.testzip() is None;facts={(r['game_id'],r['player_id']):r for r in csv.DictReader(io.StringIO(gzip.decompress(z.read('facts.csv.gz')).decode()))}
    n=0
    for r in latest:
        if r['status'] not in ['WIN','LOSS','PUSH']:continue
        f=facts[(r['game_id'],r['player_id'])];assert float(f[CATEGORIES[r['category']][1]])==r['actual'] and grade(r['actual'],r['line'],r['selected_side'])==r['status'];n+=1
    source=get('sources/propline-v7/nfl_graded_props_14d.csv.gz');cases=read('reports/propline-v7/ELIGIBLE_OFFERS.json')['cases']+read('artifacts/reliability-v8/BOOK_CASES.json.gz')['cases'];wanted={q['csv_line']:q for c in cases for q in c['quotes'].values()};seen=0
    for i,r in enumerate(csv.DictReader(io.StringIO(gzip.decompress(source).decode())),2):
        if i in wanted:assert r=={k:v for k,v in wanted[i].items() if k!='csv_line'};seen+=1
    assert seen==5538
    bank=read('artifacts/reliability-v8/REFERENCE_BANK.json.gz');inference=[]
    for cat in ['pass_yd','rush_yd','rec','rec_yd']:
      for week in [2,3]:
        model=read(f'reports/propline-v7/models/{cat}-W{week:02}.json.gz');refs=[x for x in bank['references'].values() if x['saved']['target']==cat and x['saved']['week']==week]
        q=refs[0];r=q['saved'];law=infer_forest(model,np.asarray([r['features']],float),[r['position']])[0];assert law_data(law)==q['law']
        offer=next(x for x in latest if x['category']==cat and x['game_id']==r['game_id'] and x['player_id']==r['player_id'] and x['method_id']=='P3_DIRECT');lo,hi,_=thresholds_for_line(offer['line'],1);cp=hgb_cdf(bank['direct_models'][q['direct_model_id']],r['features'],[lo,hi]);assert np.allclose([cp[0],cp[1]-cp[0],1-cp[1]],[offer['p_under'],offer['p_push'],offer['p_over']],rtol=0,atol=1e-10);inference.append(dict(category=cat,week=week,P2_full_law_and_P3_exact_line=True))
    workload=read('artifacts/reliability-v8/WORKLOAD_PREDICTIONS.json.gz');models={};new_inference=[]
    for origin in sorted({r['origin_id'] for r in workload}):
        models[origin]=(read('artifacts/reliability-v8/workload-models/'+origin+'/attempt_model.json.gz'),read('artifacts/reliability-v8/workload-models/'+origin+'/joint_model.json.gz'));get('artifacts/reliability-v8/workload-models/'+origin+'/membership.json.gz')
    for r in workload:
        nm,joint=models[r['origin_id']];nLaw=infer_forest(nm,np.asarray([r['features']],float),['QB'])[0];assert law_data(nLaw)==r['attempt_law'];base_law,_=linked_law(joint,r['features']);new,_=linked_law(joint,r['features'],forecast_bins(nLaw));assert law_data(base_law)==r['arms']['P2_LINKED_V8']['law'] and law_data(new)==r['arms']['P2_WORKLOAD_V8']['law'];new_inference.append(r['origin_id'])
    ranks=read('artifacts/reliability-v8/RANK_MEMBERSHIP.json.gz');sums=read('reports/reliability-v8/RANK_RESULTS.json.gz');byid={r['record_id']:r for r in latest}
    for s in sums:
        m=[r for r in ranks if r['diagnostic_id']==s['diagnostic_id']];assert len(m)==s['selected_count'] and len({r['player_id'] for r in m})==len(m);counts=Counter(byid[r['record_id']]['status'] for r in m);assert counts['WIN']==s['wins'] and counts['LOSS']==s['losses']
    get('docs/data/reliability-v8.json');get('reports/reliability-v8/WORKLOAD_PAIRED_UNCERTAINTY.json')
    result=dict(id='C-SELECTED-RELIABILITY-GITHUB-RESTORE-v8',commit=commit,observed_UTC=datetime.now(timezone.utc).isoformat(),files=files,downloaded_bytes=sum(f['bytes'] for f in files),canonical_method_rows=len(latest),unique_offer_quotes=len(cases),source_side_quotes_verified=seen,statistical_method_grades_recomputed=n,scorecard_reproduced=True,baseline_inference=inference,workload_representative_inference=dict(Counter(new_inference)),ranked_lists_reconciled=len(sums),model_format='NUMERIC_JSON_ONLY_NO_PICKLE',new_fits=0,original_v7_and_v4_receipts_preserved=True,not_claimed='Authenticated historical quote freshness, current paper admission, venue settlement, entry success, or predictive improvement')
    a.stable_write(receipt,result);print(json.dumps({k:v for k,v in result.items() if k not in ['files','baseline_inference']},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--commit',required=True);p.add_argument('--destination',type=Path,required=True);p.add_argument('--receipt',type=Path,required=True);x=p.parse_args();run(x.commit,x.destination,x.receipt)
