"""Source/venue sensitivity views of saved canonical grades; no new grader."""
import gzip,json
from collections import defaultdict
from shared_game_sim01_budget import ROOT,D
from shared_game_sim01_metrics import _summarize,_pair
from shared_game_sim01_report import enrich

def main():
 p=ROOT/'private/shared-game-sim-01';raw=json.loads(gzip.decompress((p/'raw_grades.json.gz').read_bytes()))
 bench={r['case_id']:r['point_source'] for r in map(json.loads,(p/'views/comparison_inputs/benchmarks.jsonl').read_bytes().splitlines())}
 groups=defaultdict(list)
 for r in raw:groups[r['method'],r['category'],r['venue'],bench[r['case_id']]].append(r)
 summaries=[];pairs=[]
 for (m,c,v,src),rr in sorted(groups.items()):
  summaries.append(dict(method=m,category=c,venue=v,case_point_source=src,**enrich(_summarize(rr),rr)))
  if not m.startswith('C'):continue
  for control in ('W0','W1','ALWAYS_OVER','ALWAYS_UNDER'):
   cc=groups.get((control,c,v,src),[])
   pairs.append(dict(candidate=m,control=control,category=c,venue=v,case_point_source=src,**_pair(rr,cc)))
 out=dict(scope='Same admitted full frame/source composition; no book/threshold selection by outcomes. All lineclasses unclassified and quote/issue clocks unknown. Raw source=model/average separate from each method learned/fallback attribution.',summaries=summaries,paired=pairs)
 body=(json.dumps(out,indent=2,allow_nan=False)+'\n').encode();(D/'SOURCE_STRATA.json.gz').write_bytes(gzip.compress(body,mtime=0))
 print('SOURCE_VENUE_STRATA_VIEWS_COMPLETE',len(summaries),len(pairs))
if __name__=='__main__':main()
