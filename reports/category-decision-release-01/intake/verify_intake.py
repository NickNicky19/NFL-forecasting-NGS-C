"""Validate retained public exact-version bytes and coverage; no network or NFL fitting."""
from pathlib import Path
import json,lzma,hashlib,csv,io
R=Path(__file__).resolve().parent
ledger=json.loads((R/'FETCH_LEDGER.json').read_text());assert len(ledger)==73
manifest=json.loads((R/'AGGREGATE_MANIFEST.json').read_text());rows=0
for rec in manifest['files']:
 p=R/rec['path'];assert hashlib.sha256(p.read_bytes()).hexdigest()==rec['retained_SHA256']
 b=lzma.decompress(p.read_bytes());assert len(b)==rec['bytes'] and hashlib.sha256(b).hexdigest()==rec['SHA256']
 rs=list(csv.DictReader(io.StringIO(b.decode())));assert len(rs)==rec['rows'];rows+=len(rs)
assert len(manifest['files'])==65 and rows==4758
matrix=json.loads(lzma.decompress((R/'NEW_EXACT_PRODUCT_WEEK_MATRIX.json.xz').read_bytes()))
assert len(matrix)==160 and len({r['candidate_id'] for r in matrix})==20
for cid in sorted({r['candidate_id'] for r in matrix}):
 rs=[r for r in matrix if r['candidate_id']==cid];assert sorted(int(r['week_view']) for r in rs)==list(range(1,9))
 assert [int(r['week_view']) for r in rs if (r.get('combined_decided') or 0)>0]==[1,2,3,4,5]
primary=json.loads(lzma.decompress((R/'NEW_EXACT_PRODUCT_CUMULATIVE.json.xz').read_bytes()))
for r in primary:
 for side in ['over','under','combined']:
  assert r[side+'_wins']+r[side+'_losses']==r[side+'_decided']
 assert r['combined_wins']==r['over_wins']+r['under_wins']
 assert r['combined_decided']==r['over_decided']+r['under_decided']
a=json.loads((R/'ADMISSION.json').read_text());assert a['W5_overlap']['state']=='UNKNOWN_PRIVATE_NORMALIZED_MEMBERSHIP_NOT_EXPORTED'
assert a['new_fits']==a['new_inference']==a['new_NFL_games_or_weeks']==0
print('EXACT_PEER_READBACK_VALID',65,4758,20,160)
