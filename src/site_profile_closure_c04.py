"""Deterministic C04 site projection. No fits, grading, ranking or acquisition."""
from __future__ import annotations
import argparse, hashlib, json, lzma, re
from pathlib import Path
from datetime import datetime
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'reports/profile-closure-next-02'
EXP=BASE/'timing'
SCHEMA='C04-PROFILE-CLOSURE-RESEARCH-v1'
LABELS={'F0':'F0 · seven-day support baseline','F1':'F1 · seven-day player profile','F2':'F2 · one-day support baseline','F3':'F3 · one-day player profile','P1':'Retained C pooled context law','P2':'Retained C partial-pooling law','E0':'Retained C direct control','ALWAYS_OVER':'Always-Over control','ALWAYS_UNDER':'Always-Under control','RETAINED_EARLIER_PREVALENCE_V8':'Earlier role prevalence control','CONTROL_LEAF':'Retained unchanged C Leaf','CONTROL_CONTEXT_P1':'Retained C pooled point control','CONTROL_CONTEXT_P2':'Retained C partial-pooling point control'}
MODELS={'C_V4_RETAINED_REFERENCE_OBSERVED':'C reference · observed current history','C_V11_P1_E2_POOLED_7D':'C pooled reference · seven-day history','C04_F3_PROFILE_1D_SHADOW':'C04 F3 shadow · one-day profile'}
CONTRASTS=[('F1','F0'),('F2','F0'),('F3','F2'),('F3','F1')]

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
 p=Path(p);b=p.read_bytes();return json.loads(lzma.decompress(b) if p.suffix=='.xz' else b)
def stamp(s):
 d=datetime.fromisoformat(s.replace('Z','+00:00'))
 if d.tzinfo is None:raise ValueError('CLOCK_MUST_HAVE_TIMEZONE')
 return d.timestamp()
def encoded(d):return (json.dumps(d,separators=(',',':'),ensure_ascii=False,allow_nan=False)+'\n').encode()
def load(path,sources):
 p=Path(path);sources.append(dict(path=p.relative_to(ROOT).as_posix(),SHA256=sha(p)));return read(p)
def scoped(rows):return [r for r in rows if r['scope']=='WR_TE' and r.get('cohort','ALL')=='ALL' and r.get('week','ALL')=='ALL']
def method_label(method):
 if method.split('_')[0] in ['F0','F1','F2','F3']:
  arm,product=method.split('_',1);return LABELS[arm]+' / '+{'LAW':'law direction','MEAN':'mean direction','MEDIAN':'median direction'}[product]
 if method.startswith('CONTROL_LEAF_'):return 'Retained unchanged C Leaf / '+method.removeprefix('CONTROL_LEAF_').lower()+' direction'
 return LABELS.get(method,method)
def research():
 sources=[];runs=[];num=[];pairs=[];decision=load(EXP/'KEEP_STOP.json',sources)
 for year in [2026,2025]:
  runs.append(load(EXP/f'RUN-{year}.json',sources))
  for r in scoped(load(EXP/f'QUALIFIED_NUMERICAL_SCORES-{year}.json.xz',sources)):
   if r['method'] in ['F0','F1','F2','F3','CONTROL_LEAF']:num.append(dict(r,label=LABELS[r['method']]))
  pairs.extend(r for r in scoped(load(EXP/f'NUMERICAL_PAIRED-{year}.json.xz',sources)) if r['metric']=='median_absolute_error' and (r['candidate'],r['control']) in CONTRASTS)
 actual=[]
 for r in scoped(load(EXP/'ACTUAL_LINE_SCORES.json.xz',sources)):
  if r['method'].split('_')[0] in ['F0','F1','F2','F3'] or r['method'] in ['P1','P2','E0','ALWAYS_OVER','ALWAYS_UNDER','RETAINED_EARLIER_PREVALENCE_V8'] or r['method'].startswith('CONTROL_LEAF_'):actual.append(dict(r,label=method_label(r['method'])))
 order=[a+'_'+p for p in ['LAW','MEAN','MEDIAN'] for a in ['F0','F1','F2','F3']]+['CONTROL_LEAF_LAW','CONTROL_LEAF_MEAN','CONTROL_LEAF_MEDIAN','P1','P2','E0','ALWAYS_OVER','ALWAYS_UNDER','RETAINED_EARLIER_PREVALENCE_V8'];actual.sort(key=lambda r:order.index(r['method']))
 ap=[r for r in scoped(load(EXP/'PAIRED_CHANGES.json.xz',sources)) if r['product']=='LAW' and ((r['candidate'].removesuffix('_LAW'),r['control'].removesuffix('_LAW')) in CONTRASTS or (r['candidate']=='F3_LAW' and r['control'] in ['P2','E0','RETAINED_EARLIER_PREVALENCE_V8']))]
 offered=scoped(load(EXP/'QUALIFIED_OFFERED_NUMERICAL_SCORES.json.xz',sources))
 assert len(num)==10 and all(r['actual_weeks']==list(range(1,9)) for r in num)
 assert actual and all(r['weeks']==[2,3] for r in actual)
 return dict(schema=SCHEMA,status='Completed aligned timing/profile comparison. Retained seven-day baselines are reused. No primary replacement, validated confidence or Top Picks change is admitted.',decisions=decision['decisions'],category='rec',role_scope='WR_TE',actual_scope='Pinnacle 2026 Weeks 2–3 only, WR/TE. Timing-unverified actual lines and current-vintage chronological reconstruction; exposed research, not original issued selections or verified sportsbook settlement.',actual_scores=actual,numerical_scores=num,actual_paired_changes=ap,numerical_paired_changes=pairs,offered_numerical_scores=offered,primary_releases=0,qualified_paper_picks=0,actual_scored_weeks=[2,3],numerical_season_weeks={str(r['year']):list(range(1,9)) for r in runs},source_bindings=sources,generated_from_latest_run_UTC=max(r['created_UTC'] for r in runs),report_path=BASE.relative_to(ROOT).as_posix(),limits=['One day is a reconstructed timing-sensitivity assumption,notauthenticatedoriginalpublication.','Only two actual-line weeks; numerical eight-week history does not qualify probability,direction or Top Picks.','Full-role/cohort/weekly views remain in canonical linked evidence.','This wave adds no defensive-value block; C03 defense findings stay separate.'])

def current():
 sources=[];proof=load(BASE/'CURRENT_PUBLICATION_RECEIPT.json',sources)
 run_id=proof['run_id'];assert re.fullmatch(r'[A-Za-z0-9_.-]+',run_id)
 run=ROOT/'prospective/runs'/run_id;m=load(run/'RUN.json',sources)
 assert proof['fresh_download_verified'] is True and proof['qualified_before_first_kickoff'] is True
 assert proof['run_manifest_SHA256']==sha(run/'RUN.json') and proof['forecast_SHA256']==sha(run/'FORECASTS.json.xz')
 assert re.fullmatch(r'[a-f0-9]{40}',proof['capture_commit'])
 assert stamp(proof['server_check_completed_UTC'])<stamp(m['first_kickoff_UTC'])
 for name,entry in m['files'].items():
  p=run/name;assert p.stat().st_size==entry['bytes'] and sha(p)==entry['SHA256']
 rows=load(run/'FORECASTS.json.xz',sources)
 assert len(rows)==m['forecast_rows'] and {r['model_id'] for r in rows}==set(MODELS)
 assert len({(r['model_id'],r['game_id'],r['player_id']) for r in rows})==len(rows)
 masks={model:{(r['game_id'],r['player_id']) for r in rows if r['model_id']==model} for model in MODELS}
 assert all(mask==next(iter(masks.values())) for mask in masks.values()),'CURRENT_MODEL_QUERY_MASK_MISMATCH'
 assert len({r['player_id'] for r in rows})==m['unique_players'] and {r['game_id'] for r in rows}==set(m['games'])
 assert m['real_offers']==m['real_selections']==0 and m['primary_replacement'] is False
 keys=['forecast_id','model_id','model_SHA256','player_id','name','position','team','opponent_team','game_id','season','week','category','kickoff_UTC','mean','median','p05','p95','history_support','any_imputed','sparse_history','profile_missing','hard_incumbent_fallback','prior_provenance','feature_policy','appearance_conditioning','information_cutoff_UTC','inference_UTC','issued_UTC','native_status_observed_UTC','expires_UTC','line','selected_side','confidence','EV','latest_admitted_game','latest_game_age_at_feature_cutoff_days']
 projected=[]
 for r in rows:
  assert r['category']=='rec' and r['line'] is None and r['selected_side'] is None and r['probability_at_line'] is None and r['confidence'] is None and r['EV'] is None
  assert stamp(r['issued_UTC'])<=stamp(proof['server_check_completed_UTC'])<stamp(r['kickoff_UTC'])
  assert stamp(r['information_cutoff_UTC'])<=stamp(r['inference_UTC'])<=stamp(r['issued_UTC'])
  projected.append({k:r.get(k) for k in keys})
 return dict(schema='C04-CURRENT-SITE-v1',run_id=run_id,rows=projected,models=[dict(model_id=k,label=v) for k,v in MODELS.items()],unique_players=m['unique_players'],games=len(m['games']),basic_rows=m['basic_rows'],real_offers=0,real_selections=0,primary_replacement=False,server_qualified=True,capture_commit=proof['capture_commit'],server_run_URL=proof['server_run_URL'],server_persisted_UTC=proof['server_check_completed_UTC'],information_cutoff_UTC=m['information_cutoff_UTC'],issued_UTC=m['issued_UTC'],first_inference_UTC=min(r['inference_UTC'] for r in rows),last_inference_UTC=max(r['inference_UTC'] for r in rows),native_status_observed_UTC=max(r['native_status_observed_UTC'] for r in rows),roster_contract=m['roster_contract'],roster_week=None,individual_transaction_effective_UTC=None,original_website_incumbent=False,source_bindings=sources)

def export(validate=False):
 payload=dict(schema='C04-SITE-PROFILE-CLOSURE-NEXT-02-v1',research=research(),current=current())
 body=encoded(payload);target=ROOT/'docs/data/profile-closure-next-02.json'
 digest=hashlib.sha256(body).hexdigest();buildpath=ROOT/'docs/build.json';build=read(buildpath)
 if validate:
  assert target.read_bytes()==body and build['profile_closure_next02_SHA256']==digest,'C04_SITE_CANONICAL_OR_HASH_MISMATCH'
  html=(ROOT/'docs/context.html').read_text();js=(ROOT/'docs/context.js').read_text()
  for element in ['c04-status','c04-decisions','c04-actual','c04-paired','c04-numerical','c04-current-status','c04-model','c04-role','c04-game','c04-search','c04-current']:
   assert f'id="{element}"' in html and element in js,'C04_RENDER_CONTRACT_MISMATCH:'+element
 else:
  target.write_bytes(body);build['profile_closure_next02_SHA256']=digest;buildpath.write_bytes(encoded(build))
 print('C04_SITE_'+('CANONICAL_VALID' if validate else 'WRITTEN'),len(body))
 return payload

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--validate',action='store_true');a=p.parse_args();export(a.validate)
