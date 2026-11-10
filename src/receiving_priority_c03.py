"""Frozen workload-priority views; never a selection/confidence policy."""
from collections import defaultdict
import math

POLICY='C-RECENT3-TARGET-WORKLOAD-PRIORITY-v1'

def memberships(pool,hist,g):
    cuts={(int(y),int(w)):float(f.kickoff.min()) for (y,w),f in g.groupby(['season','week'])}
    out=[];priors={}
    for r in pool:
        key=(int(r['season']),int(r['week']));cut=cuts[key]
        if key not in priors:
            sums=defaultdict(lambda:[0.,0])
            for rs in hist.groups.values():
                for x in rs:
                    v=x.get('targets')
                    if x['available']<cut and v is not None and math.isfinite(v) and v>=0:
                        a=sums[x['position']];a[0]+=v;a[1]+=1
            priors[key]={k:a[0]/a[1] for k,a in sums.items() if a[1]}
        rows=[x for x in hist.before(r['player_id'],cut,3) if x.get('targets') is not None and math.isfinite(x['targets']) and x['targets']>=0]
        value=sum(x['targets'] for x in rows)/len(rows) if rows else priors[key].get(r['position'])
        offered=bool(r.get('qualified_offer',False))
        priority=offered or bool(rows and any(x['targets']>0 for x in rows))
        reason='RECORDED_QUALIFIED_OFFER_TIMING_UNVERIFIED' if offered else 'POSITIVE_TARGETS_IN_ELIGIBLE_RECENT3' if priority else 'BASIC_COVERAGE_SPARSE_OR_NO_RECENT_TARGETS'
        out.append(dict(game_id=r['game_id'],player_id=r['player_id'],season=key[0],week=key[1],position=r['position'],profiling_priority=priority,priority_reason=reason,top20_expected_targets=False,reference_expected_targets=value,reference_cutoff=cut,reference_policy=POLICY,reference_fallback='NONE' if rows else 'EARLIER_ROLE_MEAN' if value is not None else 'UNAVAILABLE',latest_admitted_game=rows[-1]['game_id'] if rows else None,population_tier='STAT_ROW_OR_NATIVE_OFFER_RECONSTRUCTION_NOT_AUTHENTICATED_PREGAME_ROSTER'))
    groups=defaultdict(list)
    for r in out:
        if r['position'] in ['WR','TE'] and r['reference_expected_targets'] is not None:
            groups[(r['season'],r['week'],r['position'])].append(r)
    for rr in groups.values():
        # One player per weekly cohort; deterministic event order for rare duplicates.
        chosen=[];seen=set()
        for r in sorted(rr,key=lambda x:(-x['reference_expected_targets'],x['player_id'],x['game_id'])):
            if r['player_id'] not in seen:chosen.append(r);seen.add(r['player_id'])
        for r in chosen[:20]:r['top20_expected_targets']=True
    return out
