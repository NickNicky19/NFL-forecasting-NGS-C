"""C independent B review: no producer summary calls, fits or unsafe models.
Input cache members are exact pinned public GitHub files named in B_REVIEW.json.
Raw PBP/charting are C's already retained source projections (source versions differ).
"""
import collections,gzip,hashlib,json,math,pathlib,sys,datetime
import numpy as np
import pandas as pd
from scipy.special import expit
from scipy.stats import nbinom
ROOT=pathlib.Path(__file__).resolve().parents[3]
CACHE=pathlib.Path(sys.argv[1]) if len(sys.argv)>1 else pathlib.Path('/workspace/c-acceptance-b')
def read(n):return json.loads(gzip.decompress((CACHE/n).read_bytes()))
rows=read('download_0.json.gz');pred=read('download_1.json.gz');partial=read('download_2.json.gz');forest=read('more_0.json.gz');chart=read('more_1.json.gz')
by={(r['game_id'],r['player_id']):r for r in rows}
# Recompute complete down/depth attempt and completion vectors from raw plays.
raw_checks=[];raw_disagreements=[];raw_b_seen=[]
for season in [2025,2026]:
 rawpath=ROOT/'sources/player-context-matchup-01'/f'pbp_facts_{season}.csv.xz';raw=pd.read_csv(rawpath,low_memory=False)
 assert not raw.duplicated(['game_id','play_id']).any()
 plays=raw[(raw['pass_attempt']==1)&(raw['sack']!=1)&(raw['two_point_attempt']!=1)]
 ag={}
 for (gid,pid),g in plays.groupby(['game_id','passer_player_id'],dropna=False):
  a=np.zeros(25,dtype=int);c=a.copy()
  for _,p in g.iterrows():
   down=int(p['down'])-1 if p['down'] in [1,2,3,4] else 4
   air=p['air_yards'];depth=4 if pd.isna(air) else 0 if air<0 else 1 if air<10 else 2 if air<20 else 3
   j=down*5+depth;a[j]+=1;c[j]+=int(p['complete_pass']==1)
  ag[gid,pid]=(a,c,len(g))
 matched=0;correct=0
 for k,r in by.items():
  if r['season']!=season or r['game_id'] not in set(raw['game_id']):continue
  matched+=1;a,c,n=ag.get(k,(np.zeros(25,int),np.zeros(25,int),0));ok=np.array_equal(a,r['context_attempts']) and np.array_equal(c,r['context_completions']);correct+=int(ok)
  if not ok:raw_disagreements.append({'game_id':k[0],'player_id':k[1],'B_attempts':r['attempts'],'C_snapshot_attempts':int(a.sum()),'max_context_delta':int(np.max(np.abs(a-np.array(r['context_attempts']))))})
  if len(raw_b_seen)<8 and (r['week'] in [1,5] or r['official_attempts']==0):raw_b_seen.append({'game_id':k[0],'player_id':k[1],'raw_attempts':int(a.sum()),'B_attempts':r['attempts'],'unknown_depth':int(a[[4,9,14,19,24]].sum()),'known_zero_vector':bool(a.sum()==0),'vectors_match':ok})
 raw_checks.append({'season':season,'matched_QB_games':matched,'vectors_equal':correct,'C_source_SHA256':hashlib.sha256(rawpath.read_bytes()).hexdigest(),'source_vintage_note':'Comparative C snapshot; disagreement need not be producer bug'})
 # Independent FTN positive/known counts on official throw joins, not all plays.
 cpath=ROOT/'sources/player-context-matchup-01'/f'ftn_charting_{season}.csv.xz';ftn=pd.read_csv(cpath,low_memory=False)
 assert not ftn.duplicated(['nflverse_game_id','nflverse_play_id']).any()
 joined=plays.merge(ftn,left_on=['game_id','play_id'],right_on=['nflverse_game_id','nflverse_play_id'],how='left',validate='one_to_one',indicator=True)
 cb={(r['game_id'],r['player_id']):r for r in chart if r['season']==season};same=0;qb_same=0;diff=[];sample=[]
 for k,g in joined.groupby(['game_id','passer_player_id'],dropna=False):
  if k not in cb:continue
  r=cb[k];v={'eligible_throws':len(g),'matched_chart_rows':int((g['_merge']=='both').sum())};ok=v['eligible_throws']==r['eligible_throws'] and v['matched_chart_rows']==r['matched_chart_rows']
  flags={}
  for flag in ['is_catchable_ball','is_contested_ball','is_drop']:
   vals=g[flag];known=int(vals.notna().sum());positive=int(vals.fillna(False).astype(bool).sum());flags[flag]={'known':known,'positive':positive};ok=ok and flags[flag]==r['flags'][flag]
  same+=int(ok);qb_same+=int(ok and k in by)
  if not ok:diff.append({'game_id':k[0],'player_id':k[1],'C':v,'B':{'eligible_throws':r['eligible_throws'],'matched_chart_rows':r['matched_chart_rows']}})
  if len(sample)<2:sample.append({'game_id':k[0],'player_id':k[1],**v,'flags':flags,'match':ok})
 raw_checks[-1]['FTN_checks']={'thrower_games':sum(k in cb for k in joined.groupby(['game_id','passer_player_id'],dropna=False).groups),'equal':same,'qualified_QB_games':sum(k in cb and k in by for k in joined.groupby(['game_id','passer_player_id'],dropna=False).groups),'equal_qualified_QB_games':qb_same,'disagreements':diff,'samples':sample,'C_source_SHA256':hashlib.sha256(cpath.read_bytes()).hexdigest()}
# Independently rebuild context mixtures and opponent difficulty references.
hist=sorted([r for r in rows if r.get('physical_participation') and r['target_parity']],key=lambda r:(r['kickoff'],r['game_id'],r['player_id']))
def eligible(t):return [r for r in hist if r['available']<t]
def sums(rr,key):return sum((np.array(r[key],float) for r in rr),np.zeros(25))
def own(pid,t):return [r for r in eligible(t) if r['player_id']==pid][-8:]
def desc(q):
 rr=eligible(q['kickoff']);a=sums(rr,'context_attempts');c=sums(rr,'context_completions');pooled=(c+1)/(a+2);oo=own(q['player_id'],q['kickoff']);oa=sums(oo,'context_attempts');oc=sums(oo,'context_completions');mix=(oa+20*(a+1)/(a.sum()+25))/(oa.sum()+20);rates=(oc+20*pooled)/(oa+20)
 result={}
 for typ,identity,field in [('defense',q['opponent'],'opponent'),('offense',q['team'],'team')]:
  candidates=[r for r in rr if r[field]==identity];games=sorted({(r['kickoff'],r['game_id']) for r in candidates})[-16:];ids={g[1]for g in games};past=[r for r in candidates if r['game_id'] in ids];da=sums(past,'context_attempts');dc=sums(past,'context_completions');exp=np.zeros(25)
  for p in past:
   pp=eligible(p['kickoff']);pa=sums(pp,'context_attempts');pc=sums(pp,'context_completions');base=(pc+1)/(pa+2)
   if typ=='defense':
    op=own(p['player_id'],p['kickoff']);aa=sums(op,'context_attempts');cc=sums(op,'context_completions');rate=(cc+20*base)/(aa+20)
   else:rate=base
   exp+=np.array(p['context_attempts'])*rate
  result[typ]=(da,dc,exp,len(games))
 da,dc,de,ng=result['defense'];ta,tc,te,_=result['offense'];res=(dc-de)/(da+100);main=float((dc.sum()-de.sum())/(da.sum()+100));team=float((tc.sum()-te.sum())/(ta.sum()+100));return {'mix':mix,'rate':rates,'own_a':oa,'own_c':oc,'res':res,'main':main,'team':team,'da':da,'dc':dc,'de':de,'ng':ng,'own':oo,'eligible':rr}
# Origins chosen by deterministic first saved W05 QB, not observed success.
qpred=next(r for r in pred['rows'] if r['method']=='P2');q=by[qpred['game_id'],qpred['player_id']];d=desc(q);model=partial['model'];beta=np.array(model['beta']);levels=model['levels'];offset=29;maps={}
for k,v in levels.items():maps[k]={identity:offset+i for i,identity in enumerate(v)};offset+=len(v)
pps=[]
for j in range(25):
 v=np.zeros(len(beta));v[j]=1;v[25]=math.log((d['own_c'].sum()+1)/(d['own_a'].sum()-d['own_c'].sum()+1));v[26:29]=[d['main'],d['res'][j],d['team']]
 for field,mapping in maps.items():
  if q[field]in mapping:v[mapping[q[field]]]=1
 pps.append(float(expit(v@beta)))
pps=np.array(pps);integrated=float(d['mix']@pps);earlier=[r for r in d['eligible'] if r['season']>=q['season']-1];baseline=float(np.mean([r['official_attempts']for r in earlier]));mu=float((sum(r['official_attempts']for r in d['own'])+4*baseline)/(len(d['own'])+4));mean=mu*integrated
assert np.max(np.abs(d['mix']-qpred['components']['predicted_context_mix']))<1e-12
assert np.max(np.abs(pps-qpred['components']['conditional_completion_probability']))<1e-12
assert abs(mean-qpred['mean'])<1e-10
# Direct E3 feature context suffix is checked independently; base20 is reused.
e=next(r for r in pred['rows'] if r['method']=='E3'and r['game_id']==q['game_id']and r['player_id']==q['player_id']);x=e['features'];assert len(x)==179
assert np.max(np.abs(np.array(x[20:45])-d['mix']))<1e-12
assert np.max(np.abs(np.array(x[102:127])-d['res']))<1e-12
assert np.max(np.abs(np.array(x[154:179])-d['mix']*d['res']))<1e-12
# Independently interpret saved forest arrays, no author inference call.
fm=forest['model'];raw=np.array([math.nan if v is None else v for v in x]);med=np.array(fm['design']['median']);design=np.r_[np.where(np.isfinite(raw),raw,med),~np.isfinite(raw)].astype(np.float32);weights=np.zeros(len(fm['support']))
for t in fm['trees']:
 i=0
 while t['left'][i]!=-1:i=t['left'][i] if design[t['feature'][i]]<=t['threshold'][i] else t['right'][i]
 h=t['leaf_histogram']
 for node,col,w in zip(h['rows'],h['columns'],h['values']):
  if node==i:weights[col]+=w/len(fm['trees'])
assert np.max(np.abs(weights-e['law']['weights']))<1e-12
# Saved negative-binomial law coherence and exact nonrounded line boundaries.
law=qpred['law'];n=law['shape'];p=n/(n+law['mean']);support=np.arange(0,10001);mass=nbinom.pmf(support,n,p);assert abs(mass.sum()-1)<1e-10
checks=[]
for line in [0,0.5,20,20.5,21,21.5]:
 k=math.floor(line);under=nbinom.cdf(k-1,n,p) if float(line).is_integer() else nbinom.cdf(k,n,p);over=nbinom.sf(k,n,p);push=nbinom.pmf(k,n,p) if float(line).is_integer() else 0
 assert abs(under+over+push-1)<1e-12;checks.append({'line':line,'Under':under,'Push':push,'Over':over})
assert all(checks[i]['Over']>=checks[i+1]['Over'] for i in range(len(checks)-1))
# Independently partition all published complete side triads and focal counts.
sides=json.loads((CACHE/'sides.json').read_text());triads=[]
for r in sides:
 s=r['sides'];o,u,c=s['over'],s['under'],s['Combined']
 for field in ['wins','losses','decided','selected']:assert o[field]+u[field]==c[field]
 for z in s.values():
  assert z['decided']==z['wins']+z['losses'];assert z['hit_rate'] is None if z['decided']==0 else abs(z['hit_rate']-z['wins']/z['decided'])<1e-12
 if r['week_view']=='ALL'and r['output_rule']in ['P2_STATISTICAL_LAW','REGISTERED_DIRECTION']and r['procedure_id']in ['B-player-context-matchup-01-v1:E0','B-player-context-matchup-01-v1:E3','B-player-context-matchup-01-v1:COMMON_EXPOSURE','SAVED_ADJUSTED','EARLIER_LINE_PREVALENCE']:
  triads.append({'target':r['category'],'procedure':r['procedure_id'],'policy':r['output_rule'],'sides':s,'eligible':r['eligible'],'games':r['games'],'numerical_n':r['numerical_n']})
selected=json.loads((CACHE/'selected.json').read_text());best=min(selected['validation'],key=lambda r:(r['NLL'],[4,8,16].index(r['window']),[20,80].index(r['strength'])));assert(best['window'],best['strength'])==(selected['window'],selected['strength'])==(8,20)
result={'created_UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'reviewer':'C internal independent calculation; not B/A acknowledgement','no_author_summary_or_inference_function_called':True,'new_fits':0,'public_GETs':16,'raw_context_checks':raw_checks,'raw_context_disagreements':raw_disagreements,'raw_deterministic_sample':raw_b_seen,'representative_inference':{'game_id':q['game_id'],'player_id':q['player_id'],'model':'2026-W05-P2','mean':mean,'saved_mean':qpred['mean'],'attempt_mean':mu,'integrated_completion_probability':integrated,'latest_admitted_own_game':d['own'][-1]['game_id'],'latest_admitted_available':max(r['available']for r in d['eligible']),'fit_cutoff':pred['fit_cutoff'],'query_cutoff':q['kickoff'],'fit_latest_training_label':partial['latest_training_label'],'fit_latest_training_feature':partial['latest_training_feature'],'conditional_probability_max_delta':float(np.max(np.abs(pps-qpred['components']['conditional_completion_probability'])))},'opponent_equation':{'conditional_residual':'r_j=(sum completed_j - sum[attempts_j*(own_completed_j+20*earlier_pooled_j)/(own_attempts_j+20)])/(sum attempts_j+100), using last16 eligible opponent team-games','interaction':'z_j=predicted_own_mix_j*r_j (25 distinct coordinates); does not algebraically collapse to one scalar','example_context':int(np.argmax(d['da'])),'defense_attempts':d['da'].tolist(),'defense_completed':d['dc'].tolist(),'offense_quality_expected_completed':d['de'].tolist(),'residual':d['res'].tolist(),'mix':d['mix'].tolist(),'interactions':(d['mix']*d['res']).tolist(),'context_residual_range':[float(d['res'].min()),float(d['res'].max())],'interpretation':'QB-passing completion response by down/depth; not causal defense talent, all-player dropbacks or receiver alignment'},'safe_forest_leaf_weights_max_delta':float(np.max(np.abs(weights-e['law']['weights']))),'law_checks':checks,'aggregate_side_triads_checked':len(sides),'focal_records':triads,'earlier_window_selection':{'season':2024,'weeks':[1,2,3,4,5,6,7,8],'objective':'full-game forecast completion count NLL','validation_rows':302,'window':8,'strength':20,'selection_recomputed_from_saved_scores':True,'fresh_tuning_fits_reproduced':False},'actual_offer_row_regrade':'UNKNOWN; offers are owner-local and row_calculations_sha256 commitments do not disclose exact private thresholds or selected members','offered_numerical_population':'Owner reports E3mean MAE5.3547/bias-1.4779 on112 vs5.8362/bias-0.9234 on277; cannot independently recompute private112 membership','source_vintage':'C and B current/revised snapshots; plus7day strictly earlier availability is reconstructed, not original publication authentication','bounds':'No NFL fits, unsafe deserialization, external messages, B writes, raw private offer export or source-policy changes'}
# Inspect the actual source-bound v2 repair, not the old order-sensitive restore.
import ast,copy
from scipy import special
code=ast.parse((CACHE/'core.py').read_text());wanted=[n for n in code.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))and n.name in ['_conditional_x','CompletionModel']]
env={'np':np,'special':special,'CONTEXTS':25,'math':math};exec(compile(ast.Module(body=wanted,type_ignores=[]),'<reviewed B pure coefficient interpreter>','exec'),env)
adapter=ast.parse((CACHE/'adapter_v2.py').read_text());adapter.body=[n for n in adapter.body if not isinstance(n,ast.ImportFrom)];env.update(VERSION='B-player-context-matchup-01-v1');exec(compile(adapter,'<reviewed B v2 portable adapter>','exec'),env)
restored=env['restore_completion'](model,producer_version=env['VERSION']);sorted_restored=env['restore_completion'](json.loads(json.dumps(model,sort_keys=True)),producer_version=env['VERSION'])
class HistoryFixture:
 def describe(self,query):return dict(own_attempts=float(d['own_a'].sum()),own_completions=float(d['own_c'].sum()),opponent_residual_main=d['main'],opponent_residual=d['res'],team_residual=d['team'])
pp=restored.probabilities(q,HistoryFixture());ss=sorted_restored.probabilities(q,HistoryFixture());assert np.max(np.abs(pp-pps))<1e-12 and np.array_equal(pp,ss)
rejected=[]
for malformed,version in [(dict(model,levels={}),env['VERSION']),(model,'OTHER_PRODUCER')]:
 try:env['restore_completion'](malformed,producer_version=version)
 except ValueError:rejected.append(True)
assert len(rejected)==2
result['public_GETs']=17;result['active_adapter_repair']={'path':'nfl_v2/player_context_typed_adapter_v2.py','producer_commit':'3ad682cf86912f025e5a1699c8a396f3d9065222','SHA256':hashlib.sha256((CACHE/'adapter_v2.py').read_bytes()).hexdigest(),'source_bound_v2_read':True,'coefficient_order':['team','opponent','player_id'],'original_and_sorted_JSON_probabilities_exact':True,'independent_manual_probability_max_delta':float(np.max(np.abs(pp-pps))),'bad_level_groups_and_producer_rejected':2,'old_NFL_predictions_changed':False,'fit_reproduction':False}
result['fit_verification_scope']='Saved JSON inference only. No B fresh-fit reproduction was run by C in this package. B existing independent restoration receipt was inspected for byte/scope claims, not treated as new fit reproduction.'
path=ROOT/'reports/player-context-matchup-01/acceptance-v1/B_CALCULATION_CHECKS.json';path.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps({'raw':[(r['season'],r['matched_QB_games'],r['vectors_equal'],r['FTN_checks']['equal'])for r in raw_checks],'raw_disagreements':len(raw_disagreements),'mean_delta':mean-qpred['mean'],'triads':len(sides),'wrote':str(path)}))
