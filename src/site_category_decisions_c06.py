"""Publish the coordinator's bound category decisions without ranking or grading.

This is a projection of an existing canonical record. It makes no model,
selection, primary-product, or original-website activation decision.
"""
from __future__ import annotations
import argparse, hashlib, json, math
from pathlib import Path
from datetime import datetime
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'reports/category-decision-release-01'
CANONICAL=BASE/'CATEGORY_PRODUCT_DECISIONS.json'
SITE=ROOT/'docs/data/category-decisions-c06.json'
BUILD_KEY='category_decisions_c06_SHA256'
SCHEMA='C-CATEGORY-PRODUCT-DECISIONS-v1'
SITE_SCHEMA='C-CATEGORY-PRODUCT-DECISIONS-SITE-v1'
CATEGORIES={'pass_yd','pass_td','pass_cmp','pass_att','pass_int','rush_yd','rush_att','rec','rec_yd','rush_rec_yd','anytime_td','nick-chart-ppr-v1'}
DECISIONS={'KEEP_INCUMBENT','PROVISIONALLY_SWITCH','SHADOW','ABSTAIN','BLOCKED'}
REQUIRED={'category','label','origin','exact_procedure','output','history_policy','role_scope','decision','preferred_eligible_candidate','highest_observed_panels','actual_weeks_by_season','OVER','UNDER','COMBINED','coverage','controls','uncertainty','evidence_tier','five_week_status','current_query','actual_live_method','remaining_owner_action','other_products'}

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def encoded(x):return (json.dumps(x,separators=(',',':'),ensure_ascii=False,allow_nan=False)+'\n').encode()
def read(p):return json.loads(Path(p).read_bytes())
def canonical_category(v):return 'nick-chart-ppr-v1' if v=='fpts' else v

def finite_tree(v):
 if isinstance(v,float) and not math.isfinite(v):raise ValueError('NONFINITE_PUBLICATION_VALUE')
 if isinstance(v,dict):
  for z in v.values():finite_tree(z)
 elif isinstance(v,list):
  for z in v:finite_tree(z)

def count(v):
 if isinstance(v,bool) or not isinstance(v,int) or v<0:raise ValueError('INVALID_COUNT')
 return v

def record(v):
 if v is None:return
 assert isinstance(v,dict),'RECORD_MUST_BE_OBJECT_OR_NULL'
 for k in ['wins','losses','decided','rate']:assert k in v,'INCOMPLETE_OWN_SIDE_RECORD'
 w,l,n=(count(v[k]) for k in ['wins','losses','decided'])
 assert w+l==n,'OWN_SIDE_DENOMINATOR_MISMATCH'
 p=v['rate']
 if n==0:assert p is None,'EMPTY_DENOMINATOR_IS_NA'
 else:assert isinstance(p,(float,int)) and not isinstance(p,bool) and math.isfinite(p) and abs(p-w/n)<1e-12,'OWN_SIDE_RATE_MISMATCH'

def validate_document(x):
 assert x['schema']==SCHEMA,'UNEXPECTED_CANONICAL_SCHEMA'
 assert isinstance(x['status'],str) and isinstance(x['prepared_UTC'],str)
 assert datetime.fromisoformat(x['prepared_UTC'].replace('Z','+00:00')).tzinfo is not None,'AWARE_PREPARATION_CLOCK_REQUIRED'
 rows=x['categories'];assert isinstance(rows,list) and len(rows)==12,'TWELVE_CATEGORY_RECORD_REQUIRED'
 ids=[canonical_category(r['category']) for r in rows]
 assert len(set(ids))==12 and set(ids)==CATEGORIES,'MISSING_OR_DUPLICATE_CATEGORY'
 for r in rows:
  assert REQUIRED<=r.keys(),'INCOMPLETE_CATEGORY_DECISION'
  assert r['decision'] in DECISIONS,'UNKNOWN_OPERATIONAL_DECISION'
  assert isinstance(r['highest_observed_panels'],list) and isinstance(r['other_products'],list)
  assert isinstance(r['actual_weeks_by_season'],dict) and isinstance(r['coverage'],dict)
  for weeks in r['actual_weeks_by_season'].values():
   assert isinstance(weeks,list) and len(weeks)==len(set(weeks)) and all(type(w)==int and 1<=w<=18 for w in weeks),'INVALID_SCORED_WEEK_LIST'
  for side in ['OVER','UNDER','COMBINED']:record(r[side])
  if all(r[k] is not None for k in ['OVER','UNDER','COMBINED']):
   for k in ['wins','losses','decided']:assert r['OVER'][k]+r['UNDER'][k]==r['COMBINED'][k],'COMBINED_MUST_SUM_COUNTS'
  for k in ['eligible','available','selected','unknown','unavailable','fallback','games','player_games']:
   if k in r['coverage'] and r['coverage'][k] is not None:count(r['coverage'][k])
 finite_tree(x)
 return x

def current_projection(descriptor):
 if descriptor is None:return None
 assert isinstance(descriptor,dict),'CURRENT_PACKET_DESCRIPTOR_REQUIRED'
 run=(ROOT/descriptor['run_path']).resolve();receipt_path=(ROOT/descriptor['receipt_path']).resolve()
 assert run.is_relative_to((ROOT/'prospective/runs').resolve()) and receipt_path.is_relative_to(ROOT.resolve()),'CURRENT_PACKET_PATH_OUTSIDE_C'
 from prospective_v4 import validate_run,validate_receipt
 manifest,rows=validate_run(run);proof=read(receipt_path);validate_receipt(run,proof,manifest,rows);input_manifest=read(run/'INPUT_MANIFEST.json')
 assert manifest['schema']=='C06-CURRENT-SOURCE-P1-QUERY-RUN-v1' and manifest['primary_replacement'] is False
 assert manifest['real_offers']==manifest['real_selections']==manifest['new_fits']==0
 assert len(rows)==manifest['forecast_rows']==25 and len({r['forecast_id'] for r in rows})==25
 assert len({(r['player_id'],r['game_id']) for r in rows})==25
 assert {r['model_id'] for r in rows}=={'C_V11_P1_E2_POOLED_7D'}
 assert sum(r['position'] in ['WR','TE'] for r in rows)==18 and sum(r['position']=='RB' for r in rows)==7
 keys=['forecast_id','model_id','model_SHA256','player_id','name','position','team','opponent_team','game_id','kickoff_UTC','mean','median','p05','p95','point_types','product_type','feature_policy','model_fit_cutoff_UTC','information_cutoff_UTC','original_feature_preparation_cutoff_UTC','original_prepared_inference_UTC','inference_UTC','issued_UTC','native_status_observed_UTC','expires_UTC','expiry_action','history_support','latest_admitted_game','latest_game_age_at_current_feature_cutoff_days','sparse_history','any_imputed','hard_incumbent_fallback','prior_provenance','appearance_conditioning','direction_candidate_role_eligible','RB_status','corrector','starter_state','injury_state','individual_clock_state','information_policy','line','selected_side','probability_at_line','confidence','EV']
 projected=[]
 for row in rows:
  assert all(row[k] is None for k in ['line','selected_side','probability_at_line','confidence','EV'])
  assert row['direction_candidate_role_eligible']==(row['position'] in ['WR','TE'])
  assert all(type(row[k]) in [int,float] and math.isfinite(row[k]) and row[k]>=0 for k in ['mean','median','p05','p95'])
  projected.append({k:row.get(k) for k in keys})
 bindings=[dict(path=p.relative_to(ROOT).as_posix(),SHA256=sha(p)) for p in [run/'RUN.json',run/'FORECASTS.json.xz',run/'INPUT_MANIFEST.json',run/'CURRENT_REUSE_ASSESSMENT.json',receipt_path]]
 return dict(schema='C06-CURRENT-P1-SITE-PACKET-v1',state='SERVER_QUALIFIED_FORECAST_SHADOW_ONLY',run_id=manifest['run_id'],model_id='C_V11_P1_E2_POOLED_7D',rows=projected,forecast_rows=25,players=25,WR_TE_direction_candidate_rows=18,RB_shadow_rows=7,available_players=manifest['available_players'],unavailable_players=manifest['unavailable_players'],games=manifest['games'],real_offers=0,real_selections=0,primary_replacement=False,new_fits=0,new_inference_rows=manifest['new_inference_rows'],information_policy=manifest['information_policy'],source_input=manifest['source_input'],source_observed_UTC=input_manifest['source_observed'],roster_observed_UTC=input_manifest['roster_source']['observed_UTC'],roster_published_UTC=input_manifest['roster_published_UTC'],model_fit_cutoff_UTC=rows[0]['model_fit_cutoff_UTC'],information_cutoff_UTC=manifest['information_cutoff_UTC'],first_inference_UTC=min(r['inference_UTC'] for r in rows),last_inference_UTC=max(r['inference_UTC'] for r in rows),issued_UTC=manifest['issued_UTC'],native_status_observed_UTC=rows[0]['native_status_observed_UTC'],expires_UTC=min(r['expires_UTC'] for r in rows),server_persisted_UTC=proof['server_check_completed_UTC'],capture_commit=proof['capture_commit'],server_run_URL=proof['server_run_URL'],source_bindings=bindings,qualification='18WRTE_HISTORICAL_CANDIDATE_SCOPE;7RB_SHADOW;ENTIRE_PACKET_SHADOW;NO_PRIMARY_PRODUCT_INHERITANCE')

def project():
 x=validate_document(read(CANONICAL));bindings=[]
 for row in x['source_bindings']:
  assert isinstance(row,dict) and isinstance(row.get('path'),str) and isinstance(row.get('SHA256'),str),'LOCAL_RETAINED_SOURCE_BINDING_REQUIRED'
  p=(ROOT/row['path']).resolve();assert p.is_relative_to(ROOT.resolve()),'SOURCE_PATH_OUTSIDE_C'
  assert p.is_file() and sha(p)==row['SHA256'],'SOURCE_BINDING_MISMATCH:'+row['path']
  bindings.append(dict(row))
 return dict(schema=SITE_SCHEMA,canonical=dict(path=CANONICAL.relative_to(ROOT).as_posix(),SHA256=sha(CANONICAL)),prepared_UTC=x['prepared_UTC'],status=x['status'],categories=x['categories'],source_bindings=bindings,current_packet=current_projection(x.get('current_packet')),publication_scope='C_COORDINATOR_RESEARCH_DECISIONS;ORIGINAL_WEBSITE_OWNER_ALONE_RELEASES',model_or_policy_activation=False,new_NFL_observations=0)

def export(validate=False):
 x=project();body=encoded(x);buildp=ROOT/'docs/build.json';build=read(buildp);digest=hashlib.sha256(body).hexdigest()
 if validate:
  assert SITE.read_bytes()==body and build.get(BUILD_KEY)==digest,'CANONICAL_DECISION_OR_CHECKSUM_MISMATCH'
  html=(ROOT/'docs/championship.html').read_text();js=(ROOT/'docs/championship.js').read_text()
  for ident in ['c06-status','c06-limits','c06-clock','c06-category','c06-records','c06-products','c06-error','c06-current-section','c06-current-status','c06-current-clock','c06-current-role','c06-current-records']:
   assert f'id="{ident}"' in html and ident in js,'C06_RENDER_CONTRACT_MISSING:'+ident
 else:
  SITE.parent.mkdir(parents=True,exist_ok=True);SITE.write_bytes(body);build[BUILD_KEY]=digest;buildp.write_bytes(encoded(build))
 print('CATEGORY_DECISIONS_SITE_'+('VALID' if validate else 'WRITTEN'),len(body));return x

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--validate',action='store_true');a=p.parse_args();export(a.validate)
