"""Append-only marginal coherence diagnostics; no forecast repair or fitting."""
import argparse,gzip,json,hashlib
from pathlib import Path
from safe_models_v4 import law_load

def build(root,output):
    from prospective_v4 import validate_run,validate_receipt
    pairs={};sources={}
    for p in sorted((root/'receipts').glob('*.json')):
        proof=json.loads(p.read_text());run=root/'runs'/proof['run_id'];m,rs=validate_run(run);validate_receipt(run,proof,m,rs)
        sources[proof['run_id']]=hashlib.sha256((run/'forecasts.json.gz').read_bytes()).hexdigest()
        for r in rs:
            if r['category'] in ['pass_cmp','pass_att']:pairs.setdefault((r['game_id'],r['player_id'],r['policy_id'],r['information_cutoff_UTC'],r['run_id']),{})[r['category']]=r
    rows=[]
    for (game,player,policy,cutoff,run_id),pair in sorted(pairs.items()):
        if len(pair)!=2 or len({r['information_cutoff_UTC'] for r in pair.values()})!=1:
            for r in pair.values():rows.append(dict(forecast_id=r['forecast_id'],game_id=game,player_id=player,state='CROSS_STATISTIC_COHERENCE_UNCHECKED',reason='PAIR_UNAVAILABLE'))
            continue
        c,a=pair['pass_cmp'],pair['pass_att'];cl,al=law_load(c['law']),law_load(a['law']);maximum=max(100,int(max(cl.v,default=0)),int(max(al.v,default=0)))
        violations=[k for k in range(maximum+1) if cl.probability(k)['over']>al.probability(k)['over']+1e-12]
        mean=c['mean']>a['mean']+1e-10;median=c['median']>a['median'];tail=cl.prior.q>al.prior.q+1e-12
        state='COMPLETION_ATTEMPT_CONTRADICTION' if violations or mean or median or tail else 'CMP_ATT_ORDER_CHECKED_NOT_A_JOINT_LAW'
        for r in pair.values():rows.append(dict(forecast_id=r['forecast_id'],game_id=game,player_id=player,state=state,mean_violation=mean,median_violation=median,CDF_violation_thresholds=violations,geometric_tail_order_violation=tail,max_integer_threshold_checked=maximum))
    j=dict(schema='C-MARGINAL-COHERENCE-v4.1',forecast_sources_SHA256=sources,rows=rows,action='Suppress dependent CMP/ATT selections on violation or missing pair; preserve original forecasts and all adverse results',new_fits=0)
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('x') as f:json.dump(j,f,separators=(',',':'))
    return j

def state_for(forecast_id,root=None):
    root=root or Path(__file__).resolve().parents[1]/'prospective/metadata'
    found=[]
    for p in root.glob('COHERENCE*.json'):
        j=json.loads(p.read_text());assert j['schema']=='C-MARGINAL-COHERENCE-v4.1'
        found.extend(r['state'] for r in j['rows'] if r['forecast_id']==forecast_id)
    if len(set(found))>1:raise ValueError('CONFLICTING_COHERENCE_METADATA')
    return found[0] if found else 'CROSS_STATISTIC_COHERENCE_UNCHECKED'

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('prospective'));p.add_argument('--output',type=Path,required=True);a=p.parse_args();build(a.root,a.output)
