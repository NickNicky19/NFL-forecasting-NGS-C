"""C-only normal Git Data API fallback for failed Git transport.

Preserve original local object identities; never force a ref or claim client
commit dates as server persistence. No model execution or external messages.
"""
import base64,argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime,timezone,timedelta
from pathlib import Path

REPO='NickNicky19/NFL-forecasting-NGS-C'
BRANCH='research/execution-closure-02'
parser=argparse.ArgumentParser();parser.add_argument('--base',default='df02c7656dd616224057176d057e2494d51c5b32');parser.add_argument('--target',default='0496ad9ddc233c0dca1e18a381afcc00fcaf5a50');parser.add_argument('--receipt-name',default='PUBLICATION_API_RECEIPT.json');parser.add_argument('--call-cap',type=int,default=160);args=parser.parse_args()
BASE=args.base
TARGET=args.target
OUT=Path('/workspace/c-closure02-git-transport');OUT.mkdir(exist_ok=True)
LIMIT=args.call_cap
assert 1<=LIMIT<=160 and len(BASE)==len(TARGET)==40
assert Path(args.receipt_name).name==args.receipt_name
calls=0
records=[]

def git(*args):return subprocess.check_output(['git',*args])
def api(path,data=None):
    global calls
    calls+=1;assert calls<=LIMIT,'C_PUBLICATION_API_CAP'
    command=['gh','api','repos/'+REPO+'/'+path]
    if data is not None:
        p=OUT/'request.json';p.write_text(json.dumps(data,separators=(',',':')));command+=['--method','POST' if not path.startswith('git/refs/') else 'PATCH','--input',str(p)]
    r=subprocess.run(command,capture_output=True,text=True)
    assert r.returncode==0,(path,r.stderr[:1000])
    return json.loads(r.stdout)
def person(line):
    ident,epoch,offset=line.rsplit(' ',2);name,email=ident.rsplit(' <',1);email=email.rstrip('>')
    sign=1 if offset[0]=='+' else -1;minutes=sign*(int(offset[1:3])*60+int(offset[3:5]))
    return {'name':name,'email':email,'date':datetime.fromtimestamp(int(epoch),timezone(timedelta(minutes=minutes))).isoformat()}

assert git('remote','get-url','origin').decode().strip()=='https://github.com/'+REPO+'.git'
head=api('git/ref/heads/'+BRANCH)['object']['sha'];assert head==BASE,('C_BRANCH_MOVED',head)
known=set(git('ls-tree','-r','--format=%(objectname)',BASE).decode().splitlines())
commits=git('rev-list','--reverse',BASE+'..'+TARGET).decode().splitlines()
for sha in commits:
    raw=git('cat-file','commit',sha).decode();headers,message=raw.split('\n\n',1);h=dict(x.split(' ',1) for x in headers.splitlines());parent=h['parent']
    entries=[]
    for line in git('diff-tree','--no-commit-id','--name-status','-r',parent,sha).decode().splitlines():
        status,path=line.split('\t',1)
        assert path.startswith(('AGENTS.md','START_HERE.md','protocol/','reports/','sources/','src/','tests/','prospective/','docs/','scripts/','.github/workflows/c-checks-pages.yml')),'UNEXPECTED_C_PUBLICATION_PATH'
        if status=='D':entries.append({'path':path,'mode':'100644','type':'blob','sha':None});continue
        row=git('ls-tree',sha,'--',path).decode();left,_=row.split('\t');mode,kind,blob=left.split();assert kind=='blob'
        if blob not in known:
            b=git('cat-file','blob',blob);assert len(b)<4*1024*1024
            obj=api('git/blobs',{'content':base64.b64encode(b).decode(),'encoding':'base64'});assert obj['sha']==blob,'BLOB_HASH_CHANGED';known.add(blob)
            records.append({'kind':'blob','SHA1':blob,'bytes':len(b),'path':path})
        entries.append({'path':path,'mode':mode,'type':'blob','sha':blob})
    parent_tree=git('rev-parse',parent+'^{tree}').decode().strip()
    tree=api('git/trees',{'base_tree':parent_tree,'tree':entries});assert tree['sha']==h['tree'],'TREE_HASH_CHANGED'
    c=api('git/commits',{'tree':tree['sha'],'parents':[parent],'message':message,'author':person(h['author']),'committer':person(h['committer'])})
    assert c['sha']==sha,('COMMIT_HASH_CHANGED',sha,c['sha'])
    records.append({'kind':'commit','SHA1':sha,'tree':tree['sha'],'exact_local_identity_preserved':True,'API_observed_UTC':datetime.now(timezone.utc).isoformat()})
    print('REMOTE_EXACT_COMMIT_OBJECT',sha,flush=True)
assert api('git/ref/heads/'+BRANCH)['object']['sha']==BASE,'C_BRANCH_MOVED_BEFORE_UPDATE'
updated=api('git/refs/heads/'+BRANCH,{'sha':TARGET,'force':False});assert updated['object']['sha']==TARGET
receipt={'completed_UTC':datetime.now(timezone.utc).isoformat(),'repository':REPO,'branch':BRANCH,'previous':BASE,'head':TARGET,'force':False,'API_calls':calls,'records':records,'client_dates_not_server_proof':True,'claim':'Objects published through normal API; prospective qualification still requires actual bound server checks and fresh readback.'}
(OUT/args.receipt_name).write_text(json.dumps(receipt,indent=2)+'\n');print('NORMAL_C_API_PUBLICATION_PASS',TARGET,calls)
