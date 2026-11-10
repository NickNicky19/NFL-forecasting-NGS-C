"""Read-only parity against C's canonical context rows and common scorer."""
from collections import Counter
from context_experiment_c01 import ROOT,read
from context_report_c01 import group_score
from context_identity_view_c01 import corrected_rows
def validate():
 site=read(ROOT/'docs/data/context-matchup-v1.json');rows=corrected_rows();scores=read(ROOT/'reports/player-context-matchup-01/ACTUAL_LINE_SCORES.json.gz')
 assert site['schema']=='C-CONTEXT-RESEARCH-v1.1' and site['primary_releases']==site['qualified_paper_picks']==0
 assert len({(r['method'],r['offer_id']) for r in rows})==len(rows),'REPEATED_QUOTE_METHOD'
 assert all(r['category']=='rec' and r['season']==2026 and r['week'] in [2,3] and r['venue']=='pinnacle' for r in rows)
 roles={'ALL_SUPPORTED':['RB','WR','TE'],'WR_TE':['WR','TE'],'RB':['RB'],'WR':['WR'],'TE':['TE']}
 for s in site['actual_scores']:
  rr=[r for r in rows if r['method']==s['method'] and r['position'] in roles[s['scope']]];expected=group_score(rr)
  for k in ['OVER','UNDER','COMBINED','eligible','states','unavailable','abstentions','mean_Brier']:
   assert s[k]==expected[k],(s['method'],s['scope'],k)
 assert site['grade_summary']['states']=={'UNKNOWN':76,'GRADED_PLAYED':127}
 assert len(site['twelve_category_retained_status'])==12
 print('CONTEXT_CANONICAL_SERVED_INPUT_PARITY',len(site['actual_scores']),len(rows))
 # C03 is an export of canonical records, never another grader.
 if (ROOT/'docs/data/profile-increment-v2.json').exists():
  import subprocess,sys
  subprocess.run([sys.executable,str(ROOT/'scripts/export_profile_increment_v2.py'),'--validate'],check=True)
if __name__=='__main__':validate()
