"""Fresh GitHub byte recovery and independent saved-score replay; zero fits."""
import argparse,gzip,hashlib,json,math,sys
from collections import Counter,defaultdict
from pathlib import Path
from urllib.request import Request,urlopen
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from safe_models_v4 import infer_forest,law_load,law_data
from forward_sources_v4 import stamp

ROOT=Path(__file__).resolve().parents[1]
def main():
    p=argparse.ArgumentParser();p.add_argument('--commit',required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--receipt',type=Path,required=True);a=p.parse_args();assert not a.output.exists();a.output.mkdir(parents=True);downloads=[];cache={}
    def fetch(path,ref=a.commit,retain=True):
        key=(ref,path)
        if key in cache:return cache[key]
        with urlopen(Request('https://raw.githubusercontent.com/NickNicky19/NFL-forecasting-NGS-C/'+ref+'/'+path,headers={'Cache-Control':'no-cache','Accept-Encoding':'identity'}),timeout=30) as r:b=r.read(16777217)
        assert len(b)<=16777216 and b==(ROOT/path).read_bytes(),'GITHUB_RESTORE_BYTES:'+path
        cache[key]=b;downloads.append(dict(path=path,commit=ref,bytes=len(b),SHA256=hashlib.sha256(b).hexdigest(),fresh_GitHub_bytes=True,local_retained_copy=retain))
        if retain:
            out=a.output/path;out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(b)
        return b
    def js(path,ref=a.commit,retain=True):
        b=fetch(path,ref,retain);return json.loads(gzip.decompress(b) if path.endswith('.gz') else b)
    registry=js('reports/week8-v9/GRADE_VERSION_REGISTRY.json');sets=[];gradechecks=[]
    for v in registry['versions']:
        vid=v['id'];base='reports/week8-v9/' if vid.endswith('001') else 'reports/week8-v9/runs/'+vid+'/'
        run=js(base+'GRADING_RUN.json');packet=js(run['outcome_packet']);assert hashlib.sha256(cache[(a.commit,run['outcome_packet'])]).hexdigest()==run['outcome_SHA256'];folder=str(Path(run['outcome_packet']).parent)
        for e in packet['source_evidence']:
            b=fetch(folder+'/'+e['path'],retain=vid==registry['canonical']);assert hashlib.sha256(b).hexdigest()==e['SHA256']
        rows=js(base+'GRADED_FORECAST_ROWS.json.gz');sets.append(rows);combined=[]
        for g in run['grade_files']:
            b=fetch(g['path'],retain=False);assert hashlib.sha256(b).hexdigest()==g['SHA256'];combined+=json.loads(b)['grades']
        assert len(rows)==len(combined)==2513
        lookup={r['forecast_id']:r for r in rows}
        for r in combined:
            q=lookup[r['forecast_id']];assert all(q.get(k)==r.get(k) for k in ['state','actual','absolute_error','mean_squared_error','CRPS','NLL'])
        gradechecks.append(dict(version=vid,states=dict(Counter(r['state'] for r in rows)),rows=2513))
    originals={};inferences=[]
    for name in ['C-FWD-v4-20261101-0009-P2-pass_yd','C-FWD-v4-20261101-0011-P2-remainder']:
        proof=js('prospective/receipts/'+name+'.json');base='prospective/runs/'+name+'/';rows=js(base+'forecasts.json.gz',proof['capture_commit'],retain=False);originals.update({r['forecast_id']:r for r in rows});manifest=js(base+'model_manifest.json',proof['capture_commit'],retain=False)
        for m in manifest:
            numeric=js(base+m['artifact'],proof['capture_commit'],retain=False);assert hashlib.sha256(cache[(proof['capture_commit'],base+m['artifact'])]).hexdigest()==m['model_SHA256'];r=next(r for r in rows if r['category']==m['target']);law=infer_forest(numeric,[[float('nan') if v is None else v for v in r['features']]],[r['position']])[0];assert law_data(law)==r['law'];inferences.append(dict(category=r['category'],forecast_id=r['forecast_id'],safe_JSON_tree_inference=True,first_server_UTC=proof['server_check_completed_UTC'],future_actuals_used=False))
    canonical=sets[-1];errors=defaultdict(list);proper=defaultdict(list)
    for r in canonical:
        if r['state']!='GRADED_PLAYED':continue
        f=originals[r['forecast_id']];law=law_load(f['law']);actual=r['actual'];scaled=round(actual*law.scale)
        crps=law.crps(actual);logp=law.logpmf(scaled);assert math.isclose(crps,r['CRPS'],rel_tol=1e-11,abs_tol=1e-10);assert math.isclose(-logp,r['NLL'],rel_tol=1e-11,abs_tol=1e-10)
        proper[r['category']].append(crps)
        if r['median'] is not None:errors[r['category']].append(abs(r['median']-actual))
    summary=js('reports/week8-v9/SUMMARY.json')
    for c in summary['categories']:
        assert math.isclose(sum(proper[c['category']])/len(proper[c['category']]),c['CRPS'],rel_tol=1e-12)
        if errors[c['category']]:assert math.isclose(sum(errors[c['category']])/len(errors[c['category']]),c['median_MAE'],rel_tol=1e-12)
    top={name:js(path) for name,path in [('weekly','reports/topk-reference-v9/WEEKLY_RESULTS.json.gz'),('cumulative','reports/topk-reference-v9/CUMULATIVE.json.gz'),('members','artifacts/topk-reference-v9/MEMBERSHIP.json.gz'),('pool','artifacts/topk-reference-v9/COMMON_POOL.json.gz'),('overlaps','reports/topk-reference-v9/OVERLAPS.json.gz')]};by=defaultdict(list)
    for r in top['members']:by[r['diagnostic_id']].append(r)
    for r in top['weekly']:
        mm=by[r['diagnostic_id']];known=[x for x in mm if x['statistical_status'] in ['WIN','LOSS']];assert len(mm)==r['selected_count'] and sum(x['statistical_status']=='WIN' for x in mm)==r['wins'] and len(known)==r['decided'];assert len({x['player_id'] for x in mm})==len(mm)
        if known:assert math.isclose(sum(x['p_selected'] for x in known)/len(known),r['mean_confidence_decided'],rel_tol=1e-12)
        if mm:assert math.isclose(sum(x['p_selected'] for x in mm),r['all_selected_expected_wins'],rel_tol=1e-12)
    assert len(top['weekly'])==810 and len(top['cumulative'])==405 and len(top['members'])==9238
    result=dict(id='C-WEEK8-TOPK-GITHUB-RESTORATION-v9',commit=a.commit,verified_UTC=stamp(),files=downloads,downloaded_bytes=sum(x['bytes'] for x in downloads),all_hashes_match=True,grade_versions=gradechecks,full_original_issued_population=2513,canonical_played_scores_recomputed=1441,unknown=873,pending=199,canonical_12category_MAE_CRPS_reproduced=True,baseline_numeric_inferences=inferences,TopK_weekly_lists=810,TopK_membership=9238,decided_vs_all_confidence_masks_reproduced=True,new_NFL_fits=0,pickle_loaded=False,source_code_executed_from_download=False,original_selections=0,qualified_Week8_actual_line_replays=0,not_claimed='Prop hit rates, current offers, settled wagers, promotion or validated future confidence')
    a.receipt.parent.mkdir(parents=True,exist_ok=True)
    with a.receipt.open('x') as f:json.dump(result,f,indent=2)
    print('GITHUB_WEEK8_TOPK_RESTORED',len(downloads),result['downloaded_bytes'],1441,810)

if __name__=='__main__':main()
