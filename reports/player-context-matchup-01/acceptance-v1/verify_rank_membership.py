"""Independent list reconstruction from declared ranking contract, not choose()."""
import collections,csv,gzip,hashlib,io,json,zipfile
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
ROOT=Path(__file__).resolve().parents[3]
read=lambda p:json.loads(gzip.decompress((ROOT/p).read_bytes()))
rows=read('artifacts/player-context-matchup-01/CANONICAL_REPORT_ROWS.json.gz')
lists=read('reports/player-context-matchup-01/TOPK_RESULTS.json.gz');members=read('artifacts/player-context-matchup-01/TOPK_MEMBERSHIP.json.gz')
with zipfile.ZipFile(ROOT/'artifacts/basic-football-facts-v2.1.zip') as z:
 schedule=list(csv.DictReader(io.StringIO(z.read('schedule.csv').decode())))
kicks={r['game_id']:datetime.fromisoformat(r['gameday']+'T'+r['gametime']).replace(tzinfo=ZoneInfo('America/New_York')).astimezone(ZoneInfo('UTC')).isoformat() for r in schedule}
positions={'ALL_SUPPORTED':['RB','WR','TE'],'WR_TE':['WR','TE'],'RB':['RB'],'WR':['WR'],'TE':['TE']};bylist=collections.defaultdict(list)
for r in members:bylist[r['list_id']].append(r)
unknown=0
for l in lists:
 scope=l['scope'].removeprefix('WITHIN_REC_');candidates=[]
 for r in rows:
  if r['method']!=l['method'] or r['week']!=l['week'] or r['position'] not in positions[scope] or not r.get('probabilities') or r['selected_side'] not in ['OVER','UNDER']:continue
  if l['side']!='MIXED' and r['selected_side']!=l['side'].split('_')[0]:continue
  confidence=r['probabilities'][r['selected_side'].lower()];candidates.append((r,confidence))
 candidates.sort(key=lambda x:(-x[1],kicks[x[0]['game_id']],x[0]['game_id'],x[0]['player_id'],x[0]['category'],x[0]['offer_id']))
 selected=[];seen=set()
 for r,p in candidates:
  if r['player_id'] in seen:continue
  seen.add(r['player_id']);selected.append(r)
  if len(selected)==l['K']:break
 assert [r['offer_id'] for r in selected]==l['member_ids'],l['id']
 emitted=sorted(bylist[l['id']],key=lambda r:r['rank']);assert [r['offer_id'] for r in emitted]==l['member_ids']
 for r,m in zip(selected,emitted):assert r['status']==m['status'] and r['selected_side']==m['side']
 for side in ['OVER','UNDER','COMBINED']:
  q=[r for r in selected if side=='COMBINED' or r['selected_side']==side];w=loss=0
  for r in q:
   if r['appearance']!='PLAYED' or r['actual'] is None or r['actual']==r['line']:continue
   good=(r['actual']>r['line'])==(r['selected_side']=='OVER');w+=int(good);loss+=int(not good)
  a=l[side];assert (len(q),w,loss)==(a['selected'],a['wins'] or 0,a['losses'] or 0)
 unknown+=sum(r['status']=='UNKNOWN_PARTICIPATION' for r in selected)
 assert 'NO_SIMULTANEOUS_BOARD' in l['tier']
result={'state':'PASS','lists':len(lists),'membership_rows':len(members),'unknown_selected_views_retained':unknown,'side_partitions':len(lists)*3,'candidate_board_timing':'Timing-unverified end-of-week last-recorded lines;not simultaneous available slate','zero_new_NFL_outcomes':True,'new_fits':0,'author_choose_function_called':False,'no_six_leg_entry_or_payout_claim':True}
p=Path(__file__).with_name('RANK_MEMBERSHIP_REVIEW.json');assert not p.exists();p.write_text(json.dumps(result,indent=2)+'\n');print(result)
