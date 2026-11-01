"""Separate exact-offer projection. Original v4 forecast files are never rewritten."""
import argparse,hashlib,json
from pathlib import Path
from datetime import datetime,timezone
from paper_v5 import ROOT,REGISTRY,read,sha,validate_packet,check_receipt,forecast_pool
from contracts_v2 import CATEGORIES

def projection(root=ROOT/'paper'):
    registry=read(REGISTRY);inventory=read(ROOT/'reports/actual-offers-v5/INVENTORY.json');records=[];first={};pool,_=forecast_pool(ROOT/'prospective')
    byid={f['forecast_id']:f for f in pool.values()}
    for p in sorted((root/'receipts').glob('*.json')):
        proof=read(p);run=root/'runs'/proof['run_id'];m,rows=validate_packet(run);persisted=check_receipt(run,proof,m,rows)
        packet=read(run/'offers.json');status={s['game_id']:s for s in packet['event_status']}
        for r in rows:
            if not r.get('forecast_id'):continue
            f=byid.get(r['forecast_id'])
            if not f:
                fs,_=forecast_pool(ROOT/'prospective',bound_ids={r['forecast_id']});f=next(iter(fs.values()))
            key=tuple(r[k] for k in ['game_id','player_id','category','venue','product'])
            order=(persisted,m['run_id'],r['offer_id'])
            if r.get('primary_in_packet') and not r['reasons']:first[key]=min(first.get(key,order),order)
            records.append(r|dict(name=f['name'],position=f['position'],team=f['team'],opponent_team=f['opponent_team'],mean=f['mean'],median=f['median'],selection_created_UTC=m['created_UTC'],selection_persisted_UTC=proof['server_persisted_UTC'],selection_run_id=m['run_id'],status_observed_UTC=status.get(r['game_id'],{}).get('observed_UTC'),event_state=status.get(r['game_id'],{}).get('state'),event_completed=status.get(r['game_id'],{}).get('completed'),server_receipt_URL=proof['server_URL'],evidence_tier='GITHUB_SERVER_VERIFIED_PREGAME_PAPER',book_settlement='UNVERIFIED',price_aware_state='NOT_VALUE_ADMITTED',rank=None))
    for r in records:
        key=tuple(r[k] for k in ['game_id','player_id','category','venue','product']);r['primary_scoring_snapshot']=first.get(key)==(check_time(r['selection_persisted_UTC']),r['selection_run_id'],r['offer_id'])
    groups={}
    for r in records:
        if r['primary_scoring_snapshot'] and r['P2_state']=='SELECTED' and not r['reasons']:
            key=(r['selection_run_id'],r['venue'],r['product'],r['tier']);groups.setdefault(key,[]).append(r)
    for rows in groups.values():
        for i,r in enumerate(sorted(rows,key=lambda r:(-max(r['p_over'],r['p_under']),r['game_id'],r['player_id'],r['category'],r['offer_id']))):r['rank']=i+1
    categories=[]
    for cat in CATEGORIES:
        inv=next(c for c in inventory['historical']['categories'] if c['category']==cat)
        categories.append(inv|dict(label=CATEGORIES[cat][0],historical_comparisons=0,historical_result='N/A: provider analysis/retention scope and original offered-side/contract evidence unqualified',paper_offers=sum(r['category']==cat for r in records),paper_selected=sum(r['category']==cat and r['P2_state']=='SELECTED' and r['primary_scoring_snapshot'] for r in records),graded=0,improvement='NOT_DEMONSTRATED'))
    return dict(schema='C-ACTUAL-PROPS-SITE-v5',policy='C-ACTUAL-OFFERS-v5',source_registry_SHA256=sha(REGISTRY),inventory_SHA256=sha(ROOT/'reports/actual-offers-v5/INVENTORY.json'),forward_manifest_SHA256=sha(ROOT/'docs/data/forward-manifest.json'),source_status=[dict(source_id=k,state=s['state'],analysis_qualified=s['analysis_qualified'],public_retention_qualified=s['public_retention_qualified'],evidence=s['evidence']) for k,s in registry['sources'].items()],categories=categories,records=records,historical_results=[],prospective_grades=[],historical_line_views=inventory['historical']['line_views'],historical_games=inventory['historical']['games'],six_leg_state='NO_QUALIFIED_SIX_LEG_ENTRY',entries=[],quotes_do_not_refresh_on_build=True,manual_only=True)

def check_time(v):
    from offer_validator_v2 import instant
    return instant(v)

def build(docs):
    j=projection();p=docs/'data/actual-props-v5.json';p.write_text(json.dumps(j,separators=(',',':'),allow_nan=False));b=read(docs/'build.json');b['actual_props_SHA256']=sha(p);b['actual_props_adapter_version']='C-ACTUAL-OFFERS-v5';(docs/'build.json').write_text(json.dumps(b,separators=(',',':')));print('EXACT_OFFER_SITE',len(j['records']),'NFL fits',0)

def validate(docs):
    j=read(docs/'data/actual-props-v5.json');assert j==projection(),'OFFER_SITE_NOT_PARITY_WITH_VERIFIED_PACKETS'
    assert read(docs/'build.json')['actual_props_SHA256']==sha(docs/'data/actual-props-v5.json')
    assert len(j['categories'])==12 and j['forward_manifest_SHA256']=='0d6e930ebdf683183db5f0383cebe56026974598b023e2c3cd5d8a2f8abe6f12','V4_DATA_UNEXPECTEDLY_CHANGED'
    print('EXACT_OFFER_SITE_PARITY',len(j['records']))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['build','validate']);p.add_argument('--docs',type=Path,default=ROOT/'docs');a=p.parse_args();build(a.docs) if a.command=='build' else validate(a.docs)
