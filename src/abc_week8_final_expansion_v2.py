"""Append Monday labels to original C capture through the retained v4 grader. No fits."""
import csv,gzip,hashlib,io,json,math,shutil,time
from pathlib import Path
import pandas as pd
from collections import Counter
from contracts_v2 import CATEGORIES,WEIGHTS,RARE,SIGNED,integer,target,chart
from data_v2 import PHYSICAL
from forward_sources_v4 import Retriever,scoreboard_projection,stamp,write
from prospective_v4 import grade_run
from week8_grading_v9 import captures,ROOT,sha,read
ID='C-W8-FINAL-EXPANSION-20261104-v2-1'
# The identifier is a version label, not an issuance date; actual clocks below govern.
def build():
 start=time.monotonic();out=ROOT/'prospective/outcomes'/ID;assert not out.exists();tmp=Path('/workspace/c-abc-continuation/monday-final');retriever=Retriever(tmp,limit=2)
 b,statmeta=retriever.fetch('status','https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates=20261102&limit=100');ev=scoreboard_projection(json.loads(b),'MONDAY_FINAL',statmeta['observed_UTC']);assert len(ev)==1;event=ev[0];assert event['espn_event_id']=='401873036' and event['state']=='post' and event['completed'] and event['status_name']=='STATUS_FINAL'
 b,meta=retriever.fetch('stats','https://github.com/nflverse/nflverse-data/releases/download/stats_player/stats_player_week_2026.csv.gz');df=pd.read_csv(io.BytesIO(b),compression='gzip',low_memory=False);df=df[(df.season==2026)&(df.week==8)&(df.season_type=='REG')&(df.game_id=='2026_08_CHI_SEA')];assert not df.duplicated(['game_id','player_id']).any() and len(df)>0
 cols=list(dict.fromkeys(['player_id','game_id','team','opponent_team','position','season','week','season_type']+PHYSICAL+[x[1] for x in CATEGORIES.values() if x[1]]+list(SIGNED)+list(WEIGHTS)+['fumble_recovery_tds','special_teams_tds']));cols=[c for c in cols if c not in RARE];assert set(cols)<=set(df.columns);df=df[cols];facts={r['player_id']:r for r in df.astype(object).where(pd.notna(df),None).to_dict('records')}
 rows,proofs=captures();before=ROOT/'prospective/outcomes/C-W8-v9-20261102-003';packet=read(before/'OUTCOMES.json');old=packet['outcomes'];assert not any(r['game_id']=='2026_08_CHI_SEA' for r in old);new=[]
 for r in rows:
  if r['game_id']!='2026_08_CHI_SEA':continue
  assert r['espn_event_id']==event['espn_event_id'] and r['kickoff_UTC']==event['kickoff_UTC'];f=facts.get(r['player_id']);proof=[];appearance='UNKNOWN';actual=None;why=[]
  if f:
   assert f['team']==r['team'] and f['opponent_team']==r['opponent_team'];proof=[c for c in PHYSICAL if integer(f.get(c)) not in [None,0]]+[c for c in SIGNED if integer(f.get(c),True) not in [None,0]]
   if proof:appearance='PLAYED';actual=target(f,r['category'],True)
  if appearance=='UNKNOWN':why=['MISSING_OR_ALLZERO_STAT_NOT_DNP_OR_ZERO']
  elif actual is None:why=['MISSING_OR_RARE_COMPONENT_UNQUALIFIED']
  q=dict(game_id=r['game_id'],player_id=r['player_id'],category=r['category'],espn_event_id=r['espn_event_id'],kickoff_UTC=r['kickoff_UTC'],scoring_contract_id=r['scoring_contract_id'],event_status='FINAL',observed_UTC=meta['observed_UTC'],appearance=appearance,actual=actual,participation_proof_fields=proof,unavailable_reasons=why)
  if r['category']=='anytime_td' and appearance=='PLAYED':q['event_components']={k:integer(f.get(k)) for k in ['rushing_tds','receiving_tds']}
  if r['category']=='fpts' and actual is not None:
   comp={k:integer(f.get(k),k in SIGNED) for k in WEIGHTS if k not in RARE};comp.update({k:0 for k in RARE});assert f['fumble_recovery_tds']==0 and f['special_teams_tds']==0;assert sum(WEIGHTS[k]*v for k,v in comp.items())/50==actual
   q.update(score_components=comp,unique_event_credits_verified=True,unique_credit_proof=dict(native_player_game_row_unique=True,fumbles_lost='Oneofficialtotalnotcategoriesadded',two_points='DistinctproducerstatIDs77/75/104;ordinaryreceptions21/22',rare_TD='Explicitzerosupersets fumbleRecoveryTD0/STTD0',definition_reference='evidence/producer_calculate_stats.R'))
  new.append(q)
 assert len(new)==199;out.mkdir(parents=True);shutil.copytree(before/'evidence',out/'evidence');df.to_csv(out/'evidence/MONDAY_FACTS.csv',index=False);write(out/'evidence/MONDAY_STATUS_SOURCE.json',dict(event=event,status_source=statmeta,stat_source=meta,raw_player_rows=len(df),columns=cols,rights='MinimumNFLnumericalfacts underretainednflverseCCBY4; noNGS/EPA/CPOE/portraits/publisherfantasy/odds',sunday_labels='Original003Sundaylabelsandprovenanceunchanged;onlyMonday199appended'))
 packet.update(version=ID,created_UTC=stamp(),supersedes='C-W8-v9-20261102-003',outcomes=old+new,correction_scope='Append199Mondayoutcomes;Sunday003labelsretainedbyte-for-field;no originalforecastchanged');packet['source_evidence']=[dict(path=str(p.relative_to(out)),SHA256=sha(p),source='Original003qualifiedsourceevidence+newMondayminimalNFLfacts') for p in sorted((out/'evidence').iterdir())];write(out/'OUTCOMES.json',packet)
 grades=[];files=[]
 for run,receipt in proofs:
  path=ROOT/'prospective/grades'/(ID+'-'+run.name+'.json');g=grade_run(run,receipt,out/'OUTCOMES.json',path);grades+=g;files.append(dict(path=str(path.relative_to(ROOT)),SHA256=sha(path)))
 original={r['forecast_id']:r for r in rows};known={r['forecast_id']:r for r in grades};cat=[]
 for c in CATEGORIES:
  rr=[g for g in grades if g['category']==c];ok=[g for g in rr if g['state']=='GRADED_PLAYED'];num=[g for g in ok if g['absolute_error'] is not None];cat.append(dict(category=c,issued=len(rr),graded=len(ok),states=dict(Counter(g['state'] for g in rr)),median_MAE=sum(g['absolute_error'] for g in num)/len(num) if num else None,mean_RMSE=math.sqrt(sum(g['mean_squared_error'] for g in num)/len(num)) if num else None,CRPS=sum(g['CRPS'] for g in ok)/len(ok) if ok else None))
 result=dict(id=ID,created_UTC=stamp(),source_observed_UTC=meta['observed_UTC'],original_forecasts=2513,original_roster_candidates=407,captured_games=13,Week8_schedule_games=14,Thursday_not_captured=True,final_captured_games=13,new_Monday_outcome_views=199,old_Sunday_outcome_views=len(old),states=dict(Counter(g['state'] for g in grades)),categories=cat,grade_files=files,outcome_packet=str((out/'OUTCOMES.json').relative_to(ROOT)),outcome_SHA256=sha(out/'OUTCOMES.json'),original_pregame_actual_line_selections=0,qualified_C_actual_line_replays=0,forecast_only=True,old_grades_preserved=True,source_prior_versions_preserved=True,CMP_ATT_paper_blocks_preserved=True,fantasy_label_shadow_preserved=True,new_fits=0,wall_seconds=time.monotonic()-start,coverage_expansion_for_A_C='NewCactualcoverageavailable;Aownerstillneedsupdatedlabels,matchingprivateboard,guardremedy,andnewversion;noautomaticoverlapexpansionclaim')
 write(ROOT/'reports/abc-championship/continuation-v2/C_WEEK8_FINAL_FORECAST_GRADES.json',result);print('WEEK8_FINAL_CAPTURE_GRADED',result['states'])
if __name__=='__main__':build()
