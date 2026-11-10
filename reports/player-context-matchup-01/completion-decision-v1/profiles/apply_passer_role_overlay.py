"""Append-only qualification of passer roles in the first profile projection.

Only profile metadata/targeting labels change. Old profile bytes remain frozen;
forecasts, ordinary/context feature arrays and model scores are unchanged.
"""
import gzip,hashlib,io,json,sys,zipfile
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT/'src'))
from receiving_profiles_c02 import ProfileBuilder,Capped,instant
from data_v2 import History,DAY

def corrected_profiles(profiles,overlay):
 assert len({r['profile_id'] for r in profiles})==len(profiles)
 import copy
 out=copy.deepcopy(profiles)
 for r in out:
  correction=overlay['profiles'].get(r['profile_id'])
  if correction:r['receiving']['QB_pair_targeting']=correction
 return out

def main():
 out=Path(__file__).resolve().parent/'current-W10';base=out/'PROFILES.json.gz';original=json.loads(gzip.decompress(base.read_bytes()));snapshot=ROOT/'sources/player-context-matchup-01/completion-decision-v1/current-query'
 with zipfile.ZipFile(ROOT/'artifacts/basic-football-facts-v2.1.zip') as z:
  old=pd.read_csv(io.BytesIO(z.read('facts.csv.gz')),compression='gzip',low_memory=False);schedule=pd.read_csv(io.BytesIO(z.read('schedule.csv')))
 new=pd.read_csv(snapshot/'current_facts_2026.csv.gz',low_memory=False);raw=pd.concat([old[old.season<2026],new],ignore_index=True)
 sg=pd.read_csv(snapshot/'schedule.csv');schedule=pd.concat([schedule[schedule.season<2026],sg[sg.season==2026]],ignore_index=True);schedule['kickoff']=pd.to_datetime(schedule.gameday+' '+schedule.gametime).dt.tz_localize('America/New_York').dt.tz_convert('UTC').astype('int64')/1e9
 raw=raw.merge(schedule[['game_id','kickoff']],on='game_id',validate='many_to_one');raw['available']=raw.kickoff+7*DAY;raw=raw[raw.player_id.notna()];history=History(raw,'player_id')
 frames=[pd.read_csv(ROOT/p,low_memory=False) for p in ['sources/player-context-matchup-01/completion-decision-v1/pbp_facts_2024.csv.xz','sources/player-context-matchup-01/pbp_facts_2025.csv.xz','sources/player-context-matchup-01/completion-decision-v1/current-query/pbp_context_2026.csv.xz']]
 builder=ProfileBuilder.__new__(ProfileBuilder);builder.pbp=pd.concat(frames,ignore_index=True);builder.hist=Capped(history,instant(original[0]['key']['information_cutoff_UTC']))
 corrections={};other=unknown=0
 for p in original:
  if p['key']['position']=='QB':continue
  q=dict(p['key'],kickoff=instant(p['kickoff_UTC']));pairs=builder._qb_pairs(q,p['history']['games']);before=p['receiving']['QB_pair_targeting']
  oldcounts={r['QB_player_id']:(r['targets'],r['QB_attempts_in_same_eligible_player_appearances']) for r in before['pairs']};newcounts={}
  for r in pairs['pairs']:
   pair=newcounts.setdefault(r['passer_player_id'],[0,0]);pair[0]+=r['targets'];pair[1]+=r['passer_attempts_in_same_eligible_player_appearances']
   other+=r['role_qualification']=='NON_QB_PASSER';unknown+=r['role_qualification']=='UNKNOWN_PASSER_ROLE'
  assert oldcounts=={k:tuple(v) for k,v in newcounts.items()}
  corrections[p['profile_id']]=pairs
 d={'id':'C-PROFILE-PASSER-ROLE-CORRECTION-v1','base_SHA256':hashlib.sha256(base.read_bytes()).hexdigest(),'reason':'A passer is not automatically a QB; label by historical game role, preserve nonQB/unknown buckets. Original53profilebytesfrozen.','profiles':corrections,'nonQB_pair_views':other,'unknown_role_pair_views':unknown,'feature_probability_grade_changes':0}
 path=out/'PASSER_ROLE_OVERLAY.json.gz';assert not path.exists();path.write_bytes(gzip.compress(json.dumps(d,separators=(',',':')).encode(),mtime=0))
 receipt={'id':d['id'],'original_profile_SHA256':d['base_SHA256'],'overlay_SHA256':hashlib.sha256(path.read_bytes()).hexdigest(),'overlay_bytes':path.stat().st_size,'rows':len(original),'receiving_profiles':len(corrections),'nonQB_pair_views':other,'unknown_role_pair_views':unknown,'original_generator':'../generator-v1.py.gz','source_counts_preserved':True,'scientific_prediction_or_score_changes':0,'canonical_view':'corrected_profiles(original,overlay)'}
 (out/'PROFILE_METADATA_CORRECTION.json').write_text(json.dumps(receipt,indent=2)+'\n');print(receipt)
if __name__=='__main__':main()
