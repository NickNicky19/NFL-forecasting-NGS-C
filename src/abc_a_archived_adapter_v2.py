"""Source-bound A weekly aggregate adapter and exact own-decided-mask controls."""
import csv,gzip,io,json,hashlib,time,os
from pathlib import Path
from collections import defaultdict
from abc_championship_v2 import ROOT
OUT=ROOT/'reports/abc-championship/continuation-v2'
BASE=Path(os.environ.get('ABC_INTAKE',str(OUT/'intake')))
def emit(n,j):
 b=(json.dumps(j,separators=(',',':'),allow_nan=False)+'\n').encode();(OUT/n).write_bytes(gzip.compress(b,mtime=0) if n.endswith('.gz') else b)
def build():
 weekly=list(csv.DictReader(io.StringIO(gzip.decompress((BASE/'A-EACH_POINT_PRODUCTS_OWN_OVER_UNDER_BY_WEEK.csv.gz').read_bytes()).decode())));cum=list(csv.DictReader((BASE/'A-EACH_POINT_PRODUCTS_OWN_OVER_UNDER_W1_7.csv').open()));by=defaultdict(list)
 for x in weekly:by[(x['category'],x['method'],x['product'])].append(x)
 out=[];controls=[]
 for x in cum:
  key=(x['category'],x['method'],x['product']);ww=by[key];assert sorted(int(q['week']) for q in ww)==list(range(1,8))
  for side in ['over','under']:
   for k in ['wins','losses','decided','pushes','DNP','unresolved']:assert sum(int(q[side+'_'+k]) for q in ww)==int(x[side+'_'+k]),(key,side,k)
  assert sum(int(q['correct']) for q in ww)==int(x['total_correct']);assert sum(int(q['decided']) for q in ww)==int(x['total_decided'])
  ow,ol,uw,ul=[int(x[k]) for k in ['over_wins','over_losses','under_wins','under_losses']];n=ow+ol+uw+ul;assert n==int(x['total_decided']);assert abs((ow+uw)/n-float(x['hit_rate']))<1e-12 if n else True
  z=dict(session='A',source='A_FIXED_W1_W7_ARCHIVED_POINT_PANEL',period_id='E1',requested_weeks=list(range(1,9)),actual_weeks=list(range(1,8)),category=x['category'],procedure_id='A::'+x['category']+'::'+x['method']+'::'+x['procedure_version']+'::'+x['product'],method=x['method'],product=x['product'],history='ExactproducerboundhistorynotexpandedinCSV;seeAfinalistcatalog/config;notassumedMULTI',source_headline_eligible=x['headline_eligible']=='True',eligible=int(x['opportunities']),games=int(x['games']),no_lean=int(x['no_lean']),missing_offer_or_prediction=int(x['missing_offer_or_prediction']),unknown_participation=int(x['unknown_participation']),played_missing=int(x['played_missing']),OVER=dict(wins=ow,losses=ol,decided=ow+ol,rate=ow/(ow+ol) if ow+ol else None),UNDER=dict(wins=uw,losses=ul,decided=uw+ul,rate=uw/(uw+ul) if uw+ul else None),COMBINED=dict(wins=ow+uw,losses=ol+ul,decided=n,rate=(ow+uw)/n if n else None),settlement=x['settlement'],quote_timing=x['quote_timing'],rights='Publishedaggregateexportonly;Arawboardremainrestricted',scope='OWNER_LOCAL_AGGREGATE_ARITHMETIC_ADMISSION;NOT_CROWPARITY_OR_ORIGINAL_ISSUANCE',role_policy='QBpassing;RBprimaryrushing;RB/WR/TEreceiving;noQB+RBheadlineconflation',week_rows=ww)
  z.update(selected=z['eligible']-z['no_lean']-z['missing_offer_or_prediction'],scored_coverage=n/z['eligible'] if z['eligible'] else None,pushes=sum(int(x[t+'_pushes']) for t in ['over','under']),DNP=sum(int(x[t+'_DNP']) for t in ['over','under']),unresolved=sum(int(x[t+'_unresolved']) for t in ['over','under']))
  assert z['unresolved']==z['unknown_participation']+z['played_missing']
  assert z['eligible']==n+z['no_lean']+z['missing_offer_or_prediction']+z['unresolved']+z['pushes']+z['DNP']
  out.append(z);controls.append(dict(procedure_id=z['procedure_id'],category=x['category'],scope='OWN_SELECTED_DECIDED_POOL_ONLY;NOTFULL_ELIGIBLEBOARD_OR_NEW_POLICY',decided=n,original_wins=ow+uw,always_Over_wins=ow+ul,always_Under_wins=ol+uw,change_vs_best_constant=(ow+uw)-max(ow+ul,ol+uw),derivation='Overtruth=Overwins+Underlosses;Undertruth=Overlosses+Underwins;decidedonly'))
 emit('A_W1_W7_ARCHIVED_SCORES.json.gz',out);emit('A_W1_W7_OWN_MASK_CONSTANT_CONTROLS.json',controls)
 leaders=[]
 for c in sorted({x['category'] for x in out}):
  for side in ['OVER','UNDER','COMBINED']:
   rr=[x for x in out if x['category']==c and x[side]['decided']];best=max(x[side]['rate'] for x in rr);leaders.append(dict(category=c,side=side,raw_max=best,ties=[{k:x[k] for k in ['procedure_id','method','product','source_headline_eligible','eligible','games',side]} for x in rr if x[side]['rate']==best],best_supported='NOT_ESTABLISHED;sourcecommonmask/fullhistory/uncertaintyparitypending',period='2026W1-W7only',other_panels_not_comparable=True))
 emit('A_W1_W7_RAW_LEADERS.json',leaders)
 emit('A_W1_W7_RUN.json',dict(cumulative_views=len(out),weekly_views=len(weekly),weekly_cumulative_reconciled=True,new_fits=0,new_inference=0,independent_outcomes_added=0,source_raw_sha256=hashlib.sha256((BASE/'A-EACH_POINT_PRODUCTS_OWN_OVER_UNDER_W1_7.csv').read_bytes()).hexdigest(),source_weekly_sha256=hashlib.sha256((BASE/'A-EACH_POINT_PRODUCTS_OWN_OVER_UNDER_BY_WEEK.csv.gz').read_bytes()).hexdigest()))
 print('A_ARCHIVED_EXECUTED',len(out),len(weekly))
if __name__=='__main__':build()
