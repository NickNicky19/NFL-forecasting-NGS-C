"""One-off qualified FTN charting intake, distinct from participation data.

Retained factual charting projection is CC BY-SA4 with explicit attribution.
No alignment, all-route or player-motion attribution is inferred.
"""
import csv,gzip,hashlib,io,json
from pathlib import Path
from urllib.request import Request,urlopen
from context_sources_c01 import OUT,REPORT,now,sha,write,guard

def run():
 assert not (REPORT/'FTN_INVENTORY.json').exists(),'COMPLETED_INTAKE_FROZEN'
 docs=json.loads((REPORT/'SOURCE_DOCUMENTATION.json').read_text());license_evidence=docs['ftn_load']
 assert any('CC-BY-SA 4.0' in x for x in license_evidence['excerpts'])
 ledger=REPORT/'SOURCE_REQUESTS.json';req=json.loads(ledger.read_text());inventory=[]
 for year in [2025,2026]:
  a=next(a for a in docs['ftn_release']['actual_assets'] if a['name']==f'ftn_charting_{year}.csv');assert len(req)<28
  item=dict(url=a['browser_download_url'],started_UTC=now());req.append(item);write(ledger,req)
  with urlopen(Request(a['browser_download_url'],headers={'User-Agent':'Session-C-manual-context-study-v1'}),timeout=35) as f:
   b=f.read(9000001);assert len(b)<=9000000;item.update(status=f.status,observed_UTC=now(),bytes=len(b),SHA256=sha(b),asset_id=a['id'],asset_updated_UTC=a['updated_at'])
  assert item['SHA256']==a['digest'].split(':')[1],'CHARTING_ASSET_CHANGED';assert sum(v.get('bytes',0) for v in req)<=33554432,'SOURCE_BYTES_CAP';write(ledger,req)
  reader=csv.DictReader(io.StringIO(b.decode()));columns=reader.fieldnames;rows=list(reader)
  # Preserve the public29-column annotation contract and explicit missing values.
  keep=[c for c in columns if c not in ['note','notes','description']]
  out=io.StringIO();w=csv.DictWriter(out,fieldnames=keep,lineterminator='\n');w.writeheader();w.writerows({k:r[k] for k in keep} for r in rows);body=gzip.compress(out.getvalue().encode(),mtime=0)
  p=OUT/f'ftn_charting_{year}.csv.gz';assert not p.exists();guard();p.write_bytes(body);guard()
  wk={}
  for r in rows:
   v=wk.setdefault(r['week'],dict(rows=0,games=set()));v['rows']+=1;v['games'].add(r['nflverse_game_id'])
  inventory.append(dict(year=year,source=item,projection_path=str(p.relative_to(OUT.parents[1])),projection_SHA256=sha(body),projection_bytes=len(body),columns=keep,rows=len(rows),weeks={k:dict(v,games=sorted(v['games'])) for k,v in wk.items()},missing={k:sum(r[k] in ['', 'NA'] for r in rows) for k in keep},alignment_route_denominators='NOT_PRESENT',motion='PLAY_LEVEL_FLAG;not moving receiver identity'))
 write(REPORT/'FTN_INVENTORY.json',dict(id='C-FTN-CHARTING-SOURCE-v1',created_UTC=now(),license='CC BY-SA4.0',attribution='FTN Data via nflverse; FTNData.com',rights=dict(analysis='Qualified under published CC BY-SA4 grant',GitHub_retention='Qualified attributed projection under same CC BY-SA4;not a grant for participation/otherFTNproducts',derived_publication='Attribution and applicable share-alike conditions retained; no implied endorsement'),license_source=license_evidence['source'],availability='Documented charting within48h, actual current downloads/revisions pinned; historical timing remains reconstructed not authenticated',sources=inventory,owner_use='B owns QB/catchability fits;C sourceexport only;not duplicate B experiment'))
 (OUT/'FTN_ATTRIBUTION.md').write_text('FTN charting data: FTN Data (FTNData.com) via nflverse, https://github.com/nflverse/nflverse-data/releases/tag/ftn_charting. This charting projection is licensed CC BY-SA 4.0: https://creativecommons.org/licenses/by-sa/4.0/. C converts the publisher CSV to deterministic gzip and retains its factual columns and missingness. No FTN endorsement is implied. It is distinct from FTN participation and does not establish receiver alignment or untargeted routes. Historical source publication is not authenticated by this download.\n')
 print(json.dumps([dict(year=x['year'],rows=x['rows'],weeks=sorted(x['weeks']),columns=x['columns'],bytes=x['projection_bytes']) for x in inventory]))
if __name__=='__main__':run()
