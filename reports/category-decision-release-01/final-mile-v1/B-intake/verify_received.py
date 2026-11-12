"""Verify the received public B bindings/counts; no NFL prediction/grading."""
import json, lzma, hashlib
from pathlib import Path
R=Path(__file__).resolve().parent
load=lambda n:json.loads(lzma.decompress((R/(n+'.json.xz')).read_bytes()))
idx=load('CURRENT_EXPORT_INDEX')
a=json.loads((R/'ADMISSION.json').read_text())
for receipt in a['source_receipts']:
 body=lzma.decompress((R/(receipt['key']+'.json.xz')).read_bytes())
 entry=next(x for x in idx['exports'] if x['path']==receipt['path'])
 assert hashlib.sha256(body).hexdigest()==entry['sha256']==receipt['decoded_SHA256']
 assert len(body)==entry['bytes']==receipt['decoded_bytes']
s=load('SELECTOR_ACCOUNTING')
for w in s['weeks']:
 for key in ['selected','wins','losses','decided','unresolved','push','void']:
  assert w['candidate_generated_selected'][key]+w['fallback_generated_selected'][key]==w['candidate_full_system'][key]
 assert w['common_same_side_selected']+w['candidate_only_memberships']['selected']==24
 assert w['common_same_side_selected']+w['control_only_memberships']['selected']==24
assert [w['candidate_generated_selected']['selected'] for w in s['weeks']]==[2,4,2,0]
assert [w['fallback_generated_selected']['selected'] for w in s['weeks']]==[22,20,22,24]
assert s['cumulative']['candidate_generated_selected']['wins']==5
assert s['cumulative']['candidate_generated_selected']['losses']==3
assert s['cumulative']['full_candidate']['wins']==50
assert s['cumulative']['full_control']['wins']==48
assert s['cumulative']['complete_system_scored_weeks']==[5,6,7,8]
p=load('PRODUCT_RECEIPTS')['B_ATT_exact_product']
assert sum(int(w['COMBINED_wins']) for w in p['weekly'])==44
assert sum(int(w['COMBINED_losses']) for w in p['weekly'])==43
assert int(p['own_record']['COMBINED_decided'])==87
op=load('OPERATIONAL_ADDENDUM')
assert sum(op['native']['category_counts'].values())==1614
assert op['selected_research_rows']==0 and op['original_site_research_release'] is False
assert op['latest_workflow']['event']=='workflow_dispatch'
print('B_FINAL_MILE_RECEIPTS_VALID;2/4/2/0_C_SELECTED;NO_FIFTH_OR_COUNTA_DELIVERY_IN_SCOPE')
