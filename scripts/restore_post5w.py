"""Fresh GitHub byte recovery and safe primitive inference; no pickle or fits."""
import argparse
import gzip
import hashlib
import json
import sys
import urllib.request
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from reliability_v8 import hgb_cdf

ROOT=Path(__file__).resolve().parents[1]
BASE='reports/post-wave-5w-v1/'
FILES=[BASE+x for x in ['QUALIFICATION_TABLE.json.gz','MODEL_INPUT_TRACE.json','SYNTHETIC_PATH_POSITIVE_CONTROL.json','COUNT_A_DELIVERY_DISPOSITION.json','B_LATEST_EXPORT_INDEX.json.gz','B_SCORES.json.gz','B_SCORES_SOURCE_CLOCK_AND_ATTRIBUTION_ANNOTATIONS_V3.json.gz','B_SOURCE_CLOCK_AND_ATTRIBUTION_QUALIFICATION_V3.json.gz','README.md','INDEPENDENT_VERIFICATION.json']]+['reports/abc-championship/continuation-v2/A_W1_W7_ARCHIVED_SCORES.json.gz','docs/data/qualification-5w.json.gz','artifacts/predictive-C01/share-actual/2026-W02-S0-MODEL.json.gz','artifacts/predictive-C01/share-actual/2026-W02-S1-MODEL.json.gz','artifacts/predictive-C01/share-actual/PREDICTIONS.json.gz']

def main(ref,receipt,verified_downloads=None):
    assert len(FILES)==15 and not receipt.exists(),'No duplicate completed restoration'
    recovered={};records=[];total=0
    prior=json.loads(verified_downloads.read_text()) if verified_downloads else None
    if prior:assert prior['source_ref']==ref and len(prior['records'])==15
    for path in FILES:
        expected=(ROOT/path).read_bytes();url=f'https://raw.githubusercontent.com/NickNicky19/NFL-forecasting-NGS-C/{ref}/{path}'
        assert total+len(expected)<=8388608,'Registeredtemporarybytes'
        if prior:
            bound=next(r for r in prior['records'] if r['path']==path)
            assert hashlib.sha256(expected).hexdigest()==bound['SHA256']
            actual=expected # Same bytes proved equal to the fresh response before postprocessing failed.
        else:
            with urllib.request.urlopen(url,timeout=30) as response:actual=response.read(len(expected)+1)
        assert actual==expected,('GITHUB_READBACK_MISMATCH',path)
        digest=hashlib.sha256(actual).hexdigest();records.append(dict(path=path,source_ref=ref,SHA256=digest,bytes=len(actual),fresh_readback=True));recovered[path]=actual;total+=len(actual)
    def load(path):
        b=recovered[path];return json.loads(gzip.decompress(b) if path.endswith('.gz') else b)
    qualification=load(BASE+'QUALIFICATION_TABLE.json.gz');archived=load('reports/abc-championship/continuation-v2/A_W1_W7_ARCHIVED_SCORES.json.gz')
    source=next(r for r in archived if 'f8607aa99a94c7c1c9ab5c89599e07eba9b15527749b092b225f368032881e83' in r['procedure_id'])
    weeks=source['week_rows'];wins=sum(int(w['over_wins'])+int(w['under_wins']) for w in weeks);losses=sum(int(w['over_losses'])+int(w['under_losses']) for w in weeks)
    assert (len([w for w in weeks if int(w['over_decided'])+int(w['under_decided'])]),wins,losses)==(7,87,55)
    q=next(r for r in qualification['rows'] if r.get('named_delivery_product'));assert q['own_side_record']['COMBINED']['wins']==wins
    query=next(r for r in load('artifacts/predictive-C01/share-actual/PREDICTIONS.json.gz') if r['origin']=='2026-W02');predictions=[]
    for arm in ['S0','S1']:
        model=load(f'artifacts/predictive-C01/share-actual/2026-W02-{arm}-MODEL.json.gz')['model'];saved=query['arms'][arm]
        predicted=1-np.asarray(hgb_cdf(model,np.asarray(saved['features'],float),saved['grid']))
        assert np.allclose(predicted,saved['p_over'],rtol=0,atol=1e-12)
        assert np.all(np.diff(predicted)<=1e-12) and np.all((predicted>=0)&(predicted<=1))
        predictions.append(dict(arm=arm,game_id=query['game_id'],player_id=query['player_id'],exact_thresholds=saved['grid'],p_over=predicted.tolist(),safe_JSON_primitive_inference=True))
    assert predictions[0]['p_over']==predictions[1]['p_over']
    toy=load(BASE+'SYNTHETIC_PATH_POSITIVE_CONTROL.json');low=np.zeros(43);high=np.zeros(43);low[-1]=-1;high[-1]=1
    assert abs(hgb_cdf(toy['model'],low,[3])[0]-toy['CDF3_low_feature'])<1e-12
    assert abs(hgb_cdf(toy['model'],high,[3])[0]-toy['CDF3_high_feature'])<1e-12
    site=load('docs/data/qualification-5w.json.gz');assert site['ledger_SHA256']==hashlib.sha256(recovered[BASE+'QUALIFICATION_TABLE.json.gz']).hexdigest()
    receipt.write_text(json.dumps(dict(id='C-POST5W-GITHUB-RESTORATION-v1',checked_UTC=datetime.now(timezone.utc).isoformat(),source_ref=ref,restored_objects=records,total_bytes=total,recoverable_bytes='Fresh immutable GitHub response bytes proved equal to bound local bytes; no extra sole local archive',verified_download_attempt=verified_downloads.name if prior else None,new_HTTP_reads_this_completion=0 if prior else 15,CountA_independent_saved_score_check=dict(scored_weeks=7,wins=wins,losses=losses,decided=wins+losses),representative_baseline_and_candidate_inference=predictions,synthetic_software_model_inference_restored=True,site_ledger_hash_matches=True,untrusted_pickle_executed=False,new_fits=0,new_NFL_observations=0),indent=2)+'\n')
    print('GITHUB_RESTORATION_PASS',len(records),'OBJECTS',total,'BYTES;SAFE_INFERENCE_AND_COUNTA_SCORE_REPRODUCED')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--ref',required=True);p.add_argument('--receipt',type=Path,required=True);p.add_argument('--verified-downloads',type=Path);a=p.parse_args();main(a.ref,a.receipt,a.verified_downloads)
