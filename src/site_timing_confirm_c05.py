"""C05 publication projection: retained public counts and a typed shadow packet.

No fits, collection, grading, ranking or original-site writes.
"""
from __future__ import annotations
import argparse, hashlib, json, lzma, math, re
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'reports/profile-timing-closure-confirm-01'
MODELS={'C_V4_RETAINED_REFERENCE_OBSERVED':'C reference · observed-history recipe, frozen inputs','C_V11_P1_E2_POOLED_7D':'C pooled reference · seven-day recipe, frozen inputs','C04_F3_PROFILE_1D_SHADOW':'C04 F3 shadow · one-day recipe, frozen inputs'}
OLD=Path('prospective/runs/C-C04-20261110-W10-FIRST-01')
TARGET='2026_10_NE_DET'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
 p=Path(p);b=p.read_bytes();return json.loads(lzma.decompress(b) if p.suffix=='.xz' else b)
def encoded(d):return (json.dumps(d,separators=(',',':'),ensure_ascii=False,allow_nan=False)+'\n').encode()
def clock(v):
 d=datetime.fromisoformat(v.replace('Z','+00:00'))
 if d.tzinfo is None:raise ValueError('AWARE_CLOCK_REQUIRED')
 return d.timestamp()
def load(p,sources):
 p=Path(p);sources.append(dict(path=p.relative_to(ROOT).as_posix(),SHA256=sha(p)));return read(p)
def number(v):
 if v is None or v=='':return None
 f=float(v)
 if not math.isfinite(f):raise ValueError('NONFINITE_SOURCE_NUMBER')
 return f
def integer(v):
 f=number(v)
 if f is None or f<0 or not f.is_integer():raise ValueError('INVALID_SOURCE_COUNT')
 return int(f)
def record(row,side):
 n=integer(row[f'{side}_decided'])
 # Author CSV leaves W/L blank only for an explicitly empty side.
 wins,losses=(0 if n==0 and row[f'{side}_{k}'] in ('',None) else integer(row[f'{side}_{k}']) for k in ['wins','losses'])
 rate=number(row.get(f'{side}_rate'))
 assert wins+losses==n and ((rate is None and n==0) or (n>0 and abs(rate-wins/n)<1e-12)),'SOURCE_SIDE_ARITHMETIC'
 return dict(wins=wins,losses=losses,decided=n,rate=rate)
def normalize(row):
 pid=row.get('procedure',row.get('candidate_id'))
 assert pid and row['source_panel']=='ANNUAL_NAMED_NJ' and row['week_view']=='ALL'
 weeks=json.loads(row.get('actual_retained_threshold_weeks',row.get('retained_threshold_weeks')))
 assert weeks==[1,2,3,4,5],'MIXED_PANEL_CANNOT_BE_ANNUAL'
 over,under,total=(record(row,s) for s in ['over','under','combined'])
 assert over['wins']+under['wins']==total['wins'] and over['decided']+under['decided']==total['decided']
 return dict(procedure_id=pid,category=row['category'],role_scope=row.get('roles',row.get('role')),source_panel=row['source_panel'],actual_weeks=weeks,OVER=over,UNDER=under,COMBINED=total,eligible=integer(row['eligible']),selected=integer(row['selected']),unavailable=integer(row['unavailable']),abstained=integer(row['abstained']),unknown_participation=integer(row.get('unknown_participation',row.get('UNKNOWN_PARTICIPATION'))),games=integer(row['games']),numerical_MAE=number(row.get('numerical_MAE',row.get('numeric_MAE'))),numerical_MSE=number(row.get('numerical_MSE',row.get('numeric_MSE'))),evidence_tier=row.get('evidence',row.get('source_timing')),probabilities=None)
def receipts():
 sources=[];h=load(BASE/'intake/HEADLINE.json',sources);admission=load(BASE/'intake/ADMISSION.json',sources);alias=load(BASE/'verification/BASELINE_ALIAS_REUSE.json',sources);binding=load(BASE/'intake/EXACT_C03_SOURCE_BINDING.json',sources)
 assert alias['status'].startswith('PASS') and alias['A_C03_source_bytes_exact']['SHA256']=='0a374a147bdad11bf3226265894b00b39928903f62740e0a4d2344f91eeb8497'
 reception=[normalize(r) for r in h['C03_reception_annual_all_procedures']];completion=[normalize(r) for r in h['B_prior_completion_annual_all_procedures']]
 assert len(reception)==22 and len(completion)==22
 assert all(r['eligible']==469 and r['COMBINED']['decided']==412 and r['games']==53 for r in reception)
 assert all(r['eligible']==88 and r['COMBINED']['decided']==88 and r['games']==51 for r in completion)
 aliases=alias['baseline_products'];assert len(aliases)==4 and all(r['actual_retained_threshold_weeks']==[1,2,3,4,5] for r in aliases)
 return dict(schema='C05-EXACT-PUBLIC-RECEIPTS-SITE-v1',reception_annual=reception,completion_annual=completion,point_aliases=aliases,new_C04_timing_join=h['new_C04_F2_F3_private_board_join'],new_B_timing_join=h['new_B_F2_F3_earlier_completion_join'],qualification_correction='Only the retained annual Weeks 1–5 panel is actual-line evidence here. Weeks 6–7 are internal or unqualified website-threshold diagnostics. The older 733/667 seven-week totals are preserved as mixed diagnostics, not seven qualified offered-line weeks.',source_bindings=sources,private_row_parity='UNKNOWN_OWNER_LOCAL_ROWS_NOT_TRANSFERRED',new_primary_switch=False,point_probability_inheritance=False)
def current():
 sources=[];proof=load(BASE/'CURRENT_PUBLICATION_RECEIPT.json',sources)
 assert proof['schema']=='C05-SERVER-PREGAME-RECEIPT-v1' and proof['qualified_prospective'] is True and proof['fresh_GitHub_bytes_verified'] is True
 run_id=proof['run_id'];assert re.fullmatch(r'[A-Za-z0-9_.-]+',run_id)
 assert re.fullmatch(r'[0-9a-f]{40}',proof['capture_commit']),'IMMUTABLE_CAPTURE_COMMIT_REQUIRED'
 run=ROOT/'prospective/runs'/run_id;m=load(run/'RUN.json',sources)
 assert m['schema']=='C05-FROZEN-FOOTBALL-CURRENT-QUERY-RUN-v1' and m['run_id']==run_id
 assert m['games']==[TARGET]
 assert m['new_fits']==m['real_offers']==m['real_selections']==0 and m['primary_replacement'] is False
 assert proof['forecast_blob_SHA256']==sha(run/'FORECASTS.json.xz') and proof['run_manifest_SHA256']==sha(run/'RUN.json')
 assert proof['not_client_commit_dates'] is True
 assert clock(proof['server_run_created_UTC'])<=clock(proof['server_run_started_UTC'])<=clock(proof['server_check_completed_UTC'])
 assert clock(m['issued_UTC'])<=clock(proof['server_check_completed_UTC']) and clock(proof['server_check_completed_UTC'])+300<clock(m['first_kickoff_UTC'])
 for name,entry in m['files'].items():
  p=(run/name).resolve();assert p.is_relative_to(run.resolve()) and p.stat().st_size==entry['bytes'] and sha(p)==entry['SHA256']
 rows=load(run/'FORECASTS.json.xz',sources);assert len(rows)==m['forecast_rows'] and len({r['forecast_id'] for r in rows})==len(rows)
 assert set(r['model_id'] for r in rows)==set(MODELS)
 assert len({(r['model_id'],r['game_id'],r['player_id']) for r in rows})==len(rows),'DUPLICATE_MODEL_PLAYER_GAME'
 masks=[{(r['game_id'],r['player_id']) for r in rows if r['model_id']==model} for model in MODELS];assert all(x==masks[0] for x in masks)
 assert len(masks[0])==m['unique_players']==m['available_players']
 keys=['forecast_id','model_id','model_SHA256','player_id','name','position','team','opponent_team','game_id','kickoff_UTC','mean','median','p05','p95','information_cutoff_UTC','original_prepared_inference_UTC','inference_UTC','eligibility_information_cutoff_UTC','current_roster_observed_UTC','native_status_observed_UTC','issued_UTC','expires_UTC','history_support','latest_admitted_game','latest_game_age_at_feature_cutoff_days','feature_policy','hard_incumbent_fallback','any_imputed','sparse_history','profile_missing','prior_provenance','appearance_conditioning','information_policy','line','selected_side','probability_at_line','confidence','EV']
 projected=[]
 for r in rows:
  assert r['game_id']==TARGET and r['category']=='rec' and all(r[k] is None for k in ['line','selected_side','probability_at_line','confidence','EV'])
  assert all(isinstance(r[k],(float,int)) and not isinstance(r[k],bool) and math.isfinite(r[k]) and r[k]>=0 for k in ['mean','median','p05','p95'])
  assert clock(r['information_cutoff_UTC'])<=clock(r['original_prepared_inference_UTC'])<clock(r['inference_UTC'])<clock(r['issued_UTC'])<=clock(proof['server_check_completed_UTC'])<clock(r['kickoff_UTC'])
  assert clock(r['eligibility_information_cutoff_UTC'])<=clock(r['inference_UTC']) and clock(r['native_status_observed_UTC'])<=clock(r['issued_UTC'])
  projected.append({k:r.get(k) for k in keys})
 old=load(ROOT/OLD/'RUN.json',sources);assert old['forecast_rows']==75 and sha(ROOT/OLD/'FORECASTS.json.xz')=='4334c6e93d41487011e3bedb9a0a0173e38ccfcf5c568b30efbd0b73995be362'
 return dict(schema='C05-FROZEN-FOOTBALL-SHADOW-SITE-v1',state='GITHUB_SERVER_QUALIFIED_SHADOW',run_id=run_id,rows=projected,models=[dict(model_id=k,label=v) for k,v in MODELS.items()],players=m['unique_players'],games=m['games'],eligible_players=m['current_eligible_players'],available_players=m['available_players'],unavailable_players=m['unavailable_players'],new_fits=0,new_inference_rows=m['new_inference_rows'],real_offers=0,real_selections=0,primary_replacement=False,information_policy=m['information_policy'],model_feature_cutoff_UTC=m['information_cutoff_UTC'],football_source_cutoff_UTC=m['lineage']['football_source_cutoff_UTC'],eligibility_input_cutoff_UTC=m['eligibility_input_cutoff_UTC'],first_prepared_inference_UTC=min(r['original_prepared_inference_UTC'] for r in rows),first_inference_UTC=min(r['inference_UTC'] for r in rows),last_inference_UTC=max(r['inference_UTC'] for r in rows),native_status_observed_UTC=max(r['native_status_observed_UTC'] for r in rows),issued_UTC=m['issued_UTC'],server_persisted_UTC=proof['server_check_completed_UTC'],capture_commit=proof['capture_commit'],server_run_URL=proof['server_run_URL'],old_packet_preserved=dict(run_id=old['run_id'],rows=75,forecast_SHA256=sha(ROOT/OLD/'FORECASTS.json.xz')),source_bindings=sources)
def original_site():
 sources=[];r=load(BASE/'original-site/RECEIPT.json',sources);leaf=r['current_overlay_leaf'];meta=leaf['metadata']
 wrapper=load(BASE/'intake/A_INCUMBENT_PACKET_RECEIPT.json.xz',sources);ack=load(BASE/'intake/INCUMBENT_RECEIPT_ARITHMETIC.json',sources);d=wrapper['document']
 assert ack['status']=='PASS_PUBLIC_METADATA_ARITHMETIC_AND_DECLARED_CLOCK_ORDER' and ack['C_original_payload_downloaded'] is False and ack['served_consumer_verified_by_C_this_intake'] is False
 assert d['forecast_rows']==ack['forecast_rows']==sum(d['category_counts'].values())==sum(d['line_source_counts'].values())==1610
 assert d['unique_player_games']==ack['unique_player_games']==423 and d['unique_games']==ack['games']==14 and len(d['category_counts'])==ack['category_count']==11
 assert d['source_clock_verified_counts']=={'False':1610} and ack['qualified_actual_offer_selections_established_by_this_receipt']==0
 assert clock(d['generated_UTC'])<=clock(d['captured_UTC'])<clock(d['earliest_kickoff_UTC'])
 incumbent={k:d[k] for k in ['id','state','commit','compressed_sha256','decoded_sha256','generated_UTC','captured_UTC','earliest_kickoff_UTC','forecast_rows','unique_games','unique_player_games','category_counts','line_source_counts','source_clock_verified_counts','TopOver','TopUnder','model','schema']}
 incumbent.update(C_payload_downloaded=False,C_served_consumer_verified=False,qualified_actual_offer_selections_established=0,A_receipt_observed_UTC=wrapper['source']['observed_UTC'],metadata_arithmetic_checked_UTC=ack['at_UTC'],missing_parent_category=ack['missing_parent_category'])
 return dict(repository=r['repository'],checked_repository_tree=r['tree_SHA'],observed_UTC=leaf['observed_UTC'],repository_overlay_state=meta['state'],repository_overlay_selected_rows=meta['rows_count'],repository_overlay_week=meta['week'],actual_served_or_producer_use='NOT_VERIFIED_BY_METADATA',incumbent_packet_receipt=incumbent,original_site_writes=0,source_bindings=sources)
def export(validate=False):
 payload=dict(schema='C05-TIMING-CLOSURE-CONFIRM-SITE-v1',receipts=receipts(),current=current(),original_site=original_site(),primary_switches=0,Top_Picks_changes=0)
 body=encoded(payload);p=ROOT/'docs/data/timing-confirm-c05.json';buildp=ROOT/'docs/build.json';build=read(buildp);digest=hashlib.sha256(body).hexdigest()
 if validate:
  assert p.read_bytes()==body and build['timing_confirm_c05_SHA256']==digest,'C05_CANONICAL_OR_HASH_MISMATCH'
  html=(ROOT/'docs/context.html').read_text();js=(ROOT/'docs/context.js').read_text()
  for x in ['c05-status','c05-source-correction','c05-reception-summary','c05-completion-summary','c05-reception','c05-completion','c05-alias','c05-new-joins','c05-current-status','c05-model','c05-role','c05-search','c05-current','c05-current-clocks','c05-original-site']:
   assert f'id="{x}"' in html and x in js,'C05_RENDER_CONTRACT_MISMATCH:'+x
 else:p.write_bytes(body);build['timing_confirm_c05_SHA256']=digest;buildp.write_bytes(encoded(build))
 print('C05_SITE_'+('CANONICAL_VALID' if validate else 'WRITTEN'),len(body));return payload
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--validate',action='store_true');a=p.parse_args();export(a.validate)
