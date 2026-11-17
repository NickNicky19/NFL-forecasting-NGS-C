"""Bounded independent no-fit grade/aggregate check; no author grader imports."""
import time
START_CPU=time.process_time()
import datetime,gzip,hashlib,json,math
from collections import Counter
from decimal import Decimal
from pathlib import Path

ROOT=Path(__file__).resolve().parents[5]
HERE=Path(__file__).resolve().parent
P=ROOT/'reports/information-skill-01/execution-authorization-02/pilot'
SOURCE=ROOT/'reports/targeted-accuracy-w1w9-01/M3/inputs/NATIVE_OFFERS.json.gz'
TOL=1e-12

def read(path):return json.loads(gzip.decompress(Path(path).read_bytes()))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def manual_grade(row,side):
    if side is None:return 'UNAVAILABLE_FORECAST'
    if side=='ABSTAIN':return 'ABSTAIN'
    if row['appearance']!='PLAYED':return 'UNKNOWN_PARTICIPATION'
    if row['actual'] is None:return 'MISSING_ACTUAL'
    y,line=Decimal(str(row['actual'])),Decimal(str(row['line']))
    return 'PUSH' if y==line else 'WIN' if (y>line)==(side=='OVER') else 'LOSS'

def main():
    source={r['offer_id']:r for r in read(SOURCE)['primary'] if r['category']=='rec'}
    assert len(source)==295 and len({(r['category'],r['game_id'],r['player_id']) for r in source.values()})==295
    resultpath=P/'scores/RESULTS.json.gz'
    published={(r['arm'],r['week']):r for r in read(resultpath)['rows'] if r['arm'] in ['C1_SUPPORT','C2_VALUE'] and r['product']=='LAW'}
    paths=[SOURCE,resultpath]+[P/'raw'/f'W{w}-{a}.json.gz' for a in ['C1_SUPPORT','C2_VALUE'] for w in [2,3]]
    hashes={str(p.relative_to(ROOT)):sha(p) for p in paths}
    metrics=[];groups={};checks=0
    for arm in ['C1_SUPPORT','C2_VALUE']:
        rows=[r for week in [2,3] for r in read(P/'raw'/f'W{week}-{arm}.json.gz')]
        assert len(rows)==295 and len({r['offer_id'] for r in rows})==295
        assert {r['offer_id'] for r in rows}==set(source)
        manual=[]
        for r in rows:
            s=source[r['offer_id']]
            for key in ['game_id','player_id','category','team','opponent_team','season','week','line','venue',
                        'period','comparator','scoring_contract_id','actual','appearance','line_tier']:
                assert r.get(key)==s.get(key),(arm,r['offer_id'],key)
                checks+=1
            p=r.get('probabilities')
            if p is None:side=None
            else:
                assert set(p)=={'under','push','over'}
                assert all(math.isfinite(v) and v>=0 for v in p.values()) and abs(sum(p.values())-1)<=TOL
                side='OVER' if p['over']>p['under']+TOL else 'UNDER' if p['under']>p['over']+TOL else 'ABSTAIN'
            state=manual_grade(r,side)
            assert side==r['selected_side'] and state==r['status'],(arm,r['offer_id'],state,r['status'])
            # No source null is replaced by zero; exact observed zeros remain zeros.
            if s['actual'] is None:assert r['actual'] is None
            if s['appearance']=='PLAYED' and s['actual']==0:assert r['actual']==0
            checks+=4
            manual.append(dict(r,manual_side=side,manual_state=state))
        groups[arm]=manual
        for week in ['ALL',2,3]:
            rr=manual if week=='ALL' else [r for r in manual if r['week']==week]
            pp=published[(arm,week)];states=Counter(r['manual_state'] for r in rr)
            selected=[r for r in rr if r['manual_side'] in ['OVER','UNDER']]
            unknown=sum(r['manual_state'] in ['UNKNOWN_PARTICIPATION','MISSING_ACTUAL','PENDING'] for r in selected)
            assert pp['eligible']==len(rr) and pp['unavailable']==states['UNAVAILABLE_FORECAST']
            assert pp['unknown']==unknown and pp['abstentions']==states['ABSTAIN']
            assert pp['pushes']==states['PUSH'] and pp['games']==len({r['game_id'] for r in rr})
            out=dict(arm=arm,week=week,eligible=len(rr),available=len(rr)-states['UNAVAILABLE_FORECAST'],
                     unknown=unknown,states=dict(states),explicit_played_zeros=sum(r['appearance']=='PLAYED' and r['actual']==0 for r in rr))
            for side in ['OVER','UNDER','COMBINED']:
                pool=selected if side=='COMBINED' else [r for r in selected if r['manual_side']==side]
                wins=sum(r['manual_state']=='WIN' for r in pool);losses=sum(r['manual_state']=='LOSS' for r in pool);n=wins+losses
                expected=dict(selected=len(pool),wins=wins if n else None,losses=losses if n else None,decided=n,rate=wins/n if n else None)
                for k,v in expected.items():
                    if k=='rate' and v is not None:assert abs(pp[side][k]-v)<=TOL
                    else:assert pp[side][k]==v,(arm,week,side,k,pp[side][k],v)
                    checks+=1
                out[side]=expected
            known=[r for r in rr if r['appearance']=='PLAYED' and r['actual'] is not None and r.get('probabilities') is not None]
            briers=[];logs=[];infinite=0
            for r in known:
                y,line=Decimal(str(r['actual'])),Decimal(str(r['line']))
                event='under' if y<line else 'over' if y>line else 'push'
                p=r['probabilities'];briers.append(.5*sum((p[k]-(1 if k==event else 0))**2 for k in ['under','push','over']))
                if p[event]<=0:infinite+=1
                else:logs.append(-math.log(p[event]))
            quality=pp['probability_quality']
            assert quality['probability_scored']==len(known) and quality['infinite_log_loss_count']==infinite
            if known:assert abs(quality['Brier_half_multiclass']-sum(briers)/len(briers))<=TOL
            if known and not infinite:assert abs(quality['log_loss']-sum(logs)/len(logs))<=TOL
            out['independent_Brier_half_multiclass']=sum(briers)/len(briers) if briers else None
            out['independent_log_loss']=sum(logs)/len(logs) if logs and not infinite else None
            checks+=4;metrics.append(out)
    left={r['offer_id']:r for r in groups['C2_VALUE']};right={r['offer_id']:r for r in groups['C1_SUPPORT']}
    decided=[(left[k],right[k]) for k in sorted(left) if left[k]['manual_state'] in ['WIN','LOSS'] and right[k]['manual_state'] in ['WIN','LOSS']]
    paired=dict(common_decided=len(decided),side_disagreements=sum(a['manual_side']!=b['manual_side'] for a,b in decided),
        C2_only_wins=sum(a['manual_state']=='WIN' and b['manual_state']=='LOSS' for a,b in decided),
        C1_only_wins=sum(a['manual_state']=='LOSS' and b['manual_state']=='WIN' for a,b in decided))
    assert all(sha(ROOT/p)==h for p,h in hashes.items()),'READONLY_ARTIFACT_CHANGED'
    out=dict(id='C-DYAD-INDEPENDENT-ALL-RAW-AGGREGATE-v1',recorded_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        status='PASS_INDEPENDENT_NO_FIT_RAW_GRADES_AND_AGGREGATES',checks=checks,raw_rows_checked=590,
        arm_period_summaries=metrics,paired_C2_C1=paired,source_bindings=hashes,
        source_nulls_preserved=True,source_played_zeros_preserved=True,no_author_grader_import=True,
        no_fit_or_model_inference=True,new_source_GETs=0,parent_LEDGER_not_modified=True,
        process_CPU_seconds=time.process_time()-START_CPU,conservative_reporting_to_root_CPU_charge=2.0,
        charge_rule='One charge only: remaining2 of original10 independent-subtaskCPU ceiling; root appends after its own activeprocess. No pilot extension.',
        scope='Exact retained input/probability/grade arithmetic. Does not authenticate historical source vintages, verify every source-presence claim from rawproviderbytes, or reproduce more fits.')
    with (HERE/'AGGREGATE_CHECK.json').open('x') as f:f.write(json.dumps(out,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(status=out['status'],checks=checks,raw_rows=590,paired=paired,CPU=out['process_CPU_seconds'])))

if __name__=='__main__':main()
