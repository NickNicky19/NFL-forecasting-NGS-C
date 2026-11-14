"""Select existing public aggregate views; no forecasts, raw grades, or union scoring."""
import collections,datetime,gzip,hashlib,json,math,pathlib,time
start=time.process_time();out=pathlib.Path(__file__).resolve().parent
src=pathlib.Path('/tmp/w1w9-B-common-controls.json');raw=src.read_bytes();data=json.loads(raw);h=hashlib.sha256(raw).hexdigest();assert h=='945a3b979f8c0539d88c249bc1123e1235ceb27ebfc9337f03c794346faab0e9'
allowed={'method','policy','window','sides','probability','games','K','rank_scope','weekly_selected','weeks_evaluated','weeks_with_selections'}
assert all(set(r)<=allowed for r in data)
controls={'SAVED_ADJUSTED','SAVED_RAW','EARLIER_LINE_PREVALENCE','ALWAYS_OVER','ALWAYS_UNDER'}
arms={'B-FTN-BALL-QUALITY-COMPLETION-v1:B0','B-FTN-BALL-QUALITY-COMPLETION-v1:B2'};policies={'P1_MEAN','P1_LOWER_MEDIAN','P2_STATISTICAL_LAW'};windows={'ALL',5,6,7,8,9}
selected=[r for r in data if r['window'] in windows and (r['method'] in controls and r['policy']=='REGISTERED_DIRECTION' or r['method'] in arms and r['policy'] in policies)]
assert len(selected)==66,len(selected);assert len({(r['method'],r['policy'],r['window']) for r in selected})==66
rows=[];check=[]
for r in selected:
 sides={s['side']:s['metrics'] for s in r['sides']};assert set(sides)=={'over','under','Combined'}
 for side,m in sides.items():
  assert m['WIN']+m['LOSS']==m['denominators']['decided'];n=m['denominators']['decided'];rate=None if not n else m['WIN']/n
  assert m['hit_rate'] is None if rate is None else math.isclose(m['hit_rate'],rate,abs_tol=1e-14)
 for k in ['WIN','LOSS','PUSH']:assert sides['Combined'][k]==sides['over'][k]+sides['under'][k]
 cm=sides['Combined'];row={'owner':'B','category':'pass_cmp','procedure_id':r['method'],'product':r['policy'],'season':2026,'week':r['window'],'actual_offer_weeks':[5,6,7,8,9] if r['window']=='ALL' else [r['window']],'eligible':cm['selection_pool_count'],'selected':cm['denominators']['outer_rows'],'available':None,'unknown':cm['denominators']['unresolved'],'technical_unavailable':cm['technical_unavailable'],'abstained':cm['admitted_rule_abstentions'],'fallback':cm['fallback_issued'],'learned_issued_source_label':cm['learned_issued'],'games':r['games'],'source_decoded_sha256':h,'source_semantics':'Precomputedpublicaggregateonly; no protectedrow access; no new scores or combinedsourceunion','evidence_tier':'CURRENT_VINTAGE_FTN_SEVEN_DAY_RECONSTRUCTION_TIMING_UNVERIFIED_ACTUAL_LINE_DIAGNOSTIC','horizon_strata':'W5-8nativeper-gamerolling-source;W9separatefixedpre-firstT90file;individualquote/providerclocksunverified','source_raw_probability_summary':r['probability'],'probability_type':'NONE_FOR_SAVED_POINT_CONSTANT_CONTROLS' if r['method'] in {'SAVED_ADJUSTED','SAVED_RAW','ALWAYS_OVER','ALWAYS_UNDER'} else 'REPORTED_EXISTING_COUNT_LAW_OR_EARLIER_PREVALENCE;NOT_DERIVED_FROM_POINT_GAP','own_sides':{}}
 for s,name in [('over','over'),('under','under'),('Combined','combined')]:
  m=sides[s];row['own_sides'][name]={'wins':m['WIN'],'losses':m['LOSS'],'decided':m['denominators']['decided'],'rate':m['hit_rate'],'selected':m['denominators']['outer_rows'],'unknown':m['denominators']['unresolved'],'push':m['PUSH'],'void':m['status_counts']['VOID']}
  for k,value in row['own_sides'][name].items():row[name+'_'+k]=value
 if r['method'] in {'SAVED_ADJUSTED','SAVED_RAW','ALWAYS_OVER','ALWAYS_UNDER'}:assert r['probability']['n']==0 and r['probability']['brier'] is None and r['probability']['log_loss'] is None
 rows.append(row)
for method,policy in sorted({(r['method'],r['policy']) for r in selected}):
 rr=[r for r in rows if r['procedure_id']==method and r['product']==policy];allr=next(r for r in rr if r['week']=='ALL');weeks=[r for r in rr if isinstance(r['week'],int)];assert sorted(r['week'] for r in weeks)==[5,6,7,8,9]
 for side in ['over','under','combined']:
  for k in ['wins','losses','decided','selected','unknown','push','void']:assert allr[side+'_'+k]==sum(r[side+'_'+k] for r in weeks),(method,policy,side,k)
 check.append({'method':method,'policy':policy,'weekly_to_cumulative':'PASS'})
(out/'B_NATIVE_W5_W9_STRONG_CONTROLS_AND_RETAINED_PRODUCTS.json').write_text(json.dumps({'id':'C-B-NATIVE-142-STRONG-CONTROLS-EXACT-OWNSIDES-v1','source_decoded_sha256':h,'rows':rows,'interpretation':['Each procedure chooses its own sides on same nominal native142board; no paired-disagreements inferred from aggregateaccuracy.','Differentoutputs/policiesandweekly/cumulativeviewscannotbeaddedintooneNFLdenominator.','Available/unverified fields remainnull; savedproviderlearned/fallbackattributionunknown(notzero).','Constantcontrols historicalcomparisononly; notautomaticlivepolicies.','Pointcontrols have no invented probability or EV; countlawdiagnostics retainseparateidentity.']},indent=2)+'\n')
wire=gzip.compress(raw,mtime=0);(out/'COMMON_CONTROL_TABLE_SOURCE.json.gz').write_bytes(wire)
entry=json.load(open(out.parent/'B-intake/STRONG_CONTROL_ARTIFACT_BINDING.json'))['source'];assert entry['sha256']==h and entry['bytes']==len(raw)
bind={'source_repository':'NickNicky19/NFL-forecasting-V2','source':entry,'source_decoded_bytes':len(raw),'source_decoded_sha256':h,'local_wire':'COMMON_CONTROL_TABLE_SOURCE.json.gz','wire_bytes':len(wire),'wire_sha256':hashlib.sha256(wire).hexdigest(),'encoding':'lossless gzip original JSON bytes','upstream_retrieval_executor':'C root; oneboundedapprovedimmutableGitHubread','this_subtask_network_reads':0,'rights':'Publishedprecomputedaggregateonly. FTN-dependentderivedcomparisonresults retainCC-BY-SA-4.0;FTNData via nflverse. UnrelatedB0/provider/constantcontrolsretainseparatesourcecontracts; no blanketrelicensingofprotectedoffers.','new_derivation':'C selectedexisting66aggregateviews andindependentlyrecomputedcount/rate/weekly identities; no new forecasts/outcomes/union.'}
(out/'SOURCE_BINDING.json').write_text(json.dumps(bind,indent=2)+'\n')
receipt={'id':'C-B-NATIVE-142-CONTROL-ARITHMETIC-v1','created_UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_rows':len(data),'selected_complete_procedure_views':len(rows),'selected_side_views':len(rows)*3,'method_policy_families':len(check),'checks':check,'aggregate_count_rate_side_weekly_identities':'PASS','source_top_schema_aggregate_only':True,'source_private_rows_retrieved':False,'network_reads':0,'new_fits':0,'new_grades':0,'new_union_scores':0,'new_NFL_games_or_weeks':0,'CPU_seconds':time.process_time()-start,'CPU_cap_seconds':30,'retention_cap_bytes':1048576,'exact_same142_member_mask_verification':'Notestablishedfromaggregateobject;sameboardidentity/sourcecontractisupstreamownerbound. No private-memberparity claim.'}
(out/'INDEPENDENT_ARITHMETIC_RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n')
print('views',len(rows),'gzip',len(wire),'retained',sum(q.stat().st_size for q in out.iterdir() if q.is_file()))
for r in rows:
 if r['week']=='ALL':print(r['procedure_id'],r['product'],r['over_wins'],r['over_losses'],r['under_wins'],r['under_losses'],r['combined_wins'],r['combined_losses'])
