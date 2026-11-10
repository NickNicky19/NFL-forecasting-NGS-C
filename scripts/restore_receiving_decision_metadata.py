"""Restore one whitelisted losslessly retained metadata member, never fits."""
from pathlib import Path
import json,gzip,hashlib
root=Path(__file__).resolve().parents[1];folder=root/'reports/player-context-matchup-01/completion-decision-v1';m=json.loads((folder/'REPORT_METADATA_RETENTION.json').read_text());allowed='reports/player-context-matchup-01/completion-decision-v1/lookback/VALIDATION_SCORES.json'
assert m['original_path']==allowed and m['retained_path']==allowed+'.gz'
p=root/m['original_path'];q=root/m['retained_path'];b=gzip.decompress(q.read_bytes());assert hashlib.sha256(q.read_bytes()).hexdigest()==m['retained_SHA256'];assert hashlib.sha256(b).hexdigest()==m['original_SHA256']
if p.exists():assert p.read_bytes()==b,'REFUSE_OVERWRITE_DIFFERENT_EVIDENCE'
else:p.write_bytes(b)
print('EXACT_VALIDATION_METADATA_RESTORED_NO_FITS')
