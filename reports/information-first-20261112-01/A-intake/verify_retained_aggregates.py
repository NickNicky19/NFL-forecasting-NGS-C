"""Read-only common-intake arithmetic checks, not a forecast or NFL-row grader."""
import pathlib,json,gzip,hashlib
BASE=pathlib.Path(__file__).resolve().parent
m=json.loads((BASE/'SOURCE_PROJECTION_BINDINGS.json').read_text());triads=0;empty=0

def verify(s):
 global triads,empty
 triads+=1
 for side in ['OVER','UNDER','COMBINED']:
  r=s[side]
  if r['decided']:
   assert r['wins']+r['losses']==r['decided'];assert abs(r['rate']-r['wins']/r['decided'])<1e-12
  else:assert r['wins']is None and r['losses']is None and r['rate']is None;empty+=1
 for k in ['wins','losses','decided','selected']:assert(s['COMBINED'][k]or 0)==(s['OVER'][k]or 0)+(s['UNDER'][k]or 0)

for binding in m['bindings']:
 p=BASE/pathlib.Path(binding['projection_path']).name;assert hashlib.sha256(p.read_bytes()).hexdigest()==binding['projection_SHA256'];d=json.loads(gzip.decompress(p.read_bytes()))
 if 'records'in d:
  for r in d['records']:
   verify(r['summary'])
   for x in r.get('weekly',[]):verify(x['summary'])
   if r.get('weekly'):
    for s in ['OVER','UNDER','COMBINED']:
     for k in ['wins','losses','decided','selected']:assert sum((x['summary'][s][k]or 0)for x in r['weekly'])==(r['summary'][s][k]or 0)
  for x in d['paired_controls']:assert x['win_difference']==x['candidate_wins']-x['control_wins']
 else:
  for r in d['summaries']+d['common_available_summaries']:verify(r)
  for x in d['paired']:assert abs(x['accuracy_change']-(x['left_wins']-x['right_wins'])/x['common_decided'])<1e-12
assert triads==528 and empty==407
rows=json.loads(gzip.decompress((BASE/'NORMALIZED_HISTORICAL_CONTROL_ROWS.json.gz').read_bytes()));assert len(rows)==528;assert sum(x['execution_state']=='NO_SCORED_OUTCOME_NOT_TEST'for x in rows)==81
assert all(x['no_new_2026_or_original_issued_record']is True for x in rows)
print('PASS_RETAINED_AGGREGATE_ARITHMETIC',triads,'TRIADS',empty,'EMPTY_SIDE_NA',81,'NO_SCORED_ROWS_NOT_TESTS')
