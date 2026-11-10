from fetch_delta import O,CAP,SINGLE,GETS,now,write,RETAIN
import subprocess,json,hashlib,lzma

def get(repo,name):
 lp=O/'FETCH_LEDGER.json';ledger=json.loads(lp.read_text());assert len(ledger)<GETS;bound=min(SINGLE,CAP-sum(r.get('response_bytes',0) for r in ledger));assert bound>0
 route=f'repos/{repo}/pulls?state=open&per_page=10&sort=updated&direction=desc';row=dict(repository=repo,route=route,started_UTC=now(),state='ATTEMPT_REGISTERED',max_response=bound);ledger.append(row);write(lp,ledger)
 p=subprocess.Popen(['gh','api',route],stdout=subprocess.PIPE,stderr=subprocess.PIPE);b=p.stdout.read(bound+1)
 if len(b)>bound:p.terminate();row.update(state='CAP_FAILURE',response_bytes=len(b));write(lp,ledger);raise RuntimeError('CAP')
 err=p.stderr.read(1024);rc=p.wait();row.update(returncode=rc,response_bytes=len(b),response_SHA256=hashlib.sha256(b).hexdigest(),observed_UTC=now())
 if rc:row.update(state='FAILED',error=err.decode(errors='replace')[:300]);write(lp,ledger);raise RuntimeError('GET_FAILED')
 rows=json.loads(b);project=[{k:r.get(k) for k in ['number','title','state','draft','created_at','updated_at','html_url']}|{'head':{k:r['head'].get(k) for k in ['ref','sha']},'base':{k:r['base'].get(k) for k in ['ref','sha']}} for r in rows]
 out=O/(name+'.json.xz');out.write_bytes(lzma.compress((json.dumps(dict(source=row,projection='PublicopenPRidentityonly;noPRbody/comments/secrets/peerwrites',records=project),separators=(',',':'))+'\n').encode(),preset=9));row.update(state='RECEIVED_PUBLIC_PR_METADATA',retained=out.name,retained_bytes=out.stat().st_size,retained_SHA256=hashlib.sha256(out.read_bytes()).hexdigest());write(lp,ledger);assert sum(p.stat().st_size for p in O.rglob('*') if p.is_file())<RETAIN
 print(name,json.dumps(project,indent=2))
for repo,name in [('NickNicky19/NFL-forecasting','A_OPEN_PRS'),('NickNicky19/NFL-forecasting-V2','B_OPEN_PRS')]:get(repo,name)
