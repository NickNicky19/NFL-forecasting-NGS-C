"""Independent public aggregate arithmetic; no scorer, model, private rows."""
from pathlib import Path
from decimal import Decimal
import csv,io,json,lzma,re,hashlib
OUT=Path(__file__).resolve().parent

def read(n):return json.loads(lzma.decompress((OUT/(n+'.json.xz')).read_bytes()))['document']
def check(scores):
 sides=0
 for r in scores:
  for s in ['OVER','UNDER','COMBINED']:
   x=r[s];w=x['wins'] or 0;l=x['losses'] or 0;n=x['decided'];assert w+l==n
   assert (x['rate'] is None if not n else abs(Decimal(str(x['rate']))-Decimal(w)/Decimal(n))<Decimal('1e-14'))
   assert x['selected']>=n;sides+=1
  for k in ['wins','losses','decided','selected']:assert (r['OVER'][k] or 0)+(r['UNDER'][k] or 0)==(r['COMBINED'][k] or 0)
  assert r['eligible']==r['COMBINED']['selected']+r['unavailable']+r['abstentions']
  states=r['states'];assert sum(states.values())==r['eligible']
  assert states.get('WIN',0)==(r['COMBINED']['wins'] or 0) and states.get('LOSS',0)==(r['COMBINED']['losses'] or 0)
 # Each independent source/view/procedure's ALL cumulative equals its weekly sum.
 groups={ (r['view'],r['source_panel'],r['candidate_id']) for r in scores }
 for g in groups:
  rr=[r for r in scores if (r['view'],r['source_panel'],r['candidate_id'])==g];allr=next(r for r in rr if r['week_view']=='ALL');weeks=[r for r in rr if r['week_view']!='ALL']
  for s in ['OVER','UNDER','COMBINED']:
   for k in ['wins','losses','decided','selected']:assert (allr[s][k] or 0)==sum(r[s][k] or 0 for r in weeks)
  for k in ['eligible','unavailable','abstentions']:assert allr[k]==sum(r[k] for r in weeks)
 return sides,len(groups)

reception=read('A_RECEPTION_STRONG');rec_checks=check(reception['summaries']);attempts=read('A_B_ATT_EARLIER');att_checks=check(attempts['scores'])
for d,pairkey in [(reception,'paired'),(attempts,'paired_controls')]:
 for r in d[pairkey]:
  assert r['left_wins']-r['right_wins']==r['win_change']
  assert 0<=r['left_wins']<=r['common_decided'] and 0<=r['right_wins']<=r['common_decided']
# Every C Leaf CSV count is independently reconciled; full/fixed selected masks differ.
leaf=list(csv.DictReader(io.StringIO(read('A_C_LEAF_TABLES'))))
for r in leaf:
 vals={k:int(r[k]) if r[k] else 0 for k in ['eligible','selected','unavailable','over_w','over_l','over_n','under_w','under_l','under_n','total_w','total_l','total_n','unknown']}
 assert vals['over_w']+vals['over_l']==vals['over_n'] and vals['under_w']+vals['under_l']==vals['under_n']
 assert vals['over_w']+vals['under_w']==vals['total_w'];assert vals['over_l']+vals['under_l']==vals['total_l'];assert vals['over_n']+vals['under_n']==vals['total_n'];assert vals['total_w']+vals['total_l']==vals['total_n']
 assert vals['selected']==vals['total_n']+vals['unknown'];assert vals['eligible']==vals['selected']+vals['unavailable']
# Verify an otherwise stale expected CSV hash differs solely by line encoding.
text=read('A_C_LEAF_TABLES');assert hashlib.sha256(text.replace('\n','\r\n').encode()).hexdigest()=='0ac525fb94cb625d8c8db2c3a901ed752d77e178dbd9efce7bc138e66a372598'
# Recompute B's four published own-side rows independently from report text.
B=[]
for line in read('B_PROFILE_REPORT').splitlines():
 if not re.match(r'^\| R[0-3] \|',line):continue
 cols=[c.strip() for c in line.strip('|').split('|')];counts=[]
 for value in cols[1:4]:
  m=re.match(r'(\d+)–(\d+)/(\d+) \(([\d.]+)%\)',value);assert m,value
  w,l,n=map(int,m.group(1,2,3));assert w+l==n;assert abs(100*w/n-float(m.group(4)))<.0051;counts.append({'wins':w,'losses':l,'decided':n,'rate':w/n})
 assert counts[0]['wins']+counts[1]['wins']==counts[2]['wins'];assert counts[0]['losses']+counts[1]['losses']==counts[2]['losses'];assert counts[2]['decided']==112
 B.append({'reported_namespace':'B-QB-OPPORTUNITY-PROFILE-INCREMENT-v1','arm_alias':cols[0],'category':'pass_cmp','OVER':counts[0],'UNDER':counts[1],'COMBINED':counts[2],'Brier':float(cols[4]),'eligible':112,'selected':112,'decided':112,'actual_weeks':[5,6,7,8],'games':56,'tier':'OWNER_LOCAL_TIMING_UNVERIFIED_ACTUAL_LINE_DIAGNOSTIC','raw_row_parity_by_C':False})
assert len(B)==4
(OUT/'B_COMPLETION_ARM_HEADLINE.json').write_text(json.dumps(B,indent=2)+'\n')
# Compact common-board reception headline contains every received applicable point product.
rec=[r for r in reception['summaries'] if r['view']=='FULL_A733' and r['source_panel']=='ALL' and r['week_view']=='ALL']
for row in leaf:
 if (row['view'],row['source'],row['week'])!=('FULL_A733','ALL','ALL'):continue
 sides={}
 for label,p in [('OVER','over'),('UNDER','under')]:
  w,l,n=(int(row[p+x]) for x in ['_w','_l','_n']);sides[label]={'wins':w,'losses':l,'decided':n,'rate':w/n,'selected':None}
 w,l,n=(int(row[k]) for k in ['total_w','total_l','total_n']);sides['COMBINED']={'wins':w,'losses':l,'decided':n,'rate':w/n,'selected':int(row['selected'])}
 rec.append({'candidate_id':row['method'],**sides,'eligible':int(row['eligible']),'unavailable':int(row['unavailable']),'states':{'UNKNOWN_PARTICIPATION':int(row['unknown'])},'games':int(row['games']),'weeks':list(range(1,8)),'source_panel':'ALL','evidence':'Samefixed667points;source-mixedownerlocalquote-timing-unverified diagnostic;no newC03profileprocedure'})
(OUT/'RECEPTION_ALL_RECEIVED_HEADLINE.json').write_text(json.dumps(rec,indent=2)+'\n')
result={'status':'PASS_PUBLIC_AGGREGATE_ARITHMETIC','A_reception_summaries':len(reception['summaries']),'A_reception_side_partitions':rec_checks[0],'A_reception_weekly_groups':rec_checks[1],'A_reception_paired_cells':len(reception['paired']),'A_C_leaf_table_cells':len(leaf),'A_ATT_summaries':len(attempts['scores']),'A_ATT_side_partitions':att_checks[0],'A_ATT_weekly_groups':att_checks[1],'A_ATT_paired_cells':len(attempts['paired_controls']),'B_completion_arms':len(B),'new_fits':0,'private_rows_regraded':0,'raw_identity_quote_timing_or_model_parity':'NOT_VERIFIED_BY_C','bootstrap_interval_endpoints':'Receivedownerintervals;notredrawn','new_C03_longer_replay':'NOT_IN_RECEIVED_PACKAGES;separatefromcompletedolderCpooled/Leafjoins','earlier_completion_join':'NOT_EXECUTED_IN_RECEIVED_PACKAGE;A88earlyoffers inventory+exactBoutputs needed;distinctfromcompletedATT'}
(OUT/'ARITHMETIC_REVIEW.json').write_text(json.dumps(result,indent=2)+'\n');print(result)
