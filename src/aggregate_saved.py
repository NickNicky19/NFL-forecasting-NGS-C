"""Rebuild numerical summaries from saved rows into a NEW output directory.

This performs no fitting, inference, acquisition or capture.
"""
import argparse,gzip,json
from pathlib import Path
import pandas as pd
from study import score

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--runs',nargs='+',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 rows=[]
 for run in a.runs:
  for f in sorted(run.glob('*.json.gz')):
   with gzip.open(f,'rt') as h:rows.extend(json.load(h))
 r=pd.DataFrame(rows)
 if r.duplicated(['season','week','target','arm','game_id','player_id']).any():raise ValueError('duplicate queries; do not pool reruns')
 a.output.mkdir(parents=True,exist_ok=False);score(r,a.output)
 print(json.dumps(dict(fits=0,inference=0,rows=len(r),output='new supplied output directory')))
