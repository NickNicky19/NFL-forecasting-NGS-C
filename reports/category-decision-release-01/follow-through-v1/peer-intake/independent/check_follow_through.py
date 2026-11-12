"""Independent stdlib arithmetic and AST-only source review; no foreign code/model execution."""
from pathlib import Path
import ast,collections,csv,gzip,hashlib,io,json,lzma,math,resource,sys,time
from datetime import datetime,timezone
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;REPO=Path(__file__).resolve().parents[5]

def read(n):
 p=ROOT/n;b=p.read_bytes();return json.loads(lzma.decompress(b) if p.suffix=='.xz' else b)
def near(a,b):return abs(float(a)-float(b))<=1e-10*max(1.,abs(float(a)),abs(float(b)))
def own(sides):
 for side in ['OVER','UNDER','COMBINED']:
  x=sides[side];assert isinstance(x['decided'],int) and x['decided']>=0
  if x['decided']==0:
   assert x['wins'] in [None,0] and x['losses'] in [None,0] and x['rate'] is None
  else:
   assert all(isinstance(x[k],int) and x[k]>=0 for k in ['wins','losses']) and x['wins']+x['losses']==x['decided']
   assert near(x['rate'],x['wins']/x['decided'])
 for k in ['wins','losses','decided']:
  c=sides['COMBINED'][k];a=sides['OVER'][k];b=sides['UNDER'][k]
  assert (0 if c is None else c)==(0 if a is None else a)+(0 if b is None else b)
def main():
 cpu=time.process_time();a=read('A_CONTRIBUTION.json.xz');w=read('A_WEEKLY_COVERAGE.json.xz');ack=read('B_JOIN_ACKNOWLEDGMENT.json.xz');sel=read('B_SELECTOR_VERIFICATION.json.xz');mean=read('COUNT_A_MEAN_OWN_WEEKLY_REUSE.json');extension=read('A_COUNTA_EXTENSION.json.xz')
 ledger=read('FETCH_LEDGER.json');hash_checks=[]
 names=['A_CONTRIBUTION','A_WEEKLY_COVERAGE','B_JOIN_ACKNOWLEDGMENT','B_SELECTOR_VERIFICATION','A_COUNTA_EXTENSION','A_COUNTA_CORRECTOR_SOURCE']
 for n in names:
  p=ROOT/(n+('.py.xz' if n=='A_COUNTA_CORRECTOR_SOURCE' else '.json.xz'));b=lzma.decompress(p.read_bytes());expected=next(x['decoded_SHA256'] for x in ledger if x.get('name')==n)
  actual=hashlib.sha256(b).hexdigest();assert actual==expected,(n,'SHA256');hash_checks.append({'member':p.name,'decoded_bytes':len(b),'SHA256':actual})
 assert len(a['rows'])==12 and len(w['rows'])==242 and len(w['procedures'])==36
 scored=[];unscored=[];fallback_unknown=[];role_unknown=[]
 for x in a['rows']:
  cat=x['category'];s=x.get('own_sides')
  if s is None:assert x.get('exact_procedure') is None and x.get('actual_scored_season_weeks',[])==[];unscored.append(cat);continue
  own(s);c=x['coverage'];eligible=c['eligible'];assert s['COMBINED']['selected']<=eligible
  if 'states' in c:assert sum(c['states'].values())==eligible and c['states'].get('WIN',0)==s['COMBINED']['wins'] and c['states'].get('LOSS',0)==s['COMBINED']['losses']
  assert x['actual_scored_season_weeks']==[[2026,i] for i in range(1,6)] and 'UNVERIFIED' in x['evidence_tier'] and x['primary_switch_executed_by_A'] is False
  if '' in c.get('fallback_states',{}):assert c['fallback_count']=='UNSPECIFIED';fallback_unknown.append(cat)
  for p in x.get('matched_strong_control_pairs',[])+x.get('registered_learned_pairs',[]):
   if p.get('accuracy_change') is not None:assert near(p['accuracy_change'],(p['left_wins']-p['right_wins'])/p['common_decided'])
   if p.get('side_disagreements') is not None:
    d=p['side_disagreements'];delta=p['left_wins']-p['right_wins'];assert d>=abs(delta) and (d+delta)%2==0
  scored.append({'category':cat,'procedure':x['exact_procedure'],'own':s,'eligible':eligible,'actual_weeks':[1,2,3,4,5]})
 assert len(scored)==10 and set(unscored)=={'anytime_td','nick-chart-ppr-v1'}
 bp=w['annual_source_policy'];assert [(x['book_id'],x['name']) for x in bp['book_priority']]==[(68,'DraftKings NJ'),(69,'FanDuel NJ'),(79,'bet365 NJ')]
 assert bp['cutoff_qualified'] is False and bp['quote_time']=='UNKNOWN_NOT_RETAINED'
 weekly_scored=0;weekly_unknown=0;weekly_groups=collections.defaultdict(list)
 for x in w['rows']:
  assert 1<=x['week']<=8 and x['season']==2026
  if x['procedure_ref'] is None:
   assert x['category'] in ['anytime_td','nick-chart-ppr-v1'] and x['status']=='NO_COMPATIBLE_OFFER_PRODUCT_IN_THIS_SCOPE';weekly_unknown+=1;continue
  assert x['procedure_ref'] in w['procedures']
  p=w['procedures'][x['procedure_ref']]
  if p.get('role_scope')=='UNKNOWN':role_unknown.append(x['procedure_ref'])
  if not isinstance((x.get('COMBINED') or {}).get('wins'),int):weekly_unknown+=1;continue
  own(x);c=x['counts'];assert c['decided']==x['COMBINED']['decided'];assert c['selected']==x['COMBINED']['selected']
  if all(isinstance(c.get(k),int) for k in ['eligible','available','unavailable','selected']):assert c['available']+c['unavailable']==c['eligible'] and c['selected']<=c['available']
  if isinstance(c.get('states'),dict) and isinstance(c.get('eligible'),int):assert sum(c['states'].values())==c['eligible']
  if '' in c.get('fallback_states',{}):assert c['fallback']=='UNKNOWN'
  if x['status']=='SCORED_ACTUAL_LINES_TIMING_UNVERIFIED':assert x['week'] in [1,2,3,4,5] and x['quote_observation_UTC']=='UNKNOWN'
  weekly_groups[(x['procedure_ref'],x['panel'])].append(x);weekly_scored+=1
 # The visible weekly TD references are explicitly LEGACY, so cannot qualify the corrected mean.
 for ref in ['P002','P013']:
  assert w['procedures'][ref]['procedure_version']=='9c48aab650f35a60631fd5d6af2cef4b8c513416fe0f9b2c61591d7f8af4b85f'
  assert w['procedures'][ref]['output']=='legacy_empirical_point'
 f860='f8607aa99a94c7c1c9ab5c89599e07eba9b15527749b092b225f368032881e83'
 assert mean['procedure_version']==f860 and mean['legacy_product_used_to_fill_mean_weeks'] is False
 for f in mean['source_files']:
  p=REPO/f['path'];assert p.stat().st_size==f['bytes'] and hashlib.sha256(p.read_bytes()).hexdigest()==f['SHA256']
 rawp=REPO/mean['source_files'][0]['path'];raw=list(csv.DictReader(gzip.open(rawp,'rt')));raw=[x for x in raw if x['category']=='pass_td' and x['method']=='COUNT_A_MEAN' and x['product']=='mean_objective_point']
 cumulative=list(csv.DictReader((REPO/mean['source_files'][1]['path']).open()));cm=next(x for x in cumulative if x['category']=='pass_td' and x['method']=='COUNT_A_MEAN' and x['product']=='mean_objective_point');assert cm['procedure_version']==f860
 archived=json.load(gzip.open(REPO/mean['source_files'][2]['path'],'rt'));am=next(x for x in archived if x['category']=='pass_td' and x['method']=='COUNT_A_MEAN' and x['product']=='mean_objective_point');assert f860 in am['procedure_id'] and len(am['week_rows'])==7
 assert set(mean['old_alias'].split('::'))==set(mean['new_alias'].split('::')) and f860 in mean['old_alias']
 sums={side:{k:0 for k in ['wins','losses','decided']} for side in ['OVER','UNDER','COMBINED']};witness=[]
 for x in mean['actual_own_rows']:
  week=x['week'];assert 1<=week<=5 and x['product']=='mean_objective_point' and f860 in x['exact_procedure'];own(x)
  r=next(z for z in raw if int(z['week'])==week);ar=next(z for z in am['week_rows'] if int(z['week'])==week);assert r==ar
  for side in ['OVER','UNDER']:
   for k in ['wins','losses','decided']:assert x[side][k]==int(r[side.lower()+'_'+k]);sums[side][k]+=x[side][k]
  for k,field in [('wins','correct'),('decided','decided')]:assert x['COMBINED'][k]==int(r[field])
  for k in ['wins','losses','decided']:sums['COMBINED'][k]+=x['COMBINED'][k]
  assert x['source_issue_clock']=='UNVERIFIED' and x['games']=='NOT_EXPORTED_FOR_THIS_MEAN_WEEKLY_ROW' and x['fallback']=='UNSPECIFIED_NOT_ZERO'
  witness.append({'week':week,'wins':x['COMBINED']['wins'],'decided':x['COMBINED']['decided']})
 assert witness==[{'week':1,'wins':4,'decided':9},{'week':2,'wins':13,'decided':25},{'week':3,'wins':14,'decided':24},{'week':4,'wins':14,'decided':23},{'week':5,'wins':4,'decided':5}]
 td=next(x for x in a['rows'] if x['category']=='pass_td');assert td['exact_procedure']==mean['new_alias']
 for side in sums:
  for k,v in sums[side].items():assert v==mean['combined'][side][k]==td['own_sides'][side][k]
 # A genuine B receipt is separate from this C arithmetic calculation.
 assert ack['id'].startswith('B-') and len(ack['annual_records'])==64 and ack['W5_overlap']['state']=='UNKNOWN_PRIVATE_NORMALIZED_MEMBERSHIP_NOT_EXPORTED'
 assert ack['nonpooled_week_union']['pooled_record']=='NOT_ESTABLISHED'
 for x in ack['annual_records']:
  own({side.upper():{z:x[side+'_'+z] for z in ['wins','losses','decided','rate']} for side in ['over','under','combined']})
  for k in ['wins','losses','decided','selected']:assert (x['combined_'+k] or 0)==(x['over_'+k] or 0)+(x['under_'+k] or 0)
 for x in ack['selected_paired_records']:
  d=x['left_wins']-x['right_wins'];assert abs(d)<=x['side_disagreements']
  if 'candidate_correct_control_wrong' in x:assert x['candidate_correct_control_wrong']-x['control_correct_candidate_wrong']==d
 assert sel['state']=='PASS_WITHIN_FOUR_WEEK_CONDITIONAL_RETROSPECTIVE_SCOPE' and sel['canonical_membership_rows']==192
 assert [x['week'] for x in sel['weeks']]==[5,6,7,8] and sel['tested_scored_historical_weeks']==4 and sel['five_week_primary_qualification'] is False
 for policy in ['saved_control','candidate']:
  states=collections.Counter();sides={z:collections.Counter() for z in ['over','under']};selected=0
  for wrow in sel['weeks']:
   n=wrow['selected'][policy];st=wrow['states'][policy];assert sum(st.values())==n
   selected+=n;states.update(st)
   for side in sides:sides[side].update(wrow['own_sides'][policy].get(side,{}))
  c=sel['cumulative'][policy];assert selected==c['selected']==96 and dict(states)==c['states'] and states['hit']+states['miss']==c['decided']==93 and near(c['accuracy'],states['hit']/93)
  for side in sides:assert dict(sides[side])==c['own_sides'][side]
 assert sel['cumulative']['saved_control']['states']['hit']==48 and sel['cumulative']['candidate']['states']['hit']==50
 assert [sel['cumulative']['saved_control']['own_sides'][z]['hit'] for z in ['over','under']]==[22,26]
 assert [sel['cumulative']['candidate']['own_sides'][z]['hit'] for z in ['over','under']]==[21,29]
 dis=sel['membership_disagreements'];assert dis['common_same_side_policy_memberships']==88 and dis['control_removed']==dis['candidate_added']==8
 assert dis['added_states']['hit']-dis['removed_states']['hit']==dis['net_hits']==2
 assert sel['weeks'][-1]['candidate_selected_model_rows']==0
 # Parse the published corrector; do not import or execute it.
 src=lzma.decompress((ROOT/'A_COUNTA_CORRECTOR_SOURCE.py.xz').read_bytes());spec=next(x for x in extension['code'] if x['source_path']=='tools/modern_count_a_mean_v3.py');assert len(src)==spec['bytes']==31195 and hashlib.sha256(src).hexdigest()==spec['sha256']
 tree=ast.parse(src);fun=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='correct_fallbacks');text=ast.get_source_segment(src.decode(),fun)
 assert 'result[index] = prior.mean' in text and 'reasons != ""' in text and 'np.array_equal' in text and 'warm = reasons == ""' in text
 assert extension['identity']['procedure_version']==f860 and extension['exact_callable']['function']=='predict_verified_mean' and extension['exact_callable']['corrector_function']=='correct_fallbacks'
 assert extension['stages']['current_inference']=='NOT_EXECUTED' and extension['stages']['producer_extension_catalog']=='NOT_IMPLEMENTED_AT_fa919; exact sites above'
 result={'id':'C-FOLLOW-THROUGH-INDEPENDENT-PEER-REVIEW-v1','checked_UTC':datetime.now(timezone.utc).isoformat(),'status':'PASS_RECEIVED_PUBLIC_ARITHMETIC_AND_STATIC_BINDINGS;CONDITIONAL_SOURCE_SCOPE','source_hashes_verified':hash_checks,'A_contribution_rows':12,'A_scored_category_rows':len(scored),'A_no_compatible_product_categories':unscored,'A_category_own_records':scored,'A_weekly_source_rows':242,'A_projected_procedures':36,'A_weekly_scored_rows_checked':weekly_scored,'A_weekly_no_score_rows_preserved':weekly_unknown,'A_projected_unknown_role_refs':sorted(set(role_unknown)),'fallback_blank_key_categories':'Explicit UNSPECIFIED/UNKNOWN, not zero: '+','.join(fallback_unknown),'annual_book_priority':bp['book_priority'],'quote_time':bp['quote_time'],'COUNT_A_MEAN':{'exact_procedure_version':f860,'direct_own_weekly_witnesses':witness,'combined':mean['combined'],'proof':'Actual cached COUNT_A_MEAN/mean_objective_point raw weekly CSV and original cumulative procedure-version row, plus archived own week rows; no legacy tie inference','legacy_P002_P013':'9c48 legacy products remain separate','per_week_games_and_source_clocks':'UNKNOWN_NOT_UPGRADED','five_week':'DURATION_AT_UNVERIFIED_QUOTE_TIER_ONLY;NOT_ADMISSION'},'B_owner_receipt':{'id':ack['id'],'annual_records_checked':64,'selected_pairs_checked':len(ack['selected_paired_records']),'qualification':ack['qualification'],'W5_overlap':'UNKNOWN;NO_CROSS_SOURCE_POOLED_RECORD','verification_identity':'Actual published B acknowledgement is received; this C calculation does not impersonate B or independently inspect its private underlying source.'},'selector':{'owner_policy':sel['owner_protocol'],'actual_ranker_SHA256':sel['actual_ranker_sha256'],'weeks':[5,6,7,8],'control':'48W45L/93,3unknown,96selected','candidate':'50W43L/93,3unknown,96selected','control_own_over_under_wins':[22,26],'candidate_own_over_under_wins':[21,29],'paired_net_hits':2,'five_week_primary_qualification':False,'week8_candidate_model_selections':0,'scope':'Actual B independent owner receipt; C checked public weekly/cumulative arithmetic, not repeated raw regrading or production execution.','incumbent_limit':sel['current_v2_incumbent_historical_comparison']},'corrector_AST_only':{'SHA256':hashlib.sha256(src).hexdigest(),'bytes':len(src),'function':'correct_fallbacks','formula':'Only explicit nonempty fallback reasons are replaced with the actually trained role/global prior.mean; warm bit identity guard is present.','foreign_source_imported_or_executed':False,'actual_producer_corrector_application_or_inference':'NOT_VERIFIED_BY_AST_OR_PREPARED_PACKAGE'},'new_GETs':0,'new_fits':0,'new_model_inference':0,'new_NFL_observations':0,'CPU_seconds':time.process_time()-cpu,'peak_RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,'limits':['Protected source membership, per-offer clocks, historical feature vintages and fitted artifacts were not independently inspected.','An actual B verification receipt is acknowledged at its own scope; this does not extend its four-week selector into five weeks or prove live admission.','Current producer integration remains distinct from code publication, restoration and metadata availability.']}
 (HERE/'INDEPENDENT_FOLLOW_THROUGH_REVIEW.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ['A_category_own_records','source_hashes_verified','COUNT_A_MEAN','B_owner_receipt','selector','corrector_AST_only']}))
if __name__=='__main__':main()
