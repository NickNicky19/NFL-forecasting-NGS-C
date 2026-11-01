"""One actual-offer row ledger -> headline, methods, leaders, CSV, chat and site.

No acquisition, fitting, hypothetical lines, probability-to-hit conversion or
automatic policy promotion. Empty/unqualified NFL inputs remain empty.
"""
import argparse,csv,hashlib,json,math,io,gzip
from pathlib import Path
from collections import Counter,defaultdict
from datetime import datetime,timezone
from decimal import Decimal
from functools import lru_cache
from contracts_v2 import CATEGORIES,grade,WEIGHTS,SIGNED,integer
from offer_validator_v2 import instant
from selection import point_side

ROOT=Path(__file__).resolve().parents[1]
POLICY=ROOT/'protocol/ACTUAL_ACCURACY_POLICY_V6.json'
OUT=ROOT/'reports/actual-accuracy-v6'
MANIFEST=ROOT/'reporting/actual-props-v6/DATASETS.json'
METHODS=['P1_MEDIAN','P1_MEAN','P2_LAW','P3_DIRECT','P2_LINKED_V8','P2_WORKLOAD_V8','EARLIER_PREVALENCE_V8','P4_HYBRID','ALWAYS_OVER','ALWAYS_UNDER']
LAW_METHODS=['P2_LAW','P2_LINKED_V8','P2_WORKLOAD_V8']
PROB_METHODS=[*LAW_METHODS,'P3_DIRECT','P4_HYBRID','EARLIER_PREVALENCE_V8']
TIERS=['ORIGINAL_AUTHENTICATED_PREGAME','QUALIFIED_CHRONOLOGICAL_ACTUAL_OFFER_REPLAY','TIMING_UNVERIFIED_ACTUAL_LINE_DIAGNOSTIC','GENUINE_PROSPECTIVE_W8_PLUS']
STATUSES=['WIN','LOSS','PUSH','VOID','DNP','PENDING','UNKNOWN_PARTICIPATION','MISSING_ACTUAL','UNAVAILABLE_FORECAST','ABSTAIN']
STRATA=['decision_horizon','venue','product','line_tier']
LABELS={k:v[0] for k,v in CATEGORIES.items()}|{'pass_int':'Interceptions Thrown','fpts':'Fantasy Points (nick-chart-ppr-v1)'}
def read(p):
    p=Path(p);return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def digest(j):return hashlib.sha256(json.dumps(j,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def stable_write(p,j):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(j,separators=(',',':'),allow_nan=False)+'\n')
def policies():return ['ALL_ELIGIBLE_OFFERS']+[f'{s}_TOP{k}_{side}' for s in ['GLOBAL','CATEGORY'] for k in [6,10,20] for side in ['MIXED','OVER_ONLY','UNDER_ONLY']]
def safe_file(base,path,expected):
    p=(base/path).resolve();assert p.is_relative_to(base.resolve()) and sha(p)==expected,'RETAINED_BYTES_OR_PATH_INVALID';return p

def validate_row(r):
    assert r['record_kind']=='ACTUAL_OFFER' and not r.get('is_fixture'),'SYNTHETIC_OR_FIXTURE_IN_NFL_SCORECARD'
    assert r['category'] in CATEGORIES and r['method_id'] in METHODS and r['policy_id'] in policies()
    assert r['evidence_tier'] in TIERS and r['status'] in STATUSES
    for k in ['record_id','grade_id','method_version','selector_id','game_id','player_id','espn_event_id','scoring_contract_id','scoring_snapshot_id',*STRATA]:assert isinstance(r.get(k),str) and r[k],'MISSING_IDENTITY_OR_COMPARABILITY_FIELD:'+k
    assert r.get('position') in ['QB','RB','WR','TE'] and r.get('role_evidence_reference'),'HISTORICAL_ROLE_PROVENANCE_REQUIRED'
    assert r['period']=='FULL_GAME_INCLUDING_OT' and isinstance(r['season'],int) and isinstance(r['week'],int) and 2022<=r['season']<=2026 and 1<=r['week']<=18 and r.get('season_type')=='REG'
    assert isinstance(r['offered_sides'],list) and r['offered_sides'] and len(r['offered_sides'])==len(set(r['offered_sides'])) and set(r['offered_sides'])<=({'YES'} if r['category']=='anytime_td' else {'OVER','UNDER'})
    side=r.get('selected_side');assert side in r['offered_sides'] or side in [None,'ABSTAIN']
    if side is None:assert r['status']=='UNAVAILABLE_FORECAST','TECHNICAL_UNAVAILABLE_MISLABELLED_AS_OUTCOME'
    if side=='ABSTAIN':assert r['status']=='ABSTAIN','ABSTENTION_MISLABELLED_AS_OUTCOME'
    if r['status']=='PENDING':assert side in r['offered_sides'] and r['appearance']=='PENDING' and r.get('actual') is None and r.get('graded_UTC') is None
    if r['status']=='MISSING_ACTUAL':assert r['appearance']=='PLAYED' and r.get('actual') is None
    if r['status']=='UNKNOWN_PARTICIPATION':assert r['appearance'] in ['UNKNOWN','UNKNOWN_PARTICIPATION'] and r.get('actual') is None
    if r['method_id']=='P1_MEAN':assert r['point_type']=='MEAN'
    if r['method_id']=='P1_MEDIAN':assert r['point_type']=='MEDIAN'
    if r['method_id'] in ['P1_MEAN','P1_MEDIAN'] and r.get('point') is not None:assert isinstance(r['point'],(int,float)) and not isinstance(r['point'],bool) and math.isfinite(r['point']),'INVALID_TYPED_POINT'
    if r['evidence_tier']=='GENUINE_PROSPECTIVE_W8_PLUS':assert r['season']==2026 and r['week']>=8,'PROSPECTIVE_WEEK_TIER_MISMATCH'
    if r['category']=='anytime_td':assert r['comparator']=='AT_LEAST_ONE_RUSH_REC_TD' and 'UNDER' not in r['offered_sides'] and r['scoring_contract_id']=='rush-or-rec-at-least-one-v1'
    else:assert isinstance(r.get('line'),(int,float)) and not isinstance(r['line'],bool) and math.isfinite(r['line']) and r['comparator'] in ['STRICT_OVER_UNDER','AT_LEAST'],'EXACT_LINE_OR_COMPARATOR_UNQUALIFIED'
    if r['category']=='fpts':assert r['scoring_contract_id']=='nick-chart-ppr-v1' and r.get('venue_scoring_parity_verified') is True
    if r['method_id'] in ['P1_MEAN','P1_MEDIAN']:
        expected=None if r['category']=='anytime_td' or r['comparator']!='STRICT_OVER_UNDER' else point_side(r.get('point'),r['line'])
        if expected=='UNAVAILABLE':expected=None
        if expected not in [None,'ABSTAIN'] and expected not in r['offered_sides']:expected='ABSTAIN'
        assert side==expected,'FROZEN_POINT_DIRECTION_MISMATCH'
    if r['method_id'] in PROB_METHODS and r['status']!='UNAVAILABLE_FORECAST':
        ps=[r[k] for k in ['p_under','p_push','p_over']];assert all(isinstance(p,(int,float)) and not isinstance(p,bool) and math.isfinite(p) and p>=0 for p in ps) and abs(sum(ps)-1)<1e-10
        assert r.get('probability_line')==r.get('line'),'PROBABILITY_NOT_EVALUATED_AT_EXACT_OFFER_LINE'
        assert r.get('probability_inference_evidence_reference') and r.get('information_set_id'),'PROBABILITY_INFERENCE_PROVENANCE_REQUIRED'
        if r['comparator']!='STRICT_OVER_UNDER' or Decimal(str(r['line']))*CATEGORIES[r['category']][3]!=(Decimal(str(r['line']))*CATEGORIES[r['category']][3]).to_integral_value():assert abs(ps[1])<=1e-12,'IMPOSSIBLE_PUSH_MASS'
        if r['method_id'] in LAW_METHODS:
            from actual_offers_v4 import probabilities
            assert r['law']['scale']==CATEGORIES[r['category']][3] and r['law']['prior']['kind']==CATEGORIES[r['category']][2],'LAW_SUPPORT_OR_UNITS_MISMATCH'
            actual=probabilities(r,dict(category=r['category'],law=r['law']))
            assert all(abs(actual[k]-r['p_'+k])<=1e-10 for k in ['under','push','over']),'RETAINED_LAW_EXACT_LINE_MISMATCH'
        expected='ABSTAIN' if abs(ps[2]-ps[0])<=1e-12 else 'OVER' if ps[2]>ps[0] else 'UNDER'
        if r['category']=='anytime_td':expected='YES' if ps[2]>.5+1e-12 else 'ABSTAIN'
        elif expected not in r['offered_sides']:expected='ABSTAIN'
        assert side==expected,'FROZEN_PROBABILITY_DIRECTION_MISMATCH'
    if r['method_id'] in ['ALWAYS_OVER','ALWAYS_UNDER']:
        target='OVER' if r['method_id']=='ALWAYS_OVER' else 'UNDER';assert side==(target if target in r['offered_sides'] else 'ABSTAIN')
    instant(r['decision_UTC']);instant(r['kickoff_UTC'])
    if r['policy_id']!='ALL_ELIGIBLE_OFFERS':
        for key in ['slate_id','membership_evidence_reference','candidate_universe_SHA256','slate_decision_UTC','slate_earliest_kickoff_UTC']:assert r.get(key),'MISSING_FROZEN_TOPK_MEMBERSHIP:'+key
        assert instant(r['decision_UTC'])<=instant(r['slate_decision_UTC'])<instant(r['slate_earliest_kickoff_UTC'])<=instant(r['kickoff_UTC'])
        k=int(r['policy_id'].split('_')[1][3:]);assert isinstance(r.get('frozen_rank'),int) and 1<=r['frozen_rank']<=k
        if r['policy_id'].endswith('OVER_ONLY'):assert side in ['OVER','YES']
        if r['policy_id'].endswith('UNDER_ONLY'):assert side=='UNDER'
    if r['evidence_tier'] in ['GENUINE_PROSPECTIVE_W8_PLUS','ORIGINAL_AUTHENTICATED_PREGAME']:
        assert instant(r['decision_UTC'])<=instant(r['selection_server_UTC'])<instant(r['kickoff_UTC']) and r['server_receipt_reference']
    if r['evidence_tier']=='GENUINE_PROSPECTIVE_W8_PLUS':assert (instant(r['kickoff_UTC'])-instant(r['selection_server_UTC'])).total_seconds()>300,'V5_PREGAME_PERSISTENCE_BUFFER_FAILED'
    if r['status'] in ['WIN','LOSS','PUSH']:
        assert side in r['offered_sides'] and r['appearance']=='PLAYED' and r['graded_UTC'] and r['outcome_evidence_reference']
        assert instant(r['kickoff_UTC'])<instant(r['graded_UTC'])<=datetime.now(timezone.utc)
        actual=r['actual'];scale=CATEGORIES[r['category']][3];assert isinstance(actual,(int,float)) and not isinstance(actual,bool) and math.isfinite(actual)
        k=round(actual*scale);assert abs(actual*scale-k)<1e-8;actual=Decimal(k)/Decimal(scale)
        if CATEGORIES[r['category']][2]=='count':assert actual>=0
        if r['category']=='anytime_td':
            c=r['event_components'];ru=integer(c.get('rushing_tds'));re=integer(c.get('receiving_tds'));assert ru is not None and re is not None and actual==int(ru+re>0),'ANYTIME_RUSH_REC_COMPONENT_MISMATCH'
        if r['category']=='fpts':
            vals={key:integer(r['score_components'].get(key),key in SIGNED) for key in WEIGHTS};assert all(v is not None for v in vals.values()) and sum(WEIGHTS[key]*vals[key] for key in vals)==k and r.get('unique_event_credits_verified') is True,'EXACT_CHART_COMPONENT_OR_UNIQUE_CREDIT_MISMATCH'
        if r['comparator']=='AT_LEAST':expected='WIN' if (actual>=Decimal(str(r['line'])))==(side=='OVER') else 'LOSS'
        elif r['comparator']=='AT_LEAST_ONE_RUSH_REC_TD':assert actual in [0,1];expected='WIN' if actual==1 else 'LOSS'
        else:assert r['comparator']=='STRICT_OVER_UNDER';expected=grade(actual,r['line'],side)
        assert r['status']==expected,'RETAINED_WIN_LOSS_BOUNDARY_MISMATCH'
    if r['status']=='ABSTAIN':assert side=='ABSTAIN'
    if r['status']=='UNAVAILABLE_FORECAST':assert side is None
    if r['status'] in ['VOID','DNP','UNKNOWN_PARTICIPATION','MISSING_ACTUAL']:
        assert r.get('graded_UTC') and r.get('outcome_evidence_reference')
        assert instant(r['kickoff_UTC'])<instant(r['graded_UTC'])<=datetime.now(timezone.utc)
    if r['status']=='DNP':assert r['appearance']=='DNP' and r.get('actual') is None
    if r['status']=='VOID':assert r.get('void_evidence_reference') and r['appearance'] in ['VOID','CANCELLED'] and r.get('actual') is None and r.get('void_kind')=='STATISTICAL_EVENT_VOID','VENUE_SETTLEMENT_MUST_REMAIN_SEPARATE_FROM_STATISTICAL_RESULT'
    return r

def opportunity(r):return tuple(r[k] for k in ['game_id','player_id','category'])
def offer_case(r):return tuple(r[k] for k in ['game_id','player_id','category','venue','product','line_tier','period','comparator','line','decision_horizon','evidence_tier'])
def snapshot_key(r):
    keys=['category','game_id','player_id','method_id','method_version','selector_id','policy_id','venue','product','line_tier','evidence_tier']
    # v5 first-paper policy did not create an extra primary by alternate line tier.
    if r['evidence_tier']=='GENUINE_PROSPECTIVE_W8_PLUS':keys.remove('line_tier')
    return tuple(r[k] for k in keys)
def deduplicate(rows):
    """Append-only grade corrections; first frozen snapshot, never best revision."""
    versions={}
    fixed=['record_kind','record_id','method_id','method_version','selector_id','policy_id','category','game_id','player_id','espn_event_id','season','week','scoring_snapshot_id','selected_side','offered_sides','line','comparator','period','scoring_contract_id','decision_UTC','kickoff_UTC','evidence_tier','point','point_type','p_under','p_push','p_over','probability_line','law','probability_inference_evidence_reference','information_set_id','forecast_id','model_id','model_SHA256','position','role_evidence_reference','slate_id','membership_evidence_reference','candidate_universe_SHA256','slate_decision_UTC','slate_earliest_kickoff_UTC','frozen_rank','selection_run_id','selection_server_UTC','server_receipt_reference','server_receipt_SHA256','conditioning','feature_cutoff_UTC','forecast_generated_UTC',*STRATA]
    monotonic=defaultdict(list)
    for r in rows:
        validate_row(r);old=versions.get(r['record_id'])
        if r['method_id'] in PROB_METHODS and r['status']!='UNAVAILABLE_FORECAST':monotonic[tuple(r[k] for k in ['game_id','player_id','category','method_id','method_version','information_set_id','comparator'])].append(r)
        if old:
            if r==old:continue
            assert r.get('supersedes_grade_id')==old['grade_id'],'CONFLICTING_OR_UNLINKED_GRADE_CORRECTION'
            assert r['grade_id']!=old['grade_id'],'GRADE_ID_REUSED'
            assert all(r.get(k)==old.get(k) for k in fixed),'CORRECTION_CHANGED_ORIGINAL_SELECTION'
            assert r.get('graded_UTC') and (not old.get('graded_UTC') or instant(r['graded_UTC'])>=instant(old['graded_UTC']))
        versions[r['record_id']]=r
    for rs in monotonic.values():
        ordered=sorted(rs,key=lambda r:Decimal(str(r['line'])) if r['line'] is not None else Decimal(0))
        for left,right in zip(ordered,ordered[1:]):
            if left['line']==right['line']:assert all(abs(left[k]-right[k])<=1e-10 for k in ['p_over','p_under','p_push']),'SAME_INFORMATION_THRESHOLD_CONFLICT'
            assert left['p_over']>=right['p_over']-1e-10 and left['p_under']<=right['p_under']+1e-10,'THRESHOLD_MONOTONICITY_FAILURE'
    first={}
    for r in versions.values():
        key=snapshot_key(r);clock=r['selection_server_UTC'] if r['evidence_tier'] in ['GENUINE_PROSPECTIVE_W8_PLUS','ORIGINAL_AUTHENTICATED_PREGAME'] else r['decision_UTC'];order=(instant(clock),r['scoring_snapshot_id']);old=first.get(key)
        if old and order==old[0]:assert r==old[1],'PAIRED_SIDES_OR_CONFLICTING_DUPLICATE_SNAPSHOT'
        if old is None or order<old[0]:first[key]=(order,r)
    result=[v[1] for _,v in sorted(first.items())];groups=defaultdict(list)
    for r in result:
        if r['policy_id']!='ALL_ELIGIBLE_OFFERS':groups[(r['slate_id'],r['category'] if r['policy_id'].startswith('CATEGORY') else 'GLOBAL',r['method_id'],r['method_version'],r['policy_id'])].append(r)
    for key,rs in groups.items():
        assert len(rs)<=int(key[-1].split('_')[1][3:]),'TOPK_EXCEEDS_FROZEN_ENTRY_BUDGET'
        assert len({r['frozen_rank'] for r in rs})==len(rs),'CONFLICTING_FROZEN_RANKS'
    return result

@lru_cache(maxsize=32)
def retained_paper(receipt_path,expected_sha):
    from paper_v5 import validate_packet,check_receipt,forecast_pool
    path=safe_file(ROOT,receipt_path,expected_sha);proof=read(path);assert Path(proof['run_id']).name==proof['run_id'];run=ROOT/'paper/runs'/proof['run_id'];m,rows=validate_packet(run);at=check_receipt(run,proof,m,rows)
    bindings=read(run/'forecast_bindings.json');pool,_=forecast_pool(ROOT/'prospective',instant(m['decision_cutoff_UTC']),set(bindings));return dict(at=at,manifest=m,rows=rows,forecasts={r['forecast_id']:r for r in pool.values()},input=read(run/'offers.json'))

def eligible_paper_offer(packet,e):
    """Source eligibility independent of whether a model could select a side."""
    cutoff=instant(packet['manifest']['decision_cutoff_UTC']);at=packet['at']
    raw=list({digest(o):o for o in packet['input']['offers'] if o['offer_id']==e['offer_id'] and o.get('observed_at_UTC')==e.get('observed_at_UTC') and o['venue']==e['venue'] and o['product']==e['product']}.values())
    if len(raw)!=1:return False
    o=raw[0]
    if o.get('lifecycle')!='OPEN' or o.get('side_states')!={s:'OPEN' for s in o['offered_sides']}:return False
    try:
        source,observed=instant(o['source_asof_UTC']),instant(o['observed_at_UTC'])
        if not source<=observed<=cutoff<=at or not 0<=(at-source).total_seconds()<=900:return False
        ss=[s for s in packet['input']['event_status'] if s['game_id']==o['game_id']]
        if len(ss)!=1:return False
        s=ss[0]
        return s['state']=='pre' and s['status_name']=='STATUS_SCHEDULED' and s['completed'] is False and s['espn_event_id']==o['espn_event_id'] and instant(s['kickoff_UTC'])==instant(o['kickoff_UTC']) and 0<=(cutoff-instant(s['observed_UTC'])).total_seconds()<=1800
    except (KeyError,TypeError,ValueError):return False

@lru_cache(maxsize=8)
def first_paper_index(receipts,coverage=False):
    first={}
    for path,h in receipts:
        packet=retained_paper(path,h)
        for r in packet['rows']:
            if r.get('primary_in_packet') and (eligible_paper_offer(packet,r) if coverage else not r.get('reasons')):
                key=tuple(r[k] for k in ['game_id','player_id','category','venue','product']);order=(packet['at'],packet['manifest']['run_id']);first[key]=min(first.get(key,order),order)
    return first

def tier_allowed(review,tier):
    allowed=review.get('qualified_evidence_tiers',[])
    return allowed.get(tier) is True if isinstance(allowed,dict) else isinstance(allowed,list) and all(isinstance(v,str) for v in allowed) and tier in allowed

def verify_future_record(r):
    assert r['method_id'] in ['P1_MEDIAN','P2_LAW'] and r['policy_id']=='ALL_ELIGIBLE_OFFERS','NO_RETAINED_ISSUANCE_FOR_THIS_FUTURE_METHOD_POLICY'
    packet=retained_paper(r['server_receipt_reference'],r['server_receipt_SHA256']);assert packet['at']==instant(r['selection_server_UTC']) and packet['manifest']['run_id']==r['selection_run_id']
    matches=[x for x in packet['rows'] if x['offer_id']==r['offer_id'] and all(x[k]==r[k] for k in ['game_id','player_id','category','line','comparator','period','scoring_contract_id','venue','product','offered_sides','espn_event_id'])];assert len(matches)==1,'PAPER_OFFER_BINDING_MISMATCH';e=matches[0]
    assert e.get('primary_in_packet') is True and e['tier']==r['line_tier'] and instant(e['kickoff_UTC'])==instant(r['kickoff_UTC'])
    receipts=tuple((p.relative_to(ROOT).as_posix(),sha(p)) for p in sorted((ROOT/'paper/receipts').glob('*.json')))
    unavailable=r['status']=='UNAVAILABLE_FORECAST';assert eligible_paper_offer(packet,e),'SOURCE_OFFER_NOT_ELIGIBLE_AT_DECLARED_SNAPSHOT'
    key=tuple(e[k] for k in ['game_id','player_id','category','venue','product']);assert first_paper_index(receipts,unavailable).get(key)==(packet['at'],r['selection_run_id']),'NOT_ORIGINAL_V5_PRIMARY_OR_COVERAGE_SNAPSHOT'
    assert instant(packet['manifest']['decision_cutoff_UTC'])==instant(r['decision_UTC']) and e.get('forecast_id')==r.get('forecast_id')
    if unavailable and not r.get('forecast_id'):
        assert all(r.get(k) is None for k in ['model_id','model_SHA256','point','law','p_under','p_push','p_over']),'MISSING_FORECAST_HAS_INVENTED_OUTPUT'
        return
    assert instant(e['cutoff_UTC'])==instant(r['decision_UTC'])
    for k in ['model_id','conditioning']:assert e.get(k)==r.get(k),'PAPER_MODEL_OR_CONDITIONING_CHANGED'
    for k in ['feature_cutoff_UTC','forecast_generated_UTC']:assert instant(e[k])==instant(r[k])
    method='P1' if r['method_id']=='P1_MEDIAN' else 'P2';assert e[method+'_side']==r['selected_side'],'ORIGINAL_PAPER_SIDE_CHANGED'
    if method=='P1':
        assert e.get('point')==r.get('point')
        if not unavailable:assert e.get('point_type')==r.get('point_type'),'ORIGINAL_PAPER_POINT_TYPE_CHANGED'
    elif r['status']!='UNAVAILABLE_FORECAST':assert all(e[k]==r[k] for k in ['p_under','p_push','p_over']),'ORIGINAL_PAPER_PROBABILITIES_CHANGED'
    if r.get('forecast_id'):
        f=packet['forecasts'][r['forecast_id']];assert f['model_SHA256']==r['model_SHA256'] and f['position']==r['position']
        assert all(f[k]==r[k] for k in ['season','week','game_id','player_id','category','espn_event_id','scoring_contract_id']),'ORIGINAL_FORECAST_IDENTITY_OR_PERIOD_CHANGED'
        assert instant(f['kickoff_UTC'])==instant(r['kickoff_UTC'])
        if method=='P2' and not unavailable:assert f['law']==r.get('law'),'ORIGINAL_FORECAST_FULL_LAW_CHANGED'

def load_records():
    m=read(MANIFEST);rows=[];receipts=[]
    for d in m['datasets']:
        review_file=safe_file(ROOT,d['review_path'],d['review_SHA256']);review=read(review_file)
        assert m['trusted_review_SHA256'].get(review['review_id'])==digest(review),'UNREGISTERED_SOURCE_REVIEW'
        assert all(review['facets'].get(k)=='QUALIFIED' for k in ['analysis','GitHub_evidence_retention','derived_aggregate_publication']),'SOURCE_FACETS_NOT_QUALIFIED'
        safe_file(ROOT,review['permission_evidence_path'],review['permission_evidence_SHA256'])
        p=safe_file(ROOT,d['path'],d['SHA256']);assert d['SHA256'] in review['approved_dataset_SHA256'],'EXACT_DATASET_SCOPE_UNQUALIFIED'
        for e in d.get('source_grade_files',[]):safe_file(ROOT,e['path'],e['SHA256'])
        j=read(p);assert j['schema']=='C-QUALIFIED-ACTUAL-PROP-ROWS-v6' and not j.get('is_fixture') and j['source_review_id']==review['review_id']
        for e in j['retained_evidence']:safe_file(ROOT,e['path'],e['SHA256'])
        assert j['retained_evidence'],'REPRODUCIBLE_MINIMUM_EVIDENCE_REQUIRED'
        for r in j['rows']:
            assert tier_allowed(review,r['evidence_tier']),'LICENSE_IS_NOT_TIMING_AUTHENTICATION'
            if r['evidence_tier']=='GENUINE_PROSPECTIVE_W8_PLUS':verify_future_record(r)
        rows.extend(j['rows']);receipts.append(dict(dataset_id=d['dataset_id'],path=d['path'],SHA256=d['SHA256'],rows=len(j['rows']),review_id=review['review_id']))
    # A newly retained grade must not silently leave a permanently empty dashboard.
    registered={d['path'] for d in m['datasets']}|{e['path'] for d in m['datasets'] for e in d.get('source_grade_files',[])}
    pending=[p.relative_to(ROOT).as_posix() for folder in [ROOT/'paper/grades',ROOT/'paper/historical'] for p in folder.glob('*.json') if read(p).get('schema') in ['C-PAPER-GRADING-v5','C-HISTORICAL-EXACT-LINE-RESULTS-v5'] and p.relative_to(ROOT).as_posix() not in registered]
    assert not pending,'RETAINED_GRADE_REQUIRES_QUALIFIED_SCORECARD_IMPORT:'+','.join(pending)
    return deduplicate(rows),receipts

def interval(rows):
    q=[r for r in rows if r['status'] in ['WIN','LOSS']];n=len(q)
    if not n:return dict(kind='N/A_NO_DECIDED_RESULTS',low=None,high=None,dependence_aware=False)
    by=defaultdict(lambda:[0,0])
    for r in q:by[(r['season'],r['week'])][r['status']=='LOSS']+=1
    if len(by)<5:
        z=1.959963984540054;p=sum(r['status']=='WIN' for r in q)/n;den=1+z*z/n;mid=(p+z*z/(2*n))/den;half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
        return dict(kind='WILSON_INDEPENDENT_BERNOULLI_DIAGNOSTIC_ONLY',low=mid-half,high=mid+half,dependence_aware=False,week_clusters=len(by))
    import numpy as np
    a=np.asarray(list(by.values()));rng=np.random.default_rng(661107);s=a[rng.integers(len(a),size=(2000,len(a)))].sum(axis=1);rates=s[:,0]/s.sum(axis=1);lo,hi=np.quantile(rates,[.025,.975])
    return dict(kind='WEEK_BLOCK_BOOTSTRAP95_2000_DRAWS',low=float(lo),high=float(hi),dependence_aware=True,week_clusters=len(by),small_cluster_caution=len(by)<20)

def side_counts(rows,side):
    q=[r for r in rows if r.get('selected_side')==side or (side=='OVER' and r.get('selected_side')=='YES')] if side!='COMBINED' else [r for r in rows if r.get('selected_side') in ['OVER','UNDER','YES']]
    c=Counter(r['status'] for r in q);w=c['WIN'];l=c['LOSS'];n=w+l;dec=[r for r in q if r['status'] in ['WIN','LOSS']];unique=len({opportunity(r) for r in dec});games=len({r['game_id'] for r in dec});weeks=len({(r['season'],r['week']) for r in dec});ci=interval(q)
    support=read(POLICY)['leader_support'];eligible=unique>=support['minimum_decided_unique_football_opportunities'] and games>=support['minimum_distinct_games'] and weeks>=support['minimum_distinct_weeks'] and ci['dependence_aware']
    return dict(selected=len(q),wins=w if n else None,losses=l if n else None,decided=n,rate=w/n if n else None,pushes=c['PUSH'],voids=c['VOID'],DNP=c['DNP'],pending=c['PENDING'],unknown_participation=c['UNKNOWN_PARTICIPATION'],missing_actuals=c['MISSING_ACTUAL'],unique_decided_football_opportunities=unique,games=games,weeks=weeks,uncertainty=ci,support_eligible_for_comparison=eligible,evidence_supported_leader='NOT_ESTABLISHED: prespecified superiority/confirmation and multiplicity review also required')

def aggregate(rows):
    c={s:side_counts(rows,s) for s in ['OVER','UNDER','COMBINED']};status=Counter(r['status'] for r in rows);o,u=c['OVER'],c['UNDER'];diff=None if not o['decided'] or not u['decided'] else 100*(o['rate']-u['rate'])
    return dict(**c,eligible_offers=len(rows),unique_football_opportunities=len({opportunity(r) for r in rows}),scored_offers=sum(r['status'] in ['WIN','LOSS','PUSH'] for r in rows),games=len({r['game_id'] for r in rows}),weeks=len({(r['season'],r['week']) for r in rows}),abstentions=status['ABSTAIN'],unavailable_forecasts=status['UNAVAILABLE_FORECAST'],states={s:status[s] for s in STATUSES},higher_side=None if diff is None else 'TIE' if abs(diff)<1e-12 else 'OVER' if diff>0 else 'UNDER',Over_minus_Under_percentage_points=diff,side_population_caution='Over/Under selections are different player/line populations; no causal side advantage inferred')

def observed_leaders(cells):
    result={}
    for side in ['OVER','UNDER','COMBINED','CATEGORY_AND_SIDE']:
        q=[]
        for c in cells:
            for s in (['OVER','UNDER'] if side=='CATEGORY_AND_SIDE' else [side]):
                v=c[s]
                if v['decided']:q.append(dict(category=c['category'],method_id=c['method_id'],method_version=c['method_version'],side=s,**v))
        if not q:result[side]=dict(state='NOT_ESTABLISHED',observed=[],reason='No qualified real-offer decided results');continue
        best=max(x['rate'] for x in q);result[side]=dict(state='HIGHEST_OBSERVED_ONLY',observed=[x for x in q if abs(x['rate']-best)<1e-12],evidence_supported='NOT_ESTABLISHED',reason='Descriptive maximum/ties; support eligibility and superiority/confirmation are separate')
    return result

def method_version(cat,method,period):
    if method in ['P2_LINKED_V8','P2_WORKLOAD_V8']:return 'C-PASS-WORKLOAD-LINK-v8/'+method+('/PASS_YD_ONLY_NOT_EXECUTED' if cat!='pass_yd' else '')
    if method=='EARLIER_PREVALENCE_V8':return 'C-EARLIER-ROLE-PREVALENCE-v8'
    arm=read(ROOT/'protocol/PROSPECTIVE_V4.json')['primary']['arms'][cat] if prospective_period(period) else 'E0_OP'
    if method in ['P1_MEDIAN','P1_MEAN','P2_LAW']:return f"{'C-FORWARD-P2-v4' if prospective_period(period) else 'C-ALL12-LAW-THRESHOLD-v2.1'}/P2_LEAF/H-MULTI/{arm}/{method}"
    return {'P3_DIRECT':'P3_HGB: no retained actual-line inference','P4_HYBRID':'NOT_EXECUTED','ALWAYS_OVER':'ALWAYS_OVER-v6 diagnostic','ALWAYS_UNDER':'ALWAYS_UNDER-v6 diagnostic'}[method]

def prospective_period(period):
    return period=='2026_W8_PLUS' or (period.startswith('2026_W') and period[6:].isdigit() and int(period[6:])>=8)

def matches(r,period,tier,policy):
    if r['evidence_tier']!=tier or r['policy_id']!=policy:return False
    if period=='2026_W8_PLUS':return r['season']==2026 and r['week']>=8
    if period.startswith('2026_W') and period!='2026_W1_W7':return r['season']==2026 and r['week']==int(period.split('W')[-1])
    return r['season']==(2026 if period=='2026_W1_W7' else int(period)) and (period!='2026_W1_W7' or 1<=r['week']<=7)

def table(rows,period='2026_W1_W7',tier=TIERS[2],policy='ALL_ELIGIBLE_OFFERS',method='PRIMARY'):
    selected=[r for r in rows if matches(r,period,tier,policy)];cells=[]
    for cat in CATEGORIES:
        mid='P2_LAW' if method=='PRIMARY' else method;q=[r for r in selected if r['category']==cat and r['method_id']==mid];eligible=[r for r in selected if r['category']==cat] if policy=='ALL_ELIGIBLE_OFFERS' else q;universe={offer_case(r) for r in eligible};missing=len(universe-{offer_case(r) for r in q})
        versions={r['method_version'] for r in q};assert len(versions)<=1,'VERSION_POOLING_REQUIRES_EXPLICIT_CHRONOLOGICAL_PROCEDURE'
        reason=('No retained exact-line prediction/selection for this procedure; qualified offer coverage retained' if missing else 'No qualified actual-offer rows; source-specific analysis/retention/contract gates remain') if not q else None
        if not q and mid=='P3_DIRECT':reason='No qualified retained exact-line P3 inference; synthetic-grid results excluded'
        if not q and mid=='P4_HYBRID':reason='No executed qualified hybrid procedure'
        if not q and policy!='ALL_ELIGIBLE_OFFERS':reason='Frozen slate/candidate/Top-K membership unavailable; no hindsight list or forced K'
        if not q and cat=='anytime_td' and not universe:reason='No qualified genuinely offered YES market; NO/Under not invented'
        if not q and cat=='anytime_td' and universe and mid in ['P1_MEAN','P1_MEDIAN','ALWAYS_UNDER','ALWAYS_OVER']:reason='This point/constant Over-Under procedure has no matching offered event side; YES law/event procedure remains separate'
        if not q and cat=='fpts' and not universe:reason='Exact venue/chart contract and full label/offer qualification unavailable'
        strata=[dict(zip(STRATA,key)) for key in sorted({tuple(r[x] for x in STRATA) for r in eligible})]
        totals=aggregate(q);totals['eligible_offers']=len(universe);totals['scored_games']=len({r['game_id'] for r in q if r['status'] in ['WIN','LOSS','PUSH']});totals['scored_weeks']=len({(r['season'],r['week']) for r in q if r['status'] in ['WIN','LOSS','PUSH']});totals['games']=len({r['game_id'] for r in eligible});totals['weeks']=len({(r['season'],r['week']) for r in eligible});totals['unique_football_opportunities']=len({opportunity(r) for r in eligible});totals['unavailable_forecasts']+=missing;totals['states']['UNAVAILABLE_FORECAST']+=missing;totals['missing_method_records']=missing
        cells.append(dict(category=cat,label=LABELS[cat],method_id=mid,method_version=next(iter(versions)) if versions else method_version(cat,mid,period),selector='P2_EXACT_LINE_SELECTOR-v4.1' if mid=='P2_LAW' else mid+'-strict-v6',policy_id=policy,period=period,evidence_tier=tier,reason=reason,strata=strata,strata_count=len(strata),pooling_disclosure='ALL_ELIGIBLE_OFFERS explicit full-procedure aggregate; cross-category leaders only within a common stratum' if len(strata)>1 else 'One stratum or no qualified rows',**totals))
    return cells

def scorecard(rows,receipts):
    periods=['2026_W1_W7']+[f'2026_W{w}' for w in range(1,8)]+['2025','2024','2023','2022','2026_W8_PLUS'];views=[]
    # One baseline view per period, plus actual supported method/policy/tier cells.
    combos={(p,TIERS[3] if p=='2026_W8_PLUS' else TIERS[2],'ALL_ELIGIBLE_OFFERS','PRIMARY') for p in periods}
    combos|={('2026_W1_W7',TIERS[2],'ALL_ELIGIBLE_OFFERS',m) for m in METHODS}
    for r in rows:
        p='2026_W8_PLUS' if r['season']==2026 and r['week']>=8 else '2026_W1_W7' if r['season']==2026 else str(r['season']);combos.add((p,r['evidence_tier'],r['policy_id'],r['method_id']));combos.add((p,r['evidence_tier'],r['policy_id'],'PRIMARY'))
        if r['season']==2026:
            wp=f"2026_W{r['week']}";combos.add((wp,r['evidence_tier'],r['policy_id'],r['method_id']));combos.add((wp,r['evidence_tier'],r['policy_id'],'PRIMARY'))
            if wp not in periods:periods.append(wp)
    for p,t,k,m in sorted(combos):
        cells=table(rows,p,t,k,m);groups=defaultdict(list)
        for r in rows:
            if matches(r,p,t,k):groups[tuple(r[x] for x in STRATA)].append(r)
        leaders=[]
        for key,rr in sorted(groups.items()):
            ranked=[c for method in (METHODS if m=='PRIMARY' else [m]) for c in table(rr,p,t,k,method)]
            leaders.append(dict(stratum_id=digest(list(key))[:16],stratum=dict(zip(STRATA,key)),cells=table(rr,p,t,k,m),leaders=observed_leaders(ranked)))
        overall=leaders[0]['leaders'] if len(leaders)==1 else observed_leaders([]) if not leaders else dict(state='NO_POOLED_CROSS_STRATUM_LEADER',groups=len(leaders))
        views.append(dict(period=p,evidence_tier=t,policy_id=k,method=m,cells=cells,leader_scope='ALL_EVALUATED_PROCEDURES' if m=='PRIMARY' else m,leader_groups=leaders,leaders=overall))
    last=max((r['graded_UTC'] for r in rows if r.get('graded_UTC')),key=instant,default=None)
    templates={key:{cat:{method:method_version(cat,method,p) for method in METHODS} for cat in CATEGORIES} for key,p in [('historical','2026_W1_W7'),('prospective','2026_W8_PLUS')]}
    display_keys=['record_kind','record_id','offer_id','category','method_id','policy_id','game_id','player_id','player_name','position','season','week','venue','product','line_tier','evidence_tier','decision_horizon','line','point','point_type','p_under','p_push','p_over','selected_side','actual','status','appearance','decision_UTC','kickoff_UTC','graded_UTC','source_snapshot_clocks']
    display=[{k:r[k] for k in display_keys if k in r} for r in rows]
    return dict(schema='C-ACTUAL-PROP-ACCURACY-v6',record_projection='C-DISPLAY-ROWS-v8;everycase retained;full laws/features/provenance in input_receipts canonical datasets',policy_SHA256=sha(POLICY),dataset_manifest_SHA256=sha(MANIFEST),retained_rows=len(rows),records=display,input_receipts=receipts,last_graded_update_UTC=last,message='No qualified real-prop results yet' if not any(r['status'] in ['WIN','LOSS'] for r in rows) else 'Own selected sides against exact recorded offers',periods=periods,evidence_tiers=TIERS,methods=['PRIMARY',*METHODS],policies=policies(),views=views,unavailable_cells=table([]),method_reference_templates=templates,policy_status='Top-K membership and candidate-slate evidence required; per-leg accuracy is not entry6/6',settlement='Statistical grading distinct from venue settlement',uncertainty_rules=read(POLICY)['leader_support'],source_facets_reference='protocol/SOURCE_FACETS_V6.json',source_facets=read(ROOT/'protocol/SOURCE_FACETS_V6.json'))

def side_text(c):return 'N/A / 0 / N/A' if not c['decided'] else f"{c['wins']}-{c['losses']} / {c['decided']} / {100*c['rate']:.2f}%"
def markdown(j,period='2026_W1_W7',tier=None,policy='ALL_ELIGIBLE_OFFERS',method='PRIMARY',stratum='ALL'):
    tier=tier or (TIERS[3] if prospective_period(period) else TIERS[2]);v=next(v for v in j['views'] if v['period']==period and v['method']==method and v['evidence_tier']==tier and v['policy_id']==policy)
    if stratum!='ALL':
        group=next(g for g in v['leader_groups'] if g['stratum_id']==stratum);v=v|dict(cells=group['cells'],leaders=group['leaders'],leader_groups=[group])
    s='| Category | Method/version; policy | Over W-L / decided / rate | Under W-L / decided / rate | Combined W-L / decided / rate | Eligible/scored | Games/weeks | Uncertainty | Evidence tier |\n|---|---|---|---|---|---|---|---|---|\n'
    for c in v['cells']:s+=f"| {c['label']} | {c['method_version']}; {c['policy_id']} | {side_text(c['OVER'])} | {side_text(c['UNDER'])} | {side_text(c['COMBINED'])} | {c['eligible_offers']}/{c['scored_offers']} | {c['games']}/{c['weeks']} | {'N/A' if not c['COMBINED']['decided'] else c['COMBINED']['uncertainty']['kind']} | {c['evidence_tier']} |\n"
    for label,key in [('Most accurate Over category','OVER'),('Most accurate Under category','UNDER'),('Combined leader','COMBINED'),('Highest category-and-side','CATEGORY_AND_SIDE')]:
        leader=v['leaders'].get(key,dict(state='NOT_ESTABLISHED'));values=leader.get('observed',[])
        detail='; '.join(f"{x['category']} / {x['method_version']} / {x['side']}: {side_text(x)} ({'support eligible; superiority unestablished' if x['support_eligible_for_comparison'] else 'insufficient support'})" for x in values)
        missing='NOT POOLED — book-specific observed maxima below; evidence-supported leader NOT ESTABLISHED' if len(v['leader_groups'])>1 else 'NOT ESTABLISHED — no comparable qualified decided results'
        s+=f"\n{label}: {detail or missing}.\n"
    if len(v['leader_groups'])>1:
        s+='\nNo pooled cross-stratum leader. All eligible offers is an explicitly mixed whole-procedure view.\n'
        for group in v['leader_groups']:
            s+='\nComparable stratum: '+json.dumps(group['stratum'],sort_keys=True)+'\n'
            for side,value in group['leaders'].items():s+='\n'+side+': '+('; '.join(x['category']+' / '+x['method_version']+' / '+x['side']+' '+side_text(x) for x in value.get('observed',[])) or 'NOT ESTABLISHED')+'\n'
    return s

def csv_text(j):
    cols=['period','evidence_tier','policy_id','category','method_id','method_version','eligible_offers','scored_offers','games','weeks','abstentions','unavailable_forecasts','reason'];flat=[]
    for v in j['views']:
        groups=[('ALL',{},v['cells'])]+[(g['stratum_id'],g['stratum'],g['cells']) for g in v['leader_groups']]
        for sid,stratum,cells in groups:
            for c in cells:
                r=dict(row_kind='SUMMARY_VIEW_NOT_NEW_OBSERVATION',view_method=v['method'],stratum_id=sid,**{k:stratum.get(k) for k in STRATA},**{k:c.get(k) for k in cols})
                for side in ['OVER','UNDER','COMBINED']:
                    for k in ['selected','wins','losses','decided','rate','pushes','voids','DNP','pending','unknown_participation','missing_actuals']:r[side+'_'+k]=c[side][k]
                flat.append(r)
    f=io.StringIO();w=csv.DictWriter(f,fieldnames=list(flat[0]),lineterminator='\n');w.writeheader();w.writerows(flat);return f.getvalue()

def build():
    rows,receipts=load_records();j=scorecard(rows,receipts);stable_write(OUT/'scorecard.json',j);(OUT/'HEADLINE.md').write_text(markdown(j));(OUT/'PROSPECTIVE_HEADLINE.md').write_text(markdown(j,'2026_W8_PLUS'));stable_write(ROOT/'docs/data/actual-accuracy-v6.json',j);(OUT/'SCORECARD.csv').write_text(csv_text(j))
    for path in [ROOT/'START_HERE.md',OUT/'README.md']:
        if path.exists() and '<!-- ACTUAL_SCORECARD_START -->' in path.read_text():
            text=path.read_text();before,rest=text.split('<!-- ACTUAL_SCORECARD_START -->',1);_,after=rest.split('<!-- ACTUAL_SCORECARD_END -->',1);path.write_text(before+'<!-- ACTUAL_SCORECARD_START -->\n'+markdown(j)+'<!-- ACTUAL_SCORECARD_END -->'+after)
    b=read(ROOT/'docs/build.json');b['actual_accuracy_SHA256']=sha(ROOT/'docs/data/actual-accuracy-v6.json');b['actual_accuracy_policy']='C-ACTUAL-ACCURACY-v6';stable_write(ROOT/'docs/build.json',b);print(j['message']);print('ACTUAL_NFL_DECIDED',sum(r['status'] in ['WIN','LOSS'] for r in rows))

def validate():
    rows,receipts=load_records();expected=scorecard(rows,receipts);assert read(OUT/'scorecard.json')==expected and read(ROOT/'docs/data/actual-accuracy-v6.json')==expected
    assert (OUT/'HEADLINE.md').read_text()==markdown(expected) and (OUT/'PROSPECTIVE_HEADLINE.md').read_text()==markdown(expected,'2026_W8_PLUS') and (OUT/'SCORECARD.csv').read_text()==csv_text(expected),'CHAT_CSV_LEDGER_MISMATCH';assert read(ROOT/'docs/build.json')['actual_accuracy_SHA256']==sha(ROOT/'docs/data/actual-accuracy-v6.json');print('ACTUAL_ACCURACY_PARITY',len(rows))
    for p in [ROOT/'START_HERE.md',OUT/'README.md']:
        assert p.read_text().split('<!-- ACTUAL_SCORECARD_START -->\n',1)[1].split('<!-- ACTUAL_SCORECARD_END -->',1)[0]==markdown(expected),'CHECKPOINT_HEADLINE_DRIFT'

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['build','validate','chat']);a=p.parse_args();build() if a.command=='build' else validate() if a.command=='validate' else print(markdown(read(OUT/'scorecard.json')))
