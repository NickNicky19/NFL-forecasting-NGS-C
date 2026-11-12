"""Current-source P1 delivery with evidence-bound cache reuse; no search or grader.

The only fast path requires identical eligible raw facts/context and unchanged
query identity/features. An ineligible source correction cannot silently trigger
a refit; a relevant change blocks this path for a separately bounded rebuild.
"""
from __future__ import annotations
import argparse,ast,collections,hashlib,json,lzma,math,resource,subprocess,time
from pathlib import Path
from datetime import timezone
from email.utils import parsedate_to_datetime
from urllib.request import Request
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
from context_experiment_c01 import pooled_mu
from current_query_capture_c05 import read,write,sha,now,git
from receiving_current_validation_c04 import aware,bound_files,close
from receiving_current_capture_c04 import query_universe,independent_response_clock,qualified_events
from forward_sources_v4 import kickoff_frame,scoreboard_projection

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'sources/category-decision-release-01'
REPORT=ROOT/'reports/category-decision-release-01/current'
REG=ROOT/'reports/category-decision-release-01/CURRENT_P1_DELIVERY_REGISTRATION.json'
OLD=ROOT/'prospective/runs/C-C04-20261110-W10-FIRST-01'
MODEL='C_V11_P1_E2_POOLED_7D'
TARGET='2026_10_WAS_NYG'
SCHEMA='C06-CURRENT-SOURCE-P1-QUERY-RUN-v1'
RECEIPT_SCHEMA='C06-SERVER-PREGAME-RECEIPT-v1'
POLICY='CURRENT_SOURCE_REQUALIFIED_SEVEN_DAY_P1;EXACT_ELIGIBLE_INPUT_CACHE_REUSE'
CODE=['src/current_query_delivery_c06.py','src/receiving_current_capture_c04.py','src/receiving_current_validation_c04.py','src/context_experiment_c01.py','src/context_features_c01.py','src/data_v2.py','src/forward_sources_v4.py','src/laws_v2.py','src/prospective_v4.py','src/receiving_increment_query_c03.py']

def binding(p):
 p=Path(p);return dict(path=p.resolve().relative_to(ROOT).as_posix(),bytes=p.stat().st_size,SHA256=sha(p))
def verify_bind(b):
 p=(ROOT/b['path']).resolve();assert p.is_relative_to(ROOT),'C06_BIND_PATH_ESCAPE';assert p.stat().st_size==b['bytes'] and sha(p)==b['SHA256'],'C06_BOUND_BYTES_CHANGED:'+b['path'];return p

def committed():
 paths=[*CODE,str(REG.relative_to(ROOT)),str((REPORT/'fetch_current_football.py').relative_to(ROOT))]
 hashes={}
 for rel in paths:
  actual=sha(ROOT/rel);assert hashlib.sha256(subprocess.check_output(['git','show','HEAD:'+rel],cwd=ROOT)).hexdigest()==actual,'C06_UNCOMMITTED_CODE_OR_REGISTRATION:'+rel;hashes[rel]=actual
 return dict(code_commit=git('rev-parse','HEAD'),code_SHA256=hashes,registration_SHA256=sha(REG))

def eligible_seven_day_games(schedule,cutoff):
 """Declared strict reconstruction, not authenticated publication time."""
 return set(schedule.loc[(schedule.kickoff+7*86400<float(cutoff))&schedule.home_score.notna()&schedule.away_score.notna(),'game_id'])

def canonical_equal(old,new,keys,allowed):
 a=pd.read_csv(old,low_memory=False);b=pd.read_csv(new,low_memory=False)
 assert list(a.columns)==list(b.columns) and not a.duplicated(keys).any() and not b.duplicated(keys).any(),'C06_CANONICAL_SCHEMA_OR_DUPLICATE'
 a=a[a.game_id.isin(allowed)].sort_values(keys).reset_index(drop=True);b=b[b.game_id.isin(allowed)].sort_values(keys).reset_index(drop=True)
 return bool(a.equals(b)),len(a),len(b)

def lineage():
 run=read(OLD/'RUN.json');bound_files(OLD,run['files']);app=read(OLD/'RECOVERY_COMPLETENESS_APPENDIX.json');assert app['parent_RUN_SHA256']==sha(OLD/'RUN.json');bound_files(OLD,{x['path']:x for x in app['added_files']})
 draft=read(OLD/'draft/DRAFT.json');bound_files(OLD/'draft',draft['files']);spec=next(x for x in draft['models'] if x['model_id']==MODEL);p=OLD/'draft'/spec['path'];assert sha(p)==spec['SHA256']
 meta=read(p);assert meta['family']=='POISSON' and meta['model']['type']=='L2_POOLED_POISSON' and meta['model']['partial'] is False
 assert meta['feature_policy']=='ALL_LABEL_FEATURE_QUERY_KICKOFF_PLUS7D_STRICT_RECONSTRUCTION;CONTEXT2025_2026_ONLY' and len(meta['feature_order'])==60
 rows=read(OLD/'draft/DRAFT_FORECASTS.json.xz');prepared=[x for x in rows if x['model_id']==MODEL and x['game_id']==TARGET];assert len({x['player_id'] for x in prepared})==len(prepared)
 game=next(x for x in draft['candidate_games'] if x['game_id']==TARGET)
 return meta,prepared,game,dict(model=binding(p),original_RUN=binding(OLD/'RUN.json'),original_draft=binding(OLD/'draft/DRAFT.json'),original_prepared_rows=binding(OLD/'draft/DRAFT_FORECASTS.json.xz'),model_producer_commit=draft['code_commit'],model_producer_code_SHA256=draft['code_SHA256'],old_feature_cutoff_UTC=draft['input_cutoff_UTC'])

def source_inputs(source=SOURCE,at=None):
 source=Path(source);m=read(source/'MODEL_INPUT_MANIFEST.json');at=aware(now()).timestamp() if at is None else float(at)
 assert m['id']=='C06-CURRENT-INPUT-MANIFEST-v1' and m['roster_contract']=='NFLVERSE_CURRENT_KNOWN_SEASON_ROSTER_SNAPSHOT-v1' and m['roster_week'] is None
 assert aware(m['actual_input_cutoff_UTC']).timestamp()<=at and m['future_target_outcomes_absent'] is True
 for x in m['files']:verify_bind(x)
 for s in m['sources']:assert s['HTTP_status']==200 and s['state']=='RECEIVED' and aware(s['observed_UTC']).timestamp()<=aware(m['actual_input_cutoff_UTC']).timestamp()
 roster=m['roster_source'];pub=parsedate_to_datetime(roster['HTTP_Last_Modified']).timestamp();assert 0<=at-pub<=36*3600,'C06_ROSTER_EXPIRED_OR_FUTURE'
 assert m['source_execution_code']['SHA256']==sha(ROOT/m['source_execution_code']['path'])
 return m,read(source/'roster_current_season.json')

def assess(source=SOURCE,at=None):
 """No inference/fit: prove the relevant input basis and current query mapping."""
 source=Path(source);m,roster=source_inputs(source,at);meta,prepared,game,lin=lineage()
 oldsource=ROOT/'sources/profile-closure-next-02';assert (source/'schedule.csv').read_bytes()==(oldsource/'schedule.csv').read_bytes(),'C06_SCHEDULE_CHANGE_REQUIRES_REBUILD'
 schedule=kickoff_frame(pd.read_csv(source/'schedule.csv'));oldcut=aware(meta['fit_information_cutoff_UTC']).timestamp();cut=aware(m['actual_input_cutoff_UTC']).timestamp()
 before=eligible_seven_day_games(schedule,oldcut);after=eligible_seven_day_games(schedule,cut)
 old_finality_path=verify_bind(m['old_finality_contract']);old_finality=read(old_finality_path);original_finality=read(OLD/'draft/DRAFT.json')['source_bindings']['finality_proof'];assert m['old_finality_contract']==original_finality,'C06_CHANGED_FINALITY_BINDING';assert before<=set(old_finality['completed_game_ids']),'C06_ELIGIBLE_GAMES_WITHOUT_BOUND_FINALITY'
 facts,nold,nnew=canonical_equal(oldsource/'current_facts_2026.csv.gz',source/'current_facts_2026.csv.gz',['game_id','player_id'],after)
 pbp,pold,pnew=canonical_equal(oldsource/'pbp_facts_2026.csv.xz',source/'pbp_facts_2026.csv.xz',['game_id','play_id'],after)
 archive=ROOT/'artifacts/basic-football-facts-v2.1.zip';original_draft=read(OLD/'draft/DRAFT.json');assert sha(archive)==original_draft['source_bindings']['SHA256'],'C06_EARLIER_ARCHIVE_CHANGED'
 context_refs=original_draft['source_bindings']['context_sources'];prior_paths=[ROOT/name for name in context_refs if name.endswith(('pbp_facts_2025.csv.gz','pbp_facts_2025.csv.xz'))];assert len(prior_paths)==1,'C06_AMBIGUOUS_BOUND_PRIOR_CONTEXT'
 prior_context=prior_paths[0]
 assert sha(prior_context)==context_refs[str(prior_context.relative_to(ROOT))],'C06_2025_CONTEXT_CHANGED'
 dependency_names=['data_v2.py','contracts_v2.py','context_features_c01.py','context_experiment_c01.py','receiving_current_capture_c04.py','laws_v2.py','forward_sources_v4.py']
 dependencies={name:sha(ROOT/'src'/name) for name in dependency_names}
 assert all(dependencies[name]==original_draft['code_SHA256'][name] for name in dependency_names),'C06_FEATURE_RECIPE_CODE_CHANGED'
 historical_source=ROOT/'reports/category-decision-release-01/current/source-snapshots/prospective_v4_at_9994055.py'
 historical_bytes=historical_source.read_bytes();assert hashlib.sha256(historical_bytes).hexdigest()==original_draft['code_SHA256']['prospective_v4.py'],'C06_HISTORICAL_SOURCE_SNAPSHOT_HASH_MISMATCH'
 old_prospective=historical_bytes.decode('utf-8')
 def function_ast(text,name):
  found=[n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef) and n.name==name];assert len(found)==1;return ast.dump(found[0],include_attributes=False)
 current_prospective=(ROOT/'src/prospective_v4.py').read_text()
 # C05 added typed forecast-file validation, not a new training filter. Prove
 # its exact legacy core while retaining the actual stronger format checks.
 old_held=next(n for n in ast.parse(old_prospective).body if isinstance(n,ast.FunctionDef) and n.name=='held_ungraded_games')
 new_held=next(n for n in ast.parse(current_prospective).body if isinstance(n,ast.FunctionDef) and n.name=='held_ungraded_games')
 grade_loops=[n for n in new_held.body if isinstance(n,ast.For) and any(isinstance(v,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='forecast_name' for t in v.targets) for v in n.body)];assert len(grade_loops)==1,'C06_AMBIGUOUS_TYPED_GRADE_LOOP'
 grade_loop=grade_loops[0]
 removed=[];kept=[]
 for n in grade_loop.body:
  is_assign=isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='forecast_name' for t in n.targets)
  is_assert=isinstance(n,ast.Assert) and isinstance(n.test,ast.Compare) and isinstance(n.test.left,ast.Name) and n.test.left.id=='forecast_name'
  is_if=isinstance(n,ast.If) and isinstance(n.test,ast.Compare) and isinstance(n.test.left,ast.Name) and n.test.left.id=='forecast_name'
  if is_assign or is_assert or is_if:removed.append(n)
  else:kept.append(n)
 assert [type(n).__name__ for n in removed]==['Assign','Assert','If'],'C06_UNKNOWN_HELD_FORMAT_EXTENSION'
 assert len(removed[2].body)==1 and isinstance(removed[2].body[0],ast.Assert),'C06_UNKNOWN_HELD_TYPED_BRANCH'
 grade_loop.body=kept
 class LegacyForecastName(ast.NodeTransformer):
  def visit_Name(self,node):return ast.Constant(value='forecasts.json.gz') if node.id=='forecast_name' else node
 normalized=LegacyForecastName().visit(new_held)
 training_function_parity={'qualified_training_frame':function_ast(old_prospective,'qualified_training_frame')==function_ast(current_prospective,'qualified_training_frame'),'legacy_held_ungraded_core':ast.dump(old_held,include_attributes=False)==ast.dump(normalized,include_attributes=False)}
 assert all(training_function_parity.values()),'C06_TRAINING_ELIGIBILITY_CODE_CHANGED'
 typed_runs=[]
 for rp in (ROOT/'prospective/runs').glob('*/RUN.json'):
  rm=read(rp)
  if rm.get('schema')!='C-PREGAME-RUN-v4':
   games=set(rm.get('games',[]));assert games and not games.intersection(after),'C06_NEW_TYPED_CAPTURE_IN_ELIGIBLE_TRAINING_WINDOW';typed_runs.append(dict(run_id=rm['run_id'],games=sorted(games)))
 basic,queries=query_universe(roster,[game],2026);byid={x['player_id']:x for x in prepared};available=[];unavailable=[]
 for q in queries:
  old=byid.get(q['player_id']);ok=old is not None and all(old[k]==q[k] for k in ['game_id','team','position','opponent_team','kickoff'])
  if ok:available.append(q['player_id'])
  else:unavailable.append(dict(player_id=q['player_id'],game_id=q['game_id'],reason='NO_EXACT_RETAINED_CURRENT_FEATURE_IDENTITY'))
 passed=before==after and facts and pbp
 return dict(id='C06-P1-ELIGIBLE-BASIS-ASSESSMENT-v1',state='EXACT_RETAINED_FIT_AND_VECTOR_REUSE_PROVED' if passed else 'REBUILD_REQUIRED_NO_INFERENCE_AUTHORIZED',model_id=MODEL,model=lin['model'],source_input=binding(source/'MODEL_INPUT_MANIFEST.json'),old_fit_cutoff_UTC=meta['fit_information_cutoff_UTC'],current_feature_validation_cutoff_UTC=m['actual_input_cutoff_UTC'],strict_reconstructed_7day_game_sets_equal=before==after,new_eligible_games=sorted(after-before),removed_eligible_games=sorted(before-after),eligible_2026_game_ids=sorted(after),eligible_facts_equal=facts,eligible_fact_rows_old=nold,eligible_fact_rows_current=nnew,eligible_PBP_equal=pbp,eligible_PBP_rows_old=pold,eligible_PBP_rows_current=pnew,archive=binding(archive),finality_proof=binding(old_finality_path),prior_context=binding(prior_context),basic_rows=len(basic),current_query_rows=len(queries),available_players=len(available),available_player_ids=sorted(available),unavailable=unavailable,WR_TE_current_query_rows=sum(x['position'] in ['WR','TE'] for x in queries),RB_shadow_rows=sum(x['position']=='RB' for x in queries),new_fits_required=0 if passed else None,feature_recipe_code_SHA256=dependencies,training_eligibility_AST_parity=training_function_parity,typed_capture_games_outside_eligible_window=True,lineage=lin,target_event=game,explanation='Changed source cells outside the entire eligible seven-day facts/context basis cannot affect these fixed query features, training labels, imputation or coefficients. Strict boundary and exact identity/cache keys are verified; historical source timing remains reconstructed.')

def prepare(source=SOURCE):
 started=time.process_time();a=assess(source);out=dict(created_UTC=now(),assessment=a,CPU_seconds=time.process_time()-started,new_fits=0,new_inference_rows=0)
 p=REPORT/'P1_CURRENT_REUSE_ASSESSMENT.json';assert not p.exists(),'C06_ASSESSMENT_ALREADY_FROZEN';write(p,out,True);return out

def current_rows(queries,prepared,meta,cutoff,executed):
 """Same safe Poisson transform/link, applied once to exact reusable vectors."""
 byid={r['player_id']:r for r in prepared};chosen=[q for q in queries if q['player_id'] in byid and all(byid[q['player_id']][k]==q[k] for k in ['team','position','game_id','opponent_team','kickoff'])]
 old=[byid[q['player_id']] for q in chosen]
 if not old:return []
 assert all(r['feature_order']==meta['feature_order'] for r in old)
 x=np.asarray([r['features'] for r in old],float)
 with threadpool_limits(limits=1):mu=pooled_mu(meta['model'],x,None)
 from scipy.stats import poisson
 out=[]
 for q,r,v in zip(chosen,old,mu):
  assert close(float(v),r['mean']),'C06_RETAINED_MEAN_PARITY'
  z=dict(q,model_id=MODEL,model_SHA256=r['model_SHA256'],category='rec',mean=float(v),median=float(poisson.ppf(.5,v)),p05=float(poisson.ppf(.05,v)),p95=float(poisson.ppf(.95,v)),law=dict(kind='POISSON',mu=float(v),assumption='EXPERIMENTAL_REGISTERED_COUNT_LAW_CONDITIONAL_ON_APPEARANCE'),point_types=['EXPECTED_MEAN','LOWER_MEDIAN'],product_type='MEAN_POINT_DIRECTION_CANDIDATE;MEDIAN_AND_LAW_SEPARATE_SHADOW_PRODUCTS',features=r['features'],feature_order=r['feature_order'],feature_policy=meta['feature_policy'],model_fit_cutoff_UTC=meta['fit_information_cutoff_UTC'],information_cutoff_UTC=cutoff,original_feature_preparation_cutoff_UTC=r['information_cutoff_UTC'],feature_cache_reuse='EXACT_CURRENT_ELIGIBLE_BASIS_PARITY',original_prepared_inference_UTC=r['inference_UTC'],inference_UTC=executed,admitted_prior_games=r['admitted_prior_games'],latest_admitted_game=r['latest_admitted_game'],latest_game_age_at_current_feature_cutoff_days=(aware(cutoff).timestamp()-r['admitted_prior_games'][-1]['kickoff'])/86400 if r['admitted_prior_games'] else None,feature_age_semantics='Current-admission minus latest admitted game; actual model lag/rest-age features remain target-kickoff based under unchanged recipe.',history_support=r['history_support'],sparse_history=r['sparse_history'],any_imputed=r['any_imputed'],hard_incumbent_fallback=False,prior_provenance=r['prior_provenance'],appearance_conditioning='CONDITIONAL_ON_APPEARANCE_NOT_STARTER_HEALTH_OR_PARTICIPATION_PROBABILITY',direction_candidate_role_eligible=q['position'] in ['WR','TE'],RB_status='SEPARATE_FORECAST_ONLY_SHADOW' if q['position']=='RB' else None,corrector='NO_EXTRA_CORRECTOR;TRAINING_IMPUTATION_SCALE_AND_POISSON_EXP_LINK_ONCE',state='DRAFT_NOT_ISSUED',line=None,selected_side=None,probability_at_line=None,confidence=None,EV=None)
  assert z['median']==r['median'] and z['p05']==r['p05'] and z['p95']==r['p95'];out.append(z)
 return out

def point_direction_record(row,offer,decision_UTC,*,repricing_policy=None):
 """Use an externally admitted real offer; never alter the saved forecast.

 The admission receipt remains the source/rights authority. This adapter checks
 compatibility and executes only the already declared unrounded-mean rule.
 """
 from receiving_increment_query_c03 import _qualified_offer
 at=aware(decision_UTC).timestamp();record=dict(model_id=MODEL,player_id=row['player_id'],game_id=row['game_id'],category='rec',selection_product='EXPECTED_MEAN_POINT_DIRECTION',decision_policy_id='C06_P1_UNROUNDED_MEAN_AT_EXACT_OFFER-v1',forecast_id=row.get('forecast_id'),forecast_issued_UTC=row.get('issued_UTC'),decision_UTC=decision_UTC,selected_side=None,line=None,confidence=None,probability_at_line=None,EV=None,primary_replacement=False)
 if row.get('model_id')!=MODEL:raise ValueError('C06_WRONG_MEAN_PROCEDURE')
 point=row.get('mean')
 if isinstance(point,bool) or point is None or not math.isfinite(float(point)):raise ValueError('C06_FINITE_EXPECTED_MEAN_REQUIRED')
 if row.get('position') not in ['WR','TE']:return dict(record,state='UNSUPPORTED_EVALUATED_DIRECTION_ROLE;FORECAST_SHADOW_ONLY')
 if not row.get('issued_UTC') or not row.get('expires_UTC'):return dict(record,state='FORECAST_NOT_ISSUED_OR_EXPIRY_UNKNOWN')
 issued=aware(row['issued_UTC']).timestamp();expiry=aware(row['expires_UTC']).timestamp();kick=aware(row['kickoff_UTC']).timestamp()
 if not issued<=at<expiry or at+300>=kick:return dict(record,state='FORECAST_EXPIRED_FUTURE_OR_STARTED')
 if offer is None:return dict(record,state='NO_QUALIFIED_CURRENT_OFFER')
 line=offer.get('line')
 if isinstance(line,bool) or line is None or not math.isfinite(float(line)):raise ValueError('C06_FINITE_EXACT_OFFER_LINE_REQUIRED')
 profile={'base_profile':{'key':{'player_id':row['player_id'],'game_id':row['game_id']},'kickoff_UTC':row['kickoff_UTC']}}
 if not _qualified_offer(offer,profile,float(line),at):return dict(record,state='OFFER_NOT_EXTERNALLY_ADMITTED')
 observed=aware(offer['observed_UTC']).timestamp()
 if observed>issued and repricing_policy!='LATER_CAPTURED_PREGAME_LINE_BOTH_CLOCKS_PRESERVED':return dict(record,state='EXPLICIT_LATER_LINE_REPRICING_CONTRACT_REQUIRED')
 side='OVER' if float(point)>float(line) else 'UNDER' if float(point)<float(line) else None
 if side not in offer['offered_sides']:side=None
 record.update(line=float(line),expected_mean=float(point),offer_observed_UTC=offer['observed_UTC'],repricing_policy=repricing_policy,selected_side=side,state='SELECTED_STATISTICAL_DIRECTION' if side else 'ABSTAIN_EQUAL_POINT_OR_UNOFFERED_SIDE',offer_binding={k:offer.get(k) for k in ['admission_record_SHA256','source_snapshot_SHA256','source','venue','product','tier','observed_UTC','expiry_UTC','offered_sides']},settlement_status='STATISTICAL_CROSSING_NOT_VERIFIED_VENUE_RETURN')
 return record

def clean_start(output):
 assert not git('status','--porcelain'),'C06_WHOLE_TREE_MUST_BE_CLEAN';p=Path(output).resolve();assert not p.is_relative_to(ROOT);r=dict(created_UTC=now(),git_status='',**committed());write(p,r,True);return r

def resource_guard(extra=()):
 from forward_budget_v4 import complete_C_roots,tree_bytes
 roots=complete_C_roots([ROOT,*Path('/workspace').glob('c0[456]*'),*extra]);total=sum(tree_bytes(x) for x in roots)
 assert total<=read(REG)['whole_C_bytes_cap_unchanged'],'C06_WHOLE_C_BYTE_CAP'
 return total

def infer_draft(output,source=SOURCE):
 reg=read(REG);assert reg.get('execution_authorized') is True,'C06_ROOT_COMMITTED_EXECUTION_AUTHORIZATION_REQUIRED';bind=committed();assert not git('status','--porcelain'),'C06_WHOLE_TREE_MUST_BE_CLEAN'
 a=assess(source);saved=read(REPORT/'P1_CURRENT_REUSE_ASSESSMENT.json');assert a==saved['assessment'] and a['state']=='EXACT_RETAINED_FIT_AND_VECTOR_REUSE_PROVED' and a['available_players']>0,'C06_CACHE_REUSE_NOT_PROVED_OR_EMPTY'
 p=Path(output).resolve();assert not p.is_relative_to(ROOT) and not p.exists();p.mkdir();resource_guard([p]);started=now();cpu=time.process_time();wall=time.monotonic();meta,prepared,game,lin=lineage();m,roster=source_inputs(source);basic,queries=query_universe(roster,[game],2026)
 rows=current_rows(queries,prepared,meta,m['actual_input_cutoff_UTC'],now());assert len(rows)==a['available_players']
 write(p/'FORECASTS_DRAFT.json.xz',rows,True);write(p/'CURRENT_BOARD.json.xz',basic,True);write(p/'INPUT_MANIFEST.json',m,True);write(p/'CURRENT_REUSE_ASSESSMENT.json',saved,True)
 d=dict(schema='C06-CURRENT-P1-INFERENCE-DRAFT-v1',created_UTC=now(),started_UTC=started,**bind,source_input=binding(Path(source)/'MODEL_INPUT_MANIFEST.json'),information_cutoff_UTC=m['actual_input_cutoff_UTC'],target_event=game,lineage=lin,forecast_rows=len(rows),basic_rows=len(basic),current_query_players=len(queries),available_players=len(rows),unavailable_players=len(queries)-len(rows),new_fits=0,new_inference_rows=len(rows),CPU_seconds=time.process_time()-cpu,wall_seconds=time.monotonic()-wall,peak_RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024)
 assert d['CPU_seconds']<=reg['CPU_seconds_max'] and d['peak_RSS_bytes']<=reg['RSS_bytes_max'];d['files']={x.name:dict(bytes=x.stat().st_size,SHA256=sha(x)) for x in p.iterdir()};write(p/'DRAFT.json',d,True);resource_guard([p]);assert sum(x.stat().st_size for x in p.rglob('*') if x.is_file())<=reg['new_current_temporary_bytes_max'];return d

def native_status(draft,proof_path):
 """One reserved final native check after a clean, committed inference gate."""
 from urllib.request import build_opener
 proof=read(proof_path);bind=committed();assert proof['git_status']=='' and all(proof[k]==v for k,v in bind.items()) and not git('status','--porcelain')
 d=read(Path(draft)/'DRAFT.json');assert all(d[k]==v for k,v in bind.items());assert 0<=aware(now()).timestamp()-aware(proof['created_UTC']).timestamp()<=1800
 ledger=REPORT/'NATIVE_REQUEST.json';assert not ledger.exists(),'C06_FINAL_NATIVE_ATTEMPT_ALREADY_RETAINED';reg=read(REG);assert reg['upstream_requests_max_total']==6
 m=dict(id='C06_WAS_NYG_NATIVE_20261112',url='https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates=20261112&limit=100',method='GET',started_UTC=now(),state='ATTEMPTING');write(ledger,m,True)
 try:
  with build_opener().open(Request(m['url'],headers={'User-Agent':'C06-final-native-gate'}),timeout=30) as r:
   body=r.read(3145728);heads={k.lower():v for k,v in r.headers.items()};assert r.status==200 and len(body)<3145728
   m.update(state='RECEIVED',HTTP_status=r.status,observed_UTC=now(),body_bytes_read=len(body),SHA256=hashlib.sha256(body).hexdigest(),HTTP_Date=heads.get('date'),HTTP_Age=heads.get('age'),HTTP_Last_Modified=heads.get('last-modified'),ETag=heads.get('etag'))
  write(ledger,m);assert read(REPORT/'BODY_RESOURCE.json')['body_bytes_total']+len(body)<=reg['source_body_bytes_max_total'],'C06_SOURCE_BODY_CAP';clock=independent_response_clock(m,aware(m['observed_UTC']).timestamp());events=scoreboard_projection(json.loads(body),m['id'],m['observed_UTC']);accepted,rejected=qualified_events([d['target_event']],events,aware(m['observed_UTC']).timestamp(),after=aware(proof['created_UTC']).timestamp());assert list(accepted)==[TARGET]
  write(REPORT/'NATIVE_EVENTS.json',events,True);status=dict(id='C06-NATIVE-STATUS-BINDING-v1',source=m,response_clock=clock,event_binding=binding(REPORT/'NATIVE_EVENTS.json'),source_input=d['source_input'],execution_code_SHA256=sha(Path(__file__)),target_event=accepted[TARGET],rejected=rejected);write(REPORT/'STATUS_SOURCE_MANIFEST.json',status,True);return status
 except Exception as e:
  m.update(state='FAILED',error_type=type(e).__name__,error=str(e),observed_UTC=now());write(ledger,m);raise

def issue(draft,proof_path,output,run_id):
 draft=Path(draft);output=Path(output);assert not output.exists();bind=committed();proof=read(proof_path);d=read(draft/'DRAFT.json');at=aware(now()).timestamp()
 assert all(d[k]==v==proof[k] for k,v in bind.items()) and proof['git_status']=='' and 0<=at-aware(proof['created_UTC']).timestamp()<=1800
 allowed={str((REPORT/name).relative_to(ROOT)) for name in ['NATIVE_REQUEST.json','NATIVE_EVENTS.json','STATUS_SOURCE_MANIFEST.json']};dirty=subprocess.check_output(['git','status','--porcelain','--untracked-files=all'],cwd=ROOT,text=True).splitlines();assert all(x[3:] in allowed for x in dirty),'C06_UNEXPECTED_CHANGES_AFTER_CLEAN_GATE'
 bound_files(draft,d['files']);m,_=source_inputs(at=at);assert m==read(draft/'INPUT_MANIFEST.json') and sha(ROOT/d['source_input']['path'])==d['source_input']['SHA256']
 status=read(REPORT/'STATUS_SOURCE_MANIFEST.json');assert status['execution_code_SHA256']==sha(Path(__file__)) and status['source_input']==d['source_input'];verify_bind(status['event_binding']);events=read(REPORT/'NATIVE_EVENTS.json');clock=independent_response_clock(status['source'],at);accepted,_=qualified_events([d['target_event']],events,at,after=aware(proof['created_UTC']).timestamp());assert list(accepted)==[TARGET]
 issued=now();expiry=min(parsedate_to_datetime(m['roster_source']['HTTP_Last_Modified']).timestamp()+36*3600,aware(status['source']['observed_UTC']).timestamp()+1800,d['target_event']['kickoff']-300);rows=read(draft/'FORECASTS_DRAFT.json.xz')
 for r in rows:r.update(run_id=run_id,forecast_id=hashlib.sha256((run_id+'|'+MODEL+'|'+r['game_id']+'|'+r['player_id']).encode()).hexdigest()[:24],state='ISSUED_CURRENT_SOURCE_P1_SHADOW_AWAITING_GITHUB_PROOF',issued_UTC=issued,generated_UTC=issued,native_status_observed_UTC=status['source']['observed_UTC'],expires_UTC=pd.Timestamp(expiry,unit='s',tz='UTC').isoformat(),expiry_action='STOP_CURRENT_USE_NOT_ORIGINAL_GRADING',event_state='pre',information_policy=POLICY)
 output.mkdir(parents=True);write(output/'FORECASTS.json.xz',rows,True);write(output/'CURRENT_BOARD.json.xz',read(draft/'CURRENT_BOARD.json.xz'),True);write(output/'INFERENCE_DRAFT.json',d,True);write(output/'CLEAN_START_PROOF.json',proof,True);write(output/'INPUT_MANIFEST.json',m,True);write(output/'NATIVE_STATUS.json',status,True);write(output/'CURRENT_REUSE_ASSESSMENT.json',read(draft/'CURRENT_REUSE_ASSESSMENT.json'),True)
 for p in draft.iterdir():
  if p.is_file():dest=output/'inference_draft'/p.name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(p.read_bytes())
 manifest=dict(schema=SCHEMA,run_id=run_id,created_UTC=issued,issued_UTC=issued,**bind,lineage=d['lineage'],source_input=d['source_input'],source_status_path=str((REPORT/'STATUS_SOURCE_MANIFEST.json').relative_to(ROOT)),information_policy=POLICY,information_cutoff_UTC=d['information_cutoff_UTC'],forecast_rows=len(rows),unique_players=len({r['player_id'] for r in rows}),games=[TARGET],first_kickoff_UTC=pd.Timestamp(d['target_event']['kickoff'],unit='s',tz='UTC').isoformat(),new_fits=0,new_inference_rows=len(rows),real_offers=0,real_selections=0,primary_replacement=False,original_website_incumbent=False,current_query_players=d['current_query_players'],available_players=d['available_players'],unavailable_players=d['unavailable_players'],publication_state='AWAITING_GITHUB_SERVER_PROOF',original_first_scoring_snapshot_unchanged=True,supplementary_revision_of='C-C04-20261110-W10-FIRST-01',conditioning='Conditionalonappearance;18WRTEpointcandidateand7RBforecastshadow;nohealthorstarterclaim')
 manifest['files']={p.relative_to(output).as_posix():dict(bytes=p.stat().st_size,SHA256=sha(p)) for p in output.rglob('*') if p.is_file()};write(output/'RUN.json',manifest,True);resource_guard([draft]);assert sum(p.stat().st_size for p in output.rglob('*') if p.is_file())<=read(REG)['new_source_retention_bytes_max'];return manifest

def validate_run(run,check_clock=False):
 run=Path(run);m=read(run/'RUN.json');assert m['schema']==SCHEMA and m['information_policy']==POLICY and m['new_fits']==m['real_offers']==m['real_selections']==0 and m['primary_replacement'] is False
 bound_files(run,m['files']);d=read(run/'INFERENCE_DRAFT.json');assert d==read(run/'inference_draft/DRAFT.json');bound_files(run/'inference_draft',d['files']);assert all(m[k]==d[k] for k in ['code_commit','code_SHA256','registration_SHA256','source_input','lineage','information_cutoff_UTC'])
 proof=read(run/'CLEAN_START_PROOF.json');assert proof['git_status']=='' and all(proof[k]==m[k] for k in ['code_commit','code_SHA256','registration_SHA256']);issued=aware(m['issued_UTC']).timestamp();assert 0<=issued-aware(proof['created_UTC']).timestamp()<=1800
 source_m,roster=source_inputs(at=issued);assert source_m==read(run/'INPUT_MANIFEST.json');assert sha(ROOT/m['source_input']['path'])==m['source_input']['SHA256']
 assessment=read(run/'CURRENT_REUSE_ASSESSMENT.json');assert assessment['assessment']==assess(at=issued);meta,prepared,game,lin=lineage();assert lin==m['lineage']
 status=read(run/'NATIVE_STATUS.json');assert status==read(ROOT/m['source_status_path']) and status['source_input']==m['source_input'] and status['execution_code_SHA256']==m['code_SHA256']['src/current_query_delivery_c06.py'];verify_bind(status['event_binding']);events=read(ROOT/status['event_binding']['path']);assert all(e['source_id']==status['source']['id'] and e['observed_UTC']==status['source']['observed_UTC'] for e in events);independent_response_clock(status['source'],issued);accepted,_=qualified_events([game],events,issued,after=aware(proof['created_UTC']).timestamp());assert list(accepted)==[TARGET]
 board,queries=query_universe(roster,[game],2026);assert board==read(run/'CURRENT_BOARD.json.xz');rows=read(run/'FORECASTS.json.xz');fresh=read(run/'inference_draft/FORECASTS_DRAFT.json.xz');assert len(rows)==len(fresh)==m['forecast_rows'] and len({r['forecast_id'] for r in rows})==len(rows)
 byid={r['player_id']:r for r in fresh};expected=current_rows(queries,prepared,meta,m['information_cutoff_UTC'],rows[0]['inference_UTC']);check={r['player_id']:r for r in expected}
 for r in rows:
  assert all(r.get(k)==v for k,v in byid[r['player_id']].items() if k!='state')
  assert r['game_id']==TARGET and r['category']=='rec' and close(r['mean'],check[r['player_id']]['mean']) and r['median']==check[r['player_id']]['median'];assert r['features']==check[r['player_id']]['features'] and r['feature_order']==meta['feature_order']
  assert all(r[k] is None for k in ['line','selected_side','probability_at_line','confidence','EV']) and not any(k in r for k in ['actual','played','realized_starter'])
  assert r['model_SHA256']==lin['model']['SHA256'] and r['model_fit_cutoff_UTC']==meta['fit_information_cutoff_UTC'];assert aware(r['model_fit_cutoff_UTC'])<=aware(r['information_cutoff_UTC'])<aware(r['inference_UTC'])<aware(r['issued_UTC'])<aware(r['expires_UTC'])<aware(r['kickoff_UTC'])
  assert all(math.isfinite(r[k]) and r[k]>=0 for k in ['mean','median','p05','p95']) and close(r['law']['mu'],r['mean'])
 if check_clock:assert aware(now()).timestamp()+300<game['kickoff'],'C06_SERVER_CHECK_AFTER_CUTOFF'
 return m,[dict(r,policy_id='C06::'+MODEL,scoring_contract_id='official-player-fullgame-OT-v1') for r in rows]

def validate_receipt(run,receipt,m,rows):
 assert receipt['schema']==RECEIPT_SCHEMA and receipt['qualified_prospective'] is True and receipt['run_id']==m['run_id'];assert receipt['forecast_blob_SHA256']==sha(Path(run)/'FORECASTS.json.xz') and receipt['run_manifest_SHA256']==sha(Path(run)/'RUN.json');assert receipt['fresh_GitHub_bytes_verified'] is True and receipt['not_client_commit_dates'] is True
 created=aware(receipt['server_run_created_UTC']);started=aware(receipt['server_run_started_UTC']);done=aware(receipt['server_check_completed_UTC']);assert created<=started<=done and aware(m['issued_UTC'])<=done;assert all(done+pd.Timedelta(seconds=300)<aware(r['kickoff_UTC']) for r in rows);return done

if __name__=='__main__':
 p=argparse.ArgumentParser();s=p.add_subparsers(dest='command',required=True)
 s.add_parser('prepare');a=s.add_parser('infer-draft');a.add_argument('--output',type=Path,required=True)
 a=s.add_parser('clean-start');a.add_argument('--output',type=Path,required=True)
 a=s.add_parser('native-status');a.add_argument('--draft',type=Path,required=True);a.add_argument('--proof',type=Path,required=True)
 a=s.add_parser('issue');a.add_argument('--draft',type=Path,required=True);a.add_argument('--proof',type=Path,required=True);a.add_argument('--output',type=Path,required=True);a.add_argument('--run-id',required=True)
 a=p.parse_args();r=prepare() if a.command=='prepare' else infer_draft(a.output) if a.command=='infer-draft' else clean_start(a.output) if a.command=='clean-start' else native_status(a.draft,a.proof) if a.command=='native-status' else issue(a.draft,a.proof,a.output,a.run_id)
 print(json.dumps({k:v for k,v in r.items() if k not in ['files','lineage','code_SHA256']},indent=2))
