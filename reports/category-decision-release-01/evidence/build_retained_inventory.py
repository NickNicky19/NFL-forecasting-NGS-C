"""Bounded reconciliation of already-admitted aggregate/qualification records.
No forecast generation, NFL fitting, row-level grading or source collection.
"""
from pathlib import Path
import csv,gzip,hashlib,io,json,lzma,collections,datetime,time
ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).resolve().parent
SOURCES=[
'reports/abc-championship/execution-closure-02/QUALIFICATION_TABLE.json.gz',
'reports/abc-championship/execution-closure-02/CATEGORY_PRODUCT_DECISIONS.json',
'reports/abc-championship/execution-closure-02/A_PANEL_PRODUCT_RANKINGS.json.gz',
'reports/abc-championship/continuation-v2/A_W1_W7_ARCHIVED_SCORES.json.gz',
'reports/profile-timing-closure-confirm-01/intake/HEADLINE.json',
'reports/profile-timing-closure-confirm-01/intake/QUALIFICATION_AMENDMENT.json',
'reports/profile-timing-closure-confirm-01/SOURCE_TIER_CORRECTION.json',
'reports/abc-championship/METHOD_ROSTER-v2-C-1.json',
'reports/abc-championship/METHOD_COVERAGE.json',
'reports/player-context-matchup-01/PRODUCT_QUALIFICATION.json',
'reports/profile-increment-v2/METHOD_ROSTER_V2.json',
'reports/profile-closure-next-02/METHOD_ROSTER_AMENDMENT.json',
'reports/profile-closure-next-02/PRODUCT_QUALIFICATION.json',
'reports/profile-timing-closure-confirm-01/PRODUCT_QUALIFICATION.json',
'protocol/ACTUAL_ACCURACY_POLICY_V6.json',
'reports/abc-championship/shared-intake-v3/A_HISTORICAL_SCORES.json.gz',
'reports/abc-championship/shared-intake-v3/A_HISTORICAL_PAIRED_CONTROLS.json',
'reports/abc-championship/shared-intake-v3/HISTORICAL_RAW_LEADERS.json.gz',
]
CATEGORIES=['pass_yd','pass_td','pass_cmp','pass_att','pass_int','rush_yd','rush_att','rec','rec_yd','rush_rec_yd','anytime_td','fpts']
def load(rel):
 p=ROOT/rel;b=p.read_bytes()
 if p.suffix=='.gz':b=gzip.decompress(b)
 if p.suffix=='.xz':b=lzma.decompress(b)
 return json.loads(b)
def write(name,x):
 (OUT/name).write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')
def gz(name,blob):
 (OUT/name).write_bytes(gzip.compress(blob,mtime=0))
def si(v):
 try:return int(v)
 except (TypeError,ValueError):return None
def partition(w,l):
 n=w+l;return dict(wins=w,losses=l,decided=n,rate=w/n if n else None)
def bound(rel):
 p=ROOT/rel;return dict(path=rel,bytes=p.stat().st_size,SHA256=hashlib.sha256(p.read_bytes()).hexdigest())
def known_book(s):
 hits=[v for v in ['pinnacle','draftkings','fanduel'] if v in s.lower()]
 return hits[0] if len(hits)==1 else None
start=time.process_time();q=load(SOURCES[0]);rs=q['rows'];assert len({r['row_id'] for r in rs})==len(rs)
actual=[r for r in rs if str(r.get('product','')).startswith('ACTUAL_LINE_DIRECTION') and any(t[0]==2026 for t in r.get('tested_season_weeks',[]))]
counts=dict(id='CATEGORY-RELEASE-RETAINED-INVENTORY-COUNTS-v1',source=bound(SOURCES[0]),total_product_policy_profiles=len(rs),distinct_procedure_id_strings=len({r['procedure_id'] for r in rs}),by_owner=dict(collections.Counter(r['owner'] for r in rs)),by_product=dict(collections.Counter(r['product'] for r in rs)),by_reported_floor=dict(collections.Counter(r['five_week_floor'] for r in rs)),current_2026_explicit_actual_direction_profiles=len(actual),current_actual_by_owner=dict(collections.Counter(r['owner'] for r in actual)),current_actual_by_category=dict(collections.Counter(r['category'] for r in actual)),current_actual_reported_floor_by_owner={o:dict(collections.Counter(r['five_week_floor'] for r in actual if r['owner']==o)) for o in 'ABC'},do_not_inflate='Profiles/procedure-ID strings include output/history/policy/source views; these are NOT independent learner-family counts or extra games.',scope='Programmatic reconciliation of all8072 retained qualification rows, plus named amendment files. It is not every test ever executed; private/unlocated/invalid/incompatible states remain.')
counts['reported_floor_scope']='As-of retained shared-v2 table across its declared season set; not proof of five current-season actual-offer weeks. Newer C03/C04/Btiming deltas and source corrections must be composed separately.'
write('RETAINED_INVENTORY_COUNTS.json',counts)
# Small lossless policy-profile projection retaining exact source bindings; no predictions/labels.
profiles=[]
for r in actual:
 profiles.append({k:r.get(k) for k in ['row_id','owner','procedure_id','category','product','role_scope','history','policy','source_panel','evidence_tier','source_artifacts','tested_season_weeks','scored_cases','own_side_record','operational_export','same_decided_constants','strongest_bound_model_control','season_records','windows','scored_week_count','current_2026_scored_week_count','five_week_floor','attempted_season_weeks','zero_selection_weeks','unresolved_only_weeks']})
gz('RETAINED_ACTUAL_DIRECTION_PROFILES.json.gz',(json.dumps(profiles,separators=(',',':'),allow_nan=False)+'\n').encode())
# Every requested current-season week remains visible, even absent/pending records.
fields=['row_id','owner','category','procedure_id','product','history','role_scope','source_panel','book','evidence_tier','season','week','status','eligible','available','selected','scored','unknown','abstained','fallback','games','player_games','over_wins','over_losses','under_wins','under_losses','source_artifacts','verification_limit']
s=io.StringIO();w=csv.DictWriter(s,fieldnames=fields);w.writeheader()
for r in actual:
 weekly={(int(x.get('season',2026)),int(x['week'])):x for x in r.get('week_records',[]) if 'week' in x}
 for wk in range(1,9):
  x=weekly.get((2026,wk));parts=x.get('sides',{}) if x else {};states=x.get('states',{}) if x else {};source=r.get('source_panel','')
  status='COMPLETED_REPORTED_ACTUAL_DIRECTION' if x and (x.get('scored') or 0)>0 else 'ATTEMPTED_ZERO_OR_UNRESOLVED' if x else 'MISSING_EXACT_PRODUCT_WEEK'
  if source=='A_FIXED_W1_W7_ARCHIVED_POINT_PANEL' and x:status+=';ARCHIVED_SOURCE_WEEK_CLASSIFICATION_NEEDS_LATEST_OWNER_BINDING'
  unknown_values=[v for k,v in states.items() if isinstance(v,(int,float)) and any(t in k for t in ['UNKNOWN','UNRESOLVED','MISSING_ACTUAL'])]
  unknown=sum(unknown_values) if unknown_values else None
  row={k:r.get(k) for k in ['row_id','owner','category','procedure_id','product','history','role_scope','source_panel','evidence_tier','source_artifacts']}
  for k,v in list(row.items()):
   if isinstance(v,(list,dict)):row[k]=json.dumps(v,separators=(',',':'))
  row.update(book=known_book(source),season=2026,week=wk,status=status,eligible=x.get('eligible') if x else None,available=x.get('available') if x else None,selected=x.get('selected') if x else None,scored=x.get('scored') if x else None,unknown=unknown,abstained=states.get('ABSTAIN') if x else None,fallback=x.get('fallback') if x else None,games=x.get('games') if x else None,player_games=x.get('player_games') if x else None,over_wins=parts.get('OVER',{}).get('wins'),over_losses=parts.get('OVER',{}).get('losses'),under_wins=parts.get('UNDER',{}).get('wins'),under_losses=parts.get('UNDER',{}).get('losses'),verification_limit='Owner-local public aggregates; no private identities/source clocks/fit parity implied. Missing fields stay null.')
  w.writerow(row)
gz('RETAINED_W1_W8_COVERAGE.csv.gz',s.getvalue().encode())
# Re-aggregate old A saved weekly scores without pretending to requalify their source.
a=load(SOURCES[3]);sub=[]
lookup={r['procedure_id']:r for r in rs if r.get('source_panel')=='A_FIXED_W1_W7_ARCHIVED_POINT_PANEL'}
for r in a:
 weeks=[v for v in r['week_rows'] if 1<=int(v['week'])<=5];assert all(v['category']==r['category'] for v in weeks)
 over=partition(sum(int(v['over_wins']) for v in weeks),sum(int(v['over_losses']) for v in weeks));under=partition(sum(int(v['under_wins']) for v in weeks),sum(int(v['under_losses']) for v in weeks));combined=partition(over['wins']+under['wins'],over['losses']+under['losses'])
 assert combined['decided']==sum(int(v['decided']) for v in weeks)
 p=lookup.get(r['procedure_id'],{});selected=sum(int(v['opportunities']) for v in weeks)
 sub.append(dict(category=r['category'],origin='A',procedure_id=r['procedure_id'],method=r['method'],output=r['product'],history=p.get('history',r['history']),role_scope=p.get('role_scope',r['role_policy']),policy=p.get('policy','P1_UNROUNDED_POINT_VS_EXACT_RETAINED_THRESHOLD'),requested_weeks=list(range(1,9)),actually_scored_partitions=[int(v['week']) for v in weeks if int(v['decided'])>0],source_panel='A_FIXED_W1_W7_ARCHIVED_POINT_PANEL::FIRST_FIVE_WEEK_SUBPANEL',source_classification='SOURCE_QUALIFICATION_PENDING_LATEST_A_BINDING;NOT_AUTOMATICALLY_SAME_AS_C03_ANNUAL_BOARD',OVER=over,UNDER=under,COMBINED=combined,eligible=selected,selected=selected,available=None,unknown=sum(int(v.get('over_unresolved',0))+int(v.get('under_unresolved',0)) for v in weeks),abstained=sum(int(v.get('no_lean',0)) for v in weeks),pushes=sum(int(v.get('over_pushes',0))+int(v.get('under_pushes',0)) for v in weeks),fallback=None,games=None,player_games=None,reported_full_seven_week_games=r['games'],same_decided_constants=dict(ALWAYS_OVER=over['wins']+under['losses'],ALWAYS_UNDER=over['losses']+under['wins'],decided=combined['decided']),evidence_tier='TIMING_UNVERIFIED_ARCHIVED_SCORE_PARTITIONS;SOURCE_WEEK_CLASSIFICATION_NOT_REQUALIFIED',source=bound(SOURCES[3]),note='Counts-only reuse of fixed predictions/saved grades; no new NFL games, fits, forecasts or source qualification. Scientific game-count support cannot be inferred from the full seven-week total.'))
write('A_ARCHIVED_FIRST5_SUBPANELS.json',sub)
leaders=[]
for c in CATEGORIES:
 xs=[r for r in sub if r['category']==c and r['COMBINED']['decided']]
 if not xs:leaders.append(dict(category=c,status='NO_ACTUAL_DIRECTION_IN_THIS_SOURCE'));continue
 best=max(r['COMBINED']['rate'] for r in xs);win=[r for r in xs if r['COMBINED']['rate']==best]
 leaders.append(dict(category=c,status='RAW_OBSERVED_FIRST5_SUBPANEL_ONLY;SOURCE_ADMISSION_PENDING',leaders=[dict(procedure_id=r['procedure_id'],method=r['method'],output=r['output'],role_scope=r['role_scope'],OVER=r['OVER'],UNDER=r['UNDER'],COMBINED=r['COMBINED'],same_decided_constants=r['same_decided_constants']) for r in win],selection_exposure='Already inspected retrospective data; no earlier-executable method router inferred.'))
write('A_ARCHIVED_FIRST5_SCOPED_LEADERS.json',leaders)
# Already-admitted C05 actual annual and mixed views; new timing joins belong to root intake.
head=load(SOURCES[4]);write('ADMITTED_C05_ANNUAL_REFERENCE.json',dict(id='CATEGORY-RELEASE-C05-ANNUAL-REFERENCES-v1',C03_reception_annual=head['C03_reception_annual_all_procedures'],B_prior_completion_annual=head['B_prior_completion_annual_all_procedures'],qualification_amendment=load(SOURCES[5]),new_timing_join_status='Superseded by the current wave intake when actual receipts are read; do not reuse C05 stale pending status.'))
# Explicit scope table, not a new universal leaderboard or final release decision.
source_status=[]
for c in CATEGORIES:
 ca=[r for r in actual if r['category']==c]
 source_status.append(dict(category=c,retained_explicit_actual_direction_profiles=len(ca),owners=sorted({r['owner'] for r in ca}),reported_source_panels=len({r['source_panel'] for r in ca}),reported_actual_weeks_by_owner={o:sorted({int(v[1]) for r in ca if r['owner']==o for v in r['tested_season_weeks'] if v[0]==2026}) for o in sorted({r['owner'] for r in ca})},qualification='No calendar-week union across different procedures/outputs/policies/horizons. Use each profile row.',finite_next_action=('Qualify exact rushing-or-receiving anytime offer and actually offered sides; event/numerical history alone does not qualify O/U.' if c=='anytime_td' else 'Qualify exact nick-chart-ppr-v1 offer and complete chart labels; generic fantasy is incompatible.' if c=='fpts' else 'Root merges refreshed exact owner receipts with named source panels and selects strongest supported category/product under existing provisional and support policies.')))
write('TWELVE_CATEGORY_RETAINED_SCOPE.json',source_status)
# Older selective/historical contenders remain visible without pooling overlapping windows.
historical=load('reports/abc-championship/shared-intake-v3/A_HISTORICAL_SCORES.json.gz')
ha=[r for r in historical if r['week_view']=='ALL']
gz('HISTORICAL_CUMULATIVE_ROWS.json.gz',(json.dumps(ha,separators=(',',':'),allow_nan=False)+'\n').encode())
write('HISTORICAL_PANEL_SCOPE.json',dict(id='CATEGORY-RELEASE-HISTORICAL-REFERENCE-SCOPE-v1',score_cells=len(historical),cumulative_cells=len(ha),source=bound('reports/abc-championship/shared-intake-v3/A_HISTORICAL_SCORES.json.gz'),paired_controls=bound('reports/abc-championship/shared-intake-v3/A_HISTORICAL_PAIRED_CONTROLS.json'),recorded_raw_leaders=bound('reports/abc-championship/shared-intake-v3/HISTORICAL_RAW_LEADERS.json.gz'),panels=[dict(period_id=p,category=c,procedures=len([r for r in ha if r['period_id']==p and r['category']==c]),actual_weeks=sorted({v for r in ha if r['period_id']==p and r['category']==c for v in r['actual_weeks']})) for p,c in sorted({(r['period_id'],r['category']) for r in ha})],limits=['Historical/full/early windows overlap and cannot be summed twice.','Market-assisted or hybrid M/FS policies and selective coverage are not interchangeable with a full-board football-only product.','Every candidate retains own sides/selected coverage; zero-selection weeks do not qualify.','Earlier-only retained2024model-year fit and correction history are bound by the source, not re-inferred or refitted here.','No2022/2023/2025 actual-offer coverage is invented from training or numerical history.']))

manifest=dict(id='CATEGORY-RELEASE-RETAINED-EVIDENCE-MANIFEST-v1',created_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),sources=[bound(f) for f in SOURCES],code=bound(str(Path(__file__).relative_to(ROOT))),new_fits=0,new_forecast_inference=0,new_grading=0,new_NFL_observations=0,new_source_requests=0,CPU_seconds=time.process_time()-start,explicit_limits=['Old archived seven-week labels remain historical reports, not newly authenticated actual offers.','C05 W1-W5 correction applies to the named annual longer-board source, not every other source.','No new A/B timing score is inferred here; parent intake supplies exact current receipt.','Missing games/weekly counts/fallback stay null.','Family counts cannot be recovered by counting output/policy/profile rows.','Constant-side records are matched diagnostic controls, not automatic production policies.'])
write('MANIFEST.json',manifest)
print(json.dumps({'profiles_reviewed':len(rs),'explicit_2026_actual_profiles':len(actual),'coverage_rows':len(actual)*8,'A_first5_subpanels':len(sub),'CPU_seconds':manifest['CPU_seconds']}))
