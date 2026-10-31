"""Compare freshly GitHub-restored original C0 points against new saved laws."""
import argparse,gzip,json,zipfile
from pathlib import Path
import numpy as np,pandas as pd
def compare(run,archive,output):
 old=pd.DataFrame(json.loads(gzip.decompress(zipfile.ZipFile(archive).read('rows.json.gz'))));old=old[old.season==2026];new=[]
 for p in run.glob('*/rows.json.gz'):
  rows=json.loads(gzip.decompress(p.read_bytes()))
  if rows and rows[0]['family']=='P2_LEAF' and rows[0]['history']=='H-MULTI' and rows[0]['arm']=='E0_BASE':new+=rows
 new=pd.DataFrame(new);out=[]
 for t,q in old.groupby('target'):
  n=new[new.target==t];p=q.merge(n,on=['target','week','game_id','player_id','position'],suffixes=('_old','_new'),validate='one_to_one');assert len(p)==len(q)
  mismatch=~(p.actual_old.fillna(-99999)==p.actual_new.fillna(-99999));assert not mismatch.any()
  for role in ['ALL']+sorted(p.position.unique()):
   z=p if role=='ALL' else p[p.position==role];s=z[z.actual_old.notna()].copy();s['delta']=(s['median']-s.actual_new).abs()-(s.point-s.actual_old).abs();b=(s.point-s.actual_old).abs().mean();c=(s['median']-s.actual_new).abs().mean();v=dict(target=t,role=role,C0_queries=len(z),matched_queries=len(z),outcomes=len(s),label_disagreements=0,old_C0_mae=float(b),new_P2_BASE_mae=float(c),change=float(c-b),relative_change=float((c-b)/b),comparison='C_OWN_FROZEN_HGB_VS_NEW_LEAF; NOT_A_OR_B_REPRODUCTION')
   for key in ['game_id','week']:
    g=s.groupby(key).delta.agg(['sum','count']);rng=np.random.default_rng(1701);i=rng.integers(0,len(g),(500,len(g)));a=g['sum'].to_numpy()[i].sum(axis=1)/g['count'].to_numpy()[i].sum(axis=1);v[key+'_ci95']=list(map(float,np.quantile(a,[.025,.975])))
   out.append(v)
 output.write_text(json.dumps(out,indent=2));print('C0_EXACT_INTERNAL_MATCHES',len(out))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--archive',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();compare(a.run,a.archive,a.output)
