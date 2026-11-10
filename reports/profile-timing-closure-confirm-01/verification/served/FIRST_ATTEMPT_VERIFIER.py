"""One bounded readback of C's static research consumer; no forecast refresh."""
import argparse,hashlib,json,datetime
from pathlib import Path
from urllib.request import Request,urlopen
p=argparse.ArgumentParser();p.add_argument('--commit',required=True);a=p.parse_args()
root=Path('/workspace/ngs-c');base='https://nicknicky19.github.io/NFL-forecasting-NGS-C/'
files=['build.json','context.html','context.js','data/timing-confirm-c05.json','data/profile-closure-next-02.json']
saved=Path('/workspace/c05-served-bytes');saved.mkdir(exist_ok=True);rows=[]
for name in files:
 with urlopen(Request(base+name+'?verified='+a.commit,headers={'User-Agent':'C05-served-consumer-verifier','Cache-Control':'no-cache'}),timeout=30) as r:
  b=r.read(1048577);headers=dict(r.headers);assert r.status==200 and len(b)<=1048576
 if name=='build.json':
  build=json.loads(b);assert build['served_commit']==a.commit
  assert build['timing_confirm_c05_SHA256']==hashlib.sha256((root/'docs/data/timing-confirm-c05.json').read_bytes()).hexdigest()
  assert build['profile_closure_next02_SHA256']==hashlib.sha256((root/'docs/data/profile-closure-next-02.json').read_bytes()).hexdigest()
 else:assert b==(root/'docs'/name).read_bytes(),name
 target=saved/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(b)
 rows.append(dict(path=name,bytes=len(b),SHA256=hashlib.sha256(b).hexdigest(),HTTP_Date=headers.get('Date'),HTTP_Age=headers.get('Age'),exact_parity=True))
data=json.loads((saved/'data/timing-confirm-c05.json').read_text())
assert len(data['current']['rows'])==69 and data['current']['players']==23 and data['current']['games']==1
assert data['current']['real_offers']==data['current']['real_selections']==0
old=json.loads((saved/'data/profile-closure-next-02.json').read_text());assert len(old['current']['rows'])==75
report=dict(id='C05-SERVED-BYTE-VERIFICATION-v1',checked_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),URL=base+'context.html',served_commit=a.commit,files=rows,current_model_rows=69,players=23,games=1,preserved_C04_rows=75,real_offers=0,real_selections=0,information_policy=data['current']['information_policy'],football_source_cutoff_UTC=data['current']['football_source_cutoff_UTC'],model_feature_cutoff_UTC=data['current']['model_feature_cutoff_UTC'],original_website_changed=False,primary_switch=False,scope='C research view only; exact served HTML/JS/current and preserved data plus deployment commit. Browser DOM receipt is separate.',GETs=len(rows),response_bytes=sum(r['bytes'] for r in rows),new_fits=0,new_inference=0)
assert report['response_bytes']<=1048576
(root/'reports/profile-timing-closure-confirm-01/SERVED_VERIFICATION.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
