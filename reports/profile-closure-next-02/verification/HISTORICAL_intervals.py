"""Representative registered game-cluster interval recalculation, independent grades."""
import collections,datetime,hashlib,json,lzma,math,resource,time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).parent;start=time.process_time()
def read(p):return json.loads(lzma.decompress((ROOT/p).read_bytes()))
rows=read('artifacts/receiving-timing-c04/ACTUAL_OFFER_ROWS.json.xz');pairs=read('reports/profile-closure-next-02/timing/PAIRED_CHANGES.json.xz');results=[]
def win(r):
 assert r['appearance']=='PLAYED'and r['actual']is not None and r['actual']!=r['line']
 return int((r['selected_side']=='OVER')==(r['actual']>r['line']))
for candidate,control in [('F2_LAW','F0_LAW'),('F3_LAW','F1_LAW'),('F3_LAW','F2_LAW')]:
 a={r['offer_id']:r for r in rows if r['method']==candidate and r['position']in['WR','TE']};b={r['offer_id']:r for r in rows if r['method']==control and r['position']in['WR','TE']}
 ids=sorted(i for i in a.keys()&b.keys()if a[i]['appearance']=='PLAYED'and a[i]['actual']is not None and a[i]['actual']!=a[i]['line']and b[i]['appearance']=='PLAYED'and b[i]['actual']is not None and b[i]['actual']!=b[i]['line'])
 groups=collections.OrderedDict()
 for i in ids:
  for k in ['game_id','player_id','line','actual','appearance']:assert a[i][k]==b[i][k]
  block=groups.setdefault(a[i]['game_id'],[0,0]);block[0]+=win(a[i])-win(b[i]);block[1]+=1
 blocks=np.asarray(list(groups.values()),dtype=float);rng=np.random.default_rng(661107);indices=rng.integers(len(blocks),size=(2000,len(blocks)));draws=blocks[indices].sum(axis=1);interval=(100*np.quantile(draws[:,0]/draws[:,1],[.025,.975])).tolist()
 saved=next(r for r in pairs if r['scope']=='WR_TE'and r['cohort']=='ALL'and r['candidate']==candidate and r['control']==control)
 assert all(math.isclose(a,b,abs_tol=1e-12)for a,b in zip(interval,saved['game_id_sensitivity95_pp']))
 results.append(dict(candidate=candidate,control=control,eligible_decided=len(ids),independent_games=len(groups),own_win_change=sum(win(a[i])-win(b[i])for i in ids),independently_recomputed95_pp=interval,reported95_pp=saved['game_id_sensitivity95_pp'],interpretation='Gameclusterresamplingamongtwoexposedweeks;notfutureguarantee,notindependentNFLseasons'))
report=dict(id='C04-INDEPENDENT-GAME-INTERVAL-CHECK-v1',status='PASS',checked_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),comparisons=results,resamples=2000,seed=661107,calculation='Independentlyregradedrowwins/groupedopportunities,registeredratio-of-sumsresampling; noauthorsummarycall',CPU_seconds=time.process_time()-start,peak_RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,new_fits=0,GETs=0,new_NFL_observations=0)
(OUT/'HISTORICAL_INTERVAL_REVIEW.json').write_text(json.dumps(report,indent=2)+'\n');print('REPRESENTATIVE_GAME_INTERVALS_PASS',len(results),report['CPU_seconds'])
