"""No-fit diagnostic reuse, not a repair or a new evaluation period."""
from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'src'))
import receiving_timing_c04 as d
source=d.read(d.c03.ART/'ACTUAL_OFFER_ROWS.json.xz');rows=[]
for r in source:
 if r['method'] in ['R1_LAW','R2_LAW']:rows.append(d.rename_offer(r,'F0' if r['method']=='R1_LAW' else 'F1',d.POLICY7))
prob=d.reliability(rows)
broad=d.read(ROOT/'reports/profile-increment-v2/experiment/QUALIFIED_NUMERICAL_SCORES-2026.json.xz');offered=d.read(ROOT/'reports/profile-increment-v2/experiment/QUALIFIED_OFFERED_NUMERICAL_SCORES.json.xz')
num=[]
for label,src in [('BROAD_STAT_ROW',broad),('OFFERED_PLAYER',offered)]:
 for r in src:
  if r['scope']=='WR_TE' and r['cohort']=='ALL' and r['week']=='ALL' and r['method'] in ['R1','R2']:
   num.append({'population':label,'source_method':r['method'],'arm':'F0' if r['method']=='R1' else 'F1',**{k:r.get(k) for k in ['known','eligible','unknown','mean_MAE','median_MAE','mean_bias','hard_fallback','any_imputed_known','profile_covered_known']}})
examples=[]
for role in ['WR','TE','RB']:
 for state in ['WIN','LOSS','UNKNOWN_PARTICIPATION']:
  rr=sorted([r for r in rows if r['method']=='F0_LAW' and r['position']==role and r['status']==state],key=lambda r:r['offer_id'])
  if rr:
   r=rr[0];examples.append({k:r.get(k) for k in ['offer_id','game_id','player_id','position','week','line','mean','median','selected_side','probabilities','actual','status','any_imputed','profile_covered']})
out={'id':'C04-REUSED-OFFERED-POPULATION-DIAGNOSIS-v1','created_UTC':d.now(),'source_rows':{'path':str((d.c03.ART/'ACTUAL_OFFER_ROWS.json.xz').relative_to(ROOT)),'SHA256':d.sha(d.c03.ART/'ACTUAL_OFFER_ROWS.json.xz')},'real_evaluation_weeks':[2,3],'new_fits':0,'new_periods':0,'probability_diagnostics':prob,'broad_and_offered_numerical':num,'deterministic_examples':examples,'examples_rule':'First nativeofferID withinfixed WR/TE/RB xWIN/LOSS/UNKNOWN groups;no favorablecase selection','classifications':{'probability_quality':'MEASURED_WEAKNESS;Brier/confidence/rankingseparate,notcausaldiagnosis','latest_admitted_history':'MEASURED_COVERAGE_AGE_WEAKNESS fromDIAGNOSIS;accuracy-effectrequiresalignedtest','role_teammate':'UNRESOLVED_withoutqualifiedpregamevintages;no newroleadjustment','workload_conversion':'UNRESOLVED;directLeafhasnoidentifiedcomponentforecastdecomposition','profile_redundancy':'ClosedC03withinmethodresultsreused;columnsuseddoesnotproveincrementalsignal','implementation':'No new verifieddefect alleged bytheseaggregate diagnostics'},'exposure':'Already-inspectedoutcomes;groupingdiagnosis isexposeddevelopment,notrepairconfirmation','source_timing':'Unverifiedquoteclock;historicalrevisedfootballsource vintage notbackdated','hard_fallback_note':'Zero hardmodel fallback doesnotmeanallcontextpresent;5%rolepriorineverylawandorigin-onlyimputationremainexplicit'}
d.write(d.OUT/'RETAINED_DIAGNOSIS.json',out)
for x in prob:
 if x['scope']=='WR_TE' and x['week']=='ALL':print(x['method'],{k:x[k] for k in ['mean_selected_confidence','selected_accuracy','expected_wins','actual_wins','Brier','Over_AUC','confidence_correctness_AUC']})
