"""Verify the one added exact prior-context encoding read, no new HTTP."""
from pathlib import Path
import json,base64,hashlib,gzip,lzma,subprocess
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent;CACHE=Path('/workspace/c06-fresh-restore')
r=json.loads((CACHE/'PRIOR_CONTEXT_RESPONSE.json').read_bytes());b=base64.b64decode(''.join(r['content'].split()),validate=True)
assert r['commit']=='0cbf4c156608f8ec69d928ae7434eec877f14914' and len(b)==604500
assert hashlib.sha256(b).hexdigest()=='27828cc322333bd67602aea6df6a032cfb6c74cee34737bbe8b20fe02590dc8f'
assert hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==r['sha']
p=CACHE/r['path'];assert p.read_bytes()==b
csv=gzip.decompress(b);assert len(csv)==4702640 and hashlib.sha256(csv).hexdigest()=='b025865d00014f2b53b29f73d9e65b043abdbe2969e4afc29547620f6d96e097'
assert csv==lzma.decompress((ROOT/'sources/player-context-matchup-01/pbp_facts_2025.csv.xz').read_bytes())
plan=json.loads((OUT/'FRESH_GITHUB_RESTORE_PLAN.json').read_bytes())
for row in plan['paths']:
 old=subprocess.check_output(['git','rev-parse',plan['immutable_commit']+':'+row['path']],cwd=ROOT,text=True).strip()
 new=subprocess.check_output(['git','rev-parse','0cbf4c156608f8ec69d928ae7434eec877f14914:'+row['path']],cwd=ROOT,text=True).strip();assert old==new
j=json.loads((OUT/'PRIOR_CONTEXT_FRESH_RECOVERY.json').read_bytes());assert j['total_file_reads']==23 and j['total_returned_structured_content_bytes']==2643000 and j['total_returned_structured_content_bytes']<j['returned_content_byte_cap']
print('C06_EXACT_PRIOR_CONTEXT_ENCODING_RECOVERY_PASS;23FILES;NO_EXTRA_HTTP_FIT_OR_INFERENCE')
