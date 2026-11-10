"""Append-only R0 metadata/point recovery view; immutable predictions unchanged.

Safe saved typed points and saved feature vectors fill descriptive fields that
were absent from the copied law templates. No law, point, side or grade is fitted
or changed; raw driver outputs remain recoverable and explicitly superseded here.
"""
import copy,gzip,hashlib,json,sys,zipfile
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'src'))
import receiving_increment_c03 as d

def feature_lookup(year):
 archive=ROOT/('artifacts/all12-rec-v2.1.zip' if year==2026 else 'artifacts/robustness-rec-v3.zip');result={}
 with zipfile.ZipFile(archive) as z:
  names=[n for n in z.namelist() if n.endswith('/rows.json.gz') and ('H-MULTI-P2_LEAF-E0_OP' in n if year==2026 else n.startswith('raw/rec/W'))]
  for name in names:
   for r in json.loads(gzip.decompress(z.read(name))):
    if r['season']==year and 1<=r['week']<=8:result[(r['game_id'],r['player_id'])]=r
 return result

def numerical_rows(year):
 rows=d.read(d.ART/f'NUMERICAL_ROWS-{year}.json.xz');lookup=feature_lookup(year)
 for r in rows:
  if r.get('R0') is None:continue
  old=lookup.get((r['game_id'],r['player_id']))
  if old:
   assert abs(r['R0']['mean']-old['mean'])<1e-12 and r['R0']['median']==old['median']
   r['R0']['any_imputed']=any(v is None or not np.isfinite(v) for v in old['features']);r['R0']['input_support_binding']='ORIGINAL_SAFE_SAVED_32FEATURE_VECTOR'
  else:assert 'any_imputed' in r['R0'],'R0_SUPPORT_UNKNOWN'
 return rows

def offer_rows():
 rows=d.read(d.ART/'ACTUAL_OFFER_ROWS.json.xz');points=d.baseline_points();features=feature_lookup(2026)
 for r in rows:
  if not r['method'].startswith('R0_'):continue
  old=points.get((r['game_id'],r['player_id']))
  if r['selected_side'] is None:
   assert r['status']=='UNAVAILABLE_FORECAST';continue
  assert old is not None,'SELECTED_R0_MISSING_ORIGINAL_TYPED_POINT'
  assert old['mean'] is not None and old['median'] is not None
  r['mean'],r['median']=old['mean'],old['median'];feature=features.get((r['game_id'],r['player_id']))
  assert feature is not None
  r['any_imputed']=any(v is None or not np.isfinite(v) for v in feature['features'])
  r['metadata_binding']={'typed_points':'C_RETAINED_LEAF_POINTS_W1_W7.json.gz','support':'Originalsafeall12Leaf32featurevector','new_inference':0}
  if r['method']!='R0_LAW':
   v=old['mean'] if r['method']=='R0_MEAN' else old['median'];side='OVER' if v>r['line'] else 'UNDER' if v<r['line'] else 'ABSTAIN'
   assert side==r['selected_side'],'ORIGINAL_POINT_DIRECTION_MISMATCH'
   if r.get('point') is not None:assert abs(v-r['point'])<1e-12
  for key in ['Brier','log_loss','infinite_log_loss']:
   if r['method']!='R0_LAW':assert key not in r
 return rows

def offered_numeric_rows():
 from context_identity_view_c01 import corrected_rows
 rr=offer_rows();source={r['offer_id']:r for r in rr if r['method']=='R1_LAW'};controls={m:{r['offer_id']:r for r in corrected_rows() if r['method']==m} for m in ['P1','P2']};out=[]
 for offer,c in source.items():
  row=dict(game_id=c['game_id'],player_id=c['player_id'],position=c['position'],season=2026,week=c['week'],actual=c['actual'],cohort=c['cohort'])
  for arm in ['R0']+d.ARMS:
   q=next(x for x in rr if x['offer_id']==offer and x['method']==arm+'_LAW')
   row[arm]={'mean':q['mean'],'median':q['median'],'any_imputed':q.get('any_imputed',False),'hard_fallback':q.get('hard_fallback',False),'profile_covered':q.get('profile_covered',False)} if q.get('mean') is not None else None
  for m in ['P1','P2']:
   q=controls[m].get(offer);row['CONTROL_CONTEXT_'+m]={'mean':q['mean'],'median':q['median'],'hard_fallback':q.get('fallback',False)} if q and q.get('mean') is not None else None
  out.append(row)
 return out

def main(year):
 rows=numerical_rows(year);scores=[]
 for co in ['ALL','priority','workload_top20']:scores+=d.point_summary(rows,['R0']+d.ARMS,year=year,cohort=co)
 d.write(d.OUT/f'QUALIFIED_NUMERICAL_SCORES-{year}.json.xz',scores)
 if year==2026:
  offnum=offered_numeric_rows();scores=[]
  for co in ['ALL','priority','workload_top20']:scores+=d.point_summary(offnum,['R0']+d.ARMS+['CONTROL_CONTEXT_P1','CONTROL_CONTEXT_P2'],year=2026,cohort=co,offered=True)
  for r in scores:
   if r['method'].startswith('CONTROL_'):
    r['any_imputed_known']=None;r['profile_covered_known']=None;r['support_state']='Exactretainedpoints,notnewinputsupportreconstruction'
  d.write(d.OUT/'QUALIFIED_OFFERED_NUMERICAL_SCORES.json.xz',scores)
  d.write(d.OUT/'METADATA_CORRECTION.json',dict(id='C03-R0-DESCRIPTIVE-METADATA-v1',raw_rows={'path':str((d.ART/'ACTUAL_OFFER_ROWS.json.xz').relative_to(ROOT)),'SHA256':d.sha(d.ART/'ACTUAL_OFFER_ROWS.json.xz')},view='reports/profile-increment-v2/experiment/qualified_metric_view.py:offer_rows,numerical_rows',reason='Retained exact-law templates omitted typed point fields; savedpoint projection omitted any-imputed flags. Recoverexactexistingpoints/features ratherthan report unavailable or falsecompletecoverage.',point_or_probability_or_side_or_grade_changes=0,raw_files_preserved=True,new_inference=0,new_fits=0,point_metrics_probabilities='N/A',qualified_offered_R0_WRTE_known=next(r['known'] for r in scores if r['scope']=='WR_TE' and r['cohort']=='ALL' and r['week']=='ALL' and r['method']=='R0')))
 print('QUALIFIED_METADATA_VIEW',year)
if __name__=='__main__':main(int(sys.argv[1]) if len(sys.argv)>1 else 2026)
