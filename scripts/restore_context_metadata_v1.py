"""Restore exact permitted metadata bytes from the retained C zip, offline."""
import hashlib,json,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
index=json.loads((ROOT/'reports/player-context-matchup-01/SOURCE_METADATA_INDEX.json').read_text())
archive=ROOT/index['archive'];assert hashlib.sha256(archive.read_bytes()).hexdigest()==index['SHA256']
with zipfile.ZipFile(archive) as z:
 assert set(z.namelist())=={r['member'] for r in index['members']}
 for r in index['members']:
  p=(ROOT/r['member']).resolve();assert p.is_relative_to(ROOT/'reports/player-context-matchup-01')
  b=z.read(r['member']);assert len(b)==r['bytes'] and hashlib.sha256(b).hexdigest()==r['SHA256']
  if p.exists():assert p.read_bytes()==b,'PRESERVE_DIFFERENT_LOCAL_EVIDENCE'
  else:p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
print('EXACT_CONTEXT_METADATA_RESTORED',len(index['members']))
