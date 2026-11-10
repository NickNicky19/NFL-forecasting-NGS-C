"""Safe saved-point extraction only; never deserialize the legacy fitted model."""
import json,gzip,zipfile,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent

def main():
 rows=[];slots=[];games={};p=ROOT/'artifacts/all12-rec-v2.1.zip'
 with zipfile.ZipFile(p) as z:
  names=sorted(n for n in z.namelist() if n.endswith('/rows.json.gz') and 'E0_OP' in n and 'H-MULTI' in n and 'P2_LEAF' in n)
  assert len(names)==7
  for name in names:
   b=z.read(name);rr=json.loads(gzip.decompress(b));done=json.loads(z.read(name.replace('rows.json.gz','DONE.json')));assert hashlib.sha256(b).hexdigest()==done['row_sha256']
   slots.append(dict(slot=done['slot'],origin_UTC=done['origin_UTC'],training_rows=done['training_rows'],latest_training_available=done['latest_training_available'],row_sha256=hashlib.sha256(b).hexdigest(),model_sha256=done['model_sha256'],training_membership_sha256=done['training_membership_sha256']))
   for r in rr:
    assert r['target']=='rec' and r['history']=='H-MULTI' and r['arm']=='E0_OP'
    games[r['game_id']]=dict(week=r['week'],kickoff_UTC=r['kickoff_UTC'],as_of_UTC=r['as_of_UTC']);rows.append({k:r[k] for k in ['game_id','player_id','position','team','opponent','week','mean','median','fallback']})
 assert len(rows)==2152 and len({(r['game_id'],r['player_id']) for r in rows})==2152
 d=dict(schema='C-RETAINED-LEAF-POINTS-v1',category='rec',source_archive='artifacts/all12-rec-v2.1.zip',source_archive_SHA256=hashlib.sha256(p.read_bytes()).hexdigest(),source_pin='dbf3170ee1fdce091b7f4de09c780ca2df65ad7e',procedures={'mean':'C-ALL12-LAW-THRESHOLD-v2.1::rec::H-MULTI::P2_LEAF::E0_OP::MEAN_POINT_DIRECTION','median':'C-ALL12-LAW-THRESHOLD-v2.1::rec::H-MULTI::P2_LEAF::E0_OP::MEDIAN_POINT_DIRECTION'},roles=['RB','WR','TE'],games=games,slots=slots,rows=rows,policy='Unrounded point>lineOver,<lineUnder, equalityabstain; no probabilityinferredfrompoint',information_tier='CURRENT_REVISED_7DAY_RECONSTRUCTION',actuals_and_offers_excluded=True,new_fits=0,new_inference=0,unsafe_models_loaded=False)
 body=gzip.compress(json.dumps(d,separators=(',',':')).encode(),mtime=0);dest=OUT/'C_RETAINED_LEAF_POINTS_W1_W7.json.gz'
 if dest.exists():assert dest.read_bytes()==body
 else:dest.write_bytes(body)
 print(len(rows),len(body),hashlib.sha256(body).hexdigest())
if __name__=='__main__':main()
