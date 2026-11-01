"""Fresh immutable GitHub bytes -> saved grades, scores and numeric inference.

No provider access, third-party pickle loading, acquisition loops or fitting.
Use a new temporary directory; the receipt is the durable public audit output.
"""
import argparse,csv,gzip,hashlib,io,json,sys,zipfile
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import Request,urlopen
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import numpy as np
import actual_accuracy_v6 as a
from safe_models_v4 import infer_forest
from contracts_v2 import CATEGORIES,grade

def run(commit,dest,receipt):
    assert len(commit)==40 and all(c in '0123456789abcdef' for c in commit)
    dest.mkdir(parents=True,exist_ok=False);base='https://raw.githubusercontent.com/NickNicky19/NFL-forecasting-NGS-C/'+commit+'/';files=[]
    def get(name):
        expected=a.sha(a.ROOT/name)
        with urlopen(Request(base+name,headers={'Accept-Encoding':'identity','Cache-Control':'no-cache'}),timeout=45) as r:b=r.read(33554433);assert r.status==200
        assert len(b)<=33554432 and hashlib.sha256(b).hexdigest()==expected,'RESTORE_HASH_MISMATCH:'+name
        p=dest/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b);files.append(dict(path=name,bytes=len(b),SHA256=expected,fresh_GitHub_download=True));return b
    def read(name):return json.loads(get(name))
    registry=read('reporting/actual-props-v6/DATASETS.json');rows=[];receipts=[]
    for d in registry['datasets']:
        data=read(d['path']);assert a.digest(json.loads(get(d['review_path'])))==registry['trusted_review_SHA256'][data['source_review_id']]
        assert a.sha(dest/d['path'])==d['SHA256'];rows+=data['rows'];receipts.append(dict(dataset_id=d['dataset_id'],path=d['path'],SHA256=d['SHA256'],rows=len(data['rows']),review_id=data['source_review_id']))
    for name in ['protocol/ACTUAL_ACCURACY_POLICY_V6.json','protocol/SOURCE_FACETS_V6.json','sources/propline-v7/card_pinned.md','sources/propline-v7/ATTRIBUTION.md','sources/propline-v7/historical_identity_crosswalk.json.gz','sources/propline-v7/event_native_schedule.json.gz']:get(name)
    latest=a.deduplicate(rows);score=read('reports/actual-accuracy-v6/scorecard.json');assert a.scorecard(latest,receipts)==score,'RESTORED_SCORECARD_DIFFERS'
    facts_archive=get('artifacts/basic-football-facts-v2.1.zip')
    with zipfile.ZipFile(io.BytesIO(facts_archive)) as z:
        assert z.testzip() is None;fb=gzip.decompress(z.read('facts.csv.gz'));facts={(r['game_id'],r['player_id']):r for r in csv.DictReader(io.StringIO(fb.decode()))}
    graded=0
    for r in latest:
        if r['status'] not in ['WIN','LOSS','PUSH']:continue
        fact=facts[(r['game_id'],r['player_id'])];assert float(fact[CATEGORIES[r['category']][1]])==r['actual']
        assert grade(r['actual'],r['line'],r['selected_side'])==r['status'];graded+=1
    source=get('sources/propline-v7/nfl_graded_props_14d.csv.gz');raw_count=0;offers=read('reports/propline-v7/ELIGIBLE_OFFERS.json');wanted={q['csv_line']:q for c in offers['cases'] for q in c['quotes'].values()};found=0
    for i,r in enumerate(csv.DictReader(io.StringIO(gzip.decompress(source).decode())),2):
        raw_count+=1
        if i in wanted:assert r=={k:v for k,v in wanted[i].items() if k!='csv_line'};found+=1
    assert raw_count==213190 and found==1936
    models=read('reports/propline-v7/MODEL_REPLAY.json');saved=json.loads(gzip.decompress(get('reports/propline-v7/MATCHED_SAVED_FORECASTS.json.gz')));checks=[]
    for e in models['models']:
        if e['family']!='P2_LEAF':continue
        numeric=json.loads(gzip.decompress(get(e['numeric_model_path'])));assert a.sha(dest/e['numeric_model_path'])==e['numeric_model_SHA256']
        query=next(r for r in saved if r['slot']==e['slot']);law=infer_forest(numeric,np.asarray([query['features']],float),[query['position']])[0]
        graded_row=next(r for r in latest if r['method_id']=='P2_LAW' and r['game_id']==query['game_id'] and r['player_id']==query['player_id'] and r['category']==query['target']);ps=law.probability(graded_row['line'])
        assert abs(law.mean()-query['mean'])<1e-10 and law.quantile(.5)==query['median'];assert all(abs(ps[s]-graded_row['p_'+s])<1e-10 for s in ['under','push','over']);checks.append(dict(slot=e['slot'],record_id=graded_row['record_id'],line=graded_row['line'],mean_median_exact_line_parity=True))
    primary=next(v for v in score['views'] if v['period']=='2026_W1_W7' and v['method']=='PRIMARY')
    result=dict(id='C-PROPLINE-GITHUB-RESTORE-v7.1',commit=commit,observed_UTC=datetime.now(timezone.utc).isoformat(),files=files,downloaded_bytes=sum(f['bytes'] for f in files),source_rows=raw_count,source_paired_side_rows_verified=found,original_and_correction_versions=len(rows),canonical_method_rows=len(latest),unique_offer_cases=len({r['offer_id'] for r in latest}),statistical_method_grades_recomputed=graded,primary_unique_decided=sum(c['COMBINED']['decided'] for c in primary['cells']),scorecard_reproduced=True,numeric_model_inference=checks,new_fits=0,not_claimed='Fresh original-pickle refits, historical authenticated quote availability, venue settlement or prospective wins')
    a.stable_write(receipt,result);print(json.dumps({k:v for k,v in result.items() if k not in ['files','numeric_model_inference']},indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--commit',required=True);p.add_argument('--destination',type=Path,required=True);p.add_argument('--receipt',type=Path,required=True);x=p.parse_args();run(x.commit,x.destination,x.receipt)
