"""Append retained v3 research views to the static C site; no fitting or retrieval."""
import argparse,gzip,hashlib,json
from datetime import datetime,timezone
from pathlib import Path
import pandas as pd
from robustness_v3 import CAL_VERSION

FAMILY='CAL_SIGMOID_2025'
def records(path):
    frame=pd.read_csv(path).replace([float('inf'),-float('inf')],['Infinity','-Infinity'])
    return frame.astype(object).where(pd.notna(frame),None).to_dict('records')

def extend(run,report,docs):
    data=docs/'data';manifest=json.loads((data/'manifest.json').read_text())
    manifest['files']=[r for r in manifest['files'] if r['family']!=FAMILY]
    for done in sorted((run/'calibration').glob('*/DONE.json')):
        target=done.parent.name;cal=json.loads((done.parent/'calibrator.json').read_text());rows=json.loads(gzip.decompress((done.parent/'rows-2026.json.gz').read_bytes()))
        for week in range(1,8):
            part=[]
            for r in rows:
                if r['week']!=week:continue
                p=dict(r,family=FAMILY,history='H-MULTI',arm='E0_OP',season=2026,p05=None,p95=None,slot=f'{CAL_VERSION}-{target}-H-MULTI-{FAMILY}-E0_OP-W{week:02}',consumed_context=dict(calibration_intercept=cal['a'],calibration_slope=cal['b'],calibration_2025_queries=cal['training_queries']),calibration_training='2025 rolling-origin OOF predictions only; no2026outcomes in fit')
                part.append(p)
            path=data/f'{target}-H-MULTI-{FAMILY}-W{week:02}.json';path.write_text(json.dumps(part,separators=(',',':'),allow_nan=False))
            manifest['files'].append(dict(target=target,history='H-MULTI',family=FAMILY,week=week,version=CAL_VERSION,file=path.name,rows=len(part),sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    manifest['wave3_summary']=records(report/'SCORES.csv');manifest['wave3_primary_calibration']=records(report/'CATEGORY_SUMMARY.csv')
    cal=data/'wave3-reliability.json';cal.write_text(json.dumps(records(report/'RELIABILITY.csv'),separators=(',',':'),allow_nan=False));manifest['wave3_reliability_SHA256']=hashlib.sha256(cal.read_bytes()).hexdigest()
    manifest['wave3_evidence']='New2025rollingrawforecasts and2025OOFtrainedsigmoid on unchanged2026rawforecasts; syntheticexceptanytime, exposedreconstruction, no offeredpick claim'
    manifest['source_forecast_rows_unchanged']=True
    manifest['site_forecast_views']=sum(e['rows'] for e in manifest['files'])
    (data/'manifest.json').write_text(json.dumps(manifest,separators=(',',':'),allow_nan=False))
    build=json.loads((docs/'build.json').read_text());build.update(built_at_UTC=datetime.now(timezone.utc).isoformat(),served_commit='LOCAL_PREPARED_NOT_DEPLOYED',asset_release_id=hashlib.sha256((data/'manifest.json').read_bytes()).hexdigest(),model_version='Raw:C-ALL12-LAW-THRESHOLD-v2.1; fittedsigmoid:'+CAL_VERSION+'; perrow typedversions')
    (docs/'build.json').write_text(json.dumps(build,indent=2)+'\n');print('SITE_V3_RETAINED_EXTENSION',len(manifest['files']))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--report',type=Path,required=True);p.add_argument('--docs',type=Path,default=Path('docs'));a=p.parse_args();extend(a.run,a.report,a.docs)
