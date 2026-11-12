"""Read-only final public-byte verification; no network, fitting or scoring."""
from pathlib import Path
import json,lzma,hashlib,ast
R=Path(__file__).resolve().parent
for row in json.loads((R/'FETCH_LEDGER.json').read_text()):
 n=row['name']
 if row.get('kind')=='commit' or n in ['B_INDEX_CONNECTOR','A_CURRENT_NATIVE_WORKFLOW']:continue
 ext='.py.xz' if n=='A_COUNTA_CORRECTOR_SOURCE' else '.json.xz'
 p=R/(n+ext)
 if not p.exists():continue
 b=lzma.decompress(p.read_bytes())
 if n=='B_INDEX_RAW':continue  # Its retained index is an explicit sanitized discovery projection.
 assert hashlib.sha256(b).hexdigest()==row['decoded_SHA256'],n
 assert hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==row['git_blob_SHA'],n
source=lzma.decompress((R/'A_COUNTA_CORRECTOR_SOURCE.py.xz').read_bytes());assert len(source)==31195 and hashlib.sha256(source).hexdigest()=='aa7c002506b57d7c1ca643f4236e5fb8b5132bebb00ad86720ee11221b6d9fb6';ast.parse(source)
a=json.loads((R/'ADMISSION.json').read_text());assert a['new_fits']==a['new_model_inference']==a['new_NFL_games_or_weeks']==0
rows=json.loads((R/'OWNER_DECISION_ROWS.json').read_text())['rows'];assert len(rows)==12
proof=json.loads((R/'COUNT_A_MEAN_OWN_WEEKLY_REUSE.json').read_text());assert proof['legacy_product_used_to_fill_mean_weeks'] is False
assert [x['COMBINED']['wins'] for x in proof['actual_own_rows']]==[4,13,14,14,4]
assert sum(x['COMBINED']['decided'] for x in proof['actual_own_rows'])==86
print('FOLLOW_THROUGH_PUBLIC_INTAKE_VALID',12,242,'DIRECT_COUNT_A_MEAN_49_OF86')
