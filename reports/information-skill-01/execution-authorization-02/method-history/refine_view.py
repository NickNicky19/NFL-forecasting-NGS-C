"""Metadata-only normalization: coverage placeholders are not model families."""
from pathlib import Path
import csv
import gzip
import hashlib
import io
import json
import re
import time

START=time.process_time()
D=Path(__file__).resolve().parent
p=D/'METHOD_HISTORY.json.gz'
before=hashlib.sha256(p.read_bytes()).hexdigest()
view=json.loads(gzip.decompress(p.read_bytes()))
kept=[];gaps=[];aliases=[]
for item in view['procedures']:
    pid=item['original_id'];name=item['family_name'];owner=item['owner']
    reason=None
    if 'NOT_EXECUTED' in pid or name.endswith('NOT_EXECUTED'):
        reason='Coverage/status placeholder, not an identified executable method for this category'
    elif 'NO_QUALIFIED_ACTUAL_OFFER_PRODUCT' in pid:
        reason='Missing qualified product/offer contract; no method identity supplied by this placeholder'
    elif owner=='B' and name.endswith('SOURCE_METHOD'):
        reason='Extractor did not resolve an exact B procedure identity from the source container; not a tested method or loser'
    elif owner=='C' and item['category']!='pass_yd' and any(x in pid for x in ['P2_LINKED_V8','P2_WORKLOAD_V8']):
        reason='Passing-yards-only workload mechanism; other-category source rows are unsupported coverage cells'
    if reason:
        gaps.append(dict(reason=reason,source_placeholder=item,retained_execution_views=[]))
        continue
    old=item['family_id'];new=None
    if owner=='C':
        if name.endswith('P2_LAW'):new='Empirical Leaf response law'
        elif name.endswith('P3_DIRECT') or name.endswith('CONTROL_P3_DIRECT'):new='Histogram boosting threshold/direct procedure'
        elif 'PLAYER-CONTEXT-MATCHUP-01::v1.1::P1' in pid or 'PLAYER-CONTEXT-MATCHUP-01::v1.1::P2' in pid:
            new='Partially pooled Poisson'
        elif 'P2_LINKED_V8' in pid:new='Passing workload linked law (P2_LINKED_V8)'
        elif 'P2_WORKLOAD_V8' in pid:new='Passing workload law (P2_WORKLOAD_V8)'
    if new and new!=name:
        item['family_name']=new;item['family_id']='C::'+new
        item['family_alias_evidence']='C source-bound method/version identifiers plus src/laws_v2.py and retained context/workload registrations; family grouping only, exact procedure IDs are not merged.'
        item['family_aliases']=list(dict.fromkeys(item.get('family_aliases',[])+[old]))
        aliases.append(dict(procedure_key=item['procedure_key'],old_family=old,new_family=item['family_id']))
    kept.append(item)
gapmap={g['source_placeholder']['procedure_key']:g for g in gaps}
executions=[]
for row in view['executions']:
    gap=gapmap.get(row['procedure_key'])
    if gap is None:executions.append(row)
    else:gap['retained_execution_views'].append(row)
families={}
for item in kept:
    f=families.setdefault(item['family_id'],dict(family_id=item['family_id'],name=item['family_name'],owner=item['owner'],procedure_keys=[],categories=[]))
    f['procedure_keys'].append(item['procedure_key']);f['categories']=sorted(set(f['categories']+[item['category']]))
view.update(procedures=kept,families=list(families.values()),executions=executions,
            coverage_gap_records=view.get('coverage_gap_records',[])+gaps,
            family_alias_normalization=aliases)
view['limitations'].append('Pure NOT_EXECUTED/unresolved-method/unsupported-category cells are preserved under coverage_gap_records, not counted as model families or exact procedures. C family aliases are grouped only where retained identifiers/code substantiate them; ambiguous B families remain separate.')
p.write_bytes(gzip.compress(json.dumps(view,separators=(',',':'),allow_nan=False).encode(),compresslevel=6,mtime=0))
fields=['category','owner','family_id','family_name','original_id','product_types','milestones','verification_scope','scientific_disposition','source_records']
stream=io.StringIO(newline='');writer=csv.DictWriter(stream,fields);writer.writeheader()
for row in kept:writer.writerow({k:json.dumps(row[k],separators=(',',':')) if isinstance(row[k],(list,dict)) else row[k] for k in fields})
(D/'PROCEDURES.csv.gz').write_bytes(gzip.compress(stream.getvalue().encode(),compresslevel=6,mtime=0))
readme=(D/'README.md').read_text();prefix=readme.split('## pass_yd',1)[0];suffix=readme.split('## Source coverage and remaining gaps',1)[1]
prefix=re.sub(r'This extract contains \d+ descriptive family groups, \d+ exact procedure/configuration records and \d+ retained evaluation views\.',f'This extract contains {len(families)} descriptive family groups, {len(kept)} exact procedure/configuration records and {len(executions)} retained evaluation views.',prefix)
text=[prefix.rstrip(),'']
for cat in view['categories']:
    ps=[r for r in kept if r['category']==cat];ids=sorted(set(r['family_id'] for r in ps))
    text+=['## '+cat,'','| Owner / family or mechanism | Exact procedures | Retained execution/status |','| --- | ---: | --- |']
    for fid in ids:
        group=[r for r in ps if r['family_id']==fid];states=sorted(set(s for r in group for s in r['milestones']))
        text.append('| '+families[fid]['owner']+' / '+families[fid]['name'].replace('|','/')+' | '+str(len(group))+' | '+'; '.join(states).replace('|','/')+' |')
    text+=['','All exact IDs and retained metrics/periods/source locations are in the same machine view. Coverage gaps and unsupported cells are listed separately, not as model families.','']
text+=['## Source coverage and remaining gaps',suffix,
       '\n## Coverage placeholders and family aliases\n',
       f'{len(gaps)} original placeholder/configuration cells and their {sum(len(g["retained_execution_views"]) for g in gaps)} retained evaluation views were moved intact to `coverage_gap_records`. They remain inspectable; they are not forecasting methods, failed predictions or new observations.',
       'C P2_LAW/Leaf and P3_DIRECT/HGB aliases, source-bound context Poisson variants and passing-only workload aliases are grouped at family level. Exact IDs, outputs, source records and predecessors remain separate; ambiguous B mechanisms are not merged.']
(D/'README.md').write_text('\n'.join(text))
receipt=dict(status='PASS_METADATA_NORMALIZATION',before_view_SHA256=before,
    after_view_SHA256=hashlib.sha256(p.read_bytes()).hexdigest(),
    families=len(families),procedures=len(kept),execution_views=len(executions),
    moved_placeholder_records=len(gaps),moved_placeholder_execution_views=sum(len(g['retained_execution_views']) for g in gaps),
    family_alias_changes=len(aliases),new_scores=0,new_fits=0,new_network=0,
    process_CPU_seconds=time.process_time()-START,conservative_reporting_CPU_charge=2,
    source='Parent-authorized2CPU quality followup from reporting remainder; no pilot/reserve or newgrant',
    aliases=aliases)
(D/'QUALITY_FOLLOWUP.json').write_text(json.dumps(receipt,indent=2)+'\n')
assert time.process_time()-START<1.3,'FOLLOWUP_EXECUTION_CPU_GUARD'
print(json.dumps({k:v for k,v in receipt.items() if k!='aliases'}))
