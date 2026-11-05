"""Export unchanged C typed points for the retained owner's selector replay.

This is an inference-output handoff, not an additional Top Picks evaluator.
Begin with the owner's offer board; absent C queries remain unavailable.
"""
import gzip,hashlib,json,argparse
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/abc-championship/execution-closure-02'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def build(output=None):
    m=json.loads((ROOT/'docs/data/manifest.json').read_text());files=[];rows=[]
    fields=['version','slot','target','history','family','arm','game_id','player_id','name','position','team','opponent','season','week','kickoff_UTC','as_of_UTC','information_tier','generated_UTC','scoring_contract_id','fallback','mean','median','p05','p95','product_type']
    for f in m['files']:
        if f['history']!='H-MULTI' or f['family']!='P2_LEAF':continue
        p=ROOT/'docs/data'/f['file'];assert sha(p)==f['sha256'];data=json.loads(p.read_text());assert len(data)==f['rows']
        files.append(dict(path=str(p.relative_to(ROOT)),SHA256=sha(p),rows=len(data)))
        for i,r in enumerate(data):
            assert r['arm']=='E0_OP' and r['history']=='H-MULTI' and 1<=r['week']<=7
            q={k:r.get(k) for k in fields};q['source_row_index']=i;q['source_file']=str(p.relative_to(ROOT))
            q['procedure_id']='C::C-ALL12-LAW-THRESHOLD-v2.1::H-MULTI::P2_LEAF::E0_OP'
            q['evidence_tier']='CURRENT_VINTAGE_CHRONOLOGICAL_RECONSTRUCTION;NOT_ORIGINAL_PREGAME_ISSUANCE'
            q['selection_admission']='BLOCKED_CMP_ATT_COHERENCE' if r['target'] in ['pass_cmp','pass_att'] else 'NO_PROP_SELECTION_ISSUED;OWNER_EXACT_SELECTOR_REPLAY_REQUIRED'
            q['population_limit']='Retrospective participant/stat-row query population; not an authenticated pregame board. Missing query is unavailable, never DNP or zero.'
            q['law_exported']=False
            assert not any(k in q for k in ['actual','appearance','chart_state','grid','p_over','p_push','crps','grid_brier'])
            rows.append(q)
    assert len(files)==84 and len({(r['game_id'],r['player_id'],r['target']) for r in rows})==len(rows)
    b=gzip.compress((json.dumps(rows,separators=(',',':'),allow_nan=False)+'\n').encode(),mtime=0)
    if output:output.parent.mkdir(parents=True,exist_ok=True);output.write_bytes(b)
    manifest=dict(schema='C-OWNER-SELECTOR-INPUT-HANDOFF-v1',frozen_producer_commit='df02c7656dd616224057176d057e2494d51c5b32',source_manifest=dict(path='docs/data/manifest.json',SHA256=sha(ROOT/'docs/data/manifest.json')),payload=dict(path='TEMPORARY_MATERIALIZATION_ONLY',SHA256=hashlib.sha256(b).hexdigest(),bytes=len(b),rows=len(rows)),source_files=files,categories=dict(Counter(r['target'] for r in rows)),actual_weeks=list(range(1,8)),history='H-MULTI with inherited seven-day information policy; fit memory and source vintage remain exact frozen v2.1 recipe',typed_outputs='Unrounded retained mean and median plus saved intervals; no point-derived probability or grid interpolation',horizon='Per-game as_of_UTC; fixed weekly list must meet its earliest kickoff and all actual feature/offer availability constraints',source_rights='C-derived permitted public numerical outputs with original qualified football-fact source attribution; no upstream restricted offers or model files',anytime='Rush-or-receiving event only; no offered NO or point-based selection inferred',fantasy='Exact target contract with retained original label/coverage limitations; consumer must qualify venue parity',missing_inputs='Owner actual full offer board, exact proposed cross-session mapping and production selector/version, horizon/line precedence/fallback/ranking/expiry/tie-break inputs',execution_owner='Retained original-site owner; C does not create a competing Top Picks replay',consumer_acknowledgement='NOT_RECEIVED;publication is not delivery acknowledgement',new_fits=0,new_inference=0,new_scores=0,new_NFL_outcomes=0)
    manifest['materialization']=manifest.pop('payload');manifest['materialization'].pop('path')
    manifest['materialization']['command']='python scripts/export_closure02_historical_points.py --output <temporary-output.json.gz>'
    manifest['materialization']['retention']='All 84 exact source members already persist in C GitHub at frozen_producer_commit. This adapter projects their typed inputs excluding outcomes; no duplicate public archive.'
    (OUT/'C_OWNER_SELECTOR_HANDOFF.json').write_text(json.dumps(manifest,indent=2)+'\n');print('UNCHANGED_C_OWNER_INPUT_EXPORT',len(files),len(rows),len(b))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path);args=p.parse_args();build(args.output)
