"""Fresh immutable GitHub readback, primitive inference and saved-score recovery."""
import argparse
import gzip
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import Request,urlopen

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from reliability_v8 import hgb_cdf


def main():
    p=argparse.ArgumentParser();p.add_argument('--commit',required=True);p.add_argument('--receipt',type=Path,required=True);a=p.parse_args()
    base='https://raw.githubusercontent.com/NickNicky19/NFL-forecasting-NGS-C/'+a.commit+'/'
    receipts=[];cache={};cap=100
    def get(path,expected=None):
        assert len(receipts)<cap
        with urlopen(Request(base+path,headers={'Cache-Control':'no-cache','User-Agent':'C-GitHub-restoration-C01'}),timeout=30) as response:
            b=response.read(8*1024*1024+1);assert len(b)<=8*1024*1024
            server=response.headers.get('Date')
        digest=hashlib.sha256(b).hexdigest()
        if expected:assert digest==expected,('FRESH_HASH',path)
        assert (ROOT/path).read_bytes()==b,('LOCAL_BYTE_PARITY',path)
        receipts.append(dict(path=path,SHA256=digest,bytes=len(b),response_Date=server,observed_UTC=datetime.now(timezone.utc).isoformat()))
        value=json.loads(gzip.decompress(b) if path.endswith('.gz') else b) if path.endswith(('.json','.json.gz')) else b
        cache[path]=value;return value
    manifest=get('reports/predictive-C01/EVIDENCE_MANIFEST.json')
    for r in manifest['files']:get(r['path'],r['SHA256'])
    # Restore the common matched/export evidence separately, without private rows.
    for name in ['CURRENT_PROTOCOL.json','EXPORT_INDEX.json','shared-intake-v3/SAME_OFFER_COMPARISONS.json.gz','shared-intake-v3/PUBLIC_C_MASKS_AND_CONTROLS.json.gz','shared-intake-v3/PARTIAL_E5_E7_ALL_PROCEDURES.json','shared-intake-v3/PARTIAL_FIXED_SUITE_SUMMARIES.json']:
        get('reports/abc-championship/'+name)
    inference=[]
    for stage in ['share-original','share-actual','completion-original']:
        prefix='artifacts/predictive-C01/'+stage+'/'
        predictions=cache[prefix+'PREDICTIONS.json.gz']
        checked=set()
        for row in predictions:
            for arm,query in row['arms'].items():
                key=(row['origin'],arm)
                if key in checked:continue
                checked.add(key);model=cache[prefix+row['origin']+'-'+arm+'-MODEL.json.gz']['model']
                cdf=hgb_cdf(model,np.asarray(query['features'],float),np.floor(query['grid']))
                error=float(np.max(np.abs(1-np.asarray(cdf)-np.asarray(query['p_over']))));assert error<=1e-12
                inference.append(dict(stage=stage,origin=row['origin'],arm=arm,game_id=row['game_id'],player_id=row['player_id'],maximum_difference=error))
    rows=cache['reports/predictive-C01/CANONICAL_ACTUAL_ROWS.json.gz'];scores=cache['reports/predictive-C01/ACTUAL_LINE_SCORES.json.gz']
    checks=0
    for score in scores:
        rr=[r for r in rows if r['method_id']==score['method_id'] and (score['week_view']=='ALL' or score['week_view']==r['week']) and (score['role']=='ALL' or score['role']==r['position'])]
        for side in ['OVER','UNDER','COMBINED']:
            q=[r for r in rr if r['selected_side'] in ['OVER','UNDER'] and (side=='COMBINED' or r['selected_side']==side)]
            count=Counter()
            for r in q:
                if r['status'] in ['WIN','LOSS']:
                    actual=r['actual'];line=r['line'];assert actual is not None and actual!=line
                    count['WIN' if (actual>line)==(r['selected_side']=='OVER') else 'LOSS']+=1
            s=score[side];assert (len(q),count['WIN'],count['LOSS'])==(s['selected'],s['wins'] or 0,s['losses'] or 0)
            checks+=1
    result=dict(id='C01-FRESH-GITHUB-RESTORATION-v1',commit=a.commit,completed_UTC=datetime.now(timezone.utc).isoformat(),budget=dict(max_static_reads=100,actual=len(receipts),max_bytes_per_object=8388608,new_fits=0,unsafe_deserialization=False),readbacks=receipts,restored_inference=inference,canonical_side_partitions_reproduced=checks,restoration='PASS_BYTES_SCORES_AND_REPRESENTATIVE_INFERENCE',server_clocks='RealreadbackHTTPDate;notclaimedoriginalpregameissuance',limitations='A/Bprivateoutputsremainownerlocal;source-publicationtimingandfullchampionshipnotestablished')
    a.receipt.write_text(json.dumps(result,indent=2)+'\n');print('GITHUB_RESTORED',len(receipts),'INFERENCES',len(inference),'SIDE_PARTITIONS',checks)


if __name__=='__main__':main()
