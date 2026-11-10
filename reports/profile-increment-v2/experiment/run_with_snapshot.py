"""Execution wrapper: retain a data profile from the already-needed preparation.

This does not alter the fitting matrices, labels, cohorts or model code. The
snapshot is reconstructed as-of data, never a new forecast or live issuance.
"""
import argparse,hashlib,sys,zipfile,json
import numpy as np
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'src'))
import receiving_increment_c03 as model
original=model.prepare
YEAR=2026

def prepare_with_snapshot():
 result=original();defense=result[5];cut=model.now()
 if YEAR==2025:
  pool,g,_,_,_,_,mats,_,_=result;saved=model.baseline_points(2025);proof=[]
  with zipfile.ZipFile(ROOT/'artifacts/robustness-rec-v3.zip') as archive:
   for wk in range(1,9):
    meta=json.loads(archive.read(f'raw/rec/W{wk:02}/DONE.json'));origin=float(g.loc[(g.season==2025)&(g.week==wk),'kickoff'].min());train=[r for r in pool if r['available']<origin and r['values']['rec'] is not None]
    membership=hashlib.sha256('\n'.join(r['game_id']+':'+r['player_id'] for r in train).encode()).hexdigest()
    assert len(train)==meta['training_rows'] and membership==meta['training_membership_sha256'],'SAVED_R0_TRAIN_MEMBERSHIP_DIFFERS'
    assert max(r['available'] for r in train)==meta['latest_training_available'],'SAVED_R0_TRAIN_CLOCK_DIFFERS'
    assert model.pd.Timestamp(meta['origin_UTC']).timestamp()==origin,'SAVED_R0_ORIGIN_DIFFERS'
    ix=[i for i,r in enumerate(pool) if r['season']==2025 and r['week']==wk];checked=0
    for i in ix:
     r=pool[i];old=saved.get((r['game_id'],r['player_id']))
     if old is None:continue
     assert np.array_equal(np.asarray([np.nan if v is None else v for v in old['features']]),mats['R0'][i],equal_nan=True),'SAVED_R0_QUERY_FEATURE_DIFFERS';checked+=1
    proof.append(dict(week=wk,training_rows=len(train),membership_SHA256=membership,latest_training_available=meta['latest_training_available'],origin_UTC=meta['origin_UTC'],query_features_checked=checked,new_R0_fits=0))
  model.write(model.OUT/'SAVED_2025_R0_COMPATIBILITY.json',dict(status='PASS',all8_origins_checked=True,slots=proof,new_fits=0,unsafe_loads=0))
 rows=defense.snapshot(cut)
 dest=model.OUT/f'DEFENSE_SNAPSHOT-{cut[:10]}.json.xz'
 if not dest.exists():
  model.write(dest,{'id':'C-RECEIVING-DEFENSE-ASOF-DATA-v1','actual_creation_UTC':cut,'profiles':rows,'profile_count':len(rows),'forecast_or_selection_capture':False,'source_scope':'Frozen qualified2024-2026current-vintage reconstruction; strictkickoff+7day; not freshroster/authenticatedhistoricalvintage','wrapper_SHA256':model.sha(Path(__file__))})
  model.write(model.OUT/'DEFENSE_SNAPSHOT_INDEX.json',{'path':str(dest.relative_to(ROOT)),'SHA256':model.sha(dest),'profile_count':len(rows),'teams':[{'team':r['team'],'state':r['state'],'eligible_games':r['eligible_games'],'latest_source_game':r['latest_source_game']} for r in rows],'actual_creation_UTC':cut,'new_predictions':0})
 return result

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--year',type=int,choices=[2025,2026],default=2026);a=parser.parse_args()
 YEAR=a.year
 model.prepare=prepare_with_snapshot
 model.run(a.year,False)
