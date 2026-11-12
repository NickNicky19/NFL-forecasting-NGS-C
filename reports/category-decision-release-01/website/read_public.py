import json,subprocess,hashlib,lzma,datetime,sys,re
from pathlib import Path
ROOT=Path('/workspace/ngs-c/reports/category-decision-release-01/website')
ledger=ROOT/'REQUESTS.json'
def read(route,name):
 rows=json.loads(ledger.read_text()) if ledger.exists() else []
 assert len(rows)<14
 p=subprocess.run(['gh','api',route],capture_output=True)
 b=p.stdout or p.stderr
 item=dict(request=len(rows)+1,route=route,observed_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),exit_code=p.returncode,response_bytes=len(b),response_SHA256=hashlib.sha256(b).hexdigest())
 assert len(b)<=2097152 and sum(x['response_bytes'] for x in rows)+len(b)<=4194304
 rows.append(item);ledger.write_text(json.dumps(rows,indent=2)+'\n')
 if p.returncode:print(json.dumps(item));print(b.decode(errors='replace')[:600]);return
 j=json.loads(b)
 # Keep approved public GitHub metadata, never external private locators/tokens.
 s=json.dumps(j,ensure_ascii=False)
 s=re.sub(r'https?://(?!github\.com|api\.github\.com|raw\.githubusercontent\.com|nicknicky19\.github\.io)[^\s"<>]+','[EXTERNAL_LOCATOR_REDACTED]',s)
 s=re.sub(r'(?:gh[pousr]_[A-Za-z0-9_]+|github_pat_[A-Za-z0-9_]+)','[TOKEN_REDACTED]',s)
 out=(s+'\n').encode();(ROOT/(name+'.json.xz')).write_bytes(lzma.compress(out))
 print(json.dumps(item));v=json.loads(s);v=([x for x in v['tree'] if any(t in x['path'].lower() for t in ['research','contract','consumer','selector','overlay','count-a','count_a','registration']) or x['path'] in ['index.html','data/latest.json','data/top-picks.json']] if isinstance(v,dict) and 'tree' in v else v);print(json.dumps(v,indent=2,ensure_ascii=False)[:18000])
if __name__=='__main__':read(sys.argv[1],sys.argv[2])
