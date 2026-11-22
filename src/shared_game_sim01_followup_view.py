"""Bounded secondary saved-output view; no fits, sampler or source retrieval.

B's original forecast horizons are NOT the common simulator T90 origin. These
are explicitly different-horizon timing-unverified development diagnostics.
Original execution-v1 bytes stay unchanged. Protected grades/memberships stay
private; the public result is an aggregate projection of the existing grader.
"""
from __future__ import annotations
import collections, datetime, gzip, hashlib, json, math, os, resource, subprocess, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PUB=ROOT/'reports/shared-game-sim-01/follow-through-v1'
PRIV=ROOT/'private/shared-game-sim-01/follow-through-v1'
SCOPE='DIFFERENT_HORIZON_TIMING_UNVERIFIED_DEVELOPMENT_DIAGNOSTICS'
PACKET_SHA='4847b6a6152e7db3830f93bf451e27c6127fec274b6631e7c6055bb6daaec60d'
CASE_SHA='19ccf34b3037e1790ee3b2bf61d3357f33e63916779c2f36023a232f6a66ea18'
FREEZE_SHA='83468a702b6c52ea151511e6ad4ab086f4b1abf64d2039cd326f86ff0b02f6ad'
def sha(b):return hashlib.sha256(b).hexdigest()
def save(p,d):
 p.parent.mkdir(parents=True,exist_ok=True);b=(json.dumps(d,separators=(',',':'),allow_nan=False)+'\n').encode()
 p.write_bytes(gzip.compress(b,mtime=0) if p.name.endswith('.gz') else b)
 return dict(bytes=p.stat().st_size,SHA256=sha(p.read_bytes()))
def public(x):
 if isinstance(x,dict):return {k:public(v) for k,v in x.items() if k not in ('case_ids','raw_grades','selection_records','membership','origin')}
 if isinstance(x,list):return [public(v) for v in x]
 return x
def pointside(x,line):return 'OVER' if x>line else 'UNDER' if x<line else 'ABSTAIN'
def lawside(p):return 'OVER' if p['over']>p['under'] else 'UNDER' if p['under']>p['over'] else 'ABSTAIN'
def worker():
 from shared_game_sim01_metrics import build_raw_grades,evaluate,_pair,_summarize
 from shared_game_sim01_report import numeric_pair
 from shared_game_sim01_research_pairs import probability_pair
 p=PUB/'intake';body=(p/'B_ORDINAL_FROZEN_OUTPUTS_V3.json.gz').read_bytes()
 assert len(body)==90346 and sha(body)==PACKET_SHA
 packet=json.loads(gzip.decompress(body));fb=(p/'B_JOIN_FREEZE_V4.json').read_bytes()
 assert sha(fb)==packet['freeze_sha256']==FREEZE_SHA
 casesbody=(ROOT/'private/shared-game-sim-01/views/comparison_inputs/cases.jsonl').read_bytes()
 assert sha(casesbody)==packet['canonical_case_sha256']==CASE_SHA
 cases=[json.loads(x) for x in casesbody.splitlines()];assert len(cases)==packet['full_case_count']==3474
 freeze=json.loads(fb);roster={x['candidate_id']:x for x in freeze['candidates']}
 assert len(roster)==len(packet['candidates'])==36
 assert {x['candidate_id'] for x in packet['candidates']}==set(roster)
 av=0;triples=0;clock=collections.Counter();timing=collections.Counter();pred={};products=[];empties=[]
 for c in packet['candidates']:
  cid=c['candidate_id'];cat=c['category'];r=roster[cid]
  assert cat==r['category'] and c['exact_procedure_id']==r['procedure']
  ids=[x['case_ordinal'] for x in c['rows']];assert len(ids)==len(set(ids))
  assert set(ids)=={i for i,x in enumerate(cases) if x['identity']['category']==cat}
  rows=c['rows'];haslaw=any(x.get('probabilities') is not None for x in rows)
  variants=[('PRIMARY',c['primary_output'])]
  if haslaw and 'law' not in c['primary_output']:variants.append(('LAW','exact_saved_threshold_law'))
  if any(x.get('mean_sibling') is not None for x in rows) and c['primary_output']!='mean':variants.append(('MEAN','mean_sibling'))
  if any(x.get('median_sibling') is not None for x in rows):variants.append(('MEDIAN','median_sibling'))
  for x in rows:
   assert cases[x['case_ordinal']]['identity']['category']==cat
   if x['status']=='AVAILABLE':
    av+=1;clock[x['source_clock_state']]+=1;timing[x['primary_T90_comparability']]+=1
    triples+=x.get('probabilities') is not None
  for variant,typ in variants:
   method='B::'+cid+'::'+variant;out=[]
   for x in rows:
    case=cases[x['case_ordinal']];q=case['identity'];ok=x['status']=='AVAILABLE';value=x.get('point');prob=None
    if variant=='MEAN':value=x.get('mean_sibling');ok=ok and value is not None
    elif variant=='MEDIAN':value=x.get('median_sibling');ok=ok and value is not None
    elif variant=='LAW' or 'law' in c['primary_output']:prob=x.get('probabilities');ok=ok and prob is not None
    if variant=='LAW':value=None
    if variant=='PRIMARY' and 'law' in c['primary_output']:value=None
    if ok and value is None and prob is None:raise ValueError('NO_TYPED_OUTPUT')
    fb=x.get('fallback');fallback=fb not in ('none',None,'')
    out.append(dict(case_id=case['case_id'],category=cat,available=ok,point=value if ok else None,probabilities=prob if ok else None,selected_side=(lawside(prob) if prob is not None else pointside(value,q['line'])) if ok else None,native=ok and not fallback,fallback=fallback if ok else False,unavailable_reason=None if ok else x['status'],source_binding=cid))
   pred[method]=out
   products.append(dict(method=method,candidate_id=cid,procedure=c['exact_procedure_id'],category=cat,product=typ,variant=variant,roles=r['roles'],rows=len(rows),available=sum(x['available'] for x in out),source_scope=SCOPE))
   if not rows:empties.append(dict(method=method,category=cat,state='NO_CATEGORY_OFFERS_IN_FRAME'))
 assert av==5338 and triples==592
 assert timing=={'ORIGINAL_ORIGIN_DIFFERS;C_ADMISSION_REQUIRED':4131,'CLOCK_FIELDS_NOT_SUFFICIENT_FOR_AUTHENTICATION':1207}
 assert clock=={'DECLARED_KICKOFF_LEFT_LIMIT;SOURCE_AVAILABILITY_PARTIAL_OR_NOT_T90':1851,'DECLARED_KICKOFF_LEFT_LIMIT;OBSERVED_LATEST_BEFORE_T90':3487}
 old=json.loads((ROOT/'private/shared-game-sim-01/typed_all_predictions.json').read_bytes())
 for k in ('W0','W1','ALWAYS_OVER','ALWAYS_UNDER'):pred[k]=old[k]
 binding=save(PRIV/'B_typed_predictions.json.gz',pred)
 assert json.loads(gzip.decompress((PRIV/'B_typed_predictions.json.gz').read_bytes()))==pred
 save(PUB/'B_PREDICTION_BINDING.json',dict(state='FROZEN_DERIVED_SAVED_OUTPUTS_BEFORE_TARGET_GRADING',source_packet_SHA256=PACKET_SHA,case_SHA256=CASE_SHA,freeze_SHA256=FREEZE_SHA,typed_private_binding=binding,nominees=36,primary_available=av,retained_probability_triples=triples,source_clock_counts=clock,primary_T90_comparability=timing,scope=SCOPE,empty_products=empties))
 outcomes=[json.loads(x) for x in (ROOT/'private/shared-game-sim-01/views/grading_only/outcomes.v1.jsonl').read_bytes().splitlines()]
 assert len(outcomes)==3474 and sum(x['actual'] is None for x in outcomes)==464
 raw=build_raw_grades(cases,outcomes,pred);rawbinding=save(PRIV/'B_raw_grades.json.gz',raw)
 assert json.loads(gzip.decompress((PRIV/'B_raw_grades.json.gz').read_bytes()))==raw
 save(PUB/'B_RAW_GRADE_BINDING.json',dict(binding=rawbinding,rows=len(raw),state='PERSISTED_REOPENED_BEFORE_SELECTIVE_SUMMARIES',scope='PRIVATE_RAW_ROWS;NOT_PUBLIC_OR_NEW_INDEPENDENT_GAMES',no_fit_or_simulation=True))
 result=evaluate(cases,outcomes,pred,raw_grades=raw)
 groups=collections.defaultdict(list)
 for x in raw:groups[x['method'],x['category']].append(x)
 c_raw=json.loads(gzip.decompress((ROOT/'private/shared-game-sim-01/raw_grades.json.gz').read_bytes()))
 c_groups=collections.defaultdict(list)
 for x in c_raw:
  if x['method'].startswith('C'):c_groups[x['method'],x['category']].append(x)
 pairs=[];bc=[]
 for (method,cat),rr in sorted(groups.items()):
  if not method.startswith('B::'):continue
  for control in ('W0','W1','ALWAYS_OVER','ALWAYS_UNDER'):
   cc=groups[control,cat]
   for w in ['ALL']+list(range(4,10)):
    aa=rr if w=='ALL' else [x for x in rr if x['week']==w];bb=cc if w=='ALL' else [x for x in cc if x['week']==w]
    v=_pair(aa,bb)
    paired_ids=sorted(x['canonical_case_key'] for x in aa if x['status'] in ('WIN','LOSS') and any(y['case_id']==x['case_id'] and y['status'] in ('WIN','LOSS') for y in bb))
    pairs.append(dict(candidate=method,control=control,category=cat,week=w,scope=SCOPE,common_decided_mask_SHA256=sha(json.dumps(paired_ids,separators=(',',':')).encode()),**v))
  for (cm,category),cc in sorted(c_groups.items()):
   if category!=cat:continue
   bc.append(dict(B=method,C=cm,category=cat,scope=SCOPE+';UNMATCHED_ORIGIN_NOT_PRIMARY_SUPERIORITY',paired_direction=_pair(rr,cc),same_case_numerical=numeric_pair(rr,cc),same_case_probability=probability_pair(rr,cc)))
 # Reuse frozen own lists; matched capacity is by declared game-origin batch.
 sel=[];bylist={(x['method'],x['category'],x['fraction']):x['case_ids'] for x in result['own_selection_policies']}
 for (method,cat),rr in sorted(groups.items()):
  if not method.startswith('B::'):continue
  lookup={x['case_id']:x for x in rr}
  for fraction in (.5,.25,.1):
   own=[lookup[k] for k in bylist[method,cat,fraction]]
   for control in ('W0','W1'):
    refmap={x['case_id']:x for x in groups[control,cat]};ref=[refmap[k] for k in bylist[control,cat,fraction]];aa=[];bb=[]
    for origin in sorted({x['game_origin_key'] for x in rr}):
     a=[x for x in own if x['game_origin_key']==origin];b=[x for x in ref if x['game_origin_key']==origin];k=min(len(a),len(b));aa+=a[:k];bb+=b[:k]
    sel.append(dict(candidate=method,control=control,category=cat,fraction=fraction,candidate_own_matched_capacity=_summarize(aa),control_own_matched_capacity=_summarize(bb),same_candidate_selected_directions=_pair(own,[refmap[x['case_id']] for x in own]),scope=SCOPE+';OWN_LISTS_VS_SAME_SELECTED_DIRECTIONS_SEPARATE;NO_TOPPICKS'))
 result.update(scope=SCOPE,products=products,empty_nominees=empties,paired_saved_controls=pairs,paired_C_controls=bc,own_selection_comparisons=sel,source_clock_counts=clock,primary_T90_comparability=timing,source_packet_SHA256=PACKET_SHA,case_SHA256=CASE_SHA,freeze_SHA256=FREEZE_SHA,decision='SHADOW_DIAGNOSTIC_ONLY;NO_PRIMARY_T90_COMPARISON_OR_ACTIVATION',primary='NO_SIMULATOR;B_SAVED_PRODUCT_COMPANION_VIEW')
 save(PRIV/'B_complete_results_with_membership.json.gz',result)
 result.pop('raw_grades',None);result=public(result)
 save(PUB/'B_COMPARISON_RESULTS.json.gz',result)
 save(PUB/'B_PRODUCT_IDENTITIES.json',dict(scope=SCOPE,products=products,empty_nominees=empties))
 print(json.dumps(dict(state='COMPLETED',B_products=len(products),nominees=36,raw_grade_rows=len(raw),paired_C_masks=len(bc),primary_available=av,scope=SCOPE)))
def controller():
 previous=[]
 if (PUB/'B_VIEW_RESOURCE_RECEIPT.json').exists():
  prior=json.loads((PUB/'B_VIEW_RESOURCE_RECEIPT.json').read_bytes());previous=prior.get('attempts',[prior]);save(PUB/'B_VIEW_FAILED_ATTEMPT_01.json',prior)
 used_cpu=sum(x['CPU_seconds'] for x in previous);used_wall=sum(x['wall_seconds'] for x in previous)
 start_cpu=time.process_time();start_wall=time.monotonic();child0=resource.getrusage(resource.RUSAGE_CHILDREN)
 env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1',PYTHONHASHSEED='0')
 p=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--worker'],cwd=ROOT,env=env);peak=threads=0;reason=None
 deadline=datetime.datetime.fromisoformat('2026-11-22T20:05:20.108935+00:00')
 while p.poll() is None:
  try:
   s=Path(f'/proc/{p.pid}/stat').read_text().split();cpu=(int(s[13])+int(s[14]))/os.sysconf('SC_CLK_TCK');rss=int(s[23])*os.sysconf('SC_PAGE_SIZE');peak=max(peak,rss);threads=max(threads,len(list(Path(f'/proc/{p.pid}/task').iterdir())))
  except (FileNotFoundError,ProcessLookupError):continue
  if cpu+time.process_time()-start_cpu>=59-used_cpu:reason='CPU_60_SAFETY_STOP'
  elif time.monotonic()-start_wall>=119-used_wall or datetime.datetime.now(datetime.timezone.utc)>=deadline:reason='WALL_SAFE_STOP'
  elif rss>1288490188:reason='RSS_SAFE_STOP'
  elif threads>1:reason='THREAD_SAFE_STOP'
  if reason:p.terminate();break
  time.sleep(.05)
 try:p.wait(timeout=2)
 except subprocess.TimeoutExpired:p.kill();p.wait()
 ch=resource.getrusage(resource.RUSAGE_CHILDREN)
 cpu=time.process_time()-start_cpu+ch.ru_utime-child0.ru_utime+ch.ru_stime-child0.ru_stime
 current=dict(stage='B_SAVED_OUTPUT_SECONDARY_DIAGNOSTIC_GRADES',CPU_seconds=cpu,wall_seconds=time.monotonic()-start_wall,peak_RSS_bytes=peak,max_threads=threads,returncode=p.returncode,safe_stop=reason,ceiling_CPU=60,ceiling_wall=120,no_numerical_solver_or_simulation=True,original_scientific_launch_UTC='2026-11-22T18:05:20.108935+00:00',end_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),charge_instruction='Carry exact measured CPU/controller wall once into same cumulative SIM account; do not mutate sealed execution-v1 ledger; root updates followup ledger',metering_limits='Selected child+controller process CPU and RSS sampling; authoring/preparation not complete process CPU certificate')
 save(PUB/'B_VIEW_RESOURCE_RECEIPT.json',dict(state='COMPLETED' if not p.returncode and not reason else 'STOPPED',attempts=previous+[current],CPU_seconds=used_cpu+cpu,wall_seconds=used_wall+current['wall_seconds'],max_threads=max(x['max_threads'] for x in previous+[current]),peak_RSS_bytes=max(x['peak_RSS_bytes'] for x in previous+[current]),all_failures_charged=True,no_solver_or_sampling=True))
 if p.returncode or reason:raise SystemExit(reason or p.returncode)
if __name__=='__main__':worker() if '--worker' in sys.argv else controller()
