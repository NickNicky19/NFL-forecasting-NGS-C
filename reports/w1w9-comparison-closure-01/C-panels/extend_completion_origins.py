"""Two exact retained C completion origins; no offer grading or unsafe loading.

Core feature and fit implementations are imported unchanged. Only missing W8/W9
origins are selected. Existing earlier source rows and outputs stay immutable.
"""
import argparse,fcntl,gzip,hashlib,io,json,os,resource,sys,time,zipfile
from datetime import datetime,timezone
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT/'src'))
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
from data_v2 import load,History,vector
from laws_v2 import LeafModel
from safe_models_v4 import export_forest,infer_forest,save,load as safe_load,validate_training_model

OUT=HERE/'cmp-origin-extension';ARCHIVE=ROOT/'artifacts/basic-football-facts-v2.1.zip'
CURRENT=ROOT/'sources/category-decision-release-01'
MODEL_ARCHIVE=ROOT/'artifacts/all12-pass_cmp-v2.1.zip'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def stamp():return datetime.now(timezone.utc).isoformat()
def write(p,d):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(d,f,indent=2,allow_nan=False);f.write('\n')
def finite(a):return [float(v) if np.isfinite(v) else None for v in a]
def digest(a):return hashlib.sha256(json.dumps(a,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def prepare():
 with zipfile.ZipFile(ARCHIVE) as z:
  old=pd.read_csv(io.BytesIO(z.read('facts.csv.gz')),compression='gzip',low_memory=False)
  oldg=pd.read_csv(io.BytesIO(z.read('schedule.csv')))
 current=pd.read_csv(CURRENT/'current_facts_2026.csv.gz',low_memory=False)
 currentg=pd.read_csv(CURRENT/'schedule.csv')
 assert list(old.columns)==list(current.columns)
 extra=current[(current.season==2026)&current.week.isin([8,9])&(current.season_type=='REG')].copy()
 extrag=currentg[(currentg.season==2026)&currentg.week.isin([8,9])&(currentg.game_type=='REG')].copy()
 assert not extra.game_id.isin(old.game_id).any() and not extrag.game_id.isin(oldg.game_id).any()
 assert not extra[['game_id','player_id']].duplicated().any()
 assert extra.game_id.isin(extrag.game_id).all()
 assert extrag[['home_score','away_score']].notna().all().all()
 raw=pd.concat([old,extra],ignore_index=True)
 schedule=pd.concat([oldg,extrag[list(oldg.columns)]],ignore_index=True)
 class Memory:
  def __truediv__(self,name):
   if name=='facts.csv.gz':return io.StringIO(raw.to_csv(index=False))
   if name=='schedule.csv':return io.StringIO(schedule.to_csv(index=False))
   raise ValueError(name)
 d,g,teams=load(Memory());pool=d[d.position=='QB'].to_dict('records')
 hist=History(d[d.season>=2022],'player_id');th=History(teams[teams.season>=2022],'team')
 x=np.asarray([vector(r,'pass_cmp',hist,th,'E0_ENV') for r in pool],float)
 assert x.shape[1]==35
 earlier=[]
 with zipfile.ZipFile(MODEL_ARCHIVE) as z:
  for week in range(1,8):
   slot=f'C-ALL12-LAW-THRESHOLD-v2.1-pass_cmp-H-MULTI-P2_LEAF-E0_ENV-W{week:02d}'
   done=json.loads(z.read(slot+'/DONE.json'));oldrows=json.loads(gzip.decompress(z.read(slot+'/rows.json.gz')))
   origin=float(g.loc[(g.season==2026)&(g.week==week),'kickoff'].min())
   ti=[i for i,r in enumerate(pool) if r['season']>=2022 and r['available']<origin and r['values']['pass_cmp'] is not None]
   membership=hashlib.sha256('\n'.join(pool[i]['game_id']+':'+pool[i]['player_id'] for i in ti).encode()).hexdigest()
   assert membership==done['training_membership_sha256'] and len(ti)==done['training_rows']
   bykey={(r['game_id'],r['player_id']):i for i,r in enumerate(pool) if r['season']==2026 and r['week']==week}
   assert len(bykey)==len(oldrows)
   for r in oldrows:assert finite(x[bykey[r['game_id'],r['player_id']]])==r['features']
   earlier.append({'week':week,'training_membership_equal':True,'query_features_equal':True,'queries':len(oldrows)})
 return d,g,teams,pool,x,earlier,raw,schedule
def mutation_check(d,teams,pool,x,week,origin):
 # Change target and later outcomes/exposures while preserving identity/queries.
 changed=d.copy(deep=True);changed['values']=changed['values'].map(dict)
 mask=(changed.season==2026)&(changed.week>=week)
 for i in changed.index[mask]:
  changed.at[i,'values']['pass_cmp']=99999
 for c in ['attempts','carries','targets']:
  changed.loc[mask,c]=99999
 ct=teams.copy(deep=True);tm=(ct.season==2026)&(ct.week>=week)
 for c in ['attempts','carries','sacks_suffered']:
  ct.loc[tm,c]=99999
 h=History(changed[changed.season>=2022],'player_id');th=History(ct[ct.season>=2022],'team')
 qi=[i for i,r in enumerate(pool) if r['season']==2026 and r['week']==week]
 for i in qi:assert finite(vector(pool[i],'pass_cmp',h,th,'E0_ENV'))==finite(x[i])
 assert not any(r['season']==2026 and r['week']>=week for r in pool if r['available']<origin)
 return {'target_and_later_mutation_changes_earlier_features':False,'eligible_training_target_or_future_rows':0,'queries_checked':len(qi)}
def run(fit):
 start=time.process_time();wall=time.monotonic();OUT.mkdir(exist_ok=True)
 reg=json.loads((OUT/'REGISTRATION.json').read_text())
 assert sha(__file__)==reg['extension_adapter_SHA256']
 for name,h in reg['core_code_SHA256'].items():assert sha(ROOT/'src'/name)==h
 assert sha(ARCHIVE)==reg['old_source_archive_SHA256']
 for p,h in reg['current_source_SHA256'].items():assert sha(ROOT/p)==h
 lock=open('/tmp/C_NFL_RESEARCH_FIT_WORKER.lock','a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 d,g,teams,pool,x,earlier,raw,schedule=prepare()
 preflight={'id':'C-CMP-W08-W09-PREFLIGHT-v1','source_append_only':True,'original7_origins':earlier,'original242_query_features_equal':sum(r['queries'] for r in earlier)==242,'feature_count':x.shape[1],'new_QB_query_counts':{str(w):sum(r['season']==2026 and r['week']==w for r in pool) for w in [8,9]},'core_procedure_unchanged':True,'source_vintage':'Retained original prefix plus already-observed Nov12 W8/W9 ordinary facts; all historical availability is strict kickoff+7day reconstruction, not authenticated publication.'}
 if not fit:
  write(OUT/'PREFLIGHT.json',preflight);print(json.dumps(preflight));return
 assert json.loads((OUT/'PREFLIGHT.json').read_text())==preflight
 fits=0;all_points=[];receipts=[]
 for week in [8,9]:
  dest=OUT/f'W{week:02d}';dest.mkdir(exist_ok=False)
  origin=float(g.loc[(g.season==2026)&(g.week==week),'kickoff'].min())
  ti=[i for i,r in enumerate(pool) if r['season']>=2022 and r['available']<origin and r['values']['pass_cmp'] is not None]
  qi=[i for i,r in enumerate(pool) if r['season']==2026 and r['week']==week]
  train=[pool[i] for i in ti];query=[pool[i] for i in qi]
  tx=x[ti];qx=x[qi];y=np.asarray([r['values']['pass_cmp'] for r in train],float);roles=np.asarray([r['position'] for r in train]);qr=np.asarray([r['position'] for r in query])
  assert len(train)>=60 and np.isfinite(y).all() and (y>=0).all() and np.equal(y,np.rint(y)).all()
  invariant=mutation_check(d,teams,pool,x,week,origin)
  start_receipt={'week':week,'FIT_START_UTC':stamp(),'origin_UTC':pd.Timestamp(origin,unit='s',tz='UTC').isoformat(),'training_rows':len(ti),'query_rows':len(qi),'training_membership_SHA256':hashlib.sha256('\n'.join(r['game_id']+':'+r['player_id'] for r in train).encode()).hexdigest(),'training_matrix_SHA256':hashlib.sha256(tx.tobytes()+y.tobytes()).hexdigest(),'latest_training_available_epoch':max(r['available'] for r in train),'first_target_kickoff_epoch':origin,'parameters':reg['parameters'],'history':'H-MULTI;2022expanding;strict kickoff+7day < origin and querycutoff','query_universe':'Original statistical-row-conditioned QB reconstruction; not authenticated pregame roles','future_invariance':invariant,'active_lease':reg['lease'],'core_code_SHA256':reg['core_code_SHA256']}
  assert start_receipt['latest_training_available_epoch']<origin
  write(dest/'FIT_START.json',start_receipt)
  with threadpool_limits(limits=1):model=LeafModel('count',1).fit(tx,y,roles)
  fits+=1;assert fits<=2
  numeric=export_forest(model);model_hash=save(dest/'MODEL.json.gz',numeric);numeric=safe_load(dest/'MODEL.json.gz',model_hash)
  recovery=validate_training_model(numeric,tx,y,roles)
  with threadpool_limits(limits=1):reference=model.laws(qx,qr);restored=infer_forest(numeric,qx,qr)
  shuffled=list(reversed(range(len(qi))));back=infer_forest(numeric,qx[shuffled],qr[shuffled]);single=[infer_forest(numeric,qx[[j]],qr[[j]])[0] for j in range(len(qi))]
  points=[]
  for j,(r,ref,law) in enumerate(zip(query,reference,restored)):
   for other in [ref,single[j],back[len(qi)-1-j]]:
    assert abs(law.mean()-other.mean())<1e-12 and law.quantile(.5)==other.quantile(.5)
   assert np.isfinite(law.mean()) and law.mean()>=0
   slot=f'C-ALL12-LAW-THRESHOLD-v2.1-pass_cmp-H-MULTI-P2_LEAF-E0_ENV-W{week:02d}'
   points.append({'version':'C-ALL12-LAW-THRESHOLD-v2.1','slot':slot,'game_id':r['game_id'],'player_id':r['player_id'],'name':r['player_display_name'],'position':r['position'],'team':r['team'],'opponent':r['opponent_team'],'season':2026,'week':week,'kickoff_UTC':pd.Timestamp(r['kickoff'],unit='s',tz='UTC').isoformat(),'as_of_UTC':pd.Timestamp(r['kickoff'],unit='s',tz='UTC').isoformat(),'generated_UTC':stamp(),'scoring_contract_id':'official-player-fullgame-OT-v1','fallback':False,'mean':law.mean(),'median':law.quantile(.5),'category':'pass_cmp','model_SHA256':model_hash,'fit_origin_UTC':start_receipt['origin_UTC'],'feature_vector_SHA256':digest(finite(qx[j])),'typed_outputs':{'mean':'EXPECTED_MEAN_FROM_DISCRETE_LAW','median':'LOWER_DISCRETE_MEDIAN'},'information_tier':'CURRENT_REVISED_7DAY_RECONSTRUCTION','feature_count':x.shape[1]})
  with (dest/'POINTS.json.gz').open('xb') as f:f.write(gzip.compress(json.dumps(points,separators=(',',':'),allow_nan=False).encode(),mtime=0))
  receipt=start_receipt|{'FIT_COMPLETE_UTC':stamp(),'model_format':'C-NUMERIC-LEAF-v4;safeJSONonly','model_SHA256':model_hash,'points_SHA256':sha(dest/'POINTS.json.gz'),'restored_training_validation':recovery,'max_single_batch_shuffle_mean_difference_tolerance':1e-12,'point_rows':len(points),'new_fits':1,'new_actual_offer_grades':0,'CMP_ATT_primary_selection_hold':'RETAINED;not coherentjointcompletionattemptlaw'}
  write(dest/'DONE.json',receipt);receipts.append(receipt);all_points.extend(points)
  assert time.process_time()-start<=180 and resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024<=1073741824
  assert sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file())<=8388608
  print('C_CMP_ORIGIN_COMPLETE',week,len(ti),len(points),flush=True)
 write(OUT/'EXECUTED.json',{'id':'C-CMP-EXACT-ORIGIN-EXTENSION-W08-W09-v1','completed_UTC':stamp(),'new_fits':fits,'new_inference_queries':len(all_points),'weeks':[8,9],'new_actual_offer_scores':0,'new_original_issued_picks':0,'source_before_target_qualification':'Current-vintage chronological reconstruction only, not authenticated source publication','CPU_seconds':time.process_time()-start,'wall_seconds':time.monotonic()-wall,'RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,'original242_point_handoff_changed':False,'safe_restoration_verified':True,'receipts':receipts})
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--fit',action='store_true');run(parser.parse_args().fit)
