"""Exact own-output restoration slots; no source collection or retry."""
from __future__ import annotations
import argparse,base64,hashlib,json,subprocess,time
from pathlib import Path
import shared_game_sim01_repair as r
REPO='NickNicky19/NFL-forecasting-NGS-C'
def restore(path,commit,slot,*,canary=False):
 r.deadline_guard();path=Path(path)
 if path.is_absolute():path=path.relative_to(r.ROOT)
 # Slots are the twelve exact approved additional operations.
 allowed=['freeze_A',*[f'raw_shard_{i:02d}' for i in range(1,9)],'freeze_B','readable_report','machine_result']
 if slot not in allowed:raise ValueError('UNREGISTERED_OUTPUT_SLOT')
 ledger=r.initialize();used=ledger.setdefault('repair_output_slots',{})
 if slot in used:raise RuntimeError('OUTPUT_SLOT_ALREADY_ATTEMPTED_NO_RETRY')
 if ledger['output_readbacks']>=20:raise RuntimeError('OUTPUT_READBACK_CAP')
 local=r.ROOT/path;body=local.read_bytes();h=hashlib.sha256(body).hexdigest()
 oid=subprocess.check_output(['git','rev-parse',commit+':'+str(path)],cwd=r.ROOT,text=True).strip()
 w=time.monotonic()
 # Reserve before the single HTTP request; a failed attempt consumes its slot.
 ledger['output_readbacks']+=1
 used[slot]=dict(state='RESERVED_BEFORE_HTTP',path=str(path),commit=commit,blob=oid,bytes=len(body),SHA256=h,UTC=r.now().isoformat())
 r.save(r.LEDGER,ledger);result=None
 try:
  response=subprocess.run(['gh','api',f'repos/{REPO}/git/blobs/{oid}'],cwd=r.ROOT,capture_output=True,timeout=120,check=True)
  payload=json.loads(response.stdout)
  if payload['encoding']!='base64' or payload['sha']!=oid:raise ValueError('RESTORED_BLOB_ENCODING_OR_ID')
  actual=base64.b64decode(payload['content'],validate=False)
  if actual!=body or hashlib.sha256(actual).hexdigest()!=h:raise ValueError('RESTORED_OUTPUT_BODY_MISMATCH')
  work=r.PRIVATE/'repair-readback';work.mkdir(parents=True,exist_ok=True)
  target=work/(slot+'.body');target.write_bytes(actual)
  if target.read_bytes()!=body:raise ValueError('INDEPENDENT_REOPEN_DIFFER')
  if slot.startswith('raw_shard_'):
   import zipfile,io
   from shared_game_sim01_retention import reopen_replay_bundle
   with zipfile.ZipFile(io.BytesIO(actual)) as z:
    manifest=json.loads(z.read('manifest.json'))
    for record in manifest['games']:
     raw=z.read(record['member'])
     if hashlib.sha256(raw).hexdigest()!=record['SHA256']:raise ValueError('RAW_SHARD_GAME_HASH')
     p=work/(record['native_game_id']+'.zip');p.write_bytes(raw)
     kept=reopen_replay_bundle(p,record['SHA256'])
     if kept.metadata['game_id']!=record['native_game_id']:raise ValueError('REMOTE_GAME_IDENTITY_DIFFER')
   result=dict(state='REMOTE_SHARD_AND_SP_DP_STATE_REOPEN_PASS',games=len(manifest['games']))
  else:result=dict(state='ACTUAL_REMOTE_BODY_REOPEN_PASS')
  x=r.initialize();x['repair_output_slots'][slot].update(result,completed_UTC=r.now().isoformat());r.save(r.LEDGER,x)
  r.save(r.D/('READBACK_'+slot+'.json'),dict(**x['repair_output_slots'][slot],scope='Actual own immutable body restoration, not private source/fit or website served parity'))
 except BaseException as e:
  x=r.initialize();x['repair_output_slots'][slot].update(state='FAILED_NO_RETRY',reason=str(e));r.save(r.LEDGER,x)
  if not (r.D/'PACKAGE_STOP.json').exists():
   r.save(r.D/'PACKAGE_STOP.json',dict(state='OUTPUT_RESTORATION_FAILED_NO_RETRY',slot=slot,reason=str(e),completed_game_sets=len(r.index())))
  raise
 finally:
  # The mandatory outer controller meters this Python worker and its waited
  # gh child once; do not double-charge their time here.
  pass
 return result
def shard(paths,destination):
 import zipfile
 destination=Path(destination)
 if destination.exists():raise FileExistsError('IMMUTABLE_SHARD_EXISTS')
 destination.parent.mkdir(parents=True,exist_ok=True);records=[]
 with zipfile.ZipFile(destination,'x',compression=zipfile.ZIP_STORED) as z:
  for p in paths:
   p=Path(p);body=p.read_bytes();member=p.name
   info=zipfile.ZipInfo(member,date_time=(1980,1,1,0,0,0));z.writestr(info,body)
   records.append(dict(native_game_id=p.stem,member=member,bytes=len(body),SHA256=hashlib.sha256(body).hexdigest()))
  info=zipfile.ZipInfo('manifest.json',date_time=(1980,1,1,0,0,0));z.writestr(info,json.dumps(dict(format='C-SIM01-NUMERIC-SHARD-v1',games=records),sort_keys=True).encode())
 if destination.stat().st_size>67108864:raise ValueError('SHARD_64MIB_LIMIT')
 return dict(path=str(destination),bytes=destination.stat().st_size,SHA256=hashlib.sha256(destination.read_bytes()).hexdigest(),games=records)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('path');p.add_argument('commit');p.add_argument('slot');p.add_argument('--canary',action='store_true');p.add_argument('--worker',action='store_true');v=p.parse_args()
 if v.worker:print(json.dumps(restore(v.path,v.commit,v.slot,canary=v.canary)))
 else:
  import sys
  cmd=[sys.executable,str(Path(__file__).resolve()),v.path,v.commit,v.slot,'--worker']+(['--canary'] if v.canary else [])
  print(json.dumps(r.controlled('Exact output restoration '+v.slot,cmd,12,canary=v.canary,completion=not v.canary)))
