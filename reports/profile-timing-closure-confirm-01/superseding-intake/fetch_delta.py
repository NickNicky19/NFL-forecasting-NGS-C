"""Bounded immutable public delta metadata; no private rows/models/locators."""
import json,lzma,gzip,base64,subprocess,hashlib,datetime,re
from pathlib import Path
O=Path(__file__).resolve().parent;CAP=8388608;SINGLE=3145728;GETS=6;RETAIN=131072
OLD=O.parent/'intake'
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def write(p,d):p.write_text(json.dumps(d,indent=2)+'\n')
def sanitize(x):
 if isinstance(x,dict):return {k:sanitize(v) for k,v in x.items() if not any(s in k.lower() for s in ['credential','secret','private_locator','access_token']) and not(k.lower() in ['namespace','native_id','archive_id','file_id'] and str(v).startswith(('DEF_','NEXT02_')))}
 if isinstance(x,list):return [sanitize(v) for v in x]
 if isinstance(x,str):
  if re.search(r'https?://[^\s"\']*(?:drive\.google|dropbox|s3\.|storage\.google)',x,re.I) or re.match(r'^/(?:mnt|home|workspace|tmp)/',x):return '<OWNER_LOCAL_OR_RESTRICTED_LOCATOR_NOT_RETAINED>'
 return x

def fetch(repo,ref,path,name,index=False):
 lp=O/'FETCH_LEDGER.json';ledger=json.loads(lp.read_text()) if lp.exists() else [];assert len(ledger)<GETS
 prior=sum(r.get('response_bytes',0) for r in ledger);bound=min(SINGLE,CAP-prior);assert bound>0
 row=dict(repository=repo,ref=ref,path=path,started_UTC=now(),state='ATTEMPT_REGISTERED',max_response=bound);ledger.append(row);write(lp,ledger)
 p=subprocess.Popen(['gh','api',f'repos/{repo}/contents/{path}?ref={ref}'],stdout=subprocess.PIPE,stderr=subprocess.PIPE);body=p.stdout.read(bound+1)
 if len(body)>bound:p.terminate();row.update(state='CAP_FAILURE',response_bytes=len(body));write(lp,ledger);raise RuntimeError('BODY_CAP')
 error=p.stderr.read(1024);rc=p.wait();row.update(returncode=rc,response_bytes=len(body),response_SHA256=hashlib.sha256(body).hexdigest(),observed_UTC=now())
 if rc:row.update(state='FAILED',error=error.decode(errors='replace')[:300]);write(lp,ledger);raise RuntimeError('GET_FAILED')
 raw=json.loads(body);assert raw['encoding']=='base64';b=base64.b64decode(raw['content']);row.update(state='RECEIVED',decoded_bytes=len(b),decoded_SHA256=hashlib.sha256(b).hexdigest(),git_blob_SHA=raw.get('sha'))
 payload=gzip.decompress(b) if path.endswith('.gz') else lzma.decompress(b) if path.endswith('.xz') else b
 d=json.loads(payload) if path.endswith(('.json','.json.gz','.json.xz')) else payload.decode();d=sanitize(d)
 projection='Sanitizedpublicmetadata/aggregate; referencedprivatebytesnottransferred'
 if index:
  old=json.loads(lzma.decompress((OLD/(name+'.json.xz')).read_bytes()))['document'];delta={}
  for k,v in d.items():
   if k=='exports' and isinstance(v,list):
    fingerprints={json.dumps(x,sort_keys=True) for x in old.get(k,[])};new=[x for x in v if json.dumps(x,sort_keys=True) not in fingerprints]
    if new:delta[k]=new
   elif v!=old.get(k):delta[k]=v
  d={'delta_from_retained_index':str((OLD/(name+'.json.xz')).relative_to(O.parent.parent.parent)), 'changed_or_new_root_keys':delta,'new_exports_count':len(delta.get('exports',[]))};projection+='; exactstructuraldeltaagainstretainedoldindex,nooutcome-basedfilter'
 e=dict(source={k:row[k] for k in ['repository','ref','path','decoded_bytes','decoded_SHA256','git_blob_SHA','observed_UTC']},retention=projection,document=d);dest=O/(name+'.json.xz');dest.write_bytes(lzma.compress((json.dumps(e,separators=(',',':'))+'\n').encode(),preset=9));row.update(retained=dest.name,retained_bytes=dest.stat().st_size,retained_SHA256=hashlib.sha256(dest.read_bytes()).hexdigest());write(lp,ledger)
 assert sum(p.stat().st_size for p in O.rglob('*') if p.is_file())<RETAIN
 return d
if __name__=='__main__':
 for n,repo,ref in [('A_INDEX','NickNicky19/NFL-forecasting','f37279a093fcdddece1e369d42ce54349cb1913c'),('B_INDEX','NickNicky19/NFL-forecasting-V2','948cb4c5d7a9431e079caac5d345c23602603e43')]:
  d=fetch(repo,ref,'reports/abc-championship/EXPORT_INDEX.json',n,True);print(n,list(d['changed_or_new_root_keys']),d['new_exports_count'])
