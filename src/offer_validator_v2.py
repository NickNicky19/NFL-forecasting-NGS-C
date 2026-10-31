"""Bounded local schema validator, not a collector or rights/admission grant."""
import argparse,json,math,hashlib,sys
from datetime import datetime,timezone
from contracts_v2 import CATEGORIES
def instant(value):
 if not isinstance(value,str):raise ValueError('missing clock')
 d=datetime.fromisoformat(value.replace('Z','+00:00'))
 if d.tzinfo is None:raise ValueError('naive clock')
 return d.astimezone(timezone.utc)
def validate(payload):
 if not isinstance(payload,dict) or not isinstance(payload.get('offers'),list):raise ValueError('offers list required')
 errors=[];seen={};events={}
 for i,o in enumerate(payload['offers']):
  try:
   for k in ['offer_id','venue','product','native_player_id','native_event_id','player_id','game_id','category','period','comparator','offered_sides','lifecycle','source_evidence_reference']:
    if k not in o or o[k] is None:raise ValueError('missing '+k)
   if o['category'] not in CATEGORIES:raise ValueError('unknown category')
   if o['lifecycle']!='OPEN':raise ValueError('offer not OPEN; suspended sides cannot be accepted')
   sides=o['offered_sides']
   allowed={'YES'} if o['category']=='anytime_td' else {'OVER','UNDER'}
   if not isinstance(sides,list) or not sides or any(not isinstance(s,str) or s not in allowed for s in sides) or len(set(sides))!=len(sides):raise ValueError('offered_sides must be a nonempty unique list of actual side enums')
   side_states=o.get('side_states')
   if side_states is not None and (not isinstance(side_states,dict) or set(side_states)!=set(sides) or any(v!='OPEN' for v in side_states.values())):raise ValueError('per-side lifecycle unresolved, suspended or conflicting')
   if not isinstance(o['line'],(int,float)) or isinstance(o['line'],bool) or not math.isfinite(o['line']):raise ValueError('invalid line')
   if o['category']=='fpts' and o.get('scoring_contract_id')!='nick-chart-ppr-v1':raise ValueError('fantasy contract mismatch')
   if o['category']=='anytime_td' and any(x not in ['YES'] for x in o['offered_sides']):raise ValueError('NO/Under side lacks separate qualified contract')
   observed=instant(o['observed_at_UTC']);persisted=instant(o['persisted_at_UTC'])
   if persisted<observed:raise ValueError('persistence before observation')
   key=(o['venue'],o['product'],o['offer_id']);body=json.dumps(o,sort_keys=True)
   if key in seen and seen[key]!=body:raise ValueError('conflicting offer lifecycle/quote records')
   seen[key]=body;e=(o['venue'],o['native_event_id'])
   if e in events and events[e]!=o['game_id']:raise ValueError('conflicting event IDs')
   events[e]=o['game_id']
  except (ValueError,KeyError,TypeError) as e:errors.append(dict(index=i,reason=str(e)))
 return dict(state='REJECTED' if errors else 'SCHEMA_VALID_NOT_RIGHTS_OR_SETTLEMENT_QUALIFIED',rows=len(payload['offers']),errors=errors,live_access_verified=False,settlement_verified=False)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('path');p.add_argument('--expected-sha256');a=p.parse_args()
 try:
  b=open(a.path,'rb').read()
  if a.expected_sha256 and hashlib.sha256(b).hexdigest()!=a.expected_sha256:raise ValueError('archive/payload checksum mismatch')
  result=validate(json.loads(b));print(json.dumps(result));sys.exit(1 if result['errors'] else 0)
 except (ValueError,OSError) as e:print(json.dumps({'state':'REJECTED','reason':str(e)}));sys.exit(1)
