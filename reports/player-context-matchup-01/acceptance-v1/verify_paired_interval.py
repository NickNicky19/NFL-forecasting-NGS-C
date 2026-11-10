"""Separate paired game-block calculation; no summary/scorer invocation."""
import json,gzip,collections
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3]
read=lambda p:json.loads(gzip.decompress((ROOT/p).read_bytes()))
rs=read('artifacts/player-context-matchup-01/CANONICAL_REPORT_ROWS.json.gz');maps={m:{r['offer_id']:r for r in rs if r['method']==m and r['position'] in ['WR','TE']} for m in ['P1','P2']};ids=sorted(set(maps['P1'])&set(maps['P2']));blocks=collections.OrderedDict();w={m:0 for m in maps};n=0
for oid in ids:
 a,b=maps['P2'][oid],maps['P1'][oid]
 assert all(a[k]==b[k] for k in ['game_id','player_id','line','actual','appearance'])
 if a['appearance']!='PLAYED' or a['actual'] is None or a['actual']==a['line']:continue
 wins={m:int((maps[m][oid]['actual']>maps[m][oid]['line'])==(maps[m][oid]['selected_side']=='OVER')) for m in maps}
 for m in w:w[m]+=wins[m]
 v=blocks.setdefault(a['game_id'],[0,0]);v[0]+=wins['P2']-wins['P1'];v[1]+=1;n+=1
arr=np.array(list(blocks.values()));rng=np.random.default_rng(661107);sample=arr[rng.integers(len(arr),size=(2000,len(arr)))].sum(axis=1);ci=np.quantile(sample[:,0]/sample[:,1],[.025,.975])*100
ret=next(r for r in read('reports/player-context-matchup-01/PAIRED_CHANGES.json.gz') if r['scope']=='WR_TE' and r['candidate']=='P2' and r['control']=='P1');assert np.allclose(ci,ret['game_cluster_sensitivity_pp'],rtol=0,atol=1e-12)
assert (w['P2'],w['P1'],n)==(150,149,255)
x={'state':'PASS','candidate_wins':w['P2'],'control_wins':w['P1'],'decided':n,'eligible_common':len(ids),'game_clusters':len(blocks),'week_clusters':2,'difference_pp':100/n,'sensitivity95_pp':ci.tolist(),'bootstrap_draws':2000,'seed':661107,'limits':'Two exposed week clusters; repeated players and multiple comparisons; not future-season confirmation or adjusted significance','author_scorer_called':False,'new_fits':0};p=Path(__file__).with_name('PAIRED_INTERVAL_REVIEW.json');assert not p.exists();p.write_text(json.dumps(x,indent=2)+'\n');print(x)
