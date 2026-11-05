"""Thin qualification projection from the single retained product ledger; no grading."""
import gzip
import json
from pathlib import Path
from predictive_information_c01 import ROOT,read,write,sha

BASE=ROOT/'reports/post-wave-5w-v1'
SITE=ROOT/'docs/data/qualification-5w.json.gz'

def project():
    data=read(BASE/'QUALIFICATION_TABLE.json.gz')
    fields=['row_id','owner','procedure_id','category','product','role_scope','history','policy','source_panel','evidence_tier','scored_week_count','current_2026_scored_week_count','scored_cases','five_week_floor','operational_export','tested_season_weeks','zero_selection_weeks','unresolved_only_weeks','season_records','own_side_record','same_decided_constants','named_delivery_product','strongest_bound_model_control','remaining_gates','source_artifacts']
    rows=[]
    for r in data['rows']:
        q={k:r[k] for k in fields if k in r}
        q['selected']=sum(w['selected'] or 0 for w in r['week_records'])
        q['eligible']=sum(w['eligible'] or 0 for w in r['week_records'])
        rows.append(q)
    return dict(schema='ABC-PRODUCT-QUALIFICATION-5W-v1',generated_UTC=data['generated_UTC'],ledger_SHA256=sha(BASE/'QUALIFICATION_TABLE.json.gz'),rule=data['rule'],limits=data['limits'],categories=read(BASE/'TWELVE_CATEGORY_QUALIFICATION.json'),rows=rows)

def build():
    write(SITE,project());b=read(ROOT/'docs/build.json');b['qualification_5w_SHA256']=sha(SITE);write(ROOT/'docs/build.json',b)

def validate():
    a=read(SITE);assert a==project();assert sha(SITE)==read(ROOT/'docs/build.json')['qualification_5w_SHA256']
    assert len(a['categories'])==12
    assert all((r['five_week_floor']=='MET')==(r['scored_week_count']>=5) for r in a['rows'])
    c=next(r for r in a['rows'] if r.get('named_delivery_product')=='pass_td__COUNT_A_MEAN')
    assert (c['scored_week_count'],c['own_side_record']['COMBINED']['wins'],c['own_side_record']['COMBINED']['decided'])==(7,87,142)
    assert 'BLOCKED' in c['operational_export']
    print('SINGLE_LEDGER_FIVE_WEEK_SITE_PARITY_VALID;NO_PRIMARY_PROMOTION')

if __name__=='__main__':
    import sys
    validate() if 'validate' in sys.argv else build()
