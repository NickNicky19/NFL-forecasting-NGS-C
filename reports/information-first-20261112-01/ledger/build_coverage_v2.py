"""Append admitted owner aggregates to the EXISTING common coverage ledger.

No grader/ranker/model is invoked. Original decoded CSV bytes are an exact
prefix, so every old field and entry identity remains unchanged.
"""
import collections,csv,gzip,hashlib,io,json,math,resource,time
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
BASE=ROOT/'reports/information-first-20261112-01'
OLD=ROOT/'reports/category-decision-release-01/W1_W9_AND_HISTORY_COVERAGE.csv.gz'
NEW=ROOT/'reports/category-decision-release-01/W1_W9_AND_HISTORY_COVERAGE_V2.csv.gz'
A=BASE/'A-intake/NORMALIZED_HISTORICAL_CONTROL_ROWS.json.gz'
B=BASE/'B-intake/INDEPENDENT_CORRECTED_GRADE_REVIEW_V1.json'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):
 b=Path(p).read_bytes();return json.loads(gzip.decompress(b) if str(p).endswith('.gz') else b)
def text(v):
 if v is None:return ''
 if isinstance(v,(dict,list)):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False)
 return str(v)
def dump(p,o):
 with Path(p).open('x') as f:json.dump(o,f,indent=2,allow_nan=False);f.write('\n')
def check_side(s):
 for k in ['selected','decided']:assert isinstance(s[k],int) and s[k]>=0
 if s['wins'] is not None and s['losses'] is not None:assert s['wins']+s['losses']==s['decided']
 else:assert s['decided']==0 and s['rate'] is None
 assert s['rate'] is None if not s['decided'] else math.isclose(s['rate'],s['wins']/s['decided'],rel_tol=1e-12)
def check_triad(o,u,c):
 for x in [o,u,c]:check_side(x)
 for k in ['selected','decided']:assert o[k]+u[k]==c[k]
 for k in ['wins','losses']:
  if c[k] is not None:assert (o[k] or 0)+(u[k] or 0)==c[k]
def side_fields(o,u,c):
 return dict(over_wins=o['wins'],over_losses=o['losses'],over_decided=o['decided'],over_rate=o['rate'],
  under_wins=u['wins'],under_losses=u['losses'],under_decided=u['decided'],under_rate=u['rate'],
  combined_wins=c['wins'],combined_losses=c['losses'],combined_decided=c['decided'],combined_rate=c['rate'])
def bind(p):return dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,SHA256=sha(p))
def finish(fields,owner,index,source,data):
 row={k:'' for k in fields};row.update({k:text(v) for k,v in data.items()})
 assert set(row)==set(fields)
 row['row_id']=hashlib.sha256(f'C-COVERAGE-V2|{owner}|{sha(source)}|{index}'.encode()).hexdigest()
 row['coverage_entry_id']=hashlib.sha256(json.dumps({k:v for k,v in row.items() if k!='coverage_entry_id'},sort_keys=True,separators=(',',':')).encode()).hexdigest()
 return row
def build():
 cpu=time.process_time();wall=time.monotonic();reg=load(HERE/'REGISTRATION.json')
 assert not NEW.exists(),'VERSIONED_LEDGER_ALREADY_EXISTS'
 raw=gzip.decompress(OLD.read_bytes());assert raw.endswith(b'\n')
 reader=csv.DictReader(io.StringIO(raw.decode()));old=list(reader);fields=reader.fieldnames
 assert len(old)==31527 and len({r['coverage_entry_id'] for r in old})==31527
 ar=load(A);br=load(B);assert len(ar)==528 and len(br['results'])==144
 aprojections={p:load(ROOT/p) for p in sorted({r['source_projection'] for r in ar})}
 badmit=load(BASE/'B-intake/ADMISSION.json');intmeta=badmit['INT_measurement']
 bsource=load(BASE/'B-intake/OFFICIAL_INTERCEPTION_EVIDENCE_V1.json')
 assert bsource['missing_supported_explicit_zero']==46 and br['side_or_line_changes']==0
 groups=collections.defaultdict(dict)
 for r in br['results']:
  key=(r['strategy'],str(r['window']));assert r['side'] not in groups[key];groups[key][r['side']]=r
 assert len(groups)==48
 board={w:g['Combined']['selected'] for (s,w),g in groups.items() if s=='CONSTANT_OVER_FULL144'}
 selected86={w:g['Combined']['selected'] for (s,w),g in groups.items() if s=='CONSTANT_OVER_ON_SAME86'}
 added=[];bmap=[];amap=[]
 for index,((strategy,window),g) in enumerate(sorted(groups.items())):
  assert set(g)=={'over','under','Combined'};o,u,c=g['over'],g['under'],g['Combined'];check_triad(o,u,c)
  original=strategy in ['CURRENT_PUBLISHED_PRESENCE_V5','RECORDED_TOP_FLAGS_ORIGINAL']
  top=strategy.startswith('RECORDED_TOP_FLAGS');control=strategy.startswith('CONSTANT_')
  same86=strategy.endswith('_ON_SAME86');eligible=selected86[window] if same86 else board[window]
  procedure=('B::ARCHIVED_ORIGINAL_WEBSITE_LEANS_UNCHANGED_PREDICTION_LINE_SIDE' if not top and not control else
             'B::ARCHIVED_ORIGINAL_RECORDED_TOP_FLAGS' if top else 'B::'+strategy)
  weeks=sorted(int(w) for (s,w),q in groups.items() if s==strategy and w!='ALL' and q['Combined']['decided']>0)
  metrics=dict(source_side_triads=g,actual_scored_weeks=weeks if window=='ALL' else ([int(window)] if c['decided'] else []),
    requested_period='2026_REG_W5_W9',outer_board=board[window],original_stored_sides=selected86[window],
    changes='MEASUREMENT_CORRECTION_ONLY;UNCHANGED_ORIGINAL_PREDICTIONS_LINES_SIDES' if not control else 'CONSTANT_SIDE_CONTROL_ON_DECLARED_MASK',
    source_index_ref=badmit['actual_research_ref'],source_scoring_commit=intmeta['source_commit'],source_masks={k:intmeta[k] for k in ['source_mask_SHA256','board_mask_SHA256','labels_SHA256']},
    tier_limits='DK-labelled stored lines:85at0.5,one1.5;main/alternate tier,quote timing and executable availability unverified;53referenceprops separate',
    unknown_to_zero_by_C=False,explicit_zero_qualification_owner='B:dual_source_official_rows',new_forecasts=0,new_original_NFL_games=0,
    numerical_scores=None,probability_scores=None,top_flags_not_exact_changed_ranker_qualification=top)
  data=dict(owner='B',category='pass_int',procedure_id=procedure,product='RECORDED_TOP_FLAGS' if top else 'CONSTANT_SIDE_CONTROL' if control else 'ORIGINAL_ARCHIVED_SIDE_POLICY',
   history='FROZEN_ORIGINAL_METHOD_HISTORY_UNVERIFIED;NO_RECONSTRUCTION_OR_REFIT',role_scope='QB',source_panel='B_ORIGINAL_144_BOARD::'+('MATCHED_SELECTED86' if same86 else 'FULL144')+'::'+window,
   book='DraftKings-labelled;main-alt-tier-unverified',evidence_tier='TIMING_UNVERIFIED_RETAINED_ACTUAL_LINE_FINAL_LABEL_DIAGNOSTIC;PUBLIC_AGGREGATE_ARITHMETIC_ONLY',
   season=2026,week=window,status='NO_SCORED_OUTCOME_NOT_TEST' if not c['decided'] else 'B_INDEPENDENT_OWNER_LOCAL_AGGREGATE_ADMITTED',eligible=eligible,
   available=eligible if not top else None,selected=c['selected'],scored=c['decided'],unknown=c['unknown'],abstained=None if top else eligible-c['selected'],fallback=None,
   games=(72 if strategy.endswith('_FULL144') else 61 if not top else None) if window=='ALL' else None,player_games=c['selected'],
   source_artifacts=str(B.relative_to(ROOT))+';'+str((BASE/'B-intake/ADMISSION.json').relative_to(ROOT)),
   verification_limit='C received permitted commitments and independent B calculation; no private row/source-body/quote-time parity. No new model gain or release qualification.',
   source_evidence_class='B_OFFICIAL_LABEL_CORRECTION_ON_UNCHANGED_STORED_ACTUAL_LINES',new_procedure_coverage_not_new_games=True,
   required_next_owner_action='Original website owner admits explicit-zero source evidence and append-only corrected cache/grade, verifies served bytes; no model switch inferred.',
   row_kind='OWNER_REPORTED_MEASUREMENT_VERSION' if not control else 'MATCHED_CONSTANT_SIDE_CONTROL',grading_version='ORIGINAL_PRESENCE_V5_LABELS' if original else intmeta['grade_version'],
   issuance_state='ORIGINAL_DECISION_RECORD_RETAINED;QUOTE_TIMING_MAINLINE_AND_SETTLEMENT_UNVERIFIED',additional_metrics=metrics,**side_fields(o,u,c))
  row=finish(fields,'B',index,B,data);added.append(row);bmap.append(dict(index=index,strategy=strategy,window=window,coverage_entry_id=row['coverage_entry_id']))
 for index,r in enumerate(ar):
  o,u,c=r['OVER'],r['UNDER'],r['COMBINED'];check_triad(o,u,c);projection=aprojections[r['source_projection']]
  assert r['no_new_2026_or_original_issued_record'] is True
  season=2023 if '2023' in r['source_period'] or '2023' in r['source_projection'] else 2024
  assert all(1<=w<=18 for w in r['actual_scored_weeks'])
  if season==2023:assert set(r['actual_scored_weeks'])<=set(range(6,19))
  fallback=r.get('fallback_selected')
  if fallback is None and 'fallback' in r:fallback=sum(v for k,v in r['fallback'].items() if k)
  roles='|'.join(sorted(r.get('role_counts',{}))) if r['category']=='rush_att' else 'QB'
  metrics=dict(source_summary=r,source_projection_SHA256=sha(ROOT/r['source_projection']),actual_scored_weeks=r['actual_scored_weeks'],
      source_period=r['source_period'],comparison_mask=r.get('comparison_mask'),own_population_only=True,
      numerical_product=r.get('numerical'),probability_scores_not_inferred_from_point=True,
      source_original_limit=projection.get('original_source_limit'),source_population=projection.get('population',projection.get('query_population')),
      source_procedure_bindings=projection.get('procedure_bindings'),source_offer_policy=projection.get('offer_policy'),
      source_top6_timing=projection.get('Top6_weekly_timing'),source_probability_numerical_views=projection.get('numerical_and_probability_metrics') if r['category']=='rush_att' and r['week_view']=='ALL' else None,
      unavailable=r.get('unavailable'),outer_offered_board=r.get('outer_offered_board'),new_original_NFL_games=0)
  data=dict(owner='A',category=r['category'],procedure_id=r['procedure_id'],product=r['product_policy'],history='CURRENT_VINTAGE_FIXED_7D_EARLIER_HISTORY;EXACT_OWNER_PROCEDURE_BINDINGS_IN_ADDITIONAL_METRICS',
   role_scope=roles,source_panel='A::'+r['source_period']+'::'+str(r.get('comparison_mask') or 'OWN_POLICY_MASK'),book='NAMED_HISTORICAL_BOOK_POLICY;SEE_SOURCE_BINDING',
   evidence_tier=r['source_evidence_tier'],season=season,week=r['week_view'],status=r['execution_state'],eligible=r['eligible'],
   available=r['eligible']-r['unavailable'] if r.get('eligible') is not None and r.get('unavailable') is not None else None,
   selected=r.get('selected',c['selected']),scored=c['decided'],unknown=r.get('unknown'),abstained=r.get('abstentions'),fallback=fallback,games=r.get('games'),player_games=r.get('player_games'),
   source_artifacts=str(A.relative_to(ROOT))+';'+r['source_projection'],verification_limit='Owner-local permitted aggregate arithmetic only; no private row/fit parity, historical quote-time or original-issuance claim. Full/weekly/Top6/role views overlap and cannot be pooled as independent observations.',
   source_evidence_class='HISTORICAL_NAMED_BOOK_ACTUAL_LINE_DIAGNOSTIC_QUOTE_TIME_UNVERIFIED',new_procedure_coverage_not_new_games=True,
   required_next_owner_action='Maintain exact supported historical and source gaps; no new primary or changed TopPicks qualification from exposed replay alone.',row_kind='HISTORICAL_OWNER_AGGREGATE_VIEW',
   grading_version='A_RETAINED_CONTROL_FINAL_LABELS_V1',issuance_state='RETROSPECTIVE_RECONSTRUCTION;NO_ORIGINAL_ISSUANCE',additional_metrics=metrics,**side_fields(o,u,c))
  row=finish(fields,'A',index,A,data);added.append(row);amap.append(dict(index=index,procedure=r['procedure_id'],source_period=r['source_period'],week_view=r['week_view'],coverage_entry_id=row['coverage_entry_id']))
 assert len(added)==576 and len({r['coverage_entry_id'] for r in old+added})==32103
 buf=io.StringIO(newline='');writer=csv.DictWriter(buf,fieldnames=fields,lineterminator='\r\n');writer.writerows(added)
 combined=raw+buf.getvalue().encode();compressed=gzip.compress(combined,compresslevel=9,mtime=0)
 assert len(compressed)<=reg['budget']['retained_bytes_max']
 with NEW.open('xb') as f:f.write(compressed)
 # Separate readback path checks the original byte prefix and maps every new
 # entry directly to its source counters, rather than trusting builder totals.
 decoded=gzip.decompress(NEW.read_bytes());assert decoded[:len(raw)]==raw
 check=list(csv.DictReader(io.StringIO(decoded.decode())));assert check[:31527]==old and len(check)==32103
 for i,row in enumerate(check[31527:]):
  source=groups[(bmap[i]['strategy'],bmap[i]['window'])] if i<48 else ar[i-48]
  for side,prefix in [('over' if i<48 else 'OVER','over'),('under' if i<48 else 'UNDER','under'),('Combined' if i<48 else 'COMBINED','combined')]:
   for k in ['wins','losses','decided','rate']:assert row[prefix+'_'+k]==text(source[side][k])
  expected=hashlib.sha256(json.dumps({k:v for k,v in row.items() if k!='coverage_entry_id'},sort_keys=True,separators=(',',':')).encode()).hexdigest();assert row['coverage_entry_id']==expected
 cpu=time.process_time()-cpu;rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
 assert cpu<=reg['budget']['CPU_seconds_max'] and rss<=reg['budget']['RSS_bytes_max']
 sources=[OLD,A,B,BASE/'B-intake/ADMISSION.json',BASE/'B-intake/OFFICIAL_INTERCEPTION_EVIDENCE_V1.json',BASE/'A-intake/A_INTAKE_RECEIPT.json',BASE/'A-intake/SOURCE_PROJECTION_BINDINGS.json',*(ROOT/p for p in aprojections)]
 receipt=dict(id=reg['id'],completed_UTC=datetime.now(timezone.utc).isoformat(),builder_SHA256=sha(Path(__file__)),inputs=[bind(p) for p in sources],output=bind(NEW),
  prior_rows=31527,old_decoded_csv_prefix_exact=True,old_fields_exact=True,appended_B_complete_triads=48,B_source_side_views_preserved=144,appended_A_complete_views=528,total_rows=32103,unique_complete_entry_ids=32103,
  A_zero_decided_not_tests=sum(not r['COMBINED']['decided'] for r in ar),B_zero_decided_not_tests=sum(not q['Combined']['decided'] for q in groups.values()),
  added_seasons_by_owner={'A':[2023,2024],'B':[2026]},B_actual_windows=[5,6,7,8,9],new_2026_evaluation_weeks=0,new_original_NFL_games=0,new_grader_calls=0,new_fits=0,new_inference=0,network_reads=0,
  private_row_parity=False,unmatched_A_B_pooled_or_ranked=False,qualification='PUBLIC_OWNER_AGGREGATE_ARITHMETIC_AND_EXACT_SOURCE_BINDINGS_ONLY',
  CPU_seconds=cpu,wall_seconds=time.monotonic()-wall,peak_RSS_bytes=rss,readback={'source_count_fields_checked':len(added)*12,'all_side_rates_reconciled':True,'complete_entry_hashes_checked':len(added),'no_empty_side_rate_filled':True})
 dump(HERE/'BUILD_RECEIPT.json',receipt);dump(HERE/'APPEND_ENTRY_MAP.json',dict(B=bmap,A=amap));print(json.dumps({k:v for k,v in receipt.items() if k not in ['inputs','readback']},indent=2))

if __name__=='__main__':build()
