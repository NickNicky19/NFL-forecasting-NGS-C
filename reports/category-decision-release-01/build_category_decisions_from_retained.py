"""TEMP draft mechanically assembled from admitted aggregate records.
The coordinator reviews/decides; this is not a grader or a release executor.
"""
from pathlib import Path
import json,gzip,lzma,hashlib,datetime,collections
ROOT=Path('/workspace/ngs-c');OUT=Path('/workspace/category-decision-draft')
R=ROOT/'reports/category-decision-release-01';E=R/'evidence'
CATS=[('pass_yd','Passing yards'),('pass_td','Passing touchdowns'),('pass_cmp','Completions'),('pass_att','Pass attempts'),('pass_int','Interceptions thrown'),('rush_yd','Rushing yards'),('rush_att','Rushing attempts'),('rec','Receptions'),('rec_yd','Receiving yards'),('rush_rec_yd','Rush + receiving yards'),('anytime_td','Anytime rushing-or-receiving touchdown'),('nick-chart-ppr-v1','Exact nick-chart-ppr-v1 fantasy points')]
def load(p):
 p=Path(p);b=p.read_bytes();b=gzip.decompress(b) if p.suffix=='.gz' else lzma.decompress(b) if p.suffix=='.xz' else b;return json.loads(b)
def b(p):
 p=Path(p);return {'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'SHA256':hashlib.sha256(p.read_bytes()).hexdigest()}
def write(name,j):(OUT/name).write_text(json.dumps(j,indent=2,allow_nan=False)+'\n')
def side(x):
 if x is None:return {'wins':None,'losses':None,'decided':0,'rate':None}
 n=x.get('decided',0);w=x.get('wins');l=x.get('losses');assert n==(w or 0)+(l or 0)
 return {'wins':w,'losses':l,'decided':n,'rate':w/n if n else None,'selected':x.get('selected')}
def sameconstants(r):
 o,u=r['OVER'],r['UNDER'];n=r['COMBINED']['decided'];return {'ALWAYS_OVER':{'wins':o['wins']+u['losses'],'decided':n},'ALWAYS_UNDER':{'wins':o['losses']+u['wins'],'decided':n},'scope':'Same procedure own decided pool only, not a newly approved constant-side policy.'}
summary=load(R/'intake/A_EXECUTION_SUMMARY.json.xz');week=load(R/'intake/NEW_EXACT_PRODUCT_WEEK_MATRIX.json.xz');live=load(R/'website/LIVE_PRODUCT_BINDINGS.json');liveby={x['category']:x for x in live['rows']};ownerqueue=load(R/'website/EXACT_OWNER_QUEUE.json')
old=load(ROOT/'reports/post-wave-5w-v1/HEADLINE_ACTUAL_LINE_REFERENCE_V1_1.json');oldby={x['category']:x for x in old};archive=load(ROOT/'reports/abc-championship/continuation-v2/A_W1_W7_ARCHIVED_SCORES.json.gz');qa=load(ROOT/'reports/abc-championship/execution-closure-02/QUALIFICATION_TABLE.json.gz')['rows'];qby={x['procedure_id']:x for x in qa if x.get('source_panel')=='A_FIXED_W1_W7_ARCHIVED_POINT_PANEL'}
olddec=load(ROOT/'reports/abc-championship/execution-closure-02/CATEGORY_PRODUCT_DECISIONS.json');first5=load(E/'A_ARCHIVED_FIRST5_SCOPED_LEADERS.json');firstby={x['category']:x for x in first5};c05=load(ROOT/'reports/profile-timing-closure-confirm-01/intake/HEADLINE.json');native=load(ROOT/'reports/propline-v7/METHOD_RESULTS.json');roster={x['local_alias']:x['procedure_id'] for x in load(ROOT/'reports/abc-championship/METHOD_ROSTER-v2-C-1.json')};hist=load(E/'HISTORICAL_CUMULATIVE_ROWS.json.gz');histpairs=load(ROOT/'reports/abc-championship/shared-intake-v3/A_HISTORICAL_PAIRED_CONTROLS.json');panels={x['category']:x for x in summary['primary_panels']}
# Read the stronger compatible five-week annual controls; never replace them with a new arm merely because newer.
cmp=next(x for x in panels['pass_cmp']['strongest_retained_controls'] if 'CATBOOST' in x['candidate_id']);rec=panels['rec']['strongest_retained_controls'][0]
annual_c03=c05['C03_reception_annual_all_procedures'];annual_c03_by={x['procedure']:x for x in annual_c03}
def annual_old_c03(x):
 def part(prefix):return {'wins':int(x[prefix+'_wins']) if x[prefix+'_wins'] not in ['',None] else None,'losses':int(x[prefix+'_losses']) if x[prefix+'_losses'] not in ['',None] else None,'decided':int(x[prefix+'_decided']),'rate':float(x[prefix+'_rate']) if x[prefix+'_rate'] not in ['',None] else None}
 return {'candidate_id':x['procedure'],'OVER':part('over'),'UNDER':part('under'),'COMBINED':part('combined'),'eligible':int(x['eligible']),'selected':int(x['selected']),'unavailable':int(x['unavailable']),'unknown':int(x['unknown_participation']),'games':int(x['games'])}

def archived_panel(cat):
 x=oldby.get(cat)
 if not x or not (x.get('COMBINED') or {}).get('decided'):return None
 q=qby.get(x['procedure_id'],{})
 return {'panel_id':'A_ARCHIVED_W1_W7_AS_REPORTED_PENDING_SOURCE','origin':'A','procedure_id':x['procedure_id'],'output':x.get('product'),'role_scope':q.get('role_scope',x.get('role_policy')),'actual_weeks_as_reported':x.get('actual_weeks'),'source_week_qualification':'Existing archived-source admission is preserved as reported. The named C03 annual W1-W5 correction is not automatically applied to a different source; latest owner provenance must resolve any remaining overlap. No authentic timing claim.','OVER':side(x['OVER']),'UNDER':side(x['UNDER']),'COMBINED':side(x['COMBINED']),'eligible':x['eligible'],'selected':x.get('selected'),'unknown':x.get('unknown_participation'),'games':x.get('games'),'evidence_tier':x.get('quote_timing','UNVERIFIED')+';OWNER_LOCAL_AGGREGATE','source':'reports/post-wave-5w-v1/HEADLINE_ACTUAL_LINE_REFERENCE_V1_1.json'}

def native_panel(cat):
 if cat not in ['pass_yd','rush_yd','rec','rec_yd']:return None
 rows=[]
 for method,v in native[cat].items():
  if not isinstance(v,dict) or not v.get('COMBINED',{}).get('decided'):continue
  rows.append({'procedure_id':roster.get(method,method),'method':method,'OVER':side(v['OVER']),'UNDER':side(v['UNDER']),'COMBINED':side(v['COMBINED']),'duration_weeks':[2,3],'role_scope':'Exact registered source roles; do not infer RB-only from category name.'})
 return {'panel_id':'C_NATIVE_PINNACLE_2026_W2_W3','origin':'C','records':rows,'evidence_tier':'TIMING_UNVERIFIED_LAST_RECORDED_ACTUAL_LINES','five_week_status':'NOT_MET_TWO_NATIVE_WEEKS','pairing_limit':'Constant full-source pools can have one more decided outcome than learned common pools. Use retained MATCHED_COMPARISONS, not raw unequal denominators.','source':'reports/propline-v7/METHOD_RESULTS.json','adverse':'Passing P3 26/63 lost toAlwaysOver38; rushing P3 104/177 tied earlier role reference104. Other source roles/masks remain separate.'}

def named_annual_panel(cat):
 p=panels.get(cat)
 if not p:return None
 control=p['strongest_retained_controls'];actual=p['actual_retained_line_weeks']
 return {'panel_id':'A_OWNER_LOCAL_ANNUAL_NAMED_NJ_W1_W5_EXACT_NEW_TIMING_JOIN','category':cat,'actual_weeks':actual,'games':51 if cat=='pass_cmp' else 53,'evidence_tier':p['evidence_tier'],'strongest_learned_controls':control,'new_exact_products':p['own_products'],'within_method_contrasts':p['within_method_contrasts'],'paired_source':'intake/NEW_EXACT_ANNUAL_PAIRED_ROWS.json.xz','source':'intake/A_EXECUTION_SUMMARY.json.xz','probability_limit':'C04 exports are typed points only. B exact-law probabilities have their own five-week evidence; point and probability decisions are distinct.','W6_W7':'Separate site-threshold diagnostics, not additional actual-offer weeks for this annual source.','W8':'No matching annual offers in the bound bundle; do not fill with native B/reference rows.'}

def historical_panels(cat):
 rows=[x for x in hist if x['category']==cat];out=[]
 for per in sorted({x['period_id'] for x in rows}):
  xs=[x for x in rows if x['period_id']==per and x['COMBINED']['decided']>0];m=max(x['COMBINED']['rate'] for x in xs);leaders=[x for x in xs if x['COMBINED']['rate']==m]
  out.append({'panel_id':per+'::HISTORICAL_SELECTIVE_MARKET_OR_HYBRID_TRACK','origin':'A','raw_observed_own_pool_leaders':leaders,'paired_controls_for_recorded_raw_leader':[x for x in histpairs if x['category']==cat and x['period_id']==per],'scope':'Preserve14complete policies and their selected/abstained/unavailable pools. Market/hybrid assistance and selective coverage are distinct from broad football-only direction. Windows overlap; never pool early+full twice.','source':'reports/abc-championship/shared-intake-v3/A_HISTORICAL_SCORES.json.gz'})
 return out

# Explicit dispositions are draft recommendations for the coordinator, not commands to another owner.
nexts={
'pass_yd':'A supplies or verifies latest archived source-week and exact current HGB point/adapter bindings; original-site owner admits the exact point-direction rule separately from its margin/ranker and records served use. Retain strong B/C native controls as separate panels.',
'pass_td':'Actual registered A producer restores the complete pass_td__COUNT_A_MEAN recipe/corrector, qualifies current SOURCE/query universe, executes current inference, persists issuedRoot within61440B and publishes the permitted derived feed; original-site owner admits and verifies source/value/side/fallback. Do not repeat owner-local restoration or impose unrelated EPA requirements.',
'pass_cmp':'A annual timing join is COMPLETE; do not request it again. A supplies CatBoost/HGB current-query delivery bindings or another independently eligible compatible export; website owner resolves tied direction candidates under existing policy and actual readiness. B reconciles normalized W5 membership privately before any cross-panel union.',
'pass_att':'A/B preserve completed exact joins; qualify only missing source/output cells. Candidate CountA/Cat first-five observed43/87 losesAlwaysOver46; do not promote this unchanged losing recipe. Website owner keeps an honest incumbent until an independently eligible alternative is supplied.',
'pass_int':'A supplies exact Leaf mean model/history/source/current-query adapter and permitted derived output; website owner evaluates point-direction admission at the actual line, without borrowing the tiny80%Under pool as per-pick confidence.',
'rush_yd':'A keeps48h median97/177 as an inconclusive RB-scope candidate and preserves its adverseW6-W7diagnostic; do not repeat timing fits. Qualify old mixed-role point panel before comparison with RB-only. Website owner may retain unaugmented product; no automatic Under strategy.',
'rush_att':'A supplies exact Backfield mean role scope, opportunity/fallback/current-query adapter and source bindings for owner review; keep negative dynamic-allocation recipes closed. Mixed QB/RB/WR offered-player result is not an RB-only qualification.',
'rec':'A exact C04 join is COMPLETE and now received. C binds the current-query adapter/model/feature-age/role to the exact retained P1 mean239/412 recipe before delivery; website owner may review that five-week WR/TE point candidate independently of the losing C04timing arms, with strict-crossing and TopPicks isolation.',
'rec_yd':'A supplies exact retained Response/Leaf point adapter and source-week qualification; B may supply its stronger native C02 CURRENT mean as a two-week shadow, not a five-week primary direction product. C finishes only a specified supported receiving-source or delivery dependency.',
'rush_rec_yd':'A supplies exact Response mean complete-system recipe and component-complete outcomes/current query. Do not sum marginal medians or fill a missing receiving component; website owner preserves incumbent while checking an independently eligible composite product.',
'anytime_td':'Source/product owner qualifies actual rushing-or-receivingTD event offers, offered sides, participation and settlement. Event-probability history alone cannot qualify an unavailable No/Under market.',
'nick-chart-ppr-v1':'Label/source and website owners supply exact same-chart offer plus all required primitive completeness; numerical chart history remains separate. Generic fantasy or internal references cannot supply actual-offer direction.'}
conditions={
'pass_yd':'HGB MAE point is the older archived A-panel leader, not a proven global replacement; native C passing loses a strong constant. A broader current export and exact source scope are still needed.',
'pass_td':'Corrected CountA mean ties legacy points on the retained A panel and exceeds Leafmedian by2/142 in that old view; five-week duration does not activate the currently missing feed. Use corrected mean, never legacy_point/NaNmean/barepredict.',
'pass_cmp':'CatBoost mean and HGB MAE point tie52/88 on five annual weeks, exceed every new B timing output on that same panel, and beat same-poolOver48/88. This is a real scoped candidate set, not a universal champion or proof of deployment.',
'pass_att':'The older archived CountA combined lead is below its strongest constant; the exact earlier B join and stronger saved-adjusted benchmark remain separate. No new upgrade follows from the latest losing timing/profile arms.',
'pass_int':'Leaf mean is the raw archived complete-procedure leader; its ownUnder pool is tiny. Combined and side-specific support are assessed separately; do not demand100in both sides to assess combined.',
'rush_yd':'Old mixed-role Leafmedian/blend5-partition view losesUnder167vs165; A48hRB97/177 versusstrong94 is inconclusive. Do not select the easier role/source population after outcomes.',
'rush_att':'Backfield mean remains an older scoped review candidate; first-five archived146/260 beats constants130 on its own pool, while structured role/allocation challengers did not improve strong controls. Source/role/current export must be bound.',
'rec':'Retained C P1 mean239/412 is strongest in the named five-week WR/TE control set; A Leafmean238/412 and C03R3median237/412 are close. New C04F2/F3 mean216/217 and median232/234 do not displace it. Source timing and current delivery remain distinct.',
'rec_yd':'Older A Response mean wins its archived seven-week panel; first-five Leafmean wins322/593 instead, demonstrating why windows/source qualification cannot be silently exchanged. B C02native188/337 is a separate two-week panel with only+1 over the strongest B competitor.',
'rush_rec_yd':'Older Response mean is the archived observed leader; count components, participation and role remain qualified separately. No new composite test or source-qualified cross-session global winner was created.',
'anytime_td':'NO_QUALIFIED_REPLACEMENT for actual-offer O/U in the accessible comparison. Inherited event/numerical models remain scope-visible; do not invent an opposite side.',
'nick-chart-ppr-v1':'NO_QUALIFIED_REPLACEMENT for exact chart-offer direction. Exact chart numerical candidates can be reviewed separately under their actual evidence and completeness controls.'}

result=[]
for cat,label in CATS:
 key='fpts' if cat=='nick-chart-ppr-v1' else cat;oldrow=oldby.get(key);qa0=qby.get(oldrow.get('procedure_id'),{}) if oldrow else {};arch=archived_panel(key)
 main=None;origin='A';method=None;output=None;history=qa0.get('history',oldrow.get('history') if oldrow else None);role=qa0.get('role_scope',oldrow.get('role_policy') if oldrow else None)
 if cat=='pass_cmp':
  main=cmp;method=next(x['procedure_id'] for x in archive if x['category']=='pass_cmp' and x['method']=='CATBOOST_MEDIUM');output='mean_objective_point';history=qa0.get('history');role=['QB'];duration={'status':'MET_FIVE_OWNER_LOCAL_ACTUAL_LINE_WEEKS_AT_RETAINED_TIER','actual_season_weeks':[[2026,i] for i in range(1,6)],'scientific_combined_support':'88decided<100 V6scientific-leader support; five-week floor met. This does not invent a new operational provisional veto.'}
 elif cat=='rec':
  main=rec;method=rec['candidate_id'];origin='C';output='mean';history='Exact C::PLAYER-CONTEXT-MATCHUP-01::v1.1::P1 earlier-origin recipe; preserved7day reconstructed admission; immutable model/feature/update bindings in its retained export. Not the new C04one-day recipe.';role=['WR','TE'];duration={'status':'MET_FIVE_OWNER_LOCAL_ACTUAL_LINE_WEEKS_AT_RETAINED_TIER','actual_season_weeks':[[2026,i] for i in range(1,6)],'scientific_combined_support':'412decided/53games/5weeks meets count support; superiority still requires existing paired/exposure review. OVER128 andUNDER284 each also meet count threshold, not automatic superiority.'}
 elif oldrow and (oldrow.get('COMBINED') or {}).get('decided'):
  main=oldrow;method=oldrow['procedure_id'];output=oldrow.get('product');duration={'status':'MET_AS_REPORTED_7_SCORED_ARCHIVED_WEEKS;SOURCE_SCOPE_PENDING_CURRENT_BINDING','reported_season_weeks':[[2026,i] for i in oldrow['actual_weeks']],'not_global_source_revocation':'Named C03annual correction does not invalidate every other archived/source-specificW6-W8record. First-five subpanel is separately shown, not silently substituted.'}
 else:duration={'status':'NOT_MET_NO_COMPATIBLE_ACTUAL_OFFER_DIRECTION_PRODUCT','event_or_numerical_weeks_do_not_transfer':True};origin=None
 if main:
  O,U,C=side(main['OVER']),side(main['UNDER']),side(main['COMBINED']);eligible=main.get('eligible');selected=C.get('selected') if C.get('selected') is not None else main.get('selected',eligible);unavailable=48 if cat=='rec' else main.get('unavailable',main.get('missing_offer_or_prediction'))
  unknown=9 if cat=='rec' else main.get('unknown_participation',0 if cat=='pass_cmp' else None)
  coverage={'eligible':eligible,'available':421 if cat=='rec' else 88 if cat=='pass_cmp' else selected,'selected':selected,'decided':C['decided'],'unknown':unknown,'unavailable':unavailable,'fallback':None,'abstained':main.get('abstentions',main.get('no_lean')),'games':main.get('games'),'player_games':main.get('player_games'),'scope':'Named panel only; no unknown counts converted tozero. Older primary intersection is not the entire unfiltered website board.'}
  controls=sameconstants({'OVER':O,'UNDER':U,'COMBINED':C});controls['incumbent_comparison']='NOT_ESTABLISHED_ON_THIS_EXACT_PANEL; limits superiority claims, not an indefinite veto on an existing provisional path.'
 else:O=U=C=side(None);coverage={'eligible':None,'available':None,'selected':None,'decided':0,'unknown':None,'unavailable':None,'fallback':None,'games':None,'player_games':None};controls={'incumbent_comparison':'NOT_ESTABLISHED_NO_MATCHING_OFFER_CONTRACT'}
 hp=[]
 if arch:hp.append(arch)
 if firstby.get(key,{}).get('leaders'):hp.append({'panel_id':'A_ARCHIVED_FIRST5_SUBPANEL_SOURCE_PENDING','records':firstby[key]['leaders'],'scope':'Saved-score subpanel, not new games or independent source qualification. Full seventh-week game counts not reused here.','source':'evidence/A_ARCHIVED_FIRST5_SCOPED_LEADERS.json'})
 np=named_annual_panel(cat)
 if np:hp.append(np)
 cn=native_panel(key)
 if cn:hp.append(cn)
 if cat=='pass_cmp':
  hp.append({'panel_id':'B_NATIVE_W5_W8_EXACT_LAW_P2','origin':'B','actual_weeks':[5,6,7,8],'games':56,'eligible':112,'selected':112,'decided':112,'records':[{'procedure_id':'B-QB-ALIGNED-FRESHNESS-v1:'+a+'::P2','OVER':side(x['over']),'UNDER':side(x['under']),'COMBINED':side(x['Combined'])} for a,x in c05['B_new_timing_own_records'].items()],'strong_control':'Earlier prevalence59/112; strongest84sharedW5-7strictLeafmean/savedadjusted47/84 versusF2 41/F3 42. Different masks do not add.','probability':'All nativeBriers worse than .25; proper scores separate from measured direction.','evidence_tier':'TIMING_UNVERIFIED_NATIVE_ACTUAL_LINES;VENUE_SETTLEMENT_UNVERIFIED','mean_point_decided_112_wins':{'F0':55,'F1':54,'F2':56,'F3':51},'do_not_union':'A88 and nativeB112 overlapW5; normalized private book/line/source/cutoff intersection UNKNOWN. P2/lower-median resemblance does not authorize mean/probability identity substitution.'})
 hp.extend(historical_panels(key))
 oldnum=[x for x in olddec if x['category']==key and x['product']!='ACTUAL_LINE_DIRECTION']
 oth={'numerical_projection':{'decision':'SHADOW','scope':'Independent existing numerical display paths remain reviewable; direction does not inherit numerical weeks or viceversa.','retained_scoped_products':[x for x in oldnum if x['product'] in ['NUMERICAL_MAE','EXPECTED_MEAN_MSE']]},'probability_confidence':{'decision':'ABSTAIN' if cat in ['anytime_td','nick-chart-ppr-v1'] else 'SHADOW','scope':'Only an explicitly provided law/event model has probability scores; no point-implied confidence orEV. New B annual laws have five actual weeks but allBriers exceed.25; C04pointjoin provides no probabilities and does not extend Cnative2weeklaw qualification. Failed calibrators/rankers remain closed.','retained_products':[x for x in oldnum if 'PROB' in x['product'] or 'DISTRIBUTION' in x['product']]},'Top_Picks':{'decision':'BLOCKED','owner':'Original website owner; B independent verification; C records','scope':'Complete changed selector mapping/margins/eligibility/scale/quotas/ties/fallback/refresh policy requires its own5compatibleweeks. Per-categoryTopK and componenthistory do not substitute. Missingfifthboard/timing closure is a specific owner task, not an indefinite universal gate on other products.'},'EV':{'decision':'ABSTAIN','scope':'No current qualified paired offered-side price/settlement/validated probability path admitted here.'}}
 if cat in ['anytime_td','nick-chart-ppr-v1']:decision='ABSTAIN'
 elif cat=='pass_td':decision='BLOCKED'
 elif cat in ['pass_cmp','rec','rush_att','pass_int']:decision='SHADOW'
 else:decision='KEEP_INCUMBENT'
 pref={'procedure':method,'output':output,'status':('FIVE_WEEK_SCOPED_OWNER_REVIEW_CANDIDATE' if cat in ['pass_cmp','rec'] else 'OLDER_REVIEW_CANDIDATE_AT_AS_REPORTED_SCOPE;CURRENT_BINDINGS_REQUIRED' if main else 'NO_QUALIFIED_REPLACEMENT_ACTUAL_OFFER_DIRECTION'),'rationale':conditions[cat],'operational_effect':'Draft recommendation only; does not activate a website model. Existing incumbent remains active until owner release.'}
 if cat=='pass_cmp':pref['tied_candidate_set']=[x['candidate_id'] for x in panels[cat]['strongest_retained_controls']];pref['tie_policy']='Do not invent a winner from lower MAE or integration ease; use existing owner tie/continuity rule with verifiedcurrentexport.'
 if cat=='pass_att':pref['not_recommended_as_new_primary_reason']='Raw archived direction lead loses strongest constant; no demonstrated supported replacement.'
 cur={'status':'CURRENT_QUERY_DELIVERY_NOT_ESTABLISHED_FOR_THIS_EXACT_RECOMMENDATION','producer_owner':origin,'consumer_owner':'NFL-WEB-PRODUCTION-REPORT-INTEGRATION-20261025-122500Z; lease178 last reported; refresh by actual website owner','required_action':nexts[cat],'no_family_alias_equivalence':'A model name/current family alone does not bind saved historical recipe, correction, output andlivefeaturesemantics.'}
 if cat=='pass_td':cur['registered_producer_task']=ownerqueue['tasks'][0]
 if cat=='rec':cur['C_shadow_packets']='Existing C04/C05 forecast-only captures stayimmutable andservedresearch; do not automatically equate their differentlynamedmodels withthisexactannualP1 recipe or treat them as currentactual-lineadmission.'
 l=liveby[cat]
 row={'category':cat,'label':label,'origin':origin,'exact_procedure':method,'decision_policy':('P1_UNROUNDED_POINT_VS_EXACT_ACTUAL_LINE:point>lineOVER;point<lineUNDER;point==lineABSTAIN; preserved participation/push/settlementcontract' if main else 'NO_COMPATIBLE_OFFERED_DIRECTION_PRODUCT'),'output':output,'history_policy':history,'role_scope':role,'decision':decision,'preferred_eligible_candidate':pref,'highest_observed_panels':hp,'actual_weeks_by_season':{'2026':list(range(1,6)) if cat in ['pass_cmp','rec'] else oldrow.get('actual_weeks',[]) if oldrow else []},'OVER':O,'UNDER':U,'COMBINED':C,'coverage':coverage,'controls':controls,'uncertainty':{'state':'Five exposed clusters and owner-reported paired intervals for named annual5; earlier archived max selected acrossmanymethods. No universal connected cross-session ranking.','private_scope':'Publicaggregate/member arithmetic only; no private offer clocks/rows/fitted models independentlyinspected by this draft.','source_interval_binding':'intake/NEW_EXACT_ANNUAL_PAIRED_ROWS.json.xz' if cat in ['pass_cmp','rec'] else 'Archivedsource retains original intervals; no new paired interval manufactured.'},'evidence_tier':panels[cat]['evidence_tier'] if cat in panels else 'ARCHIVED_OWNER_REPORTED_TIMING_UNVERIFIED;CURRENT_SOURCE_WEEK_BINDING_PENDING' if main else 'NO_COMPATIBLE_ACTUAL_OFFER_DIRECTION_PANEL','five_week_status':duration,'current_query':cur,'actual_live_method':l,'remaining_owner_action':nexts[cat],'other_products':oth}
 result.append(row)
# Validate only arithmetic/contracts, not scientific promotion.
for r in result:
 assert r['decision'] in ['KEEP_INCUMBENT','PROVISIONALLY_SWITCH','SHADOW','ABSTAIN','BLOCKED']
 c=r['COMBINED'];o=r['OVER'];u=r['UNDER']
 assert c['decided']==o['decided']+u['decided']
 if c['decided']:assert c['wins']==o['wins']+u['wins'] and c['losses']==o['losses']+u['losses']
assert len(result)==12 and len({r['category'] for r in result})==12
out={'schema':'C-CATEGORY-PRODUCT-DECISIONS-v1','id':'NFL-CATEGORY-DECISION-AND-RELEASE-01-C-DRAFT','generated_UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'draft_status':'TEMP_FOR_COORDINATOR_REVIEW;NOT_A_SECOND_CANONICAL_TABLE_OR_RELEASE_COMMAND','categories':result,'inventory':load(E/'RETAINED_INVENTORY_COUNTS.json'),'scope':'New exact completed joins admitted only at their actual tier; oldarchived seven-week/source and first-five subsets staydistinct. No globalwinnerfromdisconnectedpanels. Originalwebsiteowner alone releases.','new_fits':0,'new_forecast_inference':0,'new_NFL_test_games_or_weeks':0,'source_bindings':[b(x) for x in [R/'intake/A_EXECUTION_SUMMARY.json.xz',R/'intake/NEW_EXACT_PRODUCT_WEEK_MATRIX.json.xz',R/'website/LIVE_PRODUCT_BINDINGS.json',R/'website/EXACT_OWNER_QUEUE.json',E/'OUTPUT_MANIFEST.json',ROOT/'reports/post-wave-5w-v1/HEADLINE_ACTUAL_LINE_REFERENCE_V1_1.json',ROOT/'reports/abc-championship/execution-closure-02/CATEGORY_PRODUCT_DECISIONS.json']]}
out['inventory']['scope_gaps']={'enumeration_scope':'All8072existingqualificationprofiles enumerated by machine, not every private/unlocated test everexecuted. DistinctprocedureIDs are notindependentlearnerfamilies.','implemented_but_not_all_actual_line_tested':['OriginalC0/C1/C2HGB numericalstudies have no complete savedactualofferlaw roster.','ALL12v2.1 numerical/syntheticcoverage does not supply actualoffers inall12categories.'],'known_invalid_excluded':['Historical original zero-collapsed B rush_att absolute-loss HGB versions; repairedPoisson/specializedversions require exactowneridentity, notautomaticname-basedinvalidity.'],'closed_negative_recipes':['Aallocation/context andstructuredcarry losses','Bintercept/calibration/confidencegate/ranker/catchability losses','Cfeature-nonuse/no-gainprofile/defense and1daytiming directions'],'proposed_not_implemented':['Unimplemented market/hybrid mechanisms remainbacklog; nativeP4zeroevaluatedrows cannotwin.'],'private_verification_limits':['A/Brestrictedoffer/source/modelrows nottransferred; aggregateadmission is notrawrow/fitparity.','Unlocated/recovery-gatedolderexactorigins do not countastestedlosers or blockindependentreadyproducts.'],'historical_scope':'Trainingyears are nottestingyears; source2024early/full selectivepanels arequalifiedseparately andoverlap; missing2022/2023/2025actualoffers cannotbeinferredfromnumericaltests.'}
write('CATEGORY_PRODUCT_DECISIONS.json',out)
write('DRAFT_CHECK.json',{'state':'PASS_MECHANICAL_ARITHMETIC_ONLY','rows':12,'own_sides_and_combined_counts_reconcile':True,'source_integrity':'Allread-onlyboundexistingartifacts; no requests/fits/consumeredits.','final_decision_owner':'Coordinator/root; originalwebsiteowner ownsrelease.'})
print('DRAFT_READY',len(result),[(r['category'],r['COMBINED']['wins'],r['COMBINED']['decided'],r['decision']) for r in result])
