"""Restore downloaded private recovery parts without exposing their locators."""
import argparse,base64,hashlib,json,zipfile,io
from pathlib import Path

def restore(parts,output):
 records=[json.loads(f.read_text()) for f in sorted(Path(parts).glob('part-*.json'))]
 if not records or [r['index'] for r in records]!=list(range(len(records))):raise ValueError('missing/duplicate/out-of-order parts')
 expected={r['archive_sha256'] for r in records}
 if len(expected)!=1:raise ValueError('mixed archives')
 b=b''.join(base64.b64decode(r['data'],validate=True) for r in records)
 if hashlib.sha256(b).hexdigest()!=next(iter(expected)):raise ValueError('archive digest mismatch')
 if zipfile.ZipFile(io.BytesIO(b)).testzip() is not None:raise ValueError('ZIP integrity')
 with Path(output).open('xb') as f:f.write(b)
 return len(b),next(iter(expected))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--parts',required=True);p.add_argument('--output',required=True);a=p.parse_args();print(restore(a.parts,a.output))
