"""Deployment-only metadata; never changes forecast or offer clocks."""
import argparse,json,hashlib
from pathlib import Path
from datetime import datetime,timezone
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--commit',required=True);p.add_argument('--root',type=Path,default=Path('docs'));a=p.parse_args();f=a.root/'build.json';j=json.loads(f.read_text());j.update(served_commit=a.commit,built_at_UTC=datetime.now(timezone.utc).isoformat());f.write_text(json.dumps(j,indent=2));print(a.commit)
