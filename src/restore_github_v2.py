"""Fresh GitHub archive readback, byte verification and actual model re-inference."""
import argparse,hashlib,json,gzip,pickle,zipfile,io,urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np
import laws_v2
def restore(entry,commit):
 url=f'https://raw.githubusercontent.com/NickNicky19/NFL-forecasting-NGS-C/{commit}/{entry["path"]}'
 b=urllib.request.urlopen(url,timeout=120).read();assert len(b)==entry['bytes'] and hashlib.sha256(b).hexdigest()==entry['sha256'];z=zipfile.ZipFile(io.BytesIO(b));assert z.testzip() is None
 models=[n for n in z.namelist() if n.endswith('/model.pkl.gz')];rowfiles=[n for n in z.namelist() if n.endswith('/rows.json.gz')];count=0;checks=[]
 for name in rowfiles:
  rows=json.loads(gzip.decompress(z.read(name)));count+=len(rows)
  if not rows or rows[0]['week']!=7 or rows[0]['arm']!='E0_OP' or rows[0]['history']!='H-MULTI':continue
  p=pickle.loads(gzip.decompress(z.read(name.replace('rows.json.gz','model.pkl.gz'))));x=np.array([r['features'] for r in rows],float);role=np.array([r['position'] for r in rows]);m=p['model']
  if rows[0]['family']=='P2_LEAF':pred=np.array([[law.probability(l)['over'] for l in rows[0]['grid']] for law in m.laws(x,role)])
  else:
   cp=m.cdfs(x,p['grid_floor']);pred=cp if p['kind']=='event' else 1-cp
  assert np.array_equal(pred,np.array([r['p_over'] for r in rows]))
  checks.append(dict(family=rows[0]['family'],queries=len(rows),probability_parity='BIT_EXACT'))
 return dict(category=entry['category'],sha256=entry['sha256'],bytes=len(b),models=len(models),row_files=len(rowfiles),forecast_views=count,zip_integrity='PASS',fresh_download=True,representative_inference=checks,new_fits=0)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--commit',required=True);p.add_argument('--manifest',type=Path,default=Path('reports/GITHUB_EVIDENCE_MANIFEST_V2.json'));p.add_argument('--receipt',type=Path,required=True);a=p.parse_args();entries=json.load(open(a.manifest))
 with ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(lambda e:restore(e,a.commit),entries))
 a.receipt.write_text(json.dumps(dict(commit=a.commit,archives=results,bytes=sum(r['bytes'] for r in results),forecast_views=sum(r['forecast_views'] for r in results),inference_queries=sum(c['queries'] for r in results for c in r['representative_inference']),new_fits=0),indent=2));print('ALL12_GITHUB_RESTORE_PASS',len(results),sum(r['forecast_views'] for r in results))
