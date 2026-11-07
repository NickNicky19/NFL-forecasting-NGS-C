"""Publish qualified source definitions and research views from common rows."""
import csv,gzip,hashlib,json,zipfile
from pathlib import Path
from collections import Counter
import numpy as np
import pandas as pd
from context_experiment_c01 import ROOT,read,write,sha,now
from context_sources_c01 import pbp_path

OUT=ROOT/'reports/player-context-matchup-01';SRC=ROOT/'sources/player-context-matchup-01'
def build():
 inventory=read(OUT/'FTN_INVENTORY.json');source=read(SRC/'SOURCE_MANIFEST.json');coverage=[]
 for item in source['sources']:
  for week,v in item['weeks'].items():coverage.append(dict(source='PBP ordinary facts',season=item['season'],week=int(week),rows=v['rows'],games=len(v['games']),field_group='down,distance,fieldposition,destination,depth,signedgains,GSIS',availability='Current-vintage kickoff+7day reconstruction',rights='CC BY4',alignment='NO',route_denominator='NO'))
 joins=[]
 pbp=pd.concat([pd.read_csv(pbp_path(year),low_memory=False) for year in [2025,2026]])
 pbpkeys={(r.game_id,str(int(r.play_id))) for r in pbp.itertuples()}
 for item in inventory['sources']:
  p=SRC/f"ftn_charting_{item['year']}.csv.gz";frame=pd.read_csv(p if p.exists() else p.with_suffix('.xz'),low_memory=False)
  keys=[(r.nflverse_game_id,str(int(r.nflverse_play_id))) for r in frame.itertuples()]
  joins.append(dict(season=item['year'],rows=len(frame),duplicate_native_play_keys=len(keys)-len(set(keys)),matched_to_retained_PBP=sum(k in pbpkeys for k in keys),unmatched_to_PBP=sum(k not in pbpkeys for k in keys),unmatched_reason='PBP projection excludesnonoffensiveplays/postseason;2026snapshotstopsW8beforeMonday;FTNincludeslaterandpostseasonrows;unknownremainingrequiresownerjoinqualification',catchable_values={str(k):int(v) for k,v in frame.is_catchable_ball.value_counts(dropna=False).items()},catchability_definition='Generallyontargetthrownotdefendedaway;notcompletionorCP',fields_without_receiver_alignment=['starting_hash isballhash','qb_location isQBposition','n_offense_backfield isteamcount','is_motion isplayflag'],live_viability='Chartingdocumentedwithin48h;currentrevisionpinsarenotoriginalpublicationclock'))
  for week,v in item['weeks'].items():coverage.append(dict(source='FTN charting',season=item['year'],week=int(week),rows=v['rows'],games=len(v['games']),field_group='29chartedfields/catchable,contested,drop,screen,playmotion,box,passrush',availability='Documented48haftergame;historicalversionsnotauthenticated',rights='CC BY-SA4 (FTNData via nflverse)',alignment='NO',route_denominator='NO'))
 write(OUT/'FIELD_SOURCE_COVERAGE.json.gz',dict(created_UTC=now(),coverage=coverage,ftn_join_diagnostics=joins,source_blockers=[dict(group='WR_TE_ALIGNMENT_ALL_ROUTES',state='SOURCE_BLOCKED',required='ReceiverGSIS/play/routeparticipationincludinguntargetedroutes;slot/outside,inline/wing/backfield,andmotionreceiverlabels;definition/clock/rights',available_proxy='Earlier targeted depth/down/distance/redzone and targetsperteamattempt;notalignment'),dict(group='FTN_PARTICIPATION_LIVE',state='SOURCE_BLOCKED_FOR_INSEASON',required='Cutoffqualifiedinseasonarchive;documented2023onwardFTNparticipationispostseasononly',charting_is_separate=True),dict(group='NGS_SEPARATION_CONTEXT',state='NOT_NEWLY_QUALIFIED',required='Permitted compatible play/targetcontext/metricdenominatorandmeasurement/revisionclock;existingweeklytargetedseparationdoesnotgiveallrouteopenness',prior_failed_recipes='Preserved;noequivalentrefit')]))
 with (OUT/'FIELD_SOURCE_COVERAGE.csv').open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(coverage[0]));w.writeheader();w.writerows(coverage)
 schema=read(OUT/'v1.1/INPUT_SCHEMA.json');schema['zero_context_limitation']='ctx_missing means NO_POSITIVE_TARGET_CONTEXT. For272queries(108in2026),knownzero-targetvolume counts remain0 but derived volume ratios omitted asNaN with qualityrates;notunknownsourceorDNP. Representationunchangedinsavedfits.';write(OUT/'EXPORTED_INPUT_SCHEMA.json',schema)
 runs=read(OUT/'v1.1/RUN.json');export=dict(id='C-PLAYER-CONTEXT-MATCHUP-01-EXPORT-v1.1',owner='C',created_UTC=now(),code_commit='Set by immutable export-index producer commit',contract='Existing ABC-ACTUAL-PROP-CHAMPIONSHIP-v2-C-1',rights=dict(PBP='CCBY4 ordinaryfactualprojectionwithattribution',FTN='CCBYSA4 annotatedchartingprojection;FTNData via nflverse;separatefromparticipation',features='C numerical derived features;no route/alignment or authenticated as-of claims'),receiver_feature_export=dict(path='artifacts/player-context-matchup-01/v1.1/FEATURE_EXPORT.json.gz',SHA256=sha(ROOT/'artifacts/player-context-matchup-01/v1.1/FEATURE_EXPORT.json.gz'),fields='Own-player/opponentandpredictedmixinteractions,GSIS/event/team/role/cutoff;outcomesabsent'),source_files=[dict(path=str(p.relative_to(ROOT)),SHA256=sha(p),bytes=p.stat().st_size) for p in sorted(SRC.iterdir()) if p.is_file()],metadata_archive=dict(path='reports/player-context-matchup-01/SOURCE_METADATA.zip',SHA256=sha(OUT/'SOURCE_METADATA.zip'),index='reports/player-context-matchup-01/SOURCE_METADATA_INDEX.json'),models=runs['models'],admission='PREPARED_PUBLIC_SOURCE_FEATURE_EXPORT;NOT_ASSUMED_A_B_RECEIVED_OR_PRODUCTION_ADMITTED',own_primary_release='NONE;no actual-line five-week qualification;negativecontextandweakprobabilityresults',ownership=dict(A='Rush direction/gap/down andallocation fits',B='QB/catchability/personalizationcoordinationandexactlineprobabilityfits',C='Receivingcontext/sourceexportandcommonintake'),new_grader=False)
 export['source_files']=[v for v in export['source_files'] if not v['path'].endswith('.csv.gz')]
 export['source_retention']='sources/player-context-matchup-01/RETENTION_V2.json;losslessCSVxzpackagingwithdecodedhashes;originalsourceversionspreserved'
 write(OUT/'OWNER_EXPORT.json',export)
 scores=read(OUT/'ACTUAL_LINE_SCORES.json.gz');num=read(OUT/'NUMERICAL_RESULTS.json.gz');old=read(ROOT/'reports/abc-championship/execution-closure-02/ACTUAL_LINE_HEADLINE.json');grade=read(ROOT/'prospective/outcomes/C-NATIVE-GRADE-20261107-JAXBAL-01/RUN.json')
 site=dict(schema='C-CONTEXT-RESEARCH-v1.1',generated_UTC=now(),actual_period='2026Weeks2–3',book='Pinnacle',evidence_tier='Timing-unverified last-recorded actual-line reconstruction;two exposed weeks',actual_scores=[s for s in scores if s['week']=='ALL' and s['method'] in ['E0','E1','E2','E3','P1','P2','P3','ALWAYS_OVER','ALWAYS_UNDER','RETAINED_EARLIER_PREVALENCE_V8']],numerical_scores=[s for s in num if len(s['actual_weeks'])==8],twelve_category_retained_status=old,sources=coverage,grade_summary=grade,primary_releases=0,qualified_paper_picks=0,source_blockers=['True receiver alignment/all-route denominator source blocked','NGScontextualseparationnotnewlyqualified','A/B newcontext comparisons not received'],GitHub_evidence='https://github.com/NickNicky19/NFL-forecasting-NGS-C/tree/main/reports/player-context-matchup-01')
 # Keep complete evidence in GitHub; the rendered payload carries its fields.
 keep=['method','label','scope','OVER','UNDER','COMBINED','eligible','states','unavailable','abstentions','mean_Brier','game_cluster_sensitivity95']
 site['actual_scores']=[{k:v for k,v in s.items() if k in keep} for s in site['actual_scores']]
 site['twelve_category_retained_status']=[dict(category=r['category'],state='UNCHANGED_SOURCE_SPECIFIC_PARENT_RECORD',evidence='reports/abc-championship/execution-closure-02/ACTUAL_LINE_HEADLINE.json') for r in old]
 site.pop('sources')
 write(ROOT/'docs/data/context-matchup-v1.json',site)
 return site
if __name__=='__main__':
 s=build();print('CONTEXT_SOURCE_EXPORT_AND_SITE_ROWS',len(s['actual_scores']))
