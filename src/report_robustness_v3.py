"""Scores and comparisons from immutable v3 rows; performs no fitting."""
import argparse,gzip,json,math
from pathlib import Path
import numpy as np
import pandas as pd
from contracts_v2 import CATEGORIES
from robustness_v3 import Budget,clean,sha,write,VERSION,CAL_VERSION

def mean_loss(a):
    a=np.asarray(a,float)
    return float(a.mean()) if len(a) else None

def proper_metrics(rows,policy):
    known=[r for r in rows if r['actual'] is not None];out=dict(queries=len(rows),outcomes=len(known),unknown=len(rows)-len(known),games=len({r['game_id'] for r in rows}),weeks=len({r['week'] for r in rows}),fallback_queries=sum(r['fallback'] for r in rows))
    for k in ['grid_brier','grid_logloss','median_mae','mean_mse','mean_rmse','mean_bias','p90_absolute_error','p95_absolute_error','exact','strict_native1','inclusive_native1','crps','nll','interval90_coverage','prevalence_brier','prior_brier','always_over_brier','always_under_brier','neutral_brier']:out[k]=None
    out.update(grid_infinite_logloss=0,nll_infinite=0)
    if not known:return out
    p=np.asarray([r['p_over'] if policy!='RAW_RETAINED_2026' else r['p_raw'] for r in known]);y=np.asarray([r['actual'] for r in known]);g=np.asarray(known[0]['grid']);truth=(y[:,None]>g).astype(float)
    with np.errstate(divide='ignore',invalid='ignore'):ll=-np.where(truth,np.log(p),np.log1p(-p)).mean(axis=1)
    out.update(grid_brier=float(((p-truth)**2).mean()),grid_logloss=mean_loss(ll),grid_infinite_logloss=int(np.isinf(ll).sum()),always_over_brier=float(((1-truth)**2).mean()),always_under_brier=float((truth**2).mean()),neutral_brier=.25)
    if 'prevalence_over' in known[0]:out['prevalence_brier']=float(((np.asarray([r['prevalence_over'] for r in known])-truth)**2).mean())
    if 'reference_over' in known[0]:out['prior_brier']=float(((np.asarray([r['reference_over'] for r in known])-truth)**2).mean())
    if policy=='RAW_2025':
        out.update(crps=float(np.mean([r['crps'] for r in known])),nll=mean_loss([r['nll'] for r in known]),nll_infinite=sum(math.isinf(float(r['nll'])) for r in known))
        if known[0]['target']!='anytime_td':
            point=np.asarray([r['median'] for r in known]);m=np.asarray([r['mean'] for r in known]);e=point-y;scale=CATEGORIES[known[0]['target']][3];lattice_error=np.abs(np.rint(point*scale)-np.rint(y*scale))
            out.update(median_mae=float(abs(e).mean()),mean_mse=float(((m-y)**2).mean()),mean_rmse=float(np.sqrt(((m-y)**2).mean())),mean_bias=float((m-y).mean()),p90_absolute_error=float(np.quantile(abs(e),.90)),p95_absolute_error=float(np.quantile(abs(e),.95)),exact=int((lattice_error==0).sum()),strict_native1=int((lattice_error<scale).sum()),inclusive_native1=int((lattice_error<=scale).sum()),interval90_coverage=float(np.mean([r['p05']<=r['actual']<=r['p95'] for r in known])))
    return out

def subsets(rows):
    target=rows[0]['target'];roles=sorted({r['position'] for r in rows});weeks=sorted({r['week'] for r in rows})
    yield 'ALL',rows
    yield 'PRIMARY',[r for r in rows if r['position'] in CATEGORIES[target][4]]
    yield 'W1-4',[r for r in rows if r['week']<=4]
    yield 'W5+',[r for r in rows if r['week']>=5]
    yield 'LEARNED',[r for r in rows if not r['fallback']]
    for role in roles:
        q=[r for r in rows if r['position']==role];yield role,q
        yield 'W1-4-'+role,[r for r in q if r['week']<=4]
        yield 'W5+-'+role,[r for r in q if r['week']>=5]
    for week in weeks:
        q=[r for r in rows if r['week']==week];yield 'W'+str(week),q
        for role in roles:yield 'W'+str(week)+'-'+role,[r for r in q if r['position']==role]

def intervals(rows,delta):
    result={}
    for key in ['game_id','week']:
        d=pd.DataFrame(dict(cluster=[r[key] for r in rows],delta=delta));g=d.groupby('cluster').delta.agg(['sum','count']);rng=np.random.default_rng(1701);i=rng.integers(0,len(g),(500,len(g)));v=g['sum'].to_numpy()[i].sum(axis=1)/g['count'].to_numpy()[i].sum(axis=1)
        result[key+'_clusters']=len(g);result[key+'_ci95']=list(map(float,np.quantile(v,[.025,.975])))
    return result

def report(root,dest):
    dest.mkdir(parents=True,exist_ok=True);scores=[];pairs=[];calibration=[];primary=[];all_rows={}
    for target in CATEGORIES:
        raw=[r for p in sorted((root/'raw'/target).glob('W*/rows.json.gz')) for r in json.loads(gzip.decompress(p.read_bytes()))]
        assert len({r['week'] for r in raw})==18
        future=json.loads(gzip.decompress((root/'calibration'/target/'rows-2026.json.gz').read_bytes()))
        assert len({r['week'] for r in future})==7
        assert not pd.DataFrame(raw).duplicated(['game_id','player_id']).any() and not pd.DataFrame(future).duplicated(['game_id','player_id']).any()
        for policy,rows,season in [('RAW_2025',raw,2025),('RAW_RETAINED_2026',future,2026),('SIGMOID_2025_TRAINED',future,2026)]:
            for horizon,q in subsets(rows):
                if not q:continue
                metric=proper_metrics(q,policy);scores.append(dict(test_id=f'{VERSION if season==2025 else CAL_VERSION}-{target}-{policy}-{horizon}',target=target,season=season,policy=policy,horizon=horizon,**metric))
                if horizon in ['ALL','PRIMARY','QB','RB','WR','TE']:
                    known=[r for r in q if r['actual'] is not None]
                    if not known:continue
                    p=np.asarray([r['p_raw'] if policy=='RAW_RETAINED_2026' else r['p_over'] for r in known]).ravel();truth=np.asarray([r['actual']>np.asarray(r['grid']) for r in known]).ravel()
                    for k in range(10):
                        mask=(p>=k/10)&((p<(k+1)/10) if k<9 else (p<=1))
                        calibration.append(dict(target=target,season=season,policy=policy,horizon=horizon,bin=k,threshold_views=int(mask.sum()),mean_probability=float(p[mask].mean()) if mask.any() else None,observed_frequency=float(truth[mask].mean()) if mask.any() else None,kind='synthetic_threshold_diagnostic' if target!='anytime_td' else 'rush_rec_TD_Bernoulli_event'))
        for horizon,q in subsets(future):
            known=[r for r in q if r['actual'] is not None]
            if not known:continue
            g=np.asarray(known[0]['grid']);y=np.asarray([r['actual'] for r in known])[:,None]>g;p=np.asarray([r['p_raw'] for r in known]);c=np.asarray([r['p_over'] for r in known]);a=((c-y)**2).mean(axis=1);b=((p-y)**2).mean(axis=1);delta=a-b
            row=dict(target=target,season=2026,horizon=horizon,queries=len(q),outcomes=len(known),raw_Brier=float(b.mean()),calibrated_Brier=float(a.mean()),delta_Brier=float(delta.mean()),relative_change=float(delta.mean()/b.mean()) if b.mean()>0 else None,**intervals(known,delta))
            pairs.append(row)
            if horizon==('RB' if target in ['rush_yd','rush_att'] else 'PRIMARY' if target=='rush_rec_yd' else 'ALL'):primary.append(row)
        all_rows[target]=(raw,future)
    pd.DataFrame(scores).to_csv(dest/'SCORES.csv',index=False);pd.DataFrame(calibration).to_csv(dest/'RELIABILITY.csv',index=False)
    (dest/'PAIRED.json').write_text(json.dumps(pairs,indent=2));pd.DataFrame(primary).to_csv(dest/'PRIMARY_CALIBRATION.csv',index=False)
    s=pd.DataFrame(scores);summary=[]
    for t in CATEGORIES:
        horizon='RB' if t in ['rush_yd','rush_att'] else 'PRIMARY' if t=='rush_rec_yd' else 'ALL'
        a=s[(s.target==t)&(s.horizon==horizon)&(s.policy=='RAW_2025')].iloc[0];b=next(r for r in primary if r['target']==t)
        summary.append(dict(target=t,primary_panel=horizon,raw2025_median_MAE=a.median_mae,raw2025_Brier=a.grid_brier,raw2025_prevalence_Brier=a.prevalence_brier,raw2025_outcomes=int(a.outcomes),raw2025_queries=int(a.queries),raw2025_fallback=int(a.fallback_queries),**{k:v for k,v in b.items() if k not in ['target','horizon']}))
    pd.DataFrame(summary).to_csv(dest/'CATEGORY_SUMMARY.csv',index=False)
    total=dict(id='C-2025-OOF-CALIBRATION-v3',raw_slots=len(list((root/'raw').glob('*/*/DONE.json'))),calibrators=len(list((root/'calibration').glob('*/DONE.json'))),raw2025_queries=sum(len(a) for a,b in all_rows.values()),raw2025_outcomes=sum(r['actual'] is not None for a,b in all_rows.values() for r in a),saved2026_queries=sum(len(b) for a,b in all_rows.values()),saved2026_outcomes=sum(r['actual'] is not None for a,b in all_rows.values() for r in b),unique2025_games=len({r['game_id'] for a,b in all_rows.values() for r in a}),new2026_base_fits=0,NGS_new_inputs=0,offered_sides='UNAVAILABLE_NOT_GRADED',six_leg='NO_QUALIFIED_SIX_LEG_ENTRY',source_tier='current_revised_seven_day_reconstruction',research_exposed=True)
    (dest/'EXECUTED.json').write_text(json.dumps(total,indent=2)+'\n');print(total)
    text=['# 2025 rolling validation and earlier-trained calibration','',
          'All twelve categories use the fixed P2_LEAF/E0_OP/H-MULTI procedure. The new216raw origins cover all18regular-season2025weeks and272games. The2026base fits/predictions are reused unchanged. One predeclared monotone sigmoid percategory learns only from2025out-of-sample probabilities and labels. These exposed periods are not fresh holdouts.','',
          'The probability change below is calibrated minus identical saved raw2026probabilities. Most thresholds are synthetic; anytime is an actual rushing-or-receiving TD event. No offered-pick or price/value result follows. Point products remain in the raw model; the calibrated threshold/event product does not claim a mean, median or complete law.','',
          '|Category / primary panel|2025 raw median MAE|2025 raw Brier / earlier prevalence|2025 outcomes/queries|2026 raw → calibrated Brier|Paired change [95% week CI]|2026 outcomes/queries|',
          '|---|---:|---:|---:|---:|---|---:|']
    for r in summary:
        ci=r['week_ci95'];mae='N/A event' if r['target']=='anytime_td' else f'{r["raw2025_median_MAE"]:.4f}'
        text.append(f'|{r["target"]} / {r["primary_panel"]}|{mae}|{r["raw2025_Brier"]:.6f} / {r["raw2025_prevalence_Brier"]:.6f}|{r["raw2025_outcomes"]}/{r["raw2025_queries"]}|{r["raw_Brier"]:.6f} → {r["calibrated_Brier"]:.6f}|{r["delta_Brier"]:+.6f} [{ci[0]:+.6f},{ci[1]:+.6f}]|{r["outcomes"]}/{r["queries"]}|')
    text+=['','All query masks/unknowns remain. Rushing RB and QB and receiving RB/WR/TE panels are reported separately in [SCORES.csv](SCORES.csv). Full, weekly, startup, learned-only, strict/inclusive1native-unit and tail views are retained. Do not rank categories using native-unit errors. Seven2026week clusters and exposed design/multiple tests limit uncertainty interpretation. [Paired records](PAIRED.json) retain every interval, gain and reversal. [Reliability](RELIABILITY.csv) describes actual raw and transformed probabilities, not guaranteed calibration improvement.','',
               'Raw2025performance is a genuine chronological reconstruction. No calibrated2025performance is claimed: the2025OOFrecords train the sigmoid. The actual final2026probabilities are also reconstructions generated after those games, not original issued forecasts. Source revisions, retrospective participant-only population, partial chart rare-component labels, and the assumed7day availability rule remain unchanged.','',
               'Real Over/Under W/L/decided/rates, A/C and B/C exact matching, six-leg success, payouts/profit and price-aware value remain N/A pending the exact previously listed exports/contracts. No anytimeNO/Under offer or chart market is created. NGSintake is a repeatedbyteidentical packet and adds no modelinput; the original failed/inconclusive NGSrecipe remains frozen.','']
    (dest/'README.md').write_text('\n'.join(text))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--report',type=Path,required=True);p.add_argument('--budget-ledger',type=Path,required=True);p.add_argument('--cache-root',type=Path,action='append',required=True);a=p.parse_args()
    with Budget(a.budget_ledger,a.run,a.cache_root):report(a.run,a.report)
