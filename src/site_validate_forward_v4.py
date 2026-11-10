"""Static future-row parity and no-synthetic-offer acceptance."""
import json,hashlib
from pathlib import Path
from prospective_v4 import validate_run,read_json,validate_receipt
from site_forward_v4 import legacy_feed_run

def validate(docs,root):
    b=read_json(docs/'build.json');path=docs/'data/forward-manifest.json'
    assert hashlib.sha256(path.read_bytes()).hexdigest()==b['forward_manifest_SHA256']
    m=read_json(path);assert m['schema']=='C-UPCOMING-SITE-v4' and len(m['categories'])==12
    original={};legacy_run_ids=set();manifest_run_ids={r['run_id'] for r in m['runs']}
    for p in (root/'receipts').glob('*.json'):
        proof=read_json(p);run=root/'runs'/proof['run_id'];meta,rows=validate_run(run);validate_receipt(run,proof,meta,rows)
        if not legacy_feed_run(meta):
            assert proof['run_id'] not in manifest_run_ids,'TYPED_SHADOW_INCLUDED_IN_LEGACY_MANIFEST'
            continue
        legacy_run_ids.add(proof['run_id'])
        original.update({r['forecast_id']:r for r in rows})
    assert legacy_run_ids==manifest_run_ids,'LEGACY_FORWARD_MANIFEST_RUN_SCOPE_MISMATCH'
    seen=set();allrows=[]
    for item in m['files']:
        p=docs/'data'/item['file'];assert hashlib.sha256(p.read_bytes()).hexdigest()==item['SHA256'];rows=read_json(p);assert len(rows)==item['rows']
        for r in rows:
            a=original[r['forecast_id']];assert r['forecast_id'] not in seen;seen.add(r['forecast_id'])
            assert r['category']==item['category'] and r['evidence_tier']=='GITHUB_SERVER_VERIFIED_PREGAME'
            for k in ['player_id','game_id','category','model_SHA256','mean','median','p05','p95','event_probability','scoring_contract_id','information_cutoff_UTC','generated_UTC','kickoff_UTC','availability']:
                assert r[k]==a[k],'SERVED_FORECAST_PARITY_'+k
            assert r['target_history_support']==int(a['features'][3]) and r['target_sparse']==(r['target_history_support']<3)
            assert r['line'] is None and r['venue'] is None and r['p_over'] is None and r['p_under'] is None and r['selected_side'] is None and r['actual'] is None
            assert r['prop_state']=='Forecast only—prop line unavailable' and r['outcome_state']=='PENDING'
            allrows.append(r)
    assert len(seen)==m['forecast_rows']==len({(r['game_id'],r['player_id'],r['category'],r['policy_id']) for r in original.values()}) and {r['category'] for r in allrows}=={r['id'] for r in m['categories']}
    assert m['real_offers']==m['real_selections']==m['graded_outcomes']==0 and not m['real_offer_results'] and not m['historical_real_offer_results']
    assert not m['entries'] and m['six_leg_state']=='NO_QUALIFIED_SIX_LEG_ENTRY'
    print('FORWARD_SITE_CONTRACT_PASS',len(allrows));return m

if __name__=='__main__':validate(Path('docs'),Path('prospective'))
