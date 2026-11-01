"""Manual, permission-gated exact-offer paper snapshots. No acquisition or fits."""
import argparse,gzip,hashlib,json,math,subprocess
from pathlib import Path
from datetime import datetime,timezone
from decimal import Decimal
from offer_validator_v2 import instant
from contracts_v2 import grade,CATEGORIES,WEIGHTS,SIGNED,integer
from selection import point_side,counts
from actual_offers_v4 import probabilities,PROBABILITY_TIE_TOLERANCE
from coherence_v4 import state_for
from prospective_v4 import validate_run,validate_receipt

ROOT=Path(__file__).resolve().parents[1]
REGISTRY=ROOT/'protocol/OFFER_SOURCE_REGISTRY_V5.json'
POLICY=ROOT/'protocol/ACTUAL_OFFER_WORK_PACKAGE_V5.json'
def stamp():return datetime.now(timezone.utc).isoformat()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def digest(j):return hashlib.sha256(json.dumps(j,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def write(p,j):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x') as f:json.dump(j,f,separators=(',',':'),allow_nan=False)

def source_gate(source_id,export_sha,registry,evidence_root,at=None):
    s=registry['sources'].get(source_id)
    if not s:return ['SOURCE_NOT_REGISTERED']
    if s.get('analysis_qualified') is not True or s.get('public_retention_qualified') is not True:return [s.get('state','SOURCE_PERMISSION_UNQUALIFIED')]
    grant=s.get('grant',{});errors=[]
    for k in ['provider','scope','effective_from_UTC','evidence_file','evidence_SHA256','review_id']:
        if not grant.get(k):errors.append('MISSING_GRANT_'+k.upper())
    if errors:return errors
    p=(evidence_root/grant['evidence_file']).resolve()
    if not p.is_relative_to(evidence_root.resolve()) or not p.is_file() or sha(p)!=grant['evidence_SHA256']:errors.append('GRANT_EVIDENCE_BYTES_UNVERIFIED')
    if export_sha not in grant.get('approved_export_SHA256',[]):errors.append('EXACT_EXPORT_OUTSIDE_APPROVED_SCOPE')
    scope=grant['scope'];needed=['automated_analysis','public_quote_retention','identities_clocks_contracts']
    if isinstance(scope,dict):qualified=all(scope.get(k) is True for k in needed)
    else:qualified=isinstance(scope,list) and all(isinstance(v,str) for v in scope) and all(k in scope for k in needed)
    if not qualified:errors.append('GRANT_SCOPE_INCOMPLETE')
    try:
        t=instant(at or stamp())
        if instant(grant['effective_from_UTC'])>t or (grant.get('effective_until_UTC') and t>instant(grant['effective_until_UTC'])):errors.append('GRANT_OUTSIDE_EFFECTIVE_DATES')
    except (ValueError,TypeError):errors.append('GRANT_DATE_UNQUALIFIED')
    return errors

def quote_universe(offers,cutoff):
    """A later closed/suspended record suppresses an earlier OPEN quote."""
    latest={}
    for o in offers:
        if o.get('record_kind')!='ACTUAL_OFFER':raise ValueError('SYNTHETIC_OR_HYPOTHETICAL_RECORD_REJECTED')
        key=(o['venue'],o['product'],o['offer_id']);observed=instant(o['observed_at_UTC'])
        if observed>cutoff:raise ValueError('OFFER_OBSERVED_AFTER_CUTOFF')
        old=latest.get(key)
        if old and any(old.get(k)!=o.get(k) for k in ['game_id','player_id','category','period','comparator','scoring_contract_id','espn_event_id','kickoff_UTC']):raise ValueError('CONFLICTING_MARKET_IDENTITY')
        if old and instant(old['observed_at_UTC'])==observed and old!=o:raise ValueError('CONFLICTING_SAME_CLOCK_QUOTE')
        if old is None or instant(old['observed_at_UTC'])<observed:latest[key]=o
    return [latest[k] for k in sorted(latest)]

def exact_directions(o,f,mode,cutoff,status=None,coherence=None):
    """P1 does not depend on a distribution; P2 unavailable is a separate state."""
    reasons=[]
    for k in ['offer_id','venue','product','tier','game_id','player_id','category','period','comparator','scoring_contract_id','identity_evidence_reference','source_evidence_reference','offered_sides']:
        if o.get(k) in [None,'',[]]:reasons.append('MISSING_'+k.upper())
    if o.get('record_kind')!='ACTUAL_OFFER':raise ValueError('NOT_AN_ACTUAL_OFFER')
    for k in ['game_id','player_id','category','scoring_contract_id']:
        if o.get(k)!=f.get(k):reasons.append('IDENTITY_OR_CONTRACT_MISMATCH_'+k.upper())
    try:
        if instant(o['kickoff_UTC'])!=instant(f['kickoff_UTC']) or o['espn_event_id']!=f['espn_event_id']:reasons.append('NATIVE_EVENT_VERSION_MISMATCH')
    except (KeyError,ValueError,TypeError):reasons.append('EVENT_VERSION_UNQUALIFIED')
    if o.get('period')!='FULL_GAME_INCLUDING_OT':reasons.append('PERIOD_MISMATCH')
    event=f['category']=='anytime_td';sides=o.get('offered_sides',[]);allowed=['YES'] if event else ['OVER','UNDER']
    if not isinstance(sides,list) or not sides or len(sides)!=len(set(sides)) or any(s not in allowed for s in sides):reasons.append('OFFERED_SIDES_UNQUALIFIED')
    line=o.get('line')
    if not event and (not isinstance(line,(int,float)) or isinstance(line,bool) or not math.isfinite(line)):reasons.append('EXACT_LINE_UNAVAILABLE')
    if instant(f['information_cutoff_UTC'])>cutoff:reasons.append('FORECAST_INFORMATION_AFTER_CUTOFF')
    if o.get('comparator') not in (['AT_LEAST_ONE_RUSH_REC_TD'] if event else ['STRICT_OVER_UNDER','AT_LEAST']):reasons.append('COMPARATOR_UNQUALIFIED')
    if mode=='PROSPECTIVE':
        try:
            source,observed=instant(o['source_asof_UTC']),instant(o['observed_at_UTC'])
            if not source<=observed<=cutoff or (cutoff-source).total_seconds()>900 or (cutoff-observed).total_seconds()>900:reasons.append('QUOTE_CLOCK_OR_FRESHNESS_FAILED')
            if instant(f['generated_UTC'])>cutoff or (instant(f['kickoff_UTC'])-cutoff).total_seconds()<=300:reasons.append('STARTED_LATE_OR_TOO_CLOSE')
        except (KeyError,ValueError,TypeError):reasons.append('QUOTE_CLOCK_UNQUALIFIED')
        if o.get('lifecycle')!='OPEN' or o.get('side_states')!={s:'OPEN' for s in sides}:reasons.append('LIFECYCLE_NOT_OPEN')
        if not status:reasons.append('CURRENT_EVENT_STATUS_UNAVAILABLE')
        else:
            if status.get('state')!='pre' or status.get('status_name')!='STATUS_SCHEDULED' or status.get('completed') is not False:reasons.append('EVENT_NOT_VERIFIED_UNPLAYED')
            try:
                if status.get('espn_event_id')!=f['espn_event_id'] or instant(status['kickoff_UTC'])!=instant(f['kickoff_UTC']):reasons.append('CURRENT_EVENT_IDENTITY_CHANGED')
                if not 0<=(cutoff-instant(status['observed_UTC'])).total_seconds()<=1800:reasons.append('STATUS_STALE_OR_FROM_FUTURE')
            except (KeyError,ValueError,TypeError):reasons.append('CURRENT_EVENT_STATUS_UNQUALIFIED')
        if o.get('availability_review') not in ['CURRENT_ACTIVE_OR_UNKNOWN_CONDITIONAL','CURRENT_OUT','CURRENT_DOUBTFUL']:reasons.append('CURRENT_AVAILABILITY_REVIEW_MISSING')
        if o.get('availability_review') in ['CURRENT_OUT','CURRENT_DOUBTFUL'] or f.get('selection_availability')=='BLOCKED_OUT':reasons.append('OUT_OR_DOUBTFUL')
    elif mode!='HISTORICAL_DIAGNOSTIC':reasons.append('INVALID_MODE')
    coh=coherence if coherence is not None else state_for(f['forecast_id'])
    if f['category'] in ['pass_cmp','pass_att'] and coh not in ['CMP_ATT_ORDER_CHECKED_NOT_A_JOINT_LAW']:reasons.append('CMP_ATT_SELECTION_BLOCKED_'+coh)
    if f.get('readiness')=='EXPERIMENTAL_SHADOW_LABEL_COVERAGE':reasons.append('CHART_LABEL_COVERAGE_UNQUALIFIED')
    r={k:o.get(k) for k in ['offer_id','venue','product','tier','player_id','game_id','category','period','line','comparator','scoring_contract_id','offered_sides','source_asof_UTC','observed_at_UTC','kickoff_UTC','espn_event_id','source_evidence_reference','identity_evidence_reference','lifecycle','prices','availability_review']}
    r.update(record_kind='ACTUAL_OFFER',forecast_id=f['forecast_id'],model_id=f.get('model_id'),forecast_generated_UTC=f.get('generated_UTC'),feature_cutoff_UTC=f['information_cutoff_UTC'],conditioning=f.get('appearance_conditioning'),cutoff_UTC=cutoff.isoformat(),book_settlement='UNVERIFIED',P1_side=None,P2_side=None,p_under=None,p_push=None,p_over=None,reasons=sorted(set(reasons)),P1_state='UNAVAILABLE',P2_state='UNAVAILABLE')
    if reasons:return r
    point=f.get('median') if f.get('median') is not None else f.get('point');side=None if event or o['comparator']!='STRICT_OVER_UNDER' else point_side(point,line)
    if side not in [None,'ABSTAIN','UNAVAILABLE'] and side not in sides:side='ABSTAIN'
    r.update(P1_side=side,P1_state='UNAVAILABLE' if side in [None,'UNAVAILABLE'] else 'ABSTAIN' if side=='ABSTAIN' else 'SELECTED',point=point,point_type='MEDIAN' if f.get('median') is not None else f.get('point_type','POINT_UNSPECIFIED'))
    if 'law' not in f:r['P2_reason']='NO_PROBABILITY_LAW';return r
    try:p=probabilities(o,f)
    except (ValueError,AssertionError,KeyError,TypeError):r['P2_reason']='PROBABILITY_LAW_OR_COMPARATOR_UNAVAILABLE';return r
    side='ABSTAIN' if abs(p['over']-p['under'])<=PROBABILITY_TIE_TOLERANCE else 'OVER' if p['over']>p['under'] else 'UNDER'
    if event:side='YES' if p['over']>.5+PROBABILITY_TIE_TOLERANCE else 'ABSTAIN'
    elif side not in sides:side='ABSTAIN'
    r.update(P2_side=side,P2_state='ABSTAIN' if side=='ABSTAIN' else 'SELECTED',p_under=p['under'],p_push=p['push'],p_over=p['over'])
    return r

def forecast_pool(root,cutoff=None,bound_ids=None):
    pool={};proofs=[]
    for p in sorted((root/'receipts').glob('*.json')):
        proof=read(p)
        if cutoff and instant(proof['server_check_completed_UTC'])>cutoff:continue
        run=root/'runs'/proof['run_id'];m,rs=validate_run(run);validate_receipt(run,proof,m,rs);proofs.append(proof)
        for r in rs:
            if bound_ids is not None and r['forecast_id'] not in bound_ids:continue
            key=(r['game_id'],r['player_id'],r['category']);old=pool.get(key)
            if old and instant(old['forecast_server_persisted_UTC'])>=instant(proof['server_check_completed_UTC']):continue
            pool[key]=r|dict(forecast_server_persisted_UTC=proof['server_check_completed_UTC'],forecast_capture_commit=proof['capture_commit'])
    return pool,proofs

def primary_candidates(rows):
    """One deterministic quote per football case/venue/product, before ranking."""
    by={}
    for r in rows:
        key=tuple(r.get(k) for k in ['game_id','player_id','category','venue','product'])
        order=(instant(r['observed_at_UTC']) if r.get('observed_at_UTC') else datetime.min.replace(tzinfo=timezone.utc),r['offer_id'])
        if key not in by or order>by[key][0]:by[key]=(order,r['offer_id'])
    return [r|dict(primary_in_packet=by[tuple(r.get(k) for k in ['game_id','player_id','category','venue','product'])][1]==r['offer_id']) for r in rows]

def evaluate_packet(packet,pool,cutoff):
    status={s['game_id']:s for s in packet['event_status']};rows=[]
    for o in quote_universe(packet['offers'],cutoff):
        f=pool.get((o['game_id'],o['player_id'],o['category']))
        if not f:rows.append(o|dict(P1_side=None,P2_side=None,P1_state='UNAVAILABLE',P2_state='UNAVAILABLE',reasons=['NO_MATCHED_FORECAST']));continue
        rows.append(exact_directions(o,f,'PROSPECTIVE',cutoff,status.get(o['game_id'])))
    return primary_candidates(rows)

def prepare(packet_path,out,forecast_root,registry_path=REGISTRY):
    b=packet_path.read_bytes()
    if len(b)>2097152:raise ValueError('PACKET_BYTE_CAP')
    packet=json.loads(b);assert packet['schema']=='C-ACTUAL-OFFERS-v5';registry=read(registry_path)
    reasons=source_gate(packet['source_id'],hashlib.sha256(b).hexdigest(),registry,registry_path.parent)
    if reasons:raise ValueError('SOURCE_GATE:'+','.join(reasons))
    if packet.get('is_fixture') or packet['source_id'].startswith('TEST'):raise ValueError('FIXTURE_FORBIDDEN_IN_PAPER_EVIDENCE')
    if subprocess.check_output(['git','status','--porcelain'],text=True).strip():raise ValueError('COMMIT_SELECTOR_BEFORE_PAPER_CREATION')
    if out.exists():raise FileExistsError('IMMUTABLE_PAPER_DESTINATION_EXISTS')
    cutoff=instant(stamp());offers=packet['offers'];assert len(offers)<=1000
    pool,proofs=forecast_pool(forecast_root,cutoff);rows=evaluate_packet(packet,pool,cutoff)
    used={r['forecast_id'] for r in rows if r.get('forecast_id')};bindings={r['forecast_id']:dict(run_id=r['run_id'],capture_commit=r['forecast_capture_commit'],server_persisted_UTC=r['forecast_server_persisted_UTC']) for r in pool.values() if r['forecast_id'] in used}
    out.mkdir(parents=True);write(out/'offers.json',packet);write(out/'evaluations.json',rows);write(out/'forecast_receipts.json',proofs)
    write(out/'forecast_bindings.json',bindings)
    grant=registry['sources'][packet['source_id']]['grant'];evidence=(registry_path.parent/grant['evidence_file']);(out/'permission.txt').write_bytes(evidence.read_bytes());write(out/'source_review.json',registry['sources'][packet['source_id']])
    manifest=dict(schema='C-PAPER-RUN-v5',run_id=out.name,policy_id='C-ACTUAL-OFFERS-v5',policy_SHA256=sha(POLICY),selector_id='P2_EXACT_LINE_SELECTOR-v4.1',created_UTC=stamp(),decision_cutoff_UTC=cutoff.isoformat(),code_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),source_id=packet['source_id'],source_export_SHA256=hashlib.sha256(b).hexdigest(),quote_candidates=len(offers),deduplicated_offers=len(rows),P2_selected=sum(r.get('P2_state')=='SELECTED' for r in rows),P1_selected=sum(r.get('P1_state')=='SELECTED' for r in rows),publication_state='AWAITING_OWN_GITHUB_SERVER_PROOF',six_leg_state='NO_QUALIFIED_SIX_LEG_ENTRY',NFL_fits=0)
    manifest['files']={p.name:dict(SHA256=sha(p),bytes=p.stat().st_size) for p in out.iterdir() if p.is_file()};write(out/'RUN.json',manifest);return manifest

def validate_packet(run,check_clock=False):
    m=read(run/'RUN.json');assert m['schema']=='C-PAPER-RUN-v5'
    assert m['policy_SHA256']==sha(POLICY),'PAPER_POLICY_CHANGED_REQUIRES_VERSIONED_VALIDATOR'
    for name,info in m['files'].items():
        assert Path(name).name==name,'PAPER_PATH_TRAVERSAL'
        assert sha(run/name)==info['SHA256'] and (run/name).stat().st_size==info['bytes'],'PAPER_BYTES_CHANGED'
    packet=read(run/'offers.json');assert sha(run/'offers.json')==m['source_export_SHA256']
    review=read(run/'source_review.json');registry=read(REGISTRY)
    trusted=registry['sources'].get(m['source_id'])==review or registry.get('retained_review_SHA256',{}).get(review.get('grant',{}).get('review_id'))==digest(review)
    assert trusted,'SOURCE_REVIEW_NOT_IN_TRUSTED_REGISTRY'
    assert not source_gate(m['source_id'],m['source_export_SHA256'],dict(sources={m['source_id']:review}),REGISTRY.parent,m['decision_cutoff_UTC']),'SOURCE_PERMISSION_UNQUALIFIED'
    assert sha(run/'permission.txt')==review['grant']['evidence_SHA256']
    assert not packet.get('is_fixture') and not m['source_id'].startswith('TEST')
    rows=read(run/'evaluations.json');cutoff=instant(m['decision_cutoff_UTC']);assert cutoff<=instant(m['created_UTC'])
    bindings=read(run/'forecast_bindings.json');pool,proofs=forecast_pool(ROOT/'prospective',cutoff,set(bindings))
    actual={r['forecast_id']:dict(run_id=r['run_id'],capture_commit=r['forecast_capture_commit'],server_persisted_UTC=r['forecast_server_persisted_UTC']) for r in pool.values()}
    assert actual==bindings,'FORECAST_BINDING_CHANGED'
    stored=read(run/'forecast_receipts.json')
    assert all(proof in proofs for proof in stored),'FORECAST_SERVER_PROOF_CHANGED'
    expected=evaluate_packet(packet,pool,cutoff)
    assert rows==expected,'PAPER_EXACT_LINE_OR_SELECTOR_MISMATCH'
    if check_clock:assert all(instant(stamp()).timestamp()+300<instant(r['kickoff_UTC']).timestamp() for r in rows),'PAPER_SERVER_CHECK_TOO_LATE'
    return m,rows

def receipt(run,commit,workflow_run,output):
    m,rows=validate_packet(run);repo='NickNicky19/NFL-forecasting-NGS-C';j=json.loads(subprocess.check_output(['gh','api',f'repos/{repo}/actions/runs/{workflow_run}']))
    assert j['head_sha']==commit and j['event']=='pull_request' and j['conclusion']=='success' and j['path']=='.github/workflows/c-checks-pages.yml'
    jobs=json.loads(subprocess.check_output(['gh','api',f'repos/{repo}/actions/runs/{workflow_run}/jobs']))['jobs'];job=next(r for r in jobs if r['name']=='checks')
    assert any(s['name']=='Verify immutable paper captures' and s['conclusion']=='success' for s in job['steps'])
    persisted=instant(job['completed_at']);assert persisted>=instant(m['created_UTC'])
    assert all(persisted.timestamp()+300<instant(r['kickoff_UTC']).timestamp() for r in rows)
    assert all((persisted-instant(r['source_asof_UTC'])).total_seconds()<=900 for r in rows if not r.get('reasons')),'QUOTE_EXPIRED_BEFORE_PERSISTENCE'
    from urllib.request import urlopen
    relative=run.resolve().relative_to(ROOT).as_posix();base=f'https://raw.githubusercontent.com/{repo}/{commit}/{relative}/'
    for name in ['RUN.json',*m['files']]:assert hashlib.sha256(urlopen(base+name,timeout=30).read()).hexdigest()==sha(run/name)
    proof=dict(schema='C-PAPER-SERVER-RECEIPT-v5',run_id=m['run_id'],capture_commit=commit,run_SHA256=sha(run/'RUN.json'),evaluations_SHA256=sha(run/'evaluations.json'),server_workflow_run=workflow_run,server_created_UTC=j['created_at'],server_persisted_UTC=job['completed_at'],server_URL=j['html_url'],verified_UTC=stamp(),fresh_GitHub_bytes=True,qualified_pregame_paper=True,not_forecast_issue_time=True)
    write(output,proof);return proof

def check_receipt(run,proof,m,rows):
    assert proof['schema']=='C-PAPER-SERVER-RECEIPT-v5' and proof['qualified_pregame_paper'] is True and proof['fresh_GitHub_bytes'] is True
    assert proof['run_id']==m['run_id'] and proof['run_SHA256']==sha(run/'RUN.json') and proof['evaluations_SHA256']==sha(run/'evaluations.json')
    t=instant(proof['server_persisted_UTC']);assert instant(m['created_UTC'])<=t
    assert instant(proof['server_created_UTC'])<=t
    assert all(t.timestamp()+300<instant(r['kickoff_UTC']).timestamp() for r in rows)
    assert all(0<=(t-instant(r[k])).total_seconds()<=900 for r in rows if not r.get('reasons') for k in ['source_asof_UTC','observed_at_UTC']),'QUOTE_EXPIRED_BEFORE_PERSISTENCE'
    return t

def verify(root):
    n=0
    for p in root.glob('runs/*/RUN.json'):
        run=p.parent;proof=root/'receipts'/f'{run.name}.json';m,rows=validate_packet(run,not proof.exists())
        if proof.exists():check_receipt(run,read(proof),m,rows)
        n+=1
    print('PAPER_PACKETS_VALID',n)

def grade_records(rows,outcomes,method):
    judged=[]
    for r in rows:
        if r.get('record_kind')!='ACTUAL_OFFER':raise ValueError('SYNTHETIC_IN_REAL_OFFER_RESULTS')
        a=outcomes.get((r['game_id'],r['player_id'],r['category']));side=r.get(method+'_side');appearance='PENDING' if a is None else a['appearance'];actual=None if a is None else a.get('actual')
        raw_actual=actual;lattice=None
        if isinstance(actual,bool) or (actual is not None and (not isinstance(actual,(int,float)) or not math.isfinite(actual))):actual=None
        if actual is not None:
            scale=CATEGORIES[r['category']][3];lattice=round(actual*scale)
            assert abs(actual*scale-lattice)<1e-8,'OUTCOME_OFF_CONTRACT_LATTICE'
            actual=Decimal(lattice)/Decimal(scale)
        if side in [None,'UNAVAILABLE']:state='UNAVAILABLE'
        elif side=='ABSTAIN':state='ABSTAIN'
        elif r['comparator']=='AT_LEAST_ONE_RUSH_REC_TD':state=grade(actual,.5,'OVER',appearance)
        elif r['comparator']=='AT_LEAST' and appearance=='PLAYED' and actual is not None:state='WIN' if (actual>=Decimal(str(r['line'])))==(side=='OVER') else 'LOSS'
        else:state=grade(actual,r['line'],side,appearance)
        score=loss=None
        if appearance=='PLAYED' and actual is not None and all(r.get(k) is not None for k in ['p_under','p_push','p_over']):
            comparator=r['comparator'];y=actual;line=Decimal(str(r['line'])) if r['line'] is not None else None
            truth=[float(y<line),float(y==line),float(y>line)] if comparator=='STRICT_OVER_UNDER' else [float(y<line),0.,float(y>=line)] if comparator=='AT_LEAST' else [float(y==0),0.,float(y==1)]
            law=[r[k] for k in ['p_under','p_push','p_over']];assert abs(sum(law)-1)<1e-10 and min(law)>=0
            score=.5*sum((x-y)**2 for x,y in zip(law,truth));p=sum(x*y for x,y in zip(law,truth));loss=-math.log(p) if p>0 else 'Infinity'
        judged.append(dict(offer_id=r['offer_id'],forecast_id=r.get('forecast_id'),game_id=r['game_id'],player_id=r['player_id'],category=r['category'],side='OVER' if side=='YES' else side,grade=state,actual=None if actual is None else float(actual),actual_raw=raw_actual,actual_lattice_integer=lattice,appearance=appearance,probability_half_brier=score,probability_logloss=loss,book_settlement='UNVERIFIED'))
    return judged

def statistical_grades(rows,outcomes,method):
    judged=grade_records(rows,outcomes,method)
    return counts(judged)|dict(offers=len(rows),abstentions=sum(r['grade']=='ABSTAIN' for r in judged),unavailable=sum(r['grade']=='UNAVAILABLE' for r in judged),other={s:sum(r['grade']==s for r in judged) for s in sorted({r['grade'] for r in judged}-{'WIN','LOSS','ABSTAIN','UNAVAILABLE'})})

def outcome_lookup(path,rows):
    packet=read(path);assert packet['schema']=='C-OUTCOMES-v4' and packet['source_qualification']=='OFFICIAL_NUMERICAL_FACTS_VERIFIED'
    assert packet['source_evidence'],'OUTCOME_SOURCE_PROVENANCE_REQUIRED'
    for e in packet['source_evidence']:
        p=(path.parent/e['path']).resolve();assert p.is_relative_to(path.parent.resolve()) and sha(p)==e['SHA256'] and e['source'],'OUTCOME_SOURCE_BYTES_UNVERIFIED'
    lookup={(a['game_id'],a['player_id'],a['category']):a for a in packet['outcomes']};assert len(lookup)==len(packet['outcomes']),'DUPLICATE_OUTCOME'
    for r in rows:
        a=lookup.get((r['game_id'],r['player_id'],r['category']))
        if not a:continue
        assert a['scoring_contract_id']==r['scoring_contract_id'] and a['espn_event_id']==r['espn_event_id'],'OUTCOME_CONTRACT_IDENTITY_MISMATCH'
        assert instant(a['kickoff_UTC'])==instant(r['kickoff_UTC']),'OUTCOME_EVENT_VERSION_CHANGED'
        assert a['event_status']=='FINAL' and instant(a['kickoff_UTC'])<instant(a['observed_UTC'])<=instant(stamp()),'OUTCOME_NOT_FINAL'
        assert a['appearance'] in ['PLAYED','DNP','UNKNOWN','VOID','CANCELLED','PENDING']
        y=a.get('actual')
        if a['appearance']!='PLAYED' or y is None:continue
        assert isinstance(y,(int,float)) and not isinstance(y,bool) and math.isfinite(y)
        cat=r['category'];scale=CATEGORIES[cat][3];assert abs(y*scale-round(y*scale))<1e-8,'OUTCOME_OFF_CONTRACT_LATTICE'
        if CATEGORIES[cat][2]=='count':assert y>=0
        if cat=='anytime_td':
            c=a['event_components'];ru=integer(c.get('rushing_tds'));re=integer(c.get('receiving_tds'));assert ru is not None and re is not None and y==int(ru+re>0),'ANYTIME_REQUIRES_RUSH_REC_EVENT'
        if cat=='fpts':
            v={k:integer(a['score_components'].get(k),k in SIGNED) for k in WEIGHTS};assert all(x is not None for x in v.values()) and abs(sum(WEIGHTS[k]*v[k] for k in v)/50-y)<1e-10 and a.get('unique_event_credits_verified') is True,'EXACT_CHART_CREDITS_REQUIRED'
    return lookup,packet

def summaries(rows,lookup):
    return [dict(category=cat,method=method,policy='ALL_RECORDED_ELIGIBLE_OFFERS',**statistical_grades([r for r in rows if r['category']==cat],lookup,method)) for cat in CATEGORIES for method in ['P1','P2']]

def retained_forecast(f,base):
    """Verify typed points against recoverable saved C rows, not caller assertions."""
    path=(base/f['retained_forecast_evidence']).resolve()
    assert path.is_relative_to(base.resolve()) and sha(path)==f['retained_forecast_SHA256'],'RETAINED_FORECAST_BYTES_UNVERIFIED'
    b=path.read_bytes();rows=json.loads(gzip.decompress(b) if path.name.endswith('.gz') else b)
    matches=[r for r in rows if r['game_id']==f['game_id'] and r['player_id']==f['player_id'] and r.get('target',r.get('category'))==f['category'] and r.get('slot',r.get('method_id'))==f['method_id']]
    assert len(matches)==1,'SAVED_FORECAST_IDENTITY_NOT_UNIQUE'
    r=matches[0]
    for key in ['mean','median','point','point_type','scoring_contract_id']:assert f.get(key)==r.get(key),'SAVED_POINT_OR_CONTRACT_CHANGED'
    assert instant(f['information_cutoff_UTC'])==instant(r.get('as_of_UTC',r.get('information_cutoff_UTC'))),'SAVED_FORECAST_HORIZON_CHANGED'
    assert instant(f['kickoff_UTC'])==instant(r['kickoff_UTC'])
    if 'law' in f:
        # A stored threshold grid is not an exact-line law; only a retained full law qualifies.
        assert r.get('law')==f['law'],'EXACT_SAVED_LAW_REQUIRED_NO_GRID_INTERPOLATION'
    return r

def historical(packet_path,outcomes,output):
    """Approved exact-row replay; invokes no fitting, law invention or acquisition."""
    packet=read(packet_path);assert packet['schema']=='C-HISTORICAL-EXACT-OFFERS-v5'
    errors=source_gate(packet['source_id'],sha(packet_path),read(REGISTRY),REGISTRY.parent)
    if errors:raise ValueError('SOURCE_GATE:'+','.join(errors))
    assert not packet.get('is_fixture') and not packet['source_id'].startswith('TEST')
    offers=packet['offers'];forecasts=packet['forecasts'];result=[]
    for method in sorted({f['method_id'] for f in forecasts}):
        fs=[f for f in forecasts if f['method_id']==method];index={(f['game_id'],f['player_id'],f['category']):f for f in fs};assert len(index)==len(fs),'DUPLICATE_METHOD_FORECAST'
        rows=[]
        for o in offers:
            if o.get('record_kind')!='ACTUAL_OFFER':raise ValueError('SYNTHETIC_IN_REAL_OFFER_REPLAY')
            f=index.get((o['game_id'],o['player_id'],o['category']))
            if f:
                retained_forecast(f,packet_path.parent)
                r=exact_directions(o,f,'HISTORICAL_DIAGNOSTIC',instant(f['information_cutoff_UTC']))
            else:r=o|dict(P1_side=None,P2_side=None,P1_state='UNAVAILABLE',P2_state='UNAVAILABLE',reasons=['NO_MATCHED_FORECAST'])
            rows.append(r|dict(method_id=method,evidence_tier='TIMING_UNVERIFIED_HISTORICAL_DIAGNOSTIC'))
        lookup,p=outcome_lookup(outcomes,rows);result.append(dict(method_id=method,rows=rows,grades={m:grade_records(rows,lookup,m) for m in ['P1','P2']},summary=summaries(rows,lookup)))
    write(output,dict(schema='C-HISTORICAL-EXACT-LINE-RESULTS-v5',created_UTC=stamp(),input_SHA256=sha(packet_path),outcome_SHA256=sha(outcomes),policy_SHA256=sha(POLICY),results=result,NFL_fits=0,prices_required=False,book_settlement='UNVERIFIED'))

def paper_grade(run,outcomes,output):
    m,rows=validate_packet(run);root=run.parent.parent;proof=read(root/'receipts'/f'{run.name}.json');check_receipt(run,proof,m,rows)
    # Earliest qualified paper snapshot per football case, not best eventual revision.
    first={}
    for p in sorted((root/'receipts').glob('*.json')):
        pr=read(p);rr=root/'runs'/pr['run_id'];mm,rs=validate_packet(rr);at=check_receipt(rr,pr,mm,rs)
        for r in rs:
            key=tuple(r[k] for k in ['game_id','player_id','category','venue','product'])
            if r.get('primary_in_packet') and not r.get('reasons'):
                first[key]=min(first.get(key,(at,mm['run_id'])),(at,mm['run_id']))
    original=[r for r in rows if r.get('primary_in_packet') and first.get(tuple(r[k] for k in ['game_id','player_id','category','venue','product']),[None,None])[1]==m['run_id']]
    lookup,packet=outcome_lookup(outcomes,original)
    write(output,dict(schema='C-PAPER-GRADING-v5',run_id=m['run_id'],created_UTC=stamp(),evaluations_SHA256=sha(run/'evaluations.json'),outcome_SHA256=sha(outcomes),outcome_version=packet['version'],primary_offers=len(original),not_primary=len(rows)-len(original),grades={m:grade_records(original,lookup,m) for m in ['P1','P2']},summary=summaries(original,lookup),book_settlement='UNVERIFIED',six_leg_state='NO_QUALIFIED_SIX_LEG_ENTRY'))

if __name__=='__main__':
    p=argparse.ArgumentParser();s=p.add_subparsers(dest='command',required=True);a=s.add_parser('prepare');a.add_argument('--input',type=Path,required=True);a.add_argument('--output',type=Path,required=True);a.add_argument('--forecasts',type=Path,default=ROOT/'prospective');a=s.add_parser('verify');a.add_argument('--root',type=Path,default=ROOT/'paper');a=s.add_parser('receipt');a.add_argument('--run',type=Path,required=True);a.add_argument('--commit',required=True);a.add_argument('--workflow-run',type=int,required=True);a.add_argument('--output',type=Path,required=True)
    a=s.add_parser('historical');a.add_argument('--input',type=Path,required=True);a.add_argument('--outcomes',type=Path,required=True);a.add_argument('--output',type=Path,required=True)
    a=s.add_parser('grade');a.add_argument('--run',type=Path,required=True);a.add_argument('--outcomes',type=Path,required=True);a.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.command=='prepare':prepare(a.input,a.output,a.forecasts)
    elif a.command=='receipt':receipt(a.run,a.commit,a.workflow_run,a.output)
    elif a.command=='historical':historical(a.input,a.outcomes,a.output)
    elif a.command=='grade':paper_grade(a.run,a.outcomes,a.output)
    else:verify(a.root)
