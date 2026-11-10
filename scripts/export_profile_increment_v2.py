"""Publish a deterministic C research view of existing canonical C03 scores.

No model evaluation, fitting, grading or new selection occurs here. The qualified
numerical overlays preserve old R0 typed points and missingness corrections.
"""
from __future__ import annotations
import argparse,hashlib,json,lzma
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'reports/profile-increment-v2'
EXP=BASE/'experiment'
TARGET=ROOT/'docs/data/profile-increment-v2.json'
SCHEMA='C-PROFILE-INCREMENT-RESEARCH-v2'
LABELS={'R0':'R0 · unchanged Leaf','R1':'R1 · support and age','R2':'R2 · player values','R3':'R3 · receiving-defense values','P1':'Retained context P1 law','P2':'Retained context P2 law','E0':'Retained direct E0','ALWAYS_OVER':'Always-Over control','ALWAYS_UNDER':'Always-Under control','RETAINED_EARLIER_PREVALENCE_V8':'Earlier role prevalence control'}
ACTUAL_METHODS=[f'{arm}_{product}' for product in ['LAW','MEAN','MEDIAN'] for arm in ['R0','R1','R2','R3']]+['P1','P2','E0','ALWAYS_OVER','ALWAYS_UNDER','RETAINED_EARLIER_PREVALENCE_V8']

def read(path):
 b=Path(path).read_bytes();return json.loads(lzma.decompress(b) if str(path).endswith('.xz') else b)
def label(method):
 if method.startswith(('R0_','R1_','R2_','R3_')):
  arm,product=method.split('_');return LABELS[arm]+' / '+{'LAW':'exact-law direction','MEAN':'expected-mean direction','MEDIAN':'lower-median direction'}[product]
 return LABELS[method]

def build():
 sources=[]
 def load(path):
  p=Path(path);b=p.read_bytes();sources.append({'path':str(p.relative_to(ROOT)),'SHA256':hashlib.sha256(b).hexdigest()});return read(p)
 numerical=[];numeric_pairs=[];runs=[]
 for year in [2026,2025]:
  runs.append(load(EXP/f'RUN-{year}.json'))
  rows=load(EXP/f'QUALIFIED_NUMERICAL_SCORES-{year}.json.xz')
  for arm in ['R0','R1','R2','R3']:
   r=next(x for x in rows if x['scope']=='WR_TE' and x['cohort']=='ALL' and x['week']=='ALL' and x['method']==arm)
   keys=['season','method','eligible','available','known','unknown','unavailable','games','player_games','actual_weeks','median_MAE','mean_MAE','mean_MSE','mean_bias','hard_fallback','profile_covered_known','any_imputed_known']
   numerical.append({**{k:r.get(k) for k in keys},'label':LABELS[arm]})
  pp=load(EXP/f'NUMERICAL_PAIRED_CHANGES-{year}.json.xz')
  for a,b in [('R2','R0'),('R2','R1'),('R3','R2')]:numeric_pairs.append(next(x for x in pp if x['scope']=='WR_TE' and x['cohort']=='ALL' and x['candidate']==a and x['control']==b and x['metric']=='median_absolute_error'))
 actual=[];rows=load(EXP/'ACTUAL_LINE_SCORES.json.xz')
 for method in ACTUAL_METHODS:
  r=next(x for x in rows if x['scope']=='WR_TE' and x['cohort']=='ALL' and x['week']=='ALL' and x['method']==method)
  keys=['method','OVER','UNDER','COMBINED','eligible','unavailable','abstentions','states','games','player_games','weeks','coverage','Brier','log_loss','profile_covered','hard_fallback','evidence_tier']
  actual.append({**{k:r.get(k) for k in keys},'label':label(method)})
 offered=load(EXP/'QUALIFIED_OFFERED_NUMERICAL_SCORES.json.xz')
 offered=[{k:r.get(k) for k in ['method','eligible','available','known','unknown','median_MAE','mean_MAE','mean_MSE','mean_bias','any_imputed_known']} for r in offered if r['scope']=='WR_TE' and r['cohort']=='ALL' and r['week']=='ALL']
 pp=load(EXP/'PRODUCT_PAIRED_CHANGES.json.xz');pairs=[]
 for a,b in [('R1','R0'),('R2','R0'),('R2','R1'),('R3','R2')]:
  r=next(x for x in pp if x['scope']=='WR_TE' and x['cohort']=='ALL' and x['product']=='LAW' and x['candidate']==a and x['control']==b)
  pairs.append({k:r[k] for k in ['candidate','control','product','decided','candidate_wins','control_wins','win_change','change_pp','uncertainty','evidence']})
 current=load(BASE/'CURRENT_BASIC_INDEX.json');qualification=load(BASE/'CURRENT_QUERY_QUALIFICATION.json');defense=load(EXP/'DEFENSE_SNAPSHOT_INDEX.json');load(EXP/'METADATA_CORRECTION.json')
 assert current['counts']['forecast_admitted']==0 and current['counts']['offers']==0
 assert all(r['weeks']==[2,3] for r in actual)
 assert len(numerical)==8 and all(r['actual_weeks']==list(range(1,9)) for r in numerical)
 return {'schema':SCHEMA,'title':'Focused receiving player and defense increment','category':'rec','role_scope':'WR_TE','labels':LABELS,'generated_from_latest_run_UTC':max(r['created_UTC'] for r in runs),'evidence_tier':'TIMING_UNVERIFIED_LAST_RECORDED_ACTUAL_LINES;EXPOSED_CURRENT_VINTAGE_7DAY_RECONSTRUCTION','actual_period':'2026 Weeks 2–3 only','numerical_periods':['2026 Weeks 1–8','2025 Weeks 1–8'],'book':'Pinnacle','primary_releases':0,'original_issued_selections':0,'current_packets':0,'qualified_paper_picks':0,'decisions':{'actual_direction_probability_TopK_replacement':'CLOSE_RECIPE_NO_GAIN','numerical_increment':'INCONCLUSIVE'},'current_profile':{'basic_players':current['profile_rows'],'receiving_priority':current['counts']['receiving_priority'],'defense_teams':defense['profile_count'],'source_cutoff_UTC':current['current_source_cutoff_UTC'],'source_roster_week':qualification['source_week'],'event_week':qualification['event_week'],'gate':qualification['current_forecast_admission']},'actual_scores':actual,'numerical_scores':numerical,'offered_numerical_scores':offered,'actual_paired_changes':pairs,'numerical_paired_changes':numeric_pairs,'limitations':['Priority/top20 are workload cohorts, not best-prop rankings; this main table retains the broad WR/TE board.','New arms:278 selected/255 decided/23 unknown. R0:258 selected/255 decided/3 unknown plus20 unavailable. Extra unresolved forecasts do not add wins.','Only two actual-offer weeks. Eight numerical weeks qualify only duration for the exact numerical products; no probability/TopPicks inheritance.','Raw role/depth defense response is not opponent-adjusted talent. No alignment/all-route/coverage mechanism was tested.','Exposed reconstructed periods and dependent games/players; paired intervals are descriptive and unadjusted. No betting returns or confidence claim.'],'source_bindings':sources,'report_path':'reports/profile-increment-v2/experiment/README.md'}

def serialized():return (json.dumps(build(),ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n').encode()
def main():
 p=argparse.ArgumentParser();p.add_argument('--validate',action='store_true');args=p.parse_args();body=serialized()
 if args.validate:
  assert TARGET.read_bytes()==body,'PROFILE_INCREMENT_SERVED_DATA_MISMATCH'
  html=(ROOT/'docs/context.html').read_text();js=(ROOT/'docs/context.js').read_text()
  for element in ['profile-increment-status','profile-increment-actual','profile-increment-numerical','profile-increment-paired','profile-increment-current']:
   assert f'id="{element}"' in html and element in js,'PROFILE_INCREMENT_RENDER_CONTRACT_MISMATCH:'+element
  assert SCHEMA in js and 'data/profile-increment-v2.json' in js
  print('PROFILE_INCREMENT_CANONICAL_EXPORT_VALID',len(body));return
 TARGET.parent.mkdir(parents=True,exist_ok=True);TARGET.write_bytes(body);print('PROFILE_INCREMENT_CANONICAL_EXPORT_WRITTEN',len(body))
if __name__=='__main__':main()
