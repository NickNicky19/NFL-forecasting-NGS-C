"""Versioned numerical log-score correction; no refits or forecast changes."""
import argparse,gzip,json,pickle,math,hashlib
from pathlib import Path
import numpy as np
from threadpoolctl import threadpool_limits
from laws_v2 import Law
def correct(root,receipt):
 counts=dict(slots=0,rows=0,true_infinities_retained=0,false_infinities_corrected=0,max_finite_difference=0.,fits=0,forecast_values_changed=0)
 for done in sorted(root.glob('*/DONE.json')):
  d=done.parent;a=json.load(open(d/'ATTEMPT.json'))
  if a['family']!='P2_LEAF' or a.get('score_version')=='ANALYTIC_LOGPMF_V1':continue
  output=d/'NLL_ANALYTIC_V1.json.gz'
  if output.exists():continue
  rows=json.loads(gzip.decompress((d/'rows.json.gz').read_bytes()));p=pickle.loads(gzip.decompress((d/'model.pkl.gz').read_bytes()));x=np.asarray([r['features'] for r in rows],float);roles=np.asarray([r['position'] for r in rows])
  with threadpool_limits(limits=1):laws=p['model'].laws(x,roles) if p['model'] else [Law([],[],p['prior'].get(role,p['global_prior']),p['scale']) for role in roles]
  values=[]
  for r,law in zip(rows,laws):
   if r['actual'] is None:values.append(None);continue
   new=-law.logpmf(int(round(r['actual']*p['scale'])));old=float(r['nll']);counts['rows']+=1
   if math.isinf(new):counts['true_infinities_retained']+=1
   elif math.isinf(old):counts['false_infinities_corrected']+=1
   else:counts['max_finite_difference']=max(counts['max_finite_difference'],abs(old-new))
   values.append('Infinity' if math.isinf(new) else new)
  with gzip.open(output,'wt') as f:json.dump(dict(version='ANALYTIC_LOGPMF_V1',original_rows_sha256=hashlib.sha256((d/'rows.json.gz').read_bytes()).hexdigest(),nll=values),f,allow_nan=False)
  counts['slots']+=1
 receipt.parent.mkdir(parents=True,exist_ok=True);receipt.write_text(json.dumps(counts,indent=2));print(counts)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--receipt',type=Path,required=True);a=p.parse_args();correct(a.root,a.receipt)
