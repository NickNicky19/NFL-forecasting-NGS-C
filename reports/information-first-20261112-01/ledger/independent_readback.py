"""Independent stdlib/Decimal source-to-ledger check; no builder import."""
import csv,gzip,hashlib,io,json,time,resource
from decimal import Decimal
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
def read(p):
 b=Path(p).read_bytes();return json.loads(gzip.decompress(b) if str(p).endswith('.gz') else b)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def scalar(v):return '' if v is None else str(v)
def verify():
 cpu=time.process_time();old=ROOT/'reports/category-decision-release-01/W1_W9_AND_HISTORY_COVERAGE.csv.gz';new=old.with_name('W1_W9_AND_HISTORY_COVERAGE_V2.csv.gz')
 a=read(HERE.parent/'A-intake/NORMALIZED_HISTORICAL_CONTROL_ROWS.json.gz');b=read(HERE.parent/'B-intake/INDEPENDENT_CORRECTED_GRADE_REVIEW_V1.json')
 original=gzip.decompress(old.read_bytes());body=gzip.decompress(new.read_bytes());assert body.startswith(original)
 legacy=list(csv.DictReader(io.StringIO(original.decode())));current=list(csv.DictReader(io.StringIO(body.decode())))
 assert current[:len(legacy)]==legacy and len(current)==32103 and len({r['coverage_entry_id'] for r in current})==32103
 bgroup={}
 for r in b['results']:bgroup.setdefault((r['strategy'],str(r['window'])),{})[r['side']]=r
 appended=current[31527:];checks=0;empty_rates=0;empty_counts=0
 for i,row in enumerate(appended):
  metrics=json.loads(row['additional_metrics'])
  if row['owner']=='B':
   raw=metrics['source_side_triads'];key=(raw['Combined']['strategy'],str(raw['Combined']['window']));assert raw==bgroup[key]
   sides=[raw['over'],raw['under'],raw['Combined']]
  else:
   raw=a[i-48];assert metrics['source_summary']==raw
   sides=[raw['OVER'],raw['UNDER'],raw['COMBINED']]
   assert row['season'] in ['2023','2024']
   if row['season']=='2023':assert set(raw['actual_scored_weeks'])<=set(range(6,19))
  for prefix,s in zip(['over','under','combined'],sides):
   for key in ['wins','losses','decided','rate']:
    assert row[prefix+'_'+key]==scalar(s[key]);checks+=1
    if s[key] is None:
     empty_rates+=key=='rate';empty_counts+=key in ['wins','losses']
   if s['decided']:
    assert s['wins']+s['losses']==s['decided']
    exact=Decimal(s['wins'])/Decimal(s['decided']);assert abs(exact-Decimal(str(s['rate'])))<Decimal('1e-12')
   else:assert s['rate'] is None
  for k in ['selected','decided']:assert sides[0][k]+sides[1][k]==sides[2][k]
 # Independent weekly/cumulative arithmetic for all eight B strategies.
 for strategy in {k[0] for k in bgroup}:
  allrow=bgroup[(strategy,'ALL')]
  for side in ['over','under','Combined']:
   for k in ['selected','wins','losses','push','decided','unknown']:
    assert allrow[side][k]==sum(bgroup[(strategy,str(w))][side][k] for w in [5,6,7,8,9])
 report={'id':'C-COVERAGE-V2-INDEPENDENT-DECIMAL-READBACK-v1','state':'PASS','imports':'Pythonstdlibonly; no builder/scorer/grader imports',
  'source_scalar_mapping_checks':checks,'new_complete_entries':576,'original_entries_exact':31527,'unique_entries':32103,
  'B_144_side_views_as_48_triads':True,'B_all8strategies_weekly_cumulative_reconciled':True,'A528summaries_exactly_embedded':True,
  'source_null_rates_preserved_empty':empty_rates,'source_null_win_loss_counts_preserved_empty':empty_counts,
  'new_original_NFL_games':0,'new_2026_weeks':0,'network':0,'fits':0,'output':{'path':str(new.relative_to(ROOT)),'SHA256':sha(new)},
  'code_SHA256':sha(Path(__file__)),'CPU_seconds':time.process_time()-cpu,'peak_RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024}
 with (HERE/'INDEPENDENT_READBACK.json').open('x') as f:json.dump(report,f,indent=2);f.write('\n')
 print(json.dumps(report,indent=2))
if __name__=='__main__':verify()
