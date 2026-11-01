"""Exact-line evaluation of frozen new laws, preserving original v7/v4 rows."""
import argparse,copy,json
from pathlib import Path
from reliability_v8 import ROOT,OUT,ART,read,write,key,now
from safe_models_v4 import law_load
import actual_accuracy_v6 as a
from contracts_v2 import grade

def run():
    dest=ART/'WORKLOAD_GRADED_ROWS.json.gz';assert not dest.exists(),'FROZEN_NEW_ARM_GRADES_EXIST'
    base,_=a.load_records();raw=base+read(ART/'BOOK_GRADED_ROWS.json.gz')['rows'];raw=a.deduplicate(raw);pred={(r['game_id'],r['player_id']):r for r in read(ART/'WORKLOAD_PREDICTIONS.json.gz') if r['season']==2026};out=[]
    for old in raw:
        if old['category']!='pass_yd' or old['method_id']!='P2_LAW':continue
        p=pred.get((old['game_id'],old['player_id']))
        for arm in ['P2_LINKED_V8','P2_WORKLOAD_V8']:
            r=copy.deepcopy(old);r.update(record_id=old['offer_id']+'-'+arm,grade_id=old['offer_id']+'-'+arm+'-STAT-G1',method_id=arm,method_version=a.method_version('pass_yd',arm,'2026_W1_W7'),selector_id=arm+'-strict-v8',graded_UTC=now(),forecast_generated_UTC=read(OUT/'WORKLOAD_RUN.json').get('generated_UTC',now()),probability_inference_evidence_reference='artifacts/reliability-v8/WORKLOAD_PREDICTIONS.json.gz',information_set_id='C-PASS-WORKLOAD-LINK-v8:'+arm+':'+old['game_id']+':'+old['player_id'],forecast_id='C-PASS-WORKLOAD-LINK-v8:'+arm+':'+old['game_id']+':'+old['player_id'])
            if old['status']!='UNAVAILABLE_FORECAST':
                assert p and p['actual']==old['actual'] and a.instant(p['as_of_UTC'])==a.instant(old['decision_UTC']);ar=p['arms'][arm];law=law_load(ar['law']);ps=law.probability(old['line']);side='ABSTAIN' if abs(ps['over']-ps['under'])<=1e-12 else 'OVER' if ps['over']>ps['under'] else 'UNDER';r.update(law=ar['law'],probability_line=old['line'],**{'p_'+k:v for k,v in ps.items()},selected_side=side,status='ABSTAIN' if side=='ABSTAIN' else 'UNKNOWN_PARTICIPATION' if old['appearance']!='PLAYED' else grade(old['actual'],old['line'],side),typed_mean=ar['mean'],typed_median=ar['median'],workload_bin_weights=ar['bin_weights'],leaf_missing_bin_forecast_mass=ar['leaf_missing_bin_forecast_mass'])
            else:
                for k in ['law','p_under','p_push','p_over','probability_line']:r.pop(k,None)
            a.validate_row(r);out.append(r)
    paths=['artifacts/reliability-v8/WORKLOAD_PREDICTIONS.json.gz','reports/reliability-v8/WORKLOAD_RUN.json','protocol/WORKLOAD_LINK_V8.json','artifacts/basic-football-facts-v2.1.zip','sources/propline-v7/nfl_graded_props_14d.csv.gz']
    write(dest,dict(schema='C-QUALIFIED-ACTUAL-PROP-ROWS-v6',source_review_id='C-PROPLINE-CCBY-WORKLOAD-v8',retained_evidence=[dict(path=p,SHA256=a.sha(ROOT/p)) for p in paths],rows=out));print('NEW_ARM_METHOD_ROWS',len(out))
if __name__=='__main__':run()
