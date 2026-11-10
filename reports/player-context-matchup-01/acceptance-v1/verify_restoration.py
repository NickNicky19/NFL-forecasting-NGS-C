import urllib.request,hashlib,json,zipfile,io,gzip,datetime,pathlib
root=pathlib.Path(__file__).resolve().parents[3];out=pathlib.Path(__file__).resolve().parent;pin='fa503c1e1a9993e655a905195ce428edf630add5'
import argparse
parser=argparse.ArgumentParser();parser.add_argument('--receipt',type=pathlib.Path,required=True);args=parser.parse_args();assert not args.receipt.exists()
paths=['artifacts/basic-football-facts-v2.1.zip','artifacts/player-context-matchup-01/v1.1/2026-W01-P1.json.gz','artifacts/player-context-matchup-01/v1.1/2026-W01-P2.json.gz','artifacts/player-context-matchup-01/v1.1/2026-W02-E3.json.gz'];rows=[];facts=None
for p in paths:
 with urllib.request.urlopen('https://raw.githubusercontent.com/NickNicky19/NFL-forecasting-NGS-C/'+pin+'/'+p,timeout=40) as f:b=f.read(2097153);assert len(b)<=2097152;date=f.headers.get('Date')
 h=hashlib.sha256(b).hexdigest();assert h==hashlib.sha256((root/p).read_bytes()).hexdigest();r={'path':p,'bytes':len(b),'SHA256':h,'HTTP_Date':date,'observed_UTC':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 if p.endswith('.zip'):
  z=zipfile.ZipFile(io.BytesIO(b));names=z.namelist();assert all(not n.startswith('/') and '..' not in pathlib.PurePosixPath(n).parts for n in names)
  checked=[]
  for n in names:
   info=z.getinfo(n);assert info.file_size<8*1024*1024
   v=z.read(n);s=hashlib.sha256(v).hexdigest();checked.append({'member':n,'bytes':len(v),'SHA256':s})
   if n.endswith('facts.csv.gz'):assert s=='9abc681265b6bec413de2d9002aa72ac19b1a48ea2e57d4f38698b1cc8717a11';facts=s
  r['members']=checked;r['zip_integrity']='PASS'
 else:
  m=json.loads(gzip.decompress(b));assert isinstance(m['model'],dict) and m.get('training_fingerprint');r['training_fingerprint']=m['training_fingerprint']
 rows.append(r)
assert facts
result={'id':'C-ACCEPTANCE-FRESH-SOURCE-MODEL-BYTES-v1','pin':pin,'requests':4,'bytes':sum(r['bytes'] for r in rows),'files':rows,'clean_fetch_process':True,'disk_or_unsafe_model_loading':False,'fresh_fit_receipt':'FIT_REPRODUCTION_FINAL.json','scope':'Fresh source/model bytes verified against exactlocal inputs/models used in independentfit reproduction;new clean isolatedcontainerfit not claimed','new_fits':0}
args.receipt.write_text(json.dumps(result,indent=2)+'\n');print('FRESH_SAFE_SOURCE_AND_3MODEL_HASHES_PASS',result['bytes'])
