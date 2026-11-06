"""Thin qualification projection from the single retained product ledger; no grading."""
import gzip
import json
from pathlib import Path
from predictive_information_c01 import ROOT,read,write,sha

BASE=ROOT/'reports/post-wave-5w-v1'
CURRENT=ROOT/'reports/abc-championship/execution-closure-02'
SITE=ROOT/'docs/data/qualification-5w.json.gz'

def project():
    base=CURRENT if (CURRENT/'QUALIFICATION_TABLE.json.gz').exists() else BASE
    data=read(base/'QUALIFICATION_TABLE.json.gz')
    records=list(data['rows'])
    if data.get('profile_partitions'):
        from execution_closure02 import b_profiles
        assert len(data['profile_partitions'])==1
        part=data['profile_partitions'][0];assert sha(ROOT/part['source']['path'])==part['source']['SHA256']
        extra=b_profiles();assert len(extra)==part['rows'];records+=extra
    fields=['row_id','owner','procedure_id','category','product','role_scope','history','policy','source_panel','evidence_tier','scored_week_count','current_2026_scored_week_count','scored_cases','five_week_floor','operational_export','tested_season_weeks','zero_selection_weeks','unresolved_only_weeks','season_records','own_side_record','same_decided_constants','named_delivery_product','strongest_bound_model_control','remaining_gates','source_artifacts']
    rows=[]
    for r in records:
        q={k:r[k] for k in fields if k in r}
        if r['owner']=='B' and r['category']=='rush_att' and 'hgb-direct-history-controls-v1:absolute_error_point' in r['procedure_id']:
            q['operational_export']='INELIGIBLE_HISTORICAL_DEGENERATE_HGB_VERSION;NO_PRIMARY_PROMOTION'
            q['remaining_gates']='Audit C-F1: original pooled absolute-loss collapse; retain scores as invalidated evidence. Separately named Poisson/role repairs retain their own tested losses and are not collapsed into this version.'
        if r.get('named_delivery_product')=='pass_td__COUNT_A_MEAN':
            q['remaining_gates']=str(q.get('remaining_gates',''))+'; A owner must bind exact active history/corrector path and resolve any affected clock/ordering semantics before producer admission; no blanket claim that frozen scores are contaminated.'
        q['selected']=sum(w['selected'] or 0 for w in r['week_records']) if r['week_records'] else None
        q['eligible']=sum(w['eligible'] or 0 for w in r['week_records']) if r['week_records'] else None
        rows.append(q)
    return dict(schema='ABC-PRODUCT-QUALIFICATION-5W-v1',generated_UTC=data['generated_UTC'],ledger_SHA256=sha(base/'QUALIFICATION_TABLE.json.gz'),rule=data['rule'],limits=data['limits'],current_limits=data.get('current_limits'),profile_partitions=data.get('profile_partitions',[]),categories=read(BASE/'TWELVE_CATEGORY_QUALIFICATION.json'),rows=rows)

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
