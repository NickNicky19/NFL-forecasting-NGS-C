"""Independent arithmetic checks of immutable published C comparison evidence.

Not a common evaluator or new research run. Only the named published M3 mean
products may be reconstructed, and only after their exact case-mask hashes
match. No fitting, source collection, simulator or new candidate search.
"""
from __future__ import annotations
import argparse,collections,datetime,gzip,hashlib,json,math,pathlib,resource,time
from decimal import Decimal

def digest(b):return hashlib.sha256(b).hexdigest()
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def finite(v):return type(v) in (int,float) and math.isfinite(v)
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for field in ('machine','base','masks','canonical','identity','output'):
        ap.add_argument('--'+field,type=pathlib.Path,required=True)
    a=ap.parse_args();cpu=time.process_time();wall=time.monotonic();checks=[];failures=[]
    mb=a.machine.read_bytes();bb=a.base.read_bytes()
    if digest(mb)!='ed8d013b994df3953b3b0a4998d57c81f5bb38885fad874dc478c9f2f15dc969':raise ValueError('Exact C machine commitment')
    if digest(bb)!='907decacb4ce8ca1b4990ba6ec3eef43049e62b12ae4f4a526776ab4e926faee':raise ValueError('Exact C source forecasts')
    c=json.loads(gzip.decompress(mb));masks=json.loads(a.masks.read_bytes())
    def check(state,label):
        checks.append(label)
        if not state:failures.append(label)
    def value(v):return 0 if v is None else v
    def sides(d,label):
        for side in ('OVER','UNDER','COMBINED'):
            x=d[side];w,l,n=value(x.get('wins')),value(x.get('losses')),x['decided']
            check(w+l==n,label+'/'+side+'/denominator')
            check(x['rate'] is None if n==0 else math.isclose(x['rate'],w/n,abs_tol=1e-12),label+'/'+side+'/rate')
            if 'selected'in x:check(x['selected']>=n,label+'/'+side+'/selected')
        for field in ('wins','losses','decided','selected'):
            if field in d['COMBINED']:check(value(d['OVER'].get(field))+value(d['UNDER'].get(field))==value(d['COMBINED'].get(field)),label+'/weighted/'+field)
    def walk(v,label):
        if isinstance(v,dict):
            if {'OVER','UNDER','COMBINED'}<=set(v):sides(v,label)
            if {'primary_wins','control_wins','common_decided','win_difference'}<=set(v):
                n=v['common_decided'];p=v['primary_wins'];q=v['control_wins'];delta=p-q
                check(delta==v['win_difference'],label+'/paired_difference')
                check(v['paired_rate_difference'] is None if not n else math.isclose(v['paired_rate_difference'],delta/n,abs_tol=1e-12),label+'/paired_rate')
                check(0<=p<=n and 0<=q<=n,label+'/paired_support')
                if 'primary_only_wins'in v:
                    x,y=v['primary_only_wins'],v['control_only_wins'];check(x-y==delta,label+'/discordance_difference')
                    check(p-x==q-y and 0<=p-x<=n,label+'/both_correct')
            for k,x in v.items():walk(x,label+'/'+k)
        elif isinstance(v,list):
            for j,x in enumerate(v):walk(x,label+'/'+str(j))
    walk(c,'machine')
    scores={(r['method'],r['category'],str(r['week'])):r for r in c['scores']}
    for (method,cat,week),row in scores.items():
        if week!='ALL':continue
        weekly=[scores[method,cat,str(w)] for w in range(4,10) if (method,cat,str(w))in scores]
        for side in ('OVER','UNDER','COMBINED'):
            for field in ('wins','losses','decided','selected'):
                check(sum(value(r[side].get(field)) for r in weekly)==value(row[side].get(field)),method+'/'+cat+'/weekly/'+side+'/'+field)
        for field in ('available','unavailable','selected_unknown','native','fallback','attribution_unknown','pushes','voids'):
            check(sum(r.get(field,0) for r in weekly)==row.get(field,0),method+'/'+cat+'/weekly/'+field)
        actual=[w for w in range(4,10) if (method,cat,str(w))in scores and scores[method,cat,str(w)]['COMBINED']['decided']>0]
        check(actual==row['decided_weeks'],method+'/'+cat+'/actual_scored_weeks')
        check(row['available']+row['unavailable']==row['eligible'],method+'/'+cat+'/full_frame')
        check(all(0<=row[k]<=row['available'] for k in ('native','fallback','attribution_unknown')),method+'/'+cat+'/attribution_support')
    for j,s in enumerate(c['own_selection_policies']):
        batches=s['batches'];selected=sum(x['selected'] for x in batches);summary=s['own_selected_summary']
        check(sum(x['eligible'] for x in batches)==s['eligible_board'],f'select/{j}/eligible')
        check(selected==summary['COMBINED']['selected'],f'select/{j}/selected')
        check(sum(x['unknown'] for x in batches)==summary['selected_unknown'],f'select/{j}/unknown')
        check(math.isclose(s['achieved_coverage'],selected/s['eligible_board'] if s['eligible_board'] else 0,abs_tol=1e-12),f'select/{j}/coverage')
        for b in batches:check(b['capacity']==math.floor(s['fraction']*b['eligible']) and 0<=b['selected']<=b['capacity'],f'select/{j}/capacity')
    # Independent exact-ID mask reconstruction. Never infer identities by name.
    from bind_shared_sim_saved_b_v1 import prior_identity_maps,team_key
    identity=json.loads(a.identity.read_bytes());players=prior_identity_maps(identity);events=identity['ESPN_game_to_canonical_game']
    cb=(a.canonical/'comparison_inputs/cases.jsonl').read_bytes()
    if digest(cb)!='19ccf34b3037e1790ee3b2bf61d3357f33e63916779c2f36023a232f6a66ea18':raise ValueError('Canonical cases changed')
    cases=[json.loads(x) for x in cb.splitlines()];index={};duplicates=set()
    for raw in json.loads(gzip.decompress(bb)):
        if raw['season']!=2026 or raw['arm']!='M3-0':continue
        key=(raw['week'],raw['game_id'],raw['player_id'],raw['category'])
        r={k:raw.get(k) for k in ('position','team','mean','median','learned','fallback','model_binding','feature_age_policy')}
        if key in index and index[key]!=r:duplicates.add(key)
        index[key]=r
    reconstructed={};mask_reviews=[]
    for cat in ('rec','rec_yd'):
        method=f'C-M3-v1.1::{cat}::M3-0::base::MEAN_POINT';keep={}
        for ordinal,case in enumerate(cases):
            q=case['identity']
            if q['category']!=cat or q['position'] not in ('WR','TE'):continue
            g=events.get(str(q['game_id']));p=players[q['week']].get(str(q['player_id']))
            if not g or not p:continue
            key=(q['week'],g['game_id'],p,cat);row=index.get(key)
            if key in duplicates or row is None or row['position']!=q['position'] or team_key(row['team'])!=team_key(q['team']) or not finite(row['mean']):continue
            keep[case['case_id']]=(ordinal,case,row)
        ids=sorted(keep);h=digest(json.dumps(ids,separators=(',',':')).encode());group=next(x for x in masks['groups'] if x['category']==cat and method in x['methods'])
        equal=h==group['available_case_mask_SHA256'];mask_reviews.append({'category':cat,'procedure':method,'reconstructed_available':len(ids),'published_available':group['available'],'reconstructed_mask_SHA256':h,'published_mask_SHA256':group['available_case_mask_SHA256'],'exact_mask_match':equal,'scope':'Independent retained stable-ID join; no names or outcome availability used. If not equal, no aggregate raw grade reproduction asserted.'})
        if equal:reconstructed[cat]=(method,keep)
    # Only exact-mask verified products may open outcomes in this verifier.
    reproduction=[]
    if reconstructed:
        ob=(a.canonical/'grading_only/outcomes.v1.jsonl').read_bytes()
        if digest(ob)!='666885cbdc2ae7551f637b3d4a6999f15c07db956861f3f0374fad9c91b3a5ad':raise ValueError('Canonical outcomes changed')
        outcomes={r['case_id']:r['actual'] for r in map(json.loads,ob.splitlines())}
        benchmarks={r['case_id']:r for r in map(json.loads,(a.canonical/'comparison_inputs/benchmarks.jsonl').read_bytes().splitlines())}
        def direction(p,line):return 'OVER' if p>line else 'UNDER' if p<line else None
        def correct(side,y,line):return None if y is None or side is None or Decimal(str(y))==Decimal(str(line)) else (Decimal(str(y))>Decimal(str(line)))==(side=='OVER')
        for cat,(method,keep)in reconstructed.items():
            counts={s:collections.Counter() for s in ('OVER','UNDER')};pairs={k:collections.Counter() for k in ('W0','W1')}
            for cid,(_,case,row)in keep.items():
                line=case['identity']['line'];s=direction(row['mean'],line);y=outcomes[cid];z=correct(s,y,line)
                if s:counts[s]['selected']+=1
                if s and y is None:counts[s]['unknown']+=1
                if z is not None:counts[s]['wins' if z else 'losses']+=1
                for control,field in [('W0','W0_literal_saved_adj'),('W1','W1_literal_provider_or_adjusted_fallback')]:
                    bs=direction(benchmarks[cid][field],line);bz=correct(bs,y,line)
                    if z is None or bz is None:continue
                    pairs[control]['common_decided']+=1;pairs[control]['primary_wins']+=int(z);pairs[control]['control_wins']+=int(bz)
            own=scores[method,cat,'ALL']
            for s in ('OVER','UNDER'):
                for field in ('wins','losses','selected'):check(counts[s][field]==value(own[s][field]),f'reconstruct/{cat}/{s}/{field}')
                check(counts[s]['unknown']==own[s]['selected_unknown'],f'reconstruct/{cat}/{s}/unknown')
            for control,r in pairs.items():
                expected=next(x for x in c['saved_control_vs_website']['paired'] if x['candidate']==method and x['category']==cat and x['control']==control and str(x['week'])=='ALL')
                for field in ('common_decided','primary_wins','control_wins'):check(r[field]==expected[field],f'reconstruct/{cat}/{control}/{field}')
                reproduction.append({'category':cat,'procedure':method,'control':control,'counts':dict(r),'paired_scope':'Exact available-case mask matched before canonical grade join; independent Decimal strict crossing, not common scorer call.'})
    report={'id':'B-C-SAVED-COMPARISON-INDEPENDENT-REVIEW-v1','UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'state':'PASS_SCOPED' if not failures else 'FAIL_SCOPED','arithmetic_checks':len(checks),'failed_checks':failures,'published_vectors':{'scores':len(c['scores']),'paired':len(c['paired']),'own_selection_policies':len(c['own_selection_policies']),'saved_control_pairs':len(c['saved_control_vs_website']['paired'])},'independent_mask_reviews':mask_reviews,'raw_mean_reproduction':reproduction,'selection_scope':'Batches/capacity/own-side/unknown conservation checked. Private selection memberships not supplied; no Bfullmembershipreproduction claim.','unverified':['Private full typed27000k forecastbody/hash reconstruction','Private Cidentitymapping except independently matching named masks if any','Model/fit reproduction and source publication vintages','Bootstrap resampling/interval endpoints','Law source-to-CDF reproduction and full own-list membership','Simulator mutation/conservation; zero simulatorgames/trajectories'],'source_hashes':{'machine':digest(mb),'base_saved_forecasts':digest(bb),'canonical_cases':digest(cb)},'new_predictive_experiments':0,'new_grades_scope':'Verification of already-published immutable Cproducts only, no newcandidate tournament or canonical result replacement','resource':{'CPU_seconds':time.process_time()-cpu,'wall_seconds':time.monotonic()-wall,'peak_RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,'scope':'Controlled verifier only; preparation/controller overhead separately limited'}}
    a.output.write_bytes(canonical(report)+b'\n')
    print(json.dumps({'state':report['state'],'arithmetic_checks':len(checks),'failed_checks':len(failures),'mask_reviews':mask_reviews,'exact_mean_reproductions':len(reproduction),'CPU':report['resource']['CPU_seconds']}))
if __name__=='__main__':main()
