"""Bounded owner-export read-only intake; no private rows or models."""
import json,gzip,lzma,base64,subprocess,hashlib,datetime,re
from pathlib import Path
OUT=Path(__file__).resolve().parent
CAP=4194304; SINGLE=2097152; GETS=8

def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def write(p,d):p.write_text(json.dumps(d,indent=2)+'\n')
def fetch(repo,ref,path,name):
 lp=OUT/'FETCH_LEDGER.json';rows=json.loads(lp.read_text()) if lp.exists() else []
 assert len(rows)<GETS
 used=sum(r.get('response_bytes_read',0) for r in rows);remaining=CAP-used;limit=min(SINGLE,remaining);assert limit>0
 r={'repository':repo,'ref':ref,'path':path,'started_UTC':now(),'state':'REQUEST_REGISTERED','response_limit':limit,'prior_response_bytes':used};rows.append(r);write(lp,rows)
 route=f'repos/{repo}/contents/{path}?ref={ref}'
 process=subprocess.Popen(['gh','api',route],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 b=process.stdout.read(limit+1)
 if len(b)>limit:
  process.terminate();r.update(state='STOPPED_RESPONSE_CAP',response_bytes_read=len(b),complete_response_unknown=True,observed_UTC=now());write(lp,rows);raise RuntimeError('BOUND_RESPONSE_CAP')
 err=process.stderr.read(2048);rc=process.wait();r.update(response_bytes_read=len(b),response_SHA256=hashlib.sha256(b).hexdigest(),observed_UTC=now(),returncode=rc)
 if rc:
  r.update(state='ROUTE_FAILED',error=err.decode(errors='replace')[:500]);write(lp,rows);raise RuntimeError('ROUTE_FAILED')
 raw=json.loads(b);assert raw.get('encoding')=='base64' and 'content' in raw
 decoded=base64.b64decode(raw['content']);r.update(state='RECEIVED',decoded_bytes=len(decoded),decoded_SHA256=hashlib.sha256(decoded).hexdigest(),Git_blob_SHA=raw.get('sha'))
 # Retain a source-bound metadata projection. Private/credential/local locators
 # are not republished merely because an owner index contains them.
 payload=gzip.decompress(decoded) if path.endswith('.json.gz') else decoded
 assert len(payload)<=4194304,'DECODED_MEMBER_CAP'
 r['member_decoded_bytes']=len(payload);r['member_decoded_SHA256']=hashlib.sha256(payload).hexdigest()
 d=json.loads(payload) if path.endswith(('.json','.json.gz')) else payload.decode()
 removed=[]
 def sanitize(v,key=''):
  if isinstance(v,dict):
   out={}
   for k,x in v.items():
    if any(w in k.lower() for w in ['credential','secret','private_locator','access_token']):removed.append(k);continue
    out[k]=sanitize(x,k)
   return out
  if isinstance(v,list):return [sanitize(x,key) for x in v]
  if isinstance(v,str):
   if re.search(r'https?://[^\s"\']*(?:drive\.google|dropbox|s3\.|storage\.google)',v,re.I) or re.match(r'^/(?:mnt|home|workspace|tmp)/',v):removed.append(key);return '<OWNER_LOCAL_OR_RESTRICTED_LOCATOR_NOT_RETAINED>'
  return v
 projected=sanitize(d)
 meta={'source':{k:r[k] for k in ['repository','ref','path','decoded_bytes','decoded_SHA256','Git_blob_SHA','observed_UTC']},'retention':'Publishedderivedexportmetadata;private/local locators omitted;no rights asserted for referenced private rows/models','redacted_field_count':len(removed),'document':projected}
 dest=OUT/(name+'.json.xz');packed=lzma.compress((json.dumps(meta,separators=(',',':'))+'\n').encode(),preset=9);assert sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file())+len(packed)+4096<=163840,'RETENTION_PREFLIGHT_CAP';dest.write_bytes(packed);r.update(retained=str(dest.relative_to(OUT)),retained_bytes=dest.stat().st_size,retained_SHA256=hashlib.sha256(dest.read_bytes()).hexdigest(),redacted_field_count=len(removed));write(lp,rows)
 assert sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file())<=163840
 return projected

if __name__=='__main__':
 for name,repo,ref in [('A_INDEX','NickNicky19/NFL-forecasting','1511d1c03a7bf0e7a139d38b602daf68620dbf29'),('B_INDEX','NickNicky19/NFL-forecasting-V2','05032e19e30b1f890a6b2679c70d3c97f0bbb2a1')]:
  d=fetch(repo,ref,'reports/abc-championship/EXPORT_INDEX.json',name);print(name,list(d)[:30])
