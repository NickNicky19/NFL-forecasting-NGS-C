"""Fail-closed paper-entry eligibility. No bookmaker execution or collection."""
import math
from offer_validator_v2 import instant
def qualify(offers,quote,cutoff):
 reasons=[]
 if not quote:reasons.append('NO_EXACT_ENTRY_QUOTE')
 else:
  for k in ['venue','product','entry_type','payout_table','quoted_at_UTC','combination_rules','void_rules']:
   if not quote.get(k):reasons.append('MISSING_'+k.upper())
 eligible=[];seen=set()
 for o in offers:
  required=['offer_id','venue','product','player_id','game_id','category','line','side','observed_at_UTC','persisted_at_UTC','settlement_contract','rights_status']
  if any(o.get(k) is None for k in required) or o.get('rights_status')!='PUBLIC_RETENTION_QUALIFIED':continue
  try:
   if o.get('lifecycle')!='OPEN' or instant(o['observed_at_UTC'])>instant(cutoff) or instant(o['persisted_at_UTC'])>instant(cutoff):continue
  except (ValueError,TypeError):continue
  if o['side'] not in o.get('offered_sides',[]):continue
  if quote and (o['venue'],o['product'])!=(quote['venue'],quote['product']):continue
  if not isinstance(o.get('p_win'),(int,float)) or not 0<=o['p_win']<=1:continue
  key=(o['venue'],o['product'],o['offer_id'])
  if key in seen:continue
  seen.add(key);eligible.append(o)
 if len(eligible)<6:reasons.append('FEWER_THAN_SIX_QUALIFIED_LEGS')
 return dict(state='NO_QUALIFIED_SIX_LEG_ENTRY' if reasons else 'REQUIRES_COMBINATION_RULE_VALIDATION',eligible_candidates=len(eligible),reasons=sorted(set(reasons)),selected=[],entries=0)
def independent_all_win(probabilities):
 if len(probabilities)!=6 or any(not 0<=p<=1 for p in probabilities):raise ValueError('sixvalidmarginalsrequired')
 return math.prod(probabilities)
def overlap(first,second):
 a,b=set(first),set(second);return dict(shared_legs=len(a&b),unique_legs=len(a|b),independence_assumed=False)
