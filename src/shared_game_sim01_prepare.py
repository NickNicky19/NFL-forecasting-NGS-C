"""Isolated deterministic private case preparation; never a forecast worker."""
from __future__ import annotations
import argparse,hashlib,importlib.util,json,sys,zipfile
from pathlib import Path
from shared_game_sim01_budget import ROOT,D,save
from shared_game_sim01_inputs import canonical_team

ZIP_SHA='afcd4cfc52685657f969a80651831b075f9351ef298dda0a0553791f7444b365'
SP_SHA='b24d08193d95bdea509bd20ece6ebf66fd29da49d144c213369e493eace11bf1'
PRIVATE=ROOT/'private/shared-game-sim-01'
def module(name,p):
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
def sha(b):return hashlib.sha256(b).hexdigest()
def prepare(attachment):
 body=Path(attachment).read_bytes();assert len(body)==915706 and sha(body)==ZIP_SHA
 package=PRIVATE/'package';assert not package.exists(),'Existing package: reopen checkpoint rather than overwrite'
 package.mkdir(parents=True,mode=0o700)
 with zipfile.ZipFile(attachment) as z:
  assert sum(i.file_size for i in z.infolist())==9088315
  for i in z.infolist():
   p=Path(i.filename);assert not p.is_absolute() and '..' not in p.parts and not i.is_dir()
   out=package/p;out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(z.read(i))
 builder=module('website_case_builder',D/'intake/website-public/build_case_contract_v1.py')
 mf=builder.prepare(package,PRIVATE/'views');assert sha((PRIVATE/'views/forecast_worker/manifest.json').read_bytes())==SP_SHA
 expected=json.loads((D/'intake/website-public/CASE_MANIFEST.json').read_text())
 assert mf==expected,'DETERMINISTIC_CASE_MANIFEST_PARITY'
 docs=builder.load_forecast_inputs(PRIVATE/'views/forecast_worker',SP_SHA)
 identity=module('sim_identity_bridge',ROOT/'reports/shared-game-sim-01/readiness/inspect_identity_adapter.py')
 rows,pools,queries,paths,qb=identity.build_adapter(Path(attachment))
 old=json.loads((ROOT/'reports/shared-game-sim-01/readiness/IDENTITY_ORIGIN_READINESS.json').read_text())
 assert identity.digest(rows)==old['adapter_full_metadata_fingerprint'],'STRICT_V2_1428_CONTEXT_PARITY'
 # One exact canonical bridge per case; the forecast worker never receives the
 # ZIP, comparator/case rows, names, lines, outcomes or archive records.
 save(PRIVATE/'identity_rows.json',rows)
 bypg={}
 for r in rows:
  k=(r['week'],r['source_game_id'],r['source_player_id']);bypg.setdefault(k,[]).append(r)
 mapped=[];conflicts=0
 for p in docs['players_sp.jsonl']:
  q=dict(p);rr=bypg[(q['week'],q['game_id'],q['player_id'])];ready=[r for r in rr if r['status'].startswith('READY_')]
  values={(r['canonical_player_id'],r['team'],r['canonical_game_id'],r['canonical_kickoff_UTC'],r['assumed_model_cutoff_UTC']) for r in ready}
  if len(values)==1:
   gs,team,ng,kick,cut=next(iter(values));q.update(gsis_id=gs,native_game_id=ng,native_kickoff_utc=kick,model_cutoff_utc=cut,identity_available=True)
   if canonical_team(team)!=canonical_team(q['team']):
    q['identity_available']=False;q['identity_reason']='SOURCE_VS_PRIOR_TEAM_CONFLICT';conflicts+=1
   elif team!=q['team']:q['identity_reason']='QUALIFIED_EXACT_FRANCHISE_NAMESPACE_ALIAS_LAR_LA'
  else:q.update(identity_available=False,identity_reason='STRICT_V2_BRIDGE_UNAVAILABLE')
  mapped.append(q)
 save(PRIVATE/'mapped_players.json',mapped)
 outputs=[PRIVATE/'views'/f for f in mf['files']]
 outputs +=[PRIVATE/'identity_rows.json',PRIVATE/'mapped_players.json']
 # Every body independently reopened before readiness is claimed; no grade.
 bound=[]
 for p in outputs:
  b=p.read_bytes();assert sha(p.read_bytes())==sha(b);bound.append(dict(relative_private_role=str(p.relative_to(PRIVATE)),bytes=len(b),SHA256=sha(b)))
 save(D/'INPUT_REBUILD_RECEIPT.json',dict(source_ZIP_SHA256=ZIP_SHA,closed_SP_manifest_SHA256=SP_SHA,website_manifest='EXACT_PARITY',private_views_reopened=bound,cases=mf['case_count'],unknowns=mf['unknown_outcome_count'],player_games=len(mapped),supported_player_games=sum(x['identity_available'] for x in mapped),source_prior_team_conflicts=conflicts,raw_inputs_published=False,original_outcomes_changed=False,scope='Private deterministic rebuild and identity-only enrichment, no fitting/predictions/grading',source_clocks='Original issuance/quote unknown; nativeT90 reconstructed clock and archived schedule retained separately'))
 print('PRIVATE_INPUTS_REBUILT_AND_REOPENED',len(mapped),sum(x['identity_available'] for x in mapped))
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('attachment');v=a.parse_args();prepare(v.attachment)
