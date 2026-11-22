"""Named pairwise research masks over existing frozen grades; no new forecasts."""
import gzip,json,math
from collections import defaultdict
from itertools import combinations
from shared_game_sim01_budget import ROOT,D
from shared_game_sim01_metrics import _pair
from shared_game_sim01_report import numeric_pair

def probability_pair(a,b):
 lookup={r['case_id']:r for r in b};pa=[];pb=[];la=[];lb=[];za=zb=0
 for r in a:
  q=lookup.get(r['case_id'])
  if q is None or r['actual'] is None or not r['available'] or not q['available'] or r['probabilities'] is None or q['probabilities'] is None:continue
  event='over' if r['actual']>r['line'] else 'under' if r['actual']<r['line'] else 'push'
  for row,bs,ls,which in [(r,pa,la,0),(q,pb,lb,1)]:
   p=row['probabilities'];bs.append(.5*sum((p[k]-(k==event))**2 for k in ('under','push','over')))
   if p[event]==0:
    if which:zb+=1
    else:za+=1
   else:ls.append(-math.log(p[event]))
 n=len(pa)
 return dict(n=n,first_Brier=sum(pa)/n if n else None,second_Brier=sum(pb)/n if n else None,Brier_difference=(sum(pa)-sum(pb))/n if n else None,first_log_loss='Infinity' if za else sum(la)/n if n else None,second_log_loss='Infinity' if zb else sum(lb)/n if n else None,scope='Same available known-outcome probability cases; raw zero log convention; descriptive point differences only')
def main():
 p=ROOT/'private/shared-game-sim-01';raw=json.loads(gzip.decompress((p/'raw_grades.json.gz').read_bytes()));groups=defaultdict(dict)
 for r in raw:
  if r['method'].startswith('C'):groups[r['category']].setdefault(r['method'],[]).append(r)
 pairs=[]
 for cat,methods in sorted(groups.items()):
  for a,b in combinations(sorted(methods),2):
   x,y=methods[a],methods[b]
   pairs.append(dict(category=cat,first=a,second=b,paired_direction=_pair(x,y),same_case_numerical=numeric_pair(x,y),same_case_probability=probability_pair(x,y)))
 body=(json.dumps(dict(scope='Frozen C nominees only; pairwise masks, not a total leaderboard; all exposed development. A/B owned same-frame grades remain pending.',pairs=pairs),indent=2,allow_nan=False)+'\n').encode();(D/'RESEARCH_PAIRS.json.gz').write_bytes(gzip.compress(body,mtime=0));print('NAMED_RESEARCH_PAIRS',len(pairs))
if __name__=='__main__':main()
