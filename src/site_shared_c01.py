"""Minimal current shared/predictive projection; no new grading or model fits."""
import json
from pathlib import Path
from predictive_information_c01 import ROOT,OUT,read,write,sha,now

BASE=ROOT/'reports/abc-championship/shared-intake-v3'
SITE=ROOT/'docs/data/championship-shared-c01.json'


def project():
    status=read(BASE/'TWELVE_CATEGORY_STATUS.json')
    historical=read(BASE/'HISTORICAL_RAW_LEADERS.json.gz')
    pooled=read(BASE/'PARTIAL_E5_E7_ALL_PROCEDURES.json')
    scores=read(OUT/'ACTUAL_LINE_SCORES.json.gz')
    def row(r,period):
        q=dict(r);q['period']=period
        q['method']=r.get('procedure_id',r.get('method_id','N/A'))
        q['selected']=r.get('selected',(r.get('COMBINED') or {}).get('selected'))
        q['unavailable']=r.get('unavailable')
        return q
    panels={}
    panels['S']=dict(label='A/B/C · shared masks and separate Week 8 boards',details='Requested2026W1–8 remains PARTIAL. Three exact-offer diagnostic intersections now include A/B/C; native offer/outcome masks verified, common historical source cutoffs/private re-inference not established. Other categories use a separate A Week8 full-board point replay. Constant controls included. These are not one combined operational suite.',leaders='On shared Pinnacle W2–3 cases: passingyards AlwaysOver38/63; receptions B D2 and C P3 tie194/337; receivingyards B C02mean188/337 (only +1win versus strongest otherB187/337). Rushing A RB111 and B QB/RB174 remain separate. No universal or future champion.',rows=[row(r,'2026 weeks '+str(r['actual_weeks'])+' · '+r['panel']) for r in status])
    for key,period,title in [('H','E3_PARTIAL_2024_W1_8','A · 2024 Weeks 1–8 · source-specific'),('F','E4_PARTIAL_FULL_2024','A · full 2024 window · source-specific')]:
        # Bind actual source period labels instead of guessing a season from dates.
        ids=sorted({r['period_id'] for r in historical})
        matched=[p for p in ids if ('2024' in p and ('FULL' in p if key=='F' else 'W1_8' in p))]
        assert len(matched)==1,(key,ids)
        rr=[r for r in historical if r['period_id']==matched[0] and r['side']=='COMBINED']
        panels[key]=dict(label=title,details='Owner-local A retained procedure results through the pinned common summary. Fixed representative-book priority68/69/79; timing-unverified lines and settlement. All weeks shown within a partial source board, not every NFL offer. Private origin/source artifacts remain owner-local. Every procedure, weekly partition, losing arm and tied maximum is linked in the report.',leaders='Raw complete-policy maxima include controls and different selected subsets. Full2024 receptions P1_M206/320 selected331/2998, versus paired football175/320; attempts173/313 versus football172/313. Neither price-aware profit nor cross-session seasonal championship established.',rows=[row(t,matched[0]) for r in rr for t in r['raw_ties']])
    rr=[]
    for cat in ['pass_att','rush_att','rec']:
        choices=[r for r in pooled if r['category']==cat and r['COMBINED']['decided']]
        best=max(r['COMBINED']['rate'] for r in choices)
        rr.extend(row(r,'PARTIAL E5/E7 · 2024+2026 Weeks1–5 only') for r in choices if r['COMBINED']['rate']==best)
    panels['E']=dict(label='Partial pooled · same 2024+2026 Weeks 1–5',details='New aggregation of all14 fixed A procedures on BOTH same years and same Weeks1–5. Every season appears before pooling. No missing2022/2023/2025 silently dropped from a claimed full period. Fixed three-category suite summaries retain category-balanced and equal-season weights; these are not all12 routers.',leaders='Observed pooled complete-policy leaders: attempts122/225 (equal-season53.91%); carries74/125 (59.03%); receptions101/163 (61.96%). Receptions selected172/1522. Strong football controls on these exact new selected masks still require A supplement; constants alone are not sufficient evidence of incremental skill.',rows=rr)
    rr=[r for r in scores if r['week_view']=='ALL' and r['role']=='ALL' and r['method_id'] in ['share:S0','share:S1','completion:C0','completion:C1','completion:C2','retained:P2_LAW','retained:EARLIER_PREVALENCE_V8']]
    panels['M']=dict(label='C · new receiving information tests',details='Qualified exact Pinnacle receptions,2026W2–3 only. Unchanged learner/history/rows within each test. ShareS1 adds values toS0; completionC2 adds values toC1 and comparesC0. All22 unresolved native-team queries held unavailable;3selectedunknown remain. Raw fits/inference and classification correction retained. Both2025origins separately tested only synthetic diagnostics; no actual2025offers invented.',leaders='Target-share values:0wins/0probability change versus support. Completion values/support:0wins/0probability change versus C0. C0/C1/C2=194/337; S0/S1=189/337. Brier0.259868/0.260622 exceeds neutral0.25. No new feature earns inclusion;90% TARGET_NOT_ESTABLISHED. All registered Top6/10/20 variants remain exploratory last-recorded-line lists,not tickets.',rows=[row(r,'2026 W2–3 / exact lines / fullboard') for r in rr])
    bindings=[dict(path=str(p.relative_to(ROOT)),SHA256=sha(p)) for p in [BASE/'TWELVE_CATEGORY_STATUS.json',BASE/'HISTORICAL_RAW_LEADERS.json.gz',BASE/'PARTIAL_E5_E7_ALL_PROCEDURES.json',OUT/'ACTUAL_LINE_SCORES.json.gz',OUT/'IDENTITY_QUALIFICATION_HOLD.json']]
    return dict(schema='ABC-SHARED-PREDICTIVE-C01-SITE-v1',prepared_UTC=now(),protocol='ABC-ACTUAL-PROP-CHAMPIONSHIP-v2-C-1',panels=panels,source_bindings=bindings,A_B_acknowledgements='RECEIVED_PINNED_C1_SCOPED_PUBLIC_CHECKS',publication='RESEARCH_DIAGNOSTIC_ONLY;no new original C props issued')


def build():
    write(SITE,project())
    b=read(ROOT/'docs/build.json');b['championship_shared_C01_SHA256']=sha(SITE);write(ROOT/'docs/build.json',b)


def validate():
    saved=read(SITE);expected=project()
    for key in ['schema','protocol','panels','source_bindings','A_B_acknowledgements','publication']:assert saved[key]==expected[key],key
    assert sha(SITE)==read(ROOT/'docs/build.json')['championship_shared_C01_SHA256']
    scores=read(OUT/'ACTUAL_LINE_SCORES.json.gz');rows=read(OUT/'CANONICAL_ACTUAL_ROWS.json.gz')
    for r in rows:
        if r.get('qualification'):assert r['selected_side'] is None and r['status']=='UNAVAILABLE_FORECAST' and r['probabilities'] is None
    assert len(saved['panels']['S']['rows'])==12
    for m,w in [('completion:C0',194),('completion:C1',194),('completion:C2',194),('share:S0',189),('share:S1',189)]:
        r=next(r for r in scores if r['method_id']==m and r['week_view']=='ALL' and r['role']=='ALL')
        assert (r['COMBINED']['wins'],r['COMBINED']['decided'],r['unavailable'],r['states']['UNKNOWN_PARTICIPATION'])==(w,337,22,3)
    print('SHARED_PREDICTIVE_CANONICAL_SITE_PARITY_VALID')


if __name__=='__main__':
    import sys
    validate() if 'validate' in sys.argv else build()
