"""Independent aggregate reconciliation; no private-row/scorer invocation."""
import collections,csv,gzip,json,hashlib
from pathlib import Path
R=Path(__file__).resolve().parent
read=lambda n:json.loads(gzip.decompress((R/n).read_bytes()))
d=read('A_C_POINTS_ON_REC_BOARD_V1.json.gz');assert hashlib.sha256(gzip.decompress((R/'A_C_POINTS_ON_REC_BOARD_V1.json.gz').read_bytes())).hexdigest()=='b19f895cce4cc636bae0b760d3381d06812aa7d935d2775bbf5a21742783ccd9'
checks=0
for r in d['scores']:
 for side in ['OVER','UNDER','COMBINED']:
  s=r[side];w=s['wins'] or 0;l=s['losses'] or 0;assert w+l==s['decided'];assert (s['rate'] is None if not w+l else abs(s['rate']-w/(w+l))<1e-14);checks+=1
 for key in ['wins','losses','decided','selected']:assert (r['OVER'][key] or 0)+(r['UNDER'][key] or 0)==(r['COMBINED'][key] or 0)
 assert r['eligible']==r['COMBINED']['selected']+r['unavailable']+r['abstentions']
 assert r['COMBINED']['selected']==r['COMBINED']['decided']+r['states'].get('UNKNOWN_PARTICIPATION',0)
 # Outcome-side controls derived from the method's own decisions.
 over=(r['OVER']['wins'] or 0)+(r['UNDER']['losses'] or 0);under=(r['OVER']['losses'] or 0)+(r['UNDER']['wins'] or 0)
 assert over==(r['constants']['OVER']['COMBINED']['wins'] or 0) and under==(r['constants']['UNDER']['COMBINED']['wins'] or 0)
full=[r for r in d['scores'] if r['source_panel']=='ALL' and r['week_view']=='ALL']
assert len(full)==4
for r in full:
 assert (r['eligible'],r['COMBINED']['selected'],r['COMBINED']['decided'],r['unavailable'],r['states']['UNKNOWN_PARTICIPATION'])==(733,678,667,55,11)
 weeks=[x for x in d['scores'] if x['source_panel']=='ALL' and x['week_view']!='ALL' and x['procedure_id']==r['procedure_id'] and x['product']==r['product']]
 assert sorted(x['week_view'] for x in weeks)==list(range(1,8))
 for side in ['OVER','UNDER','COMBINED']:
  for k in ['wins','losses','decided','selected']:assert sum(x[side][k] or 0 for x in weeks)==(r[side][k] or 0)
for p in d['paired']:
 assert p['common_decided']==667 and p['left_wins']-p['right_wins']==p['win_change'] and p['common_mask_sha256']=='b84a7cfca0df5449af90b7b747df536081f34ef5656d62920dc920c02873d3d4'
assert [r['COMBINED']['wins'] for r in full]==[382,389,379,385]
result={'status':'PASS_PUBLIC_AGGREGATE_ARITHMETIC','summary_cells':len(d['scores']),'side_cells':checks,'paired_cells':len(d['paired']),'rows_independently_regraded_by_C':0,'private_row_parity':'NOT_VERIFIED_BY_C','owner_independent_receipt':'A_INDEPENDENT_C_POINT_REPLAY_V1.json.gz','seven_week_point_duration':True,'probability_or_TopK_duration_inherited':False,'strongest_learned_model_comparison':'NOT_EXECUTED_IN_RECEIVED_EXPORT','new_fits':0}
(R/'ARITHMETIC_REVIEW.json').write_text(json.dumps(result,indent=2)+'\n')
fields=['procedure_id','product','OVER','UNDER','COMBINED','eligible','selected','decided','unavailable','selected_unknown','games','weeks','tier']
with (R/'A_C_POINT_HEADLINE.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=fields,lineterminator="\n");w.writeheader()
 for r in full:
  rec={s:f"{r[s]['wins']}-{r[s]['losses']}/{r[s]['decided']}/{100*r[s]['rate']:.6f}%" for s in ['OVER','UNDER','COMBINED']};rec.update(procedure_id=r['procedure_id'],product=r['product'],eligible=733,selected=678,decided=667,unavailable=55,selected_unknown=11,games=81,weeks='1,2,3,4,5,6,7',tier=r['evidence_tier']);w.writerow(rec)
print(result)
