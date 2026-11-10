import argparse,hashlib,json,datetime
from pathlib import Path
from urllib.request import Request,urlopen
p=argparse.ArgumentParser();p.add_argument('--commit',required=True);a=p.parse_args()
root=Path('/workspace/ngs-c');base='https://nicknicky19.github.io/NFL-forecasting-NGS-C/';files=['build.json','context.html','context.js','data/profile-closure-next-02.json'];saved=Path('/workspace/c04-served-bytes');saved.mkdir(exist_ok=True);rows=[]
for name in files:
 with urlopen(Request(base+name+'?verified='+a.commit,headers={'User-Agent':'C04-served-consumer-verifier'}),timeout=30) as r:
  b=r.read(2*1024*1024);headers=dict(r.headers);assert r.status==200 and len(b)<2*1024*1024
 if name=='build.json':
  build=json.loads(b);assert build['served_commit']==a.commit;assert build['profile_closure_next02_SHA256']==hashlib.sha256((root/'docs/data/profile-closure-next-02.json').read_bytes()).hexdigest()
 else: assert b==(root/'docs'/name).read_bytes(),name
 target=saved/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(b)
 rows.append(dict(path=name,bytes=len(b),SHA256=hashlib.sha256(b).hexdigest(),HTTP_Date=headers.get('Date'),HTTP_Age=headers.get('Age'),exact_parity=True))
data=json.loads((saved/'data/profile-closure-next-02.json').read_text());assert len(data['current']['rows'])==75 and data['current']['unique_players']==25 and data['current']['games']==1
report=dict(id='C04-SERVED-BYTE-VERIFICATION-v1',checked_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),URL=base+'context.html',served_commit=a.commit,files=rows,current_model_rows=75,players=25,games=1,source_status_is_immutable_early_snapshot=True,original_website_changed=False,primary_switch=False,scope='Cownresearchview;HTML/JS/data served bytes plus actualdeploymentcommit. BrowserDOMreceipt separate.')
(root/'reports/profile-closure-next-02/SERVED_VERIFICATION.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
