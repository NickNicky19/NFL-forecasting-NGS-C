"""Compact site evidence derived from full canonical records; never fits models."""
import json
from collections import Counter
from pathlib import Path
from reliability_v8 import ROOT,OUT,ART,read,write,key,references,now
from diagnose_v8 import latest,cases,classify,metrics
import actual_accuracy_v6 as a

def compact(m):return {k:v for k,v in m.items() if k not in ['provider_VOID_sensitivity_fixed_membership','confidence_bins']}
def display_metric(m):
    d={k:v for k,v in m.items() if k!='note'}
    if 'confidence_bins' in d:d['confidence_bins']=[{k:v for k,v in b.items() if k in ['bin','n','mean_selected_probability','observed_win_rate','winrate_interval']} for b in d['confidence_bins'] if b['n']]
    if 'uncertainty' in d:d['uncertainty']={k:v for k,v in d['uncertainty'].items() if k!='qualification'}
    if 'provider_VOID_sensitivity_fixed_membership' in d:d['provider_VOID_sensitivity_fixed_membership']=display_metric(d['provider_VOID_sensitivity_fixed_membership'])
    return d
def build():
    raw=latest();cmap=cases();bank=references();rr=[classify(r,cmap[r['offer_id']],bank) for r in raw if r['method_id'] in ['P1_MEAN','P1_MEDIAN','P2_LAW','P3_DIRECT','P2_LINKED_V8','P2_WORKLOAD_V8','EARLIER_PREVALENCE_V8']];slices=[];curves=[]
    for book in ['pinnacle','draftkings','fanduel']:
     for cat in ['pass_yd','rush_yd','rec','rec_yd']:
      for method in ['P1_MEAN','P1_MEDIAN','P2_LAW','P3_DIRECT','P2_LINKED_V8','P2_WORKLOAD_V8','EARLIER_PREVALENCE_V8']:
       parent=[r for r in rr if r['venue']==book and r['category']==cat and r['method_id']==method]
       if not parent:continue
       for week in ['ALL','2','3']:
        for role in ['ALL']+sorted({r['position'] for r in parent}):
         for side in ['ALL','OVER','UNDER']:
            q=[r for r in parent if (week=='ALL' or r['week']==int(week)) and (role=='ALL' or r['position']==role) and (side=='ALL' or r['selected_side']==side)];slices.append(dict(book=book,category=cat,method=method,week=week,role=role,side=side,**metrics(q)))
       for threshold in [.5,.6,.7,.8,.9]:
            q=[r for r in parent if r['_confidence'] is not None and r['_confidence']>=threshold];curves.append(dict(book=book,category=cat,method=method,minimum_nominal_probability=threshold,parent_eligible=len(parent),rule='DIAGNOSTIC_FIXED_PREDECLARED_DECILE_BOUNDARY;NOT_AN_ADMITTED_SELECTOR',**compact(metrics(q))))
    ranks=read(OUT/'RANK_RESULTS.json.gz');thin=[]
    for r in ranks:
        z=compact(r);sens=r['provider_VOID_sensitivity_fixed_membership'];z['provider_VOID_sensitivity_fixed_membership']=compact(sens);thin.append(z)
    mechanism=[dict(book=b,method=m,**metrics([r for r in rr if r['venue']==b and r['category']=='pass_yd' and r['method_id']==m])) for b in ['pinnacle','draftkings','fanduel'] for m in ['P2_LAW','P3_DIRECT','P2_LINKED_V8','P2_WORKLOAD_V8']]
    write(OUT/'WORKLOAD_ACTUAL_RESULTS.json',mechanism);write(OUT/'RELIABILITY_SLICES.json.gz',slices);write(OUT/'CONFIDENCE_COVERAGE.json.gz',curves)
    coverage={cat:{b:sum(c['category']==cat and c['venue']==b for c in cmap.values()) for b in ['pinnacle','draftkings','fanduel']} for cat in a.CATEGORIES}
    data=dict(schema='C-SELECTED-SIDE-RELIABILITY-v8',generated_UTC=now(),generated_clock_kind='REPORT_GENERATION_NOT_FORECAST_OR_QUOTE_REFRESH',source_revision='f37857bfdc67ac4e3ecb2851eb274aee7601057d',source_attribution='PropLine (prop-line.com), CC BY4.0; C normalization, exact-line statistical grading, ranking and workload models are separate modifications.',period='2026Weeks2-3;2025workloadvalidationONLYW9andW13',tier='TIMING_UNVERIFIED_ACTUAL_LINE_DIAGNOSTIC',ranking_tier='EXPLORATORY_LAST_RECORDED_LINE_RANKING_DIAGNOSTIC',no_common_pregame_slate=True,no_entry_or_payout=True,overview=read(OUT/'OVERVIEW.json'),books=['pinnacle','draftkings','fanduel'],categories=[dict(id=c,label=v[0]) for c,v in a.CATEGORIES.items()],methods=sorted({r['method_id'] for r in rr}),slices=[display_metric(s) for s in slices],rankings=[display_metric(s) for s in thin],confidence_coverage=[display_metric(s) for s in curves],workload_actual=[display_metric(s) for s in mechanism],workload_numerical=read(OUT/'WORKLOAD_NUMERICAL.json'),book_inventory=read(OUT/'BOOK_INVENTORY.json'),intersections=[{k:v for k,v in g.items() if k not in ['same_cases','mismatches']} for g in read(OUT/'BOOK_INTERSECTIONS.json.gz')],coverage=coverage,current_offer_gate=read(OUT/'CURRENT_GATE_INITIAL.json')['exact_offer_gate'],market_benchmark='N/A: no retained historical OPEN lifecycle; identical side clocks/prices alone do not qualify a market.',scientific_state='NO_PROMOTION;TWO_EXPOSED_WEEKS;BOOKS_REPEAT_FOOTBALL_OUTCOMES',mechanism_scope='Onlypass_yd;within-categoryranking only. Global challenger ranking unavailable without a separately registered complete procedure.',retained_bin_schema='Fixed10deciles; omitted zero-n bins render N/A; full bins/rolecounts retained in RELIABILITY_SLICES.json.gz',evidence_base='https://github.com/NickNicky19/NFL-forecasting-NGS-C/tree/main/reports/reliability-v8',retained_canonical_datasets=[dict(path=d['path'],SHA256=d['SHA256']) for d in a.read(a.MANIFEST)['datasets']])
    write(ROOT/'docs/data/reliability-v8.json',data);b=a.read(ROOT/'docs/build.json');b['reliability_v8_SHA256']=a.sha(ROOT/'docs/data/reliability-v8.json');a.stable_write(ROOT/'docs/build.json',b);print('RELIABILITY_SITE',len(slices),len(thin),'DATA_BYTES',(ROOT/'docs/data/reliability-v8.json').stat().st_size)
def validate():
    data=read(ROOT/'docs/data/reliability-v8.json');assert a.sha(ROOT/'docs/data/reliability-v8.json')==read(ROOT/'docs/build.json')['reliability_v8_SHA256']
    assert data['slices']==[display_metric(s) for s in read(OUT/'RELIABILITY_SLICES.json.gz')]
    assert data['confidence_coverage']==[display_metric(s) for s in read(OUT/'CONFIDENCE_COVERAGE.json.gz')]
    assert data['rankings']==[display_metric(compact(s)|{'provider_VOID_sensitivity_fixed_membership':compact(s['provider_VOID_sensitivity_fixed_membership'])}) for s in read(OUT/'RANK_RESULTS.json.gz')]
    rows=latest();assert len(rows)==data['overview']['canonical_method_rows']
    for s in data['slices']:
        q=[r for r in rows if r['venue']==s['book'] and r['category']==s['category'] and r['method_id']==s['method'] and (s['week']=='ALL' or r['week']==int(s['week'])) and (s['role']=='ALL' or r['position']==s['role']) and (s['side']=='ALL' or r['selected_side']==s['side'])]
        assert len(q)==s['eligible_rows'] and sum(r['status']=='WIN' for r in q)==s['wins'] and sum(r['status']=='LOSS' for r in q)==s['losses']
        assert sum(b['n'] for b in s['confidence_bins'])==s['known_probability_rows']
    assert len(data['categories'])==12 and data['no_common_pregame_slate'] and data['no_entry_or_payout']
    print('RELIABILITY_SITE_CANONICAL_PARITY',len(data['slices']),len(data['rankings']))

if __name__=='__main__':
    import sys
    validate() if sys.argv[1:]==['validate'] else build()
