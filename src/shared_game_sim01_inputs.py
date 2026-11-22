"""Closed S-P loader plus separately bound identity-only enrichment.

No starter ZIP, comparison fields, grading fields, actual source participation,
or outcomes are opened here. Team LAR->LA is a registered namespace alias only.
"""
from __future__ import annotations
import datetime,hashlib,json
from pathlib import Path

SP_SHA='b24d08193d95bdea509bd20ece6ebf66fd29da49d144c213369e493eace11bf1'
FORBIDDEN={'actual','outcome','result','grade','label','correct','win','loss','line','venue','book','price','saved_lean','saved_adjusted_point','provider_first_point','target_stats','final_score','score','actual_participation','eventual_participant'}
def utc(x):
 return datetime.datetime.fromisoformat(x.replace('Z','+00:00')).timestamp()
def iso(t):return datetime.datetime.fromtimestamp(t,datetime.timezone.utc).isoformat().replace('+00:00','Z')
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def canonical_team(x):return {'LAR':'LA'}.get(x,x)
def _check(x):
 if isinstance(x,dict):
  if set(x)&FORBIDDEN:raise ValueError('PROHIBITED_QUERY_FIELD')
  for v in x.values():_check(v)
 elif isinstance(x,list):
  for v in x:_check(v)
def load_closed(root):
 root=Path(root)
 if root.is_symlink() or {p.name for p in root.iterdir()}!={'players_sp.jsonl','games_sp.jsonl','manifest.json'}:raise ValueError('CLOSED_SP_DIRECTORY')
 b=(root/'manifest.json').read_bytes()
 if hashlib.sha256(b).hexdigest()!=SP_SHA:raise ValueError('CLOSED_SP_EXTERNAL_FREEZE')
 m=json.loads(b);out={}
 for name,info in m['files'].items():
  if name not in ('players_sp.jsonl','games_sp.jsonl'):raise ValueError('UNREGISTERED_SP_FILE')
  p=root/name;b=p.read_bytes()
  if p.is_symlink() or p.resolve().parent!=root.resolve() or len(b)!=info['bytes'] or hashlib.sha256(b).hexdigest()!=info['sha256']:raise ValueError('SP_BODY_BINDING')
  rows=[json.loads(s) for s in b.splitlines()];_check(rows);out[name]=rows
 return out
def load_context(private):
 private=Path(private);docs=load_closed(private/'views/forecast_worker')
 original=json.loads((private/'mapped_players.json').read_text())
 # Mapping was independently rebuilt from admitted identity metadata. Discard
 # duplicate provider fields: the actual anchors come ONLY from closed bytes.
 keys=('player_game_key','identity_available','identity_reason','gsis_id','native_game_id','native_kickoff_utc','model_cutoff_utc')
 mapping={p['player_game_key']:{k:p[k] for k in keys if k in p} for p in original}
 players=[]
 for p in docs['players_sp.jsonl']:
  q=dict(p);q['team']=canonical_team(q['team']);q['opponent']=canonical_team(q['opponent']);q.update(mapping[q['player_game_key']]);players.append(q)
 games=[]
 for g in docs['games_sp.jsonl']:
  q=dict(g);q['home']=canonical_team(q['home']);q['away']=canonical_team(q['away'])
  pp=[p for p in players if p['game_origin_key']==q['game_origin_key']]
  available=[p for p in pp if p['identity_available']]
  ids={(p['native_game_id'],p['native_kickoff_utc'],p['model_cutoff_utc']) for p in available}
  if len(ids)!=1:raise ValueError('UNAMBIGUOUS_NATIVE_GAME_REQUIRED')
  ng,nk,nc=next(iter(ids));q.update(native_game_id=ng,native_kickoff_utc=nk,native_cutoff_utc=nc,
   source_schedule_cutoff_utc=iso(utc(q['kickoff_utc'])-5400),model_cutoff_utc=iso(min(utc(nc),utc(q['kickoff_utc'])-5400)))
  games.append(q)
 return sorted(games,key=lambda q:(utc(q['model_cutoff_utc']),q['native_game_id'])),players
