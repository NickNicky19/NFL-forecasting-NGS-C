"""One finite immutable C run readback; public GitHub only, no NFL fitting."""
import concurrent.futures,datetime,hashlib,json
from pathlib import Path
from urllib.request import Request,urlopen
ROOT=Path(__file__).resolve().parents[2]
COMMIT='ff104ad177d57da28043272cbd0bea13dd88d008'
RUN=Path('prospective/runs/C-C04-20261110-W10-FIRST-01')
CACHE=Path('/workspace/c04-github-readback')
files=sorted(p for p in (ROOT/RUN).rglob('*') if p.is_file())
assert len(files)==17
assert sum(p.stat().st_size for p in files)<5*1024*1024
CACHE.mkdir(exist_ok=True)
def one(p):
 rel=p.relative_to(ROOT);url='https://raw.githubusercontent.com/NickNicky19/NFL-forecasting-NGS-C/'+COMMIT+'/'+rel.as_posix()
 with urlopen(Request(url,headers={'User-Agent':'C04-immutable-restoration-check'}),timeout=30) as r:
  body=r.read(2*1024*1024);headers=dict(r.headers);status=r.status
 assert len(body)<2*1024*1024 and status==200
 expected=hashlib.sha256(p.read_bytes()).hexdigest();actual=hashlib.sha256(body).hexdigest();assert expected==actual and len(body)==p.stat().st_size,rel
 out=CACHE/rel;out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(body)
 return dict(path=str(rel),bytes=len(body),SHA256=actual,HTTP_status=status,HTTP_Date=headers.get('Date'),fresh_readback=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex: rows=list(ex.map(one,files))
report=dict(id='C04-GITHUB-CURRENT-RESTORATION-v1',commit=COMMIT,checked_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),files=rows,GETs=len(rows),bytes=sum(r['bytes'] for r in rows),all_exact=True,new_NFL_observations=0)
(ROOT/'reports/profile-closure-next-02/CURRENT_GITHUB_READBACK.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='files'}))
