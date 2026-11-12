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

def project():
 x=validate_document(read(CANONICAL));bindings=[]
 for row in x['source_bindings']:
  assert isinstance(row,dict) and isinstance(row.get('path'),str) and isinstance(row.get('SHA256'),str),'LOCAL_RETAINED_SOURCE_BINDING_REQUIRED'
  p=(ROOT/row['path']).resolve();assert p.is_relative_to(ROOT.resolve()),'SOURCE_PATH_OUTSIDE_C'
  assert p.is_file() and sha(p)==row['SHA256'],'SOURCE_BINDING_MISMATCH:'+row['path']
  bindings.append(dict(row))
 return dict(schema=SITE_SCHEMA,canonical=dict(path=CANONICAL.relative_to(ROOT).as_posix(),SHA256=sha(CANONICAL)),prepared_UTC=x['prepared_UTC'],status=x['status'],categories=x['categories'],source_bindings=bindings,publication_scope='C_COORDINATOR_RESEARCH_DECISIONS;ORIGINAL_WEBSITE_OWNER_ALONE_RELEASES',model_or_policy_activation=False,new_NFL_observations=0)

def export(validate=False):
 x=project();body=encoded(x);buildp=ROOT/'docs/build.json';build=read(buildp);digest=hashlib.sha256(body).hexdigest()
 if validate:
  assert SITE.read_bytes()==body and build.get(BUILD_KEY)==digest,'CANONICAL_DECISION_OR_CHECKSUM_MISMATCH'
  html=(ROOT/'docs/championship.html').read_text();js=(ROOT/'docs/championship.js').read_text()
  for ident in ['c06-status','c06-limits','c06-clock','c06-category','c06-records','c06-products','c06-error']:
   assert f'id="{ident}"' in html and ident in js,'C06_RENDER_CONTRACT_MISSING:'+ident
 else:
  SITE.parent.mkdir(parents=True,exist_ok=True);SITE.write_bytes(body);build[BUILD_KEY]=digest;buildp.write_bytes(encoded(build))
 print('CATEGORY_DECISIONS_SITE_'+('VALID' if validate else 'WRITTEN'),len(body));return x

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--validate',action='store_true');a=p.parse_args();export(a.validate)
